#!/usr/bin/env bash
# Smoke a staged candidate IN ISOLATION. Takes the card, so it stops when the governor
# reports another holder (STOP condition 2) and when there is nothing to smoke.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$MODELOPS"
[ $# -gt 0 ] || die "usage: models-verify.sh <candidate-id>
  runs modelops --smoke-candidate; requires a staged candidate"
if "$ROOT/scripts/gpu-governor.sh" status 2>/dev/null | grep -qiE '^ *lock +held|holder'; then
  die "STOP: the governor reports another holder -- refusing to contend for the card"
fi
[ "$(payload_count)" = "0" ] && die "STOP: no model payload on disk -- nothing to smoke"
exec bash "$MODELOPS" --smoke-candidate "$@"
