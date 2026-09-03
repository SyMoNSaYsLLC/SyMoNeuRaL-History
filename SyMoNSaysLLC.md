# SyMoNSaysLLC — organization, platform and component registry

Canonical registry, reconciled **2026-09-03**. Current measured state belongs in
[ProjectStatus.md](ProjectStatus.md); this document records relationships and architectural direction.
Garrett is the sole task authorizer. **EXISTING** means source or cited evidence exists; it does not
mean every workflow is LIVE, VERIFIED, REPRODUCIBLE or RELEASE-COMPLETE. **PLANNED** means no completed
implementation is established by this registry. No engineering task is activated here.

## Organization and product role

**SyMoNSaysLLC** (owner naming also SymonSaysLLC / SymonSays LLC): Ben supplies the business perspective;
Garrett supplies engineering and remains the owner/task authorizer. Rough ideas, customer needs,
requirements, opportunities and operational problems enter SyMoNeuRaL to be professionalized,
formalized, routed, governed and verified.

SyMoNeuRaL is the proprietary professionalization, orchestration, routing, governance, execution,
evidence, entitlement and integration layer. Providers supply intelligence; SyMoNeuRaL supplies
the professional system around it. This is a working architecture statement, not a release or SLA claim.

```text
SyMoNSaysLLC
  Ben — Business / Garrett — Engineering
       ↓ ideas, requirements, customer needs
SyMoNeuRaL — professionalizes / formalizes / routes / governs / verifies
       ↓ professional applications and subject-matter workflows
Task Gate + Mutation Lease + Evidence Contract
       ↓
Symon Business — Planner / Governor
Symon Coder — Operator / Auditor
Symon SME — Domain Specialist
       ↓
Controlled Tool Executor
       ↓
repo / filesystem / Git / systemd / services / builds / tests / APIs / devices

Reasoning/provider layer beneath first-party control:
Symon-local / OpenAI / Anthropic / Google / Qwen / future providers
```

The target enforced control plane and executor are **PLANNED**. Current task-gated human/agent
operating rules are standing requirements, not proof of their implementation in software.

## Authority, identity and controlled execution

Agent identity, role, provider and mutation authority are independent fields. For example:
Symon Coder / AUDITOR / Codex / mutation NO; or Symon Coder / OPERATOR / Symon-local /
mutation YES only under the named owner gate. **Provider identity MUST NOT determine project authority.**

The planned executor validates an active task, one mutation owner, authorized operation/path,
prerequisites, rollback and evidence requirements before a proposed action can reach the host.
This applies eventually to filesystem, shell, Git, systemd, packages, builds, tests, networking,
privilege, reboot, external APIs and devices. A provider's proposed command is not permission.

Direct Claude/Codex sessions remain transitional and subordinate to the active task:
task contracts → normalized provider tasks → proposals with Symon-controlled execution →
canonical Symon Coder roles → preferred Symon-local where qualified → optional external escalation.
No transition phase is implemented or activated merely by writing this direction.

## First-party registry

### Shared source/licensing convention

For each component below, the listed source paths are relative to the canonical repository.
[LICENSE](LICENSE) governs first-party material; applicable upstream licenses/model provenance/notices
retain their own terms. [LICENSES.md](LICENSES.md) is a **dated reference inventory**, with unresolved
distribution claims and stale paths. It is not fresh license clearance or a blanket permissive claim.
Model house names are aliases, not transfers of authorship. Upstream weights are not claimed as
trained or modified by SyMoNeuRaL merely because they were restored.

Deploy Methods describe existing mechanisms or planned relationships, not authority to run them.
Third-Party Contributors identify projects/providers, not an exhaustive legal notices audit or
a claim of direct endorsement. Missing final supplier or release decisions remain unselected.

### SyMoNeuRaL Platform / API

