#!/usr/bin/env bash
# Launch a QLoRA fine-tune under the governor.
#
# STOP condition 3: refuses when the training corpus is absent, and never echoes it -- the
# corpus is protected trade secret (docs/ops/EXPORTS.md rule 2) and printing it here would
# put it in a terminal transcript.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
TRAINER="$ROOT/training/train_lora.py"
require_authority "$TRAINER"
[ -f "$ROOT/training/corpus.jsonl" ] || die "STOP: training corpus absent -- nothing to fine-tune on"
if "$ROOT/scripts/gpu-governor.sh" status 2>/dev/null | grep -qiE '^ *lock +held|holder'; then
  die "STOP: the governor reports another holder -- refusing to contend for the card"
fi
[ "${1:-}" = "--execute" ] || {
  say "fine-tune is a long GPU job and is not started without --execute"
  printf '  would run: %s under scripts/gpu-governor.sh with train\n' "training/train_lora.py"
  exit 2; }
shift
exec "$ROOT/scripts/gpu-governor.sh" with train -- python3 "$TRAINER" "$@"
