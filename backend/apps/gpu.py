"""The lease's Python side. Currently one thing: telling the governor what it evicts.

`scripts/gpu-governor.sh` holds the lock and must keep holding it -- `mkdir` is the atomic
primitive, it has no runtime dependency, and it survives `api.py` being dead, which a governor
living inside the API process cannot. It is also proven: 46 samples, 0 two-holder, 0
two-resident, negative control red on 25 of 27. Rewriting the component that holds the central
invariant means re-proving it, and the proof is the expensive part.

## What is NOT here, and why -- read this before adding to it

`class GpuQueue` was on the list for this extraction and **could not come.** It calls
`bus.announce()` (`api.py:996`), `push_rack()` (`api.py:2804`) and `run()`, and `push_rack`
calls `build_status()` -- which is the rack, and the rack is most of `api.py`. Moving
`GpuQueue` therefore means either dragging the rack out with it, which is `SPLIT-API` stage
1's job and not this commit's, or injecting three callables into its constructor, which
changes the call site that this extraction was required not to change.

So `GpuQueue` extraction is **blocked behind the rack extraction**, not behind anything here.
That is a sequencing finding, and it is written down rather than worked around.
"""
from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import subprocess

log = logging.getLogger("symoneural.api")

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: The governor. Spelled from the repository root rather than relative to this file, because
#: this module may be imported from `backend/` or from `backend/apps/` depending on the caller.
GOVERNOR = ROOT / "scripts" / "gpu-governor.sh"


async def record_engine(pid: int) -> None:
    """Tell the governor which process is actually holding the card.

    The lease records the *holder* -- the process that took the lock. During a live render
    `run/gpu.lock.d/holder` read `image 1509`, and 1509 is this API: the process that
    spawned the engine and is waiting on it. Evicting by that pid would stop the API and
    leave the engine resident. So the spawned pid is recorded separately and eviction
    signals it by identity instead of by `pkill -f <pattern>`.

    The pgid is offered only when the child is genuinely a group leader. `run()` below
    passes `start_new_session=True`, so its children are; `_llama` at the chat spawn and
    `sigils.render._spawn` are not, and their process group is this API's own. Handing the
    governor that pgid would arm a group kill aimed at ourselves -- strictly worse than the
    pattern kill being replaced. `os.getpgid(pid) == pid` is the check that distinguishes
    them, and the governor re-verifies it rather than trusting us.

    Best-effort by design: a failure here costs the identity path and falls back to the
    pattern arms, which is the behaviour that exists today. It must never fail a render.
    """
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        return
    argv = [str(GOVERNOR), "engine", str(pid)]
    if pgid == pid:
        argv.append(str(pgid))
    try:
        # `to_thread`, not a bare `subprocess.run`. This is called from two coroutines, and a
        # blocking exec in either stalls the WHOLE event loop for up to the 10 s timeout --
        # no other request, no streaming token, and not /api/status. Shipped that way and
        # caught in review: every engine spawn would have looked like an outage to the
        # watchdog that polls /api/status, which is a monitor made useless by its own server.
        await asyncio.to_thread(
            subprocess.run, argv, capture_output=True, timeout=10, check=False)
    except Exception:  # noqa: BLE001 -- see the docstring: never fail a render over this
        log.warning("could not record engine pid %s with the governor", pid)
