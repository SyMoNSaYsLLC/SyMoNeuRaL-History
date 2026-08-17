# Bringing the Gateway online — the operator's procedure

**Everything an agent could do is done.** What is left is in this file, and it is left because
each step is a decision or a credential rather than a task: a company keypair, a contract
deployment under that key, and two `sudo` commands. `docs/specs/gateway-completion.md` §7 marks
these **(b)** for that reason, and `.claude/HANDOVER.md` §5 item 0 sets the precedent — the
contract signing key was Garrett's call too.

**Nothing in Phase A or B costs any money.** Nile is a free testnet. Money enters at Phase D
and nowhere earlier.

> **The state stays `offline` at the end of Phase C, and that is correct.** A deployed contract
> is not a working licensing service. See "What `ready` would take" at the bottom — it is the
> one part of this that is still a decision rather than a procedure.

---

## What is already true, measured rather than assumed

Run these first; they need no key, no funds and no sudo, and they are the floor everything
below stands on.

```bash
cd backend && python3 -m apps.gateway          # reads three real TRON networks
cd ops/gateway && node test_contracts.mjs      # executes the contracts in a local EVM
cd backend && python3 -m pytest apps/gateway -q # 57 offline tests
```

Measured 2026-08-17 from this box:

| Reading | Value |
|---|---|
| Nile head block | 70,157,962 · 462 ms |
| Shasta head block | 67,584,537 · 654 ms |
| mainnet head block | 85,439,122 · 430 ms |
| mainnet USDT `TR7NHq…Lj6t` | **present** — `TetherToken`, 33 ABI functions |
| the same address on Nile / Shasta | **absent** — the node answers `{}` |
| `SymoneuralLicence` | 4,453 bytes, solc 0.8.18, evm istanbul, 17/17 logic tests |
| `MockTRC20` | 1,860 bytes, same settings |

---

## Phase A — the operator keypair *(yours, and it is a company artefact)*

```bash
./ops/gateway/setup.sh                                    # builds both toolchains, ~1 min
ops/gateway/.venv/bin/python ops/gateway/gateway-cli.py \
    keygen --out ~/symoneural-gateway-operator
```

It writes the key at 0600, prints the address, and **refuses to write under `/tmp`** — that is
exactly how the contract signing key was lost. Back it up somewhere that survives a reboot.

**This key never goes into a systemd unit, a drop-in, the repo, or any file the web process can
read.** It signs quotes; it is not the same thing as the account that receives fees, and
keeping those separate is why the contract takes two addresses.

Fund it from the Nile faucet — free, and it is a browser form:
<https://nileex.io/join/getJoinPage>

```bash
ops/gateway/.venv/bin/python ops/gateway/gateway-cli.py \
    balance --network nile --address <the address keygen printed>
```

Expect a few thousand TRX. Under ~1,000 and a deployment can fail part-way; top up rather than
find out.

## Phase B — deploy to Nile *(free)*

A testnet has no USDT, so deploy a token to denominate in first.

```bash
CLI="ops/gateway/.venv/bin/python ops/gateway/gateway-cli.py"

$CLI deploy --network nile --key ~/symoneural-gateway-operator --contract MockTRC20

$CLI deploy --network nile --key ~/symoneural-gateway-operator \
    --contract SymoneuralLicence \
    --quote-signer <operator address> \
    --beneficiary <where fees should land>
```

Add `--dry-run` to either to see the plan without broadcasting.

Then verify it from the *other* side — the tool reporting SUCCESS is not the chain agreeing:

```bash
$CLI inspect --network nile --contract <licence address>
```

## Phase C — point the rack at it *(needs `sudo`)*

A drop-in, not the `@@ROOT@@` template, while this is a testnet rehearsal. One file, reversible
by deleting one file, and it does not modify a tracked template.

```bash
sudo install -d /etc/systemd/system/symoneural-api.service.d
sudo cp ops/gateway/gateway.conf.example \
        /etc/systemd/system/symoneural-api.service.d/gateway.conf
sudo nano /etc/systemd/system/symoneural-api.service.d/gateway.conf   # set the contract
sudo systemctl daemon-reload && sudo systemctl restart symoneural-api

curl -s localhost:8800/api/gateway/state | python3 -m json.tool
```

