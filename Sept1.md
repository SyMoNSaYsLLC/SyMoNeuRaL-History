# Sept1.md — Complete Server / Application / Customer Delivery Plan

**Status:** PLANNING PASS — no implementation performed.
**Written:** 2026-09-01, against repository HEAD `1df394f0`.
**Authority for customer slotting:** `SyMoNeuRaL_Customer_Application_Slotting_Architecture.md` (read in full; normative for §10/§11).

> **How to read this document.** Every claim about the system is tagged:
>
> | Tag | Meaning |
> |---|---|
> | **CURRENT** | Verified present and working, on this box, today |
> | **EXISTING-INCOMPLETE** | Present but not finished or not wired end to end |
> | **PROPOSED** | Suggested new work. Does not exist |
> | **REQUIRED** | Must exist before a dependent phase can proceed |
> | **DECISION** | Needs Garrett; not decided here |
> | **FUTURE** | Deferred beyond this plan |
>
> Untagged prose is commentary. No untagged statement should be read as a claim about current wiring.

---

## 1. Executive Scope

### What this document is

A reviewed implementation plan covering seven bodies of work requested 2026-09-01:

1. Operator launchers + READMEs for model management (`control/models/`)
2. SyMoNeuRaL Studio as an advanced model/workflow surface
3. Look-and-feel pass across Live Stack applications
4. Customer login / account / entitlement flow
5. Customer-scoped application download ("GitHub-like")
6. Alignment with SymonSays / SyMoNeuRaL / Symon naming architecture
7. Complete server/runtime/library/binary shipping scope

### What was actually found

The single most important finding: **most of this already exists in some form.** The work is predominantly *reconciliation and completion*, not greenfield construction.

- **CURRENT** — 18 backend app packages, 21 mounted API namespaces, 26 site pages, 12 rack surfaces reporting live state.
- **CURRENT** — Model management has real authority already: `tools/modelops_inventory.py` (scan-based, cross-checks three sources) and `scripts/modelops/symoneural-modelops-stage.sh` (21,688 B; 8 modes; `--activate-candidate` guarded by six refusals; `--rollback`).
- **CURRENT** — Studio is ~2,704 lines across six modules with ComfyUI graph integration, custom nodes, MCP server, 11 API routes, and the only `gate.py` in the codebase.
- **RESOLVED 2026-09-02 (was EXISTING-INCOMPLETE)** — Accounts has 8 endpoints (signup/login/logout/me/sessions/password/signout-everywhere/status). It had **no customer→application entitlement**; A-3 (`ef1a4af4`) added the correspondence + grant bridge, and 1 grant is provisioned and runtime-verified on both sides (200 entitled / 403 unentitled). DispatchOS still runs its **own** login — that is now the *intended* end state under **D-3(b)**, not an incompleteness.
- **DELIVERED 2026-09-02 (was REQUIRED)** — `tools/export_snapshot.sh` did not exist; A-2 (`728df639`) delivered it — 192 lines, fail-closed, 17 protected patterns, stage-2 refusal proven by sabotage. It is the only sanctioned export path per `docs/ops/EXPORTS.md` rule 4. The tool no longer blocks the feature; **external export/distribution remains NOT authorized** (D-11 **DECIDED** 2026-09-02 — architecture ruled; no key exists, no artifact signed, external release still not authorized).
- **CURRENT** — **Zero learned model payloads on this box** (measured §4.1.1). 11 `PROVENANCE.json` entries are declared-but-absent historical metadata. "No model installed" is the real, valid baseline — and per Q1 it is the correct condition for validating `control/models/`.
- **CURRENT** — Multi-architecture delivery is **further along than the repo alone suggests**: `/yocto/artifacts` holds **76,208 packages** across arm/arm64/x86/x86-64 in both DEB and IPK, plus 13 SDK installers (§13.2). Two gaps on the primary arch (`x86-64/ipk` absent; `x86-64/deb` feed index missing) and **every artifact is unsigned**.

### Scope boundaries honoured

- No repository restructuring. The reverted `symoneural-server/` consolidation is not revived.
- `control/` is the additive operator surface and is extended, not used to justify duplication.
- No second source of truth for any capability.

---

## 2. Frozen Architecture / Naming Rules

Normative, from `SyMoNeuRaL_Customer_Application_Slotting_Architecture.md`.

```
SymonSaysLLC          company / legal / ownership
└── SyMoNeuRaL        shared system, platform, network, build, release, custody
    ├── symoneural-*  platform/system/infrastructure authority
    ├── Symon         model / agent / runtime / software identity
    │   └── symon-*   executable / runtime / component / artifact
    │       symon_*   importable Python module when required
    ├── Applications  customer-facing application layer (Live Stack)
    └── Third-party   retain upstream names (NVIDIA, CUDA, Caddy, PostgreSQL…)
```

### The rules that constrain every later section

1. SyMoNeuRaL remains **one shared platform authority**.
2. Symon remains the **shared runtime/software identity**.
3. Customer applications remain **application-layer identities**.
4. **Do not** create `symoneural-<customer-app>` merely because a customer application exists. Specifically: **`symoneural-dispatchos` must not be created.**
5. Do not duplicate shared platform code into every customer application.
6. **Do not move working source merely to make the ownership tree look prettier.**
7. Customer-specific logic stays inside the customer/application boundary.
8. Shared functionality moves upward only via the Promotion Rule (§10.4).
9. Third-party/vendor names remain upstream.
10. Every customer gets the same logical slot structure.
11. Every customer export is scoped and fail-closed.
12. Every application must have an explicit verification path before release.
13. Customer origin, project ownership, and third-party ownership are tracked **independently of directory location**.

### The distinction that governs this whole plan

> **The architecture tree expresses ownership and responsibility, not a requirement to physically move every existing repository path. Existing functional paths may remain where they are when they are already wired correctly.**

Conceptual architecture ≠ filesystem layout. This is why §10 slots map onto existing paths rather than proposing moves — and it is the same principle that made the `symoneural-server/` consolidation the wrong answer.

---

## 3. Current Server Baseline

Measured 2026-09-01, not carried forward.

| Item | Value |
|---|---|
| Repo HEAD | `1df394f0` (`feat(control): add control/…`) |
| Branch / remotes | `main` / **0 remotes** — nothing leaves this box via git |
| Working tree — *baseline before Sept1.md* | tracked modifications = 0; `Sept1.md` not yet present |
| Working tree — *current planning-pass end state* | tracked modifications = 0; untracked = `Sept1.md` only |
| `symoneural-api.service` | **enabled, active**, PID 186057, 0 restarts, HTTP 200 |
| `symoneural-gateway.service` | installed, disabled, inactive |
| `symoneural-web.service` | installed, disabled, inactive |
| `symoneural-deploy.service` | **intentionally removed** 2026-09-01 (backup + repo template retained) |
| Disk | `/` 11 % · `/home` 38 % of 885 G |
| GPU | 16,303 MiB total; ~1 GiB used at idle; governor lock free |
| Engines on disk | `symoneural-llm`, `symoneural-diffuse`, `symoneural-ui` (all derived, `/engines/` gitignored) |

**Session history that must not be misread** (carried per instruction §I):

1. **CURRENT** — The `symoneural-server/` consolidation was reverted. Do not revive it. It caused an ~8-hour outage and 7,500+ crash-loop restarts.
2. **CURRENT** — `control/` is the accepted additive control-board model.
3. **CURRENT** — `scripts/deploy.sh` is load-bearing manual deployment tooling (70 references; in `docs/ENGINEERING.md`; named in an open task). **Not obsolete.**
4. **CURRENT** — `symoneural-deploy.service` was intentionally removed. Do not silently recreate it.
5. **CURRENT** — `scripts/gcommit.sh` is supported interactive operator tooling (504 commits under that identity; `.mailmap` canonicalizes 4 addresses onto it). Zero source references ≠ orphaned.
6. **CURRENT** — `scripts/modelops/symoneural-modelops-stage.sh` exists in a nested directory. Search subtrees before declaring modelops absent.
7. Existing implementations are extended/reconciled, never duplicated.

---

## 4. Existing Authority Inventory

Every entry verified on disk this pass.

### 4.1 Model management

| Authority | Lines/Size | Role | State |
|---|---|---|---|
| `tools/modelops_inventory.py` | scan tool | Cross-checks disk × `PROVENANCE.json` × `api.py` active set. Stdlib only, no network, downloads/activates/deletes nothing | **CURRENT** |
| `scripts/modelops/symoneural-modelops-stage.sh` | 21,688 B | Stage / smoke / promote / rollback a model bundle | **CURRENT** |
| `scripts/fetch-models.sh` | 9,824 B | Fetch GGUF weight sets + licences. Enforces house naming; FLUX.1-schnell only | **CURRENT** |
| `scripts/fetch-whisper.sh` | 4,916 B | ASR weights | **CURRENT** |
| `scripts/fetch-cutout.sh` | 4,671 B | Cutout model | **CURRENT** |
| `scripts/gpu-governor.sh` | 21,440 B | **Only** authority permitted to touch the GPU lock. 101 references | **CURRENT** |
| `backend/models/PROVENANCE.json` | record | Upstream → house-name mapping. 11 manifest entries, **0 with a file on disk** (§4.1.1) | **EXISTING-INCOMPLETE** |
| `training/train_lora.py` | QLoRA | Fine-tune; adapter kept separate, not merged | **CURRENT** |
| `training/probe_27b.py` | measurement | Measured VRAM footprint; runs under governor | **CURRENT** |
| `training/adapter/`, `adapter-qwen36/` | weights | **PROTECTED** — never exported | **CURRENT** |
| `backend/apps/studio/custom_nodes/symoneural_gguf` | node pack | GGUF handling inside Studio | **CURRENT** |

**`symoneural-modelops-stage.sh` — complete mode list** (all 8 verified against case branches):

| Mode | Behaviour | Writes? | GPU? | Net? |
|---|---|---|---|---|
| `--dry-run` | Say what each mode would do | no | no | no |
| `--inventory` | Measured inventory via `modelops_inventory.py` | no | no | no |
| `--stage-openai-gpt-oss-20b` | Prepare staging dir; prints download cmd, does **not** run it | staging only | no | no |
| `--write-docs` | Regenerate inventory block in ops docs | docs | no | no |
| `--smoke-plan` | Print smoke steps a candidate must pass | no | no | no |
| `--smoke-candidate <id>` | Run candidate **in isolation** — no fallback possible | no | **yes** | no |
| `--activate-candidate <id>` | Promote staged+smoked candidate — **six refusal gates** | **yes** | no | no |
| `--rollback [<id>]` | Print/write rollback path; restore backup | **yes** | no | no |

Governing rule, quoted from the script: *"NOTHING IS DOWNLOADED, ACTIVATED, MOVED OR DELETED WITHOUT AN EXPLICIT FLAG."*

**Rebranding is already implemented, not missing.** `fetch-models.sh`: *"HOUSE NAMES. Nothing under `backend/models/` keeps an upstream filename."* Language tiers land as `symon-1.0-*`; image/ASR as `symoneural-image-*` / `symoneural-listen-*`; `PROVENANCE.json` records the upstream each came from.

#### 4.1.1 Current model-payload baseline — MEASURED 2026-09-01

**Correction.** An earlier draft stated "28 weight files, 17 unresolved, ~78 GiB." That was **stale text from the tool's docstring, not a measurement.** Re-running the read-only authority (`python3 tools/modelops_inventory.py`) gives the actual current state:

```
weight files on disk (excl. hf cache) : 0
  in PROVENANCE.json                  : 0        0.00 GiB
  NOT in PROVENANCE.json              : 0        0.00 GiB
manifest entries with no file on disk : 11
adapters (training/, protected)       : 0
ACTIVE DEFAULTS                       : 0
UNKNOWN-BLOCKED                       : 0
```

| Dimension | Measured value |
|---|---|
| Learned-weight payload objects | **0** |
| Learned-weight payload bytes | **0** |
| Metadata / source fixtures / placeholders | 2 files, **both 0 bytes** (not payloads) |
| `backend/models/` total size | 2.8 MB (scaffolding + configs) |
| Model-class directories | 31, of which 3 completely empty |
| `PROVENANCE.json` manifest entries | 11 — **none** with a file on disk |
| Adapters on disk | 0 (`training/adapter` 24 K, `adapter-qwen36` 28 K — no payload files) |
| Currently selected / active defaults | 0 |
| Currently loaded / resident | 0 (rack: chat/image `offline`) |
| Acquisition / staging / cache / archive | none staged; no HF cache counted |

**This is the defining constraint for §6.** The box currently has **no learned model payloads at all.** Every `control/models/` launcher must therefore treat *"no model installed"* as the **normal, explicit, first-class state** — not an error, and never masked by a CPU fallback or a fake success. The 11 manifest entries describe models that are **declared but absent**.

**Provenance/licence language (corrected).** Absence from `PROVENANCE.json` does **not** prove a model is unlicensed. Correct terminology throughout:

| Term | Meaning |
|---|---|
| `PROVENANCE VERIFIED` | Recorded in `PROVENANCE.json` **and** file present on disk |
| `PROVENANCE STATUS UNKNOWN/UNVERIFIED` | Not recorded, or recorded with no file to check |
| `LICENCE STATUS UNKNOWN/UNVERIFIED` | No independent licence authority consulted |

Never invent provenance. Never infer absence of licence solely from absence in `PROVENANCE.json`. Current tally: **0 provenance-verified**, **11 provenance-unverified** (declared, no file), **11 licence-unverified**.

### 4.2 Operator surface

| Authority | Role | State |
|---|---|---|
| `control/` (11 files) | Additive control board; thin wrappers only | **CURRENT** |
| `control/status-all.sh` | Units, 12 surfaces, GPU, engines, disk in one screen | **CURRENT** |
| `control/_common.sh` | Shared root-guard + helpers | **CURRENT** |
| `scripts/symoneural.sh` | Production service control (`on`/`off`/`status`/`log`/`off-at`) | **CURRENT** |
| `scripts/symoneural-ui.sh` | Render-UI process control on :8188 | **CURRENT** |
| `scripts/enable-surfaces.sh` | Writes systemd drop-in enabling token-gated surfaces | **CURRENT** |

### 4.3 Build / release / custody

| Authority | Role | State |
|---|---|---|
| `tools/fork_engines.sh` | Derives `engines/` from `references/` | **CURRENT** |
| `tools/fork_render_ui.sh` | Derives `engines/symoneural-ui` | **CURRENT** |
| `scripts/build-deb.sh` | `.deb` packaging (`opt/symoneural/{bin,scripts}`) | **CURRENT** |
| `scripts/build-apt-repo.sh` | APT repo publication | **CURRENT** |
| `ops/build-gateway.sh` | Rust gateway build | **CURRENT** |
| `ops/build-symoneural-web.sh` | Go web build | **CURRENT** |
| `ops/install-runtime.sh` | Runtime install hub (6 dependents) | **CURRENT** |
| `ops/verify-runtime.sh` | Runtime verification | **CURRENT** |
| `ops/rollback-runtime.sh` | Runtime rollback | **CURRENT** |
| `ops/install-service.sh` | `@@ROOT@@` template substitution for units | **CURRENT** |
| `scripts/deploy.sh` | Publish staged site to `/var/www/symoneural` | **CURRENT** |
| `docs/ops/PROVENANCE.md`, `backend/vendor/PROVENANCE.md` | Custody records | **CURRENT** |
| `LICENSE`, `LICENSES.md` | `LicenseRef-SyMoNeuRaL-Proprietary` | **CURRENT** |

### 4.4 Accounts / auth / entitlement

| Authority | Role | State |
|---|---|---|
| `backend/apps/accounts/` | 8 endpoints; scrypt N=131072 (128 MiB), legacy-hash upgrade path | **CURRENT** |
| `backend/apps/gateway/entitlement.py` | **Ed25519 licence entitlements** — payer settled a licence for a workspace, expiring. TRON/chain settlement | **CURRENT** |
| `backend/apps/licensing/` | Contract signing, issuance | **CURRENT** |
| `backend/apps/dispatchos/` login | **Separate** `/api/dispatchos/{login,logout,me}` | **CURRENT — intended under D-3(b)** (was EXISTING-INCOMPLETE; separation is the settled design, bridged by entitlement only) |
| `tools/dispatchos_accounts.py` | DispatchOS-specific account tooling | **CURRENT** |

> **Critical finding — since ADDRESSED, retained because the distinction still holds.** `gateway/entitlement.py` is *licence* entitlement (chain settlement), **not** customer→application access control; that remains true. What has changed: as of A-3 (`ef1a4af4`) there **is** a shared customer→application entitlement layer — `apps/accounts` holds the correspondence and grant, and `apps/dispatchos/authz.py` is the consuming seam. DispatchOS still runs its own login by design (**D-3(b)**). The original wording — *"no shared customer→application entitlement layer today"* — was accurate when written and is now false.

### 4.5 Export / delivery

| Authority | State |
|---|---|
| `docs/ops/EXPORTS.md` | **CURRENT** — policy, 4 rules |
| `tools/export_snapshot.sh` | **CURRENT** — delivered by A-2, `728df639` (was: does not exist). Fail-closed; 17 protected patterns; stage-2 refusal verified. Running it for external release is **not** authorized |

---

## 5. Complete Live Stack Inventory

Derived from `backend/apps/`, live OpenAPI, `site/`, and `/api/status`. **Not eight applications.**

### 5.1 Taxonomy

An earlier draft both excluded and counted the same surfaces. Resolved with an explicit taxonomy — **not** by adjusting a number. Every surface below is classified into exactly one category.

| Category | Definition | Slot standard applies? |
|---|---|---|
| `CUSTOMER_APPLICATION` | Delivered to a named external customer under an entitlement | **Yes** — §10 in full |
| `SHARED_APPLICATION` | First-party application offered to all users of the Live Stack | Partially — no `CUSTOMER_IDENTITY` |
| `EMBEDDED_APPLICATION_SURFACE` | Capability surfaced inside another application; no standalone page | No |
| `PLATFORM_SURFACE` | Shared infrastructure consumed by applications | No |
| `OPERATOR_SURFACE` | Internal operator tooling, not customer-facing | No |
| `INFORMATIONAL_PAGE` | Site chrome, catalogue, documentation | No |

> **The customer-slot standard (§10) applies to `CUSTOMER_APPLICATION` objects only.** It does not automatically apply to platform or operator surfaces.

### 5.2 Counts by category

```
CUSTOMER_APPLICATION .............  1   DispatchOS (Donnie)
SHARED_APPLICATION ............... 12
EMBEDDED_APPLICATION_SURFACE .....  4
PLATFORM_SURFACE .................  6
OPERATOR_SURFACE .................  2
INFORMATIONAL_PAGE ...............  7
                                   ──
TOTAL SURFACE INVENTORY .......... 32

raw discovery: 18 backend/apps packages · 21 mounted /api/ namespaces
               · 26 site/*.html pages · 12 rack surfaces in /api/status
```

