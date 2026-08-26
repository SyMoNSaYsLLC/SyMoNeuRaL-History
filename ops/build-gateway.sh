#!/usr/bin/env bash
# Build the SyMoNeuRaL gateway for THIS Debian host, reproducibly, from canonical source.
#
#   ops/build-gateway.sh              build if the binary is missing or stale
#   ops/build-gateway.sh --force      rebuild unconditionally
#   ops/build-gateway.sh --check      report what would happen; build nothing
#
# ## Why a NATIVE build and not the Yocto SDK -- measured, not assumed
#
# Garrett's rule: *"Build from /yocto when appropriate, but never require /yocto at
# runtime"*, together with: never install a target binary on the Debian host without proving
# its interpreter, ABI, dependencies and runtime compatibility.
#
# The extensible SDK that exists on this box was read rather than guessed at, from its own
# `…toolchain-0.1.0.testdata.json` in `/yocto/build-symoneural/tmp-arm64-*/deploy/sdk`:
#
#     SDK_SYS                    x86_64-oesdk-linux      <- the machine that RUNS the compiler
#     TARGET_SYS                 aarch64-oe-linux        <- what it COMPILES FOR
#     TARGET_ARCH                aarch64
#     MACHINE                    symoneural-arm64
#     TCLIBC                     glibc
#     SDKPATH                    /usr/local/oe-sdk-hardcoded-buildpath
#
# The live host is `x86_64-linux-gnu`, Debian 13.6. **The SDK's target is aarch64, so it
# cannot produce a binary that runs here at all** -- this is case 2 of the component
# decision: the SDK is for a separate SyMoNeuRaL image, and the Debian-host artifact comes
# from a separate reproducible native build of the same canonical source. Being both
# "x86-64" is not the question; the SDK is x86-64 on the *host* side and aarch64 on the
# *target* side, and the target side is what lands in a binary.
#
# So this uses the Debian toolchain, verified present at build time and recorded in the
# build record: cargo/rustc from Debian, linking against the host's own glibc.
#
# ## What it refuses to do
#
# It will not write outside the repository, will not touch /yocto, and will not install
# anything into /etc. Installation is `ops/install-runtime.sh`'s job, deliberately separated
# so a build can be run and inspected without a service restart anywhere near it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }

SRC="$ROOT/backend/apps/gateway"
OUT="$SRC/target/release/symon-gateway"
RECORD="$ROOT/ops/manifests/gateway-build.json"

MODE=build
case "${1:-}" in
    --force) MODE=force ;;
    --check) MODE=check ;;
    "")      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

say() { printf '  %s\n' "$*"; }

# ---------------------------------------------------------------- toolchain
say "toolchain (Debian native, not the SDK):"
for t in cargo rustc cc; do
    command -v "$t" >/dev/null || { echo "  MISSING: $t -- install the Debian toolchain" >&2; exit 1; }
    say "  $(printf '%-6s' "$t") $($t --version 2>&1 | head -1)"
done
HOST_TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
say "  rustc host triple: $HOST_TRIPLE"
case "$HOST_TRIPLE" in
    x86_64-unknown-linux-gnu) ;;
    *) echo "  refusing: rustc host triple is $HOST_TRIPLE, expected x86_64-unknown-linux-gnu" >&2; exit 1 ;;
esac

[ -f "$SRC/Cargo.toml" ] || { echo "  no Cargo.toml at $SRC" >&2; exit 1; }

if [ "$MODE" = check ]; then
    say "check only -- nothing built."
    [ -f "$OUT" ] && say "existing binary: $(stat -c '%s bytes, mtime %y' "$OUT")" || say "no existing binary"
    exit 0
fi

# ---------------------------------------------------------------- build
# `--locked` so the build is reproducible from Cargo.lock rather than from whatever crates.io
# happens to offer today. If the lock file is missing or stale the build FAILS instead of
# quietly resolving something else, which is the whole point of calling this reproducible.
LOCKED=--locked
[ -f "$SRC/Cargo.lock" ] || { say "no Cargo.lock -- building without --locked (NOT reproducible)"; LOCKED=; }

say "building (cargo build --release $LOCKED) ..."
( cd "$SRC" && CARGO_TERM_COLOR=never cargo build --release $LOCKED ) || {
    echo "  BUILD FAILED -- the existing binary was left untouched" >&2; exit 1; }

[ -f "$OUT" ] || { echo "  build reported success but $OUT is absent" >&2; exit 1; }

