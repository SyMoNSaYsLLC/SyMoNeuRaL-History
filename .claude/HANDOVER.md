# HANDOVER — symoneural.com

**Last updated 2026-08-17 08:30. Written for a fresh agent with zero prior context.**

> **If you read nothing else:** nothing is broken, nothing is blocked, and **nothing is
> waiting on a deploy** — the repo and production agree. Run `node tests/frontend.mjs` and
> `node tests/frontend.mjs https://symoneural.com`; both should say **26/26**. If they
> disagree, production is behind and only Garrett can fix that — see §0b. Read `git log`,
> then §5.

Read this file first and read all of it. It is standalone — you will not have the previous
conversation, so every number, path and decision you need is stated here.

> **Precedence:** this file is authoritative for *state and what is left to do*.
> `.claude/CLAUDE.md` remains authoritative for *rules*. Anything in `docs/archive/` is
> superseded — do not act on it.

---

## 0. Sixty-second version

- **Nothing is broken, nothing is blocked, nothing is pending.** **26/26 locally and
  26/26 against the public site**, verified 2026-08-17 08:30. The suite generates a real
  image on the real card mid-run, so it is a genuine end-to-end check.
- **Three deploy commands exist and they are not interchangeable.** `site/` content needs
  `sudo scripts/deploy.sh --prune`; `backend/api.py` needs
  `sudo systemctl restart symoneural-api`; `ops/Caddyfile` needs
  `sudo ./scripts/install-caddy.sh`. Work out which a change requires and say so — several
  rounds were lost to running the right command for the wrong file.
- The repo is at `/home/google/Symoneural`, branch `main`, no remote. **Every commit
  states its reason**; `git log` is genuinely worth twenty minutes before you touch
  anything. Several entries below will otherwise look arbitrary.
- **Nothing hardcodes its own location.** Scripts derive their root from their own path,
  `backend/api.py` from `__file__`, the engine binaries via `$ORIGIN` RUNPATH, the systemd
  unit from a `@@ROOT@@` template. Clone it anywhere and `./scripts/setup.sh` works. Keep
  it that way — the user asked for this explicitly and it has been broken four times.
- **Caddy serves static files; FastAPI does all routing.** Apache is gone entirely. Do not
  reintroduce a second thing that routes.
- **One RTX 5070 Ti, 15.92 GiB, one tenant at a time**, arbitrated by a `mkdir` lock at
  `<root>/run/gpu.lock.d`. That constraint is the architecture. See §4.
- **Twelve rack units now**, not eight and not five. `GET /api/status` is the authority and it
  answers, in order: `chat`, `image`, `remix`, `ravencalc`, `train`, `asicminer`, `gpuminer`,
  `tuner`, `coder`, `gateway`, `guide`, `project` (verified 2026-08-17 against the running
  API). Count it there, not here — this line has already been stale twice. The four beyond the
  eight below arrived on 2026-08-17 from work that is **in the working tree and uncommitted**:
  `gpuminer` (§5 item 4), `coder`, `guide` and `project`. §2c has the shape of the first three
  additions; §2d the dev fee; §2e firmware and the QEMU emulator.
- **`/` redirects (302) to `/overview`.** The front page is four sections, each at its own
  URL — `/overview`, `/livestack`, `/controlboard`, `/receipts`. The tabbed one-screen
  `index.html` still exists and still answers at `/index.html`; it is the page
  `tools/build_split.py` reads to build the other four, so it cannot simply stop being
  generated. **Whether to retire it is an open question — see §5.** Eleven generators now.
  §3.0 explains the layout and, more usefully, the four ways its tests lied.
- **Every section fits one screen with no internal scroll**, at every viewport the gate
  allows, 1301x740 through 2560x1440. Below 1301px wide the gate is off and the page
  scrolls normally with everything visible. **Mobile cannot reach zero scroll** — at 390px
  the rack alone is 2,700px — and should not be promised it.
- **The queue in §5 was rewritten** at the end of that session. Read §5, not §5b — the
  latter is the original list kept only for reference and much of it is done.

## 0b. First moves

```bash
node tests/frontend.mjs                 # 26/26 against the local API on :8800
node tests/frontend.mjs https://symoneural.com   # 26/26 -- these should agree
git log --oneline -25
```

**The one workflow fact that has caused every misunderstanding in this project:** API
responses change the instant you edit `backend/api.py` and restart the service; static
files under `site/` do not reach a visitor until someone with root runs
`sudo scripts/deploy.sh --prune`. You cannot run that yourself. When you finish a frontend
change, say so plainly and hand the user the command — do not describe the change as live.

A second, related one: **a running Python process pins its import paths and its resolved
`pathlib` constants at start.** Moving a file under a live service leaves it working until
something touches the moved thing. After any move, ask for `sudo systemctl restart
symoneural-api` and then hit the surface you moved. This bit twice in one night.

---

## 0c. THE OVERNIGHT QUEUE — written 2026-08-17 ~12:45, Garrett asleep

Garrett handed over a long list and went to bed, asking explicitly that the plan live here in
case the session dies. This section is that plan. **Work top to bottom; each item says what
"done" means so a fresh agent can tell finished from started.** Tick items off *in this file* as
they land, and keep the measurements — they are the deliverable as much as the code is.

### WHO IS WRITING WHAT — read this before you edit, 2026-08-17 ~17:00

Garrett has put **one agent per app** on the five surfaces, so several writers are live in
this repo at once. `tools/build_*.py` all rewrite files under `site/`, and two writers in that
directory clobber each other silently — the file just loses one of the two edits.

| Claimed by | Files |
|---|---|
| the tuner/site agent (this one) | `backend/apps/tuner/**`, `tools/build_pages.py`, `site/tuner*.html`, `site/symoneural.css`, `tests/tuner_*`, `tests/frontend.mjs` |
| per-app agents | `backend/apps/<their app>/**`, `site/<their surface>.html` and the generator that writes it |
| nobody — coordinate first | `ops/Caddyfile`, `scripts/deploy.sh`, this file's §0c |

**`backend/api.py` was edited by the tuner session at ~14:45**, for one thing only: deleting the
`guide` rack unit for the Tuner+Guide merge Garrett asked for. Nothing else in that file was
touched. It is otherwise still coordinate-first. See §2h.

If you need a file another agent holds, say so in your report rather than editing it. Append to
this file; never rewrite a section you did not write.

### BLOCKER, and it blocks everything backend

```bash
sudo systemctl restart symoneural-api     # backend changes -- Movies, slots, EPG, everything
sudo scripts/deploy.sh --prune            # site/ -> /var/www/symoneural
```

Neither can be run without a password, so **no agent can verify any backend change against the
live site.** Verify against a throwaway app instead — the recipe that works is in §2c-bis. Say
plainly in every report that the live site does not have the change yet. Garrett spent an hour
believing Movies was still broken when the fix had been on disk the whole time; the running
process was started at 11:43:56 and every fix postdates it.

### 1. Tuner — DONE, on disk, unverified live

- **Movies load.** 31,888 titles. Cause and fix: §2c-bis.
- **All size caps removed at Garrett's explicit instruction** (`Policy.max_bytes`,
  `CATALOGUE_MAX_BYTES`, `m3u.MAX_CHANNELS`, `routes.MAX_PASTE` — all `0`, meaning uncapped).
  Wall-clock deadlines are what bound a fetch now, and that was always the bound doing the work.
- **Time to first frame: 31 s -> 2,384 ms**, measured in real Chrome on ESPN FHD off the real
  panel. Cause: `-c copy` cuts only on keyframes, so a 10 s GOP yields 10.4 s segments whatever
  `-hls_time` says (measured `#EXT-X-TARGETDURATION:10`, `#EXTINF:10.427`), and hls.js's default
  `liveSyncDurationCount: 3` therefore waited ~31 s. Now 1. **This is not a language problem and
  rewriting anything in C++ will not touch it** — ffmpeg stream-copies, nothing decodes, the box
  is idle while the player waits on its own buffer policy. Garrett asked about C/C++ twice; the
  answer is the buffer arithmetic above, and it is worth restating rather than re-litigating.
- **Slots.** `tune` now takes `release`, so a channel change hands its slot back in the same
  request; `POST /session/{sid}/stop` exists for `navigator.sendBeacon` on `pagehide`; a tab
  hidden 20 s releases; `IDLE_TIMEOUT` 45 -> 12 s and the reaper ticks 2 s instead of 5.
  Measured: one session across three channel changes, **zero within 2.5 s of closing the tab**
  (it was up to ~50 s). The account's own `max_connections` is 2 and `MAX_SESSIONS` is 2, so a
  leaked slot was half the tuner.
- **The lie that made this look like censorship:** a full tuner answered "your provider refused
  it — not a limit here", which is exactly backwards. Now named as this box's limit. There is
  nothing adult-specific anywhere in the code and never was; ADULT channels stream h264 fine.

### 1b. THE FLEET — eleven sessions are in this working copy RIGHT NOW (2026-08-17 14:55)

This is no longer a two-session split. `ListAgents` reports a background session per surface,
and the file times agree with the names:

| Session | Owns — do not write these files | Evidence on disk |
|---|---|---|
| `symoneural reinforce lora tuning` | `backend/apps/reinforce/**` on branch `worktree-reinforce-rl` | `23f96b3` |
| **unidentified** | `tools/build_reinforce.py`, `site/reinforce.html`, `site/reinforce.js`, and the uncommitted `/api/train` mount in `main`'s working copy | written 14:49, still untracked |
| `symoneural miner completion` | `backend/apps/asicminer/**` (code), `site/miner.html` | — |
| `symoneural coder online integration` | `backend/apps/coder/**` | — |
| `symoneural gateway online status` | `backend/apps/gateway/**`, `site/gateway.html` | — |
| `symoneural project completion verification` | `backend/apps/project/**`, `site/project.html` | — |
| the tuner session | `backend/apps/tuner/**`, `tests/tuner_*`, `site/tuner*.html` | 13:44–14:40 |
| `symoneural typography spacing` | type/spacing in `site/symoneural.css` | — |
| `online applications testing` | `tests/frontend.mjs` | 29-line rack-unit block added |
| this session (handover/review) | `.claude/HANDOVER.md`, `tools/build_masthead.py`, `backend/apps/accounts/routes.py`, `scripts/qemu-antminer.sh` | committed below |

**`tools/build_pages.py` and `backend/api.py` are the two contended files.** Every surface needs
a page (`build_pages.py`) and a mount (`api.py`), so both will be edited by several sessions in
the same hour. Rules that follow from that, and they are not optional:

- **Never rewrite either file whole.** Targeted edits only, re-read immediately before writing.
- **`python3 -c "import ast; ast.parse(open('backend/api.py').read())"` after every api.py edit.**
  A half-applied concurrent edit there takes the entire site down on the next restart, and
  nobody can restart it — `sudo systemctl restart symoneural-api` needs a password no agent has.
- Commit your own paths as you finish. Never `git add -A`: it will stage nine other sessions'
  half-finished work, and one of those files is a generator mid-rewrite.

Merges have worked so far: the tuner session's `ac3`/`aac` fixture cases and this session's
`emptylive` case coexist and `node tests/tuner_failpaths.mjs` is **27/27** with both in.

### 1c. THE MERGE — nine branches, four bases, and one file everybody edited (14:59)

`git branch` shows **nine `worktree-*` branches**, one per fleet session, forked from **four
different base commits** (`595835d`, `2f285a5`, `8e835cb`, `e38f463`). Nobody merging one of them
can see this list, so it is recorded here. Measured with `git merge-tree --write-tree --name-only
main <branch>`, which trial-merges without touching the working tree — re-run it, do not trust
the table's age:

| Branch | Base | Merges into `main` |
|---|---|---|
| `worktree-project-page` | `e38f463` | **clean** |
| `worktree-site-typography-tlc` | `2f285a5` | **clean** (and it rewrites 12 `site/*.html`) |
| `worktree-docs-accuracy` | `2f285a5` | **clean** |
| `worktree-online-apps-audit` | `8e835cb` | **clean** |
| `worktree-stickers` | `8e835cb` | empty — 0 commits |
| `worktree-miner-online` | `e38f463` | conflicts in `.claude/HANDOVER.md` only |
| `worktree-gateway-online` | `595835d` | 5: `apps/gateway/__init__.py`, `site/gateway.html`, `tests/frontend.mjs`, `tools/build_pages.py`, a spec |
| `worktree-coder-online` | `595835d` | 8, including `.claude/CLAUDE.md`, `backend/api.py`, `tools/build_pages.py`, `tests/frontend.mjs` |
| `worktree-reinforce-rl` | `595835d` | 10 — `backend/api.py` and **every file in `backend/apps/reinforce/`** |

**Merge in that order — clean first.** Each merge changes `main` and can turn a clean branch
dirty, so the four that cost nothing should land before the four that cost something.

Three things will save the person doing it real time:

- **A conflict in `site/*.html` is not a conflict.** Eleven of those pages are generator output.
  Resolve by taking either side, then re-running the generator and committing what it emits —
  `site/gateway.html` conflicting while `tools/build_pages.py` also conflicts means there is
  exactly one real conflict, in the generator. Hand-merging the HTML produces a page that no
  generator will reproduce, and the next build silently reverts it.
- **`.claude/HANDOVER.md` conflicts are append-vs-append.** Keep both sides. That is the whole
  resolution, and it is why `worktree-miner-online` is listed as conflicting at all.
- **`backend/api.py` is the one file with a real merge.** Four branches edit it: coder, miner and
  reinforce add units or mounts, and the miner session has already merged the two miner rows into
  one `Unit(id="miner")` carrying `sub: list[SubUnit]` with `gpuminer`/`asicminer` one level down.
  **Anything that looks up a unit by id must search the top level and then `sub`** — the site
  deploys before the API restarts, so both shapes are live at once for a while. `ast.parse`
  after every resolution.

**Merging `worktree-reinforce-rl`'s `backend/api.py` wholesale reverts four surfaces.** That
branch forked at `595835d`, so its copy of the file carries **two** `include_router` calls —
`tuner` and the new `reinforce` — where `main` has five. Verified here, not taken on trust:
`git show worktree-reinforce-rl:backend/api.py | grep -c include_router` prints 2. Take the
import line and the `include_router` line by hand; accepting that side of the conflict silently
un-mounts accounts, gateway, guide and project. The mount itself is right and is `23f96b3`.

