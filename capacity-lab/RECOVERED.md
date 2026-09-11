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

**Updated 2026-09-10, later the same day.** The first version of this file said *"nothing in
the recovered files was edited"* and recorded both defects below as noted-but-unfixed. That
was true when written and is **no longer true**: on the owner's follow-up instruction
(`RECOVERY-NOTES.md`), defect 1 was fixed and defect 2 was marked superseded in place. The
original wording is corrected here rather than left standing, because two records
contradicting each other about the same tree is worse than either.

What was authorised and what was not: *"recover `capacity-lab` with `gpu_state()` explicitly
disabled and saying why … Either way, the hardcoded path does not survive recovery"*, and
*"No refactor of `capacity-lab` beyond the path fix that is required for it to be honest."*
So: one function replaced, one paragraph stamped, nothing else. `BookingScenario.run()` is
**not** filled in.

---

## 1. `suite.py` imported a module from a worktree that no longer exists — **FIXED**

As recovered, `capacity-lab/suite.py:344` in `gpu_state()`:

```python
sys.path.insert(0, str(Path("/home/google/Symoneural/.claude/worktrees/"
                            "native-hybrid-gpu-player/engines/symoneural-hybrid")))
import gpu_guard
```

Measured 2026-09-10:

- **that worktree is gone.** As of 2026-09-11 `/home/google/Symoneural/.claude/worktrees/`
  contains nothing at all: `authority-plane-plan` was the last one and was removed with
  `git worktree remove` once its only unique content -- the authority-plane spec -- had been
  recovered into the tree at `dc7a73d3` and verified byte-identical. Its branch survives.
- **`gpu_guard` exists nowhere in this repository**, tracked or untracked, and it is not in
  `44863110` either — it was never part of this tree.
- the path also uses the **superseded** `engines/symoneural-<name>/` layout. Engines live at
  `symoneural-<name>/` at the repo root now.

So **`gpu_state()` raised `ModuleNotFoundError` on call** — demonstrated, not assumed:

```
$ python3 -c "import sys; sys.path.insert(0, '…/native-hybrid-gpu-player/engines/symoneural-hybrid'); import gpu_guard"
ModuleNotFoundError: No module named 'gpu_guard'
```

**The fix.** `gpu_state()` is now *declared but refuses to run* — the idiom this tree already
uses for `BookingScenario`, rather than a second one invented beside it. It returns
`available: False`, a `reason`, and `NOT AVAILABLE` for every field it cannot measure. The
hardcoded `.claude/worktrees/` path is gone entirely, not preserved in a commented-out form:
a first-party file reaching into that directory is the defect class `symoneural-audit` exists
to catch, and its README states the rule — never count parents to find the repository root.

`_legacy_engine_pids()` is first-party and still answers, so it is **still reported**.
Zero-filling a field that can be measured would be the mirror of the mistake being avoided.

**The first-party replacement exists and was deliberately not wired in.**
`tools/lease_proof_2p.py:75` `compute_apps()` returns pid → MiB from
`nvidia-smi --query-compute-apps`, and `:91` `vram()` returns the card reading — between them,
exactly what `gpu_guard.compute_apps()` and `gpu_guard.gpu_snapshot()` supplied. Wiring them
is a real change needing a real test, and it is past the path fix this recovery authorises.
It belongs in its own commit.

Verified after the change: `gpu_state("…")` returns the refusal dict instead of raising, and
118 tests still collect.

## 2. `README.md`'s booking blocker is no longer true — **MARKED SUPERSEDED IN PLACE**

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
and UI are already shaped for it."* That condition is now met.

**A dated `SUPERSEDED` block now stands above that paragraph in `README.md` itself**, so the
correction is where the claim is rather than only in this file. The original paragraph is
**left standing, not rewritten** — it was true when written, its audit is still the reason
`BookingScenario` has the shape it has, and overwriting somebody's dated measurement is not
the same as correcting it.

Filling in `BookingScenario.run()` is real work and is **not** done here. It is the obvious
next task for this tree and it needs its own commit.

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

### The hazard that follows from that, measured 2026-09-10

**Nothing scopes pytest collection to `backend/`.** There is no `testpaths` or
`norecursedirs` in `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini` or any root
`conftest.py` — I checked all six. So a bare `pytest` **from the repository root** will
collect `capacity-lab/tests/`, and those tests construct a player aimed at
`http://127.0.0.1:8800`. That turns an idle command into load against a serving API.

This is the same shape as `docs/HANDOFF.md` bite 11 — a whole-directory run doing far more
than the person expected — one directory up. **No config was added to prevent it**, because
that is a change beyond recovering this tree; it is recorded here so the next person meets
it in writing rather than in production. Run `capacity-lab/tests` on purpose or not at all.

## One known consequence, not guessed at

`restore/manifests/` and `FIRST-PARTY-CLOSURE.tsv` are generated, and a new first-party
top-level tree may warrant a row in them. That cannot be checked without running
`tools/build_restore_manifests.py`, which is an eleven-minute 48 GB scan and a scheduled job,
not a side effect of this commit (`docs/HANDOFF.md` bite 11). **Flagged for that scheduled
regeneration rather than hand-added**, because hand-editing a generated file is how the
generated file stops being the record.
