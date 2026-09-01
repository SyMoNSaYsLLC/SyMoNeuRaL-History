#!/usr/bin/env bash
# One screen: every service, every surface, the card, the disk. Read-only -- starts nothing.
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

say "── systemd units ───────────────────────────────────────────"
for u in symoneural-api symoneural-gateway symoneural-web; do
  if systemctl list-unit-files "$u.service" &>/dev/null; then
    printf '  %-26s %-9s %s\n' "$u" "$(systemctl is-enabled $u.service 2>/dev/null)" "$(systemctl is-active $u.service 2>/dev/null)"
  else
    printf '  %-26s %s\n' "$u" "not installed"
  fi
done

echo; say "── API ─────────────────────────────────────────────────────"
if api_up; then
  printf '  %-26s %s\n' "endpoint" "$API_BASE  HTTP 200"
  curl -fsS "$API_BASE/api/status" 2>/dev/null \
    | python3 "$(dirname "${BASH_SOURCE[0]}")/_fmt_units.py" 2>/dev/null
else
  printf '  %-26s %s\n' "endpoint" "$API_BASE  DOWN"
fi

echo; say "── GPU ─────────────────────────────────────────────────────"
"$ROOT/scripts/gpu-governor.sh" status 2>/dev/null | sed 's/^/  /' || echo "  (governor status unavailable)"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu \
  --format=csv,noheader 2>/dev/null | sed 's/^/  vram: /'

echo; say "── engines on disk ─────────────────────────────────────────"
for e in symoneural-llm symoneural-diffuse symoneural-ui; do
  printf '  %-26s %s\n' "$e" "$([ -d "$ROOT/engines/$e" ] && echo present || echo '<missing>')"
done

echo; say "── disk ────────────────────────────────────────────────────"
df -h "$ROOT" | tail -1 | awk '{printf "  %-26s %s used of %s (%s)\n","/home",$3,$2,$5}'
