# MIT AI Training

Consolidated manual and a native CUDA engine, both verified against this
machine (NVIDIA GeForce RTX 5070 Ti, Blackwell `sm_120`, CUDA 13.3).

## The manual — three forms, same content

| Form | Path | Use it for |
|---|---|---|
| **Browsable page** | [`MIT_AI_Training.html`](MIT_AI_Training.html) | Reading. Sidebar nav, scroll-spy, collapsible READMEs, light/dark. Open it directly — no server, no network. |
| **Single markdown** | [`MIT_AI_Training.md`](MIT_AI_Training.md) | Grepping, diffing, feeding to a tool. 8,415 lines. |
| **Modular tree** | [`docs/`](docs/README.md) | Editing one topic without touching the rest. 19 files. |

All three are generated from the same source and carry identical content:
the 11 playbooks plus all 34 CUDA Python sample documents, corrected and
annotated with what actually happened when each was run here.

## What is here

```
MIT_AI_Training/
├── MIT_AI_Training.html      browsable manual (420 KB, self-contained)
├── MIT_AI_Training.md        the same manual as one markdown file
├── docs/                     the same manual, sliced into 19 files
│   ├── 01-hardware-dossier.md        measured specs + raw captures
│   ├── 02-setup-environments.md      layout, venv policy, runnability matrix
│   ├── 03-playbooks/                 the 11 playbooks, one file each
│   ├── 04-cuda-curriculum/           34 samples, grouped by category
│   └── 05-verification.md            what was proven vs carried over
├── 00-MANUAL-INDEX.md …      the original 11 playbooks, unmodified
├── cuda-samples/             the NVIDIA clone (python/ + cpp/ + build/)
└── symoneural_reinforce/     native CUDA inference engine
```

## The five findings

1. **PCIe is the bottleneck.** The GPU does Gen 5; the host caps it at **Gen 3 x8**. Measured ~6.9 GB/s up, ~7.2 GB/s down — about 1% of internal bandwidth.
2. **Resident data is fast.** **752 GB/s** measured, 84% of the 896 GB/s peak, confirmed by three independent samples.
3. **Stream overlap does nothing here** — 1.00 / 0.98 / 0.93x for 2 / 4 / 8 streams. Transfer dominates; there is nothing to hide it behind.
4. **Attack launch overhead instead.** CUDA graphs **1.91x**; privatised atomics **89.5x**.
5. **Keep `cuda-samples/python/.venv` pristine.** Isolate every extra dependency; `numba-cuda` silently downgrades numpy.

## The engine

[`symoneural_reinforce/`](symoneural_reinforce/README.md) — a from-scratch CUDA
inference and compute engine on `cuda.core` and NVRTC-compiled C++ kernels. No
third-party inference runtime is wrapped.

```bash
cd symoneural_reinforce
./scripts/run_tests.sh --bench      # builds an isolated /tmp venv; never touches yours
```

67 tests pass, 1 waives (P2P needs a second GPU). Benchmarks land within 1–7% of
the dossier figures for copy, reduction, transpose and host transfer.