**State: EXISTING implementation; target governed executor PLANNED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Professionalize requirements and integrate professional workflows under owner control. |
| Scope Boundaries: | Routing, governance, identity, evidence and integrations; model intelligence does not itself grant execution rights. |
| Software/Hardware Descriptions: | Python API/application host; CPU orchestration and governed local GPU or external provider work. |
| Aliases: | SyMoNeuRaL; API; platform backend. |
| Deploy Methods: | Existing systemd API mechanism; activation requires its own owner gate. |
| Affected Components: | All professional applications, account/entitlement and HTTP ingress. |
| Location of Source Code and Licensing: | `backend/api.py`; `backend/apps/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | FastAPI, uvicorn and dependency authors; model/runtime attribution is separate. |
| Associated Runtimes: | Python; subprocess model runtimes; existing GPU governor. |

### SyMoNeuRaL HTTP Gateway

**State: EXISTING implementation; dated LIVE evidence in ProjectStatus.**

| Field | Registry entry |
|---|---|
| Business Justification: | Provide the public serving chain's routing/validation boundary. |
| Scope Boundaries: | HTTP gateway; distinct from blockchain licensing gateway code in the same parent directory. |
| Software/Hardware Descriptions: | Rust HTTP/proxy module; CPU/network execution. |
| Aliases: | symoneural-gateway; HTTP Gateway. |
| Deploy Methods: | Existing systemd Gateway mechanism, loopback :8000 in accepted evidence; no deployment authorized here. |
| Affected Components: | Web, API, app inventory/status. |
| Location of Source Code and Licensing: | `backend/apps/gateway/src/`; `backend/apps/gateway/Cargo.toml`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Axum, Tokio, Reqwest, Wasmtime and their respective contributors. |
| Associated Runtimes: | Rust binary; upstream libraries retain their terms. |

### SyMoNeuRaL Web

**State: EXISTING implementation; dated LIVE evidence in ProjectStatus.**

| Field | Registry entry |
|---|---|
| Business Justification: | Serve site/TLS entry and connect requests to the API chain. |
| Scope Boundaries: | First-party wrapper/integration around upstream Caddy; not a claim of authorship of Caddy. |
| Software/Hardware Descriptions: | Go wrapper; existing Web owns :80/:443 in accepted evidence. |
| Aliases: | symoneural-web; Web. |
| Deploy Methods: | Existing systemd Web mechanism; independent distro caddy stays inactive/disabled in accepted baseline. |
| Affected Components: | Site artifacts, HTTP Gateway, public ingress. |
| Location of Source Code and Licensing: | `web/symoneural-web/main.go`; `web/symoneural-web/go.mod`; `web/symoneural-web/build/THIRD_PARTY_NOTICES.md`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Caddy and dependency contributors; go.mod records Caddy v2.11.4. |
| Associated Runtimes: | Go; Caddy library. Build identity and installation remain separate evidence. |

### Symon Chat

**State: EXISTING; dated real-response acceptance.**

| Field | Registry entry |
|---|---|
| Business Justification: | Provide professional language interaction through the selected Symon experience. |
| Scope Boundaries: | Language generation; base-model restoration does not establish proprietary model training. |
| Software/Hardware Descriptions: | Local language runtime on shared GPU with CPU orchestration; target provider routing remains governed. |
| Aliases: | SyMoNeuRaL Chat; SymonChat S1-7B (existing house identity). |
| Deploy Methods: | API/page mechanisms and configured local model artifacts; model fetch/start is separately gated. |
| Affected Components: | Remix, Project callbacks, Coder/Studio provider use, governor. |
| Location of Source Code and Licensing: | `backend/api.py`; `site/chat.html`; `backend/models/PROVENANCE.json`; `engines/symoneural-llm/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | llama.cpp/ggml; Qwen model authors and model distributors identified in provenance. |
| Associated Runtimes: | symoneural-llm; 7B base and small draft artifacts; retain upstream identities. |

### Symon Image

