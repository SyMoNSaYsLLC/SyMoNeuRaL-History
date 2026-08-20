# SyMoNeuRaL Yocto layers

Twelve `meta-symoneural-*` layers and two scripts, whose point is stated in the distro
conf: a Yocto-built target and the apt-installed reference workstation should be managed
the same way. The distro packages as `.deb` because `scripts/build-apt-repo.sh` publishes
a flat apt repository and a target built with ipk could not consume it, and
`symoneural-image` sets `package-management` so a built appliance is *capable* of
`apt update && apt upgrade` the moment a repository it can reach is configured. The
recipe's own comment states the missing half plainly: that repository is a build-host
`file://` path no target can see, and nothing here yet serves it over a network or signs
it — so today every update of a deployed target would be a reflash, and without
package-management it would be a reflash with no other path ever possible
(`docs/upgrading.md` has the story).

Each layer carries a one-line `README.md` naming what it is. This file is the cross-layer
state: what parses, what builds, what needs a decision, and — since the cross-compilation
claim is what motivated the whole family — which targets are actually reachable from this
box, which need something the operator must supply, and which are aspiration.

## Build state, dated

Measured at commit `11dc426` (2026-08-19), the commit that first fed these files to
bitbake:

- `bitbake -p` exits 0 — 963 `.bb` parsed, 1992 targets, 0 errors, 3 warnings. All nine
  first-party recipes confirmed present individually via `bitbake-layers show-recipes`,
  not inferred from the total.
- `bitbake -g symoneural-image` exits 1 — `Nothing PROVIDES 'virtual/kernel'` — and that
  failure is left loud deliberately; see the blockers below.
- **No image and no SDK has ever been built from these layers.** Everything below the
  parse line is design that has been made to parse, not a result.

`backend/apps/test_yocto_layers.py` guards the layer family statically (nine tests, three
of them anti-vacuity checks), because a test needing a 963-recipe parse and a writable
`DL_DIR` would be skipped everywhere and guard nothing. To reproduce the real thing:

    yocto/scripts/setup-build.sh                 # writes bblayers.conf and local.conf
    cd /home/google/yocto && source openembedded-core/oe-init-build-env build-symoneural
    bitbake -p                                   # the cheapest real check

`setup-build.sh` writes `bblayers.conf` fresh every run, includes `meta-openembedded`
only when its layer series matches the core's, and includes `meta-symoneural-mingw` and
`meta-symoneural-aws` only when the upstream layer each depends on is present — listing a
layer whose dependency is absent is a fatal parse error that reads like our layers are
broken.

## The two blockers

Both are decisions, not gaps to guess at, and both are queued in `GARRETT-INBOX.md`.

**No kernel provider resolves.** Every `linux-yocto` provider in openembedded-core is
gated on a closed, qemu-only `COMPATIBLE_MACHINE` regex (`linux-yocto_6.18.bb:55` and
three siblings), which no bbappend can widen — `meta-symoneural-kernel`'s
`linux-yocto_%.bbappend` matches and its base recipe is still skipped, which is why the
append's own header says INERT AS SHIPPED. The supported path is copying upstream's
`linux-yocto-custom.bb` into `meta-symoneural-kernel` and supplying a kernel tree, a
`SRCREV` and a defconfig — choices about what we ship. The two wrong fixes are named in
`meta-symoneural-bsp/conf/machine/symoneural-workstation.conf` above the
`PREFERRED_PROVIDER_virtual/kernel` line, and the short version is: deleting that line
lets `linux-dummy` satisfy both graph errors and boot nothing, and a guessed
KMACHINE/KBRANCH can only be validated against `yocto-kernel-cache`, which is not on this
box, so it would parse green and fail at `do_kernel_metadata`.

