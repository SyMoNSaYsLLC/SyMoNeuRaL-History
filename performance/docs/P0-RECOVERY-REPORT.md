# P0 — Historical recovery report

**2026-08-24. Read-only forensic pass.** No engine installed, cloned, built,
downloaded, loaded or benchmarked. No service, driver, CUDA, kernel, systemd or
Caddy change. Production and the frozen research repository were read only.

P0 had one job: **replace memory with evidence.** Below is what survived that
test and what did not.

---

## 1. What exact historical stack can we prove?

**The enumerated GPU/driver/CUDA identity, comprehensively — and no relevant
drift was observed in it.**

| | Historical (Grade A) | Current | |
|---|---|---|---|
| GPU | RTX 5070 Ti | RTX 5070 Ti | ✅ |
| compute capability | 12.0 / `sm_120` | 12.0 / `sm_120` | ✅ |
| driver | 610.57.04 | 610.57.04 | ✅ |
| CUDA | 13.3 | 13.3 (V13.3.73) | ✅ |
| VRAM | 16,303 MiB | 16,303 MiB | ✅ |
| PCIe | Gen 3 ×8 | Gen 3 max, ×8 | ✅ |

Every historical row comes from verbatim `deviceQuery` / `nvidia-smi` transcript.

**No relevant drift was observed in the enumerated GPU/driver/CUDA identity used
for this comparison. This does not establish that every host variable is
identical to the historical run** — kernel version, CPU governor, thermal state,
power limit, application clocks and concurrent host load were never recorded
historically and cannot be compared. The six fields above match; the *host* is
not thereby proven identical.

That is still the most useful single finding in P0, because it removes the
GPU/driver/CUDA *version* confound from P1. It does not remove every confound.

**Build configuration for both C++ engines, from machine-generated CMake caches:**

| Engine | Flags | Grade |
|---|---|---|
| llama.cpp fork | `CMAKE_CUDA_ARCHITECTURES=120`, **`GGML_CUDA=ON`**, `Release` | **B** |
| sd.cpp fork | `CMAKE_CUDA_ARCHITECTURES=120`, **`SD_CUDA=ON`**, `Release`, `--recursive` | **B** |

**Upstream identities:** llama.cpp `ggml-org/llama.cpp @ 4df29be`;
stable-diffusion.cpp `leejet/stable-diffusion.cpp master-820-de298c2`;
whisper.cpp `1fe009c`. All Grade **B**.

## 2. Which engine has the strongest historical evidence?

**llama.cpp**, but not for the results the project usually quotes.

The strongest single result in the whole recovery is the **Qwen3.6-27B**
`llama-bench` run: **1537.77 ± 94.82 tok/s** prompt, **56.90 ± 0.22 tok/s**
generation, build `4df29be`, model `symon-1.0-27b-q2_k_xl.gguf` at exactly
11,849,779,424 bytes, `-ngl 99`. **It carries error bars — the only historical
throughput figures with variance attached** — plus a measured context ladder up to
the 128K OOM ceiling and KV slopes at two cache types.

CUDA Samples is a close second on *result* quality (verbatim transcripts) but
last on reproducibility: **version and build flags are entirely unrecorded.**

## 3. Which results are direct measurements?

**Grade A (9 artifacts):**

- `alignedTypes` **341.533883 GB/s** — full transcript, every type, `0 Failures`
- PCIe **6.94** H→D / **7.20** D→H GB/s pinned — verbatim CuPy table
- CuPy D2D 512 MB → **380.71 GB/s** one-way (~761 DRAM)
- Host identity (GPU, cc, driver, CUDA, cores, PCIe) — `deviceQuery` transcript
- llama.cpp 27B **pp512 1537.77 ± 94.82** and **tg128 56.90 ± 0.22 tok/s**
- llama.cpp 27B context ceilings — each row a real `llama-server` load
- vLLM **0.25.1** / torch **2.11.0+cu130** — read live from package metadata
- Current host inventory

**Grade B (7):** the two CMake caches, both upstream commits, vLLM
`installed-not-serving` + its service configuration, TensorRT-LLM source presence.

**Regraded 2026-08-24 — B → C:** the two `reduction` bandwidth figures (752.30 /
708.92 GB/s). A benchmark *result* can only be **A** (machine output) or **C** (a
reported claim); **B is for configuration evidence** and must never be assigned to
a number just because it is written in a document. Re-inspection found prose
only, and additionally established both were the **Python** sample variants. See
`manifests/historical/cuda-samples.md`.

## 4. Which results are only notes or recollections?

