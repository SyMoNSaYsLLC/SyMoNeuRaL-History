"""The HTTP surface for accounts. Mounted at `/api/accounts` by `backend/api.py`.

The module beside this one does all the thinking -- hashing, throttling, session rows.
This file is deliberately thin, and everything in it is about the boundary: what a
stranger may send, what a stranger may see, and what goes in the cookie.

Four decisions that are easy to get wrong and are made here on purpose:

**The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.** HttpOnly is the
whole point -- a session token readable by `document.cookie` is a session token that any
injected script exfiltrates. `Secure` is conditional on the request scheme rather than
hardcoded, because hardcoding it breaks `http://127.0.0.1:8800` for anybody developing
against the API directly, and hardcoding it off would ship a token over plaintext.

**A wrong password and an unknown address give the same answer.** `verify()` already pays
for a full scrypt against a dummy hash so the timing does not answer "is this person a
customer"; returning a different *message* would give away for free what that cost buys.

**The throttle's `Retry-After` is reported, because a lockout the visitor cannot see is
indistinguishable from a broken login.** That is a reading, not a leak: it is about the
request in front of us and says nothing about whether the account exists.

**Nothing here invents a plan, a tier or a price.** `.claude/CLAUDE.md` forbids it, and a
route that returned a `plan` field would be the place a price eventually appeared.
Pricing questions go to symonsayadmin@symoneural.com.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from . import (AccountExists, AccountsError, AccountsUnavailable, InvalidEmail,
               Throttled, WeakPassword, change_password, create_account, enabled,
               init_db, issue_session, read_session, revoke_all_sessions,
               revoke_session, session_ttl_s, sessions_for, unit_state, verify)

log = logging.getLogger("symoneural.accounts")

router = APIRouter(tags=["accounts"])

COOKIE = "sym_session"


# Every field has a default for the same reason the tuner's models do: a *missing*
# required field makes pydantic raise a ValidationError whose `input` is the whole
# request body, and FastAPI serialises that into the 422 -- which would echo the
# password back inside an error document. With defaults there is no validation path
# that can touch these values; the handlers check them by hand.
class SignupBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = ""
    password: str = ""
    display_name: str = ""
    quote_id: str = ""


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = ""
    password: str = ""


class PasswordBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    old: str = ""
    new: str = ""


def _client_ip(request: Request) -> str:
    """The visitor's address, as far as it can honestly be known.

    Caddy fronts everything, so the socket address is always the loopback proxy and
    `X-Forwarded-For` is the only thing carrying the real client. Take the FIRST hop:
    later entries are appended by intermediaries and the first is the one Caddy wrote.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def _require_enabled() -> None:
    if not enabled():
        raise HTTPException(503, "accounts are not switched on for this box")


def _set_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token,
        max_age=session_ttl_s(), httponly=True, samesite="lax",
        # Not hardcoded: see the module docstring. `url.scheme` is what the request
        # actually arrived on, which behind Caddy is https in production and http for
        # anybody hitting 127.0.0.1:8800 directly.
        secure=request.url.scheme == "https",
        path="/")


def _current(request: Request) -> dict:
    token = request.cookies.get(COOKIE, "")
    sess = read_session(token) if token else None
    if not sess:
        raise HTTPException(401, "not signed in")
    return sess


@router.get("/status", summary="Whether accounts are open on this box")
async def status_route() -> dict:
    """No counts and no addresses. How many customers exist is not a visitor's business,
    and a count is also a slow leak of how the business is doing."""
    on = enabled()
    return {
        "enabled": on,
        "signup_open": on,
        "session_ttl_s": session_ttl_s() if on else None,
        "note": ("sign in or create an account" if on else
                 "this box has not been given a session secret, so accounts are closed"),
    }


@router.post("/signup", status_code=201, summary="Create an account")
async def signup(body: SignupBody, request: Request, response: Response) -> dict:
    _require_enabled()
    try:
        init_db()
        acct = create_account(body.email, body.password,
                              display_name=(body.display_name or None),
                              quote_id=(body.quote_id or None))
        token = issue_session(acct["id"])
    except (InvalidEmail, WeakPassword) as exc:
        # These messages are about what the visitor typed and are safe to repeat --
        # they carry no information about any other account.
        raise HTTPException(400, str(exc)) from None
    except AccountExists:
        raise HTTPException(409, "an account already exists for that address") from None
    except AccountsUnavailable as exc:
        log.error("accounts unavailable: %s", exc)
        raise HTTPException(503, "accounts are not configured on this box") from None
    except AccountsError:
        raise HTTPException(400, "could not create that account") from None
    _set_cookie(request, response, token)
    return acct


