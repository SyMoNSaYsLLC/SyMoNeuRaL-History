# benchmarks/

Benchmark definitions and comparison methodology.

**The definition is separate from the runner on purpose.** `harness/` is the code
that generates load; this directory is *what load, against what, measured how,
and what counts as comparable*. Keeping them apart means a benchmark can be
re-run by a different harness without silently becoming a different benchmark.

Belongs here:

- workload definitions: prompt distributions, request mixes, concurrency ladders
- what each metric means and how it is derived
- the rules that make two runs comparable
- the acceptance criteria for a valid result

Every definition here has to satisfy `PERFORMANCE-POLICY.md` §3: load rises
until throughput materially flattens, requested and achieved concurrency are
recorded separately, and the saturation knee is reported distinctly from the
eventual hard failure.

A benchmark whose definition changed between two runs has produced two results
that must not be compared. Version the definition, not just the numbers.
