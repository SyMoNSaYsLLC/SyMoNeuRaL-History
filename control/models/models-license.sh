#!/usr/bin/env bash
# Licence status per artefact. Absence from a provenance record does NOT prove "unlicensed" --
# it proves nothing was recorded. This prints UNVERIFIED, never a licence conclusion.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── licence status ─────────────────────────────────────────"
printf '  first-party licence: %s\n' "$([ -f "$ROOT/LICENSE" ] && echo 'LICENSE present' || echo 'UNKNOWN')"
printf '  third-party notices: %s\n' "$([ -f "$ROOT/LICENSES.md" ] && echo 'LICENSES.md present' || echo 'UNKNOWN')"
echo
if [ "$(payload_count)" = "0" ]; then
  printf '  no payloads on disk -- per-artefact licence status: N/A\n'
else
  printf '  per-artefact licence: UNVERIFIED (no independent licence authority consulted)\n'
fi
echo
print_payload_state
