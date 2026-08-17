# Design specs and audits — proposals, not state

**None of these is authoritative for what the project currently is.** `.claude/HANDOVER.md`
is the one state document and `.claude/CLAUDE.md` is the one rulebook; that separation exists
because three files once all claimed to describe current state and agents kept acting on the
stale one. Most of these are *inputs* — findings and recommendations produced on 2026-08-17 by
agents working in parallel. Read them as arguments to evaluate, not as decisions taken.
`miner-preemption.md` is the exception in kind: it is not a proposal awaiting a decision, it
records a decision already taken — the yield protocol is specified so that the three files
citing it resolve, and its §7 argues for leaving it unbuilt.

They live here rather than in a scratch directory because each represents real measurement
work that would be expensive to redo, and scratch directories do not survive the session.
`docs/` is not deployed — `scripts/deploy.sh` publishes `site/` only — so nothing here
reaches a visitor.

| File | What it is | Status |
|---|---|---|
| `image-spec.md` | Restyle brief for `/image.html` (HANDOVER §5 item 1) | proposed, not implemented |
| `chat-spec.md` | Restyle brief for `/chat.html` (§5 item 2), modelled on the llama.cpp web UI | proposed, not implemented |
| `css-audit.md` | Collision audit of `site/symoneural.css`, plus a reserved-name list | findings; one live bug unfixed |
| `cuda-audit.md` | Audit of the CUDA engine (§5 item 8) | findings; nothing fixed |
| `symon-ml-review.md` | Review of the SyMoN_ML blueprint and the TRON licensing PoC | review; nothing implemented |
| `miner-preemption.md` | The GPU miner yield protocol — why a live miner is never evicted, and the mechanism that would change it | **specified, deliberately not implemented — read its §7 first** |

## What is worth acting on, and what was verified independently

Three claims from these reports were checked directly rather than taken on trust, because a
report is not evidence:

- **`.card` is defined twice** — `site/symoneural.css:118` and `:955`. The later rule was
  written for the homepage receipts grid and should have been `.cards .card`; it is winning
  on eleven unrelated `.card` elements in `documentation.html`. This is a **live bug** and a
  fourth instance of the collision class already documented in CLAUDE.md.
- **The CUDA engine is not where the brief said it was.** There is no `symoneural_reinforce/`;
  it is `backend/apps/reinforce/`, moved in `9b5da84`, and it is 35 Python files with no
  `.cu` and no CMake — it compiles through NVRTC at runtime. HANDOVER §10's layout block
  still showed the old path and has been corrected.
- **`context.py:149`** is the only `_attr` call in that file without an explicit default,
  and `_attr` defaults to `0`, so a name mismatch yields zero SMs silently while every
  neighbouring call guards itself. Confirmed by reading the file.

The rest of each report is unverified beyond the agent's own working. Where a report claims a
measurement, it generally records how it was taken; where it claims a bug, treat it as a lead
until you have reproduced it. The `cuda-audit.md` honest-labelling findings in particular
touch the argument the whole site rests on and deserve a careful second look before anything
is changed on their say-so.

## One thing these reports cannot tell you

They were written against the tree as it stood on 2026-08-17 and they quote line numbers.
`build_pages.py` has already changed since (the miner surface was added at the end of
`main()`). Re-grep before trusting any `file:line` in here.
