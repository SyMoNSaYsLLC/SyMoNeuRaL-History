# symoneural-miner-core

First-party miner layers: the parts that can be written from public specifications and
verified, without deriving from anyone's implementation. **Tracked, and ours.**

**This is not a complete miner.** The KawPoW hash and its GPU kernel are not implemented
here. `docs/ALGORITHM-GAP.md` states exactly where the line is and why — read it before
citing this directory as a first-party miner.

## What is here

```
src/symoneural_miner_core/keccak.py    Keccak-f[800] and f[1600] from FIPS PUB 202
src/symoneural_miner_core/config.py    fail-closed configuration and strict validation
src/symoneural_miner_core/stratum.py   Stratum client: JSON-RPC over TCP
src/symoneural_miner_core/fakepool.py  a loopback pool fixture that also misbehaves
bin/symoneural-miner-smoke             end-to-end smoke; writes SMOKE-miner-core.md
tests/                                 51 tests
```

## Run it

```bash
python3 -m pytest symoneural-miner-core/tests/ -q      # 51 tests
symoneural-miner-core/bin/symoneural-miner-smoke       # end-to-end, loopback only
```

The smoke does more than print a version: it arms a validated config, completes a Stratum
handshake against a local pool, receives real work, derives a deterministic candidate with
our own Keccak, formats and submits a share, has it accepted, and shuts down releasing the
socket. 13 checks. It writes `SMOKE-miner-core.md`, which cannot be written honestly
without running the thing.

## Nothing arms by default

No pool, no wallet, no worker, or no `SYMONEURAL_MINER_ENABLED=1` means no mining. The
enable flag must be the **literal string `1`** — `true`, `yes` and `on` are refused, and
that is tested. A non-loopback endpoint needs `SYMONEURAL_MINER_ALLOW_PUBLIC_POOL=1` as a
second deliberate step, which is a guardrail under the owner's authorisation and not a
substitute for it.

**No test or smoke contacts a public pool, uses a real wallet, or submits a real share.**
`fakepool.py` binds `127.0.0.1` as a class constant with no code path that changes it.

## Provenance

Written from FIPS PUB 202 and the public Stratum protocol description. Not derived from
`kawpowminer`, `cpp-kawpow`, `ethash`, or any other implementation. The correctness evidence
for the primitive is the standard's own published test vectors, plus an independent
cross-check against `hashlib` — used in tests only, never on the runtime path.

Platform dependencies are listed in `docs/ALGORITHM-GAP.md` and are explicitly **not**
claimed as first-party.

## Relationship to `symoneural-miner/`

`symoneural-miner/` is the runtime `backend/apps/cryptominer/` actually invokes. It is a
derivative of GPL-3.0 `kawpowminer` and `tools/fork_engines.sh` refuses to stamp our licence
on it. This directory does not replace it and does not link against it: there is no import,
no exec, and no build dependency in either direction.
