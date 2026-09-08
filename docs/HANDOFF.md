# HANDOFF — symoneural.com

**Canonical handoff document.** Migrated from `docs/HANDOFF.md` on 2026-09-08. The
rules that cite it now point here; the provider-specific path is retired and untracked.
Current verified state lives in `ProjectStatus.md`; this file records what will bite the
next person.

**Next executor: any coding agent or person.** The provider-specific "next executor: Claude"
language below is historical and is superseded by this line.


## Current handoff — 2026-09-08, consolidation + restructure + application verification

**Next executor: any coding agent or person.** (This line read "Claude" until 2026-09-08; the provider-specific form is retired.) The next task is the **first-party miner**: adopt Apache-2.0
`cpp-kawpow` via `tools/index_references.py adopt`, stand up a CPU path that passes its own
progpow test vectors, then the CUDA kernel for sm_120. This current entry supersedes the
older executor pointers preserved below.

**State at handoff.** HEAD `e6000070`, branch main, tree clean, 0 staged, 0 stashed. Suite
**2340 passed / 0 failed / 59 skipped**, measured at this SHA. `symoneural-api` and
`symoneural-web` active and enabled, site 302. `symoneural-gateway` inactive and disabled,
source intact. Full detail is in `ProjectStatus.md` under *Current state → 2026-09-08*;
this entry says only what will bite the next executor.

**What will bite you.**

1. **`symoneural-api` is running pre-restructure paths in memory.** The five runtimes moved
   out of `engines/` to the repo root, and `engines/`+`bin/` are compatibility symlinks. Nine
   Python files including `backend/api.py` resolved engines through the old split path form
   and were fixed, but pid 1507 has not been restarted, so **the shims are load-bearing
   right now**. Restarting it needs root and drops the resident model. Delete the shims only
   after that restart, and verify with a real request rather than a path listing.

2. **Do not move `/var/lib/caddy`.** It holds live Let's Encrypt *production* ACME state and
   a certificate valid to 2026-11-15. Copy and chown; a move loses it and the next start
   re-issues, spending rate limit on a public site. Caddy derename step 1 (config path →
   `ops/Caddyfile`) is done and live; step 2 (`User=caddy`, the state dir) is not.

3. **`symoneural-web` is the public site.** Active/enabled is correct. There is no fallback:
   vendor `caddy.service` is inactive AND disabled and the unit declares `Conflicts=`. A
   service-map row reading *"defined but disabled"* nearly got it disabled this session.

4. **Two engines are GPL-3.0** — `symoneural-miner` and `symoneural-ui`. `fork_engines.sh`
   refuses to stamp the SyMoNeuRaL licence over them, deliberately. Do not "fix" that by
   editing a LICENSE file.

5. **81 files compute a repo root by counting parents.** `bin/symoneural-audit` finds them;
   `test_path_fragility.py` ratchets the count. Adding one fails the suite. Resolve roots by
   walking up for `backend/api.py`.

6. **The window test is opt-in.** `SYMONEURAL_TEST_WINDOW=1` for
   `apps/test_desktop_shell.py`. It opens a real GTK window and runs the real client; it
   appeared repeatedly on the owner's desktop before being gated.

**Where things are now.** `README.md` lists every top-level folder and what it is for.
`external/` is the renamed `references/` and is read-only — nothing in it may be imported,
built, linked or executed, enforced by `apps/test_reference_isolation.py`. `archive/` is
bulk, `releases/` is release output.

**Not done, named rather than dropped.** The `symoneural-api` restart and shim deletion;
caddy derename step 2; the first-party miner; the render surface replacing ComfyUI; the 81
ratcheted path files; `Downloads/`.

---

## Earlier handoffs

Everything before 2026-09-08 is in **`docs/handoffs/HANDOVER-ARCHIVE-pre-20260908.md`** —
4,876 lines of accreted history, kept verbatim and clearly marked as
historical. It was split out because a canonical handoff that grows by prepending stops being
a handoff, and because present-tense audit checks cannot tell a 2026-08 statement from a
claim about today. The dated per-window handoffs are in `docs/handoffs/`.
