# P0 — Historical performance table

Recovered 2026-08-24. Every row is graded, and **the grade is part of the
result**.

> **These rows are not comparable to each other and are deliberately not ranked.**
> GPU memory bandwidth (GB/s), token throughput (tok/s) and image render time
> (seconds) answer different questions about different hardware paths.
> Normalising them into one league table would manufacture a ranking that no
> measurement supports.

**Grades:** **A** direct measured (tool output) · **B** direct configuration
(machine-generated file/metadata) · **C** documented historical claim · **D**
inference · **E** not available.

---

## CUDA Samples — raw hardware

| Workload | Measured result | Grade | Source | Repro | Notes |
|---|---|---|---|---|---|
| `alignedTypes` RGBA32 copy | **341.533883 GB/s** one-way | **A** | `docs/01-hardware-dossier.md:355` | HISTORICAL RESULT ONLY | Verbatim transcript, all types + `TEST OK` + `0 Failures`. 50 MB working set |
| `reduction` sample | **752.30 GB/s** | **C** | `2_CoreConcepts.md:2661` | HISTORICAL RESULT ONLY | **Regraded B→C 2026-08-24.** Prose only. **PYTHON sample** (`python reduction.py`) |
| `reductionMultiBlockCG` | **708.92 GB/s** | **C** | `2_CoreConcepts.md:2826` | HISTORICAL RESULT ONLY | **Regraded B→C.** Prose only. **PYTHON sample**, needed `--cuda-include-dir` for libcu++ |
| PCIe H→D pinned | **6.94 GB/s** | **A** | `01-hardware-dossier.md:304` | HISTORICAL RESULT ONLY | 88% of Gen 3 ×8 peak. Verbatim CuPy table |
| PCIe D→H pinned | **7.20 GB/s** | **A** | `:304` | HISTORICAL RESULT ONLY | 91% of peak |
| CuPy D2D, 512 MB | 380.71 GB/s one-way → **~761 GB/s** DRAM | **A** | `:304` | HISTORICAL RESULT ONLY | A copy reads *and* writes; DRAM sees 2× |
| Working bandwidth figure | **~750 GB/s** (84% of 896.1 theoretical) | **C** | `:101` | — | Rests on the two Grade-C figures above, so a reference claim, not a proven baseline |

**Repro is HISTORICAL RESULT ONLY for every row:** the samples tree is absent,
its version unknown, its build flags unrecorded.

**Regrade note, 2026-08-24.** The two `reduction` figures were first recorded as
**B**. That misapplied the scale: **B is for direct configuration evidence, and a
benchmark result can never be B for being written in a document.** Both are prose
(`> **Result** — PASSED … 752.30 GB/s`), no verbatim stdout survives anywhere, so
both are **C**. Re-inspection also established they were the **Python** sample
variants — `python reduction.py` and `reductionMultiBlockCG.py` under a
`venv-extras` environment — which makes a C++ v13.3 build a *different program*.
Any P1 comparison against them is **DIRECTIONAL at best**.

**The L2 trap:** with 48 MB of L2, any bandwidth test under ~100 MB measures
cache, not DRAM. P1 must size above that or produce a false regression.

---

## llama.cpp — token throughput

### Grade A — Qwen3.6-27B, `llama-bench -p 512 -n 128`, build `4df29be`

| Workload | Measured result | Grade | Source | Repro | Notes |
|---|---|---|---|---|---|
| prompt, pp512 | **1537.77 ± 94.82 tok/s** | **A** | `.claude/HANDOVER.md:1257`, `docs/symoneural-manual.md:214` | MOSTLY RECONSTRUCTABLE | **± error bars ⇒ repeats were run.** Concurrency 1 |
| generation, tg128 | **56.90 ± 0.22 tok/s** | **A** | same | MOSTLY RECONSTRUCTABLE | Model = 11,849,779,424 B exactly, `-ngl 99` |
| peak VRAM at bench | 11,916 / 16,303 MiB | **A** | same | — | At bench's *short* context — not a session figure |
| 64K ctx @ q8_0 KV | 14,288 MiB, loads | **A** | `HANDOVER.md:1265` | — | Largest context that loads |
| 128K ctx @ q8_0 KV | **FAILS** — `cudaMalloc failed: out of memory` | **A** | same | — | The measured ceiling |
| KV slope | 63.5 MiB/1K (f16) · 38.1 MiB/1K (q8_0) | **A** | same | — | |

**The only historical throughput figures in this entire recovery with variance
attached.** Also carries a self-correction worth keeping: the bandwidth-derived
prediction was **~11.5% optimistic** (752 GB/s ÷ 11.85 GB predicted 63.46 tok/s;
the card delivered 56.90).

### Grade C — the 7B Q4 suite

