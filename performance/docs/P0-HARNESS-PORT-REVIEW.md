# P0.6 — Capacity Lab harness port review

**Read-only review. NOTHING WAS COPIED, and nothing in the frozen research was
modified.** Source read from
`/home/google/SyMoNeuRaL-Projects/Symoneural-Custom/capacity-lab` at
`44863110`.

The question this answers: *which parts of the existing harness are genuinely
engine-neutral instrumentation, and which are welded to the native runtime or to
the DispatchOS workload?* Copying the wrong half would quietly make this
repository a fork of the research line it was created to be independent of.

## Method

Measured coupling per file rather than judged it — counted references to native
runtime symbols (`native_player`, `chat_worker`, `NativeChat`, `hybrid`), to
DispatchOS workload vocabulary (`booking`, `dispatch`, `rider`, `driver`), and to
hardcoded absolute paths.

| File | Lines | native refs | dispatchos refs | abs paths | Class |
|---|---|---|---|---|---|
| `capacity_lab/players.py` | 126 | 0 | 0 | 0 | **A** |
| `capacity_lab/__init__.py` | 10 | 0 | 0 | 0 | **A** |
| `cli.py` | 66 | 0 | 0 | 0 | **A** |
| `capacity_lab/core.py` | 287 | 0 | 1 | **2** | **A** (with changes) |
| `capacity_lab/scenario.py` | 388 | 0 | **36** | 0 | **C** |
| `capacity_lab/lifecycle.py` | 153 | 0 | **13** | 0 | **C** |
| `capacity_lab/harness.py` | 459 | **20** | **13** | 1 | **C** (split required) |
| `capacity_lab/native_player.py` | 292 | **7** | 0 | **3** | **B** |
| `control_service.py` | 251 | 2 | **13** | 1 | **C** |
| `suite.py` | 555 | 3 | 3 | 1 | **D** |
| `slice3.py` | 1510 | 8 | **11** | 2 | **D** |

---

## A. ENGINE-NEUTRAL — PORT CANDIDATE

### `capacity_lab/core.py` — the highest-value port in the tree

| | |
|---|---|
| **Source** | `capacity-lab/capacity_lab/core.py` (287 lines) |
| **Members** | `Sampler` (class, ~150 lines) · `percentiles()` · `summarise()` · `host_identity()` · `new_run_id()` · `is_benchmark_id()` · `known_run_ids()` · `repo_commit()` |
| **Purpose** | GPU/host telemetry sampling, percentile maths, run identity, host snapshot |
| **Dependencies** | stdlib + `nvidia-smi` subprocess. **No torch, no engine client, no web framework.** |
| **Native assumptions** | **None** — zero native references |
| **Absolute-path assumptions** | 2, both fixable: `core.py:32` defaults `REPORT_DIR` to `/home/google/experiments/capacity-lab/reports` (already env-overridable via `CAPACITY_LAB_REPORTS`); `core.py:276` defaults `repo_commit(repo="/home/google/Symoneural")` |
| **Required changes** | Re-point both defaults at this repository (`results/raw/` and the Performance repo root). Keep the env override. Drop the one DispatchOS word. |
| **Provenance to preserve** | Origin repo, `research/custom-runtime-freeze-20260824`, commit `44863110`, original path. Cite in a module docstring. |

`Sampler` is the piece worth having: it already reports GPU utilisation, VRAM,
power, temperature, CPU and RAM as `{min,avg,max}` series, and it already
distinguishes per-sample series from capacity totals — a distinction that
`slice3.py`'s comments record as having crashed the code once when confused.
`PERFORMANCE-POLICY.md` §3 requires exactly this metric set.

### `capacity_lab/players.py` — the interface, not an implementation

| | |
|---|---|
| **Source** | `capacity-lab/capacity_lab/players.py` (126 lines) |
| **Members** | `PlayerResult` · `Player` (ABC) · `NullPlayer` · `SymonChatPlayer` · `build_player()` |
| **Purpose** | The abstraction every engine is driven through |
| **Dependencies** | stdlib + HTTP client |
| **Native assumptions** | **None** — 0 native refs, 0 dispatchos refs, 0 absolute paths |
| **Required changes** | `SymonChatPlayer` targets an OpenAI-compatible endpoint, so it already works for vLLM (`:9001`), SGLang and `llama-server`. Rename to something engine-neutral (`OpenAICompatPlayer`); add per-engine subclasses in P2. |
| **Provenance to preserve** | Same as above. |

