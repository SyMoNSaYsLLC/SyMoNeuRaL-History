# Historical: stable-diffusion.cpp

**Recovered 2026-08-24. Read-only forensic pass. Nothing was built, loaded or run.**

The only engine whose **exact upstream version string** survives, and one of two
with machine-generated build flags. Its *result*, however, is a range in an
archived summary — not a transcript.

## IDENTITY

| Field | Value | Grade |
|---|---|---|
| project | stable-diffusion.cpp | **A** |
| upstream repository | **`github.com/leejet/stable-diffusion.cpp`** | **B** |
| **historical version string** | **`master-820-de298c2`** | **B** |
| historical binaries | `sd-cli`, `sd-server` under `contrib/stable-diffusion.cpp/build/bin/` | **C** |
| fork present today | `engines/symoneural-diffuse` — renamed fork, binary **BUILT** | **A** |
| fork binary | `build/bin/symoneural-diffuse`, 124,170,408 B, 2026-08-20 15:43 | **A** |
| fork's upstream commit | **NOT RECOVERABLE** — no `origin` remote; tracked inside production repo | **E** |
| original `contrib/` tree | **ABSENT** | **A** |

`docs/specs/sigils-spec.md:76` is the source of the version string, naming
`contrib/stable-diffusion.cpp/build/bin/sd-cli` as *"a C++ binary,
`master-820-de298c2`"*. That is a self-reported version from the tool itself,
transcribed — Grade **B**. It also confirms the brief's `de298c2` lead and
localises it to **820 commits past master's tag base**.

**Has `.gitmodules`** — `.claude/HANDOVER.md:1834` records `--recursive` as
*stable-diffusion-only* among the three engines. That is a real reproduction
requirement: a non-recursive clone of this project is incomplete.

## BUILD

From `engines/symoneural-diffuse/build/CMakeCache.txt` — machine-generated, Grade **B**:

| Field | Value | Grade |
|---|---|---|
| `CMAKE_BUILD_TYPE` | `Release` | **B** |
| `CMAKE_CUDA_ARCHITECTURES` | **`120`** | **B** |
| **`SD_CUDA`** | **`ON`** | **B** |
| `CMAKE_CUDA_COMPILER` | `/usr/local/cuda/bin/nvcc` | **B** |
| `CMAKE_CXX_COMPILER` | `/usr/bin/c++` | **B** |
| build date (binary mtime) | 2026-08-20 15:43 | **A** |
| submodules | **required** (`--recursive`) | **C** |

**The option is `SD_CUDA`, not `GGML_CUDA`.** `.claude/HANDOVER.md:1834` records
that a documented rebuild command *"used the wrong option name for
stable-diffusion.cpp"* and that the error *"would have produced CPU-only builds
that compile, link and run, failing silently."* Confirmed against the cache:
`SD_CUDA:BOOL=ON` is present and there is no `GGML_CUDA` entry. This corrects the
P0 brief's `CMAKE_CUDA_ARCHITECTURES=120` lead — that flag is right, but it is not
sufficient on its own.

`docs/archive/HANDOVER-2026-08-16-1910.md:258` adds: both engines *"configured
with `-DCMAKE_CUDA_ARCHITECTURES=120`. GGML deliberately, **not torch**"* — a
design decision, Grade **C**.

## HOST

Same box; see `cuda-samples.md` for the fully-evidenced host block.
RTX 5070 Ti · `sm_120` · driver 610.57.04 · CUDA 13.3. Grade **A**.

## MODEL / WORKLOAD

| Field | Value | Grade |
|---|---|---|
| model family | FLUX.1-schnell | **C** |
| quantisation | q4_k (per the brief's lead; **not independently confirmed** in local evidence) | **D** |
| model file / exact bytes / revision | **not recorded** | **E** |
| resolution | **768 × 768** | **C** |
| steps | **4** | **C** |
| sampling method | **not recorded** | **E** |
| seed / CFG / other sampler params | **not recorded** | **E** |
| VAE / text-encoder components | not recorded for this run | **E** |

The workload line survives as a single table row:
`docs/archive/PROJECT-STATE.md:79` — `| FLUX 768², 4 steps | 9.3–11.1 s |`.

**Note the discrepancy with the brief**, recorded rather than smoothed over: the
brief's lead says *"roughly 9.3–11.2 sec"*; the local evidence says
**9.3–11.1 s**. One tenth of a second, and it is the difference between quoting
a source and quoting a memory of it. The local figure is authoritative here.

`q4_k` is graded **D** (inference): the archived evidence names FLUX at 768²/4
steps but does not state the quantisation. A related but *different* file
(`docs/ops/COMFY-FLUX-BUNDLE.md:53`) discusses a GGUF that upstream's loader
**rejects** — so quantisation claims for this engine need care, not assumption.

## RUNTIME

| Field | Value | Grade |
|---|---|---|
| binary | `sd-cli` (bare), `sd-server` (service) | **C** |
| **launch command** | **NOT RECOVERED** — no invocation survives | **E** |
| ports | not recorded | **E** |
| threading | not recorded | **E** |
| environment variables | not recorded | **E** |
| GPU handoff | *"clean handoff between runs"*, ~1 s drain to a 1.5 GB floor, 3/3 cycles no OOM | **C** |

The GPU-handoff behaviour corroborates the brief's "clean GPU handoff" lead and
comes from the same archived table (`PROJECT-STATE.md:81`).

No credential material found in any stable-diffusion.cpp evidence.

## RESULTS

| Measurement | Value | Unit | Grade |
|---|---|---|---|
| FLUX 768², 4 steps | **9.3 – 11.1** | seconds per image | **C** |
| GPU drain to floor | ~1 | seconds | **C** |
| OOM-free handoff cycles | 3 / 3 | cycles | **C** |

Concurrency: **1** (single-image CLI render). Grade **D** (inferred from the
workload description; not stated).

Runs: a **range** is quoted, which implies more than one render, but **no run
count and no distribution** survive. Grade **E**.

Path: **bare benchmark** (`sd-cli`), not the server path. Grade **C**.

**The result is a range in a summary table inside `docs/archive/`**, whose README
states *"Nothing in this directory is current … do not act on it."* No timing
transcript, no per-step output, no command line. Grade **C**, and it must not be
promoted.

## MISSING

- exact model file, bytes and revision — **E**
- quantisation, confirmed rather than inferred — currently **D**
- sampling method, seed, CFG — **E**
- launch command — **E**
- run count and variance behind the 9.3–11.1 s range — **E**
- fork's upstream merge-base — **E**
- whether the range came from `sd-cli` or `sd-server` — **C** at best

## REPRODUCTION STATUS

**PARTIALLY RECONSTRUCTABLE.**

The strongest half is the build: `master-820-de298c2` plus `SD_CUDA=ON`,
`CMAKE_CUDA_ARCHITECTURES=120`, `Release`, and a recorded `--recursive`
requirement is genuinely enough to rebuild a matching engine.

The workload half is not. Without the model file, its quantisation confirmed, the
sampler and the command line, a re-run at 768²/4 steps would produce a number
that *looks* comparable to 9.3–11.1 s while potentially differing in
quantisation, sampler or component set. That is the specific trap
`PERFORMANCE-POLICY.md` §2 exists to prevent, so the comparison must not be made
casually.
