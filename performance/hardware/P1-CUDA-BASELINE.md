# P1 — Current raw CUDA / GPU baseline

**Measured 2026-08-24 on the production host.** CUDA Samples **v13.3** at commit
`b7c5481c556c3fe98db060207ecaa41a4b9a9abc`, built for `sm_120`.

**No AI model was loaded. No engine was started. No driver, CUDA, kernel, clock,
power-limit or persistence setting was changed.** This measures the host's
**current operating state**, deliberately untuned.

---

## Build

```
cmake -S sources/cuda-samples -B build/cuda-samples-v13.3 \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120
```

Configured from the **repository root**, not `-S cpp`. CMake 3.31.6, nvcc 13.3
V13.3.73, c++ (Debian 14.2.0-19) 14.2.0.

| CMakeCache field | Value |
|---|---|
| `CMAKE_BUILD_TYPE` | `Release` |
| `CMAKE_CUDA_ARCHITECTURES` | `120` |
| `CMAKE_CUDA_COMPILER` | `/usr/local/cuda/bin/nvcc` |
| `CMAKE_CXX_COMPILER` | `/usr/bin/c++` |

The root configure initially **failed** in `cpp/0_Introduction/simpleMPI`:
`FindMPI` advertised `MPI::MPI_C` with a non-existent include directory because
`libopenmpi-dev` was not installed while `libopenmpi40` runtime was. The operator
installed `libopenmpi-dev 5.0.7-1`, after which the root configure succeeded. That
is the only system change in this pass and it was made by the operator, not by
this process.

### Binary provenance

| Sample | SHA256 |
|---|---|
| `deviceQuery` | `711b4d684ad2055e106f10ba616acc1fd5805d957c3f315f4701080cb929f70d` |
| `alignedTypes` | `ee1cd65054506554943440920a48e73c6d5e17a3f8c3455971017f6a34c26fd5` |
| `reduction` | `c31c8d49e0e24c07a318d2a605a3b3aa108d98454ade33c79df329756437cb1c` |
| `reductionMultiBlockCG` | `cbdcaf9b2d128c81feb74f1737adc1c29a30728929b28e42d1bce17df2372fa1` |
| `transpose` | `fb00574dc81942b5dbe1aceac608464c73f982642642455a371119a617d8541b` |
| `p1_cuda_pcie` (ours) | `5ea2da7b0ba058b7cc4adf043711f66925513c0f7c8697fbb2daf4769705aed8` |

---

## Pre-run host state (frozen 15:25:15 −04:00)

| Field | Value |
|---|---|
| kernel | `6.12.101+deb13-amd64` |
| CPU | Intel i9-10900KF, 10C/20T, 800–5300 MHz |
| **CPU governor** | **`powersave`** — left untouched; recorded as an uncontrolled variable |
| RAM | 96,360 MiB total |
| GPU | RTX 5070 Ti, `GPU-15e0078a-cb3a-50d1-a40b-94e4d538fc78` |
| VBIOS | `98.03.58.00.23` |
| driver | 610.57.04 |
| CUDA | 13.3 / 13.3 (nvcc V13.3.73) |
| compute capability | 12.0 (`sm_120`) |
| **persistence mode** | **Enabled** |
| power limit | 300.00 W (default 300.00 W) |
| idle power | 30.25 W |
| idle clocks | 1642 MHz SM, 405 MHz mem |
| idle temp | 48 °C |
| PCIe | gen.max 3, width.max 16, **gen.current 2, width.current 8** at idle |

`deviceQuery` reports **L2 = 50,331,648 bytes (48 MiB)** — the figure behind the
L2 trap, now confirmed on this build rather than inherited from the dossier.

### Known contamination, recorded not hidden

**19 graphics contexts** (Xorg 378 MiB, kwin_x11 175 MiB, plasmashell 231 MiB,
Chrome, konsole…) hold **~1,254–1,309 MiB** of VRAM and idle at 13–15% GPU
utilisation. **Zero compute contexts.** This is a KDE desktop session, and it was
present for every run.

It was **not** stopped: shutting down the operator's desktop is out of scope.

**The current desktop graphics workload remained present and stable enough for
the P1 measurements. Historical graphics-load equivalence was not proven.** No
record of the historical graphics load exists, so whether it resembled this one is
unknown. Recorded as a **standing confound** affecting all P1 numbers equally.

---

## deviceQuery — validation

**`Result = PASS`.**

