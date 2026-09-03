# SyMoNeuRaL Project Status

## Checkpoint

Canonical current verified project-state authority, reconciled **2026-09-03 EDT** after the
accepted Persona / LoRA restoration and safe workspace cleanup reports.
Canonical repository: `/home/google/Symoneural`; branch: `main`.
Accepted starting HEAD: **`5427f2a5f5ec40761d6d957fab810644bae6292a`**,
`docs: establish canonical project authorities`. Starting staged/stash counts: **0 / 0**.

The earlier engineering checkpoint remains `1d72cc6e5435a9c9572f0ea6b5faf2aa2d0933a0`,
`models: harden image payload provenance` [E5]. The first documentation consolidation is [E9].
This checkpoint advances the starting HEAD by one documentation-only commit; its identity is
recorded in the [checkpoint report](/home/google/SyMoNeuRaL-Workspace/evidence/documentation-checkpoint-20260903/DOCUMENTATION-CHECKPOINT-20260903.md).
No runtime, source implementation, model payload, cleanup action or deployed artifact is changed
by this documentation gate.

## Active work

Garrett authorized one documentation checkpoint for two completed owner-authorized state changes.
Codex is its sole mutation owner. Claude is **STOPPED — MUTATION AUTHORITY: NONE** and is not
dispatched by this gate. Only ProjectStatus requires a current-state update; the existing registry
relationships are unchanged. PROJECT-TASKS and all prior dirty work remain untouched.
On delivery Codex stops with no mutation authority. No next task is selected.

## Current state

The September 3 repository baseline is **VERIFIED** after owner reconciliation of the Claude display
setting and Codex Desktop's imported AGENTS pointer. Image and text-generated Sigils were restored and
proved through the production API. Immutable provenance checks for their four image payloads were
verified and committed.

The **first-party persona adapter was restored from custody and verified applied at serving time**
[E10]. The unrestarted API recognized it dynamically; one bounded Chat request returned
`adapter=true` while the live engine argv carried `--lora` with the restored serving payload.
**Restoration is not new training. Held-out evaluation remains outstanding; the broader
training/model-development milestone is NOT complete.** One response does not objectively establish
persona quality, and restored upstream Image/Sigils base weights remain separate from first-party
trained-model evidence.

The **SAFE CLEANUP PHASE is VERIFIED; 45 HELD ITEMS REMAIN** [E11]. Safe audited actions completed
and the external workspace now exists. Relocated bytes did not free disk space; the much smaller
reclaimed total comes from the deletion ledger. Overall home cleanup remains PARTIAL.

All operational statements below are bounded by their cited reports and observation times.
This documentation gate performs no new service-health, Internet, inference, training, render or
cleanup verification workload; its current process/lock inspection is limited to the agent-control boundary.

## Executive status table

