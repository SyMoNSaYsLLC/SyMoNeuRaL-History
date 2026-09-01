#!/usr/bin/env bash
# Run the repo's test suites from one place. Read docs/ops/MEASUREMENTS.md before quoting
# any count from this -- it prints what it measured, not a stored figure.
#
#   test-all.sh py|node|progress|all
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

run_py() { say "── pytest (backend) ──"; ( cd "$ROOT/backend" && python3 -m pytest -q 2>&1 | tail -15 ); }
run_progress() {
  say "── progress generator (run twice, diff) ──"
  ( cd "$ROOT" && python3 tools/build_progress.py >/dev/null 2>&1 \
    && cp run/progress.html /tmp/.pg1 \
    && python3 tools/build_progress.py >/dev/null 2>&1 \
    && { diff -q /tmp/.pg1 run/progress.html >/dev/null && echo "  stable ✓" || echo "  UNSTABLE — accumulation bug"; } )
  ( cd "$ROOT/backend" && python3 -m pytest apps/test_build_progress.py -q 2>&1 | tail -3 )
}
run_node() {
  say "── node suites ──"
  [ -d "$ROOT/tests" ] || { warn "no tests/ dir"; return; }
  ls "$ROOT"/tests/*.mjs 2>/dev/null | sed 's|.*/|  |' || echo "  (none)"
  warn "browser suites take the GPU and must not run in parallel -- run individually:"
  echo "    node tests/<name>.mjs"
}

case "${1:-all}" in
  py) run_py ;; node) run_node ;; progress) run_progress ;;
  all) run_py; echo; run_progress; echo; run_node ;;
  *) die "usage: test-all.sh py|node|progress|all" ;;
esac