Total surface inventory is retained deliberately — but **not every user-visible surface is an application.**

### 5.3 Master surface table

Every row classified into exactly one category. Impl: **C**=working, **P**=partial, **S**=stub. Rack = live `/api/status`.

#### CUSTOMER_APPLICATION (1)

| Application | Slug | Customer | Frontend | Backend | API | Rack | Tests | Impl |
|---|---|---|---|---|---|---|---|---|
| **DispatchOS** | `dispatchos` | **Donnie** | `share-dispatchos.html` + `/demo/dispatchos` | `apps/dispatchos/` | `/api/dispatchos` (13) | ready | **0** | **P** |

#### SHARED_APPLICATION (12)

| Application | Slug | Frontend | Backend | API | Rack | Tests | Impl | UI |
|---|---|---|---|---|---|---|---|---|
| Chat | `chat` | `chat.html` | `api.py` surface | `/api/chat` (1) | offline | — | **C** | authored |
| Image | `image` | `image.html` | `api.py` surface | `/api/image` (1) | offline | — | **C** | authored |
| Remix | `remix` | `remix.html` | `apps/remix/` | `/api/remix` (1) | offline | 3 | **C** | authored |
| RavenCalc | `ravencalc` | `ravencalc.html` | `apps/ravencalc/` | `/api/ravencalc` (1) | ready | 4 | **C** | authored |
| **Studio** | `studio` | `studio.html` | `apps/studio/` | `/api/studio` (11) | offline | 56 | **P** | **§7** |
| Coder | `coder` | `coder.html` | `apps/coder/` | — | ready | 3 | **P** | authored |
| Project | `project` | `project.html` | `apps/project/` | `/api/project` (12) | ready | 2 | **C** | authored |
| Sigils | `sigils` | `sigils.html` | `apps/sigils/` | `/api/sigils` (5) | offline | —² | **C** | authored |
| Live | `live` | `live.html` | `apps/live/` | `/api/live` (5) | ready | 1 | **C** | authored |
| Streamer | `streamer` | `streamer.html`, `streamer-watch.html` | `apps/streamer/` | `/api/streamer` (13) | ready | 5 | **C** | authored |
| Miner (ASIC) | `miner` | `miner.html` | `apps/asicminer/` | `/api/asicminer` (3) | offline | 34 | **C** | Braiins ref |
| Training | `training` | `training.html` | `training/` | `/api/train` (7)¹ | — | — | **P** | authored |

#### EMBEDDED_APPLICATION_SURFACE (4)

No standalone application identity; surfaced inside a host application.

| Surface | Host | Backend | API | Impl |
|---|---|---|---|---|
| GPU Miner | `miner.html` | `apps/cryptominer/` | `/api/gpuminer` (2) | **P** |
| Voice | chat surface | `apps/voice/` | `/api/voice` (3) | **C** |
| Reinforce | `reinforce.html` | `studio/plugins/reinforce`¹ | `/api/train` (7)¹ | **P** |
| Exp | `exp.html` | `studio/plugins/exp`¹ | `/api/exp` (13) | **P** |

#### PLATFORM_SURFACE (6)

Shared infrastructure consumed by applications. **Slot standard does not apply.**

| Surface | Backend | API | Role |
|---|---|---|---|
| Accounts | `apps/accounts/` | `/api/accounts` (8) | Shared authentication authority (**§9**) |
| Gateway | `apps/gateway/` (Rust) | `/api/gateway` (1) | Licence entitlement / settlement |
| Licensing | `apps/licensing/` | — | Contract signing, issuance |
| News | `apps/news/` | `/api/news` (1) | Shared page chrome (ticker) |
| Rack / Status | `api.py` | `/api/rack` (2), `/api/status` (1) | Platform state |
| Gen / Capture | `apps/capture/` | `/api/gen` (1) | Shared generation/capture plumbing |

#### OPERATOR_SURFACE (2)

| Surface | Backend | Role |
|---|---|---|
| Controlboard | `apps/controlboard/` + `controlboard.html` | Operator control page (generated) |
| `control/` | — | Additive CLI operator board (11 files) |

#### INFORMATIONAL_PAGE (7)

`index` · `overview` · `documentation` · `credits` · `receipts` · `build` · `livestack`

`livestack.html` is the application **catalogue**, not an application. It is generated, and it is where entitlement-aware rendering must land (**A-3/A-6**).

---

¹ **Correction to naive discovery.** `exp` and `train` have no `backend/apps/` package — they are **Studio plugins** (`backend/apps/studio/plugins/exp`, `.../reinforce`). Any inventory listing them as standalone apps is wrong.

² **`sigils` test count omitted deliberately.** A recursive glob returned 1,167 — a counting artefact, not a measured suite size. Per house rule, no figure beats an unverified one. **REQUIRED:** re-measure per `docs/ops/MEASUREMENTS.md` before quoting.

---

## 6. control/models Plan

### 6.1 Philosophy (inherited from `control/`)

Additive · thin wrappers · existing implementation stays authoritative · no second source of truth · no copied runtime implementation · runnable from the central control surface · documented · testable.

**`control/models/` must implement nothing.** Every launcher delegates to §4.1 authorities. If a capability does not exist underneath, the launcher says so explicitly rather than faking it.

### 6.2 Governing constraints

- **No model downloads during planning.** Not performed.
- **"No model installed" is a normal, explicit state** — never hidden behind a CPU fallback or fake success.
- One GPU, one job. Every GPU-touching launcher goes through `scripts/gpu-governor.sh`.
- Privileged operations state so and refuse rather than silently `sudo`.

### 6.3 Proposed launchers

All **PROPOSED**. None exist.

| Launcher | Purpose | Wraps (existing authority) | R/W | Model? | GPU? | Net? | Priv? |
|---|---|---|---|---|---|---|---|
| `models-list.sh` | What models are present on disk | `tools/modelops_inventory.py` | read | no | no | no | no |
| `models-active.sh` | Which model each surface *selects* | `modelops_inventory.py` (parses `api.py`) | read | no | no | no | no |
| `models-loaded.sh` | What is actually *resident* now | `/api/status` + `gpu-governor.sh status` | read | no | no | no | no |
| `models-provenance.sh` | Upstream origin per artifact | `backend/models/PROVENANCE.json` | read | no | no | no | no |
| `models-license.sh` | Licence per artifact | `LICENSES.md` + `PROVENANCE.json` | read | no | no | no | no |
| `models-checksums.sh` | Verify recorded digests | `modelops-stage.sh --inventory` | read | no | no | no | no |
| `models-compat.sh` | Runtime/engine compatibility | `ops/verify-runtime.sh`, engine probes | read | no | no | no | no |
| `models-acquire.sh` | Acquire a model | `scripts/fetch-models.sh` / `fetch-whisper.sh` | **write** | no | no | **yes** | no |
| `models-stage.sh` | Stage a candidate bundle | `modelops-stage.sh --stage-*` | staging | no | no | no | no |
| `models-verify.sh` | Smoke a candidate in isolation | `modelops-stage.sh --smoke-candidate` | read | yes | **yes** | no | no |
| `models-activate.sh` | Promote staged+smoked candidate | `modelops-stage.sh --activate-candidate` | **write** | yes | no | no | no |
| `models-rollback.sh` | Restore previous active model | `modelops-stage.sh --rollback` | **write** | yes | no | no | no |
| `models-release.sh` | Unload / free the card | `gpu-governor.sh release` | **write** | no | **yes** | no | no |
| `models-adapters.sh` | List/inspect LoRA adapters | `training/adapter*/` | read | no | no | no | no |
| `models-finetune.sh` | Launch QLoRA fine-tune | `training/train_lora.py` under governor | **write** | yes | **yes** | no | no |
| `models-rebrand.sh` | Inspect/verify house naming | `fetch-models.sh` convention + `PROVENANCE.json` | read | no | no | no | no |
| `models-gpu.sh` | GPU/runtime state | `control/gpu.sh` | read | no | no | no | no |

**Deliberately not proposed:** conversion and quantization launchers. No existing authority was found for either (`symoneural_gguf` custom node is Studio-internal, not a CLI authority). Proposing a launcher with nothing underneath would violate the thin-wrapper rule. → **DECISION D-6**.

### 6.4 STOP conditions (apply to every write-mode launcher)

1. `models-activate.sh` STOPS unless the candidate is staged **and** smoked — it must not bypass any of the six gates.
2. Any GPU launcher STOPS if the governor reports another holder.
3. `models-finetune.sh` STOPS if `training/corpus.jsonl` is absent — and never echoes its contents (protected).
4. `models-acquire.sh` STOPS without explicit confirmation; it is the only network launcher.
5. All launchers STOP with an explicit "no model installed" message rather than degrading to CPU or reporting false success.

### 6.5 Verification

Per launcher: run read-only mode against the live box, assert exit 0 and non-empty output; assert write-mode launchers refuse without their explicit flag. Plus `control/models/README.md` covering every entry, and a `SMOKE-models.md` record that cannot be written honestly without a real run.

---

## 7. Studio Plan

### 7.1 Current Studio — reconciled, not assumed

**EXISTING-INCOMPLETE**, ~2,704 lines:

| Module | Lines | Role |
|---|---|---|
| `routes.py` | 951 | 11 mounted API routes |
| `agent.py` | 451 | Agent orchestration |
| `comfy.py` | 422 | **ComfyUI integration** |
| `registry.py` | 352 | Node/model registry |
| `graph.py` | 308 | Graph/node execution |
| `inference.py` | 220 | Inference dispatch |
| `gate.py` | — | Access gate (**only one in the codebase**) |
| `custom_nodes/` | — | `symoneural_cleanroom`, `symoneural_gguf` |
| `plugins/` | — | `discovery`, `exp`, `reinforce` |
| `mcp_server.py`, `mcpframework.py` | — | MCP surface |
| `page.html`, `page.js` | — | Front end |
| 56 tests + `SMOKE-bench.md`, `SMOKE-cleanroom.md` | — | Coverage |

**A blind rebuild would destroy substantial working capability. Studio is extended, never replaced.**

### 7.2 Target (reference patterns: ComfyUI, vLLM playground, DeepSeek Harness)

Graph/node workflow · model selection · runtime selection · model inspection · lifecycle visibility · adapter management · fine-tuning controls · conversion/quantization *where an authority exists* · job/status visibility · logs · GPU state · artifact provenance · checksums · explicit activation/release · fail-closed operations.

### 7.3 Gap analysis

| Capability | Current | Target | Gap |
|---|---|---|---|
| Node graph editor | `graph.py` + `comfy.py` | Full canvas | **P** — reconcile with ComfyUI patterns |
| Custom nodes | 2 packs | Model-lifecycle nodes | **P** |
| Model selection | via registry | First-class picker | **P** |
| Model inspection | — | Provenance/licence/checksum panel | **MISSING** |
| Adapter management | `training/adapter*` on disk | UI surface | **MISSING** |
| Fine-tune controls | `train_lora.py` CLI | UI trigger + progress | **MISSING** |
| GPU state | governor CLI | Live panel | **MISSING** |
| Job/status | partial | Queue + history | **P** |
| Explicit activate/release | `modelops-stage.sh` CLI | UI action, fail-closed | **MISSING** |
| Conversion/quantization | none | — | **DECISION D-6** |

### 7.4 The binding constraint

> **Studio and `control/models/` must call the SAME underlying authorities.** No duplicate model-management backend. Studio's model panels call `modelops_inventory.py` / `modelops-stage.sh` / `gpu-governor.sh` — the identical set §6 wraps.

**Recommended:** a thin shared read layer (e.g. `backend/apps/studio/modelctl.py`) that shells to the same authorities, so CLI and GUI cannot diverge. It is an adapter, not a second implementation.

---

## 8. Per-Application UI Plan

### 8.1 Finding that determines the shape of this work

**`site/*.html` is a hybrid.** All 26 pages are tracked, but 8 carry generated-by banners:

- **GENERATED (8)** — `index` · `overview` · `livestack` · `controlboard` · `account` · `documentation` · `receipts` · `build`. Owned by `tools/build_pages.py`, `build_tabs.py`, `build_masthead.py`, `build_stack.py`, `build_studio.py`, `build_rack.py`, `build_gallery.py`, and the family map `tools/page_families.py`.
- **HAND-AUTHORED (18)** — `chat` · `coder` · `credits` · `exp` · `gateway` · `image` · `live` · `miner` · `project` · `ravencalc` · `reinforce` · `remix` · `share-dispatchos` · `sigils` · `streamer` · `streamer-watch` · `studio` · `training`.

> **Consequence:** editing a generated page directly is wasted work — the next generator run overwrites it. **`livestack.html` and `account.html` are both generated**, and both are central to this request. Their changes belong in the generators.

**Shared shell:** `symoneural.css`, `shell.js`, `ui.js`, `app.js`. Per-app: `coder.{css,js}`, `image.{css,js}`, `live.{css,js}`, `studio.js`, `exp.js`, `reinforce.js`, `console.js`, `hls.js`, `visualizer.js`, `rack-detail.css`.

### 8.2 Reference material supplied

| Reference | Read | Applies to |
|---|---|---|
| Braiins OS+ dashboard (`minerlooknfee`, WebP 1543×1136) | **yes** | `miner.html` — dense telemetry, KPI tile grid, time-series + sub-tabs, status pills, fan gauges, dark shell |
| vLLM Playground | screenshot | Studio — left config rail, centre workspace, right metrics |
| ComfyUI graph | screenshot | Studio — node canvas, typed ports |
| Mission Control "AI Fleet" | screenshot | `livestack.html` — card grid, LIVE/OFFLINE pills, latency/mode tiles |
| Gemini | screenshot | `chat.html` — sidebar + centred composer |
| Claude Code CLI | screenshot | `coder.html` — terminal aesthetic |
| Casio/TI calculators | screenshots | `ravencalc.html` — keypad, F-key row, LCD |
| Waze | screenshot | DispatchOS — map-first mobile |
| DeepSeek Harness quickstart | URL | Studio/Training — docs-and-workflow density |

**Design rule:** *"The goal is not to clone another product. Each SyMoNeuRaL application should visually communicate what class of application it is while remaining part of one coherent SyMoNeuRaL product."* Shared shell stays constant; the workspace expresses the class.

### 8.3 Per-application UI table

| Application | Page (gen?) | Reference | Preserve | Redesign |
|---|---|---|---|---|
| Miner | `miner.html` (authored) | **Braiins OS+** | live ASIC data paths | KPI tiles, hashrate chart, hash-board table, fan gauges, pool status |
| Studio | `studio.html` (authored) | vLLM + ComfyUI | 2,704 lines of graph/node/MCP | config rail, node canvas, metrics rail, model panel |
| Live Stack | `livestack.html` (**GEN**) | Mission Control | catalogue data | **edit generator** — card grid, state pills, entitlement-aware |
| Chat | `chat.html` (authored) | Gemini | streaming, voice | sidebar, composer, model chip |
| Coder | `coder.html` (authored) | Claude Code CLI | terminal surface | monospace shell, session list |
| RavenCalc | `ravencalc.html` (authored) | Casio/TI | exact symbolic engine | keypad, F-keys, LCD readout |
| DispatchOS | `share-dispatchos.html` (authored) | Waze | booking/quote flows | map-first, mobile-first, customer branding |
| Image | `image.html` (authored) | ComfyUI-lite | governor/eviction UX | params panel, gallery |
| Account | `account.html` (**GEN**) | — | scrypt copy (just synced) | **edit generator** — login/signup/app selection (§9) |
| Streamer / Live | authored | — | HLS paths | consistent player chrome |
| Sigils / Project / Gateway / Exp / Reinforce / Training | authored | — | working surfaces | shell alignment only |

**Cross-cutting REQUIRED:** responsive (mobile-first for DispatchOS), accessibility (`tests/accessibility.mjs` + `docs/ops/SMOKE-ACCESSIBILITY.md` already exist — keep green), and per-page screenshot records via `tests/run_ui_verification.mjs` → `SMOKE-APPLICATIONS.md`.

---

## 9. Customer Account / Auth / Entitlement Plan

### 9.1 What exists

**CURRENT** — `backend/apps/accounts/`: `/api/accounts/{status,signup,login,logout,me,sessions,password,signout-everywhere}`; scrypt N=131072 (128 MiB, OWASP baseline) with legacy-hash upgrade; sessions; `account.html` (generated).

**CURRENT** — `backend/apps/gateway/entitlement.py`: Ed25519 **licence** entitlements, minted operator-side, expiring, re-verified on use. Concerns *payer settled a licence for a workspace*.

**CURRENT — intended under D-3(b)** (was EXISTING-INCOMPLETE) — DispatchOS has its **own** `/api/dispatchos/{login,logout,me}` plus `tools/dispatchos_accounts.py`. D-3 is settled as **(b) keep application authentication separate, bridge identity correspondence + entitlement only**, so this separation is the design, not a defect. Measured: all 7 application auth components own; **0** shared session/login imports.

### 9.2 The gap

> **CLOSED 2026-09-02 by A-3 (`ef1a4af4`).** As written, this said: *there is no customer→application entitlement layer* — `accounts/routes.py` had zero application-mapping references, and `gateway/entitlement.py` answers "is this licence paid for," not "may this customer open DispatchOS." That gap is now closed: `apps/accounts` carries the correspondence and grant, `apps/dispatchos/authz.py` consumes it, and the check **fails closed** — an entitlement check that could not run has not passed. DispatchOS still authenticates independently of `accounts`, which is **D-3(b)** by decision. The licence-vs-access distinction below remains valid and unchanged.

Required flow vs. reality:

| Step | State |
|---|---|
| Customer enters SyMoNeuRaL | **CURRENT** |
| Account creation / login | **CURRENT** (`/api/accounts`) |
| Customer identity established | **CURRENT** |
| **Entitlement resolved** | **MISSING** |
| **Authorized applications displayed** | **MISSING** (`livestack.html` is not entitlement-aware) |
| Customer selects application | **CURRENT** (catalogue only) |
| Customer application opens | **CURRENT** (`/demo/dispatchos` exists) |

### 9.3 Plan (all **PROPOSED**)

1. **Do not build a second auth system.** `accounts` is the authority. Extend it.
2. Add an entitlement mapping — customer identity → permitted `APPLICATION_SLUG` set — as a **shared** service (`ENTITLEMENT_SLOT` per §10). Not per-customer code.
3. Make the Live Stack entitlement-aware **in the generator** (`livestack.html` is generated).
4. **Reconcile DispatchOS login with `accounts`** → **DECISION D-3** (product decision; not settled here).
5. Fail closed **per route class**, never blanket — see §9.4.

### 9.4 Route authorization — measured, 15 method+path pairs

