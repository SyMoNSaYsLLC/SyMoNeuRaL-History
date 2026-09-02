#!/usr/bin/env bash
# Restore the previous active model.
# Wraps: scripts/modelops/symoneural-modelops-stage.sh --rollback. The one mode that is safe to reach for in a hurry.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$MODELOPS"
exec bash "$MODELOPS" --rollback "$@"
