# SyMoNeuRaL Tuner

An IPTV surface. The visitor brings their own subscription; this box brings a validated fetch,
a stream-copy transcode and a bounded number of slots. **No playlist, credential or channel is
stored here** — the browser holds all of it in `localStorage` and sends what it needs per
request.

Standard library plus `fastapi` and `pydantic`, which the system interpreter already has.
Nothing was installed, no venv was created. `ffmpeg` 7.1.5 is the transcoder.

```
backend/apps/tuner/
  __init__.py     exports `router` and `status` — the whole contract with api.py
  safefetch.py    the SSRF door: validate, pin, connect, redirect, redact
  m3u.py          M3U/EXTINF channel parser + a separate HLS playlist parser
  xtream.py       Xtream Codes protocol client
  sessions.py     ffmpeg HLS sessions: the pump, the caps, the reaper
  routes.py       the APIRouter and the rack `status()`
  test_tuner.py   55 tests, offline, no provider needed
```

---

## Wiring — what the API needs to do

```python
# backend/api.py — the whole of it
from apps.tuner import router as tuner_router, status as tuner_status

app.include_router(tuner_router, prefix="/api/tuner")
```

and in `build_status()`:

```python
Unit(**tuner_status()),
```

Points that matter:

- **`backend/` must be on `sys.path`.** It already is when `api.py` runs, and `apps` is an
  implicit namespace package, so `import apps.tuner` works with no `__init__.py` in `apps/`.
  This module is *not* added to `sys.path` the way `ravencalc` is — it is a package, imported
  as one.
- **The prefix is assumed to be `/api/tuner` but not hardcoded.** The router declares relative
  paths only. The one place the prefix leaks is `Session.public()["playlist"]`, which is the
  **relative** string `stream/<id>/live.m3u8`; the page must resolve it against the tune
  endpoint's own URL. It is relative precisely so this module never has to know its mount point.
- **`status()` is synchronous, cheap and safe to call on every rack poll.** It reads a dict of
  live sessions and touches no filesystem and takes no lock.
- **`status()` returns a plain dict, not a `Unit`.** Its keys match `api.py`'s `Unit` fields so
  `Unit(**tuner_status())` works. It deliberately does not import `Unit` — that would put this
  module inside `api.py`'s import graph, which is outside the scope this was built in. If you
  prefer the import, the change is yours to make.
- **Shutdown hook:** call `apps.tuner.sessions.MANAGER.shutdown()` from the API's lifespan
  teardown. Without it, a reload leaves ffmpeg processes running until their lifetime cap.
  Not fatal, but untidy on a box with a contended GPU. Note this takes no governor lock and
  must never take one — see below.
- **No config file, no secrets, no new deploy step.** Everything tunable is an environment
  variable with a safe default (table below).
- **The page needs `hls.js`** — see "Frontend" below. That is the one thing this module cannot
  do for you.

### The GPU governor is deliberately not involved

The Tuner never takes the GPU lock. It is `-c copy` — a demux and a remux, no decoding, no
encoding, no CUDA — so it is a CPU surface like RavenCalc, and the rack unit reports
`bus: "cpu"`. Making it queue behind chat or image would be a lie about what it uses.

### Environment variables (all optional)

| Variable | Default | Meaning |
|---|---|---|
| `SYMONEURAL_TUNER_MAX_SESSIONS` | `2` | Concurrent ffmpeg processes (clamped 1–8) |
| `SYMONEURAL_TUNER_IDLE_TIMEOUT` | `45` s | No player request for this long → reaped |
| `SYMONEURAL_TUNER_MAX_LIFETIME` | `1800` s | Hard ceiling on a session |
| `SYMONEURAL_TUNER_MAX_BYTES` | `4096` MB | Per-session upstream data cap |
| `SYMONEURAL_TUNER_DIR` | a fresh `mkdtemp` | Where HLS segments are written |