@router.post("/login", summary="Sign in")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    _require_enabled()
    try:
        init_db()
        acct = verify(body.email, body.password, ip=_client_ip(request))
    except Throttled as exc:
        # 429 with Retry-After, because a lockout nobody can see reads as a broken login.
        raise HTTPException(429, str(exc),
                            headers={"Retry-After": str(exc.retry_after)}) from None
    except AccountsUnavailable:
        raise HTTPException(503, "accounts are not configured on this box") from None
    if not acct:
        # One answer for a wrong password and for an address with no account. Saying
        # which would give away for free exactly what the dummy-hash timing cost buys.
        raise HTTPException(401, "that address and password do not match an account")
    token = issue_session(acct["id"])
    _set_cookie(request, response, token)
    return acct


@router.post("/logout", status_code=204, summary="Sign out")
async def logout(request: Request, response: Response) -> Response:
    token = request.cookies.get(COOKIE, "")
    if token:
        try:
            revoke_session(token)
        except AccountsUnavailable:
            pass
    # Clear the cookie whatever happened. A logout that leaves the cookie in place
    # because the row was already gone is a logout the visitor cannot trust.
    response.delete_cookie(COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", summary="The signed-in account")
async def me(request: Request) -> dict:
    _require_enabled()
    return _current(request)["account"]


@router.get("/sessions", summary="Live sessions for the signed-in account")
async def my_sessions(request: Request) -> dict:
    _require_enabled()
    sess = _current(request)
    rows = sessions_for(sess["account_id"])
    # Mark which row is the browser asking. Without it the list is a set of opaque ids
    # and "sign out everywhere else" is a button nobody can aim.
    for r in rows:
        r["current"] = (r.get("sid") == sess["sid"])
    return {"count": len(rows), "sessions": rows}


@router.post("/password", status_code=204, summary="Change the password")
async def password(body: PasswordBody, request: Request, response: Response) -> Response:
    _require_enabled()
    sess = _current(request)
    try:
        # Returns False for a wrong current password -- it does not raise for that, and
        # treating a False as success would be a password change that silently did not
        # happen. Throttled DOES raise, and shares the login counter on purpose.
        if not change_password(sess["account_id"], body.old, body.new):
            raise HTTPException(403, "the current password is not correct")
    except Throttled as exc:
        raise HTTPException(429, str(exc),
                            headers={"Retry-After": str(exc.retry_after)}) from None
    except WeakPassword as exc:
        raise HTTPException(400, str(exc)) from None
    except AccountsUnavailable:
        raise HTTPException(503, "accounts are not configured on this box") from None
    # change_password kills every session including this one. Issue a fresh cookie so the
    # visitor is not silently signed out by succeeding.
    _set_cookie(request, response, issue_session(sess["account_id"]))
    response.status_code = 204
    return response


@router.post("/signout-everywhere", status_code=204,
             summary="Revoke every session for this account")
async def signout_everywhere(request: Request, response: Response) -> Response:
    _require_enabled()
    sess = _current(request)
    revoke_all_sessions(sess["account_id"])
    response.delete_cookie(COOKIE, path="/")
    response.status_code = 204
    return response


def status() -> dict:
    """The rack unit, as a plain dict, shaped for `api.py`'s `Unit`.

    The state comes from `unit_state()` in the module beside this one rather than being
    recomputed here, so there is exactly one definition of what "the account surface is
    working" means. `offline` on a box with no session secret is a reading and not a
    decoration -- the surface genuinely cannot authenticate anybody, and the detail line
    names what is missing instead of leaving somebody to guess.
    """
    state, detail = unit_state()
    return {
        "id": "accounts", "label": "SyMoNeuRaL Account", "slot": "1U",
        "state": state, "bus": "cpu", "href": "/account.html",
        "spec": "scrypt N=2^16 \u00b7 server-side sessions",
        "detail": detail,
    }
