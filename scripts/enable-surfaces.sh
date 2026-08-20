#!/usr/bin/env bash
#
# Switch on the token-gated surfaces that ship OFF by default: Coder, Project, Studio, and
# the operator power switch this repo calls Rack. Optionally the TRON licensing Gateway,
# which needs two facts this script cannot invent.
#
#   sudo ./scripts/enable-surfaces.sh project rack
#   sudo ./scripts/enable-surfaces.sh coder studio                # local-only, see below
#   sudo ./scripts/enable-surfaces.sh gateway --network nile \
#          --contract TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#   sudo ./scripts/enable-surfaces.sh --show                      # what is set, no secrets
#
# ## Why a drop-in and an env file rather than editing the unit
#
# The live unit is the TEMPLATED copy at /etc/systemd/system/symoneural-api.service, written
# by ops/install-service.sh with the repo root substituted in. Editing ops/symoneural-api.service
# changes nothing that is running, and editing the installed copy is undone the next time
# anybody re-runs the installer. A drop-in at .../symoneural-api.service.d/ survives both.
#
# Tokens do NOT go in `Environment=` lines. `systemctl show symoneural-api` prints those to
# any user on the box, which would put a shared secret in the output of an unprivileged
# command. They go in /etc/symoneural/api.env, root-owned and mode 0600, referenced by
# `EnvironmentFile=`. That file is outside the repo and can never be committed by accident.
#
# ## What this script will not do
#
# It will not enable remote access to anything. SYM_CODER_ALLOW_REMOTE and
# SYM_RACK_ALLOW_REMOTE are never written here, so both surfaces stay loopback-only, which
# is the shape their own documentation argues for: backend/apps/coder/README.md is explicit
# that an agent which can develop the site is arbitrary code execution on the box that
# serves the public internet. Opening either one to the network is a deliberate act and
# should look like one -- add the line by hand, having decided to.
#
# It will not overwrite a token that already exists. Re-running is safe and idempotent: a
# surface already switched on keeps the token it has, so restarting does not invalidate a
# session or a saved credential somewhere else.
set -euo pipefail

ENV_FILE=/etc/symoneural/api.env
DROPIN_DIR=/etc/systemd/system/symoneural-api.service.d
DROPIN="$DROPIN_DIR/10-surfaces.conf"
UNIT=symoneural-api.service

die() { printf '%s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "This writes to /etc and restarts a service. Run it with sudo."

# ---------------------------------------------------------------- read what is already set

# `set -a` in a subshell, so a malformed line cannot leak into this script's own namespace.
get_var() {
  [ -f "$ENV_FILE" ] || { printf ''; return; }
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -1
}

show() {
  printf 'env file : %s\n' "$ENV_FILE"
  if [ ! -f "$ENV_FILE" ]; then
    printf '           (absent -- nothing enabled by this script)\n'
    return
  fi
  # Values are never printed. A token is either set or it is not; showing it here would put
  # it in a terminal scrollback and, sooner or later, in a screenshot.
  while IFS='=' read -r k v; do
    case "$k" in
      ''|'#'*) continue ;;
      *TOKEN*) printf '  %-28s = <set, %d chars>\n' "$k" "${#v}" ;;
      *)       printf '  %-28s = %s\n' "$k" "$v" ;;
    esac
  done < "$ENV_FILE"
}

# ---------------------------------------------------------------- arguments

WANT_CODER=0 WANT_PROJECT=0 WANT_RACK=0 WANT_GATEWAY=0 WANT_STUDIO=0
GW_NETWORK="" GW_CONTRACT=""

[ $# -gt 0 ] || die "Nothing asked for. Surfaces: coder project studio rack gateway (or --show)."

while [ $# -gt 0 ]; do
  case "$1" in
    coder)   WANT_CODER=1 ;;
    project) WANT_PROJECT=1 ;;
    rack)    WANT_RACK=1 ;;
    gateway) WANT_GATEWAY=1 ;;
    studio)  WANT_STUDIO=1 ;;
    --network)  GW_NETWORK="${2:-}"; shift ;;
    --contract) GW_CONTRACT="${2:-}"; shift ;;
    --show)  show; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
  shift
done

# The two facts this script cannot invent. `mainnet` is real money and a contract address is
# not guessable, so a missing one is a hard stop rather than a default.
if [ "$WANT_GATEWAY" -eq 1 ]; then
  case "$GW_NETWORK" in
    nile|shasta|mainnet) ;;
    "") die "gateway needs --network nile|shasta|mainnet." \
            "There is no sane default: mainnet is real money." ;;
    *)  die "--network must be one of nile, shasta, mainnet (got '$GW_NETWORK')." ;;
  esac
  [ -n "$GW_CONTRACT" ] || die "gateway needs --contract, the deployed licensing contract" \
                               "address (34 chars, begins with T)."
  case "$GW_CONTRACT" in
    T?????????????????????????????????) ;;
    *) die "--contract does not look like a TRON address:" \
           "expected 34 characters beginning with T." ;;
  esac
fi

# ---------------------------------------------------------------- write

install -d -m 0700 -o root -g root /etc/symoneural
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cat > "$ENV_FILE" <<'HEADER'
# SyMoNeuRaL API surface switches. Written by scripts/enable-surfaces.sh.
#
# Root-owned, mode 0600, and deliberately OUTSIDE the repo: these are shared secrets and
# there is no git remote today, but "not committed" should not depend on remembering.
# Read by symoneural-api.service via an EnvironmentFile= drop-in -- NOT by Environment=
# lines, which `systemctl show` would print to any user on the box.
HEADER
fi
chown root:root "$ENV_FILE"; chmod 0600 "$ENV_FILE"