**This is the single most reusable file in the tree.** `PERFORMANCE-POLICY.md`
requires every candidate to be driven through one common interface or the
comparison measures the harness; this file *is* that interface, and it is already
clean.

### `cli.py` and `capacity_lab/__init__.py`

Thin, zero-coupling. Port as structural scaffolding when the harness lands.

---

## B. NATIVE-RUNTIME-SPECIFIC — DO NOT PORT

### `capacity_lab/native_player.py` (292 lines)

Supervises the native chat worker: spawns it, tracks its PID, manages a FIFO
ticket queue, measures cold-start and per-process VRAM. Three hardcoded paths
into the native worktree and `/home/google/.venvs/vllm/bin/python`.

**Do not port.** It exists to drive one specific runtime that this project has no
preference for.

**One idea inside it is worth reimplementing rather than copying:** the queue
depth accounting at `native_player.py:180`, where `max_depth` is captured under
the same lock that performs the waiting→active transition, so depth means
*requests waiting behind the one in service* rather than "requests in the
system". `max_total_ai_in_system_observed` is likewise observed directly rather
than summed from two maxima taken at different instants. Those are correctness
properties any queue-aware harness needs, and getting them wrong produces a
depth figure no request ever experienced. **Reimplement the semantics; do not
inherit the native supervisor.**

---

## C. DISPATCHOS-WORKLOAD-SPECIFIC — OPTIONAL PORT

### `capacity_lab/scenario.py` (388 lines, 36 dispatchos refs)

Booking-session scenarios — the P5 application workload. **Not needed for
P2–P4.** Revisit at P5, and expect to rewrite rather than port: P5 needs a
workload shaped like DispatchOS, not this code's specific request sequence.

### `capacity_lab/lifecycle.py` (153 lines, 13 refs)

Synthetic-booking creation and cleanup. Its useful idea — **benchmark data that
fails to clean up is a hard failure, not a footnote** — is a policy this
repository should adopt, not a file it needs. The frozen research learned that
when an interrupted run left 32 synthetic bookings behind.

### `capacity_lab/harness.py` (459 lines) — **split, do not port whole**

The most tangled file: 20 native references *and* 13 DispatchOS references. It
contains genuinely neutral orchestration (level runs, load-generator materiality
accounting, report emission) welded to native supervision and booking workload.

**Recommendation:** treat as a design reference, not a port. Extract two ideas:

1. **Load-generator materiality**, expressed as a share of *total host capacity*
   rather than of one core. On this 20-thread box those differ by 20×, and the
   per-core reading fires falsely and voids a valid measurement.
2. **Requested vs achieved concurrency as separate recorded fields.**

### `control_service.py` (251 lines)

The service that was listening on **:8811** and had to be stopped before the old
worktree could be removed. DispatchOS-shaped. Not needed.

---

## D. HISTORICAL ONLY

### `slice3.py` (1510 lines) and `suite.py` (555 lines)

The Slice 3 driver and suite. Carry the nine integrity guards (cleanup
hard-failure, honest execution counts, GPU-ownership contracts, 5xx attribution,
timeout-vs-hard-limit, repeatability, `supports_capacity_claim`, queue-depth
semantics) — all mutation-tested at the freeze.

**Do not port.** They are welded to the native/DispatchOS pairing. But **read
them before writing the P4 saturation finder**: those nine guards are a list of
ways a capacity headline can be wrong, each learned from a real failure. The
guards are the asset; the code is not.

---

## Recommendation

**Port at P2, not now.** Three files: `core.py`, `players.py`, `cli.py` —
~480 lines, one reviewed commit, with provenance in each module docstring.

Everything else is either engine-specific (B), deferred to P5 (C), or a
design reference to read rather than copy (D).

**Nothing was copied during P0.** `manifests/ORIGIN.md` records why this is the
only acceptable route: an unattributed paste would make this repository a
derivative of the research line without saying so.