The rack's detail line should change from *"not configured — set SYM_GATEWAY_ENABLED=1…"* to a
measured reading naming Nile, the contract, its function count and the block it was read at.

**The unit still says `offline`, and every one of the module's five returns is `offline` by
design.** Three files say so and a test enforces it. That is not a bug to fix on the way past.

**To undo:** `sudo rm /etc/systemd/system/symoneural-api.service.d/gateway.conf`, then reload
and restart.

### The page, which is coupled to this and is the half that is easy to forget

`site/gateway.html` currently states, truthfully, that there is *no deployed contract, no
wallet, no daemon and no key material on this box*. **Phase B makes the first clause false.**
The page is generated, so edit `GATEWAY_BODY` in `tools/build_pages.py`, never the HTML:

```bash
python3 tools/build_pages.py && python3 tools/build_cachebust.py   # cachebust ALWAYS last
node tests/frontend.mjs                                            # expect green
sudo scripts/deploy.sh --prune                                     # only this reaches visitors
```

A live page contradicting the API is this repo's most-repeated failure. Do not leave Phase B
sitting on a page that denies it.

## Phase D — mainnet *(this is where money enters, and only here)*

Everything above, repeated with `--network mainnet --yes-mainnet`, denominated in real USDT
(`TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`), with real TRX for Energy. `SYM_GATEWAY_NETWORK=mainnet`
should be the last thing that ever changes.

The tool refuses mainnet without `--yes-mainnet` and then asks you to type `MAINNET`. That is
deliberate friction on the only irreversible step in this document.

---

## Issuing a licence — "quoted, not published", in practice

There is no price in the contract, and that is the point. `.claude/CLAUDE.md` forbids
publishing prices, and a `price` variable on a public chain is a permanent, world-readable
price list. Instead you sign one quote at a time:

```bash
$CLI quote --network nile --key ~/symoneural-gateway-operator \
    --contract <licence address> \
    --payer  <the customer's TRON address> \
    --token  <MockTRC20 address, or real USDT on mainnet> \
    --amount 250000000 \
    --workspace "debian-13 · cuda-12.8 · sm_120" \
    --hours 48
```

That prints a JSON quote the customer redeems. What is enforced on chain, and was exercised in
the local EVM:

- only the named `payer` can redeem it — an intercepted quote is worthless to anyone else
- it expires
- one nonce, one licence: a replay is refused
- changing the amount invalidates the signature rather than silently charging more
- a failed fee transfer records **no** licence
- the contract never holds funds; the fee goes straight to `beneficiary`

The amount exists in the quote and, once redeemed, in one settled transaction. It is never
published anywhere, which is as close to "quoted, not published" as a public ledger permits.

---

## What `ready` would take — and why nobody should reach for it yet

The rack's `ready` means one thing across every unit: *this surface will do its job if you
click it.* For the Gateway that means a visitor can obtain a licence. Phase C does not deliver
that, and lighting the LED on a deployed contract would be the decorative indicator
`.claude/CLAUDE.md` forbids. Still missing:

1. **The off-chain daemon** — the approval pause and the log hashing the page describes.
2. **A payment path a real person can complete**, not a CLI invocation.
3. **An unlock that actually gates something** — and this is the open question, not a task.
   `docs/specs/symon-ml-review.md` finding 2: a blockchain is public, so a decryption key
   cannot live in it; if a server we run hands out the key, that server is the licence
   authority and the chain is a payment rail rather than a moat.
4. **One complete round trip**, exercised end to end at least once.

**The review's own recommendation is worth taking as the answer rather than a fallback: keep
the at-rest encryption, treat the chain as a payment rail, and describe both as exactly that.**
A payment rail is a good product. A DRM claim we cannot back is the thing this site exists to
argue against.

There is a neat fit available if that answer is taken, and it needs no new cryptography:
`backend/apps/licensing/` already mints Ed25519-signed contract keys that a rig verifies
**offline**, so a confirmed payment could mint one. That closes the loop without ever putting a
secret on chain. It also needs the licensing signing key regenerated first
(`.claude/HANDOVER.md` §5 item 0) — another of yours.

**That decision is the last thing standing between this surface and `ready`. It is not an
agent's to make.**
