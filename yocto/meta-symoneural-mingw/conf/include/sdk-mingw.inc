# A Windows-hosted SDK: bitbake builds a cross-toolchain whose HOST is Windows and whose
# TARGET is still the appliance. Require this from local.conf, then:
#
#     bitbake symoneural-image -c populate_sdk
#
# The installer arrives in tmp/deploy/sdk/ as a .zip rather than the .sh a Linux SDK
# produces, because the machine that runs it is Windows.
#
# meta-mingw is upstream and is NOT in /home/google/yocto -- clone it first, or every
# recipe below resolves to nothing:
#     git -C /home/google/yocto clone https://git.yoctoproject.org/meta-mingw
SDKMACHINE = "x86_64-mingw32"

# What the operator gets on the Windows side. The CLI is Python and needs no
# cross-compilation at all; what actually needs a Windows host toolchain is symon-gateway
# (Rust) and anything linking against the target sysroot.
TOOLCHAIN_HOST_TASK:append = " nativesdk-cmake nativesdk-ninja"

# Canadian cross builds are slower than they look -- the toolchain that builds the
# toolchain is itself built first. Expect roughly double a native SDK's wall clock, and do
# not read the long silence as a hang.
