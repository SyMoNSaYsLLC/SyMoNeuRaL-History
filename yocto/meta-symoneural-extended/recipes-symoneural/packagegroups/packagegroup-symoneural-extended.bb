SUMMARY = "The optional surfaces: studio, ComfyUI, reinforce, remix"
DESCRIPTION = "Everything gated behind an environment switch on the reference box. Each \
of these is off unless two variables are set, which is this project's own convention for \
a surface that reaches the host or the card -- see apps/voice and apps/asicminer."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit packagegroup

PACKAGES = "\
    packagegroup-symoneural-extended \
    packagegroup-symoneural-studio \
    packagegroup-symoneural-training \
"

# Studio drives ComfyUI over HTTP and a WebSocket. websockets and httpx are the whole
# dependency set on the reference box -- both already in the serving interpreter -- so the
# bridge adds nothing to the target beyond what the API already needs.
RDEPENDS:packagegroup-symoneural-studio = "\
    symoneural-stack-api \
    python3-websockets \
    python3-httpx \
"

# Training is NOT in the default set and is not a smaller version of the serving path: a
# QLoRA run wants ~12 GiB of the 15.92 GiB card, so a box doing it cannot also serve chat
# or image. It gets its own group so that choice is made explicitly.
RDEPENDS:packagegroup-symoneural-training = "\
    python3-core \
    python3-numpy \
    git \
"

RDEPENDS:packagegroup-symoneural-extended = "\
    packagegroup-symoneural-studio \
"

# ComfyUI itself has no recipe here and that is deliberate rather than unfinished. It is a
# third-party clone with its own .venv and 223 packages including torch 2.13.0+cu130 built
# for sm_120; packaging that as recipes would mean maintaining a CUDA Python stack in
# bitbake against a driver the target may not have. scripts/comfyui.sh manages it from the
# checkout, and the image ships that script.