**Revised 2026-09-01** from reading every handler. The earlier draft asserted 13 routes and
assigned no `OPERATOR_ONLY` class; both were wrong. Measured authority: **13 distinct paths,
15 method+path pairs**. Two paths pair a read with a write at *different privilege levels*,
so classification is per method+path, never per path.

#### 9.4.1 The five classes

| Class | Definition | Entitlement behaviour |
|---|---|---|
| `PUBLIC_BOOTSTRAP` | Reachable pre-authentication; needed to reach a usable state | **Never** entitlement-gated |
| `SHARED_AUTH` | Establishes or ends identity | **Never** entitlement-gated |
| `AUTHENTICATED_APPLICATION` | Requires a session; not customer-scoped | 401 unauthenticated; **no** entitlement check |
| `ENTITLEMENT_REQUIRED` | Customer-scoped data or actions | **403 fail-closed** when authenticated but unentitled |
| `OPERATOR_ONLY` | Internal operator surface | Operator role; **no customer entitlement required** |

#### 9.4.2 Authorization precedence — DECIDED

```
1. authentication            (session established, or the route is exempt)
2. route authorization class (fixed per method+path, from the matrix below)
3. class-specific check:
     ENTITLEMENT_REQUIRED -> customer entitlement
     OPERATOR_ONLY        -> operator role
4. ownership scoping        (row-level, where the handler already applies it)
```

**An operator is never denied an `OPERATOR_ONLY` route for lacking a customer entitlement.**
Operator authority and customer entitlement are separate axes; conflating them would lock the
operator out of the surface they administer.

`PUBLIC_BOOTSTRAP`, `SHARED_AUTH` and `AUTHENTICATED_APPLICATION` **must not acquire an
entitlement requirement** without separate authorization.

Ownership scoping is listed last and is deliberately **not** merged into entitlement:
entitlement asks *may this identity use this application*; ownership asks *is this row yours*.
The handlers already enforce ownership, and this plan does not change it.

#### 9.4.3 The authorization matrix — all 15 pairs

Guard column records what the handler enforces **today**. Class is the authoritative
assignment. Nothing in this table has been implemented.

| # | Method | Route | Guard today | Class | Entitlement | Reason |
|---|---|---|---|---|---|---|
| 1 | GET | `/status` | none | `PUBLIC_BOOTSTRAP` | no | Returns only on/off, assistant-connected, rates-configured, state list. No customer data. Must answer while the surface is off |
| 2 | POST | `/login` | enabled-check | `SHARED_AUTH` | no | Establishes identity. Gating it would make entitlement unreachable |
| 3 | POST | `/logout` | **none** | `SHARED_AUTH` | no | **Deliberately usable without a valid live session** — see 9.4.4 |
| 4 | GET | `/me` | signed-in | `AUTHENTICATED_APPLICATION` | no | Identity echo, not customer payload |
| 5 | GET | `/board` | signed-in + ownership scope | `ENTITLEMENT_REQUIRED` | **yes** | Returns customer booking data |
| 6 | POST | `/bookings` | signed-in | `ENTITLEMENT_REQUIRED` | **yes** | Creates customer data |
| 7 | GET | `/bookings/{bid}` | signed-in + ownership | `ENTITLEMENT_REQUIRED` | **yes** | Per-record customer data |
| 8 | POST | `/ask` | signed-in + ownership scope | `ENTITLEMENT_REQUIRED` | **yes** | AI over the customer's own board |
| 9 | POST | `/bookings/{bid}/quote` | **operator** | `OPERATOR_ONLY` | no | Operator action against rate rules |
| 10 | POST | `/bookings/{bid}/advance` | **operator** | `OPERATOR_ONLY` | no | Mutates workflow state |
| 11 | POST | `/bookings/{bid}/message` | **operator** | `OPERATOR_ONLY` | no | Composes customer-facing text |
| 12 | **GET** | `/rules` | **operator** | `OPERATOR_ONLY` | no | Exposes pricing configuration |
| 13 | **PUT** | `/rules` | **operator** | `OPERATOR_ONLY` | no | Writes pricing configuration |
| 14 | **GET** | `/drivers` | **operator** | `OPERATOR_ONLY` | no | Personnel data |
| 15 | **POST** | `/drivers` | **operator** | `OPERATOR_ONLY` | no | Adds personnel |

```
PUBLIC_BOOTSTRAP            1
SHARED_AUTH                 2
AUTHENTICATED_APPLICATION   1
ENTITLEMENT_REQUIRED        4
OPERATOR_ONLY               7
                           ──
TOTAL                      15
```

`/rules` GET+PUT and `/drivers` GET+POST are listed as **four separate entries** on purpose.
Collapsing either pair to a path would apply one privilege rule to a read and a write, which
is how a read-only viewer silently acquires write access.

#### 9.4.4 Exemptions — the four routes that must stay reachable

| Route | Exemption | Why |
|---|---|---|
| `GET /status` | no authentication, no entitlement | An operator diagnosing a switched-off surface must be able to ask. It exposes no customer data |
| `POST /login` | no entitlement | Identity must be establishable before anything can look up an entitlement for it |
| `POST /logout` | **no authentication, no entitlement** | **Must succeed with an absent, expired or already-invalidated session.** The handler runs no enabled-check and no session check today, and that is correct: a user holding a dead cookie must still be able to clear it. Any enforcement that made logout fail would strand a session token in the browser |
| `GET /me` | authentication only, no entitlement | Answers "who am I", which an unentitled-but-authenticated caller legitimately needs in order to be told *why* they are unentitled |

The exemption list is **explicit and enumerated**, never a prefix or wildcard. A wildcard
exemption is how an entitlement-required route silently becomes exempt.

#### 9.4.5 Enforcement model — dependency seam, DECIDED

**Explicit dependency-based enforcement.** Not prefix middleware, and not entitlement logic
scattered per handler.

Measured constraint: **no route in this router uses `Depends()` today.** All guards are called
inside handler bodies. So the seam must be *introduced*, and the earlier plan's assumption of
an existing interception point was wrong.

Proposed shape — **PROPOSED, not implemented:**

```
a single authorization dependency, parameterised by class:

    require(PUBLIC_BOOTSTRAP)           -> no checks
    require(SHARED_AUTH)                -> no checks (identity may be absent)
    require(AUTHENTICATED_APPLICATION)  -> session
    require(ENTITLEMENT_REQUIRED)       -> session + customer entitlement
    require(OPERATOR_ONLY)              -> session + operator role

attached per route via the router's dependency argument, so each route's class is
declared at its definition and is greppable, reviewable, and independently testable.
```

Properties this buys, each of which the rejected alternatives lose:

- **Explicit** — a route's class is visible at its declaration, not inferred from a path prefix
- **Reviewable** — the matrix above can be diffed against the code mechanically
- **Testable** — the dependency is exercisable without driving a full request
- **Exemption-preserving** — exemptions are named routes, not pattern holes

**Existing authentication and role behaviour must remain unchanged.** The seam wraps the
existing guards; it does not replace or relax them. Entitlement enforcement is added only
where a later A-3 authorization explicitly permits it.

#### 9.4.6a FIXED ARCHITECTURE DECISIONS — D-A3-1 and D-A3-2

Authorized 2026-09-01. These are **fixed**; A-3 implementation derives strictly from them.

**D-A3-1 — Entitlement store**
- One entitlement **join table in the shared accounts store**
- Mapping is **customer account → application**
- **No entitlement row means not entitled** (fail closed)
- **Revocation must remain auditable** — never a silent delete of the historical grant
- The authorized writer is the **operator provisioning CLI**
- **No self-service grant path**
- **No new privileged admin API** as part of this decision

**D-A3-2 — Identity correspondence**
- One **nullable explicit reference** from the application's local user record to the shared account identity
- Populated **during provisioning**
- **NULL means no shared identity, therefore no entitlement** (fail closed)
- **Never infer** correspondence from username, email, or any other natural key
- **No identity-matching heuristics**
- The application's authentication, cookies, sessions, login/logout and roles stay **separate** from shared accounts

#### 9.4.6 The entitlement bridge under D-3(b) — the seam already exists

D-3 resolved to **(b)**: the customer application keeps its own authentication; entitlement is
bridged to the shared accounts authority.

**A partial bridge is already in place and is the correct starting point.** Measured: the
application's store imports password primitives *from the shared accounts module* —
`hash_password`, `check_password_or_dummy`, `WeakPassword` — while keeping its own session
store and cookie.

So D-3(b) is narrower than "build a bridge". It is **extend an existing import seam from
password hashing to entitlement lookup**:

```
today      app store  --imports-->  shared accounts (password primitives only)
D-3(b)     app store  --imports-->  shared accounts (password primitives
                                     + customer->application entitlement lookup)
```

What stays unchanged: the application's own session cookie, its own session store, its own
login and logout endpoints, and its two roles.

What is added: an entitlement lookup consulted by `require(ENTITLEMENT_REQUIRED)` only.

**Still undefined and out of scope here:** the shared entitlement store's shape, and how an
identity in the application maps to an identity in shared accounts. Both are A-3
implementation questions, not classification questions.

## 10. Customer Application Slotting Standard

**Normative source:** `SyMoNeuRaL_Customer_Application_Slotting_Architecture.md`. This section preserves its architectural meaning.

### 10.1 The core rule

> SymonSaysLLC builds SyMoNeuRaL. Symon runs on SyMoNeuRaL. Customer applications run on SyMoNeuRaL and consume shared Symon/SyMoNeuRaL capabilities **without becoming system-level components themselves**.

A customer application does **not** become a `symoneural-*` system component merely because SyMoNeuRaL hosts it.

### 10.2 Reused vs instantiated

**Reused — one shared authority, never duplicated per customer:**
`symoneural-platform` · `symoneural-network` · `symoneural-build` · `symoneural-release` · `symoneural-custody` · `symon-engine` · `symon-gateway` · `symon-api` · `symon-web` · accounts/auth · shared access/entitlement · shared release/custody · shared verification infrastructure.

**Instantiated per customer/application:**
application identity · route · API namespace · backend module · frontend surface · customer workflows · configuration · branding/content/assets · entitlement mapping · delivery/export manifest · application-specific tests · customer-specific release artifacts.

### 10.3 The 19 slot indicators

A customer is correctly slotted only when every indicator has an explicit value.

| Indicator | Meaning | Required state |
|---|---|---|
| `CUSTOMER_IDENTITY` | Customer/account identity exists | Defined |
| `APPLICATION_IDENTITY` | Application product name | Defined |
| `APPLICATION_SLUG` | Stable route/API-safe slug | Defined |
| `FRONTEND_SLOT` | Application UI location | Wired |
| `BACKEND_SLOT` | Application backend location | Wired |
| `API_SLOT` | Application API namespace | Wired |
| `CUSTOMER_ROUTE` | Preview/production customer route | Wired |
| `AUTH_SLOT` | Login/account/access path | Wired |
| `ENTITLEMENT_SLOT` | Customer accesses only authorized apps | Wired |
| `WORKFLOW_SLOT` | Customer/domain logic boundary | Defined |
| `CONFIG_SLOT` | Customer configuration boundary | Defined |
| `ASSET_SLOT` | Customer content/assets boundary | Defined |
| `SHARED_SERVICE_MAP` | Which shared services are consumed | Defined |
| `EXPORT_SCOPE` | What the customer may receive | Defined |
| `PROTECTED_EXCLUSIONS` | What may never enter an export | Defined |
| `RELEASE_IDENTITY` | Version/checksum/release info | Defined |
| `CUSTODY_RECORD` | Provenance/licensing/artifact identity | Defined |
| `TEST_PATH` | Verification path | Passing before release |
| `LIVE_STACK_ENTRY` | Appears in Live Stack | Wired when approved |

> A page existing does not make a slot complete. The slot is complete only with an explicit **customer boundary** *and* an explicit **shared-platform dependency map**.

### 10.4 Promotion rule

Customer code becomes shared platform only when **all** hold: used by multiple applications/customers **AND** responsibility is no longer customer-specific **AND** a stable shared interface exists **AND** consumers are identified **AND** shared tests exist **AND** ownership/licensing/provenance are clear. Until then it stays in the application layer.

### 10.5 Blank reusable new-customer slot template

```text
CUSTOMER_IDENTITY        <Customer-Name>
APPLICATION_IDENTITY     <Application-Name>
APPLICATION_SLUG         <application-slug>

FRONTEND_SLOT            frontend/src/app/demo/<application-slug>/
                         or site/<application-slug>.html
BACKEND_SLOT             backend/apps/<application_slug>/
API_SLOT                 /api/<application-slug>
CUSTOMER_ROUTE           /demo/<application-slug>   (or approved production route)

AUTH_SLOT                /api/accounts              (shared — do NOT fork)
ENTITLEMENT_SLOT         <customer> -> [<application-slug>, ...]

WORKFLOW_SLOT            <domain workflow 1>
                         <domain workflow 2>
CONFIG_SLOT              <customer configuration boundary>
ASSET_SLOT               <customer content/assets boundary>

SHARED_SERVICE_MAP       symon-web
                         symon-gateway
                         symon-api
                         symon-engine            (only if required)
                         accounts/auth
                         access/credits/entitlements
                         symoneural release/custody

EXPORT_SCOPE             <approved customer-scoped artifact set>
PROTECTED_EXCLUSIONS     training/corpus.jsonl
                         training/build_dataset.py
                         training/adapter*/ weights
                         GARRETT-REQUESTS.md, INTAKE.md, review/
                         .env files, tokens, secrets
                         run/, session transcripts
                         all other customers' data
                         canonical source repository history
RELEASE_IDENTITY         <version> + <sha256>
CUSTODY_RECORD           <provenance / licence / artifact identity>
TEST_PATH                backend/apps/<application_slug>/test_*.py
                         + end-to-end smoke record
LIVE_STACK_ENTRY         <wired when approved>
```

**Do not copy customer-specific business logic into a new slot.** Future customers inherit the *shape*, not Donnie's workflows.

---

## 11. Donnie / DispatchOS Reference Slot

The populated reference implementation.

> **Definition is not implementation.** The architecture document is *normative* — it says what a correct slot looks like. It is **never** evidence that something is wired on this box. Each indicator below carries a runtime state derived from repository/runtime evidence only.

**State vocabulary:**

| State | Meaning |
|---|---|
| `DEFINED` | Named in the architecture or a document. No implementation claim. |
| `PRESENT` | Artifact exists on disk |
| `WIRED` | Connected into the running system (mounted route, loaded module) |
| `VERIFIED` | Observed working at runtime this pass |
| `EXISTING-INCOMPLETE` | Partially implemented |
| `MISSING` | No implementation |

| Indicator | Value | State | Evidence |
|---|---|---|---|
| `CUSTOMER_IDENTITY` | **1 shared account** (`a3ee3403…e755`) ← **1 correspondence** ← application user id 5 | **VERIFIED** | **Provisioned 2026-09-02.** Measured: accounts **1** · correspondences **1** · other 4 users unlinked · correspondence and grant reference the **same** account id. Observed working at runtime: the linked customer authenticates through the application's own login and is authorized. Promoted from DEFINED past PRESENT and WIRED because it is not merely on disk or connected — it was **observed working this pass** |
| `APPLICATION_IDENTITY` | DispatchOS | **PRESENT** | `backend/apps/dispatchos/`, site pages |
| `APPLICATION_SLUG` | `dispatchos` | **WIRED** | Used in API namespace + route |
| `FRONTEND_SLOT` | **`backend/apps/dispatchos/page.py`** (served by `ui_router`) | **VERIFIED** | **D-4 = (a), authorized 2026-09-02.** Measured: this module serves the live route. The two candidates named earlier serve nothing — the static page is unreferenced by the backend and the Next.js directory holds 2 files. The route is extensionless and `scripts/deploy.sh` publishes `site/` at `-maxdepth 1`, so it cannot be a file there. Not migrated; serving path unchanged |
| `BACKEND_SLOT` | `backend/apps/dispatchos/` | **PRESENT** | Package on disk |
| `API_SLOT` | `/api/dispatchos` — 13 paths / **15 method+path pairs** (§9.4.3) | **VERIFIED** | Live OpenAPI; `/board` returned HTTP 401 (mounted, token-gated) |
| `CUSTOMER_ROUTE` | `/demo/dispatchos` | **WIRED** | **D-5 = (a), authorized 2026-09-02** — retained for A-4. No alias, no rename, no proxy/catalogue change for naming. Production naming reconsidered separately at customer launch. Entitlement gates the surface regardless of its name |
| `AUTH_SLOT` | **Own** `/api/dispatchos/{login,logout,me}` + own session table, own cookie, + `tools/dispatchos_accounts.py`; bridge limited to correspondence + entitlement | **VERIFIED** | **Resolved 2026-09-02 under D-3(b).** The earlier `EXISTING-INCOMPLETE` cited D-3 as *unresolved*; D-3 is settled as **(b) keep separate, bridge entitlement**, which makes separation the **intended end state**, not an incompleteness. Measured: all 7 application auth components own (login · logout · me · session create/validate/revoke · own sessions table), cookie `symon_dispatchos` unchanged, **0** shared session/login imports — only password primitives cross. Runtime-observed: provisioned customer authenticates via the application's own login (200) and receives its own cookie; app login creates **no** shared session (2 app rows vs 1 shared, from signup); an **unlinked** user logs in **200** then gets **403** *"not entitled to this application"* — denied by **entitlement, not authentication**, which is the separation working. §10 requires `Wired`; observed working this pass, so `VERIFIED` |
| `ENTITLEMENT_SLOT` | Seam: `backend/apps/dispatchos/authz.py` (`ENTITLEMENT_REQUIRED`, `_entitlement_or_403`) → `apps/accounts` (`is_entitled`) ← `store.shared_account_id`; **1 active grant** | **VERIFIED** | **A-3 `ef1a4af4`** wired it; **provisioned 2026-09-02.** Measured: **1** total grant, **1** active for this application, **0** for any other, no wildcard, no duplicate. Both sides observed at runtime: entitled customer **200** on all four protected routes; authenticated **unprovisioned** user **403** on all four with *"not entitled to this application"*. §10 requires `Wired`; the measured state exceeds it |
| `WORKFLOW_SLOT` | booking · quotes · reminders · driver assignments · review requests · intake | **PRESENT** | 15 method+path pairs cover these; not individually verified |
| `CONFIG_SLOT` | Boundary recorded in §11.4 — customer config is the operator rate-rules key in the application settings table | **DEFINED — satisfied** | **D-A4-CONFIG = Option A, authorized 2026-09-02.** §10 requires `Defined` for this indicator, and the boundary is now documented from measurement, so `DEFINED` is the satisfied state. No stronger state is evidence-supported: the boundary is a definition, not an on-disk artifact, so `PRESENT` would be a claim the evidence does not carry |
| `ASSET_SLOT` | Boundary recorded in §11.5 — the customer-asset class is measurably **empty** | **DEFINED — satisfied** | **D-A4-ASSET = Option A, authorized 2026-09-02.** §10 requires `Defined`; the boundary is documented from measurement. An empty class is a legitimate slot value, not an incomplete one. No stronger state applies — there is no artifact to be `PRESENT` |
| `SHARED_SERVICE_MAP` | see §11.1 — 5 required + 1 conditional dependency; 2 platform services explicitly outside the map | **DEFINED — satisfied** | **Corrected 2026-09-02.** §10 requires `Defined` = *"named in the architecture or a document. No implementation claim."* No specification language requires a mapped service to be active, enabled, running, wired or runtime-verified. Every service has known identity, role, seam, ownership and accurately recorded state, and unavailable ones are explicitly represented. The prior `EXISTING-INCOMPLETE` came from judging this slot against a `VERIFIED` runtime standard §10 does not ask for. **A-4 does not authorize or require service enablement.** |
| `EXPORT_SCOPE` | `backend/apps/dispatchos/EXPORT-SCOPE.manifest` — 7 entries: the page module + 6 application-specific source modules | **POPULATED, VERIFIED** | **Option B authorized 2026-09-02.** Boundary reviewed per-module: all 7 are category 1 (application-specific). `apps/accounts` is category 2 (shared platform, multiple consumers) and is **excluded** — returned for separate authorization. Tests, runtime state, operator tooling, infrastructure config and prior internal archives all excluded. Verified through the A-2 exporter: stage 1 selected 7, stage 2 passed, **no archive written**. **Export/distribution NOT authorized** |
| `PROTECTED_EXCLUSIONS` | Application-specific statement recorded in §11.6 | **DEFINED — satisfied** | **Authorized 2026-09-02.** Twelve classes recorded, each with evidence; global stage-2 protections remain the mechanical authority (17 patterns, verified enforcing). Existing 7-entry manifest **complies** — 0 violations across 15 checks. `DEFINED` is the satisfied state: §10 requires `Defined`, and the statement is a definition, not an on-disk artifact |
| `RELEASE_IDENTITY` | A-2 export manifest: source commit + per-file SHA-256 | **AUTHORIZED (A-4 only)** | **D-11 = (d) for A-4 only, authorized 2026-09-02.** Identity is asserted, not signed |
| `CUSTODY_RECORD` | **UNSIGNED — external release NOT authorized** | **AUTHORIZED (A-4 only)** | D-11 is **DECIDED** as of 2026-09-02 (owner ruling, §22) — but the ruling is *architecture only*: **no signing key exists, no artifact is signed**, and no key generation, key storage, signing infrastructure, artifact signing, or external distribution is authorized. **A-4 completion must never be represented as external-release readiness** |
| `TEST_PATH` | `backend/apps/dispatchos/test_route_authorization.py` (in-package, 22 tests) + `backend/apps/test_dispatchos.py`, `test_dispatchos_security.py`, `frontend/tests/dispatchos-slice.test.mjs` | **PRESENT — PASSING** | **A-3 `ef1a4af4`** added the in-package suite; the other three predate it. Regression repaired 2026-09-02: **159 passed / 0 failed** across the full set, matching the pre-A-3 baseline. Fixture provisions a real entitlement; the class was not weakened, bypassed or mocked, and the deny side (T3/T15/T18/T21) still passes. See §11.3 |
| `LIVE_STACK_ENTRY` | linked from `index.html`, `livestack.html` | **WIRED** | Catalogue entry present; not entitlement-aware |

