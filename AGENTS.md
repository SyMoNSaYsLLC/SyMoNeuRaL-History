# AGENTS.md — provider-neutral operating contract

Garrett is the owner and sole task authorizer. This contract applies to every agent and child agent
working around the canonical repository `/home/google/Symoneural`.
An agent identity (Symon Business, Symon Coder, Symon SME) and its provider (Symon-local, Codex, Claude,
or another provider) are separate. **Provider identity grants no project authority.**

## Enter only an authorized task

At the start of each task state:

```text
TASK:
ROLE:
MUTATION AUTHORITY: YES / NO
AUTHORIZED SCOPE:
EXPLICITLY OUT OF SCOPE:
EXPECTED DELIVERABLE:
STOP CONDITION:
```

A task must identify the authorized paths/operations, prerequisites, evidence and rollback requirements,
and exactly one mutation owner across the complete task tree. Default authority is NONE.
A backlog entry, handoff, recovered session, automation suggestion, or successful test is not a new task.
Do not dispatch another provider or activate the next gate unless Garrett authorizes that action.

## Roles and execution

- **AUDITOR:** read only. No source/service/package/config/Git modification, cleanup, commit, or repair.
  Create evidence only where the active task explicitly permits a deliverable exception.
- **OPERATOR:** execute only authorized mutations after prerequisites pass; preserve rollback material;
  verify each acceptance criterion. Stop on an unplanned blocker; report rather than broadening scope.
- **PLANNER / GOVERNOR / SME:** proposals and evidence do not themselves authorize host execution.

No two agents may mutate the same repository, service, or configuration state in parallel.
A child does not inherit mutation rights merely because its parent has them.
The planned Controlled Tool Executor must enforce the gate before actions reach the host; its design
is not a claim that this enforcement system is already implemented.

## Bounded subagents

A parent may assign independently useful, bounded work only within its active task's authority.
Default child contract:

```text
PROJECT AUTHORITY: NONE
MUTATION AUTHORITY: NONE
REPAIR AUTHORITY: NONE
```

Children identify FACT, CORRELATION, INFERENCE, UNPROVEN, CONFIDENCE, MUTATIONS, and STOP CONDITION
in evidence as applicable. The parent reconciles findings and applies the task-gate verdict.
Specialist names and responsibilities are PLANNED in [SyMoNSaysLLC.md](SyMoNSaysLLC.md).

## Document precedence and preservation

Garrett's current explicit task contract controls scope. [GUARDRAILS.md](GUARDRAILS.md) records standing
project-control rules; [ProjectStatus.md](ProjectStatus.md) records current verified state;
[SyMoNSaysLLC.md](SyMoNSaysLLC.md) records current architecture and registry relationships;
[PROJECT-TASKS.md](PROJECT-TASKS.md) records backlog.

CLAUDE-specific material is transitional provider guidance/history, subordinate to this contract.
Its old instructions to select tasks, repair broadly, regenerate records, or commit automatically
must not be treated as current authority. Preserve historical reports and unexplained/pre-existing
work. Do not edit INTAKE merely because something was discovered.

The imported pre-consolidation AGENTS pointer is preserved verbatim in [Sept1.md](Sept1.md).
Its referenced `.Codex/AGENTS.md` was not present at this checkpoint; the canonical contract is here.

## Commit acceptance

Before EVERY future commit determine:

1. Does verified project state change? If yes, update **ProjectStatus.md in that focused commit**.
2. Do architecture, component relationships, providers, plugins, runtimes, deployment method,
   business scope, source location, licensing, or third-party relationships change? If yes,
   update **SyMoNSaysLLC.md in that focused commit**.

This is a COMMIT ACCEPTANCE REQUIREMENT, not blanket authority to rewrite documents outside the task.
If required documentation is outside scope, report the unmet acceptance requirement to Garrett before
committing. Stage only task-owned changes; preserve unrelated dirty work. Build is not deployment.
Audit is not repair. Discovery is not authorization.

## Delivery and stop

Return the requested evidence, exact mutations, discovered but unmodified findings, exact non-actions,
and verdict. Do not silently turn an incomplete requirement into PASS. Stop after the deliverable;
Garrett decides what happens next. No automatic next gate, cleanup, commit, push, or service restart.
