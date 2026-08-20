SUMMARY = "A bootable SyMoNeuRaL appliance: the serving path and nothing decorative"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit core-image

IMAGE_FEATURES += "ssh-server-openssh package-management"
# package-management is in the list on purpose and is the point of the whole exercise:
# it puts apt on the target, which makes the target *capable* of `apt update && apt
# upgrade` the moment a repository it can actually reach is configured. That reachable
# repository is the missing half and is not in this tree: the flat repository
# scripts/build-apt-repo.sh publishes is `deb [trusted=yes] file:///home/google/symoneural-apt ./`,
# a build-host path no target can see, and the script's own closing paragraph says the
# trusted=yes argument does not survive the repository being served over a network --
# reaching a target takes both serving that directory over the network and `--sign`,
# and no script here does either yet. An earlier version of this comment promised
# upgrades "exactly as the reference workstation does"; that is true only on the
# workstation, the one machine where that file:// path exists. So today every update of
# a deployed target is a reflash. Without package-management it would be a reflash with
# no other path ever possible.

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
