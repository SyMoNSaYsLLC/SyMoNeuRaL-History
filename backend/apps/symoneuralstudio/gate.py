"""The structural switch, in its own module so nothing has to import the package to ask.

`__init__.py` re-exports these and `routes.py` imports them directly. Splitting them out is
not decoration: `routes.py` is imported *by* `__init__.py`, so a module-level
`from . import enabled` inside routes would run against a half-initialised package. One tiny
leaf module removes the cycle instead of hiding it behind a function-local import.

There is no content filter here and no allow-list -- Garrett's standing instruction is that
the project carries no filters or safeguards until he has tested what he wants to pass. This
is the same on/off switch `apps/voice` and `apps/asicminer` already put on write-capable
surfaces, and nothing more: with both variables set, every tool runs unrestricted.
"""
from __future__ import annotations

import hmac
import os

__all__ = ["enabled", "token_ok", "present_token", "ENV_ENABLED", "ENV_TOKEN", "HEADER",
           "HEADER_LEGACY", "COOKIE", "COOKIE_LEGACY", "COOKIE_PATH"]

ENV_ENABLED = "SYMONEURAL_STUDIO_ENABLED"
ENV_TOKEN = "SYMONEURAL_STUDIO_TOKEN"
HEADER = "X-Symoneural-Token"

# The name this header had until the rename, still accepted and deliberately second. Not
# politeness to old scripts: `site/studio.js` is cached by the browser, so a visitor holding
# yesterday's copy sends the old name until that cache turns over, and renaming only the
# server would 401 them while their token is correct. New name wins when both are present,
# matching `symoneuralenv.promote()` -- one precedence rule for the whole rename.
HEADER_LEGACY = "X-Sym-Token"

# Only the proxied editor uses this, and only under its own path. See `present_token`.
COOKIE = "symoneural_studio"

# And the legacy cookie has a sharper reason to be read than the legacy header does. This one
# is minted by `routes.editor` on a request the operator already made, so a tab that is open
# right now is holding `sym_studio` and will keep sending it: the editor's sub-resource
# requests are the ONLY thing that credential exists for, and they carry no header and no
# query string to fall back on (see `present_token`). Reading one name and minting the other
# would break the framed editor for every open session at the moment of deploy -- which is
# exactly the seven-aborted-requests failure `tests/studio.mjs` was written to catch. Read
# both, mint only `COOKIE`, so an open session heals on its next entry-document load.
COOKIE_LEGACY = "sym_studio"
COOKIE_PATH = "/studio/comfy"


def enabled() -> bool:
    """Both, or the surface does not exist. `== "1"` and not truthiness, matching voice and
    asicminer -- it reads like a boolean and is not one, and that is a confusion worth keeping
    consistent rather than solving differently in each package."""
    return os.environ.get(ENV_ENABLED) == "1" and bool(os.environ.get(ENV_TOKEN))


def token_ok(presented: str | None) -> bool:
    """Constant-time compare, so a wrong token cannot be discovered a character at a time.

    Both sides are encoded first. `hmac.compare_digest` accepts `str` only if it is ASCII and
    raises `TypeError` otherwise, so a presented token carrying one non-ASCII character -- a
    pasted em-dash, a smart quote, anything a phone keyboard produces -- was a 500 out of a
    gate that had already decided the answer was no. It matters more here than in
    `apps/symoneuralexp/gate.py`, where the same fix landed first: this is the gate in front of
    `run_command` and `write_file`, and `present_token` below also reads a **cookie**, which is
    a third path whose contents this process does not choose. Comparing UTF-8 bytes is the same
    constant-time compare and answers a plain no for every input.
    """
    want = os.environ.get(ENV_TOKEN) or ""
    if not want or not presented:
        return False
    try:
        return hmac.compare_digest(presented.encode("utf-8"), want.encode("utf-8"))
    except (AttributeError, UnicodeEncodeError):    # not a str, or unpaired surrogates
        return False


def present_token(headers, query, cookies=None) -> str | None:
    """Pull the token out of a request: header, then query string, then cookie.

    The query-string form exists because two real browser contexts cannot set a header:
    `<img src="/api/studio/image?...">` and `new WebSocket(...)`. Refusing to accept it there
    would not make the surface safer, it would make images and live progress impossible.

    The cookie form exists for exactly one thing, and an earlier version of this docstring
    said it was "worse" than the query string, which was written before the editor was framed
    and turned out to be a claim about a situation that does not arise. The proxied ComfyUI
    editor at `/studio/comfy/` loads its own assets by *relative* URL -- `assets/index-*.js`,
    `materialdesignicons.min.css`, `api/userdata/user.css` -- from inside an iframe. Those
    requests carry no header (no JavaScript of ours issues them) and no query string (the
    token was on the iframe's URL, not on theirs), so every one of them 401'd and the editor
    never booted. That is not hypothetical either: it is what `tests/studio.mjs` reported,
    seven aborted requests and a timeout waiting for the canvas.

    A cookie is the only mechanism a browser applies to sub-resource requests it issues on its
    own. It is minted by `routes.editor` on the entry document, scoped to `COOKIE_PATH` so it
    is never sent to `/api/studio` or to any other part of the site, `SameSite=Strict`, and
    given no expiry so it dies with the tab -- the same lifetime as the `sessionStorage` copy
    the page holds.

    It is also `HttpOnly`, and that flag wants stating narrowly: it keeps *this copy* out of
    `document.cookie` and it protects nothing about the token itself. The same secret is on the
    iframe's own URL -- `page.js:373` sets `frame.src = '/studio/comfy/?token=' + token()` --
    so it sits in `location.search` of the framed document, readable by any script ComfyUI
    loads there, its own frontend bundle and any custom node alike. `page.js:274` puts it on
    image URLs the same way, and the page holds a copy in `sessionStorage` besides. Anything
    that can run script in either document already has the operator token. `HttpOnly` is
    hygiene on one copy of several, not a boundary, and this docstring read as though it were.
    """
    # Both spellings, new first. Both cases of each, because this is handed a plain dict by
    # the tests as often as a case-insensitive Starlette `Headers`.
    for key in (HEADER, HEADER.lower(), HEADER_LEGACY, HEADER_LEGACY.lower()):
        value = headers.get(key)
        if value:
            return value
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if query is not None:
        found = query.get("token")
        if found:
            return found
    if cookies:
        for name in (COOKIE, COOKIE_LEGACY):
            found = cookies.get(name)
            if found:
                return found
    return None
