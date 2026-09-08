#!/usr/bin/env bash
# The image surface. Like chat, the API owns the engine (`symoneural-diffuse`) and
# runs it under the governor -- starting "the image server" means having the API up.
# Generating evicts chat from the card; that is by design, one GPU job at a time.
#
#   launch-image-server.sh status|test|release
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  status)
    "$ROOT/scripts/gpu-governor.sh" status || true
    if api_up; then
      curl -fsS "$API_BASE/api/status" 2>/dev/null \
        | python3 "$(dirname "${BASH_SOURCE[0]}")/_fmt_units.py" | grep -E "^  (image|remix) " || true
    else warn "API down -- control/launch-api.sh start"; fi ;;
  test)
    require_api; warn "this evicts chat from the GPU"; say "generating a small test image ..."
    curl -fsS -m 600 -X POST "$API_BASE/api/image" \
      -H 'content-type: application/json' \
      -d '{"prompt":"a red cube on a white background","steps":4}' | head -c 400; echo ;;
  release) "$ROOT/scripts/gpu-governor.sh" release image ;;
  *) die "usage: launch-image-server.sh status|test|release" ;;
esac
