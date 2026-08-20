SUMMARY = "Minimal initramfs: find the root, find the models volume, hand over"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

PACKAGE_INSTALL = "\
    initramfs-framework-base \
    initramfs-module-udev \
    initramfs-module-setup-live \
    busybox \
    base-passwd \
    ${VIRTUAL-RUNTIME_base-utils} \
"

# This image is deliberately small and does NOT load the GPU driver. An initramfs that
# initialises the card holds VRAM before the governor exists to arbitrate it, and the
# first surface to ask for the lock then OOMs at step 0 against memory nothing will
# release. The driver loads from the real root, under the governor's rules.
IMAGE_FEATURES = ""
export IMAGE_BASENAME = "symoneural-initramfs"
IMAGE_LINGUAS = ""
IMAGE_FSTYPES = "cpio.gz"
IMAGE_ROOTFS_SIZE = "8192"
IMAGE_ROOTFS_EXTRA_SPACE = "0"

inherit core-image

# The models volume is mounted by the initramfs rather than by fstab, because an fstab
# entry for a volume that is absent stops boot at the emergency shell. Here a missing
# volume is a message and a continued boot, and `symoneural-cli status` then reports the
# surfaces as not built -- which is the accurate reading, not a degraded mode.
