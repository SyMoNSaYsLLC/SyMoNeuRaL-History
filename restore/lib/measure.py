# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""The measured half of the restore control plane.

Nothing in this module makes a judgement. It reads the disk and reports what is there:
revisions, file counts, checksums, ELF architectures, whether a binary a recipe promises is
actually where the recipe says. Every value it returns is a reading taken now.

That separation is the whole point. This repository has published a test count that was
never true of the commit it sat beside, reported a service as disabled off a table row while
the unit file said enabled, and recorded an engine as unbuilt because a probe looked in the
wrong directory. Each was the same failure -- acting on a row rather than on the thing. So
the judgements live in `registry.py` where a human can argue with them, and everything that
can be measured is measured here, at generation time, every time.

Two conventions that matter:

* A measurement that cannot be taken returns a string saying so. It never returns a
  plausible default. `"NOT_PRESENT"` and `"UNMEASURED"` are values; `0` and `""` are not,
  because a zero that means "absent" is indistinguishable from a zero that means zero.

* Nothing here shells out to anything that could mutate state. It is all reads, so
  `symoneural-restore verify` is safe to run on a live box.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import subprocess


def find_root(start: pathlib.Path) -> pathlib.Path:
    """Walk up for a marker; never count parents.

    `ROOT = HERE.parent.parent` encodes the file's depth in the tree and breaks silently the
    day the file moves. `symoneural-audit` ratchets a count of that pattern and has twice
    caught new files written by the same author who added the check.
    """
    for cand in (start, *start.parents):
        if (cand / "backend" / "api.py").is_file():
            return cand
    raise SystemExit(f"symoneural-restore: no repository root above {start}")


ROOT = find_root(pathlib.Path(__file__).resolve().parent)


# ---------------------------------------------------------------------------- process
def run(args: list[str], cwd: pathlib.Path | None = None, timeout: int = 60) -> str:
    """Run a read-only command and return stripped stdout, or a marker string."""
    try:
        p = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True,
                           timeout=timeout)
    except FileNotFoundError:
        return "TOOL_NOT_INSTALLED"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if p.returncode != 0:
        return "UNMEASURED"
    return p.stdout.strip()


# ---------------------------------------------------------------------------- git
def head() -> str:
    return run(["git", "rev-parse", "HEAD"])


def branch() -> str:
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def is_clean() -> bool:
    return run(["git", "status", "--porcelain"]) == ""


def tracked_count(rel: str) -> int | str:
    out = run(["git", "ls-files", "--", rel])
    if out in ("UNMEASURED", "TIMEOUT", "TOOL_NOT_INSTALLED"):
        return out
    return len([ln for ln in out.splitlines() if ln])


def untracked_count(rel: str) -> int | str:
    """Untracked-and-not-ignored files under `rel`.

    Ignored files are excluded deliberately: for the five derived engine trees EVERY file is
    ignored, and counting them as untracked source would report thousands of defects for a
    tree whose canonical source is an upstream pin. `--exclude-standard` is what makes the
    number mean "source we forgot to track" rather than "files on disk".
    """
    out = run(["git", "ls-files", "--others", "--exclude-standard", "--", rel])
    if out in ("UNMEASURED", "TIMEOUT", "TOOL_NOT_INSTALLED"):
        return out
    return len([ln for ln in out.splitlines() if ln])


def repo_rev_of(path: pathlib.Path) -> str:
    if not (path / ".git").exists():
        return "NOT_A_GIT_REPO"
    return run(["git", "rev-parse", "HEAD"], cwd=path)


def repo_dirty_count(path: pathlib.Path) -> int | str:
    if not (path / ".git").exists():
        return "NOT_A_GIT_REPO"
    out = run(["git", "status", "--porcelain"], cwd=path)
    if out in ("UNMEASURED", "TIMEOUT"):
        return out
    return len([ln for ln in out.splitlines() if ln])


