# results/

Accepted summaries and result manifests.

**Small accepted summaries are tracked here. Raw output is not.** `results/raw/`
and `results/tmp/` are ignored; this directory's own tracked files are the
findings.

That split is deliberate and is the point of the directory:

- a **summary** is a conclusion, belongs in the history beside the configuration
  that produced it, and is small enough to diff;
- a **raw sample stream** is regenerable bulk that would swamp the history and be
  read by nobody.

Tracked here: comparison tables, accepted per-run summaries, result manifests
(CSV / JSON / Markdown).

Not tracked: raw harness output, per-sample telemetry dumps, engine logs.

**Every accepted result must name its raw report path and that report's SHA256**
(`PERFORMANCE-POLICY.md` §6). The path points outside git; the hash is what makes
the summary checkable against a file this repository does not carry. A summary
without them is an assertion.

Also required before a figure becomes a headline: repeated-run evidence. A
boundary observed once is an anecdote, and an unconfirmed observation is reported
as unconfirmed rather than rounded into a result.
