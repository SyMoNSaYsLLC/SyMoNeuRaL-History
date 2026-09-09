# engines/

Adapter and configuration documentation for each candidate engine.

**Actual source checkouts live under ignored `sources/`.** Nothing in this
directory is an upstream source tree, and nothing here should become one.
`.gitignore` states the reasoning: vendoring upstream projects would fork them
silently at whatever commit we happened to clone, mix their licence obligations
into ours with no record of provenance, and make this repository enormous. What
is tracked instead is the commit and the flags — from which a checkout can be
recreated, where the reverse is not true.

Belongs here, per engine:

- how it is built on this hardware, and which flags matter
- how it is launched and configured
- how it is driven through the harness's common interface
- known constraints, quirks and failure modes observed here
- notes on what a reasonable tuning pass consists of for it

`CANDIDATES.md` is the register of what is under consideration. Every row
currently reads `NOT YET BENCHMARKED IN THIS REPOSITORY`, and a row moves only
when a measurement exists that satisfies `PERFORMANCE-POLICY.md` §6.
