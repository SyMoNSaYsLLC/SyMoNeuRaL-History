# scripts/

Reproducible setup, build, run and measurement scripts.

**Reproducible is the operative word.** A benchmark that was produced by
commands typed once into a terminal cannot be re-run, and a result that cannot
be re-run cannot be confirmed — which `PERFORMANCE-POLICY.md` §6 requires for
anything that becomes a headline figure.

Belongs here: environment preparation, engine build steps, launch wrappers,
measurement drivers, snapshot collectors.

Three constraints, each learned the expensive way elsewhere in this project:

1. **A script that mutates production state does not belong in this repository.**
   Nothing here changes services, Caddy, systemd, drivers, CUDA or system
   packages. The roadmap's P0–P4 constraint depends on that being true by
   construction rather than by care.

2. **State what a script does before it does it.** A destructive step whose only
   warning is a comment is a step somebody will run without reading. Prefer a
   dry-run default and an explicit flag to act.

3. **Print the identity of what was run.** A script that produces a measurement
   should emit the versions, commits and flags it used, so the manifest is a
   product of the run rather than a transcription of it. A transcribed hash
   proves nothing.
