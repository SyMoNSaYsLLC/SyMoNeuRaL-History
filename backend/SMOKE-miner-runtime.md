# Smoke readings — the miner runtime, driven by actually running it

`apps/cryptominer` is structural about its engine: it holds a path and refuses to turn it into a
running process. Nothing in its 98 passing tests can tell you the binary at the end of that path
exists, and for a long time it did not — `KAWPOW_BINARY` named `contrib/kawpowminer/...`, and
`/contrib` is gitignored. This file is the other half.

**Measured 2026-09-04**, on `e97ad901` plus the working tree that became the commit this file
arrives in. The engine did not exist under our name before that tree, so nothing here is carried
forward from an earlier reading.

## What was built, and from what

`tools/fork_engines.sh miner` — tracked, so this is reproducible rather than a binary somebody
made by hand once. Source and every dependency are vendored, so the build needed **no network**:

| Input | Version |
|---|---|
| kawpowminer | 1.2.4 (RavenCommunity) |
| cpp-kawpow | 1.1.0 — where the KawPow hash itself lives |
| boost | 1.83.0, static |
| jsoncpp | 1.8.0, static |
| CLI11 | 1.8.0 |

The dependency prefix is **copied into the engine**, not pointed at under `references/`. They are
static, so nothing is loaded from there at runtime either way — copying makes the engine
independent of the read-only tree at *build* time too, which is what first-party has to mean.

## The reading that matters

```
$ engines/symoneural-miner/build/kawpowminer/symoneural-miner --version
SyMoNeuRaL Miner 1.2.4
Build: linux/release/gnu
```

exit 0. **It runs, and it announces our name.** A file of the right size proves neither.

| | |
|---|---|
| artefact | `engines/symoneural-miner/build/kawpowminer/symoneural-miner` |
| bytes | 6,218,920 |
| CUDA | `COMPUTE=120` (sm_120), `ETHASHCUDA=ON`, `ETHASHCL=OFF` |
| RUNPATH | `/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs:` |

`CMAKE_BUILD_RPATH_USE_ORIGIN=ON` was set and correctly did **not** rewrite that RUNPATH:
`$ORIGIN` can only make *build-tree* paths relative, and these are the system CUDA toolkit, which
is at the same absolute path on any machine that has it. This is unlike `symoneural-diffuse`,
whose absolute RUNPATH *is* a relocatability problem.

## Identity — checked in both directions

- **Ours is present:** `SyMoNeuRaL Miner 1.2.4` and
  `SyMoNeuRaL Miner - GPU ProgPOW(0.9.3) miner for Zing` in the shipped binary.
- **Theirs is gone:** no `kawpowminer - GPU ...` banner survives, and **no executable named
  `kawpowminer` exists anywhere in the build tree**. That second check is the one that matters:
  the vendored source ships a working binary from 2026-08-17 under the third-party name, and
  that binary is precisely what must not be what we ship.

`project()` is deliberately **not** renamed. Unlike llama.cpp, `PROJECT_NAME` is load-bearing
here — `CMakeLists.txt` feeds it to `cable_add_buildinfo_library` and `CPACK_PACKAGE_FILE_NAME` —
so renaming it would rewrite generated build-info symbols for a name no user ever sees. The
exception is stated rather than taken silently.

## What the surface sees now

```
KAWPOW_BINARY: /home/google/Symoneural/engines/symoneural-miner/build/kawpowminer/symoneural-miner
exists: True   executable: True
unit_state(): ('offline', 'disabled — copy miner.env.example to miner.env and set ...')
```

**`offline` here is correct and must stay correct.** Mining is off until an operator configures
it, and `KAWPOW_BINARY` is a signpost quoted back by `selftest()` — no code path turns it into a
process. An unconfigured box that started hashing because a binary appeared would be the exact
failure this surface is built to prevent. What changed is that the signpost now points at
something that exists; what did not change is that nothing runs it.

## What this file does NOT claim

- **No hashrate.** No benchmark was run and none is reported. This repo has a 52–53 MH/s figure
  on record from an earlier binary; carrying it forward beside a newly built one and re-dating it
  is the single failure `.claude/CLAUDE.md` warns about most, and the fact that both binaries are
  6,218,920 bytes is a reason to be *more* careful about that, not less.
- **No GPU work of any kind was performed.** `--version` does not initialise CUDA. The governor
  lock was never taken and the card was never held.
- **Nothing was enabled.** No `miner.env` was created, no pool, no wallet, no token. Configuring
  the miner is an owner action involving money and is not an engineering one.
