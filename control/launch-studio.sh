#!/usr/bin/env bash
# Studio surface + its render UI. Two separate things:
#   * the Studio routes live in the API behind SYMONEURAL_STUDIO_ENABLED
#   * the render UI is a real separate server on :8188, run by scripts/symoneural-ui.sh
#
#   launch-studio.sh start|stop|status|open|enable
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  start)  say "starting render UI on 127.0.0.1:8188"; "$ROOT/scripts/symoneural-ui.sh" start ;;
  stop)   "$ROOT/scripts/symoneural-ui.sh" stop ;;
  status) "$ROOT/scripts/symoneural-ui.sh" status
          api_up && curl -fsS -m 5 -o /dev/null -w 'GET /api/studio -> HTTP %{http_code}\n' "$API_BASE/api/studio" || true ;;
  open)   xdg-open "$API_BASE/studio.html" 2>/dev/null || say "open $API_BASE/studio.html" ;;
  enable) say "enabling the studio surface (needs sudo)"; sudo "$ROOT/scripts/enable-surfaces.sh" studio ;;
  *) die "usage: launch-studio.sh start|stop|status|open|enable" ;;
esac
