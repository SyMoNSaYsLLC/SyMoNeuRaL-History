#!/usr/bin/env bash
# The chat/LLM surface. It is NOT a separate daemon you start: the API owns the engine and
# spawns `engines/symoneural-llm` on demand, under the GPU governor.
#
#   launch-llm-server.sh status    what the card and the chat surface are doing
#   launch-llm-server.sh warm      send one tiny request so the weights become resident
#   launch-llm-server.sh release   hand the card back
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  status)
    "$ROOT/scripts/gpu-governor.sh" status || true
    if api_up; then
      curl -fsS "$API_BASE/api/status" 2>/dev/null \
        | python3 "$(dirname "${BASH_SOURCE[0]}")/_fmt_units.py" | grep -E "^  (chat|remix) " || true
    else warn "API down -- control/launch-api.sh start"; fi ;;
  warm)
    require_api; say "warming chat (one short prompt) ..."
    curl -fsS -m 180 -X POST "$API_BASE/api/chat" \
      -H 'content-type: application/json' \
      -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":8}' | head -c 400; echo ;;
  release) "$ROOT/scripts/gpu-governor.sh" release chat ;;
  *) die "usage: launch-llm-server.sh status|warm|release" ;;
esac
