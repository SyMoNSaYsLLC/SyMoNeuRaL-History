# harness/

Engine-neutral workload generator and telemetry code.

**Engine-neutral is the requirement, not a preference.** A harness that reaches
for one engine's client library, or assumes its metrics endpoint, has stopped
being an instrument and become part of the thing being measured. Every candidate
must be driven through the same interface, or the comparison is measuring the
harness.

Belongs here:

- the load generator
- telemetry sampling (GPU, host, process)
- result recording and manifest emission
- adapters that present each engine through one common interface

Two constraints worth stating before any code lands:

1. **The harness must measure its own materiality.** If the generator consumes a
   significant share of host CPU, it is competing with the server it is
   measuring, and the result is about the box rather than the engine. That
   fraction must be recorded per run, expressed against total host capacity.

2. **Requested and achieved concurrency are separate outputs.** A run that asked
   for 64 and achieved 40 measured 40. Conflating them is the cheapest way to
   publish a capacity figure that was never true.

Raw output goes to ignored `results/raw/`; accepted summaries are tracked in
`results/`.
