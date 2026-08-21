#!/usr/bin/env bash
# SyMoNeuRaL GPU governor.
#
# One card, 15.92 GiB, two surfaces whose weight sets do not co-fit. This
# serialises them: any surface that wants the GPU takes the lock first, and
# nothing else touches the device until it is released.
#
# The mutex is the easy half. The half that actually bites is the handoff --
# killing a holder returns the lock long before the CUDA context has finished
# tearing down, so the next surface allocates into memory that is still held
# and dies at step 0. Release therefore does not merely unlock: it waits for
# the driver to hand the memory back, and only then lets the next surface in.
#
# The mutex is a mkdir lock, not flock on a file descriptor, because a hold
# has to outlive the shell that took it -- the API server acquires in one
# process and releases in another.
#
#   gpu-governor.sh acquire <surface> [timeout]   take the card
#   gpu-governor.sh release                       give it back, wait for drain
#   gpu-governor.sh status                        who holds it, how much is free
#   gpu-governor.sh with <surface> -- cmd...      acquire, run, always release
set -uo pipefail

# Repo root is one level up now that this lives in scripts/. This calculation has
# been wrong three times in this repo (the demo/ flatten, the tools/ move, here) and
# it fails silently, because the wrong parent is usually a directory that exists.
# The guard below turns that into an immediate, obvious failure.
# RUN in particular is the GPU mutex: gpu.lock.d lives in it. Point this at the
# wrong directory and the lock silently stops being shared -- two tenants both acquire,
# both load weights, and ~12 GB of models hit a 16 GB card.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }
# HERE is the repo ROOT, not this script's directory, and the two call sites below spell
# their paths from the root accordingly. They did not until 2026-08-20: they read
# "$HERE/symoneural" and "$HERE/<launcher>.sh", neither of which has ever existed at the
# root, so both graceful stops silently fell through to their `||` pkill fallback --
# and for comfy that fallback is precisely the ungraceful kill the comment on its arm
# argues against. A `||` fallback hides a broken primary; both are checked by
# apps/test_governor_paths.py now.
HERE="$ROOT"
RUN="$ROOT/run"
LOCKDIR="$RUN/gpu.lock.d"
HOLDER="$LOCKDIR/holder"
LOG="$RUN/governor.log"

# Idle on this box measures ~988 MiB. Under this floor means the previous
# tenant has genuinely let go rather than merely exited.
DRAIN_FLOOR_MIB=1500
DRAIN_TIMEOUT_S=60
ACQUIRE_TIMEOUT_S=300

mkdir -p "$RUN"

