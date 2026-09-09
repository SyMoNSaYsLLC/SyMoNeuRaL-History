# HANDOFF — symoneural.com

**Canonical handoff document.** Migrated from `docs/HANDOFF.md` on 2026-09-08. The
rules that cite it now point here; the provider-specific path is retired and untracked.
Current verified state lives in `ProjectStatus.md`; this file records what will bite the
next person.

**Next executor: any coding agent or person.** The provider-specific "next executor: Claude"
language below is historical and is superseded by this line.


## Current handoff — 2026-09-08 (late), restore control plane + disk reckoning

**Next executor: any coding agent or person.** The next task is **the coder training corpus**,
and it does not exist yet -- see item 5 below. This entry supersedes the older pointers
preserved further down.

**State at handoff.** HEAD `2eb03803`, branch main, tree clean, 0 staged, 0 stashed. Suite
**2400 passed / 0 failed / 56 skipped**, recorded in `run/SUITE-LAST.txt` and read from there
rather than typed. `RESTORE_VERIFY=PASS` over 81 rows. `symoneural-web` active and enabled
serving :80/:443; **`symoneural-api` is STOPPED** at the owner's request (enabled, so a reboot
restores it); `symoneural-gateway` inactive and disabled, source intact. Full detail in
`ProjectStatus.md` under *Current state → 2026-09-08 (late)*; this entry says only what will
bite you.

**What will bite you.**

1. **11 of the 14 restore smokes need `symoneural-api` running.** It is stopped. Start it
   (`sudo systemctl start symoneural-api`) before `restore/symoneural-restore smoke all`, or
   read the canonical 14/14 capture at `.private/rehearsal/SMOKE-RUN-r20260908.txt`, taken
   while it was up.

2. **The installed `symoneural-api` and `symoneural-gateway` units are STALE against their
   templates.** `StartLimitIntervalSec`/`StartLimitBurst` still sit in `[Service]`, where
   systemd silently ignores them -- so the crash-loop protection their own comments describe
   has never once applied. `SERVICES.tsv` records this as DIVERGED. Reinstalling alters a
   production service and that authority was not granted; it is the owner's call.

3. **`symoneural-web` has no fallback.** It owns :80 and :443 and `caddy.service` is
   *disabled*. The restore plan must never `systemctl start caddy` -- `symoneural-web.service`
   declares `Conflicts=caddy.service`, so starting the vendor unit makes systemd **stop the
   production web server**. That defect was in RESTORE-ORDER step 90 and is fixed; do not
   reintroduce it. The Caddyfile is configuration consumed by symoneural-web, not a unit.

4. **`/yocto/artifacts` is the only surviving copy** of 248 GB de-duplicated out of `/home`.
   Until it is verified on Drive, do not touch `/yocto`. `YOCTO_WIPE_READY=NO`.

5. **"Train the SyMoNeuRaL Coder" has no corpus.** `training/train_lora.py` is real and good,
   but its own docstring says it turns a stock Qwen into the **admin/persona** model, and
   `training/corpus.jsonl` is 327 identity examples. Running it trains the persona adapter
   again beside the two that exist. A coder corpus is real work that has not been started;
   do not report a persona run as coder training.

6. **`symoneural-diffuse` links an ABSOLUTE CUDA path**, not `$ORIGIN` like the other
   engines: `/usr/local/cuda-13.3/targets/x86_64-linux/lib`. Measured on both the production
   and rebuilt artefacts, so it is by design. A restored machine without CUDA at that exact
   path builds the image engine successfully and then fails to load it at run time -- which
   surfaces only when a visitor asks for an image.

7. **`symoneural-web` needs Go >= 1.25.1.** This host bootstraps 1.24.4 and `GOTOOLCHAIN=auto`
   silently fetches the newer toolchain as a module. With `GOTOOLCHAIN=local` the build
   **fails**. Provision Go explicitly rather than relying on the auto-download.

8. **Rotate the provider credentials.** Seven keys sat at mode 0664 -- world-readable -- and
   are now at `.private/secrets/` 0600. `GITHUB_TOKEN` and `HF_TOKEN` do not expire on their
   own, and the machine they sat on is being decommissioned.

## Earlier handoffs

Everything before 2026-09-08 is in **`docs/handoffs/HANDOVER-ARCHIVE-pre-20260908.md`** —
4,876 lines of accreted history, kept verbatim and clearly marked as
historical. It was split out because a canonical handoff that grows by prepending stops being
a handoff, and because present-tense audit checks cannot tell a 2026-08 statement from a
claim about today. The dated per-window handoffs are in `docs/handoffs/`.
