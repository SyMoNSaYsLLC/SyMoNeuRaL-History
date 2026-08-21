#!/usr/bin/env bash
# Install the SyMoNeuRaL HTTP gateway as a system service.
#
#     sudo ./scripts/install-gateway.sh    (from the repo root)
#
# After this the gateway starts on boot and restarts on crash, the same way the API does.
# It does NOT touch Caddy; run `sudo systemctl reload caddy` yourself after the Caddyfile is
# in place, so that the two changes fail independently and are diagnosable apart.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
UNIT=/etc/systemd/system/symoneural-gateway.service
# Under backend/apps/gateway/, with every other app. See the note in
# ops/symoneural-gateway.service for what the stale spelling of this path cost.
BIN="$ROOT/backend/apps/gateway/target/release/symon-gateway"

[ "$(id -u)" -eq 0 ] || { echo "run me with sudo" >&2; exit 1; }
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }

# Refuse rather than install a unit that will crash-loop on ENOENT. Restart=always means a
# missing binary is five restarts and then a silent dead unit, which is a poor way to find
# out you forgot to build.
if [ ! -x "$BIN" ]; then
  echo "gateway binary not found at $BIN" >&2
  echo "build it first:  cd $ROOT/backend/apps/gateway && cargo build --release" >&2
  exit 1
fi

echo "installing unit -> $UNIT"
sed "s|@@ROOT@@|$ROOT|g" "$ROOT/ops/symoneural-gateway.service" > "$UNIT.tmp"
install -m 644 -o root -g root "$UNIT.tmp" "$UNIT"
rm -f "$UNIT.tmp"
echo "  unit points at $ROOT"

# Anything started by hand has to go, or two processes fight over port 8000.
#
# `-x -f` together, not `-f` alone: -f matches against the whole command line, which includes
# the command line of anything that merely mentions the path -- an editor, a build, or the
# shell running this very script. That is not hypothetical; a bare `pkill -f` on this path
# killed the shell that invoked it during testing, which surfaced as an unexplained exit 144.
# -x demands the full command line equal the pattern, and the gateway runs with no arguments.
pkill -x -f "$BIN" 2>/dev/null || true
sleep 1

systemctl daemon-reload
systemctl enable symoneural-gateway.service
systemctl restart symoneural-gateway.service

sleep 2
echo
systemctl --no-pager --lines=0 status symoneural-gateway.service || true
echo

# Health, then a real proxied request. The first proves the process is up; only the second
# proves it can reach the API, and they fail for different reasons.
if ! curl -sf --max-time 8 http://127.0.0.1:8000/healthz >/dev/null; then
  echo "gateway is NOT answering on :8000 -- check: journalctl -u symoneural-gateway -n 50" >&2
  exit 1
fi
echo "gateway is answering on 127.0.0.1:8000"

if curl -sf --max-time 10 http://127.0.0.1:8000/api/status >/dev/null; then
  echo "and it can reach the API through /api/status"
else
  echo "WARNING: /healthz is up but /api/status did not answer through it." >&2
  echo "         That is the API, not the gateway: systemctl status symoneural-api" >&2
fi

cat <<'EOF'

managing it from here:
  systemctl status symoneural-gateway      what it is doing
  systemctl restart symoneural-gateway     after cargo build --release
  systemctl stop symoneural-gateway        take the gateway offline
  journalctl -u symoneural-gateway -f      follow the log (JSON records)

the Caddy half is a separate, deliberate step:
  sudo caddy validate --config /etc/caddy/Caddyfile
  sudo systemctl reload caddy
EOF