vram_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '; }
vram_free() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '; }
log() { printf '%s  %-8s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2" | tee -a "$LOG" >&2; }

held_surface() { cut -d' ' -f1 "$HOLDER" 2>/dev/null || true; }
held_pid()     { cut -d' ' -f2 "$HOLDER" 2>/dev/null || true; }

# A holder that died without releasing must not wedge the card forever.
break_if_stale() {
  local pid; pid="$(held_pid)"
  [ -z "$pid" ] && return 1
  if ! kill -0 "$pid" 2>/dev/null; then
    log stale "holder pid $pid is gone -- breaking the lock"
    rm -rf "$LOCKDIR"
    return 0
  fi
  return 1
}

# Wait for the driver to actually give device memory back.
drain() {
  local waited=0 used
  while :; do
    used="$(vram_used)"; used="${used:-0}"
    if [ "$used" -lt "$DRAIN_FLOOR_MIB" ]; then
      log drain "settled at ${used} MiB after ${waited}s (floor ${DRAIN_FLOOR_MIB} MiB)"
      return 0
    fi
    if [ "$waited" -ge "$DRAIN_TIMEOUT_S" ]; then
      log drain "FAILED: still ${used} MiB after ${waited}s -- refusing to hand over"
      return 1
    fi
    sleep 1; waited=$((waited + 1))
  done
}

# Stop whatever is resident, then wait for the memory back.
evict() {
  local prev="${1:-}"
  [ -z "$prev" ] && return 0
  log evict "stopping '$prev' to make room -- the weight sets do not co-fit"
  case "$prev" in
    chat)  "$HERE/bin/symoneural-cli" _stop-chat >/dev/null 2>&1 || pkill -f 'bin/symoneural-llm' 2>/dev/null || true ;;
    image) pkill -f 'bin/symoneural-diffuse' 2>/dev/null || true ;;
    # Stickers. Same engine as image, so the same kill -- but the name has to be here
    # anyway, because without a case of its own it falls to *) below, and *) pkills
    # the LLM engine too and takes chat down as collateral. Registering a surface name
    # and adding its case are one change, not two: the miner) arm exists because the
    # *) arm was once found logging a successful eviction while the tenant kept the card.
    #
    # Known and deliberate: `pkill -f 'bin/symoneural-diffuse'` cannot tell a sigil render from an image
    # render, so evicting either kills both. The global lock serialises them and the
    # engine is not resident between jobs, so the window is small -- but it is written down
    # here rather than discovered by whoever next sees an image render die unexplained.
    sigil) pkill -f 'bin/symoneural-diffuse' 2>/dev/null || true ;;
    # The render UI. It is a long-lived HTTP server that holds ~12 GB of weights while
    # resident, so it MUST have its own arm: the '*)' arm below pkills the LLM and
    # diffusion engines, neither of which is this, and would log a successful eviction while
    # the card stayed full -- the exact failure the miner) comment records.
    #
    # The stop is deliberately graceful and staged. `scripts/symoneural-ui.sh stop` asks the
    # server to unload (POST /free) and then signals its pidfile, because SIGKILLing a
    # process mid-CUDA-teardown returns the lock before the driver has taken the memory
    # back and the next tenant OOMs at step 0 -- which is what `drain` below exists to
    # catch. The pkill is the fallback for a server started outside the script.
    #
    # The fallback pattern must name the path the process ACTUALLY runs from, which is now
    # engines/symoneural-ui. It used to name the upstream tree's main.py at the repo root,
    # a path that no longer exists under any spelling; a pkill that matches nothing does not
    # fail -- it succeeds having killed nothing, so the governor logs an
    # eviction, the card stays full, and the next tenant OOMs at step 0. That is the same
    # silent-failure shape as the two broken `$HERE` paths this arm was already fixed for.
    comfy) "$HERE/scripts/symoneural-ui.sh" stop >/dev/null 2>&1 || pkill -f 'engines/symoneural-ui/main.py' 2>/dev/null || true ;;
    # A training run holds ~10-13 GB for hours. It is never killed to make room for a demo
    # request -- a half-finished fine-tune is not worth a page view. Serving surfaces queue
    # behind it instead, which is what the acquire timeout is for.
    train)
      if pgrep -f '[t]rain_lora.py' >/dev/null 2>&1; then
        log evict "REFUSING to evict a training run -- wait for it or stop it deliberately"
        return 1
      fi
      # `resident` outlives the process that wrote it. A finished fine-tune is a historical
      # record, not a tenant, and treating it as one wedged the card indefinitely.
      log evict "'train' recorded but no run is active -- treating as stale"
      ;;
    # The exact opposite of 'train': a miner yields to everything, because no hashrate is
    # worth making a visitor wait. It is stopped through its own module so the pidfile and
    # the process group are handled in one place -- signalling the recorded pid alone
    # leaves the actual miner orphaned and still resident, which reads as a clean stop and
    # is not one.
    #
    # This case is inert until SYMONEURAL_MINER_CMD names a real binary: nothing writes 'miner'
    # into run/resident before then. Without it, a miner tenant would fall through to the
    # '*)' arm below and be "evicted" by pkilling the LLM engine -- which would leave the
    # miner holding the card while the governor logged a successful eviction.
    miner)
      python3 -c 'import sys; sys.path.insert(0, "'"$ROOT"'/backend/apps"); import cryptominer; cryptominer.stop()' \
        >/dev/null 2>&1 || pkill -g "$(cat "$RUN/miner.pid" 2>/dev/null || echo -1)" 2>/dev/null || true
      ;;
    *)     pkill -f 'bin/symoneural-llm|bin/symoneural-diffuse' 2>/dev/null || true ;;
  esac
  drain
}

