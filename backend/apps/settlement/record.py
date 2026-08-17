"""Turn a verified on-chain settlement into a recorded clearance. The only writer there is.

## Why this file has to exist

`unit_state` lights the Gateway's LED when `_cleared` finds a clearance for the configured
network and contract. `verify_payment` can prove a settlement happened. Until this module,
nothing joined the two: a real customer could have paid on a real chain and the rack would
have stayed dark forever, because no code path anywhere wrote a clearance. `DEPLOY.md` claimed
a purchase would turn the surface green "with no further code", and that was simply false.
This is the further code.

## It is deliberately the only writer

`ClearanceStore.append` is reachable from here and from the rehearsal in `__main__.py`, which
writes to a temp file it creates itself. Nothing else in the serving path can append. That
matters because the clearance file *is* the LED: anything that can write it can light the
lamp, and a lamp that can be lit by something other than a settlement is the decorative
indicator `.claude/CLAUDE.md` forbids.

So there is exactly one way to get a line into that file, and it runs a chain read first.
There is no `--force`, no `--assume-paid` and no way to pass in a record; the only inputs are
what to expect, and the answer comes from the node.

## Recording is not deciding

This writes down that a settlement *happened*. It is not an entitlement and it is not a
grant — `entitlement.mint` still needs the authority key, and `verify_payment` is still
re-run per request rather than trusting this file. The clearance is evidence, kept because
re-reading the whole chain on every page view is not sensible, and it carries the block and
the nonce precisely so it can be re-checked against the chain later.

## Idempotent, because operators re-run things

Recording the same nonce twice appends nothing the second time and reports that it was
already there. An append-only log with a duplicate in it is not corrupt, but "how many
licences have settled" would start lying, and the retry after a half-visible error is the
most likely way anyone ever runs this twice.
"""
from __future__ import annotations

import argparse
import sys

from .store import Clearance, ClearanceStore
from .verify import Granted, Refused, verify_payment

try:
    from gateway import chain
except ImportError:                             # pragma: no cover - exercised by __main__
    from ..gateway import chain                 # type: ignore[no-redef]


class AlreadyRecorded(Refused):
    """Not a denial of the payment — a statement that this nonce is already on file.

    It subclasses `Refused` so it is falsy, which keeps `if record_settlement(...):` meaning
    "a new clearance was written". A caller that wants to treat a repeat as success can test
    for this type explicitly; a caller that does not think about it gets the conservative
    answer rather than a second log line.
    """


def already_recorded(store: ClearanceStore, network: str, contract: str,
                     nonce: int) -> Clearance | None:
    """The existing clearance for this exact nonce on this exact contract, if any.

    Keyed on all three because a nonce is only unique within one deployment: the same nonce
    exists on Nile and on mainnet and they are different licences.
    """
    for c in store.all():
        if c.nonce == nonce and c.network == network and c.contract == contract:
            return c
    return None


def record_settlement(network: str, contract: str, nonce: int, *,
                      expect_payer: str, expect_token: str, expect_workspace: str,
                      min_amount: int, store: ClearanceStore | None = None,
                      fetch=None, timeout: float = chain.TIMEOUT) -> Granted | Refused:
    """Verify a settlement against the chain and, only if it holds, record it.

    Returns exactly what `verify_payment` returned, so every refusal reason survives to the
    caller unchanged. On `Refused` **nothing is written** — that is the property the tests
    exercise one failure mode at a time, because "the chain was unreachable" must not be able
    to leave a clearance behind that outlives the outage.

    The `expect_*` arguments are keyword-only and all required, inherited from
    `verify_payment` for the same reason: an optional check is a check somebody omits.
    """
    store = store if store is not None else ClearanceStore()

    seen = already_recorded(store, network, contract, nonce)
    if seen is not None:
        return AlreadyRecorded("this nonce is already recorded",
                               f"nonce {nonce} on {network} at block {seen.at_block:,}")

    result = verify_payment(network, contract, nonce,
                            expect_payer=expect_payer, expect_token=expect_token,
                            expect_workspace=expect_workspace, min_amount=min_amount,
                            fetch=fetch, timeout=timeout)
    if not result:
        return result                            # Refused: write nothing, say why

    store.append(Clearance(
        nonce=result.nonce, payer=result.payer, token=result.token, amount=result.amount,
        workspace=result.workspace, network=network, contract=contract,
        at_block=result.at_block, at_time=result.at_time,
    ))
    return result


def main(argv: list[str] | None = None) -> int:
    """`python3 -m apps.settlement.record` — the operator's post-purchase step.

    Prints the refusal reason and exits non-zero on anything but a fresh recording, so it can
    be run from a shell script without the caller having to parse the output.
    """
    p = argparse.ArgumentParser(
        prog="python3 -m apps.settlement.record",
        description="Verify one settled licence against the chain and record it.")
    p.add_argument("--network", required=True, choices=sorted(chain.NODES))
    p.add_argument("--contract", required=True, help="the deployed SymoneuralLicence address")
    p.add_argument("--nonce", required=True, type=int)
    p.add_argument("--payer", required=True, help="the address that was quoted")
    p.add_argument("--token", required=True, help="the token the fee was denominated in")
    p.add_argument("--workspace", required=True, help="the workspace string that was quoted")
    p.add_argument("--min-amount", required=True, type=int)
    a = p.parse_args(argv)

    result = record_settlement(a.network, a.contract, a.nonce,
                               expect_payer=a.payer, expect_token=a.token,
                               expect_workspace=a.workspace, min_amount=a.min_amount)
    print(result)
    if isinstance(result, AlreadyRecorded):
        return 0                                 # re-running is not an error
    if not result:
        return 1
    print("recorded — the Gateway unit will read `ready` on the next status poll")
    return 0


if __name__ == "__main__":                       # pragma: no cover
    sys.exit(main())
