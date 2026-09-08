#!/usr/bin/env bash
# Cross-compilation targets for SyMoNeuRaL, and what each one actually needs.
#
#     yocto/scripts/symoneural-sdk.sh status              what is installed, what is not
#     yocto/scripts/symoneural-sdk.sh darwin  [PKGDIR]    macOS / iOS, via the Swift SDK
#     yocto/scripts/symoneural-sdk.sh android [PKGDIR]    Android and Fire OS
#     yocto/scripts/symoneural-sdk.sh wasm    [PKGDIR]    WebAssembly
#     yocto/scripts/symoneural-sdk.sh linux   [PKGDIR]    static Linux, any distribution
#     yocto/scripts/symoneural-sdk.sh mingw               how the Windows SDK is built
#     yocto/scripts/symoneural-sdk.sh yocto               how the Linux target SDK is built
#
# ONE SCRIPT, not five, because five scripts each checking for swiftly is how a tools
# directory becomes unreadable. Every subcommand reports what it found before it acts, so
# a missing toolchain is a sentence rather than a compiler error forty lines down.
#
# THE DIVISION THAT MATTERS. Two different things get called "cross-compiling to Apple"
# and only one of them is free:
#
#   talking TO an Apple device      usbmuxd + libimobiledevice, both in meta-oe, both
#                                   buildable by Yocto today, no Apple account involved
#   producing binaries FOR Apple    needs Apple's SDK headers and libraries, which come
#                                   out of an Xcode .xip you download under your own Apple
#                                   ID. Nothing here redistributes them.
#
# The second is set up on the reference box already -- see `status`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }

SDK_HOME="${HOME}/.swiftpm/swift-sdks"
SWIFTLY_BIN="${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/bin"

c_ok()   { printf '  \033[32m%-14s\033[0m %s\n' "$1" "$2"; }
c_no()   { printf '  \033[33m%-14s\033[0m %s\n' "$1" "$2"; }
c_head() { printf '\n\033[1m%s\033[0m\n' "$1"; }

find_swift() {
  if command -v swift >/dev/null 2>&1; then command -v swift; return 0; fi
  if [ -x "$SWIFTLY_BIN/swift" ]; then echo "$SWIFTLY_BIN/swift"; return 0; fi
  return 1
}

need_swift() {
  if ! SWIFT="$(find_swift)"; then
    cat >&2 <<'MISSING'
swift is not installed on this host, and every Swift SDK below needs it.

The Darwin SDK being present does not help on its own: an artifactbundle is headers,
libraries and a toolset description, and `swift build --swift-sdk ...` is the thing that
reads it. Install the compiler with swiftly, from swift.org:

    curl -O https://download.swift.org/swiftly/linux/swiftly-$(uname -m).tar.gz
    tar zxf swiftly-$(uname -m).tar.gz
    ./swiftly init --quiet-shell-followup
    . "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh"
    swiftly install latest

Then re-run this command. Nothing here installs a toolchain for you: swiftly wants a
shell profile it can edit and a version choice, and a script making both decisions
silently is how two toolchains end up on one PATH.
MISSING
    exit 1
  fi
  export SWIFT
}

