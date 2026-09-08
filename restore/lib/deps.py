# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""DEPENDENCIES.tsv and THIRD-PARTY-REBUILD-MANIFEST.tsv.

The owner's rule for the reset is that external things are described, not carried:

    "For dependencies that are legally and technically external but reinstallable, store
     metadata, not source."

So this emits two tables.

`THIRD-PARTY-REBUILD-MANIFEST.tsv` is the one that replaces 149 GB of `external/`. Each row
is an upstream that a first-party component is BUILT from, pinned to an exact revision on a
public remote. `SOURCE_COPY_REQUIRED=NO` on those rows is the claim that makes the tree
omittable, and it is only true because the pin is real -- which the generator verifies
against the checkout while the checkout is still here.

`DEPENDENCIES.tsv` is everything else: the platform, the toolchain, and the Python
distributions.

## Two honesty decisions, both visible in the output

**Licences are read, not assumed.** A Python distribution's licence comes from its own
metadata -- the `License` field, or the `License ::` trove classifier when the field is the
useless `UNKNOWN` that setuptools writes by default. Where neither exists the cell says
`UNDECLARED`, which is a fact about the package. Guessing "MIT" because most things are MIT
would put a legal claim in a manifest on the strength of a base rate.

**Per-package rows for the serving environment only.** The serving interpreter is what
`ops/symoneural-api.service` execs, so its 196 distributions each get a row. The six
per-application venvs get one row each pointing at their lock file, because 594 rows whose
licence column was filled by the same weak inference would look like more diligence and be
less. The locks carry the exact pins either way, and `REINSTALL_METHOD` names them.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

from lib import measure as M
from lib import registry as R

ROOT = M.ROOT
NUL = "-"

LOCKS = ROOT / "restore" / "locks"

# Host-level things a fresh Debian install needs before anything here builds. Versions are
# MEASURED at generation time; the package names are what apt actually calls them, checked
# against this host rather than remembered.
PLATFORM: list[tuple[str, str, str, str, str, str]] = [
    # (dep_id, name, tool_probe, apt package, class, used_by)
    ("dep-gcc", "GNU C compiler", "gcc", "gcc", "TOOLCHAIN",
     "symoneural-llm,symoneural-diffuse,symoneural-listen,symoneural-miner"),
    ("dep-gxx", "GNU C++ compiler", "g++", "g++", "TOOLCHAIN",
     "symoneural-llm,symoneural-diffuse,symoneural-listen,symoneural-miner"),
    ("dep-cmake", "CMake", "cmake", "cmake", "BUILD_TOOL",
     "symoneural-llm,symoneural-diffuse,symoneural-listen,symoneural-miner"),
    ("dep-git", "Git", "git", "git", "BUILD_TOOL", "all"),
    ("dep-python", "CPython", "python3", "python3", "PLATFORM_RUNTIME", "all"),
    ("dep-node", "Node.js", "node", "nodejs", "BUILD_TOOL", "frontend,tests"),
    ("dep-npm", "npm", "npm", "npm", "BUILD_TOOL", "frontend,tests"),
    ("dep-rsync", "rsync", "rsync", "rsync", "BUILD_TOOL",
     "tools/fork_engines.sh, restore-state"),
    ("dep-sqlite", "SQLite CLI", "sqlite3", "sqlite3", "RUNTIME",
     "accounts-db consistent backup and integrity_check"),
    ("dep-nvcc", "CUDA toolkit", "nvcc", "cuda-toolkit (NVIDIA repository)",
     "PLATFORM_RUNTIME",
     "symoneural-llm,symoneural-diffuse,symoneural-listen,symoneural-miner"),
    ("dep-ccache", "ccache", "ccache", "ccache", "BUILD_TOOL",
     "tools/fork_engines.sh (optional; makes an unchanged rebuild cheap)"),
    ("dep-ninja", "Ninja", "ninja", "ninja-build", "BUILD_TOOL", "optional cmake generator"),
    ("dep-go", "Go", "go", "golang-go", "TOOLCHAIN", "symoneural-web"),
    ("dep-cargo", "Cargo", "cargo", "cargo", "TOOLCHAIN", "symoneural-gateway"),
    ("dep-rustc", "rustc", "rustc", "rustc", "TOOLCHAIN", "symoneural-gateway"),
]


def _classifier_licence(meta) -> str:
    """Licence from metadata, or an explicit UNDECLARED. Never a guess."""
    lic = (meta.get("License") or "").strip()
    if lic and lic.upper() not in ("UNKNOWN", "UNDECLARED", ""):
        # Some packages paste an entire licence text into this field.
        first = lic.splitlines()[0].strip()
        return (first[:60] + "…") if len(first) > 60 else first
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License ::"):
            return c.rsplit("::", 1)[-1].strip()
    expr = (meta.get("License-Expression") or "").strip()
    return expr or "UNDECLARED"


