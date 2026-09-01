#!/usr/bin/env bash
# DispatchOS surface. It lives INSIDE the API process behind SYMONEURAL_DISPATCHOS_ENABLED,
# so "launching" it means making sure the flag is on and the API is up.
#
#   launch-dispatchos.sh status|open|enable
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  status)
    api_up || { warn "API down -- control/launch-api.sh start"; exit 1; }
    say "dispatchos store: $ROOT/run/dispatchos.db"
    # /api/dispatchos/board is the surface's own health read. A 401/403 still proves the
    # routes are mounted -- it means the surface is up and asking for a token, which is a
    # different thing from 404 (not mounted at all).
    code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$API_BASE/api/dispatchos/board" 2>/dev/null)
    case "$code" in
      200)     say "mounted and answering (HTTP 200)" ;;
      401|403) say "mounted, needs a token (HTTP $code)" ;;
      404)     warn "not mounted (HTTP 404) -- enable it: control/launch-dispatchos.sh enable" ;;
      *)       warn "unexpected HTTP $code from /api/dispatchos/board" ;;
    esac ;;
  open) require_api; xdg-open "$API_BASE/dispatchos.html" 2>/dev/null || say "open $API_BASE/dispatchos.html" ;;
  enable)
    say "enabling the dispatchos surface (writes the systemd drop-in, needs sudo)"
    sudo "$ROOT/scripts/enable-surfaces.sh" dispatchos ;;
  *) die "usage: launch-dispatchos.sh status|open|enable" ;;
esac
