# AWS targets, and the ambiguity worth resolving before building anything.
#
# "meta-symoneural-aws" could mean either of two unrelated things, and they need different
# work:
#
#   1. AWS Graviton / EC2 aarch64 Linux -- a real Yocto target. Build
#      symoneural-arm64 from meta-symoneural-bsp; the resulting image boots on Graviton.
#      Nothing extra is needed and no AWS-specific layer is involved.
#
#   2. AWS IoT Greengrass on an edge device -- this needs meta-aws, which is upstream and
#      is NOT in /home/google/yocto:
#          git -C /home/google/yocto clone https://github.com/aws4embeddedlinux/meta-aws
#      Then add both it and this layer to bblayers.conf.
#
# A Fire TV stick is NEITHER of these. Fire OS is Android -- see
# meta-symoneural-quail/conf/include/android-notes.inc. It is listed under "aws" in
# conversation because Amazon sells it, which is not a build system relationship.
#
# This layer holds no recipes yet. That is a statement about what has been decided, not an
# unfinished file: until the choice between 1 and 2 is made, any recipe here would encode
# a guess.
