#!/usr/bin/env bash
# Fetch the GGUF weight sets for the SyMoNeuRaL demo surfaces.
# Every source here is ungated and commercially licensed:
#   Qwen2.5-14B-Instruct  Apache-2.0
#   FLUX.1-schnell        Apache-2.0
set -euo pipefail
M="$(cd "$(dirname "$0")/.." && pwd)/models"
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
echo "done."
