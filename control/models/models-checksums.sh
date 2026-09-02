#!/usr/bin/env bash
# Recorded digests.
# Wraps: scripts/modelops/symoneural-modelops-stage.sh --inventory. With zero payloads there is nothing to verify, and saying so is the
# correct output -- not an empty success that reads like a passing check.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$MODELOPS"
say "── checksum verification ──────────────────────────────────"
n="$(payload_count)"
if [ "$n" = "0" ]; then
  printf '  no payload objects require verification (0 on disk)\n'
elif [ "$n" = "UNKNOWN" ]; then
  printf '  UNKNOWN -- model directory not readable\n'
else
  bash "$MODELOPS" --inventory
fi
echo
print_payload_state
