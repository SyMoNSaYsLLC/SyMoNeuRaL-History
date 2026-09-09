# Historical: llama.cpp

**Recovered 2026-08-24. Read-only forensic pass. Nothing was built, loaded or run.**

The engine with the strongest *configuration* evidence — build flags survive as a
machine-generated CMake cache — and a **split** results picture that matters
more than the headline numbers.

## IDENTITY

| Field | Value | Grade |
|---|---|---|
| project | llama.cpp | **A** |
| upstream repository | **`github.com/ggml-org/llama.cpp`** | **B** |
| historical build (`contrib/`) | **`4df29be`** | **B** |
| fork present today | `engines/symoneural-llm` — a **renamed fork**, tracked inside the production repo | **A** |
| fork's own upstream commit | **NOT RECOVERABLE** — no `origin` remote, no independent history; `git describe` returns the *SyMoNeuRaL* tag | **E** |
| original `contrib/llama.cpp` tree | **ABSENT** — `docs/ops/MEASUREMENTS.md:214` confirms `api.py` probes a path *"not on"* disk | **A** |

**The identity gap is the important finding.** Two different things existed:

1. `contrib/llama.cpp @ 4df29be` — upstream, gitignored, **gone**. This is what
   produced the historical benchmark numbers.
2. `engines/symoneural-llm` — a fork renamed into SyMoNeuRaL identity, committed
   *inside* the production repo, so its git history is the production history.
   Its upstream merge-base is not recoverable from git metadata on this box.

A benchmark citing "llama.cpp `4df29be`" therefore cannot be reproduced from the
fork without first establishing what the fork descends from.

## BUILD

From `engines/symoneural-llm/build/CMakeCache.txt` — machine-generated, Grade **B**:

| Field | Value | Grade |
|---|---|---|
| `CMAKE_BUILD_TYPE` | `Release` | **B** |
| `CMAKE_CUDA_ARCHITECTURES` | **`120`** | **B** |
| `GGML_CUDA` | **`ON`** | **B** |
| `CMAKE_CUDA_COMPILER` | `/usr/local/cuda/bin/nvcc` | **B** |
| `CMAKE_CXX_COMPILER` | `/usr/bin/c++` | **B** |
| build date (binary mtime) | 2026-08-20 15:56 | **A** |
| `.gitmodules` | none — `--recursive` not required | **C** |

`.claude/HANDOVER.md:1834` records that a documented rebuild command **omitted
`-DGGML_CUDA=ON`** and that the omission *"would have produced CPU-only builds
that compile, link and run, failing silently."* That is the single most valuable
build fact in this recovery: the flag is not optional and its absence is
invisible until the numbers are wrong.

## HOST

Same box throughout; see `cuda-samples.md` for the fully-evidenced host block.
RTX 5070 Ti · `sm_120` · driver 610.57.04 · CUDA 13.3 · PCIe Gen3 ×8. Grade **A**.

## MODEL / WORKLOAD — two distinct workloads, not one

### (a) Qwen3.6-27B UD-Q2_K_XL — the best-evidenced llama.cpp result

| Field | Value | Grade |
|---|---|---|
| weights | `symon-1.0-27b-q2_k_xl.gguf` | **A** |
| exact size on disk | **11,849,779,424 bytes** (11.03 GiB) | **A** |
| parameters | 26.90 B | **A** |
| quantisation | UD-Q2_K_XL | **A** |
| offload | `-ngl 99` — fully GPU-resident, no CPU offload | **A** |
| architecture | `general.architecture = qwen35` | **A** |
| revision / provenance of the GGUF | not recorded | **E** |

### (b) 7B Q4 — the figures named in the P0 brief

| Field | Value | Grade |
|---|---|---|
| model | "7B Q4" — **no filename, no exact size, no revision** | **C** |
| quantisation | Q4 (variant unspecified) | **C** |
| LoRA adapter | referenced as "with adapter" for the API path | **C** |
| draft model (speculative) | referenced, **not identified** | **C** |
| context size | not recorded | **E** |
| batch / ubatch | not recorded | **E** |
| flash attention | not recorded | **E** |
| threads | not recorded | **E** |

