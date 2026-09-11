# SMOKE — #81 image-first: `/livestack/image`, `/live-stack/image`, and the html/js/css split

**SHIP_SHA: `e71b51f7`** — "One spelling in front of a person, two answering".
Preceded by **`1bccb765`** — "Ten pages at two spellings is twenty chances to type one wrong",
which carried the routes, the generator split and the tests. Both are in this record because
the second changed what the first published, and the public origin was only ever verified
against the pair.

Measured 2026-08-22, 00:41–01:45 EDT, on this box. Every figure below was read on the tree it
sits next to. Nothing here is carried forward.

---

## What was verified

| Gate | Result |
|---|---|
| `python3 -m py_compile backend/api.py tools/build_pages.py` | OK |
| `tools/build_pages.py` run twice | byte-identical output; idempotent |
| `tools/build_cachebust.py` | 329 asset links stamped across 25 pages |
| `pytest` — livestack + caddy + deploy suites | **23 passed** in 0.29 s |
| `pytest` — the same three plus `apps/coder/tests/test_coder_surface.py` | **36 passed** in 0.32 s |
| `caddy validate --config ops/Caddyfile` | `Valid configuration` |
| `tests/frontend.mjs` on `:8875` | **63/63 passed**, twice |
| `sudo ./scripts/deploy.sh` | 92 files staged, exit 0 |
| `sudo ./scripts/install-caddy.sh` | validates, Caddy active, `/api/ws` upgraded 101 |
| public origin, all seven addresses | 200 |
| public stamps == committed stamps | yes |

**Stamps shipped**

```
/image.css?v=2e7314121b
/image.js?v=91f28314b0
```

Read back off `https://symoneural.com/livestack/image` at 01:45 and identical to the
committed page. That equality is what ties this record to `e71b51f7`; the SHA names the
commit, the stamps name the bytes.

**The run-only gate**

```
PASS  the deferred page script ran and bound its controls  -- stepsv "4" -> "7"
```

This is the assertion the task exists to satisfy and the only one no file check can make.
The split moved the page's behaviour into a **deferred** external file while the shared
`$`, `status()` and `api()` helpers stayed inline in the shell. Invert that ordering and
`site/image.js` throws `$ is not defined` on its first line — every control on the page dead,
markup rendering perfectly, every `exists`/`grep` check still green. That is #94's shape, and
this assertion drives a real control and reads back a value only the page's own script writes.

**Addresses**

```
PASS  the image page answers at /livestack/image   -- HTTP 200, settled at /livestack/image
PASS  the image page answers at /live-stack/image  -- HTTP 200, settled at /live-stack/image
PASS  the image page answers at /image.html        -- HTTP 200, settled at /image.html
```

`settled at` is the half that matters: none of the three redirects, so the address in the
operator's URL bar still agrees with the address they typed. #81 requires the clean URLs to be
"an addition, not a redirect".

**The page actually renders.** `POST /api/image` → 200,
`/api/gen/gen-1787374580219-1359765078.png` → 768×768 decoded in the browser. The suite took
the card and gave it back.

---

## Three bugs, found by this sequence before anything shipped

All three were mine, in the patch, and all three would have been invisible to inspection.

1. **`tests/frontend.mjs` did not parse.** `const split` collided with an existing top-level
   `const split = []` at line 598 — a module-level SyntaxError, so **zero** assertions ran and
   node reported it as the whole suite failing rather than as one block. Renamed `imgSplit`.
   This is the `.bar` / `.live` / `.card` collision this repo has hit five times in CSS,
   arriving in JS, where it is louder and no less avoidable.

2. **A test that went red on healthy code.** `test_every_livestack_page_is_not_reported_missing`
   filtered the route set by the `livestack/` prefix, which also catches `livestack/live` and
   `livestack/coder` — literal decorators, not `LIVESTACK_PAGES` entries. It therefore demanded
   a `/live-stack/live` that had never existed. A check that fails on a healthy tree gets
   switched off, and then it protects nothing. Now reads the dict via `_livestack_names()`.

3. **`/livestack/live` had shipped at one spelling since #96.** Found by the new
   `test_every_application_answers_at_both_spellings`, not by anyone typing the address —
   which is the point of it. A *missing* route is not a broken one: nothing goes red, every
   other test passes, and a visitor typing the other spelling gets a 404. `/live-stack/live`
   now answers, with its matcher and its deploy exemption.

---

## The finding that outlives this task: the running process is not the committed code

The public origin was **404 on five of seven addresses after a clean deploy and a clean Caddy
install**, and the pattern is the whole diagnosis:

