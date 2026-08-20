# GARRETT-INBOX

Things the coder found while Garrett was away that require his judgment or his sudo. Nothing
here is fixed; each entry is waiting for him.

---

## From the reconcile — pre-existing before the autonomous run

- **Secrets in a tarball.** `backend/apps/remix/.env` is tracked and contains
  `SPOTIFY_CLIENT_SECRET`, `VLLM_API_KEY`, `DJ_TOKEN`. It is in a cloud tarball that carries
  `.git`. If that tarball is anywhere untrusted, those three secrets are out. Rotate them.
  Not fixable in code — the exposure already happened.

- **Live wrong claim on production.** `site/documentation.html` diverges from
  `/var/www/symoneural/documentation.html` on 18 non-cachebust lines. Deployed page prints
  `$ symoneural residency` (pre-rename CLI command) with stale figures. Needs `sudo
  scripts/deploy.sh --prune`.

- **Node ≥22 upgrade.** Current is v20.19.2. Bumping node risks the vendored playwright
  1.56.1 gate that 43/43 and 16/16 depend on. Deferred to Garrett.

---

## From the autonomous audit run — iteration 4, `yocto/` (audit item 6)

The 12 `meta-symoneural-*` layers now parse clean (`bitbake -p`, exit 0, 963 recipes, 0 errors,
3 warnings). `bitbake -g` still fails, on two things neither of which I can decide.

- **Which kernel tree, which revision, which defconfig.** `bitbake -g symoneural-image` exits
  1 with `Nothing PROVIDES 'virtual/kernel'`. Every linux-yocto provider in openembedded-core
  is gated on a closed regex of qemu machines (`linux-yocto_6.18.bb:55` and three siblings), so
  no `.bbappend` can widen it — ours matches and its base is still printed `(skipped)`.
  Upstream's answer is `meta-skeleton/recipes-kernel/linux/linux-yocto-custom.bb`, whose own
  header (:7-15) says to copy it into our layer and supply a kernel tree, a `SRCREV` and a
  defconfig; :21-25 warns that omitting the defconfig gives build or boot errors "This is not
  a bug." Those three values are engineering choices about what we ship, not gaps I should
  guess: the KMACHINE/KBRANCH pair can only be validated against `yocto-kernel-cache`, and
  that repo is not on this box, so anything I wrote would be a plausible string that parses
  green and fails at `do_kernel_metadata`. I left the failure loud instead and wrote the
  reasoning into `meta-symoneural-bsp/conf/machine/symoneural-workstation.conf` above the
  `PREFERRED_PROVIDER_virtual/kernel` line. **Do not "fix" this by deleting that line** —
  `linux-dummy.bb:10` PROVIDES `virtual/kernel` and `:18` adds `kernel-modules`, so both
  errors vanish and the image does not boot. I confirmed that is exactly why linux-dummy is
  currently skipped.

- **`meta-openembedded` is on the wrong branch, and fixing it is a write outside my boundary.**
  `bitbake -g symoneural-stack` exits 1 on `Nothing RPROVIDES 'python3-httpx'`.
  `symoneural-stack_git.bb` RDEPENDS on eight python packages; three of them
  (`python3-core`, `-json`, `-shell`) are packages of core's own python3 and resolve fine
  (they are in `python3-manifest.json`). The other five — `python3-sympy`, `-fastapi`,
  `-uvicorn`, `-pydantic`, `-httpx` — live in `meta-openembedded/meta-python`, which is on
  disk but declares `LAYERSERIES_COMPAT = "whinlatter wrynose"` against core's `blacksail`,
  so `yocto/scripts/setup-build.sh:46-51` correctly drops it from `bblayers.conf`. The fix is
  `git -C /home/google/yocto/meta-openembedded fetch --all && checkout <branch naming
  blacksail>`, which is a write under `/home/google/yocto` — outside
  `/home/google/Symoneural/`, so forbidden to me. `setup-build.sh:113-120` already prints
  this as guidance; it has not been run. **Until it is, RavenCalc cannot be built for a
  target at all**, because SymPy is the one hard dependency of the surface that was supposed
  to be the arm64 machine's whole reason to exist (`symoneural-arm64.conf:5-8`).

- **One boundary violation to disclose, mine, unavoidable.** Running `bitbake` against
  `/home/google/yocto` byte-compiled nine of openembedded-core's own python modules, creating
  `__pycache__` directories under `openembedded-core/meta/lib/oe/`. That is nine writes
  outside `/home/google/Symoneural/`, which the hard rules forbid. I did not intend them and
  cannot prevent them: CPython writes `__pycache__` next to any module it imports, and the
  modules being imported are bitbake's. Nothing was modified, only compiled caches added, and
  no first-party file is involved. Flagging it rather than letting you find it.

(Coder appends here.)

## From the offline-units directive — 2026-08-19 23:52 UTC

The coder is fixing what it can (Studio, Project). What follows requires you when you're back:

- **Coder unit** — `sudo scripts/enable-surfaces.sh coder`. Sets `SYM_CODER_ENABLED=1` and a
  fresh token; the rack row flips to `ready · local only · workspace X · no GPU lease`.
  Prerequisite: none. Runs in one command.

- **Studio unit** — `sudo scripts/enable-surfaces.sh studio`. Prerequisite: none any more —
  the `studio)` case landed in **`431c337`**, so the argument is accepted as of that commit.
  If you are running from an older checkout the script still rejects `studio` as an unknown
  argument, which is the one way this can surprise you.

