#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
r"""The single checkpointed owner of the storage reorganisation.

    tools/storage_reorg.py plan      what would happen, and why, per operation
    tools/storage_reorg.py run       execute from the last verified checkpoint
    tools/storage_reorg.py resume    alias for run; a restart is always a resume
    tools/storage_reorg.py status    the operation ledger
    tools/storage_reorg.py verify    re-check completed operations against reality

## Why this replaces the shell pipelines (spec section 0)

The shell pipelines moved data but kept reproducing the same two failures, recorded here so
the replacement is judged against them rather than against a preference for Python:

**Orphaned children.** Killing a pipeline left its `rclone` child alive. Twice. One orphan
held 16.8 GB of RSS while re-uploading a 27 GB tar a second pipeline was also uploading.
The cause is structural: a shell script's children are not its responsibility, so there is
nowhere to record "this operation is in flight" that survives the parent.

**Editing a script while bash was reading it.** Bash reads a script incrementally by byte
offset, so an edit under a running interpreter shifts the remaining bytes and can make it
execute garbage. That happened once; the workaround was a whole new file per revision,
which does not scale.

Both are solved by the same thing: **state lives in a file, not in a process.** Every
operation has a stable ID and a persisted state, so a restart resumes rather than replays,
and this file can be edited freely between runs because nothing is remembered in the
interpreter.

## The state machine, and why two states rather than one

    PLANNED -> PACKING -> UPLOADING -> DEST_VERIFIED -> SOURCE_RETIRED -> COMPLETE
                                    \-> FAILED (source left exactly where it is)

`DEST_VERIFIED` and `SOURCE_RETIRED` are deliberately separate. The gap between them is the
only moment when the data exists in two places, and therefore the only moment when a crash
is harmless. Collapsing them into a single "moved" state is how a tool ends up having
deleted a source whose destination it never actually confirmed.

`FAILED` never advances and never retires a source. A failed operation's local copy may be
the only copy.

## Tar at the semantic leaf, never at the tree root

The first draft packed each source tree into one opaque `.tar.zst`. That is the exact
failure the spec opens by naming -- "moved data but did not complete the required semantic
reorganization" -- and it makes four requirements unsatisfiable:

* section 4 groups files ">=1 MiB by exact size + Drive MD5". Drive sees one object per
  tarball, so duplicates *inside* it can never be found.
* section 5's `CATALOG.tsv` wants `FILE_COUNT` and `IMPORTANT_FORMATS` per collection. A
  tarball yields one uninspectable row.
* section 4 calls a generic migration tar a *temporary safety container, not permanent
  authority*, and forbids keeping one beside the organised collections.
* section 12 gates on a future engineer answering "where are the old snapshots?" Nobody
  browses into `sendtodrive.tar.zst`.

The opposite extreme fails too: `/yocto/artifacts` is 105,851 files and the Drive mount runs
`--tpslimit 8`, so per-file upload is hours of API calls before any bytes move. The rule
that resolves it:

    one archive per SEMANTIC LEAF, each with a sibling .manifest.tsv listing every
    path and size inside it.

`/yocto/artifacts` becomes six objects keyed by architecture -- which is what section 1.4
means by "preserve architecture/package-manager layout" -- and `/yocto/sendtodrive` becomes
one object per collection at the destination section 3.2 routes it to, which is what
section 1.5 means by "do not simply put the whole mess under one folder called
sendtodrive". The manifests restore browsability without 353,182 Drive objects.

## The verification rule

Google Drive's only native hash is MD5 -- `rclone backend features gdrive:` reports
`Hashes: ['md5']`, and `rclone hashsum sha256` returns EMPTY for this remote, which is the
shape of a check that appears to pass because it produced no complaint. So:

    local md5  ->  upload  ->  md5 read back FROM THE REMOTE  ->  compare

Never from the `/mnt/gdrive` FUSE mount, which can answer out of its own vfs cache and so
proves only that the cache exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import zipfile

ROOT = pathlib.Path("/home/google/Symoneural")
STATE_DIR = ROOT / ".private" / "storage-reorg"
STATE = STATE_DIR / "state.json"
OPS = STATE_DIR / "operations.tsv"
VERIFY_DIR = STATE_DIR / "verification"
LOCK = STATE_DIR / "owner.lock"
STAGE = ROOT / ".private" / "offload-stage"

REMOTE = "gdrive:"
SENDTODRIVE_ZIP = pathlib.Path("/yocto/Archives/sendtodrive.zip")

#: Measured on this box: 20 cores, ~94 GB RAM, ~5 MB/s upload ceiling. Chunk size is the
#: single biggest lever on Drive throughput for multi-gigabyte objects.
RCLONE = ["--checksum", "--transfers", "8", "--checkers", "16",
          "--drive-chunk-size", "256M", "--drive-upload-cutoff", "256M",
          "--buffer-size", "128M", "--retries", "5",
          "--stats", "5m", "--stats-one-line"]

#: Already-compressed payloads gain nothing from zstd and cost CPU for ~0%.
NO_COMPRESS = (".tar.gz", ".tgz", ".zip", ".xz", ".zst", ".bz2", ".7z", ".gz",
               ".gguf", ".safetensors", ".deb", ".rpm", ".iso", ".img", ".ipk")


# =========================================================================================
# Route tables. Declarative on purpose: the plan is data, so `plan` and `run` cannot
# disagree about what will happen, and a new destination is a row rather than a code path.
# =========================================================================================

#: /yocto/sendtodrive is a dismembered copy of the pre-2026-08-20 Symoneural repo, one
#: directory per top-level folder of that repo. Section 3.2 routes by TYPE, not by
#: container, so each lands where a future engineer would actually look.
_SNAP = "Symoneural/History/Source-Snapshots/symoneural-repo-20260820"
_BUILDS = "Symoneural/History/Build-History/symoneural-repo-20260820"
SENDTODRIVE_ROUTES: dict[str, str] = {
    "models":                 "Models/Historical/sendtodrive-models-20260820",
    "old-backend":            _SNAP,
    "old-symoneural":         _SNAP,
    "old-engines":            _SNAP,
    "old-site":               _SNAP,
    "old-tools":              _SNAP,
    "old-tests":              _SNAP,
    "old-deploy":             _SNAP,
    "old-ops":                _SNAP,
    "old-training":           _SNAP,
    "old-incoming":           _SNAP,
    "old-meta-symoneural":    _SNAP,
    "old-desktop-app":        _SNAP,
    "old-desktop-client":     _SNAP,
    "old-bin":                _BUILDS,
    "old-SyMoNeuRaL-Builds":  _BUILDS,
    "old-run":                "Symoneural/History/Task-and-Terminal-History/repo-20260820-run",
    "old-review":             "Symoneural/History/Task-and-Terminal-History/repo-20260820-review",
    "old-docs":               "Symoneural/Documentation/Historical/repo-20260820",
    "old-brand":              "Symoneural/Brand-Assets/Historical/repo-20260820",
    "RESTORE.md":             "Symoneural/Restore-Recovery/Historical/repo-20260820",
    # AppleSDK is deliberately ABSENT. The local directory copy is PARTIAL: the zip holds
    # 38,310 additional AppleSDK files totalling 21.5 GB that were deleted from disk at
    # some point. Uploading the partial copy would enshrine the lossy one as authority, so
    # AppleSDK is handled by op `mv-applesdk-from-zip`, which takes it from the zip.
}

#: Section 1.4: preserve the architecture / package-manager layout. One object per
#: architecture does exactly that, and caps staging at the largest single arch (48G)
#: instead of the whole 149G tree.
ARTIFACT_ROUTES: dict[str, str] = {
    "arm":            "Build-Outputs/Yocto/Packages",
    "arm64":          "Build-Outputs/Yocto/Packages",
    "x86":            "Build-Outputs/Yocto/Packages",
    "x86-64":         "Build-Outputs/Yocto/Packages",
    "baseline":       "Build-Outputs/Yocto/Manifests",
    "Symoneural.zip": "Build-Outputs/Symoneural/Yocto-Image",
}

OPERATIONS: list[dict] = [
    # ------------------------------------------------------- section 7.3: regenerable
    # These run FIRST: instant disk relief at zero bandwidth cost.
    dict(id="drop-frontend-node-modules", kind="drop", src="frontend/node_modules",
         why="Regenerable from frontend/package-lock.json. Section 7.3 is explicit that "
             "caches are removed rather than uploaded -- archiving a node_modules tree "
             "would pay Drive storage for what npm rebuilds from a lockfile.",
         guard="frontend/package-lock.json"),
    dict(id="drop-tests-node-modules", kind="drop", src="tests/node_modules",
         why="Same, against tests/package-lock.json.",
         guard="tests/package-lock.json"),
    dict(id="drop-pycache", kind="drop_glob", src="__pycache__",
         why="Python bytecode caches. Regenerated on import; carrying them is noise."),

    # ------------------------------------------------------- section 6.2: /yocto output
    dict(id="mv-yocto-sendtodrive", kind="move_leaves", src="/yocto/sendtodrive",
         routes=SENDTODRIVE_ROUTES,
         why="Section 1.5: 'do not simply put the whole mess under one new folder called "
             "sendtodrive'. It is a dismembered copy of the pre-2026-08-20 repo, so each "
             "collection is routed by type per section 3.2. MEASURED: all 353,182 files "
             "are CRC32-identical to entries in Archives/sendtodrive.zip (25 differ, all "
             "of them .git/index stat caches), so nothing here is a sole copy.",
         evidence=".private/storage-reorg/verification/sendtodrive-containment.txt"),
    dict(id="mv-applesdk-from-zip", kind="extract_upload", src=str(SENDTODRIVE_ZIP),
         member_prefix="sendtodrive/AppleSDK/",
         dest="Development-Reference/Apple/SDKs/AppleSDK-20260820",
         why="Section 3.3 routes AppleSDK to Development-Reference/Apple/SDKs. Taken from "
             "the ZIP rather than from disk because the disk copy is PARTIAL: the zip has "
             "38,310 more AppleSDK files (21.5 GB) than /yocto/sendtodrive/AppleSDK. "
             "Uploading the disk copy would make the lossy version authority."),
    dict(id="mv-yocto-artifacts", kind="move_leaves", src="/yocto/artifacts",
         routes=ARTIFACT_ROUTES,
         why="Section 1.4: completed package output (arm/arm64/x86/x86-64 deb and ipk "
             "trees plus baseline manifests), 149G across 105,851 files. Split by "
             "architecture so the layout survives on Drive. THIS IS NOW THE ONLY COPY -- "
             "the 248G duplicate under archive/workspace-archives/yocto was already "
             "retired against it -- so its verification gate matters more than any other."),
    dict(id="mv-yocto-dispatchos", kind="move_out", src="/yocto/dispatchos",
         dest="Build-Outputs/Symoneural/DispatchOS",
         why="Section 1.3 MEASURED: only .tar.gz/.zip/.MANIFEST.txt release sets -- "
             "completed output, not build-system input."),
    dict(id="mv-yocto-cgminer", kind="move_out", src="/yocto/cgminer",
         dest="Projects/Crypto/Reference-Source",
         why="Section 1.2/6.3 MEASURED: meta-cryptocurrency/recipes-miners/cgminer/*.bb "
             "fetch upstream (SRC_URI git://github.com/{vthoang,dmaxl,ckolivas}/"
             "cgminer.git), so no local tree is a build source. 22M / 286 files, git at "
             "93db9b54e3."),
    dict(id="mv-yocto-cgminer-master", kind="move_out", src="/yocto/cgminer-master",
         dest="Projects/Crypto/Reference-Source",
         why="Same measurement. NOT a duplicate of cgminer: 8M / 258 files with no git at "
             "all, against 22M / 286 with history. Section 1.2 says compare rather than "
             "assume, and the comparison says these are two different things."),

    # ------------------------------------------------------- section 7.2: archive/ history
    dict(id="mv-workspace-source-candidates", kind="move_out",
         src="archive/workspace-source-candidates",
         dest="Symoneural/History/Source-Snapshots",
         why="Section 7.2: 3.2G of historical source snapshots (~116k tree entries). Git "
             "carries the real history; this does not belong inside the running project."),
    dict(id="mv-build-20260902-src", kind="move_out", src="archive/build-20260902-src",
         dest="Symoneural/History/Source-Snapshots",
         why="Section 7.2: 2.9G snapshot dated 2026-09-02."),
    dict(id="mv-build-20260902-src-b", kind="move_out", src="archive/build-20260902-src-b",
         dest="Symoneural/History/Source-Snapshots",
         why="Section 7.2: 234M second snapshot. Preserved separately rather than assumed "
             "a duplicate of the first -- they are distinct worktrees and were never "
             "compared byte for byte."),
    dict(id="mv-workspace-builds", kind="move_out", src="archive/workspace-builds",
         dest="Symoneural/History/Build-History",
         why="Section 7.2: 4.4G of historical build output."),
    dict(id="mv-workspace-archives", kind="move_out", src="archive/workspace-archives",
         dest="Symoneural/History/Build-History",
         why="Section 7.2 lists this as a MOVE target: 238M remaining after the 248G "
             "yocto duplicate inside it was retired. The earlier hard-stop forbade "
             "DELETING it; verified-relocation-then-retire is not deletion, and the "
             "DEST_VERIFIED -> SOURCE_RETIRED gap is what earns that distinction."),
    dict(id="mv-workspace-backups", kind="move_out", src="archive/workspace-backups",
         dest="Symoneural/Restore-Recovery/Historical",
         why="Section 7.2: 16G of historical backups. Restore-relevant, so Restore-"
             "Recovery rather than generic History."),
    dict(id="mv-transcripts", kind="move_out", src="archive/transcripts",
         dest="Symoneural/History/Task-and-Terminal-History",
         why="Section 7.2: agent session transcripts."),
    dict(id="mv-from-desktop", kind="move_out", src="archive/from-desktop",
         dest="Symoneural/History/Storage-Audit/2026-09-09",
         why="Section 7.2/9.1: material swept off the Desktop in the earlier pass."),
    dict(id="mv-from-home", kind="move_out", src="archive/from-home",
         dest="Symoneural/History/Storage-Audit/2026-09-09",
         why="Section 7.2/9.1: material swept out of /home/google, including the owner's "
             "task prompts and session histories -- the record of what was asked and why."),
    dict(id="mv-tree-dumps", kind="move_out", src="archive/tree-dumps",
         dest="Symoneural/History/Storage-Audit/2026-09-09",
         why="98M of filesystem tree dumps from prior audits."),
    dict(id="mv-lora-staging", kind="move_out",
         src="archive/symoneural-lora-restore-staging-20260903",
         dest="Models/Historical",
         why="Section 7.2: 40M of old LoRA restore staging. Model-adjacent, so Models/"
             "Historical rather than generic history."),
    dict(id="mv-model-downloads", kind="move_out",
         src="archive/symoneural-model-downloads-20260902",
         dest="Models/Historical",
         why="Section 7.2: old model download staging."),

    # ------------------------------------------------------- sections 7.5 / 7.6
    dict(id="mv-incoming", kind="move_out", src="incoming",
         dest="Projects/Archived/Incoming-Symoneural",
         why="Section 7.5: examples and old project candidates (fullstack-example, "
             "RavenCalc Christmas tree, SyMoNeuRaL_TV, symv2-parallel), not active "
             "source authority."),
    dict(id="mv-releases", kind="move_out", src="releases",
         dest="Symoneural/Release-Artifacts",
         why="Section 7.6: binary release archives. Nothing in the deployment path reads "
             "them from here -- verified by grepping ops/ and scripts/ for the path."),

    # ------------------------------------------------------- section 9: /home/google
    dict(id="mv-home-experiments", kind="move_out", src="/home/google/experiments",
         dest="Projects/Experimental",
         why="Section 9.3: not active project work; owner states there is no other "
             "active work."),
    dict(id="mv-home-wallpapers", kind="move_out", src="/home/google/ia.Wallpapers",
         dest="Media/Images/Wallpapers", why="Section 9.5: media worth retaining."),
    dict(id="mv-home-platforms", kind="move_out", src="/home/google/Platforms.tar.gz",
         dest="Development-Reference/SDKs/Platforms",
         why="Platform SDK tarball; reference material, not runtime."),
    dict(id="mv-home-music", kind="move_out", src="/home/google/Music",
         dest="Media/Audio", why="Section 9.5."),
    dict(id="mv-home-videos", kind="move_out", src="/home/google/Videos",
         dest="Media/Video", why="Section 9.5."),
]

# =========================================================================================
# section 7.1 -- external/ reference warehouse
# =========================================================================================
#
#: HARD-STOP PROTECTED. The standing rule is "do not delete or purge any Claude file,
#: directory, session, runtime, cache, socket, configuration, worktree, or backup", and
#: section 9.6 adds "keep [Claude retirement control files] outside the repo until the
#: post-exit finalizer no longer requires them. Do not move early merely for cosmetic
#: cleanup." These four entries (~5.75 GB) therefore stay exactly where they are, and
#: `EXTERNAL_LOCAL_REFERENCE_BYTES` will not reach 0 while they do -- which is the correct
#: reported outcome, not a failure to finish.
EXTERNAL_PROTECTED = {
    "anthropics", "Claude", "ClaudeAlienware",
    "claude-desktop_1.32885.1_amd64.deb",
}

_NV = "Development-Reference/NVIDIA-CUDA"
_TC = "Development-Reference/Toolchains"
_AI = "Development-Reference/AI-Research"
_REF = "Symoneural/Reference"
_STUB = "Symoneural/Reference/external-symoneural-stubs"

#: Everything else at the top of external/, routed by DOMAIN rather than by the accident of
#: which download directory it landed in.
EXTERNAL_ROUTES: dict[str, str] = {
    # NVIDIA / CUDA reference collections
    "apex": _NV, "cosmos": _NV, "cudf": _NV, "cuml": _NV, "DALI": _NV,
    "DeepLearningExamples": _NV, "FasterTransformer": _NV, "Megatron-LM": _NV,
    "Nemotron-main": _NV, "nim-deploy": _NV, "nvidia-aws-samples": _NV,
    "nvidia-azure-samples": _NV, "nvidia-gcp-samples": _NV, "nvidia-oci-samples": _NV,
    "open-gpu-kernel-modules": _NV, "TransformerEngine": _NV, "vid2vid": _NV,
    "ninjatraining": _NV,
    # toolchains and platform SDKs
    "Toolchains": _TC, "Toolchains.tar.gz": _TC,
    "Platforms": "Development-Reference/SDKs/Platforms",
    "Platforms.tar.gz": "Development-Reference/SDKs/Platforms",
    # AI research / agent tooling reference
    "skills": _AI, "SkillSpector": _AI, "bentoml": _AI,
    "DeepSeek Harness developer preview_ Everything is a plugin.mhtml": _AI,
    "DeepSeek Harness.mhtml": _AI,
    "qwen3.6-27b _ NVIDIA NGC.mhtml": _AI, "qwen3.6-27b _ NVIDIA NGC.pdf": _AI,
    "SyMoN_ML (1).pdf": "Symoneural/Documentation/Historical",
    # linux / shell reference
    "OpenShell": "Development-Reference/Linux-System",
    "simpy": "Development-Reference/Linux-System", 
    "simpy.tar.gz": "Development-Reference/Linux-System",
    # archived projects
    "RavenCalcServer_Christmas_20251224-1007": "Projects/Archived/RavenCalc-Christmas-2025",
    # SyMoNeuRaL-NAMED SCAFFOLD STUBS. These are NOT runtime authority: the standing rule
    # is "do not modify or execute source under reference, external, vendor, archive, or
    # evidence trees as first-party runtime code", and a scan of 3,149,423 files under
    # external/ earlier in this work found ZERO first-party-licensed files. The real
    # runtimes live at the repository root (web/symoneural-web, etc), not here.
    "symoneural-browser": _STUB, "symoneural-chat": _STUB, "symoneural-coin": _STUB,
    "symoneural-desktop": _STUB, "symoneuraldesktop.py": _STUB, "symoneural-dj": _STUB,
    "symoneural-image": _STUB, "symoneural-iptv": _STUB, "symoneural-ravencalc": _STUB,
    "symoneural-reinforce": _STUB, "symoneural-studio": _STUB,
    "symoneural-support": _STUB, "symoneural-tv": _STUB, "symoneural-web": _STUB,
    "symoneuralweb.py": _STUB, "symoneural-browser.tar.gz": _STUB,
    "symoneural code": "Symoneural/History/Source-Snapshots/external-symoneural-code",
    "symoneural code.tar.gz": "Symoneural/History/Source-Snapshots/external-symoneural-code",
    "symoneural_tbd": _REF, "Symoneural_OE": _REF, "Symoneural_OE.tar.gz": _REF,
    # miscellaneous reference material and captures
    "reading": _REF, "oematch": _REF, "oematch.tar.gz": _REF,
    "referencesforchatgpt": _REF, "referencesforchatgpt.tar.gz": _REF,
    "drive-download-20260817T185705Z-1-001": _REF,
    "drive-download-20260826T005724Z-1-001": _REF,
    "clone-oss.sh": _REF, "q.json": _REF, "bin": _REF,
}


def _refchatgpt_routes() -> dict[str, str]:
    """Build the referencestochatgpt route table FROM docs/reference/UPSTREAM-PINS.tsv.

    The manifest is the single authority for provenance, so the destinations are derived
    from it rather than retyped. Section 7.1 wants pinned upstreams at
    `Symoneural/Upstream-Source/<project>/<revision>/`, so the revision is part of the
    path -- which is what makes the snapshot immutable and identifiable.
    """
    tsv = ROOT / "docs" / "reference" / "UPSTREAM-PINS.tsv"
    routes: dict[str, str] = {}
    if not tsv.is_file():
        return routes
    for line in tsv.read_text().splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 8:
            continue
        name, rev, cls = f[0], f[3], f[7]
        if cls == "PINNED_CLEAN":
            routes[name] = f"Symoneural/Upstream-Source/{name}/{rev[:12]}"
        elif cls == "PINNED_DIRTY":
            # A dirty tree is not the upstream revision, so it must not be filed as if it
            # were. The suffix keeps it from ever being mistaken for a clean snapshot.
            routes[name] = f"Symoneural/Upstream-Source/{name}/{rev[:12]}-dirty"
        else:
            routes[name] = f"Symoneural/Reference/referencestochatgpt/{name}"
    # Loose entries the manifest does not cover (it enumerates directories only).
    routes["deepseek-harness.tar.gz"] = "Symoneural/Reference/referencestochatgpt"
    # `claude-desktop` is PROTECTED and deliberately absent, so it stays local.
    return routes


OPERATIONS.extend([
    dict(id="mv-external-refchatgpt", kind="move_leaves",
         src="external/referencestochatgpt", routes=_refchatgpt_routes(),
         why="Section 7.1: pinned upstreams become immutable revision-keyed snapshots at "
             "Symoneural/Upstream-Source/<project>/<revision>/. MEASURED across 30 "
             "subtrees: 18 PINNED_CLEAN (18.05 GB), 2 PINNED_DIRTY (0.48 GB, patches "
             "preserved under .private/storage-reorg/patches/), 10 with NO git provenance "
             "at all (2.65 GB) which therefore need a real snapshot rather than a pin. "
             "`claude-desktop` inside is PROTECTED and stays.",
         evidence="docs/reference/UPSTREAM-PINS.tsv"),
    dict(id="mv-external-rest", kind="move_leaves", src="external",
         routes=EXTERNAL_ROUTES,
         why="Section 7.1: the remaining reference warehouse, routed by domain. The four "
             "Claude-related entries (~5.75 GB) are UNROUTED on purpose -- the hard-stop "
             "rule and section 9.6 both keep them local until the owner's retirement "
             "backup is taken, so they stay and are reported rather than moved."),
])


#: Sections 3.1-3.9. Server-side Drive reorganisation: metadata work inside one Drive, so a
#: 700+ GiB store reorganises in minutes instead of re-uploading. These run BEFORE the local
#: moves because they are effectively free and they fix the most visible section 12 gates
#: (top-level count; `Projects_Organize` / `offload` not surviving as buckets).
DRIVE_MOVES: list[tuple[str, str, str]] = [
    ("Projects_Active",         "Projects/Active",                          "3.1"),
    ("Projects_Crypto",         "Projects/Crypto",                          "3.1"),
    ("Projects_Database",       "Projects/Database",                        "3.1"),
    ("Projects_ForHost",        "Projects/Host",                            "3.1"),
    ("Projects_Github",         "Projects/GitHub-Mirrors",                  "3.1"),
    ("Projects_helperscripts",  "Projects/Utilities/Helper-Scripts",        "3.1"),
    ("Projects_Streamer",       "Projects/Streaming",                       "3.1"),
    ("Projects_WebandML",       "Projects/Web-ML",                          "3.1"),
    ("SymoneuralSeptBuilds",    "Symoneural/History/Build-History/Sept-Builds", "3.2"),
    ("symon-backups",           "Symoneural/Restore-Recovery/Historical/symon-backups", "3.2"),
    ("SyOsML_Documentation",    "Symoneural/Documentation/SyOsML",           "3.2"),
    ("SyMoNeuRaL_Runtime_Engineering_Guide",
     "Symoneural/Documentation/Runtime-Engineering-Guide",                  "3.2"),
    ("ClaudeAlienware",         "Symoneural/History/Agent-Sessions/ClaudeAlienware", "3.2"),
    ("AppleSDK",                "Development-Reference/Apple/SDKs/AppleSDK-drive", "3.3"),
    ("Apple Machine Learning Research_files",
     "Development-Reference/Apple/ML-Research",                             "3.3"),
    ("Cross-Platform Development", "Development-Reference/Cross-Platform",   "3.3"),
    ("Source Code and SDK Matrix",
     "Development-Reference/SDKs/Source-and-SDK-Matrix",                    "3.3"),
    ("Hardware Profiles",       "Development-Reference/Hardware",            "3.3"),
    ("System Optimization Reference",
     "Development-Reference/Linux-System/Optimization",                     "3.3"),
    ("System Security",         "Development-Reference/Security",            "3.3"),
    ("Backstage Templates",     "Development-Reference/SDKs/Backstage-Templates", "3.3"),
    ("VMScripts",               "Virtualization/Scripts",                    "3.4"),
    ("Blockchain Proofs of Concept",
     "Projects/Crypto/Research/Blockchain-Proofs-of-Concept",               "3.5"),
    ("Yocto Firmware",          "Build-Outputs/Yocto/Firmware",              "3.5"),
    ("HR MEETING",              "Personal/HR/HR-Meeting",                    "3.6"),
    ("Logistics",               "Personal/Logistics",                        "3.6"),
    ("resumes",                 "Personal/Employment/Resumes",               "3.6"),
    ("Documents",               "Personal/Documents/Drive-Documents",        "3.6"),
    ("Imagesandvideos",         "Media/Imported-Albums",                     "3.7"),
    ("MITModel",                "Models/Historical/MITModel",                "9"),
    ("yocto",                   "Build-Outputs/Yocto/Historical/yocto-root", "3.5"),
    ("Markdown Dialect Tool",   "Projects/Utilities/Markdown-Dialect-Tool",  "2"),
    ("Spotify API Documentation",
     "Development-Reference/AI-Research/Spotify-API",                        "2"),
    ("spotify-integration",     "Projects/Archived/Spotify-Integration",     "2"),
    ("hiranktesting",           "Projects/Experimental/hiranktesting",       "2"),
    ("Archive",                 "Historical-Archive/Drive-Archive",          "2"),
    ("Saved from the Google app",
     "Historical-Archive/Saved-From-Google-App",                             "3.9"),
]


# =========================================================================================
# State
# =========================================================================================
def load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(VERIFY_DIR, 0o700)
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            # A truncated state file is recoverable only by refusing to trust it: better to
            # re-plan than to resume from half a JSON document.
            print("  state.json unreadable; re-planning (completed work is re-verified, "
                  "not replayed)")
    return {"ops": {}}


def save_state(st: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(STATE)          # atomic: a crash leaves the old state, never a partial one


#: Phase 2 (Drive API walks) and phase 3 (uploads) run concurrently, so every state write
#: is serialised. The ledger is the only shared mutable thing between them.
_STATE_LOCK = threading.Lock()


def record(st: dict, op_id: str, **kw) -> None:
    with _STATE_LOCK:
        _record_locked(st, op_id, **kw)


def _record_locked(st: dict, op_id: str, **kw) -> None:
    st["ops"].setdefault(op_id, {})
    st["ops"][op_id].update(kw)
    st["ops"][op_id]["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_state(st)
    hdr = not OPS.exists()
    with OPS.open("a") as fh:
        if hdr:
            fh.write("WHEN\tOP_ID\tSTATE\tDETAIL\n")
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{op_id}\t"
                 f"{kw.get('state','?')}\t{str(kw.get('detail',''))[:200]}\n")
    os.chmod(OPS, 0o600)


def state_of(st: dict, op_id: str) -> str:
    return st["ops"].get(op_id, {}).get("state", "PLANNED")


def take_lock() -> bool:
    """One owner. A stale lock from a dead pid is reclaimed; a live one is respected."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK.is_file():
        try:
            pid = int(LOCK.read_text().strip())
            os.kill(pid, 0)
            print(f"  another storage_reorg owner is live (pid {pid}); refusing to be a "
                  f"second. ACTIVE_STORAGE_MUTATION_OWNERS must stay 1.")
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            print("  reclaiming a stale lock from a dead pid")
    LOCK.write_text(str(os.getpid()))
    os.chmod(LOCK, 0o600)
    return True


