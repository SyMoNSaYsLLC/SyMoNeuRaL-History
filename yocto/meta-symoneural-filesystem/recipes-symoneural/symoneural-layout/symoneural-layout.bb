SUMMARY = "The on-disk layout: where state, secrets, weights and the webroot live"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://symoneural.conf"
S = "${WORKDIR}/sources"
UNPACKDIR = "${S}"

inherit allarch systemd

do_install() {
    # run/ is runtime state, not logs, and the name is load-bearing: call it logs/ and
    # sooner or later something logrotates it, which deletes gpu.lock.d while a surface is
    # holding the card. On a Yocto target /run is already a tmpfs, which is the same
    # convention this project adopted by hand.
    install -d -m 0755 ${D}${localstatedir}/lib/symoneural
    install -d -m 0755 ${D}${localstatedir}/lib/symoneural/run
    install -d -m 0755 ${D}${localstatedir}/lib/symoneural/output

    # Weights. A separate directory because it is ~104 GiB on the reference box and
    # therefore almost always a separate volume; the tmpfiles entry creates the mountpoint
    # so a missing volume presents as an empty directory rather than as a write into the
    # root filesystem that fills it.
    install -d -m 0755 ${D}${localstatedir}/lib/symoneural/models

    # 0700 and root-owned. api.env holds SPOTIFY_CLIENT_SECRET, VLLM_API_KEY and DJ_TOKEN,
    # and the unit reads it with EnvironmentFile= rather than Environment= because
    # `systemctl show` prints the latter to any user on the box.
    install -d -m 0700 ${D}${sysconfdir}/symoneural

    install -d ${D}${sysconfdir}/tmpfiles.d
    install -m 0644 ${S}/symoneural.conf ${D}${sysconfdir}/tmpfiles.d/symoneural.conf
}

FILES:${PN} = "\
    ${localstatedir}/lib/symoneural \
    ${sysconfdir}/symoneural \
    ${sysconfdir}/tmpfiles.d/symoneural.conf \
"