- **Gateway unit** — cannot be enabled by env alone. `_cleared(net, addr)` requires a licence
  to have actually settled against a deployed contract. `SymoneuralLicence.sol` in
  `ops/gateway/contracts/` has never been deployed. Path: `ops/gateway/DEPLOY.md` — deploy to
  Nile testnet first, fund a wallet, then `sudo scripts/enable-surfaces.sh gateway --network
  nile --contract T...`. This is a business action, not a script call.

## From the autonomous audit run — iteration 5: the four OFFLINE rack units

You asked for all of these brought online. One of the four is done and needs nothing from you;
one needed a repo fix that is now in; two are yours, and one of those two is not a command at
all. Measured against the live API (pid 90295) at the time of writing, not inferred:

```
  coder     offline  disabled — local-only operator surface, off by default
  gateway   offline  not configured — set SYM_GATEWAY_ENABLED=1, SYM_GATEWAY_NETWORK …
  project   ready    cpu only, never queues          <-- done, no action from you
  studio    offline  set SYM_STUDIO_ENABLED=1 and SYM_STUDIO_TOKEN=<secret> …
  exp       queued   container up, nothing mounted; preset dev mounts on first request
```

### Project — reads `ready`, still nothing for you, but read the second paragraph

Its environment was already set. It was offline for a second reason: the store file did not
exist and nothing on the serving path creates one (`connect()` creates it, and the rack poll
deliberately uses `probe()`, which opens read-only, so the poll can never create it). It reads
`ready` now, no sudo and no restart — rack rows are computed per request.

**Correcting my own earlier entry here, which said "DONE, nothing for you" and stopped.** What
I did first was create `run/project/store.db` by hand. That fixed this box and nothing else:
`store.init_db()` has existed the whole time with **no caller anywhere**, so any fresh install
— a new host, or a rebuild from the `.deb` — would have come up `offline / no project store
initialised` again, and my note would have told you the item was closed. The real fix is
`store.bootstrap()` called from `api.py`'s `lifespan`: it creates the store when the surface is
switched on and deliberately does *not* when it is off. That is **`deaa19d`**, with tests. One
consequence for you: the store now appears at first API start rather than at first POST, so
after the next `sudo systemctl restart symoneural-api` a fresh box shows Project `ready`
without anyone visiting the page.

That restart is also what *triggers* the new code, which is why there is a third paragraph.
`bootstrap()` runs inline in the lifespan, before the server accepts anything, and in
`deaa19d` a failure there — a full disk, a read-only remount, a `run/project/` owned by
someone else — would have propagated out of the lifespan. uvicorn would have failed to start,
`Restart=always` would have retried forever, and the restart *I told you to run* would have
been the outage, across all thirteen units rather than the one row this was about. I caught it
by checking rather than assuming, and **`1537262`** guards it: the create is wrapped, a failure
is logged, and the row falls back to the reading that was already true, `offline / no project
store initialised`. Nothing for you here either, but you should know the restart in the line
above was, for one commit, more dangerous than it looked.

I also checked the thing that would have made this bite today: `/etc/systemd/system/symoneural-api.service`
has `User=google`, the same owner as the store file, so there is no permission mismatch
waiting on the existing `run/project/store.db`.

### Studio — one command, and it did not exist until today

`scripts/enable-surfaces.sh` accepted `coder project rack gateway` and had no `studio` arm at
all, so there was no sanctioned way to switch Studio on — `enable-surfaces.sh studio` died with
"Unknown argument: studio". Fixed in **`431c337`**, with the write loop itself under
test — backend suite 1111 passed at that tree. Your command:

    sudo scripts/enable-surfaces.sh studio

Read this before you run it. Studio has no `ALLOW_REMOTE` second gate the way Coder and Rack
do, so `SYM_STUDIO_TOKEN` is the entire boundary, and
`backend/apps/symoneuralstudio/__init__.py:42` is explicit that the surface can write to the
host. On a box with a public IP that is a different risk class from the other three. The script
prints this warning at the end for the same reason.

A third step, and it is not sudo. I had only ever measured Studio `ready` with ComfyUI
already up, which is not the state your two commands leave the box in. Re-measured with 8188
down — the honest post-restart condition, since there is no systemd unit for ComfyUI, only
`scripts/comfyui.sh` — the row still reads `ready · 26 tools · workspace /home/google/Symoneural
(found by walk)`. That is deliberate rather than lucky: `status()`'s docstring says the row
describes the orchestrator, not the bench, and the bench has its own reading —
`routes.py:347` returns `comfyui: {up, url}` and `page.js:90-93` prints it as its own strip
cell, showing `scripts/comfyui.sh start` when it is down. Every render route answers 503
`comfyui_unreachable` with that same fix string rather than hanging.

So after your two commands the page loads, the tools work, and image generation does not. The
third step is yours to run whenever you want the bench, and it needs no root:

    bash scripts/comfyui.sh start

It does not survive a reboot. Nothing in the repo starts it — that is filed as audit item 27,
and it is a decision for you, not a fix for me: a unit file for a process that takes the whole
GPU is a policy call about what this box is for.

### Coder — one command, pure env-set, verified

`unit_state` (`apps/coder/__init__.py:945-956`) needs `enabled()` and `workspace().is_dir()`.
`workspace()` (`:124-132`) defaults to the repo root, and I resolved it: `/home/google/Symoneural`,
`is_dir()` True. So there is no second blocker behind the env vars — this is a pure switch-on:

    sudo scripts/enable-surfaces.sh coder

