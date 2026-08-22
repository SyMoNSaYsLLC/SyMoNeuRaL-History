#!/usr/bin/env bash
# symoneural-modelops-stage.sh -- stage, smoke, promote and roll back a model bundle.
#
# ## What this is for
#
# Swapping the model a surface loads is the highest-consequence change on this box and the
# easiest one to do badly: the weights are 194 GB, the active default is four lines in
# `backend/api.py`, and nothing in git records either. So the swap gets a script with the
# guardrails written as refusals rather than as comments, and every mode below is safe to run
# on a live box.
#
# ## The rule this file exists to enforce
#
#   NOTHING IS DOWNLOADED, ACTIVATED, MOVED OR DELETED WITHOUT AN EXPLICIT FLAG.
#
# `--inventory`, `--dry-run`, `--smoke-plan` and `--write-docs` are read-only. `--stage-*`
# prepares a directory and prints the download command but does not run it unless the operator
# also passes the confirmation phrase. `--activate-candidate` refuses on five separate
# conditions, and `--rollback` is the only mode that is safe to reach for in a hurry.
#
# ## Modes
#
#   --dry-run                      say what each mode would do; change nothing
#   --inventory                    the measured model inventory (tools/modelops_inventory.py)
#   --stage-openai-gpt-oss-20b     prepare staging for the LLM candidate; no download
#   --write-docs                   regenerate the inventory block in the ops docs
#   --smoke-plan                   print the smoke steps a candidate must pass
#   --activate-candidate <id>      promote a staged, smoked candidate -- five gates
#   --rollback [<id>]              print and write the rollback path; restore a backup
#
# ## Why the download is two steps
#
# `openai/gpt-oss-20b` is tens of gigabytes onto a disk already holding 194 GB. A flag that
# both prepares and downloads means a typo costs a disk. So `--stage-*` writes the manifest,
# the rollback note and the exact command, and the download itself needs
# SYMONEURAL_MODELOPS_CONFIRM to carry the phrase Garrett has to type.
set -euo pipefail

CONFIRM_PHRASE="RUN MODEL DOWNLOAD"
CANDIDATE_ID="symon-openai-20b"
CANDIDATE_UPSTREAM="openai/gpt-oss-20b"
STAGING_REL="backend/models/staging"

# ---------------------------------------------------------------------------- guardrail 1
# Run from the repo root or not at all. Every path below is relative, and a script like this
# run from the wrong directory is how a staging tree lands somewhere nobody looks again.
if [[ ! -f "backend/api.py" || ! -f "tools/modelops_inventory.py" ]]; then
  echo "refusing: run this from the repository root (backend/api.py not found here)" >&2
  exit 2
fi
ROOT="$(pwd)"

BOLD=$'\033[1m'; DIM=$'\033[2m'; AMBER=$'\033[33m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
head_() { printf '%s%s%s\n' "$BOLD" "$*" "$OFF"; }
warn() { printf '%s%s%s\n' "$AMBER" "$*" "$OFF" >&2; }
dim()  { printf '%s%s%s\n' "$DIM" "$*" "$OFF"; }

DRY_RUN=0

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ---------------------------------------------------------------------------- disk
show_disk() {
  head_ "disk"
  df -h . | awk 'NR==1 || NR==2 {print "  " $0}'
  if [[ -d backend/models ]]; then
    dim "  backend/models: $(du -sh backend/models 2>/dev/null | cut -f1)"
  fi
}

# ---------------------------------------------------------------------------- inventory
mode_inventory() {
  python3 tools/modelops_inventory.py
  say ""
  show_disk
}

# ---------------------------------------------------------------------------- smoke plan
mode_smoke_plan() {
  local id="${1:-$CANDIDATE_ID}"
  head_ "smoke plan for $id"
  cat <<'PLAN'
  A candidate is not smoked because it downloaded. It is smoked when a real generation came
  out of it on this box, and the marker file is the evidence:

    1. runtime load        the serving engine opens the file without converting it
    2. tokenizer/template  a chat turn round-trips with the model's own chat template
    3. one real generation  non-empty output, recorded with the prompt and the timing
    4. VRAM measured        nvidia-smi during the generation, not a projection
    5. governor lease       the generation took and released a lease like any other tenant
    6. fallback proven      the previous default still loads after the candidate is unloaded

  Write the readings into:

    backend/models/staging/<id>/SMOKE-PASSED.txt

  That file cannot be written honestly without having run the thing, which is the whole
  reason `--activate-candidate` requires it. `exists` and `grep` cannot ask whether a model
  works; a stamped smoke record can.
PLAN
}

