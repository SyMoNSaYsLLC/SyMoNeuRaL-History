#!/usr/bin/env bash
# Install or migrate the SyMoNeuRaL runtime so it serves from THIS repository and nothing else.
#
#   sudo ops/install-runtime.sh --dry-run     print every action, change nothing
#   sudo ops/install-runtime.sh               install, restart, verify, roll back on failure
#   sudo ops/install-runtime.sh --no-restart  install units only; do not touch running services
#
# ## What this replaces
#
# The migration off /yocto was first done by hand. Hand-run commands are not a deployment:
# they cannot be reviewed, repeated on another box, or rolled back. Garrett, 2026-08-26:
# *"No final production state may rely on commands that were performed manually but not
# represented in the repository."* This script IS that representation, and running it on an
# already-migrated box is a no-op that says so.
#
# ## The boundary
#
# `/yocto` is an authorized BUILD environment -- SDK, toolchains, sysroots, BitBake, caches.
# What is forbidden is a live component REQUIRING it. This script installs only files that
# live under this repository and under /etc, never anything that points into /yocto, and
# `ops/verify-runtime.sh` is run at the end to prove it rather than assert it.
#
# ## Idempotent, and atomic where it matters
#
# Unit files are rendered to a temporary file and `install`ed over the target, which is an
# atomic rename on the same filesystem -- there is no instant at which a half-written unit
# exists. Re-running with no changes reports "unchanged" and does not restart anything, so
# this is safe to run from a provisioning step.
#
# ## Rollback
#
# Every run backs the current units and environment files up to a timestamped directory under
# /etc/symoneural/unit-backups/ FIRST. If the health check fails after the restart, the backup
# is restored and the services are restarted again, automatically, before this script exits
# non-zero. `ops/rollback-runtime.sh` does the same thing by hand for a later regret.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }

UNITS=(symoneural-api symoneural-gateway symoneural-deploy)
UNIT_DIR=/etc/systemd/system
BACKUP_ROOT=/etc/symoneural/unit-backups
ENV_FILES=(/etc/symoneural/api.env /etc/symoneural/deploy.env)
HEALTH_LOCAL=http://127.0.0.1:8800/api/status
HEALTH_PUBLIC=https://symoneural.com/api/status

DRY=0; RESTART=1
for a in "$@"; do
    case "$a" in
        --dry-run)    DRY=1 ;;
        --no-restart) RESTART=0 ;;
        *) echo "unknown argument: $a" >&2; exit 2 ;;
    esac
done

say()  { printf '  %s\n' "$*"; }
step() { printf '\n== %s ==\n' "$*"; }
run()  { if [ "$DRY" -eq 1 ]; then printf '  DRY  %s\n' "$*"; else eval "$@"; fi; }

if [ "$DRY" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    echo "This needs root to write $UNIT_DIR. Re-run with sudo, or use --dry-run." >&2
    exit 1
fi

# ---------------------------------------------------------------- preflight
step "preflight: the canonical tree has what the units will point at"
PREFLIGHT_OK=1
need() {  # need <relative path> <what it is>
    if [ -e "$ROOT/$1" ]; then say "OK      $1  ($2)"
    else say "MISSING $1  ($2)"; PREFLIGHT_OK=0; fi
}
need backend/api.py                                          "the API"
need scripts/deploy.sh                                       "the publisher"
need scripts/gpu-governor.sh                                 "governor, called by ExecStartPre"
need site                                                    "what deploy publishes"
need backend/apps/gateway/target/release/symon-gateway       "gateway binary (ops/build-gateway.sh)"
need engines/symoneural-llm/build/bin/symoneural-llm         "inference engine"
need backend/models/llm/symon-1.0-7b-q4_k_m.gguf             "chat model"
for u in "${UNITS[@]}"; do need "ops/$u.service" "unit template"; done
if [ "$PREFLIGHT_OK" -eq 0 ]; then
    echo >&2
    echo "Refusing to install: the canonical tree is incomplete (see MISSING above)." >&2
    echo "A unit pointing at a path that does not exist fails at boot, not now." >&2
    exit 1
fi

# The gateway binary must be an independent regular file, not a hardlink into a build tree
# and never a symlink into /yocto.
GW="$ROOT/backend/apps/gateway/target/release/symon-gateway"
if [ -L "$GW" ]; then say "REFUSING: the gateway binary is a symlink"; exit 1; fi
case "$(readlink -f "$GW")" in *yocto*) say "REFUSING: the gateway binary resolves into /yocto"; exit 1;; esac
if ldd "$GW" 2>/dev/null | grep -q '/yocto'; then say "REFUSING: gateway links a library from /yocto"; exit 1; fi
say "gateway artifact: $(stat -c '%s bytes, st_nlink=%h' "$GW"), no /yocto linkage"

