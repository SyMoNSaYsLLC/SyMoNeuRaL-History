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
# The record list is under "weights" in schema 1. This tried "artifacts" then "models"
# and defaulted to [], so it printed "records: 0" against a manifest holding six -- an
# empty success that reads like a passing check, which is the one thing this folder
# exists to prevent. An unrecognised shape is now UNKNOWN, never 0.
entries = None
if isinstance(d, list):
    entries = d
else:
    for _key in ("weights", "artifacts", "models"):
        if isinstance(d.get(_key), list):
            entries = d[_key]
            break
if entries is None:
    print("  PROVENANCE STATUS UNKNOWN -- no recognised record list in "
          f"{sorted(d) if isinstance(d, dict) else type(d).__name__}")
    raise SystemExit(0)
print(f"  records: {len(entries)}")
print("  NOTE: a provenance record describes an artefact's origin.")
print("        It is NOT evidence the artefact is on disk now.")
PY
else
  printf '  PROVENANCE STATUS UNKNOWN -- no record file at %s\n' "$PROVENANCE"
fi
echo
print_payload_state
