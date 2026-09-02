#!/usr/bin/env bash
# GPU/runtime state. Delegates to control/gpu.sh -- the existing wrapper -- rather than
# calling the governor directly, so there is one wrapper per authority and no duplication.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
exec "$_MODELS_DIR/../gpu.sh" "${@:-status}"
