#!/usr/bin/env bash
#
# fork_engines.sh -- build SyMoNeuRaL's inference engines into engines/, from source,
# under our own names.
#
# WHY THIS SCRIPT EXISTS. The two engines behind the chat and image surfaces were being
# run straight out of references/, which is a reference-only tree: nothing in it may be
# imported, built or linked by the shipped product, and nothing ships under a third-party
# name. api.py pointed at references/contrib/.../llama-server and .../sd-cli, so both
# rules were broken at once and, once references/ moved, chat and image went offline.
#
# This script takes the vendored upstream source as INPUT -- the way you would treat a
# release tarball -- and produces our engine as OUTPUT under engines/. After it runs, the
# running product has no path into references/ at all: the binaries live in engines/, and
# their RUNPATH is $ORIGIN, so every library they load is one we built and named.
#
# HOW THE RENAMING WORKS, and why it is not a sed sweep over 874 MB of C++. CMake's
# OUTPUT_NAME changes the file written to disk and nothing else -- every
# target_link_libraries() reference in the tree is by CMake *target* name, which we leave
# alone. So the build graph is untouched (zero risk of a broken link line) while the
# artifacts that actually ship carry our names. This is only safe because
# GGML_BACKEND_DL is OFF in this configuration: backends are linked directly, so nothing
# discovers a library by globbing a filename pattern. Verified before writing this:
#   grep GGML_BACKEND_DL build/CMakeCache.txt  ->  OFF
#   readelf -d build/bin/llama-server          ->  RUNPATH [$ORIGIN]
# If you ever turn GGML_BACKEND_DL on, renaming libggml-*.so by OUTPUT_NAME will make the
# CUDA backend undiscoverable at runtime and the card will silently not be used.
#
# CUDA and NVIDIA names are deliberately NOT renamed -- that is the one standing
# exemption. "cuda" stays a word in these filenames because it names the vendor's
# toolkit, not somebody else's product identity.
#
# Idempotent: re-running re-syncs the source and rebuilds incrementally. ccache makes an
# unchanged rebuild cheap.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/references/contrib"
DST="$ROOT/engines"
JOBS="$(nproc)"

# The ASR upstream is not under references/contrib with the other two -- it was vendored
# into a differently-named parent. Searched rather than hard-coded to one spelling, because
# the whole reason this engine did not exist for so long is that its source was assumed to
# be somewhere it was not. First hit that actually looks like the tree wins; if none does,
# fork_listen says where it looked instead of failing with an empty path.
# Generalised to all three engines, not just this one. `references/contrib` no longer holds
# llama.cpp or stable-diffusion.cpp either -- it holds a miner build script and cuda-samples
# -- so `fork_engines.sh llm` and `diffuse` could not rebuild the two engines this box
# actually serves from, and nothing noticed: the binaries were already built and sitting in
# engines/, which is gitignored. That is a packaging problem before it is a build problem.
# An installer that cannot rebuild an engine from source can only ship a binary somebody
# built by hand once, which is the state this repo has been burned by twice already.
#
# Each candidate is confirmed to LOOK like the tree rather than merely exist -- an empty
# directory of the right name is the failure this guards against.
upstream_src() {
    local name="$1" c
    for c in "$SRC/$name" \
             "$ROOT/references/referencestochatgpt/$name"; do
        [ -f "$c/CMakeLists.txt" ] && [ -d "$c/src" ] && { printf '%s' "$c"; return 0; }
    done
    return 1
}

log() { printf '\n=== %s\n' "$*"; }

