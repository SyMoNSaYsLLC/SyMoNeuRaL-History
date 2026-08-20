# SyMoNeuRaL — working agreements

Repo for symoneural.com: the public site, the live API behind it, the CUDA engine, and
the engineering manual the site's numbers come from.

## Where to look — there is exactly one of each

Three files once all claimed to describe "current state" and agents kept acting on the stale
one. There is now one of each, and everything superseded lives in `docs/archive/` behind a
README that says so.

| Question | File |
|---|---|
| What are the rules? | **this file** |
| What is the state, what is left to do, what will bite me? | **`.claude/HANDOVER.md`** |
| What does the hardware actually do? | `docs/symoneural-manual.md`, and `docs/` |
| Why is the code like this? | **`git log`** — every commit states its reason |

Do not create a second state document. Update `.claude/HANDOVER.md`.

**`demo/` no longer exists.** It was flattened into the repo root: `demo/api.py` is `api.py`,
`demo/playground.sh` is `scripts/symoneural.sh`. Any path with `demo/` in it is from before that and
is wrong.

## Parallelise builds

**Run as many agents concurrently as quality allows.** Compiles, model downloads and fine-tunes
occupy the machine for tens of minutes; that wall-clock should be filled with independent work,
not spent watching a progress bar. Launch subagents in one message so they actually run in
parallel. The GPU is available to agents that genuinely need it.

Scope agents to files nobody else is writing. The real hazard here is the generator scripts:
`tools/build_pages.py`, `tools/build_rack.py`, `tools/build_console.py`, `tools/build_cost.py`, `tools/build_stack.py`,
`tools/build_training.py` and `tools/build_gallery.py` all rewrite files under `site/`, so two writers in
that directory will clobber each other. Safe parallel
tracks are read-only audits, brand-new standalone files, docs, and tests.

## The GPU is a single, contended resource

One RTX 5070 Ti, 15.92 GiB. Chat (~5 GB), image (~7 GB) and a QLoRA run (~12 GB) cannot coexist.

- Everything touching the GPU goes through `scripts/gpu-governor.sh`, ideally as
  `gpu-governor.sh with <surface> -- <cmd>`, which always releases even on crash.
- **Hold the lock for a job, never for a process lifetime.** Residency (weights loaded) and
  work (using the card) are separate. Holding the lock while a model is merely resident and
  idle locks every other process out — including the CLI — until the acquire timeout.
- **Never call a bare `release`.** Name the surface (`release chat`). An unscoped release once
  destroyed a running fine-tune's lock from the API's shutdown hook.
- The governor waits for VRAM to drain below a 1.5 GB floor between tenants. Killing a process
  returns the lock before CUDA has torn down, and the next tenant OOMs at step 0.
- `train` is never evicted to serve a page view.
- RavenCalc (SymPy, CPU) deliberately never takes the lock. That is what lets it speculatively
  pre-compute while the GPU is loading.

## Python environments

The **CUDA sample venv** at `contrib/cuda-samples/python/.venv` is pinned at exactly **7 packages** and
must never be extended:

```bash
contrib/cuda-samples/python/.venv/bin/pip freeze | wc -l    # expect exactly 7
```

`numba-cuda` silently downgrades numpy, and three other packages pin conflicting
`cuda-core`/`cuda-python` versions. (Earlier revisions of this file said "the base interpreter
is pinned at 7 packages, check with `pip freeze | wc -l`". That is wrong twice over: the bare
command runs against the **system** interpreter, which is a Debian install carrying 212
packages, and the count would never have been 7. Use the full path above.)

- The serving API deliberately uses only the **system** interpreter: fastapi, uvicorn, pydantic
  and sympy are already OS packages, so there is no virtualenv in the serving path. Do not
  `pip install` into it — the deny rules in `.claude/settings.local.json` block the bare forms
  precisely because a stray install there is hard to notice and hard to undo.
- Training has its own venv at `training/.venv` (torch cu128 — Blackwell sm_120 needs it).
- Anything else that conflicts gets its own isolated venv.