# ---------------------------------------------------------------------------- files
def sha256(path: pathlib.Path) -> str:
    """Hash a file by reading it. No `-L`: `sha256sum` has no dereference flag, and a
    session was spent chasing a source/launcher 'mismatch' that was `sha256sum -bL`
    silently doing something other than what was intended."""
    if not path.is_file():
        return "NOT_PRESENT"
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError as e:
        return f"UNREADABLE({e.errno})"
    return h.hexdigest()


def exists(rel: str) -> str:
    p = ROOT / rel
    if p.is_file():
        return "FILE"
    if p.is_dir():
        return "DIR"
    return "ABSENT"


def mode_of(path: pathlib.Path) -> str:
    if not path.exists():
        return "NOT_PRESENT"
    return oct(path.stat().st_mode & 0o7777)[2:].rjust(3, "0")


def file_type(path: pathlib.Path) -> str:
    if not path.is_file():
        return "NOT_PRESENT"
    out = run(["file", "-b", str(path)])
    return out.split(",")[0].strip() if out not in ("UNMEASURED", "TOOL_NOT_INSTALLED") \
        else out


def elf_arch(path: pathlib.Path) -> str:
    if not path.is_file():
        return "NOT_PRESENT"
    out = run(["readelf", "-h", str(path)])
    if out in ("UNMEASURED", "TOOL_NOT_INSTALLED", "TIMEOUT"):
        return out
    for ln in out.splitlines():
        if ln.strip().startswith("Machine:"):
            return ln.split(":", 1)[1].strip()
    return "NOT_AN_ELF"


def dynamic_deps(path: pathlib.Path, limit: int = 6) -> str:
    """Direct NEEDED entries, not the full transitive `ldd` closure.

    `ldd` runs the loader and is not something to point at an untrusted binary; `readelf -d`
    reads the table. The count is what a restore actually needs to know -- which shared
    objects must exist -- and the first few names identify the dependency family.
    """
    if not path.is_file():
        return "NOT_PRESENT"
    out = run(["readelf", "-d", str(path)])
    if out in ("UNMEASURED", "TOOL_NOT_INSTALLED", "TIMEOUT", "NOT_AN_ELF"):
        return out
    needed = [ln.split("[", 1)[1].rstrip("]").strip()
              for ln in out.splitlines() if "(NEEDED)" in ln and "[" in ln]
    if not needed:
        return "none"
    shown = ";".join(needed[:limit])
    return f"{len(needed)} NEEDED: {shown}" + ("…" if len(needed) > limit else "")


def du_bytes(path: pathlib.Path) -> int | str:
    if not path.exists():
        return "NOT_PRESENT"
    out = run(["du", "-sb", str(path)], timeout=300)
    if out in ("UNMEASURED", "TIMEOUT", "TOOL_NOT_INSTALLED"):
        return out
    return int(out.split()[0])


