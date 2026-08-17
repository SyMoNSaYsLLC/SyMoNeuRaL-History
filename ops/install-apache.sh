#!/usr/bin/env bash
# Install the playground proxy stanza into the live symoneural.com vhost.
#
#     sudo /home/google/MIT_AI_Training/MIT_AI_Training/ops/install-apache.sh
#
# This touches a live TLS vhost, so it is written to be un-doable: the current config is
# copied aside first, the new one is validated with `apache2ctl configtest` BEFORE any
# reload, and if validation fails the original is put straight back and Apache is never
# asked to reload. A broken configtest here should cost nothing but a message.
set -uo pipefail

LIVE=/etc/apache2/sites-available/symoneural.conf
NEW="$(cd "$(dirname "$0")" && pwd)/symoneural.conf"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/etc/apache2/sites-available/symoneural.conf.bak-$STAMP"

[ "$(id -u)" -eq 0 ] || { echo "run me with sudo" >&2; exit 1; }
[ -f "$NEW" ]  || { echo "staged config missing: $NEW" >&2; exit 1; }
[ -f "$LIVE" ] || { echo "live config missing: $LIVE" >&2; exit 1; }

if diff -q "$LIVE" "$NEW" >/dev/null; then
  echo "config already matches -- nothing to do"; exit 0
fi

echo "changes to be applied:"
diff "$LIVE" "$NEW" | sed 's/^/    /'
echo

cp -p "$LIVE" "$BACKUP"
echo "backup:  $BACKUP"

install -m 644 -o root -g root "$NEW" "$LIVE"

echo "validating..."
if ! apache2ctl configtest 2>&1 | sed 's/^/    /'; then
  echo
  echo "configtest FAILED -- restoring the original and leaving Apache untouched." >&2
  cp -p "$BACKUP" "$LIVE"
  exit 1
fi

# proxy/proxy_http are already enabled on this box, but enabling twice is harmless and
# makes the script correct on a machine where they are not.
a2enmod proxy proxy_http >/dev/null 2>&1

echo "reloading apache..."
systemctl reload apache2

echo
echo "done. /api now proxies to 127.0.0.1:8800."
echo "the playground itself is started separately:  playground.sh on"
echo "to roll back:  sudo cp $BACKUP $LIVE && sudo systemctl reload apache2"
