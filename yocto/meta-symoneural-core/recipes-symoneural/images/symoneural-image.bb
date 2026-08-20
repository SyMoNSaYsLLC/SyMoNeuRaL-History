SUMMARY = "A bootable SyMoNeuRaL appliance: the serving path and nothing decorative"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit core-image

IMAGE_FEATURES += "ssh-server-openssh package-management"
# package-management is in the list on purpose and is the point of the whole exercise:
# with it, and with the flat apt repository scripts/build-apt-repo.sh publishes, a target
# built from this image upgrades with `apt update && apt upgrade` exactly as the reference
# workstation does. Without it, every update is a reflash.

IMAGE_INSTALL:append = " \
    packagegroup-symoneural-serving \
    packagegroup-base-extended \
    kernel-modules \
"

# Weights are not in the image and cannot be: backend/models is ~104 GiB on the reference
# box, which is larger than most targets' whole storage. The image ships
# scripts/fetch-models.sh, and `symoneural-cli status` reports the surfaces as not built
# until the weights and the engine binaries exist. That is accurate, not a stub.
IMAGE_ROOTFS_EXTRA_SPACE = "2097152"

# No X, no wayland, no browser. The only interface this appliance offers is HTTP.
IMAGE_FEATURES:remove = "x11-base hwcodecs"

export IMAGE_BASENAME = "symoneural-image"