There is deliberately **no variable that relaxes the SSRF policy.** A test asserts that
`safefetch.py` never reads the environment at all.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/playlist` | `{url}` or `{text}` → parsed channels, groups, `truncated` |
| `POST` | `/xtream/info` | `{server, username, password}` → account status, expiry, connection limits |
| `POST` | `/xtream/channels` | `+ {kinds: ["live","vod","series"]}` → catalogue |
| `POST` | `/tune` | `{url, label}` → starts a session, waits up to 10 s for real output |
| `GET` | `/session/{sid}` | session state (also a heartbeat) |
| `DELETE` | `/session/{sid}` | stop and free the slot |
| `GET` | `/stream/{sid}/{name}` | the HLS playlist and its segments (also the heartbeat) |
| `GET` | `/state` | slots, active sessions, whether ffmpeg exists |

**Every credential arrives in a POST body.** There is no `GET` that takes one and there never
may be: uvicorn logs the full request line, so a credential in a query string or path segment
is a credential written to `run/api.log` on every request. A test enforces this structurally
against the route table.

`POST /tune` waits for ffmpeg to actually write a playlist before returning success, because
ffmpeg on a source it cannot stream-copy exits several seconds after starting — returning "ok"
on `Popen` succeeding would be a status the box has not earned.

---

## SSRF — `safefetch.validate_url`

One function, one docstring listing every rule, one hostile-input table in the tests.

1. `http` and `https` only, by allow-list, so `file:`, `gopher:`, `dict:`, `data:` and the rest
   need no individual rule.
2. The hostname is **resolved once**, and **every** address it returns must pass. A name with
   both a public and a private answer is refused outright rather than having the public one
   picked.
3. The **resolved address** is judged, never the hostname string: loopback, RFC1918 private,
   link-local (`169.254.0.0/16`, so cloud metadata), IPv6 unique-local, multicast, reserved,
   CGNAT and everything else not globally routable, with IPv4 addresses embedded in IPv6
   (`::ffff:`, 6to4, Teredo) unwrapped and judged on their own merits. This is why
   `http://2130706433/`, `http://0177.0.0.1/` and `http://127.1/` are all blocked and why no
   hostname denylist is needed or used.
4. Redirects are followed **by this module, capped at 3**, and each `Location` goes back
   through the same validator.

**DNS rebinding** is handled by there being only one lookup. `validate_url` resolves the name
and returns the approved address; `_PinnedHTTPConnection` connects to *that address* while
keeping the hostname for the `Host:` header and the TLS SNI, so certificate validation and
name-based virtual hosting still work and there is no second lookup for an attacker's second
answer to win. A test asserts the resolver is called **exactly once** for a successful fetch —
if a future change reintroduces a lookup at connect time, that count goes to 2 and the test
fails.

**The validator is not advisory.** No visitor-supplied URL is ever handed to a subprocess.
ffmpeg would resolve its own names and follow its own redirects in another process, which would
make this file decoration — so Python holds the upstream socket and ffmpeg reads `pipe:0` with
`-protocol_whitelist pipe,fd`. A test greps `_spawn` to keep it that way.

---

## Credentials

Never written to disk, never logged, never in a URL on any route here.

- The pipe architecture keeps them out of `argv`, so they are not visible in `ps` either.
- `XtreamCreds.__repr__` and `__str__` are overridden, so a traceback containing the object
  does not contain the password.
- Every credential-bearing pydantic field **has a default**. This is a leak fix, not laziness:
  a *missing required field* makes pydantic raise a `ValidationError` whose `input` is the whole
  request body, and FastAPI serialises that into the 422 response — so omitting `server` would
  have echoed the password back inside an error document. With defaults there is no validation
  path that can touch these values.
- Upstream exceptions are never re-raised with their message; `ssl` and `http.client` both quote
  URLs. Errors are rebuilt from a fixed string plus `scheme://host:port`.
- `Scrubber` carries the session's own literals, because an Xtream password sits in a *path
  segment* (`/live/<user>/<pass>/<id>.ts`) where a pattern-based redactor sees nothing. It is
  applied to ffmpeg's stderr. `Scrubber.from_url` derives those literals from the URL itself,
  which is what protects the **M3U path** — a visitor who pastes an Xtream-exported playlist
  sends `/tune` no username or password field at all, so a scrubber primed from the request
  body would be empty.
- **ffmpeg's stderr never reaches the client.** It is kept in `Session.transcoder_error`
  (internal, for logging) and `public()["error"]` carries only this package's own origin-only
  messages, or the fixed sentence *"the transcoder could not stream-copy this source"*. So the
  page cannot show ffmpeg's exact complaint — deliberately. Read it from the log instead.
- The test suite pushes a sentinel password through the real router and greps **log output, the
  response bodies, the exception text and the session document**.

---

## Frontend — what the page must do (not built here; out of scope)

- **Include `hls.js`.** Safari plays `.m3u8` natively; Chrome and Firefox need MSE. This module
  cannot supply it and does not pretend to. Note the site's CSP/no-external-asset habit: it will
  need to be vendored locally, not pulled from a CDN.