| Area | Status | Evidence boundary / remaining acceptance |
|---|---|---|
| September 3 baseline | VERIFIED | Owner-reconciled final checkpoint [E1]; earlier HOLD reports remain historical. |
| Production serving chain | LIVE in dated evidence | Sep 3 02:41:49 EDT socket/unit evidence [E2]; [E11] later records all three services still active after cleanup. No new public functional probe. |
| Image | LIVE / VERIFIED | Sep 3 approximately 03:25 EDT: HTTP 200, 768×768 RGB, output retrieval 200 [E3]. |
| Text-generated Sigils | LIVE / VERIFIED | Same batch: HTTP 200, 512×512 RGBA, 85.88% transparent, nondegenerate [E3]. |
| Four image payloads | VERIFIED / REPRODUCIBLE within scope | Pinned acquisition/identity and fail-closed fixture tests [E4]; committed [E5]. No deterministic-render or whole-build claim. |
| Chat / persona adapter | LIVE / VERIFIED in September 3 evidence | One governed Chat request at 05:13 EDT returned HTTP 200 and `adapter=true`; engine argv used restored LoRA; API unrestarted [E10]. |
| Persona / LoRA restoration | VERIFIED; broader training milestone OPEN | Existing first-party artifacts restored from custody, not newly trained. Held-out evaluation remains outstanding [E10]. |
| Remix | LIVE in dated September 2 evidence | Three generated Remix tracks [E6]; the later Chat request is not a fresh Remix acceptance run. |
| Multi-Coder response/debate | Partly VERIFIED; full acceptance BLOCKED | Initial Symon+Claude live evidence; three-round debate verified on scratch API :8898 [E7]. Current production debate acceptance unestablished. |
| Codex answer-only boundary | BLOCKED | Probe performed a file read; required boundary not proven. Four of seven presets unavailable [E7]. |
| Symon Coder control plane / subagents | PLANNED | Existing workspace and multi-response modules are not the proposed task/lease/executor architecture. |
| Unified Studio | PLANNED; existing bench incomplete | Image restoration does not prove the separate Studio render backend or unified UI. |
| rembg / Whisper | OPEN | Segmentation/speech payload gaps; not blockers for verified text Image/Sigils [E3]. |
| Miner operation | BLOCKED in last operational evidence | Disabled/unconfigured paths and unproven device/runtime readiness [E8]; not fixed by image weights. |
| Login / customer entitlements | OPEN | Existing account/entitlement code is not acceptance of all R-188/R-191/R-193 requirements. |
| Workspace cleanup / custody | SAFE CLEANUP PHASE VERIFIED; 45 HELD ITEMS REMAIN | 121 objects relocated, 11 deleted, top-level entries 294 → 173; overall cleanup PARTIAL [E11]. |
| Documentation | Current-state checkpoint | LoRA and cleanup reconciled; registry structure and protected task-list hunks unchanged. |
| Responsive UI / telemetry | PLANNED repairs | Owner screenshot requirements and backlog; no frontend implementation in this gate. |
| Customer/distribution release | RELEASE-COMPLETE NOT ESTABLISHED | Runtime checks and payload identity do not establish release, licensing, signed artifacts, or customer acceptance. |

## Protected/current baseline

The exact starting short status for this checkpoint was:

```text
 M .claude/HANDOVER.md
 M .claude/settings.local.json
 M PROJECT-TASKS.md
 M backend/api.py
 M backend/apps/ROSTER.md
 M docs/ops/EXPORTS.md
 M docs/ops/MEASUREMENTS.md
?? backend/apps/coders/
?? site/coders.html
?? tests/coders_smoke.mjs
```

Six previously modified tracked paths and six untracked coder/page/test files remain
**RECONCILED PRIOR STATE**. The expanded coder directory contains `__init__.py`, `page.html`,
`routes.py`, and `test_coders.py`. The settings-only display change remains
**EXPLAINED SYSTEM EFFECT**. The former imported AGENTS pointer's origin remains explained;
[E9] deliberately replaced it with the now-committed root contract. This gate does not edit AGENTS.
Ignored review evidence and `run/progress.html` remain **GENERATED / IGNORED STATE**.

[E9] excluded the prior 57 PROJECT-TASKS additions from its commit. This checkpoint leaves that
entire working file untouched and stages none of its prior hunks. Every prior dirty source,
configuration, provider handover, operational record and untracked implementation stays protected.
[E10]'s three restored payloads are gitignored and were not committed; unchanged Git status alone
does not prove those payloads' existence or custody.

### Evidenced production topology

At [E2]'s observation: `symoneural-web` PID **1449** owned TCP 80/443 and UDP 443;
admin port 2019 was not remeasured in [E2]. `symoneural-gateway` PID **1538** owned
`127.0.0.1:8000`; `symoneural-api` PID **1505** owned `127.0.0.1:8800`.
All three were active/enabled with NRestarts 0. Distro `caddy` was inactive/disabled.
The intended chain is Web → HTTP Gateway → API; direct API probes and public serving are separate proofs.

