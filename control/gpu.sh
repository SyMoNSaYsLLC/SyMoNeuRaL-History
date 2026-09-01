#!/usr/bin/env bash
# The card: who holds it, and take it back. Thin pass-through to scripts/gpu-governor.sh,
# which is the only thing allowed to touch the GPU lock.
#
#   gpu.sh status|release <surface>|release-all|nvidia
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  status)      "$ROOT/scripts/gpu-governor.sh" status ;;
  release)     [ $# -ge 2 ] || die "usage: gpu.sh release <chat|image|train|...>"
               "$ROOT/scripts/gpu-governor.sh" release "$2" ;;
  release-all) for s in chat image train; do "$ROOT/scripts/gpu-governor.sh" release "$s" 2>/dev/null; done
               say "released chat, image, train" ;;
  nvidia)      nvidia-smi ;;
  *) die "usage: gpu.sh status|release <surface>|release-all|nvidia" ;;
esac
