"""Generic PLAYER interface.

A "player" is whatever actually does the inference work for a session step. The
Capacity Lab measures players through this interface only, so a future
SyMoNeuRaL AR / .syar player is benchmarkable by adding a class here -- not by
rewriting the harness. Nothing below imports torch, transformers or diffusers:
the lab measures a player over the wire, it does not host one.

AI OFF is a real player (`NullPlayer`), not a hidden button. It bypasses
inference server-side by never issuing an inference request at all, which is
verifiable from the outside: no GPU worker spawns and the card stays at
baseline. That is the AI-OFF routing proof.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .core import NOT_AVAILABLE


@dataclass
class PlayerResult:
    ok: bool
    latency_s: float
    http_status: int | None = None
    ttft_s: float | None = None          # time to first token, when the path exposes it
    tokens: int | None = None
    tok_per_s: float | None = None
    model: str | None = None
    error: str | None = None
    bypassed: bool = False               # True when inference was deliberately not invoked


class Player:
    """Interface every player implements. Keep it this small."""
    name = "abstract"
    kind = "abstract"
    uses_gpu = False

    def invoke(self, prompt: str, timeout: float) -> PlayerResult:
        raise NotImplementedError

    def identity(self) -> dict:
        return {"player": self.name, "kind": self.kind, "uses_gpu": self.uses_gpu}


class NullPlayer(Player):
    """AI DISABLED. Inference is bypassed server-side -- no request is issued to
    any inference endpoint, so no GPU worker is ever asked to exist."""
    name = "none"
    kind = "bypass"
    uses_gpu = False

    def invoke(self, prompt: str, timeout: float) -> PlayerResult:
        return PlayerResult(ok=True, latency_s=0.0, bypassed=True)


class SymonChatPlayer(Player):
    """AI ENABLED. The real SyMon AI inference path: POST /api/chat, SSE stream.

    The endpoint's own final event reports `tokens`, `seconds` and `tok_per_s`,
    and its docstring states the rate "is measured, not claimed" -- so those are
    read from the server rather than derived here. Time-to-first-token is
    measured by this client as the wall time until the first `delta` arrives.
    """
    name = "SyMon AI"                    # customer-facing name; no upstream branding
    kind = "chat"
    uses_gpu = True

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def invoke(self, prompt: str, timeout: float) -> PlayerResult:
        body = json.dumps({"prompt": prompt, "max_tokens": 48}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=body, method="POST",
            headers={"content-type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        t0 = time.monotonic()
        ttft = None
        tokens = tok_s = None
        model = None
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        ev = json.loads(payload)
                    except Exception:
                        continue
                    if ev.get("delta") and ttft is None:
                        ttft = time.monotonic() - t0
                    if ev.get("done"):
                        tokens = ev.get("tokens")
                        tok_s = ev.get("tok_per_s")
                        model = ev.get("model")
            return PlayerResult(ok=True, latency_s=time.monotonic() - t0,
                                http_status=status, ttft_s=ttft, tokens=tokens,
                                tok_per_s=tok_s, model=model)
        except urllib.error.HTTPError as e:
            return PlayerResult(ok=False, latency_s=time.monotonic() - t0,
                                http_status=e.code, error=f"HTTP {e.code}")
        except Exception as e:                        # noqa: BLE001
            return PlayerResult(ok=False, latency_s=time.monotonic() - t0,
                                error=f"{type(e).__name__}: {e}")


def build_player(ai_mode: str, base_url: str, api_key: str | None = None) -> Player:
    if ai_mode == "off":
        return NullPlayer()
    if ai_mode == "on":
        return SymonChatPlayer(base_url, api_key)
    raise ValueError(f"unknown ai_mode {ai_mode!r}")
