# garbo — documents that claimed to describe the project and no longer do

Garrett, 2026-08-21: *"no files shoud be blocking you from doing what i ask in my project so
move all of bullshit hullinatios put in folder afrer creating"*.

Everything in here is a **second state document**. `.claude/CLAUDE.md` bars them by name and
says why: *"Three files once claimed to describe current state and agents kept acting on the
stale one."* Then seven more appeared anyway, over two days in August, each one written by an
agent finishing a piece of work and wanting somewhere to put its summary.

They are moved, not deleted. `git mv` keeps every line of history, and a file that turns out to
be needed comes back with one command:

```bash
git mv garbo/<name>.md .
```

## Why these seven, and how that was decided rather than guessed

Two questions were asked of every candidate, and both had to come out the same way.

**1. Does any code read it?** Checked by grepping `tools/`, `backend/`, `scripts/` and `tests/`
for each filename. All seven: no hits outside prose.

**2. Does anything outside the group cite it?** They form a closed ring — `SWEEP-READY` cites
`REVIEW-LOG` cites `CLOSEOUT` cites `AUDIT-SURFACE`, and so on round. Nothing outside the ring
needed any of them except one prose sentence in `.claude/HANDOVER.md`, which is updated in the
same commit so it does not dangle.

| moved | lines | what it was |
|---|---|---|
| `CLOSEOUT-2026-08-19.md` | 374 | a review's own sign-off |
| `CODER-STATE-2026-08-19.md` | 51 | a state document, named as one |
| `RECONCILE-2026-08-19.md` | 147 | reconciling two of the others against each other |
| `HANDOFF-FROM-COWORK-2026-08-20.md` | 74 | a handover nothing ever read — cited by **nothing** |
| `SWEEP-READY.md` | 1103 | the largest, and a punch-list duplicating the task file |
| `REVIEW-LOG.md` | 81 | a log of the review that produced the four above |
| `REVIEWER-INBOX.md` | 520 | a second inbox beside `GARRETT-INBOX.md` |

**2350 lines.** The two that were *not* moved are the more useful half of this list:

- **`AUDIT-SURFACE-2026-08-19.md`** looks identical to the seven and is **load-bearing**.
  `tools/build_progress.py:960` opens it and reads a status token out of each item heading, so
  moving it would break the progress page — which is the handover artefact, the one thing that
  is supposed to survive *"even if my computer blows up"*. It stays until that coupling is
  removed deliberately, and removing it is not a filing decision.
- **`GARRETT-INBOX.md`** is read by the same tool for whether `## v3 MILESTONE` exists, is named
  in `backend/apps/test_build_progress.py`, and is Garrett's own file rather than an agent's.

That is the whole lesson of this directory: **two files that look like clutter were doing work,
and the only way to tell was to ask the code instead of reading the names.** A tidy-up that
had gone by title would have taken the progress page down.

`GUARDRAILS.md` was left in place too. It is a rules document rather than a state document, and
it is entangled with `build_progress.py`'s rule-pointer matching in ways worth reading before
touching. It is a question, not a decision.

## What to use instead

`.claude/CLAUDE.md` already answers this, and it is the answer these seven files kept working
around:

| Question | File |
|---|---|
| What are the rules? | `.claude/CLAUDE.md` |
| What is the state, what is left, what will bite me? | `.claude/HANDOVER.md` |
| What is left to do? | `PROJECT-TASKS.md`, rendered by `run/progress.html` |
| Why is the code like this? | `git log` |

**Do not add an eighth file to this directory by writing a new one first.** If a summary needs
to exist, it belongs in a commit message or in `.claude/HANDOVER.md`. The reason a second state
document is barred is not tidiness — it is that agents keep reading the stale one and acting on
it, which is how work gets redone and how a figure nobody re-measured gets published.
