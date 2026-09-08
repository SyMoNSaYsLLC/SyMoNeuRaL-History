# Project authority — provider-neutral

The operating contract for this repository is **`docs/authority/PROJECT-AUTHORITY.md`**.

This file used to be a provider-specific shim that imported `.claude/CLAUDE.md`. That
import was a dependency on one vendor's directory layout, and it is gone as of 2026-09-08:
the rules were migrated to the neutral path above and the `.claude` paths were removed from
Git tracking. The physical copies are retained on this machine only until the owner's
retirement backup is taken.

`CLAUDE.md` is kept as a filename because several coding tools look for it by name. It is a
pointer and nothing else — do not put rules here, or there will be two authorities again.

| Question | File |
|---|---|
| What are the rules? | `docs/authority/PROJECT-AUTHORITY.md` |
| What is the current verified state? | `ProjectStatus.md` |
| What is left, and what will bite me? | `docs/HANDOFF.md` |
| Every folder and what it is for | `README.md` |
| Tool policy: what is refused | `docs/authority/TOOL-POLICY.json` |
| What may leave this box? | `docs/ops/EXPORTS.md` |
| Why is the code like this? | `git log` |

One canonical current-state source and one canonical handoff source. Do not create a third.
