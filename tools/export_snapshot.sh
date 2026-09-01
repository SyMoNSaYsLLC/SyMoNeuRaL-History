#!/usr/bin/env bash
#
# export_snapshot.sh -- the only sanctioned way a snapshot leaves this box.
#
# `docs/ops/EXPORTS.md` rule 4 names this script and nothing else. It exists because of the
# #75 finding: every whole-repo zip shared for review carried `training/corpus.jsonl` and
# `training/build_dataset.py`, because both are tracked and the zips were built from tracked
# files. Trade secret exists only while reasonable measures keep it in.
#
# ## Allow-list construction, not repository-minus-deny-list
#
# The export is BUILT UP from an explicit scope manifest. It is never the repository with
# known-bad paths subtracted. That distinction is the whole security argument and the two
# architectures give OPPOSITE answers for a path nobody classified:
#
#     deny-list   unclassified path -> SHIPPED     (fails open; one missed pattern leaks)
#     allow-list  unclassified path -> ABSENT      (fails closed; must be named to ship)
#
# So stage 1 starts from the empty set and adds only what the manifest names. A file that
# nobody thought about cannot leave, because nothing put it in.
#
# ## Two independent stages, both must pass
#
#   stage 1   construct   start empty; add only manifest-named paths that exist
#   stage 2   enforce     re-scan the CONSTRUCTED set for protected classes; abort on any
#
# Stage 2 is not redundant. It catches an over-broad manifest entry -- a directory named in
# the manifest that later gains a protected file underneath it. Stage 1 trusts the manifest;
# stage 2 trusts nothing.
#
# ## Refusal is not an error path, it is the point
#
# Every refusal exits non-zero and emits NO archive. A tool that detects a violation after
# writing the archive has already produced the artefact that must not exist, so the archive
# is assembled in a staging directory and only sealed once stage 2 has passed.
#
#   export_snapshot.sh --manifest <file> --out <archive.zip> [--root <dir>] [--dry-run]
#
# The manifest is a newline-delimited list of repo-relative paths. Blank lines and `#`
# comments are ignored. THIS IS THE MINIMUM INTERFACE NEEDED TO CONSUME AN EXPLICIT
# ALLOW-LIST -- it is deliberately not a production manifest schema. Who owns a manifest,
# where it lives, how it is generated per customer, and what a real customer is allowed to
# receive are all A-4 questions and are NOT decided here.
set -euo pipefail

PROG="$(basename "$0")"
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 1; }
refuse() { printf '%s: REFUSED -- %s\n' "$PROG" "$*" >&2; exit 3; }
info() { printf '%s: %s\n' "$PROG" "$*"; }

# --- protected classes ------------------------------------------------------------------
# Derived from docs/ops/EXPORTS.md rules 2 and 3. These are matched against the CONSTRUCTED
# set in stage 2. Extended-regex, matched against the repo-relative path.
#
# Note the deliberate redundancy with stage 1: nothing here is load-bearing for a correct
# manifest, and all of it is load-bearing for an incorrect one.
PROTECTED_PATTERNS=(
  'training/corpus\.jsonl$'            # the 327 hand-authored examples -- the #75 leak
  'training/build_dataset\.py$'        # reconstructs the corpus
  '(^|/)training/adapter[^/]*/'        # adapter weights
  '(^|/)GARRETT-REQUESTS\.md$'         # mode-600 ledger
  '(^|/)INTAKE\.md$'                   # mode-600 ledger
  '(^|/)review/'                       # internal audit/evidence
  '(^|/)run/'                          # runtime state
  '(^|/)\.git/'                        # canonical history -- never leaves this box
  '\.env$'                             # secrets
  '(^|/)\.env\.'                       # secrets
  '(^|/)\.git-credentials$'            # credentials
  '(^|/)\.[a-z]*credentials$'          # credentials
  '(^|/)\.passwd-'                     # credentials
  '(^|/)id_(rsa|ed25519|ecdsa)$'       # private keys
  '\.(pem|key|p12|pfx)$'               # private keys / signing material
  '(^|/)secrets?/'                     # secret material
  'providerapikeys'                    # api keys
)
PROTECTED_LABELS=(
  "protected training corpus" "corpus build script" "adapter weights"
  "mode-600 ledger" "mode-600 ledger" "internal review material" "runtime state"
  "repository history" "environment secrets" "environment secrets"
  "credential file" "credential file" "credential file"
  "private key" "key/signing material" "secret material" "api keys"
)

