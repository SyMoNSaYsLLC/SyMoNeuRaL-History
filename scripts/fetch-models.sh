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
#
# HOUSE NAMES. Nothing under backend/models/ keeps an upstream filename. What lands on disk
# is symon-1.0-* for the language tiers and symoneural-image-* / symoneural-listen-* for the
# rest; backend/models/PROVENANCE.json records which upstream artefact each one came from,
# and backend/apps/test_weight_names.py fails if a file appears that is not in the manifest
# or not named to the rule. The upstream URLs below are the one thing that cannot be
# rebranded -- you cannot fetch from a repository without naming it -- and the manifest is
# where that mapping is kept honest.
#
# `adopt` below is what makes this safe to run on a box that already downloaded the old
# names: it renames in place. A rename is not a re-quantisation and not a merge, so the
# bytes are untouched and 40 GB is not re-transferred. On a fresh clone the adopt calls are
# all no-ops and the house name is simply what gets downloaded.
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
adopt() { # legacy-path house-path
  local old="$1" new="$2"
  [ -s "$new" ] && return 0            # already adopted; say nothing
  [ -s "$old" ] || return 0            # never downloaded under the old name
  mv "$old" "$new"
  echo "  adopt $(basename "$new") <- $(basename "$old")"
}
# Unconditional, and deliberately above the opt-in gate below: a 27B that was fetched under
# its upstream name must be renamed whether or not this run would fetch it.
echo "house names:"
adopt "$M/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf"   "$M/llm/symon-1.0-7b-q4_k_m.gguf"
adopt "$M/llm/Qwen2.5-14B-Instruct-Q4_K_M.gguf"  "$M/llm/symon-1.0-14b-q4_k_m.gguf"
adopt "$M/llm/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf" "$M/llm/symon-1.0-draft-0.5b-q4_k_m.gguf"
adopt "$M/llm/Qwen3.6-27B-UD-Q2_K_XL.gguf"       "$M/llm/symon-1.0-27b-q2_k_xl.gguf"
adopt "$M/llm/mmproj-F16.gguf"                   "$M/llm/symon-1.0-27b-vision-f16.gguf"
adopt "$M/image/flux1-schnell-q4_k.gguf"         "$M/image/symoneural-image-unet-q4_k.gguf"
adopt "$M/image/t5xxl-Q8_0.gguf"                 "$M/image/symoneural-image-t5-q8_0.gguf"
adopt "$M/image/clip_l.safetensors"              "$M/image/symoneural-image-clip.safetensors"
adopt "$M/image/ae.safetensors"                  "$M/image/symoneural-image-vae.safetensors"
adopt "$M/whisper/ggml-base.en.bin"              "$M/whisper/symoneural-listen-base-en.bin"
HF=https://huggingface.co
echo "chat surface:"
# 7B is the resident workhorse and the base the SyMoNeuRaL LoRA is trained against -- the
# adapter is rank-compatible with these weights and with nothing else. 14B is the heavy tier,
# loaded only when it is the whole job.
get "$HF/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf"   "$M/llm/symon-1.0-7b-q4_k_m.gguf"
get "$HF/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf" "$M/llm/symon-1.0-14b-q4_k_m.gguf"
get "$HF/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf" "$M/llm/symon-1.0-draft-0.5b-q4_k_m.gguf"
# The 27B tier is opt-in, not part of a default install: it is 11.85 GB on its own and is
# still being evaluated as a chat base, so a fresh clone should not pay for it silently.
#   SYMONEURAL_FETCH_27B=1 ./scripts/fetch-models.sh
#
# The gate used to be called SYM_FETCH_QWEN36, which put an upstream company name in an
# environment variable this repo owns. It is accepted as a legacy fallback below so an old
# command line or a stale shell export does not silently stop fetching.
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
# work was needed. The vision tower is fetched but not required -- text inference works
# without it.
if [ "${SYMONEURAL_FETCH_27B:-${SYM_FETCH_27B:-${SYM_FETCH_QWEN36:-0}}}" = "1" ]; then
  echo "chat surface (27B tier, opt-in):"
  get "$HF/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-UD-Q2_K_XL.gguf" "$M/llm/symon-1.0-27b-q2_k_xl.gguf"
  get "$HF/unsloth/Qwen3.6-27B-GGUF/resolve/main/mmproj-F16.gguf"             "$M/llm/symon-1.0-27b-vision-f16.gguf"
else
  echo "chat surface (27B tier): skipped -- set SYMONEURAL_FETCH_27B=1 to fetch 12.8 GB"
fi
# The 32B tier, also opt-in:
#   SYMONEURAL_FETCH_32B=1 ./scripts/fetch-models.sh
#
# UD-Q2_K_XL is 12,797,352,608 bytes. That is a content-length reading taken 2026-08-20, not
# a load attempt, and this repo does not call a file size a fit -- the arithmetic that made it
# worth fetching is: the 27B is 11,849,779,424 bytes and measures 12,354 MiB resident at
# -ngl 99, ctx 8192, f16 KV, so 12.80 GB of weights should land near 13.3 GB resident and
# leave roughly 2.9 GB of the card for KV and CUDA context. Near, should, roughly. Whether it
# actually holds is a llama-bench run, and until that run exists no tok/s or context figure
# from this tier goes on a page.
#
# The other quants were read at the same time and are recorded here so nobody re-measures
# them: UD-IQ2_M 11,553,366,688 B (smaller than the 27B already resident here, so near-certain
# to fit), UD-IQ2_XXS 9,277,096,608 B, UD-Q3_K_XL 16,403,102,368 B (exceeds the 16,303 MiB
# card outright and is not a candidate).
#
# This is NOT the NIM container route. nvcr.io/nim/qwen/qwen3-32b:1.0.0 is refused on three
# independent grounds -- it does not fit, NGC marks it end-of-support, and NVIDIA AI
# Enterprise licenses it for use rather than redistribution. See docs/nim-on-one-card.md.
# The GGUF here is Apache-2.0 and carries none of those problems.
if [ "${SYMONEURAL_FETCH_32B:-${SYM_FETCH_32B:-0}}" = "1" ]; then
  echo "chat surface (32B tier, opt-in):"
  get "$HF/unsloth/Qwen3-32B-GGUF/resolve/main/Qwen3-32B-UD-Q2_K_XL.gguf" "$M/llm/symon-1.0-32b-q2_k_xl.gguf"
else
  echo "chat surface (32B tier): skipped -- set SYMONEURAL_FETCH_32B=1 to fetch 12.80 GB"
fi
echo "image surface:"
get "$HF/leejet/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-q4_k.gguf"                 "$M/image/symoneural-image-unet-q4_k.gguf"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/ae.safetensors"                    "$M/image/symoneural-image-vae.safetensors"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/clip_l.safetensors"                "$M/image/symoneural-image-clip.safetensors"
get "$HF/second-state/FLUX.1-schnell-GGUF/resolve/main/t5xxl-Q8_0.gguf"                   "$M/image/symoneural-image-t5-q8_0.gguf"
# Licences travel with the weights. models/ is gitignored (40 GB), so these files exist
# on disk beside what they cover rather than in git -- and they must be included in any
# customer image. Apache-2.0 obliges shipping the licence text with the artefact.
#
# These filenames keep the upstream name on purpose, and they are the one exception to the
# house-name rule. A licence text is an attribution artefact: a file called
# symon-1.0-7b.LICENSE.txt would be asserting that we licensed those weights, which is not
# what the document says. PROVENANCE.json points each house name at the licence covering it.
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
