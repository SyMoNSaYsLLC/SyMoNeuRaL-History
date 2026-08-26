#!/usr/bin/env bash
# Prove the live runtime does not depend on /yocto, and that it runs what we think it runs.
#
#   ops/verify-runtime.sh              full check, exit 1 on any failure
#   ops/verify-runtime.sh --quiet      only failures and the verdict
#
# ## The boundary this enforces
#
# `/yocto` is an AUTHORIZED BUILD ENVIRONMENT: extensible SDK, toolchains, sysroots, BitBake,
# caches, staging. Building there is fine and expected. What is forbidden is a live component
# NEEDING it. Garrett, 2026-08-26: *"Build from /yocto when appropriate, but never require
# /yocto at runtime."*
#
# So this script deliberately does NOT grep the repository for the string `/yocto` -- build
# logs, CMake caches and the `yocto/` layer directory legitimately contain it, and a check
# that fails on those trains people to ignore it. It inspects the RUNNING SYSTEM and the
# INSTALLABLE ARTIFACTS instead:
#
#   unit files          WorkingDirectory / Exec* / Environment / paths
#   live processes      cwd, exe, argv, environ, open fds, mapped files
#   ELF artifacts       interpreter, RPATH, RUNPATH, unresolved deps
#   python              sys.path of the serving interpreter
#   boot behaviour      what an enabled unit would republish
#
# `/home/google/yocto` was permanently deleted and must never be recreated; that is checked
# too, because a path that no longer exists is exactly the kind of thing a script recreates
# by accident with `mkdir -p`.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

FAILED=0
pass() { [ "$QUIET" -eq 1 ] || printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; [ -n "${2:-}" ] && printf '        %s\n' "$2"; FAILED=1; }
info() { [ "$QUIET" -eq 1 ] || printf '        %s\n' "$1"; }
head_() { [ "$QUIET" -eq 1 ] || printf '\n== %s ==\n' "$1"; }

CANON=/home/google/Symoneural
UNITS=(symoneural-api symoneural-gateway symoneural-deploy)

# `sudo -n`: this script must be runnable unprivileged and say so rather than prompting.
have_sudo() { sudo -n true 2>/dev/null; }

# ---------------------------------------------------------------- 0. the deleted directory
head_ "the permanently deleted directory"
if [ -e /home/google/yocto ]; then
    fail "/home/google/yocto exists again" "it was permanently deleted and must not be recreated"
else
    pass "/home/google/yocto absent (correct -- permanently deleted)"
fi

# ---------------------------------------------------------------- 1. unit files
head_ "systemd units"
for u in "${UNITS[@]}"; do
    f=/etc/systemd/system/$u.service
    if ! sudo -n test -f "$f" 2>/dev/null; then
        if [ ! -r "$f" ]; then info "$u: cannot read $f (need sudo); skipping file check"; continue; fi
    fi
    body="$(sudo -n cat "$f" 2>/dev/null || cat "$f" 2>/dev/null)"
    if [ -z "$body" ]; then info "$u: unreadable, skipped"; continue; fi
    # Only EXECUTABLE/PATH directives matter. A Documentation= URL naming a build tree is a
    # comment, not a runtime dependency -- but we still fail it, because these units are
    # generated from templates and a stale Documentation= line means the template was not
    # re-rendered, which is the actual defect.
    if grep -qE '^[^#]*=.*(^|[^A-Za-z])/yocto' <<<"$body"; then
        fail "$u references /yocto in a directive" "$(grep -nE '^[^#]*=.*/yocto' <<<"$body" | head -3 | tr '\n' ' ')"
    else
        pass "$u: no /yocto in any directive"
    fi
    wd="$(sudo -n systemctl show "$u" -p WorkingDirectory --value 2>/dev/null)"
    [ "$wd" = "$CANON" ] && pass "$u: WorkingDirectory=$CANON" \
                         || fail "$u: WorkingDirectory is '$wd', expected $CANON"
done

