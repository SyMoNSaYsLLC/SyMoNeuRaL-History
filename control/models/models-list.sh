#!/usr/bin/env bash
# What model payloads are present on disk. Read-only.
# Wraps tools/modelops_inventory.py -- the scan authority. Reimplementing the scan here
# would create a second answer to "what is installed", which is the drift this folder exists
# to avoid.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$INVENTORY"
say "── model inventory (measured) ─────────────────────────────"
python3 "$INVENTORY" "$@"
echo
print_payload_state