# ---------------------------------------------------------------- render
step "render unit templates against ROOT=$ROOT"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
CHANGED=()
for u in "${UNITS[@]}"; do
    sed "s|@@ROOT@@|$ROOT|g" "$ROOT/ops/$u.service" > "$TMP/$u.service"
    if grep -q '@@[A-Z_]*@@' "$TMP/$u.service"; then
        say "REFUSING: unsubstituted placeholder in $u.service"; exit 1
    fi
    if grep -qE '^[^#]*=.*/yocto' "$TMP/$u.service"; then
        say "REFUSING: rendered $u.service still references /yocto in a directive"; exit 1
    fi
    if [ -f "$UNIT_DIR/$u.service" ] && cmp -s "$TMP/$u.service" "$UNIT_DIR/$u.service"; then
        say "unchanged  $u.service"
    else
        say "will write $u.service"; CHANGED+=("$u")
    fi
done

if [ "${#CHANGED[@]}" -eq 0 ]; then
    say "every unit is already correct -- nothing to install."
else
    # ------------------------------------------------------------ backup
    step "backup"
    STAMP="$(date +%Y%m%d-%H%M%S)"; BK="$BACKUP_ROOT/$STAMP"
    run "install -d -m 0700 -o root -g root '$BK'"
    for u in "${UNITS[@]}"; do
        [ -f "$UNIT_DIR/$u.service" ] && run "cp -a '$UNIT_DIR/$u.service' '$BK/'"
    done
    [ -d "$UNIT_DIR/symoneural-api.service.d" ] && run "cp -a '$UNIT_DIR/symoneural-api.service.d' '$BK/'"
    for f in "${ENV_FILES[@]}"; do [ -f "$f" ] && run "cp -a '$f' '$BK/'"; done
    run "chmod -R go-rwx '$BK'"
    say "backup: $BK"
    [ "$DRY" -eq 0 ] && echo "$BK" > /etc/symoneural/.last-unit-backup

    # ------------------------------------------------------------ install
    step "install"
    for u in "${CHANGED[@]}"; do
        # `install` replaces atomically and sets ownership/mode deliberately rather than
        # inheriting whatever the temp file had.
        run "install -o root -g root -m 0644 '$TMP/$u.service' '$UNIT_DIR/$u.service'"
        say "installed $u.service"
    done
    run "systemctl daemon-reload"
    say "daemon-reload done"
fi

# ---------------------------------------------------------------- restart
if [ "$RESTART" -eq 0 ]; then
    step "restart skipped (--no-restart)"
elif [ "${#CHANGED[@]}" -eq 0 ]; then
    step "restart skipped (nothing changed)"
else
    step "controlled restart"
    # Gateway first: it is a thin proxy in front of the API, so restarting it while the API is
    # still up is the shorter outage. The API second, because it is the slow one.
    run "systemctl restart symoneural-gateway"
    run "systemctl restart symoneural-api"

    step "health"
    OK=0
    if [ "$DRY" -eq 1 ]; then say "DRY  would poll $HEALTH_LOCAL then $HEALTH_PUBLIC"; OK=1; else
        for i in $(seq 1 30); do
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTH_LOCAL" 2>/dev/null)"
            [ "$code" = "200" ] && { say "local $HEALTH_LOCAL -> 200 after ~$((i*2))s"; OK=1; break; }
            sleep 2
        done
        if [ "$OK" -eq 1 ]; then
            pub="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$HEALTH_PUBLIC" 2>/dev/null)"
            say "public $HEALTH_PUBLIC -> $pub"
            [ "$pub" = "200" ] || { say "public health is not 200"; OK=0; }
        else
            say "local health never reached 200"
        fi
    fi

    # ------------------------------------------------------------ rollback
    if [ "$OK" -eq 0 ]; then
        step "HEALTH FAILED -- rolling back automatically"
        for u in "${UNITS[@]}"; do
            [ -f "$BK/$u.service" ] && install -o root -g root -m 0644 "$BK/$u.service" "$UNIT_DIR/$u.service" \
                && say "restored $u.service"
        done
        [ -d "$BK/symoneural-api.service.d" ] && cp -a "$BK/symoneural-api.service.d" "$UNIT_DIR/"
        systemctl daemon-reload
        systemctl restart symoneural-gateway || true
        systemctl restart symoneural-api || true
        sleep 5
        back="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_LOCAL" 2>/dev/null)"
        say "after rollback, local health -> $back"
        echo >&2
        echo "INSTALL FAILED AND WAS ROLLED BACK. Units restored from $BK." >&2
        echo "Nothing further was changed. Investigate with:" >&2
        echo "  journalctl -u symoneural-api -n 60 --no-pager" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------- verify
step "verify the runtime boundary"
if [ "$DRY" -eq 1 ]; then
    say "DRY  would run ops/verify-runtime.sh"
else
    if "$ROOT/ops/verify-runtime.sh" --quiet; then
        say "ops/verify-runtime.sh: clean"
    else
        say "ops/verify-runtime.sh REPORTED A VIOLATION -- see above"
        exit 1
    fi
fi

echo
printf '\033[32mRUNTIME INSTALLED\033[0m  root=%s\n' "$ROOT"
