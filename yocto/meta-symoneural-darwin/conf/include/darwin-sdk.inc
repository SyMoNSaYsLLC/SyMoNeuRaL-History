# Where the Darwin Swift SDK lives, and why it is referenced rather than packaged.
#
# On the reference box the SDK is already installed and was extracted on 2026-07-25:
#
#   ~/.swiftpm/swift-sdks/darwin.artifactbundle          3.2 GiB
#     Developer/Platforms/MacOSX.platform/.../MacOSX26.5.sdk
#     Developer/Platforms/iPhoneOS.platform/.../iPhoneOS26.5.sdk
#     Developer/Platforms/iPhoneSimulator.platform/.../iPhoneSimulator26.5.sdk
#
#   target triples it declares, read out of its swift-sdk.json:
#     x86_64-apple-macosx   arm64-apple-macosx
#     arm64-apple-ios       arm64-apple-ios-simulator   x86_64-apple-ios-simulator
#
# So cross-compiling from this Linux host to macOS and iOS is set up, not hypothetical.
#
# NO RECIPE FETCHES OR PACKAGES THAT BUNDLE, and the reason is not squeamishness: it is
# extracted from an Xcode .xip downloaded under an Apple ID against the Xcode licence
# agreement, which permits use on Apple-branded hardware and does not permit
# redistribution. A recipe that copied it into a package would put Apple's SDK inside an
# artefact this project hands to other people. `xtool setup` re-derives it in minutes from
# a .xip the operator downloads themselves, which is the supported path and keeps the
# licence between Apple and the operator.
SYMONEURAL_DARWIN_SDK ?= "${HOME}/.swiftpm/swift-sdks/darwin.artifactbundle"

# The Swift toolchain that consumes it. `swift` is NOT on PATH on the reference box as of
# 2026-08-19 -- the SDK is installed and the compiler that would use it is not, so
# `swift build --swift-sdk arm64-apple-ios` fails at the first word. Install it with
# swiftly, per swift.org:
#   curl -O https://download.swift.org/swiftly/linux/swiftly-$(uname -m).tar.gz
#   tar zxf swiftly-$(uname -m).tar.gz && ./swiftly init --quiet-shell-followup
SYMONEURAL_SWIFT ?= "${HOME}/.local/share/swiftly/bin/swift"
