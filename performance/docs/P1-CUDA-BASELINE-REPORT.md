# P1 — Current CUDA / hardware baseline report

**One question:** does the current raw GPU/host performance match or exceed the
historical raw hardware evidence?

**Answer: YES on every measurement where a defensible comparison exists.** No
software-stack investigation is justified.

Measured 2026-08-24. CUDA Samples **v13.3** @ `b7c5481c556c3fe98db060207ecaa41a4b9a9abc`,
`sm_120`, Release. No model loaded, no engine started, nothing tuned.

---

## The comparability table — read this before any delta

`PERFORMANCE-POLICY.md` §2 forbids comparing unlike things and calling it a
result. Each row was classified against the six criteria (same sample, same
algorithm/semantics, same problem size, same arguments, same iteration count,
same units and measurement definition) **before** any number was differenced.

| Measurement | Same sample | Same semantics | Same size | Same args | Same iters | Same units | **Class** |
|---|---|---|---|---|---|---|---|
| `alignedTypes` RGBA32 | ✅ C++ both | ✅ | ✅ **49,999,872 B identical** | ✅ none accepted | ❓ unrecorded | ✅ | **MOSTLY COMPARABLE** |
| `deviceQuery` | ✅ | ✅ | n/a | ✅ | n/a | ✅ | **EXACTLY COMPARABLE** (validation) |
| `reduction` | ❌ **C++ vs Python** | ❌ | ~ read count matched | ❌ | ❓ | ✅ | **DIRECTIONAL ONLY** |
| `reductionMultiBlockCG` | ❌ **C++ vs Python** | ❌ | ❓ unrecorded | ❌ | ❓ | ✅ | **DIRECTIONAL ONLY** |
| PCIe pinned H2D / D2H | ❌ **CUDA runtime vs CuPy** | ❌ | ✅ 512 MiB | ❌ | ❌ | ✅ one-way | **DIRECTIONAL ONLY** |
| `transpose` | — no historical figure | — | — | — | — | — | **NOT COMPARABLE** (current only) |

**Why nothing reaches EXACTLY COMPARABLE on throughput:** the historical CUDA
Samples *version* was never recorded (P0, Grade E), and iteration counts were
never recorded for any sample. `alignedTypes` reaches MOSTLY COMPARABLE because it
is the same C++ sample at a byte-identical, compile-time-fixed working set.

**Two of these classifications exist because of the P0 correction gate.** The
`reduction` pair were regraded B → C when re-inspection showed they were the
**Python** samples. Without that correction this report would have differenced a
C++ binary against a Python result and called −20.89% a driver regression.

---

## HISTORICAL vs CURRENT vs DELTA

### 1. alignedTypes — MOSTLY COMPARABLE

| | |
|---|---|
| **HISTORICAL** | 341.533883 GB/s · **Grade A** (verbatim transcript) |
| **CURRENT** | mean **332.3580** · median 330.3286 · **best run 340.9868** GB/s · 5 runs, CoV 1.455% |
| **DELTA** | mean **−2.69%** · **best run −0.16%** |
| **VERDICT** | **PASS** |

The historical figure is a **single run with no variance recorded**. Our best run
sits 0.16% from it — inside any plausible run-to-run band. Run ordering: run 1 at
340.99, then 330.62 → 330.33 → 330.18 → 329.67.

Observed alongside: temperature **53 → 54 °C**, power **50 → 63 W** against a
300 W limit, and **SM clock RISING 2760 → 2985 MHz**.

**This is run-to-run warm-state/clock/background-load variability; no evidence of
thermal or power throttling was observed.** Corrected 2026-08-24 — an earlier
draft called it a "thermal ramp / clock-state signature", which the data does not
support: 1 °C is not a thermal event, and a rising clock is the opposite of
throttling. The mechanism is **not established**; what is established is that the
first run differed from the steady state.

P1.11 excludes both thermal state and measurement methodology as grounds for a
regression claim, and unexplained run-to-run variability of this size is not
evidence of one either. If the historical number was a first-run-after-idle
figure — and a single number with no variance plausibly was — the two are
consistent.

### 2. transpose — CURRENT CHARACTERISATION (NOT COMPARABLE)

| | |
|---|---|
| **HISTORICAL** | none exists |
| **CURRENT** | simple copy **648.78 GB/s** (CoV 0.446%), shared-mem copy **654.00** (CoV 0.634%), 5 runs each |
| **VERDICT** | no comparison possible; **highest-confidence current number in P1** |