| Workload | Claimed result | Grade | Source | Repro | Notes |
|---|---|---|---|---|---|
| 7B Q4 bare decode | 149.6 tok/s | **C** | `docs/archive/PROJECT-STATE.md:74` | HISTORICAL RESULT ONLY | Model not identified |
| via API + LoRA | ~104–114 tok/s | **C** | `:74` | HISTORICAL RESULT ONLY | Adapter not identified |
| speculative, depth 2 | 157.4 tok/s, 43.8% accept | **C** | `:75` | HISTORICAL RESULT ONLY | Draft model not identified |
| speculative, library default | 139.1 tok/s (**net loss**) | **C** | `:76` | HISTORICAL RESULT ONLY | "default is a net loss here" |
| speculative, depth 5 | 121.4 tok/s | **C** | `:77` | HISTORICAL RESULT ONLY | |
| q8_0 KV cache | 142.7 tok/s | **C** | `:78` | HISTORICAL RESULT ONLY | "memory win, not a speed win" |

**All six exist only in `docs/archive/`, whose README opens:** *"Nothing in this
directory is current … If a file is in here, do not act on it."* Summary table,
no raw output, no command line, no model identity, no run counts. **Not
promotable.** These are the figures quoted most often in project prose and the
ones with the weakest evidence — the exact asymmetry P0 exists to expose.

---

## stable-diffusion.cpp — image render time

| Workload | Measured result | Grade | Source | Repro | Notes |
|---|---|---|---|---|---|
| FLUX 768², 4 steps | **9.3 – 11.1 s** per image | **C** | `docs/archive/PROJECT-STATE.md:79` | PARTIALLY RECONSTRUCTABLE | A *range* ⇒ >1 render, but no count or distribution |
| GPU drain to floor | ~1 s to 1.5 GB | **C** | `:81` | — | Clean handoff |
| OOM-free handoff | 3 / 3 cycles | **C** | `:81` | — | |

**Discrepancy recorded rather than smoothed:** the P0 brief's lead said
*"9.3–11.2 s"*; local evidence says **9.3–11.1 s**. The local figure is
authoritative. Build side is much stronger than the result side —
`master-820-de298c2`, `SD_CUDA=ON`, `CMAKE_CUDA_ARCHITECTURES=120`, `Release`,
`--recursive` required — all Grade **B**.

---

## vLLM — no numeric baseline exists

| Workload | Measured result | Grade | Source | Repro | Notes |
|---|---|---|---|---|---|
| throughput | **NOT AVAILABLE** | **E** | — | INSUFFICIENT EVIDENCE | |
| latency (any percentile) | **NOT AVAILABLE** | **E** | — | INSUFFICIENT EVIDENCE | |
| TTFT | **NOT AVAILABLE** | **E** | — | INSUFFICIENT EVIDENCE | |
| concurrency tested | **NOT AVAILABLE** | **E** | — | INSUFFICIENT EVIDENCE | |

> ### HISTORICAL VLLM EXECUTION CONFIRMED
> ### NUMERIC PERFORMANCE BASELINE NOT RECOVERED

What *is* evidenced:

| Field | Value | Grade |
|---|---|---|
| installed version | **vLLM 0.25.1** | **A** |
| torch | 2.11.0+cu130 | **A** |
| runtime state | **`installed-not-serving`** | **B** |
| API shape | OpenAI-compatible | **B** |
| port | **9001**, loopback | **B** |
| model id | **`symon`** | **B** |
| launch command | **NOT RECOVERED** | **E** |

Searched the production repo, the frozen research, `experiments/` and the venv.
**No vLLM benchmark output, report, CSV or logged figure exists at any grade.**
No number was invented to fill the gap.

---

## Diffusers / PyTorch, SGLang, TensorRT-LLM

| Engine | Historical evidence | Grade |
|---|---|---|
| Diffusers / PyTorch image path | **none found** | **E** |
| SGLang | **none found** | **E** |
| TensorRT-LLM | source tree at `/home/google/TensorRT-LLM`; **no build, no result** | **E** |

`docs/ops/RUNTIME-PROFILES.md:45` classifies TensorRT-LLM / Triton / CUDA-graphs
as *"future NVIDIA-optimized path, **after proof**"* — absent, future/audit only.

---

## Summary — what P0 actually established

| Engine | Historical speed | Exact commit | Build flags | Model | Repro confidence |
|---|---|---|---|---|---|
| **CUDA Samples** | `alignedTypes`+PCIe **PROVEN** (A); `reduction` **CLAIMED ONLY** (C) | UNKNOWN (E) | UNKNOWN (E) | n/a | **LOW** — result only |
| **llama.cpp 27B** | **PROVEN** (A, with ±) | `4df29be` (B) | **PROVEN** (B) | **PROVEN** (A) | **HIGH** |
| **llama.cpp 7B** | CLAIMED ONLY (C) | `4df29be` (B) | **PROVEN** (B) | UNKNOWN (E) | **LOW** |
| **stable-diffusion.cpp** | CLAIMED ONLY (C) | `master-820-de298c2` (B) | **PROVEN** (B) | PARTIAL (C/D) | **MEDIUM** |
| **vLLM** | **NOT AVAILABLE** (E) | n/a (wheel) | n/a | UNKNOWN (E) | **MEDIUM** as config, **NONE** as baseline |