**State: EXISTING; September 3 text render VERIFIED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Generate useful images through the first-party workflow. |
| Scope Boundaries: | Image UI/integration and governed rendering; upstream diffusion model attribution remains intact. |
| Software/Hardware Descriptions: | GPU diffusion plus CPU work such as text encoding; four image payloads have accepted immutable provenance. |
| Aliases: | SyMoNeuRaL Image; SymonImage F1 (existing house identity). |
| Deploy Methods: | Configured API/diffusion subprocess and adopted artifacts; no new installation or activation here. |
| Affected Components: | Sigils, image outputs, governor; separate Studio backend is not implicitly restored. |
| Location of Source Code and Licensing: | `backend/api.py`; `site/image.html`; `backend/models/PROVENANCE.json`; `engines/symoneural-diffuse/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | stable-diffusion.cpp contributors; FLUX.1-schnell, T5, CLIP and VAE source/distributor identities in provenance. |
| Associated Runtimes: | symoneural-diffuse; verified payload acquisition identities, not deterministic render reproducibility. |

### Symon Sigils

**State: EXISTING; text-generated alpha output VERIFIED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Produce constrained sticker/cutout assets with actual alpha. |
| Scope Boundaries: | Constrained Image variant; text rendering, uploaded-photo segmentation, and speech are distinct capabilities. |
| Software/Hardware Descriptions: | Shared image GPU runtime plus first-party CPU alpha/keying; optional segmentation/speech dependencies remain OPEN. |
| Aliases: | SyMoNeuRaL Sigils; owner 'stigils' references resolve to Sigils. |
| Deploy Methods: | API/page with shared image artifacts; optional rembg/Whisper adoption requires a separate gate. |
| Affected Components: | Image, governor, output retrieval, optional upload/speech workflows. |
| Location of Source Code and Licensing: | `backend/apps/sigils/`; `site/sigils.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Image runtime/model contributors; rembg/ONNX and Whisper dependencies where enabled. |
| Associated Runtimes: | Shared diffusion runtime; CPU postprocessing; optional ONNX/Whisper subprocesses. |

### Symon Remix

**State: EXISTING; dated real playlist acceptance.**

| Field | Registry entry |
|---|---|
| Business Justification: | Turn language requests into ordered playlists/workflows. |
| Scope Boundaries: | Current playlist client uses Chat; older standalone DJ deployment descriptions are historical, not today's topology. |
| Software/Hardware Descriptions: | CPU/network orchestration around local language inference; optional music-service integrations. |
| Aliases: | SyMoNeuRaL Remix; DJ (historical subproject). |
| Deploy Methods: | Current API/site mechanism; historical subproject :8090/:9001 instructions require separate reconciliation before use. |
| Affected Components: | Chat; playlist UI; optional external music service. |
| Location of Source Code and Licensing: | `backend/api.py`; `backend/apps/remix/`; `site/remix.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Local language contributors; FastAPI/httpx; Spotify integration where configured. |
| Associated Runtimes: | Current local language path; distinct legacy DJ service documentation retained. |

### Symon RavenCalc

**State: EXISTING exact symbolic implementation; GPU numerical extension PLANNED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Provide exact mathematical computation with inspectable results. |
| Scope Boundaries: | Exact symbolic expression-tree work remains CPU-first / CPU-capable; GPU is not required for exactness. |
| Software/Hardware Descriptions: | SymPy-backed CPU operations. Optional separate numerical/batched accelerator may target matrices, vectors, numerical integration and high-volume evaluation. |
| Aliases: | RavenCalc; SyMoNeuRaL RavenCalc. |
| Deploy Methods: | Existing app/API/page mechanism; no numerical GPU backend enabled by this registry. |
| Affected Components: | Math UI, future workflow routing and numerical accelerator. |
| Location of Source Code and Licensing: | `backend/apps/ravencalc/ravencalc.py`; `site/ravencalc.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | SymPy contributors; future acceleration dependencies unselected. |
| Associated Runtimes: | Python/SymPy today; future GPU numerical runtime is PLANNED. |

### Symon Project

**State: EXISTING workspace/store implementation; requested model workflow acceptance OPEN.**

| Field | Registry entry |
|---|---|
| Business Justification: | Organize project knowledge, records and governed work. |
| Scope Boundaries: | Workspace/store orchestration owns no weights. Source availability does not prove requested direct-model behavior. |
| Software/Hardware Descriptions: | Python/FastAPI/Pydantic with SQLite/FTS5; optional model callback. |
| Aliases: | SyMoNeuRaL Project; Project. |
| Deploy Methods: | Existing API/page mechanism; no migration or model routing change authorized here. |
| Affected Components: | Chat/model callback, project records, future Coder/Studio integration. |
| Location of Source Code and Licensing: | `backend/apps/project/`; `site/project.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | FastAPI, Pydantic, SQLite and optional model/runtime contributors. |
| Associated Runtimes: | CPU data/storage operations; local or cloud inference classified separately when connected. |

### Symon Coder

**State: EXISTING workspace module; first-party control plane PLANNED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Carry out bounded engineering work with auditable authority and evidence. |
| Scope Boundaries: | Existing file/tool operations do not establish task leases, controlled execution, independent audit, or qualified autonomous coding. |
| Software/Hardware Descriptions: | Parent role and bounded specialist architecture below; one owner across the task tree. |
| Aliases: | Symon Coder Operator; Symon Coder Auditor; existing coder module. |
| Deploy Methods: | Existing workspace surface is configuration-gated; future controlled executor deployment unselected. |
| Affected Components: | Project, Studio, providers, evidence, Git and controlled host tools. |
| Location of Source Code and Licensing: | `backend/apps/coder/`; `site/coder.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Existing Python/tool dependencies; selected reasoning providers retain their identities. |
| Associated Runtimes: | CPU orchestration with local GPU/CLOUD/HYBRID reasoning as selected; authority is independent of compute. |

