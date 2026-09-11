# Recovered 2026-09-10 — read this before trusting `README.md`

This tree was recovered by path from `44863110` (`experiment/native-hybrid-gpu-player`,
also tipped by `research/custom-runtime-freeze-20260824` — two branch names, one pair of
commits), where it had sat unmerged since **2026-08-24**. It was found by the
repo-disposition measurement in `review/commissioning-20260909/REPO-DISPOSITION-20260910.md`
(Q3), which asked whether the unmerged branches carried anything not already present,
superseded, or dead. This was one of two things that did.

**It was taken by path, not merged**, because its branch's two commits also touch 26 other
files — August edits to `backend/apps/dispatchos/`, `test_control_plane_matrix.py` and
others that this branch has since moved past. Merging would have quietly reverted them. The
cost of that choice is that those two commits' messages did not come across; this file
stands in for them.

**Nothing in the recovered files was edited.** The two items below are defects in the tree
as it arrived, recorded here rather than fixed, and recorded *beside* `README.md` rather
than inside it — its blocker section is somebody's measured claim, correct on the day it
was written, and appending a dated note is honest where rewriting it would not be.

---

## 1. `suite.py` imports a module from a worktree that no longer exists

`capacity-lab/suite.py:344` in `gpu_state()`:

```python
sys.path.insert(0, str(Path("/home/google/Symoneural/.claude/worktrees/"
                            "native-hybrid-gpu-player/engines/symoneural-hybrid")))
import gpu_guard
```

Measured 2026-09-10:

- **that worktree is gone.** `/home/google/Symoneural/.claude/worktrees/` contains only
  `authority-plane-plan/`.
- **`gpu_guard` exists nowhere in this repository**, tracked or untracked, and it is not in
  `44863110` either — it was never part of this tree.
- the path also uses the **superseded** `engines/symoneural-<name>/` layout. Engines live at
  `symoneural-<name>/` at the repo root now.

So **`gpu_state()` raises `ModuleNotFoundError` on call.** Everything that does not call it
is unaffected; 118 tests collect clean (see below). Whoever needs GPU sampling here should
take it from `tools/gpu-governor.sh` and `ops/RUNTIMES.tsv`, which are the current
authorities, rather than restoring a path into a deleted worktree.

## 2. `README.md`'s booking blocker is no longer true

`README.md` opens with *"**There is no Donnie booking application.** Repo audit at
`main @ 7d1a5529`: 0 routes matching `book|appoint|dispatch|slot|schedul`…"*, and on that
basis `BookingScenario` is declared but refuses to run, with every booking metric reporting
`NOT AVAILABLE`.

**That was true when written and is false now.** Measured 2026-09-10 —
`backend/apps/dispatchos/routes.py` carries **15 route decorators**, including:

```
POST /bookings                  GET  /board
GET  /bookings/{bid}            POST /bookings/{bid}/quote
POST /login                     GET  /me
```

The README states its own unblocking condition: *"When the booking application exists,
filling in `BookingScenario.run()` is the only change — the harness, samplers, report schema
and UI are already shaped for it."* That condition is now met. Filling it in is real work and
is **not** done here; this note only records that the blocker has lifted, so nobody reads
`NOT AVAILABLE` as a fact about the server.

---

## What was verified on recovery, and what was not

**Verified.** `python3 -m pytest capacity-lab/tests -q --collect-only` → **118 tests
collected in 0.13s**, no import errors. So the package imports and the test files are intact.

**Not verified — and deliberately not.** The tests were **not run**. `tests/test_capacity_lab.py`
constructs `players.SymonChatPlayer("http://127.0.0.1:8800")`, and this harness exists to
open concurrent synthetic sessions against the API. Running it is a load test against a
service that is serving right now; that is the owner's call, not a side effect of a recovery
commit. **Treat every number this tree can produce as unmeasured on this box until someone
runs it on purpose.**

The repository's scoped suite (`docs/HANDOFF.md:110`) does not reach this tree either — it
is outside `backend/`. `457 passed, 4 skipped` before and after this recovery says nothing
about the code here.

## One known consequence, not guessed at

`restore/manifests/` and `FIRST-PARTY-CLOSURE.tsv` are generated, and a new first-party
top-level tree may warrant a row in them. That cannot be checked without running
`tools/build_restore_manifests.py`, which is an eleven-minute 48 GB scan and a scheduled job,
not a side effect of this commit (`docs/HANDOFF.md` bite 11). **Flagged for that scheduled
regeneration rather than hand-added**, because hand-editing a generated file is how the
generated file stops being the record.