| Field | Current | Historical | Match |
|---|---|---|---|
| device | RTX 5070 Ti | RTX 5070 Ti | ✅ |
| CUDA driver / runtime | 13.3 / 13.3 | 13.3 / 13.3 | ✅ |
| compute capability | 12.0 | 12.0 | ✅ |
| MPs × cores/MP | 70 × 128 = 8960 | 70 × 128 = 8960 | ✅ |
| memory clock | 14001 MHz | 14001 MHz | ✅ |
| bus width | 256-bit | 256-bit | ✅ |
| global memory | 15858 MB (16,628,514,816 B) | — | — |
| L2 | 50,331,648 B | 48 MB (stated) | ✅ |
| max clock | 2572 MHz | — | — |

No warnings, no mismatches. Cooperative kernel launch: supported. ECC: disabled.
Compute mode: Default.

---

## Results

### alignedTypes — EXACTLY COMPARABLE on problem size

`MEM_SIZE` is a compile-time constant with **no CLI override**; `scale_factor`
resolves to 1.00 on 8960 cores, so the working set printed **`49999872`** —
byte-identical to the historical run. All runs reported `0 Failures`.

RGBA32 copy throughput, warm-up discarded, 5 recorded runs:

| Run | GB/s |
|---|---|
| 1 | 340.986806 |
| 2 | 330.621769 |
| 3 | 330.328586 |
| 4 | 330.182207 |
| 5 | 329.670865 |

| Statistic | Value |
|---|---|
| mean | **332.3580** GB/s |
| median | 330.3286 |
| min / max | 329.6709 / 340.9868 |
| stdev | 4.8359 |
| **CoV** | **1.455 %** |

**Historical (Grade A): 341.533883 GB/s.** Mean delta **−9.18 GB/s (−2.69%)**;
best-run delta **−0.55 GB/s (−0.16%)**.

**The distribution is the finding, not the mean.** Run 1 landed at 340.99, within
**0.16%** of historical. Runs 2–5 settled at 330.20 ± 0.40.

Observed alongside that decline: temperature moved only **53 → 54 °C**, power
**50 → 63 W** against a 300 W limit, and **SM clock ROSE 2760 → 2985 MHz**.

**This is run-to-run warm-state/clock/background-load variability; no evidence of
thermal or power throttling was observed.** Corrected 2026-08-24: an earlier draft
called it a "thermal / clock-state signature", which overstated the evidence. A
1 °C change is not a thermal event, and a clock that *increases* is the opposite
of throttling. What the data supports is that the first run differed from the
steady state; the mechanism is not established.

### transpose — L2-EXCEEDING current characterisation

`-dimX=8192 -dimY=8192` → 268,435,456 B per matrix, ~512 MiB of traffic, far
beyond the 48 MiB L2. **There is no historical `transpose` figure**, so this is
current characterisation only — not a comparison.

| Kernel | mean GB/s (5 runs) | CoV |
|---|---|---|
| simple copy | **648.78** | 0.446 % |
| shared-memory copy | **654.00** | 0.634 % |
| fine-grained | ~651.8 | — |
| coarse-grained | ~617.8 | — |
| optimized | ~619.0 | — |
| coalesced | ~613.7 | — |
| diagonal | ~563.3 | — |
| naive | ~381.0 | — |

All runs `Test passed`. **This is the most important number in P1 for planning:**
at a genuinely DRAM-bound working set the card sustains **~650 GB/s**, i.e. ~73%
of the 896.1 GB/s theoretical peak — roughly **double** the ~332 GB/s that
alignedTypes reports at 50 MB. The L2 trap is now demonstrated on this hardware,
not merely quoted.

### reduction (C++) — DIRECTIONAL ONLY

`-n=8388608`, matching the historical **read count** (2^23). 256 threads,
64 blocks. All `Test passed`.

| Run | GB/s |
|---|---|
| 1 | 692.1291 |
| 2 | 787.8475 |
| 3 | 694.1335 |
| 4 | 688.7198 |
| 5 | 770.6576 |

mean **726.6975** · median 694.1335 · min 688.7198 · max 787.8475 · sd 48.3981 ·
**CoV 6.660 %**

Also at the default `n=16777216`: mean **351.87** GB/s (3 runs, CoV 2.71%).

**Historical: 752.30 GB/s, Grade C, and produced by the PYTHON sample.** Mean
delta −3.40% — but the classification is **DIRECTIONAL ONLY** and that delta must
not be read as a regression. Note also the timed interval is ~40–50 µs, which is
why CoV is 6.7%: this sample is too short to be a stable bandwidth probe.

