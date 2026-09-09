# Origin manifest

Where this repository came from and what it was separated out of, recorded at
initialization so the boundary is checkable later rather than remembered.

Written 2026-08-24. Every hash below was read off disk at that time, not carried
forward from a prior document.

---

## Production baseline

```
repo:  /home/google/Symoneural
main:  7d1a5529
```

The shipped application: the site, the API, the live surfaces. **This repository
does not modify it.** Confirmed clean at the initialization commit.

## Frozen custom research

```
path:    /home/google/SyMoNeuRaL-Projects/Symoneural-Custom
branch:  research/custom-runtime-freeze-20260824
HEAD:    44863110
```

Evidence tags, both annotated:

```
research/native-runtime-freeze-20260824       -> 1016a956
research/trusted-firmware-scaffold-20260824   -> 44863110
```

The custom/native runtime line, frozen after the Slice 3 integrity guards. That
worktree is **locked** against pruning, and the branch plus both tags keep
`44863110` reachable independently of any worktree.

Its relationship to this repository is one-directional and thin: this repository
*names* the freeze so the lineage is legible, and depends on none of it. The
native runtime is a historical challenger in `engines/CANDIDATES.md` with no
standing — see `PERFORMANCE-POLICY.md` §1.

## Performance lab

```
path:    /home/google/SyMoNeuRaL-Projects/Symoneural-Performance
branch:  main
remote:  none, deliberately
```

---

## Reason for a new repository

**Separate performance-first runtime selection from production application
development and custom-runtime research.**

Three concerns were previously entangled in one history, and each was distorting
the others:

1. **Production development** ships to real users and cannot absorb the churn of
   an engine bake-off. A benchmark that needs a service restarted is
   incompatible with a service that is answering requests.

2. **Custom-runtime research** carries an implicit thesis — that runtime code
   written here is worth writing. That thesis is legitimate as research and
   corrosive as a starting assumption for a selection process. Keeping it in the
   same repository would have made every bake-off partly a referendum on it.

3. **Performance selection** needs to be free to conclude that an upstream
   project wins outright and that nothing written here should serve production.
   That conclusion is much harder to reach inside a repository whose history is
   the custom runtime.

Separation makes the third conclusion reachable without the first two objecting,
which is the whole point. It also gives each repository one clear question:
*what do we ship* / *what did we learn* / *what is fastest*.

## What was NOT copied

**No source code was copied during initialization.** Not from the production
repository, not from the frozen research. This repository begins with
documentation and empty directories only.

The `capacity-lab` harness in the frozen research is a known, working,
engine-neutral load generator, and copying it would have been the obvious
shortcut. It was not taken. If any of it is wanted here it should arrive as a
deliberate, reviewed port with its provenance recorded — not as an unattributed
paste that quietly makes this repository a fork of the research line it was
created to be independent of.

## Verified unchanged at initialization

Recorded because "we did not touch it" is a claim, and a claim needs a reading:

| | State at init |
|---|---|
| `/home/google/Symoneural` `main` | `7d1a5529`, clean |
| Custom worktree HEAD | `44863110`, clean, locked |
| `research/native-runtime-freeze-20260824` | annotated tag → `1016a956` |
| `research/trusted-firmware-scaffold-20260824` | annotated tag → `44863110` |
| `symoneural-api` · `caddy` · `symoneural-gateway` | all `active`, PIDs unchanged |
| Port 8811 | not listening |
| `chat_worker.py` / `image_worker.py` | none running |
| GPU compute applications | none |

No service was started, stopped or reconfigured. No driver, CUDA, or package
state was altered. No model was downloaded or loaded. No engine was cloned.
