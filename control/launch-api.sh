#!/usr/bin/env bash
# Launch / stop / inspect the SyMoNeuRaL inference API (chat, image, ravencalc, remix).
#
#   launch-api.sh start|stop|status|log
#
# Wraps `scripts/symoneural.sh`, which is the real implementation. Prefers the systemd unit
# when it is installed, because that is what runs in production and what survives a reboot.
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  start)
    if systemctl list-unit-files symoneural-api.service &>/dev/null; then
      say "starting symoneural-api.service (systemd)"; sudo systemctl start symoneural-api.service
    else
      say "starting via scripts/symoneural.sh (no unit installed)"; "$ROOT/scripts/symoneural.sh" on
    fi
    sleep 2; api_up && say "API up on $API_BASE" || warn "API not answering yet -- check: control/launch-api.sh log" ;;
  stop)   say "stopping API and releasing the card"; "$ROOT/scripts/symoneural.sh" off ;;
  status) "$ROOT/scripts/symoneural.sh" status ;;
  log)    "$ROOT/scripts/symoneural.sh" log ;;
  *) die "usage: launch-api.sh start|stop|status|log" ;;
esac