Boot ID: `9abf2443-70ee-43e5-ad9f-e4c952472fd5`; kernel boot **2026-09-02 23:12:14 EDT**
(**2026-09-03 03:12:14 UTC**); service starts recorded at 23:12:25 EDT.
These were **EXPECTED BOOT EFFECT**, not unexplained source mutation. September 3 baseline verification
did not repeat public HTTP/exposure testing. Earlier Gate 1.1 failures and later bounded evidence remain
intact; same-host public-URL checks do not prove an independent Internet network vantage.
Later [E10] records dynamic adapter recognition without API restart; [E11] records all three services
active after cleanup. Neither is a new boot, socket-ownership or independent Internet acceptance test.

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
- **Documentation:** [E9] established current authorities, reconciled document ownership, recorded
  planned architecture and preserved twelve exact owner screenshots. This checkpoint reconciles the
  two subsequently accepted state changes below; it does not implement the backlog.

### Models / first-party Persona / LoRA

**PERSONA / LORA RESTORATION VERIFIED** [E10]. Three existing payloads were restored from the vault
to already-declared destinations at mode 600 with staged/adopted SHA-256 equality:

- Primary serving payload: `training/adapter/symoneural-lora.gguf` (80,767,680 bytes).
- Existing PEFT payload: `training/adapter/adapter_model.safetensors` (161,533,192 bytes).
- Existing sibling adapter payload: `training/adapter-qwen36/adapter_model.safetensors`
  (200,384,784 bytes); this is not nested under `training/adapter/`.

The unrestarted API recognized the primary adapter dynamically. At **05:13 EDT**, the live
`symoneural-llm` argv carried `--lora /home/google/Symoneural/training/adapter/symoneural-lora.gguf`,
and a bounded normal-path Chat request returned HTTP 200 with `adapter=true`.
The report records the governor taking and releasing the lease, with one controlled engine remaining
normally resident at 8,330 MiB COMPUTE and the lock free; that is not a claim of zero post-request VRAM
or a second uncontrolled CUDA workload. Desktop GRAPHICS allocations were distinguished.

This verifies restoration and serving application of an existing first-party persona adapter.
**No new training or held-out evaluation occurred; the broader model-development milestone remains
incomplete.** A response sounding like Symon is not objective persona-quality proof.
Both `training/adapter/tokenizer.json` and `training/adapter-qwen36/tokenizer.json` remain
**UNKNOWN_STOP / not restored**. The historical reinforce smoke-run adapter at
`run/reinforce/adapters/20260817-102314-8e6000/adapter_model.safetensors` remains intentionally unrestored.

### Workspace / cleanup / custody

**SAFE CLEANUP PHASE VERIFIED — 45 HELD ITEMS REMAIN.**
The accepted [E11] verdict remains **HOME WORKSPACE CLEANUP PARTIAL — SAFE ACTIONS COMPLETE,
HELD ITEMS REMAIN**; it does not mean all of `/home/google` has been cleaned.

| Measure | Accepted cleanup result |
|---|---|
| Relocation inside the same filesystem | **121 objects; 27,989,292,625 bytes** (reported as **26.067 GB**). |
| Deletion / reclamation | **11 objects; 439,007,621 bytes** (reported as approximately **0.409 GB**) per the deletion ledger. |
| /home/google top-level entries | **294 → 173**. |
| Held work | **45 items**: 35 REVIEW / UNKNOWN_STOP, six ACTIVE scripts, three new protected/unaudited roots, one read-only rollback directory. |

Relocation is **not reclaimed disk space**. The report's GB approximations use binary conversion
(26.067 GiB / 0.409 GiB); exact byte counts above remove unit ambiguity. Its reclaimed total comes from
pre-deletion per-object byte measurements, not an independent byte-granular `df` before/after proof.

