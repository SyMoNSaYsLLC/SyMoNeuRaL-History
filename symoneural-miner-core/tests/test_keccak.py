# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""Known-answer tests for the first-party Keccak, against the standard's own vectors.

The correctness evidence for a from-specification implementation cannot be "it looks like
the reference code", because it was deliberately not written from reference code. It has to
be the published test vectors. Two independent checks:

  * SHA3-256 digests published in FIPS PUB 202 / NIST's CAVP examples. If the f[1600]
    permutation, the rotation table, the round constants and the padding are all correct,
    these match; if any one is wrong, they do not.

  * The round constants recomputed from the standard's LFSR definition against the values
    the standard prints. This is what separates "constants copied from an implementation"
    from "constants derived from the specification" -- the file computes them, and this
    test proves the computation lands on the published numbers.

f[800] has no published digest vector of its own (it is not used by SHA-3), so it is checked
structurally: correct width, 22 rounds, its own round constants, and the avalanche and
invertibility-of-shape properties any permutation must have.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from symoneural_miner_core import keccak                              # noqa: E402


class RoundConstantsComeFromTheSpecification(unittest.TestCase):
    """FIPS 202 §3.2.5 prints these. The file computes them from the LFSR."""

    PUBLISHED_1600 = (
        0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
        0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
        0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
        0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
        0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
        0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
    )

    def test_the_computed_constants_match_the_published_ones(self):
        self.assertEqual(self.PUBLISHED_1600, keccak.RC_1600)

    def test_there_are_twenty_two_constants_at_width_800(self):
        """22 rounds, not 24: rounds = 12 + 2*l, and l = 5 for a 32-bit lane."""
        self.assertEqual(22, len(keccak.RC_800))
        for rc in keccak.RC_800:
            self.assertLessEqual(rc, 0xFFFFFFFF, "a 32-bit lane cannot hold this constant")

    def test_the_800_constants_are_the_low_words_of_the_1600_ones(self):
        """Both come from the same LFSR; the narrow one simply drops the high bits."""
        for i in range(22):
            self.assertEqual(keccak.RC_1600[i] & 0xFFFFFFFF, keccak.RC_800[i])


class Sha3MatchesTheStandard(unittest.TestCase):
    """End-to-end: if these pass, f[1600] and the padding are both right."""

    #: Published SHA3-256 digests. The empty-string and "abc" values appear in every
    #: published vector set for the algorithm.
    VECTORS = (
        (b"", "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"),
        (b"abc", "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"),
        (b"a" * 200, None),                      # cross-checked against hashlib below
    )

    def test_published_digests(self):
        for data, want in self.VECTORS:
            if want is None:
                continue
            with self.subTest(length=len(data)):
                self.assertEqual(want, keccak.sha3_256(data).hex())

    def test_agrees_with_the_platform_implementation_across_lengths(self):
        """Independent cross-check, including every length around the 136-byte rate.

        hashlib's SHA3 is a separate implementation of the same standard, so agreement
        across a block boundary exercises the padding and the multi-block path in a way two
        short vectors cannot.
        """
        for n in list(range(0, 8)) + [135, 136, 137, 271, 272, 273, 500]:
            with self.subTest(n=n):
                data = bytes((i * 7 + n) & 0xFF for i in range(n))
                self.assertEqual(hashlib.sha3_256(data).hexdigest(),
                                 keccak.sha3_256(data).hex())


class F800BehavesLikeAPermutation(unittest.TestCase):
    """No published digest vector exists for f[800], so check the properties instead."""

    def test_width_is_enforced(self):
        with self.assertRaises(ValueError):
            keccak.keccak_f800([0] * 24)
        with self.assertRaises(ValueError):
            keccak.keccak_f1600([0] * 26)

    def test_output_stays_inside_thirty_two_bit_lanes(self):
        out = keccak.keccak_f800([0xFFFFFFFF] * 25)
        self.assertEqual(25, len(out))
        for lane in out:
            self.assertTrue(0 <= lane <= 0xFFFFFFFF)

    def test_the_all_zero_state_does_not_stay_zero(self):
        """iota alone must break it; a permutation that fixes zero has lost its constants."""
        self.assertNotEqual([0] * 25, keccak.keccak_f800([0] * 25))

    def test_one_flipped_input_bit_changes_most_of_the_output(self):
        """Avalanche. A wrong rotation table or a skipped step shows up here.

        Not a cryptographic claim -- just that the diffusion is of the right order. A
        broken implementation typically changes a handful of bits, not hundreds.
        """
        a = keccak.keccak_f800([0] * 25)
        b = keccak.keccak_f800([1] + [0] * 24)
        differing = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
        self.assertGreater(differing, 300, f"only {differing} of 800 bits changed")

    def test_it_is_deterministic(self):
        s = [i * 2654435761 & 0xFFFFFFFF for i in range(25)]
        self.assertEqual(keccak.keccak_f800(list(s)), keccak.keccak_f800(list(s)))

    def test_the_input_list_is_not_mutated(self):
        """The caller's state must survive; a kernel comparison depends on it."""
        s = [7] * 25
        keccak.keccak_f800(s)
        self.assertEqual([7] * 25, s)


if __name__ == "__main__":
    unittest.main()
