#!/usr/bin/env bash
# Runtime/engine compatibility.
# Wraps: engines/ presence probes + nvidia-smi/nvcc. No model authority needed by design. Deliberately answerable with no model present: the question
# "can this box run a model" is independent of "is a model here".
. "$(dirname "${BASH_SOURCE[0]}")/_models_common.sh"
say "── runtime / engine compatibility ─────────────────────────"
for e in symoneural-llm symoneural-diffuse symoneural-ui; do
  printf '  %-22s %s\n' "$e" "$([ -d "$ROOT/$e" ] && echo present || echo '<absent>')"
done
printf '  %-22s %s\n' "nvcc" "$(nvcc --version 2>/dev/null | grep -oE 'release [0-9.]+' || echo UNKNOWN)"
printf '  %-22s %s\n' "driver" "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo UNKNOWN)"
printf '  %-22s %s\n' "compute capability" "$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 || echo UNKNOWN)"
echo
print_payload_state
