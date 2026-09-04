# SyMoNeuRaL Project Status

## Checkpoint

Canonical current verified project-state authority, reconciled **2026-09-04 EDT** after the
runtime first-party migration run.
Canonical repository: `/home/google/Symoneural`; branch: `main`.
Accepted HEAD: **`aa1bdff2`** (this section reconciled 2026-09-04 ~15:5x EDT).
Staged / stash counts: **0 / 0**.
Backend suite at this SHA: **2281 passed, 0 failed, 55 skipped**, measured, not carried forward.

**THIS FILE HAS NOW GONE STALE THE SAME WAY TWICE, AND THE PATTERN IS THE FINDING.** The entry
below records `5427f2a5` standing while the tree advanced fifteen commits. That was re-pinned to
`d79513b1` on 2026-09-03 -- and by 2026-09-04 the tree had advanced **nineteen** commits past
*that*. A second occurrence of an identical failure is not bad luck; it is a document whose
accuracy depends on somebody remembering, against a tree that moves every commit.

Two things follow, and only the second is a fix. First: **a SHA in this file is a claim about a
moment, and the only honest way to read one is to compare it against `git rev-parse HEAD`
yourself.** Second: the durable repair is a check that fails when the pinned SHA is not an
ancestor-or-equal of HEAD, in the manner of the count tripwires that have caught real drift
three times in this repo. Re-pinning by hand a third time would produce this same paragraph in
another day. **That check does not exist yet and is listed under Remaining work.**

**Superseded: `5427f2a5`, `docs: establish canonical project authorities`.** That SHA stood
here while the tree advanced fifteen commits past it, which is precisely the drift this file
exists to prevent -- a canonical current-state document describing a tree that had not existed
for hours. It was caught by an independent release red-team, not by this document. The commits
between are the 2026-09-03 production-closure run: repository-wide pytest collection
(`71e78186`), the multi-coder surface and its publish-path removal (`1dbcc4c9`), three tripwire
repairs (`423ae6d5`), the permission-mode display fix (`f023365e`, `f7f423e6`), the export
drift fix (`6ead248b`), the coders secret-containment, default-off switch and journal
(`ca5cb4e2`, `c5697bef`, `c1cf1e9d`), the garbo disposition (`4ad4aee4`), and the
install-caddy refusal (`3145876a`).

The earlier engineering checkpoint remains `1d72cc6e5435a9c9572f0ea6b5faf2aa2d0933a0`,
`models: harden image payload provenance` [E5]. The first documentation consolidation is [E9].

### The nineteen commits this file did not know about, 2026-09-03 → 2026-09-04

Grouped by what they did, because a list of subject lines is not a state description:

- **Mutation authority** — one plane and three surfaces routed through it: `8e99549e` (the plane
  itself, plus Studio's four `dangerous=True` tools), `d14ce57d` (every `apps/coder` host effect),
  `eb6d0f42` (the `apps/coders` provider spawn). `b0195e1d` updated the module counts.
- **Secret containment** — `debef396` (`--show` was printing the live session-signing secret),
  `6d6e08aa`, `f2a4a8fa`, `2d30b667` (a separate owner for the signer domain), `16b1cd44`
  (api.env split by security domain, values unchanged), `98964d7b`.
- **Runtimes made first-party** — `4b91a754` (the ASR engine built under our own name in
  `engines/symoneural-listen`, after weeks of both call sites naming a binary in gitignored
  `contrib/`), `f5f0a7e4` (its weight fetched; **ASR serves for the first time**), `af2d907d`
  (all three upstreams found where they actually are, so the engines can be rebuilt at all),
  `aa1bdff2` (**the LLM engine was announcing `Server: llama.cpp` on every HTTP response and
  `owned_by: llamacpp` in `/v1/models`**; both now ours, verified against the running server).
- **Truthfulness and units** — `4352767a` (stop claiming resident VRAM the box does not measure),
  `34b2975c` (boot ordering, and a start limit that was in the wrong section to apply),
  `cebaf674` (the canonical component/application/artifact model), `4d80c5cd`, `bca945f1`.

## Active work

**Runtime first-party migration, in progress.** Mutation owner: the agent working in
`/home/google/Symoneural`. This supersedes the 2026-09-03 documentation gate, under which Codex
was sole mutation owner and Claude was STOPPED; that gate is closed and its stop condition was
met. Nothing in this section grants authority for a future task.

Current runtime position, measured 2026-09-04:

| Runtime | Home | First-party? |
|---|---|---|
| `symoneural-llm` | `engines/symoneural-llm` | **yes** — artefacts and announced identity |
| `symoneural-diffuse` | `engines/symoneural-diffuse` | **yes** — artefacts; identity not audited |
| `symoneural-listen` | `engines/symoneural-listen` | **yes** — new 2026-09-04, CPU-only |
| `symoneural-ui` | `engines/symoneural-ui` | **NO — vendored ComfyUI**, the last one |

**Services deliberately stopped on owner instruction, 2026-09-04**, and this is a state
description rather than a fault: `symoneural-web` (stopped), `symoneural-gateway` (stopped and
disabled), `cloudflared` (stopped and disabled — a third-party binary whose unit named
`/usr/local/bin/cloudflared` while the binary is at `/usr/bin/cloudflared`, and which had
therefore failed **12,850** times since boot). Only `symoneural-api` runs. The gateway's source
and its 24 test files are untouched; removal was not performed, and the two premises offered for
it -- that it parented a shell, and that it carried the miner runtime -- were both measured false.

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
| September 3 baseline | VERIFIED at `d79513b1` | Owner-reconciled checkpoint [E1]; earlier HOLD reports remain historical. **Re-pinned 2026-09-03**: this row read VERIFIED while the accepted HEAD above still named `5427f2a5`, fifteen commits behind. A verdict is only as current as the SHA beside it. |
| Production serving chain | LIVE in dated evidence | Sep 3 02:41:49 EDT socket/unit evidence [E2]; [E11] later records all three services still active after cleanup. No new public functional probe. |
| Boot-publish guarantee | **NOT INSTALLED** | `symoneural-deploy.service` — the oneshot that republishes staged `site/` to `/var/www/symoneural` at boot — has no unit file in `/etc/systemd/system`. `ops/verify-runtime.sh` exits 1 on this alone (22 PASS / 9 FAIL); every other boundary check passes. Bounded: the webroot already holds the correct bytes and persists across reboot, so a reboot still serves — but the guarantee does not exist and any staged change needs `scripts/deploy.sh` run by hand. |
| Web runtime self-healing | **NOT SELF-HEALING** | `symoneural-web.service` is `Restart=no`, unlike api and gateway which are `Restart=always`. A crash of the TLS runtime does not come back on its own. |
| Image | LIVE / VERIFIED | Sep 3 approximately 03:25 EDT: HTTP 200, 768×768 RGB, output retrieval 200 [E3]. |
| Text-generated Sigils | LIVE / VERIFIED | Same batch: HTTP 200, 512×512 RGBA, 85.88% transparent, nondegenerate [E3]. |
| Four image payloads | VERIFIED / REPRODUCIBLE within scope | Pinned acquisition/identity and fail-closed fixture tests [E4]; committed [E5]. No deterministic-render or whole-build claim. |
| Chat / persona adapter | LIVE / VERIFIED in September 3 evidence | One governed Chat request at 05:13 EDT returned HTTP 200 and `adapter=true`; engine argv used restored LoRA; API unrestarted [E10]. |
| Persona / LoRA restoration | VERIFIED; broader training milestone OPEN | Existing first-party artifacts restored from custody, not newly trained. Held-out evaluation remains outstanding [E10]. |
| Remix | LIVE in dated September 2 evidence | Three generated Remix tracks [E6]; the later Chat request is not a fresh Remix acceptance run. |
| Multi-Coder response/debate | Partly VERIFIED; full acceptance BLOCKED | Initial Symon+Claude live evidence; three-round debate verified on scratch API :8898 [E7]. Current production debate acceptance unestablished. |
| Codex answer-only boundary | BLOCKED | Probe performed a file read; required boundary not proven. Four of seven presets unavailable [E7]. |
| Symon Coder control plane / subagents | PLANNED | Existing workspace and multi-response modules are not the proposed task/lease/executor architecture. |
| Unified Studio — inference surface | SERVING | `/api/studio/state` answers `enabled:true`. Distinct from the render backend below; the two were previously one row and the working half hid the broken half. |
| Unified Studio — render backend | **DEGRADED IN PRODUCTION** | ComfyUI on `127.0.0.1:8188` does not answer and `/api/status` reports the unit `offline`. Nothing starts it at boot: `scripts/symoneural-ui.sh start` is a manual step with no unit behind it. Every Studio render claim is unsupported while this is down. |
| rembg / Whisper | OPEN | Segmentation/speech payload gaps; not blockers for verified text Image/Sigils [E3]. |
| Miner operation | BLOCKED in last operational evidence | Disabled/unconfigured paths and unproven device/runtime readiness [E8]; not fixed by image weights. |
| Login / customer entitlements | OPEN | Existing account/entitlement code is not acceptance of all R-188/R-191/R-193 requirements. |
| Workspace cleanup / custody | SAFE CLEANUP PHASE VERIFIED; 45 HELD ITEMS REMAIN | 121 objects relocated, 11 deleted, top-level entries 294 → 173; overall cleanup PARTIAL [E11]. |
| Documentation | Current-state checkpoint | LoRA and cleanup reconciled; registry structure and protected task-list hunks unchanged. |
| Responsive UI / telemetry | PLANNED repairs | Owner screenshot requirements and backlog; no frontend implementation in this gate. |
| Customer/distribution release | RELEASE-COMPLETE NOT ESTABLISHED | Runtime checks and payload identity do not establish release, licensing, signed artifacts, or customer acceptance. |

## Protected/current baseline

The short status, re-measured 2026-09-03:

```text
 M .claude/HANDOVER.md
 M .claude/settings.local.json
 M PROJECT-TASKS.md
```

Three modified tracked files, **0 untracked**, 0 staged, 0 stash. All three are records rather
than source: a handoff pointer, task notes, and a settings display toggle. No source file is
dirty.

**The previous block listed seven more paths and every one of those claims is now false.**
`backend/api.py`, `backend/apps/ROSTER.md`, `docs/ops/EXPORTS.md`, `docs/ops/MEASUREMENTS.md`,
`backend/apps/coders/` and `tests/coders_smoke.mjs` are all tracked and clean --
they were committed during the 2026-09-03 closure run. `site/coders.html` is **absent by
design**: it was a superseded draft of the local-only operator surface sitting in the directory
`scripts/deploy.sh` publishes, so it was moved to
`SyMoNeuRaL-Workspace/evidence/coders-surface-disposition-20260903/` (byte-identical copies
retained) and `ops/Caddyfile` gained a `/coders` matcher so the API refuses the path rather
than `file_server` serving it.

Recording the correction rather than quietly replacing the block: a status file that keeps
listing committed work as uncommitted trains its readers to disbelieve it. The settings-only
display change remains **EXPLAINED SYSTEM EFFECT**. The former imported AGENTS pointer's origin remains explained;
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
| Models / LoRA | First-party persona adapter restored from custody and verified applied at serving time [E10] -- and still applied: a 2026-09-04 chat request measured **94.7 tok/s with `adapter: true`**. Held-out evaluation remains outstanding; restoration is not new training and the broader milestone is incomplete. **Whisper is RESOLVED** (`f5f0a7e4`: engine, weight, and a real transcription -- see `backend/SMOKE-listen-asr.md`); **rembg/u2net remains OPEN**; two tokenizers remain UNKNOWN_STOP and the historical reinforce smoke adapter remains unrestored. The 14B named by the tuner registry is absent from disk. Restored upstream base weights are not trained first-party model evidence. |
| **Runtimes (first-party)** | **`symoneural-miner` is the one runtime that is MISSING rather than absent by design.** `cryptominer/__init__.py:107` resolves `KAWPOW_BINARY` to `contrib/kawpowminer/...`, and `/contrib` is gitignored -- **the third instance of the pattern that already ate the ASR engine and the miner's own benchmark binary.** Buildable offline now: kawpowminer 1.2.4 source and all four dependency archives (boost 1.83.0, jsoncpp 1.8.0, CLI11 1.8.0, cpp-kawpow 1.1.0) are vendored under `references/referencestochatgpt/`. A working binary from 2026-08-17 exists there too but is quarantined under `references/`, exactly as the two `whisper-cli` binaries were. **`symoneural-ui` (ComfyUI) is the last vendored runtime**; Studio is the only rack row that depends on it. `symoneural-diffuse` ships an absolute CUDA RUNPATH and is **not relocatable by an installer** -- the fix is the `CMAKE_BUILD_RPATH_USE_ORIGIN=ON` flag already used for `listen`. Optional, not gaps: `streamer` (ffmpeg) and `live` (obs) execute third-party binaries and have no first-party runtime; six rack rows execute nothing external at all and need none. |
| Miner | Configured software, safe GPU/governor behavior, real-device proof where applicable; no operation authorized here. Runtime gap recorded in the Runtimes row above. |
| **This file** | **A tripwire that fails when the pinned checkpoint SHA is not an ancestor-or-equal of HEAD.** Twice now this document has described a tree that no longer existed, and both times a human caught it rather than a check. Until that exists, every SHA here must be read against `git rev-parse HEAD`. Second item: **14 of this file's 19 links do not survive a clone** -- 9 are absolute paths under `/home/google/...` and 5 point into `review/`, which `.gitignore:166` ignores. They all resolve on this box, which is why the problem is invisible from here. Relocating evidence is a custody decision and is Garrett's, not a repair to make silently. |
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
Studio and Miner have separate runtime/configuration gaps: **Studio's is a vendored runtime**
(ComfyUI, not first-party, and nothing starts it at boot -- `/api/status` reports it `offline`
and says so honestly), **Miner's is a missing one** (see the Runtimes row). Those are different
problems and the distinction is the point: one is built and unowned, the other is unbuilt.
**Speech is CLOSED** as of `f5f0a7e4` -- the ASR engine is first-party, the weight is on disk,
and a real transcription is recorded. Segmentation (u2net / rembg) remains open.
The `voice` surface is not on the rack: it needs `SYMONEURAL_VOICE_ENABLED=1` and
`SYMONEURAL_VOICE_TOKEN` in root-owned config, and because `/api/*` is public, enabling it
without the token would spend this box's CPU for strangers. That is an owner action.
Eleven `apps/voice` ASR tests still skip for want of `tests/fixtures/speech.wav`; the repo's own
README puts recording it on Garrett's side, and pointing them at a sample by environment
variable passes 33/33, which is evidence the path works and not a substitute for the fixture.
Dated license inventories contain unresolved distribution statements; no licensing/release PASS is asserted.
Protected working-tree work remains intentionally uncommitted and must not be swept into another commit.
The two UNKNOWN_STOP tokenizers and historical reinforce smoke adapter remain unrestored; no restoration
is activated here. Cleanup retains 45 held items. The mode-555 rollback directory is an acceptable
in-place HOLD, not a required repair. The vault remains KEEP / DURABLE_EVIDENCE.

## Next owner-authorized task

**Build `engines/symoneural-miner` from the vendored kawpowminer source**, owner-authorized
2026-09-04. It is the last application runtime that is missing rather than absent by design, all
sources and dependency archives are on disk so no network fetch is required, and the pattern is
the one already executed twice today for `symoneural-listen`: fork into `engines/` under our own
names via a step in the tracked `tools/fork_engines.sh`, never into gitignored `contrib/`, and
prove it with a real run rather than a file listing.

Acceptance, so this cannot be declared done from a directory listing: the binary exists under
our name at `engines/symoneural-miner/build/bin/symoneural-miner`; no third-party product name
survives in what ships; `cryptominer/__init__.py` resolves `KAWPOW_BINARY` there instead of
`contrib/`; and a stamped smoke record beside the code carries a reading only a real invocation
could produce. Garrett decides everything after that.

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
