# Current host inventory

# OBSERVATION ONLY — NOT A PERFORMANCE BASELINE

Read 2026-08-24 by query, not by benchmark. **No CUDA sample was run, no kernel
was launched, no model was loaded, and no GPU work was submitted.** Every value
below came from `uname`, `nvidia-smi --query-*`, `nvcc --version`, `lscpu`,
`free` or a directory listing.

This file exists so P1 has something to compare against. It is **not** the P1
baseline — P1 produces that by measuring.

## System

| Field | Value |
|---|---|
| kernel | `6.12.101+deb13-amd64` |
| arch | `x86_64` |
| OS | GNU/Linux (Debian 13) |

## GPU

| Field | Value |
|---|---|
| name | **NVIDIA GeForce RTX 5070 Ti** |
| UUID | `GPU-15e0078a-cb3a-50d1-a40b-94e4d538fc78` |
| VBIOS | `98.03.58.00.23` |
| driver | **610.57.04** |
| compute capability | **12.0** (`sm_120`) |
| VRAM total | **16,303 MiB** |
| PCI bus id | `00000000:01:00.0` |
| compute applications running | **none** |

## PCIe link — read this before comparing anything

| Field | Value |
|---|---|
| link gen, current | **1** |
| link gen, max | **3** |
| link width, current | **8** |
| link width, max | 16 |

**`gen.current = 1` is idle power management, not a fault.** The link downshifts
when there is no traffic and negotiates up under load. The comparable figure
against the historical record is **`gen.max = 3` and `width.current = 8`** —
i.e. **Gen 3 ×8**, which matches the historical dossier exactly.

Anyone reading `gen.current` at idle and concluding "the slot has regressed to
Gen 1" would be wrong, and would then go looking for a hardware fault that does
not exist. P1 must sample link state **during** transfer, not before it.

## CUDA toolchain

| Field | Value |
|---|---|
| `nvcc` | `/usr/local/cuda/bin/nvcc` |
| release | **13.3**, V13.3.73 |
| build | `cuda_13.3.r13.3/compiler.38244171_0` |
| toolkit paths | `/usr/local/cuda`, `/usr/local/cuda-13`, `/usr/local/cuda-13.3` |

## Host CPU / RAM

| Field | Value |
|---|---|
| CPU | **Intel Core i9-10900KF @ 3.70 GHz** |
| cores / threads | 10 cores, 2 threads per core, **20 logical** |
| RAM total | **94 GiB** |
| RAM available at read time | 84 GiB |

The 20 logical CPUs matter for §3 load-generator materiality: a harness consuming
"7.4% CPU" means 7.4% of *one* core, which is 0.37% of this host. Those are very
different numbers and conflating them voids a server-limit claim.

## Comparison against the historical record

**This is the single most important table in P0 for planning P1.**

| Field | Historical (Grade A) | Current | Match |
|---|---|---|---|
| GPU | RTX 5070 Ti | RTX 5070 Ti | ✅ |
| compute capability | 12.0 / `sm_120` | 12.0 / `sm_120` | ✅ |
| driver | 610.57.04 | 610.57.04 | ✅ |
| CUDA runtime/toolkit | 13.3 | 13.3 (V13.3.73) | ✅ |
| VRAM | 16,303 MiB | 16,303 MiB | ✅ |
| PCIe | Gen 3 ×8 | Gen 3 max, ×8 current | ✅ |

**No relevant drift was observed in the enumerated GPU/driver/CUDA identity used
for this comparison. This does not establish that every host variable is
identical to the historical run.**

Corrected 2026-08-24: an earlier draft said "the host has not drifted", which
claims more than six rows can support. What is established is that *these six
fields* match. What is **not** established, and is not knowable from the
historical record, includes: kernel version at the historical run (never
recorded), CPU governor and clock state, thermal state, GPU power limit and
application clocks, persistence mode, what else was resident on the card, and
background load on the host. Any of those can move a bandwidth figure without
any of the six fields above changing.

That is still a strong result for P1: with the GPU, compute capability, driver,
CUDA and PCIe width all matching, a current run is comparable to the Grade-A
`alignedTypes` 341.53 GB/s and PCIe 6.94 / 7.20 GB/s figures **without a
GPU/driver/CUDA version confound**. Other confounds remain open, and the
uncontrolled variables listed above are the reason P1 records telemetry per run
rather than a single number.

It also means **there is no evidence-based reason to change the driver or CUDA**:
the versions in use today are the versions the historical figures were taken on,
so there is no delta to blame and nothing to roll back to.

## Python environments present

| Path | Contents |
|---|---|
| `/home/google/.venvs/vllm` | **vLLM 0.25.1**, Python 3.12.13, torch 2.11.0+cu130 |
| `/home/google/.venvs/symoneural` | production venv |
| `/home/google/.venvs/symoneural-hybrid` | hybrid/native experiment venv |
| `/home/google/.venvs/coreml` | unrelated |

## Engine binaries and source trees present

| Item | State |
|---|---|
| `Symoneural/engines/symoneural-llm` (llama.cpp fork) | **BUILT** — `libsymoneural_llm.so.0.1.0`, 2026-08-20 |
| `Symoneural/engines/symoneural-diffuse` (sd.cpp fork) | **BUILT** — `symoneural-diffuse`, 124 MB, 2026-08-20 |
| `.venvs/vllm` | **INSTALLED** — importable, sees the GPU |
| `/home/google/TensorRT-LLM` | **SOURCE PRESENT** — not built, not evaluated |
| `contrib/` (upstream llama.cpp / sd.cpp / cuda-samples) | **ABSENT** — the whole tree is gone |
| CUDA Samples source or binaries | **ABSENT** anywhere on the box |
| `llama-server` / `llama-cli` / `llama-bench` | **ABSENT** — no upstream binaries |
| `sd-cli` / `sd-server` | **ABSENT** — only the renamed fork binary exists |
| `deviceQuery` / `bandwidthTest` | **ABSENT** |

**The two SyMoNeuRaL-named binaries are renamed forks, not upstream builds.**
They are usable, but a result from them is not a result from upstream
`llama.cpp` or `stable-diffusion.cpp` unless the fork's merge-base is
established first — see the identity sections in the engine manifests.

## Models on disk

34 weight files under `Symoneural/backend/models/`, including the
`symoneural-image-*` FLUX component set and several large `.safetensors`. The
**27B GGUF** named in the best-evidenced llama.cpp result was not located during
this pass; its presence should be confirmed before P2 attempts that comparison.

## What was deliberately not done

No benchmark. No kernel launch. No model load. No install, clone, build or
download. No service, driver, CUDA, kernel, systemd or Caddy change. Production
and the frozen research repository were read only.
