# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""First-party Stratum client: newline-delimited JSON-RPC over TCP.

## Provenance

Written from the public Stratum mining protocol description — the newline-delimited
JSON-RPC 2.0 framing, and the `mining.subscribe` / `mining.authorize` / `mining.notify` /
`mining.submit` / `mining.set_difficulty` method names that every pool documents. Method
names and message shapes are an interoperability contract, not an implementation: this file
was not derived from `kawpowminer`'s `libpoolprotocols`, or from any other client.

## What this handles and what it refuses

Handled: subscribe, authorize, job receipt, difficulty updates, share submission, server
responses and errors, reconnect with bounded backoff, and orderly cancellation.

Refused, deliberately:

  * **Any connection the configuration did not authorise.** `connect()` takes a validated
    `Endpoint` from `config.py`; it does not parse a string and it cannot be handed a bare
    host. Fail-closed is enforced at the type boundary, not by a check that can be skipped.
  * **Oversized or unframed input.** A line longer than `MAX_LINE` aborts the connection
    instead of buffering. A pool is not a trusted peer: it is a socket on the internet, and
    the first thing a hostile one tries is an unterminated line.
  * **Unknown methods and malformed JSON**, which are counted and dropped rather than
    raised, because one bad frame is not a reason to drop a working session.

## What this is NOT

It does not hash. It carries work in and shares out. The KawPoW hash and its GPU kernel are
not implemented in this repository first-party yet — see `docs/ALGORITHM-GAP.md`. A client
with no hasher is still worth having: it is the half that talks to somebody else's machine,
and it is testable against a local fixture without touching a public pool.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .config import Endpoint

MAX_LINE = 64 * 1024          #: a Stratum frame is small; 64 KiB is already generous
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 90.0           #: pools send set_difficulty/notify well inside this
BACKOFF_BASE = 0.5
BACKOFF_MAX = 30.0


class StratumError(RuntimeError):
    """Protocol-level failure. Never carries a credential in its message."""


@dataclass
class Job:
    """One unit of work as the pool described it. Opaque to this layer by design."""
    job_id: str
    header_hash: str
    seed_hash: str
    target: str
    height: int | None = None
    clean: bool = False
    received_at: float = field(default_factory=time.monotonic)


@dataclass
class Share:
    job_id: str
    nonce: str
    mix_hash: str

    def as_params(self, worker: str) -> list[str]:
        """`mining.submit` parameters, in the order pools expect for this family.

        Nonce and mix hash are sent `0x`-prefixed lower-case hex, which is what the
        published examples show. Formatting is asserted in the tests rather than assumed,
        because a share formatted wrongly is rejected silently by the pool and reads on this
        side as "no luck".
        """
        return [worker, self.job_id, _hex0x(self.nonce), _hex0x(self.mix_hash)]


def _hex0x(v: str) -> str:
    s = v.lower()
    if not s.startswith("0x"):
        s = "0x" + s
    body = s[2:]
    if not body or any(c not in "0123456789abcdef" for c in body):
        raise StratumError("share field is not hexadecimal")
    return s


