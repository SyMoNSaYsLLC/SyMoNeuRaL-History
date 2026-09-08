# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""Keccak-f[800] and Keccak-f[1600], written from the published specification.

## Provenance, because it is the whole point of this file

Written from **FIPS PUB 202** (SHA-3 Standard, NIST, August 2015) and the Keccak reference
specification, both public documents. The round constants and rotation offsets below are
mathematical constants defined by that specification — the round constants are the output of
a linear feedback shift register the standard defines, and the rotation offsets are a fixed
table in it. Reproducing a specification's constants is not copying an implementation.

No line here was taken from, adapted from, or checked against `kawpowminer`,
`cpp-kawpow`, `ethash`, or any other implementation's source. The correctness evidence is
the specification's own test vectors, in `tests/test_keccak.py`.

## Why f[800] and not just f[1600]

KawPoW — the Ravencoin variant of ProgPoW — uses the **800-bit** Keccak permutation for its
header hash, with a 32-bit lane width, where SHA-3 proper uses 1600 bits and 64-bit lanes.
The permutation is the same algorithm at a different width: 22 rounds instead of 24, and
`rot` taken modulo 32 instead of 64. Both are implemented here so the width difference is
visible rather than buried in a parameter.

## What this file is NOT

It is not KawPoW. KawPoW is Keccak-f[800] **plus** the ProgPoW random-program loop over a
DAG, and that loop is the part this repository does not yet implement first-party. See
`docs/ALGORITHM-GAP.md`. Nothing here should be read as a mining implementation.
"""
from __future__ import annotations

#: Rotation offsets for rho, indexed [x][y]. Fixed table from FIPS 202 §3.2.2.
_RHO = (
    ( 0, 36,  3, 41, 18),
    ( 1, 44, 10, 45,  2),
    (62,  6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39,  8, 14),
)

#: Round constants for iota. FIPS 202 §3.2.5 defines these as rc(t) from an LFSR; they are
#: computed here rather than pasted, so the file carries the definition and not a copy of
#: somebody's table. Verified against the published values by the test suite.
def _round_constants(rounds: int, lane_bits: int) -> tuple[int, ...]:
    """rc values per FIPS 202 Algorithm 5 (`rc`) and §3.2.5 (`iota`)."""
    out = []
    lfsr = 1
    mask = (1 << lane_bits) - 1
    for _ in range(rounds):
        rc = 0
        for j in range(7):                      # l = 6 for w = 64; bits at 2**j - 1
            bit_pos = (1 << j) - 1
            if lfsr & 1:
                if bit_pos < lane_bits:
                    rc ^= 1 << bit_pos
            # LFSR: x^8 + x^6 + x^5 + x^4 + 1, per the standard
            lfsr <<= 1
            if lfsr & 0x100:
                lfsr ^= 0x171
        out.append(rc & mask)
    return tuple(out)


RC_1600 = _round_constants(24, 64)
RC_800 = _round_constants(22, 32)


def _permute(state: list[int], lane_bits: int, rounds: int, rc: tuple[int, ...]) -> None:
    """Keccak-p[b, rounds] in place. `state` is 25 lanes of `lane_bits` bits.

    The five step mappings in the order the specification gives them: theta, rho, pi, chi,
    iota. Written straightforwardly rather than unrolled — this is the reference against
    which a future kernel is checked, so being readable matters more than being fast.
    """
    mask = (1 << lane_bits) - 1

    def rol(v: int, n: int) -> int:
        n %= lane_bits
        return ((v << n) | (v >> (lane_bits - n))) & mask if n else v

    for rnd in range(rounds):
        # theta
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20]
             for x in range(5)]
        d = [c[(x - 1) % 5] ^ rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] ^= d[x]

        # rho and pi combined, as the specification permits
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = rol(state[x + 5 * y], _RHO[x][y])

        # chi
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y] & mask)
                                                   & b[(x + 2) % 5 + 5 * y])

        # iota
        state[0] ^= rc[rnd]


def keccak_f800(state: list[int]) -> list[int]:
    """Keccak-f[800]: 25 lanes of 32 bits, 22 rounds. The permutation KawPoW uses."""
    if len(state) != 25:
        raise ValueError(f"Keccak-f[800] takes 25 lanes, got {len(state)}")
    s = [v & 0xFFFFFFFF for v in state]
    _permute(s, 32, 22, RC_800)
    return s


def keccak_f1600(state: list[int]) -> list[int]:
    """Keccak-f[1600]: 25 lanes of 64 bits, 24 rounds. SHA-3's permutation."""
    if len(state) != 25:
        raise ValueError(f"Keccak-f[1600] takes 25 lanes, got {len(state)}")
    s = [v & 0xFFFFFFFFFFFFFFFF for v in state]
    _permute(s, 64, 24, RC_1600)
    return s


def sha3_256(data: bytes) -> bytes:
    """SHA3-256 per FIPS 202: pad10*1 with the 0x06 domain suffix, rate 1088 bits.

    Present so the permutation above can be checked against the standard's own published
    digests, which is stronger evidence of correctness than any internal test could be.
    """
    rate = 136                                   # (1600 - 2*256) / 8
    s = [0] * 25
    buf = bytearray(data)
    buf.append(0x06)                             # SHA-3 domain separation + start of pad
    while len(buf) % rate != 0:
        buf.append(0x00)
    buf[-1] |= 0x80                              # final pad bit

    for off in range(0, len(buf), rate):
        block = buf[off:off + rate]
        for i in range(rate // 8):
            s[i] ^= int.from_bytes(block[i * 8:(i + 1) * 8], "little")
        s = keccak_f1600(s)

    out = bytearray()
    while len(out) < 32:
        for i in range(rate // 8):
            out += s[i].to_bytes(8, "little")
            if len(out) >= 32:
                break
        else:
            s = keccak_f1600(s)
    return bytes(out[:32])