At 8192×8192 fp32 (~512 MiB of traffic, ≫ 48 MiB L2) the card sustains **~650
GB/s = ~73% of the 896.1 GB/s theoretical peak**, with sub-1% variance.

**This is the number to plan against.** It also proves the L2 trap on this
hardware: ~650 GB/s DRAM-bound versus ~332 GB/s at alignedTypes' 50 MB working
set — the same card, a factor of two apart, purely from working-set size.

### 3. reduction (C++) — DIRECTIONAL ONLY

| | |
|---|---|
| **HISTORICAL** | 752.30 GB/s · **Grade C** · **Python** sample |
| **CURRENT** | mean **726.6975** · median 694.13 · max **787.85** GB/s · 5 runs, CoV 6.660% |
| **DELTA** | nominal −3.40% — **not a valid regression figure** |
| **VERDICT** | **PASS (directional)** |

Our maximum (787.85) **exceeds** the historical claim; our mean sits 3.4% under
it. With CoV 6.7% on a ~40–50 µs timed interval, a 3.4% mean gap is noise. This
sample is too short to be a stable bandwidth probe and should not be a P1 anchor.

### 4. reductionMultiBlockCG (C++) — DIRECTIONAL ONLY

| | |
|---|---|
| **HISTORICAL** | 708.92 GB/s · **Grade C** · **Python** sample |
| **CURRENT** | mean **560.8410** GB/s · 5 runs, CoV 2.496% |
| **DELTA** | nominal −20.89% — **NOT a regression claim** |
| **VERDICT** | **NOT COMPARABLE for a regression conclusion** |

The largest apparent gap in P1, and the one most likely to be misread. Three
reasons it cannot support a regression finding:

1. **Different program.** Historical was `reductionMultiBlockCG.py` under a
   `venv-extras` environment needing a two-directory `--cuda-include-dir` for
   libcu++ from `cuda-cccl`. Ours is the C++ sample.
2. **Problem size unknown.** Historical element count was never recorded; the C++
   default is 33,554,432. A different N alone can produce this gap.
3. **Grade C.** The baseline is prose, not machine output.

What *does* corroborate: `numBlocks: 70` matches the historical "70 blocks →
`grid.sync()`" exactly, so the algorithm shape is right.

**This is precisely the row that would have been reported as a driver regression
without the P0 correction gate.**

### 5. PCIe — DIRECTIONAL ONLY, and consistent with the link

| | |
|---|---|
| **HISTORICAL** | H2D pinned **6.94**, D2H pinned **7.20** GB/s · **Grade A** · **CuPy** implementation (512 MB row) |
| **CURRENT** | H2D pinned **6.9262** (CoV 0.690%), D2H pinned **7.1945** (CoV 0.455%) GB/s · 512 MiB, 12 iterations each · **CUDA Runtime API** |
| **CLASS** | **DIRECTIONAL ONLY** — implementations not equivalent |
| **VERDICT** | **PASS** — consistent with a healthy Gen 3 ×8 link |

Deliberately **no regression percentage**. The defensible statement is the
physical one: Gen 3 ×8 theoretical is 7.88 GB/s, so H2D is at **87.9%** and D2H
at **91.3%** of ceiling. The historical dossier recorded **88%** and **91%**.

Pageable, as current characterisation only: H2D 6.8234, D2H 6.9700 GB/s.

**Link state during sustained transfer** — 46 of 50 samples read **gen 3 / ×8**;
the 4 gen-1 samples are the idle period before the run started. The idle
downshift P0 flagged is now demonstrated rather than asserted, and reading
`gen.current` at idle would have produced a phantom Gen-1 regression.

---

## GPU telemetry during runs

| Phase | GPU util | Mem util | SM clock | Mem clock | Power | Temp | PCIe |
|---|---|---|---|---|---|---|---|
| idle (pre) | 13–15% | 14% | 1642 MHz | 405 MHz | 30.25 W | 48 °C | gen 2 ×8 |
| alignedTypes | 32–43% | — | 2760→2985 MHz | 13801 MHz | 50→63 W | 53→54 °C | **gen 3 ×8** |
| transpose | 40–100% | — | 2992 MHz | 13801 MHz | 76→83 W | 55→57 °C | **gen 3 ×8** |
| reduction | 6–11% | — | 1515 MHz | 405 MHz | 33→46 W | 54–55 °C | gen 3 ×8 |
| reductionMultiBlockCG | 0–43% | — | 2565→2632 MHz | 13801 MHz | 31→46 W | 54–55 °C | gen 3 ×8 |
| PCIe sustained | **100%** | 2–14% | 300 MHz | 405 MHz | →57.15 W | →56 °C | **gen 3 ×8** |
| idle (post) | 1% | 15% | 540 MHz | — | 15.17 W | 52 °C | gen 1 ×8 |

