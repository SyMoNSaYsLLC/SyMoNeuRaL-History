# SyMoNeuRaL Performance

**Purpose.** A performance-first laboratory for selecting and tuning the
production AI runtime stack used by SyMoNeuRaL-hosted applications.

**This is NOT the custom-runtime research repository.**

## The three repositories, and why they are separate

| | Path | Holds |
|---|---|---|
| Production application | `/home/google/Symoneural` | the site, the API, the shipped surfaces |
| Frozen custom research | `/home/google/SyMoNeuRaL-Projects/Symoneural-Custom` | the native runtime line, frozen |
| **Performance lab** | `/home/google/SyMoNeuRaL-Projects/Symoneural-Performance` | **this repository** |

Frozen custom research is pinned at:

```
branch  research/custom-runtime-freeze-20260824
HEAD    44863110
```

It is preserved as research and is **not** a launch requirement. Nothing in this
repository depends on it, and nothing here is obliged to beat it, use it, or
justify replacing it.

## Core rule

> **Fastest reliable compliant implementation wins.**

**No engine has privileged status.** Specifically and deliberately, this project
has *no* preference for SyMoNeuRaL-written inference code. A candidate is judged
on measured throughput, measured latency, measured reliability and licence
fitness for hosted service — never on who wrote it.

The full rules, including how a fair comparison is defined and what a valid
result must carry, are in **`PERFORMANCE-POLICY.md`**. Read it before running a
benchmark, because a measurement taken outside those rules is not admissible
here and re-running it costs more than reading first.

## What this repository contains, and what it never will

It contains configuration, method, provenance and conclusions.

It does **not** contain engine source trees, model weights, or raw benchmark
output. Upstream projects are checked out into ignored `sources/`; weights live
in ignored `models/`; raw run output lands in ignored `results/raw/`. What gets
tracked is the exact commit, the exact flags and the accepted summary — the
parts from which a run can be recreated and a claim can be checked.

`.gitignore` states the reasoning for each of those exclusions rather than
merely listing them.

## Status

**Nothing has been benchmarked in this repository yet.** No engine has been
installed, cloned, built, loaded or selected. `engines/CANDIDATES.md` lists the
contenders and marks every one of them `NOT YET BENCHMARKED IN THIS REPOSITORY`,
which is the honest state and is meant to stay honest — a candidate's row moves
only when a measurement exists to move it.

The sequence of work is in **`docs/PERFORMANCE-ROADMAP.md`**. The constraint that
matters most while that work is in progress: **the production stack does not
change during P0–P4.** Selection happens at P6, after the measurements exist.

## Layout

```
docs/         architecture, decisions, benchmark reports, the roadmap
configs/      tracked runtime and build configurations
hardware/     raw-host validation and the CUDA Samples baseline
benchmarks/   benchmark definitions and comparison methodology
harness/      engine-neutral workload generator and telemetry
scripts/      reproducible setup / build / run / measure scripts
manifests/    environment, engine, model and benchmark provenance
licenses/     hosted-service dependency and licence ledger
engines/      per-candidate adapter and configuration notes
results/      accepted summaries (raw output is ignored)
```

Each of those directories carries its own `README.md` stating what belongs in it
and what does not.

## Boundaries

Local git only. **No remote is configured, and none should be.** This repository
does not deploy, does not change services, and does not modify either of the
other two repositories.
