#!/usr/bin/env bash
# Move symoneural.com from Apache to Caddy.
#
#   sudo /home/google/MIT_AI_Training/MIT_AI_Training/ops/install-caddy.sh
#
# This takes the site down for a few seconds between stopping Apache and Caddy having a
# certificate. It is written to be reversible: Apache is disabled, not removed, and the
# last section of this file is the exact rollback.
#
# What it does NOT do: touch /var/www/symoneural. Deploying the site is still deploy.sh.
set -euo pipefail

DOMAIN="symoneural.com"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBROOT="/var/www/symoneural"
API="127.0.0.1:8800"

[ "$(id -u)" -eq 0 ] || { echo "must run as root: sudo $0"; exit 1; }

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- preflight ---------------------------------------------------------------
# Caddy provisions a certificate over ports 80 and 443 on first start. If DNS does not
# resolve here, or the API is down, we want to know before Apache is stopped rather than
# during the outage.
say "Preflight"
[ -d "$WEBROOT" ] || { echo "FAIL: $WEBROOT does not exist -- run deploy.sh first"; exit 1; }
[ -f "$SRC/Caddyfile" ] || { echo "FAIL: $SRC/Caddyfile missing"; exit 1; }
echo "  webroot   $WEBROOT ($(find "$WEBROOT" -maxdepth 1 -type f | wc -l) files)"

if curl -fsS -m 5 "http://$API/api/status" >/dev/null 2>&1; then
  echo "  api       up on $API"
else
  echo "  api       DOWN on $API -- the static site will serve, but every surface will 502."
  echo "            Start it first, then re-run. Continuing anyway in 5s (Ctrl-C to abort)."
  sleep 5
fi

resolved="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
echo "  dns       $DOMAIN -> ${resolved:-UNRESOLVED}"
[ -n "$resolved" ] || { echo "FAIL: $DOMAIN does not resolve; Caddy cannot get a certificate"; exit 1; }

# --- install -----------------------------------------------------------------
say "Installing Caddy"
if command -v caddy >/dev/null; then
  echo "  already installed: $(caddy version | head -1)"
else
  apt-get update -qq
  apt-get install -y caddy
fi

say "Installing the Caddyfile"
install -d -m 755 /etc/caddy
if [ -f /etc/caddy/Caddyfile ] && ! cmp -s "$SRC/Caddyfile" /etc/caddy/Caddyfile; then
  cp -a /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.prev-$(date +%Y%m%d-%H%M%S)"
  echo "  previous Caddyfile backed up"
fi
install -m 644 "$SRC/Caddyfile" /etc/caddy/Caddyfile
install -d -m 755 -o caddy -g caddy /var/log/caddy

# Validate before anything is stopped. A bad config here means Apache keeps serving.
if ! caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "FAIL: Caddyfile did not validate; Apache left running and untouched."
  exit 1
fi
echo "  Caddyfile validates"

# --- cut over ----------------------------------------------------------------
say "Stopping Apache"
# Disabled, not purged -- the rollback at the bottom of this file depends on it.
systemctl stop apache2 || true
systemctl disable apache2 || true
echo "  apache2 stopped and disabled (not removed)"

say "Starting Caddy"
systemctl enable caddy
systemctl restart caddy
sleep 4

# --- verify ------------------------------------------------------------------
say "Verifying"
fail=0
check() { # label url expected
  code="$(curl -fsS -o /dev/null -w '%{http_code}' -m 15 "$2" 2>/dev/null || echo 000)"
  if [ "$code" = "$3" ]; then printf '  ok    %-28s %s\n' "$1" "$code"
  else printf '  FAIL  %-28s %s (wanted %s)\n' "$1" "$code" "$3"; fail=1; fi
}
check "https:// index"        "https://$DOMAIN/"             200
check "https:// api status"   "https://$DOMAIN/api/status"   200
check "https:// swagger"      "https://$DOMAIN/docs"         200
check "https:// openapi"      "https://$DOMAIN/openapi.json" 200
check "http:// redirects"     "http://$DOMAIN/"              200

# The reason for the migration: /api/ws must upgrade rather than fall back to polling.
say "WebSocket upgrade"
# Two traps here, both of which produce a convincing false failure:
#   1. `Upgrade:` is an HTTP/1.1 mechanism. It does not exist in HTTP/2, and curl
#      negotiates h2 with Caddy by default -- so the header arrives as meaningless
#      metadata, FastAPI sees a plain GET on a websocket-only route, and returns 404.
#      Browsers are unaffected: a page loaded over h2 still opens a separate HTTP/1.1
#      connection for the handshake. Hence --http1.1.
#   2. A *successful* upgrade leaves the socket open and streaming, so curl exits 28
#      on timeout no matter how well it worked. Read the status line out of the headers
#      rather than trusting curl's exit code.
wshdr="$(mktemp)"
curl -sS --http1.1 -o /dev/null -D "$wshdr" -m 6 \
      -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
      -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
      "https://$DOMAIN/api/ws" >/dev/null 2>&1 || true
if grep -qi '^HTTP/1.1 101' "$wshdr" && grep -qi '^Sec-Websocket-Accept:' "$wshdr"; then
  echo "  ok    /api/ws upgraded (101 Switching Protocols)"
else
  echo "  FAIL  /api/ws did not upgrade -- the rack will fall back to polling"
  sed 's/^/        /' "$wshdr" | head -6
  fail=1
fi
rm -f "$wshdr"

if [ "$fail" -eq 0 ]; then
  say "Done. Caddy is serving $DOMAIN and FastAPI is doing all the routing."
  systemctl --no-pager --lines=0 status caddy || true
else
  cat <<ROLLBACK

Something failed. Logs:
    journalctl -u caddy -n 60 --no-pager

To go back to Apache:
    sudo systemctl stop caddy && sudo systemctl disable caddy
    sudo systemctl enable apache2 && sudo systemctl start apache2
ROLLBACK
  exit 1
fi
