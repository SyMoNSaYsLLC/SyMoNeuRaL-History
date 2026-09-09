# Engine and tool candidate register

Every candidate under consideration, and nothing about how they are expected to
place. **No engine candidate has been benchmarked or ranked** — every row in
LLM SERVERS, RTX / IMAGE and OPTIMIZATION / KERNEL still reads
`NOT YET BENCHMARKED IN THIS REPOSITORY`. See the note at the bottom for why.

The only rows carrying a result are **instruments** in RAW / DIAGNOSTIC — CUDA
Samples and `p1_cuda_pcie` from P1, and NVBandwidth from P1.6. Those measure the
hardware; they do not compete with anything.

Updated 2026-08-24 (through **P1.6**) with the qualified NVIDIA toolchain and the
NVBandwidth forward PCIe baseline. Columns: **Local** = present on this host ·
**Src** = source acquired under ignored `sources/`.

---

## RAW / DIAGNOSTIC

| Candidate | Local | Src | Status |
|---|---|---|---|
| **CUDA Samples** | ✅ built v13.3 | ✅ `v13.3` @ `b7c5481c` | **BENCHMARKED IN P1** |
| **NVBandwidth** | ✅ built v0.10.0 | ✅ `v0.10.0` @ `82fc4e8c` | **BENCHMARKED IN P1.6** |
| **NVBench** | ❌ absent | ✅ main @ `66212f1d` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| `p1_cuda_pcie` (ours) | ✅ built | authored here | **BENCHMARKED IN P1** — current PCIe characterisation |

**These are instruments, not contenders.** CUDA Samples is the hardware control.
NVBandwidth is an NVIDIA-authored **PCIe bandwidth reference**, not an AI
inference engine, and it competes with nothing in the LLM SERVERS or RTX / IMAGE
sections below. NVBench has **no stable release tag** — only `python-*` binding
releases — so pinning a main SHA is the only option available.

### NVBandwidth — P1.6 result

**NVIDIA NVBandwidth v0.10.0**, commit
`82fc4e8c6afa0babb8687793678f615b3b8d793e`, pristine Release build for `sm_120`
(source `dirty=0` before and after; no patch applied).

| Testcase | Mean | % of Gen 3 ×8 ceiling |
|---|---|---|
| `host_to_device_memcpy_ce` | **6.9320 GB/s** | **88.0 %** |
| `device_to_host_memcpy_ce` | **7.2100 GB/s** | **91.5 %** |

**Verdict: PASS — link healthy at negotiated Gen 3 ×8.**

**P1.6 independently reconfirms P1's Gen 3 ×8 under-load observation.** The
**×8-versus-reported-×16-maximum question remains unresolved** and is outside
P1.6 — `width.max` reads 16 while the link negotiates 8, and nothing measured
here establishes whether that is a slot, riser, BIOS or board limit.

Comparisons against the historical CuPy figures and against P1's own CUDA-runtime
test remain **DIRECTIONAL ONLY**: three separate implementations with
unproven-equivalent timing and allocation semantics, agreeing closely but not
promoted to EXACT on that basis.

Full detail in `docs/P1.6-NVBANDWIDTH-REPORT.md` and
`hardware/P1.6-NVBANDWIDTH-BASELINE.md`.

## PROFILING

| Candidate | Local | Status |
|---|---|---|
| **Nsight Systems** | ✅ **2026.1.3.425** at `/usr/local/cuda-13.3/bin/nsys` | `NOT YET USED IN THIS REPOSITORY` |
| **Nsight Compute** | ✅ **2026.2.1.0** at `/usr/local/cuda-13.3/bin/ncu` | `NOT YET USED IN THIS REPOSITORY` |

Both arrived bundled with the CUDA Toolkit (`cuda-nsight-systems-13-3`,
`cuda-nsight-compute-13-3`) — **no separate download or portal access required.**

- **Nsight Systems** — whole-system CPU/runtime/CUDA scheduling timeline.
- **Nsight Compute** — kernel-level throughput, occupancy, memory, tensor-core
  and stall analysis.

**Finalists are profiled after performance ranking**, not before. Profiling an
engine that loses on throughput spends the expensive tool on a rejected
candidate.

## OPTIMIZATION / KERNEL

| Candidate | Local | Src | Status |
|---|---|---|---|
| **Model Optimizer** | ❌ not installed | ✅ `0.46.0` @ `43fd41a5` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **CUTLASS / CuTe** | ❌ not installed | ✅ `v4.7.0` @ `dcf215af` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **TensorRT** | ❌ **SDK absent** (`libnvinfer` and `trtexec` both absent) | ✅ `v11.1` @ `82d1dca8` + 3 submodules | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| cuDNN | ✅ **9.19.0.56** (pip wheel) | — | supporting library |
| NCCL | ✅ 2.28.9 (pip wheel) | — | supporting library; single-GPU host |
| Triton (kernel language) | ✅ 3.6.0 | — | **not** NVIDIA Triton Inference Server |

**TensorRT version note:** `v11.1` is checked out because NVIDIA documentation
establishes **11.1 GA with CUDA 13.3** as the default path. **`v11.2` exists
upstream** (`1dade062`, 2026-08-04) and is newer — recorded, **not selected**.

## LLM SERVERS

