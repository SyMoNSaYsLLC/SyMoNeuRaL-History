#!/usr/bin/env bash
# What is actually RESIDENT right now -- distinct from installed and from selected.
# Reads the live API and the governor. Neither is inferred from disk.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── resident now ───────────────────────────────────────────"
if api_up; then
  curl -fsS "$API_BASE/api/status" 2>/dev/null \
    | python3 "$_MODELS_DIR/../_fmt_units.py" | grep -E 'chat|image|remix|voice' || true
else
  warn "API down -- residency UNKNOWN (not 'none')"
fi
echo
say "── card ───────────────────────────────────────────────────"
"$ROOT/scripts/gpu-governor.sh" status 2>/dev/null | sed 's/^/  /' || warn "governor status UNKNOWN"
echo
print_payload_state
