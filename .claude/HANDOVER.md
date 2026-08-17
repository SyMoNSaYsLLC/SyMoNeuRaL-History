# HANDOVER — symoneural.com

**Written 2026-08-16 ~23:10 by the outgoing agent, for a fresh agent with zero prior context.**

Read this file first and read all of it. It is standalone — you will not have the previous
conversation, so every number, path and decision you need is stated here.

> **Precedence:** this file supersedes `HANDOVER-2026-08-16-1910.md` (the previous session's,
> archived for history) and `PROJECT-STATE.md`. `.claude/CLAUDE.md` remains authoritative for *rules*;
> this file is authoritative for *state and what is left to do*.

---

## 0. Sixty-second version

- The repo is now **a git repository** (it was not before). 18 commits, working tree clean,
  branch `main`, no remote. Every change below is committed with a reason in the message —
  `git log` is genuinely worth reading before you touch anything.
- **`demo/` is gone.** Everything moved to the repo root. `demo/api.py` is now `api.py`,
  `demo/playground.sh` is now `scripts/symoneural.sh`. Old paths in your memory are wrong.
- **Apache is retired; Caddy serves the site.** This is live and verified.
- **The site is DEPLOYED and current** as of 2026-08-16 23:28. `scripts/deploy.sh` had been failing
  for a different reason than everyone assumed — see §1. The API also runs under systemd now.
- There is a **real browser test suite**: `node tests/frontend.mjs` — 9/9 passing. Run it
  after any frontend change. It catches things curl cannot.

---

## 1. The deploy blocker — resolved, and it was not the password

`sudo ./scripts/deploy.sh` failed for hours with:

```
no staged site at /home/google/MIT_AI_Training/site
```

The script computed its source as `dirname "$0"/..` — correct while it lived in `demo/`, one
level too high after the flatten. **The password was never the problem; the path was.**
`scripts/fetch-models.sh` carried the identical bug. Both fixed, and a sweep of every tracked shell
script found no others (the two remaining `../` climbs are in correctly-nested scripts).

**Lesson worth keeping:** when the Python `.parent` climbs were fixed after the flatten, the
shell scripts were missed because the search was for Python idiom. If you move directories
again, grep for `dirname` and `../` in `*.sh` as well.

Two further fixes to `scripts/deploy.sh` in the same pass:

- Its verification loop piped into `while read`, so `missing=1` was set in a subshell and
  discarded — it could print `MISSING` and still exit 0. It now counts and exits 1.
- That check then cried wolf with `MISSING docs`, because `/docs` is a **route** served by
  FastAPI through Caddy, not a file. It now recognises proxied routes. A check that reports a
  false failure is worse than no check.

The static Swagger copy that used to be deployed to `/var/www/symoneural/docs/` is gone from
the deploy: Caddy proxies `/docs` to FastAPI, which generates it, so a disk copy is shadowed
and only ever goes stale. It was also the last routing living outside the API.

**Still true:** `sudo` is denied to agents and there is no TTY, so the user runs `scripts/deploy.sh`.
It works now.

---

## 2. Shipped in this session — all of it is live

All committed and deployed. Verified against symoneural.com after the deploy at 23:28:
`/`, `/documentation.html`, `/account.html`, `/docs` and `/api/status` all 200, the rack
precedes the control board, and the band artwork loads.