| Candidate | Local | Src | Status |
|---|---|---|---|
| **vLLM** | ✅ **0.25.1** installed-not-serving | ✅ `v0.27.1` @ `6e448d0e` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **SGLang** | ❌ not installed | ✅ `v0.5.18` @ `71de97b2` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **TensorRT-LLM** | ❌ not installed | ✅ `v1.2.1` @ `376f7e1b` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **llama.cpp** | ❌ upstream absent (fork built in production repo) | ✅ master `f280b269` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **NVIDIA NIM (LLM)** | ❌ **no entitlement established** | container-only | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **SyMoNeuRaL native reference** | frozen at `44863110` | — | **Historical challenger only** |

**llama.cpp:** the historical build **`4df29be` exists upstream** (2026-08-16), so
P0's Grade-A 27B baseline is genuinely reproducible.

**NIM** requires NGC authentication, which is **not configured**, and its licence
is separate from every OSS row here. Reference candidate only.

**Native reference** carries no standing — `PERFORMANCE-POLICY.md` §1 gives
internally-written code no preference and §4 states the tie rule is not a
protection rule for it.

## RTX / IMAGE

| Candidate | Local | Src | Status |
|---|---|---|---|
| **stable-diffusion.cpp** | ❌ upstream absent (fork built in production repo) | ✅ master `97d29908` + 4 submodules | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **Diffusers** | ✅ **0.40.0** in `symoneural-hybrid` | — | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **TensorRT-RTX** | ❌ **SDK NOT PRESENT** | ✅ OSS samples `v1.6.1.120` @ `058c78af` | `NOT YET BENCHMARKED IN THIS REPOSITORY` |
| **NVIDIA Visual GenAI NIM** | ❌ no entitlement established | container-only | `NOT YET BENCHMARKED IN THIS REPOSITORY` |

**stable-diffusion.cpp:** historical `de298c2` **exists upstream** (2026-08-12).

> **TensorRT-RTX is NOT available.** The GitHub tree contains `demo/` and
> `samples/` only — verified by listing it. **The complete SDK requires a
> separate NVIDIA download and is not present.** Cloning the OSS repo does not
> make TensorRT-RTX installed, and this row must not be read as though it did.

---

## The three-way distinction that must not be collapsed

Recorded because conflating these produces wrong architectural conclusions, and
one of the three descriptions is now historically obsolete.

| | What it is |
|---|---|
| **TensorRT** | A general high-performance **inference SDK and runtime**. Builds optimised engines from ONNX or a network definition. Not LLM-specific. |
| **TensorRT-LLM** | NVIDIA's current **generative/LLM serving framework** — scheduler, KV cache, batching, decoding, serving — running on a **PyTorch execution backend**. |
| **TensorRT-RTX** | An **RTX-focused general inference SDK/runtime** with JIT optimisation for RTX GPUs. Distinct product, distinct SDK, distinct download. |

**Do not describe current TensorRT-LLM as "TensorRT + an LLM serving wrapper"
without historical qualification.** That was true of earlier releases and is not
true now: **Release 1.2 removed the TensorRT execution backend**, and current
TensorRT-LLM uses the PyTorch execution backend.

Verified in the acquired v1.2.1 tree rather than assumed. `docs/source/release-notes.md`
records, under Release 1.2 → Documentation:

> *"Refactored the doc structure to focus on the PyTorch workflow."*
> *"Removed legacy documentation related to the TensorRT workflow."*

and elsewhere *"Remove support for llmapi + TRT backend in Triton"*. The tree
still carries `tensorrt_llm/_torch/` (present) alongside a legacy `builder.py`.
The same release notes record **SM120/SM121/SM103 paths** — this GPU's
architecture is explicitly enabled.

The practical consequence: **TensorRT-LLM does not require the TensorRT SDK to be
installed**, so the absent TensorRT runtime is not a blocker for evaluating it.
Those are two separate products with two separate acquisition problems.

## Cross-cutting techniques — not candidates

FlashAttention and other attention backends · `torch.compile` · CUDA Graphs ·
speculative decoding · quantisation format and precision · fused/optimised
kernels · Triton kernels · batching and KV-cache policy.

These are **tuning dimensions within** a candidate and belong in that candidate's
`PERFORMANCE-POLICY.md` §2 configuration record. Several move throughput further
than the choice of engine, which is exactly why §2 requires each to be named in
every result.

## Why every ENGINE status line is identical

A register that pre-ranks its candidates has decided the bake-off before it runs.
Once a prediction is written down it becomes the thing later measurements get
compared against, and disagreeing results start to look like mistakes. So this
file records **what is under consideration**, never what is expected to win.

**The instruments are the exception, and deliberately so.** CUDA Samples,
`p1_cuda_pcie` and NVBandwidth carry results because measuring the hardware is
their whole purpose — they are the control, not the contest. Every actual engine
candidate still reads `NOT YET BENCHMARKED IN THIS REPOSITORY`.

A row's status changes only when a measurement exists that satisfies
`PERFORMANCE-POLICY.md` §6 — commit, engine version, model revision, config,
hardware and environment snapshot, raw report path and its SHA256.

**Nothing in this update selects anything.** Newer tags exist for several
components (`TensorRT v11.2`, `vLLM v0.28.0rc2`, `ModelOpt 0.47.0dev`,
`TensorRT-LLM v1.3.0rc24`) and none was chosen — being newer is not a selection
criterion.
