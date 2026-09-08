# The algorithm gap, stated precisely

`symoneural-miner-core` is first-party. It is **not a complete miner**, and this file says
exactly where the line is, because "first-party miner" with the gap unstated would be the
relabelling this repository has been burned by before.

## What is implemented first-party, from public specifications

| Layer | Source of truth | Evidence |
|---|---|---|
| **Keccak-f[800] and f[1600]** | FIPS PUB 202 (NIST, Aug 2015) — round constants computed from the standard's LFSR, rotation offsets from its table | 11 tests; published SHA3-256 vectors; cross-check against `hashlib` across the 136-byte rate boundary |
| **Stratum client** | the public Stratum mining protocol: newline-delimited JSON-RPC 2.0, `mining.subscribe` / `authorize` / `notify` / `submit` / `set_difficulty` | 22 tests against a loopback pool fixture that also misbehaves |
| **Fail-closed configuration** | this project's own rule | 18 tests; no default arms anything |
| **Lifecycle** | — | idempotent close, bounded backoff, EOF return, socket release |

Method names and message shapes are an interoperability contract, not an implementation.
None of this was derived from `kawpowminer`, `cpp-kawpow`, `ethash`, or any other codebase.

## What is NOT implemented

**The KawPoW hash itself.** KawPoW is the Ravencoin variant of ProgPoW:

1. a Keccak-f[800] pass over the header — *implemented here*;
2. a **pseudo-random program**, regenerated every `PROGPOW_PERIOD` blocks, of ~`PROGPOW_CNT_MATH` arithmetic operations mixed with `PROGPOW_CNT_CACHE` cache reads and `PROGPOW_CNT_DAG` DAG reads — **not implemented**;
3. a **DAG**, generated from a seed hash and several gigabytes in size — **not implemented**;
4. a final Keccak pass producing the result compared against the target — *the primitive exists, the composition does not*.

**No GPU kernel.** Steps 2 and 3 are the entire performance problem, and a CPU version of
them would be correct and useless.

## Why the gap was not closed in this pass

Two reasons, both recorded rather than implied.

**It is a project, not a task.** A correct ProgPoW implementation needs the DAG generator,
the program generator, its keccak-based random source, the exact mixing schedule, and a
CUDA kernel for `sm_120`, then validation against published block solutions. That is not
something to half-finish next to a repository migration.

**The repository already reasoned about this and said no.**
`backend/apps/cryptominer/__init__.py` states it plainly:

> *"It runs an **external miner binary** you supply. It does not implement KawPow. Writing a
> competitive KawPow kernel is a project in its own right and a bad one to attempt here: the
> value in this repo is the orchestration — the governor integration, honest telemetry and a
> rack unit that tells the truth — not a slower reimplementation."*

That position may be overridden by the owner, but it should be overridden deliberately, not
by a session quietly deciding otherwise.

## The consequence for the existing runtime

`symoneural-miner/` — the built runtime that `backend/apps/cryptominer/` actually invokes —
is a **derivative of kawpowminer, which is GPL-3.0**. Measured: `symoneural-miner/LICENSE`
is the GNU GPL v3 text, and `external/contrib/build-kawpowminer.sh` clones
`RavenCommunity/kawpowminer` at 1.2.4 and compiles from that tree. `tools/fork_engines.sh`
therefore **refuses** to stamp the SyMoNeuRaL licence on it, and that refusal is tested.

So today:

- `symoneural-miner-core/` — first-party, tracked, tested. Not a miner.
- `symoneural-miner/` — a working miner. Not first-party, and cannot be made so by editing
  a licence file.

The route to one thing that is both: implement steps 2–4 above over the **Apache-2.0**
`cpp-kawpow` algorithm layer (measured: `external/referencestochatgpt/kawpow-src/cpp-kawpow-1.1.0/LICENSE`
is the Apache License 2.0), or clean-room them from the ProgPoW specification. Apache-2.0
permits linking into a proprietary product with a NOTICE; GPL-3.0 does not.

## Platform dependencies — not first-party, and not claimed to be

Nothing below is ours. Listing them is the point:

- Linux kernel and its network stack
- glibc / the system C library
- CPython 3 and its standard library (`socket`, `json`, `threading`, `ipaddress`)
- for any future kernel: the NVIDIA driver, the CUDA runtime and toolkit, and the host compiler

`hashlib` is used **only in tests**, as an independent implementation of the same published
standard to cross-check ours. The runtime path does not import it.