`/home/google/SyMoNeuRaL-Workspace/` now contains `evidence/`, `handoffs/`, `staging/`,
`builds/`, `archives/`, `backups/` and `imports/`. [E11] records staging/imports empty at that
checkpoint, not permission to populate them. It records all safe audited actions complete while
REVIEW / UNKNOWN_STOP dispositions were not decided or mutated.

The cleanup evidence records the canonical repository preserved, all three services still active,
the outbound `references/ComfyUI-Shared` symlink resolving to `/home/google/ComfyUI-Shared`,
registered Git worktrees preserved, and the restored adapters plus LoRA staging/evidence intact.
The LoRA roots stayed at `/home/google/symoneural-lora-restore-staging-20260903/` and
`/home/google/symoneural-lora-restoration-20260903/`.

The vault `/home/google/Downloads/symoneural-vault-2026-08-19-v2.tar.gz` remains
**KEEP / DURABLE_EVIDENCE**, mode 600, **398,369,206 bytes**, with unchanged re-measured SHA-256
`86aa9d85f7894640ace5e21b59aff2549b10bab72482dd41d8a6bbdab117644f` in [E10]/[E11].
Gitignored restored payloads do not replace its custody role. No move/delete is implied.

`/home/google/symoneural-cutover-rollback-20260826-154113` remains mode **555** read-only rollback
evidence in its original location. Under the current owner gate this is an **acceptable HOLD**;
no chmod or cosmetic relocation is required or authorized.

## Remaining work by area

| Area | Owner-controlled backlog |
|---|---|
| UI and docs | /docs CSS leakage; documentation overflow; usable 100% browser zoom; useful Image/Remix/RavenCalc views; Chat branding; Login; Control Board and text-density repairs. |
| Live Stack | CPU/GPU/CLOUD/HYBRID/DEVICE execution and OFFLINE state; concise per-app rackview; first-party GPU and provider-router telemetry. |
| Coder / Studio | Task Gate + Mutation Lease + Evidence Contract; controlled execution; bounded subagents; unified Studio rails/tabs and policy-driven routing. |
| Multi-Coder | Prove Codex boundary, production debate acceptance, per-user provider isolation, batch/rotation, exact unanimous trainer approval and actual receiver training evidence. |
| Models / LoRA | First-party persona adapter restored from custody and verified applied at serving time [E10]. Held-out evaluation remains outstanding; restoration is not new training and the broader milestone is incomplete. rembg/Whisper remain OPEN; two tokenizers remain UNKNOWN_STOP and the historical reinforce smoke adapter remains unrestored. Restored upstream base weights are not trained first-party model evidence. |
| Miner | Configured software, safe GPU/governor behavior, real-device proof where applicable; no operation authorized here. |
| Accounts / demos | Visible Login/signup; owner super-admin and temporary credential administration; server-enforced per-demo assignment and independently tested all-demo access. |
| Delivery / licensing | Resolve historical inventory/source-location discrepancies and satisfy per-artifact release gates in a separately authorized task. |
| Workspace / custody | Safe cleanup complete within its audited boundary; 45 held items remain. Preserve vault and LoRA recovery roots; leave mode-555 rollback evidence in place. Any further disposition needs Garrett's separate gate. |

Actionable identifiers and acceptance proposals are in [PROJECT-TASKS.md](PROJECT-TASKS.md).
The [design index](docs/design/references/2026-09-03/INDEX.md) maps all twelve source screenshots.
Older per-demo requests distinguish super-admin from all-demo access; the named all-demo accounts
are not evidence that those privileges have been created.
PROJECT-TASKS is unchanged in this checkpoint. Future reconciliation of its Models/LoRA and workspace
notes, if needed, belongs in a separately authorized task; existing owner hunks must remain protected.

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