# --- status ------------------------------------------------------------------
cmd_status() {
  c_head "host toolchains"
  if SWIFT="$(find_swift)"; then
    c_ok "swift" "$SWIFT ($("$SWIFT" --version 2>/dev/null | head -1))"
  else
    c_no "swift" "not installed -- see 'swiftly' below. Every Swift SDK needs it."
  fi
  if [ -x "$SWIFTLY_BIN/swiftly" ]; then
    c_ok "swiftly" "$SWIFTLY_BIN/swiftly"
  else
    c_no "swiftly" "not installed: curl -O https://download.swift.org/swiftly/linux/swiftly-\$(uname -m).tar.gz"
  fi
  if command -v cargo >/dev/null; then
    c_ok "cargo" "$(command -v cargo) -- builds symon-gateway"
  else
    c_no "cargo" "not installed; symon-gateway is Rust"
  fi

  c_head "swift SDK bundles installed"
  if [ -d "$SDK_HOME" ] && [ -n "$(ls -A "$SDK_HOME" 2>/dev/null)" ]; then
    for b in "$SDK_HOME"/*; do
      [ -d "$b" ] || continue
      name="$(basename "$b")"
      triples="$(sed -n 's/.*"targetTriples":{//p' "$b/swift-sdk.json" 2>/dev/null \
                 | grep -o '"[a-z0-9_]*-[a-z0-9-]*"' | tr -d '"' | sort -u | tr '\n' ' ')"
      c_ok "$name" "$(du -sh "$b" | cut -f1)${triples:+ -- $triples}"
    done
  else
    c_no "(none)" "no bundles under $SDK_HOME"
  fi

  c_head "apple: producing binaries FOR macOS / iOS"
  if [ -d "$SDK_HOME/darwin.artifactbundle" ]; then
    ver="$(cat "$SDK_HOME/darwin.artifactbundle/darwin-sdk-version.txt" 2>/dev/null || echo unknown)"
    c_ok "darwin SDK" "installed, Xcode SDK version: $ver"
    find "$SDK_HOME/darwin.artifactbundle/Developer/Platforms" -maxdepth 4 -name '*.sdk' \
        -printf '                 %f\n' 2>/dev/null | sort
  else
    c_no "darwin SDK" "absent. Build it from your own Xcode .xip: xtool setup"
  fi
  # The name collision is called out because it is genuinely confusing: `xtool` resolves,
  # runs, and fails with a linker error about a library nobody in this project installed.
  if command -v xtool >/dev/null; then
    if xtool --version >/dev/null 2>&1; then
      c_ok "xtool" "$(command -v xtool)"
    else
      c_no "xtool" "$(command -v xtool) EXISTS BUT DOES NOT RUN -- this is a different"
      printf '                 tool of the same name (a dub package needing libxadi.so),\n'
      printf '                 not xtool-org/xtool. Build the real one from\n'
      printf '                 external/xtool and put it earlier on PATH.\n'
    fi
  else
    c_no "xtool" "not on PATH; clone is at external/xtool"
  fi

  c_head "apple: talking TO a device (no Apple account needed)"
  local oe="/home/google/yocto/meta-openembedded/meta-oe"
  if [ -d "$oe" ]; then
    for r in usbmuxd libimobiledevice libplist libusbmuxd; do
      f="$(find "$oe" -name "$r*.bb" 2>/dev/null | head -1)"
      [ -n "$f" ] && c_ok "$r" "${f#/home/google/yocto/}" || c_no "$r" "no recipe found"
    done
  else
    c_no "meta-oe" "not at $oe"
  fi

  c_head "yocto layers"
  for l in /home/google/yocto/openembedded-core /home/google/yocto/bitbake \
           /home/google/yocto/meta-openembedded; do
    [ -d "$l" ] && c_ok "$(basename "$l")" "present" || c_no "$(basename "$l")" "ABSENT"
  done
  for l in meta-mingw meta-clang meta-aws; do
    [ -d "/home/google/yocto/$l" ] && c_ok "$l" "present" \
      || c_no "$l" "absent -- needed by meta-symoneural-${l#meta-}"
  done
  echo
  # Stated here rather than discovered at build time. bitbake's compat check is fatal.
  core="$(grep -h 'LAYERSERIES_COMPAT_core' \
      /home/google/yocto/openembedded-core/meta/conf/layer.conf 2>/dev/null \
      | sed 's/.*= *//;s/"//g')"
  oecompat="$(grep -h 'LAYERSERIES_COMPAT_openembedded-layer' \
      /home/google/yocto/meta-openembedded/meta-oe/conf/layer.conf 2>/dev/null \
      | sed 's/.*= *//;s/"//g')"
  printf '  core series      %s\n  meta-oe accepts  %s\n' "${core:-?}" "${oecompat:-?}"
  case " $oecompat " in
    *" $core "*) c_ok "compatible" "meta-oe parses against this core";;
    *) c_no "MISMATCH" "meta-oe will refuse to parse. Update meta-openembedded to a"
       printf '                 branch whose LAYERSERIES_COMPAT names %s.\n' "$core";;
  esac
}

# --- swift SDK builds --------------------------------------------------------
# One implementation, three subcommands. The only thing that differs between building for
# iOS, Android and WebAssembly is the SDK identifier passed to --swift-sdk, so writing
# three copies of this would be three places for the same bug.
swift_build() {
  local sdk="$1" label="$2" pkgdir="${3:-.}"
  need_swift
  if ! "$SWIFT" sdk list 2>/dev/null | grep -q .; then
    echo "no Swift SDKs are installed for this toolchain." >&2
    echo "install one:  swift sdk install <url-or-file> --checksum <sum>" >&2
    exit 1
  fi
  if ! "$SWIFT" sdk list 2>/dev/null | grep -qi "$sdk"; then
    echo "the $label SDK is not installed for this toolchain. Installed:" >&2
    "$SWIFT" sdk list >&2
    exit 1
  fi
  echo "building $pkgdir for $label ($sdk)"
  ( cd "$pkgdir" && "$SWIFT" build --swift-sdk "$sdk" )
}