## Honesty rules for anything user-facing

These are the product, not decoration. The site's entire argument is that its numbers are real.

- Label every figure: **measured** on this machine, **vendor** specification, or **projected**
  arithmetic. Never present a projection as a result.
- Never invent pricing. Direct pricing questions to symonsayadmin@symoneural.com.
- No decorative status indicators. Every LED and gauge on the site reflects a real reading; a
  fake activity light is the one dishonest pixel on a page arguing for measurement.
- Publish negative results too — the PCIe Gen 3 ×8 ceiling and the failed multi-stream overlap
  are on the site deliberately.
- Layout changes must not drop data. Fold long content into `<details>`; do not trim it.
  **This includes CSS.** `text-overflow:ellipsis` on a detail line is data loss with extra
  steps — the control board was showing `~84% of 896.1 p…` and the rack was cutting
  `built on Qwen2.5-7B-Instruct` down to `…7B-Ins…`, and that attribution is an Apache-2.0
  licence condition. Every ellipsis rule has been removed. Do not add one back; let it wrap.

## What is SyMoNeuRaL's, and must never be published

The stack is off-the-shelf and permissively licensed, so nothing here is protected by a
licence. Two artefacts are protected only by not being public, and trade secret — unlike
copyright — exists only while reasonable measures are taken to keep it that way. Once it is
out, it cannot be pulled back.

- **`training/corpus.jsonl`** — 327 hand-authored examples: the company voice, what the model
  may claim, and what it must refuse to invent (the pricing refusal is trained in, not
  prompted).
- **`training/build_dataset.py`** — the method that produces it.
- **`training/adapter/`** weights — already gitignored (`*.safetensors`, `*.gguf`).

**Never copy any of these into `site/`, never serve them from an endpoint, and never quote
their contents into a page or a commit message.** An agent asked to "publish the manual" could
reasonably mistake the corpus for documentation. It is not: it is the recipe for the product.
`docs/symoneural-manual.md` is the manual and is publishable; the corpus is not.

The line that resolves this against the site's transparency argument: **publish the numbers,
keep the methods.** "151 tok/s on a 7B Q4_K_M, measured here" is the sales argument and gives
away nothing. How the adapter was built is the asset. The site promises measurement, not open
source, and has never promised the recipe.

There is currently **no git remote** — history never leaves this box, which is doing a lot of
the protecting. If one is ever added, audit what is tracked first.

## Build and deploy

```bash
./scripts/fetch-models.sh            # weights -> models/ (ungated, Apache-2.0 sources)
python3 tools/build_pages.py       # chat/image/calc/remix   -> site/*.html
python3 tools/build_rack.py        # live rack               -> site/index.html
python3 tools/build_console.py     # control board           -> site/index.html
python3 tools/build_cost.py        # Owned vs Rented         -> site/documentation.html
python3 tools/build_stack.py       # Inference Architecture  -> site/documentation.html
python3 tools/build_training.py    # manual                  -> site/training.html
python3 tools/build_tabs.py        # one-screen front page   -> site/index.html
python3 tools/build_gallery.py     # homepage art (uses GPU) -> site/art-*.png
python3 tools/build_gallery.py --restamp   # redraw the watermark bar only -- NO GPU
python3 tools/build_cachebust.py   # ALWAYS LAST -- see below
./scripts/symoneural.sh on|off|status   # the live API (off is the kill switch)
sudo ./scripts/deploy.sh                # site/ -> /var/www/symoneural (needs a password)
```

**`build_cachebust.py` runs last, and every generator run un-does it.** The generators emit
plain `href="/symoneural.css"`; the stamper rewrites those to `?v=<content hash>` so a week-old
cached stylesheet can never be served against new markup. That means any generator you run
*strips the stamps off every page it writes*, and a commit made at that moment ships pages whose
assets are cacheable for a week with no way to invalidate them. This is not theoretical: a run of
`build_pages.py` here silently destamped seven pages, and the diff read like a harmless refresh.
So: **regenerate, then stamp, then look at `git status`** — if a page you did not touch is still
modified, you skipped the stamper. It is idempotent and cheap; there is no reason not to run it.