#### 11.3 REGRESSION — 17 failures introduced by A-3 (`ef1a4af4`)

**Measured 2026-09-02, by comparison against the pre-A-3 baseline:**

| Commit | `test_dispatchos.py` + `test_dispatchos_security.py` |
|---|---|
| `a5fb0fbb` (pre-A-3) | **48 passed, 0 failed** |
| `94156d39` (now) | **31 passed, 17 failed** |

**Cause.** A-3 attached `ENTITLEMENT_REQUIRED` to `/board`, `/bookings`, `/bookings/{bid}` and `/ask`. These suites predate entitlement and provision none, so those routes now return **403** and the assertions fail — e.g. `KeyError: 'bookings'` where a board payload was expected.

**The behaviour is correct; the tests are stale.** 403 for an authenticated-but-unentitled caller is exactly what A-3 was authorized to do and what T3 asserts. These suites assert the pre-entitlement contract.

**Why it was not caught earlier — recorded so it is not repeated.** The regression set used during A-3 was `test_accounts.py`, `apps/dispatchos/`, `test_export_snapshot.py`, `test_control_models.py`. The `apps/dispatchos/` path matched only the in-package suite; `backend/apps/test_dispatchos.py` and `test_dispatchos_security.py` sit **outside** the package directory and were never in the set. A regression set that misses the suites most affected by the change is the defect.

**RESOLVED 2026-09-02.** `Base.setUp` now provisions a real shared identity and an active grant for each seeded user, against a throwaway shared store. Result: **48 passed / 0 failed**, matching the baseline exactly; **159 passed / 0 failed** across the full set.

The entitlement is real, not mocked. `ENTITLEMENT_REQUIRED` still guards 4 routes, the lookup is unchanged, no production file was touched, and the deny-side tests still pass.

**A second defect surfaced during the repair, and it was mine.** Both the new fixture and A-3's own `test_entitlement.py` called `importlib.reload` on the shared accounts module. That module is where `store.py` binds `WeakPassword`, `hash_password` and `validate_password` **at import time**, so reloading replaced those class objects and left `store` raising a `WeakPassword` a later suite's `assertRaises` no longer recognised. Two tests in a third file failed *only when one of these ran first* — passing in isolation, failing in a set, which is the worst shape a test defect can take. Both reloads are removed; the reload was never necessary because the database path is read per connection. Order-independence verified in both directions.

#### 11.4 `CONFIG_SLOT` — the configuration boundary

Authorized 2026-09-02 (D-A4-CONFIG = Option A). Recorded from measurement, not inference.

| Category | Content | Export position |
|---|---|---|
| **Customer-specific configuration** | The operator's rate rules — **one key** in the application settings table, customer-authored at runtime through an operator-only route | **Not exportable.** It resides in the runtime database, which exporter stage 2 refuses as runtime state |
| **Application defaults** | **None.** No default rule set ships; an unconfigured application renders blank by design rather than a confident zero | Nothing to export |
| **Shared / platform configuration** | The shared subsystem's enable flag and session secret | Platform-owned; never customer content |
| **Runtime / operator configuration** | Surface enable flag and database path, from the operator-owned environment file | Operator-owned; never customer content |
| **Protected internal configuration** | Secrets, `.env` files, credentials, private keys, signing material, api keys, runtime state, mode-restricted ledgers, internal review material, repository history, internal infrastructure configuration | **Never exportable** — enforced mechanically by stage 2, independent of any manifest |

**Resulting export position: no configuration of any category enters the customer export.** The manifest contains zero configuration files, and that is correct.

**Deliberately not built.** No customer-configuration export mechanism exists, rate rules are not extracted from the runtime database, and **no exception was added to the runtime-state refusal**. Whether customer configuration may ever leave the runtime database is a *separate* safety decision and is not answered here — carving a hole in a refusal for convenience is the failure shape this project keeps guarding against.

#### 11.5 `ASSET_SLOT` — the asset boundary

Authorized 2026-09-02 (D-A4-ASSET = Option A). Recorded from measurement.

| Category | Content | Export position |
|---|---|---|
| **Customer-owned / customer-specific assets** | **None exist.** Measured: no asset directory, no upload path, no binary storage | Class is **empty**, not unknown |
| **Application-default assets** | **None.** The page is self-contained — one inline style block, one inline script block, **zero** external references | Presentation is source and travels as source |
| **Shared platform assets** | The shared brand directory and shared site CSS/JS | Platform-owned, single authority, never per-customer, never exported |
| **Protected internal assets** | Adapter weights, signing material, secret material, model payloads | **Never exportable** — enforced by stage 2 |
| **Generated / transient assets** | **None** for this application. No output directory, no generated media | — |

**Resulting export position: no asset of any category enters the customer export.** The manifest contains source only, and that is correct.

**Explicitly NOT a customer asset: the static preview page in the site tree.** D-4 measured that the live route renders from the page module and that this file is unreferenced by the backend — it serves nothing. Exporting it would deliver a **stale duplicate that can silently diverge** from the page the customer actually sees, which is worse than exporting nothing.

**Deliberately not built.** No asset directory was created, the static preview page was not added to the export, and no asset was moved, copied, classified or duplicated. **The export manifest is unchanged, because neither decision requires a manifest change.**

#### 11.6 `PROTECTED_EXCLUSIONS` — what must never enter this application's customer export

Authorized 2026-09-02. Recorded from evidence, not inference.

**Two enforcement tiers, and the difference matters.** Classes 1–9 are refused *mechanically* by
exporter stage 2 whatever a manifest says. Classes 10–12 are **not** global protected classes:
tested this pass, a manifest naming them **passes stage 2 unflagged**, so they rest on manifest
discipline and review. That is the same gap D-12 tracks, restated here per class so the
distinction is not lost.

| # | Class | This application's artifacts | Enforcement |
|---|---|---|---|
| 1 | **Secrets and credentials** | Any credential file; the application stores password hashes, never plaintext | **stage 2** — 4 patterns |
| 2 | **`.env` / operator configuration** | The operator-owned environment file supplying the surface flag and database path | **stage 2** — 2 patterns |
| 3 | **Private keys and signing material** | None exist for this application. D-11 is now **DECIDED** (OpenPGP, org authority — §22) but **no key has been generated**, so no signing material exists yet. **P1 (§22.1) must extend these patterns before any key is created** — measured: `.asc`/`.gpg`/`.kbx`/`.gnupg/`/extensionless private keys currently pass stage 2 | **stage 2** — 2 patterns |
| 4 | **API keys and tokens** | Session tokens are hashed in the runtime store; api-key files are global-protected | **stage 2** |
| 5 | **Runtime databases and runtime state** | The application database and its WAL/SHM companions — **and the customer's rate rules live inside it** (§11.4) | **stage 2** — verified refusing |
| 6 | **Restricted ledgers / custody records** | Mode-restricted ledgers; no custody record exists for this application (unsigned per D-11) | **stage 2** |
| 7 | **Internal review / audit material** | Internal review directory; the in-package smoke record is internal verification evidence | **stage 2** for the directory; the smoke record by manifest discipline |
| 8 | **Repository history / development metadata** | Repository history; build caches | **stage 2** |
| 9 | **Model payloads and adapter weights** | Adapter weights and model payloads; this application loads none, but the assistant layer can reach shared inference | **stage 2** |
| 10 | **Internal infrastructure configuration** | Reverse-proxy configuration. **Evidence:** the prior internal archive carried 5 such paths | **manifest discipline** |
| 11 | **Shared platform assets / configuration** | The shared brand directory (135 files), shared site CSS/JS, and the shared accounts module — category 2, ruled not exportable | **manifest discipline** |
| 12 | **Application-specific protected classes** | **(a)** the four prior export archives — their own manifests read `customer_deliverable=no` / `internal_archive_only=yes` and they carry infrastructure configuration; **(b)** the operator provisioning CLI — it is the **sole entitlement writer**, so shipping it hands over the grant mechanism; **(c)** the static preview page — unreferenced by the backend, would ship a stale duplicate (§11.5); **(d)** test suites — excluded by the Option C refusal | **manifest discipline** |

**Authority and scope of this statement**

- The **existing exporter stage-2 protections remain the mechanical enforcement authority.** 17 patterns, verified enforcing this pass.
- **This task created no new exporter rules.** Exporter code and policy classes are unchanged.
- The statement **documents** the boundary for this application; it does **not** replace or narrow global enforcement. Where the two overlap, global enforcement wins and is not weakened.
- Classes 10–12 have **no mechanical guard**. Whether one should exist is D-12, which remains open and unimplemented.

**Manifest compliance — verified, 0 violations**

The authorized 7-entry manifest was checked against every class above: **0 occurrences** of runtime
state, `.env`, credentials, keys, tokens, review material, repository history, infrastructure
configuration, prior archives, operator tooling, static site tree, shared brand assets, training
material, tests or smoke records. **No currently authorized export entry conflicts with any
exclusion.** No manifest change was required and none was made.

#### 11.1 `SHARED_SERVICE_MAP` — the application's dependency map

**This is a dependency-map definition, not a runtime-consumption scorecard.** The earlier
version of this section was the latter, and judging the slot by its strictest column is what
produced a false `EXISTING-INCOMPLETE`: §10 requires **`Defined`**, and the vocabulary defines
that as *"named in the architecture or a document. **No implementation claim.**"* A state that
disclaims implementation cannot require running services, and no language in §10 or the
normative architecture requires a mapped service to be active, enabled, running, wired or
runtime-verified.

So: **architectural membership and runtime availability are tracked separately below.** A
service that is disabled, offline, absent or blocked can be *fully defined*. **A-4 neither
authorizes nor requires enabling any service.**

##### Required dependencies

Per the architecture's own reference map for this customer:

| Shared dependency | Role for this application |
|---|---|
| Shared API | Hosts the application's API namespace |
| accounts/auth — identity + entitlement bridge | The D-3(b) bridge: correspondence lookup + entitlement check |
| Shared web | Web runtime / frontend delivery |
| Shared gateway | Request routing to the application |
| Shared project/application services | Shared application-layer services |

##### Conditional dependency

| Shared dependency | Condition |
|---|---|
| Shared inference / Symon runtime | **"when required"** — the architecture states this conditionally in three separate places. The application's assistant layer can reach it, and degrades to a stated non-model answer when it is unavailable. Offline with zero model payloads does **not** make the map undefined |

##### Platform services outside this application's dependency map

Real shared/platform services that this application does **not** consume. Their existence is
preserved in the platform record; they are simply not this application's dependencies.

| Platform service | Exists | Consumed by this application | Therefore |
|---|---|---|---|
| Credits / metering | yes — 3 tables defined in the metering module | **no** — measured **0** references | outside this map |
| Release / custody | yes — export manifest + the A-2 exporter | **no** — measured **0** references; it governs *delivery*, not application runtime | outside this map |

**Release/custody, additionally:** **D-11 is DECIDED** (architecture, 2026-09-02, §22) while **no key exists and nothing is signed**; release/custody remains
unavailable for external release. **That runtime/release condition does not make it an
application dependency** — the two questions are independent.

*Note on the earlier count:* a previous grep appeared to show one credits reference. It matched
the word *"parameters"* inside a comment about scrypt, not the metering module. Actual
consumption is zero.

##### Current runtime / implementation status — recorded separately

State is recorded for completeness and **is not** an input to whether the map is defined.

| Service | Measured state | In this map? |
|---|---|---|
| Shared API | **active — runtime verified** (HTTP 200) | required |
| accounts/auth bridge | **enabled, consumed, verified** — entitlement lookup exercised end to end | required |
| Shared web | **defined but disabled** — unit installed, repo template present | required |
| Shared gateway | **defined but disabled** — unit installed, Rust crate built | required |
| Shared inference | **defined but offline**, 0 model payloads — conditional | conditional |
| Shared project services | **defined / ready** per measured rack state | required |
| Credits / metering | **platform service, absent / not implemented** | **not a dependency** |
| Release / custody | **platform delivery service, blocked on D-11** | **not a dependency** |

**None of disabled, offline, absent or blocked means undefined.** Each has a known identity,
role, seam, ownership boundary and accurately recorded state, and each unavailable service is
**explicitly represented rather than silently omitted** — which is what a defined map requires.

#### 11.7 A-4 completion determination — 2026-09-02

All 19 indicators evaluated against their **actual §10 required states**:

```
indicators at or above requirement   19 of 19
indicators below requirement          0
```

# A-4 IS COMPLETE

**No additional runtime enablement is required for A-4 completion.** Not shared web, not the
gateway, not inference, not credits. Each is an implementation prerequisite for *other* work
and none is required by any A-4 indicator's stated requirement.

**A-4 complete is NOT external release authorized.** These are different claims and must not
be conflated:

| | Status |
|---|---|
| **D-11** signing authority and key custody | **DECIDED 2026-09-02** — architecture only (§22). No key exists; no artifact signed; **external release still NOT authorized** |
| **External release** | **NOT authorized** — custody is unsigned |
| **D-12** mechanical ownership guard | **unimplemented**, explicitly outside A-4 |
| Shared web / gateway / inference / credits implementation | **separately gated** where applicable |

A-4 completion means exactly one thing: **every indicator is at or above the state §10 requires of it.** It does not mean all 19 are wired, and it does not mean all 19 are runtime-verified — **6 of 19 are** (§11.2). Four indicators are satisfied at `DEFINED` because `Defined` is what §10 asks for; two are `AUTHORIZED (A-4 only)` under a scope limit. It says nothing about whether an artifact may leave this box — that remains gated on D-11 and remains unauthorized.

#### 11.2 Reference-slot summary — regenerated 2026-09-02

> **This table was previously a pre-A-series snapshot and was stale.** It listed
> `SHARED_SERVICE_MAP`, `AUTH_SLOT` and `FRONTEND_SLOT` as `EXISTING-INCOMPLETE` and five
> indicators as `MISSING`, all of which have since been resolved. The buckets below are
> **regenerated mechanically from the 19 rows of the §11 indicator table above**, not restated
> from an earlier pass. The indicator table is the authority; §11.7 carries the completion
> determination.

| Bucket | Count | Indicators |
|---|---|---|
| **VERIFIED** | 5 | `CUSTOMER_IDENTITY`, `FRONTEND_SLOT`, `API_SLOT`, `AUTH_SLOT`, `ENTITLEMENT_SLOT` |
| **POPULATED, VERIFIED** | 1 | `EXPORT_SCOPE` |
| **WIRED** | 3 | `APPLICATION_SLUG`, `CUSTOMER_ROUTE`, `LIVE_STACK_ENTRY` |
| **PRESENT** | 3 | `APPLICATION_IDENTITY`, `BACKEND_SLOT`, `WORKFLOW_SLOT` |
| **PRESENT — PASSING** | 1 | `TEST_PATH` |
| **DEFINED — satisfied** | 4 | `CONFIG_SLOT`, `ASSET_SLOT`, `SHARED_SERVICE_MAP`, `PROTECTED_EXCLUSIONS` |
| **AUTHORIZED (A-4 only)** | 2 | `RELEASE_IDENTITY`, `CUSTODY_RECORD` |
| **EXISTING-INCOMPLETE** | **0** | — |
| **MISSING** | **0** | — |

**Total 19.** **6 of 19 indicators are runtime-verified** (the 5 `VERIFIED` plus `EXPORT_SCOPE`,
whose stage-1/stage-2 exporter behaviour was observed this pass). The reference slot is a
working application with a **complete** customer slot as §10 defines completeness — see §11.7
for what that does and does not authorize.