### reductionMultiBlockCG (C++) — DIRECTIONAL ONLY

Default 33,554,432 elements, `numThreads: 768`, **`numBlocks: 70`** — the block
count matches the historical note's "70 blocks → `grid.sync()`".

| Run | GB/s |
|---|---|
| 1 | 571.552932 |
| 2 | 551.610057 |
| 3 | 540.785813 |
| 4 | 572.235003 |
| 5 | 568.021247 |

mean **560.8410** · median 568.0212 · min 540.7858 · max 572.2350 · sd 13.9959 ·
**CoV 2.496 %**

**Historical: 708.92 GB/s, Grade C, PYTHON sample.** Apparent delta −20.89%.
**This is NOT a regression claim.** The element count for the historical run was
never recorded, the language and launch path differ, and the C++ default may
simply be a different problem size. Classification: **DIRECTIONAL ONLY**.

### PCIe — CURRENT CUDA-RUNTIME PCIE CHARACTERIZATION

**Not a reproduction.** CuPy is absent from every environment on this box and the
historical `venv-extras` no longer exists; CuPy was **not** installed.
**NVBANDWIDTH = ABSENT · P1 INSTALL DEFERRED** (verified three ways: `command -v`
rc=1; `find` rc=0 with 0 matches; `dpkg -l` 0 matches).

Implementation: `benchmarks/p1_cuda_pcie.cu`, source SHA256
`c7f5c77c91787b7fdb7791ca874d5c25225a9118efcaa1a10da422a148ac0ce2`, built with

```
/usr/local/cuda/bin/nvcc -O3 -arch=sm_120 -o build/p1-cuda/p1_cuda_pcie benchmarks/p1_cuda_pcie.cu
```

`cudaHostAlloc` pinned buffers, `cudaMemcpyAsync`, CUDA events around the
transfer region only, allocation/free outside the timed region, warm-up
discarded, **512 MiB**, **12 recorded iterations** per direction.

**Bandwidth formula: `bytes / elapsed_seconds` — ONE WAY**, not read+write.

| Direction | mean | median | min | max | sd | CoV |
|---|---|---|---|---|---|---|
| **H2D pinned** | **6.9262** | 6.9310 | 6.8380 | 6.9820 | 0.0478 | **0.690 %** |
| **D2H pinned** | **7.1945** | 7.1960 | 7.1330 | 7.2420 | 0.0327 | **0.455 %** |
| H2D pageable | 6.8234 | 6.8614 | 6.6936 | 6.9089 | 0.0868 | 1.272 % |
| D2H pageable | 6.9700 | 6.9613 | 6.8691 | 7.0661 | 0.0710 | 1.018 % |

**Consistency with the physical link,** which is the only claim the methodology
supports: Gen 3 ×8 theoretical is 7.88 GB/s, so H2D pinned is at **87.9%** and
D2H pinned at **91.3%** of ceiling. The historical dossier recorded **88%** and
**91%**. The current result is fully consistent with a healthy Gen 3 ×8 link.

**No regression percentage against the historical CuPy figures is computed**,
deliberately — the implementations are not equivalent.

### PCIe link state DURING sustained transfer

The decisive observation, and it settles the P0 caveat empirically. 50 samples at
250 ms during an 8.53 s sustained window (112 transfers):

| gen / width | samples | when |
|---|---|---|
| **gen 3 / ×8** | **46** | transfer active |
| gen 1 / ×8 | 4 | the idle samples before the run began |

Telemetry envelope during transfer: GPU util → **100%**, memory util 2–14%,
power → **57.15 W**, temp → 56 °C, SM clock 300 MHz (a copy engine workload does
not need SM clocks).

**Idle `gen.current = 1` is power management, and it negotiates to Gen 3 under
load.** Anyone reading the idle value would have reported a Gen-1 regression that
does not exist.

---

## Post-run safety

Zero GPU compute apps · no benchmark process remaining · GPU returned to idle
(1% util, 1222 MiB graphics-only, 15.17 W, 52 °C, gen 1 ×8) · nothing listening
on 8811 or 9001 · `symoneural-api` / `caddy` / `symoneural-gateway` all **active**
with unchanged PIDs 1866 / 1907 / 1903 · production `main` `7d1a5529` clean ·
frozen custom `44863110` clean and locked.