**Who wrote the training bay page is unknown, and that matters for who to ask.** An earlier
revision of §1b credited `tools/build_reinforce.py` and `site/reinforce.html` to the reinforce
session. It has checked and denies them: they are absent from its branch, and it never created
them. They appeared in `main`'s working copy at 14:49 alongside an uncommitted `/api/train`
mount and an uncommitted `tools/build_pages.py`, and all of it is **still untracked or
uncommitted**. So the bay page has no owner on record — do not assume the reinforce session
will commit it, and do not delete it assuming it is a stray.

**The sharpest hazard is Reinforce, which exists in two places at once.** `main`'s working copy
carries an uncommitted `/api/train` mount in `backend/api.py`, an uncommitted
`tools/build_pages.py`, and untracked `site/reinforce.html`, `site/reinforce.js`,
`tools/build_reinforce.py` — a training-bay surface. Separately, `worktree-reinforce-rl` rewrites
the whole of `backend/apps/reinforce/` (it adds `rewards.py` and `rollout.py`, so it is
reinforcement learning, not the LoRA bay) and conflicts with all ten of those files. **Do not
merge that branch before someone has committed or discarded the working-copy work**, or one of
the two bodies of work will be silently overwritten. Whoever owns them should say which is which
before either lands.

### 2. Tuner guide + EPG — **DONE 2026-08-17 ~14:45**, on disk, live site pending a restart

His words: *"update the damn tuner guide with epg and not that terrible tiny select and deselect
shit"*, integrate the **SyMoNeuRaL Guide AI** so it is "smart based off location, asks a couple
questions, and has a floating prompt available for the user to custom prompt update the tv
guide", and move the stream to its **own page — `symoneural.com/tuner/watch`** — so it can go
near-fullscreen with PiP and guide settings.

- EPG sources, both reachable through the existing `safefetch` path: `xmltv.php?username=&
  password=` for the whole account as XMLTV, and `player_api.php?action=get_short_epg&
  stream_id=N&limit=N` for one channel as JSON with base64 titles. The join key is `tvg_id` /
  `epg_channel_id`, which `load_channels` already carries. Full XMLTV for 10,124 channels is
  large — the caps are gone, so that is no longer a blocker, but per-channel on focus is the
  lighter default and gives now/next on the row.
- The category chips are what he means by "tiny select and deselect". Replace with a real grid:
  time across, channels down, now/next in the cell.
- ~~`/tuner/watch` is a new route, so `ops/Caddyfile` must delegate it.~~ **Moot, and checked:
  no Caddy change is needed and no `sudo ./scripts/install-caddy.sh` is owed.** The warning was
  right about the mechanism and wrong about what got built: the watch surface shipped as
  `site/tuner-watch.html`, a static file, and `grep` finds no `/tuner/watch` route in
  `backend/api.py`. Caddy's `@sections` matcher is still exactly `/ /overview /livestack
  /controlboard /receipts`, and `handle { file_server }` serves any new `.html` off the webroot
  with no config at all. Same for `site/reinforce.html`. The rule that remains true, and it is
  the one to carry forward: only a new top-level *section* path costs four files
  (`ops/Caddyfile`, `tools/build_split.py`, `backend/api.py`, `tests/frontend.mjs`).
- Guide AI: `backend/apps/guide/` exists with 50 tests. Location-aware means asking, not
  geolocating — do not add IP geolocation to a box whose whole argument is that it measures
  rather than infers.

### 3. Player options / settings / statistics — **DONE**, on both tuner pages

Garrett asked for this directly. Everything must be a real reading, house rule: level and
bitrate, audio tracks, buffer length, dropped frames, measured throughput — all available from
hls.js. `segment_s` and `segments` are already published on the session for this purpose.

Built as `<details class="tn-stats">` on `/tuner.html` and as the `s` panel on
`/tuner-watch.html`: twelve readings, a quality selector, an audio-track selector, PiP and full
screen. See §2h. Every figure is read from the player or the session document, and a figure the
player has not reported yet renders `-`, which is itself the reading.

### 4. Five surfaces to bring online — ONE SESSION EACH, IN FLIGHT (see §1b)

**Do not start these from a general session.** As of 14:55 there is a dedicated background
session per surface and they are already writing: `site/reinforce.html` and
`tools/build_reinforce.py` appeared at 14:49. A second agent doing the same surface will clobber
a generator mid-write. What is below is the survey those sessions should be reading, not a
queue to pick up.

**Still true and owned by nobody, so somebody must do it:** `apps.reinforce` has *no*
`include_router` in `backend/api.py` (verified 14:52 — only tuner, accounts, gateway, guide,
project are mounted), and the `train` rack unit at `api.py:1449` is hand-rolled with
`href="/training.html"` — the manual — while `apps.reinforce.status()` already returns the
correct unit dict with `href="/reinforce.html"`. Its own docstring names the contract:
`app.include_router(router, prefix="/api/train", tags=["reinforce"])` and `Unit(**status())`.
Verified safe to mount: `python3 -c "import sys; sys.path.insert(0,'backend'); from apps.reinforce
import router, status"` imports clean on the **system** interpreter (7 routes) — it does not drag
torch into the serving path.


In his order: **Reinforce** as a real tuning/training studio, **Miner** online, **Coder** online,
**Gateway** online, **Project** online ("this is like cowork"). All five already have rack units
and backend apps; "online" means a working page and route, not a new surface. (An earlier
revision said Reinforce carried a red test and an alpha/rank question for Garrett. It carries
neither — that was stale bytecode, settled in `f9f3546`. See §1.)

What each one actually needs, established by reading the code rather than assuming:

- **Reinforce** — `backend/apps/reinforce/routes.py` is complete, and its docstring says it is
  "Mounted at `/api/train` by `backend/api.py`". **It is not mounted**; there is no
  `include_router` for it. The gate is already right: `enabled()` needs both
  `SYM_REINFORCE_ENABLED=1` and `SYM_REINFORCE_TOKEN`, reads are open once enabled, writes always
  need the token in an `x-reinforce-token` header via `hmac.compare_digest`. There is no studio
  page — `site/training.html` is the 8253-line *manual*, which is why the `train` unit's href
  points at it.
- **Coder** — offline **by deliberate design**, and it has no HTTP route at all. An agent that can
  develop the site is arbitrary code execution on the box serving the public internet, and
  `/api/*` is wholly delegated to FastAPI, so a route is a public route. "Online" here cannot mean
  a public endpoint; decide what it *does* mean before writing anything.
- **Project** — offline solely for want of `SYM_PROJECT_ENABLED`/`SYM_PROJECT_TOKEN`. Its 14
  routes exist and work. `site/project.html` belongs in `tools/build_pages.py`, which the tuner
  session is holding, so the page is blocked on that session landing — not on any design question.

**A new `.html` file and a new `/api/*` subtree need no `ops/Caddyfile` change and no `is_route()`
change** — verified by reading both. `handle /api/*` delegates the whole subtree, and
`is_route()` in `scripts/deploy.sh` checks a new page as a *file*. Only a new top-level *section*
path (the `/overview /livestack /controlboard /receipts` class) costs four files.

### 5. Site-wide, and he repeated it twice

- **"We went a little too small on the website; fill the detected window better on the fly"** —
  for `/overview`, `/livestack`, `/controlboard`, `/receipts` specifically. **DONE for all four,
  measured; see §5c for the numbers and the two negative results.** In short: the causes were not
  the ones anyone assumed. Content already spanned the width; what was small was the 1120px
  header/footer islands and 12.5px type at *every* width, plus a control board sitting 383px tall
  in a 1277px panel. All three fixed in `site/symoneural.css` (which is **not** generator-written,
  so it is safe to edit by hand). Both browser suites re-run green afterwards: `frontend.mjs`
  26/26, `tuner_failpaths.mjs` 23/23.
- **Verify every link works. DONE, and it is now a command rather than an audit:**
  `python3 tools/check_links.py` — 20 pages, 912 links, 282 unique targets, **clean**, exit 1 if
  not (re-run 14:58, after `site/reinforce.html` and `site/tuner-watch.html` appeared). One real
  break existed and is fixed in `b5f4e4f`: the masthead's `See it running` pointed at `#rack`,
  which does not exist on `/overview` since the page split — and `/` 302s there, so it was dead
  on the page nearly every visitor reads. Two false positives are guarded in the script and
  documented in its docstring, because both cost time: `data-src="live"` is not a link (a bare
  `(href|src)=` regex matches the tail of `data-src`), and `documentation.html#hardware` is a
  file *plus* an anchor, so both halves need checking — that second one is what found the break.
- **Fix grammar, capitalisation, and sentences that do not make sense.** Sweep, do not
  blind-replace — most `MIT` matches in this corpus are ordinary words. **Partly done, and the
  rest is deliberately deferred — read this before re-running it.**
  - Fixed: both `/api/accounts/status` notes, which were lower-case fragments rendered verbatim
    as a sentence on `/account.html` and read like a log line that had escaped onto the page
    (`b5f4e4f`).
  - A mechanical pass over all 20 pages (prose inside `<p>/<li>/<h*>/<dd>/<summary>`, looking for
    lower-case sentence starts, doubled words, its/it's, and the product name misspelled) threw
    **321 hits and not one real defect**. They are artefacts of the extractor, and both causes
    are worth knowing before someone runs the same idea again: the bulk are `build.html`'s image
    *prompts*, which are lower-case on purpose and are quoted input rather than prose, and the
    rest are HTML entities — stripping `&mdash;` to a space turns "net of its own electricity —
    12 to 41 days" into a sentence that looks broken and is not. **Regex will not find this
    class of bug here. It needs reading.**
  - Deferred on purpose: `site/miner.html`, `gateway.html`, `project.html`, `reinforce.html` and
    the tuner pages are being rewritten by their own sessions *right now* (§1b). Proof-reading a
    page that is mid-rewrite means proof-reading text that will not exist in an hour. Do this
    sweep when the fleet has landed, and do it by reading the rendered pages.
- **`SYM_ASIC_ENABLED=1` is confusing on the QEMU Antminer emulators.** His words. **DONE in
  three of four places**, and the confusion was worth naming precisely: the two variables gate
  the **HTTP API only**. `scripts/qemu-antminer.sh` needs neither, and no emulator can ever
  produce telemetry — QEMU emulates the Zynq CPU, not the hashboards, so nothing answers on
  port 4028 whatever the variables say. That is now written at each point of use:
  `backend/apps/asicminer/__init__.py` (docstring + both refusal strings, which keep the literal
  `SYM_ASIC_ENABLED=1` because it is copy-pasteable and `test_asic.py::test_disabled` asserts
  it — 42/42 green), `scripts/qemu-antminer.sh` (a header block: YOU DO NOT NEED
  SYM_ASIC_ENABLED TO RUN THIS), and `backend/apps/asicminer/README.md`.
  **OWED: the same sentence on `site/miner.html`**, which is written by `tools/build_pages.py`.
  That file was held by the tuner session and is now in the miner session's lane (§1b), so this
  half is handed to whoever owns `build_pages.py` — it is a page-text change, not a code change.
  Landing three quarters of a clarification reads as done and is why this line exists.
- **"Account needs to be configured as discussed."** *What was discussed is not in this file and
  not in any transcript here.* §2g holds two undecided design questions that may be it. **Ask
  before building; do not guess at an account model.** But separate the two halves, because one
  of them costs Garrett a single sentence to answer:
  - **The switch.** `/account.html` reads CLOSED for a mechanical reason, not a design one:
    `enabled()` in `backend/apps/accounts/__init__.py:233` needs `SYM_ACCOUNTS_ENABLED=1` **and**
    `SYM_SESSION_SECRET`, and `ops/symoneural-api.service` sets neither (it carries only
    `PYTHONUNBUFFERED` and `SYMONEURAL_PORT`). Turning accounts on is two `Environment=` lines
    plus `sudo systemctl daemon-reload && sudo systemctl restart symoneural-api` — **a password
    no agent has.** Generate the secret on the box, never in a transcript:
    `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
    The status note both states now read as sentences rather than log lines (`tests/account.mjs`
    still 17/17, it matches `/session secret/i`).
  - **The model** — who may sign up, what an account entitles, whether it gates the tuner or
    only the paid surfaces. That is the part that needs him, and no amount of reading settles it.

### 6. Later, explicitly not now

Once the server is finished: either train the model or build **individual Apple apps per
surface** (`symonioschat`, `symoniosimage`, ... — his names, approximate) talking to this API.
That is a client project against a stable API, so it is gated on the API being stable.

### The standing risk — the backlog is gone, the remote still is too

The ~100-path pile is **committed**: `8e835cb`, `e38f463`, `f9f3546`. Garrett's instruction is
**"you own the commits, I'll tell the others to stop staging"** — so commit your own work as you
finish it, stage only the paths you actually own, and never `git add -A` while another session is
writing. What remains uncommitted is one session's live work, which is theirs to land.

**There is still no git remote.** History never leaves this box, and that is doing a lot of the
protecting for `training/corpus.jsonl`. Two sessions have died mid-work and a reboot destroyed a
finished write-up, so commit early — but if a remote is ever added, audit what is tracked first.

---

## 1. State of the machine, verified 2026-08-17 08:30

| Thing | State |
|---|---|
| `https://symoneural.com/` | 200, current markup, cache-busted assets |
| `/build.html`, `/ravencalc.html`, `/documentation.html`, `/account.html` | 200 |
| `POST /api/ravencalc` | exact SymPy, `check.passed: true` |
| `symoneural-api.service` | active, restarted 01:03, PID 170388 |
| Caddy | serving, TLS auto-renew |
| `tests/frontend.mjs` | **26/26 local, 26/26 production** |
| `https://symoneural.com/` | **302 -> /overview** |
| `https://www.symoneural.com/` | 200, its own Let's Encrypt cert (Caddy issues per name, so the apex cert's SAN list is apex-only — that is correct, not a fault) |
| Rack units | **12** — chat, image, remix, ravencalc, train, asicminer, gpuminer, tuner, coder, gateway, guide, project (read from `/api/status`, 2026-08-17) |
| Webroot orphans | 0 (35 pruned across two deploys) |
| Generators | **11**, all idempotent, hash-verified across two runs |
| `/overview` `/livestack` `/controlboard` `/receipts` | 200, each fitting one screen |
| Pending deploy | **two, both for the tuner Movies fix** — `sudo systemctl restart symoneural-api` (backend) and `sudo scripts/deploy.sh --prune` (page). See §2c-bis. |
| Backend suites | **679 passed, 1 failed** at `f9f3546` (14:40), excluding `reinforce/tests` and `remix/tests` — those two need venvs this interpreter does not have (`cupy`, `symoneural_dj`) and error at *collection*, which is not the same as failing. The one red is the tuner codec test, and it belongs to a live writer — see below. |
| Uncommitted | **16 paths at 14:43, and every one of them is the tuner session's live work** (`epg.py`, `sessions.py`, `tuner.html`, `tuner-watch.html`, `build_pages.py`, `build_masthead.py`, `api.py`, `frontend.mjs`, …). The ~100-path backlog is gone: `8e835cb`, `e38f463` and `f9f3546` landed it. **Still no git remote** — history never leaves this box. |

