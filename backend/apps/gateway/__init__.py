"""SyMoNeuRaL Gateway -- stablecoin licensing and validation, on TRON.

From the proof of concept at `references/Projects_Crypto/TRX_POC (1).pdf`: SyMoN SaYs LLC,
a Global Stablecoin Licensing & Validation Gateway. A visitor pays a micro-licensing fee in
USDT (TRC-20) for a custom Debian/Ubuntu workspace compilation; a local TronWeb daemon
validates the environment configuration and, once the payment confirms, unlocks the compiled
workspace.

## Status: designed, not built. The surface reports `offline` and that is the truth.

There is no deployed contract, no wallet, no daemon and no key material on this box. That is
why every reading here is null and the rack unit is offline. It is listed on the rack anyway
for the same reason the QLoRA bay is: a surface that exists in the architecture but is not
running should be visible and honestly labelled, not hidden until it works.

## Every figure the PoC quotes belongs to someone else

`.claude/CLAUDE.md` requires each figure be labelled **measured** on this machine, **vendor**
specification, or **projected** arithmetic. Nothing in the PoC is measured, because nothing
has run:

- **~3 second block confirmation** -- VENDOR. That is TRON's DPoS block time as published by
  the network, not a timing taken here. The PoC says "exactly three seconds"; block times are
  a target, not a guarantee, and this module does not repeat the word "exactly".
- **27 Super Representatives** -- VENDOR. A parameter of the TRON network.
- **"transaction fee is effectively zero"** -- PROJECTED, and the wording matters. Energy
  rental does not make execution free; it moves the cost from the end user to whoever rents
  the Energy. Presenting that as "zero fees" would be describing an accounting choice as a
  physical property.
- **Throughput, settlement rates, cost per licence** -- none exist. There is nothing to
  quote and this module quotes nothing.

## Pricing

There is none here, deliberately. The site's standing rule is that prices are quoted, not
published, and inventing one on a licensing surface would be the most damaging possible place
to break it. Fee questions go to symonsayadmin@symoneural.com.

## Switches, off by default

    SYM_GATEWAY_ENABLED=1        # the surface exists at all
    SYM_GATEWAY_NETWORK=shasta   # shasta (testnet) | nile (testnet) | mainnet
    SYM_GATEWAY_CONTRACT=T...    # deployed licensing contract address

Mainnet moves real money, so it is never the default and the state line always names the
network it is pointed at. A gateway that does not say which chain it is on is one
misconfiguration away from taking real USDT while everyone believes it is a test.

**No private key is read by this module, and none should ever be put in the environment of a
public-facing web process.** Signing belongs in the off-chain daemon on the operator's own
machine, which is exactly where the PoC puts it.
"""
from __future__ import annotations

import os
import re

# TRON base58 addresses start with T and are 34 characters. Checked before the address is
# ever displayed, so a typo in the environment surfaces as "malformed" rather than being
# rendered as though it were a real deployment.
ADDRESS = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")

NETWORKS = {
    "shasta": "Shasta testnet",
    "nile": "Nile testnet",
    "mainnet": "TRON mainnet",
}


def enabled() -> bool:
    return os.environ.get("SYM_GATEWAY_ENABLED") == "1"


def network() -> str:
    return (os.environ.get("SYM_GATEWAY_NETWORK") or "").strip().lower()


def contract() -> str:
    return (os.environ.get("SYM_GATEWAY_CONTRACT") or "").strip()


def unit_state() -> tuple[str, str]:
    """(state, detail) for the rack.

    Offline on every path today, because nothing is deployed. Each path gives the actual
    reason rather than a single vague label -- "not configured" and "pointed at a contract
    that does not parse" are different problems and the rack should say which one it is.
    """
    if not enabled():
        return "offline", "designed, not deployed — see /gateway.html"
    net = network()
    if net not in NETWORKS:
        return "offline", (f"SYM_GATEWAY_NETWORK={net or 'unset'} — expected one of "
                           + ", ".join(NETWORKS))
    addr = contract()
    if not addr:
        return "offline", f"{NETWORKS[net]} — no contract address set"
    if not ADDRESS.match(addr):
        return "offline", f"{NETWORKS[net]} — contract address is malformed"
    # Configured, but this module does not reach the chain, so it will not claim the
    # contract is live. Verifying that needs the daemon, which is not built.
    return "offline", (f"{NETWORKS[net]} · {addr[:6]}…{addr[-4:]} configured — "
                       "daemon not built, nothing has confirmed on-chain")
