# Where this came from, and what still has to happen to it

**Adopted from `references/RavenCalcServer_Christmas_20251224-1007` by `tools/index_references.py adopt`.**

`references/` is read-only material -- *"we cannot use code in references its for
reference only we must rebrand if we want to use it"*. That rule is about **where a file
lives**, so this copy exists to get past it honestly: everything under `incoming/` is on
its way to being rebranded, and nothing here is shipped from where it sits.

The original is still at `references/RavenCalcServer_Christmas_20251224-1007` and was **copied, not moved**. That is
deliberate: the reference copy is what a rebrand gets checked against, and deleting it to
satisfy a rule about it would leave nothing to check.

| | |
|---|---|
| origin | `references/RavenCalcServer_Christmas_20251224-1007` |
| built of | 8 `.py`, 1 `.md`, 1 `.html`, 1 `.sh` |
| licence file | **none shipped** |
| licence line | — |

## Surfaces it exposes

- `/health`
- `/`
- `/ui/compute`
- `/api/compute`

## Before anything here ships

1. **Rebrand.** Names, paths, user-visible strings. Not a blind replace -- most `MIT`
   substrings in this corpus are ordinary words (limits, submit, emits).
2. **Keep the attribution the licence requires.** If the table above says a licence
   shipped, its terms travel with the code; if it says none shipped, that is a decision
   to make knowingly rather than a gap to fill in silently.
3. **Give it a task number.** `PROJECT-TASKS.md` is where work comes from, and an
   adoption is not itself permission to build -- `INTAKE.md` is the way in.
