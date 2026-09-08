# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""Fail-closed configuration. The default must be OFF, and every refusal must say why."""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from symoneural_miner_core import config as C                        # noqa: E402

GOOD_WALLET = "R" + "9" * 33
LOOPBACK = "stratum+tcp://127.0.0.1:3333"
FULL = {"SYMONEURAL_MINER_ENABLED": "1", "SYMONEURAL_MINER_POOL": LOOPBACK,
        "SYMONEURAL_MINER_WALLET": GOOD_WALLET, "SYMONEURAL_MINER_WORKER": "rig-1"}


class NothingArmsByDefault(unittest.TestCase):

    def test_an_empty_environment_is_off_and_says_why(self):
        c = C.load({})
        self.assertFalse(c.enabled)
        self.assertIn("pool is not set", c.why_not())
        self.assertIn("SYMONEURAL_MINER_ENABLED is not the literal string 1", c.why_not())

    def test_a_complete_configuration_without_the_enable_flag_is_still_off(self):
        """The one that matters: everything present, still refuses."""
        env = dict(FULL); del env["SYMONEURAL_MINER_ENABLED"]
        c = C.load(env)
        self.assertFalse(c.enabled)

    def test_truthy_spellings_are_not_accepted(self):
        for v in ("true", "TRUE", "yes", "on", "Y", "01", " 1", "1 "):
            with self.subTest(value=v):
                c = C.load({**FULL, "SYMONEURAL_MINER_ENABLED": v})
                self.assertFalse(c.enabled, f"{v!r} armed the miner")

    def test_the_literal_one_with_everything_present_arms_it(self):
        """The positive control. Without this, a config that refuses everything passes."""
        c = C.load(FULL)
        self.assertTrue(c.enabled, c.why_not())
        self.assertEqual(3333, c.endpoint.port)
        self.assertTrue(c.endpoint.is_loopback)


class EndpointValidation(unittest.TestCase):

    def test_a_port_is_required(self):
        for raw in ("stratum+tcp://pool.example.com", "127.0.0.1:3333", "pool.example:3333"):
            with self.subTest(raw=raw):
                with self.assertRaises(C.ConfigError):
                    C.parse_endpoint(raw)

    def test_privileged_ports_are_refused(self):
        with self.assertRaises(C.ConfigError) as e:
            C.parse_endpoint("stratum+tcp://127.0.0.1:80")
        self.assertIn("privileged", str(e.exception))

    def test_out_of_range_ports_are_refused(self):
        with self.assertRaises(C.ConfigError):
            C.parse_endpoint("stratum+tcp://127.0.0.1:70000")

    def test_a_malformed_hostname_is_refused(self):
        for host in ("-bad.example", "bad-.example", "a" * 300):
            with self.subTest(host=host):
                with self.assertRaises(C.ConfigError):
                    C.parse_endpoint(f"stratum+tcp://{host}:3333")

    def test_loopback_is_detected_for_names_and_literals(self):
        for raw, want in (("stratum+tcp://127.0.0.1:3333", True),
                          ("stratum+tcp://localhost:3333", True),
                          ("tcp://[::1]:3333", True),
                          ("stratum+tcp://pool.example.com:3333", False)):
            with self.subTest(raw=raw):
                self.assertEqual(want, C.parse_endpoint(raw).is_loopback)

    def test_a_public_pool_needs_a_second_deliberate_flag(self):
        env = {**FULL, "SYMONEURAL_MINER_POOL": "stratum+tcp://pool.example.com:3333"}
        c = C.load(env)
        self.assertFalse(c.enabled)
        self.assertIn("not loopback", c.why_not())
        c2 = C.load({**env, "SYMONEURAL_MINER_ALLOW_PUBLIC_POOL": "1"})
        self.assertTrue(c2.enabled, c2.why_not())


class WalletAndWorker(unittest.TestCase):

    def test_wallet_shape_per_chain(self):
        self.assertEqual(GOOD_WALLET, C.validate_wallet(GOOD_WALLET, "ravencoin-mainnet"))
        with self.assertRaises(C.ConfigError):
            C.validate_wallet(GOOD_WALLET, "ravencoin-testnet")     # wrong prefix
        with self.assertRaises(C.ConfigError):
            C.validate_wallet("R" + "0" * 33, "ravencoin-mainnet")  # 0 is not base58
        with self.assertRaises(C.ConfigError):
            C.validate_wallet("R" + "9" * 20, "ravencoin-mainnet")  # too short

    def test_an_unknown_chain_is_refused_by_name(self):
        with self.assertRaises(C.ConfigError) as e:
            C.validate_wallet(GOOD_WALLET, "dogecoin")
        self.assertIn("unknown chain", str(e.exception))

    def test_the_shape_check_documents_that_it_is_not_a_checksum(self):
        """A regex cannot catch a typo that preserves the shape, and must not imply it can."""
        self.assertIn("checksum", C.ADDRESS_NOTE)

    def test_worker_name_rules(self):
        self.assertEqual("rig_1.a-b", C.validate_worker(" rig_1.a-b "))
        for bad in ("", "   ", "rig 1", "rig/1", "rig;rm -rf /", "x" * 65, "rig\n1"):
            with self.subTest(bad=bad):
                with self.assertRaises(C.ConfigError):
                    C.validate_worker(bad)


class RefusalsAreLegibleAndSafe(unittest.TestCase):

    def test_an_unrecognised_variable_is_reported_not_ignored(self):
        c = C.load({**FULL, "SYMONEURAL_MINER_POOOL": LOOPBACK})
        self.assertFalse(c.enabled)
        self.assertIn("SYMONEURAL_MINER_POOOL", c.why_not())

    def test_the_redacted_form_masks_the_wallet(self):
        r = C.load(FULL).redacted()
        self.assertNotIn(GOOD_WALLET, str(r))
        self.assertIn("…", r["wallet"])

    def test_no_refusal_message_echoes_a_configured_value(self):
        """A reason must name the field, never print what was in it."""
        secretish = "R" + "z" * 33
        c = C.load({**FULL, "SYMONEURAL_MINER_WALLET": secretish,
                    "SYMONEURAL_MINER_CHAIN": "ravencoin-testnet"})
        self.assertNotIn(secretish, c.why_not())

    def test_load_never_raises(self):
        """The rack polls this on every request and must always get an answer."""
        for env in ({}, {"SYMONEURAL_MINER_POOL": "!!!"},
                    {"SYMONEURAL_MINER_WALLET": ""}, {"SYMONEURAL_MINER_CHAIN": "nope"}):
            with self.subTest(env=env):
                self.assertFalse(C.load(env).enabled)


if __name__ == "__main__":
    unittest.main()
