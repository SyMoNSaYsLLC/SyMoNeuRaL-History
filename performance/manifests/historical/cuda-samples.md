# Historical: CUDA Samples

**Recovered 2026-08-24. Read-only forensic pass. Nothing was built or run.**

The strongest historical evidence of the four engines, and the only one where raw
tool transcripts survive verbatim — for **some** of its results. Two were
regraded on 2026-08-24; see RESULTS.

## IDENTITY

| Field | Value | Grade |
|---|---|---|
| project | NVIDIA CUDA Samples | **A** |
| upstream repository | not evidenced locally | **E** |
| version / tag / commit | **not recorded anywhere on this box** | **E** |
| samples evidenced | `deviceQuery`, `alignedTypes` (C++) · `reduction`, `reductionMultiBlockCG` (**Python** variants) | **A** |
| source or binaries present today | **ABSENT** — no `contrib/`, no `cuda-samples` tree, no built binaries | **A** |

`docs/01-hardware-dossier.md:91` states it directly: *"the repository no longer
ships `bandwidthTest`"*. The samples were built, run, and the tree removed.

## BUILD

| Field | Value | Grade |
|---|---|---|
| compiler / toolchain | not recorded for the samples specifically | **E** |
| CUDA toolkit | 13.3 at run time (from `deviceQuery` output) | **A** |
| architecture flags | not recorded | **E** |
| CMake flags | not recorded — **no `CMakeCache.txt` survives** | **E** |

**This is the central gap for CUDA Samples.** The best results are Grade A; the
build that produced them is Grade E. See REPRODUCTION STATUS.

## HOST (at time of measurement)

Every row below is from verbatim `deviceQuery` / `nvidia-smi` transcript pasted
into `docs/01-hardware-dossier.md`.

| Field | Value | Grade |
|---|---|---|
| GPU | NVIDIA GeForce RTX 5070 Ti | **A** |
| compute capability | **12.0** (`sm_120`, "Blackwell") | **A** |
| SM count | 70 MP × 128 cores = 8960 cores | **A** |
| driver | **610.57.04** | **A** |
| CUDA driver (user-mode) | 13.3 | **A** |
| CUDA driver (kernel-mode) | 610.57.4 | **A** |
| CUDA runtime | 13.3 | **A** |
| theoretical DRAM bandwidth | 896.1 GB/s | **A** |
| L2 cache | 48 MB | **A** |
| PCIe link | **Gen 3 ×8** | **A** |
| kernel | not recorded alongside the samples run | **E** |
| CPU / RAM | not recorded alongside the samples run | **E** |

## WORKLOAD

Four independent memory-bandwidth measurements, deliberately not one:

| Sample | Working set | Grade |
|---|---|---|
| `alignedTypes` | 49,999,872 B (~50 MB) | **A** |
| `reduction` | 8,388,608 global reads, 32,768 block outputs, two-stage | **C** |
| `reductionMultiBlockCG` | single launch, 70 blocks, `grid.sync()` | **C** |
| CuPy D2D copy | 512 MB | **A** |

## RESULTS

| Measurement | Value | Unit | Grade | Source |
|---|---|---|---|---|
| `alignedTypes` RGBA32 copy throughput | **341.533883** | GB/s one-way | **A** | verbatim transcript, `01-hardware-dossier.md:355` |
| `reduction` sample | **752.30** | GB/s | **C** | prose only — see the regrade note below |
| `reductionMultiBlockCG` | **708.92** | GB/s | **C** | prose only — and a **Python** sample, not the C++ one |
| PCIe H→D pinned | **6.94** | GB/s (88% of Gen3 ×8 peak) | **A** | verbatim CuPy table, `:304` |
| PCIe D→H pinned | **7.20** | GB/s (91% of peak) | **A** | verbatim CuPy table, `:304` |
| CuPy D2D 512 MB | 380.71 one-way → ~761 DRAM | GB/s | **A** | verbatim table |

**Grade split matters here and is not a technicality.** `alignedTypes` and the
PCIe figures survive as full tool output — every type tested, every timing, the
`TEST OK` lines and `0 Failures`.