### Three red tests — two settled in `f9f3546`, one belongs to a live writer

All three were recorded here as possible *code* bugs needing an owner decision. Two were not:
in both cases the code was right and the test's premise was wrong, and in one of those the
"failure" was not even in the source. **Neither needs anything from Garrett. Both are green.**

1. **`test_alpha_is_twice_rank_everywhere`** — was `48 != 64` against a `presets.py` that plainly
   reads `lora_alpha=64`. **Not a hyper-parameter decision: stale bytecode.** The edit `48`→`64`
   changed no bytes and landed in the same clock second as the `.pyc` write, so Python's
   mtime-and-size validation passed and every interpreter on this box kept loading the old value.
   Deleting `backend/apps/reinforce/__pycache__/presets.cpython-313.pyc` fixed it; source and test
   were both correct throughout. **The 2× ratio holds across all four presets and always did.**
   Confirmed the wrong `48` never reached a surface: no match in `site/*.html` or
   `docs/symoneural-manual.md`, no generator reads `presets`, and the router is not mounted.
   `scripts/check-stale-pyc.py` now detects this class of failure — see §6.
2. **`test_despill_pulls_the_field_colour_out_of_the_edge`** — was `230 not less than 230`. Not an
   off-by-one in the threshold: `matte.CHOKE = 1` throws away the outermost ring of the subject
   before despill runs, so the test's pixels at x=4 and x=13 had become *background* and there was
   nothing there to despill. The despill works. The coordinates are now derived from `matte.CHOKE`
   rather than hard-coded, so the next change to the choke moves the test with the code, and the
   choked ring is asserted transparent rather than merely dim. `matte.py` was **not** modified.
3. **`TestCodecReporting::test_public_document_carries_the_codec`** (tuner) — went red mid-session
   when another session wrote `backend/apps/tuner/sessions.py` at 14:23. **That is their file and
   their in-flight work. Leave it alone.** It is the one failure in the 679-passed backend run.

Both fixes were verified the way §3.0 requires — by reintroducing the bug and watching the test go
red — and both temporarily-patched source files were restored (`git diff --stat` empty before the
commit). What made these expensive was believing a red test that contradicted the source in front
of me. **Run `python3 scripts/check-stale-pyc.py` before diagnosing the next one.**

### Five tasks still queued from the killed `fwcheck` work

`backend/apps/asicminer/fwcheck.py`, all read as real and none started: give honest
format-detection verdicts; the `fileinfo`/`md5_info` signed family currently fails as
"cert.pem missing" when that is not the problem; replace the invented 4-byte fixtures with a
64-byte slice of a real vendor header; report the 0x08 build timestamp.
| Podman container `symoneural-api` | **running but unreachable** — 8800/tcp is not published, and the image predates today's changes. It is inert, not a live server. It exists because the user wanted to learn CDI. Stop it or rebuild it; do not debug against it. |

## 2. Shipped 2026-08-17 (all of it is live)

Seven commits, `14f1599` through `677e25b`. In the order they happened:

1. **The order form moved to `/build.html`.** The front page was ending on a form instead
   of on the machine. Every "Have one built" route goes there, including the header CTA on
   every page.
2. **The receipts index is a card grid** — eight cards, each one claim plus what backs it.
   The PCIe negative result is amber rather than green because it is not a win; the API
   card carries a live dot because its destination is generated by the running service.
3. **`tools/build_cachebust.py`** stamps `?v=<content hash>` on every local CSS/JS link.
   The Caddyfile sets `max-age=604800`, which is right for immutable assets and wrong for a
   site under development: it served a week-old stylesheet against new markup and put
   nineteen full-size renders down the left of the live page in front of a visitor. **Run it
   last, after every other generator.**
4. **`calc` → `ravencalc` everywhere it is reachable** — route, page, rack unit id, WebSocket
   frame type, rate-limit bucket, CLI subcommand, docs. No compatibility alias.
5. **The Under Construction banner is gone**, all nine pages plus both generators.
   `@keyframes pulse` stays: four live indicators use it.
6. **Every render links to its full-size PNG** with a lightbox (`site/ui.js`). See §4 on
   why this is not cosmetic.
7. **Both header dropdowns are gone.** They painted underneath the hero, which was not a
   tuning problem: `.menu` was `z-index:60` inside a header that is itself a `z-index:20`
   stacking context, so 60 only ever competed with the header's own children. Both opened
   onto a single destination. They are plain links; the JS and CSS behind them are deleted.
8. **The front page was restructured so pitch, hero and rack fit one look.** See §3.
9. **`scripts/deploy.sh` got three fixes** — see §3.

### Bugs found while verifying, worth knowing about

- **`.band-art` had `pointer-events:none`.** Correct for the layer, which spanned the band
  and would otherwise swallow clicks on the CTA — but it also disabled every descendant, so
  the hover captions showing each render's prompt **had never once appeared** since they
  shipped. A feature that is written, styled and unreachable is invisible to any test that
  only checks markup. The test added for it asserts computed `pointer-events`.
- **The deploy's reference check would have failed on a correct deploy.** It tests `-f` on
  every `(src|href)="/…"`, and cache-busting made it look for a file literally named
  `symoneural.css?v=b56305bfed`. A verification step that fails on healthy input gets
  switched off, and then it protects nothing.
- **`js` listed before `json` in a `find -regex` alternation silently dropped every .json
  file.** `-regex` must match the whole path; `js` matched, `on` did not, and it never
  backed up to try the longer alternative. Order alternations longest-first.

## 2b. The watermark work — DEPLOYED 2026-08-17 03:12, verified live

Production is **18/18**. Verified beyond the suite: the render served from
`https://symoneural.com/art-fast.png?v=153f708e54` is byte-identical to the local file
(SHA-256 match) and measures **768×848**, i.e. the new 80px bar. The `?v=` value is the
file's own content hash, which is the cache-bust working as designed — `max-age=604800` is
still set on the PNG, but the URL now changes whenever the file does.

- **The watermark is two rows of 20px instead of one of 12px**, on all 18 `site/art-*.png`.
  Redrawn with `build_gallery.py --restamp` — no GPU, no governor lease, artwork unchanged.
- **Each gutter render prints its provenance as HTML text** (`.gprov`), because a burned-in
  strip cannot survive a 3.5× downscale at any size that leaves the picture intact.
- **`tools/build_cachebust.py` now stamps `.png`, `.svg` and `.woff2`, not just CSS and JS.**
  This one is load-bearing for the above: the Caddyfile puts `max-age=604800` on `*.png` and
  the renders keep their filenames, so without a stamp the user deploys, looks, sees the old
  four-pixel bar and reasonably concludes it did not work.
- **`build_sky.py`'s caption reads the sidecar** instead of a hardcoded `FLUX.1-schnell · 4
  steps`, so a caption can no longer disagree with the watermark on the image it captions.
- **`_art.dims()` reads the PNG header** rather than trusting `height="802"`, which the
  watermark change made wrong in two generators at once.
- **An 18th assertion**, `the watermark is readable as text without opening the render`. It
  was verified to fail: injecting `text-overflow:ellipsis` into `.gprov` turns it red.

## 2c. Second session, 2026-08-17 — three new surfaces, and the mining stack

All of this is **deployed and verified live** (21/21 against production at 05:35).

### The rack went from five units to eight

| Unit | Bus | State | Why |
|---|---|---|---|
| `asicminer` | `asic` | **offline** | No mining hardware attached. Operator-gated; see below. |
| `tuner` | `net` | **ready** | IPTV. Genuinely ready — it holds no content, the visitor brings the playlist. |
| `gateway` | `net` | **offline** | TRON/USDT licensing. Designed, not deployed: no contract, no wallet, no daemon. |

`Unit.bus` gained `asic` and `net`. **This exposed a live bug**: `console.js` rendered
`u.bus === 'cpu' ? 'CPU' : 'GPU'`, so an ASIC surface would have printed "GPU" — the wrong
hardware on the one plate the page asks you to trust. It is a lookup now, printing `--` for
anything unrecognised.

### Subsystems added

- **`backend/apps/asicminer/`** — the ASIC control panel. `probe.py` (pyasic telemetry),
  `scan.py` (discovery), `fwcheck.py` (firmware pre-flight). Off unless `SYM_ASIC_ENABLED=1`
  **and** `SYM_ASIC_TOKEN` are both set, so a misconfiguration fails closed on a public box.
- **`backend/apps/tuner/`** — IPTV over ffmpeg stream-copy to HLS. 57 tests.
- **`backend/apps/gateway/`** — TRON licensing surface.
- **`backend/apps/licensing/`** — the dev fee. 21 tests. See §2d.
- **`scripts/qemu-antminer.sh`** — boots real Antminer firmware under QEMU. See §2e.

### Three API routes, all operator-gated

```
GET  /api/asicminer/firmware    what firmware is actually on this machine
POST /api/asicminer/scan        discover rigs on a PRIVATE range only
POST /api/asicminer/emulator    start / stop / status
```

`X-Sym-Token`, constant-time compared, 503 when the surface is off. **The scanner refuses any
globally routable CIDR before sending a packet** — this box has a public IP, and a scanner
that takes an arbitrary range is one someone can aim at the internet from our address. The
check is on the parsed network, not the string. Prefixes wider than /20 are refused too.

The emulator starts **by package id, never by a caller-supplied path**.

### Bugs fixed, both found by audit rather than by anyone noticing

- **`.card` was defined twice** (`symoneural.css:118` and the receipts block). The later rule
  won every `.card` on the site — measured: eleven cards on `documentation.html` were
  rendering `display:flex` with the wrong padding and a gradient. The receipts block is now
  scoped to `.cards`. **This was the fourth instance of that bug class** after `.bar`,
  `.live` and `#console .sub`.
- **The lightbox asserted a burned-in watermark strip** that only `build_gallery.py` produces.
  It was *true* for every render it was bound to, so it was a trap rather than a falsehood —
  it becomes false the moment the lightbox is reused on the image page, which
  `docs/specs/image-spec.md` proposes. It now derives the claim from the file's own shape.
- **The tuner page posted to `/api/tuner/channels`**, which no router serves, so it fell
  through to the static mount and returned 405. The real routes are `/api/tuner/playlist` and
  `/api/tuner/xtream/channels`. Its `tn-` CSS had also never been written, so the form
  rendered as raw HTML.

## 2c-bis. The Tuner became a real player (last thing built, 2026-08-17 ~06:00)

**Not yet deployed at the time of writing — needs `sudo scripts/deploy.sh --prune`.**

- **Playback is `hls.js`**, vendored at `site/hls.js` (384 KB light build, Apache-2.0, licence
  at `site/hls-LICENSE.txt`). Chrome and Firefox will not play an `.m3u8` natively; Safari
  will, and the page uses the native path there.
- **VLC was rejected, and this is recorded so nobody retries it.** `references/IPTV/vlc-master/`
  is **GPLv2** and its only web path is `extras/package/wasm-emscripten` — an hours-long build
  producing a GPL WASM blob that would then be part of what we distribute in `site/`, making
  the site GPL-encumbered. See `LICENSES.md`.
- **Browsing is built from the playlist**: kind chips (Live TV / Movies / Series) and group
  chips, counted from the loaded channels, not a fixed list.
- **The model turns a question into a filter and never sees the playlist.** One call to the
  card, not one per channel.

### The lesson worth keeping from that last piece

Asking this 7B for a **JSON object** made it loop. Measured: it emitted
`{"match":["premier league","nfl","nba","mlb","f1","nfl","nba",…` until it hit the token cap,
so the object never closed, nothing parsed, and the fallback would have fired on **every**
request while the feature appeared to work. Asking for **one line of comma-separated
keywords** it answers cleanly every time.

**Pick the output format the model can finish.** A small model is far better at a flat list
than at nested structure, and a feature whose happy path never executes is worse than one
that is honestly absent — it looks fine until someone measures it.

### Prompt boxes

Chat, image, ravencalc and remix were 46px and one line. Now **80px and 16px**, with the chat
textarea's auto-grow cap raised 150 → 260 to match its new floor.

### The Movies section was empty on a real panel — fixed 2026-08-17, NOT YET DEPLOYED

Garrett reported it from the live site: Live TV and Series filled in, Movies never did.
Reproduced first try against his panel and it was not the classifier, not the frontend filter
and not the kind names — it was a **byte ceiling wearing the wrong hat**.

`Policy.max_bytes` is 24 MiB and its own comment says what it was sized for: "playlists; a big
provider M3U is a few MB". `load_channels` then handed that same policy to the Xtream catalogue
fetches, and a movie catalogue is not a playlist. Every film row a panel returns carries `plot`,
`cast`, `director` and `youtube_trailer` — metadata this module discards — so a title costs
~900 bytes on the wire where a channel costs a few hundred. **Measured on his panel: live 10,124
channels / 3.77 MB, series 7,883 shows / 6.43 MB, movies 31,888 titles / 27.57 MB.** Only the
third crossed 24 MiB. Two of three kinds fitting is precisely why this looked like a movies
bug rather than a size bug.

- Fix: `xtream.CATALOGUE_MAX_BYTES` (64 MiB), applied via `dataclasses.replace` to the catalogue
  fetches **only**, so every other field of the caller's policy — `allow_private` above all —
  is carried through unchanged. Raising `Policy.max_bytes` itself would have widened the same
  guard for playlist fetches and live stream sessions, which is how a guard stops guarding.
  Peak RSS to fetch and decode that 27.57 MB was 189 MB on a 96 GiB box; the ceiling stays a
  ceiling.
- The note was also **dishonest**, which is why nobody could act on it. Any failed non-live
  fetch appended "vod: unavailable on this panel", and the panel was not the problem — this box
  refused it. `safefetch.ResponseTooLarge` (a `FetchError` subclass, so nothing that caught the
  old class changes) and `xtream.XtreamTooLarge` now separate "your provider does not carry
  this" from "we declined to load it", and the note says which.