It stays loopback-only. The script never writes `SYM_CODER_ALLOW_REMOTE`, deliberately.

That paragraph above reasons from the code, which is not the same as having seen it. I had
never once observed a `coder` row reach `ready`, so I ran it: with `SYM_CODER_ENABLED=1` and a
token on a spare-port instance, the row reads `ready · local only · workspace Symoneural · no
GPU lease`. There is no third prerequisite hiding behind the detail string.

### Gateway — NOT a command. Do not expect this one to go green.

Verified from the code rather than from the docs, because the reviewer asked whether any
configuration-only path can reach `ready`. It cannot. `unit_state` needs, in order:
`configured()`, then a chain reading whose network and contract match the configured ones,
then `contract_present is True`, then `_cleared(net, addr)` returning a settlement recorded by
the code path that verified it (`apps/gateway/__init__.py:271-306`). The clearance store is
`backend/state/clearances.jsonl`; it does not exist and holds 0 records.

So `sudo scripts/enable-surfaces.sh gateway --network nile --contract T…` moves the detail
string from "not configured" to a measured chain reading and leaves the state `offline`. That
is correct behaviour, not a bug — `ops/gateway/DEPLOY.md:14` says so in its own words, and the
docstring at `:334-341` names "the contract is there, so report ready" as the wrong next commit.

Reaching `ready` needs a company keypair, a contract deployed under it, and a licence that
actually settles. That is `ops/gateway/DEPLOY.md` Phases A–D, money enters at D, and the whole
thing is a decision rather than a procedure. Nothing an agent can do moves it.

### Exp — `queued` is already the honest reading, and one warm request changes it

Not offline. Its own status function says "container up, nothing mounted; preset dev mounts on
first request", which is a true description of "nothing has hit `/api/exp/*` yet". If you want
it `ready` on the dashboard the fix is one warm request at startup or from the frontend, not a
change here. Filed low-priority on the audit surface rather than done, because deciding that
the dashboard should provoke a mount is a design call.

### Order, if you run all three

    sudo scripts/enable-surfaces.sh coder studio        # one restart, both surfaces
    sudo scripts/enable-surfaces.sh --show              # confirm, no secrets printed

`--show` needs sudo too: the file is root 0600, and a non-root read could only report "absent",
which would be a lie in the one direction that matters. That is why the root check at
`enable-surfaces.sh:46` runs before argument parsing, and why I did not loosen it to make my
own test easier — the test reads the script's text instead, and says so.

### `gpu-governor.sh status` — one word, and it is yours not mine

`scripts/gpu-governor.sh:200` prints `resident surface   <x>`, where `<x>` is whatever surface
last *acquired* the lock. Nothing clears it on release, which is deliberate — your comment at
`:121` says so, and the evict path relies on it to spot a stale `train`. But the label says the
surface is resident now. I watched it print `resident surface comfy / lock free / vram used
725 MiB` right after ComfyUI had fully drained, and `resident surface image` with the same
725 MiB before ComfyUI ever started. Nothing was resident either time.

`git blame` says `bf7c8fb`, you, 2026-08-16, so I did not touch it. The fix is one word in
`cmd_status`: `last held by` instead of `resident surface`. Do not clear the file on release
instead — that is the history `:121-123` depends on. Filed as item 26 in
`AUDIT-SURFACE-2026-08-19.md` with the measurement.

## Persona corpus still teaches the old tagline (2026-08-20)

`f70d6a3` changed the homepage positioning line to "SyMoNeuRaL builds custom server
software, firmware and middleware, built with Machine Learning capabilities."

`training/build_dataset.py:68` still contains the old sentence — "SyMoNeuRaL builds custom
AI stacks that you install rather than subscribe to." — as persona training text. CLAUDE.md
puts that file off limits to me, so I did not touch it.

Consequence: the site says one thing and the fine-tuned model says another. Anyone who asks
the chat surface what the company does gets the old positioning. Fixing it is an edit to
that one string plus a corpus rebuild and adapter retrain — yours, not mine.

## Restart needed: weight files renamed under a running service (2026-08-20)

`34c5009` gave every file under `backend/models/` a house name. The systemd unit runs
`/home/google/Symoneural/backend/api.py` **in place** (`WorkingDirectory=/home/google/Symoneural`,
`ExecStart=/usr/bin/python3 .../backend/api.py`), so the process that is live right now still
holds the old `CHAT_MODEL` / `IMAGE_MODELS` paths in memory and those paths no longer exist on
disk. Chat and image will fail until:

    sudo systemctl restart symoneural-api

The constants are already correct in the file, so the restart alone fixes it — no deploy step
is required for this, though `sudo scripts/deploy.sh --prune` would also do it.

I did not paper over this with compatibility symlinks. Symlinks named
`Qwen2.5-7B-Instruct-Q4_K_M.gguf` would have kept the service up without a restart, but they are
exactly the foreign names on disk you just asked to be rid of, and creating them unilaterally
would have quietly undone the thing the commit was for. If you would rather have zero downtime
than a clean `models/` for the next few minutes, say so and I will add them and delete them
after the restart.

## Three commands to turn the news ticker on, and the order matters (2026-08-20)

The bar you asked for is built and tested — `16ddfb9` (collector) and `26cb58e` (endpoint plus
the crawl). `.claude/HANDOVER.md` §2i has the whole design. **Production shows nothing until you
run these, in this order:**

    sudo scripts/deploy.sh --prune
    # then add one line to /etc/symoneural/api.env   (root, 0600, via EnvironmentFile=)
    #     SYMONEURAL_NEWS_ENABLED=1
    sudo systemctl restart symoneural-api