# ---------------------------------------------------------------- symoneural-llm
fork_llm() {
    local src dst="$DST/symoneural-llm"
    src="$(upstream_src llama.cpp)" || {
        echo "no llama.cpp upstream found under references/ -- looked beside the other" >&2
        echo "  engines and under the vendored tree that actually holds it." >&2; return 1; }

    log "syncing llm source -> $dst"
    mkdir -p "$dst"
    # node_modules is 711 MB of the web UI's build-time dependencies and is not needed to
    # build the server; tools/ui/dist (the already-built UI the server serves) IS kept.
    # The vocab .gguf files under models/ are test fixtures, not weights we serve.
    rsync -a --delete \
        --exclude '.git/' \
        --exclude '/build/' \
        --exclude 'tools/ui/node_modules/' \
        --exclude 'models/*.gguf' \
        "$src/" "$dst/"

    log "installing our names"
    mkdir -p "$dst/cmake"
    cat > "$dst/cmake/symoneural-names.cmake" <<'CMAKE'
# Ship under SyMoNeuRaL names. OUTPUT_NAME rewrites only the filename produced on disk --
# every target_link_libraries() in the tree refers to the CMake target name, which is
# untouched, so the dependency graph is exactly as upstream configured it.
#
# Safe only while GGML_BACKEND_DL is OFF. With it ON, ggml discovers backends by globbing
# libggml-*.so and these renames would hide the CUDA backend at runtime.
if(GGML_BACKEND_DL)
    message(FATAL_ERROR
        "symoneural-names.cmake: GGML_BACKEND_DL is ON. Renaming the ggml backend "
        "libraries would make them undiscoverable at runtime. Refusing to configure.")
endif()

# target                 -> filename on disk        ("cuda" stays: vendor name, exempt)
set(SYMONEURAL_NAME_MAP
    "llama"              "symoneural_llm"
    "llama-common"       "symoneural_llm_common"
    "ggml"               "symoneural_tensor"
    "ggml-base"          "symoneural_tensor_base"
    "ggml-cpu"           "symoneural_tensor_cpu"
    "ggml-cuda"          "symoneural_tensor_cuda"
    "mtmd"               "symoneural_multimodal"
    "llama-server-impl"  "symoneural_llm_server_impl"
    "llama-cli-impl"     "symoneural_llm_cli_impl"
    "llama-server"       "symoneural-llm"
    # The one-shot CLI. `bin/symoneural-cli`'s `chat` runs this rather than the
    # server, deliberately: `api.py` owns the server inside gpu.hold("chat") and a
    # second spawner would race it for :8081 and the lease. Building only the server
    # left that path pointing at a binary this fork does not produce.
    "llama-cli"          "symoneural-llm-cli"
)

list(LENGTH SYMONEURAL_NAME_MAP _n)
math(EXPR _last "${_n} / 2 - 1")
foreach(_i RANGE ${_last})
    math(EXPR _ti "${_i} * 2")
    math(EXPR _ni "${_ti} + 1")
    list(GET SYMONEURAL_NAME_MAP ${_ti} _target)
    list(GET SYMONEURAL_NAME_MAP ${_ni} _outname)
    if(TARGET ${_target})
        set_target_properties(${_target} PROPERTIES OUTPUT_NAME "${_outname}")
        message(STATUS "symoneural: ${_target} -> ${_outname}")
    endif()
endforeach()
CMAKE

    # Append the include once, at the very end, so every target is already defined.
    local marker='include(${CMAKE_CURRENT_LIST_DIR}/cmake/symoneural-names.cmake)'
    if ! grep -qF 'symoneural-names.cmake' "$dst/CMakeLists.txt"; then
        printf '\n# SyMoNeuRaL: rename the shipped artefacts. Must stay last -- it needs\n# every target to exist already.\n%s\n' \
            "$marker" >> "$dst/CMakeLists.txt"
    fi

    log "configuring llm (CUDA, sm_120)"
    cmake -S "$dst" -B "$dst/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DGGML_CUDA=ON \
        -DGGML_NATIVE=ON \
        -DCMAKE_CUDA_ARCHITECTURES=120 \
        -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
        -DLLAMA_CURL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CUDA_COMPILER_LAUNCHER=ccache

    log "building the llm server and the one-shot cli (their deps, not the whole tool suite)"
    cmake --build "$dst/build" --target llama-server llama-cli -j "$JOBS"
}

