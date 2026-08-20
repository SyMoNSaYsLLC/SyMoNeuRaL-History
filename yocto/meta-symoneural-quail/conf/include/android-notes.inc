# Android and Fire OS. Read this before adding a machine conf to this layer.
#
# There is no Yocto machine for Android, and this layer does not invent one. Android's C
# library is bionic; an OpenEmbedded toolchain emits glibc or musl binaries, and Android
# will not load them. That is an ABI fact, not a missing recipe, and a machine conf named
# symoneural-android would produce binaries that build cleanly and fail at exec.
#
# What DOES reach the target, both real and both supported upstream:
#
#   Swift SDK for Android      published by swift.org as an artifactbundle alongside the
#                              Static Linux and WebAssembly SDKs.
#                                swift sdk install <url> --checksum <sum>
#                                swift build --swift-sdk android
#
#   Android NDK                for the C and C++ parts. Standard cross toolchain, entirely
#                              outside bitbake.
#
# Fire OS is Android, so a Fire TV stick is an aarch64 Android target and takes the same
# toolchain -- there is no separate "firestick" anything to build.
#
# yocto/scripts/symoneural-sdk.sh android drives the Swift path and reports what is
# missing rather than failing inside a compiler.
#
# WHAT THIS LAYER IS FOR, then: the aarch64 Linux side of the same work. An Android
# handset talking to a SyMoNeuRaL appliance needs the appliance, and that appliance is
# meta-symoneural-bsp's symoneural-arm64. This layer holds what is specific to serving
# Android clients -- nothing yet, and it says so rather than shipping a stub recipe.
