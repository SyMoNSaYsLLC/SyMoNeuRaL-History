# SyMoNeuRaL

Custom AI infrastructure that runs on hardware you own. This repo is **symoneural.com** and
the machine behind it: the public site, the inference API, the CUDA engine, and the
engineering manual every number on the site is drawn from.

The site is not a brochure with a demo bolted on. It is the machine, live — the rack on the
front page is reading `/api/status` as you look at it, and the images in the band were
rendered by the image surface below them, seed printed on each one.

**One RTX 5070 Ti, 15.92 GiB.** Chat (~5 GB), image (~7 GB) and a QLoRA run (~12 GB) cannot
co-reside, so exactly one holds the card at a time and the rest queue. That constraint is the
architecture, and the site says so rather than hiding it.

---

## Quick start

```bash
git clone <repo> symoneural && cd symoneural
./scripts/setup.sh            # checks the machine, tells you what is missing
./scripts/fetch-models.sh     # weights + their licences -> backend/models/
./scripts/symoneural.sh on    # API on 127.0.0.1:8800, serving site/ too
```

Then `http://127.0.0.1:8800/`.

**Nothing here hardcodes its own location.** Clone it anywhere: scripts derive their root
from their own path, `api.py` from `__file__`, the engine binaries from `$ORIGIN`, and the
systemd unit is a template the installer fills in.

Three steps need root, and `scripts/setup.sh` prints them rather than taking root itself:

```bash
sudo ./scripts/install-service.sh   # run the API under systemd
sudo ./scripts/install-caddy.sh     # TLS + static serving, /api proxied to the API
sudo ./scripts/deploy.sh --prune    # publish site/ -> /var/www/symoneural
```

**Three deploy commands exist and they are not interchangeable.** Working out which one a
change needs is the single thing that has cost this project the most rounds, so it is stated
here rather than only in the handover:

| What you changed | What publishes it |
|---|---|
| anything under `site/` | `sudo scripts/deploy.sh --prune` |
| `backend/api.py` or any `backend/apps/` module | `sudo systemctl restart symoneural-api` |
| `ops/Caddyfile` — including **any new top-level route** | `sudo ./scripts/install-caddy.sh` |

The third is the one that surprises people. Caddy serves everything from disk except the
paths it explicitly delegates, so **a new top-level URL 404s in production until that script
runs**, however correct the FastAPI route is. `127.0.0.1:8800/newpath` will answer 200 the
whole time, and `tests/frontend.mjs` passed 25/25 locally while all four section pages were
dead live. Run the suite against `https://symoneural.com` after any routing change.

`--prune` matters: without it, every file a deploy would no longer publish stays in the
webroot forever, never updated and never removed. Thirty-five orphans have been cleared this
way.

## Running it in a container

The GPU is attached with CDI, and the repo is mounted at `/app` so the host location is
irrelevant:

```bash
podman build -t symoneural-api -f ops/Containerfile .
./scripts/container-run.sh --detach
```

The one flag that matters is the bind mount of the repo, because `scripts/gpu-governor.sh` is a
**mkdir lock** on `run/gpu.lock.d` and that directory *is* the mutex. A container with its own
copy would let the host and the container both acquire, both load weights, and put ~12 GB of
models on a 16 GB card — a silent OOM that looks like a CUDA fault. `scripts/container-run.sh`
explains every flag it passes.

## Layout

