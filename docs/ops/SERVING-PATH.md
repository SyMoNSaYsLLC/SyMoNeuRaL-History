# Serving path audit — `/yocto` out, `/home/google/Symoneural` canonical

**Audited 2026-08-26, 09:15–09:25 EDT. Nothing was changed. No service was restarted.**

Garrett, 2026-08-26, setting the boundary: *"`/home/google/Symoneural` is the sole canonical
source, runtime, deployment, engine, and model location for the live Debian machine"*, and
*"Nothing under `/yocto` may remain in any live service working directory, executable path,
Python import path, model path, environment setting, Caddy target, symlink, hardlink, or bind
mount."* `/yocto` may be a temporary build workspace and a **read-only** source for an
existing model artifact; anything retained becomes an independent regular file under
`/home/google/Symoneural`.

Also standing: **`/home/google/yocto` was permanently deleted.** Do not recreate or reference
it. The top-level `/yocto` mount is a different thing and is the one discussed below.

Classified with the Repo Update Audit System (`docs/ops/REPOSITORY-PURPOSE.md`): **PROD** =
proven working on this box, **AUDIT** = unverified or scaffold, **REMOVED** = wrong, dead, or
contradicted by the box.

---

## 1. Live systemd services — what they actually use

| unit | WorkingDirectory | ExecStart | EnvironmentFile | verdict |
|---|---|---|---|---|
| `symoneural-api.service` | `/yocto/Symoneural` | `/usr/bin/python3 /yocto/Symoneural/backend/api.py` | `-/etc/symoneural/api.env` | **REMOVED** — must move |
| `symoneural-gateway.service` | `/yocto/Symoneural` | `/yocto/Symoneural/backend/apps/gateway/target/release/symon-gateway` | (none) | **REMOVED** — must move |
| `symoneural-deploy.service` | `/yocto/Symoneural` | `bash /yocto/Symoneural/scripts/deploy.sh --prune` | `-/etc/symoneural/deploy.env` | **REMOVED** — must move |
| `caddy.service` | (none) | `/usr/bin/caddy run --config /etc/caddy/Caddyfile` | — | **PROD** — no `/yocto` anywhere |

Fragment paths: `/etc/systemd/system/symoneural-{api,gateway,deploy}.service`, plus one
drop-in `/etc/systemd/system/symoneural-api.service.d/10-surfaces.conf` (EnvironmentFile only,
no path). `symoneural-api` runs as `google`, `Environment=PYTHONUNBUFFERED=1
SYMONEURAL_PORT=8800`.

**`symoneural-deploy.service` is ENABLED**, so it republishes `site/` from its
WorkingDirectory at every boot. Until it moves, a reboot reverts anything deployed from the
canonical checkout — including the #107 maintenance banner.

## 2. Every live reference to `/yocto`

| where | finding | verdict |
|---|---|---|
| API process (pid 3869716) | `cwd=/yocto/Symoneural`, argv `/yocto/Symoneural/backend/api.py`, **6 open fds** under `/yocto`, **1 mapped file** under `/yocto` | **REMOVED** |
| Gateway process (pid 1868) | `cwd=/yocto/Symoneural`, **exe itself** is `/yocto/Symoneural/backend/apps/gateway/target/release/symon-gateway` | **REMOVED** |
| systemd units | 3 files reference `/yocto` (api, gateway, deploy) | **REMOVED** |
| `/etc/caddy/Caddyfile` | **zero** `/yocto` references; `root * /var/www/symoneural` | **PROD** |
| `/etc/symoneural/api.env` | **zero** `/yocto` references | **PROD** |
| bitbake (pids 22388/22429) | `cwd=/yocto/build-symoneural` — the **build workspace**, not a live service | **AUDIT** — allowed use |

Non-live: 15 tracked files in the canonical repo mention `/yocto` in prose, plus the
`yocto/` layer directory. Those are documentation and build-layer sources, not runtime
references. Not a blocker; listed so nobody mistakes a grep hit for a live path.

## 3. Host baseline — verified, and it differs from the expectation

| item | expected | **measured** | verdict |
|---|---|---|---|
| Architecture | AMD64 | `x86_64`, dpkg `amd64` | **PROD** |
| OS | Debian 13 | **Debian 13.6 (trixie)**, kernel `6.12.105+deb13-amd64` | **PROD** |
| Python ABI | — | `3.13.5`, SOABI `cpython-313-x86_64-linux-gnu`, multiarch `x86_64-linux-gnu` | **PROD** |
| GPU | RTX 5070 Ti | **NVIDIA GeForce RTX 5070 Ti**, compute cap **12.0**, 16303 MiB | **PROD** |
| NVIDIA driver | 590.48.01 | **610.57.04** (`nvidia-driver`, `nvidia-kernel-open-dkms` 610.57.04-1) | **corrected** |
| CUDA toolkit | 13.1 | **13.3** (`nvcc` V13.3.73, `/usr/local/cuda -> cuda-13.3`) | **corrected** |

The two corrections are **not blockers**: the engine links `libcudart.so.13` / `libcublas.so.13`
and targets `sm_120a`, which is exactly compute capability 12.0. Recorded because the
instruction was to verify rather than assume, and a doc that repeats the wrong driver version
is how the wrong one gets installed later.

## 4. The native inference engine — already correct for this host

