#!/usr/bin/env bash
# Publish the staged site to /var/www/symoneural.
#
# Needs root because the webroot is www-data owned. Run it with sudo:
#     sudo /home/google/MIT_AI_Training/MIT_AI_Training/deploy.sh
#
# Backs up the current index.html to a fresh timestamped name every time. It never touches
# index.backup-20260816-141604.html -- that is the 419 KB original training page and the only
# copy of it.
set -euo pipefail

# Repo root, not its parent. This climbed one level when the script lived in demo/;
# after the flatten it resolved to /home/google/MIT_AI_Training/site, which does not
# exist, so every deploy exited with "no staged site" and the live site stayed stale.
SRC="$(cd "$(dirname "$0")" && pwd)/site"
DST=/var/www/symoneural
STAMP="$(date +%Y%m%d-%H%M%S)"

[ -d "$SRC" ] || { echo "no staged site at $SRC" >&2; exit 1; }
[ -d "$DST" ] || { echo "no webroot at $DST" >&2; exit 1; }

echo "staged:  $SRC  ($(find "$SRC" -maxdepth 1 -type f | wc -l) files)"

if [ -f "$DST/index.html" ]; then
  cp -p "$DST/index.html" "$DST/index.prev-$STAMP.html"
  echo "backup:  index.prev-$STAMP.html"
fi

# Top-level files.
find "$SRC" -maxdepth 1 -type f -exec install -o www-data -g www-data -m 644 {} "$DST/" \;

# /docs is the one subdirectory: a static Swagger UI page plus the schema snapshot. It is
# served straight off disk rather than proxied, so the API reference works after a plain
# deploy with no web server change -- and it keeps working when inference is switched off.
if [ -d "$SRC/docs" ]; then
  install -d -o www-data -g www-data -m 755 "$DST/docs"
  find "$SRC/docs" -maxdepth 1 -type f -exec install -o www-data -g www-data -m 644 {} "$DST/docs/" \;
  echo "deployed /docs (static swagger)"
fi
echo "deployed to $DST"

echo
echo "verifying every local asset reference resolves on disk:"
# Fragment links (href="/#build") are in-page anchors, not files -- excluding '#' keeps
# them out of the report instead of listing three permanent phantom failures that train
# the reader to ignore the whole check.
#
# This used to pipe into `while read`, which runs in a subshell, so the `missing=1` set
# inside it was discarded and the script could print MISSING lines and still exit 0. The
# whole point of a verification step is that it can fail, so the loop reads from a process
# substitution and the count survives.
missing=0
while read -r ref; do
  if [ -f "$DST/$ref" ]; then
    printf '  ok      %s\n' "$ref"
  else
    printf '  MISSING %s\n' "$ref"; missing=$((missing + 1))
  fi
done < <(grep -ohE '(src|href)="/[^"#]+"' "$DST"/*.html \
         | sed 's/.*"\/\(.*\)"/\1/' | sort -u)

echo
if [ "$missing" -gt 0 ]; then
  echo "FAILED: $missing referenced asset(s) are not on disk. The site is deployed but"
  echo "incomplete -- fix the reference or ship the file, then re-run."
  exit 1
fi
echo "done. reload https://symoneural.com/ with a hard refresh."
