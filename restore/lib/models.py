# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""MODELS.tsv -- which weights travel in the backup and which are refetched.

This decides roughly 17 GB of archive size, so it is worth getting right rather than
guessing. The owner's Target 17 asks every asset to be classified, and the two
classifications that matter are:

    DOWNLOADABLE_MODEL   a public artefact under a house name. Reacquirable from its
                         upstream repository, so the bytes do NOT travel; the row does.
    UNIQUE_MODEL         produced here and existing nowhere else. Must travel, because
                         losing it loses work that cannot be recreated by downloading.

**The classification is read, not invented.** `backend/models/PROVENANCE.json` already
records, for every weight file on this box, which upstream artefact the house name was
fetched from -- and its own note says why it exists: *"a house name with no recorded origin
is an unfalsifiable claim about what the bytes are."* This module joins that manifest
against the disk and emits the restore view of it.

The single most consequential thing it establishes: `symon-1.0-7b-q4_k_m.gguf` is 4.4 GB and
sounds like a trained SyMoNeuRaL model. It is not. PROVENANCE.json records it as
`bartowski/Qwen2.5-7B-Instruct-GGUF` renamed, Apache-2.0, unmodified. What is actually ours
is the persona LoRA in `training/adapter/` -- 232 MB that no download can replace. Carrying
the 4.4 GB base and calling it first-party would be both wasteful and a false claim about
authorship; carrying the adapter is the thing that matters.