- Resolve `session.playlist` (relative) against the tuner API base.
- Keep requesting segments — that is the session heartbeat. Stop, and the slot is reclaimed in
  `IDLE_TIMEOUT` seconds. Call `DELETE /session/{sid}` on unload to be polite.
- **With nothing loaded, show empty and offline.** No mock channel list, no sample EPG, no
  signal-strength meter. `/state` returns `channels_stored: 0` and means it.
- No `text-overflow: ellipsis` anywhere — channel names and group titles wrap. House rule.

---

## What is implemented

- M3U/EXTINF parser: attributes, `group-title`, `tvg-*`, `#EXTGRP`, CRLF, BOM, bare URLs,
  commas inside quoted attribute values, `MAX_CHANNELS` bound with an honest `truncated` flag.
- Xtream Codes: authenticate, account info, live/VOD/series catalogues, stream URL construction.
- HLS output by stream copy, verified end to end: a real transport stream in, `live.m3u8` plus
  segments out, segments confirmed to decode as `h264`/`aac` with no re-encode.
- Upstream **direct** (continuous TS) and upstream **HLS** (master-variant selection, media
  playlist polling, `EXT-X-MEDIA-SEQUENCE` tracking), both verified end to end locally.
- Caps: concurrent sessions, idle timeout, hard lifetime, per-session byte cap, a reaper that
  runs whether or not the client disconnected politely, and a segment-name allow-list.
- 55 tests, offline, ~1 second.

## What is NOT implemented — the honest gap list

1. **No frontend.** No `site/tuner.html`, no player, no CSS. Out of scope by instruction, and
   the module is untested against a real browser.
2. **No EPG.** `xmltv.php` exists on Xtream panels and is not fetched. `tvg-id` is parsed and
   passed through so a future EPG can join on it, and that is all.
3. **Series episodes are not playable.** The catalogue lists a series with an **empty `url`**
   because `get_series_info` is not called; the UI must not show a play button for those. An
   episode URL was deliberately not guessed — that would produce a channel that looks playable
   and is not.
4. **AES-encrypted HLS is refused,** not decrypted. `#EXT-X-KEY` is detected and the session
   fails with a clear message rather than piping garbage into ffmpeg.
5. **No reconnect or failover.** The reference's failover between two hardcoded sources went
   with the hardcoding; failing over to a source the visitor did not choose is not resilience.
   A dropped upstream ends the session and says so. A brief reconnect for live streams would be
   a reasonable addition and is not here.
6. **Progressive MP4 VOD over a pipe may fail.** An MP4 whose `moov` atom is at the end of the
   file is not demuxable from a non-seekable stdin. Live TS and HLS are unaffected. Untested
   against a real VOD source — I had no provider.
7. **Never tested against a real IPTV provider.** Every test and every smoke run used
   synthetic streams generated locally. The Xtream client is written to the protocol shapes in
   the JS reference and is **unverified against a live panel** — that is the single largest
   risk in this module, and the first thing to exercise once someone has credentials.
8. **`-c copy` only.** A source whose codecs cannot enter an MPEG-TS segment unchanged fails
   with ffmpeg's error rather than being re-encoded. Deliberate: the GPU is reserved for
   inference and re-encoding on the CPU would compete with serving the site.
9. **Bandwidth.** Session and byte caps bound it, but a public tuner is still a box fetching
   third-party video on request. Whether that is acceptable egress is a product decision nobody
   has made yet.
10. **Segments default to `/tmp`, which is usually tmpfs**, so they cost RAM. Bounded at
    roughly `hls_list_size × hls_time × bitrate × MAX_SESSIONS` — about 25 MB at 8 Mb/s with
    the defaults. Point `SYMONEURAL_TUNER_DIR` at real disk if that trade is wrong.

## Open questions for the user

- **Legality and framing.** This box will proxy whatever stream a visitor points it at. The
  module takes no view; the page's copy should. Worth a decision before it is public.
- **Should the Tuner appear on the rack at all when it has no content of its own?** It reports
  `ready` when ffmpeg is present and no session is running, with a detail line saying plainly
  that no channels are stored here. The alternative reading — always `offline` until a visitor
  loads something — is defensible too, but the server genuinely cannot know what is in someone's
  `localStorage`, and a unit that is permanently `offline` while working is its own kind of
  dishonest indicator. Overrule me in `status()` if you disagree; it is six lines.
