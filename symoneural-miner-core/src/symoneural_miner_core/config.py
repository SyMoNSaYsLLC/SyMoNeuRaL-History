# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""Fail-closed configuration for the first-party miner. No default arms anything.

The rule this module exists to enforce, stated in `backend/apps/cryptominer/__init__.py`
and worth repeating where it is implemented: *"a miner that starts because a file happened
to exist is malware with good manners."* This box serves the public internet and the
electricity is somebody's.

So there is no default pool, no default wallet, no default worker, and no default that
turns mining on. `load()` returns a config whose `enabled` is False unless every required
field is present AND the explicit enable flag is set to the literal string `1`. Absence,
emptiness, `true`, `yes`, `on` and `TRUE` all mean off — matching the convention the ASIC
surface already documents (*"the literal string 1, not true"*).

Validation is strict rather than forgiving, because every field here points at somebody
else's machine or somebody's money:

  * the pool endpoint must be an explicit scheme, host and port, and the host must resolve
    to a syntactically valid name or literal address — not merely "contain a dot";
  * the port must be in range and not privileged;
  * the wallet must match the address shape the configured chain declares;
  * the worker name must be printable ASCII within the length a pool will accept;
  * anything unrecognised in the environment is reported, not ignored, because a typo in
    `SYMONEURAL_MINER_POOL` silently mining to nowhere is worse than a refusal.