**Grade C (5 artifacts, after the 2026-08-24 regrade) — and this is the
uncomfortable finding.**

Every llama.cpp **7B** figure named in the P0 brief — 149.6 bare, 104–114 API,
157.4 at depth 2 with 43.8% accept, 139.1 default, 121.4 at depth 5, 142.7 q8_0 KV
— exists **only** in `docs/archive/PROJECT-STATE.md:74-78`. Same for
stable-diffusion.cpp's **9.3–11.1 s** FLUX render and the GPU-handoff figures.

`docs/archive/README.md` opens: *"Nothing in this directory is current … **If a
file is in here, do not act on it.**"*

No raw output, no command lines, no model identity, no draft-model identity, no
run counts. **These are the numbers quoted most often in project prose and the
ones with the weakest evidence.** They are recorded as C and must not be promoted.

Two discrepancies against the brief's leads, recorded rather than smoothed:

- FLUX render: brief said *9.3–11.2 s*; local evidence says **9.3–11.1 s**. Local wins.
- `q4_k` quantisation for FLUX is **Grade D (inference)** — not stated locally.

## 5. What exact configurations can be reproduced?

| Engine | Verdict |
|---|---|
| **llama.cpp 27B bench** | **MOSTLY RECONSTRUCTABLE** — command, model bytes, offload, build flags all survive |
| **stable-diffusion.cpp** | **PARTIALLY** — build fully specified; workload (model file, sampler, quantisation) is not |
| **llama.cpp 7B suite** | **HISTORICAL RESULT ONLY** — model unidentified, no flags |
| **CUDA Samples** | **HISTORICAL RESULT ONLY** — results excellent, build unrecoverable |
| **vLLM** | **INSUFFICIENT** as a baseline; **MOSTLY RECONSTRUCTABLE** as a service config |

**One blocker spans both C++ engines.** The `contrib/` trees that produced the
benchmarks are **gone**. What survives is `engines/symoneural-llm` and
`engines/symoneural-diffuse` — **renamed forks committed inside the production
repo**, with no `origin` remote and no independent history. `git describe` returns
a *SyMoNeuRaL* tag. So their upstream merge-base is **Grade E**, and a result from
them is not a result from upstream until that base is established.

## 6. What important fields are missing?

- CUDA Samples version and build flags — **E**
- Both forks' upstream merge-base — **E**
- 7B model filename, bytes, revision; draft model identity — **E**
- Context / batch / ubatch / flash-attention / threads for every 7B run — **E**
- FLUX model file, sampler, seed, CFG; confirmed quantisation — **E/D**
- Launch commands for llama.cpp 7B, sd.cpp, **and `vllm serve`** — **E**
- Run counts and variance for everything except the 27B bench — **E**

## 7. Did historical vLLM performance numbers survive?

> ### HISTORICAL VLLM EXECUTION CONFIRMED
> ### NUMERIC PERFORMANCE BASELINE NOT RECOVERED

The evidence supports that distinction exactly.

**Confirmed:** vLLM **0.25.1** installed at `/home/google/.venvs/vllm`, imports,
sees the GPU, torch 2.11.0+cu130 (Grade A). Classified
**`installed-not-serving`** with a correction record noting an earlier "absent"
claim was false when written (Grade B). OpenAI-compatible on **loopback :9001**,
model id **`symon`**, auth via `VLLM_API_KEY` — all recovered from the *client*
side (Grade B).

**Not recovered:** any throughput, latency, TTFT or concurrency figure, at any
grade. Searched the production repo, the frozen research, `experiments/` and the
venv. **No vLLM benchmark output, report, CSV or logged figure exists.** No
`vllm serve` invocation survives either.

**No number was invented.** vLLM arrives at P2 needing a first measurement, not
defending an old one.

## 8. Which Capacity Lab pieces should be ported later?

**Three files, ~480 lines, at P2 — not now.** Full analysis in
`docs/P0-HARNESS-PORT-REVIEW.md`; classification was measured (coupling counts
per file), not judged.

| File | Class | Why |
|---|---|---|
| `capacity_lab/core.py` | **A — port** | `Sampler` already emits the exact §3 metric set; 0 native refs; 2 fixable path defaults |
| `capacity_lab/players.py` | **A — port** | The engine-neutral interface itself. 0 native, 0 dispatchos, 0 abs paths |
| `cli.py` + `__init__.py` | **A — port** | Zero-coupling scaffolding |
| `native_player.py` | **B — do not port** | Native supervisor. *Reimplement* its queue-depth semantics |
| `scenario.py`, `lifecycle.py`, `harness.py`, `control_service.py` | **C — optional/P5** | 13–36 DispatchOS refs; `harness.py` also has 20 native refs |
| `slice3.py`, `suite.py` | **D — read, don't port** | The nine integrity guards are the asset, not the code |

