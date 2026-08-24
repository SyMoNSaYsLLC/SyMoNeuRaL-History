# SyMoNeuRaL Capacity Lab

Factual concurrent-user measurement for **this exact server**, including where it
degrades and where it fails. Not a marketing benchmark.

**Concurrent user** = one simultaneous synthetic application *session* — a sequence of
real HTTP steps — not a single request. Sessions are released together on a barrier, and
the *achieved* concurrency is measured and reported next to the requested number, because
only one of those is a fact about the server.

## The booking blocker — read this first

**There is no Donnie booking application.** Repo audit at `main @ 7d1a5529`:

- 0 routes matching `book|appoint|dispatch|slot|schedul` across all 32 route decorators
  in `backend/api.py` and every app under `backend/apps/`
- no booking tables (`accounts` has only `meta`/`accounts`/`sessions`/`attempts`)
- `site/share-dispatchos.html` carries **0 fetch calls, 0 forms, 0 `/api` references** —
  it was built as a deliberately backend-free preview
- `/home/google/DonaldNorris/` is macOS RTFD notes; its four `donnie_*` folders are empty

So `BookingScenario` is **declared but refuses to run**, and every booking metric reports
`NOT AVAILABLE`. Inventing endpoints to benchmark would produce numbers labelled MEASURED
that describe code written only to be measured. When the booking application exists,
filling in `BookingScenario.run()` is the only change — the harness, samplers, report
schema and UI are already shaped for it.

## What it measures today

| layer | how |
|---|---|
| APPLICATION | real sessions over `/api/status` → AI step → `/api/ravencalc` → `/api/status` |
| PLAYER | generic `Player` interface — `NullPlayer` (AI off) / `SymonChatPlayer` (AI on) |
| GPU | continuous timestamped `nvidia-smi` sampler — min/avg/max VRAM, util, power, temp, compute PIDs |
| SYSTEM | `/proc` — CPU, loadavg, RAM, swap |

`/api/ravencalc` is documented in `api.py` as *"Exact symbolic mathematics. No GPU, no
lock, no queue"* — a genuinely deterministic server-side transaction, unaffected by AI
mode. That is what makes it a valid control for the AI ON/OFF differential.

## AI OFF is a real bypass, not a hidden button

`NullPlayer` issues **no inference request at all**, so no GPU worker is ever asked to
exist. This is verifiable from outside: the sampler shows 0 compute apps and VRAM flat at
baseline. AI ON spawns the engine and the sampler sees it. Those two observations are the
routing proofs.

## Honesty rules baked into the code

- Empty sample sets return `NOT AVAILABLE`, never `0` — see `test_percentiles_report_not_available_rather_than_zero`.
- Percentiles use nearest-rank, so every reported p50/p95/p99 is a value some session
  actually experienced, not an interpolation nobody measured.
- The sampler is a **series**, not a snapshot. A single `nvidia-smi` reading is never
  called a peak.
- **No SLA thresholds are invented.** `thresholds` ships empty, `DEGRADED` cannot be
  assigned by guesswork, and `UPGRADE REQUIRED` reads `NOT YET DETERMINED` unless there
  is an objective hard failure.
- The lab imports no torch/transformers/diffusers/vllm — it measures a player over the
  wire, it does not host one. Enforced by `test_no_inference_library_is_imported_by_the_lab`.
- Business View says **SyMon AI**. Implementation identifiers appear only in the
  Engineering View, for reproducibility.

## Isolation

Every run gets `BENCH-YYYYMMDD-NNNN`. `clear_run_data()` refuses anything that is not a
well-formed benchmark id and deletes exactly one run's artefacts — there is deliberately
no "clear all". The scenarios that exist today create no persistent server-side records,
and the cleanup block says so rather than reporting a deletion that never happened.

## Usage

```bash
python3 cli.py run --users 2 --ai off      # AI DISABLED
python3 cli.py run --users 2 --ai on       # AI ENABLED (SyMon AI)
python3 cli.py list
python3 cli.py clear BENCH-20260824-0001
python3 -m pytest tests/ -q
```

`--users > 2` is **refused** in slice 1. `FIND SERVER LIMIT` is not implemented and its
button is disabled — the destructive ramp needs separate approval.

Open `ui/capacity-lab.html` and drag a report JSON onto it, or pass `?report=<url>`.

## Layout

| path | role |
|---|---|
| `capacity_lab/core.py` | run ids, isolation, continuous sampler, statistics, host identity |
| `capacity_lab/players.py` | generic PLAYER interface — AR/.syar ready |
| `capacity_lab/scenario.py` | APPLICATION sessions; `BookingScenario` declared, unavailable |
| `capacity_lab/harness.py` | concurrency barrier, classification, JSON report, scoped cleanup |
| `cli.py` | run / list / clear |
| `ui/capacity-lab.html` | Business View + Engineering View |
| `tests/` | 22 tests: identity, isolation, cleanup scoping, classification, telemetry honesty |

Reports: `/home/google/experiments/capacity-lab/reports/BENCH-*.json`
