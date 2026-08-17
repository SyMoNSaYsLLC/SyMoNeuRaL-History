"""On-chain settlement: turning a confirmed TRON payment into an entitlement.

## This is NOT `backend/apps/licensing/`, and the difference matters

Two things in this repo are called licensing and they are unrelated:

| | `apps/licensing/` | `apps/settlement/` (here) |
|---|---|---|
| What | a **dev fee** on mining firmware | a **workspace licence** bought with USDT |
| Artefact | `SYMN1.<payload>.<sig>` contract key | on-chain payment + a short-lived entitlement |
| Question | "what rate is this rig running, and is it disclosed?" | "did this buyer pay for this build?" |
| Consumer | the miner surface | the Gateway surface |

They both use Ed25519 and both talk about "licences", which is exactly why this note is at the
top: an earlier revision of this work was written *into* `apps/licensing/` and overwrote it.
If the two are ever unified that should be a deliberate commit that reconciles the token
formats, not a name collision. Note that `apps/licensing` verifies via `openssl` by exec on
the grounds that the serving interpreter has no asymmetric crypto; that is worth revisiting,
because `cryptography` 43.0.0 is in fact an OS package here and is what this module uses.

`backend/apps/gateway/` reads the chain and reports what it sees. This package is the other
half — it decides whether a settlement covers a request. `docs/specs/gateway-completion.md`
§7 phase 3 calls these items 10–13 and blocks them on `docs/specs/symon-ml-review.md`
findings 1 and 2 having written-down answers. Both answers are written down here, because a
design decision that lives only in a review is not a decision.

## Finding 2 — answered: this is a payment rail, not DRM. Say so.

The review asked how a decryption key reaches a buyer such that only a payer can use it, and
noted it may not be resolvable as posed. It is not. A blockchain is public: a key in the
contract, in calldata, or in an event is a key published to everyone. The only constructions
that work put a server we run in the loop — and at that point *that server* is the licence
authority, and the chain is a payment rail rather than a moat.

So the chain is a payment rail. It is a good one: settlement is final, auditable, and needs no
card processor. What it is not is a technical guarantee that an unlicensed copy cannot run, and
this repo does not get to claim one it cannot back. `.claude/CLAUDE.md`: the site's whole
argument is that its numbers are real, and a DRM claim we cannot back is precisely the thing
that argument exists to oppose.

Concretely: at-rest encryption stays, the payment rail stays, and neither is described as more
than it is. **Nothing in this package may be described on the site as preventing copying.**

## Finding 1 — answered: fail closed, and re-check every time.

The bug in the reviewed PoC was `_check_local_sandbox_state()` returning `True`
unconditionally, so blocking `api.trongrid.io` with one firewall rule *granted* the licence. A
check that fails open is worse than no check, because the product around it claims protection.

Two rules follow, and both are enforced by tests that were verified to go red when the bug is
put back:

1. **Every failure path returns a refusal.** No `except` here may return an entitlement, and
   none may return "allowed". Unreachable node, malformed answer, timeout, unparseable
   record — all of them are `Refused`, and `Refused` is falsy.
2. **A positive result is never cached for the process lifetime.** The reviewed code set
   `is_licensed = True` once and never re-checked or expired it. Entitlements here carry an
   explicit expiry, are re-verified on use, and `verify_payment` keeps no state at all.

## What is checked, and why each one

The review's checklist, which the PoC failed: it verified only *recipient* and *confirmed*, so
any confirmed transfer of any token, of any size, at any time, granted a permanent licence.
`verify_payment` checks the **payer**, the **token contract**, the **amount** and the
**workspace**, and refuses if any disagrees.

## Layout

    verify.py        read a settled licence off-chain and decide if it covers this request
    entitlement.py   Ed25519 entitlement: mint (operator side) and verify (server side)
    store.py         the durable record of cleared settlements — what earns `ready`
    __main__.py      the round trip, printed:  python3 -m apps.settlement
    test_settlement.py

## Where the keys are, and are not

The Ed25519 **signing** key is the authority's and lives on the operator's machine, exactly
like the TRON key in `ops/gateway/`. The serving process gets the **public** key only, and
`entitlement.verify` needs nothing else. That asymmetry is the point: a web process that is
compromised cannot mint a licence, only check one.

**Nothing here may import from `ops/`.** Same one-way rule the gateway package states: the
server side must remain runnable without the operator toolchain, which has its own venv and a
signing key the server must never be able to reach.
"""
from __future__ import annotations

from .entitlement import Entitlement, EntitlementError, mint, verify
from .store import Clearance, ClearanceStore
from .verify import Granted, Refused, verify_payment

__all__ = [
    "Entitlement", "EntitlementError", "mint", "verify",
    "Clearance", "ClearanceStore",
    "Granted", "Refused", "verify_payment",
]