**`meta-openembedded` is on an incompatible branch.** openembedded-core on this box
reports `LAYERSERIES_COMPAT_core = "blacksail"`; the meta-openembedded checkout declares
`whinlatter wrynose`, so `setup-build.sh` correctly drops it from `bblayers.conf`. Five of
`symoneural-stack`'s eight Python runtime dependencies — `python3-sympy`, `-fastapi`,
`-uvicorn`, `-pydantic`, `-httpx` — live in its `meta-python`, and the Apple device
bridge recipes live in its `meta-oe`, so until that checkout moves to a branch naming
`blacksail`, neither resolves. The recorded consequence worth repeating: RavenCalc cannot
be built for a target at all until then, and SymPy is the one hard dependency of the
surface that is the arm64 machine's whole reason to exist.

## The layers

| Layer | What it is |
|---|---|
| `meta-symoneural-core` | the distro (`symoneural`), the image (`symoneural-image`), the serving packagegroup, and `symoneural-stack_git.bb`, which packages this repository from a `file://` fetcher — there is no git remote by design — with the same delete-then-verify never-ship list as `scripts/build-deb.sh` |
| `meta-symoneural-kernel` | config fragments for the GPU and containers, carried by a bbappend that is inert until a real kernel recipe lands (see blockers) |
| `meta-symoneural-python` | the serving interpreter's packages as distribution packages — the same no-venv-in-the-serving-path policy the reference box runs; deliberately no torch, no transformers, no cupy |
| `meta-symoneural-networking` | Caddy, certificates, and nothing that routes — the FastAPI-does-all-routing rule expressed as a packagegroup |
| `meta-symoneural-filesystem` | the on-disk layout (`symoneural-layout.bb`, tmpfiles.d) and the wic partitioning, which puts the ~104 GiB models volume on its own filesystem so a full disk is a missing-weights report rather than an outage |
| `meta-symoneural-initramfs` | minimal early boot that deliberately does not load the GPU driver — an initramfs holding VRAM before the governor exists breaks the arbitration the whole stack rests on |
| `meta-symoneural-extended` | the optional surfaces (studio, training) as opt-in groups; ComfyUI itself deliberately has no recipe — packaging a 223-package CUDA venv in bitbake against a driver the target may not have is maintenance with no payoff |
| `meta-symoneural-bsp` | the two machines: `symoneural-workstation` (the reference box, x86-64) and `symoneural-arm64` (Graviton, an SBC, a CPU-only appliance — no GPU is its defining property) |
| `meta-symoneural-darwin` | the Apple side: where the user-supplied Swift SDK lives, the SDK bridge include, and the device-bridge packagegroup |
| `meta-symoneural-mingw` | one include that turns the SDK build Windows-hosted (`SDKMACHINE = "x86_64-mingw32"`); depends on upstream `meta-mingw` |
| `meta-symoneural-quail` | Android and Fire OS: notes only, deliberately — there is no Yocto machine for Android and this layer does not invent one |
| `meta-symoneural-aws` | notes only, deliberately — holds no recipes until the Graviton-vs-Greengrass ambiguity in its `aws-notes.inc` is decided |

## The SDK and target matrix, honestly

Three columns, as plain as the sources allow: the target, what is actually on this box
today, and what a build would still need. "On this box" rows carry their source and date;
none of them is a promise.

