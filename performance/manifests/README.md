# manifests/

Exact environment, engine, model and benchmark provenance.

**This directory is what makes a number checkable.** `PERFORMANCE-POLICY.md` §6
is explicit that a benchmark result is not valid without its configuration, and
this is where the identity half of that requirement lives: what exactly was
running, built from what, against which model revision, on which driver.

Belongs here:

- environment snapshots (driver, CUDA, kernel, Python, key libraries)
- engine provenance: upstream project, commit, build flags
- model provenance: revision or digest, format, quantisation
- benchmark run manifests, including raw report path and its SHA256
- `ORIGIN.md` — where this repository came from

**Why the raw report is hashed rather than stored.** The report lives outside git
under ignored `results/raw/`. Storing it would bloat the history with
regenerable bulk; storing nothing would make the summary unfalsifiable. The
SHA256 lets anyone verify the summary against the file without this repository
carrying it.

The standing hazard this directory exists to prevent: a figure carried forward
and re-dated. A number with a fresh date and a stale provenance is worse than no
number, because it looks current. Re-measure or drop it.
