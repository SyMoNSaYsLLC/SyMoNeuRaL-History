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

## Phase 0 — get this work into your checkout *(nothing below exists there yet)*

All of it — `ops/gateway/`, `backend/apps/gateway/__main__.py`, the contracts, the two new
frontend assertions — is on the branch **`worktree-gateway-online`**, currently through
`7ac0881` (it starts at `15ac0cf`). In your working checkout `ops/gateway/setup.sh` is still a
missing file, so Phase A step 1 fails until you do this. The branch lives in the shared `.git`,
so it survives the worktree being removed.

**Take the branch, not a single commit.** Cherry-picking `15ac0cf` alone silently drops
everything in `7ac0881` — the low-s signing guard, the coincurve pin, the `isLicensed`
pre-mainnet decision below, and this section.

```bash
cd /home/google/Symoneural
git status                                 # FIRST -- see the next paragraph
git merge worktree-gateway-online
python3 tools/build_pages.py               # re-run: build_pages.py moved under me once already
python3 tools/build_cachebust.py           # LAST, always
node tests/frontend.mjs                    # expect 28/28
sudo scripts/deploy.sh --prune             # the page is repo-only until this runs
```

**The merge will abort if you run it today.** The shared checkout is dirty across exactly the
files this branch touches — `backend/api.py`, a dozen `site/*.html`, `tools/build_rack.py`,
`tools/build_stack.py`, `tools/build_training.py` — plus untracked `backend/apps/{accounts,
coder,cryptominer,guide,project,reinforce,sigils}/` from other sessions still working. Git
refuses to merge when local modifications would be overwritten, and the error reads as though
this branch is broken when the problem is only that the tree is busy. Commit or stash that work
first. Expect the conflict in `tools/build_pages.py` specifically: it is shared ground and it
already moved under this work once, when another session landed the Tuner EPG guide in it.

The regeneration matters and the order matters. Re-running the generators after the merge is
what stops a stale seed from silently reverting somebody else's page.
`build_cachebust.py` runs last or the stamps are wrong.

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
| the *configured* `offline` line, rendered | 215 chars, 3 lines at 1440px / 6 at 390px, 0 clipped, 0 ellipsis rules |
| tronpy signature `s` values | 0 of 500 in the upper half — the bound the contract enforces |

That second-to-last row is the one worth knowing about, because it is the state the rack will
actually be in after Phase B. Until today every check had seen the surface *unconfigured*, so
the page only ever rendered the short "not configured" string; the richer branch — the one that
names the network, contract, block height and reading age — existed only in unit tests holding
synthetic readings. It has now been driven end to end, chain → API → page → DOM, by pointing a
throwaway app at real mainnet USDT: the rack row carries `TetherToken`, its power LED stays
**unlit** (`class="led"`, `data-state="offline"`), and nothing wraps off the screen at 390px.

### What has *not* run, and you should know it before you trust it

Honest gaps, since everything above is stated as measured:

- **`gateway-cli.py deploy`, `inspect` and `quote` have never executed against a chain.** Only
  `keygen`, `balance`, the dry-run paths and the refusal guards are exercised. Phase B is their
  first real run — expect to debug there, not to have it work silently.
- **No transaction has ever been signed or broadcast**, so no key, no funds and no gas
  estimate has been tested. The contracts are proven by *execution* in a local EVM at Istanbul,
  which is much stronger than compiling, but it is not the TVM.
- The 57 backend tests all inject `fetch=`, so they never touch the network. That gap is
  exactly why `python3 -m apps.gateway` exists; run it if you want the transport proven today.

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

### Before mainnet, settle `isLicensed` — it does not scale, and the contract cannot be upgraded

`SymoneuralLicence.isLicensed(payer, workspace)` walks the whole `_nonces` array and does two
cold storage reads per entry:

```solidity
for (uint256 i = _nonces.length; i > 0; i--) {
    Licence storage l = _byNonce[_nonces[i - 1]];
    if (l.payer == payer && l.workspace == workspace) return true;
}
```

As a `view` this is free when read off-chain — but TRON caps energy on
`wallet/triggerconstantcontract`, so the call gets slower as licences accumulate and eventually
reverts. Everything here is fail-closed, which is right, and which means the revert reads as
**"not licensed."** A licence check that quietly starts denying customers as the business
succeeds. On Nile it will never be hit; there is no traffic. It is a mainnet problem and it
arrives on a delay.

**This must be decided before Phase D, not after, because the contract is deliberately not
upgradeable.** Two ways out, and they are not the same decision:

1. **Keep the check on-chain, make it O(1).** Add `mapping(bytes32 => bool) private _licensed`
   keyed on `keccak256(abi.encode(payer, workspace))`, written in `redeem` beside the nonce
   burn. Small change, changes the storage layout, needs `build.mjs` and `test_contracts.mjs`
   re-run.
2. **Delete it.** If `docs/specs/symon-ml-review.md` finding 2 resolves the way that review
   itself recommends — the chain is a *payment rail*, not a DRM, and entitlement is minted
   off-chain by `backend/apps/licensing/` on a confirmed payment — then `isLicensed` is not
   the source of truth for anything and should not be on-chain at all.

Option 2 is likelier to be correct, which is exactly why this was left alone rather than
optimised: fixing the loop now would bake in the assumption that the answer is option 1. That
is your call, not an agent's. **Nothing else in this document is blocked on it** — Phases A–C
are safe to run today, and the loop is harmless at Nile volumes.

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