- **Homepage rebuilt as a lead-generation page.** Split hero ("Custom AI platforms that live
  in *your* building"), a full-bleed band of business objections around "why are you renting
  this?", an order section ("Tell us what you want to run"), and a flat link index.
- **Six band images rendered on this card** by `tools/build_gallery.py`, each watermarked with
  model, size, steps, seed and seconds. Seeds are pinned; `--force` re-renders.
- **Landing page is live-machine only**: hero → rack → control board. 6,236px → ~2,059px.
- **`documentation.html`** — the eight reference sections behind a tab strip, deep-linkable
  (`/documentation.html#kernels`).
- **`account.html`** — says plainly there is no signup/subscription/billing yet and quotes no
  price. **Do not add a price to this page.** See §4.
- **New header** across all pages: Documentation ⌄ / Manuals / API / Account ⌄ / Contact.
- **Rack above the control board**, hero tightened, `.vent` → real GPU/CPU bus plate.
- **Phone layout fixed** — `.unit` had no breakpoint at all below 620px.
- **Control board**: all 19 modules now carry a plain-English line above the engineering line.
- **No truncated text anywhere** — every `text-overflow:ellipsis` removed.
- **"Playground" wording purged**; `playground.sh` → `scripts/symoneural.sh`.
- Unit `train` renamed **SyMoNeuRaL Quantized Low-Rank Adaptation Tool**, detail
  "adapter loaded · for model/adapter tuning".

---

## 3. What changed structurally (do not re-learn this the hard way)

### 3.1 `demo/` was flattened into the repo root
Three things broke silently and are fixed; if you move anything again, check the same three:

1. `api.py` and `symoneural` used `ROOT = HERE.parent`. After the move that resolved to the
   repo's *parent*, which **exists** — so `models/` and `site/` would have been silently empty
   rather than raising. Now `ROOT = HERE`.
2. The five `build_*.py` generators used `.parent.parent / "site"`. Now `.parent`.
3. `training/.venv` had the old absolute path in 40 files (shebangs + `pyvenv.cfg`). Rewritten.
   Verified: `torch 2.11.0+cu128`, CUDA available.

### 3.2 llama.cpp binaries had an absolute RUNPATH
`llama-server` died with `libllama-server-impl.so: cannot open shared object file` because
cmake baked `/…/demo/llama.cpp/build/bin` into RUNPATH. **102 binaries repointed to `$ORIGIN`**
with `patchelf`, so the build tree is now relocatable rather than merely correct at one path.
If you rebuild llama.cpp, re-apply that or the same breakage returns.

### 3.3 Renders are served by the API, not the webroot
Generated images used to come back as `/<file>` — a path in the deployed webroot — while the
API wrote them into the staging `site/`. **Every image generated on the live site 404'd until
someone deployed.** They now come back as `/api/gen/<name>`, served by FastAPI, on the already-
proxied `/api` path. The name is attacker-controlled and hits the filesystem, so it is matched
against the exact shape the generator emits; traversal and bogus names 404.

### 3.4 Caddy replaced Apache — LIVE AND VERIFIED
`ops/Caddyfile` + `scripts/install-caddy.sh`. The user ran the manual equivalent. Verified:
`caddy` active/enabled, `apache2` inactive/disabled, fresh Let's Encrypt cert, `/`,
`/api/status`, `/docs`, `/openapi.json` all 200, and **`/api/ws` returns `101 Switching
Protocols`** — the rack's "pushed live over one socket" claim is true in production for the
first time (Apache never had `mod_proxy_wstunnel` enabled, so it had been silently falling
back to polling).

> **Testing WebSockets — two traps that produce convincing false failures.** `Upgrade:` is an
> HTTP/1.1 mechanism that does not exist in HTTP/2, and curl negotiates h2 with Caddy by
> default, so the header arrives as meaningless metadata and FastAPI 404s a websocket-only
> route. Use `curl --http1.1`. And a *successful* upgrade leaves the socket open and streaming,
> so curl exits 28 on timeout however well it worked — read the status line out of `-D` headers
> rather than trusting the exit code. Both are handled in `scripts/install-caddy.sh`.

**Architecture rule the user stated explicitly and cares about:**
> "only routing is done through the fastapi nothing else. Apache is just holding the frontend browser"

Caddy terminates TLS and serves static files. Everything else is `reverse_proxy` to
`127.0.0.1:8800`. No rewrites, no aliases, no conditional logic in the web server config.
`ops/symoneural.conf` and `ops/install-apache.sh` were **deleted** rather than left beside the
Caddyfile — two competing web-server configs is the same failure mode as the two competing
state files that already caused confusion here. Git still has them if rollback is ever needed.

### 3.5 The API serves `site/` at `/`
`api.py` mounts `StaticFiles` at `/` **last**, so it never shadows an API route. Production is
unaffected (Caddy serves the webroot), but it means the whole site runs from one origin, which
is the only way to exercise the real frontend — `console.js` opens a WebSocket and falls back
to polling, and neither works when pages are served from a different port than the API.

---

## 4. Rules that are not negotiable

`.claude/CLAUDE.md` has the full set. The ones that actually bit during this session:

- **Never invent pricing.** `account.html` and the order section both say outright that
  prices are quoted, not published, and *why*. The user has not asked for a price to be added
  and adding one would break the argument the entire site rests on.
- **Layout changes must not drop data.** This includes CSS truncation. Half the control board
  was showing `~84% of 896.1 p…` and the rack was cutting `built on Qwen2.5-7B-Instruct` down
  to `…7B-Ins…` — that attribution is an **Apache-2.0 licence condition**, not a nicety.
  Every `text-overflow:ellipsis` is now gone. Do not reintroduce one.
- **No decorative indicators.** The `.vent` slat block was removed for exactly this reason.
  Every LED and gauge reflects a real reading.
- **Label every figure** measured / vendor / projected.
- **Generators must stay idempotent.** Run each twice and `diff` — `tools/build_console.py` once
  nested folds inside folds. The BEGIN/END marker strings are the contract: if you change a
  marker in a generator you **must** change it in the HTML in the same commit, or the generator
  stops finding its block and appends a second one.
- **GPU: never a bare `gpu-governor.sh release`.** Name the surface. Fixed in
  `ops/symoneural-api.service`, which had it in both `ExecStartPre` and `ExecStopPost`.
- **Never `pip install` into the base interpreter** (pinned at exactly 7 packages). Installing
  into a venv *by its full path* is allowed and is the intended route.

### CSS collisions are a recurring bug class here
Three now: `.bar` (site header collapsed to 7px), `.live` (nav badge styling the control board
legend, so one of three legend chips had a pill and drew every eye), and `#console .sub`
(a density rule outranking `.mod .sub`, rendering the mono footnote at 15px — larger than the
sentence above it). **Render the page and read computed styles rather than reasoning about the
cascade.** The tooling for that is in §6.

---

## 5. Still to do

Roughly in the order the user asked for it. Items 1–2 are what the outgoing agent was about
to start.

1. **Image page restyle** — reference `references/stable-diffusion-webui-master/`.
   The user's words: "the text is all jacked up and looks like shit. Make it look good like
   the rest of the site."
2. **Chat page restyle** — reference the llama.cpp web UI. **It is already built** at
   `llama.cpp/tools/ui/dist/` (SvelteKit; `npx vite build` in `llama.cpp/tools/ui`). Serve it
   with `python3 -m http.server 8877 --directory llama.cpp/tools/ui/dist` and screenshot it.
   Design cues: slim left icon rail, centred empty state, one large rounded composer.
   The user wants **our colours and branding**, that layout.
3. **SyMoNeuRaL IPTV Player.** Base: `references/IPTV/IPTV/iptv_gateway_server.py` — FastAPI +
   ffmpeg stream-copy, most recent (Jul 18), and needs **zero new Python packages** (ffmpeg
   7.1.5 is installed). Use `references/IPTV/xtremecodes/services/XtreamClient.js` as the
   Xtream Codes protocol reference only. **`references/IPTV/mediatek_builds/` is empty** — the user guessed it
   was the good one; it is not. Requirement: load `playlist.m3u` **or** Xtream Codes
   url/username/password. **Credentials: visitor supplies their own, localStorage only, never
   stored on the box** (the user chose this explicitly).
4. **SyMoNeuRaL Miner** — GPU, Ravencoin. Base: `backend/apps/cryptominer/` (first-party, the
   user's own prior work; PowerShell-oriented, needs porting to Linux). It already refuses to
   start without `SYM_MINING_ENABLED=1` and reads real `nvidia-smi` telemetry. **Two
   constraints:** the governor has no concept of a tenant that *everything else* evicts (a
   miner is the opposite of `train`, which is never evicted) — design that tenant class
   explicitly; and **any Ravencoin/KawPow hashrate is vendor-or-projected, never measured**,
   until a miner binary actually runs, so the rack unit's honest default state is `offline`.
   There are two copies of `SymoneuralGPUWorker/SyMon_MinerGPUWorker_PROD_20260102-1818`
   (one with a ` 2` suffix) — diff and drop the duplicate.
5. **ASIC firmware control panel** for MicroBT + Antminer rigs. References: `references/Projects_Crypto/`
   (~2.5 GB of firmware), `references/CGMiner-master/`, `references/braiins-os-feeds-master/`, and `references/Pete/` (contains
   `pyasic` and `whatsminer-api`). **This is a much larger piece than the GPU miner — keep it
   separate, do not conflate them.**
6. **Backstage.io backend API pattern** — the user said this "MUST follow". References:
   `references/backstage-master/`, `references/software-templates-main/`. Needs its own scoping pass.
7. **`references/nx-master/`** as the server frontend reference.
8. **Audit the other agent's CUDA work** against the cuda-samples layout, the Python tooling,
   the cpp libraries and `references/reading/cuda-programming-guide.pdf`.
12. **Split `api.py` by concern, and put the engines behind an interface.** Garrett asked
    for this and the shape is agreed; it was deferred only because it would have been the
    seventh structural move of one long session.

    `api.py` is 1,573 lines and the mass is not where you would guess: roughly 1,060 lines
    of GPU/engine lifecycle, 186 of rate limiting, 92 of schemas, 91 of routes, 87 of
    websocket. So a thin `main.py -> server.py -> api.py` chain would produce three files
    and the same monolith. Split by concern instead, which is what llama.cpp does — its
    `main.cpp` is five lines and the work lives in `server-context`, `server-http`,
    `server-queue`, `server-task`, `server-chat` (all readable in
    `contrib/llama.cpp/tools/server/`).

    Target shape:
    ```
    backend/main.py        uvicorn entrypoint
    backend/app.py         FastAPI app, middleware, the static mount
    backend/engines/       llamacpp.py, sdcpp.py -- behind ONE interface
    backend/gpu.py         governor integration, eviction, residency
    backend/routes/        chat, image, calc, remix, status, gen
    backend/limits.py      throttling
    backend/schemas.py     pydantic models
    backend/live.py        the websocket hub
    ```

    **`backend/engines/` is the part with commercial value**, and it is the reason to do
    this at all. `LLAMA_SERVER` and `SD_CLI` are currently hardcoded paths, so supporting
    vLLM means editing the API. A customer with an A100 wants vLLM's throughput; a customer
    with a consumer card wants llama.cpp. The rack, the governor and the routes should not
    know which is running.

    **Do it with the test suite as the safety net**: `node tests/frontend.mjs` passes 9/9
    today, and it asserts on rendered DOM rather than on endpoints, so it will catch a
    broken split. Run it after every extraction, not at the end.

    Note when moving `api.py`: `HERE`/`ROOT` are derived from `__file__`, and `GOVERNOR`,
    `LLAMA_SERVER`, `SD_CLI`, `MODELS` and `GALLERY` all hang off it. That calculation has
    been wrong four times in this repo. Assert the root, as the generators and scripts now do.

13. **Compose the backend as plugins — the Backstage model, which Garrett required.**
    This is the other half of item 12 and the two fit together: llama.cpp gives the file
    layout, Backstage gives the composition model. Read
    `references/backstage-master/packages/backend/src/index.ts` and
    `references/backstage-master/plugins/search-backend/src/plugin.ts` for the real shape.

    Backstage declares a plugin as an id plus a register hook whose init receives its
    dependencies (`httpRouter`, `logger`, `rootConfig`) rather than importing them. Three
    consequences matter here, and each one solves a problem this repo already has:

    - **Every surface becomes a peer.** Garrett's objection was "why do reinforce and remix
      get directories but chat and image do not — cannot play favourites". Under a plugin
      model chat, image, calc, remix, IPTV and miner are the same kind of thing by
      construction, not by a naming convention someone has to remember.

    - **Injected services give the engine abstraction for free.** A plugin declares
      `deps: {gpu, limits, config}` and never learns whether llama.cpp or vLLM is behind
      the GPU service. Item 12's `backend/engines/` interface stops being a separate
      refactor and becomes a consequence of the composition model.

    - **The rack becomes a registry.** Today the five units are a hardcoded list inside
      `api.py`, so adding the IPTV player means editing the Unit list, the rack generator
      and the routes. Under a plugin model a surface appears on the rack *because it
      registered*. That is the difference between the six queued surfaces being days of
      work and being weeks of it. Do this **before** building IPTV and Miner, not after —
      they are the first two customers of it.

    URL shape already matches: Backstage mounts plugins at `/api/<pluginId>`, and this API
    already serves `/api/chat`, `/api/image`, `/api/calc`.

    **Take the boundary, not the ceremony.** Backstage's extension points, alpha service
    refs and DI container earn their keep across dozens of plugins and many teams. This is
    one box and one developer. Take the plugin boundary, the injected services and the
    registry; leave the rest until something actually hurts.

10. **Fix the `deploy.sh` subshell bug** (§1). Garrett asked for this explicitly
   and his reasoning is sound: the whole project is NVIDIA-bound, so learning the container
   path now is better than learning it under delivery pressure. He saved a reference at
   `Support for Container Device Interface — NVIDIA Container Toolkit.mhtml`.

   **DONE 2026-08-16 23:35 — CDI works.** `podman`, `nvidia-container-toolkit` 1.20.0 and
   `libnvidia-container` are installed. `/etc/cdi/nvidia.yaml` generated (CDI spec 0.7.0,
   3 devices: `nvidia.com/gpu=0`, `=GPU-15e0078a-...`, `=all`), and
   `nvidia-cdi-refresh.service`/`.path` are enabled so the spec regenerates on driver
   updates. Verified end to end: `nvidia-smi` printed the RTX 5070 Ti from inside a
   **rootless** container on the first attempt. Driver 610.57.04, CUDA UMD 13.3.

   ```bash
   podman run --rm --device nvidia.com/gpu=all \
     docker.io/nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi     # known good
   ```

   **What is left is the hard half:** deciding how a containerised API shares the GPU lock.

   **Recommend Podman over Docker here**, and say why rather than just doing it: rootless, so
   no daemon runs as root on a box serving the public; CDI is the native device path in
   toolkit 1.20 (exactly what his reference covers) rather than a legacy runtime hook; and
   quadlet gives systemd units, which is the model he just adopted for the API.

   Suggested first pass, in this order, and **verify each step before the next**:
   ```bash
   sudo apt-get install -y podman nvidia-container-toolkit
   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
   nvidia-ctk cdi list                        # expect nvidia.com/gpu=0 and =all
   podman run --rm --device nvidia.com/gpu=all \
     docker.io/nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
   ```
   That last command is the whole milestone: if `nvidia-smi` prints the 5070 Ti from inside a
   rootless container, CDI works and everything after it is ordinary packaging.

   **The GPU lock is the whole problem, and the failure mode is not what you would guess.**
   `scripts/gpu-governor.sh` is a **mkdir lock**: `run/gpu.lock.d`. `mkdir` is atomic, so the first
   process to create that directory wins and everyone else spins until it is removed. That
   directory *is* the mutex — there is nothing else.

   A container has its own filesystem. Run the API in one without bind-mounting `run/` and it
   creates `/app/run/gpu.lock.d` **inside the container**, which is a different directory from
   the host's. The host CLI mkdirs the host lock and succeeds. The container mkdirs its own
   lock and also succeeds. Both believe they own the card, both load weights, and ~12 GB of
   models hit a 16 GB card.

   The result is **not** a deadlock — a deadlock would be safe, because everything would stop
   and you would notice. What you get is a silent OOM at step 0 that looks like a CUDA problem,
   and you can lose hours in the wrong layer. (An earlier version of this note said "deadlock".
   That was wrong and worth correcting, because it points the debugging in the wrong direction.)

   The fix is one flag once you get there — bind-mount the run directory so both sides see the
   same lock:
   ```bash
   -v /home/google/Symoneural/run:/app/run
   ```
   Simplest correct design is one container holding every GPU surface, which matches the
   one-tenant-at-a-time architecture anyway. If surfaces are ever split across containers, the
   lock directory must be a shared volume every one of them mounts.

   **The real prize is the customer image, not this box.** `sm_120` + `cu128` on Blackwell is
   fragile to reproduce; "here is the image" is a far stronger handover than "here is a script".
   Note also that CUDA's EULA governs redistribution, so if a delivered image bakes CUDA in,
   read that clause first — see `LICENSES.md` §6.

10. **Fix the `scripts/deploy.sh` subshell bug** (§1).
11. **`sudo scripts/install-service.sh`** — DONE 2026-08-16 23:23; the unit is installed,
    enabled and running. Manage with `systemctl {status,restart,stop} symoneural-api`.

---

## 6. How to work on this

### Run the site locally
```bash
./scripts/symoneural.sh on          # API on 127.0.0.1:8800, serves site/ at / too
./scripts/symoneural.sh status
./scripts/symoneural.sh off         # stops everything, frees the card
```

### The build chain
```bash
python3 tools/build_pages.py       # chat/image/calc/remix surface pages
python3 tools/build_rack.py        # live rack        -> site/index.html
python3 tools/build_console.py     # control board    -> site/index.html
python3 tools/build_cost.py        # Owned vs Rented  -> site/documentation.html
python3 tools/build_stack.py       # Inference Arch   -> site/documentation.html
python3 tools/build_gallery.py     # homepage artwork -> site/art-*.png (renders on the GPU)
```
**Always run every generator twice and `diff` before committing.**

### Test in a real browser — this is the important one
```bash
node tests/frontend.mjs                    # 9/9; uses system Chrome via Playwright
```
It asserts on what the DOM *shows*: units render from `/api/status`, the bus plate carries
GPU/CPU/`--`, nothing overlaps at 390px, calc returns `x**3/3`, and **a generated image
actually decodes** (`naturalWidth > 0`). That last one is the assertion that would have caught
the 404 that shipped — curl proved the endpoint answered, which was never in doubt.

Playwright lives in `llama.cpp/tools/ui/node_modules` (installed for the webui build) and is
imported by absolute path. `channel: 'chrome'` uses the system browser, so nothing downloads.

Two scratch scripts worth recreating if you need them (they were in `/tmp`, not committed):
a **truncation checker** (compare `scrollWidth` to `clientWidth` across widths) and a **type
scale dump** (computed `font-size` for every text class, sorted). Both found real bugs that
looked fine by eye.

### Screenshots
```bash
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1600,3400 --virtual-time-budget=13000 \
  --screenshot=out.png http://127.0.0.1:8800/
```
PIL and ImageMagick are both available for cropping.

### Beware `pkill -f 'llama-server'`
The bracket trick does **not** save you with `pkill -f`: if the pattern appears anywhere in
your own shell's command line, pkill kills its own parent and your Bash tool call dies with
exit 144. Put the pkill in a command that does not otherwise mention the process name.

---

## 7. How the user works — read this, it will save you

- **They send many requests in rapid succession**, often several while one turn is still
  running. Expect to be interrupted and redirected mid-task.
- **They asked explicitly for a running checklist at the bottom of every reply**, grouped by
  status, because they lose track otherwise. Do this. Split it into **live on the site** vs
  **built but needs their deploy** vs **repo only** — conflating those caused a real
  "not true" disagreement this session, and they were right to push back.
- They will say **"not true"** or **"this didn't work"** with a screenshot. Check the live site
  before defending anything; usually the answer is that the change is real but undeployed.
- They **reverse decisions** — the rack CTAs were built and then removed on their say-so.
  Revert cleanly and completely (including any API field you added) rather than leaving dead
  code behind.
- They like the honesty framing and will back you when you hold a line on it, but do not
  lecture — state it in a sentence and move on.
- They reference designs by screenshot (the Anthropic homepage and nav were the models for the
  current front page). Ask for the reference if the description is ambiguous, but **verify it
  yourself** — they said the IPTV reference was "the one with mediatek" and that directory is
  empty.

---

## 8. Machine facts

- **RTX 5070 Ti**, Blackwell `sm_120`, 15.92 GiB usable, ~946 MiB idle.
- **PCIe Gen 3 ×8, host capped** — ~7 GB/s host↔device. The GPU itself does Gen 5. This is a
  published negative result and stays on the site.
- Chat: ~5 GB resident, measured **80–92 tok/s** with the persona adapter loaded.
- Image: FLUX.1-schnell q4_k, ~7 GB, **~11.2s** per 768×768 at 4 steps.
- Chat and image weight sets **cannot co-reside**. `scripts/gpu-governor.sh` serialises them.
- Base interpreter: exactly **7 packages** (`pip freeze | wc -l`). Training venv:
  `training/.venv`, torch cu128.
- Node 20.19.2 / npm 9.2.0, ffmpeg 7.1.5, patchelf, PIL 11.1.0, ImageMagick all present.
- `google-chrome` at `/usr/bin/google-chrome`.

---

## 9. Repo hygiene — what was cleaned up at the end of this session

- **`stable-diffusion-webui-master/` was committed by accident** (296 files, 4.6 MB) and is
  now untracked and gitignored. It is a vendored design reference for queue item 1, not our
  code. **Check `git status` before `git add -A`** — the user drops large reference trees into
  the repo root while you are working, and several have already had to be caught this way.
- **Three files claimed to be "current state".** There is now one: this file. `PROJECT-STATE.md`,
  the previous `HANDOVER`, the eleven root-level playbooks (superseded by `docs/symoneural-manual.md`),
  the old `.claude/START-PROMPT.txt` and `checkcoderswork.txt` all moved to **`docs/archive/`**, which
  has a README explaining what each one is and why it is not authoritative. Do not create a
  second state document; update this one.
- **The duplicate `SymoneuralGPUWorker/…-1818 2/` copy was byte-identical and is deleted.**
- **Every Apache reference that meant *the web server* is now Caddy**, including
  `ops/symoneural-api.service`, which still ordered itself `Before=apache2.service` — a real
  functional error after the migration. `scripts/install-caddy.sh` was reframed: it reads as a
  rebuild tool rather than a pending migration, and it no-ops cleanly on a machine without
  apache2. Remaining "Apache" mentions are **Apache-2.0 licence** references and must stay.

### Licensing, since it comes up
It is not Apache-only. What is actually in play:

| Licence | What |
|---|---|
| **Apache-2.0** | the model weights (Qwen2.5, FLUX.1-schnell) and Caddy |
| **MIT** | llama.cpp, stable-diffusion.cpp, FastAPI, Pillow (MIT-CMU) |
| **BSD-3-Clause** | uvicorn, SymPy |
| **NVIDIA** | the CUDA toolkit (not redistributed — customers install it themselves) |

Nothing is GPL or AGPL, and nothing forces this project's own code to be opened.

**MPL-2.0 does not apply to symoneural.com.** An earlier draft of this section said `certifi`
brought weak copyleft in. It does not: `certifi` is a Debian OS package on this box (pulled in
by certbot and requests), the serving stack never imports it — verified, importing fastapi,
uvicorn and sympy does not load it — and we do not redistribute it. The MPL line came from
`backend/apps/remix/THIRD-PARTY-LICENSES.md`, which audits the **remix component's** bundled
dependencies. That is a different distribution unit; if remix is ever shipped as a package, the
obligation is real there.

**The distinction that matters for any licence question here:** obligations attach to what we
*distribute*, not to what is installed on the server. We distribute `site/` (which includes a
vendored Swagger UI) and we serve model output. Debian packages on the box are the operator's
dependencies, not our redistribution.

**Known compliance gap, not yet fixed:** `site/swagger-ui-bundle.js` is 1.45 MB served to every
visitor and its own banner reads `For license information please see
swagger-ui-bundle.js.LICENSE.txt` — a file that does not exist in `site/`, in the webroot, or
anywhere on the box. Swagger UI is Apache-2.0 and the bundle embeds MIT code (core-js). Fetch
that file from the matching swagger-ui-dist release and drop it beside the bundle; `scripts/deploy.sh`
will pick it up.
`backend/apps/remix/THIRD-PARTY-LICENSES.md` has the full audit. The Apache-2.0 attribution on
the rack's `detail` line ("built on Qwen2.5-7B-Instruct") is a **licence condition** — that is
why truncating it mattered.

## 10. Repo layout after the flatten

```
api.py  symoneural  ravencalc.py            # the API, the CLI, the SymPy engine
build_pages.py build_rack.py build_console.py build_cost.py build_stack.py
build_training.py build_gallery.py         # generators
symoneural.sh gpu-governor.sh deploy.sh fetch-models.sh
ops/            Caddyfile, install-caddy.sh, install-service.sh, symoneural-api.service
site/           the deployable site (index, documentation, account, 4 surfaces, art-*.png)
tests/          frontend.mjs
training/       corpus, train_lora.py, adapter/, .venv
llama.cpp/ stable-diffusion.cpp/ models/    # gitignored, large
symoneural_reinforce/ symoneural_remix/     # CUDA engine, remix client
```

Gitignored: `models/` (40 GB), all vendored checkouts, `references/Projects_Crypto/` (~2.5 GB),
`references IPTV/`, `references/Pete/`, every `.venv`, `run/`, `site/gen-*.png`, `*.safetensors`, `*.gguf`.
Tracked: 337 files, ~7 MB, plus the six `site/art-*.png`.

**Watch out:** the user drops large reference trees into the repo root while you are working.
Check `git status` before `git add -A`.