## RUNTIME

| Field | Value | Grade |
|---|---|---|
| bench command (27B) | **`llama-bench -p 512 -n 128`** | **A** |
| launch command (7B) | **not recovered** | **E** |
| context ceilings measured | each row a real `llama-server` load | **A** |
| KV cache type | `f16` and `q8_0` both measured | **A** |
| KV slope | 63.5 MiB/1K at f16 · 38.1 MiB/1K at q8_0 | **A** |
| server ports | not recorded for llama.cpp | **E** |
| environment variables | not recorded | **E** |

No credential material found in any llama.cpp evidence.

## RESULTS

### Grade A — Qwen3.6-27B, `llama-bench`, build `4df29be`

| Measurement | Value | Unit | Grade |
|---|---|---|---|
| prompt (pp512) | **1537.77 ± 94.82** | tok/s | **A** |
| generation (tg128) | **56.90 ± 0.22** | tok/s | **A** |
| peak VRAM during bench | 11,916 of 16,303 | MiB | **A** |
| 8K context / f16 | 12,354 | MiB | **A** |
| 16K / f16 | 12,874 | MiB | **A** |
| 32K / f16 | 13,914 | MiB | **A** |
| 32K / q8_0 | 13,040 | MiB | **A** |
| 64K / q8_0 | 14,288 | MiB | **A** |
| 128K / q8_0 | **FAILS** — `cudaMalloc failed: out of memory` | — | **A** |

**These carry ± error bars, which means repeats were run.** That makes them the
only historical throughput figures in this entire recovery with variance
attached. Concurrency: **1** (`llama-bench` is single-stream). Path: **bare
benchmark**.

### Grade C — the 7B Q4 figures from the brief

Every one of these appears **only** in `docs/archive/PROJECT-STATE.md:74-78` and
`docs/archive/HANDOVER-2026-08-16-1910.md`, as a summary table. No raw
`llama-bench` output, no `llama_perf` block, no command line.

| Claim | Value | Grade |
|---|---|---|
| 7B Q4 bare decode | 149.6 tok/s | **C** |
| via API with adapter | ~104–114 tok/s | **C** |
| speculative, draft depth 2 | 157.4 tok/s, 43.8% accept | **C** |
| speculative, library default | 139.1 tok/s (net loss) | **C** |
| speculative, depth 5 | 121.4 tok/s | **C** |
| q8_0 KV cache | 142.7 tok/s | **C** |

**`docs/archive/README.md` opens with: *"Nothing in this directory is current …
If a file is in here, do not act on it."*** The table's own header says *"all
reproduced on this box"*, which is a claim about the past, not a machine result.
These are recorded as **C** — documented historical claim — and must not be
promoted.

## MISSING

- upstream merge-base of `engines/symoneural-llm` — **E**, blocks exact reproduction
- 7B model filename, exact bytes, revision — **E**
- draft model identity for the speculative results — **E**
- context, batch, ubatch, flash-attention, thread settings for every 7B run — **E**
- launch command for the 7B bare and API paths — **E**
- run counts / variance for all 7B figures — **E**
- GGUF provenance for the 27B — **E**

## REPRODUCTION STATUS

**PARTIALLY RECONSTRUCTABLE.**

Split by workload, because one blanket verdict would be wrong:

- **27B `llama-bench`** — *mostly* reconstructable. Command, model, exact bytes,
  offload and build flags all survive; only the fork's upstream base is unknown.
- **7B speculative / API suite** — **HISTORICAL RESULT ONLY.** The model is not
  identified, the draft model is not identified, no runtime flags survive, and
  the numbers live in a directory whose README says not to act on it.

The 7B figures are the ones quoted most often in project prose and the ones with
the weakest evidence. Re-measuring them is P2 work, not a recovery task.
