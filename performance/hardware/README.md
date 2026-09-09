# hardware/

Raw-host validation and the CUDA Samples baseline.

**This is the control, not a contender.** An engine benchmark cannot be
interpreted without knowing what the card does under a known-good workload: if a
serving number drops 15%, the cause is either the engine or the floor beneath it,
and only a current hardware reading separates those two.

Belongs here:

- CUDA Samples results and the exact sample set / flags used
- driver, CUDA and kernel identity at the time of each reading
- thermal and clock behaviour observed during a run
- host CPU / RAM / PCIe characterisation relevant to serving

Does not belong here: engine results (`results/`), engine configuration
(`configs/`, `engines/`).

A hardware reading is only useful with its date and the driver/CUDA state it was
taken on. A floor figure with no environment beside it cannot be compared to the
next one — which is the only thing a floor figure is for.