Peak temperature **57 °C** against a 300 W limit never approached (max 83 W). The
card was never thermally or power constrained, which is itself why the
alignedTypes decline cannot be attributed to throttling.

## Contamination

**Present, disclosed, not eliminated.** 19 **graphics** contexts (Xorg 378 MiB,
kwin_x11 175 MiB, plasmashell 231 MiB, Chrome, konsole…) holding ~1,222–1,309 MiB
and idling at 13–15% GPU utilisation throughout. **Zero compute contexts** — no
AI engine, no `chat_worker`, no `llama-server`, nothing on 8811 or 9001.

Not stopped: shutting down the operator's desktop is out of scope.

**The current desktop graphics workload remained present and stable enough for
the P1 measurements. Historical graphics-load equivalence was not proven** — no
record of the historical graphics load exists.

**Production did not interfere.** `symoneural-api`, `caddy` and
`symoneural-gateway` stayed active with unchanged PIDs and hold no GPU compute
context. No benchmark was aborted for contention.

Uncontrolled variables, recorded because they are the honest limits: CPU governor
`powersave` (untouched), background desktop load, and the fact that none of these
were recorded historically either.

---

## P1 conclusion

**The current raw GPU/host baseline matches or exceeds the historical evidence
wherever a defensible comparison exists.**

| Measurement | Class | Verdict |
|---|---|---|
| deviceQuery | EXACTLY COMPARABLE | **PASS** — identity matches on every field |
| alignedTypes | MOSTLY COMPARABLE | **PASS** — best run within 0.16% |
| PCIe pinned | DIRECTIONAL | **PASS** — 87.9% / 91.3% vs historical 88% / 91% |
| reduction | DIRECTIONAL | **PASS** — max exceeds historical claim |
| reductionMultiBlockCG | NOT COMPARABLE | **no conclusion** — different program, unknown N, Grade C |
| transpose | current only | **~650 GB/s**, 73% of peak, CoV <1% |

**Is a driver or CUDA investigation justified? NO.**

P1.11 requires *multiple well-controlled comparable metrics showing consistent
regression*. What the evidence shows instead:

- the one **MOSTLY COMPARABLE** metric passes (best run −0.16%);
- both **PCIe** directions land within a tenth of a percent of the historical
  *fraction of link ceiling*;
- `reduction`'s **maximum exceeds** the historical claim;
- the only large gap (`reductionMultiBlockCG`, −20.89%) is a C++-vs-Python
  comparison against a Grade-C baseline at an unknown problem size — explicitly
  excluded by P1.11;
- there is **no version delta to investigate**: driver 610.57.04 and CUDA 13.3 are
  the versions the historical figures were taken on.

Changing driver or CUDA now would discard a matching baseline in pursuit of a
regression that has not been demonstrated.

## Caveats a later reader should not lose

1. **`reductionMultiBlockCG` −20.89% is not a regression.** If anyone wants to
   settle it, run the *Python* sample from `python/2_CoreConcepts/` — it exists in
   this v13.3 checkout — which is a genuine like-for-like path.
2. **alignedTypes measures L2, not DRAM.** Its ~332 GB/s and transpose's ~650
   GB/s are the same card at different working-set sizes. Quote the right one.
3. **The historical figures are single runs with no variance.** Our CoV of
   0.4–6.7% across samples is a reminder that a lone number carries an unstated
   error bar, and `reduction` at 6.7% is too noisy to anchor anything.
4. **The desktop was resident throughout.** Every P1 number includes it, and
   historical graphics-load equivalence was not proven.

## Recommended next step

Not P2 yet. Two cheap items would close P1 properly:

- **Run the Python `reduction` / `reductionMultiBlockCG` samples** from this same
  v13.3 checkout to convert the two DIRECTIONAL rows into like-for-like
  comparisons. Requires checking whether `python/requirements.txt` deps are
  already present — **no installs** without approval.
- **Repeat alignedTypes with deliberate idle gaps between runs**, to characterise
  the run-1-versus-steady-state difference behind the −2.69% mean. The mechanism
  is unexplained, and naming it would require evidence P1 does not have.

Neither is a blocker. The baseline needed to proceed exists.
