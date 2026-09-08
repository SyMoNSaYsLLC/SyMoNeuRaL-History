# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""A local Stratum pool, for tests and for the smoke. Loopback only, by construction.

Binds `127.0.0.1` on an ephemeral port and speaks enough of the protocol to exercise the
client: subscribe, authorize, notify, set_difficulty, submit accept/reject. It can also be
told to misbehave — truncated JSON, an unterminated line, an unknown method, a flood — so
the client's refusals are tested against something that actually does the bad thing rather
than against a mock that pretends to.

**It cannot reach the internet.** The bind address is hard-coded to `127.0.0.1` and there is
no code path that changes it. That is the whole reason this exists: the miner's protocol
behaviour has to be verifiable without a public pool, a real wallet, or a submitted share.
"""
from __future__ import annotations

import json
import socket
import threading


class FakePool:
    """Context manager. `with FakePool() as p:` then connect to `p.endpoint`."""

    BIND = "127.0.0.1"                           # not configurable, deliberately

    def __init__(self, *, accept_shares: bool = True, difficulty: float = 1.0,
                 misbehave: str | None = None):
        self.accept_shares = accept_shares
        self.difficulty = difficulty
        self.misbehave = misbehave               # None | 'truncated' | 'unterminated'
                                                 # | 'unknown-method' | 'garbage'
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.BIND, 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # what the client sent us, for assertions
        self.subscribed = False
        self.authorized_as: str | None = None
        self.submissions: list[list] = []
        self.jobs_sent = 0

    @property
    def endpoint_str(self) -> str:
        return f"stratum+tcp://{self.BIND}:{self.port}"

    def __enter__(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self.close()
        return False

    def close(self) -> None:
        self._stop.set()
        try:
            self._srv.close()
        except OSError:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    # ------------------------------------------------------------------ server
    def _serve(self) -> None:
        try:
            self._srv.settimeout(5.0)
            conn, _ = self._srv.accept()
        except (OSError, socket.timeout):
            return
        with conn:
            conn.settimeout(5.0)
            if self.misbehave == "unterminated":
                # a frame that never ends: the client must abort, not buffer forever
                try:
                    while not self._stop.is_set():
                        conn.sendall(b"x" * 4096)
                except OSError:
                    pass
                return
            if self.misbehave == "truncated":
                conn.sendall(b'{"id":1,"result":[[],"aa",4]\n')       # missing brace
            if self.misbehave == "garbage":
                conn.sendall(b"not json at all\n\n{}\n")
            buf = b""
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except (OSError, socket.timeout):
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._reply(conn, msg)

    def _reply(self, conn: socket.socket, msg: dict) -> None:
        def send(o: dict) -> None:
            try:
                conn.sendall((json.dumps(o, separators=(",", ":")) + "\n").encode())
            except OSError:
                pass

        m = msg.get("method")
        mid = msg.get("id")
        if m == "mining.subscribe":
            self.subscribed = True
            send({"id": mid, "result": [["mining.notify", "sub1"], "00", 4], "error": None})
            send({"id": None, "method": "mining.set_difficulty",
                  "params": [self.difficulty]})
        elif m == "mining.authorize":
            p = msg.get("params") or []
            self.authorized_as = p[0] if p else None
            send({"id": mid, "result": True, "error": None})
            if self.misbehave == "unknown-method":
                send({"id": None, "method": "mining.something_new", "params": [1]})
            self.notify(conn)
        elif m == "mining.submit":
            self.submissions.append(msg.get("params") or [])
            if self.accept_shares:
                send({"id": mid, "result": True, "error": None})
            else:
                send({"id": mid, "result": False,
                      "error": [23, "Low difficulty share", None]})
        else:
            send({"id": mid, "result": None, "error": [20, "Unknown method", None]})

    def notify(self, conn: socket.socket) -> None:
        """Send one job. Values are fixed so a test can assert on them exactly."""
        self.jobs_sent += 1
        job = {
            "id": None, "method": "mining.notify",
            "params": [
                f"job{self.jobs_sent}",
                "0x" + "ab" * 32,                 # header hash
                "0x" + "cd" * 32,                 # seed hash
                "0x00000000ffff0000000000000000000000000000000000000000000000000000",
                "1234567",                        # height
                True,                             # clean jobs
            ],
        }
        try:
            conn.sendall((json.dumps(job, separators=(",", ":")) + "\n").encode())
        except OSError:
            pass
