# Put the Apple device libraries inside the SDK, not on the target.
#
#     require ${LAYERDIR}/../meta-symoneural-darwin/conf/include/sdk-apple-bridge.inc
#     bitbake symoneural-image -c populate_sdk
#
# TOOLCHAIN_TARGET_TASK and IMAGE_INSTALL are different variables and the mistake is easy:
# appending to IMAGE_INSTALL puts usbmuxd on the running appliance and leaves the SDK
# without it, so the cross-development host still cannot see an attached iPhone. This is
# the SDK's target task, which is what ends up in the installer's sysroot.
TOOLCHAIN_TARGET_TASK:append = " \
    usbmuxd \
    libimobiledevice \
    libimobiledevice-dev \
    libimobiledevice-tools \
    libusbmuxd \
    libusbmuxd-dev \
    libplist \
    libplist-dev \
"

# The -dev packages are named explicitly. Without them the SDK carries the shared objects
# and no headers, so linking works and compiling does not -- a failure that looks like a
# missing include path rather than a missing package.