The generator scripts are idempotent and must stay that way — `tools/build_console.py` once nested
folds inside folds when run twice. **Run every generator twice and `diff` before committing.**
The BEGIN/END marker strings are the contract: change a marker in a generator and you must
change it in the HTML in the same commit, or the generator stops finding its block and appends
a second one.

`scripts/deploy.sh`'s reference check **can** fail the build — the loop reads from a process
substitution, so `missing` survives into the exit test. It used to pipe into `while read`,
which put the counter in a subshell and threw it away; that was fixed in `aa424d3` and
verified by running the block against a fake webroot with one missing reference. Earlier
revisions of this file said the bug was still live. It is not.

The general lesson stands and is what to carry forward: **a counter incremented inside a
piped `while read` is discarded.** The orphan-scan loop above it is still in a subshell, and
that is fine, because it only writes to stdout and sets nothing its caller reads.

## Test in a real browser, not with curl

```bash
node tests/frontend.mjs             # every page, against a running API on :8800
node tests/tuner_failpaths.mjs      # tuner.html, self-contained -- starts its own fake provider
node tests/tuner_watch.mjs          # tuner-watch.html, ditto -- no account, no real stream
node tests/studio.mjs               # /studio -- needs the surface on, ComfyUI up, and the GPU
cd backend && python3 -m pytest apps/ -q --ignore=apps/reinforce/tests --ignore=apps/remix/tests
```

**1093 pass at `e81ffa4`, measured 2026-08-19 from `backend/` in 109.36 s, with
`--collect-only` collecting the same 1093 in 0.81 s; the two `--ignore`s are not optional and
not a failure you introduced.** The number moved because `e81ffa4` added 8 — the first tests
against `bin/symoneural-cli`. It was **1085 at `df1d862`**, 110.38 s then 111.55 s on that
tree: two readings of one tree, so treat the wall time as a range and the count as the reading.
The count drifts upward as apps land — it was 682, then 941, then 973, then 981, then 1084,
then 1085 — so treat the absolute number as a date-stamped reading,
not a contract, and put a commit SHA beside it. A published 1063 turned out never to have been
true of the commit it sat beside: the tree it named collects 1084, so the figure was carried
forward from an earlier one. A number with no SHA cannot be checked, only believed.
`--collect-only` should report the same figure; that comparison is what catches a collection
abort, which is not a smaller number but no number at all. Without them pytest stops at
*collection* — `Interrupted: 2 errors`, zero tests run, which reads exactly like you broke the
suite. `apps/reinforce/tests` imports `cupy` and `apps/remix/tests` imports `symon_capture`;
neither is installed on the **system** interpreter and neither may be, since that is the serving
path (see *Python environments*). They are per-project suites that need their own environment, so
they are excluded here rather than made to look green.

**`frontend.mjs` is 43/43 at `e81ffa4`, and the rack red that stood here is fixed.**
Measured 2026-08-19 on a spare port (`node tests/frontend.mjs http://127.0.0.1:8875`), which
is the only honest way to run it — see below. `#rack` on
`/livestack` overflowed its one-screen budget at 1855x745 — `scrollHeight` 599 against
`clientHeight` 584 — because `site/index.html` renders the rack client-side from `/api/status`
and the rack went from eleven units to thirteen when `studio` and `exp` landed (`e27b9c1`).
Nothing in any page source regressed. Two spacing rules closed it, both in the `html.ns` block
of `site/symoneural.css`: the rack note's measure (96ch → 160ch, three line boxes → two) and
the `.rk-fold` pill moved out of the heading's inline run onto the `.shead` row, which was a
whole line box on its own. No word, row or type token changed. **Measure slack with a cloned
`.unit`, not with `scrollHeight`** — it floors at `clientHeight`, so `584/584` says "fits" and
nothing about by how much, and three of the four in-gate viewports read `over=0` before the fix
as well. By that method fourteen units now fit everywhere and fifteen only at 1990x970; the
binding viewport is **1301x740**, not 1855x745, because its rows are 26.6px. `.claude/HANDOVER.md`
§0 has the full table, the retraction of the two-column option it used to recommend, and the one
lever deliberately left unspent. Do not close the next overflow by dropping a row or adding
`text-overflow` — both are barred above. The other two suites are green on the same tree:
`tuner_failpaths.mjs` **32/32** and `tuner_watch.mjs` **8/8**, measured 2026-08-19 at
`e81ffa4` — the same tree as the two figures above, which is what "same tree" has to
mean to be worth writing.