```
CLAUDE.md               a one-line import -- must stay at root or the rules stop loading

backend/                the server
  api.py                chat, image, ravencalc, remix, status, /api/gen
  apps/                 components with their own code, docs and lifecycle
    accounts/           signup, login, sessions -- standard library only, not yet routed
    asicminer/          ASIC control panel; off unless SYM_ASIC_ENABLED and a token are set
    coder/              workspace agent; local-first, three gates, all failing closed
    cryptominer/        GPU miner (Ravencoin/KawPow) -- the `gpuminer` rack unit
    gateway/            TRON/USDT licensing; offline on the rack, designed not deployed
    guide/              turns a question into a channel filter; owns no weights
    licensing/          the dev fee -- signed contracts, verified offline
    project/            shared workspace for a person and the local models
    ravencalc/          exact symbolic maths (SymPy, CPU, never takes the GPU lock)
    reinforce/          TWO things share this directory. `symoneural/` is the native
                        CUDA engine (NVRTC, its own venv, its own suite). The modules
                        beside it are the training bay, which is what the rack unit
                        points at. Neither is the QLoRA; the fine-tune lives in training/
    remix/              playlist client of the chat surface
    sigils/             stickers with a real alpha channel, keyed out arithmetically
    tuner/              IPTV over ffmpeg stream-copy to HLS

bin/symoneural          the CLI -- one command over the whole stack

tools/                  the site generators, all idempotent -- twelve of them
  build_pages.py        the prompt surfaces           -> site/
  _art.py               shared markup for a render (not a generator -- do not run it)
  build_masthead.py     pitch + hero side by side     -> site/index.html
  build_rack.py         the live rack, two renders    -> site/index.html
  build_sky.py          the 19-render constellation   -> site/build.html
  build_console.py      the control board             -> site/index.html
  build_cost.py         Owned vs Rented               -> site/documentation.html
  build_stack.py        Inference Architecture        -> site/documentation.html
  build_training.py     the manual                    -> site/training.html
  build_sigils.py       the sigils surface            -> site/sigils.html
  build_tabs.py         one-screen front page, tabs   -> site/index.html
  build_split.py        one page per section -> site/{overview,livestack,controlboard,
                        receipts}.html. READS index.html, so it must run AFTER
                        everything that writes into it
  build_gallery.py      homepage artwork (uses the GPU, watermarks each render)
  build_cachebust.py    stamps ?v=<hash> on every local asset -- run this LAST

.claude/                CLAUDE.md (the rules), HANDOVER.md, START-PROMPT.txt, settings
site/                   the deployable site
scripts/                everything you execute
  setup.sh              verify a fresh clone can run here
  symoneural.sh         start/stop/status for the API
  container-run.sh      run the API in a rootless container with the GPU
  gpu-governor.sh       the GPU mutex -- one surface holds the card at a time
  fetch-models.sh       weights and their licences -> backend/models/
  deploy.sh             site/ -> /var/www/symoneural            (root)
  install-service.sh    run the API under systemd               (root)
  install-caddy.sh      TLS + static serving                    (root)

ops/                    config artifacts installed onto a system, not run from here
  Caddyfile             -> /etc/caddy/Caddyfile
  symoneural-api.service-> /etc/systemd/system/  (a @@ROOT@@ template)
  Containerfile         the API image recipe

contrib/                third-party source we build and run
  llama.cpp/            the chat engine
  stable-diffusion.cpp/ the image engine
  cuda-samples/         NVIDIA samples + the pinned 7-package venv
tests/frontend.mjs      drives the real pages in a real browser (26/26, local and production)
training/               corpus, train_lora.py, adapter/, its own venv (torch cu128)
docs/                   the manual, hardware dossier, environments, verification
docs/archive/           superseded -- do not act on anything in here
references/             third-party reference material, ~8.5 GB, none of it ours
backend/models/         weights, 40 GB, fetched by fetch-models.sh, never committed
backend/output/         generated renders, served as /api/gen/<name> -- NOT from site/
run/                    runtime state: the GPU lock directory, pidfile, logs.
                        Not "logs/" -- gpu.lock.d lives here and the name is what stops
                        somebody logrotating a mutex out from under a running surface
```

**Why `backend/apps/` has thirteen entries and chat/image do not.** Chat and image are
routes inside `api.py` — one process, one GPU lock, one deployment. The things under `apps/`
are separate codebases with their own docs, dependencies and release cycle. That is a real
distinction rather than a favourite, and it answers the next question directly: a surface
arriving with its own dependencies and deploy story belongs in `backend/apps/`; a surface
that is just more routes belongs in `api.py`.

The owner has already pushed back on this once — "why do reinforce and remix get directories
but chat and image do not, cannot play favourites" — and the answer above is the reason
rather than a defence of it. `.claude/HANDOVER.md` §5 item 11 records the agreed fix: compose
the backend as plugins so every surface is a peer by construction, and the rack becomes a
registry a surface appears on *because it registered*. That is not built.

**The rack is the authority on how many surfaces exist, and this file is not.** `GET
/api/status` answers with the live list, currently twelve units. Count it there; the
equivalent line has already been stale twice in `.claude/HANDOVER.md`.

## The rules this project actually runs on

Read `.claude/CLAUDE.md` before changing anything. The short version:

- **Label every figure** — measured on this machine, vendor specification, or projected
  arithmetic. A projection is never presented as a result.
- **Never invent pricing.** Quotes depend on hardware and workload; a made-up number would be
  the one dishonest thing on a site whose whole argument is measurement.
- **No decorative indicators.** Every LED and gauge reflects a real reading.
- **Layout changes must not drop data** — including CSS. `text-overflow: ellipsis` on a detail
  line is data loss with extra steps.
- **Publish negative results.** The PCIe Gen 3 ×8 ceiling is on the site deliberately.
- **Generators must stay idempotent.** Run each twice and `diff` before committing.
- **Test in a browser, not with curl.** A render once succeeded server-side and still showed
  as a broken image to every visitor.

## Where to look

| Question | File |
|---|---|
| What are the rules? | `.claude/CLAUDE.md` |
| What is the state, what is left to do? | `.claude/HANDOVER.md` |
| What can we ship, and what must travel with it? | `LICENSES.md` |
| What does the hardware actually do? | `docs/symoneural-manual.md`, `docs/` |
| Why is the code like this? | `git log` — every commit states its reason |

## Licensing

The stack is permissively licensed throughout — Apache-2.0 for the weights and Caddy, MIT for
llama.cpp and stable-diffusion.cpp, BSD-3 for uvicorn and SymPy. **Nothing is copyleft**, so
products built on this can be proprietary. What must travel with a build, and the obligations
for each licence, are in `LICENSES.md`.

Our own code, the LoRA adapter and the training corpus are proprietary to SymonSays LLC.

---

© SymonSays LLC · [symoneural.com](https://symoneural.com) · symonsayadmin@symoneural.com
