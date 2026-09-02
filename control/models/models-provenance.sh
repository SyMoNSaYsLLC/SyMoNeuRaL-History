#!/usr/bin/env bash
# Provenance RECORDS -- historical origin statements. A record is not an installed model and
# this script refuses to conflate them: it prints the record count and the payload count as
# two separate figures, always.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── provenance records ─────────────────────────────────────"
if [ -f "$PROVENANCE" ]; then
  python3 - "$PROVENANCE" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print(f"  PROVENANCE STATUS UNKNOWN -- unreadable: {e.__class__.__name__}"); raise SystemExit(0)
entries = d if isinstance(d, list) else d.get("artifacts", d.get("models", []))
print(f"  records: {len(entries)}")
print("  NOTE: a provenance record describes an artefact's origin.")
print("        It is NOT evidence the artefact is on disk now.")
PY
else
  printf '  PROVENANCE STATUS UNKNOWN -- no record file at %s\n' "$PROVENANCE"
fi
echo
print_payload_state
