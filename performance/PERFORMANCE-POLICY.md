# Performance policy

The rules a measurement in this repository has to satisfy to count. They exist
because the failure mode here is not "we picked a slow engine" — it is **"we
picked an engine on evidence that did not mean what it appeared to mean"**, and
that failure is invisible until production load finds it.

Every section below is a rule, not an aspiration. A result that breaks one is
not a weaker result; it is inadmissible, and re-running it later costs more than
following the rule the first time.

---

## 1. Performance first

Use any engine, library, kernel or tool that is legally usable for the hosted
service and that performs.

**Do not favour internally-written code merely because it is custom.** This is
stated as a rule rather than left to judgement because the pull is real: custom
code is understood, its author is available, and it feels like an asset. None of
that is throughput. The frozen SyMoNeuRaL native runtime enters as a *historical
challenger* — it may be measured for reference, and it has no claim to win.

The converse also holds. An upstream project is not automatically faster because
it is popular or because a vendor benchmark says so. Vendor figures are measured
on vendor hardware under vendor conditions; this box is the only authority on
this box.

## 2. Best configuration versus best configuration

**Each serious contender gets a reasonable tuning pass before it is compared.**

A tuned engine measured against a default-configured one is not a comparison of
engines — it is a comparison of *effort*, and it will reliably tell you that
whichever engine somebody cared about is the better engine. That result feels
earned and is worthless.

Concretely: if a contender is going to be rejected, it must be rejected in a
configuration its own upstream documentation would recognise as reasonable. If
the tuning pass for one candidate was materially deeper than for another, that
asymmetry is itself a finding and must be recorded beside the numbers.

Record, per contender, and treat a missing field as an incomplete result rather
than a tidy-up task for later:

- exact upstream project
- exact version / commit
- exact build flags
- exact runtime flags
- model revision
- model format
- quantisation
- CUDA version
- driver version
- attention backend
- batching settings
- KV-cache settings
- speculative-decoding settings
- relevant environment variables

The reason the list is this long is that most of these silently change the
answer. An attention backend or a KV-cache setting can move throughput further
than the choice of engine, so a comparison that does not name them is not
comparing what it claims to compare.

## 3. Saturation, not just failure

**Increase load until the throughput curve flattens.** The production boundary
that matters is the point where additional concurrency stops buying throughput
and starts buying only latency. Hard failure is a *secondary* observation: it
tells you where the software breaks, not where the service stops being good.

An engine that survives to 200 concurrent requests while delivering its peak
throughput at 24 has a capacity of 24 for planning purposes. Reporting the 200
would be true and misleading, which is the worst combination a figure can have.

Measure at minimum:

| | |
|---|---|
| load | requested concurrency · achieved concurrency |
| throughput | throughput · decode tokens/sec · prefill throughput (when available) |
| latency | p50 · p95 · p99 · TTFT (when available) · queue delay |
| GPU | utilisation · VRAM · power · temperature |
| host | CPU · RAM |
| failure | error rate · timeout rate |

**Requested and achieved concurrency are separate fields on purpose.** A level
that requested 64 and achieved 40 measured 40, and quoting it as 64 is the
single easiest way to publish a capacity number that was never true.

Identify separately, and do not collapse them into one headline:

- low-load performance
- engineering knee
- throughput saturation knee
- latency acceleration region
- first bottleneck
- eventual hard failure

Those are six different questions. A single "capacity" number answers none of
them well.

## 4. The 10 percent tie rule

When two practical production candidates land within approximately 10% on the
important workload metrics, treat them as tied on speed and decide on:

- reliability
- repeatability
- latency consistency
- VRAM efficiency
- startup time
- teardown / recovery
- operational simplicity
- integration effort
- maintainability

Why a band at all: a 6% throughput edge measured once, on one workload, on one
afternoon, is inside the noise of most of the variables in §2. Treating it as
decisive is false precision — and it would let an engine win on a rounding error
while being materially worse to operate.

**This is not a protection rule for custom code.** It is a tie-breaker between
genuine finalists, and "we wrote it" is not on the list above.

## 5. Hosted-service licensing

The goal is not to protect a custom runtime. The goal is narrower: establish
that each dependency and model **may be used for the intended hosted service**,
and record what notices or obligations come with it.

**Do not assume server-only use eliminates every obligation.** It is a common and
expensive assumption. Serving over a network is not distribution under most
licences, but some carry network-use or attribution terms that apply anyway, and
model weights frequently carry use restrictions that have nothing to do with
distribution at all. The question is never "did we ship a binary" — it is "what
does this specific licence require of this specific use".

Record per component:

- component
- version / commit
- licence
- modified / unmodified
- hosted-service considerations
- distribution considerations
- required action / notices

`modified / unmodified` is tracked because it changes the obligation under
several licences, and because it is the field nobody can reconstruct later: a
patched engine in `sources/` looks identical to a clean one once the reason for
the patch is forgotten.

## 6. Reproducibility

**A benchmark result is not valid without its configuration.** A number with no
provenance is an anecdote, and this project has already learned that a figure
carried forward and re-dated is worse than no figure — it is a false claim with a
plausible date on it.

Every accepted result must be tied to:

- Git commit (of this repository)
- engine source commit / version
- model revision
- configuration
- hardware snapshot
- environment snapshot
- raw report path
- report SHA256
- summary CSV / JSON
- repeated-run evidence where appropriate

The raw report lives **outside** git under ignored `results/raw/`, and its
**SHA256 is tracked**. That is deliberate: storing the file would bloat the
history, and storing nothing would make the summary uncheckable. The hash makes
the claim verifiable against a file this repository does not have to carry.

"Repeated-run evidence where appropriate" means: a boundary observed once is an
anecdote. Anything that becomes a headline figure — a selected engine, a quoted
capacity, a saturation knee — needs independent repeats, and an unconfirmed
observation is reported as unconfirmed rather than rounded into a result.

---

## What this policy does not do

It does not pick an engine. It does not rank the candidates. It does not predict
which will win, and no document in this repository should — a prediction written
down before the measurement becomes the thing the measurement gets compared
against, and that is how a bake-off acquires a favourite.

`engines/CANDIDATES.md` therefore lists every contender with the same status:
`NOT YET BENCHMARKED IN THIS REPOSITORY`.
