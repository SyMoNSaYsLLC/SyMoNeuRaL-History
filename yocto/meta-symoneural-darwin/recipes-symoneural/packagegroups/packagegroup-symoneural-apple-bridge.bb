SUMMARY = "Talk to, pair with and deploy to Apple devices over USB"
DESCRIPTION = "usbmuxd and the libimobiledevice family, so a SyMoNeuRaL target or SDK can \
enumerate, pair with, install onto and read logs from an attached iPhone or iPad. Every \
recipe named here already exists in meta-oe -- this group is the list, not new code."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit packagegroup

# Verified present in the meta-openembedded checkout on the reference box, by path:
#   meta-oe/recipes-connectivity/usbmuxd/usbmuxd_git.bb
#   meta-oe/recipes-connectivity/libimobiledevice/libimobiledevice_1.4.0.bb
#   meta-oe/recipes-connectivity/libimobiledevice/libtatsu_1.0.5.bb
#   meta-oe/recipes-connectivity/libimobiledevice-glue/libimobiledevice-glue_1.3.2.bb
#   meta-oe/recipes-extended/libimobiledevice/libplist_2.7.0.bb
#   meta-oe/recipes-extended/libimobiledevice/libusbmuxd_2.1.1.bb
#
# ideviceinstaller and idevicerestore are NOT in that checkout and are therefore not
# listed. Adding them would produce "Nothing PROVIDES", and a packagegroup that cannot be
# resolved is worse than a shorter one that can.
RDEPENDS:${PN} = "\
    usbmuxd \
    libimobiledevice \
    libimobiledevice-tools \
    libusbmuxd \
    libplist \
"

# usbhost is required in DISTRO_FEATURES or usbmuxd builds and then finds no device.
# conf/distro/symoneural.conf sets it; this note is here because the failure -- a daemon
# that starts, logs nothing and never sees the phone -- does not point at its cause.
