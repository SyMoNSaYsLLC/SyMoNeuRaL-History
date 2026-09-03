# GUARDRAILS.md — standing project-control and safety rules

Reconciled 2026-09-03. Garrett is the owner and sole task authorizer.
These rules replace the older blanket home-directory write and “default FIX” authority.
The exact retired text is preserved in [Sept1.md](Sept1.md), under retired root documentation snapshots.

## One task, one mutation owner

All work is task-gated. A current task specifies role, mutation authority, scope, authorized paths and
operations, prerequisites, rollback/evidence contract, and stop condition. Exactly one mutation owner
exists across the complete agent tree. Everyone else is read-only unless Garrett explicitly transfers
authority. A provider name, filesystem permission, old backlog, or previously proposed plan confers none.

No adjacent fixes, cleanup, automatic task promotion, documentation regeneration, service recovery,
or next gate may be inferred. An existing authorization remains valid within its stated task/scope;
it does not become permanent general project authority. A discovered defect is reported and classified.

## Mutation and delivery boundaries

- AUDIT IS NOT REPAIR. Auditors do not edit source, Git, services, packages, configuration, or perform cleanup.
  A task may explicitly permit a bounded evidence-file write.
- BUILD IS NOT DEPLOYMENT. Installation, promotion, signing, publication, service replacement/reload,
  and restart require authorization in the current task.
- Paths under `/home/google` are not automatically writable by project authority. Privileged paths,
  external APIs, credentials, devices, spending, and provider dispatch likewise require scoped authorization.
- Prove prerequisites before mutation. Preserve rollback/evidence material. Stop on an unplanned blocker.
  Do not erase failed evidence, fabricate provenance, normalize away failures, or claim untested acceptance.
- Preserve all prior dirty/untracked/ignored work. No reset, restore, delete, stash, clean, amend, stage,
  commit, remote change, or push beyond the explicit gate.
- Return the evidence/report, exact mutations, exact non-actions, unresolved findings and verdict, then STOP.
  Garrett selects the next task.

## Secrets, custody, GPU, and evidence

Do not print or commit credential values, private keys, tokens, or secret-bearing configuration.
Use names and redacted classifications in reports. Never treat editing a local secret as proof that
an upstream credential was revoked. Protected `training/corpus.jsonl`, `training/build_dataset.py`,
and `training/adapter/` require explicit path-specific authorization; historic backup exceptions
are not continuing write permission. No remote publication is implied by a local commit.

Honor the existing shared GPU governor within an authorized workload. Do not infer permission to
launch competing jobs, mining, training, model downloads, or inference from available VRAM.
Separate model COMPUTE residency from desktop GRAPHICS allocations. Measure the authorized acceptance
boundary; labels, process existence, page HTTP success, or a previous report alone cannot replace
required live functional evidence.

Historical review/evidence records keep their identity and verdict. Ignored files must not be force-added
or regenerated merely because documentation references them. A task may explicitly authorize publishing
particular documentation; record exactly what enters history and preserve unrelated material.

## Native platform holds

Linux native applications, Apple/Darwin, Windows, and Android/Firestick require separately named
owner-authorized tasks. Existing retired scaffolds and toolchain work are not advanced or removed by
inference. The former browser/API and SDK/toolchain exceptions are historical, not standing authority
to build, maintain, repair, or deploy without a current gate.

## Documentation and commit acceptance

[ProjectStatus.md](ProjectStatus.md) is current verified state.
[SyMoNSaysLLC.md](SyMoNSaysLLC.md) is current business/platform/component/provider/plugin registry.
[AGENTS.md](AGENTS.md) is the provider-neutral operating contract.
Historical dated records and provider handovers do not override them.

Before EVERY future commit determine whether verified current state changes; if yes, update
**ProjectStatus.md in that focused commit**. Determine whether architecture, component relationships,
providers, plugins, runtimes, deployment method, business scope, source location, licensing or
third-party relationships change; if yes, update **SyMoNSaysLLC.md in that focused commit**.

This is a **COMMIT ACCEPTANCE REQUIREMENT**, not standing authority to edit beyond the active gate.
If the necessary update is not authorized, report the scope/acceptance conflict before committing.
No task list or checkbox can by itself grant mutation authority.
