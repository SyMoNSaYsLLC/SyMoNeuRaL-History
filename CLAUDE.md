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
| What is the state, what is left to do, what will bite me? | **`HANDOVER.md`** |
| What does the hardware actually do? | `MIT_AI_Training.md`, and `docs/` |
| Why is the code like this? | **`git log`** — every commit states its reason |

Do not create a second state document. Update `HANDOVER.md`.

**`demo/` no longer exists.** It was flattened into the repo root: `demo/api.py` is `api.py`,
`demo/playground.sh` is `symoneural.sh`. Any path with `demo/` in it is from before that and
is wrong.

## Parallelise builds

**Run as many agents concurrently as quality allows.** Compiles, model downloads and fine-tunes
occupy the machine for tens of minutes; that wall-clock should be filled with independent work,
not spent watching a progress bar. Launch subagents in one message so they actually run in
parallel. The GPU is available to agents that genuinely need it.

Scope agents to files nobody else is writing. The real hazard here is the generator scripts:
`build_pages.py`, `build_rack.py`, `build_console.py`, `build_cost.py`, `build_stack.py`,
`build_training.py` and `build_gallery.py` all rewrite files under `site/`, so two writers in
that directory will clobber each other. Safe parallel
tracks are read-only audits, brand-new standalone files, docs, and tests.

## The GPU is a single, contended resource

One RTX 5070 Ti, 15.92 GiB. Chat (~5 GB), image (~7 GB) and a QLoRA run (~12 GB) cannot coexist.

- Everything touching the GPU goes through `gpu-governor.sh`, ideally as
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

The base interpreter is pinned at exactly **7 packages** and must never be extended — check with
`pip freeze | wc -l`. `numba-cuda` silently downgrades numpy, and three other packages pin
conflicting `cuda-core`/`cuda-python` versions.

- The serving API deliberately uses only the **system** interpreter: fastapi, uvicorn and sympy
  are already OS packages, so there is no virtualenv in the serving path.
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

## Build and deploy

```bash
./fetch-models.sh            # weights -> models/ (ungated, Apache-2.0 sources)
python3 build_pages.py       # chat/image/calc/remix   -> site/*.html
python3 build_rack.py        # live rack               -> site/index.html
python3 build_console.py     # control board           -> site/index.html
python3 build_cost.py        # Owned vs Rented         -> site/documentation.html
python3 build_stack.py       # Inference Architecture  -> site/documentation.html
python3 build_training.py    # manual                  -> site/training.html
python3 build_gallery.py     # homepage art (uses GPU) -> site/art-*.png
./symoneural.sh on|off|status   # the live API (off is the kill switch)
sudo ./deploy.sh                # site/ -> /var/www/symoneural (needs a password)
```

The generator scripts are idempotent and must stay that way — `build_console.py` once nested
folds inside folds when run twice. **Run every generator twice and `diff` before committing.**
The BEGIN/END marker strings are the contract: change a marker in a generator and you must
change it in the HTML in the same commit, or the generator stops finding its block and appends
a second one.

`deploy.sh` pipes into `while read`, so its `missing=1` is set in a subshell and discarded — it
prints `MISSING <file>` but can never exit non-zero on it. Read the output, do not trust the
exit code.

## Test in a real browser, not with curl

```bash
node tests/frontend.mjs      # 9/9; system Chrome via Playwright, nothing to download
```

It asserts on what the DOM *shows*: units render from `/api/status`, the bus plate carries a
real reading, nothing overlaps at 390px, calc returns `x**3/3`, and a generated image actually
decodes. That last assertion exists because a render once succeeded server-side and still
showed as a broken image for every visitor — curl proved the endpoint answered, which was never
in doubt. Add an assertion here whenever you fix a frontend bug.

**Read computed styles rather than reasoning about the cascade.** Three separate bugs have now
come from generic class names colliding across components: `.bar` (collapsed the site header to
7px sitewide), `.live` (the nav badge styling the control board legend), and `#console .sub`
(a section rule outranking `.mod .sub`, rendering a footnote larger than the sentence above it).
Render the page and measure.

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