cmd_darwin() {
  local pkgdir="${1:-.}"
  if [ ! -d "$SDK_HOME/darwin.artifactbundle" ]; then
    cat >&2 <<'NOSDK'
no Darwin SDK under ~/.swiftpm/swift-sdks/darwin.artifactbundle.

Build one from an Xcode .xip you download under your own Apple ID:

    swift build -c release --package-path external/xtool   # the real xtool
    xtool setup                                              # walks the .xip extraction

Nothing in this repository ships Apple's SDK. The Xcode licence permits use, not
redistribution, so the extraction has to happen on your account, on your machine.
NOSDK
    exit 1
  fi
  # Every triple the installed bundle declares, read from it rather than assumed -- the
  # set differs between Xcode versions and a hardcoded list goes stale silently.
  echo "triples this bundle declares:"
  grep -o '"[a-z0-9_]*-apple-[a-z0-9-]*"' "$SDK_HOME/darwin.artifactbundle/swift-sdk.json" \
      | tr -d '"' | sort -u | sed 's/^/  /'
  echo
  swift_build darwin "macOS / iOS" "$pkgdir"
  echo
  echo "pick a triple explicitly for a specific device, e.g.:"
  echo "  swift build --swift-sdk darwin --triple arm64-apple-ios"
}

cmd_android() {
  cat <<'NOTE'
Android and Fire OS are the same target here: Fire OS is Android, so a Fire TV stick takes
an aarch64 Android build. Two toolchains reach it and they are not interchangeable --

  Swift SDK for Android   swift.org publishes it as an artifactbundle. Use this for
                          anything written in Swift.
                            swift sdk install <android bundle url> --checksum <sum>

  Android NDK             for the C and C++ parts. Yocto does not target Android and no
                          layer here pretends otherwise: bionic is not glibc or musl, and
                          an OE toolchain emits binaries Android will not load.

NOTE
  swift_build android "Android" "${1:-.}"
}

cmd_wasm() {
  echo "WebAssembly, via the Swift SDK for WebAssembly published on swift.org."
  swift_build wasm "WebAssembly" "${1:-.}"
}

cmd_linux() {
  cat <<'NOTE'
The Static Linux SDK produces a binary with no dynamic dependencies at all -- not even
libc -- so it runs on any distribution. The cost is real and worth stating: no dlopen, no
system libraries, and any C dependency must be statically linked by you. It is built on
musl rather than glibc, so a dependency that does `import Glibc` needs a
`canImport(Musl)` branch.

NOTE
  swift_build static-linux "static Linux" "${1:-.}"
}

# --- yocto SDKs --------------------------------------------------------------
cmd_mingw() {
  cat <<'NOTE'
The Windows SDK is a Yocto SDK, not a Swift one: bitbake builds a cross-toolchain whose
host is Windows.

  1. Clone the layer upstream provides for it -- there is no first-party substitute:
       git -C /home/google/yocto clone https://git.yoctoproject.org/meta-mingw
  2. Add meta-mingw and meta-symoneural-mingw to bblayers.conf (setup-build.sh does this).
  3. Select the SDK host and build:
       SDKMACHINE=x86_64-mingw32 bitbake symoneural-image -c populate_sdk

The installer lands in tmp/deploy/sdk/ as a .zip rather than the .sh a Linux SDK
produces, because the host that runs it is Windows.

meta-mingw is ABSENT from /home/google/yocto right now -- step 1 is not optional.
NOTE
}

cmd_yocto() {
  cat <<'NOTE'
The Linux target SDK -- a cross-compiler plus a sysroot matching the image, as one
self-extracting installer:

    bitbake symoneural-image -c populate_sdk

To put the Apple device libraries INSIDE that SDK, so the SDK's own host tools can talk to
an attached iPhone, add them to the SDK's target task rather than to the image:

    TOOLCHAIN_TARGET_TASK:append = " usbmuxd libimobiledevice libimobiledevice-dev"

meta-symoneural-darwin/conf/include/sdk-apple-bridge.inc does exactly that; require it
from local.conf. IMAGE_INSTALL and TOOLCHAIN_TARGET_TASK are different variables and the
mistake is easy: appending to IMAGE_INSTALL puts the libraries on the running target and
leaves the SDK without them.

The installer is written to tmp/deploy/sdk/ and runs on any Linux host of the right
architecture -- it carries its own sysroot, so the host distribution does not matter.
NOTE
}

case "${1:-status}" in
  status)  cmd_status;;
  darwin|apple|ios|macos) shift || true; cmd_darwin "${1:-.}";;
  android|quail|firestick|fireos) shift || true; cmd_android "${1:-.}";;
  wasm|webassembly) shift || true; cmd_wasm "${1:-.}";;
  linux|static) shift || true; cmd_linux "${1:-.}";;
  mingw|windows) cmd_mingw;;
  yocto|sdk) cmd_yocto;;
  -h|--help|help) sed -n '2,30p' "$0";;
  *) echo "unknown target: $1" >&2; sed -n '2,12p' "$0" >&2; exit 2;;
esac
