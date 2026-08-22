# SyMoNeuRaL Therapist — model supervision, hallucination recovery, intervention

R-179, adopted 2026-08-22 into `docs/specs/scope-of-work-2026-08-22.md` as **Phase 4.8**.
A dated spec, not a state document; `PROJECT-TASKS.md` stays canonical and this becomes a
numbered task (proposed #104) through intake when its dependencies clear.

**What it is:** a model-facing supervisor between a client and a target model. It shadows the
context window, reads the draft response before it becomes durable conversation state, scores
it, and intervenes on an escalation ladder. **What it is not, and the production wording must
say so:** *"SyMoNeuRaL Therapist is an AI model-supervision and correction system. It is not
healthcare, clinical therapy, medical advice, or psychological treatment for people."* The
clinic framing ("the doctor is in") is brand voice for a supervisor of machines, and every
user-facing string obeys the SymonSays naming rules (R-97) like any other surface.

## Placement

A Studio plugin on the Phase-3 surface, its capabilities declared as Phase-4 function blocks,
its pipelines as manifests, its evaluator models as catalog entries. Not a second gateway,
not a second arbitrator, not a public `/dev` surface, no migration of existing routes.

Dependencies, hard: Phase 0 (clean tree) → Phase 1 (#75 secrets/export, restart guard) →
Phase 3 (plugin surface **and the permissions card**, which Level 4 escalation renders
through) → #88 (token posture — every write/intervention route waits on it) → Phase 4
(catalog, provenance gate, governor profile planner). Nothing here starts before those.

## The loop

```
client → Therapist (shadow context) → target model → draft
      → Evaluator scores draft
      → clean: release into history, audit "clean"
      → suspect: choose level → optionally retry with note or pruned context
      → final response + APPEND-ONLY audit record → Studio panel shows the trail
```

Production names: Interceptor (intake) · Evaluator (diagnosis) · Intervention (treatment).

**Intervention ladder:**

| Level | Action | Constraint |
|---|---|---|
| 0 | observe only — score, log, pass through unchanged | the first smoke runs here; no lease |
| 1 | nudge — hidden supervisor note on a retry, user intent preserved | note text is in the audit |
| 2 | context pruning — quarantine the turn, replace with a factual summary, retry | the pruned turn is KEPT in the audit, never deleted |
| 3 | parameter restraint — lower temperature/top_p, grounded mode until recovery | changes recorded per retry |
| 4 | escalate — pause, render the Phase-3 permissions card, operator approves/denies | integrates, does not reimplement |

**The audit rule is the honesty rule wearing a new coat:** no intervention writes durable
context without an append-only audit entry carrying original draft, symptoms, level, edit,
and final output. A supervisor that silently rewrites history is the one dishonest pixel this
product cannot carry — the site's whole argument is measurement.

## Two corrections to the source addendum

**1. `/v1/chat/completions` is already someone's address.** `ops/Caddyfile` sends `/v1/*` to
symon-gateway (:8000) — the existing OpenAI-compatible surface. A Therapist claiming that
path would shadow or be shadowed by it. If a compatibility shim is ever wanted, it is a
**gateway adapter** (the gateway already validates payloads on that path and can route
"supervised" requests through the Therapist), or it lives at
`/api/therapist/v1-compat/chat/completions`. Never a second claimant to `/v1`.

**2. Streaming is the design decision, so it is made now.** The interception model assumes a
draft can be inspected before the user sees it. `/api/chat` streams tokens — a token shown
cannot be unshown, and the warm first-frame is a measured 0.2 s that buffering would spend.
So per-surface, one of two modes, declared in the manifest and shown in the panel:
`buffered` (full interception; adds latency; for pipelines and non-interactive runs) or
`post-hoc` (stream passes; a detected symptom produces a **visible** correction event and an
audited retry — supervision the user can see, never a silent rewrite of what they read).

Also normalised from the source: the manifest's static `requires_governor_lease: false`
becomes **per-mode** — rules-only evaluation takes no lease (RavenCalc's precedent: CPU by
design and says so); a model evaluator runs as a small tenant under a governor-approved
profile, which is exactly the 7B-Q4-plus-small-tenant dual the Phase-4 planner certifies.

## Function blocks and aliases (into the Phase-4 vocabulary)

```
therapist · interceptor · evaluator · intervention · hallucination_detector ·
context_drift_detector · contradiction_checker · entropy_monitor · context_pruner ·
parameter_restraint · retry_supervisor · session_auditor
```

Aliases, normalised in code (the jokes may live in aliases; canonical names in all UI):
`therapy`/`model_therapy`/`model_doctor` → therapist · `reality_check` →
hallucination_detector · `chemical_restraint` → parameter_restraint · `memory_wipe` →
context_pruner · `nudge` → retry_supervisor.

## Routes

Public (all gated per #88 once decided; writes never before it):
`GET /api/therapist/status` · `POST /api/therapist/evaluate` · `POST /api/therapist/run` ·
`POST /api/therapist/retry` · `GET /api/therapist/sessions[/{id}]` ·
`POST /api/therapist/sessions/{id}/approve|deny`.
Local, behind `_require_local`: `/local/therapist`, `/local/therapist/routes`,
`/local/therapist/sessions`, `/local/therapist/events`. No `file://`/`vscode://`/`pycharm://`
in any public response — same rule, same test shape, as the Phase-4 route index.

## Studio panel

Sessions with target model, evaluator, mode (`buffered`/`post-hoc`), symptom score, last
intervention, retry count, lease state, audit link. Visible states:
`clean · watching · suspect · nudged · pruned · restrained · escalated · blocked · recovered`.
Every state is a real reading — no decorative indicators, per the standing rule.

## Evaluator models

Catalog entries like any Phase-4 model: license and provenance required, `status:
blocked-until-provenance` until the record exists. This is exactly the pattern
`incoming/scope-example/` already demonstrates red-first (`big-llm-fp16`), and the same
refusal vocabulary applies. First implementation: **rules + optional small classifier/judge**
— never a second 7B by default.

## Tests and evidence

Backend: `apps/studio/test_therapist.py` (+ manifest, interventions, routes files as listed
in R-179's source). Browser: session state visible in `tests/studio.mjs`. Minimum assertions,
all behavioural: plugin loads only on the plugin surface; rules-only evaluator flags a
contradiction with no GPU lease; drift → Level 1; repetition escalates to Level 2; restraint
provably lowers sampling parameters on the retry; **no durable write without an audit entry**;
approve/deny obey #88; nothing public carries an editor link; an unprovenanced evaluator is
refused by exact reason.

`backend/SMOKE-therapist.md` is written from the **first run against a real target model**,
with the fields R-179 lists (SHA, weights yes/no, lease events, draft, symptoms, level, edit,
final, result). Mock runs label every figure mock and claim nothing about the stack.

Checks (assigned at promotion; the SMOKE check is the one only a run turns green):

```
check: exists backend/apps/studio/test_therapist.py
check: grep TherapistPluginSurfaceTests -- backend/apps/studio/test_therapist.py
check: exists backend/SMOKE-therapist.md
check: grep Intervention level -- backend/SMOKE-therapist.md
check: grep Governor lease events -- backend/SMOKE-therapist.md
```