class StratumClient:
    """One connection, one session. Not reused after `close()`.

    Threading: `run()` blocks on the socket and dispatches callbacks on its own thread.
    `close()` is safe from another thread and makes `run()` return; there is no attempt to
    make the object thread-safe beyond that, because a miner needs exactly one reader.
    """

    def __init__(self, endpoint: Endpoint, wallet: str, worker: str, *,
                 on_job: Callable[[Job], None] | None = None,
                 on_difficulty: Callable[[float], None] | None = None,
                 sock_factory: Callable[[], socket.socket] | None = None):
        self.endpoint = endpoint
        self._wallet = wallet                    # not logged, not repr'd
        self.worker = worker
        self.on_job = on_job
        self.on_difficulty = on_difficulty
        self._sock_factory = sock_factory or (lambda: socket.socket(socket.AF_INET,
                                                                    socket.SOCK_STREAM))
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 1
        self._stop = threading.Event()
        self.subscribed = False
        self.authorized = False
        self.malformed_frames = 0
        self.unknown_methods = 0
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.difficulty: float | None = None
        self.last_job: Job | None = None

    # ------------------------------------------------------------------ lifecycle
    def connect(self) -> None:
        if self._sock is not None:
            raise StratumError("client already connected; construct a new one")
        s = self._sock_factory()
        s.settimeout(CONNECT_TIMEOUT)
        s.connect((self.endpoint.host, self.endpoint.port))
        s.settimeout(READ_TIMEOUT)
        self._sock = s

    def close(self) -> None:
        """Idempotent, and safe to call from another thread or twice."""
        self._stop.set()
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_exc):
        self.close()
        return False

    # ------------------------------------------------------------------ framing
    def _send(self, method: str, params: list) -> int:
        if self._sock is None:
            raise StratumError("not connected")
        mid = self._next_id
        self._next_id += 1
        line = json.dumps({"id": mid, "method": method, "params": params},
                          separators=(",", ":")) + "\n"
        self._sock.sendall(line.encode())
        return mid

    def _readline(self) -> str | None:
        """One frame, or None at clean EOF. Aborts on an over-long line.

        The cap is the point: without it a peer that never sends `\\n` makes this buffer
        until the process dies, which is a denial of service that costs the attacker one
        open socket.
        """
        while b"\n" not in self._buf:
            if len(self._buf) > MAX_LINE:
                raise StratumError(f"peer sent more than {MAX_LINE} bytes with no newline; "
                                   "aborting rather than buffering")
            if self._sock is None:
                return None
            chunk = self._sock.recv(8192)
            if not chunk:
                return None
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        if len(line) > MAX_LINE:
            raise StratumError("frame exceeds the maximum line length")
        return line.decode("utf-8", "replace")

    # ------------------------------------------------------------------ protocol
    def handshake(self) -> None:
        self._send("mining.subscribe", ["symoneural-miner-core/0.1"])
        self._send("mining.authorize", [f"{self._wallet}.{self.worker}", "x"])

    def submit(self, share: Share) -> int:
        return self._send("mining.submit", share.as_params(f"{self._wallet}.{self.worker}"))

    def handle(self, msg: dict) -> None:
        """Dispatch one decoded frame. Unknown shapes are counted, never fatal."""
        method = msg.get("method")
        if method == "mining.notify":
            p = msg.get("params") or []
            if len(p) < 4:
                self.malformed_frames += 1
                return
            job = Job(job_id=str(p[0]), header_hash=str(p[1]), seed_hash=str(p[2]),
                      target=str(p[3]),
                      height=int(p[4]) if len(p) > 4 and str(p[4]).isdigit() else None,
                      clean=bool(p[5]) if len(p) > 5 else False)
            self.last_job = job
            if self.on_job:
                self.on_job(job)
            return
        if method == "mining.set_difficulty":
            p = msg.get("params") or []
            try:
                self.difficulty = float(p[0])
            except (IndexError, TypeError, ValueError):
                self.malformed_frames += 1
                return
            if self.on_difficulty:
                self.on_difficulty(self.difficulty)
            return
        if method is not None:
            self.unknown_methods += 1
            return
        # a response to something we sent
        if "result" in msg or "error" in msg:
            if msg.get("error"):
                self.shares_rejected += 1 if msg.get("id", 0) > 2 else 0
                return
            mid = msg.get("id")
            if mid == 1:
                self.subscribed = True
            elif mid == 2:
                self.authorized = bool(msg.get("result"))
            elif msg.get("result") is True:
                self.shares_accepted += 1
            elif msg.get("result") is False:
                self.shares_rejected += 1
            return
        self.malformed_frames += 1

    def run(self) -> None:
        """Read frames until EOF or `close()`. Returns; does not reconnect."""
        while not self._stop.is_set():
            try:
                line = self._readline()
            except socket.timeout:
                raise StratumError(f"no frame from the pool within {READ_TIMEOUT}s")
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.malformed_frames += 1
                continue
            if not isinstance(msg, dict):
                self.malformed_frames += 1
                continue
            self.handle(msg)


def backoff_delays(n: int) -> list[float]:
    """Bounded exponential backoff. Deterministic, so a test can assert the schedule.

    No jitter here on purpose: jitter belongs to the caller that owns the clock, and a
    deterministic schedule is testable. Capped at `BACKOFF_MAX` so a pool outage does not
    turn into an unbounded wait.
    """
    return [min(BACKOFF_BASE * (2 ** i), BACKOFF_MAX) for i in range(n)]
