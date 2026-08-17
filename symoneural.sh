#!/usr/bin/env bash
# Production service control: on, off, and what it did.
#
# The surfaces are open and free, which means the important command here is `off`. It stops
# the API, stops whatever holds the GPU, and releases the governor -- after which
# symoneural.com still serves every static page, just without the live surfaces. Nothing
# about turning it off is a rollback or a redeploy.
#
# For boot-start and crash-restart, install the systemd unit instead:
#   sudo ops/install-service.sh
#
#   symoneural.sh on          start the API (loopback; Caddy proxies /api to it)
#   symoneural.sh off         stop everything, free the card
#   symoneural.sh status      is it up, what is resident, what is queued
#   symoneural.sh log         recent requests
#   symoneural.sh off-at 07:00   turn it off automatically at a wall-clock time
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RUN="$HERE/run"; mkdir -p "$RUN"
PIDFILE="$RUN/api.pid"
PORT="${SYMONEURAL_PORT:-8800}"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "${1:-status}" in
  on)
    if running; then echo "already up (pid $(cat "$PIDFILE"))"; exit 0; fi
    setsid python3 "$HERE/api.py" >>"$RUN/api.out" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 2
    if running; then
      echo "symoneural api up on 127.0.0.1:$PORT (pid $(cat "$PIDFILE"))"
      echo "remember: 'symoneural.sh off' ends it whenever you like."
    else
      echo "failed to start -- see $RUN/api.out" >&2; exit 1
    fi
    ;;

  off)
    if running; then kill "$(cat "$PIDFILE")" 2>/dev/null; sleep 1; fi
    rm -f "$PIDFILE"
    # Whatever the API left holding the card goes too, then the lock is cleared so the
    # next tenant is not left waiting behind a process that no longer exists.
    pkill -f 'llama-server' 2>/dev/null
    pkill -f 'sd-cli' 2>/dev/null
    # Only our own surfaces -- a fine-tune holding the card is not ours to end.
    "$HERE/gpu-governor.sh" release chat >/dev/null 2>&1
    "$HERE/gpu-governor.sh" release image >/dev/null 2>&1
    echo "surfaces off. static pages unaffected; the card is free."
    ;;

  status)
    if running; then echo "api        up (pid $(cat "$PIDFILE")) on 127.0.0.1:$PORT"
    else echo "api        down"; fi
    curl -s --max-time 3 "http://127.0.0.1:$PORT/api/status" | python3 -m json.tool 2>/dev/null \
      || "$HERE/gpu-governor.sh" status
    ;;

  log)
    tail -n "${2:-40}" "$RUN/api.log" 2>/dev/null || echo "no log yet"
    ;;

  off-at)
    at="${2:?usage: off-at HH:MM}"
    # No at(1) dependency -- a detached sleep is enough and leaves an obvious process.
    secs=$(( $(date -d "$at" +%s) - $(date +%s) ))
    [ "$secs" -lt 0 ] && secs=$(( secs + 86400 ))
    setsid bash -c "sleep $secs; '$HERE/symoneural.sh' off" >/dev/null 2>&1 &
    echo "will turn off at $at (in $((secs / 60)) minutes)"
    ;;

  *) echo "usage: $(basename "$0") {on|off|status|log|off-at HH:MM}" >&2; exit 2 ;;
esac
