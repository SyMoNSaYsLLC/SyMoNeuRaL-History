"""The structural switch, in its own leaf module so nothing has to import the package to ask.

Same shape as `apps/symoneuralstudio/gate.py`, and split out for the same reason: `routes.py`
is imported *by* `__init__.py`, so a module-level `from . import enabled` inside routes would
run against a half-initialised package.

There is no filter here. Garrett's standing instruction is that the project carries no filters
or safeguards until he has tested what he wants to pass, and a plugin runtime is the last place
to start adding them -- a plugin is imported into the serving process and can do anything the
process can do, so a gate on the HTTP surface is honest about being a switch and dishonest the
moment it is described as containment. `docs/isolation.md` says what containment would take.

What the token divides is narrower than in studio and worth stating: **reads are open, writes
and config are not.** Anyone may see which plugins are mounted, in what state, and what they
inject -- that is the observability the whole runtime is for, and hiding it makes the page
useless to the person it is for. Nobody without the token may mount, patch, reload, or read a
plugin's *config*, because a config is where a plugin's credentials live.
"""
from __future__ import annotations

import hmac
import os

__all__ = ["enabled", "token_ok", "present_token", "ENV_ENABLED", "ENV_TOKEN", "HEADER"]

ENV_ENABLED = "SYM_EXP_ENABLED"
ENV_TOKEN = "SYM_EXP_TOKEN"
HEADER = "X-Sym-Token"


def enabled() -> bool:
    """Both, or the mutation surface does not exist. `== "1"` and not truthiness, matching
    voice, asicminer and studio -- it reads like a boolean and is not one, and that is a
    confusion worth keeping consistent rather than solving differently in each package."""
    return os.environ.get(ENV_ENABLED) == "1" and bool(os.environ.get(ENV_TOKEN))


def token_ok(presented: str | None) -> bool:
    """Constant-time compare, so a wrong token cannot be discovered a character at a time.

    Both sides are encoded first. `hmac.compare_digest` accepts `str` only if it is ASCII and
    raises `TypeError` otherwise, so a presented token containing one non-ASCII character --
    a pasted em-dash, a smart quote, anything typed on a phone keyboard -- was a 500 out of a
    route that had already decided the answer was no. Comparing UTF-8 bytes is the same
    constant-time compare and answers 401 for every input.
    """
    want = os.environ.get(ENV_TOKEN) or ""
    if not want or not presented:
        return False
    try:
        return hmac.compare_digest(presented.encode("utf-8"), want.encode("utf-8"))
    except (AttributeError, UnicodeEncodeError):    # not a str, or unpaired surrogates
        return False


def present_token(headers, query=None) -> str | None:
    """Header, `Authorization: Bearer`, then query string.

    No cookie form, unlike studio's. That one exists because the proxied ComfyUI editor issues
    its own sub-resource requests from inside an iframe and a cookie is the only credential a
    browser attaches to those. Nothing here is framed and nothing here loads sub-resources
    under its own path, so a cookie would be a credential minted for no request -- and one
    scoped, inevitably, more broadly than the single path that justified it.
    """
    for key in (HEADER, HEADER.lower()):
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
    return None
