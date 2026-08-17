# SyMoNeuRaL Miner: how to make it ours, and make it work

The ask: build SyMoNeuRaL Miner on Braiins as an SDK/source base so the hashboards actually
hash, and have it be **our custom code**. Those two goals pull in opposite directions in one
specific place, and there is a clean way to get both. Everything below was checked against
live repositories or the files in `references/`.

---

## The licence boundary, because it decides the architecture

Every piece of code that can drive an Antminer hashboard today is **GPLv3**:

- **cgminer** — GPLv3 (its own `COPYING`, read from the reference tree earlier in this work)
- **bmminer** — Bitmain's cgminer fork, therefore GPLv3-derived
- **bosminer** — Braiins' rewrite, GPLv3

So a fork of Braiins source *is a derivative work* and must ship under GPLv3, with source
made available to anyone who receives the binary. "Fork Braiins and keep it proprietary" is
not available, and this matters beyond principle: the SyMoN_ML blueprint's IP-moat strategy
assumes the opposite, and `.claude/HANDOVER.md` records that nothing in this project is GPL.

**But the GPL binds derivative works, not separate programs that talk over an interface.** A
control plane in its own process, communicating with a miner over a network API, is not a
derivative of it. That is the boundary every commercial mining-firmware vendor uses, and it
is the one to build on.

## The finding that makes this easy: BOS+ has a public API

`github.com/braiins/bos-plus-api` — **last pushed 2026-08-13**, actively maintained. It is a
complete gRPC surface, defined in `.proto`:

| Proto | What it gives SyMoNeuRaL Miner |
|---|---|
| `authentication.proto` | login — the "it will ask for login" step |
| `miner.proto` | live telemetry |
| `cooling.proto` | fans and temperatures |
| `performance.proto` | **autotuning, power targets** — the part with real commercial value |
| `pool.proto` | pool configuration |
| `network.proto` | network settings |
| `actions.proto` | reboot, pause, resume |
| `upgrade.proto` | **firmware upgrade** |
| `configuration.proto`, `constraints.proto`, `advanced_settings.proto`, `license.proto`, `units.proto`, `common.proto` | the rest |

This is the whole feature list of the miner settings page, as a documented, supported,
versioned API. No reverse engineering, no forking, no GPL obligation on our side.

It also explains something already in the tree: pyasic ships
`pyasic/web/braiins_os/boser.py` built on `betterproto`, which consumes exactly these
definitions. (And why pyasic 0.78+ breaks at import — it ships without the *generated* proto
stubs. We are pinned to 0.75.0 for that reason.)

## The recommended shape

```
  ON THE RIG                              ON OUR BOX / THE CUSTOMER'S SERVER
  ──────────────────────────              ─────────────────────────────────────
  Braiins OS+          (GPLv3)   <──────  SyMoNeuRaL Miner        (ours, closed)
    bosminer, drivers,            gRPC      discovery + IP scan
    autotune engine               API       fleet management
    upgrade.proto                           telemetry + history
                                            tuning POLICY
                                            firmware pre-flight + rollout
                                            branding, UI, licensing
```

- **The engine is a commodity.** Braiins already solved hashboard control; we would spend
  years reproducing it and end up with something worse that we still had to open-source.
- **The control plane is the product**, and it is where the value and the differentiation
  live: fleet policy, pre-flight validation, telemetry, and the SyMoNeuRaL brand.
- **`backend/apps/asicminer/` is already this.** The architecture is not a rewrite; it is
  what has been built. What it gains from BOS+ is a first-class API instead of the
  lowest-common-denominator one.

If firmware genuinely must carry our name on the rig, the honest version is a **branded BOS+
distribution**: our configuration, our defaults, our provisioning, GPL-compliant, with the
source offer included. That is a packaging and support product, not a code-ownership one, and
it is achievable. What is not achievable is a proprietary fork.

## What the local Braiins reference actually is

`references/braiins-os-feeds-master/` is **packaging recipes, not miner source**. Every
`Makefile` is OpenWrt (`include $(TOPDIR)/rules.mk`, `PKG_NAME`, `PKG_RELEASE`) and the
sources point at Braiins' internal host:

```make
PKG_SOURCE_URL:=git@gitlab.bo:x/bmminer.git      # unreachable
PKG_SOURCE_URL:=git@gitlab.bo:x/cgminer.git      # unreachable
```

There is a supported escape hatch — `CONFIG_EXTERNAL_BMMINER_TREE`,
`CONFIG_EXTERNAL_CGMINER_TREE`, `CONFIG_EXTERNAL_UBOOT_TREE` point a build at a local tree —
but you must supply that tree yourself. The feeds do not contain it.

Also note: **Braiins OS source is not on GitHub.** `braiins/braiins-os`,
`braiins/braiins-os-plus`, `bitmaintech/meta-bitmain` and `bitmaintech/openwrt` all 404. The
`braiins` GitHub org holds old Puppet infrastructure. Only `braiins/bos-plus-api` is live —
which is the API, and which is the point.

---

## MicroBT / Whatsminer

**The same analysis cannot be done, because there is no MicroBT firmware here.** All five
files in `references/Projects_Crypto/Antminer/Whatsminer/` are failed downloads saved with a
`.bin` extension:

| File | Size | What it actually is |
|---|---|---|
| `WhatsMiner-all-2026.bin` | 138 B | an **nginx 404 page** |
| `WhatsMiner-M30-Series-2025.bin` | 0 B | empty |
| `WhatsMiner-M50-Series-2025.bin` | 0 B | empty |
| `WhatsMiner-M30-Series-Stable.bin` | 4,983 B | an HTML page |
| `WhatsMiner-all-20260104.bin` | 77 KB | an HTML document |

Real Whatsminer firmware is tens of megabytes. Nothing here can be extracted, verified or
flashed. Re-download from MicroBT's own portal before any MicroBT firmware work.

**The good news is that MicroBT does not need any of it.** Whatsminer exposes the **btminer
API** on TCP 4028 — JSON over a socket, with read-only status unauthenticated and privileged
commands (reboot, power mode, pool change) sent as AES-encrypted tokens. `pyasic` already
speaks it via `pyasic/rpc/btminer.py`, which is installed and verified in
`backend/apps/asicminer/.venv`.

So the MicroBT path is **the control plane only, and it already works** — the same shape
recommended for Antminer above, and reachable today without touching firmware.

---

## Recommended order

1. **Point `fwcheck.py` and the panel at a real BOS+ rig** — nothing else can be validated
   against hardware until one exists.
2. **Generate Python stubs from `bos-plus-api` protos** into `backend/apps/asicminer/`, so
   SyMoNeuRaL Miner drives BOS+ natively rather than through pyasic's
   lowest-common-denominator model. This is the real "Braiins as an SDK" step, and it is an
   API dependency, not a code fork — our side stays ours.
3. **Keep pyasic for breadth** — stock Antminer and Whatsminer, where no BOS+ API exists.
4. **Re-obtain the MicroBT firmware** if firmware work there is actually wanted.
5. **Only then**, if a branded on-rig image is still wanted, scope a GPL-compliant BOS+
   distribution — with the source offer, which is the cost of that route.

## Stale paths, corrected

`references/CGMiner-master/` and `references/Pete/` no longer exist — they were present
earlier in this work and have since been removed. `docs/antminer-firmware-upgrade.md` and
`.claude/HANDOVER.md` §5 both cite them. pyasic is unaffected: it was installed from PyPI
into the app's own venv, not from the reference tree.