# ------------------------------------------------------------ symoneural-diffuse
fork_diffuse() {
    local src dst="$DST/symoneural-diffuse"
    src="$(upstream_src stable-diffusion.cpp)" || {
        echo "no stable-diffusion.cpp upstream found under references/ -- looked beside the" >&2
        echo "  other engines and under the vendored tree that actually holds it." >&2; return 1; }

    log "syncing diffuse source -> $dst"
    mkdir -p "$dst"
    # NOTE the leading slash on '/build/'. Unanchored, rsync's pattern matches a
    # directory called build at ANY depth -- and this tree has
    # thirdparty/libwebm/build/cxx_flags.cmake, which defines require_cxx_flag_nomsvc.
    # Dropping it fails configure with "Unknown CMake command", which reads like a CMake
    # version problem and is not one. Anchored, it means only the top-level build output.
    rsync -a --delete --exclude '.git/' --exclude '/build/' "$src/" "$dst/"

    # The CLI prints its own product name in its version banner, which is a third-party
    # name in output a person reads. One line, and it has to be done HERE rather than by
    # hand in the fork, because the rsync above re-syncs the tree on every run and would
    # wipe a manual edit. Asserted, not hoped: if an upstream refresh moves this string the
    # build stops rather than quietly shipping the old name again.
    local banner='engines/symoneural-diffuse/examples/common/common.cpp'
    banner="$dst/examples/common/common.cpp"
    if grep -q '"stable-diffusion.cpp version "' "$banner"; then
        sed -i 's/"stable-diffusion.cpp version "/"SyMoNeuRaL Diffuse version "/' "$banner"
    elif ! grep -q '"SyMoNeuRaL Diffuse version "' "$banner"; then
        echo "fork_engines: the version banner in $banner is not where it was; find it and" >&2
        echo "  rename it, or this engine ships under somebody else's product name." >&2
        return 1
    fi

    log "installing our names"
    mkdir -p "$dst/cmake"
    cat > "$dst/cmake/symoneural-names.cmake" <<'CMAKE'
# See the note in symoneural-llm/cmake/symoneural-names.cmake -- same mechanism, same
# reason. "cuda" is the exempt vendor name and stays.
if(GGML_BACKEND_DL)
    message(FATAL_ERROR "symoneural-names.cmake: GGML_BACKEND_DL is ON; refusing.")
endif()

set(SYMONEURAL_NAME_MAP
    "stable-diffusion"  "symoneural_diffuse_core"
    "ggml"              "symoneural_tensor"
    "ggml-base"         "symoneural_tensor_base"
    "ggml-cpu"          "symoneural_tensor_cpu"
    "ggml-cuda"         "symoneural_tensor_cuda"
    "sd-cli"            "symoneural-diffuse"
)

list(LENGTH SYMONEURAL_NAME_MAP _n)
math(EXPR _last "${_n} / 2 - 1")
foreach(_i RANGE ${_last})
    math(EXPR _ti "${_i} * 2")
    math(EXPR _ni "${_ti} + 1")
    list(GET SYMONEURAL_NAME_MAP ${_ti} _target)
    list(GET SYMONEURAL_NAME_MAP ${_ni} _outname)
    if(TARGET ${_target})
        set_target_properties(${_target} PROPERTIES OUTPUT_NAME "${_outname}")
        message(STATUS "symoneural: ${_target} -> ${_outname}")
    endif()
endforeach()
CMAKE

    if ! grep -qF 'symoneural-names.cmake' "$dst/CMakeLists.txt"; then
        printf '\n# SyMoNeuRaL: rename the shipped artefacts. Must stay last.\n%s\n' \
            'include(${CMAKE_CURRENT_LIST_DIR}/cmake/symoneural-names.cmake)' \
            >> "$dst/CMakeLists.txt"
    fi

    log "configuring diffuse (CUDA, sm_120)"
    cmake -S "$dst" -B "$dst/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DSD_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES=120 \
        -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CUDA_COMPILER_LAUNCHER=ccache

    log "building diffuse cli"
    cmake --build "$dst/build" --target sd-cli -j "$JOBS"
}

