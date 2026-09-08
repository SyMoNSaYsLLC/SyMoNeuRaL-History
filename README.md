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

Every top-level directory, what it is, and how it is used. **Tracked** means a clone carries
it. **Ignored** means it is derived, bulk, or host-local: a clone rebuilds or refetches it,
and nothing in it may be treated as a source of truth. Sizes measured 2026-09-08.

### The runtime folders

Nine, each its own top-level component. They split into two kinds and the difference is
whether a clone carries them.

**Ours — first-party source, tracked.**

| Directory | What it is |
|---|---|
| `symoneural-api/` | the API and orchestration runtime, `:8800`. A licensed entry point; the application stays in `backend/`. |
| `symoneural-code/` | `symoneural-cli`, `symoneural-code`, `symoneural-discovery` — the operator command line and the interactive session. |
| `symoneural-audit/` | finds code that breaks when a directory moves. Written the day a move broke the client. |
| `symoneural-adaptive-fabric/` | **PLANNED, NOT_IMPLEMENTED.** A home and a README; no code. Status quoted from `docs/architecture/COMPONENT-MAP.tsv:15`. |

**Derived — built from vendored upstream source by `tools/fork_engines.sh`, gitignored.**
The recipe is tracked; the 11 GB of objects are not. Each carries a generated `README.md`,
a `LICENSE`, and a `THIRD_PARTY_NOTICES.md` naming what it came from.

| Directory | Size | Role | Licence position |
|---|---|---|---|
| `symoneural-llm/` | 383M | language-model serving, `127.0.0.1:8081` | SyMoNeuRaL over permissive upstream |
| `symoneural-diffuse/` | 797M | diffusion image generation | SyMoNeuRaL over permissive upstream |
| `symoneural-listen/` | 57M | speech recognition, CPU only | SyMoNeuRaL over permissive upstream |
| `symoneural-miner/` | 805M | mining control: GPU, ASIC, settlement | **upstream copyleft — not first-party** |
| `symoneural-ui/` | 8.2G | graph and workflow editor | **upstream copyleft — not first-party** |

```bash
tools/fork_engines.sh all         # sync, patch identity, build all five
tools/fork_engines.sh licences    # licences, notices and READMEs only, no rebuild
python3 tools/probe_engines.py    # audit artefact identity, announced identity, real work
bin/symoneural-audit --strict depth-root
```

The last two rows of the derived table are the honest part. `fork_engines.sh` **refuses** to
write the SyMoNeuRaL licence over a copyleft upstream: a licence is a grant from the
copyright holders, and editing the file would remove a notice the project must keep rather
than change the grant. Replacing both with first-party implementations is open work —
`cpp-kawpow` is Apache-2.0 and can carry a first-party miner; the render surface can be
built over the already-MIT `symoneural-diffuse`.

`engines/` still holds five compatibility symlinks into the derived directories, and `bin/`
holds symlinks into `symoneural-code/` and the two entry points, so nothing that named the
old paths broke. Both sets are temporary.

### Code a clone carries

| Directory | Size | What it is | How it is used |
|---|---|---|---|
| `backend/` | 24G | `api.py` and `apps/` — the API and every first-party application module | `cd backend && python3 -m pytest -q` runs the suite |
| `frontend/` | 484M | browser-side sources for the application surfaces | built by `tools/build_studio.py` and the site pipeline |
| `web/` | 73M | `symoneural-web/` — the first-party HTTP/TLS runtime, Caddy imported as a library | serves `:80`/`:443`; config is `ops/Caddyfile` |
| `site/` | 12M | site and application page sources | staged and published by the deploy path |
| `scripts/` | 304K | operational scripts: setup, GPU governor, modelops, archive guard | read the header before running one; several mutate the box |
| `tools/` | 1.8M | build, audit and evidence generators | `fork_engines.sh`, `probe_engines.py`, `probe_apps.py`, `build_progress.py`, `index_references.py` |
| `ops/` | 380K | deployment config and artefact manifests | `ops/Caddyfile` is the live web config; `ops/manifests/` records artefact identity |
| `control/` | 124K | one folder to run and test the server locally | see its own README |
| `bin/` | 295M | operator entry points — `symoneural-cli`, `symoneural-code`, `symoneural-discovery` | `bin/symoneural-code` opens an interactive session |
| `desktop/`, `desktop-client/` | 60K, 2.4G | GTK/VTE window over `bin/symoneural-code`, and the native client | `desktop/shell.py` |
| `harness/` | 192K | test harness support | used by the suite |
| `tests/` | 14M | cross-cutting tests that are not unit tests of one app | |
| `docs/` | 22M | the manual, architecture maps, ops runbooks, decisions and the handoff chain | `docs/ops/EXPORTS.md` before any byte leaves the box |
| `brand/` | 2.6M | brand assets | |
| `deploy/` | 164M | deployment payloads | |
| `training/` | 7.7G | training corpus, configuration and adapters | **protected** — see `docs/ops/EXPORTS.md` rule 2 |
| `yocto/` | 1.6M | twelve `meta-symoneural-*` layers and their scripts | embedded image builds |
| `incoming/` | 41M | staging for reference projects being rebranded | `tools/index_references.py adopt <project>`; only `PROVENANCE.md` is tracked |

### Not carried by a clone

| Directory | Size | What it is |
|---|---|---|
| `external/` | 149G | **third-party material, read-only.** 46 upstream OSS trees, vendored engine sources, SDKs, saved documents. Renamed from `references/` on 2026-09-08. Nothing in it may be imported, built, linked or executed — enforced by `backend/apps/test_reference_isolation.py`, not merely written down. |
| `archive/` | 285G | consolidated bulk: workspace archives, backups, build evidence, session transcripts, weight staging. Ours, but not source. |
| `releases/` | 49M | release tarballs and their MANIFESTs, produced by the export pipeline. Renamed from `archives/` because one letter of difference from `archive/` is a hazard. |
| `run/` | 819M | runtime state and generated pages, including `run/progress.html` and `run/config/` |
| `review/` | 4.2M | host-local evidence; not guaranteed in a fresh clone |

### The one rule about `external/`

> *"we cannot use code in external its for reference only we must rebrand if we want to use
> it"* — standing owner rule, quoted in `tools/index_references.py`.

The way past it is to move the thing, not to argue with it: `tools/index_references.py adopt`
copies a project into `incoming/` with its licence detected and a `PROVENANCE.md` written,
and from there it can be rebranded into first-party code.

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
