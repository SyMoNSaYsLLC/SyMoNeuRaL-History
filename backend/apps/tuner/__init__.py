"""SyMoNeuRaL Tuner -- an IPTV surface the visitor brings their own subscription to.

Two exports, and they are the whole contract with `api.py`:

    from apps.tuner import router, status
    app.include_router(router, prefix="/api/tuner")
    ...
    Unit(**status())            # the rack unit; keys match api.py's Unit model

Everything else is internal. See `README.md` in this directory for what is implemented, what
is not, and what the wiring needs.

The design in one paragraph: the visitor's playlist and credentials live in their browser and
are sent per request; nothing is written to disk and nothing credential-bearing is logged. A
visitor-supplied URL is validated by `safefetch.validate_url`, which judges the *resolved
address* and pins it, and the pinned address is the only thing ever connected to -- ffmpeg
never sees a URL, only `pipe:0`, which is what keeps the SSRF control real and keeps the
credentials out of `argv`. Output is HLS by stream copy, capped at a small number of concurrent
sessions with idle and lifetime timeouts and a reaper.
"""
from __future__ import annotations

from .routes import router, status

__all__ = ["router", "status"]