### Multi-Coder session surface

**State: EXISTING uncommitted prototype; full seven-preset/rotation/training acceptance OPEN.**

| Field | Registry entry |
|---|---|
| Business Justification: | Let the user compare attributed provider answers and decide disagreements. |
| Scope Boundaries: | One prompt, separate attributed responses; no hidden winner. Current source excludes automatic workspace mutation, rotation and training. |
| Software/Hardware Descriptions: | Seven listed presets; four involving unavailable Codex are disabled pending a proven answer-only boundary. |
| Aliases: | Multi-Coder; local coders; transitional Claude/Codex/Symon responses. |
| Deploy Methods: | Existing local-only API/page source; scratch debate acceptance recorded separately from live acceptance. |
| Affected Components: | Providers, user decisions, future Studio/training/batch routing. |
| Location of Source Code and Licensing: | `backend/apps/coders/`; `site/coders.html`; `tests/coders_smoke.mjs`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Symon-local runtime/model authors; Anthropic/Claude and OpenAI/Codex installed CLI providers. |
| Associated Runtimes: | Python session orchestration; local language API and installed provider CLIs; per-user isolation remains OPEN. |

### Symon Studio

**State: EXISTING agent/render bench incomplete; unified workspace PLANNED.**

| Field | Registry entry |
|---|---|
| Business Justification: | Unify professional applications, tools, provider routing and evidence for the operator. |
| Scope Boundaries: | Do not equate the current bench with the proposed unified workspace or image restoration with ComfyUI recovery. |
| Software/Hardware Descriptions: | Existing Python agent/tool integration and separate ComfyUI backend; target UI/control areas below. |
| Aliases: | SyMoNeuRaL Studio; Symon Studio; image bench (existing). |
| Deploy Methods: | Existing gated API integration/separate render process; future unified deployment requires its own task. |
| Affected Components: | Chat, Image, Sigils, Project, Coder, providers, plugins, telemetry/evidence. |
| Location of Source Code and Licensing: | `backend/apps/studio/`; `engines/symoneural-ui/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | ComfyUI, llama.cpp/Ollama adapters and optional FastMCP dependencies. Upstream ComfyUI terms remain separate; release classification is unresolved. |
| Associated Runtimes: | Python; language adapters; ComfyUI HTTP/WebSocket backend; optional isolated venv. |

### Symon Miner — GPU / ASIC / licensing

**State: EXISTING modules; operational acceptance BLOCKED in last evidence.**

| Field | Registry entry |
|---|---|
| Business Justification: | Support governed mining operations and hardware/device workflows. |
| Scope Boundaries: | Orchestration does not implement KawPow itself. Real ASIC telemetry needs responding hardware; QEMU control-board emulation does not emulate hashboards. No earnings guarantee. |
| Software/Hardware Descriptions: | GPU mining engine, DEVICE control and CPU/network licensing are distinct subunits of one product/rack identity. |
| Aliases: | SyMoNeuRaL Miner; cryptominer; asicminer; mining licensing gateway. |
| Deploy Methods: | Operator-configured external miner/device runtimes; explicit enable/config/operation gate required. |
| Affected Components: | GPU governor, device network, entitlement/settlement, Miner UI. |
| Location of Source Code and Licensing: | `backend/apps/cryptominer/`; `backend/apps/asicminer/`; `backend/apps/gateway/`; `ops/gateway/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Operator-supplied miner authors, device/firmware vendors, QEMU and TRON integration contributors; per-artifact terms required. |
| Associated Runtimes: | External KawPow process; isolated ASIC control venv/device protocols; QEMU; TRON/USDT licensing. GPU/DEVICE/HYBRID as applicable. |

