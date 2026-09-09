# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""HOME-DISPOSITION.tsv -- what happens to everything in /home/google at the reset.

The machine is being erased. Every top-level item outside the repository is therefore about
to be destroyed, and the only two acceptable states for each are: *represented under
/home/google/Symoneural*, or *deliberately let go*. What is not acceptable is the third
state -- unexamined -- because that is how somebody discovers after the wipe that the thing
they needed was a file nobody classified.

So each item gets a disposition, and the ones that must survive get a canonical location.

## What this file records and does not

**Names and sizes only.** No contents, no excerpts, no credential values. `providerapikeys.txt`
appears here as a row saying it was migrated; what was in it does not appear anywhere.

**The classification is a judgement and is written down as one.** A generator cannot know
whether `Pictures/` matters to the owner. What it CAN do is refuse to leave anything
unclassified, which is what `test_home_disposition_is_complete` enforces: an item on disk
with no row fails the build rather than being quietly skipped.

## Dispositions

    PROJECT_AUTHORITY   project material that must survive; names its canonical location
    HISTORY_EVIDENCE    records of how the project got here; survive as evidence
    CLAUDE_BACKUP       retirement backup material, already under .private/
    SECRET              credential-bearing; migrated to .private/secrets/
    DUPLICATE           the same bytes exist under the canonical root
    SUPERSEDED          replaced by something newer that IS preserved
    OWNER_PERSONAL      the owner's own files; theirs to decide, NOT swept by this session
    UNRELATED           not project material and not preserved here
    SYSTEM              a mount point or OS-managed path