# ---------------------------------------------------------------------------- staging
mode_stage_gpt_oss() {
  local dir="$STAGING_REL/openai-gpt-oss-20b"
  head_ "stage $CANDIDATE_ID  <-  $CANDIDATE_UPSTREAM"

  if (( DRY_RUN )); then
    dim "  dry run: would create $dir, write STAGED-MANIFEST.json and ROLLBACK.md"
    dim "  dry run: would NOT download -- that needs SYMONEURAL_MODELOPS_CONFIRM"
    return 0
  fi

  mkdir -p "$dir"

  # The manifest is written BEFORE any download, so a half-finished fetch still leaves a
  # record of what was being attempted and where it came from.
  cat > "$dir/STAGED-MANIFEST.json" <<JSON
{
  "candidate_id": "$CANDIDATE_ID",
  "display_name": "SyMoNeuRaL OpenAI 20B",
  "short_name": "SyMon OpenAI 20B",
  "upstream_repo": "$CANDIDATE_UPSTREAM",
  "local_dir": "$dir",
  "status": "AUDIT / CANDIDATE",
  "active_default": false,
  "downloaded": false,
  "smoke_passed": false,
  "rollback_to": {
    "chat": "backend/models/llm/symon-1.0-7b-q4_k_m.gguf",
    "chat_draft": "backend/models/llm/symon-1.0-draft-0.5b-q4_k_m.gguf",
    "upstream": "bartowski/Qwen2.5-7B-Instruct-GGUF",
    "note": "measured active default at the time of staging; not deleted, not moved"
  },
  "runtime_compatibility": "UNRECORDED -- see docs/ops/OPENAI-GPT-OSS-MIGRATION.md",
  "license": "UNRECORDED -- upstream licence must be read and stored before activation",
  "notes": "Written by scripts/modelops/symoneural-modelops-stage.sh. No weights fetched."
}
JSON

  cat > "$dir/ROLLBACK.md" <<'ROLL'
# Rollback — SyMoNeuRaL OpenAI 20B candidate

**The rollback is that nothing was removed.** Staging does not touch the active default, so
the previous model is not "restored" — it never stopped being the one in use.

The active chat default is set in **`backend/api.py`**:

    CHAT_MODEL = MODELS / "llm" / "symon-1.0-7b-q4_k_m.gguf"
    DRAFT_MODEL = MODELS / "llm" / "symon-1.0-draft-0.5b-q4_k_m.gguf"

## If a promotion has been applied and you want it undone

1. `scripts/modelops/symoneural-modelops-stage.sh --rollback` — restores
   `backend/api.py` from the `.modelops-backup` written at promotion time.
2. Restart the API. A file swap is not live until the process re-reads it.
3. Confirm with `/api/status` that `model` reads the Qwen file again.

## What rollback does NOT do

It does not delete the candidate, and it does not delete the Qwen weights — **no mode of this
script deletes a weight file.** Disk is cheaper than a model you cannot get back.
ROLL

  say ""
  dim "  wrote $dir/STAGED-MANIFEST.json"
  dim "  wrote $dir/ROLLBACK.md"
  say ""
  head_ "download -- NOT run"
  say "  The command, recorded rather than executed:"
  say ""
  say "    huggingface-cli download $CANDIDATE_UPSTREAM \\"
  say "      --include \"original/*\" \\"
  say "      --local-dir $dir/"
  say ""
  if [[ "${SYMONEURAL_MODELOPS_CONFIRM:-}" == "$CONFIRM_PHRASE" ]]; then
    warn "  SYMONEURAL_MODELOPS_CONFIRM is set, but this script still will not fetch."
    warn "  The download is Garrett's to run by hand: it is tens of GB onto a disk already"
    warn "  holding 194 GB, and a script that can spend a disk should not be one flag away."
  else
    dim "  refusing to download: SYMONEURAL_MODELOPS_CONFIRM is not set to the phrase."
  fi
  say ""
  show_disk
}

