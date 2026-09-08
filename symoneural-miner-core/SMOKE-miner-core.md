# SMOKE — symoneural-miner-core

Measured 2026-09-08T04:35:52-04:00 at HEAD `544168a1`.

Loopback fixture only. **No public pool was contacted, no real wallet was used, and no share was submitted to any network.** The wallet is a shape-valid placeholder.

| Check | Result | Detail |
|---|---|---|
| empty environment refuses to arm | PASS | pool is not set |
| loopback configuration arms | PASS | stratum+tcp://127.0.0.1:45553 |
| wallet is masked in the loggable form | PASS | R999…9999 |
| stratum handshake completed | PASS | authorized as smoke |
| difficulty received | PASS | 2.0 |
| real work received from the pool | PASS | job1 |
| candidate is deterministic | PASS | fa8822e402d2e099… |
| candidate differs for a different nonce | PASS |  |
| share is correctly formatted | PASS | 0x0123456789abcdef |
| pool accepted the submitted frame | PASS | 1 submission(s) seen by the pool |
| client closed and socket released | PASS |  |
| reader thread exited | PASS |  |
| first-party Keccak matches the published SHA3-256 vector | PASS |  |

**13/13 passed.**

## What this does and does not prove

Proves: the config refuses to arm by default; a validated loopback endpoint arms; the Stratum handshake, difficulty delivery and job receipt work against a real socket; a deterministic candidate is derived from real job fields by first-party Keccak; the share is formatted as pools document; a pool accepted the frame; and the client shuts down releasing its socket.

Does **not** prove: KawPoW correctness, GPU execution, or any hashrate. The ProgPoW loop and its kernel are not implemented first-party — see `docs/ALGORITHM-GAP.md`. No hashrate figure appears in this file because none was measured.
