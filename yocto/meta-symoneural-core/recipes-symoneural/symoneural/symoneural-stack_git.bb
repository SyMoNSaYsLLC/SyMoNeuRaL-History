SUMMARY = "SyMoNeuRaL local AI stack -- CLI, API, site and operator tooling"
DESCRIPTION = "The first-party half of the stack: the FastAPI service, the operator CLI, \
the generated static site, the GPU governor and the shell tooling. Model weights and the \
llama.cpp / stable-diffusion.cpp binaries are not here -- those are fetched and built on \
the target, against its own driver."
HOMEPAGE = "https://symoneural.com"
LICENSE = "CLOSED"
SECTION = "science"

# CLOSED is the accurate value and is chosen deliberately rather than for convenience.
# LICENSES.md section 7 puts api.py, the generators, the CLI, ravencalc.py, the shell
# tooling, backend/apps/reinforce and backend/apps/remix under "all rights reserved,
# covered by no licence in that file". Declaring MIT here to make the QA warning go away
# would be a licence grant made by a build file, which is not a thing a build file may do.
# The third-party components this depends on carry their own licences and are packaged by
# their own recipes, where those licences are declared.

SRC_URI = "${SYMONEURAL_GIT_URI}"
SRCREV = "${SYMONEURAL_SRCREV}"
S = "${WORKDIR}/git"

# AUTOREV in the default means the recipe has no fixed version. That is correct for a
# working branch and wrong for a release, so the distro exposes SYMONEURAL_SRCREV and this
# is where you pin it.
PV = "0.1.0+git${SRCPV}"

inherit systemd

DEPENDS = "python3-native"
RDEPENDS:${PN}-cli = "python3-core python3-json python3-sympy python3-shell"
RDEPENDS:${PN}-api = " \
    ${PN}-cli \
    python3-core \
    python3-fastapi \
    python3-uvicorn \
    python3-pydantic \
    python3-sympy \
    python3-httpx \
"

PACKAGES =+ "${PN}-cli ${PN}-api ${PN}-site ${PN}-tools"

# Anything that must never be packaged, removed from the fetched tree before install
# rather than merely omitted from FILES. Omitting a path from FILES leaves it in the
# sysroot and produces an "installed but not shipped" QA error; deleting it means the file
# is not on the build host's staging area either, which is the actual intent. This is the
# same list scripts/build-deb.sh enforces, for the same reason: the first .deb this
# project produced shipped backend/apps/remix/.env.
SYMONEURAL_NEVER_SHIP = " \
    training/corpus.jsonl \
    training/build_dataset.py \
    training/project-history/build_history_corpus.py \
    training/adapter \
    training/adapter-qwen36 \
    backend/apps/remix/.env \
    .claude \
    .github \
"

do_install() {
    install -d ${D}/opt/symoneural

    for p in ${SYMONEURAL_NEVER_SHIP}; do
        rm -rf "${S}/$p"
    done

    # A guard, not a comment. If any of those paths survived the loop above, the build
    # stops here rather than producing a package that carries the training corpus.
    for p in ${SYMONEURAL_NEVER_SHIP}; do
        if [ -e "${S}/$p" ]; then
            bbfatal "refusing to package: $p is still present in ${S}"
        fi
    done

    cp -a ${S}/. ${D}/opt/symoneural/
    rm -rf ${D}/opt/symoneural/.git ${D}/opt/symoneural/.gitignore

    install -d ${D}${bindir}
    ln -sf /opt/symoneural/bin/symoneural-cli ${D}${bindir}/symoneural-cli
    chmod 0755 ${D}/opt/symoneural/bin/symoneural-cli

    # The unit in the repo is a template: systemd cannot express a relative path, so
    # scripts/install-service.sh substitutes the checkout root at install time. The
    # packaged copy is installed to a fixed prefix, so the substitution happens here and
    # the value is /opt/symoneural. Shipping the template unsubstituted would install a
    # unit whose ExecStart is the literal string @@ROOT@@.
    install -d ${D}${systemd_system_unitdir}
    sed 's|@@ROOT@@|/opt/symoneural|g' ${S}/ops/symoneural-api.service \
        > ${D}${systemd_system_unitdir}/symoneural-api.service
    sed 's|@@ROOT@@|/opt/symoneural|g' ${S}/ops/symoneural-gateway.service \
        > ${D}${systemd_system_unitdir}/symoneural-gateway.service

    # Runtime state, and the secrets file the unit reads with EnvironmentFile=. Created
    # empty and 0600: the unit must not use Environment=, because `systemctl show` prints
    # that to any user on the box.
    install -d -m 0755 ${D}${localstatedir}/lib/symoneural
    install -d -m 0700 ${D}${sysconfdir}/symoneural
    touch ${D}${sysconfdir}/symoneural/api.env
    chmod 0600 ${D}${sysconfdir}/symoneural/api.env

    # The webroot the site package populates. Owned by the web server at runtime, not at
    # package time -- Yocto has no www-data yet at do_install.
    install -d ${D}${localstatedir}/www/symoneural
    cp -a ${S}/site/. ${D}${localstatedir}/www/symoneural/
}

FILES:${PN}-cli = "/opt/symoneural/bin ${bindir}/symoneural-cli /opt/symoneural/scripts"
FILES:${PN}-api = " \
    /opt/symoneural/backend \
    /opt/symoneural/ops \
    ${systemd_system_unitdir} \
    ${sysconfdir}/symoneural \
    ${localstatedir}/lib/symoneural \
"
FILES:${PN}-site = "${localstatedir}/www/symoneural /opt/symoneural/site"
FILES:${PN}-tools = "/opt/symoneural/tools /opt/symoneural/tests"
FILES:${PN} = "/opt/symoneural"

CONFFILES:${PN}-api = "${sysconfdir}/symoneural/api.env"

SYSTEMD_SERVICE:${PN}-api = "symoneural-api.service"
# Not enabled by default. The .deb does not start anything either, and for the same
# reason: the API is useless until weights exist under backend/models, and a unit that
# restarts forever on a box with no weights fills the journal and looks like a fault.
SYSTEMD_AUTO_ENABLE:${PN}-api = "disable"

# The tree carries .py files that are byte-compiled at first run into __pycache__, and
# shell scripts with a #!/usr/bin/env bash line. Neither is an ELF object, so the usual
# stripping and dependency scanning have nothing to do.
INSANE_SKIP:${PN} += "arch"
INSANE_SKIP:${PN}-cli += "arch"