**Nothing was copied.** An unattributed paste would make this repository a
derivative of the research line it exists to be independent of.

## 9. What current binaries and source trees exist locally?

| Item | State |
|---|---|
| `engines/symoneural-llm` (llama.cpp fork) | **BUILT** 2026-08-20 |
| `engines/symoneural-diffuse` (sd.cpp fork) | **BUILT** 2026-08-20, 124 MB |
| `.venvs/vllm` | **INSTALLED** vLLM 0.25.1, importable |
| `/home/google/TensorRT-LLM` | source present, never built |
| `contrib/` (upstream llama.cpp / sd.cpp / cuda-samples) | **ABSENT — entire tree gone** |
| CUDA Samples, `deviceQuery`, `bandwidthTest` | **ABSENT** |
| `llama-server` / `llama-cli` / `llama-bench` | **ABSENT** |
| `sd-cli` / `sd-server` | **ABSENT** |
| Weights | 34 files under `backend/models/`; **the 27B GGUF was not located** — confirm before P2 |

## 10. What should P1 run first?

**Run CUDA Samples and answer one question:**

> **DOES THE CURRENT RAW CUDA/HARDWARE BASELINE MATCH OR EXCEED THE HISTORICAL
> RAW HARDWARE BASELINE?**

Targets, in evidence order:

1. **`alignedTypes`** — Grade A with a full transcript and a known 50 MB working
   set. The cleanest possible comparison. Target: **341.53 GB/s**.
2. **PCIe pinned H→D / D→H** — Grade A. Targets: **6.94 / 7.20 GB/s**.
3. **`reduction` / `reductionMultiBlockCG`** — **Grade C, reference claims only**
   (regraded 2026-08-24). Nominal: 752.30 / 708.92 GB/s. **These were the
   PYTHON sample variants**, so a C++ v13.3 build is a different program: any
   comparison is **DIRECTIONAL at best** and cannot support a regression claim.

**Three traps that will produce false regressions if ignored:**

- **The L2 trap.** 48 MB of L2 means any bandwidth test under ~100 MB measures
  cache, not DRAM. This is why `alignedTypes` at 50 MB reads *lower* than
  `reduction`.
- **PCIe idle downshift.** `pcie.link.gen.current` reads **1** at idle — power
  management, not a fault. Compare `gen.max` (3) and `width.current` (8), and
  sample link state *during* transfer.
- **CUDA Samples must be obtained.** The tree is absent, so P1 needs a clone —
  the first sanctioned clone of the Performance project, and a P1 action, not a
  P0 one.

**Do NOT change the driver or CUDA.** Not merely because the brief says so, but
because the evidence removes the motive: the current host is **identical** to the
historical host on GPU, compute capability, driver, CUDA, VRAM and PCIe width.
There is no version delta to blame and nothing to roll back to. Investigate a
runtime/driver regression **only if the raw baseline actually shows one.**

**Sequencing note.** P1 needs no model, no engine build and no server. It is the
cheapest phase and it gates every later comparison — if the floor moved, every
engine number after it inherits the discrepancy.

---

## Bottom line

```
CUDA Samples
  historical speed:        PROVEN (A/B, verbatim transcripts)
  exact version:           UNKNOWN
  build flags:             UNKNOWN
  reproduction confidence: LOW  (result only)

llama.cpp — 27B llama-bench
  historical speed:        PROVEN (A, with error bars)
  exact commit:            PROVEN (4df29be) / fork base UNKNOWN
  build flags:             PROVEN (B)
  model:                   PROVEN (exact bytes)
  reproduction confidence: HIGH

llama.cpp — 7B suite
  historical speed:        CLAIMED ONLY (C, superseded archive)
  model:                   UNKNOWN
  reproduction confidence: LOW

stable-diffusion.cpp
  historical speed:        CLAIMED ONLY (C, 9.3-11.1 s)
  exact commit:            PROVEN (master-820-de298c2)
  build flags:             PROVEN (SD_CUDA=ON, arch 120)
  reproduction confidence: MEDIUM

vLLM
  historical execution:    PROVEN (0.25.1 installed, imports, sees GPU)
  historical speed:        NOT AVAILABLE
  launch configuration:    PARTIAL (port 9001, model symon, API shape)
  reproduction confidence: MEDIUM
```
