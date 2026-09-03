#!/usr/bin/env bash
# Shared preamble for control/models/. Sources control/_common.sh rather than restating it.
#
# ## The distinction every launcher here must preserve
#
# A provenance record is not a model. `backend/models/PROVENANCE.json` currently carries 11
# entries and there are zero weight files on disk, so a tool that counts records and calls
# them models reports eleven installed models on a machine that has none. That is the exact
# failure this file exists to prevent, and it is not hypothetical -- a stale figure of
# "28 weights / 17 unresolved / 78 GiB" was quoted from a docstring into a planning document
# while the measured count was 0.
#
#   PAYLOAD          learned-model bytes on disk. The only thing that can serve a request.
#   METADATA         config/tokeniser/scaffolding. Present without a payload means nothing
#                    is installed.
#   PROVENANCE       a historical record of where an artefact came from. Says nothing about
#                    whether it is here now.
#   CONFIGURATION    which model a surface SELECTS. A selection is not a presence.
#   ABSENT           measured, and measured as not here. A normal state, not an error.
#   UNKNOWN          could not be established. Never collapsed into ABSENT or into a guess.
#
# ABSENT and UNKNOWN are deliberately distinct. "I looked and there is nothing" and "I could
# not look" are different answers and a caller acts differently on each.
set -uo pipefail

_MODELS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_MODELS_DIR/../_common.sh"

INVENTORY="$ROOT/tools/modelops_inventory.py"
MODELOPS="$ROOT/scripts/modelops/symoneural-modelops-stage.sh"
PROVENANCE="$ROOT/backend/models/PROVENANCE.json"
MODELS_DIR="$ROOT/backend/models"

# Payload = non-empty file with a weight extension. Size matters: a 0-byte placeholder is
# scaffolding, not a model, and counting it would report an installed model that cannot load.
payload_count() {
  # UNKNOWN, not 0. "I could not look" is not "there is nothing here", and a caller
  # that cannot tell them apart will report an empty box as a verified-empty box.
  [ -n "${MODELS_DIR:-}" ] || { echo UNKNOWN; return; }
  [ -d "$MODELS_DIR" ] || { echo UNKNOWN; return; }
  [ -r "$MODELS_DIR" ] || { echo UNKNOWN; return; }
  find "$MODELS_DIR" -type f -size +0 \
    \( -name '*.gguf' -o -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' \) \
    2>/dev/null | grep -vc '/hf/hub/' || true
}

adapter_payload_count() {
  local n=0 d
  for d in "$ROOT/training/adapter" "$ROOT/training/adapter-qwen36"; do
    [ -d "$d" ] || continue
    n=$((n + $(find "$d" -type f -size +0 \
      \( -name '*.safetensors' -o -name '*.bin' -o -name '*.gguf' \) 2>/dev/null | wc -l)))
  done
  printf '%s' "$n"
}

# The line every launcher prints. One wording, so "no model installed" cannot be phrased
# three different ways and be misread as three different conditions.
print_payload_state() {
  local n; n="$(payload_count)"
  if [ "$n" = "UNKNOWN" ]; then
    printf 'LEARNED MODEL PAYLOADS: UNKNOWN (%s not readable)\n' "$MODELS_DIR"
  else
    printf 'LEARNED MODEL PAYLOADS: %s\n' "$n"
    # An `if` rather than `[ ... ] && printf`, because this is the last statement of the
    # last function most read launchers call, so its value IS the script's exit status.
    # `[ 6 -eq 0 ] && ...` short-circuits to 1, and eight read-only launchers therefore
    # exited 1 -- reporting failure precisely BECAUSE payloads had been restored, while
    # printing a completely correct inventory. It only passed while the count was 0.
    if [ "$n" -eq 0 ]; then
      printf '  no model installed -- this is a valid state, not an error\n'
    fi
  fi
}

require_authority() {
  [ -e "$1" ] || die "required authority missing: $1
  control/models/ wraps existing tooling; it does not reimplement it."
}
