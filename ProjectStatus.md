# SyMoNeuRaL Project Status

## Checkpoint

Canonical current verified project-state authority, reconciled **2026-09-03 EDT**.
Canonical repository: `/home/google/Symoneural`; branch: `main`.
Accepted engineering HEAD: **`1d72cc6e5435a9c9572f0ea6b5faf2aa2d0933a0`**,
`models: harden image payload provenance`. Starting staged/stash counts: **0 / 0**.

This documentation consolidation advances that engineering checkpoint by one documentation-only
commit. Its identity is the commit introducing this document, recorded in the
[external consolidation report](/home/google/symoneural-docs-reconciliation-20260903/DOCUMENTATION-RECONCILIATION-20260903.md).
The hash above is the engineering baseline, not a claim that HEAD remains unchanged after this commit.
No runtime, source implementation, model, or deployed artifact is changed by this gate.

## Active work

Garrett authorized one canonical documentation consolidation gate. Codex is its sole mutation owner.
Claude is a read-only external workspace auditor with no canonical mutation authority; this gate
does not dispatch Claude. On delivery Codex stops with no mutation authority. No next task is selected.

## Current state

The September 3 repository baseline is **VERIFIED** after owner reconciliation of the Claude display
setting and Codex Desktop's imported AGENTS pointer. Image and text-generated Sigils were restored and
proved through the production API. Immutable provenance checks for their four image payloads were
verified and committed. These results do not establish a completed customer release, a trained Symon
model, a unified Studio, or the planned governed Symon Coder.

All operational statements below are bounded by their cited observation time. This documentation gate
performs no new host/service, Internet, inference, training, or render measurements.

## Executive status table

| Area | Status | Evidence boundary / remaining acceptance |
|---|---|---|
| September 3 baseline | VERIFIED | Owner-reconciled final checkpoint [E1]; earlier HOLD reports remain historical. |
| Production serving chain | LIVE at last observation | Sep 3 02:41:49 EDT socket/unit evidence [E2]; not a new public functional probe. |
| Image | LIVE / VERIFIED | Sep 3 approximately 03:25 EDT: HTTP 200, 768×768 RGB, output retrieval 200 [E3]. |
| Text-generated Sigils | LIVE / VERIFIED | Same batch: HTTP 200, 512×512 RGBA, 85.88% transparent, nondegenerate [E3]. |
| Four image payloads | VERIFIED / REPRODUCIBLE within scope | Pinned acquisition/identity and fail-closed fixture tests [E4]; committed [E5]. No deterministic-render or whole-build claim. |
| Chat / Remix | LIVE in dated September 2 evidence | Real local GPU answer and three generated Remix tracks [E6]; no fresh September 3 generation proof here. |
| Multi-Coder response/debate | Partly VERIFIED; full acceptance BLOCKED | Initial Symon+Claude live evidence; three-round debate verified on scratch API :8898 [E7]. Current production debate acceptance unestablished. |
| Codex answer-only boundary | BLOCKED | Probe performed a file read; required boundary not proven. Four of seven presets unavailable [E7]. |
| Symon Coder control plane / subagents | PLANNED | Existing workspace and multi-response modules are not the proposed task/lease/executor architecture. |
| Unified Studio | PLANNED; existing bench incomplete | Image restoration does not prove the separate Studio render backend or unified UI. |
| rembg / Whisper | OPEN | Segmentation/speech payload gaps; not blockers for verified text Image/Sigils [E3]. |
| Miner operation | BLOCKED in last operational evidence | Disabled/unconfigured paths and unproven device/runtime readiness [E8]; not fixed by image weights. |
| Login / customer entitlements | OPEN | Existing account/entitlement code is not acceptance of all R-188/R-191/R-193 requirements. |
| Responsive UI / documentation / telemetry | PLANNED repairs | Owner screenshot requirements and backlog; no frontend implementation in this gate. |
| Customer/distribution release | RELEASE-COMPLETE NOT ESTABLISHED | Runtime checks and payload identity do not establish release, licensing, signed artifacts, or customer acceptance. |

## Protected/current baseline

The exact starting short status was:

```text
 M .claude/HANDOVER.md
 M .claude/settings.local.json
 M PROJECT-TASKS.md
 M backend/api.py
 M backend/apps/ROSTER.md
 M docs/ops/EXPORTS.md
 M docs/ops/MEASUREMENTS.md
?? AGENTS.md
?? backend/apps/coders/
?? site/coders.html
?? tests/coders_smoke.mjs
```

