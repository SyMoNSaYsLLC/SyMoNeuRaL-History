"""SyMoNeuRaL Studio -- a local reasoning agent with tools, and the visual bench it drives.

Three exports, and they are the whole contract with `api.py`:

    from apps import symoneuralstudio as studio
    app.include_router(studio.router, prefix="/api/studio", tags=["studio"])   # before static
    app.include_router(studio.ui_router, prefix="/studio/comfy")               # before static
    Unit(**studio.status())          # the rack row -- same rule as voice: page first
    "studio": (60, 900)              # already present in api.py's _RATE_SUGGESTED

## What is in here, and what is deliberately not

| Module | Does |
|---|---|
| `workspace.py` | finds the live stack on startup and resolves paths against it |
| `registry.py` | turns typed Python functions into JSON Schema tool specs, stdlib only |
| `tools_impl/` | the functions themselves -- filesystem, host, stack, ComfyUI |
| `inference.py` | one interface over llama.cpp and Ollama; neither is spawned here |
| `agent.py` | the cognitive loop: call, execute, feed the raw result back, synthesise |
| `comfy.py` | ComfyUI HTTP + WebSocket, wrapped in the GPU lease cycle |
| `graph.py` | canvas document <-> ComfyUI prompt graph, validated against `/object_info` |
| `workflows.py` | the stock FLUX.1-schnell graph, built for the weights on this disk |
| `mcp_server.py` | the same functions over MCP/FastMCP, from an isolated venv |

**No node canvas is written here.** ComfyUI ships `comfyui_frontend_package` -- the production
editor, with snap-to-grid, typed port wiring, a searchable palette, link-release node
suggestions, per-node progress and inline results. Reimplementing that in vanilla JS was the
original plan and it was the wrong plan: it would have been a worse editor maintained by us
instead of a better one maintained upstream. `ui_router` proxies it at `/studio/comfy/` and
the Studio page frames it. Its frontend computes `api_base` from `location.pathname`, so it
addresses `/studio/comfy/api/...` on its own with no URL rewriting -- that is a supported
sub-path deployment, not a trick.

## The gate

Garrett's standing instruction is that the project carries no filters or safeguards: he sets
those after testing what he wants to pass. So there is no content filter here, no path
allow-list and no command blocklist -- `run_command` and `write_file` reach the whole host, as
asked, and `generate_image` renders whatever it is given.

What *is* here is the structural switch this repo already puts on every write-capable surface
(`apps/voice`, `apps/asicminer`): `SYM_STUDIO_ENABLED=1` **and** `SYM_STUDIO_TOKEN=<secret>`,
off unless both are set. That is not a filter on what the agent may do; it is the difference
between a shell on a box with a public IP being reachable by anyone and being reachable by
Garrett. With both set, it will happily `rm -rf` for him.

`GET /api/studio/state` stays tokenless and reports presence and absence only, following
`apps/gateway` -- the page has to be able to say "the surface is off" without holding a secret.
"""
from __future__ import annotations

import os

from .gate import enabled, token_ok  # noqa: F401

__all__ = ["router", "ui_router", "enabled", "token_ok", "status", "LABEL"]


def __getattr__(name: str):
    """`router` and `ui_router` are imported on first access, not at package import.

    PEP 562, and not for elegance. `routes.py` imports FastAPI; the tools, the registry and
    the workspace do not. `mcp_server.py` runs from an isolated venv holding only `fastmcp`
    -- the house convention for extra dependencies here, and every other app venv in this
    repo is `include-system-site-packages = false` -- so an eager `from .routes import router`
    at the top of this file made `import apps.symoneuralstudio` fail with
    `ModuleNotFoundError: fastapi` inside that venv, which is a real thing that happened
    rather than a hypothetical.

    The alternatives were worse: installing FastAPI into the MCP venv to satisfy an import
    nothing there uses, or letting the MCP server reach into the modules by file path and
    lose the package-relative imports `tools_impl` needs. This costs one function and no
    behaviour -- `api.py` touches `studio.router` at import time, so the routes module is
    still loaded during startup, and a syntax error in it still fails the boot loudly.
    """
    if name in ("router", "ui_router"):
        from . import routes
        return getattr(routes, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


LABEL = "SyMoNeuRaL Studio"

# `enabled()` and `token_ok()` live in `gate.py` and are re-exported here so callers can keep
# saying `studio.enabled()`. See that module for why the split exists (import cycle, not taste).


def status() -> dict:
    """The rack unit, keys matching `api.py`'s `Unit` model.

    Everything reported here is read at call time -- the workspace root from disk, the tool
    count from the registry that actually loaded. `state` is `offline` when the switches are
    unset, because that is what a visitor is looking at, and `ready` otherwise. It is never
    `busy`: this row describes the orchestrator, and the work it orchestrates is already
    reported by the surface that does it (`comfy`, `chat`). A second row lighting up for
    somebody else's job is the decorative-indicator failure CLAUDE.md forbids.
    """
    from . import registry, workspace, tools_impl  # noqa: F401  (imported for registration)

    if not enabled():
        state = "offline"
        detail = ("set SYM_STUDIO_ENABLED=1 and SYM_STUDIO_TOKEN=<secret> to switch it on; "
                  "off by default because it can write to the host")
    else:
        state = "ready"
        if workspace.ROOT is None:
            # A rack row must not be the thing that raises. `workspace.root()` raises when
            # discovery found nothing, and `api.py:build_status()` calls this inline, so one
            # unlocatable checkout took down the whole dashboard. Reported as `offline` because
            # `Unit.state` is `Literal["ready","busy","queued","offline"]` and because a Studio
            # that cannot find the stack cannot do the job the row advertises -- the detail says
            # which switch fixes it.
            state = "offline"
            detail = ("no stack found: set SYM_STUDIO_ROOT to the checkout "
                      f"({len(registry.names())} tools registered, none can reach disk)")
        else:
            detail = (f"{len(registry.names())} tools · workspace {workspace.ROOT} "
                      f"(found by {workspace.found_by()})")
    return {
        "id": "studio",
        "label": LABEL,
        "slot": "1U",
        "state": state,
        "bus": "gpu",
        "href": "/studio",
        "spec": "local agent · MCP tools · ComfyUI bench",
        "detail": detail,
    }
