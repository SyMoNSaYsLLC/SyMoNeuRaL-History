#!/usr/bin/env bash
# Install the SyMoNeuRaL API as a system service.
#
#     sudo /home/google/MIT_AI_Training/MIT_AI_Training/ops/install-service.sh
#
# After this the API starts on boot, restarts on crash, and is managed with systemctl
# rather than a shell script. It replaces playground.sh for anything production.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEMO="$(dirname "$HERE")"
UNIT=/etc/systemd/system/symoneural-api.service
ROTATE=/etc/logrotate.d/symoneural

[ "$(id -u)" -eq 0 ] || { echo "run me with sudo" >&2; exit 1; }

echo "installing unit -> $UNIT"
install -m 644 -o root -g root "$HERE/symoneural-api.service" "$UNIT"

# The app writes its own log alongside the journal; rotate it so a busy night cannot fill
# the disk the site is served from.
echo "installing logrotate -> $ROTATE"
cat > "$ROTATE" <<EOF
$DEMO/run/api.log $DEMO/run/governor.log {
    daily
    rotate 14
    size 20M
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su google google
}
EOF
chmod 644 "$ROTATE"

# Anything started by hand has to go, or two processes fight over port 8800 and the GPU.
if [ -f "$DEMO/run/api.pid" ]; then
  echo "stopping hand-started instance"
  kill "$(cat "$DEMO/run/api.pid")" 2>/dev/null || true
  rm -f "$DEMO/run/api.pid"
fi
pkill -f "[p]ython3 $DEMO/api.py" 2>/dev/null || true
sleep 1

systemctl daemon-reload
systemctl enable symoneural-api.service
systemctl restart symoneural-api.service

sleep 4
echo
systemctl --no-pager --lines=0 status symoneural-api.service || true
echo
if curl -sf --max-time 8 http://127.0.0.1:8800/api/status >/dev/null; then
  echo "API is answering on 127.0.0.1:8800"
else
  echo "API is NOT answering -- check: journalctl -u symoneural-api -n 50" >&2
  exit 1
fi

cat <<'EOF'

managing it from here:
  systemctl status symoneural-api      what it is doing
  systemctl restart symoneural-api     after changing api.py
  systemctl stop symoneural-api        take inference offline (static site unaffected)
  journalctl -u symoneural-api -f      follow the log
EOF