# ---------------------------------------------------------------- independence
# Cargo hardlinks target/release/<name> from target/release/deps/<name>-<hash>, so the
# freshly built file has st_nlink=2. The runtime contract asks for an INDEPENDENT regular
# file, so the link is broken here rather than left for somebody to notice in an audit.
# Content is unchanged and verified so.
BEFORE="$(sha256sum "$OUT" | cut -d' ' -f1)"
if [ "$(stat -c %h "$OUT")" -gt 1 ]; then
    cp -p "$OUT" "$OUT.tmp$$" && mv -f "$OUT.tmp$$" "$OUT"
    say "broke cargo's hardlink; st_nlink is now $(stat -c %h "$OUT")"
fi
AFTER="$(sha256sum "$OUT" | cut -d' ' -f1)"
[ "$BEFORE" = "$AFTER" ] || { echo "  content changed while breaking the hardlink -- refusing" >&2; exit 1; }

# ---------------------------------------------------------------- prove the artifact
say "artifact:"
say "  path      $OUT"
say "  size      $(stat -c %s "$OUT") bytes"
say "  sha256    $AFTER"
say "  links     $(stat -c %h "$OUT")"
# `|| true` on every grep here, and it is not defensive noise. This script runs under
# `set -e` with `pipefail`, and a binary with NO RPATH is the healthy case -- `grep RPATH`
# then exits 1, the assignment inherits it, and the script dies silently at the exact moment
# it is about to report a clean result. That happened on the first run: the build succeeded,
# the artifact was correct, and the build record was never written.
INTERP="$(readelf -l "$OUT" 2>/dev/null | sed -n 's/.*interpreter: \(.*\)\]/\1/p' || true)"
RPATH="$(readelf -d "$OUT" 2>/dev/null | grep RPATH | sed 's/.*\[\(.*\)\]/\1/' || true)"
RUNPATH="$(readelf -d "$OUT" 2>/dev/null | grep RUNPATH | sed 's/.*\[\(.*\)\]/\1/' || true)"
say "  interp    ${INTERP:-none}"
say "  rpath     ${RPATH:-none}"
say "  runpath   ${RUNPATH:-none}"
UNRES="$(ldd "$OUT" 2>/dev/null | grep -c 'not found' || true)"
YOCTO="$(ldd "$OUT" 2>/dev/null | grep -c '/yocto' || true)"
say "  unresolved deps      ${UNRES:-0}"
say "  deps resolved from /yocto  ${YOCTO:-0}"
[ "${UNRES:-0}" -eq 0 ] || { echo "  REFUSING: unresolved dependencies" >&2; exit 1; }
[ "${YOCTO:-0}" -eq 0 ] || { echo "  REFUSING: a dependency resolves from /yocto" >&2; exit 1; }
case "$INTERP" in *yocto*) echo "  REFUSING: ELF interpreter under /yocto" >&2; exit 1;; esac
if strings -a "$OUT" 2>/dev/null | grep -q '/yocto'; then
    say "  NOTE: the binary contains a /yocto string (build-time path). Not a runtime dep,"
    say "        but recorded below so it is visible."
    HAS_STR=true
else
    HAS_STR=false
fi

# ---------------------------------------------------------------- build record
mkdir -p "$(dirname "$RECORD")"
cat > "$RECORD" <<JSON
{
  "_comment": [
    "Build record for the Debian-host gateway. Written by ops/build-gateway.sh.",
    "The BINARY is not committed (.gitignore excludes backend/apps/gateway/target/);",
    "this record is how a rebuilt binary is compared against the one that was verified.",
    "Built natively for this host, NOT with the Yocto SDK -- that SDK targets aarch64-oe-linux",
    "and cannot produce a binary that runs on Debian x86_64 at all."
  ],
  "relative_path": "backend/apps/gateway/target/release/symon-gateway",
  "size_bytes": $(stat -c %s "$OUT"),
  "sha256": "$AFTER",
  "st_nlink": $(stat -c %h "$OUT"),
  "elf_interpreter": "${INTERP:-}",
  "rpath": "${RPATH:-}",
  "runpath": "${RUNPATH:-}",
  "unresolved_deps": ${UNRES:-0},
  "deps_from_yocto": ${YOCTO:-0},
  "contains_yocto_string": $HAS_STR,
  "rustc": "$(rustc --version)",
  "cargo": "$(cargo --version)",
  "host_triple": "$HOST_TRIPLE",
  "locked": $( [ -n "$LOCKED" ] && echo true || echo false ),
  "built_on": "$(date -Is)"
}
JSON
say "build record: $RECORD"
say "OK"
