#!/usr/bin/env bash
# House-naming verification.
# Wraps: the scripts/fetch-models.sh naming convention + backend/models/PROVENANCE.json. Rebranding is an EXISTING convention (scripts/fetch-models.sh:
# "Nothing under backend/models/ keeps an upstream filename"), so this inspects compliance
# rather than performing a rename.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── house naming ───────────────────────────────────────────"
printf '  convention: symon-1.0-* (language) / symoneural-image-* / symoneural-listen-*\n'
n="$(payload_count)"
if [ "$n" = "0" ]; then
  printf '  0 payloads on disk -- naming compliance: N/A\n'
else
  find "$MODELS_DIR" -type f -size +0 \( -name '*.gguf' -o -name '*.safetensors' \) 2>/dev/null \
    | grep -v '/hf/hub/' | while read -r f; do
        b="$(basename "$f")"
        case "$b" in symon-*|symoneural-*) printf '  ok       %s\n' "$b" ;;
                      *) printf '  UPSTREAM %s  <- house name not applied\n' "$b" ;; esac
      done
fi
echo
print_payload_state
