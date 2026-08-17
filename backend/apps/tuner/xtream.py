"""Xtream Codes panel client. Protocol only -- no credential outlives the request.

The endpoint shapes were read off `references/IPTV/xtremecodes/services/XtreamClient.js`, which
is JavaScript from a different project and was used as a protocol document, not as source. Two
deliberate divergences from what that reference does:

- **One request per stream type, not one per category.** The reference walks every category and
  asks for that category's streams, which is N+1 requests against someone else's panel to
  assemble a list the panel will return in a single call. `get_live_streams` with no
  `category_id` returns everything. Categories are fetched once, separately, purely to give the
  groups human names.
- **No retry loop.** The reference retries three times with exponential backoff over a 120 s
  timeout, which is up to six minutes of a request handler held open on a public box by a
  visitor-supplied hostname. That is a denial-of-service surface, not resilience. One attempt,
  one short timeout; a visitor whose panel is down can press the button again.

**Credentials.** They arrive in a POST body, are used to build URLs, and are never written to
disk, never logged, and never placed in a query string on any route this box serves. The one
place they unavoidably persist is inside the upstream stream URL held in memory by an active
session, which is why `Session` carries a `Scrubber` primed with them (see `sessions.py`).
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass

from . import safefetch
from .safefetch import BlockedURL, FetchError, Policy, Scrubber

__all__ = ["XtreamCreds", "XtreamError", "panel_info", "load_channels", "stream_url"]


class XtreamError(Exception):
    """A panel-level failure. The message never contains a credential."""


@dataclass(frozen=True)
class XtreamCreds:
    """Held for the life of one request. Never persisted, never logged.

    `__repr__` is overridden because a dataclass repr on this object is a credential in any
    traceback that touches it -- and a traceback is exactly where you least expect one.
    """
    server: str
    username: str
    password: str

    def __repr__(self) -> str:            # pragma: no cover - trivial, but load-bearing
        return f"XtreamCreds(server={self.server!r}, username='***', password='***')"

    __str__ = __repr__

    @property
    def scrubber(self) -> Scrubber:
        return Scrubber([self.username, self.password])


def _base(server: str) -> str:
    """Normalise a panel address into `scheme://host[:port]` with no trailing slash.

    Visitors paste `http://panel.example:8080/`, `panel.example:8080`, and
    `http://panel.example:8080/c/` about equally often. A bare host gets `http://` because
    Xtream panels overwhelmingly are plain HTTP on a high port; if the panel is HTTPS the
    visitor must say so, since silently downgrading or upgrading is worse than a clear failure.
    """
    s = (server or "").strip()
    if not s:
        raise XtreamError("no server address given")
    if "://" not in s:
        s = "http://" + s
    u = urllib.parse.urlsplit(s)
    if not u.hostname:
        raise XtreamError("server address has no host")
    netloc = u.hostname if u.port is None else f"{u.hostname}:{u.port}"
    if ":" in u.hostname:                                     # IPv6 literal
        netloc = f"[{u.hostname}]" if u.port is None else f"[{u.hostname}]:{u.port}"
    return f"{u.scheme}://{netloc}"


def _api(creds: XtreamCreds, action: str | None = None, **extra: str) -> str:
    params = {"username": creds.username, "password": creds.password}
    if action:
        params["action"] = action
    params.update({k: v for k, v in extra.items() if v})
    return f"{_base(creds.server)}/player_api.php?{urllib.parse.urlencode(params)}"


def _get_json(url: str, policy: Policy, scrub: Scrubber):
    """Fetch and decode. Every error path is scrubbed before it can become a message."""
    try:
        body, _ctype, _target = safefetch.fetch(url, policy)
    except BlockedURL as exc:
        raise XtreamError(scrub(str(exc))) from None
    except FetchError as exc:
        raise XtreamError(scrub(str(exc))) from None
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        # The body can contain the credentials echoed back by the panel's error page. Say
        # nothing about its contents.
        raise XtreamError("panel did not return JSON (is this an Xtream Codes server?)") from None


def panel_info(creds: XtreamCreds, policy: Policy = Policy()) -> dict:
    """Authenticate and return a small, credential-free summary of the account.

    A panel answers a bad login with HTTP 200 and `user_info.auth == 0`, so the status code
    proves nothing and the body must be read. Some panels omit `auth` entirely on success,
    hence the `== 0` test rather than a truthiness test -- a missing field is not a failure.
    """
    data = _get_json(_api(creds), policy, creds.scrubber)
    if not isinstance(data, dict) or "user_info" not in data:
        raise XtreamError("panel response was not an Xtream Codes account document")
    info = data.get("user_info") or {}
    if str(info.get("auth", 1)) == "0":
        raise XtreamError("panel rejected these credentials")
    if str(info.get("status", "Active")).lower() not in ("active", "", "none"):
        raise XtreamError(f"account status is {str(info.get('status'))!r}")
    server = data.get("server_info") or {}
    # Everything selected here is account metadata. The username is deliberately not echoed
    # back, and neither is anything from `server_info` that repeats the address.
    return {
        "status": str(info.get("status", "")) or "unknown",
        "expires": str(info.get("exp_date") or "") or None,
        "trial": str(info.get("is_trial", "")) == "1",
        "max_connections": _int(info.get("max_connections")),
        "active_connections": _int(info.get("active_cons")),
        "timezone": str(server.get("timezone") or "") or None,
    }


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_channels(creds: XtreamCreds, kinds: tuple[str, ...] = ("live",),
                  policy: Policy = Policy()) -> tuple[list[dict], list[str]]:
    """Fetch the account's catalogue. Returns (entries, notes).

    `notes` carries anything the visitor should know that is not an error -- "this panel has no
    VOD" is a fact about their account, not a failure, and swallowing it would leave them
    staring at a list that is shorter than they expected with no explanation.
    """
    base = _base(creds.server)
    scrub = creds.scrubber
    entries: list[dict] = []
    notes: list[str] = []

    spec = {
        "live":   ("get_live_categories", "get_live_streams", "live", "ts"),
        "vod":    ("get_vod_categories", "get_vod_streams", "movie", "mp4"),
        "series": ("get_series_categories", "get_series", "series", "mp4"),
    }
    for kind in kinds:
        if kind not in spec:
            continue
        cat_action, list_action, path, default_ext = spec[kind]
        try:
            cats = _get_json(_api(creds, cat_action), policy, scrub)
        except XtreamError:
            cats = []
        names = {str(c.get("category_id")): str(c.get("category_name", ""))
                 for c in cats if isinstance(c, dict)}
        try:
            rows = _get_json(_api(creds, list_action), policy, scrub)
        except XtreamError as exc:
            if kind == "live":
                raise                       # live is the point; vod/series are extras
            notes.append(f"{kind}: unavailable on this panel ({exc})")
            continue
        if not isinstance(rows, list):
            notes.append(f"{kind}: panel returned no list")
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = row.get("stream_id") if kind != "series" else row.get("series_id")
            if sid is None:
                continue
            ext = str(row.get("container_extension") or default_ext)
            group = names.get(str(row.get("category_id")), "")
            entries.append({
                "name": str(row.get("name") or "(unnamed)"),
                "logo": str(row.get("stream_icon") or row.get("cover") or ""),
                "group": f"{kind.upper()} | {group}" if kind != "live" else group,
                "kind": kind,
                "tvg_id": str(row.get("epg_channel_id") or ""),
                # A series id is not a playable stream -- an episode is. The catalogue lists the
                # series so the visitor can see it; `url` is empty and the UI must not offer a
                # play button for it. Inventing an episode URL here would produce a channel that
                # looks playable and is not, which is the dishonest-indicator failure in another
                # costume.
                "url": "" if kind == "series"
                       else stream_url(creds, kind, str(sid), ext),
            })
    return entries, notes


def stream_url(creds: XtreamCreds, kind: str, stream_id: str, ext: str = "ts") -> str:
    """Build the playable URL for one item.

    The path shapes are the Xtream convention and are not negotiable:
        live    {base}/live/{user}/{pass}/{id}.ts
        vod     {base}/movie/{user}/{pass}/{id}.{ext}
        series  {base}/series/{user}/{pass}/{episode_id}.{ext}
    Older panels also answer `{base}/{user}/{pass}/{id}` for live with no prefix; we do not try
    that fallback, because guessing wrong sends the visitor's credentials to a path we chose.

    The credential is in the path here, not the query. That is the provider's design and we
    cannot change it -- it is also why `Scrubber` exists: `redact()` alone would not spot a
    password sitting in a path segment.
    """
    q = urllib.parse.quote
    seg = {"live": "live", "vod": "movie", "series": "series"}.get(kind, "live")
    ext = (ext or "ts").lstrip(".")
    return (f"{_base(creds.server)}/{seg}/{q(creds.username, safe='')}/"
            f"{q(creds.password, safe='')}/{q(str(stream_id), safe='')}.{q(ext, safe='')}")
