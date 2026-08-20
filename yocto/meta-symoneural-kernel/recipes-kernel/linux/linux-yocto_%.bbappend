# INERT AS SHIPPED, and worth saying so at the top rather than letting a reader assume these
# fragments reach a kernel. This append matches, but its base recipe never builds for either
# symoneural machine: `bitbake-layers show-appends` prints "linux-yocto_6.18.bb (skipped):",
# skipped on the qemu-only COMPATIBLE_MACHINE at linux-yocto_6.18.bb:55. The fragments below
# are the requirements, written down and version-controlled; they start being applied when a
# linux-yocto-custom.bb copy lands here with a real kernel tree. See the long comment above
# PREFERRED_PROVIDER_virtual/kernel in meta-symoneural-bsp/conf/machine/symoneural-workstation.conf.

FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

# Config fragments, not a defconfig. A whole defconfig would silently pin every unrelated
# option to whatever the reference box happened to have, and the next kernel uprev would
# carry those forward invisibly. Fragments say only what this stack requires.
SRC_URI += " \
    file://symoneural-gpu.cfg \
    file://symoneural-container.cfg \
"

KERNEL_FEATURES:append = " features/security/security.scc"
