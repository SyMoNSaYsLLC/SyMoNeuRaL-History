#!/usr/bin/env bash
# Shared preamble for every launcher in control/.
#
# Nothing in control/ implements behaviour. Each script is a thin, documented wrapper over
# the tool that already does the job (scripts/, ops/, systemd), so there is exactly one
# implementation of everything and this folder cannot drift from it.
#
# The root calculation has been wrong four times in this repo and it fails silently, because
# the wrong parent is usually a directory that exists. Same guard as scripts/symoneural.sh.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || {
  echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }

API_PORT="${SYMONEURAL_PORT:-8800}"
API_BASE="http://127.0.0.1:$API_PORT"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# True when the API answers. Used by launchers whose surface lives inside the API process:
# starting "dispatchos" means starting the API with that surface enabled, not a new daemon.
api_up() { curl -fsS -m 3 -o /dev/null "$API_BASE/api/status" 2>/dev/null; }

require_api() {
  api_up || die "API is not answering on $API_BASE
  start it first:  control/launch-api.sh start"
}