System Chrome via Playwright, nothing to download. The two tuner suites need no API and no
provider account: each starts `tests/tuner_fake_provider.py` and stops it again, so the whole
invocation is the one line. **`frontend.mjs` needs an API**, and if you point it at the running
service you are testing what is *deployed*, not what you wrote — start your own on a spare port
and pass the base URL (`node tests/frontend.mjs http://127.0.0.1:8875`), or a red assertion will
send you hunting a bug you already fixed.

**`tests/studio.mjs` is the fourth suite and is deliberately not part of `frontend.mjs`.** That
one runs against any instance and asserts what every visitor sees; this one needs the Studio
surface switched on and it **takes the card for a real render**, so pointing it at the deployed
service would queue a job on the live GPU. Start ComfyUI and your own API, then run it:

```bash
bash scripts/comfyui.sh start                       # loopback :8188, no lock held
cd backend && SYM_STUDIO_ENABLED=1 SYM_STUDIO_TOKEN=devtest \
    python3 -m uvicorn api:app --port 8876          # a spare port, not the service
SYM_STUDIO_TOKEN=devtest node tests/studio.mjs http://127.0.0.1:8876
bash scripts/comfyui.sh stop                        # /free, THEN SIGTERM -- see below
```

**16/16 passed, re-measured 2026-08-19 at `1537262`**, including a 1024x1024 FLUX-schnell
render decoding in the browser in 14.4 s (14.2 s server-side, card back in 4.1 s, lock
released). The previous reading was the same 16/16 at `d20e09b`; it was re-run rather than
re-dated because `backend/api.py` had changed underneath it, and studio.mjs runs against
`api.py`. Its three `net::ERR_ABORTED` lines are labelled optional and
404 upstream at :8188 as well; they are not proxy faults. `.claude/HANDOVER.md` has the reading
and the VRAM curve. The state document claimed for two days that this suite could not run
because ComfyUI "has no venv and no torch" — it has both (torch **2.13.0+cu130**, sm_120
verified by a real CUDA probe, 223 packages), and the suite had simply never been invoked.

**Stop ComfyUI with `scripts/comfyui.sh stop`, never by killing the pid.** The script POSTs
`/free` and then waits on `gpu-governor.sh drain` — the process exiting is not the memory coming
back, and the next tenant OOMs at step 0. Measured here: a render peaks at **13,114 MiB of
16,303** and returns to 666 MiB in **4.1 s**, against the governor's 60 s timeout and 1500 MiB
floor. `comfyui.sh` deliberately does **not** hold the lock for its process lifetime; the lease
is taken per render and released after the drain, which is the rule above applied.

**The Studio agent loop does not stream tokens, so do not quote a first-token latency for
it.** `inference.Backend.chat` sends `"stream": False` and is the loop's only call site;
`Backend.stream()` is unexercised and says so. The loop's granularity is SSE *events*. Measured
2026-08-19 over six turns, warm: the `backend` probe frame lands in **0.015-0.022 s**, the first
frame carrying model output in **0.2 s warm / 1.06 s cold** (the cold penalty is `--no-warmup`
plus first processing of the 26 rendered tool specs), and a whole turn takes **0.53 s** with no
tool, **1.0-1.9 s** with one, **3.1 s** with three. Native tool calling works on this build --
no `notice` downgrade in any turn, and turn 6 returned three tools from one message.

