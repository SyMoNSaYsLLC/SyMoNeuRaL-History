"""SyMoNeuRaL Miner (ASIC) -- an operator surface for Antminer and MicroBT rigs.

This is the ASIC control panel. It is **not** the GPU Ravencoin miner, which is a separate
surface at `backend/apps/cryptominer/`. `.claude/HANDOVER.md` §5 keeps them apart on
purpose and so does this module: they share no code, no route prefix and no rack unit.

## What this is for

The site's rack reads real sensors off the RTX 5070 Ti. This does the same thing for mining
hardware: connect to Antminer (Bitmain) and MicroBT/Whatsminer rigs on the operator's
network and report what they are actually doing. It is an **operator tool**, not a public
demo -- a visitor's rig sits on the visitor's LAN and this server cannot reach it, so there
is no honest public version of a live panel.

## Two switches, and it is off unless both are set

    SYM_ASIC_ENABLED=1              # the surface exists at all
    SYM_ASIC_TOKEN=<shared secret>  # every request must present it
    SYM_ASIC_RIGS=10.0.0.11,10.0.0.12   # optional; addresses to probe

Off by default and 503 with both unset. That mirrors `backend/apps/cryptominer/`, which
already refuses to start without `SYM_MINING_ENABLED=1`, and it matters more here: this box
serves the public internet, and rig control is not something to expose by accident. Without
a token there is no route, so a misconfiguration fails closed rather than open.

## Honesty

With no rigs configured or none reachable, the state is **offline** and every reading is
null. There is no demo rig and no placeholder hashrate. Any number that reaches a page from
here was read off real hardware and is **measured**; if a figure is ever added that is not,
it must be labelled vendor or projected at the point it is introduced.

## Why a subprocess

pyasic needs 31 packages. The serving API runs on the system interpreter, which carries
fastapi, uvicorn, pydantic and sympy and nothing else, deliberately. So the rig protocols
live in `backend/apps/asicminer/.venv` behind `probe.py`, which prints JSON, and this module
execs it. Same boundary the API already uses for the GPU governor and the engine binaries.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
VENV_PY = HERE / ".venv" / "bin" / "python"
PROBE = HERE / "probe.py"
SCAN = HERE / "scan.py"

PROBE_TIMEOUT = 30.0        # probe.py already caps each rig at 8s; this bounds the whole run


def enabled() -> bool:
    return os.environ.get("SYM_ASIC_ENABLED") == "1" and bool(os.environ.get("SYM_ASIC_TOKEN"))


def rigs() -> list[str]:
    """Configured rig addresses. Empty is the normal state on a box with no ASICs."""
    raw = os.environ.get("SYM_ASIC_RIGS", "")
    return [h.strip() for h in raw.split(",") if h.strip()]


def installed() -> bool:
    return VENV_PY.is_file() and PROBE.is_file()


def token_ok(presented: str | None) -> bool:
    """Constant-time compare, so a wrong token cannot be found a character at a time."""
    import hmac
    want = os.environ.get("SYM_ASIC_TOKEN") or ""
    if not want or not presented:
        return False
    return hmac.compare_digest(presented, want)


async def probe(hosts: list[str] | None = None) -> dict:
    """Run the probe in its own interpreter and return parsed JSON.

    Never raises. Every failure path returns the same shape with an `error` string, because
    the rack renders this and a surface that throws takes the whole status endpoint with it.
    """
    hosts = rigs() if hosts is None else hosts
    if not installed():
        return {"rigs": [], "error": "asicminer venv not installed -- see backend/apps/asicminer/README.md"}
    if not hosts:
        return {"rigs": [], "error": None}

    try:
        proc = await asyncio.create_subprocess_exec(
            str(VENV_PY), str(PROBE), *hosts,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=PROBE_TIMEOUT)
    except asyncio.TimeoutError:
        return {"rigs": [], "error": f"probe exceeded {PROBE_TIMEOUT:.0f}s"}
    except Exception as e:
        return {"rigs": [], "error": f"{e.__class__.__name__}: {e}"}

    if proc.returncode != 0:
        return {"rigs": [], "error": f"probe exited {proc.returncode}: {err.decode()[:200]}"}
    try:
        return json.loads(out.decode())
    except json.JSONDecodeError as e:
        return {"rigs": [], "error": f"probe printed non-JSON: {e}"}


async def discover(cidr: str) -> dict:
    """Find rigs on a private network. Operator-gated, and refuses public ranges.

    The refusal lives in `scan.py` rather than here, so it applies however the scanner is
    invoked -- the CLI and this wrapper cannot drift apart into one being safe and the other
    not. This adds the second gate: the surface has to be switched on at all.
    """
    if not enabled():
        return {"rigs": [], "error": "surface disabled — set SYM_ASIC_ENABLED=1 and "
                                     "SYM_ASIC_TOKEN"}
    if not (VENV_PY.is_file() and SCAN.is_file()):
        return {"rigs": [], "error": "asicminer venv not installed"}
    try:
        proc = await asyncio.create_subprocess_exec(
            str(VENV_PY), str(SCAN), cidr,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        # A /20 at 0.6s per host with 256 in flight is roughly ten seconds; allow slack
        # for a slow network without letting a scan pin a worker indefinitely.
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120.0)
    except asyncio.TimeoutError:
        return {"rigs": [], "error": "scan exceeded 120s"}
    except Exception as e:
        return {"rigs": [], "error": f"{e.__class__.__name__}: {e}"}
    if proc.returncode != 0:
        return {"rigs": [], "error": f"scan exited {proc.returncode}: {err.decode()[:200]}"}
    try:
        return json.loads(out.decode())
    except json.JSONDecodeError as e:
        return {"rigs": [], "error": f"scan printed non-JSON: {e}"}


async def selftest() -> dict:
    """Check the venv without touching the network. Used by the CLI and the tests."""
    if not installed():
        return {"ok": False, "error": "venv not installed"}
    try:
        proc = await asyncio.create_subprocess_exec(
            str(VENV_PY), str(PROBE), "--selftest",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return json.loads(out.decode())
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def unit_state(result: dict | None) -> tuple[str, str]:
    """(state, detail) for the rack. Honest by construction.

    `offline` is the correct answer for a box with no rigs, and it is the default. The rack
    must never show a mining surface as `ready` on the strength of the code existing.
    """
    if not enabled():
        return "offline", "disabled — set SYM_ASIC_ENABLED=1 and SYM_ASIC_TOKEN"
    if not installed():
        return "offline", "control venv not installed"
    if result is None:
        return "offline", "not yet probed"
    if result.get("error"):
        return "offline", str(result["error"])[:90]
    found = [r for r in result.get("rigs", []) if r.get("reachable")]
    if not found:
        n = len(result.get("rigs", []))
        return "offline", (f"{n} configured, none answering" if n else "no rigs configured")
    th = sum(r["hashrate_th_s"] for r in found if r.get("hashrate_th_s") is not None)
    vendors = sorted({r["vendor"] for r in found if r.get("vendor")})
    return "ready", (f"{len(found)} rig{'s' if len(found) != 1 else ''} answering"
                     + (f" · {th:.1f} TH/s measured" if th else "")
                     + (f" · {', '.join(vendors)}" if vendors else ""))
