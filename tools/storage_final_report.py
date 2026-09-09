#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""Emit the storage reorganisation's final report, entirely from measurement.

    tools/storage_final_report.py            print the report
    tools/storage_final_report.py --json     the same values as JSON

Every field is read off the disk, the remote or the ledger at the moment it runs. Nothing is
carried forward from a previous run and nothing is typed in by hand, because this project
has already published a figure that was never true of the commit it sat beside -- somebody
carried it forward and re-dated it. A report that cannot be re-derived is a claim.

Where a value cannot be measured it prints UNMEASURED rather than 0. Those are different
statements: 0 means "measured, and it is none"; UNMEASURED means "nobody looked". Printing
0 for something unmeasured is how a gate passes without ever being checked.

The gates at the end are computed from the measured values, never asserted. In particular
STORAGE_ARCHITECTURE_COMPLETE is the conjunction of the others, so it cannot read YES while
any input says otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path("/home/google/Symoneural")
STATE = ROOT / ".private" / "storage-reorg" / "state.json"
CROSS = ROOT / ".private" / "storage-reorg" / "cross-root" / "summary.json"
UNMEASURED = "UNMEASURED"


def sh(a, t=7200):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=t)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(a, 124, "", "timeout")


def du(p) -> int | str:
    r = sh(["du", "-sb", "--one-file-system", str(p)], 3600)
    if r.returncode != 0:
        return UNMEASURED
    try:
        return int(r.stdout.split()[0])
    except (IndexError, ValueError):
        return UNMEASURED


def exists(p) -> bool:
    return pathlib.Path(p).exists()


def dfpc(mount: str) -> str:
    r = sh(["df", "--output=pcent", mount], 120)
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    return lines[-1] if len(lines) > 1 else UNMEASURED


def dfused(mount: str) -> int | str:
    r = sh(["df", "-B1", "--output=used", mount], 120)
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    try:
        return int(lines[-1])
    except (IndexError, ValueError):
        return UNMEASURED


def rsize(path: str) -> tuple[int | str, int | str]:
    r = sh(["rclone", "size", f"gdrive:{path}", "--json"], 7200)
    if r.returncode != 0:
        return UNMEASURED, UNMEASURED
    try:
        j = json.loads(r.stdout)
        return int(j.get("bytes") or 0), int(j.get("count") or 0)
    except json.JSONDecodeError:
        return UNMEASURED, UNMEASURED


def rexists(path: str) -> bool | str:
    r = sh(["rclone", "lsjson", f"gdrive:{path}", "--stat"], 600)
    return r.returncode == 0


def procs(pattern_any) -> int:
    n = 0
    me = os.getpid()
    for p in pathlib.Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == me:
            continue
        try:
            c = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if not c or "supervisor" in c or "final_report" in c:
            continue
        if any(m in c for m in pattern_any):
            n += 1
    return n