**`DEFINED — satisfied` is not a shortfall.** For `CONFIG_SLOT`, `ASSET_SLOT`,
`SHARED_SERVICE_MAP` and `PROTECTED_EXCLUSIONS`, §10 requires `Defined`. Each is a boundary or
a map — a definition, not an on-disk artifact — so no stronger state is evidence-supported, and
reaching for one would be a claim the evidence does not carry.

**`AUTHORIZED (A-4 only)` is a scope limit, not a completion.** `RELEASE_IDENTITY` and
`CUSTODY_RECORD` satisfy A-4 under D-11 = (d), which is explicitly *for A-4 only*. Identity is
asserted, not signed. **D-11 is now DECIDED as architecture (§22), and external release remains NOT authorized** — the ruling settles *how* to sign, not *whether* to ship. No key exists and no artifact is signed.

**Naming compliance:** DispatchOS stays an application identity. **`symoneural-dispatchos` must not be created.** Its store is `run/dispatchos.db`; the surface is gated by `SYMONEURAL_DISPATCHOS_ENABLED` and currently reports HTTP 401 when unauthenticated (mounted, token-gated) — i.e. wired and asking for auth.

**Remaining risks in the reference slot** (superseding the earlier "zero tests, no entitlement,
no export scope, parallel auth" — all four were resolved this pass): custody is unsigned;
`LIVE_STACK_ENTRY` is not entitlement-aware, so the catalogue advertises the surface to
unentitled viewers; `WORKFLOW_SLOT` is `PRESENT` on route coverage but no workflow was
individually exercised end-to-end.

---

## 12. Customer Export / Download Plan

### 12.1 Hard state

> **SUPERSEDED 2026-09-02.** The statement below was true when this section was written and is now false. `tools/export_snapshot.sh` **EXISTS** — delivered by A-2, commit `728df639`, 192 lines, fail-closed, stage-2 enforcement proven by sabotage. The blocking prerequisite named here is **resolved**. Retained for the audit trail; do not read it as current state.

~~**`tools/export_snapshot.sh` DOES NOT EXIST.** Verified: `ls` → *No such file or directory*.~~ `docs/ops/EXPORTS.md` rule 4 names it as the only sanctioned path, and it is now that path. **Export/distribution of any archive remains NOT authorized** — the tool existing is not permission to run it for release.

### 12.2 Policy (unchanged, authoritative)

1. **No whole-repo zip exports, ever.**
2. Protected: `training/corpus.jsonl`, `training/build_dataset.py`, `training/adapter/` weights.
3. Also excluded: `GARRETT-REQUESTS.md`, `INTAKE.md`, `review/`, `.env`, tokens, `run/`, transcripts.
4. Only sanctioned path: `tools/export_snapshot.sh` — excludes the above, writes an EXPORT-MANIFEST naming the source SHA, and **fails** if a protected path is present.

The architecture reinforces this: customer download must be application-scoped, manifest-driven, checksummed, fail-closed, and must **not** become a whole-project export.

### 12.3 Architecture — positive allow-list, then independent enforcement

**The export is CONSTRUCTED from an explicit allow-list. It is never the repository minus a deny-list.**

```
WRONG:   whole repository  −  deny-list      ← one missed pattern leaks
RIGHT:   ∅  +  explicit customer/application ALLOW-LIST
             then independently enforce global exclusions on the result
```

Deny-list-only architecture fails open: anything nobody thought to exclude ships. Allow-list construction fails closed by default — an artifact must be *named* to be included.

**Two independent stages, both must pass:**

**Stage 1 — Construct from allow-list.** Start empty. Add only paths named in that customer/application's `EXPORT_SCOPE` manifest. Anything unnamed is absent by construction.

**Stage 2 — Independently enforce exclusions** over the constructed set (defence in depth; presence of any aborts):
protected training material (`training/corpus.jsonl`, `training/build_dataset.py`, `training/adapter*/`) · canonical repository source/history · secrets, tokens, `.env` · internal audit/evidence (`review/`, `GARRETT-REQUESTS.md`, `INTAKE.md`) · runtime state (`run/`, transcripts) · **all other customers' data** · non-deliverable internal assets.

Stage 2 is not redundant: it catches an over-broad allow-list entry (e.g. a directory glob that later gains a protected file).

Required properties: customer-scoped · application-scoped · manifest-driven · fail-closed · versioned · checksummed · custody-recorded.

### 12.4 Build order

1. **REQUIRED** — `tools/export_snapshot.sh`: allow-list construction, independent exclusion enforcement, EXPORT-MANIFEST with source SHA, checksum, non-zero exit on any violation.
2. **PROPOSED** — per-application `EXPORT_SCOPE` allow-list manifest for DispatchOS.
3. **PROPOSED** — entitlement check before any export (§9.4 — `ENTITLEMENT_REQUIRED`).
4. **PROPOSED** — download UX inside the authorized application.
5. **REQUIRED** — the negative test below.

### 12.5 Fail-closed negative test — isolated fixture only

**Never plant a sentinel into real protected paths.** Not `training/corpus.jsonl`, not protected training paths, not canonical project history, not another customer's data, not live runtime state. The test builds a **disposable temporary fixture tree** resembling the export input and plants the sentinel there.

```
  tmpdir fixture tree
    ├── allowed/            (named in a fixture EXPORT_SCOPE)
    └── corpus.jsonl        ← SENTINEL, fixture-only
```

Must prove **all three**:

| # | Assertion |
|---|---|
| 1 | Protected fixture present → exporter exits **non-zero** |
| 2 | **Zero customer archive emitted** — no partial/truncated zip on disk |
| 3 | The failure is **recorded** (error names the offending path class, without printing contents) |

A happy-path-only test proves nothing. Assertion 2 matters most: a tool that detects the violation *after* writing an archive has already produced the artifact that must not exist.

---

## 13. Runtime / Library / Binary Shipping Matrix

Distinguishes source → build → generated artifact → installed runtime → package → customer delivery.

| Component | Source (tracked) | Build authority | Generated artifact | Runtime location | Config | Launcher/service | Consumer |
|---|---|---|---|---|---|---|---|
| **Inference API** | `backend/api.py`, `backend/apps/` | none (interpreted) | — | in place | `/etc/symoneural/api.env` + drop-ins | `symoneural-api.service`, `control/launch-api.sh` | all surfaces |
| **LLM engine** | `references/` (vendored) | `tools/fork_engines.sh` | `engines/symoneural-llm/**` (**gitignored**) | `engines/` | governor | spawned on demand | chat, remix |
| **Diffusion engine** | `references/` | `tools/fork_engines.sh` | `engines/symoneural-diffuse/**` (**gitignored**) | `engines/` | governor | spawned on demand | image |
| **Render UI** | `references/` | `tools/fork_render_ui.sh` | `engines/symoneural-ui/**` (**gitignored**) | `engines/` | — | `scripts/symoneural-ui.sh` :8188 | Studio |
| **Gateway (Rust)** | `backend/apps/gateway/` + `Cargo.toml` | `ops/build-gateway.sh` | `target/` binary (**gitignored**) | runtime dir | `symoneural-gateway.service` | `scripts/install-gateway.sh` | licensing |
| **Web (Go)** | `web/symoneural-web/{main.go,go.mod,go.sum,VERSION}` | `ops/build-symoneural-web.sh` | `build/symoneural-web` 73 MB (**gitignored**) | runtime dir | `symoneural-web.service` | unit | site |
| **Static site** | `site/*.html` + `tools/build_*.py` | generators + `scripts/deploy.sh` | `/var/www/symoneural` | webroot | Caddy | `scripts/deploy.sh` | public |
| **Reverse proxy** | `ops/Caddyfile` | — | — | Caddy | Caddyfile | `caddy.service` | public |
| **Models** | none (fetched) | `scripts/fetch-*.sh` | `backend/models/**` (**gitignored**) | `backend/models/` | `api.py` active set | `modelops-stage.sh` | chat/image/voice |
| **Adapters** | `training/train_lora.py` | QLoRA run | `training/adapter*/` (**PROTECTED**) | `training/` | — | — | chat |
| **Debian pkg** | all above | `scripts/build-deb.sh` | `.deb` → `opt/symoneural/{bin,scripts}` | installed | — | `ops/install-runtime.sh` | operator |
| **APT repo** | `.deb` | `scripts/build-apt-repo.sh` | repo tree | published | — | — | operator |

**Release chain per component:** source → build → binary/library → runtime location → configuration → launcher/service → consumer → smoke verification (`ops/verify-runtime.sh`) → package (`build-deb.sh`) → checksum → provenance/licence (`PROVENANCE.*`, `LICENSES.md`) → custody verification. Rollback: `ops/rollback-runtime.sh`.

> **Generated binaries are not committed to git merely because shipping needs them.** Precedent set this session: the 73 MB Go binary is gitignored while its four reproducing sources are tracked (`-trimpath`, identical digest across two clean builds). `/engines/` is gitignored for the same reason. Distribution is via `.deb`/APT, not via git.

**Gaps (bounded claim):** `symoneural-gateway.service` and `symoneural-web.service` are installed but **disabled/inactive**. **No successful run for the current binaries at the current HEAD (`1df394f0`) was established in this planning inventory.** That is not a claim that they have never run historically — no repository evidence was examined that would support the stronger statement. No end-to-end release rehearsal was found for the current HEAD.

---

### 13.2 Delivery matrix — package / architecture / SDK / feed / signing

Section 13.1 above is the **runtime** matrix. This is the **delivery** matrix. Maturity is tracked separately because these are not equivalent: *source portable → build target configured → build succeeded → package generated → package installed → runtime tested → release artifact → checksum recorded → provenance/licence recorded → artifact signed → signature verified → custody verified.*

#### 13.2.1 The two Yocto trees — do not conflate

| Tree | Contents | Role | State |
|---|---|---|---|
| `/home/google/Symoneural/yocto/` | 12 layers `meta-symoneural-{aws,bsp,core,darwin,extended,filesystem,initramfs,kernel,mingw,networking,python,quail}`; 70 files tracked in git | **Source authority**, versioned with the repo | **CURRENT** |
| `/yocto/` (492 G partition, 60 % used) | `meta-symoneural`, `meta-symoneural-bsp`, `meta-openembedded`, `meta-cryptocurrency`, `openembedded-core`, `bitbake`, `build-symoneural/`, `artifacts/` | **Build host**, outside the repo, untracked | **CURRENT** |

An earlier draft searched only the repo and concluded "no IPK authority." **That was wrong** — it missed `/yocto`. Corrected below from build evidence.

#### 13.2.2 Package format authority

| Format | Configuration authority | Evidence | State |
|---|---|---|---|
| **DEB** (repo-local) | `scripts/build-deb.sh` → `opt/symoneural/{bin,scripts}`, `Architecture: all` | script present | **CURRENT** (arch-neutral only) |
| **DEB** (Yocto) | `meta-symoneural/conf/distro/symoneural.conf` `PACKAGE_CLASSES ?= "package_deb"`; 8 `*-deb.conf` multiconfigs | 44,828 `.deb` produced | **CURRENT** |
| **IPK** (Yocto) | 8 `*-ipk.conf` multiconfigs `PACKAGE_CLASSES = "package_ipk"` | 31,380 `.ipk` produced | **CURRENT** |
| **RPM** | none | no `deploy/rpm` | **MISSING** (not a target) |

Active build config: `MACHINE = "symoneural-x86-64"`, `DISTRO = "symoneural"`.

#### 13.2.3 Architecture × format — measured artifact counts

`/yocto/artifacts/<arch>/<format>/` — **76,208 package files total.**

| Architecture | DEB pkgs | DEB feed idx | IPK pkgs | IPK feed idx | SDK `.sh` | State |
|---|---|---|---|---|---|---|
| `arm` | 9,641 | 9 | 9,495 | 10 | 2 | **CURRENT** |
| `arm64` / aarch64 | 10,093 | 9 | 9,907 | 10 | 4 | **CURRENT** |
| `x86` | 12,079 | 9 | 11,978 | 10 | 2 | **CURRENT** |
| `x86-64` / amd64 | 13,015 | **0** | **— none —** | — | 5 | **EXISTING-INCOMPLETE** |

**Two concrete gaps, both on the primary architecture:**
1. `x86-64/ipk` **does not exist** — the only missing arch/format cell. 16 multiconfigs are defined including `x86-64-ipk.conf`, so the target is *configured* but its output was not produced.
2. `x86-64/deb` has **0 feed index files** while all six other cells have 9–10. Packages exist; the consumable feed does not.

Multiconfig coverage (**CURRENT** as configuration): `{x86, x86-64, arm, arm64, qemux86, qemux86-64, qemuarm, qemuarm64} × {deb, ipk}` = 16.

> Configuration is not output. A multiconfig existing does **not** prove a package was generated for that target — `x86-64-ipk.conf` is exactly that case.

#### 13.2.4 SDK / eSDK

| Item | Evidence | State |
|---|---|---|
| SDK installers | 13 `.sh` under `artifacts/*/sdk/` (x86-64 ×5, arm64 ×4, arm ×2, x86 ×2) | **CURRENT** |
| eSDK | no `populate_sdk_ext` evidence found | **UNKNOWN** |
| SDK↔release correlation | not established | **UNKNOWN** |

#### 13.2.5 Feeds

| Item | Evidence | State |
|---|---|---|
| DEB/IPK feed indexes | 6 of 8 cells carry 9–10 index files | **EXISTING-INCOMPLETE** |
| `x86-64` feed index | 0 files | **MISSING** |
| Repo-local APT publication | `scripts/build-apt-repo.sh` | **CURRENT** |
| Feed publication authority (Yocto artifacts) | none identified | **UNKNOWN** |

#### 13.2.6 Signing — the largest delivery gap

| Item | Evidence | State |
|---|---|---|
| Unsigned build artifacts | 76,208 packages, **zero** `.gpg` / `.sig` / `InRelease` under `/yocto/artifacts` | **CURRENT (all unsigned)** |
| Signing capability (repo APT) | `build-apt-repo.sh` references `gpg`, `--sign`, `InRelease` | **EXISTING-INCOMPLETE** |
| Signing authority / key custody | not identified | **UNKNOWN** |
| Signature verification authority | none | **MISSING** |
| Private-key handling policy | none documented | **MISSING** |

> **No shipped artifact is currently signed.** Signing capability exists in the repo-local APT path only and was not applied to the Yocto artifact tree. This is **REQUIRED** before external distribution.

#### 13.2.7 Native / CUDA identity

| Item | Measured | State |
|---|---|---|
| CUDA toolchain | `nvcc` release **13.3** | **CURRENT** |
| Driver | **610.57.04** | **CURRENT** |
| Compute capability | **12.0** (Blackwell) | **CURRENT** |
| Target compute capability policy | not documented | **UNKNOWN** |
| CUDA/runtime ABI record | not documented | **MISSING** |
| Dynamic library identity record | not documented | **MISSING** |
| `symon-cuda-test` model-free verification | named in Core Identity; **no CLI authority found** | **MISSING** |

The architecture names `symon-cuda-test` (CUDA-only, GPU allocation, kernel execution, transfer verification, **model-free validation**). Given §4.1.1 (zero model payloads), a model-free CUDA verification path is the *only* way to verify the engine today. **REQUIRED.**

#### 13.2.8 Architecture-neutral vs architecture-tied packaging

Per Q4, arch-neutral packaging is **not** the intended end state.

| Component | Payload | Correct packaging | Current |
|---|---|---|---|
| API, apps, tools, scripts | Python / shell | arch-neutral — correct | `Architecture: all` **CURRENT** |
| Static site | HTML/CSS/JS | arch-neutral — correct | **CURRENT** |
| Gateway | **Rust binary** | arch-tied | `Architecture: all` — **INCORRECT** |
| Web | **Go binary** (73 MB) | arch-tied | `Architecture: all` — **INCORRECT** |
| Engines (llm/diffuse/ui) | **native + CUDA** | arch-tied + compute-cap | not in repo `.deb` — **EXISTING-INCOMPLETE** |
| CUDA libraries | **native** | arch-tied + ABI | **UNKNOWN** |

> **Defect:** `scripts/build-deb.sh` declares `Architecture: all` unconditionally. Any package carrying the Rust or Go binary would be mislabelled arch-neutral while containing arch-specific native output. → **DECISION D-9**.

#### 13.2.9 Delivery maturity by target

| Maturity stage | x86-64 | x86 | arm64 | arm |
|---|---|---|---|---|
| Source portable | ✅ | ✅ | ✅ | ✅ |
| Build target configured | ✅ | ✅ | ✅ | ✅ |
| Build completed | ✅ | ✅ | ✅ | ✅ |
| Package generated (DEB) | ✅ | ✅ | ✅ | ✅ |
| Package generated (IPK) | ❌ | ✅ | ✅ | ✅ |
| Feed index generated | ❌ | ✅ | ✅ | ✅ |
| Package installed | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Runtime tested | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Release artifact produced | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Checksum recorded | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Provenance/licence recorded | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Artifact signed | ❌ | ❌ | ❌ | ❌ |
| Signature verified | ❌ | ❌ | ❌ | ❌ |
| Release/custody verified | ❌ | ❌ | ❌ | ❌ |

Everything below "package generated" is unproven for **every** architecture. Images and packagegroups exist in `meta-symoneural/recipes-core/images`, but **an image is not evidence that a runtime payload package exists for every intended architecture.**

*All `/yocto` inspection this pass was read-only: no BitBake runs, no config edits, no package/feed/SDK generation.*

---

## 14. Proposed INTAKE Assignments

**`INTAKE.md` has NOT been modified.** These are proposals for you to accept.

---
**A-1 — Create `control/models/` operator surface** — **DELIVERED `a5fb0fbb`**
*Reason:* No single place to inspect/manage models; authorities are scattered and undocumented for operators.
*Existing:* `modelops_inventory.py`, `modelops-stage.sh` (8 modes), `fetch-*.sh`, `gpu-governor.sh`, `training/`.
*Missing:* Operator-facing launchers + README.
*Affected:* `control/models/` (new only).
*Dependencies:* none — additive.
*Risk:* **Low** — read-mostly wrappers, no live path touched.
*Excludes:* No model downloads. No new model-management implementation. No conversion/quantization until **D-6**.
```
check: exists control/models/README.md
check: exists control/models/models-list.sh
check: grep modelops_inventory -- control/models/models-list.sh
check: ngrep "import json" -- control/models/models-list.sh   # must wrap, not reimplement
check: exists control/models/SMOKE-models.md
```
*E2E:* every launcher read-mode exits 0 against the live box; write-modes refuse without explicit flag.
*Rollback:* **committed** → `git revert` the phase commit(s) (§20). **Uncommitted failed attempt** → remove the exact files created by this assignment, enumerated in its commit plan. Do **not** use broad recursive deletion as the canonical rollback.

---
**A-2 — Write `tools/export_snapshot.sh` (fail-closed)** — **DELIVERED `728df639`**
*Reason (as raised):* Only sanctioned export path per `EXPORTS.md` rule 4; does not exist; blocks all customer delivery.
*Existing:* `docs/ops/EXPORTS.md` policy; spec in `docs/specs/scope-of-work-2026-08-22.md`.
*Missing:* the script.
*Affected:* `tools/export_snapshot.sh`, a new test.
*Dependencies:* none.
*Risk:* **High** — trade-secret boundary.
*Excludes:* No whole-repo export under any flag. **No deny-list-only architecture** — construction must be allow-list first (§12.3).
```
check: exists tools/export_snapshot.sh
check: grep ALLOW -- tools/export_snapshot.sh
check: grep corpus.jsonl -- tools/export_snapshot.sh
check: grep EXPORT-MANIFEST -- tools/export_snapshot.sh
check: exists backend/apps/test_export_snapshot.py
check: grep tmp -- backend/apps/test_export_snapshot.py
```
*E2E:* isolated temporary fixture tree with a planted sentinel (**never** a real protected path) → exporter exits non-zero, **zero archive emitted**, failure recorded (§12.5).
*Rollback:* `git revert` the phase commit (§20).

---
**A-3 — Customer→application entitlement (shared)** — **DELIVERED `ef1a4af4`**
*Reason:* No entitlement layer; Live Stack shows everything to everyone; blocks customer delivery.
*Existing:* `accounts/` (8 endpoints); `gateway/entitlement.py` (licence-scoped, different concern); the customer application already imports password primitives from `apps.accounts` — the seam D-3(b) extends (§9.4.6).
*Missing:* identity→application mapping; entitlement-aware Live Stack; **the dependency seam itself** — no route in the customer router uses `Depends()` today (§9.4.5).
*Classification:* **complete and measured** — 15 method+path pairs (§9.4.3). Not 13. `/rules` GET+PUT and `/drivers` GET+POST are four separate entries.
*Decided:* D-3 = (b) bridge, not migrate · enforcement = explicit dependency seam · precedence = auth → class → entitlement-or-operator-role · operators need **no** customer entitlement.
*Affected:* `backend/apps/accounts/`, `backend/apps/dispatchos/` (dependency attachment only, guards unchanged), `tools/build_split.py` (livestack is generated).
*Dependencies:* **D-3 ✅ resolved (b)**. Two design decisions ✅ resolved. **Two prerequisites remain open — see *Blockers* below.**
*Risk:* **Medium** — touches auth. Mitigated by the seam wrapping existing guards rather than replacing them.
*Excludes:* Do not build a second auth system. Do not fork per customer. Do not migrate the customer login (D-3 chose (b)). Do not add entitlement to `PUBLIC_BOOTSTRAP`, `SHARED_AUTH` or `AUTHENTICATED_APPLICATION`. No prefix middleware. No wildcard exemptions.

*Required tests before implementation is accepted:*
```
check: grep entitle -- backend/apps/accounts/module.py
check: exists backend/apps/accounts/test_entitlement.py
check: exists backend/apps/dispatchos/test_route_authorization.py
check: grep entitle -- tools/build_split.py
check: maxcount 0 "Depends(require" -- backend/apps/dispatchos/routes.py   # pre-state; inverts on landing
```

| # | Test | Must prove |
|---|---|---|
| T1 | Matrix conformance | Every one of the 15 pairs carries exactly the class in §9.4.3 — enumerated, so a **new route with no class fails the suite** |
| T2 | Entitled customer | 200 on all 4 `ENTITLEMENT_REQUIRED` pairs |
| T3 | Authenticated, unentitled customer | **403 on all 4** `ENTITLEMENT_REQUIRED` pairs |
| T4 | **Operator without customer entitlement** | **200 on all 7** `OPERATOR_ONLY` pairs — the precedence decision, and the one most likely to regress |
| T5 | Customer on operator routes | 403 on all 7 `OPERATOR_ONLY` pairs (role check unchanged) |
| T6 | Exemption: `/status` | 200 with no session **and** while the surface is switched off |
| T7 | Exemption: `/login` | Reachable unauthenticated and unentitled |
| T8 | **Exemption: `/logout`** | **204 with an absent, expired, and already-invalidated session** — three cases, because stranding a token is the failure |
| T9 | Exemption: `/me` | 200 for authenticated-but-unentitled; entitlement never consulted |
| T10 | Method separation | `GET /rules` and `PUT /rules` resolve independently; same for `/drivers` — a read-only identity gains no write |
| T11 | Ownership preserved | Existing 403-not-yours behaviour unchanged for non-operators |
| T12 | No auth regression | Full `apps/accounts` and customer-app suites green |
| T13 | Live Stack | Unentitled identity's catalogue omits the card; generator run twice, no diff |
| T14 | Negative-control sabotage | Removing the entitlement check makes **T3 fail** — proves T3 tests enforcement, not a coincidence |

*E2E:* authenticated-but-unentitled customer receives **403 on every `ENTITLEMENT_REQUIRED` pair**, an operator lacking customer entitlement receives **200 on every `OPERATOR_ONLY` pair**, and all four exemptions stay reachable.
*Rollback:* `git revert` the phase commits (§20). Feature-flag off is a mitigation, not the rollback.

*Blockers still open:*
1. **Shared entitlement store shape is undefined** — where the customer→application mapping lives, its schema, and who writes it. §9.4.6 marks this an implementation question; it is unanswered.
2. **Identity correspondence is undefined** — how an identity in the customer application's own session store maps to an identity in shared accounts. D-3(b) keeps the two auth systems separate, which makes this mapping *load-bearing*, and nothing on disk defines it.

Neither is a classification gap. Both must be settled before the entitlement lookup can be written, because the lookup's signature depends on them.

---
**A-4 — Complete the Donnie/DispatchOS reference slot** — **COMPLETE (§11.7), 19 of 19 indicators at or above §10 requirement**
*Reason (as raised):* Reference customer slot has 0 tests, no entitlement, no export scope, parallel auth.
*Existing:* backend, 13 API routes, `/demo/dispatchos`, workflows, `run/dispatchos.db`.
*Missing (as raised):* `TEST_PATH`, `ENTITLEMENT_SLOT`, `EXPORT_SCOPE`, `RELEASE_IDENTITY`, `CUSTODY_RECORD`. **All five now satisfied** — see the §11 indicator table; `RELEASE_IDENTITY` and `CUSTODY_RECORD` are satisfied *for A-4 only* under D-11 = (d), which does **not** authorize external release.
*Dependencies:* **A-2**, **A-3**, **D-3**, **D-4**.
*Risk:* **Medium**.
*Excludes:* Do **not** create `symoneural-dispatchos`.
```
check: exists backend/apps/dispatchos/test_dispatchos.py
check: exists backend/apps/dispatchos/EXPORT-SCOPE.md
check: ngrep symoneural-dispatchos -- backend/apps/dispatchos
```
*E2E:* Donnie logs in → sees only DispatchOS → opens it → downloads scoped zip.
*Rollback:* `git revert` the phase commits (§20).

---
**A-5 — Studio model-lifecycle extension**
*Reason:* Studio lacks model inspection/adapter/fine-tune/GPU panels; must not grow a second backend.
*Existing:* ~2,704 lines incl. ComfyUI integration, 56 tests.
*Missing:* panels listed in §7.3.
*Dependencies:* **A-1** (shared authorities settled first).
*Risk:* **Medium** — largest existing surface.
*Excludes:* No blind rebuild. No duplicate model backend.
```
check: exists backend/apps/studio/modelctl.py
check: grep modelops_inventory -- backend/apps/studio/modelctl.py
check: exists backend/apps/studio/SMOKE-modelctl.md
```
*E2E:* Studio panel and `control/models/models-list.sh` return identical inventory.
*Rollback:* `git revert` the phase commits (§20) — removes `modelctl.py` and the panels; existing Studio unaffected.

---
**A-6 — Live Stack UI pass (generator-aware)**
*Reason:* Applications don't visually communicate their class; references supplied.
*Existing:* 8 generated + 18 authored pages; shared shell.
*Missing:* per-class workspace design.
*Affected:* `tools/build_*.py` for generated pages; `site/*.html` for authored; `symoneural.css`.
*Dependencies:* **A-3** for entitlement-aware Live Stack.
*Risk:* **Low-Medium** — public-facing.
*Excludes:* Never hand-edit a generated page.
```
check: grep -c "generated" -- site/livestack.html
check: exists docs/ops/SMOKE-APPLICATIONS.md
```
*E2E:* per affected generator — run twice, assert no diff, run its own test (or record that none exists), verify the rendered page. `tests/run_ui_verification.mjs` + accessibility suite stay green.
*Rollback:* `git revert` the per-page commit (§20).

---
**A-7 — Miner dashboard (Braiins reference)**
*Reason:* Reference supplied; `miner.html` doesn't match the operational density expected.
*Existing:* `apps/asicminer/` (3 routes, 34 tests), `apps/cryptominer/`, `miner.html`.
*Missing:* KPI tiles, hashrate chart, hash-board table, fan gauges, pool status.
*Dependencies:* **A-6** shell decisions.
*Risk:* **Low**.
```
check: grep hashrate -- site/miner.html
check: grep -c "tile" -- site/miner.html
```
*E2E:* page renders live ASIC data; no console errors.

---
**A-8 — Gateway + Web service verification**
*Reason:* Both installed but never verified running; shipping claims unproven.
*Existing:* units, build scripts, `ops/verify-runtime.sh`.
*Missing:* a recorded successful run.
*Dependencies:* none.
*Risk:* **Medium** — starts services.
```
check: exists docs/ops/SMOKE-RUNTIME.md
```
*E2E:* start both, verify HTTP, record, stop.
*Rollback:* no code change to revert. Restore pre-test service state per §18 step 6 — stop both units, confirm `inactive`, confirm `enabled/disabled` unchanged.

---

## 15. Dependencies / Sequencing

```
Phase 0  intake gate (Garrett ticks)          ── blocks everything
   │
   ├── Phase 1  A-1 control/models            ── additive, zero risk
   │      └── Phase 5  A-5 Studio             ── needs settled authorities
   │
   ├── Phase 2  A-2 export_snapshot.sh        ── independent, high value
   │      └──────────────┐
   ├── Phase 3  A-3 entitlement               ── needs D-3
   │      └──────────────┤
   │                     └── Phase 4  A-4 Donnie slot  ── needs A-2 + A-3
   │
   ├── Phase 6  A-6 UI pass ── needs A-3 for livestack
   │      └── Phase 7  A-7 Miner
   │
   └── Phase 8  A-8 runtime verification ── independent; do before release
```

| Phase | Auth required | Touches | Prereq | Expected result | Verification | STOP if | Commit |
|---|---|---|---|---|---|---|---|
| 0 | Garrett | `INTAKE.md` | Sept1 reviewed | Assignments ticked | entries exist | — | 1 |
| 1 | A-1 ticked | `control/models/` only | none | 17 launchers + README | all read-modes exit 0 | any launcher reimplements logic | 1–2 |
| 2 | A-2 ticked | `tools/`, test | none | Fail-closed exporter | sentinel test fails closed | export succeeds with sentinel | 1 |
| 3 | A-3 ticked + D-3 | `accounts/`, `build_split.py` | D-3 | Entitlement live | 403 for unentitled | any auth regression | 2–3 |
| 4 | A-4 ticked | `apps/dispatchos/` | 2, 3 | Slot complete | Donnie E2E | `symoneural-dispatchos` appears | 2–3 |
| 5 | A-5 ticked | `apps/studio/` | 1 | Model panels | CLI/GUI parity | duplicate backend appears | 3–4 |
| 6 | A-6 ticked | generators + authored | 3 | UI pass | a11y + screenshots green | a generated page hand-edited | 1/app |
| 7 | A-7 ticked | `miner.html` | 6 | Braiins-class dashboard | live data renders | — | 1 |
| 8 | A-8 ticked | services | none | Verified runtime | `SMOKE-RUNTIME.md` | API destabilised | 1 |

**Global STOP:** if `symoneural-api.service` leaves `active (running)` / HTTP 200 at any point, stop and restore before continuing.

---

## 16. Risks / Known Issues

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Repeating the `symoneural-server/` failure | **Critical** | Additive only; never repoint a live `ExecStart` at an unproven tree; verify by real start + HTTP 200 |
| R-2 | Protected training data escaping via export | **Critical** | A-2 fail-closed + sentinel negative test before any UX |
| R-3 | Second model-management backend for Studio | High | A-5 blocked behind A-1; shared `modelctl.py` adapter |
| R-4 | Hand-editing generated pages | Medium | §8.1 list; generator-first rule in A-6 |
| R-5 | Auth regression from entitlement work | High | Extend `accounts`; never fork; keep tests green |
| R-6 | DispatchOS 0 tests | High | A-4 adds `TEST_PATH` before release |
| R-7 | 11 `PROVENANCE.json` entries are declared-but-absent; provenance/licence status **UNVERIFIED** (not "unlicensed") | Medium | Enforce provenance at acquisition (D-1b); `models-provenance.sh` surfaces status |
| R-11 | Planning against a stale model baseline. The "28/17/78 GiB" figure came from a docstring, not a run | Medium | §4.1.1 measured 2026-09-01; re-measure before any acquisition work |
| R-8 | Gateway/Web never verified running | Medium | A-8 before any release claim |
| R-9 | Quoting the unverified `sigils` test count | Low | Re-measure per `MEASUREMENTS.md`; never carry forward |
| R-10 | Scope creep across 8 assignments | Medium | Phase gates + commit boundaries |

---

## 17. Decision Register

---
**D-1 — How should provenance be reconciled, given zero payloads on disk?**
*Evidence:* Measured 2026-09-01 (§4.1.1): **0** weight files on disk; **11** `PROVENANCE.json` entries with no corresponding file; 0 adapters; 0 active defaults. The earlier "17 unrecorded / 78 GiB" figure was **stale docstring text, not a measurement**, and is withdrawn.
*Current:* `PROVENANCE.json` describes 11 declared-but-absent models. Nothing is `unknown-blocked` today because nothing is on disk.
*Options:* (a) reconcile the 11 manifest entries now (desk exercise — no files to hash); (b) surface status via `models-provenance.sh` and reconcile at acquisition time; (c) defer.
*Tradeoff:* (a) is cheap while empty but may not survive first acquisition; (b) puts the check exactly where provenance is actually determined; (c) risks re-acquiring models with unverified provenance.
*Recommendation:* **(b)** — enforce provenance at acquisition (`models-acquire.sh`), so a model cannot land without a record.
*Decision:* Garrett. *Blocks:* customer delivery of anything model-derived. *Safe default:* (b).
*Language rule:* report `PROVENANCE STATUS UNKNOWN/UNVERIFIED`, never "unlicensed."

---
**D-2 — Should `control/models/` ever download?**
*Evidence:* `fetch-models.sh` is the acquisition authority; box is currently offline.
*Options:* (a) `models-acquire.sh` wraps it behind explicit confirmation; (b) omit acquisition entirely.
*Tradeoff:* (a) completes the board but adds the only network path; (b) keeps it read-only/safe.
*Recommendation:* **(a)** with mandatory confirmation phrase, matching `modelops-stage.sh` convention.
*Decision:* Garrett. *Blocks:* A-1 scope. *Safe default:* (b).

---
**D-3 — Reconcile DispatchOS auth with `accounts`?**
*Evidence:* `/api/dispatchos/{login,logout,me}` + `tools/dispatchos_accounts.py` run parallel to `/api/accounts`.
*Current:* Two auth systems.
*Options:* (a) migrate DispatchOS to `accounts` + entitlement; (b) keep separate, bridge entitlement; (c) leave as is.
*Tradeoff:* (a) one authority, but touches a working customer app; (b) faster, keeps the split; (c) violates "do not build a second authentication system."
*Recommendation:* **(a)** — the architecture names accounts/auth as a *shared* consumed service.
*Decision:* Garrett. *Blocks:* A-3, A-4. *Safe default:* (b) until Donnie can retest.

---
**D-4 — Where does the DispatchOS frontend actually live?**
*Evidence:* Architecture specifies `frontend/src/app/demo/dispatchos/`; on disk there is `site/share-dispatchos.html` and a `/demo/dispatchos` route in `api.py`.
*Options:* (a) treat `site/share-dispatchos.html` as the `FRONTEND_SLOT` and record it; (b) build out `frontend/src/app/demo/dispatchos/`; (c) both, one canonical.
*Tradeoff:* Architecture §194 says existing functional paths may remain when correctly wired — favouring (a).
*Recommendation:* **(a)**, record actual path in the slot; revisit only if the Next.js frontend becomes canonical.
*Decision:* Garrett. *Blocks:* A-4. *Safe default:* (a).

---
**D-5 — Is `/demo/dispatchos` the production customer route?**
*Evidence:* Template says `/demo/<slug>` "or approved production customer route."
*Options:* (a) keep `/demo/`; (b) add `/app/<slug>` for entitled customers.
*Tradeoff:* "demo" may misdescribe a paid deliverable.
*Recommendation:* **(a)** now, **(b)** when entitlement (A-3) lands.
*Decision:* Garrett. *Blocks:* A-4 route naming. *Safe default:* (a).

---
**D-6 — Conversion / quantization launchers?**
*Evidence:* Requested in the brief; **no CLI authority found**. `symoneural_gguf` is a Studio custom node, not an operator tool.
*Options:* (a) omit until an authority exists; (b) write a new authority then wrap it; (c) wrap the Studio node directly.
*Tradeoff:* (b) contradicts "additive, thin wrappers" for A-1; (c) couples CLI to Studio internals.
*Recommendation:* **(a)** — omit from A-1; file separately if wanted.
*Decision:* Garrett. *Blocks:* A-1 completeness. *Safe default:* (a).

---
**D-7 — Should generated pages stay generated?**
*Evidence:* 8 of 26 pages generated, incl. `livestack.html` and `account.html` — both central here.
*Options:* (a) keep generation, do UI work in generators; (b) freeze some pages as authored.
*Tradeoff:* (a) preserves the no-drift property; (b) is faster per page but reintroduces drift.
*Recommendation:* **(a)**.
*Decision:* Garrett. *Blocks:* A-6 method. *Safe default:* (a).

---
**D-9 — `Architecture: all` on packages containing native binaries**
*Evidence:* `scripts/build-deb.sh` declares `Architecture: all` unconditionally. The Rust gateway and the 73 MB Go web binary are arch-specific native output. `/yocto/artifacts` already produces genuinely arch-tied packages for arm/arm64/x86/x86-64.
*Current:* A repo-local `.deb` carrying a native binary would be mislabelled arch-neutral and could install on an incompatible machine.
*Options:* (a) split — arch-neutral `.deb` for Python/shell/site, arch-tied for native; (b) make the whole repo-local `.deb` arch-tied; (c) route all native delivery through Yocto and keep the repo `.deb` strictly arch-neutral.
*Tradeoff:* (a) is correct but adds package plumbing; (b) is simplest but wrongly marks Python content arch-specific; (c) has the cleanest ownership split and matches existing evidence.
*Recommendation:* **(c)** — repo `.deb` stays arch-neutral and stops carrying native output; Yocto owns arch-tied delivery.
*Decision:* Garrett. *Blocks:* correct multi-arch delivery. *Safe default:* (a).

---
**D-10 — Close the `x86-64` delivery gaps?**
*Evidence:* `x86-64/ipk` does not exist (only missing arch/format cell of 8) and `x86-64/deb` has **0 feed index files** while all six other cells have 9–10. `x86-64-ipk.conf` **is** configured.
*Current:* The primary architecture has no IPK output and no consumable DEB feed.
*Options:* (a) build `x86-64` IPK and generate the missing feed index; (b) declare x86-64 DEB-only by policy and document it; (c) defer.
*Tradeoff:* (a) completes the 8-cell matrix; (b) is legitimate if x86-64 targets only DEB systems, but the multiconfig implies otherwise; (c) leaves the primary arch least complete.
*Recommendation:* **(a)** — the config exists; the output does not.
*Decision:* Garrett. *Blocks:* x86-64 delivery completeness. *Safe default:* (b) with documentation.

---
**D-11 — Signing authority and key custody** — **DECIDED 2026-09-02 by owner ruling. See §22 for the controlling architecture.**
*Evidence:* 76,208 packages under `/yocto/artifacts`, **zero** signed. Re-measured 2026-09-02 without a depth cap: **48** feed index files + **9** `Release` files across 6 arch/format cells, **0** signatures. `scripts/build-apt-repo.sh --sign` already implements clearsign → `InRelease` + public keyring export and refuses rather than silently going unsigned; never applied to the Yocto tree. Host: GnuPG **2.4.7**, `sq`, `ssh-keygen -Y`, `apt-ftparchive`, OpenSSL 3.5.7 all present; minisign/signify/cosign/age/dpkg-sig/reprepro **absent**. **0** secret keys, **0** public keys, **0** signed commits, 6 tags **0** signed, no `user.signingkey`. **No git remote.**
*Options (as raised):* (a) full signing authority, sign everything at release; (b) sign only externally distributed artifacts; (c) defer.
*Tradeoff:* Unsigned artifacts cannot be integrity-verified by a recipient — worse, an unsigned `EXPORT-MANIFEST` is asserted by the same unsigned tool that built the archive, so substituting both is undetectable. (c) untenable before external distribution.
*Recommendation:* **(b)**, architected so (a) is later configuration rather than a re-keying event.
*Decision:* **RULED — (b).** Owner ruling recorded 2026-09-02; controlling architecture in **§22**. *Blocks:* any external distribution **still**, because the ruling is architecture only. *Superseded:* the former `Safe default: no external distribution until signed` is now the standing rule, not a fallback.
*Architecture only:* **no key generated, no signing infrastructure created, no tag or artifact signed, no custody record created, external release NOT authorized.**

---
**D-12 — Should manifest ownership boundaries receive mechanical enforcement?**
*Evidence:* Verified 2026-09-02 by adding a shared-platform module to an export manifest: stage 1 selected it and **stage 2 passed it unflagged**. Shared platform source is not a protected class — not a secret, not training material, not runtime state — so the A-2 exporter has no basis to reject it.
*Current:* Protection against exporting shared-but-unprotected platform source rests **entirely on manifest discipline and review**. A future contributor adding a shared module to a manifest receives no automated objection.
*Options:* (a) add an ownership guard — an allow-list of exportable roots, or a per-path category assertion checked at export time; (b) require manifest review as documented process only; (c) accept the gap.
*Tradeoff:* (a) makes the boundary mechanical but needs an ownership model the repository does not yet express; (b) is free and already implicit, but a review step is exactly what fails silently under time pressure; (c) leaves the only safeguard in a comment.
*Recommendation:* **(a)** eventually, once application-vs-platform ownership is expressed somewhere machine-readable. Not before — a guard built on a guessed ownership model would reject correct manifests and train people to bypass it.
*Decision:* Garrett. *Blocks:* nothing today; A-4 shipped without it by explicit ruling. *Safe default:* (b).
*Explicitly excluded from A-4:* no mechanical guard was implemented and no exporter change was authorized.

---
**D-8 — Retroactive intake for `control/`?**
*Evidence:* `control/` was built and committed (`1df394f0`) without an `INTAKE.md` entry.
*Options:* (a) add retroactive entry; (b) leave as directly-requested work.
*Recommendation:* **(a)** for ledger accuracy.
*Decision:* Garrett. *Blocks:* nothing. *Safe default:* (b).

---

## 18. Operator Commands Required

Only commands genuinely requiring Garrett — privilege, secrets, physical access, or product judgement. Nothing here is padding, and **no command prints a secret**.

**1. Tick intake assignments** — product judgement; the gate itself.
```
Review Sept1.md §14, then tick chosen items in INTAKE.md
```

**2. Enable a token-gated surface** (needed for A-3/A-4 testing) — writes a systemd drop-in; requires a token only you hold.
```bash
sudo ./scripts/enable-surfaces.sh dispatchos
sudo ./scripts/enable-surfaces.sh studio
```

**3. Inspect which surface flags are set — WITHOUT printing secrets**
```bash
sudo ./scripts/enable-surfaces.sh --show
```
> **Corrected.** An earlier draft said `sudo cat /etc/symoneural/api.env`. **Do not run that** — it prints token values into the terminal transcript and any chat they are pasted into. `enable-surfaces.sh --show` exists precisely for this: its source states *"Values are never printed. A token is either set or it is not; showing it here would put [it in the transcript]."* Use it; never `cat` the env file.

**4. Acquire models — NO sudo** (only when acquisition is separately authorized per Q2)
```bash
./scripts/fetch-models.sh          # deliberately NOT sudo
```
> **Corrected.** An earlier draft used `sudo`. Verified: `fetch-models.sh` contains **no root requirement**, and `backend/models/` is `google:google`. Running it under sudo would leave downloaded artifacts **root-owned**, breaking later non-root reads and writes. Authorizing a network operation is not a reason to escalate privilege.
> **Q2 standing rule:** a `PROVENANCE.json` record is *not* authorization to download its payload. Acquisition requires explicit authorization each time.

**5. Site deployment** (after A-6/A-7) — needs root; webroot is `www-data`-owned.
```bash
sudo ./scripts/deploy.sh
```

**6. A-8 Gateway/Web verification — complete safe lifecycle**

A-8 is *start → verify → **stop***. Both units are currently `disabled`/`inactive`; the test must leave them exactly that way.

```bash
# 1. capture pre-state (record this output)
systemctl is-enabled symoneural-gateway.service symoneural-web.service
systemctl is-active  symoneural-gateway.service symoneural-web.service

# 2. start exactly the two units (start, NOT enable — enabling changes boot state)
sudo systemctl start symoneural-gateway.service symoneural-web.service

# 3. verify
systemctl is-active symoneural-gateway.service symoneural-web.service
curl -s -o /dev/null -w 'gateway: HTTP %{http_code}\n' http://127.0.0.1:<gateway-port>/
curl -s -o /dev/null -w 'web:     HTTP %{http_code}\n' http://127.0.0.1:<web-port>/

# 4. stop exactly the two units
sudo systemctl stop symoneural-gateway.service symoneural-web.service

# 5. confirm inactive
systemctl is-active symoneural-gateway.service symoneural-web.service      # expect: inactive

# 6. confirm enabled/disabled state UNCHANGED from step 1
systemctl is-enabled symoneural-gateway.service symoneural-web.service     # expect: disabled

# 7. confirm the API was unaffected throughout
curl -s -o /dev/null -w 'api: HTTP %{http_code}\n' http://127.0.0.1:8800/api/status
```

> **Do not leave Gateway/Web running because the test passed.** A-8 proves they *can* run; it does not authorize them to stay running or to become enabled at boot. Never substitute `enable` for `start`.

**Security note (outside this plan's scope):** `providerapikeys.txt` is mode 664 in `/home/google`; `.git-credentials`, `.smbcredentials`, `.passwd-s3fs` also present. Consider rotation and tighter permissions.

## 19. Verification Matrix

| Work | Verification | Pass criterion | Evidence artifact |
|---|---|---|---|
| A-1 | Run every launcher against live box | all read-modes exit 0, non-empty | `control/models/SMOKE-models.md` |
| A-1 | Wrapper discipline | each launcher references its authority; none reimplements | grep checks |
| A-2 | Sentinel negative test | export **fails closed** with a protected path present | `test_export_snapshot.py` |
| A-2 | Manifest | EXPORT-MANIFEST names source SHA | manifest file |
| A-3 | Unentitled access | HTTP 403; Live Stack omits card | `test_entitlement.py` |
| A-3 | No auth regression | `apps/accounts` suite green | pytest |
| A-4 | Donnie E2E | login → sees only DispatchOS → opens → scoped download | `SMOKE-dispatchos.md` |
| A-4 | Naming | zero `symoneural-dispatchos` occurrences | grep |
| A-5 | CLI/GUI parity | Studio panel == `models-list.sh` output | `SMOKE-modelctl.md` |
| A-5 | No duplicate backend | `modelctl.py` calls shared authorities only | grep |
| A-6 | Accessibility | suite green, freshly stamped | `SMOKE-ACCESSIBILITY.md` |
| A-6 | Screenshots | per-app records | `SMOKE-APPLICATIONS.md` |
| A-7 | **Real ASIC/API response** received | non-empty response from `/api/asicminer` | captured response |
| A-7 | **UI consumes that response** | rendered values trace to the response, not placeholders | DOM assertion |
| A-7 | **Expected KPI value appears** | a named KPI (e.g. hashrate) matches the API value | DOM assertion |
| A-7 | No console errors | zero uncaught JS errors | test log |
| A-7 | Screenshot | *supplemental visual evidence only — never proof of live data* | PNG |
| A-8 | Binary/service identity | current binaries at HEAD identified before start | pre-state record |
| A-8 | HTTP behaviour | both units answer while running | `SMOKE-RUNTIME.md` |
| A-8 | **Pre-test state restored** | both `inactive`; `enabled/disabled` unchanged; API still 200 | post-state record |
| **All** | **API health** | `active (running)`, HTTP 200, restarts stable | `control/status-all.sh` |

**Generator verification — per generator, not blanket.**

`backend/apps/test_build_progress.py` covers **`build_progress` and `build_intake` only** — **2 of 21** `tools/build_*.py` generators. It must **not** be cited as evidence that any other generator is stable.

For **each** generator touched by A-6, all four steps:

| Step | Requirement |
|---|---|
| 1 | Run the generator |
| 2 | Run it a **second** time |
| 3 | Assert **no diff** between runs (catches the re-read accumulation bug — 3 occurrences in this repo) |
| 4 | Run **that generator's own** relevant test, if one exists; if none exists, say so explicitly rather than borrowing another's |
| 5 | Verify the **rendered page**, not just the generator exit code |

| Generated page | Owning generator | Existing test coverage |
|---|---|---|
| `livestack.html` | `build_split.py` | **none identified** — REQUIRED |
| `account.html` | `build_pages.py` | **none identified** — REQUIRED |
| `index.html`, `overview.html` | `build_pages.py` / `build_masthead.py` | **none identified** |
| `controlboard.html` | `build_console.py` | **none identified** |
| `documentation.html` | `build_docs_index.py` | **none identified** |
| `receipts.html`, `build.html` | `build_cost.py` / `build_split.py` | **none identified** |
| *(progress/intake artefacts)* | `build_progress.py`, `build_intake.py` | ✅ `test_build_progress.py` (28 tests) |

**Non-negotiable:** *"If the deliverable is a program that runs, one check must be something only a real run can turn green."* Every phase ends with a real start + real request, never inspection alone.

---

## 20. Commit / Release Plan

**Boundaries** — commit between items, never one batch; each message states its reason.

| Phase | Commits | Message shape |
|---|---|---|
| 1 | 1–2 | `feat(control): add control/models operator surface` |
| 2 | 1 | `feat(tools): fail-closed export_snapshot.sh + negative test` |
| 3 | 2–3 | `feat(accounts): customer→application entitlement` / `feat(site): entitlement-aware Live Stack generator` |
| 4 | 2–3 | `feat(dispatchos): complete reference customer slot` / `test(dispatchos): add TEST_PATH` |
| 5 | 3–4 | `feat(studio): shared modelctl adapter` / `feat(studio): model lifecycle panels` |
| 6 | 1/app | `feat(site): <app> UI pass` |
| 7 | 1 | `feat(site): miner dashboard, Braiins-class density` |
| 8 | 1 | `docs(ops): SMOKE-RUNTIME gateway+web verification` |

**Canonical rollback — applies to every assignment A-1 … A-8:**

| Situation | Rollback |
|---|---|
| Work is **committed** | `git revert <exact phase commit(s)>` — the canonical path |
| Work is **uncommitted** and failed | Remove the exact known files from that assignment's commit plan. **Broad recursive deletion (`rm -rf <dir>`) is not a rollback** and requires separate review |
| Service state changed (A-8) | Restore pre-test state per §18 step 6; no code to revert |

No assignment defines its own rollback mechanism; every `*Rollback:*` line above points here.

**Release rules:** no remotes — nothing leaves via git. Generated binaries stay out of git (§13). Every release artifact carries checksum + provenance. `ops/rollback-runtime.sh` is the runtime rollback path; per-phase rollback is `git revert` of that phase's commits.

---

## 21. Definition of Done

### For this planning pass

- [x] `Sept1.md` exists
- [x] Inventories actual implementation, not assumptions (every authority verified on disk)
- [x] Every Live Stack application represented (20 logical; 18 packages / 21 namespaces / 26 pages reconciled)
- [x] Every proposed feature has an intake assignment (A-1 … A-8)
- [x] Donnie/customer architecture integrated (§10 from the normative document)
- [x] Reusable blank slot template (§10.5)
- [x] Existing authorities distinguished from missing work (tag system)
- [x] All unresolved issues explicit (D-1 … D-8)
- [x] Dependencies sequenced (§15)
- [x] Verification defined (§19)
- [x] Commit boundaries proposed (§20)
- [x] **No feature implementation begun**

### For the build phase (future)

Each assignment is done when: its `check:` lines pass; its end-to-end runtime test passes on a real run; its smoke record is committed; the API is still `active (running)` / HTTP 200; no protected content moved; and no second source of truth was created.

---

## 22. D-11 — Controlling Signing Architecture (owner ruling, 2026-09-02)

**Status: DECIDED — architecture only.** This section is the controlling record. It replaces the
former open state in §18. It authorizes **no implementation**: **no signing key exists, no
signing infrastructure exists, no tag or artifact is signed, no custody record exists, and
external release is NOT authorized.**

### 22.1 The ruling

| Dimension | Ruling |
|---|---|
| **Scope** | **D-11(b)** — sign externally distributed artifacts. Package/feed signing becomes **mandatory when those feeds are externally distributed** |
| **Authority** | **A-4** — one **organization-level SymonSays LLC release authority**, operator-held custody. Not a personal operator key: recipients trust the organization, so the authority survives personnel change |
| **Hierarchy** | **H-2** — **offline certify-only OpenPGP primary** + **long-lived release-signing subkey** |
| **Custody** | **C-2** — primary **offline/removable**; signing subkey may be **host-held only** in an operator-owned protected location, **never service-readable, never inside the repository** |
| **Mechanism** | **OpenPGP / GnuPG** — present (2.4.7), no new dependency, and the only present mechanism covering both archive and DEB/IPK feeds |
| **Identifier of record** | **Full 40-hex primary/subkey fingerprints** as applicable. Short/long key IDs are collidable and must never appear alone in policy or verification instructions |
| **Rotation** | Rotate **signing subkeys under the existing primary**, so recipient trust is not re-established on rotation |
| **Revocation** | Revocation certificate generated **during the future key ceremony** and **held separately** from the key |
| **Expiry** | **Finite signing-subkey expiry** |
| **Runtime-secret separation** | **Absolute.** Shared-account session secrets and entitlement keys must **never** be reused as, or derived into, release-signing material |
| **Archive signing** | **Detached OpenPGP signature over the final customer archive** |
| **Release identity** | Archive `source-sha` **must correspond to a signed release tag** |
| **Custody / provenance** | A **signed release record** binding signer + fingerprint, UTC time, source SHA, archive SHA-256, licence/provenance, and export scope |
| **Feeds** | **Clearsigned `InRelease`** when DEB/IPK feeds are externally distributed |

**Why the runtime-secret separation is absolute.** Different purpose (session authentication and
licence entitlement vs artifact provenance), different lifetime (rotatable at will vs long-lived
recipient trust), different blast radius. Session secrets live in the runtime environment on the
serving host — exactly where signing material must never be. `gateway/entitlement.py` already
implements the correct *posture* (operator mints offline, server verifies with the public key
only, asserted by `test_settlement.py`); **reuse the posture, never the key.** The entitlement
authority and the release authority are distinct authorities.

### 22.2 Preserved state at the time of this ruling

| | |
|---|---|
| **A-4** | **COMPLETE, 19 of 19** — unchanged by this ruling |
| **External release** | **NOT authorized** |
| **D-12** | **separate and unimplemented** |
| **Signing key** | **none exists** |
| **Signed artifact** | **none exists** |

A ruling on *how* to sign is not permission to sign, and not permission to ship.

### 22.3 Pre-key prerequisites — characterized, NOT implemented

Ordered. **P1 must land before any key is generated.**

#### P1 — Exporter signing-material exclusions

**Measured gap.** Hypothetical signing paths matched against the **live 17 patterns** parsed from
`tools/export_snapshot.sh`:

```
BLOCKED  ops/keys/release.pem  ops/keys/release.key  ops/keys/backup.p12   by \.(pem|key|p12|pfx)$
BLOCKED  ops/keys/id_ed25519                                              by (^|/)id_(rsa|ed25519|ecdsa)$
BLOCKED  secrets/release.asc                                              by (^|/)secrets?/
BLOCKED  run/release.asc                                                  by (^|/)run/
BLOCKED  .gnupg/private-keys-v1.d/1234.key                                by \.(pem|key|p12|pfx)$

PASSES   ops/keys/release.asc              <-- NOT COVERED
PASSES   .gnupg/pubring.kbx                <-- NOT COVERED
PASSES   ops/release.gpg                   <-- NOT COVERED
PASSES   ops/release.minisig               <-- NOT COVERED
PASSES   ops/signing/release_ed25519       <-- NOT COVERED
PASSES   ops/signing/release_ed25519.pub   <-- NOT COVERED
```

**The crux: `.asc` and `.gpg` cannot be discriminated by name.** `gpg --export-secret-keys
--armor` emits `.asc` (must never leave); `build-apt-repo.sh:105` does `gpg --armor --export >
symoneural-archive-keyring.asc` (must be **publishable**, and P3 publishes exactly that). A
blanket `\.asc$` rule would refuse the public keyring and fail the requirement not to block
legitimate verification material. So P1 splits in three:

**P1-a — unambiguously private by path/name** (pure pattern additions, same architecture as today):

| Rule | Refuses | Sabotage / regression test |
|---|---|---|
| `\.kbx$` | GPG keybox | Manifest a `pubring.kbx`; assert non-zero exit, **no archive written** |
| `(^|/)private-keys-v1\.d/` | GPG private key store | Manifest a file under it; assert refusal names the class |
| `(^|/)\.gnupg/` | whole GPG home | Manifest any path under `.gnupg/`; assert refusal |
| `\.minisig$` | minisign signature/key | Manifest one; assert refusal |
| `(^|/)ops/(keys|signing)/` | the custody directories by location | Manifest a file in each; assert refusal for both |

**P1-b — ambiguous by name, resolved by CONTENT.** This is an **architectural addition**: stage 2
is currently path-regex-only, so a content sniff is a new kind of check, not another pattern.

| Rule | Refuses | Test |
|---|---|---|
| Content sniff for `-----BEGIN .*PRIVATE KEY BLOCK-----`, `-----BEGIN OPENSSH PRIVATE KEY-----`, `-----BEGIN .*PRIVATE KEY-----` on every candidate | armored private keys **whatever they are named** — including `ops/keys/release.asc`, `release.gpg`, and the **extensionless** `ops/signing/release_ed25519` that no name pattern can reach | Three tests, one per header form, each at a *different* filename (`.asc`, `.gpg`, extensionless) to prove detection is name-independent. Plus a **binary/large-file** case to prove the sniff cannot be tricked by a leading NUL or a huge file |

**P1-c — explicit carve-out, and the test that protects it:**

| Requirement | Test |
|---|---|
| The **public** keyring `.asc` (e.g. `symoneural-archive-keyring.asc`) and a published public key **must remain exportable** | Manifest the public keyring; assert **exit 0** and that it **is** present in the archive. This test is what keeps P1 from over-blocking, and it must fail loudly if someone later adds a blanket `\.asc$` |

**Blast radius note:** stage 2 only ever sees manifested candidates, so the four third-party
vendor `.asc` files under `references/` are unreachable unless someone manifests them. P1 is
about the *future* key, not existing files. **No exporter change was made in this task.**

#### P2 — Non-forgeable release identity — **COMPLETE 2026-09-02**

**Status: `P2 COMPLETE — NON-FORGEABLE RELEASE IDENTITY`.** Implemented as exporter **stage 3**
(P2-a, P2-b) plus a separate verifier `tools/verify_release_identity.sh` (P2-c). Tests: **43**
total — 7 A-2 + 15 P1 + **21 P2**, all passing.

**Proven by sabotage, three prongs, each measured:**
1. *Unresolved identity reached the old acceptance path.* Pre-P2 exporter against a non-git
   root: **exit 0, archive written, `source-sha: UNKNOWN`.** Post-P2: refused, no archive.
2. *Drift evaded release identity.* Pre-P2 with a forged working-tree candidate: archive
   written **claiming a real commit while containing bytes that commit never held** — a
   forgery invisible to a recipient, since the checksums match the manifest and the manifest
   names a real commit. Post-P2: `DRIFT [differs from HEAD]`, refused.
3. *Tag/source identity was not bound.* No verification path existed. Post-P2 refuses an
   **authentic signature over the wrong commit** and a bad signature over the right commit.

**Candidate-vs-HEAD authority: git object identity, via `git diff-index HEAD -- <path>`.**
Not mtime, not size, not timestamps. Verified against a throwaway repository before choosing
the primitive: `diff-index` reports content drift, **mode-only** drift (`100644`↔`100755`),
deletion, and **type** drift (regular↔symlink, mode `120000`).

`git hash-object` was **rejected**: without `--path` it does not apply clean filters (this tree
has `.gitattributes` under `backend/vendor/`), and on a symlink it **follows the link** and
hashes the target while git stores the link target string.

**The hole `diff-index` alone leaves, and how it is closed:** an **untracked** path does not
appear in its output at all, so it reads as clean. Stage 1 expands a manifested directory into
its files, so an uncommitted file inside a named directory becomes a candidate and would ship
under a `source-sha` that never contained it. Each candidate is therefore **also** probed with
`git cat-file -e "HEAD:$path"`, with all three exit branches handled — absent and error both
refuse.

**Invariant proved, stated no more strongly:** *candidate content, file mode and object type
match HEAD as git records them.* This is **not** a claim of post-filter byte-identity on disk.
Without `git update-index --refresh`, a stat-only change can be reported as modified; that
direction is conservative (refuses a possibly-identical file) and is accepted rather than
worked around.

**Not a clean-working-tree requirement.** Only manifested candidates are checked. The
repository intentionally carries an unrelated modified file that the customer manifest does not
name; verified that the real 7-entry manifest passes with the tree dirty.

**Root must be the repository top level.** `HEAD:<path>` and `diff-index` resolve against the
repo root, not `--root`, so a subdirectory root would silently compare the wrong paths. Checked
and refused rather than compared incorrectly.

**P2-c lives outside the exporter, deliberately.** The exporter must stay runnable with **no
signing key** — its allow-list, protected-class, P1 and P2 refusals are controls that must work
on a box with zero keys. Folding tag verification in would invert the dependency, so that a
missing key began *disabling* protections. Matches §22.4 item 6. The verifier takes an
injectable `SYM_TAG_VERIFY_CMD` (default `git verify-tag`), so the future key ceremony supplies
the real authority **without redesigning P2**.

**Both P2-c conditions are mandatory and checked independently:** the tag signature must verify
against the authorized release key, **and** the tag's commit must equal the archive's
`source-sha`. "The tag verified" is never allowed to imply "the tag points at this release" —
reusing a genuinely signed tag to bless an archive built elsewhere is a real attack shape.

**Git signing policy:** `tag.gpgsign` is recorded as the **required future setting** and was
**not** applied — setting it with zero keys would make every future tag creation fail.
**`commit.gpgsign` is NOT a D-11 requirement**, and existing unsigned commits are **not**
characterized as defective.

**Real-manifest regression:** 7 candidates, stage 1/2/2b/3 all pass, release identity resolves
to a real commit, **no archive written**.

**No key generated. No fingerprint. No tag signed. Nothing published. External release NOT
authorized.**

---

##### P2 as originally characterized


**Two fail-closed cases, not one.**

*Case 1 — `source-sha: UNKNOWN`.* Exporter: `SOURCE_SHA="$(... git rev-parse HEAD 2>/dev/null ||
echo UNKNOWN)"`. On failure it writes the literal `UNKNOWN` and continues. Required behavior:
**refuse** — non-zero, no archive — with a message naming that release identity is
unresolvable. Rationale: a signature over `UNKNOWN` is a *valid signature on an unidentifiable
release*, which is worse than no signature because it looks authoritative.

*Case 2 — working-tree drift, and this one is live today.* The exporter copies from the **working
tree** (`cp -p "$ROOT/$path"`) but labels the archive with `git rev-parse HEAD`. A
modified-uncommitted manifested file therefore ships content that **does not correspond to the
stated `source-sha`**. This session has carried ` M docs/ops/EXPORTS.md` throughout; the current
7-entry manifest happens not to overlap it — **luck, not a guarantee**. Required behavior:
**refuse if any candidate path differs from HEAD.** Signing a confidently-mislabeled archive is
the worse failure mode.

| Requirement | Test |
|---|---|
| Refuse on `git rev-parse` failure | Run with `--root` at a non-git directory; assert non-zero, **no archive**, and that `UNKNOWN` appears nowhere in output as an accepted value |
| Refuse on working-tree drift | Modify a manifested file, run; assert refusal naming the drifted path. Then `git stash`/restore and assert exit 0 — proving it is drift-sensitive, not permanently broken |
| Signed release tag required | Verification step asserts `source-sha` equals the commit of a tag that verifies against the release authority |
| Cross-check | Recipient/operator: `git verify-tag <tag>` → tag commit == manifest `source-sha`. Both must hold; either failing fails the release |

**Is commit signing necessary? NO — signed release tags are sufficient for D-11(b).** A signed
tag signs the commit SHA, which is a Merkle root over the entire tree, so signing the tag
transitively commits to exact tree content. Per-commit signing is a **development-process
attribution control**, not a release-identity control, and adopting it would retroactively
imply something about 504 existing unsigned commits. Recommendation: `tag.gpgsign` for release
tags; **do not** set `commit.gpgsign` as a D-11 requirement. **No git signing configuration was
changed; no tag was created or signed.**

#### P3 — Trusted public-key distribution — **CHANNEL CONFIRMED 2026-09-02**

**Status: `P3 CHANNEL CONFIRMED — P3-1 + P3-4`.** Re-measured against the tree at HEAD
`bb9230f4`, not carried over from the earlier recommendation. **`CHANNEL CONFIRMED` is not
`KEY PUBLISHED`, `KEY GENERATED`, `KEY CEREMONY PERFORMED`, or `RELEASE AUTHORIZED`** — those
are four separate states and all four remain **unreached**. Measured at confirmation: public
signing key **0**, private signing key **0**, fingerprint **0**, key published **0**, signed
tags **0**, signed artifacts **0**, external release **NO**.

**Constraint measured, not assumed: there is no git remote.** So GitHub/remote-based
distribution does not exist as an option. The authoritative channel the project **does** control
is the published site: `scripts/deploy.sh` publishes `site/` to `/var/www/symoneural`, served at
`https://symoneural.com/`.

**Re-measured mechanics, with file:line evidence (2026-09-02, HEAD `bb9230f4`):**

| Question | Answer | Evidence |
|---|---|---|
| Which script publishes `site/`? | **`scripts/deploy.sh`** — sole authority | `deploy.sh:39` `SRC="$ROOT/site"` |
| Destination class | **local filesystem web root**, `install`ed `www-data:www-data` mode `644` | `deploy.sh:40` `DST=/var/www/symoneural`; `deploy.sh:76` |
| Is `txt` permitted? | **YES** | `deploy.sh:61` allow-list includes `txt`; tested by matching `site/release-key.txt` against the live regex |
| Is `asc` permitted? | **NO** | same line — `asc` absent. A `.asc` in `site/` is reported `skipped: not a web asset` (`deploy.sh:62,65-67`) |
| Depth-limited? | **YES, `-maxdepth 1`** | `deploy.sh:75` — the only install action |
| Would nested `.well-known/` publish? | **NO** | no recursive copy exists anywhere in `deploy.sh`; exactly one install action, and it flattens into `$DST/` |
| Unlinked top-level `.txt` retained? | **YES** | `deploy.sh:104` retention test is `[ -f "$SRC/$f" ]` **and** extension match — **zero** link references in the orphan block |
| Does publication require a source-page link? | **NO** | the reference check (`deploy.sh:135,244`) iterates `src=`/`href=` **found in HTML** and asserts each resolves on disk. It never asserts that a published file is referenced, so an unreferenced key file is never examined and cannot fail a deploy |

**Second publication trigger — new finding, and an operational precondition.**
`scripts/build-deb.sh` postinst republishes the web root on `apt upgrade`, but it implements no
publication logic of its own: it **delegates to `deploy.sh --prune`** (`build-deb.sh:181` +
postinst). So one allow-list governs both paths. The consequence is load-bearing: because
line 104's retention test keys on presence in the **source** tree, a key file hand-placed
directly into the web root and **not** present in `site/` is an orphan and is **deleted by the
next `apt upgrade`**. A file tracked at `site/release-key.txt` survives both triggers.
**Therefore: the key must live in `site/` and must never be hand-placed in the web root.**

**P1/P3 collision check (P1 landed after this section was first written).** Tested against the
live committed patterns: `site/release-key.txt` matches **none** of the 22 P1-a path patterns,
and `-----BEGIN PGP PUBLIC KEY BLOCK-----` matches **none** of the 3 P1-b content patterns. P1
and P3 do not collide — the public key remains exportable and publishable.

| Option | Works unchanged? | Needs impl? | External trust service? | Distributes key? | Authenticates fingerprint? | Role |
|---|---|---|---|---|---|---|
| **P3-1** `site/release-key.txt` | **YES** | no | **no** | **yes** | **no** | **PRIMARY key channel** |
| **P3-2** add `asc` to `PUBLISH` | no | **yes** — `deploy.sh` change | no | yes | no | deferred cleanup, own authorization |
| **P3-3** public keyserver | no | yes | **YES** | yes | no | **rejected as primary** |
| **P3-4** out-of-band fingerprint | **YES** (business process) | no | no | no (fingerprint only) | **YES** | **PRIMARY fingerprint channel** |

**Neither path is sufficient alone.** P3-1 distributes a key but authenticates nothing; P3-4
authenticates the fingerprint but distributes no key. **Possession of a public key downloaded
from the project site is NOT authentication by itself.**

| Option | Mechanism | Tradeoffs |
|---|---|---|
| **P3-1** | **`site/release-key.txt`** — armored public key with a `.txt` extension | **Works today with zero deploy change.** HTTPS-authenticated, project-controlled, no remote needed. Extension is cosmetically wrong for OpenPGP tooling but the armored content is what matters |
| **P3-2** | Add `asc` to `PUBLISH`, publish `release-key.asc` | Correct extension and correct content-type expectations. Requires a **deploy.sh change = its own authorization**, and widens the publish allow-list |
| **P3-3** | Public keyserver | Standard OpenPGP discovery, but hands an external service a role in the trust path and cannot be retracted. Rejected as *primary* |
| **P3-4** | Out-of-band only — fingerprint in contract/onboarding material, key delivered with the archive | Strongest binding to a real business relationship, no public infrastructure. Does not scale and gives no public verification path |

**Recommendation: P3-1 as the key channel + P3-4 as the fingerprint channel.**

Publish the armored **public** key at `site/release-key.txt` (no deploy change required), and
restate the **40-hex primary fingerprint through a second, independent path** — contract or
onboarding material delivered with the archive. Rotation/revocation publish the same way: new
subkey certification and any revocation certificate replace the published file, with the
**primary fingerprint unchanged**, which is precisely why H-2 was chosen.

**On the apparent circularity:** hosting the public key on the same box that may hold the signing
subkey looks self-certifying, and **C-2's offline primary is what makes it survivable.** A host
compromise lets an attacker replace the published file; it does **not** let them produce a subkey
certification chaining to a primary fingerprint the customer already holds out-of-band. The
second fingerprint path is therefore load-bearing, not belt-and-braces. Adding `asc` to
`PUBLISH` (P3-2) is a reasonable later cleanup and is **its own authorization**.

**The guarantee, stated no more strongly than the evidence supports.** Compromise of the web
host permits **replacement of the downloadable public-key file**. It does **not**, absent
compromise of the **offline primary**, permit creation of a new subkey certification that chains
to the primary fingerprint a recipient already holds independently.

That protection is **conditional on the recipient actually performing the fingerprint check.** A
recipient who downloads the key and skips the comparison is defeated by web-host compromise
alone, because nothing else in the chain would object. **The fingerprint comparison is therefore
MANDATORY in the recipient verification procedure, not advisory** — it is the step that makes
the two-channel model load-bearing rather than decorative.

**Confirmed trust chain:**

```
offline certify-only PRIMARY            (C-2 custody, never on the serving host)
        | certifies
        v
release-signing SUBKEY
        | signs
        v
release artifacts / signed release record
        | verified using
        v
public key from project-controlled HTTPS publication   (P3-1, site/release-key.txt)
        +
40-hex PRIMARY fingerprint obtained independently      (P3-4, MANDATORY comparison)
```

**Nothing was published. No key, fingerprint, or file was created.** `site/release-key.txt`
is confirmed **viable, not present** — it does not exist, and creating it is not authorized
by this confirmation.

### 22.4 Ordered prerequisites before key generation

1. **P1** — exporter signing-material exclusions (P1-a patterns, P1-b content sniff, P1-c
   public-material carve-out) **with tests**. **Must precede key generation**: until it lands, a
   private key at `ops/keys/release.asc` is exportable.
2. **P3 channel decision confirmed** and the `site/release-key.txt` path accepted — verification
   is impossible without a trusted out-of-band fingerprint path.
3. **P2** — exporter refuses `UNKNOWN` **and** refuses working-tree drift; signed-release-tag
   requirement adopted (`tag.gpgsign`, no `commit.gpgsign`).
4. **Key ceremony** — separately authorized: primary offline, signing subkey, revocation
   certificate, 40-hex fingerprint recorded, expiry set, custody media provisioned. Report only
   *that* it succeeded plus fingerprint, location class, ownership and mode — **never** key
   material.
5. **Custody documentation** — permitted/forbidden locations, backup/recovery, rotation and
   revocation procedure, who may sign.
6. **Signing step** — a separate signer invoked *after* the exporter, never inside it. The
   exporter must remain runnable with no key present, and its refusal paths must not depend on
   signing. Fail-closed: no signature, no release.
7. **Custody-record schema** (§22.1) — does not exist.
8. **Recipient verification procedure** — exact commands, expected output, failure meaning, plus
   the independent `EXPORTS.md` acceptance grep.
9. **`EXPORTS.md` policy rule** for signing (note its pre-existing unstaged modification must be
   resolved on its own authorization first).
10. **Feeds, only on moving to (a)** — `apt-ftparchive` re-index of the 6 cells, clearsigned
    `InRelease` per cell, keyring published.

### 22.5 What remains before external release can EVER be authorized

D-11 being decided does **not** authorize external release. Still required, each separately:

1. **Explicit external-release authorization** — the ruling settles *how* to sign, not *whether*
   to ship.
2. **Implementation authorization** for each of P1/P2/P3 and items 4–10 above; none is authorized.
3. **Key ceremony authorization.**
4. **Per-archive production authorization**, naming recipient and scope manifest.
5. **Export-scope re-confirmation** — the 7-entry manifest was authorized for A-4; whether that
   exact scope is what a customer receives is a fresh decision.
6. **Licence/provenance terms** for the custody record — a legal/business input.
7. **Recipient verification path in place** — otherwise the signature is decorative.
8. **D-12 remains separate hardening, NOT required before release.** It guards against a *future
   contributor* manifesting shared-platform source; today the manifest is 7 reviewed entries. It
   should be revisited before *routine* customer exports.

**A-4 is unaffected and remains COMPLETE, 19 of 19.**

---

*End of Sept1.md. Awaiting review. No implementation authorized until this document is returned.*