# Set KEY=VALUE, but never clobber an existing non-empty value.
set_kv() {
  local key="$1" val="$2" existing
  existing="$(get_var "$key")"
  if [ -n "$existing" ]; then
    printf '  %-28s kept (already set)\n' "$key"
    return
  fi
  printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  case "$key" in
    *TOKEN*) printf '  %-28s generated\n' "$key" ;;
    *)       printf '  %-28s = %s\n' "$key" "$val" ;;
  esac
}

# secrets.token_urlsafe(32), exactly as backend/apps/project/store.py instructs -- "generate
# it with secrets.token_urlsafe(32) and never by hand". The system interpreter, since that is
# the serving path's interpreter and no virtualenv is involved.
gen_token() { /usr/bin/python3 -c 'import secrets; print(secrets.token_urlsafe(32))'; }

printf 'Writing %s\n' "$ENV_FILE"
# Four surfaces, one shape: SYM_<NAME>_ENABLED=1 plus a fresh token. This was four aligned
# one-liners; each of the three that existed already ran past this repo's 100-column limit and
# adding Studio would have made a fourth, so the shape is a loop over "want-flag NAME" pairs.
# Gateway is not in here because it takes two more values and cannot share the body.
for pair in "$WANT_CODER CODER" "$WANT_PROJECT PROJECT" "$WANT_RACK RACK" \
            "$WANT_STUDIO STUDIO"; do
  want=${pair% *}
  name=${pair#* }
  [ "$want" -eq 1 ] || continue
  set_kv "SYM_${name}_ENABLED" 1
  set_kv "SYM_${name}_TOKEN" "$(gen_token)"
done
if [ "$WANT_GATEWAY" -eq 1 ]; then
  set_kv SYM_GATEWAY_ENABLED 1
  set_kv SYM_GATEWAY_NETWORK "$GW_NETWORK"
  set_kv SYM_GATEWAY_CONTRACT "$GW_CONTRACT"
fi

install -d -m 0755 "$DROPIN_DIR"
cat > "$DROPIN" <<EOF
# Written by scripts/enable-surfaces.sh. A drop-in rather than an edit to the unit, so
# re-running ops/install-service.sh does not silently switch these surfaces back off.
#
# The leading '-' means a missing file is not a startup failure: deleting $ENV_FILE
# turns every one of these surfaces off and the API still serves chat, image and calc.
# That is the intended panic button, and it must not brick the service.
[Service]
EnvironmentFile=-$ENV_FILE
EOF
chmod 0644 "$DROPIN"
printf 'Wrote %s\n' "$DROPIN"

systemctl daemon-reload
systemctl restart "$UNIT"

# ---------------------------------------------------------------- verify against the rack
#
# The rack is the check that matters. A unit reporting `ready` in /api/status is the same
# reading the site shows a visitor, so verifying here means verifying the thing the operator
# is actually going to look at -- not merely that a process started.
printf '\nWaiting for the API to answer...\n'
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null http://127.0.0.1:8800/api/status 2>/dev/null; then break; fi
  sleep 1
done

# Two shell facts, both learned by this block being broken from the day it was written:
#
#   * The reader below is a QUOTED heredoc, not `python3 -c '...'`. Inside a
#     single-quoted shell string a backslash-quote is a literal backslash followed by a
#     quote, so the f-strings reached Python as `u[\"id\"]` and it died with
#     "SyntaxError: unexpected character after line continuation character" on every run.
#     A quoted heredoc passes its body through untouched, so `u["id"]` stays `u["id"]`
#     and there is nothing to escape. Re-quoting the -c form would have worked too and is
#     the wrong fix: it leaves the next author one edit away from the same crash.
#   * The document arrives in an environment variable rather than on stdin, because the
#     heredoc *is* stdin. Piping curl into a command that also takes a heredoc cannot work.
#
# The two failure modes are reported separately now. The old `|| die` fired on the
# SyntaxError and printed "the API did not come back" -- which was false. The API had come
# back; the operator was sent to journalctl to hunt a service fault that was in this file.
STATUS_DOC=$(curl -fsS http://127.0.0.1:8800/api/status 2>/dev/null) \
  || die "/api/status did not answer after the restart -- journalctl -u $UNIT -n 50"

# `rack` is deliberately absent from the watch set below: it is the operator power switch,
# not a rack row, and it has no `id` in /api/status. Including it would print nothing and
# read like a surface that failed to come up.
STATUS_DOC="$STATUS_DOC" /usr/bin/python3 - <<'PYEOF' \
  || die "the API answered but its reply did not parse -- the fault is here, not the service"
import json, os, sys

try:
    doc = json.loads(os.environ["STATUS_DOC"])
except Exception as e:
    sys.exit(f"/api/status did not parse: {e}")
for u in doc.get("units", []):
    if u.get("id") in {"coder", "project", "studio", "gateway"}:
        print(f'  {u["id"]:<9} {u["state"]:<8} {u["detail"]}')
PYEOF

printf '\nDone. Tokens are in %s (root, 0600). Read one with:\n' "$ENV_FILE"
printf '    sudo sed -n "s/^SYM_PROJECT_TOKEN=//p" %s\n' "$ENV_FILE"
printf '\nBoth Coder and Rack remain loopback-only: SYM_*_ALLOW_REMOTE is deliberately unset.\n'
printf 'Studio is not loopback-gated in the same way -- it has no ALLOW_REMOTE switch, so its\n'
printf 'token is the whole gate. backend/apps/symoneuralstudio/__init__.py:42 is explicit that\n'
printf 'the surface can write to the host. Treat SYM_STUDIO_TOKEN accordingly.\n'
