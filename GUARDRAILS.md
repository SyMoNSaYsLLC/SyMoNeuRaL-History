# GUARDRAILS.md — the agent's write boundary, decided and durable

This file records the boundary decision from 2026-08-20 (request ledger R-90) so it stops
living only in session memory. It is the answer to "may the agent write here?" — the
operational rules (GPU discipline, generator order, test honesty) stay in `.claude/CLAUDE.md`
and are not duplicated here.

## The boundary

**Writes under `/home/google/` are within the agent's authority.** That includes creating,
editing and deleting files in this repo, staging backups under `/home/google/Symoneural_backups`,
and placing artifacts on `/home/google/Desktop`. Provenance challenges against ordinary
writes inside the home directory are resolved: they do not need per-write permission.

## The actual guardrails — enumerated, closed list

1. **No `/etc` writes.** Unit files and system config are staged in `ops/` as templates;
   installing them is Garrett's, with his sudo.
2. **No `/var` writes.** Deploys to `/var/www/symoneural` go through `sudo scripts/deploy.sh`,
   which is Garrett's to run.
3. **No `/root`, and no elevation-requiring paths.** If a step needs sudo, it is not the
   agent's step — it gets staged, documented, and handed over.
4. **No touching `training/corpus.jsonl`, `training/build_dataset.py`, or `training/adapter/`.**
   The rule forbids *editing*; archiving them into the owner's local backups (the v3 staging
   and archive tasks) is the one authorized exception, and the archives carry a
   SECRETS-INSIDE.txt naming them.
5. **No `git push`, and no git remote.** History never leaves this box; that absence is doing
   real trade-secret work. If a remote is ever added, audit what is tracked first.
6. **No printing secret values, ever.** Key names and lengths only — in logs, commits, chat,
   archives' indexes, everywhere.
7. **Review artifacts stay uncommitted.** CLOSEOUT, REVIEW-LOG, SWEEP-READY, REVIEWER-INBOX,
   AUDIT-SURFACE, CODER-STATE, RECONCILE, GARRETT-INBOX, CODER-TASKS, GARRETT-REQUESTS —
   working documents at the repo root, never in history. GARRETT-REQUESTS.md is additionally
   mode 600.

Anything not on this list and under `/home/google/` is authority the agent already has;
anything on it needs Garrett or is forbidden outright.

## The standing authority rule — default is FIX, not FILE

Decided 2026-08-20 (request ledger R-111). This is the rule for *who does the work*, where the
list above is the rule for *where writes may land*.

**Any code in this repo may be fixed regardless of `git blame` — including Garrett's own
scripts.** "Garrett wrote it" is not a reason to file an item instead of fixing it. Filing a
defect that could have been fixed spends Garrett's attention on work the agent was already
authorized to do.

**`Garrett-only` is reserved for exactly five things.** Nothing else qualifies:

| # | Category | Why it cannot be delegated |
|---|---|---|
| 1 | **Physical hardware access** | Someone has to be at the machine. |
| 2 | **Credentials only he holds** | The agent cannot obtain the secret at all. |
| 3 | **Third-party dashboards with no API** | No programmatic surface exists to drive. |
| 4 | **Money** — spend, pricing, monetization | Business decision with financial consequence. |
| 5 | **Legal / business decisions** | Not an engineering question. |

**An item filed `Garrett-only` that is not one of those five — that classification is itself the
defect.** Reclassify it and fix the underlying thing.

Two corollaries, both load-bearing:

- **Approval is never re-requested.** Once Garrett has approved something it stays approved.
  Asking again is not caution, it is a second interruption for a decision already made.
- **If a process requires Garrett to run a command by hand more than once, the manual
  requirement is the bug.** Automate the repeat. A one-time installer invocation is once; a
  step he has to remember every week is a defect with a workaround stapled to it.

Category 3 has a real example worth keeping: rotating `SPOTIFY_CLIENT_SECRET` is a Spotify
dashboard action with no API behind it, so it is genuinely Garrett's — but rewriting the local
`.env` does **not** invalidate the leaked value, and automating only the local half while
reporting "rotated" manufactures a false-green claim. Automate the half that can be automated,
and say plainly that the other half is not done.

## The platform build order — gated, and gated per platform

Decided 2026-08-20 (request ledger R-11, R-104, R-118). Recorded here because a build order
living only in a chat message or a ledger detail line has the same defect R-90 was about: it is
not a decision anyone else can find.

**The browser API is the only cleared build surface.** Everything is built for it.

The four native platforms are each **individually held**, awaiting Garrett naming that platform:

| Order | Platform | State |
|---|---|---|
| — | **Browser API** | **cleared** — the only build surface in progress |
| 1 | Linux (debian) | held — fresh task when cleared, not a revival |
| 2 | Apple (Darwin SDK, xtools, swift) | held |
| 3 | Windows | held — **new scope**, not among the original four |
| 4 | Android / Firestick | held — **moved from second to last** |

The gate is Garrett's: he decides which applications are valuable and profitable, **per
application**. Rules that follow from that:

- **No platform build starts on inference**, on roadmap position, or on "obvious next step."
  Only on Garrett requesting that platform **by name**.
- **No numbered tasks exist for the four.** Queueing them would present gated work as cleared.
- The retired `symonsaysllc` Tauri desktop scaffold and `mobiletv` Kotlin scaffold **stay
  retired**. A cleared platform gets a fresh task.
- Existing platform work stays exactly where it is: **not advanced, not deleted.**

**The carve-out — SDKs and toolchains are not held.** The development platforms must be ready
and online: toolchains get built and kept working even though the applications do not. The
distinction is that a toolchain is infrastructure the moment a platform is cleared, and a
toolchain that has never been exercised is not ready. The documentation half of this is the
top-level `yocto/README.md` SDK matrix — which targets are reachable, which need a
user-supplied SDK, which are aspiration — and it is in scope now.