"""
from __future__ import annotations

import pathlib

from lib import measure as M

ROOT = M.ROOT
HOME = pathlib.Path("/home/google")
NUL = "-"

#: (name, disposition, canonical_location_or_reason, note)
#:
#: Ordered by disposition so the table reads as a decision list rather than a directory
#: listing. Every entry carries WHY, because a disposition without a reason is the thing
#: this table exists to replace.
DISPOSITIONS: tuple[tuple[str, str, str, str], ...] = (
    # ---------------------------------------------------------------- must survive
    ("Symoneural", "PROJECT_AUTHORITY", "/home/google/Symoneural",
     "The canonical root. Everything below either lives here already or is judged against "
     "whether it needs to."),
    ("claude-preserve-list-20260908.txt", "PROJECT_AUTHORITY",
     "copied into .private/claude-backups/ by the finalizer",
     "Names every path the purge must not touch. Useless after the purge, essential "
     "before it."),
    ("claude-purge-allowlist-20260908.txt", "PROJECT_AUTHORITY",
     "copied into .private/claude-backups/ by the finalizer",
     "13 literal paths, zero globs. The only list the purge is permitted to consult."),
    ("claude-retirement-finalize-20260908-050000.sh", "PROJECT_AUTHORITY",
     "copied into .private/claude-backups/ by the finalizer",
     "The post-exit executor. Must be readable from outside the repository because it "
     "runs when this session is gone."),
    ("symoneural-information-scan.py", "PROJECT_AUTHORITY",
     "archive/from-home/symoneural-information-scan.py",
     "First-party scanning tool that never made it into the repository."),

    # ---------------------------------------------------------------- evidence
    ("claude-system-inventory-20260908-034644.txt", "HISTORY_EVIDENCE",
     ".private/claude-backups/20260908-035459/",
     "The pre-migration system inventory the owner asked for. Evidence of what was on the "
     "box before anything was moved."),
    ("claudelastrun.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "Session record. Mode 664 -- tightened on copy."),
    ("claudeterminalhistory.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "Terminal history the owner supplied as review material."),
    ("sanitycheck.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "The owner's review of what these three tasks were meant to accomplish. It is the "
     "statement of intent the work is judged against, so it travels."),
    ("autocontinuationprompt.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "Task instructions."),
    ("patchprompt", "HISTORY_EVIDENCE", "archive/from-home/", "Task instructions."),
    ("gptosspromptandsymoneuraldefaults.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "The GPT-OSS integration and owner storage-policy instructions. Carries the model "
     "house-naming rules, the original-upstreams-live-on-Drive decision and the balanced "
     "default-selection procedure -- owner decisions that are not derivable from the code."),
    ("someofthelineswerehiddeninpromptreadthis.md", "HISTORY_EVIDENCE",
     "archive/from-home/", "Task instructions."),
    ("productiondeployment.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "Deployment notes."),
    ("security-reverify-2026-09-03.md", "HISTORY_EVIDENCE", "archive/from-home/",
     "Security re-verification record."),
    ("symoneural-packaging-recovery-audit-2026-09-03.md", "HISTORY_EVIDENCE",
     "archive/from-home/", "Packaging audit."),
    ("symoneural-production-qualification-2026-09-03.md", "HISTORY_EVIDENCE",
     "archive/from-home/", "Production qualification record."),
    ("status.md", "HISTORY_EVIDENCE", "archive/from-home/", "Status snapshot."),
    ("makecudasamples.docx", "HISTORY_EVIDENCE", "archive/from-home/", "CUDA build notes."),
    ("Source code and binaries.docx", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored notes on source and binary handling."),
    ("Source code and binaries.pdf", "HISTORY_EVIDENCE", "archive/from-home/",
     "PDF of the above."),
    ("Source code for Model.docx", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored notes on model source."),

    # ---------------------------------------------------------------- claude
    ("claudebackup.zip", "CLAUDE_BACKUP", ".private/claude-backups/legacy/",
     "4.8 GB, mode 600. The EARLIER Claude backup, superseded by the verified "
     "20260908-035459 checkpoint but NOT deleted -- the owner's instruction is explicit "
     "that a newer checkpoint existing is not a reason to destroy an older one. Kept as a "
     "second, independent copy."),

    # ---------------------------------------------------------------- secret
    ("providerapikeys.txt", "SECRET", ".private/secrets/providerapikeys.txt",
     "MIGRATED 2026-09-08. Was mode 0664 -- world-readable -- and held 7 live provider "
     "credentials. Copied at 0600, size and SHA-256 verified on both sides, then the "
     "original was unlinked. Values were never read or printed. ROTATE AFTER RESTORE."),

    # ---------------------------------------------------------------- superseded
    ("symoneural-cutover-rollback-20260826-154113", "SUPERSEDED",
     "not carried -- superseded by Git history",
     "The 2026-08-26 web cutover rollback tree. The cutover succeeded and symoneural-web "
     "has been serving since; the rollback material is reconstructible from Git. Mode "
     "555 with root-owned files inside, which is a second reason not to drag it along."),
    ("AI_PURGE_PSEUDOFS", "SUPERSEDED", "not carried",
     "Root-owned pseudo-filesystem scratch from an earlier purge exercise."),
    ("SyMoNeuRaL-Projects", "SUPERSEDED", "already consolidated into archive/",
     "2.8 GB. Its unique content was swept into the repository in the earlier "
     "consolidation; what remains is the emptied original."),
    ("experiments", "SUPERSEDED", "not carried", "2.5 GB of superseded experiment trees."),
    ("review", "SUPERSEDED", "review/ exists inside the repository",
     "Empty shell; the real review/ is tracked."),
    ("Platforms.tar.gz", "SUPERSEDED", "not carried",
     "224 MB platform tarball; a copy is already under external/."),

    # ---------------------------------------------------------------- tooling
    ("browser-webapp-purge.sh", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored maintenance script."),
    ("network-localize.sh", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored maintenance script."),
    ("symon-full-lockdown.sh", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored lockdown tooling."),
    ("symoneural-quarantine-generated.sh", "HISTORY_EVIDENCE", "archive/from-home/",
     "Owner-authored quarantine tooling."),
    ("install-ulaa-browser.sh", "UNRELATED", "not carried", "Browser installer."),

    # ---------------------------------------------------------------- owner's own
    ("Desktop", "OWNER_PERSONAL", "the owner decides",
     "292 MB. Swept for project material in the earlier consolidation; the remainder is "
     "the owner's. NOT swept by this session."),
    ("Documents", "OWNER_PERSONAL", "the owner decides", "88 MB."),
    ("Downloads", "OWNER_PERSONAL", "the owner decides",
     "34 GB, 411 entries, personal material mixed with the task prompts. Deliberately "
     "left unswept: deciding what of somebody's Downloads matters is not this session's "
     "call. The task prompt files that matter are separately preserved above."),
    ("Pictures", "OWNER_PERSONAL", "the owner decides", "1.4 GB."),
    ("Music", "OWNER_PERSONAL", "the owner decides", "-"),
    ("Videos", "OWNER_PERSONAL", "the owner decides", "-"),
    ("Public", "OWNER_PERSONAL", "the owner decides", "-"),
    ("Templates", "OWNER_PERSONAL", "the owner decides", "-"),
    ("ia.Wallpapers", "OWNER_PERSONAL", "the owner decides", "403 MB of wallpapers."),
    ("go", "UNRELATED", "regenerable",
     "1.6 GB Go module and toolchain cache. Rebuilt by `go mod download`; explicitly NOT "
     "carried, and restore/manifests records the Go >= 1.25.1 requirement instead."),
    ("test", "UNRELATED", "not carried", "Scratch file."),
    ("thinclient_drives", "SYSTEM", "not carried", "Thin-client mount point."),

    # ---------------------------------------------------------------- logs
    ("lockdown-20260831T152822Z.log", "HISTORY_EVIDENCE", "archive/from-home/logs/",
     "Lockdown run logs, 2026-08-31. Eight files, small, kept together as one record."),
)

#: The lockdown logs share one disposition; listing all eight individually would be noise.
LOCKDOWN_PREFIX = "lockdown-20260831T"

#: Hidden paths that matter. Not in the `for f in *` listing, and easy to forget.
HIDDEN: tuple[tuple[str, str, str, str], ...] = (
    (".claude", "CLAUDE_BACKUP", "purged post-exit by the finalizer; contents already "
     "captured in .private/claude-backups/",
     "5.3 GB. The user-level Claude state. Named in the purge allowlist, and the repository "
     "has been proved not to depend on it."),
    (".symoneural-full", "DUPLICATE", "not carried",
     "26 MB. A stale copy of the CLI whose launcher had DIVERGED from its source and "
     "nothing noticed -- which is why scripts/install-cli.sh installs symlinks, not "
     "copies."),
    (".config/systemd/user", "PROJECT_AUTHORITY",
     ".private/host-snapshot/rootfs/home/google/.config/systemd/user",
     "The user-scope symoneural units. Captured in the host snapshot."),
)


def gen_home_disposition(write_tsv) -> int:
    header = ["ITEM", "DISPOSITION", "CANONICAL_LOCATION", "PRESENT_ON_DISK", "SIZE_BYTES",
              "MODE", "NOTE"]
    rows: list[list] = []
    seen: set[str] = set()

    for name, disp, loc, note in DISPOSITIONS:
        p = HOME / name
        seen.add(name)
        # The canonical root's OWN size is deliberately not measured. It is live -- the API
        # appends to run/api.log while this generator runs -- so two consecutive
        # generations differed by 600 bytes and the determinism test went red. That is the
        # same self-referential trap as a manifest carrying the hash of the archive
        # containing it: the number cannot be stable because measuring it is part of the
        # thing being measured. Its size is also not a restore DECISION -- it is the tree
        # everything else is judged against.
        size = "n/a (self-referential; see the note)" if name == "Symoneural" \
            else (M.du_bytes(p) if p.exists() else 0)
        rows.append([name, disp, loc, "YES" if p.exists() else "no", size,
                     M.mode_of(p), note])

    for name, disp, loc, note in HIDDEN:
        p = HOME / name
        seen.add(name)
        rows.append([name, disp, loc, "YES" if p.exists() else "no",
                     M.du_bytes(p) if p.exists() else 0,
                     M.mode_of(p), note])

    # Anything on disk with no row. This is the whole point: an unclassified item must be
    # visible, not absent.
    if HOME.is_dir():
        for p in sorted(HOME.iterdir()):
            if p.name in seen or p.name.startswith("."):
                continue
            if p.name.startswith(LOCKDOWN_PREFIX):
                seen.add(p.name)
                continue
            rows.append([p.name, "UNCLASSIFIED", NUL, "YES", M.du_bytes(p),
                         M.mode_of(p),
                         "ON DISK WITH NO DISPOSITION. Add a row to restore/lib/home.py. "
                         "An unclassified item is destroyed by the reset without anyone "
                         "having decided that."])

    return write_tsv("HOME-DISPOSITION.tsv", header, rows, minimum=30)