def serving_distributions() -> list[tuple[str, str, str]]:
    """(name, version, licence) from the interpreter the API unit actually execs."""
    code = (
        "import importlib.metadata as m, json\n"
        "out=[]\n"
        "for d in m.distributions():\n"
        "    md=d.metadata\n"
        "    n=md['Name']\n"
        "    if not n: continue\n"
        "    lic=(md.get('License') or '').strip()\n"
        "    if not lic or lic.upper()=='UNKNOWN':\n"
        "        lic=''\n"
        "        for c in (md.get_all('Classifier') or []):\n"
        "            if c.startswith('License ::'):\n"
        "                lic=c.rsplit('::',1)[-1].strip(); break\n"
        "        if not lic:\n"
        "            lic=(md.get('License-Expression') or '').strip()\n"
        "    lic=(lic.splitlines() or [''])[0].strip() or 'UNDECLARED'\n"
        "    out.append([n, d.version, lic[:60]])\n"
        "print(json.dumps(out))\n"
    )
    try:
        p = subprocess.run(["/usr/bin/python3", "-c", code], capture_output=True,
                           text=True, timeout=180)
        if p.returncode != 0:
            return []
        import json
        rows = json.loads(p.stdout)
    except Exception:
        return []
    seen, out = set(), []
    for n, v, lic in sorted(rows, key=lambda r: r[0].lower()):
        k = n.lower().replace("_", "-")
        if k in seen:
            continue
        seen.add(k)
        out.append((n, v, lic))
    return out


def lock_summary() -> list[tuple[str, int]]:
    out = []
    if not LOCKS.is_dir():
        return out
    for f in sorted(LOCKS.glob("*.lock.txt")):
        pins = len([ln for ln in f.read_text().splitlines()
                    if ln.strip() and not ln.startswith("#")])
        out.append((f.name.replace(".lock.txt", ""), pins))
    return out


def verify_pin(c: R.Component) -> str:
    """Is the recorded upstream revision actually what is checked out right now?

    Recorded pins are the whole basis for omitting `external/`. While that tree is still on
    this disk the claim is checkable, so it gets checked -- once it is gone, nobody can.
    """
    if c.upstream_rev == NUL or c.upstream_local_path == NUL:
        return "n/a"
    p = ROOT / c.upstream_local_path
    if not p.is_dir():
        return "UPSTREAM_TREE_ABSENT (pin unverifiable from this host)"
    actual = M.repo_rev_of(p)
    if actual == c.upstream_rev:
        dirty = M.repo_dirty_count(p)
        if isinstance(dirty, int) and dirty:
            return f"PIN_VERIFIED but tree has {dirty} uncommitted change(s)"
        return "PIN_VERIFIED"
    return f"PIN_MISMATCH (registry={c.upstream_rev[:12]} disk={str(actual)[:12]})"


def gen_third_party_rebuild(write_tsv_root) -> int:
    header = ["DEPENDENCY_ID", "NAME", "CLASS", "VERSION", "LICENSE", "PACKAGE_MANAGER",
              "PACKAGE_NAME", "UPSTREAM_PROJECT", "PINNED_REVISION", "PIN_VERIFIED",
              "LOCAL_PATCH", "USED_BY", "BUILD_OR_RUNTIME", "REQUIRED",
              "REINSTALL_COMMAND_OR_METHOD", "SOURCE_COPY_REQUIRED", "NOTES"]
    rows = []
    for c in R.COMPONENTS:
        if c.upstream == NUL:
            continue
        required = "YES" if c.production_status == R.PRODUCTION else \
            f"NO ({c.production_status})"
        reinstall = (f"git clone {c.upstream} <dir> && git -C <dir> checkout "
                     f"{c.upstream_rev}")
        # A tree with uncommitted local edits cannot be restored by a pin alone. Saying
        # SOURCE_COPY_REQUIRED=NO for it would be true of the upstream and false of what
        # is actually built here, so the patch is named instead.
        copy_required = "NO"
        note = "Reacquired at the pinned revision; no source copy travels in the backup."
        if c.local_patch != NUL:
            note = ("Upstream carries UNCOMMITTED local modifications. The pin restores "
                    "the upstream; the preserved patch restores our changes. Both are "
                    "required, and neither is the source tree.")
        rows.append([
            f"upstream-{c.component_id}", c.upstream_local_path.split("/")[-1],
            "UPSTREAM_SOURCE", c.upstream_rev[:12], c.upstream_license, "git",
            c.upstream.rsplit("/", 1)[-1].replace(".git", ""), c.upstream,
            c.upstream_rev, verify_pin(c), c.local_patch, c.component_id, "BUILD",
            required, reinstall, copy_required, note,
        ])
    out = ROOT / "THIRD-PARTY-REBUILD-MANIFEST.tsv"
    out.write_text("\t".join(header) + "\n" +
                   "".join("\t".join(write_tsv_root(x) for x in r) + "\n" for r in rows),
                   encoding="utf-8")
    return len(rows)


