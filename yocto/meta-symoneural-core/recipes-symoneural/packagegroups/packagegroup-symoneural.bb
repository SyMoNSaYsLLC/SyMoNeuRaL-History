SUMMARY = "The SyMoNeuRaL serving path, as one install target"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit packagegroup

PACKAGES = "\
    packagegroup-symoneural \
    packagegroup-symoneural-serving \
    packagegroup-symoneural-dev \
"

# The serving path and nothing else: the API, the CLI, the site and the web server in
# front of it. This is what a target that only has to answer requests needs.
RDEPENDS:packagegroup-symoneural-serving = "\
    symoneural-stack-api \
    symoneural-stack-cli \
    symoneural-stack-site \
    caddy \
"

# The generators and the test suites. Separated because a deployed target has no reason
# to carry the tools that produced its own site -- they are a build-host concern, and
# tools/build_gallery.py needs the GPU.
RDEPENDS:packagegroup-symoneural-dev = "\
    symoneural-stack-tools \
    python3-pytest \
    nodejs \
"

RDEPENDS:packagegroup-symoneural = "\
    packagegroup-symoneural-serving \
"
