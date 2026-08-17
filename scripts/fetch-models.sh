#!/usr/bin/env bash
# Fetch the GGUF weight sets for the SyMoNeuRaL surfaces, and the licences that must
# travel with them.
#
# Every source here is ungated and commercially licensed, all Apache-2.0:
#   Qwen2.5-7B / 14B / 0.5B-Instruct     chat, heavy tier, speculative draft
#   FLUX.1-schnell (+ VAE, T5-XXL, CLIP-L)  image
#
# FLUX.1-schnell ONLY. FLUX.1-dev is non-commercial and must never be substituted into
# anything customer-facing. See LICENSES.md.
set -euo pipefail
# Repo root is one level up now that this lives in scripts/. This calculation has
# been wrong three times in this repo (the demo/ flatten, the tools/ move, here) and
# it fails silently, because the wrong parent is usually a directory that exists.
# The guard below turns that into an immediate, obvious failure.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/api.py" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }
M="$ROOT/models"
get() { # url dest
  local url="$1" dest="$2"
  [ -s "$dest" ] && { echo "  have $(basename "$dest")"; return; }
  echo "  get  $(basename "$dest")"
  curl -fL --retry 5 --retry-delay 3 -C - -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
}
HF=https://huggingface.co
echo "chat surface:"
# 7B is the resident workhorse and the base the SyMoNeuRaL LoRA is trained against -- the
# adapter is rank-compatible with these weights and with nothing else. 14B is the heavy tier,
# loaded only when it is the whole job.
get "$HF/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf"   "$M/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
get "$HF/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf" "$M/llm/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
echo "image surface:"
get "$HF/leejet/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-q4_k.gguf"                 "$M/image/flux1-schnell-q4_k.gguf"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/ae.safetensors"                    "$M/image/ae.safetensors"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/clip_l.safetensors"                "$M/image/clip_l.safetensors"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/t5xxl-Q8_0.gguf"                   "$M/image/t5xxl-Q8_0.gguf"
# Licences travel with the weights. models/ is gitignored (40 GB), so these files exist
# on disk beside what they cover rather than in git -- and they must be included in any
# customer image. Apache-2.0 obliges shipping the licence text with the artefact.
echo "licences:"
L="$M/licenses"; mkdir -p "$L"
lic() { # url dest
  [ -s "$L/$2" ] && { echo "  have $2"; return; }
  if curl -fsSL --retry 3 -o "$L/$2.part" "$1" 2>/dev/null && [ -s "$L/$2.part" ]; then
    mv "$L/$2.part" "$L/$2"; echo "  get  $2"
  else
    rm -f "$L/$2.part"; echo "  MISS $2 (fetch by hand before shipping a build)" >&2
  fi
}
lic "$HF/Qwen/Qwen2.5-7B-Instruct/resolve/main/LICENSE"   Qwen2.5-7B-Instruct.LICENSE.txt
lic "$HF/Qwen/Qwen2.5-14B-Instruct/resolve/main/LICENSE"  Qwen2.5-14B-Instruct.LICENSE.txt
lic "$HF/Qwen/Qwen2.5-0.5B-Instruct/resolve/main/LICENSE" Qwen2.5-0.5B-Instruct.LICENSE.txt
# black-forest-labs ships no LICENSE file; the apache-2.0 declaration is in the model card,
# so the card is the artefact worth keeping.
lic "$HF/black-forest-labs/FLUX.1-schnell/resolve/main/README.md" FLUX.1-schnell.MODEL-CARD.md

echo "done."