```
BEFORE restarting the API                    AFTER ./scripts/symoneural.sh off && on
/image.html            200                   /image.html            200
/livestack/image       404                   /livestack/image       200
/live-stack/image      404                   /live-stack/image      200
/livestack/live        200   <-- only this    /livestack/live        200
/live-stack/live       404                   /live-stack/live       200
/livestack/coder       404                   /livestack/coder       200
/live-stack/coder      404                   /live-stack/coder      200
```

The one address that answered is the one that predates the running process. `scripts/deploy.sh`
publishes `site/`. `scripts/install-caddy.sh` installs the Caddyfile. **Nothing in either
restarts the API** — `install-caddy.sh`'s own preflight prints `api up on 127.0.0.1:8800` and
means the *old* one.

An API restart cannot fix a Caddy matcher, so the restart turning all seven green is also the
proof that Caddy was delegating correctly the whole time.

**`/livestack/coder` had been publicly 404 since #87 landed, with a green suite throughout.**
`apps/test_caddy_delegation.py` compares `api.py` to `ops/Caddyfile` — both in the repo.
Nothing compares either one to what is running or to what is installed at `/etc/caddy`. That
is the tuner defect one layer further out: the guard is honest about the two files it reads
and silent about the gap between them and the box.

Not fixed here. It is not #81, and the fix is a deploy-sequence change plus a check that can
only run against a live service. It needs its own assignment.

---

## `curl -I` is the wrong probe for these routes

Measured across nine paths on `:8875`:

```
/image.html       GET=200 HEAD=200      (a real file; StaticFiles serves HEAD)
/livestack/image  GET=200 HEAD=404      /live-stack/image GET=200 HEAD=404
/livestack/live   GET=200 HEAD=404      /live-stack/live  GET=200 HEAD=404
/studio           GET=200 HEAD=404      /exp              GET=200 HEAD=404
/overview         GET=200 HEAD=404      /livestack/coder  GET=200 HEAD=404
```

Pre-existing and universal, not introduced by `LIVESTACK_PAGES`. FastAPI's `APIRoute` sets
`methods={"GET"}` and, unlike Starlette's plain `Route`, does not add HEAD; the `StaticFiles`
mount at `/` then matches the request as a **full** match, so there is no 405 — it looks for a
file of that name and 404s.

The first verification block written for this task used `curl -sI` and reported three working
pages as dead. Use `curl -s -o /dev/null -w '%{http_code}'`. Fixing HEAD properly touches
method matching on every page route including `/`, where the mount serves `index.html` on HEAD
while `api.py` redirects GET to `/overview` — its own assignment, its own measurement.

---

## What this record does NOT establish

- **`deploy.sh`'s new exemption was never exercised.** The reference check walks references
  found in the published HTML, and nothing links `/livestack/image` yet, so it printed
  `route livestack/live` and never looked up `livestack/image` at all. `is_route()` is
  covered by `apps/test_deploy_routes.py` and by nothing that has actually run in a deploy.
  The first page to link the clean URL is when that exemption is first load-bearing.
- **Two webroot orphans were left in place** by design: `index.prev-20260821-164137.html` and
  `index.prev-20260822-005036.html`. Remove with `--prune` when you mean to.
- **The other nine applications are not migrated.** #81 says image first and all the way
  through before repeating — *"a pattern proven on one page is worth more than nine
  half-migrations."* This proves the pattern on one page.

---

## Reproducing it

```bash
cd /home/google/Symoneural
python3 tools/build_pages.py && python3 tools/build_pages.py && python3 tools/build_cachebust.py
git status --short                       # only ?? symoneural.zip
( cd backend && python3 -m pytest apps/test_livestack_routes.py \
      apps/test_caddy_delegation.py apps/test_deploy_routes.py \
      apps/coder/tests/test_coder_surface.py -q )
sudo caddy validate --config ops/Caddyfile
( cd backend && exec python3 -m uvicorn api:app --port 8875 ) &
sleep 4 && node tests/frontend.mjs http://127.0.0.1:8875     # positional, NOT BASE=
```

`BASE=... node tests/frontend.mjs` is silently wrong: `frontend.mjs:13` reads
`process.argv[2]`, so the env form runs against the default `:8800` — the live service — and
the image assertion takes the card there.

Then, and only in this order: commit → `sudo ./scripts/deploy.sh` →
`sudo ./scripts/install-caddy.sh` → **`./scripts/symoneural.sh off && ./scripts/symoneural.sh on`**
→ public smoke with GET.