Six previously modified tracked paths and six untracked coder/page/test files were
**RECONCILED PRIOR STATE**. The expanded coder directory contains `__init__.py`, `page.html`,
`routes.py`, and `test_coders.py`. The settings-only display change and imported AGENTS pointer
were **EXPLAINED SYSTEM EFFECT**. Ignored review evidence and `run/progress.html` remain
**GENERATED / IGNORED STATE**; existence is not acceptance.

This gate intentionally establishes a new tracked root AGENTS contract and adds documentation-owned
backlog text. Its commit excludes the pre-existing PROJECT-TASKS hunks. Every other prior dirty source,
configuration, provider handover, operational record, and untracked implementation remains protected.
The final exact status belongs in the external consolidation report, not an invented clean-tree claim.

### Evidenced production topology

At [E2]'s observation: `symoneural-web` PID **1449** owned TCP 80/443 and UDP 443;
Admin port 2019 was not remeasured in [E2]. `symoneural-gateway` PID **1538** owned
`127.0.0.1:8000`; `symoneural-api` PID **1505** owned `127.0.0.1:8800`.
All three were active/enabled with NRestarts 0. Distro `caddy` was inactive/disabled.
The intended chain is Web → HTTP Gateway → API; direct API probes and public serving are separate proofs.

Boot ID: `9abf2443-70ee-43e5-ad9f-e4c952472fd5`; kernel boot **2026-09-02 23:12:14 EDT**
(**2026-09-03 03:12:14 UTC**); service starts recorded at 23:12:25 EDT.
These were **EXPECTED BOOT EFFECT**, not unexplained source mutation. September 3 baseline verification
did not repeat public HTTP/exposure testing. Earlier Gate 1.1 failures and later bounded evidence remain
intact; same-host public-URL checks do not prove an independent Internet network vantage.

## Controlling architecture

[SyMoNSaysLLC.md](SyMoNSaysLLC.md) owns company/platform/component/provider/plugin relationships.
[GUARDRAILS.md](GUARDRAILS.md) owns standing control rules; [AGENTS.md](AGENTS.md) owns the
provider-neutral agent contract. Garrett alone authorizes tasks; exactly one mutation owner exists
across a task tree. Provider identity never confers project authority.

The target is first-party Symon Business/Coder/SME roles above provider intelligence and a Controlled
Tool Executor. Current direct Claude/Codex sessions are transitional. A roadmap, backlog checkbox,
historical handoff, successful build, or provider response cannot activate a task or authorize deployment.

## Completed work by area

- **Baseline reconciliation:** [E1] resolved the two disputed paths without restoring the setting or
  deleting the imported pointer. Historical failed checkpoints were preserved.
- **Image/Sigils restoration:** [E3] recorded four payloads totaling **12,665,850,204 bytes**, upstream →
  staging → adopted identities, two real outputs, acquire/release cycles, and final 0 MiB COMPUTE/no compute
  processes. Desktop GRAPHICS use remained. Sigils' recorded alpha is binary, not a feathering claim.
- **Provenance:** [E4] records pinned revisions and SHA-256 verification, rejecting wrong reuse/adoption/
  promotion identities; **24 tests passed, zero skips**. [E5] committed exactly
  `backend/models/PROVENANCE.json`, `scripts/fetch-models.sh`, and
  `backend/apps/test_weight_names.py`. Seven unrelated manifest entries were outside that hardening scope.
- **Transitional multi-response work:** [E7] records 98 tests and 20 browser checks for scratch debate,
  attributed history and bounded rounds. These are not proof of full tri-coder, rotation, training,
  per-user credential isolation, or current production debate acceptance.
- **Documentation:** this gate establishes current authorities, reconciles document ownership,
  records planned architecture, and preserves twelve exact owner screenshots as design evidence.

## Remaining work by area

| Area | Owner-controlled backlog |
|---|---|
| UI and docs | /docs CSS leakage; documentation overflow; usable 100% browser zoom; useful Image/Remix/RavenCalc views; Chat branding; Login; Control Board and text-density repairs. |
| Live Stack | CPU/GPU/CLOUD/HYBRID/DEVICE execution and OFFLINE state; concise per-app rackview; first-party GPU and provider-router telemetry. |
| Coder / Studio | Task Gate + Mutation Lease + Evidence Contract; controlled execution; bounded subagents; unified Studio rails/tabs and policy-driven routing. |
| Multi-Coder | Prove Codex boundary, production debate acceptance, per-user provider isolation, batch/rotation, exact unanimous trainer approval and actual receiver training evidence. |
| Models | rembg and Whisper; owner-qualified training/LoRA work. Restored upstream base weights are not trained first-party model evidence. |
| Miner | Configured software, safe GPU/governor behavior, real-device proof where applicable; no operation authorized here. |
| Accounts / demos | Visible Login/signup; owner super-admin and temporary credential administration; server-enforced per-demo assignment and independently tested all-demo access. |
| Delivery / licensing | Resolve historical inventory/source-location discrepancies and satisfy per-artifact release gates in a separately authorized task. |

