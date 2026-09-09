# HANDOFF — symoneural.com

**Canonical handoff document.** Migrated from `docs/HANDOFF.md` on 2026-09-08. The
rules that cite it now point here; the provider-specific path is retired and untracked.
Current verified state lives in `ProjectStatus.md`; this file records what will bite the
next person.

**Next executor: any coding agent or person.** The provider-specific "next executor: Claude"
language below is historical and is superseded by this line.


## Current handoff — 2026-09-09, storage reorganisation IN FLIGHT

**Next executor: any coding agent or person.** Read this before touching storage, `/yocto`,
`/mnt/gdrive` or `archive/`. The 2026-09-08 entry below is still accurate about services and
restore; this entry supersedes it only on storage.

**There is a live, unattended migration running.** It moves roughly 295 GB to Google Drive
against a measured ~5 MB/s ceiling, so it takes hours, and it is designed to survive your
session ending.

```bash
python3 tools/storage_reorg.py status          # the ledger
python3 tools/storage_reorg_supervisor.py --status
python3 tools/storage_final_report.py          # every gate, measured, ~10 min
tail -f .private/storage-reorg/latest.log
```

### What will bite you

1. **EXACTLY ONE storage mutation owner may exist.** `tools/storage_reorg.py` is it, and
   `tools/storage_reorg_supervisor.py` keeps one alive across restarts (it starts no
   transfers itself). Before any storage action, check `--status`. **Do not start a second
   owner and do not kill the running one** — an upload interrupted mid-flight costs the
   whole transfer again unless the remote already happens to hold it.

2. **The three old shell pipelines now refuse to run** (`exit 90` unless
   `I_UNDERSTAND_THIS_IS_RETIRED=YES`). That is deliberate: running one creates a second
   owner. Their banners record why the architecture was replaced — orphaned rclone
   children, twice, and one edit-while-bash-was-reading-it.

3. **A running Python process does not see edits to its own operation table.** Operations
   added to `storage_reorg.py` while a run is in flight take effect only on the next
   resume. This already cost something real: the owner that uploaded `/yocto/artifacts`
   started at 05:50:13, before the content-manifest code existed, so it wrote size-only
   manifests. The SHA256 data for all 105,851 files was captured locally *before* the
   sources retired (`.private/storage-reorg/contents/`) and `publish-artifact-manifests`
   publishes it. If you add operations, expect a one-cycle delay.

4. **`/yocto` is itself a git repository** — 11 commits, 254 tracked files, no remote. It
   was an unprotected sole copy of first-party build authority (121 `controlboard` files,
   15 `metrics` readouts, `matrix-run`'s two live scripts). A verified bundle now exists at
   `.private/storage-reorg/yocto-git/yocto-all.bundle` (HEAD `f43caf9f371b`). Its nine
   dirty entries are all untracked directories; the state is recorded beside the bundle.

5. **`/yocto/Archives/sendtodrive.zip` (36.9 GB) must not be deleted yet.** It is the
   recovery source for content manifests of 21 already-uploaded collections, and it holds
   the only *complete* AppleSDK — 38,310 files more than the disk copy had. Retire it only
   when `ZIP_UNIQUE_UNMAPPED_BYTES=0` is actually measured.

6. **`backend/vendor` is NOT dead reference source, despite measuring as reference-only.**
   `backend/apps/test_vendor_sdks.py` (9 tests) is a licence-compliance control that reads
   licence text out of the vendored copy *on disk* and compares it to `PROVENANCE.md`.
   Deleting the tree reclaims 131M and destroys the on-disk half of that control. It is
   preserved to Drive and kept locally; see `docs/reference/VENDOR-CLASSIFICATION.md`.

7. **Two credential-bearing files were found at mode 0664** — `providerapikeys.txt` and
   `credential_setup.py`. Both now sit at 0600 under `.private/secrets/`. **Rotation is
   still outstanding and only the owner can do it**; see
   `.private/secrets/ROTATION-REQUIRED.md`. Two in different trees is a pattern: the umask
   here produces group/world-readable files unless something explicitly chmods them.

8. **`external/`'s four Claude entries (~5.5 GiB) are held on purpose** and
   `EXTERNAL_LOCAL_REFERENCE_BYTES` will not reach 0 while they remain. That is the correct
   reported outcome, not unfinished work — the hard-stop rule and section 9.6 both keep
   them until the post-exit finalizer no longer needs them.

9. **Drive permits two folders with the same name at one path.** A rename reported COMPLETE
   with 8 objects verified while a twin of that name still held 7 more at the root. If a
   collection looks half-moved, look for a twin before concluding failure.

### What is deliberately not done yet

The post-transfer stages are gated on the transfers finishing, in this order: Drive dedupe
(`tools/drive-dedupe.py`, after organization, per the spec), cross-root audit
(`tools/cross_root_audit.py scan`), catalogue publication (`tools/drive_catalog.py build`
then `upload`), then repository closure — final commit, manifests, tests, `git fsck`, one
bundle regeneration, clone, restore-verify. **Do not regenerate the bundle before the
tracked storage changes stop.**

`symoneural-api` remains deliberately stopped. Do not start it to manufacture green smoke
output; the verified 14/14 capture is preserved.

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