| Target | On this box today | A build would still need |
|---|---|---|
| `symoneural-workstation` image | all twelve layers parse (`bitbake -p` exit 0 at `11dc426`, 2026-08-19); no image ever built | the kernel recipe decision, a `blacksail`-compatible meta-openembedded, and then a first `bitbake symoneural-image` nobody has run; the NVIDIA driver is installed on the target afterwards from NVIDIA's own package — deliberately no recipe names it |
| `symoneural-arm64` image | machine conf parses; nothing built | the same two blockers; `python3-sympy` from meta-python before RavenCalc, the machine's stated point, exists on it |
| Linux target SDK (`bitbake symoneural-image -c populate_sdk`) | nothing built | everything the image needs, first; `sdk-apple-bridge.inc` then puts the Apple device libraries inside it |
| Windows-hosted SDK (`x86_64-mingw32`) | the include parses; `meta-mingw` absent from `/home/google/yocto` (recorded 2026-08-19) | clone `meta-mingw`, then everything the Linux SDK needs |
| macOS / iOS binaries (Swift) | `darwin.artifactbundle` installed: 3.2 GiB, extracted 2026-07-25, MacOSX26.5 / iPhoneOS26.5 / iPhoneSimulator26.5, five target triples (recorded in `darwin-sdk.inc`) | the `swift` compiler — not installed as of 2026-08-19; install via swiftly, then `symoneural-sdk.sh darwin` |
| Apple device bridge (usbmuxd + libimobiledevice) | the six recipes verified present in the meta-oe checkout, by path (recorded in the packagegroup) | the meta-openembedded branch fix, so meta-oe re-enters `bblayers.conf` |
| Android / Fire OS | notes and the `symoneural-sdk.sh android` driver; no Yocto machine exists or will — bionic is not glibc or musl, so OE binaries fail at exec | the Swift SDK for Android and/or the NDK on the host, outside bitbake entirely; neither verified installed here |
| WebAssembly | the `symoneural-sdk.sh wasm` driver | `swift` plus the swift.org WebAssembly SDK bundle; neither verified installed here |
| Static Linux (any distribution) | the `symoneural-sdk.sh linux` driver | `swift` plus the Static Linux SDK bundle; neither verified installed here |
| AWS Graviton / EC2 | identical to `symoneural-arm64` — a real Yocto target, no AWS-specific layer involved | what the `symoneural-arm64` row needs |
| AWS IoT Greengrass | nothing — `meta-symoneural-aws` holds no recipes, deliberately | the decision recorded in `aws-notes.inc`, then upstream `meta-aws` (absent from `/home/google/yocto`, recorded 2026-08-19) |

`yocto/scripts/symoneural-sdk.sh status` is the live reading of the host-side rows —
toolchains, installed SDK bundles, upstream layers, and the series compatibility check —
and supersedes the dated entries above whenever the two disagree.

## The Apple SDK is used here, never shipped from here

Worth its own heading because an agent or an operator could reasonably assume otherwise.
The `darwin.artifactbundle` is extracted from an Xcode `.xip` downloaded under an Apple
ID, and the Xcode licence permits use, not redistribution. **No recipe fetches or
packages that bundle, and none may.** The supported path is that each operator re-derives
it from their own `.xip` with `xtool setup` — minutes of work that keeps the licence
between Apple and the operator. The division `symoneural-sdk.sh` draws is the one that
matters: talking TO an Apple device (usbmuxd, libimobiledevice — all in meta-oe, no Apple
account involved) is free to build; producing binaries FOR Apple platforms needs Apple's
SDK, supplied by you. The same never-ship posture applies to the training corpus: the
stack recipe deletes and then verifies the trade-secret paths before packaging, and
`bbfatal`s if any survives.

## What this file could and could not verify

Checked directly in this tree (2026-08-20): the twelve layers and their contents as
described, the nine first-party `.bb` files, the kernel fragments the bbappend references
(`symoneural-gpu.cfg`, `symoneural-container.cfg`) and the wic file
(`files/wic/symoneural.wks`) all exist where their referrers point; `references/xtool`,
which `symoneural-sdk.sh` points at for building the real xtool, exists in the checkout.

Carried from the record rather than re-measured: everything about `/home/google/yocto`
(the openembedded-core / bitbake / meta-openembedded checkouts, the series values, the
absence of `meta-mingw`, `meta-aws` and `yocto-kernel-cache`) lives outside this
repository, so those rows carry the dates of the commits and comments that recorded them
— `11dc426` and the conf comments, 2026-08-19 — and the status subcommand above is how to
re-read them now.

One wrinkle to know about rather than trip over: `symoneural-sdk.sh status` also probes
for `meta-clang`, and its absence message derives a layer name mechanically, so it prints
"needed by meta-symoneural-clang". No such layer exists in this tree, and no layer here
depends on meta-clang; the probe is a leftover breadth check, not a missing dependency.
