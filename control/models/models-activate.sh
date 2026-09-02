#!/usr/bin/env bash
# Promote a staged AND smoked candidate.
# Wraps: scripts/modelops/symoneural-modelops-stage.sh --activate-candidate. The six refusal gates live in the modelops
# authority; this must not bypass them (STOP condition 1), so it forwards rather than
# reimplementing any part of the promotion.
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
require_authority "$MODELOPS"
[ $# -gt 0 ] || die "usage: models-activate.sh <candidate-id>
  the candidate must already be staged and smoked; six gates are enforced downstream"
warn "activation changes the model a live surface loads"
exec bash "$MODELOPS" --activate-candidate "$@"
