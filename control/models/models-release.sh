#!/usr/bin/env bash
# Hand the card back. Delegates to control/gpu.sh; the governor is the only thing permitted
# to touch the lock.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
[ $# -gt 0 ] || die "usage: models-release.sh <chat|image|train|...>  |  all"
if [ "$1" = "all" ]; then exec "$_MODELS_DIR/../gpu.sh" release-all; fi
exec "$_MODELS_DIR/../gpu.sh" release "$1"