Actionable identifiers and acceptance proposals are in [PROJECT-TASKS.md](PROJECT-TASKS.md).
The [design index](docs/design/references/2026-09-03/INDEX.md) maps all twelve source screenshots.
Older per-demo requests distinguish super-admin from all-demo access; the named all-demo accounts
are not evidence that those privileges have been created.

## Verification state

**LIVE** means an operation was observed on a running service at a stated time.
**VERIFIED** means specified acceptance checks passed with evidence.
**REPRODUCIBLE** identifies the exact reproducibility boundary; here, the four image payloads'
acquisition/identity and tested enforcement behavior.
**RELEASE-COMPLETE** requires the separately defined distribution/customer acceptance set.
**PLANNED** denotes approved architectural direction or backlog, not implemented functionality.
**BLOCKED** identifies an unmet prerequisite with no implied repair authority.
OPEN items may remain unimplemented without invalidating a narrower verified result.

## Acceptance still required

No broad all-app PASS exists. Remaining acceptance includes actual selected-provider answers, enforced
answer-only and per-user boundaries, user-controlled disagreement, version-bound 100% trainer agreement
before receiver dispatch, measured receiver training/evaluation, responsive browser interaction, requested
demo entitlements, Studio runtime integration, and applicable release/custody checks. Success labels must
not be inferred from HTTP 200 page shells, files on disk, model renaming, screenshots, or service PIDs alone.

## Open blockers

Codex's answer-only boundary and R-188 isolation block full multi-coder exposure/acceptance.
Studio and Miner have separate runtime/configuration gaps. Optional segmentation and speech remain open.
Dated license inventories contain unresolved distribution statements; no licensing/release PASS is asserted.
Protected working-tree work remains intentionally uncommitted and must not be swept into another commit.

## Next owner-authorized task

**None assigned by this document. STOP after the current documentation deliverable.**
Garrett decides the next bounded task, its mutation owner, evidence contract, and stop condition.

## Definition of done

For this gate: coherent current authorities; preserved history; complete planned/current distinctions;
owner design sources copied without byte changes; scoped documentation checks pass; exactly one focused
documentation commit excluding prior implementation and task-note hunks; external evidence report returned;
Codex stopped. This definition does not authorize or complete the remaining engineering backlog.

Before every future commit, assess current-state impact and update this file in the same focused commit
when needed. Assess registry impact and update [SyMoNSaysLLC.md](SyMoNSaysLLC.md) when needed.
This is a commit acceptance requirement, not standing permission to edit outside a task.

## Evidence register

- **[E1]** [Final September 3 baseline](/home/google/symoneural-start-of-day-final-20260903/START-OF-DAY-FINAL-CHECKPOINT-20260903.md).
- **[E2]** [September 3 host/baseline observations](/home/google/symoneural-start-of-day-20260903/START-OF-DAY-BASELINE-20260903.md).
- **[E3]** [Image/Sigils restoration](review/RESPONSE-2026-09-03-claude-image-sigils-payload-restoration.md).
- **[E4]** [Immutable provenance hardening](review/RESPONSE-2026-09-03-codex-image-sigils-provenance-hardening.md).
- **[E5]** [Provenance commit checkpoint](/home/google/symoneural-provenance-checkpoint-20260903/PROVENANCE-HARDENING-CHECKPOINT-20260903.md).
- **[E6]** [Chat/Remix model restoration](review/RESPONSE-2026-09-02-codex-R186-weights.md).
- **[E7]** [R-184 debate/boundary response](review/RESPONSE-2026-09-02-codex-R184-debate.md).
- **[E8]** [Channel restoration handoff](review/NEXT-CLAUDE-2026-09-02-channel-restoration.md).
- [Standing owner architecture](/home/google/symoneural-session-closeout-20260902/SYMON-STANDING-ARCHITECTURE.md).

External absolute paths and ignored review files are host-local evidence and are not promised in a fresh
clone. Historical reports retain their original verdicts; this document reconciles their bounded claims.
