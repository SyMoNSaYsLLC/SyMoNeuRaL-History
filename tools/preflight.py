#!/usr/bin/env python3
"""Check everything the API needs before it needs it, and say what to do about each gap.

    python3 tools/preflight.py            # human-readable, exits non-zero on any hard failure
    python3 tools/preflight.py --json     # same findings, machine-readable

The failure mode this replaces: `backend/api.py` dies at import with a traceback naming one
module, which tells an operator what Python could not find but not what to install, and stops
at the first problem so a box missing three packages takes three attempts to diagnose. This
checks everything, then reports every gap at once with the `apt` line that fixes it.

Two classes of requirement, and the distinction is the useful part:

  * **start** -- the process cannot come up without it. Measured: these are the distributions
    that end up in `sys.modules` when `backend/api.py` is imported.
  * **serve** -- the process comes up fine and one surface 500s on first request. `sympy` is
    the live case: `import ravencalc` is inside a function at `api.py:1166`, so a box with no
    sympy starts green and fails the moment somebody uses the calculator. Reporting a green
    start on such a box is exactly the overstatement commissioning exists to prevent.

Optional surfaces are reported and never fail the check: `cupy` absent means the training
bench is unavailable, not that the service is broken.

The declared lists below are checked against live measurement by
`backend/apps/test_preflight.py`, so adding an import to the serving path without adding it
here turns that test red rather than silently weakening this one.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Find the root by its marker, not by counting parents."""
    here = Path(__file__).resolve()
    for cand in (here, *here.parents):
        if (cand / "backend" / "api.py").is_file():
            return cand
    raise SystemExit(f"repo root not found above {here}: no backend/api.py marker")


ROOT = _repo_root()

#: module -> the Debian package that provides it. Every one of these was measured as
#: dpkg-owned; see docs/ops/SERVING-MANIFEST.md. Keeping the package name here is the point:
#: "No module named 'starlette'" is not an instruction, "apt install python3-starlette" is.
START = {
    "annotated_types": "python3-annotated-types",
    "anyio": "python3-anyio",
    "attr": "python3-attr",
    "bcrypt": "python3-bcrypt",
    "brotli": "python3-brotli",
    "click": "python3-click",
    "cryptography": "python3-cryptography",
    "email_validator": "python3-email-validator",
    "fastapi": "python3-fastapi",
    "httpx": "python3-httpx",
    "idna": "python3-idna",
    "pydantic": "python3-pydantic",
    "pydantic_core": "python3-pydantic-core",
    "pygments": "python3-pygments",
    "python_multipart": "python3-python-multipart",
    "rich": "python3-rich",
    "sniffio": "python3-sniffio",
    "starlette": "python3-starlette",
    "typing_extensions": "python3-typing-extensions",
    "websockets": "python3-websockets",
}

#: `ExecStart` runs api.py as a script, and `uvicorn.run` is inside the `__main__` guard at
#: api.py:4137 -- so uvicorn is needed to serve but never appears in an import of the module.
#: It would be invisible to a check that only measured imports.
START_SCRIPT_ONLY = {"uvicorn": "python3-uvicorn"}

#: Needed to serve a surface, not to start the process.
SERVE = {
    "sympy": ("python3-sympy", "/api/ravencalc",
              "import ravencalc is inside a function at api.py:1166"),
}

#: Absence disables one surface. Never a hard failure.
OPTIONAL = {
    "PIL": "the remix cover art surface",
    "yaml": "the studio exp plugin loader",
    "bs4": "the studio discovery plugin",
    "cupy": "the reinforce training bench",
    "cuda": "the reinforce training bench (CUDA python bindings)",
    "pyasic": "the ASIC rig probe",
    "playwright": "the studio discovery crawler",
    "rembg": "the sigils cut-out worker (runs in sigils/.venv, not here)",
    "torch": "the GGUF custom node (runs in a venv, not here)",
    "transformers": "the reinforce trainer (runs in training/.venv, not here)",
    "peft": "the reinforce trainer (runs in training/.venv, not here)",
    "trl": "the reinforce trainer (runs in training/.venv, not here)",
    "datasets": "the reinforce trainer (runs in training/.venv, not here)",
}


def resolves(name: str) -> tuple[bool, str]:
    """Resolve without importing -- importing to test importability is what we are replacing."""
    try:
        spec = importlib.util.find_spec(name)
    except Exception as exc:
        return False, f"error: {type(exc).__name__}"
    if spec is None:
        return False, "missing"
    try:
        import importlib.metadata as md
        return True, md.version(name)
    except Exception:
        return True, "present"