- **The M3U path had the same class of defect and still would have:** `parse_m3u` caps at
  `MAX_CHANNELS = 20000` and returns `truncated`; `routes.load_playlist`'s docstring says
  "`truncated` says plainly when it bit"; and `tools/build_pages.py` read that flag **nowhere**.
  An over-cap playlist lost its tail — usually the Movies block, the largest and last in most
  provider files — under the words "Loaded from your playlist." That is a silent cap, which is
  the `text-overflow:ellipsis` rule in another costume. The page now names the limit. The cap
  itself was **not** raised: the whole array is serialized to the browser, so 20k → 100k is a
  measurement, not a constant bump.
- `panel_info` deliberately keeps the narrow ceiling: the account document is **515 bytes**
  measured, so 24 MiB is four orders of magnitude of headroom. Two ceilings in one module is a
  trap unless each says which document it measures; both now do.
- The `except XtreamTooLarge` arm **must stay above** `except XtreamError` — it is a subclass, so
  the general arm would swallow it and quietly restore the note that blames the panel, with the
  note test still passing. There is a structural test asserting the order for exactly that
  reason.
- Verified in real Chrome against the real panel, served by a throwaway app carrying the tuner
  router and a static `site/` mount (not `api.py`, so the scope is the page JS and the route,
  not the production mount order): **49,895 channels, Movies 31,888 across 29 categories,
  4.5 s, no page errors, no h-overflow.** The response is 11.85 MB of JSON, **1.87 MB after
  gzip**, and `ops/Caddyfile:75` is `encode zstd gzip` with `content-encoding: gzip` confirmed
  live — worth knowing, because an 11.85 MB uncompressed body on a slow connection would come
  back as another "movies don't load" report indistinguishable from this one.
- Tests: tuner **121/121** (six new, against a fake panel — no credential is in any committed
  file), `tests/tuner_failpaths.mjs` 21/21 (six new; verified they go red with the fix removed),
  `tests/frontend.mjs` 26/26.
- **Needs `sudo systemctl restart symoneural-api` (backend) and `sudo scripts/deploy.sh --prune`
  (page).** Neither has been run; the live site still has the bug.

One thing that looks like a leak and is not: the response body contains the visitor's own
username and password, because Xtream puts them in the stream URL path and the browser needs
that URL to play anything. `xtream.py`'s docstring already calls this the one unavoidable
persistence, and it is why `Scrubber` exists for everything that is *not* the visitor.

### Still open on this surface

- Tuning a real stream end to end is still untested. Channel **listing** is now exercised
  against a live panel (see above); playback is not.
- **The full form path cannot be tested locally**: the SSRF guard correctly rejects loopback,
  so you cannot self-serve a playlist from this box to drive it. Test against a real playlist.
- hls.js is the **light** build: no subtitles, no alternate audio.
- Series episodes list without URLs; AES-encrypted HLS is refused rather than decrypted.

## 2c-ter. The GPU panel beside every prompt (last change, ~06:20)

**Not deployed at the time of writing.** On chat, image, ravencalc, remix and tuner.

**It adds no second data path, and that is the thing to preserve.** `console.js` connects
when it finds `#units` **or** `#m-vram` on a page (`console.js:266`) and then writes
`m-vram`, `m-pwr`, `m-temp`, `m-holder`, `m-queue`, `con-link`. Carrying those ids *is* the
whole integration — same websocket, same readings, same polling fallback. Its `txt()`/
`meter()` helpers no-op on absent ids, so the rack's own ids are unaffected. The stack in the
panel is `#units`, the same element console.js renders the rack into, restyled compact with
every rule scoped under `.gpu-panel`.

If you add another surface page, pass `gpu=True/False` and `surface="Name"` to `page()` in
`tools/build_pages.py` and the panel appears. `gpu=False` still shows the card — it is
shared and worth seeing — but says outright that the page does not wait for it, which is why
RavenCalc (CPU/SymPy) and Tuner (network) get that variant.

`.gbar`, not `.bar`. Redefining `.bar` collapsed the site header to 7px once; this is the
**fifth** time that bug class has had to be designed around in this stylesheet.

Verified against a real render rather than by eye: `holder` went `idle -> image` with
*SyMoNeuRaL Image* showing busy in the stack, and power differs between reads, which is what
rules out a cached value. The assertion checks **values, not markup** — renaming the panel's
ids leaves the layout intact, the socket live and the stack at eight units, and it still
fails on `vram="" temp=""`. A panel that renders and never receives data is precisely the
decorative gauge this site argues against, and it is indistinguishable from a working one in
a screenshot.

## 2f. Third session tail — type scale, chat rebuild, and two open design questions

### The type scale came down a step (global, affects every page)

Garrett put the site beside ESPN and claude.ai: our body was **16px** where ESPN runs 13–14
and Claude's sidebar is 13; h1 was 44.6px, h2 29. Everything was one step larger than the
sites it sits next to, which reads as zoomed in.

**Every type value was scaled by 0.88** — `font-size`, the `font:` shorthand, and the
`clamp()` heading values. Body is now 14.1px, h1 41.4, h2 25.5, nav 12.3. **Only values at
or above 13px were touched**: the 10.5/11.5px mono labels were already at the readability
limit and scaling them would have hit 9px. Verified after — smallest rendered text across
five pages is still 10–10.5px, because those rules were skipped rather than shrunk.

Side effect worth knowing: the rack moved from 759px to **713px** down the viewport, so the
"pitch, hero and rack fit one look" requirement is met with more room than before.

### The chat page was rebuilt (§5 item 7, done)

Rail + conversation history + document attach + multi-turn. `docs/specs/chat-spec.md` was
the input and both of its documented traps were real and avoided.

- **Conversations live in the browser.** No history endpoint, no conversation id on the
  server. The transcript is replayed to `/api/chat` each turn; the client caps at 19 to
  match the server's 20, so a long chat is trimmed client-side rather than refused.
- **`/api/chat` gained `history`** — a list of `{role, content}` turns. `role` is
  `Literal["user","assistant"]`, so a client **cannot inject a `system` turn** and override
  the trained persona and refusals. That is deliberate, not incidental.
- **Attach is text-only, and this is a hardware fact rather than a choice.**
  `Qwen2.5-7B-Instruct` has **no vision projector** — verified, there is no mmproj in
  `backend/models/`. It cannot see an image. An image picker would be a control that can
  never work. If image chat is ever wanted it needs a VLM downloaded, and chat and image
  weights already cannot co-reside in 15.92 GiB.

### THE ESCAPING BUG, which has now bitten twice

`TUNER_JS` and `CHAT_JS` are **normal triple-quoted Python strings, not raw**. A `\n`
written in the source becomes a REAL newline in the emitted JavaScript — inside a string
literal, which leaves it unterminated and kills the entire page's script. It shipped to
production once on `tuner.html`, and the suite passed 22/22 while the page was dead, because
every assertion checked markup, CSS and endpoints and none of those care whether the script
runs.

**If you add or edit inline JS in `tools/build_pages.py`, write `\\n`, not `\n`.** The
`no page throws a script error` assertion now loads all twelve pages and fails on any
`pageerror`; it caught the same bug in `CHAT_JS` before that one shipped.

## 2h. The guide, the watch page, and four bugs behind a black rectangle (2026-08-17 ~14:45)

Everything here is **on disk and unverified live** — see the BLOCKER in §0c. `backend/api.py`,
`backend/apps/tuner/**`, `tools/build_pages.py`, `site/tuner*.html`, `tests/tuner_*` and
`tests/frontend.mjs` were all edited; nothing else was touched.

### The guide is a grid now

`backend/apps/tuner/epg.py` (new, ~330 lines) reads the provider's own schedule two ways:
`get_short_epg` per channel through `POST /api/tuner/epg`, and the whole account's XMLTV
through `POST /api/tuner/epg/xmltv`. The module README section documents what it refuses to
do and why — the short version is that **a timestamp with no UTC offset is dropped and
counted, never guessed**, because a guide silently three hours wrong is worse than one that
says it has nothing.

The page has a Guide/List toggle. Guide draws time across and channels down, 30 rows and a
3-hour window, `←90 min / now / 90 min → / next 30 channels`. It asks only for the rows on
screen, caches an empty answer as empty so a channel with no schedule is not re-requested on
every redraw, and prints per row which of the three real answers applies: no guide for a
pasted playlist, nothing published for this part of the day, or no guide published for this
channel. **It never draws a "No Information" box** — a grid of those is the
decorative-indicator rule broken forty times a screen.

Measured against the real panel: catalogue of 10,072 live channels in 0.9 s, of which
**5,304 (52%) carry a `tvg_id`**; a grid of 24 named broadcasters answered **24/24 in
1,275 ms** with 23 carrying a programme on now.

### `/tuner-watch.html` — the stream on its own page

Garrett: *"You can make the stream move to its own symoneural.com/tuner/watch or something so
we can almost like full screen for improved guide pip settings etc etc."*

Video fills the window; a bar that dims after 3 s of no input carries the channel, the status
line, **now/next with the share elapsed**, and buttons for Guide, Statistics, PiP and full
screen. Keys: `g` `s` `f` `p`, `Esc` closes a panel. The guide and the statistics panel slide
over the picture; clicking a cell changes channel without leaving the page.

**It is `site/tuner-watch.html`, not `/tuner/watch`, and that is deployability rather than
preference.** `scripts/deploy.sh` publishes `find "$SRC" -maxdepth 1 -type f`, so a
`site/tuner/watch/index.html` is never copied into the webroot at all; and `ops/Caddyfile`
delegates an explicit list of top-level paths, so a new one 404s until
`sudo ./scripts/install-caddy.sh` runs. **To get the pretty path later:** add `/tuner/watch`
to the `@sections` matcher in `ops/Caddyfile` and a route in `backend/api.py` that serves this
file. The page itself needs no change.

**The handoff carries the live session id and the watch page ADOPTS it.** Nothing goes in the
URL — a stream URL carries the visitor's own provider credentials and uvicorn logs a request
line — so the channel travels in `localStorage` under `symoneural.tuner.watch`. Verified in
real Chrome against the real panel: session `apXoyVZ65L9G4MdN` before the click, the same id
after, `1/2` slots throughout. The alternative was releasing a working stream and asking the
provider for it again, which costs a fresh upstream connect and several seconds of black
screen for nothing.

### FOUR BUGS, and three of them were invisible

**1. `play()` tested `canPlayType` first, and Chrome answers `'maybe'` — a truthy string.**
So every Chrome visitor took the native-HLS branch and **the entire hls.js block was dead
code**: no `liveSyncDurationCount: 1` (so 31 s to first frame instead of 2.5 s, the very fix
§1 celebrates), no fatal-error handler that asks the box what actually happened, no level or
throughput readings. The statistics panel reading *"the browser's own HLS"* with bitrate at
`-` is what exposed it. hls.js is now tried first and the native path is the fallback for
Safari, where `Hls.isSupported()` is correctly false. Confirmed live: `hls.js 1.7.0`, 2
levels, 286 Mb/s.

**2. The audio codec was parsed and never published.** `Session.public()` now carries
`acodec`. A channel of Garrett's reported `state: live`, `vcodec: h264`, 87 MB pulled over
five minutes and every indicator green while Chrome decoded **zero frames** — MSE refuses the
whole segment when it will not take the AUDIO track, and Chrome takes no AC-3. The picture
stops for a soundtrack. This is very likely the bulk of *"most the issues are with the adult
live tv"*.

**3. The codec panel was being overwritten by the symptom it causes.** An undecodable stream
raises a fatal hls.js error moments later, and *"Playback stopped — the player could not fetch
the next part"* replaced *"This stream is H.265 / HEVC"*. Cause swapped for symptom, which is
precisely what that panel exists to prevent. The codec diagnosis is now sticky until the next
tune. **It was unreachable until bug 1 was fixed**, because the native path never raised the
error.

**4. `currentLevel` is `-1` while the level is chosen automatically**, which is the default,
so the level bitrate printed `-` beside a live throughput reading of 286 Mb/s. Falls back to
`loadLevel` and marks it `(auto)`.

**Codec support is ASKED OF THE BROWSER, not tabulated.** Both pages call
`MediaSource.isTypeSupported()` against `video/mp2t` (what the box serves) and fMP4 (what
hls.js remuxes to) and warn only when neither is accepted. Measured on Chrome 151: h264, aac,
mp2 and mp3 accepted; hevc, mpeg2video, vc1, av1, vp9, ac3, eac3, dts and truehd refused. A
hard-coded list would have been **wrong about mp2 in the same week it was written** — mp2 was
on the suspect list and is fine.

### Tuner and Guide are one rack unit

Garrett: *"symon guide and symon tuner should be migrated together"*, then *"you need to
migrate tuner and guide to be 1"*. Two units carried the same `href`, so the rack was showing
one page twice. `apps/tuner/routes.py::status()` now returns *SyMoNeuRaL Tuner & Guide* and
`backend/api.py` no longer builds a `guide` unit — **the rack is 11 units, not 12.**

Nothing was deleted: `backend/apps/guide/` is untouched and `/api/guide/*` still serves the
page's filter. The prefix was deliberately **not** renamed to `/api/tuner/guide/*` — the page
JS consumes it, and churning a working route serves no reading. The guide half's claim
(*CPU/stdlib, never takes the GPU lock*) is carried in the tuner unit's detail line in every
state, because that is the thing a visitor cannot check by looking.

The reversal is the interesting part and is recorded at the deletion site: Guide's own author
argued for exactly this fold on architecture and was overruled only because Garrett had named
it separately. He has now decided the other way.

### Tests

| Suite | Before | After |
|---|---|---|
| `tests/frontend.mjs` | 26/26 | **28/28** (against a throwaway API with the merge loaded) |
| `tests/tuner_failpaths.mjs` | 23/23 | **27/27** |
| `apps.tuner.test_epg` + `test_tuner` | — | **159/159** |

New assertions, each guarding a bug above: an undecodable **audio** codec is named on a video
codec that is fine; the panel says the sound is why the picture is black; the technical line
reports both codecs; **and a working h264+AAC stream is never called undecodable** — a warning
that fires on a stream that plays teaches the visitor to ignore the one that does not.

