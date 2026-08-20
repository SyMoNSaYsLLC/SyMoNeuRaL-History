SUMMARY = "The exact Python environment the serving path uses"
DESCRIPTION = "CLAUDE.md: the serving API deliberately uses only the system interpreter, \
because fastapi, uvicorn, pydantic and sympy are already OS packages and there is no \
virtualenv in the serving path. This packagegroup is that policy expressed for a Yocto \
target: the four are installed as distribution packages, so the target has the same \
property -- nothing to activate, nothing to pip install."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit packagegroup

# Every name here is a recipe in meta-python, not a pip name. They are not
# interchangeable: pip's `fastapi` is `python3-fastapi` to bitbake, and asking for the
# former produces "Nothing PROVIDES", which reads like the package does not exist.
RDEPENDS:${PN} = "\
    python3-core \
    python3-fastapi \
    python3-uvicorn \
    python3-pydantic \
    python3-sympy \
    python3-httpx \
    python3-websockets \
    python3-multipart \
    python3-jinja2 \
"

# Deliberately NOT here: torch, transformers, peft, cupy. Those belong to training and to
# backend/apps/reinforce, which are not part of the serving path and have their own venvs
# on the reference box (training/.venv, contrib/cuda-samples/python/.venv pinned at seven
# packages). Rolling them into the serving image would put a multi-gigabyte CUDA stack on
# a target that only answers HTTP.
