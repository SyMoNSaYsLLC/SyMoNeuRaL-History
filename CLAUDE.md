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
| Where does each surface listen? | `ops/PORTS.tsv` → `docs/ops/PORTS.md` |
| What runs behind it, what calls it, what does it load, does it take the lease? | `ops/RUNTIMES.tsv` → `docs/ops/RUNTIMES.md` |
| How do I install, start, verify or roll back the API? | `RUNBOOK.md` |
| How does any of this come back after a reinstall? | `restore/` — and `THIRD-PARTY-REBUILD-MANIFEST.tsv` for pinned upstreams |
| Why is the code like this? | `git log` |

One canonical current-state source and one canonical handoff source. Do not create a third.

`restore/` is indexed here for the same reason `RUNBOOK.md` is: it is the only record of how
each untracked component is rebuilt — which upstream revision, which build script, which
artefact hash — and nothing an arriving agent reads pointed at it. A commissioning pass
wrote a suggestion on 2026-09-09 claiming two 8 GB untracked trees had no restore path,
when both were already pinned to verified upstream commits in there. That is what an
unindexed authority costs.

`RUNBOOK.md` is neither of those two and is indexed here so it does not become a third by
accident. It is **operational procedure only** — the commands, in order, with what their
output looks like. It states no rules and no project state; where it names a current fact
it dates it and says how it was measured. Written 2026-09-09 by the commissioning pass.