# ---------------------------------------------------------------------------- toolchain
def tool_version(name: str) -> str:
    """Version of a host tool, or an explicit ABSENT.

    A restore recipe that names a toolchain has to be checkable, and the check has to be
    able to say "this machine does not have it" rather than guessing.
    """
    if shutil.which(name) is None:
        return "ABSENT"
    probes = {
        "gcc": ["gcc", "-dumpfullversion"],
        "g++": ["g++", "-dumpfullversion"],
        "cmake": ["cmake", "--version"],
        "nvcc": ["nvcc", "--version"],
        "python3": ["python3", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "git": ["git", "--version"],
        "rsync": ["rsync", "--version"],
        "sqlite3": ["sqlite3", "--version"],
        "caddy": ["caddy", "version"],
        "ninja": ["ninja", "--version"],
        "ccache": ["ccache", "--version"],
    }
    out = run(probes.get(name, [name, "--version"]), timeout=30)
    if out in ("UNMEASURED", "TIMEOUT", "TOOL_NOT_INSTALLED"):
        return out
    first = out.splitlines()[0] if out else ""
    if name == "nvcc":
        for ln in out.splitlines():
            if "release" in ln:
                return ln.strip()
    return first.strip()


def gpu() -> str:
    if shutil.which("nvidia-smi") is None:
        return "ABSENT"
    return run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader"], timeout=30).splitlines()[0] \
        if run(["nvidia-smi", "-L"], timeout=30) not in ("UNMEASURED", "TIMEOUT") \
        else "UNMEASURED"


# ---------------------------------------------------------------------------- services
def _systemctl_state(args: list[str]) -> str:
    """`systemctl is-enabled` / `is-active` answer on STDOUT and exit NON-ZERO for the
    perfectly ordinary answers `disabled`, `inactive` and `static`.

    The generic `run()` above maps a non-zero exit to `UNMEASURED`, which is right for a
    command that failed and wrong for a command that answered. Routing these two through
    `run()` reported three units as UNMEASURED when systemd had told us exactly what they
    were -- publishing "we did not look" about a thing we had looked at, which is the same
    class of error as publishing a row instead of a reading.
    """
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "UNMEASURED"
    out = p.stdout.strip()
    if out:
        return out
    return "not-found" if p.returncode else "UNMEASURED"


def unit_state(unit: str, user: bool = False) -> tuple[str, str]:
    """(enabled-state, active-state) as systemd reports them right now.

    Read from systemd, never from a table. A service-map row reading 'defined but disabled'
    was reported as an anomaly three times about a unit that was enabled and active and is
    the public web server -- the row was wrong and nobody had opened the unit.
    """
    base = ["systemctl", "--user"] if user else ["systemctl"]
    return (_systemctl_state(base + ["is-enabled", unit]),
            _systemctl_state(base + ["is-active", unit]))


def installed_unit_matches(source_rel: str, installed: str) -> str:
    """Does the installed unit still match the tracked template it came from?

    The tracked units are TEMPLATES carrying the literal `@@ROOT@@`, which the installers
    substitute for the repository root because systemd has no notion of a relative path. A
    raw checksum therefore says DIVERGED for a perfectly current install, every time, and a
    check that always fires tells you nothing. So the template is rendered the way the
    installer renders it and THEN compared.

    What survives that substitution is the difference that matters. Measured 2026-09-08:
    the installed API and gateway units still differ after rendering, because they were
    installed before the 2026-09-03 fix that moved StartLimit* out of `[Service]` -- where
    systemd was silently ignoring them -- into `[Unit]`.
    """
    src = ROOT / source_rel
    dst = pathlib.Path(os.path.expanduser(installed))
    if not src.is_file():
        return "SOURCE_ABSENT"
    if not dst.exists():
        return "NOT_INSTALLED"
    try:
        rendered = src.read_text(errors="replace").replace("@@ROOT@@", str(ROOT))
        on_disk = dst.read_text(errors="replace")
    except OSError as e:
        return f"UNREADABLE({e.errno})"
    if rendered == on_disk:
        return "MATCH"

    # Section-aware, and that is not pedantry. The 2026-09-03 fix to these units MOVED
    # StartLimitIntervalSec/StartLimitBurst from [Service] to [Unit] without changing a
    # character of either line -- systemd silently ignores them in [Service], so the
    # crash-loop protection had never applied. A set comparison of directive text calls
    # that MATCH, which would have reported the single most consequential difference
    # between the template and the installed unit as no difference at all.
    def directives(text: str) -> set[tuple[str, str]]:
        section, out = "", set()
        for ln in text.splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("[") and s.endswith("]"):
                section = s
                continue
            out.add((section, s))
        return out

    a, b = directives(rendered), directives(on_disk)
    if a == b:
        return "MATCH (comments differ only)"
    missing = sorted(a - b)
    extra = sorted(b - a)
    detail = "; ".join(f"{sec}{key.split('=')[0]}" for sec, key in (missing + extra)[:4])
    return (f"DIVERGED (installed is STALE: {len(missing)} directive(s) from the template "
            f"absent, {len(extra)} present only on disk: {detail})")
