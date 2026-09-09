# configs/

Tracked runtime and build configurations.

**These files are the finding.** An engine's throughput is a property of a
configuration, not of a name — attention backend, KV-cache policy, batching and
quantisation can each move the number further than the choice of engine. A
result whose configuration is not tracked here is not reproducible and is
therefore not admissible (`PERFORMANCE-POLICY.md` §6).

Belongs here: build flags, runtime flags, server configuration files,
environment variable sets, launch arguments — one identifiable set per
measured configuration.

Does not belong here: secrets of any kind. `.gitignore` excludes `.env`, keys
and certificates, but the ignore is a backstop and not a licence to write a
credential into a tracked config and rely on it.

Name configurations so a result can cite one unambiguously. "vLLM tuned" is not
a citation; a file that can be diffed against its predecessor is.