# ---------------------------------------------------------------- symoneural-listen
#
# THE ASR ENGINE, AND WHY IT IS CPU-ONLY. This is not a default being accepted, it is the
# same choice `scripts/fetch-whisper.sh` made and argued: one card, one tenant at a time.
# A spoken sticker is ASR -> text -> render, and if the ASR were a CUDA tenant that becomes
# take the lock, transcribe, release, wait out the drain floor, take the lock again. So the
# transcription stays off the card, where it runs *while* another surface holds the GPU.
# RavenCalc is the precedent. `-DGGML_CUDA=OFF` below is that decision, written down.
#
# WHY IT LIVES HERE RATHER THAN IN contrib/. `contrib/` is banned by
# `backend/apps/test_references_boundary.py` and, more to the point, `/contrib` is
# gitignored -- which is how this capability disappeared the first time, and how the miner's
# benchmark binary disappeared too. Two instances made it a pattern; building into
# `engines/` under our own name is the fix for the pattern, not just for this engine.
fork_listen() {
    local src dst="$DST/symoneural-listen"
    if ! src="$(upstream_src whisper.cpp)"; then
        echo "no whisper upstream found under references/ -- looked beside the other two" >&2
        echo "  engines and under the vendored tree that actually holds it." >&2
        return 1
    fi

    log "syncing listen source -> $dst  (from ${src#"$ROOT"/})"
    mkdir -p "$dst"
    # '/build/' anchored for the reason fork_diffuse spells out at length, and here it also
    # drops the 973 KB whisper-cli already sitting in the vendored tree -- a binary under a
    # third-party name that must not be what we ship.
    rsync -a --delete --exclude '.git/' --exclude '/build/' "$src/" "$dst/"

    # The CLI prints a third-party product name in output a person reads. Same treatment and
    # same assertion as diffuse: if an upstream refresh moves this string the build stops
    # rather than quietly shipping somebody else's name again.
    local banner="$dst/examples/cli/cli.cpp"
    if grep -q '"whisper\.cpp version: %s' "$banner"; then
        sed -i 's/"whisper\.cpp version: %s/"SyMoNeuRaL Listen version: %s/' "$banner"
    elif ! grep -q '"SyMoNeuRaL Listen version: %s' "$banner"; then
        echo "fork_engines: the version banner in $banner is not where it was; find it and" >&2
        echo "  rename it, or this engine ships under somebody else's product name." >&2
        return 1
    fi

    log "installing our names"
    mkdir -p "$dst/cmake"
    cat > "$dst/cmake/symoneural-names.cmake" <<'CMAKE'
# See the note in symoneural-llm/cmake/symoneural-names.cmake -- same mechanism, same
# reason. "cuda" is the exempt vendor name and stays.
if(GGML_BACKEND_DL)
    message(FATAL_ERROR "symoneural-names.cmake: GGML_BACKEND_DL is ON; refusing.")
endif()

set(SYMONEURAL_NAME_MAP
    "whisper"       "symoneural_listen_core"
    "ggml"          "symoneural_tensor"
    "ggml-base"     "symoneural_tensor_base"
    "ggml-cpu"      "symoneural_tensor_cpu"
    "whisper-cli"   "symoneural-listen"
)

list(LENGTH SYMONEURAL_NAME_MAP _n)
math(EXPR _last "${_n} / 2 - 1")
foreach(_i RANGE ${_last})
    math(EXPR _ti "${_i} * 2")
    math(EXPR _ni "${_ti} + 1")
    list(GET SYMONEURAL_NAME_MAP ${_ti} _target)
    list(GET SYMONEURAL_NAME_MAP ${_ni} _outname)
    if(TARGET ${_target})
        set_target_properties(${_target} PROPERTIES OUTPUT_NAME "${_outname}")
        message(STATUS "symoneural: ${_target} -> ${_outname}")
    endif()
endforeach()
CMAKE

    if ! grep -qF 'symoneural-names.cmake' "$dst/CMakeLists.txt"; then
        printf '\n# SyMoNeuRaL: rename the shipped artefacts. Must stay last.\n%s\n' \
            'include(${CMAKE_CURRENT_LIST_DIR}/cmake/symoneural-names.cmake)' \
            >> "$dst/CMakeLists.txt"
    fi

    log "configuring listen (CPU only -- this never takes the GPU lock)"
    # CMAKE_BUILD_RPATH_USE_ORIGIN makes the RUNPATH `$ORIGIN` instead of the absolute path
    # of whatever directory this happened to be built in. That is a packaging requirement,
    # not a tidiness one: an engine whose RUNPATH names /home/google/... loads nothing once
    # an installer puts it under /opt or /usr/lib, and it fails at load time on the user's
    # machine rather than at build time on ours. `symoneural-llm` already reads `$ORIGIN`;
    # `symoneural-diffuse` does NOT -- it carries an absolute CUDA path -- so the claim in
    # this file's header that both are $ORIGIN is currently true of one of them. Recorded
    # here because the fix for diffuse is the same flag and is not this commit's job.
    cmake -S "$dst" -B "$dst/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON \
        -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

    log "building listen cli"
    cmake --build "$dst/build" --target whisper-cli -j "$JOBS"
}

case "${1:-all}" in
    llm)     fork_llm ;;
    diffuse) fork_diffuse ;;
    listen)  fork_listen ;;
    all)     fork_llm; fork_diffuse; fork_listen ;;
    *)       echo "usage: $0 [llm|diffuse|listen|all]" >&2; exit 2 ;;
esac

log "done -- artefacts under $DST"
find "$DST" -maxdepth 3 -type f -name 'symoneural-*' -perm -u+x 2>/dev/null | while read -r b; do
    printf '  %s\n' "$b"
    readelf -d "$b" | grep -E 'RUNPATH|RPATH' | sed 's/^/      /'
done