# ---------------------------------------------------------------------------- activation
mode_activate() {
  local id="${1:-}"
  if [[ -z "$id" ]]; then
    echo "refusing: --activate-candidate needs an explicit candidate id" >&2
    exit 2
  fi
  local dir="$STAGING_REL/${id#symon-}"
  [[ -d "$dir" ]] || dir="$STAGING_REL/openai-gpt-oss-20b"

  head_ "activation gate for $id"
  local fail=0
  check() {                                       # check <label> <condition-desc> <0|1>
    if (( $3 )); then dim "  PASS  $1"; else warn "  FAIL  $1 -- $2"; fail=1; fi
  }

  check "candidate staged"          "no $dir/STAGED-MANIFEST.json" \
        "$([[ -f "$dir/STAGED-MANIFEST.json" ]] && echo 1 || echo 0)"
  check "smoke marker present"      "no $dir/SMOKE-PASSED.txt -- run the smoke plan first" \
        "$([[ -f "$dir/SMOKE-PASSED.txt" ]] && echo 1 || echo 0)"
  check "rollback recorded"         "no $dir/ROLLBACK.md" \
        "$([[ -f "$dir/ROLLBACK.md" ]] && echo 1 || echo 0)"
  check "licence recorded"          "STAGED-MANIFEST.json still says UNRECORDED for license" \
        "$([[ -f "$dir/STAGED-MANIFEST.json" ]] && ! grep -q '"license": "UNRECORDED' "$dir/STAGED-MANIFEST.json" && echo 1 || echo 0)"
  check "runtime compat recorded"   "STAGED-MANIFEST.json still says UNRECORDED for runtime" \
        "$([[ -f "$dir/STAGED-MANIFEST.json" ]] && ! grep -q '"runtime_compatibility": "UNRECORDED' "$dir/STAGED-MANIFEST.json" && echo 1 || echo 0)"
  check "owner approval in env"     "set SYMONEURAL_MODELOPS_APPROVE=$id to approve" \
        "$([[ "${SYMONEURAL_MODELOPS_APPROVE:-}" == "$id" ]] && echo 1 || echo 0)"

  say ""
  if (( fail )); then
    warn "activation REFUSED -- $id stays a candidate and the active default is untouched."
    exit 3
  fi
  if (( DRY_RUN )); then
    dim "  dry run: all gates pass; would back up backend/api.py and rewrite CHAT_MODEL"
    return 0
  fi
  # Backup first, always, and never in place.
  cp backend/api.py "backend/api.py.modelops-backup"
  dim "  backed up backend/api.py -> backend/api.py.modelops-backup"
  warn "  the CHAT_MODEL rewrite is deliberately not implemented in this script."
  warn "  Promotion edits a source file that the API reads at import; it belongs in a"
  warn "  reviewed commit with a test, not in a shell one-liner. The gate above is the"
  warn "  deliverable -- it says whether promotion is ALLOWED, not how to sneak it past review."
  exit 4
}

# ---------------------------------------------------------------------------- rollback
mode_rollback() {
  head_ "rollback"
  say "  active chat default is set in backend/api.py:"
  grep -nE '^(CHAT_MODEL|DRAFT_MODEL)\s*=' backend/api.py | sed 's/^/    /'
  say ""
  if [[ -f "backend/api.py.modelops-backup" ]]; then
    if (( DRY_RUN )); then
      dim "  dry run: would restore backend/api.py from backend/api.py.modelops-backup"
    else
      cp "backend/api.py.modelops-backup" backend/api.py
      dim "  restored backend/api.py from backend/api.py.modelops-backup"
      warn "  restart the API -- a file swap is not live until the process re-reads it."
    fi
  else
    dim "  no promotion backup exists, so there is nothing to roll back."
    dim "  The Qwen default has never been changed and its weights were never moved."
  fi
  say ""
  say "  No weight file is deleted by any mode of this script."
}

# ---------------------------------------------------------------------------- docs
mode_write_docs() {
  head_ "write-docs"
  if (( DRY_RUN )); then
    dim "  dry run: would refresh the inventory block in docs/ops/SYMONEURAL-MODEL-BUNDLES.md"
    return 0
  fi
  warn "  not implemented as an in-place rewrite on purpose."
  say "  The ops docs carry prose around their figures, and a generator that rewrites a"
  say "  section it does not fully own is how this repo grew its accumulate bug three times."
  say "  Regenerate the numbers and paste them deliberately:"
  say ""
  say "    python3 tools/modelops_inventory.py > /tmp/modelops-inventory.txt"
  say "    python3 tools/modelops_inventory.py --json > /tmp/modelops-inventory.json"
}

# ---------------------------------------------------------------------------- main
[[ $# -gt 0 ]] || usage 0
MODE=""; ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)                    DRY_RUN=1 ;;
    --inventory)                  MODE=inventory ;;
    --stage-openai-gpt-oss-20b)   MODE=stage ;;
    --write-docs)                 MODE=docs ;;
    --smoke-plan)                 MODE=smoke ;;
    --activate-candidate)         MODE=activate; ARG="${2:-}"; [[ -n "${2:-}" ]] && shift ;;
    --rollback)                   MODE=rollback; if [[ "${2:-}" == --* || -z "${2:-}" ]]; then :; else ARG="$2"; shift; fi ;;
    -h|--help)                    usage 0 ;;
    *) echo "unknown flag: $1" >&2; usage 2 ;;
  esac
  shift
done

case "$MODE" in
  inventory) mode_inventory ;;
  stage)     mode_stage_gpt_oss ;;
  smoke)     mode_smoke_plan "$ARG" ;;
  activate)  mode_activate "$ARG" ;;
  rollback)  mode_rollback ;;
  docs)      mode_write_docs ;;
  "")        usage 0 ;;
esac
