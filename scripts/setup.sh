#!/usr/bin/env bash
# Set up a fresh clone of this repo, wherever it lives.
#
#   git clone <repo> symoneural && cd symoneural && ./scripts/setup.sh
#
# Nothing in this repo hardcodes its own location any more: every script derives its root
# from its own path, api.py from __file__, the engine binaries from $ORIGIN, and the systemd
# unit is a template the installer fills in. This script checks that the machine can actually
# run it and tells you exactly what is missing.
#
# It deliberately does NOT use sudo. The three steps that need root are printed at the end
# for you to run yourself, so nothing here can quietly change the system.
set -uo pipefail

# Repo root is one level up now that this lives in scripts/. This calculation has
# been wrong three times in this repo (the demo/ flatten, the tools/ move, here) and
# it fails silently, because the wrong parent is usually a directory that exists.
# The guard below turns that into an immediate, obvious failure.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$ROOT/api.py" ] || { echo "repo root not found at $ROOT" >&2; exit 1; }
cd "$ROOT"

ok=0; warn=0; fail=0
say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
pass() { printf '  \033[32mok\033[0m    %s\n' "$*"; ok=$((ok+1)); }
note() { printf '  \033[33mnote\033[0m  %s\n' "$*"; warn=$((warn+1)); }
bad()  { printf '  \033[31mmiss\033[0m  %s\n' "$*"; fail=$((fail+1)); }

say "Repo"
pass "root is $ROOT"
[ -d .git ] && pass "git repository ($(git rev-list --count HEAD 2>/dev/null) commits)" \
            || note "not a git checkout"

say "Host tools"
for c in python3 curl; do
  command -v "$c" >/dev/null && pass "$c ($($c --version 2>&1 | head -1 | cut -c1-40))" || bad "$c is required"
done
command -v ffmpeg  >/dev/null && pass "ffmpeg  (needed by the planned IPTV surface)" || note "ffmpeg not installed"
command -v node    >/dev/null && pass "node    $(node --version) (browser tests)"     || note "node not installed — tests/frontend.mjs will not run"
command -v podman  >/dev/null && pass "podman  $(podman --version | awk '{print $3}')" || note "podman not installed — container path unavailable"
command -v caddy   >/dev/null && pass "caddy   $(caddy version 2>/dev/null | awk '{print $1}')" || note "caddy not installed — see scripts/install-caddy.sh"

say "GPU"
if command -v nvidia-smi >/dev/null; then
  pass "driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1) · $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
  [ -f /etc/cdi/nvidia.yaml ] && pass "CDI spec present (containers can use the GPU)" \
                             || note "no /etc/cdi/nvidia.yaml — run: sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml"
else
  bad "nvidia-smi not found — the GPU surfaces cannot run"
fi

say "Serving dependencies (system interpreter, no virtualenv by design)"
for m in fastapi uvicorn pydantic sympy; do
  python3 -c "import $m" 2>/dev/null && pass "python3 -m $m" || bad "python3 module '$m' missing (Debian: python3-$m)"
done

say "Engines"
for e in contrib/llama.cpp/build/bin/llama-server contrib/stable-diffusion.cpp/build/bin/sd-cli; do
  if [ -x "$e" ]; then
    if ldd "$e" 2>/dev/null | grep -q 'not found'; then
      bad "$e is present but has unresolved libraries: $(ldd "$e" | grep 'not found' | head -1 | xargs)"
    else
      pass "$e"
    fi
  else
    bad "$e not built — clone and build it, or copy the build tree in"
  fi
done

say "Weights"
missing_w=0
for w in models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf models/image/flux1-schnell-q4_k.gguf; do
  [ -s "$w" ] && pass "$(basename "$w")" || { note "$(basename "$w") missing"; missing_w=1; }
done
[ "$missing_w" = "1" ] && note "run ./scripts/fetch-models.sh to download weights and their licences"
[ -d models/licenses ] && pass "model licences present (required for any customer build)" \
                       || note "models/licenses missing — ./scripts/fetch-models.sh fetches them"

say "Adapter"
[ -s training/adapter/symoneural-lora.gguf ] \
  && pass "persona adapter present" \
  || note "no adapter — chat runs on the stock base model until one is trained"

say "Result"
printf "  %d ok, %d notes, %d missing\n" "$ok" "$warn" "$fail"

cat <<EOF

Next, and these are the only steps that need root:

  sudo ./scripts/install-service.sh    run the API under systemd (the unit is a template;
                                   the installer writes this repo's path into it)
  sudo ./scripts/install-caddy.sh      TLS + static serving, proxying /api to the API
  sudo ./scripts/deploy.sh                 publish site/ to /var/www/symoneural

Without root you can still run everything locally:

  ./scripts/symoneural.sh on               start the API on 127.0.0.1:8800
  ./scripts/container-run.sh --detach  or run it in a rootless container with the GPU
  node tests/frontend.mjs          drive the real pages in a real browser
EOF

[ "$fail" -gt 0 ] && exit 1 || exit 0
