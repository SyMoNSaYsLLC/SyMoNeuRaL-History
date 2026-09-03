#!/usr/bin/env bash
# Which model each surface SELECTS.
# Wraps: tools/modelops_inventory.py (parses backend/api.py for the active set). A selection is CONFIGURATION, not presence: a surface can
# name a model that is not on disk, and this prints exactly that when it happens.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$INVENTORY"
say "── active defaults (configuration, not presence) ──────────"
python3 "$INVENTORY" 2>/dev/null | sed -n '/ACTIVE DEFAULTS/,/^--/p' | sed '$d'
echo
print_payload_state
# Last statement of the script, so its value is the exit status -- see the note in
# _models_common.sh's print_payload_state. `[ 6 = 0 ] && warn` short-circuits to 1 and
# made this read-only launcher report failure once payloads existed.
if [ "$(payload_count)" = "0" ]; then
  warn "a selected model is not a loaded model -- 0 payloads on disk"
fi