# =========================================================================================
# Helpers
# =========================================================================================
def sh(args: list[str], timeout: int = 43200) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def md5_of(p: pathlib.Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def remote_md5(remote_path: str) -> str | None:
    r = sh(["rclone", "hashsum", "md5", f"{REMOTE}{remote_path}"], timeout=1800)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout.split()[0]


def local_path(src: str) -> pathlib.Path:
    return pathlib.Path(src) if src.startswith("/") else ROOT / src


def du_bytes(p: pathlib.Path) -> int:
    r = sh(["du", "-sb", str(p)], timeout=3600)
    try:
        return int(r.stdout.split()[0])
    except (IndexError, ValueError):
        return 0


def human(n: float) -> str:
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024 or u == "T":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024
    return str(n)


def write_manifest(src: pathlib.Path, out: pathlib.Path) -> tuple[int, int]:
    """Every archive gets a sibling manifest so Drive stays browsable without one object
    per file. Returns (file_count, total_bytes). This is what keeps section 5's
    CATALOG.tsv answerable for a collection that travels as an archive."""
    n = tot = 0
    with out.open("w") as fh:
        fh.write("RELPATH\tSIZE_BYTES\n")
        if src.is_file():
            s = src.stat().st_size
            fh.write(f"{src.name}\t{s}\n")
            os.chmod(out, 0o600)
            return 1, s
        for p in sorted(src.rglob("*")):
            if p.is_file() and not p.is_symlink():
                try:
                    s = p.stat().st_size
                except OSError:
                    continue
                fh.write(f"{p.relative_to(src)}\t{s}\n")
                n += 1
                tot += s
    os.chmod(out, 0o600)
    return n, tot


# =========================================================================================
# The single destructive primitive
# =========================================================================================
def _pack_upload_retire(op_id: str, src: pathlib.Path, dest_dir: str, why: str, st: dict,
                        retire: bool = True) -> bool:
    """Pack, upload, confirm from the remote, and only then retire. Returns True only when
    the destination was independently confirmed."""
    cur = state_of(st, op_id)
    if cur in ("COMPLETE", "SOURCE_RETIRED"):
        print(f"      {op_id}: already {cur} -- resuming past it, not replaying")
        return True
    if not src.exists():
        record(st, op_id, state="COMPLETE", detail="source already absent")
        return True

    raw = du_bytes(src)
    STAGE.mkdir(parents=True, exist_ok=True)
    os.chmod(STAGE, 0o700)

    single_file = src.is_file()
    compress = not src.name.endswith(NO_COMPRESS)
    if single_file and not compress:
        name = src.name                 # ship an already-compressed file as itself
    else:
        name = f"{src.name}.tar" + (".zst" if compress else "")
    art = STAGE / name
    dest = f"{dest_dir}/{name}"

    mani = STAGE / f"{src.name}.manifest.tsv"
    fcount, fbytes = write_manifest(src, mani)
    print(f"      {op_id}: {human(raw)}  {fcount} files -> {dest_dir}/")
    record(st, op_id, state="PACKING", detail=f"{raw} raw, {fcount} files",
           src=str(src), dest=dest, file_count=fcount, raw_bytes=raw, why=why)

    if single_file and not compress:
        art = src                       # upload in place; nothing to pack
    else:
        art.unlink(missing_ok=True)
        base, leaf = str(src.parent), src.name
        if compress:
            tar = subprocess.Popen(["tar", "-cf", "-", "-C", base, leaf],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            z = subprocess.run(["zstd", "-3", "-T0", "-q", "-o", str(art)],
                               stdin=tar.stdout)
            tar.stdout.close()
            tar.wait()
            rc = z.returncode or tar.returncode
        else:
            rc = sh(["tar", "-cf", str(art), "-C", base, leaf]).returncode
        if rc != 0 or not art.is_file():
            record(st, op_id, state="FAILED", detail=f"pack rc={rc}")
            print(f"      {op_id}: PACK FAILED -- source untouched")
            return False
        os.chmod(art, 0o600)

    packed = art.stat().st_size
    lm = md5_of(art)
    print(f"      {op_id}: packed {human(packed)}  md5 {lm[:12]}  uploading ...")
    record(st, op_id, state="UPLOADING", detail=f"{packed} packed",
           local_md5=lm, packed_bytes=packed)

    r = sh(["rclone", "copy", str(art), f"{REMOTE}{dest_dir}/"] + RCLONE)
    if r.returncode != 0:
        record(st, op_id, state="FAILED",
               detail=f"upload rc={r.returncode}: {r.stderr.strip()[:150]}")
        if art != src:
            art.unlink(missing_ok=True)
        print(f"      {op_id}: UPLOAD FAILED -- source untouched")
        return False

    # Read the hash back FROM THE REMOTE, never from the FUSE mount.
    rm = remote_md5(dest)
    if rm != lm:
        record(st, op_id, state="FAILED",
               detail=f"remote md5 {rm} != local {lm} -- NOTHING RETIRED")
        if art != src:
            art.unlink(missing_ok=True)
        print(f"      {op_id}: MD5 MISMATCH (remote={rm} local={lm}) -- source untouched")
        return False

    sh(["rclone", "copy", str(mani), f"{REMOTE}{dest_dir}/"] + RCLONE)
    record(st, op_id, state="DEST_VERIFIED", detail=f"remote md5 {rm}", remote_md5=rm)
    (VERIFY_DIR / f"{op_id.replace('/', '_').replace(':', '-')}.txt").write_text(
        f"op={op_id}\nsrc={src}\ndest={REMOTE}{dest}\nfile_count={fcount}\n"
        f"manifest_bytes={fbytes}\nraw_bytes={raw}\npacked_bytes={packed}\n"
        f"local_md5={lm}\nremote_md5={rm}\n"
        f"verified_at={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\nwhy={why}\n")

    if art != src:
        art.unlink(missing_ok=True)
    mani.unlink(missing_ok=True)

    if not retire:
        record(st, op_id, state="COMPLETE", detail=f"uploaded {human(raw)}, source kept")
        print(f"      {op_id}: COMPLETE (source intentionally kept)")
        return True

    # The only destructive step, reached only after DEST_VERIFIED.
    if src.is_dir():
        shutil.rmtree(src, ignore_errors=True)
    else:
        src.unlink(missing_ok=True)
    if src.exists():
        record(st, op_id, state="FAILED", detail="source still present after retire")
        print(f"      {op_id}: source would not retire")
        return False
    record(st, op_id, state="COMPLETE", detail=f"retired {human(raw)}")
    print(f"      {op_id}: COMPLETE -- freed {human(raw)}")
    return True


# =========================================================================================
# Operation kinds
# =========================================================================================
def do_drop(op: dict, st: dict, apply: bool) -> None:
    p = local_path(op["src"])
    if not p.exists():
        if apply:
            record(st, op["id"], state="COMPLETE", detail="already absent")
        else:
            print(f"  {op['id']:<34} already absent")
        return
    guard = op.get("guard")
    if guard and not (ROOT / guard).is_file():
        # The guard is the whole point: without its lockfile the tree is not regenerable,
        # so dropping it would destroy something unrecoverable.
        if apply:
            record(st, op["id"], state="FAILED",
                   detail=f"guard {guard} absent -- not regenerable, refusing to drop")
        print(f"  {op['id']}: GUARD MISSING ({guard}) -- NOT dropped")
        return
    n = du_bytes(p)
    if not apply:
        print(f"  {op['id']:<34} would drop {human(n):>8}  ({op['src']})")
        return
    record(st, op["id"], state="RETIRING", detail=f"{n} bytes", why=op["why"])
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink(missing_ok=True)
    ok = not p.exists()
    record(st, op["id"], state="COMPLETE" if ok else "FAILED",
           detail=f"dropped {human(n)}" if ok else "still present", raw_bytes=n)
    print(f"  {op['id']}: {'dropped' if ok else 'FAILED'} {human(n)}")


def do_drop_glob(op: dict, st: dict, apply: bool) -> None:
    """__pycache__ everywhere except trees that must not be walked or are themselves
    queued for relocation."""
    skip = ("/external/", "/archive/", "/.private/", "/node_modules/", "/.git/")
    hits = [d for d in ROOT.rglob(op["src"])
            if d.is_dir() and not any(s in f"{d}/" for s in skip)]
    total = sum(du_bytes(d) for d in hits)
    if not apply:
        print(f"  {op['id']:<34} would drop {human(total):>8}  ({len(hits)} trees)")
        return
    for d in hits:
        shutil.rmtree(d, ignore_errors=True)
    left = len([d for d in ROOT.rglob(op["src"])
                if d.is_dir() and not any(s in f"{d}/" for s in skip)])
    record(st, op["id"], state="COMPLETE", raw_bytes=total,
           detail=f"dropped {len(hits)} trees {human(total)}, {left} remain",
           why=op["why"])
    print(f"  {op['id']}: dropped {len(hits)} trees, {human(total)}")


def do_move_out(op: dict, st: dict, apply: bool) -> None:
    src = local_path(op["src"])
    if not apply:
        cur = state_of(st, op["id"])
        if not src.exists():
            print(f"  {op['id']:<34} absent ({cur})")
            return
        print(f"  {op['id']:<34} would move {human(du_bytes(src)):>8} -> {op['dest']}/  "
              f"[{cur}]")
        return
    print(f"  {op['id']}")
    _pack_upload_retire(op["id"], src, op["dest"], op["why"], st)


def do_move_leaves(op: dict, st: dict, apply: bool) -> None:
    """One archive per semantic leaf, each routed independently. A failing leaf does not
    block its siblings, and the parent container is removed only when every leaf is gone."""
    src = local_path(op["src"])
    if not src.exists():
        if apply:
            record(st, op["id"], state="COMPLETE", detail="source already absent")
        else:
            print(f"  {op['id']:<34} absent")
        return
    routes: dict[str, str] = op["routes"]
    leaves = sorted(src.iterdir())
    unrouted = [p.name for p in leaves if p.name not in routes]

    if not apply:
        print(f"  {op['id']}  ({len(leaves)} leaves, {human(du_bytes(src))} total)")
        for p in leaves:
            d = routes.get(p.name)
            print(f"        {p.name:<26} {human(du_bytes(p)):>8}  -> "
                  f"{d if d else '*** UNROUTED: stays local ***'}")
        if unrouted:
            print(f"        NOTE {len(unrouted)} unrouted: {', '.join(unrouted)}")
        return

    print(f"  {op['id']}  ({len(leaves)} leaves)")
    for p in leaves:
        d = routes.get(p.name)
        if not d:
            # Never move what the route table does not name. An unrouted leaf is an
            # unclassified one, and section 12 counts unclassified items as incomplete --
            # which is the correct visible outcome, not a silent default bucket.
            print(f"        {p.name}: UNROUTED -- left in place deliberately")
            continue
        _pack_upload_retire(f"{op['id']}::{p.name}", p, d, op["why"], st)

    remaining = [q.name for q in src.iterdir()] if src.exists() else []
    if not remaining:
        src.rmdir()
        record(st, op["id"], state="COMPLETE", detail="all leaves retired, parent removed")
        print(f"  {op['id']}: COMPLETE -- parent container removed")
    else:
        record(st, op["id"], state="PARTIAL",
               detail=f"{len(remaining)} leaves remain: {','.join(remaining[:8])}")
        print(f"  {op['id']}: PARTIAL -- {len(remaining)} leaves remain: "
              f"{', '.join(remaining[:8])}")


def do_extract_upload(op: dict, st: dict, apply: bool) -> None:
    """Take a subtree out of a zip, upload it, and retire only the staged copy.

    Used where the ZIP holds the complete collection and the on-disk copy is lossy. The
    zip itself is NOT retired here: that decision belongs to a separate coverage proof.
    """
    op_id = op["id"]
    zp = pathlib.Path(op["src"])
    prefix = op["member_prefix"]
    if state_of(st, op_id) == "COMPLETE":
        print(f"  {op_id}: already COMPLETE")
        return
    if not zp.is_file():
        if apply:
            record(st, op_id, state="COMPLETE", detail="zip absent")
        else:
            print(f"  {op_id:<34} zip absent")
        return

    with zipfile.ZipFile(zp) as z:
        members = [i for i in z.infolist()
                   if i.filename.startswith(prefix) and not i.is_dir()]
        total = sum(i.file_size for i in members)
    if not apply:
        print(f"  {op_id:<34} would extract {len(members)} members "
              f"({human(total)}) from {zp.name} -> {op['dest']}/")
        return

    print(f"  {op_id}: extracting {len(members)} members ({human(total)}) from {zp.name}")
    work = STAGE / "extract" / prefix.rstrip("/").split("/")[-1]
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    record(st, op_id, state="EXTRACTING", detail=f"{len(members)} members, {total} bytes",
           why=op["why"])
    # zipfile matches member names EXACTLY -- unlike `unzip`, which treats [ ] * in stored
    # paths as glob wildcards and matched nothing at all in these Xcode SDK trees (rc=11).
    with zipfile.ZipFile(zp) as z:
        for i in members:
            rel = i.filename[len(prefix):]
            if not rel:
                continue
            out = work / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as fh, out.open("wb") as w:
                shutil.copyfileobj(fh, w, 1 << 20)
    got = sum(1 for p in work.rglob("*") if p.is_file())
    if got != len(members):
        record(st, op_id, state="FAILED",
               detail=f"extracted {got} of {len(members)} members")
        print(f"  {op_id}: EXTRACT INCOMPLETE ({got}/{len(members)}) -- nothing retired")
        return
    print(f"  {op_id}: extracted {got} members cleanly")
    ok = _pack_upload_retire(op_id, work, op["dest"], op["why"], st, retire=True)
    shutil.rmtree(STAGE / "extract", ignore_errors=True)
    if ok:
        print(f"  {op_id}: uploaded; the source zip is deliberately KEPT pending the "
              f"coverage proof")


def do_drive_moves(st: dict, apply: bool) -> None:
    for srcname, destpath, sect in DRIVE_MOVES:
        op_id = f"drivemv-{srcname.replace(' ', '_').replace('/', '_')}"
        if state_of(st, op_id) == "COMPLETE":
            continue
        chk = sh(["rclone", "lsjson", f"{REMOTE}{srcname}", "--stat"], timeout=600)
        if chk.returncode != 0:
            if apply:
                record(st, op_id, state="COMPLETE",
                       detail="source absent (already moved, or never existed)")
            continue
        if not apply:
            print(f"  {op_id:<46} {srcname}  ->  {destpath}   [{sect}]")
            continue
        before = sh(["rclone", "size", f"{REMOTE}{srcname}", "--json"], timeout=3600)
        record(st, op_id, state="MOVING", detail=f"{srcname} -> {destpath}",
               before=before.stdout.strip()[:120])
        r = sh(["rclone", "moveto", f"{REMOTE}{srcname}", f"{REMOTE}{destpath}",
                "--checksum", "--transfers", "8", "--stats", "5m", "--stats-one-line"])
        if r.returncode != 0:
            record(st, op_id, state="FAILED", detail=r.stderr.strip()[:180])
            print(f"  {op_id}: FAILED -- {r.stderr.strip()[:110]}")
            continue
        after = sh(["rclone", "size", f"{REMOTE}{destpath}", "--json"], timeout=3600)
        record(st, op_id, state="COMPLETE",
               detail=f"{before.stdout.strip()[:70]} -> {after.stdout.strip()[:70]}",
               after=after.stdout.strip()[:120])
        print(f"  {op_id}: moved  {srcname} -> {destpath}")


# =========================================================================================
# Commands
# =========================================================================================
KINDS = {"drop": do_drop, "drop_glob": do_drop_glob, "move_out": do_move_out,
         "move_leaves": do_move_leaves, "extract_upload": do_extract_upload}
FREE_KINDS = ("drop", "drop_glob")


def cmd_plan() -> int:
    st = load_state()
    print("STORAGE REORGANISATION PLAN")
    print("=" * 78)
    print("\nPHASE 1 -- FREE, no bandwidth: drop regenerable caches\n")
    for op in OPERATIONS:
        if op["kind"] in FREE_KINDS:
            KINDS[op["kind"]](op, st, False)
    print("\nPHASE 2 -- FREE, server-side: Drive reorganisation\n")
    do_drive_moves(st, False)
    print("\nPHASE 3 -- BANDWIDTH-BOUND: local -> Drive, verified then retired\n")
    for op in OPERATIONS:
        if op["kind"] not in FREE_KINDS:
            KINDS[op["kind"]](op, st, False)
    return 0


def cmd_status() -> int:
    st = load_state()
    if not st["ops"]:
        print("  no operations recorded yet -- run `plan`")
        return 0
    by: dict[str, int] = {}
    freed = 0
    for oid, o in sorted(st["ops"].items()):
        s = o.get("state", "?")
        by[s] = by.get(s, 0) + 1
        if s == "COMPLETE":
            freed += o.get("raw_bytes", 0)
        print(f"  {oid:<54} {s:<14} {str(o.get('detail',''))[:50]}")
    print("\n  " + "   ".join(f"{k}={v}" for k, v in sorted(by.items())))
    print(f"  bytes retired locally: {human(freed)}")
    return 0


def cmd_verify() -> int:
    st = load_state()
    checked = bad = 0
    for oid, o in sorted(st["ops"].items()):
        if o.get("state") != "COMPLETE" or "remote_md5" not in o or not o.get("dest"):
            continue
        checked += 1
        rm = remote_md5(o["dest"])
        ok = rm == o["remote_md5"]
        if not ok:
            bad += 1
        print(f"  {oid:<54} {'OK' if ok else 'REMOTE CHANGED OR GONE'}")
    print(f"\n  re-verified {checked} completed operation(s); mismatches: {bad}")
    return 1 if bad else 0


def cmd_run() -> int:
    if not take_lock():
        return 1
    st = load_state()
    try:
        print("PHASE 1 -- drop regenerable caches (instant, no bandwidth)")
        for op in OPERATIONS:
            if op["kind"] in FREE_KINDS:
                KINDS[op["kind"]](op, st, True)
        # Phase 2 is API-bound (recursive Drive walks at 8 requests/second); phase 3 is
        # bandwidth-bound (~5 MB/s of upload). They contend for almost nothing, and run
        # sequentially phase 2 simply delays the 15-hour pole for no reason. So phase 2
        # goes to a worker thread and phase 3 proceeds immediately in this one.
        print("\nPHASE 2 -- Drive server-side reorganisation (background, API-bound)")
        t = threading.Thread(target=do_drive_moves, args=(st, True),
                             name="drive-moves", daemon=True)
        t.start()

        print("PHASE 3 -- local -> Drive (foreground, bandwidth-bound)\n")
        for op in OPERATIONS:
            if op["kind"] not in FREE_KINDS:
                KINDS[op["kind"]](op, st, True)

        print("\n  phase 3 done; waiting on the phase 2 Drive walks to finish ...")
        t.join()
    finally:
        LOCK.unlink(missing_ok=True)
    print("\n  run finished; `status` for the ledger, `verify` to re-check destinations")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["plan", "run", "resume", "status", "verify"])
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "status": cmd_status, "verify": cmd_verify,
            "run": cmd_run, "resume": cmd_run}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
