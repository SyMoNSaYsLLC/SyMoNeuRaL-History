# symoneural-adaptive-fabric

**PLANNED. NOT_IMPLEMENTED. There is no code here yet, and this file does not pretend
otherwise.**

The folder exists because the component is real in the architecture and was missing a home.
Its status is quoted, not summarised, from the repo's own maps.

## What the maps say

`docs/architecture/COMPONENT-MAP.tsv:15`:

```
COMPONENT_ID           symoneural-adaptive-fabric
CANONICAL_NAME         Symon Adaptive Fabric
COMPONENT_CLASS        PLANNED
IMPLEMENTATION_STATUS  NOT_IMPLEMENTED
PRODUCTION_STATUS      NOT_IN_RELEASE
SOURCE_ROOT            -
PRODUCTION_ROLE        design proposal only
OPEN_BLOCKER           not-implemented
```

## The seven subcomponents

From `docs/architecture/ALIASES.tsv:7-13`, each recorded as `PLANNED_SUBCOMPONENT` with
**0 tracked matches in source**:

| Subcomponent | Recorded note |
|---|---|
| Symon Hardware Profiler | 0 tracked matches in source; design proposal only |
| Symon Model Advisor | 0 tracked matches in source |
| Symon Placement Policy | 0 tracked matches in source |
| Symon Residency Manager | 0 tracked matches in source |
| Symon Transfer Policy | 0 tracked matches in source |
| Symon Prefill Pipeline | 0 tracked matches in source |
| Symon Memory Governor | 0 tracked matches in source; **distinct from `scripts/gpu-governor.sh`, which IS implemented** |

That last note is the one to read twice. There is a working GPU governor in this repo, and
it is **not** this. Anyone who reads "Memory Governor" and points at `gpu-governor.sh` has
found a different component that already exists — which is exactly the kind of substitution
that lets a planned thing be reported as done.

## Adjacent things that already work

Naming these here so the gap is precise rather than vague:

- `scripts/gpu-governor.sh` — GPU residency and eviction. Implemented and in use.
- `bin/symoneural-cli residency` — reports residency now.
- `ops/manifests/` — artefact identity, which a Placement Policy would need to read.

## Status vocabulary

Per `.claude/CLAUDE.md`, this component is **DEFINED**: named in the architecture, with no
implementation claim. Creating this directory does not advance it to PRESENT, and a folder
is not a runtime. When code lands here, `docs/architecture/COMPONENT-MAP.tsv` is the file
that changes to say so — and it changes on measured evidence, not on this README.