**Path discrepancy, and it needs a ruling.** The instruction names
`/home/google/Symoneural/backend/engines/symoneural-llm/build/bin/symoneural-llm`. That path
**does not exist**. `backend/api.py:183` computes `LLM_ENGINE = ROOT / "engines" / ...` where
`ROOT` is the repo root, so the real path is
`/home/google/Symoneural/engines/symoneural-llm/build/bin/symoneural-llm` — no `backend/`.
The engine is there. Moving it to match the expected string would break `api.py` unless that
line changes too, so nothing has been moved.

Measured at `/home/google/Symoneural/engines/symoneural-llm/build/bin/symoneural-llm`:

| property | value | verdict |
|---|---|---|
| `file` | ELF 64-bit LSB **pie executable, x86-64**, dynamically linked, GNU/Linux 3.2.0, not stripped | **PROD** |
| size / sha256 | 17,952 bytes / `0c4f804a5b18f754…3fe4c1` | **PROD** |
| `ldd` | **every dependency resolves; no "not found"** | **PROD** |
| CUDA linkage | `libcudart.so.13`, `libcublas.so.13`, `libcublasLt.so.13` (from `/usr/local/cuda/lib64`), `libcuda.so.1` | **PROD** |
| CUDA backend | `libsymoneural_tensor_cuda.so.0` present and linked | **PROD** |
| `cuobjdump` targets | **`sm_120a`** — native SASS for GB203 / compute 12.0 | **PROD** |
| `CMAKE_CUDA_ARCHITECTURES` | **120** | **PROD** |
| build type / compilers | `Release`; `/usr/local/cuda/bin/nvcc`, `/usr/bin/c++` | **PROD** |
| `GGML_CUDA` | `ON` (FA on, graphs on, NCCL on) | **PROD** |
| `/yocto` contamination | **0 references** in `CMakeCache.txt`; none in the binaries | **PROD** |

**Conclusion: this is a native Debian AMD64 build matched to this GPU. No rebuild is
required, and no Yocto cross-compiled binary is involved.**

Layer separation, as instructed: `guide_ask_model` is a Python adapter, the GGUF is weight
data, and this engine is the compiled component. Only the third had to be proven for this host
and GPU, and it is.

## 5. Disk, and the model file

    /home   885G total, 380G available     <- canonical
    /yocto  492G total, 129G available     <- build workspace only

`/home/google/Symoneural/backend/models/` is **145 GB** and already the larger tree.
`/yocto/Symoneural/backend/models/` is an **empty directory tree, 0 bytes** — which is exactly
why the chat surface answers "Chat surface is not available" and every GPU row on the rack
reads `offline`.

The chat model was copied in from the staged tree as a read-only source. **The `/yocto` copy
was not moved, modified or deleted.**

| property | value |
|---|---|
| path | `/home/google/Symoneural/backend/models/llm/symon-1.0-7b-q4_k_m.gguf` |
| size | **4,683,074,240 bytes** |
| sha256 | `65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423` |
| source sha256 | **identical** (`/yocto/sendtodrive/models/llm/…`, unmodified) |
| type | regular file, **links = 1**, mode `-rw-rw-r--` |
| symlink? | **no** |
| inode / device | `18364700` on dev `66308` vs source `18350088` on dev `66306` — **different inode, different filesystem: independent file, hardlink impossible** |
| format | **GGUF v3**, 339 tensors, 38 kv pairs |
| identity | `general.architecture=qwen2`, `general.name=Qwen2.5 7B Instruct`, `size_label=7B`, `file_type=15` (Q4_K_M), 28 blocks, ctx 32768, apache-2.0 |

**Not a rename.** The filename claims 7B/Q4_K_M and the header independently says 7B and
file_type 15. The file already carried this name in the source tree.

## 6. Canonical checkout completeness

Every path the service needs is present under `/home/google/Symoneural`:

    backend/api.py                                  present
    site/index.html                                 present
    engines/symoneural-llm/build/bin/symoneural-llm present   (note the path, §4)
    backend/models/llm/symon-1.0-7b-q4_k_m.gguf     present
    scripts/deploy.sh                               present
    ops/Caddyfile                                   present
    scripts/gpu-governor.sh                         present

The gateway binary already exists under the canonical tree and is **byte-identical** to the
live one: 27,232,992 bytes, sha256 `41b9eda87550c6b2…` both sides. No rebuild needed to move
that service.

---

## Blockers and rulings needed before anything restarts

1. **Engine path.** `backend/engines/…` (as instructed) vs `engines/…` (as `api.py:183`
   computes and where the binary is). Move the tree and change `api.py`, or keep the current
   path? Nothing moved pending this.
2. **Three units to rewrite**, each backed up first: `symoneural-api`, `symoneural-gateway`,
   `symoneural-deploy`. The deploy unit matters most — it is enabled and republishes `site/`
   at every boot from wherever it points.
3. **Restarting the API takes the live site down for a few seconds** and is the step that
   proves or disproves the canonical checkout. It has not been done.

## What is still unproven, and must not be claimed

`POST /api/dispatchos/ask` has **never returned `model: true`**. Every observed answer took the
deterministic fallback with `model: false`, because `CHAT_MODEL` is absent from the checkout
that currently serves. The engine and the weights are now both correct **on the canonical
side**, but no round trip has run there. Per `backend/apps/dispatchos/SMOKE.md`: do not claim
the model path works until a run records `model: true`.