On the rack, the assertion is *"no two rack units are the same page on the same bus"* rather
than a unit count. `units.length === 11` would go red every time a real surface is added,
which is the kind of assertion people delete instead of reading. Page alone is not the
invariant either: the two **Miner** units are ASIC and GPU — different hardware, one page —
and Coder and Project both link `/documentation.html` because neither has a page yet.

**`tests/frontend.mjs` scores 27/28 against the running service on :8800, and that is the
pending restart, not a regression.** That process predates the merge and still reports 12
units. Against a throwaway `uvicorn api:app` with the change loaded it is 28/28.

### Still open on this surface

- **The Guide AI's "ask a couple questions" element is not built.** The floating prompt exists
  and is wired to `/api/guide/filter`; what is missing is the short location/preference
  questionnaire Garrett described. Note his constraint carefully: *location-aware means
  **asking**, not geolocating* — do not add IP geolocation to a box whose whole argument is
  that it measures rather than infers.
- **Transcode.** Garrett approved full GPU transcode, but a peer session then measured the
  numbers and they change the answer: `-c:v copy -c:a aac` runs at **34x realtime with +0 MiB
  VRAM on the CPU**, while `hevc_cuvid -> h264_nvenc` costs ~515 MiB and is only needed when
  the *picture* is undecodable. The honest design is two-tier — repair the audio for free,
  reserve the GPU path for the case that needs it. NVENC/NVDEC are dedicated blocks and do not
  contend with inference compute (measured: GPU compute 2%, encoder 50%, decoder 28% during a
  transcode), so the governor may be the wrong instrument entirely; a VRAM budget fits the
  hardware better than the mutex. **That work is owned by the `online applications testing`
  session, not this one.** Whoever builds it must rewrite `_spawn`'s comment *"it never quietly
  re-encodes, because the GPU belongs to inference"* rather than quietly contradicting it, and
  the page copy along with it — *"uses the video engine, not the compute the models share"* is
  both true and the better line.
- 165 empty `/tmp/tuner-run-*` directories: contents are cleaned on reap, the directory itself
  is not. Harmless today, unbounded over time.

### A review pass after the above, and three things it caught (~19:10)

The work above was already committed in `4b23f85` when a review found three gaps. All three are
now fixed and each was confirmed by *breaking it again and watching the check go red* — a fix
whose test passes both with and without it is not a test.

1. **The biggest bug had no assertion.** `canPlayType` returning `'maybe'` made the whole hls.js
   block dead code, and nothing in the suite would have caught a revert. The discriminator was
   already on screen: the statistics panel's `#ps-eng` reads *"the browser's own HLS"* when
   broken and *"hls.js 1.7.0"* when not. One line in `tuner_failpaths.mjs` (now 28), and the
   control confirms it: restoring the old branch order takes the suite to 27/28 with exactly
   that assertion failing and every other one still green — which is the whole point, because
   a page that hands the stream to the wrong player still renders its lists, notes and failure
   panels perfectly.
2. **`site/tuner-watch.html` had no committed coverage at all** — 61 KB and ~700 lines of inline
   JS, guarded by nothing after the throwaway script that drove it was gone. It is now in
   `frontend.mjs`'s `pageerror` loop (13 pages, not 12), which exercises the **cold** path — no
   handoff in localStorage, the branch a visitor who types the URL gets. `node --check` would
   not have covered this; it catches parse errors, not the runtime throw.
3. **A comment claimed something the code did not do.** `tune()` called `remember(c)` *before*
   the fetch resolved, when `sid` is still `null`, and nothing rewrote it on success — only
   `adopt()` did. So after any channel change made on the watch page, the stored record read
   `sid: ""`, and a reload cold-tuned instead of adopting: one slot of a two-slot box held on a
   stream nobody was watching until the reaper got to it, with the new tune refusable meanwhile.
   Fixed with a second `remember(c)` after `sid = j.id`, keeping the early call, which is
   deliberate — it is what lets a reload *during* a tune still know what to open. Measured
   against the scripted provider: the record now carries `sid: "S1"`, and with the second call
   removed it is `sid: ""` again.

### Writing the assertion found a fifth bug, in the readout that finds the others (~19:40)

`tests/tuner_watch.mjs` is new: the watch page carries its **own** copy of `play()`, its own
statistics panel and its own `#ps-eng`, deliberately duplicated from `TUNER_JS` — so duplicated
code needs duplicated assertions or the identical bug can be reintroduced on the copy with
every existing test still green. 8 assertions, self-contained against the scripted provider.

It went 6/8 on the first run, and the second failure was real. **`#ps-eng` inferred the player
from `hls` being non-null, so it lied in exactly the situation it exists to be read in.** On the
watch page `statsStart()` is called at the *top* of `play()`, before the engine is chosen, and
its first tick is synchronous — so a channel that dies inside a second (a dead channel, which is
common) had `stopTimers()` clear the interval before any later tick, and the panel sat there
reporting *"the browser's own HLS"* for a stream hls.js had in fact been handed. The same
inference on `tuner.html` flips the readout the moment the instance is destroyed. Either way the
one line that says which player is running is wrong precisely when the picture is black — which
is how the original `canPlayType` bug stayed hidden for as long as it did.

Both pages now record `engine` at the moment of the choice and print that, with `'-'` before a
choice has been made. Removing the record takes the new suite to 7/8 with that assertion red.

The other over-strict assertion is worth remembering as a pattern: the first version asserted
the page reads *"live"*, and it got *"stopped"* — which is **true**, because the fixture serves
a manifest and no segment data. Asserting it away would have been asserting that the page lies.
It now asserts the page reaches a *definite* state and never sits on `opening…`, which is the
real invariant. That is the second time this fixture has caught an assertion for being stricter
than the truth; the first was the AAC control in `tuner_failpaths.mjs`.

**And a build-order trap that nearly shipped, now written into `.claude/CLAUDE.md`.** Running
`build_pages.py` **strips every `?v=` cache-bust stamp off the pages it writes**, because the
generators emit plain hrefs and `tools/build_cachebust.py` stamps them afterwards. Seven pages
came up modified in `git status` and the diff read like a harmless hash refresh; it was the
opposite — committing there would have shipped HTML whose CSS and JS are cacheable for a week
with no way to invalidate them, which is the exact failure that made the stamper exist. The
tell is a page you never touched showing as modified. **Regenerate, then stamp, then re-read
`git status`.**

It had already bitten somebody else: `site/project.html` was committed with **no stamps at all**,
and running the stamper here put all ten back. Check your own surface page for `?v=` before you
call it done — `grep -c '?v=' site/<page>.html` should be non-zero. And note **`deploy.sh` does
not stamp** — it only strips `?v=` when checking that references resolve, so a destamped page
deploys silently. `python3 tools/build_cachebust.py` has to run before `sudo scripts/deploy.sh`,
not as part of it.

## 2g. Two open design questions Garrett raised (NOT decided, NOT built)

**1. A no-scroll front page.** His words: *"i really like the no scroll sites maybe we could
do that but links/tabs would have to be perfect."* Worth taking seriously — the front page is
already close, with the rack at 713/1000 after the type change. Considerations before anyone
builds it: the site's argument rests on showing measured detail, so no-scroll means folding
most of it behind tabs (legitimate — §4 allows folding, forbids *dropping*); it is much
harder at 390px, and most real no-scroll sites still scroll on mobile; and it tends to break
at 200% browser zoom, which is an accessibility regression. `site/ui.js` already implements
`.tab[role="tab"]` with proper roles, so the tab machinery exists. **Recommend: no-scroll on
desktop, scroll on mobile.**

**2. A site-development agent, access-controlled.** His words: *"i want to be able to somehow
integrate site development agent but we have to be careful to only give me that maybe by the
seat — only thing with seat is i use xrdp also for this."*

The security shape matters more than the licensing shape. **An agent that can develop the
site is arbitrary code execution on the box that serves the public internet.** It must never
be reachable from a visitor-facing route, and "behind a password" is not sufficient on its
own for that capability.

His xrdp habit is actually the *safest* answer rather than a complication: an agent that runs
inside his desktop session is local-only and never exposed on `:8800` or through Caddy at
all — no route, no token to leak, no rate limit to get wrong. Per-seat licensing is a
separate question from access control and should not be conflated with it; the `licensing/`
module already issues signed contract keys and could gate a seat, but that gates *use*, not
*reach*.

## 2d. The dev fee — `backend/apps/licensing/`

Garrett set the standard rate at **2.5% (250 bps)**, matching Braiins' headline. Modelled on
the shape in `bos-plus-api`'s `license.proto`; none of their code is used.

**`STANDARD_FEE_BPS` lives in `issue.py`, the minting tool, and NOT in `__init__.py`, the half
that runs on a rig.** The verifier carries no rate at all: a machine reads its fee from a
signed contract or has no fee. A default in the verifier would be a number a tampered or
missing contract could silently fall back to. A test walks the AST to enforce this.

Contract keys are `SYMN1.<b64url payload>.<b64url ed25519 sig>`, verified **offline** by
`openssl` exec — so a rig with no route to us still knows if its licence is valid, and we
learn nothing about when or where a customer runs.

> **THE PRIVATE SIGNING KEY WAS IN `/tmp` AND IS GONE AFTER THE 2026-08-17 REBOOT.** The
> public half is committed at `backend/apps/licensing/contract-signing.pub`. **No contracts
> were ever issued to anyone**, so this is harmless — regenerate and replace the public half:
> ```bash
> python3 backend/apps/licensing/issue.py keygen --out ~/symoneural-signing
> cp ~/symoneural-signing.pub backend/apps/licensing/contract-signing.pub
> ```
> Keep the `.key` off every rig and out of git. `*.key` is gitignored; `issue.py` chmods 0600.

**It does not collect.** No hashrate diversion, no pool substitution. Collection belongs in a
mining engine and this box has none; `disclosure()` says so in every state. Two facts checked
rather than assumed: Braiins is **2–2.5% depending on hardware model**, not a flat 2.5%; and
**stock Bitmain firmware has no dev fee at all** — `bmminer` extracted from the S17 Pro rootfs
has no hardcoded pool and no devfee strings. The comparison is against Braiins, not Bitmain.

## 2e. Firmware and the QEMU emulator

Full detail in `docs/antminer-firmware-upgrade.md`,
`docs/custom-antminer-firmware-options.md` and
`docs/symoneural-miner-firmware-strategy.md`. The short version:

**Antminer packages open.** A plain signed tarball. `runme.sh` is a signature gate (exits 1–5)
wrapping an inner one that does a version gate (exit 7 blocks downgrades) then `flash_erase` +
`nandwrite` with no rollback. **Three gates run in `upgrade.cgi` before `runme.sh` is even
reached**: symlinks rejected, `runme.sh.sig` verified against `/etc/bitmain-pub.pem` *by the
CGI*, and `md5sum runme.sh` checked against `/etc/blacklist` (27 entries — a revocation list).

**`scripts/qemu-antminer.sh` boots S17 Pro, S17+ and T17 to a shell.** Four things it knows:
`ramdisk_size=131072` (the default 4 MB buffer silently truncates a 100 MB rootfs into a fake
"corrupt firmware" symptom), a devicetree must be supplied, `-nic` not `-device cadence_gem`,
and pflash is exactly 64 MB. **QEMU does not emulate the hashboards**, so lighttpd and
`upgrade.cgi` run and `bmminer` does not — good for the flash path, useless for telemetry.

**MicroBT firmware is encrypted and cannot be emulated.** `Whatsminer-all-20260416.14` (41 MB)
has a readable header — magic `0xae640a3f`, control board `h616` as ASCII — and a payload at
**7.999 bits/byte of entropy** across all 41 MB. You cannot extract a kernel from ciphertext.
Independently: `h616` is Allwinner and `qemu-system-arm` has machines only for H3, A10, R40.
`fwcheck.py` validates the container header, size consistency and declared board.

**The Braiins decision, already made:** do **not** fork their firmware. Everything that drives
an Antminer hashboard is GPLv3, so a fork must ship GPLv3 with source. `bos-plus-api` is a
public gRPC surface covering auth, telemetry, cooling, performance tuning, pools and upgrade —
so SyMoNeuRaL Miner is a proprietary control plane over it, which is a separate program and
carries no GPL obligation. `backend/apps/asicminer/` already is that.

## 3. What changed structurally (do not re-learn this the hard way)

### 3.0 The front page layout, and why it is shaped like that

The requirement, in the user's words: *"I am trying to get where you can see those two
things plus the agent stack at 100% browser first look."* The page could not do it — a
hero, then a 930px band restating the argument, then the rack (the machine reading its own
sensors while you watch, which is the entire point of the page) beginning ~1,300px down.
Three full-width sections stacked, and no trimming inside them adds up to a screen.

The fix was to stop stacking:

- **`tools/build_masthead.py`** owns the top of `site/index.html`. Four grid columns:
  `[render | pitch | hero | render]`. The `h1` is on the right where the eye lands after
  the nav; the pitch is on the left, quieter — serif, one shade down, a ghost button, so
  two solid CTAs do not read as two competing offers. The `h1` is **first in the document**
  and placed by `grid-area`, rather than writing an `h2` above the page's own `h1` to get
  the visual order.
- **The four renders live in the gutters.** At 1900px the readable centre column is 1120px
  and the ~390px either side of it were empty at every width above 1280. Two flank the
  masthead, two flank the rack (`tools/build_rack.py` emits those). They cost **zero**
  vertical space instead of a full screen. Measured at 1906×950: rack top at 744px.
- **They are capped at 268px, and 206px once they stack.** "They are gigantic" was a grid
  column doing what grid columns do: below the breakpoint each render took a full `1fr`,
  measuring 520px at an 1100px viewport — larger than they had ever been in the gutter they
  were sized for. If you add a render anywhere, cap it.
- **`tools/_art.py`** holds the markup all three placements share. The masthead, the rack
  and the constellation each had their own copy of the prompt/seed/seconds lookup, and one
  had already drifted.
- **The constellation moved to `/build.html`** (`tools/build_sky.py`), in its own `.sky`
  namespace. It is a good object and the user likes it; it just cannot live beside a
  readable centre column, because below 1280px the absolutely-positioned renders collapsed
  into a vertical stack down the left edge — which is what a visitor actually saw.
  **`.band` no longer exists. `.sky` shares nothing with the masthead but the word "art".**
  That namespace separation is deliberate: `.bar`, `.live` and `.sub` have each been
  redefined twice in `site/symoneural.css` and every time the second definition silently
  ate the first.

