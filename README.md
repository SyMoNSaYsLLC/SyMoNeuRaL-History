# SyMoNeuRaL

SyMoNeuRaL is SyMoNSaysLLC's professionalization, orchestration, routing, governance, evidence,
entitlement, and integration platform. Providers supply reasoning or generation; first-party Symon
applications provide governed professional workflows around those capabilities.

The target control plane is still being built. Existing application surfaces, restored models, and
live serving do not establish a complete trained Symon model, unified Studio, or customer release.

## Start here

| Document | Authority |
|---|---|
| [ProjectStatus.md](ProjectStatus.md) | Current verified state, dated evidence, blockers, protected baseline. |
| [SyMoNSaysLLC.md](SyMoNSaysLLC.md) | Organization, platform, applications, providers, runtimes, plugins and licensing relationships. |
| [PROJECT-TASKS.md](PROJECT-TASKS.md) | Backlog and task identifiers; entries do not authorize execution. |
| [GUARDRAILS.md](GUARDRAILS.md) | Standing project control and safety rules. |
| [AGENTS.md](AGENTS.md) | Provider-neutral agent/subagent operating contract. |
| [Design reference index](docs/design/references/2026-09-03/INDEX.md) | Exact September 3 owner screenshots and mapped requirements, not production assets. |

Garrett alone authorizes tasks. Exactly one mutation owner operates within each task tree.
Do not begin work, run install/deploy scripts, regenerate task records, or start services from this README.
Before a scoped commit, assess the required ProjectStatus and registry updates under GUARDRAILS.

## Repository map

- `backend/api.py` and `backend/apps/`: API integration and first-party application modules.
- `backend/apps/gateway/src/`: Rust HTTP Gateway; separate Python licensing code shares its parent directory.
- `web/symoneural-web/`: first-party serving wrapper around upstream Caddy.
- `engines/symoneural-llm/`, `engines/symoneural-diffuse/`, `engines/symoneural-ui/`: upstream runtime trees.
- `backend/models/PROVENANCE.json`: model/payload source attribution and identity records.
- `site/`: application/site sources; presence does not prove production deployment.
- `ops/`, `scripts/`, `tools/`: gated build, operations and evidence mechanisms.
- `review/`: mostly ignored, host-local evidence; not guaranteed in a fresh clone.

Current production observations and their limitations belong in ProjectStatus. Do not use old
quick-start/deployment instructions as proof of the present serving topology or as authority to change it.

## Historical and local records

[Sept1.md](Sept1.md), [GARRETT-INBOX.md](GARRETT-INBOX.md), and
[AUDIT-SURFACE-2026-08-19.md](AUDIT-SURFACE-2026-08-19.md) preserve dated planning/audit material.
`INTAKE.md` is the ignored local queue of unresolved incoming work;
`GARRETT-REQUESTS.md` is the ignored local owner request/disposition ledger;
`AUDIT.md` is ignored local historical audit/question evidence. Their original bytes are preserved
by this gate. Old auto-promotion/auto-repair instructions in those records have no current authority.

[CLAUDE.md](CLAUDE.md) provides transitional provider guidance subordinate to AGENTS.
Protected nested provider handovers are history, not the current-state authority.
The full pre-consolidation README, GUARDRAILS, and imported AGENTS pointer are retained verbatim
in Sept1's retired root documentation snapshots.

## Source ownership and licensing

[LICENSE](LICENSE) covers SyMoNeuRaL-authored material. Upstream engines, libraries, models, and
assets retain their own terms and attribution. [LICENSES.md](LICENSES.md) is a dated inventory with
known unresolved distribution/source-location statements, not a new licensing or release verdict.
Consult the registry's relationships and the applicable source licenses; house naming does not
transfer upstream authorship. This consolidation makes no blanket permissive/copy-left-free claim.
