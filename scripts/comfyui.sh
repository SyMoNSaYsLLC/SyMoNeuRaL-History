#!/usr/bin/env bash
# ComfyUI process control for the SyMoNeuRaL Studio surface.
#
#   comfyui.sh start     start the server on 127.0.0.1:8188 (loopback only)
#   comfyui.sh stop      unload the weights, then stop it, then wait for the VRAM back
#   comfyui.sh status    up/down, pid, port, and what the card looks like
#   comfyui.sh log       recent server output
#
# Loopback only, deliberately. The public surface is FastAPI's -- the Studio page reaches
# this server through `/studio/comfy/*`, which is proxied by `backend/apps/symoneuralstudio`.
# Binding 0.0.0.0 here would put an unauthenticated node editor with filesystem access on a
# box with a public IP.
#
# ## This does NOT take the GPU lock
#
# Deliberate, and the single most important thing to understand about this script.
# CLAUDE.md: "Hold the lock for a job, never for a process lifetime." ComfyUI is a long-lived
# HTTP server that is idle most of the time; taking `gpu-governor.sh acquire comfy` at start
# and holding it until `stop` would lock chat, image and train out of the card for as long as
# the editor happened to be open. The lock is taken per *render*, inside `comfy.lease()`, and
# given back with `POST /free` the moment the job finishes.
#
# The consequence is that a running-but-idle ComfyUI holds no lock and, once `/free` has run,
# no meaningful VRAM either. `evict()` in the governor stops it properly when another surface
# needs the card.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }
COMFY="$ROOT/ComfyUI"
VENV="$COMFY/.venv/bin/python"
RUN="$ROOT/run"; mkdir -p "$RUN"
PIDFILE="$RUN/comfyui.pid"
LOG="$RUN/comfyui.log"
PORT="${SYMONEURAL_COMFY_PORT:-${SYM_COMFY_PORT:-8188}}"
HOST="127.0.0.1"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

# Ask the server to hand the card back before we signal it. SIGTERM during CUDA teardown
# returns the process before the driver returns the memory, and the next tenant OOMs at
# step 0 -- which is exactly the failure `gpu-governor.sh drain` exists to catch.
free_vram() {
  curl -fsS --max-time 10 -X POST "http://$HOST:$PORT/free" \
       -H 'Content-Type: application/json' \
       -d '{"unload_models":true,"free_memory":true}' >/dev/null 2>&1 || true
}

case "${1:-status}" in
  start)
    if running; then echo "already up (pid $(cat "$PIDFILE")) on $HOST:$PORT"; exit 0; fi
    [ -x "$VENV" ] || { echo "no venv at $VENV -- see the Studio README" >&2; exit 1; }
    # Relink our custom node before every start. ComfyUI/ is gitignored in full (8.5 GB, and
    # it carries its own .git), so the source of truth for `symoneural_gguf` lives in the
    # repo and this is what puts it where ComfyUI looks. Delete ComfyUI/ and reclone it and
    # the node comes back on the next start rather than having to be remembered.
    NODE_SRC="$ROOT/backend/apps/symoneuralstudio/custom_nodes/symoneural_gguf"
    NODE_DST="$COMFY/custom_nodes/symoneural_gguf"
    if [ -d "$NODE_SRC" ] && [ ! -e "$NODE_DST" ]; then
      ln -s "$NODE_SRC" "$NODE_DST" && echo "linked symoneural_gguf into custom_nodes/"
    fi
    # --disable-auto-launch: this is a headless server behind a proxy; opening a browser on
    # a box being driven over SSH is noise at best.
    setsid "$VENV" "$COMFY/main.py" \
        --listen "$HOST" --port "$PORT" \
        --disable-auto-launch \
        >>"$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    # It imports torch and scans custom nodes before it binds, which is seconds not
    # milliseconds. Poll the port rather than sleeping a guessed constant.
    for _ in $(seq 1 60); do
      curl -fsS --max-time 2 "http://$HOST:$PORT/system_stats" >/dev/null 2>&1 && break
      running || { echo "died during startup -- see $LOG" >&2; rm -f "$PIDFILE"; exit 1; }
      sleep 1
    done
    if curl -fsS --max-time 2 "http://$HOST:$PORT/system_stats" >/dev/null 2>&1; then
      echo "comfyui up on $HOST:$PORT (pid $(cat "$PIDFILE"))"
      echo "the editor is served through the stack at /studio -- not from this port directly."
    else
      echo "started (pid $(cat "$PIDFILE")) but not answering yet -- see $LOG" >&2; exit 1
    fi
    ;;

  stop)
    if running; then
      free_vram
      kill "$(cat "$PIDFILE")" 2>/dev/null
      for _ in $(seq 1 20); do running || break; sleep 1; done
      running && kill -9 "$(cat "$PIDFILE")" 2>/dev/null
    else
      # Started outside this script, or the pidfile was lost.
      pkill -f "$COMFY/main.py" 2>/dev/null
    fi
    rm -f "$PIDFILE"
    # The process exiting is not the memory coming back: SIGTERM returns the process before the
    # driver returns the device allocation, and the next tenant OOMs at step 0. The loop above
    # waited for the pid; this waits for the card, against the governor's own floor
    # (DRAIN_FLOOR_MIB=1500 for DRAIN_TIMEOUT_S=60, gpu-governor.sh:41-42) so there is one
    # definition of "drained" in this repo rather than two. `drain` takes no argument and
    # returns 1 on timeout, so its exit status is the whole check.
    if "$ROOT/scripts/gpu-governor.sh" drain; then
      echo "comfyui stopped"
    else
      echo "comfyui stopped, but the card did not drain -- see gpu-governor.sh status" >&2
      exit 1
    fi
    ;;

  status)
    if running; then
      echo "comfyui    up (pid $(cat "$PIDFILE")) on $HOST:$PORT"
    elif curl -fsS --max-time 2 "http://$HOST:$PORT/system_stats" >/dev/null 2>&1; then
      echo "comfyui    up on $HOST:$PORT but NOT started by this script (no pidfile)"
    else
      echo "comfyui    down"
    fi
    "$ROOT/scripts/gpu-governor.sh" status
    ;;

  log) tail -n "${2:-40}" "$LOG" 2>/dev/null || echo "no log at $LOG" ;;

  *) echo "usage: $(basename "$0") {start|stop|status|log}" >&2; exit 2 ;;
esac
