#!/usr/bin/env bash
# LoRA adapters.
# Wraps: training/adapter*/ on disk. Adapter payloads are protected. Adapter weights are PROTECTED (docs/ops/EXPORTS.md rule 2): this lists
# presence and never prints contents.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── adapters ───────────────────────────────────────────────"
for d in training/adapter training/adapter-qwen36; do
  if [ -d "$ROOT/$d" ]; then
    printf '  %-26s dir present, %s payload file(s)\n' "$d" \
      "$(find "$ROOT/$d" -type f -size +0 \( -name '*.safetensors' -o -name '*.bin' -o -name '*.gguf' \) 2>/dev/null | wc -l)"
  else
    printf '  %-26s ABSENT\n' "$d"
  fi
done
printf '\n  ADAPTER PAYLOADS: %s\n' "$(adapter_payload_count)"
printf '  note: adapter weights are protected and are never printed or exported\n'