### REGRADED 2026-08-24: the two `reduction` figures are C, not B

They were first recorded as **B**. That was wrong, and the rule it broke is worth
stating: **B is for direct *configuration* evidence. A benchmark RESULT can never
be B merely because it is written down in a document.** A result is either
machine output (**A**) or somebody's report of a result (**C**). There is no
middle grade for a number in prose.

Re-inspected at source. Both entries in `docs/04-cuda-curriculum/2_CoreConcepts.md`
read as hand-written summary lines:

```
> **Result** — PASSED. Two-stage reduction, 8,388,608 global reads,
> 32768 block outputs, **752.30 GB/s**.

> **Result** — PASSED with **708.92 GB/s** in a single kernel launch —
> 70 blocks -> grid.sync() -> block 0 finalises.
```

Searched every `.md`, `.txt` and `.log` outside `references/` for the sample's
actual stdout (`Reducing array`, `GPU result`, throughput lines). **No verbatim
output exists anywhere on this box.** Every one of the seven places these numbers
appear is either that prose or a summary-table cell citing it.

**Both are therefore Grade C — documented historical claim — and are NOT
promoted.**

### And a second finding that matters more for P1

The recorded commands are:

```bash
cd $CUDA_SAMPLES/python/2_CoreConcepts/reduction && python reduction.py
cd $CUDA_SAMPLES/python/2_CoreConcepts/reductionMultiBlockCG && python reductionMultiBlockCG.py --cuda-include-dir ...
```

**These were the PYTHON samples, not the C++ ones.** They ran under a venv
(`venv-extras`) with `cuda-cccl`, `numba-cuda` and `torch`, and
`reductionMultiBlockCG.py` required a two-directory `--cuda-include-dir` because
cooperative_groups pulls in libcu++ from a pip package rather than from
`/usr/local/cuda/include`.

A C++ `reduction` built from `cuda-samples` v13.3 is **a different program in a
different language with a different launch path**. Comparing it against these
numbers is at best DIRECTIONAL, and calling any shortfall a driver regression
would be unfounded. P1 must classify it accordingly.

**Working figure used historically: ~750 GB/s**, 84% of theoretical peak — but
note it rests on the two Grade-C figures, so it is a reference claim rather than a
proven baseline.

Runs: **not recorded** for any sample. No repeat evidence. Grade **E**.

Path: **bare benchmark**, not a server or API path. Grade **A**.

## The L2 trap — recorded because it invalidates naive re-measurement

`01-hardware-dossier.md:103-114`: with 48 MB of L2 on this part, **any bandwidth
test under ~100 MB is measuring cache, not DRAM.** `alignedTypes` runs a 50 MB
working set, which is why its 341.5 GB/s one-way figure is *lower* than the
`reduction` figures rather than higher.

P1 must size its working set above ~100 MB or it will produce a number that
looks like a regression and is actually a cache hit.

## MISSING

- CUDA Samples version / tag / commit — **E**
- build flags and architecture flags — **E**
- `CMakeCache.txt` — does not survive
- run counts and variance for every sample — **E**
- kernel version and CPU/RAM at measurement time — **E**
- raw transcript for `reduction` / `reductionMultiBlockCG` — only summaries survive

## REPRODUCTION STATUS

**HISTORICAL RESULT ONLY.**

The `alignedTypes` and PCIe *results* are the best-evidenced in this recovery —
verbatim tool output with per-type timings. The two `reduction` figures are not:
they are Grade C. And in every case, the samples tree is **absent**, its version is **unknown**,
and its build flags are **unrecorded**. A re-run would therefore be a *new*
measurement on an unknown-matching build, not a reproduction.

This is not a blocker for P1. Blackwell `sm_120` and CUDA 13.3 are still present
(see `hardware/CURRENT-HOST-INVENTORY.md`), and the *host* rows above are
comprehensively evidenced. P1 can establish a current floor and compare it
against these numbers as a **hardware** comparison, which is exactly what P1 is
for — provided the L2 trap above is respected.