**`tools/build_band.py` is deleted.** If you find a reference to it, it is stale.

#### The one-screen layout on top of all that — `tools/build_tabs.py`, the tenth generator

Garrett asked for a no-scroll front page. The page is 3,358px at 1440×900 and 9,161px at
390px, so trimming was never on the table; `.claude/CLAUDE.md` says fold, so it folds into
four tabs: **Overview (the masthead), Live stack, Control board, Receipts.**

**Read this before touching the gate.** The first version shipped broken and the test suite
passed anyway, which is the more useful half of the story:

- The gate was `min-width:1100px`. `.mh` restacks at `max-width:1300px` from one row into
  two, which takes the masthead from 414px tall at 1440 to **727px at 1280**. So the gate
  opened *inside* the reflow band, and every window from ~1100 to ~1300 turned the
  no-scroll layout on at the exact width the masthead was tallest. The rack panel came out
  **48px tall with 1,289px in it**. The gate now opens at **1301px, above the stacking
  point**. Those two numbers in two different files are now load-bearing on each other and
  both say so — this is `.claude/CLAUDE.md`'s "two copies of a breakpoint drift" with the
  copies in different languages.
- The masthead is now the **first panel**, not chrome above the panels. That is what took
  panels from 330px to 522–744px at 1440×900. Hiding the pitch column instead would have
  been a *drop*; making it a panel is a fold, and it is still the default tab, so it is
  still what a visitor lands on.

**What it does NOT claim.** The chrome is one screen — header 67 + strip 44 + footer 45 =
156px, and the panel gets the rest. **Panels still scroll internally**, and no amount of
work closes that: the rack is ~1,009px of content (heading 134, rackrow 762, footnote 38 —
there is no padding to reclaim) against 744px of panel at 1440×900. Removing that scroll
means folding the rack's own cards into `<details>`, which is a redesign of the flagship
section and nobody has asked for it. **Do not tell Garrett the panels do not scroll.** He
has raised the scrollbar twice and the second time it was because a previous agent — me —
reported "one screen" from a test that measured the document instead of the panel.

The assertion is now `the front page folds into a panel big enough to read`. It measures
the **active panel's height as a share of the viewport** (floor 45%) at the gate
boundaries — 1301×740 one pixel in, 1300×900 one pixel out, 1280×800 the case that shipped
broken. The old assertion checked "the document does not scroll" and "no section was
dropped", both of which were true of a page rendering the rack into a 48px slit.

Two smaller things that live here: below the gate the tabs hide nothing, so they are
**jump navigation** rather than a highlight that changes nothing; and `.masthead::before`
is a 640px gradient at `top:-40%` that overflows any hero shorter than 457px, which was
harmless under `overflow:hidden` and becomes a real scrollbar on a decorative gradient
under the panel's `overflow-y:auto`. The `min-height:740px` floor clears it by 127px.
**Lower that floor below ~615px and the hero starts scrolling on a gradient.**

Anything in the test suite that asserts on the rack or control board must now `openTab()`
first — a hidden element has no box, which is exactly how `pitch, hero and rack fit one
look` went vacuous (it required `rack.top < innerHeight`; a hidden element reports 0).

#### `tools/build_split.py` — one page per section (eleventh generator)

`/overview`, `/livestack`, `/controlboard`, `/receipts`. Each page is `index.html` **with
the other sections deleted** — subtraction, not reassembly, so head/header/footer/scripts
and every cache-bust stamp match the front page by construction. **`index.html` is not
modified**: the other generators find their work by BEGIN/END markers, and moving a section
out from under them makes the next run append a second copy.

Routes are in `backend/api.py`, declared **before** the `StaticFiles` mount — a route added
after a mount at `/` is unreachable. `ops/Caddyfile` is untouched and stays that way.

**These fix the gate cliff, not the scrolling.** A page holding one section has exactly the
same vertical budget as a panel holding one. What removed the scrolling was folding plus
density (below). Do not describe the split as the thing that made it fit.

Watch the section-removal pattern: `build_console.py` emits
`<section id="console" style="padding-top:34px">`, so a regex expecting `id="console">`
silently removed nothing and welded a control board onto all four pages. The removal is
asserted (`n == 1`) rather than trusted.

#### What actually made the sections fit

In order, and only the second hides anything:

1. **Geometry.** A unit's name and attribution were stacked; side by side they are one line.
   Nothing hidden — deliberately, because that line carries `built on Qwen2.5-7B-Instruct`,
   an Apache-2.0 condition, and geometry buying the space keeps the licence obligation out
   from behind a click.
2. **Folding.** Per-unit detail and per-module explanations collapse behind real
   `<button aria-pressed>` controls, remembered in `localStorage`, **shown only inside the
   one-screen layout** — on a scrolling page there is nothing to save and hiding would be
   pure loss. The text stays intact in the DOM. The control board's provenance tag
   (measured / vendor / projected) never folds.
3. **Density.** Spacing only. The rack's height floor turned out to be **the 27px power
   glyph plus padding, not its text** — which is why an earlier padding-only trim moved
   nothing at all.

The fold handlers bind to `#rack` / `#console`, never to `#units`: `renderRack()` rewrites
`#units` on every status push, so a class toggled on a descendant is undone by the next
update.

Measured, content against panel:

