"""SyMoNeuRaL Streamer -- the IPTV surface, and the Guide that filters it.

Two units were merged here on Garrett's instruction: *"symon guide and symon tuner should be
migrated together"*, then *"you need to migrate tuner and guide to be 1"*. They had the same
`href` (`/tuner.html`), so the rack was rendering one page twice and the two rows disagreed
with each other. One package, one row, one namespace.

The seam is kept, not dissolved. `routes.py` and the modules beside it are the tuner: HLS
sessions, playlist parsing, SSRF-pinned fetches. `guide/` is the library half -- matching,
clustering, prompt-building -- plus its own thin router. Guide never opens a socket and owns
no weights (see `guide/__init__.py` for why that is the architecture and not a shortcut), so
folding it in costs the tuner nothing.

Four exports, and they are the whole contract with `api.py`:

    from apps import streamer
    app.include_router(streamer.tuner_router, prefix="/api/tuner")
    app.include_router(streamer.guide_router, prefix="/api/guide")
    Unit(**streamer.status())                 # the rack unit; keys match api.py's Unit model

`router` and `status` remain as aliases of the tuner pair because that is what `status()` has
always meant here -- the unit is the tuner, and the guide is a filter over its channel list,
not a second rack row. The explicit `tuner_*` names exist so a reader of `api.py` can tell
which of the two surfaces a line is wiring; a bare `router` in a merged package is exactly the
ambiguity this rename removes.

The visitor's playlist and credentials live in their browser and are sent per request; nothing
is written to disk and nothing credential-bearing is logged. A visitor-supplied URL is
validated by `safefetch.validate_url`, which judges the *resolved address* and pins it, and the
pinned address is the only thing ever connected to -- ffmpeg never sees a URL, only `pipe:0`,
which is what keeps the SSRF control real and keeps the credentials out of `argv`.
"""
from __future__ import annotations

from . import guide                                              # noqa: F401
from .guide.routes import router as guide_router
from .routes import router as tuner_router, status as tuner_status

router = tuner_router
status = tuner_status

__all__ = ["guide", "guide_router", "router", "status", "tuner_router", "tuner_status"]