cmd_acquire() {
  local surface="${1:?usage: acquire <surface>}" timeout="${2:-$ACQUIRE_TIMEOUT_S}"
  local waited=0 prev owner

  # Whose pid to record. NOT $$ -- for the standalone `acquire` form this script exits the
  # instant it returns, so $$ names a process that is already dead by the time anyone reads
  # the holder file. Two things then break silently: staleness detection breaks a live lock
  # on its first poll, and callers asking "who holds the card" are told nobody does.
  # The owner is the process that will still be running while the card is held -- the caller
  # (PPID), or an explicit pid via SYMONEURAL_OWNER_PID.
  owner="${SYMONEURAL_OWNER_PID:-$PPID}"
  log wait "'$surface' wants the card"
  until mkdir "$LOCKDIR" 2>/dev/null; do
    break_if_stale && continue
    if [ "$waited" -ge "$timeout" ]; then
      log wait "'$surface' TIMED OUT after ${timeout}s behind '$(held_surface)'"
      return 1
    fi
    sleep 1; waited=$((waited + 1))
  done

  # We own the lock. Whoever was resident before us has to go.
  prev="$(cat "$RUN/resident" 2>/dev/null || true)"
  echo "$surface $owner" > "$HOLDER"
  if [ -n "$prev" ] && [ "$prev" != "$surface" ]; then
    if ! evict "$prev"; then rm -rf "$LOCKDIR"; return 1; fi
  fi
  echo "$surface" > "$RUN/resident"
  log acquire "'$surface' holds the card -- $(vram_free) MiB free, waited ${waited}s"
  return 0
}

cmd_release() {
  local held claimant pid
  held="$(held_surface)"
  claimant="${1:-}"

  # Releasing a lock you do not hold is how one process quietly hands another process's
  # GPU away. The API's shutdown hook did exactly that to a running fine-tune: it called a
  # bare `release`, the lock directory vanished, and the next image request would have
  # allocated on top of an active training run. A release now has to name itself, and a
  # mismatch against a live holder is refused rather than obeyed.
  if [ -n "$held" ] && [ -n "$claimant" ] && [ "$held" != "$claimant" ]; then
    pid="$(held_pid)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      log release "REFUSED: '$claimant' tried to release '$held' (pid $pid, alive)"
      return 1
    fi
  fi

  log release "'${held:-none}' releasing"
  rm -rf "$LOCKDIR"
}

cmd_status() {
  local surface; surface="$(held_surface)"
  echo "resident surface   $(cat "$RUN/resident" 2>/dev/null || echo none)"
  # Not a ${x:+..}${x:-..} pair: when x is set, the second form expands to x rather than
  # to the default, so a held lock printed "HELD by train (pid N)train".
  if [ -n "$surface" ]; then
    echo "lock               HELD by $surface (pid $(held_pid))"
  else
    echo "lock               free"
  fi
  echo "vram used          $(vram_used) MiB"
  echo "vram free          $(vram_free) MiB"
}

# The form everything else should use: the card is always given back, even if
# the command inside crashes or the caller is interrupted.
cmd_with() {
  local surface="${1:?usage: with <surface> -- cmd...}"; shift
  [ "${1:-}" = "--" ] && shift
  SYMONEURAL_OWNER_PID=$$ cmd_acquire "$surface" || return 1
  trap "cmd_release $surface" EXIT INT TERM
  local rc=0
  "$@" || rc=$?
  trap - EXIT INT TERM
  cmd_release "$surface"
  return $rc
}

case "${1:-status}" in
  acquire) shift; cmd_acquire "$@" ;;
  release) shift; cmd_release "$@" ;;
  status)  shift; cmd_status  "$@" ;;
  with)    shift; cmd_with    "$@" ;;
  drain)   drain ;;
  *) echo "usage: $(basename "$0") {acquire|release|status|with|drain}" >&2; exit 2 ;;
esac
