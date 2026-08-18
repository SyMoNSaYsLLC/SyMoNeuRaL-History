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
[ -f "$ROOT/backend/api.py" ] || { echo "repo root not found at $ROOT (expected backend/api.py)" >&2; exit 1; }
M="$ROOT/backend/models"
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
# Qwen3.6-27B is opt-in, not part of a default install: it is 11.85 GB on its own and is
# still being evaluated as a chat base, so a fresh clone should not pay for it silently.
#   SYM_FETCH_QWEN36=1 ./scripts/fetch-models.sh
#
# UD-Q2_K_XL is 11,849,779,424 bytes, which is where the "under 12" figure comes from, and it
# has been loaded here: fully GPU-resident at -ngl 99, 12,354 MiB of 16,303 at ctx 8192 / f16
# KV. UD-IQ2_M (10.85 GB) and UD-IQ2_XXS (9.39 GB) are smaller and have NOT been tested here --
# those are content-length readings, not load attempts, and this repo does not call a file size
# a fit. UD-Q4_K_XL (17.61 GB) exceeds the card and would need CPU offload against the 94 GB of
# system RAM in this box; also untested.
#
# Do NOT confuse this with the 11.87 GB on the NGC page for the NIM container. That is a
# compressed registry image size and the near-identical number is a coincidence -- see the
# header of scripts/nim-qwen36.sh. Only the figure here is a weights-on-disk measurement.
#
# The engine already understands these: the GGUF header declares
# general.architecture = qwen35, and contrib/llama.cpp carries LLM_ARCH_QWEN35. No build
# work was needed. mmproj-F16.gguf is the vision tower -- Qwen3.6 is multimodal, and text
# inference works without it, so it is fetched but not required.
if [ "${SYM_FETCH_QWEN36:-0}" = "1" ]; then
  echo "chat surface (Qwen3.6-27B, opt-in):"
  get "$HF/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-UD-Q2_K_XL.gguf" "$M/llm/Qwen3.6-27B-UD-Q2_K_XL.gguf"
  get "$HF/unsloth/Qwen3.6-27B-GGUF/resolve/main/mmproj-F16.gguf"             "$M/llm/mmproj-F16.gguf"
else
  echo "chat surface (Qwen3.6-27B): skipped -- set SYM_FETCH_QWEN36=1 to fetch 12.8 GB"
fi
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
