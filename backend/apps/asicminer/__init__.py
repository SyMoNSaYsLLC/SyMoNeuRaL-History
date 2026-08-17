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
# backend/apps/asicminer -> repo root is three levels up.
ROOT_HINT = HERE.parent.parent.parent
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


# --------------------------------------------------------------- firmware inventory

# Where firmware packages are looked for. Both are gitignored trees, so this is operator
# data on the operator's box -- nothing here is ever published or served as a file.
FW_DIRS = [
    ROOT_HINT / "references" / "Projects_Crypto",
    pathlib.Path.home() / "Downloads",
]

# A package is one of two shapes, and the difference decides whether it can be emulated:
#   .tar.gz  browser-upgrade package -- cert/fw/runme, what upgrade.cgi accepts
#   .zip     SD recovery package     -- per-file signatures, boots the card directly
FW_SUFFIXES = (".tar.gz", ".zip")


def _fw_id(p: pathlib.Path) -> str:
    """A stable id derived from the path, so the API never takes a filesystem path.

    The emulator is started by id, never by a caller-supplied path. That is the whole
    reason this exists: an endpoint that spawns a process against an arbitrary path is a
    remote file-read at best and worse than that at worst.
    """
    import hashlib
    return hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:16]


def packages() -> list[dict]:
    """Every firmware package actually present, with what we know about each.

    Read from disk rather than hardcoded, so the model list on the page cannot claim
    firmware that is not there -- or miss firmware that is.
    """
    out = []
    for d in FW_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or not f.name.endswith(FW_SUFFIXES):
                continue
            n = f.name.lower()
            vendor = ("antminer" if "antminer" in n
                      else "microbt" if ("whatsminer" in n or "microbt" in n)
                      else None)
            if vendor is None:
                continue
            out.append({
                "id": _fw_id(f),
                "name": f.name,
                "vendor": vendor,
                "bytes": f.stat().st_size,
                "kind": "sd" if f.name.endswith(".zip") else "browser",
            })
    return out


def package_by_id(pid: str) -> pathlib.Path | None:
    for d in FW_DIRS:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f.name.endswith(FW_SUFFIXES) and _fw_id(f) == pid:
                return f
    return None


# --------------------------------------------------------------- emulator control

QEMU_SCRIPT = ROOT_HINT / "scripts" / "qemu-antminer.sh"
EMU_PID = ROOT_HINT / "run" / "qemu-antminer.pid"


def emulator_status() -> dict:
    """Is an emulator running, and which package. Reads the pidfile, never guesses."""
    out = {"running": False, "pid": None, "package": None, "web": None}
    if not EMU_PID.is_file():
        return out
    try:
        raw = EMU_PID.read_text().split("\n")
        pid = int(raw[0].strip())
        os.kill(pid, 0)                      # signal 0: does it exist, are we allowed
    except (ValueError, IndexError, ProcessLookupError, PermissionError, OSError):
        # Stale pidfile -- the process died without cleaning up. Say not running rather
        # than reporting a pid that is gone.
        EMU_PID.unlink(missing_ok=True)
        return out
    out.update(running=True, pid=pid,
               package=(raw[1].strip() if len(raw) > 1 else None),
               web="http://127.0.0.1:8080")
    return out


def emulator_start(pid_str: str) -> dict:
    """Boot one firmware package under QEMU.

    Started BY ID, never by a path the caller supplies. An endpoint that execs against an
    arbitrary path is a remote file-read at best; `package_by_id` resolves only to files
    already enumerated from the two known directories.
    """
    if not enabled():
        return {"ok": False, "error": "surface disabled"}
    if not QEMU_SCRIPT.is_file():
        return {"ok": False, "error": "scripts/qemu-antminer.sh not found"}
    cur = emulator_status()
    if cur["running"]:
        return {"ok": False, "error": f"already running (pid {cur['pid']}) — stop it first"}

    pkg = package_by_id(pid_str)
    if pkg is None:
        return {"ok": False, "error": "no such firmware package"}
    if pkg.name.endswith(".zip"):
        return {"ok": False, "error": "SD recovery packages are not bootable this way; "
                                      "the emulator takes a browser-upgrade .tar.gz"}

    import subprocess
    log = ROOT_HINT / "run" / "qemu-antminer.log"
    try:
        proc = subprocess.Popen(
            [str(QEMU_SCRIPT), str(pkg), "--shell", "--serve"],
            stdout=log.open("wb"), stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
    EMU_PID.write_text(f"{proc.pid}\n{pkg.name}\n")
    return {"ok": True, "pid": proc.pid, "package": pkg.name,
            "web": "http://127.0.0.1:8080",
            "note": "booting to a shell; the guest web UI needs lighttpd started by hand"}


def emulator_stop() -> dict:
    st = emulator_status()
    if not st["running"]:
        return {"ok": True, "note": "nothing was running"}
    import signal as _sig
    try:
        # The script execs qemu, and start_new_session puts it in its own process group,
        # so signal the group -- killing only the pid can leave qemu orphaned.
        os.killpg(os.getpgid(st["pid"]), _sig.SIGTERM)
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
    EMU_PID.unlink(missing_ok=True)
    return {"ok": True, "stopped": st["pid"]}
