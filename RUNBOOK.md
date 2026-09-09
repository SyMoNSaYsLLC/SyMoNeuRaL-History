# RUNBOOK — the SyMoNeuRaL API

Written 2026-09-09 by the commissioning pass. For someone who has never seen this box.

Everything here was run and its output read. Where something could not be verified it says
so, rather than telling you what ought to happen.

---

## 0. Sixty seconds: is it working?

```bash
cd /home/google/Symoneural
python3 tools/smoke.py --quick
```

Twelve checks, about ten seconds. Non-zero exit means something is broken, and each failure
names the cause. Drop `--quick` for the full run (adds a real image render and a GPU-lease
concurrency proof, about 40 s).

**As of 2026-09-09 this exits 1, with one failure**, and it is a real defect rather than a
flaky test — see [The public API returns 502](#the-public-api-returns-502). Everything else
passes.

Faster still, if you only want to know whether the API is alive:

```bash
systemctl is-active symoneural-api                          # expect: active
curl -s -o /dev/null -w '%{http_code}\n' localhost:8800/api/status   # expect: 200
```

## 1. What runs here

| unit | state | what it is |
|---|---|---|
| `symoneural-api` | enabled, active | the API. `python3 backend/api.py` on `127.0.0.1:8800`, **loopback only** |
| `symoneural-web` | enabled, active | the public web server on `:80`/`:443`, serving `/var/www/symoneural` |
| `symoneural-gateway` | **disabled, inactive** | a proxy hop on `:8000`. Off by design: no contract, no wallet, no key material |
| `symoneural-progress` | user unit, timer **disabled** | regenerates `run/progress.html`. Not on a schedule — see §7 |
| `symoneural-deploy` | **never installed** | publishes `site/` to `/var/www/symoneural`. See §7 |

The public request path:

```
internet -> :443 symoneural-web -> /var/www/symoneural        (static files)
                                \-> :8000 gateway -> :8800    (/api/*, /v1/*, /swagger-ui*, /api-docs/*)
                                \-> :8800 API directly        (/docs, /openapi.json, sections)
```

**The `:8000` hop is disabled**, which is why `/api/*` currently fails from outside. The API
is fine; the route to it is not.

## 2. Install

**Use one installer.** Four exist and their unit headers disagree about which owns them —
`ops/INSTALLERS.md` has the adjudication. The authoritative one is:

```bash
sudo ops/install-runtime.sh --dry-run     # read this first, it changes nothing
sudo ops/install-runtime.sh
```

It substitutes `@@ROOT@@`, refuses on an unsubstituted placeholder, refuses a unit still
naming `/yocto`, backs up what it replaces, and rolls back on failure.

**Before you run it, know this:** it also installs `symoneural-deploy.service`, which has
never been installed on this box. Whether that unit should be live is undecided (§7).

`scripts/install-service.sh` is deprecated and refuses to run. Don't use it.

The `--user` progress units have only one installer:

```bash
ops/install-service.sh          # the only thing that handles ~/.config/systemd/user/
```

### Dependencies

```bash
python3 tools/preflight.py      # exit 0 means every hard requirement is present
```

It checks all 21 start-time dependencies, the one *serve*-time dependency, and four
structural prerequisites, then prints the `apt install` line for anything missing. There is
**no virtualenv on the serving path** and all 20 loaded distributions are dpkg-owned — see
`docs/ops/SERVING-MANIFEST.md`, which is generated from measurement.

Optional surfaces (`cupy`, `torch`, `pyasic`, `playwright`, …) being absent is **not** a
failure; it means that surface is unavailable. Ten are absent here and the API serves fine.

## 3. Start, stop, and hold

```bash
sudo systemctl start   symoneural-api
sudo systemctl restart symoneural-api      # after changing backend/api.py
sudo systemctl stop    symoneural-api      # UNTIL THE NEXT BOOT ONLY
```

**A `stop` is not a hold.** The unit is `enabled`, so a stopped service comes back at the
next boot. That has already caused confusion once — a deliberate hold was in force, the box
rebooted, and the API started itself. For a hold that survives a reboot:

```bash
sudo systemctl disable --now symoneural-api    # a real hold
sudo systemctl mask    --now symoneural-api    # a hard hold: not startable even by hand
```

Verify with **both** fields, because either alone misleads:

```bash
systemctl is-active symoneural-api ; systemctl is-enabled symoneural-api
```

`inactive` + `enabled` is **not a hold**. Full detail and how to record the reason:
`ops/SERVICE-HOLD.md`.

**All of the above needs root.** As the `google` user these commands *hang* waiting for a
polkit authentication that never arrives — they do not error, they hang. If `systemctl stop`
appears to freeze, that is why; Ctrl-C and use `sudo`.

## 4. Verify

```bash
python3 tools/smoke.py                       # the whole thing
python3 tools/preflight.py                   # dependencies only
python3 tools/route_audit.py --list          # the 159 registered routes + OpenAPI cross-check
python3 tools/gpu_lease_proof.py             # prove two GPU requests cannot both load weights
python3 -m pytest backend -q                 # the unit suite -- 13m44s, see the caveat below
```

**The pytest suite takes about 14 minutes**, not the ~5 minutes older notes claim. One test
runs `tools/build_restore_manifests.py` twice and each pass reads ~48 GB to hash artifacts.
It is not hung. It also **rewrites six tracked generated files** as a side effect, so
`git status` will be dirty afterwards; that is a re-measurement, not damage.

Expect **4 failures** at time of writing, all pre-existing and none related to the API —
they are hygiene assertions about the storage migration (`test_no_claude_dependency`,
`test_references_boundary`, `test_no_external_source_dependency`, `test_path_fragility`).

## 5. Read the logs

```bash
journalctl -u symoneural-api -f              # follow
journalctl -u symoneural-api -b              # this boot only
journalctl -u symoneural-api -n 100 --no-pager
```

A healthy start looks like this, and takes about **1.2 s**:

```
promoted 6 legacy env var(s) to the SYMONEURAL_ prefix: SYM_CODER_ENABLED, ...
INFO:     Started server process [1506]
symoneural api on 127.0.0.1:8800 (loopback only)
caps: prompt<=100000 chars, queue 24, rate limited: ravencalc 240/min 6000/hr, ...
dispatchos surface enabled; store at .../run/dispatchos.db
project surface enabled; store at .../run/project/store.db
INFO:     Application startup complete.
```

**The `promoted 6 legacy env var(s)` line is normal**, not a warning to act on today. It also
tells you to "Rewrite them in `/etc/symoneural/api.env`" — **that file does not exist and is
not where the configuration lives.** Ignore that instruction; see §6.

**Two startup lines you should notice by their absence.** If
`dispatchos surface enabled` and `project surface enabled` are missing, the config file is
gone and those surfaces are **silently disabled**. Nothing logs a disable.

## 6. Configuration — three paths, one of them real

| path | reality |
|---|---|
| `run/config/api.env` | **the real one.** Mode 0600. Read by `runtimeconfig.py:126` |
| `/etc/symoneural/api.env` | **does not exist.** The unit tolerates that (`EnvironmentFile=-`) |
| `run/api.env` | **does not exist.** Named in `restore/manifests/SERVICES.tsv` |

Editing `run/config/api.env` then restarting is how you change surface switches and tokens.
It holds credentials — do not print it into a terminal others can see.

There is also a **root-owned drop-in** at
`/etc/systemd/system/symoneural-api.service.d/10-surfaces.conf` that overrides the unit and
**is not in this repository**. Nobody has read it (it needs root; `systemctl cat` refuses it
too), so the installed configuration is currently not reproducible from Git. To capture it:

```bash
sudo ops/commission-collect.sh              # read-only; writes only to review/.../root-facts/
```

## 7. Known problems

### The public API returns 502

**Symptom.** `https://symoneural.com/api/status` → 502. `http://127.0.0.1:8800/api/status`
→ 200. Same for `/v1/*`, `/swagger-ui*`, `/api-docs/*`. Static pages and `/docs` are fine.

**Cause.** The Caddyfile routes those four path families to `127.0.0.1:8000`
(`/etc/caddy/Caddyfile:51,88,94,97`), and `symoneural-gateway` — which listens there — is
disabled by design. Nothing is listening on `:8000`. The repo and installed Caddyfiles are
byte-identical, so this is intended configuration, not drift.

**Consequence.** Every documented surface — chat, image, ravencalc, remix, status — is
unreachable from outside this box, while working perfectly on `:8800`.

**Fix — a decision, not a repair.** Either:

- point those four blocks at `127.0.0.1:8800` and drop the gateway hop, or
- enable the gateway (`sudo systemctl enable --now symoneural-gateway`), which needs the
  contract, wallet and key material its own note says it lacks.

Not done by commissioning, because it decides whether the gateway is part of the product.

### The crash-loop protection is not in force

`systemctl show symoneural-api -p StartLimitIntervalUSec` reports **`10s`** — systemd's
default — not the 120s the template intends. The installed unit still has `StartLimit*` under
`[Service]`, where systemd ignores it and says so. The repo template was fixed on 2026-09-03;
the running system never received it.

```bash
sudo ops/commission-apply.sh              # DRY RUN, prints and changes nothing
sudo ops/commission-apply.sh --apply      # reinstalls the units, reloads, restarts
```

That script also installs `needrestart`, adds a GPU-mismatch apt hook, and carries the
CUDA-pin decision behind `--with-cuda-pin`. It is idempotent, backs everything up to
`/var/backups/symoneural-commission`, and does the disruptive step last.

### A driver upgrade needs a reboot, and used to say nothing

If `dist-upgrade` replaces the NVIDIA driver under a running kernel, every GPU path fails and
**no restart fixes it.** `/api/status` now reports this honestly:

```bash
curl -s localhost:8800/api/status | python3 -c 'import json,sys; g=json.load(sys.stdin)["gpu"]; print(g.get("driver","(no driver field: this service predates the change -- restart it)"), "-", g.get("driver_detail"))'
```

`mismatch` means **reboot**. `ravencalc` keeps serving through it — a GPU fault is not a
calculator outage. If the field is missing entirely, the running service predates the change;
restart it.

### `apt autoremove` is safe, but do not remove `cuda-libraries-dev-13-3`

`autoremove` currently removes nothing. But `symoneural-diffuse` hard-pins **CUDA 13.3** in
its RUNPATH, and the only thing keeping `cuda-cudart-13-3` installed is a manual mark on
`cuda-libraries-dev-13-3`. Remove that *dev* package and `autoremove` becomes free to take
the runtime the image engine needs.

Note also that the same binary loads **13.4** in an interactive shell (because
`LD_LIBRARY_PATH` overrides RUNPATH) and **13.3** under systemd. Hand-testing the image
surface does not test what production runs.

### The progress page is stale by default

`symoneural-progress.timer` is a `--user` unit and is **disabled**, so `run/progress.html`
only updates when someone runs it. Anything read off that page — including the barrier count
`CLAUDE.md` tells you to read there — is as old as the last manual run.

```bash
python3 tools/build_intake.py && python3 tools/archive_tasks.py && python3 tools/build_progress.py
```

### The public document root is published by hand

`symoneural-deploy.service` publishes `site/` → `/var/www/symoneural` and has **never been
installed**, so nothing republishes on boot. The live root was last written 2026-09-01.
It is not meaningfully stale (`index.html` and `chat.html` are byte-identical to the repo,
and no referenced asset is missing) but the mechanism is manual:

```bash
sudo bash scripts/deploy.sh --prune
```

## 8. Failure modes, measured

Each of these was deliberately caused and the result read. `fail-fast` means it refuses to
start and says why; `fail-late` means it starts clean and fails later, which is worse.

| break | behaviour | what you see |
|---|---|---|
| `scripts/gpu-governor.sh` missing | **fail-fast** | `AssertionError: .../gpu-governor.sh is not a file` |
| `SYMONEURAL_PORT` not a number | **fail-fast** | `ValueError: invalid literal for int()` |
| `run/config/api.env` missing | **fail-late** | starts, serves 200, and **silently disables** four surfaces. The only signal is two missing log lines |
| `run/` unwritable (0500) | starts fine | harmless while state files exist; would break a **first** start on a fresh box, where they must be created |
| a model file missing | **fail-late** | starts clean; fails at request time. `MODELS` paths are never `stat`ed at import |

To re-run any of these safely — they use port 8801 and never touch the live service:

```bash
python3 tools/failure_modes.py --baseline        # a clean foreground start
python3 tools/failure_modes.py                   # all five breaks, each restored in a finally
```

If that harness ever dies mid-test, the recovery procedure is
`review/commissioning-20260909/PHASE3-RECOVERY.md`. One command tells you whether anything is
outstanding:

```bash
find /home/google/Symoneural -name '*.commission-bak' -not -path '*/.git/*'
```

No output means nothing is broken.

## 9. Roll back

**A unit change** — every apply backs up first. Note the backup directory is created by
the first `commission-apply.sh --apply`; if it does not exist yet, nothing has been applied
and there is nothing to roll back:

```bash
ls /var/backups/symoneural-commission/     # "No such file or directory" = nothing applied yet
sudo cp /var/backups/symoneural-commission/symoneural-api.service.<stamp>.bak \
        /etc/systemd/system/symoneural-api.service
sudo systemctl daemon-reload && sudo systemctl restart symoneural-api
```

**A code change** — the commissioning work is on a branch, so `main` is untouched:

```bash
git log --oneline main..commission-phase1-20260909    # what commissioning changed
git checkout main                                     # abandon all of it
git revert <sha>                                      # or undo one commit
sudo systemctl restart symoneural-api
```

**The whole service** — if it will not start and you need the site up: the static site is
served by `symoneural-web` and is **independent of the API**. Visitors keep getting pages;
only the surfaces stop. There is no need to rush a bad fix.

## 10. What has never been verified on this box

Honesty about the gaps, because the alternative is you trusting something that was never
tested:

- **`systemctl start` / `stop` / `restart`, and a reboot.** All polkit-gated for the service
  user, so commissioning could not run them. The boot path *is* proven, by the boot that
  happened on 2026-09-09.
- **`ExecStopPost`** — the `pkill` of `llama-server`/`sd-cli` on stop has never run. It is
  `-` prefixed, so a failure would be silent.
- **The effective `StartLimitIntervalUSec=2min`** after the fix. Currently 10s.
- **The drop-in's contents**, and therefore the full effective environment.
- **63 POST / 5 DELETE / 3 PATCH / 2 PUT routes**, not fired at a live service. 20 auth-gated
  GETs correctly refuse; whether they work when authorised is unknown.
- **Eight surfaces that return 503 by design** — train, voice, gateway, gpuminer, asicminer.
  Correctly disabled; their working behaviour is untested, and some need absent hardware.
- **Every browser/UI suite.** `docs/ops/MEASUREMENTS.md` records that they cannot run here —
  there is no system Chrome.
- **A fresh-box install.** The dependency manifest is measured, but nobody has installed those
  packages on a bare machine and got a working API.
