#!/usr/bin/env bash
# Stage a candidate bundle.
# Wraps: scripts/modelops/symoneural-modelops-stage.sh. Pass-through to the modelops authority, which already refuses to
# download or activate anything without an explicit flag. No staging logic lives here.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$MODELOPS"
[ $# -gt 0 ] || { say "staging modes (dry-run default):"; bash "$MODELOPS" --dry-run; exit 0; }
exec bash "$MODELOPS" "$@"
