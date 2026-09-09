# Performance roadmap

The order of work, and the reason each phase comes where it does. Phases are
sequential because several of them are worthless out of order — a bake-off run
before the hardware floor is known produces numbers nobody can attribute.

> ## Do NOT change the production stack during P0–P4.
>
> This is the standing constraint on the whole first half of the roadmap.
> P0–P4 are **measurement**. Changing the serving stack while measuring it
> destroys the baseline the measurements are being compared against, and the
> damage is not recoverable by re-running — the earlier numbers were taken on a
> configuration that no longer exists. Selection happens at **P6**, after the
> evidence exists. Integration happens at **P7**.
>
> **P1.5 and P1.6 sit inside that constraint.** They were inserted after P1 was
> accepted, and the rule covers them exactly as it covers the numbered phases:
> both were measurement and acquisition only, and neither changed the production
> stack, the driver, CUDA, the kernel or any service.

---

## P0 — Historical evidence recovery

Recover the exact prior CUDA Samples, vLLM, llama.cpp and stable-diffusion.cpp
configurations already present in archives and on disk.

**First because it is the cheapest phase and the only one that gets more
expensive by waiting.** Some of this work has been done before on this hardware,
and a recovered configuration is worth more than a fresh guess: it carries the
flags somebody already found to matter. It is also perishable — archives get
pruned and disks get cleaned.

What matters is recovering the *configuration*, not the numbers. A prior figure
with no provenance cannot be carried forward (`PERFORMANCE-POLICY.md` §6); a
prior flag set can be re-run today and re-measured honestly.

## P1 — Current hardware baseline

Run CUDA Samples against the current driver and CUDA state.

**The control for everything after it.** Without a current hardware floor, an
engine result cannot be separated from a driver regression, a thermal condition
or a clock policy. If P1 disagrees with what the hardware did historically, that
is a finding in its own right and it must be resolved before any engine is
judged — otherwise every later number inherits the discrepancy.

## P1.5 — NVIDIA performance toolchain qualification — **COMPLETE**

Inventory what the host already has, and acquire the public source trees P2+ will
need — without installing an engine, loading a model or pulling a container.

**Committed at `b512ae3`, tagged `performance/p15-nvidia-toolchain-20260824`.**

Inserted between P1 and P2 rather than folded into either, because it answers a
question neither of them does: *what is already here.* The answer changed the P2
plan in both directions. Nsight Systems 2026.1.3.425 and Nsight Compute 2026.2.1.0
turned out to be **already installed** as CUDA 13.3 packages, and cuDNN 9.19.0.56
and NCCL 2.28.9 are present as pip wheels invisible to `dpkg` — so several
planned acquisitions were unnecessary. In the other direction, the TensorRT-RTX
GitHub tree holds **only `demo/` and `samples/`**, so the SDK is absent despite
the clone succeeding, and NGC authentication is **not configured**.

Twelve source trees acquired under ignored `sources/`, all `dirty=0`, nothing
selected. It also corrected a carried architectural assumption: **TensorRT-LLM 1.2
removed the TensorRT execution backend** and runs on PyTorch, so evaluating it
does not require the absent TensorRT SDK.

## P1.6 — NVIDIA NVBandwidth forward PCIe baseline — **COMPLETE**

Establish an NVIDIA-authored, reproducible forward PCIe bandwidth reference.

**Annotated completion tag: `performance/p16-nvbandwidth-20260824`.**

Measurements complete, raw evidence frozen and hashed.

NVBandwidth **v0.10.0** @ `82fc4e8c`, pristine Release build for `sm_120`:
**H2D CE 6.9320 GB/s (88.0 %)** and **D2H CE 7.2100 GB/s (91.5 %)** of the Gen 3
×8 theoretical ceiling.

**LINK HEALTHY AT NEGOTIATED GEN3 ×8.** P1.6 independently reconfirms P1's Gen 3
×8 under-load observation. **Why the platform negotiates ×8 rather than the
reported ×16 maximum remains unresolved and is outside P1.6.**

This does **not** replace the historical CuPy Grade-A figures or P1's own
CUDA-runtime characterisation. There are now three separate implementations of the
same physical measurement, agreeing within half a percentage point, and all
cross-implementation comparisons remain **DIRECTIONAL ONLY** — close agreement is
not proof of equivalent timing and allocation semantics.

## P2 — Chat engine bake-off

Tune each serious LLM serving candidate and compare.

Governed by `PERFORMANCE-POLICY.md` §2: **each contender gets a real tuning
pass**. A default-configured engine measured against a tuned one tells you which
engine somebody cared about, not which engine is faster.

## P3 — Image engine bake-off

The same discipline for image generation.

Separate from P2 rather than merged because the candidates barely overlap, the
metrics differ (there is no TTFT or decode rate for a single image), and the VRAM
profile is different enough that a shared harness configuration would be wrong
for one of them.

## P4 — Saturation finder

Push each finalist until throughput materially flattens.

Governed by `PERFORMANCE-POLICY.md` §3. The deliverable is **not** a breaking
point: it is the knee where additional concurrency stops buying throughput and
starts buying only latency. Hard failure is recorded as a secondary observation.

Only finalists reach this phase. Saturation-finding is the most expensive
measurement in the roadmap and there is no value in mapping the saturation curve
of an engine already eliminated on low-load performance.

## P5 — Full application workload

Run a DispatchOS / Donnie-style workload against the finalists.

Synthetic token throughput and real application behaviour diverge, and they
diverge in the direction that matters: real requests arrive in bursts, carry
uneven prompt lengths, and interleave with non-AI work competing for the same
host. An engine that wins P2 can lose P5, and P5 is the one that resembles
production.

## P6 — Production selection

Select the engine or engines **by measurement**.

The decision is written down with the evidence that drove it, including what the
runner-up did better. Where finalists land within ~10% on the important metrics,
`PERFORMANCE-POLICY.md` §4 applies and the tie-breakers decide.

This is the first phase permitted to change what production will run — and it
changes a *decision*, not yet a deployment.

## P7 — SyMoNeuRaL integration

Put the selected engines behind stable SyMoNeuRaL adapters and interfaces.

The adapter boundary is the point of this phase. If the chosen engine is
addressed directly from application code, replacing it later means touching the
application — which is how a measured choice becomes a permanent one regardless
of what the next measurement says. An interface keeps P6 revisitable.

## P8 — Full-server certification

The final benchmark before Donnie launch: the whole server, integrated, under
the real workload.

Separate from P5 because P5 measures a finalist and P8 measures **the shipped
system** — adapters, application, and everything else on the box competing for
the same GPU and the same host. It is the last point at which an integration
regression can be caught before a customer finds it.

---

## Where the frozen custom research sits

Nowhere on the critical path. It is preserved at
`research/custom-runtime-freeze-20260824` (`44863110`) and may be measured at P2
as a historical reference point. It is **not** a launch requirement and it has no
privileged status at P6.

## What is not in this roadmap

No predicted winner, and no phase that assumes one. `engines/CANDIDATES.md`
carries every candidate at the same status for the same reason: a prediction
recorded before the measurement becomes the thing the measurement is compared
against.