def gen_dependencies(write_tsv) -> int:
    header = ["DEPENDENCY_ID", "NAME", "VERSION", "LICENSE", "CLASS", "PACKAGE_MANAGER",
              "PACKAGE_NAME", "UPSTREAM", "CHECKSUM", "USED_BY", "BUILD_OR_RUNTIME",
              "REQUIRED", "REINSTALL_METHOD", "OFFLINE_COPY_PRESENT",
              "SOURCE_TREE_REQUIRED"]
    rows: list[list] = []

    # ---- platform and toolchain, versions measured now
    for dep_id, name, probe, pkg, cls, used in PLATFORM:
        ver = M.tool_version(probe)
        rows.append([dep_id, name, ver, "see distribution", cls, "apt", pkg,
                     "Debian" if "NVIDIA" not in pkg else "NVIDIA",
                     NUL, used, "BUILD" if cls == "BUILD_TOOL" else "RUNTIME",
                     "YES" if ver != "ABSENT" else "YES (ABSENT on this host)",
                     f"sudo apt-get install -y {pkg}", "NO", "NO"])

    # ---- linked third-party libraries that are NOT vendored source.
    #
    # Caddy is the clearest case in the project of the distinction the reset turns on:
    # web/symoneural-web/main.go is first-party Go that IMPORTS Caddy as an Apache-2.0
    # library. No Caddy source travels in the backup; `go mod download` reacquires it
    # against go.sum. It gets a row because a dependency nobody wrote down is a dependency
    # that goes missing.
    rows.append(["dep-caddy", "Caddy (linked library, not vendored)", "v2.11.4",
                 "Apache-2.0", "GO_MODULE", "go", "github.com/caddyserver/caddy/v2",
                 "https://github.com/caddyserver/caddy",
                 "pinned in web/symoneural-web/go.sum (573 entries)",
                 "symoneural-web", "BUILD+RUNTIME", "YES",
                 "cd web/symoneural-web && go mod download", "NO", "NO"])

    # ---- the Go toolchain requirement, which is a genuine restore blocker.
    rows.append(["dep-go-toolchain", "Go toolchain for symoneural-web",
                 f"required >= 1.25.1; host bootstrap {M.tool_version('go')}",
                 "BSD-3-Clause", "TOOLCHAIN", "apt + GOTOOLCHAIN=auto", "golang-go",
                 "https://go.dev", "golang.org/toolchain@v0.0.1-go1.25.1.linux-amd64",
                 "symoneural-web", "BUILD", "YES",
                 "Install Go >= 1.25.1, OR keep GOTOOLCHAIN=auto and allow the network "
                 "fetch. With GOTOOLCHAIN=local on a 1.24.x host the build FAILS rc=1. "
                 "The module and toolchain caches are NOT carried in the archive.",
                 "NO", "NO"])

    # ---- the GPU driver: not apt on this host, and saying so is the point
    rows.append(["dep-nvidia-driver", "NVIDIA driver", M.gpu(), "proprietary",
                 "PLATFORM_RUNTIME", "vendor installer", "nvidia-driver", "NVIDIA",
                 NUL, "all GPU components", "RUNTIME", "YES",
                 "Install the driver matching the CUDA toolkit above from NVIDIA. Not "
                 "redistributable; not carried in the backup.", "NO", "NO"])

    # ---- python distributions on the serving interpreter, one row each
    for name, ver, lic in serving_distributions():
        rows.append([f"py-serving-{name.lower()}", name, ver, lic, "PYTHON_PACKAGE",
                     "pip/apt", name, "PyPI", NUL, "symoneural-api", "RUNTIME", "YES",
                     "pip install -r restore/locks/serving-system.lock.txt",
                     "NO", "NO"])

    # ---- the other environments, one row each pointing at their lock
    for env, pins in lock_summary():
        if env == "serving-system":
            continue
        rows.append([f"pyenv-{env}", f"{env} virtualenv", f"{pins} pinned distributions",
                     "per-package; see the lock", "PYTHON_ENVIRONMENT", "pip", NUL,
                     "PyPI", NUL, env, "RUNTIME",
                     "YES" if env != "symoneural-ui" else "NO (component DISABLED)",
                     f"python3 -m venv <path>/.venv && <path>/.venv/bin/pip install -r "
                     f"restore/locks/{env}.lock.txt",
                     "NO", "NO"])

    return write_tsv("DEPENDENCIES.tsv", header, rows, minimum=100)