**To measure it, warm the engine through the chat surface, never by spawning llama-server.**
`inference.py` probes and never spawns, because `api.py` owns that process inside
`gpu.hold("chat")` and a second spawner would race it for :8081 and the lease:
```bash
curl -sS -X POST http://127.0.0.1:8800/api/chat -H 'Content-Type: application/json' \
    -d '{"prompt":"ready","max_tokens":8}'   # ~7.1 s of that is spawn + weight load
ss -lntp | grep 8081                            # confirm it stayed resident; chat does not stop it
```
llama-server then holds **~8.1 GiB** and stays up, while `gpu-governor.sh` reads `lock free` --
**the agent loop takes no lease.** Only `api.py` can stop it (shutdown, or an image render at
`api.py:2052`), so expect to leave it resident; that is this box's warm state, not a leak.

These assert on what the DOM *shows*: units render from `/api/status`, the bus plate carries a
real reading, nothing overlaps at 390px, calc returns `x**3/3`, and a generated image actually
decodes. That last assertion exists because a render once succeeded server-side and still
showed as a broken image for every visitor — curl proved the endpoint answered, which was never
in doubt. Add an assertion here whenever you fix a frontend bug.

**Read computed styles rather than reasoning about the cascade.** Three separate bugs have now
come from generic class names colliding across components: `.bar` (collapsed the site header to
7px sitewide), `.live` (the nav badge styling the control board legend), and `#console .sub`
(a section rule outranking `.mod .sub`, rendering a footnote larger than the sentence above it).
Render the page and measure.

## `run/` is runtime state, not logs

`run/` holds `gpu.lock.d` — the GPU mutex — alongside `api.pid`, the resident marker and the
logs. **Do not rename it `logs/`.** `/run` and `/var/run` are the Unix convention for exactly
this (pidfiles, locks, sockets) and the name is load-bearing: call the directory `logs` and
sooner or later someone logrotates it or clears it out, which deletes the lock directory while
a surface is holding the card. The logs happen to live there; the lock is the point.

Renders do **not** live there, and no longer live in `site/` either. They are API output,
written to `backend/output/` and served by `GET /api/gen/<name>`. They were in `site/` until
the backend restructure, which meant `deploy.sh` copied every one into the public webroot —
19 unreferenced PNGs were sitting there — even though nothing links to them.

## Serving architecture

**FastAPI does all the routing. The web server terminates TLS and hands back static files.**
That is the user's stated rule and the config enforces it — no rewrites, no aliases, no
conditional logic in `ops/Caddyfile`.

- **Caddy**, not Apache. Apache is disabled, and its config was deleted rather than left beside
  the Caddyfile. Caddy gives automatic TLS and, crucially, WebSocket upgrades with no directive
  — `mod_proxy_wstunnel` was never enabled under Apache, so the rack's "pushed live over one
  socket" claim had been silently falling back to polling.
- Anything the API generates is served by the API. Renders come back as `/api/gen/<name>`, not
  as a webroot path, because the API writes into the staging `site/` while the web server serves
  `/var/www/symoneural` — so every image generated on the live site used to 404 until somebody
  deployed.
- `api.py` mounts `site/` at `/` **last**, so it never shadows an API route. That is what lets
  the whole thing be exercised from one origin, which is the only way the real frontend works:
  `console.js` opens a WebSocket and falls back to polling, and neither survives a split origin.
- Testing a WebSocket: use `curl --http1.1` (`Upgrade:` does not exist in HTTP/2, and curl
  negotiates h2 with Caddy by default), and read the status line out of `-D` headers rather than
  trusting the exit code — a successful upgrade leaves the socket open, so curl exits 28.

## Branding

"MIT AI Training" is purged everywhere user-facing. Watch out: most `MIT` substring matches in
this corpus are ordinary words — limits, limited, submit, emits — so never blind-replace. Only
whole phrases and local filesystem paths.
