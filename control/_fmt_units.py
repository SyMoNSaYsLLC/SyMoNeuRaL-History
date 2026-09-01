"""Format /api/status JSON as one aligned line per surface. Reads stdin, prints nothing on
bad input -- the caller has already reported whether the API answered."""
import sys, json

try:
    units = json.load(sys.stdin).get("units", [])
except Exception:
    sys.exit(0)

for u in units:
    print("  {:<26} {}".format(u.get("id", "?"), u.get("state", "?")))
