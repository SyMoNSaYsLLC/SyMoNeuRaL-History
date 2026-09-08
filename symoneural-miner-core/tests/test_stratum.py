# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""The first-party Stratum client, against a real local pool that also misbehaves.

Every test here talks to `FakePool`, which binds 127.0.0.1 on an ephemeral port and is
incapable of reaching the internet -- its bind address is a class constant with no code
path that changes it. **No test contacts a public pool, uses a real wallet, or submits a
real share.**
"""
from __future__ import annotations

import pathlib
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from symoneural_miner_core import config as C                        # noqa: E402
from symoneural_miner_core import stratum as S                       # noqa: E402
from symoneural_miner_core.fakepool import FakePool                  # noqa: E402

WALLET = "R" + "9" * 33
WORKER = "test-rig"


def _client_for(pool: FakePool, **kw) -> S.StratumClient:
    ep = C.parse_endpoint(pool.endpoint_str)
    return S.StratumClient(ep, WALLET, WORKER, **kw)


def _run_until(client: S.StratumClient, predicate, timeout=5.0) -> bool:
    t = threading.Thread(target=lambda: _swallow(client.run), daemon=True)
    t.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _swallow(fn):
    try:
        fn()
    except Exception:
        pass


class HandshakeAndJobReceipt(unittest.TestCase):

    def test_subscribe_authorize_and_a_job_arrive(self):
        jobs: list[S.Job] = []
        with FakePool() as pool:
            with _client_for(pool, on_job=jobs.append) as cl:
                cl.handshake()
                ok = _run_until(cl, lambda: bool(jobs) and cl.authorized)
                self.assertTrue(ok, "no job or no authorization within the deadline")
                self.assertTrue(cl.subscribed)
                self.assertTrue(cl.authorized)
                self.assertEqual(f"{WALLET}.{WORKER}", pool.authorized_as)
                j = jobs[0]
                self.assertEqual("job1", j.job_id)
                self.assertEqual("0x" + "ab" * 32, j.header_hash)
                self.assertEqual("0x" + "cd" * 32, j.seed_hash)
                self.assertEqual(1234567, j.height)
                self.assertTrue(j.clean)

    def test_difficulty_is_delivered_before_work(self):
        seen: list[float] = []
        with FakePool(difficulty=4.25) as pool:
            with _client_for(pool, on_difficulty=seen.append) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: bool(seen)))
                self.assertEqual(4.25, seen[0])
                self.assertEqual(4.25, cl.difficulty)


class ShareFormatting(unittest.TestCase):
    """A share formatted wrongly is rejected silently and reads here as bad luck."""

    def test_params_are_worker_job_nonce_mixhash_all_hex_prefixed(self):
        sh = S.Share(job_id="job1", nonce="00000000deadbeef", mix_hash="ff" * 32)
        p = sh.as_params(f"{WALLET}.{WORKER}")
        self.assertEqual(4, len(p))
        self.assertEqual(f"{WALLET}.{WORKER}", p[0])
        self.assertEqual("job1", p[1])
        self.assertEqual("0x00000000deadbeef", p[2])
        self.assertEqual("0x" + "ff" * 32, p[3])

    def test_an_already_prefixed_value_is_not_double_prefixed(self):
        p = S.Share("j", "0xabc", "0xdef").as_params("w")
        self.assertEqual("0xabc", p[2])
        self.assertEqual("0xdef", p[3])

    def test_uppercase_is_normalised_to_lower(self):
        self.assertEqual("0xdeadbeef", S.Share("j", "DEADBEEF", "aa").as_params("w")[2])

    def test_a_non_hex_field_is_refused_rather_than_sent(self):
        for bad in ("", "0x", "zz", "0xg1"):
            with self.subTest(bad=bad):
                with self.assertRaises(S.StratumError):
                    S.Share("j", bad, "aa").as_params("w")

    def test_a_submitted_share_reaches_the_pool_and_is_accounted(self):
        with FakePool(accept_shares=True) as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.authorized))
                cl.submit(S.Share("job1", "00000000deadbeef", "ab" * 32))
                self.assertTrue(_run_until(cl, lambda: cl.shares_accepted >= 1))
                self.assertEqual(1, len(pool.submissions))
                self.assertEqual("0x00000000deadbeef", pool.submissions[0][2])

    def test_a_rejected_share_is_counted_as_rejected(self):
        with FakePool(accept_shares=False) as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.authorized))
                cl.submit(S.Share("job1", "01", "ab" * 32))
                self.assertTrue(_run_until(cl, lambda: cl.shares_rejected >= 1))
                self.assertEqual(0, cl.shares_accepted)


class HostileAndMalformedInput(unittest.TestCase):
    """A pool is a socket on the internet, not a trusted peer."""

    def test_an_unterminated_line_aborts_instead_of_buffering(self):
        """The denial of service that costs the attacker one open socket."""
        with FakePool(misbehave="unterminated") as pool:
            with _client_for(pool) as cl:
                with self.assertRaises(S.StratumError) as e:
                    cl.run()
                self.assertIn("no newline", str(e.exception))

    def test_garbage_frames_are_counted_and_the_session_survives(self):
        with FakePool(misbehave="garbage") as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.malformed_frames >= 1))
                self.assertTrue(_run_until(cl, lambda: cl.authorized),
                                "one bad frame must not drop a working session")

    def test_a_truncated_json_object_does_not_raise(self):
        with FakePool(misbehave="truncated") as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.malformed_frames >= 1))

    def test_an_unknown_method_is_counted_not_fatal(self):
        with FakePool(misbehave="unknown-method") as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.unknown_methods >= 1))

    def test_a_notify_with_too_few_parameters_is_malformed_not_a_crash(self):
        cl = S.StratumClient(C.parse_endpoint("stratum+tcp://127.0.0.1:3333"),
                             WALLET, WORKER)
        cl.handle({"id": None, "method": "mining.notify", "params": ["only-one"]})
        self.assertEqual(1, cl.malformed_frames)
        self.assertIsNone(cl.last_job)

    def test_a_non_numeric_difficulty_is_malformed(self):
        cl = S.StratumClient(C.parse_endpoint("stratum+tcp://127.0.0.1:3333"),
                             WALLET, WORKER)
        cl.handle({"id": None, "method": "mining.set_difficulty", "params": ["hard"]})
        self.assertEqual(1, cl.malformed_frames)
        self.assertIsNone(cl.difficulty)

    def test_a_json_array_at_the_top_level_is_malformed(self):
        with FakePool() as pool:
            with _client_for(pool) as cl:
                cl._buf = b'[1,2,3]\n'
                _run_until(cl, lambda: cl.malformed_frames >= 1, timeout=1.0)
                self.assertGreaterEqual(cl.malformed_frames, 1)


class LifecycleAndReconnect(unittest.TestCase):

    def test_close_is_idempotent_and_safe_from_another_thread(self):
        with FakePool() as pool:
            cl = _client_for(pool)
            cl.connect()
            t = threading.Thread(target=cl.close, daemon=True); t.start(); t.join(2)
            cl.close()                                  # again: must not raise
            self.assertIsNone(cl._sock)

    def test_connecting_twice_is_refused(self):
        with FakePool() as pool:
            cl = _client_for(pool)
            cl.connect()
            try:
                with self.assertRaises(S.StratumError):
                    cl.connect()
            finally:
                cl.close()

    def test_sending_without_a_connection_is_refused(self):
        cl = S.StratumClient(C.parse_endpoint("stratum+tcp://127.0.0.1:3333"),
                             WALLET, WORKER)
        with self.assertRaises(S.StratumError):
            cl.handshake()

    def test_run_returns_at_clean_eof_rather_than_hanging(self):
        with FakePool() as pool:
            with _client_for(pool) as cl:
                cl.handshake()
                self.assertTrue(_run_until(cl, lambda: cl.authorized))
                pool.close()
                t = threading.Thread(target=lambda: _swallow(cl.run), daemon=True)
                t.start(); t.join(timeout=5)
                self.assertFalse(t.is_alive(), "run() did not return after the pool closed")

    def test_backoff_is_bounded_and_deterministic(self):
        d = S.backoff_delays(10)
        self.assertEqual(d, sorted(d), "backoff must be non-decreasing")
        self.assertLessEqual(max(d), S.BACKOFF_MAX)
        self.assertEqual(d, S.backoff_delays(10), "must be deterministic for testing")
        self.assertEqual(S.BACKOFF_BASE, d[0])


class TheClientCannotBeHandedAnUnvalidatedTarget(unittest.TestCase):
    """Fail-closed at the type boundary, not by a check somebody can skip."""

    def test_the_constructor_requires_an_endpoint_object(self):
        with self.assertRaises((AttributeError, TypeError)):
            S.StratumClient("pool.example.com:3333", WALLET, WORKER).connect()

    def test_the_wallet_is_not_in_the_object_repr(self):
        cl = S.StratumClient(C.parse_endpoint("stratum+tcp://127.0.0.1:3333"),
                             WALLET, WORKER)
        self.assertNotIn(WALLET, repr(cl))


if __name__ == "__main__":
    unittest.main()
