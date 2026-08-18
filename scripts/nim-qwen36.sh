#!/usr/bin/env bash
#
# Run NVIDIA's Qwen3.6-27B NIM container on this box, or fail with a reason.
#
#   ./scripts/nim-qwen36.sh login          # one-off: podman login nvcr.io
#   ./scripts/nim-qwen36.sh preflight      # every check, pulls nothing
#   ./scripts/nim-qwen36.sh up             # pull + run, serving on :8082
#   ./scripts/nim-qwen36.sh logs           # follow
#   ./scripts/nim-qwen36.sh down           # stop and remove
#
# ## Why this exists as a script rather than a docker one-liner
#
# There is no `docker` on this box and there is not going to be: podman 5.4.2 is installed,
# rootless, with crun, and /etc/cdi/nvidia.yaml is already generated -- so GPU passthrough is
# `--device nvidia.com/gpu=all`, which is NOT the flag any NVIDIA doc shows. Every published
# NIM example says `docker run --gpus all`. Copying that here fails twice over.
#
# ## What NVIDIA does and does not say about this card
#
# The NGC page for nim/qwen/qwen3.6-27b (pulled 2026-08-18, container updated 2026-04-23)
# carries NO hardware matrix: no GPU list, no VRAM minimum, no example run command. What it
# does say, and what matters here:
#
#   Compressed Size    11.87 GB
#   How to Pull        Automatic (embedded in container)
#   Backend            SGLang
#   Multi-Arch         No
#   Labels             Experimental
#
# 11.87 GB is the COMPRESSED REGISTRY SIZE of the image, not a VRAM figure and not the size
# of the weights on disk. Quantized weights are near-incompressible, so the uncompressed
# layers are larger, and what SGLang then allocates on the card is larger again once the KV
# cache is reserved. Treat 11.87 GB as "what the pull costs", never as "what fits".
#
# NIM's own GeForce support list names the RTX 5090, 5080, 4090 and 4080. The RTX 5070 Ti in
# this machine is NOT on it, and NVIDIA's NVFP4 build of this model is reported at ~18.6 GB
# against this card's 15.92 GiB. NIM selects an optimized profile at startup and refuses when
# none fits. So this script may get all the way to a clean start and still be told no. That
# is a legitimate outcome to record, not a bug to work around -- see `docs/` on publishing
# negative results.
#
# The supported path on this card is the GGUF one: contrib/llama.cpp already carries
# LLM_ARCH_QWEN35, which is the architecture these Qwen3.6 GGUFs declare in their header.
set -euo pipefail

IMAGE=nvcr.io/nim/qwen/qwen3.6-27b:latest
NAME=symon-nim-qwen36
PORT=8082
# NIM caches the model outside the container so a re-run does not re-extract it. This is
# gitignored space on the big filesystem, not /home root and not the repo's models/ tree --
# NIM owns the layout in here and it is not a GGUF.
CACHE="${SYM_NIM_CACHE:-$HOME/.cache/nim}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok    %s\n' "$*"; }
bad()  { printf '  FAIL  %s\n' "$*"; }
warn() { printf '  warn  %s\n' "$*"; }

preflight() {
  local fatal=0
  say "preflight for $IMAGE"

  command -v podman >/dev/null && ok "podman $(podman --version | awk '{print $3}')" \
    || { bad "podman not installed"; fatal=1; }

  if [ -f /etc/cdi/nvidia.yaml ]; then
    ok "CDI spec /etc/cdi/nvidia.yaml present"
  else
    bad "no /etc/cdi/nvidia.yaml -- run: sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml"
    fatal=1
  fi

  # Credentials. nvcr.io answers 401 to an anonymous manifest request, so this is not
  # optional and cannot be worked around from here.
  if podman login --get-login nvcr.io >/dev/null 2>&1; then
    ok "logged in to nvcr.io as $(podman login --get-login nvcr.io 2>/dev/null)"
  else
    bad "not logged in to nvcr.io -- run: $0 login   (needs your NGC API key)"
    fatal=1
  fi

  local free_mib total_mib
  read -r total_mib free_mib < <(nvidia-smi --query-gpu=memory.total,memory.free \
      --format=csv,noheader,nounits | tr -d ',' )
  say "  gpu   ${free_mib} MiB free of ${total_mib} MiB"
  # 18.6 GB is the reported NVFP4 footprint. This card cannot reach it. Stated as a warning
  # rather than a hard stop because the figure is third-party and the profile NIM actually
  # picks here is exactly what we are trying to find out.
  if [ "$total_mib" -lt 19000 ]; then
    warn "this card is below the ~18.6 GB reported for the NVFP4 profile; NIM may refuse to start"
  fi

  local avail_gb
  avail_gb=$(df -BG --output=avail "$(dirname "$CACHE")" 2>/dev/null | tail -1 | tr -dc '0-9')
  if [ "${avail_gb:-0}" -ge 60 ]; then ok "${avail_gb} GB free for the image and model cache"
  else warn "only ${avail_gb} GB free at $CACHE -- the pull is 11.87 GB compressed and expands"; fi

  [ "$fatal" -eq 0 ] || { say; say "preflight failed -- nothing was pulled."; return 1; }
  say; say "preflight passed."
}

case "${1:-preflight}" in
  login)
    say "Your NGC API key is the password. Username is the literal string \$oauthtoken."
    podman login nvcr.io --username '$oauthtoken'
    ;;

  preflight) preflight ;;

  up)
    preflight
    mkdir -p "$CACHE"
    say "pulling $IMAGE (11.87 GB compressed) ..."
    podman pull "$IMAGE"
    podman rm -f "$NAME" >/dev/null 2>&1 || true
    say "starting on 127.0.0.1:$PORT ..."
    # Loopback-bound on purpose. This is an unauthenticated OpenAI-compatible endpoint and
    # the box it runs on serves the public internet; the same reasoning that keeps Coder and
    # Rack loopback-only applies here. FastAPI stays the only thing facing outward.
    podman run -d --name "$NAME" \
      --device nvidia.com/gpu=all \
      --shm-size=16g \
      -v "$CACHE:/opt/nim/.cache:z" \
      -p 127.0.0.1:$PORT:8000 \
      "$IMAGE"
    say "started. Follow the profile selection -- that is where it fails if it fails:"
    say "    $0 logs"
    say "Then:  curl -s http://127.0.0.1:$PORT/v1/models | python3 -m json.tool"
    ;;

  logs) podman logs -f "$NAME" ;;

  down) podman rm -f "$NAME" && say "removed $NAME" ;;

  *) say "usage: $0 {login|preflight|up|logs|down}"; exit 1 ;;
esac