**The env var on its own is not enough, and setting it first is worse than leaving it off.**
`26cb58e` changed `site/ui.js` and `site/symoneural.css` and re-stamped 307 asset links. Caddy
serves both of those off the webroot and the `?v=` hash is only a cache key — the old file still
answers a request for the new hash. So a switched-on bar before the deploy is new markup against
the old stylesheet: an unstyled row of headlines at the bottom of every page. Deploy first and
that state never exists.

The restart is the same one already owed for the weight rename above, so if you have not run
that yet, one restart covers both — but the deploy still has to come before the env var.

`EnvironmentFile=`, not `Environment=`: `systemctl show` prints `Environment=` values to any
user on the box. This particular value is not a secret, but the unit already has the right
mechanism and using the wrong one here is how the habit starts.

**What it will do once on:** one pass every 15 minutes, 28 requests a pass across eight hosts
(~112/hour), publisher RSS and Atom plus three keyless search feeds. No API keys, no accounts,
nothing to pay for, no browser, no scraping of HTML. To turn it back off, drop the env var and
restart — the route stays and answers 200 with an empty list, and the bar simply does not
render. To slow it down without turning it off, `SYMONEURAL_NEWS_INTERVAL_S` (clamped 300–21600).
To drop a publisher you dislike, `SYMONEURAL_NEWS_OFF=arxiv cs.LG`.

One trap in that variable, because the example I first wrote here fell into it: a name switches
off **every** source *and* search engine bearing it, and `Hacker News` is both — a publisher
feed (`hnrss.org/frontpage`) and one of the three search arms (`hnrss.org/newest?q=`), checked
against the same set at `collect.py:84` and `collect.py:100`. So `SYMONEURAL_NEWS_OFF=Hacker News`
does not drop one aggregator, it drops a third of the search coverage as well. If that is what
you want, fine; if it is not, there is currently no way to name just one of the two, and I will
add one if you say so.

One thing I deliberately did not make configurable: **which hosts it may connect to.** That list
is derived from the source tuples in code, and no environment variable can add to it. On a box
with a public IP an env-settable URL list is an SSRF primitive pointed at `169.254.169.254`.
That is a limit on where the process may connect, not a filter on what may be published — your
"no filters or safeguards" instruction is about content and I have not put any content filter
anywhere near this. If you want it env-settable anyway, that is your call to make and I will do
it; I am not making it silently.

---

## Rewrite `/etc/symoneural/api.env` to the `SYMONEURAL_` spellings — root, yours

Every environment variable this repo owns was `SYM_*` and is now `SYMONEURAL_*`
(`SYM_STUDIO_TOKEN` → `SYMONEURAL_STUDIO_TOKEN`, and so on for 96 names). The env file is
root-owned at 0600 and I do not write outside the repo, so this one is yours.

**Nothing breaks if you never do it.** `backend/apps/symoneuralenv.py` runs at startup and
copies each legacy name onto its new spelling, logging a deprecation notice naming every
variable it promoted. It **copies** rather than moves, deliberately: this repo spawns children
that inherit its environment — `llama-server`, `stable-diffusion.cpp`, the `asicminer` venv,
`gpu-governor.sh` — and some of those still read the old name. So a running process legitimately
carries both spellings at once.

Two consequences worth knowing before you edit the file:

1. **The new name wins when both are set**, and if the two values differ you get a WARNING
   naming both. So you can migrate one line at a time and see it happen.
2. **Adding the new line is enough; you do not have to delete the old one in the same pass.**
   `promote()` never overwrites a name that is already set.

    sudoedit /etc/symoneural/api.env      # rewrite SYM_* -> SYMONEURAL_*
    sudo systemctl restart symoneural-api

That restart is the same one already owed above. When it is done, tell me and I will delete the
promotion shim and the legacy header reads — both are marked in the code as things to remove
once the deployed API is known to read the new names.

## `X-Sym-Token` → `X-Symoneural-Token`: what to expect at deploy

Seven surfaces read this header. All seven now read **both** names, new first. The browser
senders and `bin/symoneural-cli` send **both** as well, which is deliberate and worth one
sentence of explanation: `site/` is deployed by `scripts/deploy.sh` and the API is restarted by
`systemctl`, two separate commands, so there is a window in which one side is new and the other
is not — and it can be either side, depending on the order you run them. Reading both on the
server covers a browser holding a cached copy of the old JavaScript; sending both from the
client covers fresh JavaScript talking to an API you have not restarted yet. Together the deploy
is order-independent, which it was not before.

The studio cookie is the one with teeth. `sym_studio` is now `symoneural_studio`, it is read
under both names and minted only under the new one, and the reason is in
`backend/apps/symoneuralstudio/gate.py:33-41`: it is the *only* credential the framed ComfyUI
editor's sub-resource requests carry, so a tab open at the moment of deploy would have 401'd
every asset it loads. That is the seven-aborted-requests failure `tests/studio.mjs` exists to
catch.

## NOT MINE — LIKELY GARRETT'S: `backend/apps/cryptominer/SyMon_MinerGPUWorker_PROD_20260102-1818/`

