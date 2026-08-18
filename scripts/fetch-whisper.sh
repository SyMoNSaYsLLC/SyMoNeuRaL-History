#!/usr/bin/env bash
# Fetch and build whisper.cpp -- the speech-to-text half of SyMoNeuRaL Stickers.
#
# **This builds a CPU-only binary on purpose, and that is the whole design.**
#
# One RTX 5070 Ti, 15.92 GiB, one tenant at a time. A sticker spoken into a phone is
# ASR -> the existing text path -> a render, and if the ASR were a CUDA tenant that
# sequence would be: take the lock, transcribe, release, wait for the 1.5 GiB drain
# floor, take the lock again, render. The drain wait alone is bounded at 60 s. So the
# transcription is deliberately kept off the card, where it can run *while* another
# surface holds the GPU rather than queueing behind it.
#
# That is not a new idea here -- it is RavenCalc's, which stays off the lock for exactly
# this reason and is the precedent HANDOVER §5 item 12 names for the voice work.
#
#   ./scripts/fetch-whisper.sh              # build + the default model
#   ./scripts/fetch-whisper.sh base.en      # a specific model
#
# Licences, both permissive and both recorded in LICENSES.md in the same commit that
# added this file:
#   whisper.cpp   MIT        (ggerganov/whisper.cpp)
#   ggml weights  MIT        (ggerganov/whisper.cpp model releases on Hugging Face)
set -uo pipefail

# Repo root is one level up from scripts/. The same calculation has been wrong three
# times in this repo and it fails silently, because the wrong parent is usually a
# directory that exists -- so it is asserted rather than assumed.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
[ -f "$ROOT/scripts/gpu-governor.sh" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }

SRC="$ROOT/contrib/whisper.cpp"
MODELS="$ROOT/backend/models/whisper"
MODEL="${1:-base.en}"
REPO="https://github.com/ggerganov/whisper.cpp.git"
WEIGHTS="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${MODEL}.bin"

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }

# ---- source ---------------------------------------------------------------------
if [ -d "$SRC/.git" ]; then
  say "whisper.cpp already checked out at $SRC"
else
  say "cloning whisper.cpp -> $SRC"
  mkdir -p "$(dirname "$SRC")"
  git clone --depth 1 "$REPO" "$SRC" || { echo "clone failed" >&2; exit 1; }
fi

# ---- build ----------------------------------------------------------------------
# -DGGML_CUDA=OFF is not a default we are accepting, it is a choice we are making. See
# the header. -DWHISPER_BUILD_TESTS=OFF keeps the build to the one binary we call.
if [ -x "$SRC/build/bin/whisper-cli" ]; then
  say "whisper-cli already built"
else
  say "building whisper.cpp (CPU only -- this never takes the GPU lock)"
  cmake -S "$SRC" -B "$SRC/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON >/dev/null || { echo "cmake configure failed" >&2; exit 1; }
  cmake --build "$SRC/build" --config Release -j "$(nproc)" || { echo "build failed" >&2; exit 1; }
fi
[ -x "$SRC/build/bin/whisper-cli" ] || { echo "whisper-cli missing after build" >&2; exit 1; }

# ---- weights --------------------------------------------------------------------
mkdir -p "$MODELS"
DEST="$MODELS/ggml-${MODEL}.bin"
if [ -s "$DEST" ]; then
  say "model already present: $DEST ($(du -h "$DEST" | cut -f1))"
else
  say "downloading ggml-${MODEL}.bin"
  curl -fL --retry 3 -o "$DEST.part" "$WEIGHTS" || { rm -f "$DEST.part"; echo "download failed" >&2; exit 1; }
  mv "$DEST.part" "$DEST"
  say "model at $DEST ($(du -h "$DEST" | cut -f1))"
fi

# ---- licences -------------------------------------------------------------------
# MIT obliges only that the copyright line and permission notice travel with the code -- but
# "only" is still an obligation, and `LICENSES.md` §9 checks `backend/models/licenses/` for
# exactly this. `contrib/whisper.cpp/LICENSE` arrives with the clone and covers the binary;
# the weights are a separate artefact from a separate publisher and need their own text.
L="$ROOT/backend/models/licenses"; mkdir -p "$L"
lic() { # url dest
  [ -s "$L/$2" ] && { echo "  have $2"; return; }
  if curl -fsSL --retry 3 -o "$L/$2.part" "$1" 2>/dev/null && [ -s "$L/$2.part" ]; then
    mv "$L/$2.part" "$L/$2"; echo "  get  $2"
  else
    rm -f "$L/$2.part"; echo "  MISS $2 (fetch by hand before shipping a build)" >&2
  fi
}
say "licences"
# The GGUF conversions are republished by ggerganov under MIT (model card declares it), and
# they are conversions of OpenAI's Whisper, which is MIT at source. Both texts are kept: the
# redistributor's and the originator's, because the weights are a derived work of the latter.
lic "https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/LICENSE" \
    whisper.cpp.LICENSE.txt
lic "https://raw.githubusercontent.com/openai/whisper/main/LICENSE" \
    openai-whisper.LICENSE.txt

say "done -- $("$SRC/build/bin/whisper-cli" --help 2>&1 | head -1)"