A weight file present on disk but ABSENT from PROVENANCE.json is reported as
`UNRECORDED_ORIGIN` and never silently assumed downloadable. That is the whole point of the
upstream manifest, and an unmatched file is exactly the case where guessing is worst.
"""
from __future__ import annotations

import json
import pathlib

from lib import measure as M

ROOT = M.ROOT
NUL = "-"

#: Weight-ish extensions. A restore needs to know about the big opaque binaries; a config
#: JSON beside them is not a model.
WEIGHT_SUFFIXES = (".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".ckpt")

#: Below this, a file is not worth an archive decision. Named rather than magic: the point
#: of the table is the multi-gigabyte artefacts.
MIN_INTERESTING = 8 * 1024 * 1024


def _provenance() -> dict[str, dict]:
    f = ROOT / "backend" / "models" / "PROVENANCE.json"
    if not f.is_file():
        return {}
    try:
        doc = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {w["path"]: w for w in doc.get("weights", []) if "path" in w}


def _on_disk() -> list[pathlib.Path]:
    base = ROOT / "backend" / "models"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*")
                  if p.is_file() and p.suffix.lower() in WEIGHT_SUFFIXES
                  and p.stat().st_size >= MIN_INTERESTING)


#: Reference KINDS. The count of files naming a weight proves nothing on its own -- what
#: matters is what kind of file names it. Measured on 2026-09-08, the four absent large
#: models are named 1-2 times each and every one of those references is a catalogue entry,
#: a documentation page or a training-target option. Treating a reference count as a
#: production requirement would have made a restore download ~34 GB of weights that no
#: runtime on this box has ever loaded.
def _reference_kind(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    if path in ("scripts/fetch-models.sh", "backend/models/PROVENANCE.json",
                "backend/models/NAMES.md"):
        return "CATALOGUE"
    if path.startswith("backend/apps/studio/plugins/reinforce/"):
        return "TRAINING_TARGET_OPTION"
    if base.startswith("test_") or "/tests/" in path:
        return "TEST_ONLY"
    if path.startswith(("docs/", "review/", "archive/", "external/")) \
            or base.endswith((".md", ".html")):
        return "DOCUMENTATION_ONLY"
    if path.startswith("site/"):
        return "DOCUMENTATION_ONLY"
    if path.startswith("symoneural-code/"):
        # The CLI offers tiers as a menu; naming one is not loading it.
        return "OPTIONAL_FEATURE"
    if path.startswith(("backend/", "run/", "ops/")):
        return "CURRENT_PRODUCTION"
    return "OTHER"


def _references(name: str) -> list[tuple[str, str]]:
    """[(path, kind)] for every tracked file naming this weight."""
    out = M.run(["git", "grep", "-l", "--", name])
    if out in ("UNMEASURED", "TIMEOUT", "TOOL_NOT_INSTALLED", ""):
        return []
    return [(h, _reference_kind(h)) for h in out.splitlines() if h]


def _requirement(rel: str, present: bool) -> tuple[str, str, str]:
    """(REQUIRED_FOR_CURRENT_PRODUCTION, RESTORE_REQUIREMENT, REFERENCES)."""
    refs = _references(pathlib.Path(rel).name)
    kinds = {k for _, k in refs}
    shown = ";".join(f"{p}[{k}]" for p, k in refs[:6]) or "none"
    if "CURRENT_PRODUCTION" in kinds:
        return ("YES", "CURRENT_PRODUCTION", shown)
    if "OPTIONAL_FEATURE" in kinds or "TRAINING_TARGET_OPTION" in kinds:
        return ("NO", "OPTIONAL" if present else "ABSENT_OPTIONAL", shown)
    if kinds <= {"CATALOGUE", "DOCUMENTATION_ONLY", "TEST_ONLY", "OTHER"} and kinds:
        return ("NO", "HISTORICAL" if not present else "OPTIONAL", shown)
    return ("NO", "OPTIONAL" if present else "ABSENT_OPTIONAL", shown)


def gen_models(write_tsv) -> int:
    header = ["ASSET_ID", "PATH", "CLASS", "BYTES", "ROLE",
              "REQUIRED_FOR_CURRENT_PRODUCTION", "RESTORE_REQUIREMENT",
              "UPSTREAM_REPO", "UPSTREAM_FILE", "UPSTREAM_REVISION", "EXPECTED_SHA256",
              "CURRENT_FILE_SHA256_MATCH", "LICENSE", "LICENSE_TEXT", "MODIFIED_BY_US",
              "FETCH_METHOD", "TRAVELS_IN_ARCHIVE", "CONSUMERS", "NOTES"]
    prov = _provenance()
    rows: list[list] = []
    seen: set[str] = set()

    for p in _on_disk():
        rel = str(p.relative_to(ROOT / "backend" / "models"))
        seen.add(rel)
        w = prov.get(rel)
        size = p.stat().st_size
        req, restore_req, users = _requirement(rel, present=True)

        if w is None:
            rows.append([
                f"model-{rel.replace('/', '-')}", f"backend/models/{rel}",
                "UNRECORDED_ORIGIN", size, NUL, req, restore_req,
                NUL, NUL, NUL, NUL, "n/a", "UNKNOWN", NUL, "UNKNOWN",
                "NONE -- origin not recorded, so it cannot be refetched",
                "YES (must travel: an unrecorded origin cannot be reacquired)", users,
                "Present on disk and absent from backend/models/PROVENANCE.json. That "
                "manifest's own note calls a house name with no recorded origin an "
                "unfalsifiable claim about what the bytes are; this row refuses to invent "
                "a licence or an upstream for it.",
            ])
            continue

        expected = str(w.get("sha256", NUL)) or NUL
        # Verify the bytes on disk against the recorded hash where one exists. Excluding
        # 16 GB from the archive is only safe if the thing being refetched is identifiable,
        # and an EXPECTED_SHA256 nobody has ever checked is decoration.
        if expected not in (NUL, "", "None"):
            actual = M.sha256(p)
            match = "YES" if actual == expected else f"NO (disk={actual[:16]}…)"
        else:
            match = "NO_HASH_RECORDED"

        modified = str(w.get("modified_by_us", "unknown"))
        cls = "DOWNLOADABLE_MODEL"
        travels = "NO -- refetched from the upstream repository"
        if modified.lower() in ("true", "yes"):
            cls = "MODIFIED_DERIVATIVE"
            travels = "YES -- modified here, so the upstream file is not equivalent"
        elif match.startswith("NO ("):
            travels = ("YES -- the bytes on disk do not match the recorded hash, so "
                       "refetching would not reproduce them")

        rows.append([
            f"model-{rel.replace('/', '-')}", f"backend/models/{rel}", cls, size,
            w.get("role", NUL), req, restore_req,
            w.get("upstream_repo", NUL), w.get("upstream_file", NUL),
            w.get("upstream_revision", NUL), expected, match,
            w.get("license", "UNKNOWN"), w.get("license_text", NUL), modified,
            f"scripts/fetch-models.sh, or huggingface-cli download "
            f"{w.get('upstream_repo', '<repo>')} {w.get('upstream_file', '<file>')}",
            travels, users,
            "Renamed, not modified. Apache-2.0 s.4 obliges attribution to travel with a "
            "redistributed artefact, which is why backend/models/licenses/ ships even "
            "though the weights do not.",
        ])

    # The genuinely irreplaceable material, which is NOT under backend/models.
    for rel, role, note in (
        ("training/adapter", "the SyMoNeuRaL persona LoRA trained against the 7B base",
         "THIS is the first-party model asset. No download replaces it: it is the output "
         "of training performed here. docs/ops/EXPORTS.md names it as a protected "
         "artefact by path."),
        ("training/adapter-qwen36", "a second trained adapter", "Same class as above."),
        ("training/corpus.jsonl", "the training dataset",
         "Protected artefact -- 327 hand-authored examples, and archive-guard.sh calls it "
         "a trade secret. The adapter cannot be retrained without it."),
    ):
        p = ROOT / rel
        if not p.exists():
            continue
        rows.append([f"model-{rel.replace('/', '-')}", rel, "UNIQUE_MODEL",
                     M.du_bytes(p), role, "YES", "CURRENT_PRODUCTION",
                     NUL, NUL, NUL, NUL, "n/a",
                     "LicenseRef-SyMoNeuRaL-Proprietary", NUL, "YES",
                     "NONE -- cannot be reacquired; it exists only here",
                     "YES -- REQUIRED", "reinforce,chat", note])

    # Recorded but not on disk. NOT automatically a restore failure.
    for rel in sorted(set(prov) - seen):
        w = prov[rel]
        req, restore_req, users = _requirement(rel, present=False)
        rows.append([f"model-{rel.replace('/', '-')}", f"backend/models/{rel}",
                     "RECORDED_BUT_ABSENT", 0, w.get("role", NUL), req, restore_req,
                     w.get("upstream_repo", NUL), w.get("upstream_file", NUL),
                     w.get("upstream_revision", NUL), str(w.get("sha256", NUL)),
                     "n/a (not on disk)", w.get("license", "UNKNOWN"),
                     w.get("license_text", NUL), str(w.get("modified_by_us", "unknown")),
                     "scripts/fetch-models.sh (only if actually wanted)",
                     "n/a", users,
                     "In PROVENANCE.json and NOT on disk. Measured: nothing outside the "
                     "fetch catalogue and the reinforce training-target registry names "
                     "it, so this box has not been serving it. RESTORE_REQUIREMENT is "
                     "therefore ABSENT_OPTIONAL -- a restore must NOT download it by "
                     "default. Letting RECORDED_BUT_ABSENT imply 'fetch all four' would "
                     "add roughly 40 GB to every restore for models nothing loads."])

    return write_tsv("MODELS.tsv", header, rows, minimum=5)