**Loopback endpoints are the only ones this module will accept without a separate explicit
acknowledgement**, so the test fixture works and a public pool needs one more deliberate
step. That is not a substitute for the owner's authorisation; it is a guardrail under it.
"""
from __future__ import annotations

import ipaddress
import os
import re
import string
from dataclasses import dataclass, field

#: Address shapes per chain, as published by each chain's own documentation. Ravencoin
#: mainnet P2PKH addresses begin `R` and are 34 base58 characters; testnet begins `m` or
#: `n`. This is a syntax check and NOT a checksum validation -- see `ADDRESS_NOTE`.
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
CHAINS = {
    "ravencoin-mainnet": re.compile(r"^R[" + _BASE58 + r"]{33}$"),
    "ravencoin-testnet": re.compile(r"^[mn][" + _BASE58 + r"]{33}$"),
}

ADDRESS_NOTE = (
    "shape only: this checks the prefix, alphabet and length a chain publishes. It does "
    "NOT verify the base58check checksum, so a typo that preserves the shape still passes "
    "here. Mining to a wrong-but-well-formed address loses the proceeds, so the owner "
    "confirms the address, not this regex."
)

_WORKER_OK = set(string.ascii_letters + string.digits + "-_.")
MAX_WORKER = 64

#: Every variable this module reads. Anything else beginning SYMONEURAL_MINER_ is reported
#: as unknown rather than ignored, so a typo cannot fail silently.
KNOWN_VARS = (
    "SYMONEURAL_MINER_ENABLED",
    "SYMONEURAL_MINER_POOL",
    "SYMONEURAL_MINER_WALLET",
    "SYMONEURAL_MINER_WORKER",
    "SYMONEURAL_MINER_CHAIN",
    "SYMONEURAL_MINER_ALLOW_PUBLIC_POOL",
)


class ConfigError(ValueError):
    """Refusal to arm. The message says which field and why, never the value."""


@dataclass(frozen=True)
class Endpoint:
    scheme: str
    host: str
    port: int
    is_loopback: bool

    def __str__(self) -> str:                    # safe: an endpoint is not a secret
        return f"{self.scheme}://{self.host}:{self.port}"


@dataclass(frozen=True)
class MinerConfig:
    enabled: bool = False
    endpoint: Endpoint | None = None
    wallet: str | None = None
    worker: str | None = None
    chain: str = "ravencoin-mainnet"
    allow_public_pool: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)
    unknown_vars: tuple[str, ...] = field(default_factory=tuple)

    def why_not(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""

    def redacted(self) -> dict:
        """A form safe to log or put in a rack row. The wallet is masked deliberately.

        A wallet address is not a secret in the cryptographic sense -- it is public on the
        chain -- but it identifies the owner's earnings, and a rack row served to anyone is
        not the place for it. First four and last four, which is enough to confirm a
        configuration matches without publishing it.
        """
        w = self.wallet
        shown = f"{w[:4]}…{w[-4:]}" if w and len(w) > 10 else ("set" if w else None)
        return {
            "enabled": self.enabled,
            "endpoint": str(self.endpoint) if self.endpoint else None,
            "wallet": shown,
            "worker": self.worker,
            "chain": self.chain,
            "why_not": self.why_not(),
            "unknown_vars": list(self.unknown_vars),
        }


def parse_endpoint(raw: str) -> Endpoint:
    """`scheme://host:port`, all three required. No guessing at defaults."""
    m = re.fullmatch(r"(?P<scheme>stratum\+tcp|stratum2\+tcp|tcp)://"
                     r"(?P<host>\[[0-9A-Fa-f:]+\]|[^:/\s]+):(?P<port>\d{1,5})", raw.strip())
    if not m:
        raise ConfigError(
            "pool endpoint must be scheme://host:port with an explicit port, where scheme "
            "is stratum+tcp, stratum2+tcp or tcp. No default port is assumed, because "
            "assuming one is how a miner connects somewhere nobody chose")
    host = m.group("host").strip("[]")
    port = int(m.group("port"))
    if not (1 <= port <= 65535):
        raise ConfigError(f"pool port {port} is outside 1-65535")
    if port < 1024:
        raise ConfigError(f"pool port {port} is privileged; a mining pool does not listen "
                          "below 1024 and this is more likely a typo than a pool")
    loop = False
    try:
        ip = ipaddress.ip_address(host)
        loop = ip.is_loopback
    except ValueError:
        # a name, not a literal: validate the shape a resolver would accept
        if len(host) > 253 or not re.fullmatch(r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
                                               r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*", host):
            raise ConfigError("pool host is not a syntactically valid hostname")
        loop = host == "localhost" or host.endswith(".localhost")
    return Endpoint(m.group("scheme"), host, port, loop)


def validate_wallet(addr: str, chain: str) -> str:
    pat = CHAINS.get(chain)
    if pat is None:
        raise ConfigError(f"unknown chain {chain!r}; known: {', '.join(sorted(CHAINS))}")
    a = addr.strip()
    if not pat.fullmatch(a):
        raise ConfigError(f"wallet address does not match the published shape for {chain} "
                          f"({ADDRESS_NOTE})")
    return a


def validate_worker(name: str) -> str:
    w = name.strip()
    if not w:
        raise ConfigError("worker name is empty")
    if len(w) > MAX_WORKER:
        raise ConfigError(f"worker name is longer than {MAX_WORKER} characters")
    bad = sorted(set(w) - _WORKER_OK)
    if bad:
        raise ConfigError("worker name may contain only letters, digits, dot, dash and "
                          f"underscore; found {len(bad)} disallowed character(s)")
    return w


def load(env: dict | None = None) -> MinerConfig:
    """Read the environment and return a config. Never raises; refusals are reasons.

    Returning rather than raising is deliberate: the rack has to be able to render "off,
    and here is exactly why" on every poll, and an exception at import time cannot do that.
    """
    e = os.environ if env is None else env
    reasons: list[str] = []

    unknown = tuple(sorted(k for k in e
                           if k.startswith("SYMONEURAL_MINER_") and k not in KNOWN_VARS))
    if unknown:
        reasons.append(f"{len(unknown)} unrecognised SYMONEURAL_MINER_* variable(s) set: "
                       f"{', '.join(unknown)} — a typo here is how a miner points nowhere")

    chain = (e.get("SYMONEURAL_MINER_CHAIN") or "ravencoin-mainnet").strip()
    if chain not in CHAINS:
        reasons.append(f"unknown chain {chain!r}")
        chain = "ravencoin-mainnet"

    endpoint = wallet = worker = None
    for name, raw, fn in (
            ("pool",   e.get("SYMONEURAL_MINER_POOL"),   lambda v: parse_endpoint(v)),
            ("wallet", e.get("SYMONEURAL_MINER_WALLET"), lambda v: validate_wallet(v, chain)),
            ("worker", e.get("SYMONEURAL_MINER_WORKER"), lambda v: validate_worker(v))):
        if not raw or not raw.strip():
            reasons.append(f"{name} is not set")
            continue
        try:
            val = fn(raw)
        except ConfigError as exc:
            reasons.append(f"{name}: {exc}")
            continue
        if name == "pool":
            endpoint = val
        elif name == "wallet":
            wallet = val
        else:
            worker = val

    allow_public = e.get("SYMONEURAL_MINER_ALLOW_PUBLIC_POOL") == "1"
    if endpoint is not None and not endpoint.is_loopback and not allow_public:
        reasons.append("endpoint is not loopback and SYMONEURAL_MINER_ALLOW_PUBLIC_POOL is "
                       "not 1 — reaching a public pool takes one more deliberate step, and "
                       "it does not substitute for the owner's authorisation")

    # The literal string "1". Not "true", not "yes", not "on".
    armed = e.get("SYMONEURAL_MINER_ENABLED") == "1"
    if not armed:
        reasons.append("SYMONEURAL_MINER_ENABLED is not the literal string 1")

    enabled = armed and not reasons
    return MinerConfig(enabled=enabled, endpoint=endpoint, wallet=wallet, worker=worker,
                       chain=chain, allow_public_pool=allow_public,
                       reasons=tuple(reasons), unknown_vars=unknown)