def structural() -> list[dict]:
    """The non-package prerequisites, each of which has bitten this repo before."""
    out: list[dict] = []

    gov = ROOT / "scripts" / "gpu-governor.sh"
    out.append({
        "check": "gpu-governor.sh present",
        "ok": gov.is_file(),
        "detail": str(gov),
        "fix": f"restore {gov.relative_to(ROOT)} -- api.py asserts on it at import (api.py:58) "
               "and will not start without it",
    })

    run = ROOT / "run"
    writable = run.is_dir() and os.access(run, os.W_OK)
    out.append({
        "check": "run/ exists and is writable",
        "ok": writable,
        "detail": str(run),
        "fix": f"mkdir -p {run} && chown google:google {run}",
    })

    # RUN must be <root>/run, never backend/run: gpu-governor.sh takes its mkdir lock in
    # <root>/run, and two lock directories would let two tenants each load weights onto a
    # 16 GB card. api.py:59-64 documents this as the reason ROOT is not HERE.
    out.append({
        "check": "run/ resolves beside backend/, not inside it",
        "ok": (ROOT / "run").is_dir() and not (ROOT / "backend" / "run").is_dir(),
        "detail": f"{ROOT / 'run'} present; {ROOT / 'backend' / 'run'} must not exist",
        "fix": "a backend/run directory means something computed ROOT as HERE; the governor "
               "and the API would take different locks and both could load weights",
    })

    cfg = ROOT / "run" / "config"
    out.append({
        "check": "run/config/ present (the real env-file directory)",
        "ok": cfg.is_dir(),
        "detail": f"{cfg} -- NOT /etc/symoneural/api.env, which does not exist on this box",
        "fix": f"mkdir -p {cfg}; runtimeconfig.py:126 resolves here",
    })

    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    findings: dict[str, list] = {"start": [], "serve": [], "optional": [], "structural": []}

    for name, pkg in sorted({**START, **START_SCRIPT_ONLY}.items()):
        ok, ver = resolves(name)
        findings["start"].append({"module": name, "package": pkg, "ok": ok, "version": ver})

    for name, (pkg, surface, why) in sorted(SERVE.items()):
        ok, ver = resolves(name)
        findings["serve"].append({"module": name, "package": pkg, "ok": ok,
                                  "version": ver, "surface": surface, "why": why})

    for name, surface in sorted(OPTIONAL.items()):
        ok, ver = resolves(name)
        findings["optional"].append({"module": name, "ok": ok, "version": ver,
                                     "surface": surface})

    findings["structural"] = structural()

    bad_start = [f for f in findings["start"] if not f["ok"]]
    bad_serve = [f for f in findings["serve"] if not f["ok"]]
    bad_struct = [f for f in findings["structural"] if not f["ok"]]
    hard = len(bad_start) + len(bad_serve) + len(bad_struct)

    if args.json:
        print(json.dumps({"findings": findings, "hard_failures": hard}, indent=2))
        return 1 if hard else 0

    print(f"preflight for {ROOT}")
    print(f"  interpreter: {sys.executable} {sys.version.split()[0]}")

    print(f"\n== required to START ({len(findings['start'])}) ==")
    for f in findings["start"]:
        print(f"  {'ok ' if f['ok'] else 'NO '} {f['module']:<18} {f['version']}")

    print(f"\n== required to SERVE a surface ({len(findings['serve'])}) ==")
    for f in findings["serve"]:
        print(f"  {'ok ' if f['ok'] else 'NO '} {f['module']:<18} {f['version']:<12} "
              f"{f['surface']}")
        if not f["ok"]:
            print(f"      why it is not a startup failure: {f['why']}")

    print(f"\n== optional surfaces ({len(findings['optional'])}) ==")
    for f in findings["optional"]:
        state = "available" if f["ok"] else "UNAVAILABLE"
        print(f"  {state:<12} {f['module']:<14} {f['surface']}")

    print("\n== structural ==")
    for f in findings["structural"]:
        print(f"  {'ok ' if f['ok'] else 'NO '} {f['check']}")
        if not f["ok"]:
            print(f"      {f['detail']}")
            print(f"      fix: {f['fix']}")

    if not hard:
        print("\nPREFLIGHT OK -- every hard requirement is present. "
              f"{sum(1 for f in findings['optional'] if not f['ok'])} optional "
              "surface(s) unavailable, which is not a failure.")
        return 0

    print(f"\nPREFLIGHT FAILED -- {hard} hard problem(s).")
    pkgs = [f["package"] for f in bad_start + bad_serve]
    if pkgs:
        print("\n  install the missing packages:")
        print(f"    sudo apt install {' '.join(sorted(set(pkgs)))}")
    for f in bad_serve:
        print(f"\n  NOTE: {f['module']} is missing. The service WILL start and "
              f"{f['surface']} will fail on first request. A green start does not mean "
              "this box can serve.")
    for f in bad_struct:
        print(f"\n  {f['check']}: {f['fix']}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