A self-contained Windows GPU-worker export dated 2026-01-02, with its own `src/config.py`,
`src/worker.py`, `run_worker.py`, `requirements.txt`, `.env.example`, `README.md` and
`tree.txt`. Its only appearance in this repo's history is `68c8450 Rename apps: calc ->
ravencalc, miner -> cryptominer`, which moved it without touching its contents.

I have **excluded it from every rename** — the env sweep, the docs sweep, and the header
tripwire, which names it as an exemption with this reason attached. It reads its own
`SYM_MINING_ENABLED`, `SYM_MINER_CMD`, `SYM_GPU_INDEX`, `SYM_STATUS_INTERVAL_S`,
`SYM_LOG_LEVEL`, `SYM_WORKDIR`, `SYM_STATUS_FILE` and `SYM_NVIDIA_SMI` from its own
`.env.example`, and it is a different program: renaming its variables from this side would
break its own reader against its own config file to satisfy a naming rule that is about this
codebase.

If it is yours and current, it wants its own migration on its own schedule. If it is a dead
export, say so and I will delete it — which would also let the tripwire exemption go.

## New surface to build: `symoneuralcredentials`

**Attribution, corrected 2026-08-20.** This section was headed "From Garrett" and it should
not have been. What is Garrett's is one sentence, verbatim: *"i want a symoneural agent
created to automate this process once user proves its not a bot."* Everything below it — the
layout, the three-layer gate, the flow list, the output path — I wrote, and heading it with
his name put my design decisions under his authority in the one file whose entire job is
telling the two apart. Two of those decisions then turned out to violate rules he set, which
is exactly the failure that mis-attribution hides.

A symoneural agent that automates the BYOK credential-setup flow currently handled by
`credential_setup.py`, gated on a human-proof check so a leaked token cannot trigger it.

**Corrected by the reviewer, 2026-08-20**, on three points, all of which stand as the built
shape: no DOM secret-scraping (navigate and click, human pastes); output inside the repo at
`run/credentials.env`; and the post-`d3a4040` env spellings. The rejected reasoning is kept
in place rather than deleted, so the record shows what was considered and thrown out.

### Why this surface exists

`credential_setup.py` today opens six provider consoles in a browser and pauses for manual
paste. It works, but the automation stops at "user pastes token". This new surface pushes it
one step further: once the user has proven a live human is at the keyboard, the agent drives
the already-logged-in Chrome via `claude-in-chrome` — navigates to each provider's console and
clicks Create Key — and then **prompts the operator to copy the key out of the modal and paste
it into the terminal.** The agent automates the navigation and the click-through. It does not
touch the secret. Login and MFA stay on the human's side — that wall is provider-enforced and
correct.

*Rejected: DOM extraction.* The original design read the raw token out of the element the
provider renders it in, which is wrong twice over. It hangs the surface on a CSS selector that
dies the day a provider redesigns their token page — six flows, six independent tripwires, each
failing at the worst possible moment. And it contradicts the source script's own docstring,
which says it does not scrape a secret out of an authenticated dashboard. Automating the
navigation is the durable half; the paste stays manual, because a human reading a modal is the
one step that never breaks.

### The security shape, three layers

1. **Environment gate** — same pattern as Studio/Coder/Project/Rack. Requires
   `SYMONEURAL_CREDENTIALS_ENABLED=1` and `SYMONEURAL_CREDENTIALS_TOKEN`. Both set via
   `scripts/enable-surfaces.sh credentials`, a **seventh** arm that script does not currently
   have; adding it is part of this work. (The original said "sixth" and used the `SYM_` prefix
   — both stale. Task 19 renamed every `SYM_*` to `SYMONEURAL_*` at `d3a4040`, and at
   `c129d81` the script arms six surfaces and names seven it cannot switch.)
2. **Token gate** — `X-Symoneural-Token` header on every `/api/credentials/*` call. Same
   `hmac.compare_digest` pattern as the other surfaces, UTF-8 encoded.
3. **Human-proof gate** — the new layer. `POST /api/credentials/run` refuses without a
   fresh, one-shot proof-of-humanity token. Two mechanisms, in order of preference:

   - **Preferred: PolKit dialog via `pkexec`.** `POST /api/credentials/challenge` runs
     `pkexec /usr/bin/true` in a subprocess; the desktop password dialog pops on the
     operator's session; on success returns a short-lived proof token (60s TTL, one-shot).
     Cryptographically bound to the login session by PolKit — a remote attacker cannot
     trigger this.
   - **Fallback (no PolKit / no desktop session): terminal challenge.** Challenge renders a
     random 6-word BIP-39 phrase in the operator's *terminal only* (never HTTP-returned). The
     operator types it back to `/verify` within 30 seconds. Weaker than PolKit — an attacker
     with `sudo` shell access could read it — but stronger than nothing.

   Each proof grants exactly one `/run` invocation. No caching, no re-use.

### Layout

    backend/apps/symoneuralcredentials/
    ├── __init__.py         # LABEL, DEFAULT_PROVIDER_SET, status()
    ├── gate.py             # env/token gate, same shape as apps/symoneuralstudio/gate.py
    ├── proof.py            # pkexec preferred, terminal-BIP39 fallback; one-shot token
    ├── driver.py           # claude-in-chrome wrapper: navigate + click only, never reads a secret
    ├── flows/
    │   ├── __init__.py     # registry
    │   ├── anthropic.py    # modal shows key once, closes on outside-click: warn, then await paste
    │   ├── google.py       # two values: API key + Search Engine ID (cx)
    │   ├── github.py       # prefer `gh auth token` if gh installed, else navigate + paste
    │   ├── huggingface.py  # prefer `huggingface-cli` if installed, else navigate + paste
    │   ├── serpapi.py
    │   └── bing.py         # LEAVE UNIMPLEMENTED with a placeholder — Microsoft retired the standalone API in 2025; note in the file, no flow
    ├── writer.py           # writes run/credentials.env at mode 600, preserving existing values
    ├── routes.py           # /api/credentials/{challenge,verify,run,state}
    ├── README.md
    └── test_credentials.py

### Wire-in points

- `scripts/enable-surfaces.sh`: add the `credentials)` arm alongside the **six** it now has
  (`asic coder gateway project rack studio`, measured at `c129d81`; the original "five" was
  stale before `asic` landed). `backend/apps/test_enable_surfaces.py` pins both directions, so
  adding the arm moves `CREDENTIALS` out of the cannot-switch set and the literal there must
  move with it in the same commit — that test fails on the way in, by design, exactly as it
  did for `discovery`.
- `backend/api.py`: `Unit(**credentials.status())` on the rack, following the pattern of every
  other unit. This becomes the fourteenth rack row.
- `.claude/HANDOVER.md` §0 and the audit block at :1020: update the rack count to 14 with
  the same SHA-anchored discipline the review has been enforcing.

### Hard limits — do not try to route around these

- **No login automation.** Provider bot-detection + MFA is intentional. Cannot be bypassed
  without violating ToS and getting accounts flagged. The agent pauses if a login page is
  shown and asks the operator to log in.
- **No MFA interception.** Same reason.
- **No storing OAuth refresh tokens.** They expire; when they do we're back at "user logs in".
  This surface never claims a session survives past its one-shot proof.
- **No writing outside the repo.** Default path is `run/credentials.env`, mode 600,
  overridable by `SYMONEURAL_CREDENTIALS_FILE`; the writer refuses any resolved path outside
  the repo root. The original said "outside `$HOME`" with a `~/providerapikeys.txt` default,
  which the reviewer caught as a violation of the standing no-writes-outside-the-repo rule.
  `run/` is already ignored at `.gitignore:25` and holds nothing tracked (`git ls-files run/`
  is empty), so the ignore requirement below is met by the path choice, not by a new rule.
- **No git-tracking the output file.** `git check-ignore run/credentials.env` already returns 0
  via `.gitignore:25`; a test asserts it, so the guarantee survives an edit to `.gitignore`.
- **Flat `KEY=VALUE` serialization, not JSON.** `symoneuraldiscovery` reads this file and its
  `envfile.py` already parses exactly that shape. A JSON structure invites schema drift between
  writer and reader for no gain — the file has one level and always will.

### Regression tests the surface must carry

- The token gate answers 401 with the right shape on a bad or missing token, per the exp/gate
  pattern with UTF-8 encoding (do not repeat the non-ASCII TypeError bug the review fixed).
- A run without a fresh proof token answers 403 with `human_proof_required`.
- A proof token used twice answers 403 the second time with `proof_already_spent`.
- A proof token older than TTL answers 403 with `proof_expired`.
- The writer refuses paths outside the repo root, mutation-checked by pointing at
  `/etc/passwd` and asserting refusal.
- `git check-ignore` returns 0 (ignored) for the default output path.
- `enable-surfaces.sh credentials` sets the two env vars and the "cannot switch" list no
  longer contains `credentials`.
- For each provider flow: the console URL and the create-button selector are documented in the
  file, and a test asserts those strings are what the docstring claims. The blast radius is
  smaller than the original design's — a stale selector costs the operator one manual click,
  not a silently-empty secret — but a wrong URL still sends someone to the wrong page.

### Order of build

1. Skeleton + gate + proof + writer + `enable-surfaces.sh` arm + first flow (Anthropic —
   already has a validation call in the current script, easiest end-to-end proof).
2. Rack row + HANDOVER update to fourteen units + SHA-anchored count in the pytest row.
3. Remaining flows one by one, each with its own commit and a mutation-check.
4. `bin/symoneural-cli credentials` subcommand — one command, drives the whole flow from a
   terminal.

Test-suite target after this lands: +N tests over the **1267** baseline measured at `c129d81`
(the original said 1118, stale by two surfaces). Do not carry that figure forward either —
re-measure at the new SHA and record the method beside it.

### One open question I am not deciding alone

The corrected flow is terminal-bound: the operator pastes the key into a prompt. That sits
badly with `POST /api/credentials/run` as a request/response endpoint, because there is no
paste inside an HTTP round-trip — and if the key ever did travel in a request body we would
have swapped a fragile DOM read for something worse. So I am building the surface with the
secret confined to the terminal: `bin/symoneural-credentials` drives the flow,
`/api/credentials/{state,challenge,verify}` carries the gate and the human-proof, and no
endpoint returns or accepts a credential. The rack row, the `credentials)` arm and all three
gate layers land as specified. If `/run` was meant to be a real minting endpoint, say so and I
will build it — but it wants a deliberate yes, because it is a key-creating endpoint on a
process with a public IP, and three gates in front of it does not change what it is.

---

## Symoneural_backups + Desktop archives — provenance answered, BLOCKED on your sign-off

The reviewer asked where this task came from and whether it duplicates `.symoneural-full/`.
Answers, with the citation, because "I think Garrett asked" is not a source.

**It has a real source.** A genuine typed prompt from you, not a summary and not a reminder:
transcript `~/.claude/projects/-home-google/a541463a-f909-4f7a-8bee-92d2b6832113.jsonl`
line 12257, uuid `3289acca-ec94-4860-be35-99f64de9e27d`, `2026-08-19T22:07:08.238Z`. Verbatim:

> when you are completely done updating the project and everything is installed and tested
> for all ON DISK then make me one more folder in /home/google/Symoneural_backups with all
> the repos folders files .deb .tar.gz meta-yocto-customlayers and trade secrets THEN ONCE
> EVERYTHING AND I MEAN EVERYTHING for the symoneural repo project in /home/google/symoneural
> is copied/migrated/etc into /home/google/Symoneural_backups then compress
> /home/google/Symoneural_backups to symoneural-allv3.tar.gz and symoneural-allv3.zip to
> /home/google/Desktop and give me another way to accomplish sudo scripts/deploy.sh --prune
> [...] or something like symoneural upgrade

That one prompt is the origin of four list items: #14 (cut the artifacts), #15 (stage the
folder), #16 (the two Desktop archives) and #11 (`symoneural upgrade` as the `deploy.sh
--prune` replacement). Only #11 is startable by me; the other three are not, for the reasons
below.

**It is NOT the same concept as `.symoneural-full/`.** That vault is yours, written by you,
and holds the working tree. This is a staging directory for *shipping* artifacts — repos,
`.deb`, `.tar.gz`, the yocto layers — and then two compressed copies on the Desktop. Different
purpose, different contents, different audience. So the duplicate-path resolution does not
apply and the task should not be dropped. It should be blocked, and it is.

**Three things need your explicit go-ahead before any of it happens. I am not proceeding.**

1. **It writes outside the repo, twice.** `/home/google/Symoneural_backups/` and
   `/home/google/Desktop/`. My hard rule is "NO filesystem writes outside
   /home/google/Symoneural/. Not /etc, not /var, not $HOME." Your prompt post-dates that rule
   but does not name it, so I am treating the instruction as real and the rule as unwaived
   rather than picking whichever reading lets me start. Two separate exceptions, please, or
   an in-repo staging path I can use instead.

2. **"and trade secrets" points at the three protected artifacts.** That is
   `training/corpus.jsonl`, `training/build_dataset.py` and `training/adapter/` — the ones
   CLAUDE.md says never to copy, never to serve, never to quote. My standing rule is not to
   touch them at all. Copying them into a staging folder is a you-action; I will not be the
   process that moves those bytes. Everything else in the archive I can assemble.

3. **The archive would carry live secrets, and this is already a logged finding.** Anything
   containing `.git` carries `backend/apps/remix/.env`, which is tracked with four non-empty
   secret-shaped values (see the reconcile entry at the top of this file). "Secrets in a
   tarball" was logged as a risk; a `symoneural-allv3.zip` sitting on the Desktop is that
   risk actually realized, in the most portable form there is. Rotation was already queued for
   you. Do that first, or accept it in writing, or let me build the archive from
   `git archive` instead so no history and no `.env` ride along.

**It is also not due yet, by its own terms.** The prompt gates the whole thing on "when you
are completely done updating the project and everything is installed and tested for all ON
DISK". That is currently false: audit items 7-12, 15, 18 and 19 are open, #11 is mid-build,
and nothing is installed by me because installing needs your sudo. So even fully authorized,
this is the last thing that happens, not the next one. Sequenced after, not before.


---

## MERGED-EXECUTION-PLAN (2026-08-20)

Saved verbatim from the reviewer's prompt so it survives any compact or restart. On resume:
re-read this, then CODER-TASKS.md for position.

> This prompt is the complete remaining work plan. Execute it top to bottom. Work ONE item at a
> time, commit between items, and update /home/google/Symoneural/CODER-TASKS.md at EVERY state
> change — it is the canonical task list from now on; the widget is just a viewport. Do not
> reorder, do not batch, do not start an item before the previous one is committed.
>
> ════════ PHASE 0 — BOOKKEEPING (minutes, no deep thinking) ════════
>
> 0.1 git log --oneline: fill the three "not in context" SHAs in CODER-TASKS.md (#17, #18,
>     #29, #30).
> 0.2 Reconcile #12 against audit item 6 (yocto family landed at 11dc426): mark completed with
>     that SHA, or state the precise remainder and fold it into 1.2's commit.
>
> ════════ PHASE 1 — THE v3 SNAPSHOT (do not skip ahead of this) ════════
>
> 1.1 (#13) Run all four suites at HEAD: pytest with the two mandatory --ignores,
>     frontend.mjs on a spare port, tuner_failpaths.mjs, tuner_watch.mjs. Record every count
>     with SHA + command in HANDOVER's suite row and CODER-TASKS.md. Anything red gets fixed
>     BEFORE proceeding — v3 is cut from a green tree only.
>
> 1.2 (#11 remainder) Write audit item 8's leak-guard test: stage a payload containing a fake
>     .env, assert build-deb.sh exits 1 naming the path, mutation-check by removing the guard.
>     Then commit build-deb.sh and build-apt-repo.sh. Mark audit item 8 with the SHA.
>
> 1.3 (#14) Cut the v3 artifacts (.deb + repo tar.gz) at the tested SHA (re-run pytest quickly
>     if 1.2 moved HEAD). Record artifact names, sizes, and source SHA in CODER-TASKS.md.
>
> 1.4 (#15) Stage /home/google/Symoneural_backups with HARDLINKS (cp -al) — everything
>     including .git and trade secrets. AUTHORIZED: owner's local backup; the training-files
>     rule forbids EDITING, not archiving. Include the v3 artifacts. Write an index file at the
>     stage root (contents + sizes). Add SECRETS-INSIDE.txt listing every sensitive path inside
>     (training/corpus.jsonl, training/build_dataset.py, training/adapter/,
>     backend/apps/remix/.env — key names and lengths only, NEVER values) plus the line:
>     "This archive must not leave this machine unencrypted."
>
> 1.5 (#16) From the stage, produce symoneural-allv3.tar.gz and symoneural-allv3.zip on
>     /home/google/Desktop under nice/ionice. Verify both: tar -tzf and unzip -l each list
>     SECRETS-INSIDE.txt and the index. Record both sizes + sha256sums in CODER-TASKS.md.
>
> 1.6 MILESTONE CHECKPOINT — do not stop, but write it down: one line in HANDOVER §0
>     ("v3 snapshot cut and archived at <SHA>"), full record in CODER-TASKS.md (suite counts,
>     artifact sizes, checksums), and append a summary block to
>     /home/google/Symoneural/GARRETT-INBOX.md headed "## v3 MILESTONE" so Garrett and the
>     reviewer can verify while you continue. Everything after this line is v4 work on a
>     safely archived base.
>
> ════════ PHASE 2 — THE RESTRUCTURE TRAIN (one item per iteration, this exact order) ════════
>
> Every item follows the same skeleton: implement → regression test that mutation-fails
> without the change (or the honest reason none is warranted) → re-run whichever suite covers
> the touched surface and record the count with SHA → update the audit surface if a numbered
> item closes → commit → update CODER-TASKS.md → next item.
>
> 2.1  (#31) Serve the studio render from disk instead of proxying GET /view. The repo's own
>      rule: renders are API output served by GET /api/gen/<name>; studio's /view proxy is the
>      outlier. Re-run tests/studio.mjs through the NEW path.
> 2.2  (#26) Route rack applications under /livestack/<name> instead of /app.html. Preserve
>      old URLs as 301s so nothing published breaks.
> 2.3  (#27) Fix Live Stack typography and promote the app brand icons.
> 2.4  (#28) Rename Symoneural Tuner & Guide to Symoneural IPTV; merge Sigils into Chat.
>      Rack row changes → update test_status_rack.py and the HANDOVER count in the same commit.
> 2.5  (#25) Apply the SymonSays naming system across code and site. Sweeping — split into
>      sub-commits per surface; site pages regenerate through their generators then
>      build_cachebust.py LAST.
> 2.6  (#21) Name the agent harness symoneural-harness.
> 2.7  (#22) Demote exp from a rack row to a symoneural-studio plugin. Rack count changes:
>      tripwire test + HANDOVER in the same commit.
> 2.8  (#23) Take reinforce out of the live stack and into symoneural-studio. Same rack-count
>      discipline.
> 2.9  (#20) Rebrand ComfyUI as symoneural-ui, keeping GPL-3.0 compliance. BIG — break into
>      sub-tasks in CODER-TASKS.md first (license audit, naming sweep, proxy paths, page,
>      tests), then execute sub-task by sub-task with commits between.
> 2.10 (#24) Build symoneural-invest: hardware configurator for server upgrade decisions.
>      New surface — follow the established app pattern (gate.py with SYMONEURAL_* vars,
>      routes, status() rack row, tests, enable-surfaces.sh arm + its bidirectional test).
>
> ════════ PHASE 3 — REMAINING QUEUE ════════
>
> 3.1 The symoneuralcredentials surface per the corrected spec in GARRETT-INBOX (terminal-bound
>     paste flow, run/credentials.env mode 600, SYMONEURAL_* vars, pkexec/BIP-39 human proof,
>     rack row, enable-surfaces arm). The open question in that spec (whether /run exists as an
>     HTTP endpoint) is answered: NO — CLI-driven only, no endpoint returns or accepts a
>     credential. Build it that way.
> 3.2 Remaining audit-surface items not already closed above (7 — CLI tests; 10 —
>     docs/upgrading.md; 11 — yocto README SDK matrix; 12 — test_studio.py:24 misattribution;
>     18 — LICENSE ref; 19 — BBFILE_PATTERN). Then item 15 (archive the review documents) LAST.
> 3.3 Re-run all four suites at final HEAD, record with SHA, update HANDOVER §0.
> 3.4 Write /home/google/Symoneural/AUDIT-DONE-2026-08-19.md: final SHA range, final counts
>     with method, all items grouped by category, any won't-fix with reason. Then STOP.
>
> ════════ STANDING RULES (carry through every compact) ════════
>
> - NO git push. NO editing training/{corpus.jsonl, build_dataset.py, adapter/} — archiving in
>   1.4/1.5 is the one authorized exception. NO /etc or /var writes. NO printing secret values
>   ever — names and lengths only.
> - Review artifacts (CLOSEOUT, REVIEW-LOG, SWEEP-READY, REVIEWER-INBOX, AUDIT-SURFACE,
>   CODER-STATE, RECONCILE, GARRETT-INBOX, CODER-TASKS) stay uncommitted.
> - Every figure SHA-anchored; never carry a count forward as re-run. Mutation-check every
>   behaviour change. If a comment claims a guard, the guard exists or the sentence goes.
> - Rack-count changes always land with the tripwire test + HANDOVER update in the SAME commit.
> - Read REVIEWER-INBOX.md at the top of each iteration; answer challenges with evidence
>   (file:line, SHA, or transcript UUID).
> - If context runs low: update CODER-TASKS.md + HANDOVER with your exact position, stop
>   cleanly, do not commit half-work. On resume: re-read this prompt from GARRETT-INBOX.md
>   where it is saved as "## MERGED-EXECUTION-PLAN", then CODER-TASKS.md for position.