### Symon Streamer

**State: EXISTING implementation; no fresh operation proof in this gate.**

| Field | Registry entry |
|---|---|
| Business Justification: | Organize and serve configured streams and guide data. |
| Scope Boundaries: | Source/provider availability and permissions are separate from local orchestration. |
| Software/Hardware Descriptions: | Python/network stream routing; ffmpeg HLS stream-copy and external IPTV sources. |
| Aliases: | SyMoNeuRaL Streamer; historical tuner/guide. |
| Deploy Methods: | Existing API/runtime mechanism; no channel or provider configuration change here. |
| Affected Components: | Guide, player surfaces, external sources. |
| Location of Source Code and Licensing: | `backend/apps/streamer/`; `backend/apps/streamer/guide/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | ffmpeg and applicable stream/guide providers; external content rights remain separate. |
| Associated Runtimes: | Python; ffmpeg; network providers. GPU not implied by the presence of video. |

### Symon Live

**State: EXISTING implementation; no fresh operation proof in this gate.**

| Field | Registry entry |
|---|---|
| Business Justification: | Integrate live production and observable media workflows. |
| Scope Boundaries: | OBS/ffmpeg encoding is distinct from language/image model compute and may operate outside the inference governor. |
| Software/Hardware Descriptions: | OBS websocket integration and HLS output; actual resource use must be observed. |
| Aliases: | SyMoNeuRaL Live; Live. |
| Deploy Methods: | Existing app and external OBS/ffmpeg setup; gated activation. |
| Affected Components: | Media outputs, Streamer/player, future telemetry. |
| Location of Source Code and Licensing: | `backend/apps/live/`; `site/live.html`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | OBS, ffmpeg and websocket client contributors. |
| Associated Runtimes: | Python/network; external encoding, optionally NVENC. Graphics/encoding must be distinguished from COMPUTE. |

### Accounts / Symon Controlboard

**State: EXISTING infrastructure; owner-requested product acceptance OPEN.**

| Field | Registry entry |
|---|---|
| Business Justification: | Provide identity, entitlements, operational visibility and user-access administration. |
| Scope Boundaries: | Existing accounts/routes are not proof of signup, super-admin, temporary password or per-demo assignment completion. |
| Software/Hardware Descriptions: | Python identity/session/meter and application-control integration; privileged actions need backend authorization. |
| Aliases: | Account; Control Board; Controlboard; future Symon Control. |
| Deploy Methods: | Existing API/page mechanisms; auth/data/service changes require an owner gate. |
| Affected Components: | All protected applications, demo routes, provider credentials, user administration. |
| Location of Source Code and Licensing: | `backend/apps/accounts/`; `backend/apps/controlboard/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Framework/security/storage dependencies under their own terms; provider authentication contracts where integrated. |
| Associated Runtimes: | CPU/API/storage and external identity/provider services where configured. |

### DispatchOS / vertical applications

**State: EXISTING DispatchOS application; complete demo entitlement acceptance OPEN.**