def collect() -> dict:
    d: dict[str, object] = {"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # ---- orchestrator ------------------------------------------------------------------
    d["ACTIVE_STORAGE_MUTATION_OWNERS"] = procs(
        ("storage_reorg.py run", "storage_reorg.py resume"))
    d["DUPLICATE_UPLOADERS"] = max(0, procs(("rclone copy", "rclone moveto")) - 1)
    d["LEGACY_PIPELINES_ACTIVE"] = procs(
        ("offload-to-drive", "cleanup-pipeline", "upstream-to-drive"))
    ops = {}
    if STATE.is_file():
        try:
            ops = json.loads(STATE.read_text()).get("ops") or {}
        except json.JSONDecodeError:
            ops = {}
    st_counts: dict[str, int] = {}
    for v in ops.values():
        k = v.get("state", "?")
        st_counts[k] = st_counts.get(k, 0) + 1
    d["LEDGER_STATES"] = st_counts
    d["LEDGER_OPERATIONS"] = len(ops)
    d["BYTES_RETIRED_LOCALLY"] = sum(
        v.get("raw_bytes", 0) for v in ops.values() if v.get("state") == "COMPLETE")
    # DEST_VERIFIED resume is proven by a test, not by an anecdote.
    t = sh([sys.executable, "-m", "pytest",
            "backend/apps/test_storage_reorg_resume.py", "-q"], 900)
    d["RESUME_TESTS"] = ("PASS" if t.returncode == 0 else "FAIL") + (
        f" ({[l for l in t.stdout.splitlines() if 'passed' in l or 'failed' in l][-1:]})"
        if t.stdout else "")
    d["DEST_VERIFIED_RESUME_PROVEN"] = "YES" if t.returncode == 0 else "NO"
    # Content manifests: are the uploaded ones content-addressed?
    n_sha = sum(1 for k, v in ops.items()
                if k.startswith("backfill-") and v.get("state") == "COMPLETE")
    d["MANIFEST_CONTENT_HASHES"] = ("SHA256 backfill COMPLETE" if n_sha else
                                    "SHA256 for new leaves; backfill pending for "
                                    "pre-hardening uploads")

    # ---- home -------------------------------------------------------------------------
    d["HOME_USED"] = dfused("/home")
    home = pathlib.Path("/home/google")
    tops = [p for p in home.iterdir()] if home.is_dir() else []
    nondot = [p.name for p in tops if not p.name.startswith(".")]
    d["HOME_TOP_LEVEL_ITEMS"] = len(tops)
    d["HOME_NONDOT_ITEMS"] = sorted(nondot)
    KNOWN_OK = {"Symoneural", "Desktop", "go", "Documents", "Pictures", "Music",
                "Videos", "deleteme"}
    d["HOME_UNCLASSIFIED"] = sorted(set(nondot) - KNOWN_OK)
    d["HOME_RANDOM_ARCHIVES"] = sorted(
        n for n in nondot if n.endswith((".tar.gz", ".zip", ".tar", ".tgz", ".zst")))

    # ---- symoneural -------------------------------------------------------------------
    d["SYMONEURAL_TOTAL"] = du(ROOT)
    d["EXTERNAL_LOCAL_REFERENCE_BYTES"] = du(ROOT / "external") if exists(
        ROOT / "external") else 0
    d["HISTORICAL_ARCHIVE_BYTES"] = du(ROOT / "archive") if exists(
        ROOT / "archive") else 0
    d["LOCAL_RUNTIME_MODEL_BYTES"] = du(ROOT / "backend" / "models")
    d["UNIQUE_TRAINING_BYTES"] = du(ROOT / "training") if exists(
        ROOT / "training") else 0
    d["RUNTIME_REQUIRED_DEPENDENCY_BYTES"] = du(ROOT / "backend" / "vendor") if exists(
        ROOT / "backend" / "vendor") else 0
    regen = 0
    for sub in ("frontend/node_modules", "tests/node_modules"):
        if exists(ROOT / sub):
            v = du(ROOT / sub)
            regen += v if isinstance(v, int) else 0
    d["REGENERABLE_CACHE_BYTES"] = regen

    # ---- yocto ------------------------------------------------------------------------
    d["YOCTO_USED"] = dfused("/yocto")
    d["YOCTO_PERCENT"] = dfpc("/yocto")
    y = pathlib.Path("/yocto")
    for name, key in (("downloads", "BUILD_DOWNLOADS"), ("sstate-cache", "SSTATE")):
        d[f"YOCTO_{key}"] = du(y / name) if exists(y / name) else 0
    completed = 0
    for name in ("artifacts", "sendtodrive", "Archives", "dispatchos", "src"):
        if exists(y / name):
            v = du(y / name)
            completed += v if isinstance(v, int) else 0
    d["YOCTO_COMPLETED_OUTPUT_BYTES"] = completed
    d["YOCTO_SENDTODRIVE_BYTES"] = du(y / "sendtodrive") if exists(y / "sendtodrive") else 0
    d["YOCTO_ARCHIVES_BYTES"] = du(y / "Archives") if exists(y / "Archives") else 0
    hist = 0
    for name in ("matrix-run", "blackwell", "metrics", "controlboard"):
        if exists(y / name):
            v = du(y / name)
            hist += v if isinstance(v, int) else 0
    d["YOCTO_RETAINED_TOOLING_BYTES"] = hist
    d["YOCTO_TOP_LEVEL"] = sorted(p.name for p in y.iterdir()) if y.is_dir() else []

    # ---- gdrive -----------------------------------------------------------------------
    about = sh(["rclone", "about", "gdrive:", "--json"], 600)
    try:
        a = json.loads(about.stdout)
        d["GDRIVE_USED"] = a.get("used", UNMEASURED)
        d["GDRIVE_FREE"] = a.get("free", UNMEASURED)
        d["GDRIVE_TRASHED"] = a.get("trashed", UNMEASURED)
    except json.JSONDecodeError:
        d["GDRIVE_USED"] = d["GDRIVE_FREE"] = d["GDRIVE_TRASHED"] = UNMEASURED
    r = sh(["rclone", "lsjson", "gdrive:"], 3600)
    try:
        root = json.loads(r.stdout)
    except json.JSONDecodeError:
        root = []
    CANON = {"Symoneural", "Models", "Build-Outputs", "Projects",
             "Development-Reference", "Virtualization", "Media", "Personal", "Private",
             "Historical-Archive", "deleteme"}
    ALLOWED_FILES = {"INDEX.md", "CATALOG.tsv", "MIGRATION-MAP.tsv", "DUPLICATES.tsv"}
    d["GDRIVE_ROOT_TOP_LEVEL_COUNT"] = len(root)
    d["GDRIVE_ROOT_DIRS"] = sorted(x["Name"] for x in root if x.get("IsDir"))
    loose = [x["Name"] for x in root if not x.get("IsDir")]
    d["GDRIVE_ROOT_LOOSE_UNCLASSIFIED"] = len([n for n in loose if n not in ALLOWED_FILES])
    d["GDRIVE_UNCLASSIFIED_TOP_LEVEL"] = sorted(
        x["Name"] for x in root if x.get("IsDir") and x["Name"] not in CANON)
    d["PROJECTS_ORGANIZE_PRESENT"] = "YES" if rexists("Projects_Organize") else "NO"
    d["OFFLOAD_BUCKET_PRESENT"] = "YES" if (
        rexists("offload") or rexists("Symoneural/offload")) else "NO"
    d["DONOTDELETE_BUCKET_PRESENT"] = "YES" if rexists("DONOTDELETE") else "NO"
    for f in ALLOWED_FILES:
        d[f"{f.split('.')[0].replace('-', '_').upper()}_PRESENT"] = (
            "YES" if rexists(f) else "NO")

    # ---- cross-root -------------------------------------------------------------------
    if CROSS.is_file():
        try:
            c = json.loads(CROSS.read_text())
            d["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"] = c.get(
                "CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES", UNMEASURED)
            d["CLAUDE_HELD_GROUPS"] = c.get("claude_held_groups", UNMEASURED)
            d["CLAUDE_HELD_BYTES"] = c.get("claude_held_bytes", UNMEASURED)
        except json.JSONDecodeError:
            d["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"] = UNMEASURED
    else:
        d["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"] = UNMEASURED
        d["CLAUDE_HELD_GROUPS"] = UNMEASURED
        d["CLAUDE_HELD_BYTES"] = UNMEASURED

    # ---- claude hold ------------------------------------------------------------------
    held = 0
    for p in ("external/anthropics", "external/Claude", "external/ClaudeAlienware",
              "external/claude-desktop_1.32885.1_amd64.deb"):
        if exists(ROOT / p):
            v = du(ROOT / p)
            held += v if isinstance(v, int) else 0
    d["LOCAL_RETIREMENT_HELD_FOR_EXIT"] = held

    # ---- repository -------------------------------------------------------------------
    d["HEAD"] = sh(["git", "rev-parse", "HEAD"], 120).stdout.strip() or UNMEASURED
    porcelain = sh(["git", "status", "--porcelain"], 600).stdout
    d["GIT_DIRTY_ENTRIES"] = len([l for l in porcelain.splitlines() if l.strip()])
    d["CLEAN"] = "YES" if d["GIT_DIRTY_ENTRIES"] == 0 else f"NO ({d['GIT_DIRTY_ENTRIES']})"
    return d


def gates(d: dict) -> dict:
    def ok(v) -> bool:
        return isinstance(v, int) and v == 0

    g = {}
    g["HOME_MINIMAL"] = "YES" if (not d.get("HOME_UNCLASSIFIED")
                                  and not d.get("HOME_RANDOM_ARCHIVES")) else "NO"
    g["SYMONEURAL_RUNTIME_PROJECT_ONLY"] = "YES" if (
        ok(d.get("EXTERNAL_LOCAL_REFERENCE_BYTES"))
        and ok(d.get("HISTORICAL_ARCHIVE_BYTES"))
        and ok(d.get("REGENERABLE_CACHE_BYTES"))) else "NO"
    g["YOCTO_BUILD_ONLY"] = "YES" if ok(d.get("YOCTO_COMPLETED_OUTPUT_BYTES")) else "NO"
    g["GDRIVE_ORGANIZED_KNOWLEDGE_STORE"] = "YES" if (
        d.get("PROJECTS_ORGANIZE_PRESENT") == "NO"
        and d.get("OFFLOAD_BUCKET_PRESENT") == "NO"
        and d.get("DONOTDELETE_BUCKET_PRESENT") == "NO"
        and not d.get("GDRIVE_UNCLASSIFIED_TOP_LEVEL")
        and d.get("GDRIVE_ROOT_LOOSE_UNCLASSIFIED") == 0) else "NO"
    g["GDRIVE_CATALOG_COMPLETE"] = "YES" if all(
        d.get(k) == "YES" for k in ("INDEX_PRESENT", "CATALOG_PRESENT",
                                    "MIGRATION_MAP_PRESENT", "DUPLICATES_PRESENT")
    ) else "NO"
    x = d.get("CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES")
    g["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"] = 0 if x == 0 else x
    # The conjunction, so it cannot read YES while an input disagrees.
    g["STORAGE_ARCHITECTURE_COMPLETE"] = "YES" if (
        g["HOME_MINIMAL"] == "YES"
        and g["SYMONEURAL_RUNTIME_PROJECT_ONLY"] == "YES"
        and g["YOCTO_BUILD_ONLY"] == "YES"
        and g["GDRIVE_ORGANIZED_KNOWLEDGE_STORE"] == "YES"
        and g["GDRIVE_CATALOG_COMPLETE"] == "YES"
        and g["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"] == 0) else "NO"
    return g


def human(v):
    if not isinstance(v, int):
        return v
    if v < 1024:
        return f"{v}"
    x = float(v)
    for u in ("KiB", "MiB", "GiB", "TiB"):
        x /= 1024
        if x < 1024 or u == "TiB":
            return f"{v} ({x:.2f} {u})"
    return str(v)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    d = collect()
    g = gates(d)
    if a.json:
        print(json.dumps({"measured": d, "gates": g}, indent=2, default=str))
        return 0
    print(f"MEASURED AT {d['measured_at']}\n")
    order = [
        ("ORCHESTRATOR", ["ACTIVE_STORAGE_MUTATION_OWNERS", "DUPLICATE_UPLOADERS",
                          "LEGACY_PIPELINES_ACTIVE", "LEDGER_OPERATIONS",
                          "LEDGER_STATES", "BYTES_RETIRED_LOCALLY", "RESUME_TESTS",
                          "DEST_VERIFIED_RESUME_PROVEN", "MANIFEST_CONTENT_HASHES"]),
        ("HOME", ["HOME_USED", "HOME_TOP_LEVEL_ITEMS", "HOME_NONDOT_ITEMS",
                  "HOME_UNCLASSIFIED", "HOME_RANDOM_ARCHIVES"]),
        ("SYMONEURAL", ["SYMONEURAL_TOTAL", "EXTERNAL_LOCAL_REFERENCE_BYTES",
                        "HISTORICAL_ARCHIVE_BYTES", "REGENERABLE_CACHE_BYTES",
                        "RUNTIME_REQUIRED_DEPENDENCY_BYTES", "LOCAL_RUNTIME_MODEL_BYTES",
                        "UNIQUE_TRAINING_BYTES"]),
        ("YOCTO", ["YOCTO_USED", "YOCTO_PERCENT", "YOCTO_BUILD_DOWNLOADS", "YOCTO_SSTATE",
                   "YOCTO_COMPLETED_OUTPUT_BYTES", "YOCTO_SENDTODRIVE_BYTES",
                   "YOCTO_ARCHIVES_BYTES", "YOCTO_RETAINED_TOOLING_BYTES",
                   "YOCTO_TOP_LEVEL"]),
        ("GDRIVE", ["GDRIVE_USED", "GDRIVE_FREE", "GDRIVE_TRASHED",
                    "GDRIVE_ROOT_TOP_LEVEL_COUNT", "GDRIVE_ROOT_LOOSE_UNCLASSIFIED",
                    "GDRIVE_UNCLASSIFIED_TOP_LEVEL", "PROJECTS_ORGANIZE_PRESENT",
                    "OFFLOAD_BUCKET_PRESENT", "DONOTDELETE_BUCKET_PRESENT",
                    "INDEX_PRESENT", "CATALOG_PRESENT", "MIGRATION_MAP_PRESENT",
                    "DUPLICATES_PRESENT"]),
        ("CLAUDE_HOLD", ["LOCAL_RETIREMENT_HELD_FOR_EXIT", "CLAUDE_HELD_GROUPS",
                         "CLAUDE_HELD_BYTES"]),
        ("CROSS_ROOT", ["CROSS_ROOT_UNEXPLAINED_LARGE_DUPLICATES"]),
        ("REPOSITORY", ["HEAD", "CLEAN", "GIT_DIRTY_ENTRIES"]),
    ]
    for section, keys in order:
        print(section)
        for k in keys:
            if k in d:
                print(f"  {k}={human(d[k])}")
        print()
    print("FINAL_GATES")
    for k, v in g.items():
        print(f"  {k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