head_ "drop-ins"
if compgen -G "/etc/systemd/system/symoneural-*.service.d/*.conf" >/dev/null 2>&1; then
    if sudo -n grep -l "/yocto" /etc/systemd/system/symoneural-*.service.d/*.conf 2>/dev/null | grep -q .; then
        fail "a drop-in references /yocto"
    else
        pass "no drop-in references /yocto"
    fi
else
    pass "no drop-ins present"
fi

# ---------------------------------------------------------------- 2. live processes
head_ "live processes"
for u in symoneural-api symoneural-gateway; do
    pid="$(systemctl show "$u" -p MainPID --value 2>/dev/null)"
    if [ -z "$pid" ] || [ "$pid" = "0" ]; then fail "$u is not running"; continue; fi
    cwd="$(sudo -n readlink /proc/$pid/cwd 2>/dev/null)"
    exe="$(sudo -n readlink /proc/$pid/exe 2>/dev/null)"
    argv="$(sudo -n tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)"
    envv="$(sudo -n tr '\0' '\n' < /proc/$pid/environ 2>/dev/null | grep -c '/yocto')"
    fds="$(sudo -n ls -l /proc/$pid/fd 2>/dev/null | grep -c '/yocto')"
    maps="$(sudo -n grep -c '/yocto' /proc/$pid/maps 2>/dev/null)"
    bad=0
    case "$cwd"  in *yocto*) fail "$u cwd is under /yocto: $cwd"; bad=1;; esac
    case "$exe"  in *yocto*) fail "$u executable is under /yocto: $exe"; bad=1;; esac
    case "$argv" in *yocto*) fail "$u argv mentions /yocto"; bad=1;; esac
    [ "${envv:-0}" -gt 0 ] 2>/dev/null && { fail "$u has $envv environment values naming /yocto"; bad=1; }
    [ "${fds:-0}"  -gt 0 ] 2>/dev/null && { fail "$u holds $fds open fds under /yocto"; bad=1; }
    [ "${maps:-0}" -gt 0 ] 2>/dev/null && { fail "$u has $maps mapped files under /yocto"; bad=1; }
    [ "$bad" -eq 0 ] && pass "$u (pid $pid): cwd, exe, argv, environ, fds, maps all clean"
done

head_ "the inference engine, if resident"
ENG_PID="$(pgrep -f "$CANON/engines/symoneural-llm/build/bin/symoneural-llm" 2>/dev/null | head -1)"
if [ -z "$ENG_PID" ]; then
    info "engine not resident (it is started on demand and never at boot) -- skipped"
else
    fds="$(sudo -n ls -l /proc/$ENG_PID/fd 2>/dev/null | grep -c '/yocto')"
    maps="$(sudo -n grep -c '/yocto' /proc/$ENG_PID/maps 2>/dev/null)"
    if [ "${fds:-0}" -eq 0 ] && [ "${maps:-0}" -eq 0 ]; then
        pass "engine (pid $ENG_PID): no /yocto fds or maps"
    else
        fail "engine holds /yocto references" "fds=$fds maps=$maps"
    fi
    if sudo -n grep -q "$CANON/backend/models/llm/" /proc/$ENG_PID/maps 2>/dev/null; then
        pass "engine has the canonical GGUF mapped"
    else
        fail "engine has not mapped a model under $CANON/backend/models/llm/"
    fi
fi

# ---------------------------------------------------------------- 3. ELF artifacts
head_ "ELF artifacts: interpreter, RPATH, RUNPATH, unresolved deps"
check_elf() {   # check_elf <path> <label>
    local f="$1" label="$2"
    [ -f "$f" ] || { fail "$label missing at $f"; return; }
    case "$(readlink -f "$f")" in *yocto*) fail "$label resolves into /yocto"; return;; esac
    [ -L "$f" ] && { fail "$label is a symlink"; return; }
    local links; links="$(stat -c %h "$f")"
    local interp rpath runpath unres
    interp="$(readelf -l "$f" 2>/dev/null | sed -n 's/.*interpreter: \(.*\)\]/\1/p')"
    rpath="$(readelf -d "$f" 2>/dev/null | grep -E 'RPATH' | sed 's/.*\[\(.*\)\]/\1/')"
    runpath="$(readelf -d "$f" 2>/dev/null | grep -E 'RUNPATH' | sed 's/.*\[\(.*\)\]/\1/')"
    unres="$(ldd "$f" 2>/dev/null | grep -c 'not found')"
    case "$interp"  in *yocto*) fail "$label ELF interpreter is under /yocto: $interp"; return;; esac
    case "$rpath"   in *yocto*) fail "$label RPATH names /yocto: $rpath"; return;; esac
    case "$runpath" in *yocto*) fail "$label RUNPATH names /yocto: $runpath"; return;; esac
    if ldd "$f" 2>/dev/null | grep -q '/yocto'; then
        fail "$label resolves a shared library from /yocto" "$(ldd "$f" | grep '/yocto' | head -2 | tr '\n' ' ')"
        return
    fi
    [ "${unres:-0}" -gt 0 ] && { fail "$label has $unres unresolved dependencies"; return; }
    pass "$label: interp=${interp:-none} rpath=${rpath:-none} runpath=${runpath:-none} unresolved=0 links=$links"
}
check_elf "$CANON/backend/apps/gateway/target/release/symon-gateway" "gateway"
check_elf "$CANON/engines/symoneural-llm/build/bin/symoneural-llm"   "inference engine"

# ---------------------------------------------------------------- 4. python import path
head_ "python import path of the serving interpreter"
APID="$(systemctl show symoneural-api -p MainPID --value 2>/dev/null)"
if [ -n "$APID" ] && [ "$APID" != "0" ]; then
    pp="$(sudo -n tr '\0' '\n' < /proc/$APID/environ 2>/dev/null | grep '^PYTHONPATH=' || true)"
    case "$pp" in *yocto*) fail "PYTHONPATH names /yocto: $pp";; *) pass "PYTHONPATH clean (${pp:-unset})";; esac
    # `grep -c` ALREADY prints 0 and exits 1 when it matches nothing, so a `|| echo 0` here
    # appends a second zero and the result is the two-line string "0\n0" -- which then fails
    # `[ -eq ]` with "integer expression expected" and reports a violation that does not
    # exist. That is exactly what this script is for, so it is worth not doing it.
    loaded="$(sudo -n ls -l /proc/$APID/fd 2>/dev/null | grep -c '/yocto/.*\.py')"
    if [ "${loaded:-0}" -eq 0 ]; then pass "no .py file open from /yocto"
    else fail "$loaded python files open from /yocto"; fi
else
    fail "symoneural-api is not running, so its import path cannot be checked"
fi

# ---------------------------------------------------------------- 5. boot behaviour
head_ "boot behaviour"
for u in "${UNITS[@]}"; do
    en="$(systemctl is-enabled "$u" 2>/dev/null || echo unknown)"
    info "$u is-enabled=$en"
done
DEPLOY_EXEC="$(sudo -n systemctl show symoneural-deploy -p ExecStart --value 2>/dev/null)"
case "$DEPLOY_EXEC" in
    *"$CANON"*) pass "symoneural-deploy publishes from $CANON -- a reboot cannot restore /yocto content" ;;
    *yocto*)    fail "symoneural-deploy still publishes from /yocto -- a reboot WILL restore it" ;;
    *)          fail "cannot read symoneural-deploy ExecStart" ;;
esac
DEPLOY_COND="$(sudo -n systemctl show symoneural-deploy -p ConditionPathIsDirectory --value 2>/dev/null)"
case "$DEPLOY_COND" in *yocto*) fail "deploy ConditionPathIsDirectory names /yocto";; *) pass "deploy condition path: ${DEPLOY_COND:-none}";; esac

# ---------------------------------------------------------------- the deploy state contract
#
# An ENABLED oneshot that has published successfully must be legible AS having published.
# Without RemainAfterExit=yes it lands on inactive(dead) with an EMPTY ActiveEnterTimestamp,
# which looks identical to "it never ran" and can only be told apart by reading the journal.
# This block is why that cannot pass silently again.
head_ "symoneural-deploy state contract"
d_type="$(sudo -n systemctl show symoneural-deploy -p Type --value 2>/dev/null)"
d_rae="$(sudo -n systemctl show symoneural-deploy -p RemainAfterExit --value 2>/dev/null)"
d_act="$(sudo -n systemctl show symoneural-deploy -p ActiveState --value 2>/dev/null)"
d_sub="$(sudo -n systemctl show symoneural-deploy -p SubState --value 2>/dev/null)"
d_ufs="$(sudo -n systemctl show symoneural-deploy -p UnitFileState --value 2>/dev/null)"
d_res="$(sudo -n systemctl show symoneural-deploy -p Result --value 2>/dev/null)"
d_st="$(sudo -n systemctl show symoneural-deploy -p ExecMainStatus --value 2>/dev/null)"
d_code="$(sudo -n systemctl show symoneural-deploy -p ExecMainCode --value 2>/dev/null)"
d_ts="$(sudo -n systemctl show symoneural-deploy -p ActiveEnterTimestamp --value 2>/dev/null)"

[ "$d_type" = "oneshot" ] && pass "deploy Type=oneshot" \
                          || fail "deploy Type=$d_type, expected oneshot"
[ "$d_rae" = "yes" ] && pass "deploy RemainAfterExit=yes" \
                     || fail "deploy RemainAfterExit=$d_rae, expected yes" \
                             "without it a successful publish reports inactive(dead) with no activation timestamp"
[ "$d_ufs" = "enabled" ] && pass "deploy UnitFileState=enabled" \
                         || fail "deploy UnitFileState=$d_ufs, expected enabled -- it will not publish at boot"
[ "$d_act" = "active" ] && pass "deploy ActiveState=active" \
                        || fail "deploy ActiveState=$d_act, expected active" \
                                "an enabled deploy unit that is not active has not published this boot"
[ "$d_sub" = "exited" ] && pass "deploy SubState=exited" \
                        || fail "deploy SubState=$d_sub, expected exited"
[ "$d_res" = "success" ] && pass "deploy Result=success" \
                         || fail "deploy Result=$d_res, expected success"
[ "$d_st" = "0" ] && pass "deploy ExecMainStatus=0" \
                  || fail "deploy ExecMainStatus=$d_st, expected 0"
# ExecMainCode is the si_code, and systemd reports it as an INTEGER: 1 == CLD_EXITED. The word
# "exited" is what `systemctl status` prints; `show` gives the number. Accept either so this
# does not fail on a systemd that renders it differently.
case "$d_code" in
    1|exited) pass "deploy ExecMainCode=$d_code (CLD_EXITED)" ;;
    *)        fail "deploy ExecMainCode=$d_code, expected 1/exited (CLD_EXITED)" ;;
esac
[ -n "$d_ts" ] && pass "deploy ActiveEnterTimestamp=$d_ts" \
               || fail "deploy ActiveEnterTimestamp is EMPTY" \
                       "a successful publish must be visible in unit state, not only in the journal"

# ---------------------------------------------------------------- 6. mounts and links
head_ "mounts, symlinks, indirection"
if findmnt -rno TARGET,SOURCE 2>/dev/null | grep -E "$CANON|/yocto" | grep -q "$CANON"; then
    fail "something is mounted over the canonical tree" "$(findmnt -rno TARGET,SOURCE | grep "$CANON" | head -2 | tr '\n' ' ')"
else
    pass "no mount over $CANON"
fi
if find "$CANON" -maxdepth 6 -xdev -type l -lname '/yocto*' -not -path '*/references/*' 2>/dev/null | grep -q .; then
    fail "a symlink under the canonical tree points into /yocto" \
         "$(find "$CANON" -maxdepth 6 -xdev -type l -lname '/yocto*' -not -path '*/references/*' 2>/dev/null | head -3 | tr '\n' ' ')"
else
    pass "no symlink under $CANON points into /yocto"
fi

# ---------------------------------------------------------------- 7. caddy
head_ "caddy"
if sudo -n grep -q '/yocto' /etc/caddy/Caddyfile 2>/dev/null; then
    fail "/etc/caddy/Caddyfile references /yocto"
else
    pass "/etc/caddy/Caddyfile has no /yocto reference"
fi

# ---------------------------------------------------------------- verdict
echo
if [ "$FAILED" -eq 0 ]; then
    printf '\033[32mRUNTIME BOUNDARY CLEAN\033[0m -- no live component requires /yocto.\n'
else
    printf '\033[31mRUNTIME BOUNDARY VIOLATED\033[0m -- see the FAIL lines above.\n'
fi
exit "$FAILED"