Held-out evaluation of the restored persona adapter remains outstanding. Neither custody restoration
nor one successful Chat response completes the training/model-development milestone or proves persona quality.
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
The two UNKNOWN_STOP tokenizers and historical reinforce smoke adapter remain unrestored; no restoration
is activated here. Cleanup retains 45 held items. The mode-555 rollback directory is an acceptable
in-place HOLD, not a required repair. The vault remains KEEP / DURABLE_EVIDENCE.

## Next owner-authorized task

**None assigned after this documentation checkpoint. STOP after its deliverable.**
Garrett decides the next bounded task, its mutation owner, evidence contract, and stop condition.

## Definition of done

For this checkpoint: the accepted LoRA and cleanup evidence is accurately reflected, with restoration
separate from training/evaluation and relocation separate from reclamation; 45 held items and custody
protections remain explicit; only authorized documentation is committed; prior dirty/untracked work and
PROJECT-TASKS are untouched; the external checkpoint report is returned; Codex stops.
This definition does not authorize or complete remaining engineering, cleanup or held dispositions.

**SYMONSAYSLLC UPDATE NOT REQUIRED — NO STRUCTURAL CHANGE.** The reports restore existing payloads
to existing consumers and organize external custody files; they do not change component, business,
provider, plugin, runtime, deployment or source/licensing relationships. The registry remains unchanged.

Before every future commit, assess current-state impact and update this file in the same focused commit
when needed. Assess registry impact and update [SyMoNSaysLLC.md](SyMoNSaysLLC.md) when needed.
This is a commit acceptance requirement, not standing permission to edit outside a task.

## Evidence register

- **[E1]** [Final September 3 baseline](/home/google/SyMoNeuRaL-Workspace/evidence/symoneural-start-of-day-final-20260903/START-OF-DAY-FINAL-CHECKPOINT-20260903.md).
- **[E2]** [September 3 host/baseline observations](/home/google/SyMoNeuRaL-Workspace/evidence/symoneural-start-of-day-20260903/START-OF-DAY-BASELINE-20260903.md).
- **[E3]** [Image/Sigils restoration](review/RESPONSE-2026-09-03-claude-image-sigils-payload-restoration.md).
- **[E4]** [Immutable provenance hardening](review/RESPONSE-2026-09-03-codex-image-sigils-provenance-hardening.md).
- **[E5]** [Provenance commit checkpoint](/home/google/SyMoNeuRaL-Workspace/evidence/symoneural-provenance-checkpoint-20260903/PROVENANCE-HARDENING-CHECKPOINT-20260903.md).
- **[E6]** [Chat/Remix model restoration](review/RESPONSE-2026-09-02-codex-R186-weights.md).
- **[E7]** [R-184 debate/boundary response](review/RESPONSE-2026-09-02-codex-R184-debate.md).
- **[E8]** [Channel restoration handoff](review/NEXT-CLAUDE-2026-09-02-channel-restoration.md).
- **[E9]** [Canonical documentation consolidation](/home/google/symoneural-docs-reconciliation-20260903/DOCUMENTATION-RECONCILIATION-20260903.md).
- **[E10]** [Persona / LoRA restoration and serving verification](/home/google/symoneural-lora-restoration-20260903/LORA-RESTORATION-20260903.md).
- **[E11]** [Safe home-workspace cleanup execution](/home/google/SyMoNeuRaL-Workspace/evidence/home-cleanup-20260903/HOME-CLEANUP-EXECUTION-20260903.md).
- [Accepted evidence relocation ledger](/home/google/SyMoNeuRaL-Workspace/evidence/home-cleanup-20260903/MOVED.tsv).
- [Standing owner architecture](/home/google/SyMoNeuRaL-Workspace/evidence/symoneural-session-closeout-20260902/SYMON-STANDING-ARCHITECTURE.md).

External absolute paths and ignored review files are host-local evidence and are not promised in a fresh
clone. [E11]'s move ledger establishes the updated paths for the relocated E1/E2/E5 and standing
architecture records. Historical reports retain their original verdicts; this document reconciles their
bounded claims without rewriting their evidence.