| Viewport | Result |
|---|---|
| 1920×1080 | all four fit |
| 1855×745 (Garrett's window) | **all four fit**, as tabs and as pages |
| 1440×900 | all four fit |
| 1301×740 | three fit; Live stack over by 76px |
| 390×844 | nothing fits and nothing can — the rack alone is 2,700px |

**Mobile cannot reach zero scroll and should not be promised it.** The gate is off below
1301px, so phones get the ordinary scrolling page with every section visible.

Two changes that look like wins and are not, both left in the CSS with their numbers:
a two-column rack (units 76px → 178px → 403px, because a unit row is a *horizontal*
layout) and gridding the heading `.wrap` (control board 1,043px → 3,553px, because
`#console` keeps its whole contents in one `.wrap`).

**`html.ns #hero:not([hidden])` — do not simplify that selector.** `hidden` works by
applying `display:none` from the *browser's* stylesheet, so any author rule that sets
`display` beats it. Written bare, the rule meant the masthead could never hide: every tab
rendered the hero above it and the page had two scrollbars. It reached production. The
other three panels were fine only because nothing sets `display` on them.

**The recurring failure in this layout is testing a proxy instead of the render.** Three
times now: the document's scroll height instead of the panel's; `rack.top` on an element
that was hidden; and `element.hidden`, the *attribute*, on an element the browser was
painting. The suite now reads `getComputedStyle(...).display` and asserts that while any
panel is open no other panel occupies vertical space. If you add a layout assertion here,
**verify it fails when you reintroduce the bug** — that check is cheap and has caught a
vacuous assertion every time it has been run.

### 3.0c Routing: Caddy decides BEFORE FastAPI ever sees the request

`.claude/CLAUDE.md` says "FastAPI does all the routing." That is true of what a URL
*returns*, and false about which URLs reach the API at all. `ops/Caddyfile` serves
everything from disk except the paths it explicitly delegates:

    /api/*   /docs*   /openapi.json   /   /overview   /livestack   /controlboard   /receipts

**Anything not on that list never reaches FastAPI.** The section pages shipped 404ing for
exactly this reason: the routes existed in `backend/api.py`, `127.0.0.1:8800/overview`
returned 200, and Caddy answered the public request from the webroot without asking. `/` is
on the list only so the redirect route can run; `path /` is an exact match and does not
affect anything else.

Adding a fifth section means touching **four** places: `tools/build_split.py`,
`backend/api.py`, `ops/Caddyfile`, and `is_route()` in `scripts/deploy.sh` (which otherwise
reports `MISSING livestack`, because pages link `/livestack` while the file is
`livestack.html` — only the extensionless form is exempted, so a genuinely missing
`livestack.html` is still caught).

**A local test run cannot catch a mistake in that list.** Against `127.0.0.1:8800` the API
answers directly and the Caddyfile is not exercised at all. `tests/frontend.mjs` passed
25/25 locally while all four URLs were dead in production. Run it against
`https://symoneural.com` after any routing change, and note that
`scripts/install-caddy.sh` now checks all four plus the redirect.

### 3.0b `scripts/deploy.sh` — three fixes, all worth understanding

1. **It publishes web assets only.** It used to `find -maxdepth 1 -type f` and install
   everything, and what was sitting in `site/` was an 11.6 MB browser "Save page as"
   capture plus its PDF print. `site/` is a working directory; the webroot is not.
   `.json` is deliberately excluded — `/openapi.json` is proxied to FastAPI and a static
   copy would be shadowed and go stale, and the twenty `art-*.json` are build-time metadata
   nothing fetches.
2. **An orphan is "a file this deploy would not publish"**, not "a file absent from
   `site/`". Those differ now, and under the old test every already-published copy of an
   excluded file stayed in the webroot forever, never updated and never removed.
3. **Prune runs before the reference check.** The check tests the webroot, so a page
   referencing a file that lived only there was reported `ok` and then deleted by the prune
   in the same run — passing on a state that no longer existed when the script exited.


### 3.0d Five verification steps have failed on healthy input. Read this before writing one.

In two days, all five of these printed FAILED or MISSING while the system was correct:

1. `deploy.sh`'s reference counter, incremented inside a piped `while read` — a subshell,
   so the count was discarded and the script exited 0 while printing MISSING lines.
2. `deploy.sh`'s reference check calling `/overview` and friends MISSING — they are routes,
   correctly not files.
3. `install-caddy.sh` asserting 200 on `http://` — Caddy's automatic HTTP→HTTPS redirect
   returns 308, and the check did not follow redirects, so it could never have gone green.
4. The same script asserting 200 on `https://symoneural.com/` after `/` became a 302.
5. Its preflight reporting `api DOWN` immediately after a successful
   `systemctl restart symoneural-api` — systemd returns before uvicorn binds the port. That
   branch offers a five-second abort, so it invited the operator to cancel a healthy
   deploy. It retries for ten seconds now.

Every one encoded an assumption about the deployment that later stopped being true, and
every one shouted. The damage is cumulative: a check that cries wolf trains the reader to
skip the whole block, and then the real failure goes through.

**If you touch a verification step, run it against the real system and confirm it passes on
known-good input — not only that it fails on known-bad.** Both halves, every time.

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

> **Updated 2026-08-17 05:35, end of the second session.** Items 3, 4 and 5 are now
> substantially built — see §2c, §2d and §2e. What follows is what is genuinely left.

### Open findings nobody has acted on

These were each found by audit and verified, and none is fixed. They are listed first
because they are the cheapest real work available.

0. **The contract signing key's private half is gone, and the committed public half is an
   orphan.** `backend/apps/licensing/contract-signing.pub` is tracked; the matching private
   key lived in `/tmp` and did not survive. Checked, so nobody re-checks: `/tmp/t.key` is a
   *different* test key and does not match. Right now the repo can verify contracts that
   nobody can sign. **Harmless — no contracts have ever been issued** — and it stays
   harmless only until someone tries to issue one. Regenerating creates the company's
   signing key, so it is Garrett's call, not an agent's:

   ```bash
   python3 backend/apps/licensing/issue.py keygen --out ~/symoneural-signing
   ```

   Not `/tmp` this time. That is what lost it.

0b. **The tabbed `index.html` is no longer linked from anywhere.** `/` redirects to
   `/overview`, so the one-screen tabbed page is reachable only by typing `/index.html`. It
   is not dead code — `tools/build_split.py` reads it to produce the other four pages, and
   `tools/build_tabs.py` still maintains it — but it is now a build artifact that also
   happens to be a working page, which is an odd thing to keep maintaining. **Decide with
   Garrett:** keep it as-is, or retire `build_tabs.py` and let `build_split.py` read an
   untabbed `index.html`. Do not quietly delete it; four assertions still address it.

   (Live stack's overflow below 1366px, which used to be item 0b, is **fixed** — see §3.0.
   The cause was the chassis strip wrapping to two lines, not the units.)

1. **The SyMoN_ML DRM fails open, and that is the most serious item here.**
   `auth_daemon.py` in the blueprint calls `_check_local_sandbox_state()` as a *fallback*
   when the TRON lookup does not match, and that function is `return True` unconditionally.
   So **blocking `api.trongrid.io` grants a licence** — `iptables -j DROP` defeats the entire
   IP moat. It is why the auth daemon was NOT built. A licence check that fails open is worse
   than none, because the surface around it claims the weights are protected. Needs a
   fail-closed redesign *and* a real answer to key exchange (a blockchain is public; the key
   cannot live there). Full write-up: `docs/specs/symon-ml-review.md`.
2. **The Akash figure has an unstated assumption.** $1.68/hr x 8 GPUs x 24 x 30 = $9,677 at
   100% utilisation; the pitch's $5,800/mo implies ~60%. That is a reasonable number and the
   document never says so, which is the first thing a sceptical reader attacks.
3. **The blueprint installs the wrong torch.** Part 2 says `--index-url .../cu121`. Blackwell
   `sm_120` needs **cu128**. Following it verbatim installs a torch that cannot run here.
4. **CUDA engine findings** — `docs/specs/cuda-audit.md`. Chiefly `context.py:149`, the only
   `_attr` call without an explicit default (so a name mismatch silently yields zero SMs), and
   several honest-labelling allegations that **should be reproduced before anyone edits on
   their say-so** because they touch the argument the site rests on.
5. **Four hover captions on `/build.html`** hang 13–71px off the left edge at 1440px.
   Pre-existing, measured identically on production. Hover-only, clips nothing.

### Queued work

6. **Image page restyle** — `docs/specs/image-spec.md`, 527 lines, ready to implement.
   Includes a measured diagnosis (the composer sits at y=760 desktop / y=1712 on a phone
   because `.stage` never scrolls) and a verified list of free class names.
7. **Chat page restyle** — `docs/specs/chat-spec.md`, 501 lines. Reference measured at three
   widths. Two traps documented: a `<nav>` rail would hit `nav a:not(.cta){display:none}` and
   vanish on phones, and deleting `#stat` makes a *successful* generation render as an error.
8. **SyMoNeuRaL Miner GPU (Ravencoin)** — `backend/apps/cryptominer/`, now built, tested and
   documented: `backend/apps/cryptominer/README.md`, 72 tests, none of which touch the GPU or
   start a miner. Still a **separate surface from the ASIC panel** — no shared code, route
   prefix, rack unit or token. Do not conflate them.
   The remaining governor work is narrower than this item used to imply, and the obvious
   reading of it is wrong: `gpu-governor.sh` *has* a working `miner)` eviction arm, but
   eviction is reached only after `cmd_acquire`'s `mkdir` succeeds, and a running miner holds
   `run/gpu.lock.d` for its whole process lifetime. So a miner that is genuinely running is
   **not** preemptible: an arriving surface spins in `until mkdir` and times out after
   `ACQUIRE_TIMEOUT_S` (measured: `acquire chat 10` against a live miner logs
   `'chat' TIMED OUT after 10s behind 'miner'`). The yield protocol that would fix this is
   specified in `docs/specs/miner-preemption.md` and is deliberately **not** implemented — it
   changes the hot path of the only arbitrator of the only contended resource here. That is
   why this surface never auto-starts.
9. **Generate Python stubs from `bos-plus-api`** into `backend/apps/asicminer/` so the panel
   drives Braiins OS+ natively rather than through pyasic's lowest-common-denominator model.
   This is the real "Braiins as an SDK" step and it is an API dependency, not a code fork.
10. **S9 under QEMU** — the package unpacks (JFFS2 via emulated MTD) but produces no console
    output; the older kernel and its devicetree do not match QEMU's zynq machine.
11. **Split `api.py` by concern** and **compose the backend as plugins** — the original items
    12 and 13, still the right shape, and now with three more surfaces arguing for it. Adding
    a unit still means editing the Unit list, a generator and the routes.

12. **SyMoNeuRaL Voice — text-to-speech, speech-to-text, and speech-to-speech, wired into
    SyMoNeuRaL Chat.** Asked for by Garrett 2026-08-17. Nothing is built; this is a spec
    task first.

    **The constraint that decides the whole design is VRAM, not model choice.** One RTX
    5070 Ti, 15.92 GiB, and chat (~5 GB) plus image (~7 GB) already cannot coexist — that
    is why the governor exists. Speech-to-speech is *two* extra models resident at once
    (an ASR and a TTS) wrapped around a chat turn that is itself holding ~5 GB. Work out
    which of these it is before writing a line:

    - **CPU inference for both ends.** `whisper.cpp` and Piper both run on CPU at usable
      speed for short utterances, take the GPU lock never, and can therefore overlap a
      chat generation instead of queuing behind it. This is the same reasoning that keeps
      RavenCalc off the lock, and RavenCalc is the precedent to copy.
    - **A third governor surface.** Honest, but it means a spoken turn is
      ASR → *evict* → chat → *evict* → TTS, with the governor's 1.5 GB VRAM drain wait
      between each. Measure that round trip before promising anyone a conversation.

    Whichever way it goes, **the latency is the product** — a voice surface that takes
    eleven seconds to answer is a demo, not a feature — so measure it early and label it
    `measured` like everything else. Note also that the chat model is text-only:
    speech-to-speech here means ASR → the existing text model → TTS, not an audio-native
    model, and the page must not imply otherwise.

    Two things already in the repo that this must not break: the browser needs a secure
    context for microphone access, which Caddy's TLS already provides but `127.0.0.1:8800`
    also counts as, so it is testable locally; and `/api/chat` streams SSE with a `history`
    array, so a voice turn should reuse that route rather than growing a second chat path.

13. **SyMoNeuRaL Stickers.** Asked for by Garrett 2026-08-17, alongside item 12. Explicitly
    *sticker-only*, in the sense the iPhone sticker drawer means it: small, one subject,
    hard-edged, **transparent background**, no scene.

    Scope it honestly before building a new surface: this is much closer to a constrained
    prompt-and-post-process variant of **SyMoNeuRaL Image** than a new agent. The same
    FLUX.1-schnell weights, a fixed prompt suffix, a smaller canvas, and then the part that
    is actually new — **background removal and an alpha channel**, which FLUX does not give
    you. That is the real work item, it is a segmentation step, and it decides whether this
    needs its own model resident (another GPU tenant) or a CPU post-process.

    Output is PNG with alpha, which means `tools/build_gallery.py`'s watermark bar must
    **not** be applied — a sticker with a caption strip burned into it is not a sticker.
    Renders still go to `backend/output/` and come back as `/api/gen/<name>`; see §3.3.

    **Both 12 and 13 are for an iPhone app Garrett intends to build against this server.**
    That is a real constraint on the API design and it lands before the UI work: the routes
    have to be usable by something that is not this site — no session-shaped assumptions, a
    stable JSON contract, and a clear answer on authentication, because `/api/chat` is
    currently open to whatever can reach the origin. The ASIC surface's
    `SYM_ASIC_ENABLED` + `SYM_ASIC_TOKEN` gate in `backend/apps/asicminer/__init__.py` is
    the pattern already in this repo for a route that must not be world-callable.

### Blocked on hardware, not on work

- **Telemetry cannot be tested.** The emulator will never run `bmminer` — no hashboards. A
  real rig, or a BOS+ rig, is the only way. No download substitutes for it.
- MicroBT emulation is **settled as impossible** (encrypted payload, §2e). The control plane
  over btminer/4028 works today and is the viable route.

---

## 5c. "Fill the window better" — DONE, and the causes were not the obvious ones

Garrett said the site "went a little too small" and named `/overview`, `/livestack`,
`/controlboard`, `/receipts`. The instinct is to widen the containers. **Measure first: the
content already spanned the window.** At 2560x1440 the four sections were already edge-to-edge.
Three other things were small, and they are what got fixed. All of it is in
`site/symoneural.css`, appended at the end — that file is hand-written, no generator owns it.

**1. The header and footer were 1120px islands on a 2560px page.** `header > .wrap` and
`footer > .wrap` inherited a max-width that the sections had already been released from, so the
nav bar floated in the middle of a full-bleed page. Now
`max-width:min(1800px, calc(100vw - 64px))`, sitewide. Measured 1120 -> 1800 at 2560.

**2. Type was 12.5px at every width above 1300px.** The three-tier machinery (§3.0) stops at
1700px and pins fixed pixel sizes, so a 2560px monitor rendered the same 12.5px body text as a
1440px laptop — which is precisely what "too small" looks like from a desk. A fourth tier at
`min-width:1601px` turns `--t1`..`--t7` into `clamp()`s that scale with the viewport, scoped by
`body:has(#hero), body:has(#rack), body:has(#console), body:has(#more)` so it can only reach the
four section pages and cannot touch the front page or the prompt surfaces.

**3. The control board was 383px tall inside a 1277px panel** — half the glass empty under a
dashboard. `html.ns #console > .wrap` and `html.ns #more > .wrap` become column flexboxes and
the grids get `flex:1 1 auto; grid-auto-rows:minmax(0,1fr)`, so the rows divide the spare height
instead of leaving it. Gated `@media (min-width:2000px) and (min-height:1000px)`. Measured 383 ->
943px at 2560x1440; the panel does not scroll at 2560x1440, 2560x1200, 2400x1000, 2200x1000 or
2000x1000.

Also widened above 2000px: `.mh` and `#rack .rackrow` to `min(2400px, calc(100vw - 96px))` with
percentage gutter tracks floored at the old fixed 420/400px, so no width can render narrower than
the tier it replaces.

Vertical fill after, content height as a share of its panel (`overview / livestack / controlboard
/ receipts`): 2560x1440 → 51/46/74/89%, 2560x1200 → 63/57/68/87%, 2000x1000 → 66/64/60/84%.
Overview and livestack sit lower because their content is text plus fixed-size art, and the art
is deliberately capped (below).

### Two negative results. Both were the obvious next move; do not re-try them.

- **Do not widen `.console` columns to `minmax(300px,1fr)`.** With the fluid type above, 300px
  tiles fit only 6 across at 2000-2200px instead of 8-9, so the board gains rows faster than the
  tiles lose wrapped lines: measured 55px of panel overflow at 2000x1000, 81px at 2200x1000, 41px
  even at 2200x1040. Eleven narrow columns that fit beat eight wide ones that scroll. The 1700px
  tier had already rejected this same number for the same reason at 1990x970.
- **Do not "release" `.gart`'s max-width without measuring it first.** A `clamp(268px, ...)` meant
  as generous actually *cut* the art from 434px to 350px at 2560 and 302px at 1920, because a
  later rule was already sizing it to 434px. It is now capped at 768px, which is the art's own
  native canvas width (`tools/_art.py`); past that the browser upscales and the watermark strip
  goes unreadable, which is the bug the 1700px tier was written to fix, reached from the other
  side.

### Whoever verifies layout next

`node tests/frontend.mjs` asserts the one-screen fit at four viewports — 1990x970, 1855x745,
1440x900, 1301x740 — **all of them under 2000px wide**, so neither block above can be caught by
that suite. The ad-hoc probe used here lives in the session scratchpad and is not worth keeping;
re-measure with a fresh Playwright script that reports, per page, `content/panel` height ratio,
page scroll, panel scroll and horizontal overflow. Read computed styles; do not reason about the
cascade.

## 5b. The original queue, for reference

### Original items (many now done — see §2c)


Roughly in the order the user asked for it. **Nothing here is blocked and nothing is
broken** — this is a queue of new work, not a repair list.

0. **The watermark question — DONE 2026-08-17, built and waiting on a deploy.** The user
   chose: bigger strip **and** the same facts as HTML text. Three things this taught, all
   worth keeping:

   - **It never needed the GPU.** The bar is drawn *below* the render, so the art is exactly
     the top `meta['size']` rows of each PNG and cropping recovers it losslessly; everything
     the bar prints is already in the `art-*.json` sidecars. `build_gallery.py --restamp`
     redraws all eighteen in a few seconds of CPU, takes no governor lease, and cannot alter
     a pixel of the artwork (verified: SHA-256 of the cropped art region is unchanged).
     An earlier draft of this section said it cost ~3.5 min of GPU. It does not.
   - **"Bigger font" was not available, only "more lines".** The old one-line bar measured
     704px of a 768px canvas; at 16px it overflows. The bar is now two rows of 20px (`FOOT`
     80px, 9% of the image). Three rows cost 16% and four cost 22% — the picture starts
     paying for its own caption, which is why two won.
   - **A burned-in caption cannot win against a 3.5× downscale.** At the 268px a gutter
     render is shown at, even a four-row bar is marginal. So `_art.provenance()` prints the
     same facts as real HTML text under each render (`.gprov`), which is crisp at every
     width and costs no image area. The strip is the copy that travels with the downloaded
     file; the text is the copy a visitor reads in place.

   There are **18** distinct renders, not nineteen — the test counts `<img>` nodes and one
   render is placed twice.

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
4. **SyMoNeuRaL Miner** — GPU, Ravencoin. `backend/apps/cryptominer/` — **ported, running and
   measured.** Mining is off by default and there is no default that turns it on: it refuses to
   start without `SYM_MINING_ENABLED=1` (the check is `== "1"`, so `true`/`yes`/`on` leave it
   off silently), reads real `nvidia-smi` telemetry, and gates control on `SYM_MINER_TOKEN`,
   which must **not** be the same string as `SYM_ASIC_TOKEN` — this one gates a process that
   takes the card from every other surface.
   **KawPow hashrate is now measured on this machine, not vendor and not projected:
   52.75 – 53.01 MH/s across two runs** — RTX 5070 Ti, 300 W limit, driver 610.57.04,
   `kawpowminer 1.2.4+commit.8bd0d598.dirty`, command `-U -M 500000`, 2026-08-17. The ~0.5%
   run-to-run spread is quoted rather than the best run and **no cause has been established**
   for it.
   **That run is a benchmark against no pool: measured, and earning nothing.** A miner with
   nowhere to submit a share earns nothing whatever its hashrate says, so `pool()` and
   `benchmarking()` now detect the absence of a pool URL (kawpowminer's own rule — "when
   playing with benchmark or simulation no connection specification is needed") and the
   distinction is surfaced in `/api/gpuminer/status`, in `selftest` and in the rack unit's
   detail line. It had to be: the rack previously displayed
   `holding the card · 53.01 MH/s reported by the miner` for a benchmark run. Every digit was
   real, and a reader would still have concluded the box was mining Ravencoin. **"Measured" and
   "earning" are different claims** and the surface now makes both.
   No earnings figure is published anywhere and none should be — earnings depend on network
   difficulty, pool fees and the RVN price, none of which this box measures. Pricing questions
   go to symonsayadmin@symoneural.com.
   Remaining: the governor still has no tenant class that *everything else* evicts (a miner is
   the opposite of `train`, which is never evicted). See item 8 above for why the existing
   `miner)` arm does not achieve this. There are two copies of
   `SymoneuralGPUWorker/SyMon_MinerGPUWorker_PROD_20260102-1818` (one with a ` 2` suffix) —
   diff and drop the duplicate.
5. **ASIC firmware control panel** for MicroBT + Antminer rigs. References: `references/Projects_Crypto/`
   (~2.5 GB of firmware), `references/CGMiner-master/`, `references/braiins-os-feeds-master/`, and `references/Pete/` (contains
   `pyasic` and `whatsminer-api`). **This is a much larger piece than the GPU miner — keep it
   separate, do not conflate them.**
6. **Backstage.io backend API pattern** — the user said this "MUST follow". References:
   `references/backstage-master/`, `references/software-templates-main/`. Needs its own scoping pass.
7. **`references/nx-master/`** as the server frontend reference.
8. **Audit the CUDA work — DONE 2026-08-17. Report: `docs/specs/cuda-audit.md`.**
   Nothing was changed; it is an audit and the fixes are a separate decision. Three things
   worth knowing before you open it:

   - **The brief's premise was wrong and the report corrects it.** There is no
     `symoneural_reinforce/`; the engine is `backend/apps/reinforce/`, 35 Python files
     compiled through NVRTC at runtime, with no `.cu` and no CMake. Verified directly.
   - **`symoneural/core/context.py:149`** is the only `_attr` call in that file with no
     explicit default, and `_attr` defaults to `0` — so a name mismatch silently yields
     zero SMs while every neighbouring call guards itself. Verified directly.
   - **The honest-labelling findings deserve a careful second look**, because they touch the
     argument the whole site rests on: an orchestrator prompt describing projected figures
     as "measured facts about the machine", a `pcie_bound` that is `return True` beside a
     comment saying it is computed, and wall-clock reported in a field named `device_ms`.
     These are unverified beyond the report — reproduce before acting.
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

    **Do it with the test suite as the safety net**: `node tests/frontend.mjs` passes 18/18
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
    already serves `/api/chat`, `/api/image`, `/api/ravencalc`.

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

10. **The `scripts/deploy.sh` subshell bug — DONE, and it was already done.** Fixed in
    commit `aa424d3`: the loop reads from a process substitution (`done < <(...)`), so it
    runs in the current shell and `missing` survives to the exit test. Verified empirically
    rather than by reading the comment — the block was run verbatim against a fake webroot
    containing one present and one absent reference, and it counted 1 and exited non-zero.
    §1 and two entries here listed it as outstanding after it had been fixed; that was the
    stale claim, not the code. The other `while read` in that script (the orphan scan) *is*
    in a subshell, but it only writes to stdout and sets nothing the caller reads, so it is
    correct as written.
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

### The build chain — eleven generators, and the order matters at both ends
```bash
python3 tools/build_pages.py       # chat/image/ravencalc/remix surfaces -> site/*.html
python3 tools/build_masthead.py    # pitch + hero side by side           -> site/index.html
python3 tools/build_rack.py        # live rack + 2 gutter renders        -> site/index.html
python3 tools/build_console.py     # control board                       -> site/index.html
python3 tools/build_cost.py        # Owned vs Rented                     -> site/documentation.html
python3 tools/build_stack.py       # Inference Architecture              -> site/documentation.html
python3 tools/build_training.py    # the manual                          -> site/training.html
python3 tools/build_sky.py         # the 19-render constellation         -> site/build.html
python3 tools/build_tabs.py        # one-screen front page, tab strip    -> site/index.html
python3 tools/build_split.py       # one page per section  -> site/{overview,livestack,
                                   #   controlboard,receipts}.html  (READS index.html;
                                   #   must run after everything that writes into it)
python3 tools/build_cachebust.py   # <-- ALWAYS LAST. stamps ?v=<hash> on every local asset
```
Two ordering constraints, not one. `build_split.py` **reads** the assembled `index.html`
and writes four pages from it, so anything that edits `index.html` must run before it or
those pages ship stale. And `build_cachebust.py` stays last, now stamping 16 pages rather
than 12 — if that count drops, a generator has stopped emitting something.
`tools/build_gallery.py` is separate, and which flag you use decides whether it touches the
card at all:

```bash
python3 tools/build_gallery.py              # render what is missing   -- GPU, ~11.2s each
python3 tools/build_gallery.py --force      # re-render everything     -- GPU
python3 tools/build_gallery.py --restamp    # redraw the watermark bar -- NO GPU, seconds
```

`--restamp` crops each PNG to `meta['size']` rows and redraws the bar from the sidecar. It
is idempotent *because* it crops to the art height rather than subtracting the current bar
height, so it discards whatever bar is present regardless of size. Changing the watermark
never needs a governor lease and never re-renders the art.

`tools/_art.py` is a shared helper, not a generator — do not run it. It is also the only
place that should compute a render's dimensions: `_art.dims()` reads the PNG's IHDR, because
`height="802"` was hardcoded in two generators and the watermark change made both wrong.

**Always run every generator twice and diff before committing.** One line does it:
```bash
md5sum site/*.html site/*.css site/*.js > /tmp/a
for g in pages masthead rack console cost stack training sky tabs cachebust; do python3 tools/build_$g.py >/dev/null; done
md5sum site/*.html site/*.css site/*.js > /tmp/b && diff /tmp/a /tmp/b && echo IDEMPOTENT
```

**`build_cachebust.py` must run last**, after anything that touches `site/*.css`, `site/*.js`
or the pages that link them. If a stylesheet changes and the stamps are not refreshed, every
visitor with a warm cache gets new markup against the old CSS — which is exactly the failure
that put nineteen full-size renders down the left of the live page.

### Before you believe a test failure that contradicts the source in front of you
```bash
python3 scripts/check-stale-pyc.py         # report; exit 1 if anything is stale
python3 scripts/check-stale-pyc.py --fix   # delete the stale ones, exit 0
```
Python trusts a timestamp-based `.pyc` on the source's **mtime truncated to whole seconds** and
its **size in bytes**. A two-character numeric edit (`48`→`64`) changes neither, and an edit that
lands in the same clock second as the bytecode write makes the cache look valid **forever**. That
cost hours and got written into this file as an open owner decision about a hyper-parameter; it
was never a decision. This script recompiles the source in memory and compares the code objects'
*logical* content — filenames deliberately excluded, because `co_filename` varies with how a
module was imported and comparing raw marshalled bytes reported 240 false positives against one
real one. Deleting a `.pyc` is always safe; it is a cache.

**Verified in both directions on 2026-08-17**, which is the standard §3.0 holds a check to: 0
stale against a healthy tree of 88 trusted files, and it reports the known-bad
`presets.cpython-313.pyc` as stale when that file is put back. It skips `-pytest-*.pyc` — those
hold pytest's assertion-rewritten bytecode, which is *supposed* to differ, and pytest validates
them itself.

### Test in a real browser — this is the important one
```bash
node tests/frontend.mjs                          # local API on :8800
node tests/frontend.mjs https://symoneural.com   # production
```
**Measured 2026-08-17 — the suite is 26 assertions now, not 18. Local 26/26 and production
26/26, verified at 14:04 after the 14:01:05 deploy.**

Worth keeping, because it is the clearest example in this file of §7's "they judge the
deployed site" and of how fast that judgement goes stale. Before that deploy, production was
**25/26**: `each section has its own URL, carrying only itself, fitting one screen` failed
because `/livestack` content overflowed its panel by 3px at 1855×745 (595/592) and by **32px
at 1301×740** (619/587), while local passed at 589/589. The diagnosis was the cachebust
stamp — production on `symoneural.css?v=5d6297cfb8` against a working tree at
`?v=3c8fa4fd4c` — so it was the §3.0 chassis-strip fix sitting undeployed, not a
regression. Confirmed by the deploy closing it: production now measures 589/589 and 587/587,
identical to local.

**The check that resolves this class in one line, and the order to do it in.** The webroot is
world-readable, so you never have to guess and you never need sudo to find out:

```bash
for f in site/*.html site/*.css site/*.js; do
  cmp -s "$f" "/var/www/symoneural/$(basename "$f")" || echo "DIFFERS $(basename "$f")"
done
```

Silence means the webroot is current and a failing assertion is a real defect. Do that
**before** concluding anything from a production run — and re-check it after, because a
concurrent session can deploy while your suite is still running, which is exactly what
happened here.

Also seen on **both** runs and **not** a failure: four `400`/`404` lines for
`/api/tuner/{playlist,xtream/channels,tune,session/__probe__}` in the trailing
"failed requests" block. That assertion tests whether the routes are *routed*, and a `400`
on an empty body is a routed endpoint rejecting bad input. Do not chase them.

It asserts on what the DOM *shows*: units render from `/api/status`, the bus plate carries
GPU/CPU/`--`, nothing overlaps or spills past the right edge at 390px, ravencalc returns
`x**3/3`, and **a generated image actually decodes** (`naturalWidth > 0`). That last one is
the assertion that would have caught the 404 that shipped — curl proved the endpoint
answered, which was never in doubt.

Four of the twenty-six exist because of specific bugs and are worth not deleting:

| Test | The bug it exists for |
|---|---|
| `a render opens large enough to read its watermark` | asserts computed `pointer-events` — a `pointer-events:none` parent had silently disabled a whole feature |
| `nothing spills past the right edge at 390px` | the nav ran to x=512 on a 390px viewport |
| `pitch, hero and rack fit one look` | asserts the *shape* (one row, four gutter renders, rack within one viewport), so copy edits do not break it but a return to stacked sections does |
| `every local asset is cache-busted` | the stale-CSS failure above |

**Run it against production too**, not just localhost. The two differ in exactly the way
that has caused every "it's still broken" exchange in this project.

Playwright lives in **`contrib/llama.cpp/tools/ui/node_modules`** (installed for the webui
build) and is imported by a path derived from the test's own location. An earlier draft of
this line omitted `contrib/`, which is a dead path — the restructure in `4b6eaba` moved the
vendored checkouts. `channel: 'chrome'` uses the system browser, so nothing downloads.

**Found while verifying the watermark work, pre-existing, NOT fixed — your call.** Four of
the nineteen hover captions on `/build.html` are positioned partly off the **left** edge of
the viewport at 1440px: the caption box is a fixed 220px centred on renders that are only
55–64px wide and sit near the left edge, so it overhangs by 13–71px. Measured identically on
production (offsets −14, −70, −47) and locally (−13, −71, −48), so it long predates this
work and the longer provenance text did not cause it — that change adds height, not width.
It is hover-only and clips nothing. The fix is to clamp `.sky .art figcaption` inside the
viewport rather than centring it unconditionally; it was left alone because nudging
absolutely-positioned, counter-rotated elements is exactly the class of change this project
has lost rounds to, and it deserves a screenshot-and-confirm rather than a drive-by.

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
- **When they describe a layout, they mean it literally and spatially.** "Side by side",
  "shift to the right center", "2 on each side of the server rack" are instructions about
  position, not vibes. This session lost three rounds to reading them loosely; the fourth
  round they drew it out with cropped screenshots and annotations, and that was the round
  that worked. If a layout instruction is even slightly ambiguous, **screenshot what you
  built at their viewport width and show it**, rather than describing it in prose.
- **They frequently judge the deployed site, not your working tree.** Before answering "it's
  still wrong", check what is actually deployed: `curl -s https://symoneural.com/index.html
  | grep -o 'symoneural.css?v=[0-9a-f]*'` and compare to the local file's hash. Most of the
  "this isn't working" exchanges in this project were a correct change that had not been
  deployed yet, and saying so plainly ends them in one line.
- **They will tell you when something is good.** Take the win, do not gild it, move on to
  the next thing.

---

## 8. Machine facts

- **RTX 5070 Ti**, Blackwell `sm_120`, 15.92 GiB usable, ~946 MiB idle.
- **PCIe Gen 3 ×8, host capped** — ~7 GB/s host↔device. The GPU itself does Gen 5. This is a
  published negative result and stays on the site.
- Chat: ~5 GB resident, measured **80–92 tok/s** with the persona adapter loaded.
- Image: FLUX.1-schnell q4_k, ~7 GB, **~11.2s** per 768×768 at 4 steps.
- Chat and image weight sets **cannot co-reside**. `scripts/gpu-governor.sh` serialises them.
- The **CUDA sample venv** at `contrib/cuda-samples/python/.venv` is the thing pinned at
  exactly **7 packages** — check it by its full path, never with a bare `pip freeze`.
  Measured 2026-08-17: that venv has 7; the **system** interpreter has **190**, because it is
  a Debian install and always was. Earlier revisions of this line said "Base interpreter:
  exactly 7 packages (`pip freeze | wc -l`)", which contradicts `.claude/CLAUDE.md` and sends
  you looking for a broken machine. Training venv: `training/.venv`, torch **2.11.0+cu128**,
  `torch.cuda.is_available()` true (verified 2026-08-17).
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

**The Swagger compliance gap is closed, and the fix this section used to recommend was
impossible.** It said to "fetch `swagger-ui-bundle.js.LICENSE.txt` from the matching
swagger-ui-dist release". That file does not exist upstream — verified by downloading
`swagger-ui-dist@5.17.14` from the npm registry and listing the tarball, which contains
exactly `package/LICENSE` and `package/NOTICE`. The banner naming it is a webpack/terser
artifact: terser writes the pointer whether or not the extracted file is published.

What is shipped is correct and complete: `site/swagger-ui-LICENSE.txt` and
`site/swagger-ui-NOTICE.txt`, both **byte-identical to upstream** (SHA-256 compared), and
`.txt` is in `deploy.sh`'s `PUBLISH` list so they reach the webroot. The bundle itself is a
SHA-256 match for 5.17.14. `LICENSES.md` §1 has the full reasoning and got there first.

Remaining nicety, not an obligation: no page *links* those two files. Apache-2.0 §4 requires
the NOTICE be included in the distribution, which it is; discoverability is a separate and
softer thing. Worth a footer link if anyone is in `documentation.html` anyway.
`backend/apps/remix/THIRD-PARTY-LICENSES.md` has the full audit. The Apache-2.0 attribution on
the rack's `detail` line ("built on Qwen2.5-7B-Instruct") is a **licence condition** — that is
why truncating it mattered.

## 10. Repo layout after the flatten

This block was stale in two ways and both would have sent you to paths that do not exist:
the generators moved into `tools/` and the scripts into `scripts/` in `4b6eaba`, and
`symoneural_reinforce/` moved to `backend/apps/reinforce/` in `9b5da84`. Corrected:

```
backend/api.py                             # the API -- 1,573 lines, see §5 item 12
backend/apps/                              # the surfaces: ravencalc, remix, reinforce,
                                           #   cryptominer (GPU), asicminer (ASIC)
backend/models/  backend/output/           # weights; generated renders
bin/                                       # the CLI
tools/          build_pages.py build_masthead.py build_rack.py build_console.py
                build_cost.py build_stack.py build_training.py build_sky.py
                build_gallery.py build_cachebust.py _art.py
scripts/        symoneural.sh gpu-governor.sh deploy.sh fetch-models.sh setup.sh
ops/            Caddyfile, install-caddy.sh, install-service.sh, symoneural-api.service
site/           the deployable site (index, documentation, account, 5 surfaces, art-*.png)
tests/          frontend.mjs
training/       corpus, train_lora.py, adapter/, .venv
docs/specs/     design specs and audits -- PROPOSALS, not state. See its README.
contrib/        llama.cpp, stable-diffusion.cpp, cuda-samples   # gitignored, large
references/     dropped-in reference trees                      # gitignored wholesale
```

**`backend/apps/reinforce/` is not a C++ project.** It is 35 Python files that compile
through NVRTC at runtime — no `.cu` files, no CMakeLists, nothing to `make`. The
`CMakeLists.txt`, `cmake/` and `bin/` you may be thinking of belong to `contrib/cuda-samples/`.
An audit brief that assumed otherwise sent an agent looking for a build system that was never
there.

Gitignored: `models/` (40 GB), all vendored checkouts, `references/Projects_Crypto/` (~2.5 GB),
`references IPTV/`, `references/Pete/`, every `.venv`, `run/`, `site/gen-*.png`, `*.safetensors`, `*.gguf`.
Tracked: 337 files, ~7 MB, plus the six `site/art-*.png`.

**Watch out:** the user drops large reference trees into the repo root while you are working.
Check `git status` before `git add -A`.