| Field | Registry entry |
|---|---|
| Business Justification: | Formalize customer-specific professional workflows. |
| Scope Boundaries: | Vertical application state/auth is separate from general operator-tool authority. Demo assignment must be enforced by the backend. |
| Software/Hardware Descriptions: | First-party routes/store/authz and AI callback integration. |
| Aliases: | DispatchOS; /demo/dispatchos; future customer demo applications. |
| Deploy Methods: | Existing API/demo mechanism; each customer/demo deployment and access gate must be explicit. |
| Affected Components: | Accounts/entitlements, workflow state, optional model callbacks. |
| Location of Source Code and Licensing: | `backend/apps/dispatchos/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Framework/runtime contributors and selected reasoning providers; customer data and rights remain separate. |
| Associated Runtimes: | Python application/storage; optional local or cloud model callbacks. |

### Symon Build / delivery engineering

**State: EXISTING build/operations sources; per-platform release gates remain OPEN.**

| Field | Registry entry |
|---|---|
| Business Justification: | Produce verifiable artifacts, custody records and controlled delivery. |
| Scope Boundaries: | Build is not install, promotion, deployment, signing, publication or release. Native platforms require named owner gates. |
| Software/Hardware Descriptions: | Python/shell, Rust, Go, optional container/platform workflows. |
| Aliases: | Build engineering; release/custody workflows; Symon Build (professional direction). |
| Deploy Methods: | Mechanisms in ops/scripts/tools; historical Bento workflow is not the current production serving chain. |
| Affected Components: | Source, models, notices, artifacts, services and delivery evidence. |
| Location of Source Code and Licensing: | `ops/`; `scripts/`; `tools/`; `web/`; `deploy/bento/`; first-party LICENSE and applicable upstream terms under the shared convention above. |
| Third-Party Contributors: | Language toolchains, container/platform projects and each packaged upstream dependency. |
| Associated Runtimes: | CPU/build toolchains; GPU/DEVICE/CLOUD only for explicitly scoped workload/tool requirements. |

## Planned professional roles and domains

| Role / route | Business purpose and scope | Source, runtime, deployment and third-party relationship |
|---|---|---|
| Symon Business — Planner / Governor | Professionalize rough ideas into problem/customer definitions, business justification, scope, product requirements, cost/value and commercial constraints, licensing/vendor considerations, acceptance/release criteria, owner assignments, risk, packaging, entitlement/billing and SME routing. Does not replace Coder. | PLANNED profile/control role; no distinct completed source/runtime or deploy method established. Uses governed provider/tool relationships selected by a future gate. |
| Symon Coder — Operator / Auditor | Controlled engineering execution and independent evidence assessment. | Existing workspace code is listed above; target authority/lease/executor and subagents are PLANNED. |
| Symon SME — Domain Specialist | Route professional work to appropriate expertise within a task/evidence contract. | PLANNED role/profile; not necessarily a separate frontend or model. |
| Proposed professional domains | Business, Research, Security, Docs, Data, Ops, Release, Custody, Hardware, Embedded, Legal, Finance, Support, Sales, Training, Automation. | Proposed routes/profiles beneath a common shell where useful; source, selected providers, deployment and release terms not established. No implementation authorization. |

Applicable planned-role aliases are their Symon names above. Their affected components are platform
intake/routing, task gates, evidence, providers and controlled tools. Their future source/license
relationships must be recorded here when an explicitly authorized implementation selects them.

## Symon Coder and bounded specialist subagents — PLANNED

Parent Symon Coder delegates bounded evidence work to specialists such as:

| Specialist | Evidence responsibility |
|---|---|
| Symon Provenance Verifier | Artifact origin, immutable identity and custody chain. |
| Symon Git Guard | Branch/HEAD/index/stash/path ownership and scope boundaries. |
| Symon GPU Observer | Compute/graphics classification, lease, process ownership and release. |
| Symon Runtime Auditor | Process/service/runtime acceptance under a read-only contract. |
| Symon Test Auditor | Test relevance, actual results, skipped/unverified boundaries. |
| Symon Configuration Investigator | Explain configuration differences with evidence, without automatic repair. |
| Symon License/Custody Auditor | Source/model/license/notice relationships and release evidence gaps. |
| Symon Network Auditor | Socket ownership, exposure boundaries and network vantage limitations. |
| Symon Build/Reproducibility Auditor | Source-to-artifact identities and bounded repeatability claims. |

Default child contract: **PROJECT AUTHORITY: NONE; MUTATION AUTHORITY: NONE; REPAIR AUTHORITY: NONE.**
Exactly **ONE mutation owner across the complete task tree**. Delegation cannot multiply authority.
Child evidence supports **FACT, CORRELATION, INFERENCE, UNPROVEN, CONFIDENCE, MUTATIONS, STOP CONDITION**.
The parent aggregates evidence and applies the task-gate verdict. Provider prose claiming a PASS
is not a substitute for the required measurements or controlled execution.

## Unified Studio workspace — PLANNED

| Region | Intended content |
|---|---|
| Left application/model rail | Symon Chat, Symon Image, Symon Sigils, Symon Project, Symon Coder, RavenCalc, Symon Miner, future first-party applications. |
| Right tool rail/workspace | Terminal, Browser, Files, Side Chat, Artifacts, Transcript with Summary and Verbose views. |
| Feature areas / tabs | Workspace, Multi-Coder, Plugins, Function Block Grid, Model Setup, Providers, Telemetry, Evidence. |
| Advanced routing policy | Local ↔ Cloud; Light ↔ Ultra/Code. |

These controls express routing, budget and reasoning **POLICY**. They do not assert that arbitrary
provider APIs support identical knobs. SyMoNeuRaL backend routing owns selection and governance;
the frontend presents only supported choices and honest provider capability limits.

The existing agent/render bench and separate ComfyUI process are useful implementation context,
not completion of this unified workspace. Multi-Coder, model setup, plugins and tool execution
remain subject to authentication, task contracts and evidence boundaries.

## Multi-Coder / training direction — PLANNED beyond current prototype

Provide single Symon/Claude/Codex sessions; all three pairings; and a tri-coder option, with genuine
availability checks. One user prompt yields separate, attributed responses. Preserve every option;
if providers disagree, the user may choose or request clarification/debate. No hidden merge, ranking,
automatic winning answer, or majority decision replaces the user.

Ordered plan → execute → report → next-plan rotation and batch processing are distinct from response
comparison. Only the task's mutation owner can execute, and a next-plan artifact does not activate it.

Training mode lets the user select subject, trainers and receiver; the receiver cannot be its own
trainer. Trainers may draft independently and discuss, but **100% explicit agreement on the same
version/identity of one training prompt** is required before receiver dispatch. Editing the prompt
invalidates assent. Similarity, majority vote, inferred agreement, or an orchestrator-written compromise
does not satisfy unanimity. No agreement means no dispatch. User selection cannot waive trainer agreement.
Agreement/dispatch are not evidence of actual training, model quality or release readiness.

R-188 per-user credential/quota isolation and Codex's answer-only boundary remain acceptance gaps.
Existing local-only prototypes must not be described as completed public or multi-user routing.

## Providers beneath the control plane

| Provider identity | Current relationship | Boundary |
|---|---|---|
| Symon-local | Existing local language/model runtime path; restored upstream base artifacts with Symon house aliases. | Preferred future provider where qualified; not proof of trained first-party weights. |
| OpenAI / Codex | Transitional direct tooling and an existing answer-adapter definition. | Codex remains unavailable in the multi-coder source pending answer-only proof; no general routing/authority claim. |
| Anthropic / Claude | Transitional direct tooling and evidenced Symon+Claude multi-response adapter behavior. | Provider session credentials are not site-wide shared authority; per-user isolation remains open. |
| Google | Owner-stated future provider relationship. | PLANNED normalized provider integration; no implemented adapter established here. |
| Qwen | Upstream local language model family represented in the provenance manifest. | Model lineage is not a hosted API promise, first-party authorship, or task authority. |
| Future providers | Optional integrations under normalized capability and entitlement policies. | Selection, API support, pricing and terms must be evidenced in a future authorized task. |

[Model provenance](backend/models/PROVENANCE.json) retains source repositories, artifacts and relationships.
Cloud operations and provider capabilities need their own router evidence; a local desktop graphics
process named ChatGPT is not proof of local OpenAI inference, and Claude need not appear in nvidia-smi.

## Plugins — proprietary/commercial extension layer

Plugins connect external AI, software, services, devices and professional workflows to the proprietary
SyMoNeuRaL backend: provider normalization, routing, entitlements, security, task contracts, mutation leases,
tool execution, evidence, customer state, domain logic, billing and auditing. This is the professional
integration value; upstream components retain their independent licensing relationships.

A plugin may supply adapters, API integrations, routes, domain logic, schemas, tool permissions, task
types, SME contracts, verification, entitlement/billing logic, UI integration and customer workflows.
The commercial control/packaging platform is **PLANNED**, not proven by existing experimental plugins.

| Existing source | Relationship / execution | Scope limit |
|---|---|---|
| `backend/apps/studio/plugins/exp/` | First-party lifecycle/container/manifest experiment: services/events, fibers, teardown, presets and HTTP/CLI surfaces; CPU orchestration with plugin-dependent resources. | Not the completed commercial governance/entitlement platform. |
| `backend/apps/studio/plugins/reinforce/` | Native CUDA training/compute integration; GPU with CPU orchestration. Package metadata declares proprietary first-party code; cuda-python/cuda-core, CuPy, NumPy and CUDA CCCL retain upstream terms. | Distinct from private `training/` QLoRA artifacts; source presence does not prove model training acceptance. |
| `backend/apps/studio/plugins/discovery/` | Search, browser crawl, optional synthesis; CPU/network and potentially CLOUD/HYBRID through configured providers. | Browser/synthesis dependencies and access must be established per task. |

Plugin registry requirements use the same Business Justification, Scope Boundaries, Software/Hardware
Descriptions, Aliases, Deploy Methods, Affected Components, Location of Source Code and Licensing,
Third-Party Contributors, Associated Runtimes fields as first-party components. Existing plugin
experiments affect Studio/runtime integration; aliases are exp, reinforce and discovery; deploy through
their documented local integration mechanisms only when gated. Their justification is respectively
plugin lifecycle experiments, training compute integration, and professional discovery/synthesis.

Future examples: GitHub Engineering, Yocto Build, NVIDIA CUDA, AWS, Cloudflare, accounting, CRM,
PLC/industrial automation, mining operations, video production and DispatchOS vertical integrations.
These are concepts, not selected vendors, deployed products, prices or authorized work.

Execution classes are **CPU, GPU, CLOUD, HYBRID, DEVICE**. Do not classify all plugins as CPU.
Classify the real dependencies; a plugin name or provider identity does not grant execution permission.

## Telemetry / Live Stack direction — PLANNED

Live Stack must represent **CPU / GPU / CLOUD / HYBRID / DEVICE**, with **OFFLINE** availability
distinguished from the execution resource class. A cloud service is not offline merely because it has
no local GPU PID. A process listed by nvidia-smi is not automatically model COMPUTE.

First-party observation should cover:

- NVIDIA GRAPHICS versus COMPUTE; PID → application/provider mapping where established; per-process VRAM.
- GPU model, driver, CUDA, utilization, memory, temperature and power.
- Governor lease, queue, acquire/release timestamps, unexpected compute PIDs and post-task leak state.
- Cloud provider/model/request/token/latency/cost activity from the SyMoNeuRaL provider router,
  with unavailable or unmeasured fields explicitly labeled rather than invented.

Per-application rackview needs a major redesign into concise app-specific telemetry instead of
duplicating the full Live Stack. Owner screenshots in the [design index](docs/design/references/2026-09-03/INDEX.md)
are requirements, not new runtime diagnoses. Snapshot GPU memory numbers alone cannot prove a leak.

RavenCalc's exact symbolic operations remain CPU-first/CPU-capable. A future GPU numerical/batched
accelerator is optional and separate, with measured workload/accuracy evidence before claiming benefit.

## Documentation ownership and commit acceptance

| Record | Ownership / treatment |
|---|---|
| ProjectStatus.md | Current verified state and evidence limits. |
| SyMoNSaysLLC.md | Current organization/platform/component/provider/plugin registry. |
| PROJECT-TASKS.md | Backlog and task IDs; not execution authority. |
| INTAKE.md | Existing ignored local unresolved incoming-work queue; preserve unique questions and source IDs. |
| GARRETT-REQUESTS.md | Existing ignored local owner request/disposition ledger; no automatic backfill/edit authority. |
| GUARDRAILS.md / AGENTS.md | Standing project control / provider-neutral task and subagent contract. |
| README.md | Concise repository entry point. |
| Sept1.md / AUDIT.md / dated audits / GARRETT-INBOX.md | Historical plans, audits, questions and escalation evidence. Dates and original verdicts remain intact. |
| CLAUDE.md and nested provider history | Transitional provider-specific guidance subordinate to first-party authority. |
| LICENSE / LICENSES.md / per-source licenses | First-party terms / dated relationship inventory / applicable upstream terms; no fresh blanket licensing PASS. |

Before **EVERY future commit**, determine whether verified current state changes; if yes,
**ProjectStatus.md must be updated in that focused commit**. Determine whether architecture,
component relationships, providers, plugins, runtimes, deployment method, business scope, source location,
licensing or third-party relationships change; if yes, **SyMoNSaysLLC.md must be updated in that focused commit**.
This is a **COMMIT ACCEPTANCE REQUIREMENT**, not blanket authority to rewrite documents outside a task.

The owner gate for this consolidation is the architecture source. Existing implementation paths and
accepted reports support only the explicitly marked existing relationships. Planned domains, controls,
plugins, telemetry and training are not implementation authorization.