MANIFEST="" OUT="" ROOT="" DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --manifest) MANIFEST="${2:-}"; shift 2 ;;
    --out)      OUT="${2:-}";      shift 2 ;;
    --root)     ROOT="${2:-}";     shift 2 ;;
    --dry-run)  DRY=1;             shift   ;;
    -h|--help)  sed -n '2,40p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ -n "$MANIFEST" ] || die "--manifest is required (no implicit whole-repo export exists)"
[ -f "$MANIFEST" ] || die "manifest not found: $MANIFEST"
[ -n "$OUT" ] || [ "$DRY" -eq 1 ] || die "--out is required unless --dry-run"

if [ -z "$ROOT" ]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
[ -d "$ROOT" ] || die "root not a directory: $ROOT"
ROOT="$(cd "$ROOT" && pwd)"

# --- stage 1: construct from the allow-list ----------------------------------------------
# Start empty. This loop is the only thing that can add a path.
CANDIDATES=()
lineno=0
while IFS= read -r raw || [ -n "$raw" ]; do
  lineno=$((lineno + 1))
  line="${raw%%#*}"
  line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -n "$line" ] || continue

  case "$line" in
    /*)    refuse "manifest line $lineno is absolute; paths must be repo-relative: $line" ;;
    *..*)  refuse "manifest line $lineno contains '..' traversal: $line" ;;
  esac

  target="$ROOT/$line"
  if [ -f "$target" ]; then
    CANDIDATES+=("$line")
  elif [ -d "$target" ]; then
    while IFS= read -r f; do
      CANDIDATES+=("${f#$ROOT/}")
    done < <(find "$target" -type f | sort)
  else
    # A manifest naming something absent is a manifest that no longer matches the tree.
    # Skipping silently would ship a smaller export than the operator authorised and nobody
    # would know, so this is fatal rather than a warning.
    refuse "manifest line $lineno names a path that does not exist: $line"
  fi
done < "$MANIFEST"

[ "${#CANDIDATES[@]}" -gt 0 ] || refuse "manifest selected zero files -- nothing to export"

# --- stage 2: independently enforce protected classes over the CONSTRUCTED set -----------
violations=0
for path in "${CANDIDATES[@]}"; do
  for i in "${!PROTECTED_PATTERNS[@]}"; do
    if printf '%s' "$path" | grep -qE "${PROTECTED_PATTERNS[$i]}"; then
      # Name the class and the path. Never the contents.
      printf '%s: PROTECTED [%s] %s\n' "$PROG" "${PROTECTED_LABELS[$i]}" "$path" >&2
      violations=$((violations + 1))
      break
    fi
  done
done

if [ "$violations" -gt 0 ]; then
  refuse "$violations protected path(s) in the candidate set; no archive written"
fi

info "stage 1: ${#CANDIDATES[@]} file(s) selected by manifest"
info "stage 2: 0 protected paths -- passed"

if [ "$DRY" -eq 1 ]; then
  printf '%s\n' "${CANDIDATES[@]}"
  info "dry run -- no archive written"
  exit 0
fi

# --- seal: assemble in staging, only then emit -------------------------------------------
command -v zip >/dev/null 2>&1 || die "zip not available"
STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

for path in "${CANDIDATES[@]}"; do
  mkdir -p "$STAGE/$(dirname "$path")"
  cp -p "$ROOT/$path" "$STAGE/$path"
done

SOURCE_SHA="$(cd "$ROOT" && git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
{
  printf 'EXPORT-MANIFEST\n'
  printf 'generated: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'source-sha: %s\n' "$SOURCE_SHA"
  printf 'scope-manifest: %s\n' "$(basename "$MANIFEST")"
  printf 'file-count: %s\n' "${#CANDIDATES[@]}"
  printf '\nsha256  path\n'
  for path in "${CANDIDATES[@]}"; do
    printf '%s  %s\n' "$(sha256sum "$STAGE/$path" | cut -d' ' -f1)" "$path"
  done
} > "$STAGE/EXPORT-MANIFEST"

OUT_ABS="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
rm -f "$OUT_ABS"
( cd "$STAGE" && zip -q -r -X "$OUT_ABS" . )
info "wrote $OUT_ABS (${#CANDIDATES[@]} file(s) + EXPORT-MANIFEST)"
info "source-sha: $SOURCE_SHA"
