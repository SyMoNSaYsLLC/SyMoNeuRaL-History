#!/usr/bin/env python3
"""Local experimental control service for the Donnie Dispatch Board.

Hosts two things on 127.0.0.1 only:

  1. the REAL DispatchOS router, at /api/dispatchos/* -- the same APIRouter that
     production api.py would mount. The benchmark therefore exercises the real
     routes and the real data model; only the host differs, and mounting it into
     production is a separate explicit gate.

  2. the benchmark control surface, at /lab/* -- start, stop, status, report,
     clear, and a telemetry poll for the board.

Local only, by construction: it binds 127.0.0.1, and every handler additionally
checks the peer address and refuses forwarded headers -- the same shape as
`_require_local()` in production api.py. It is not behind Caddy, is not in
systemd, and is not deployed.

Polling rather than SSE/WebSocket: the board needs a status object a few times a
second, and a plain GET is the smallest thing that does that. No WebSocket
redesign for a local test harness.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/home/google/Symoneural/.claude/worktrees/native-hybrid-gpu-player")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "backend"))

from fastapi import FastAPI, HTTPException, Request       # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel                            # noqa: E402

from apps.dispatchos import routes as dispatchos_routes   # noqa: E402
from apps.dispatchos import init_db                       # noqa: E402
from capacity_lab.core import Sampler, known_run_ids, REPORT_DIR  # noqa: E402
from capacity_lab.harness import Harness, STOP, clear_run_data    # noqa: E402

LOCAL_ONLY = ("127.0.0.1", "::1", "localhost")

app = FastAPI(title="DispatchOS + Capacity Lab (local experimental)",
              docs_url=None, redoc_url=None, openapi_url=None)

# The real application surface. Same router production would mount.
app.include_router(dispatchos_routes.router, prefix="/api/dispatchos",
                   tags=["dispatchos"])


def _require_local(request: Request) -> None:
    """Peer address is the real check; a forwarded header means someone proxied
    this, which is exactly the case the peer check alone would wave through."""
    peer = request.client.host if request.client else ""
    forwarded = any(h in request.headers for h in
                    ("x-forwarded-for", "x-real-ip", "forwarded"))
    if peer not in LOCAL_ONLY or forwarded:
        raise HTTPException(status_code=403, detail="local only")


# ------------------------------------------------------------------ run state
class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.run_id = None
        self.mode = None
        self.scenario = None
        self.users = 0
        self.started_at = None
        self.last_report = None
        self.error = None
        self.thread = None
        self.sampler = None


ST = _State()


class StartRun(BaseModel):
    # The ten buttons send the SLOTS they selected, not a count -- so the server
    # records which slots were chosen, and the count is derived from them.
    slots: list[int] = []
    ai: str = "off"
    scenario: str = "booking"
    timeout: float = 300.0


@app.get("/lab/health")
def health(request: Request) -> dict:
    _require_local(request)
    return {"ok": True, "service": "capacity-lab control (local experimental)"}


@app.post("/lab/start")
def start(body: StartRun, request: Request) -> dict:
    _require_local(request)
    slots = sorted({int(s) for s in body.slots if 1 <= int(s) <= 10})
    if not slots:
        raise HTTPException(400, "select at least one concurrent-user slot")
    if len(slots) > 2:
        # Slice 1.5 cap. The board renders all ten buttons; the server is what
        # actually refuses, so a UI edit cannot lift the gate.
        raise HTTPException(403, f"slice 1.5 is capped at 2 concurrent users "
                                 f"(selected {len(slots)}: {slots}). Higher "
                                 f"concurrency requires the slice 2 approval.")
    if body.ai not in ("on", "off"):
        raise HTTPException(400, "ai must be on or off")

    with ST.lock:
        if ST.running:
            raise HTTPException(409, f"a run is already active: {ST.run_id}")
        ST.running = True
        ST.mode = body.ai
        ST.scenario = body.scenario
        ST.users = len(slots)
        ST.started_at = time.time()
        ST.error = None
        ST.last_report = None
        ST.run_id = None

    def _go():
        try:
            h = Harness(base_url="http://127.0.0.1:8811", scenario=body.scenario,
                        ai_mode=body.ai, users=len(slots), timeout=body.timeout,
                        sample_interval=0.05)
            rep = h.run()
            with ST.lock:
                ST.last_report = rep
                ST.run_id = rep.get("run_id")
        except Exception as e:                    # noqa: BLE001
            with ST.lock:
                ST.error = f"{type(e).__name__}: {e}"
        finally:
            with ST.lock:
                ST.running = False

    ST.thread = threading.Thread(target=_go, daemon=True)
    ST.thread.start()
    return {"accepted": True, "slots": slots, "concurrent_users": len(slots),
            "ai": body.ai, "scenario": body.scenario}


@app.post("/lab/stop")
def stop(request: Request) -> dict:
    _require_local(request)
    STOP.set()
    return {"stopping": True, "note": "pending sessions will abort"}


@app.get("/lab/status")
def status(request: Request) -> dict:
    """Live telemetry poll for the board. Everything here is read from the
    machine; anything not instrumented is absent rather than invented."""
    _require_local(request)
    sys.path.insert(0, str(REPO / "engines" / "symoneural-hybrid"))
    import gpu_guard                              # noqa: PLC0415

    apps = gpu_guard.compute_apps()
    snap = gpu_guard.gpu_snapshot()
    legacy = []
    for p in Path("/proc").iterdir():
        if p.name.isdigit():
            try:
                if (p / "comm").read_text().strip() == "symoneural-llm":
                    legacy.append(int(p.name))
            except OSError:
                pass

    sysinfo = {}
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            k, _, v = line.partition(":")
            mem[k] = int(v.split()[0])
        sysinfo["ram_used_mib"] = round((mem["MemTotal"] - mem["MemAvailable"]) / 1024, 1)
        sysinfo["ram_total_mib"] = round(mem["MemTotal"] / 1024, 1)
        sysinfo["load1"] = float(open("/proc/loadavg").read().split()[0])
    except Exception:
        pass

    with ST.lock:
        running, run_id, mode = ST.running, ST.run_id, ST.mode
        users, err = ST.users, ST.error
        rep = ST.last_report

    return {
        "running": running, "run_id": run_id, "error": err,
        "ai_requests": "ENABLED" if mode == "on" else "DISABLED",
        # residency is a separate fact from whether AI requests are enabled --
        # "AI off" must never be confused with "VRAM reclaimed"
        "ai_engine": "LOADED" if apps else "UNLOADED",
        "concurrent_users": users,
        "gpu": {"vram_used_mib": snap["vram_used_mib"],
                "vram_total_mib": snap.get("vram_free_mib", 0) + snap["vram_used_mib"],
                "utilization_pct": snap["util_pct"], "power_w": snap["power_w"],
                "temperature_c": snap["temp_c"],
                "compute_apps": len(apps),
                "compute_pids": [p for p, _ in apps]},
        "legacy_symoneural_llm_pids": legacy,
        "system": sysinfo,
        "last_report": rep,
    }


@app.get("/lab/report/{run_id}")
def report(run_id: str, request: Request):
    _require_local(request)
    p = REPORT_DIR / f"{run_id}.json"
    if not p.exists():
        raise HTTPException(404, "no such report")
    return JSONResponse(json.loads(p.read_text()))


@app.get("/lab/reports")
def reports(request: Request) -> dict:
    _require_local(request)
    return {"runs": known_run_ids()}


@app.delete("/lab/report/{run_id}")
def clear(run_id: str, request: Request) -> dict:
    """Scoped clear: the JSON report AND that run's synthetic bookings."""
    _require_local(request)
    try:
        rep = clear_run_data(run_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    from apps.dispatchos import clear_benchmark_run, BookingError
    try:
        book = clear_benchmark_run(run_id)
    except BookingError as e:
        raise HTTPException(400, str(e)) from None
    return {"report": rep, "bookings": book}


@app.get("/board", response_class=HTMLResponse)
def board() -> str:
    return (HERE / "ui" / "dispatch-board.html").read_text()


if __name__ == "__main__":
    import uvicorn
    init_db()
    # 127.0.0.1 only. Not behind Caddy, not in systemd, not deployed.
    uvicorn.run(app, host="127.0.0.1", port=8811, log_level="warning")
