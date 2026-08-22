# Box reality audit — what works on this box vs generic scaffold

**Report only. Nothing was changed, moved, downloaded, deployed or migrated to produce it.**

Measured 2026-08-22 at `a191dba7` on this box. Requested before folder migration, to separate
actual working SyMoNeuRaL box-specific code from generic scaffold assumptions.

## The governing rule

Garrett, 2026-08-22:

> **Docs can describe future generic architecture. Implementation must match Garrett's actual
> box.**

Every classification below is that rule applied. A generic assumption in a *doc* is allowed if
labelled; the same assumption in *code* is a defect, because code runs here or nowhere.

## Classification vocabulary

| | Means |
|---|---|
| **PROD** | Proven working on this box, evidence cited |
| **AUDIT** | Generic, scaffold, or unverified — needs a decision before it is relied on |
| **REMOVED** | Wrong, dead, or contradicted by the actual box — do not assume |

## How this was measured

`tools`-style audit script over `git ls-files`, excluding `docs/archive/`, `references/`,
`review/` and `__pycache__`. That scope matters: **`engines/` is gitignored, so the vendored
ComfyUI fork is excluded automatically** and every finding below is about code this project
owns. Python string literals were tokenized so comments and docstrings do not count as code
references — a distinction that removed ~120 false positives on the first pass.

Counts: 1934 tracked `.py`/`.sh`/`.mjs`/`.js` files scanned; 149 route declarations; 84 raw
path hits triaged down to the 6 real ones in §3.

---

## 1. Models and the image backend

### 1.1 PROD — the current image baseline

`backend/models/image/`, 12.67 GB, four files. These are the only FLUX-lineage entries in
`backend/models/PROVENANCE.json` (`weights[6]`–`weights[9]`):

| File | Size | Upstream | Role |
|---|---|---|---|
| `symoneural-image-unet-q4_k.gguf` | 6.88 GB | `leejet/FLUX.1-schnell-gguf` ← `flux1-schnell-q4_k.gguf` | UNet |
| `symoneural-image-t5-q8_0.gguf` | 5.20 GB | `second-state/FLUX.1-schnell-GGUF` | T5-XXL text encoder |
| `symoneural-image-clip.safetensors` | 0.25 GB | `second-state/FLUX.1-schnell-GGUF` | CLIP-L text encoder |
| `symoneural-image-vae.safetensors` | 0.34 GB | `second-state/FLUX.1-schnell-GGUF` | autoencoder |

All four carry `license_text = licenses/FLUX.1-schnell.MODEL-CARD.md`.

**`backend/apps/studio/workflows.py` matches the disk exactly.** Its four constants resolve to
four present files, and there is **no file in `backend/models/image/` that `workflows.py` does
not reference**:

```
PRESENT  UNET    symoneural-image-unet-q4_k.gguf
PRESENT  T5      symoneural-image-t5-q8_0.gguf
PRESENT  CLIP_L  symoneural-image-clip.safetensors
PRESENT  VAE     symoneural-image-vae.safetensors
unreferenced files in image/: none
```

`backend/models/*` is gitignored at `.gitignore:5`, so **no weight can be committed by
accident.** Verified.

### 1.2 What the code expects — FLUX, not SDXL or Comfy checkpoints

The image path expects the **FLUX/Schnell GGUF family** and says so in code, not in a comment
that could drift:

- `UnetLoaderGGUF`, `DualCLIPLoaderGGUF` (`type: "flux"`), `VAELoader` — GGUF loaders from
  `custom_nodes/ComfyUI-GGUF`, because stock ComfyUI cannot read GGUF.
- `EmptySD3LatentImage`, **not** `EmptyLatentImage` — FLUX's latent space is 16-channel and
  `EmptyLatentImage` emits 4 (`workflows.py:38`, asserted at `test_studio.py:311`).
- `FluxGuidance` — guidance as embedded conditioning, `cfg` fixed at 1.0, `steps: 4`.

**No hardcoded SDXL assumption exists in our shipped image path.** Ten `sdxl`/checkpoint hits
were triaged and all ten are legitimate:

| Site | Verdict |
|---|---|
| `studio/custom_nodes/symoneural_gguf/__init__.py:20,21,140` | **PROD.** A deliberately *gated* SDXL shape workaround (`arch_str == "sdxl"`) that must **not** run for FLUX — the gate is the point. |
| `studio/custom_nodes/symoneural_gguf/__init__.py:263` | **PROD.** `type="stable_diffusion"` is upstream ComfyUI's CLIP-loader enum default, not a claim about this box. |
| `studio/workflows.py:26` | **PROD.** Explains *why* `CheckpointLoaderSimple` is not used. |
| `studio/workflows.py:38`, `studio/test_studio.py:311` | **PROD.** Both name `EmptyLatentImage` in order to reject it. |
| `sigils/test_sigils.py:356`, `test_references_boundary.py:70`, `fork_engines.sh:173` | **PROD.** Ban-lists and rebrand maps; the string is the thing being excluded. |

### 1.3 AUDIT — non-baseline weights in the curated directory

`backend/models/` is a **ComfyUI-shaped tree** (`put_*_here` placeholders are ComfyUI's own
convention) holding far more than the baseline. Eighteen category directories hold nothing but
a `put_*_here` placeholder; these are not:

| Directory | Weights | Size | Referenced by our code |
|---|---|---|---|
| `hf/` | 21 | 70.79 GB | Qwen HF snapshots — yes, by the LLM path |
| `llm/` | 6 | 39.64 GB | yes — `symon-1.0-*.gguf`, PROD |
| `diffusion_models/` | 3 | 34.02 GB | **no — zero files** |
| `text_encoders/` | 4 | 29.47 GB | **no — zero files** |
| `image/` | 4 | 12.67 GB | yes — PROD baseline |
| `checkpoints/` | 1 | 9.22 GB | **no — zero files** |
| `vae/` | 5 | 7.06 GB | one duplicate, see below |
| `loras/` | 1 | 1.96 GB | **no — zero files** |
| `clip_vision/` | 1 | 1.68 GB | **no — zero files** |
| `background_removal/` | 1 | 0.44 GB | yes (`birefnet`) |
| `rembg/`, `whisper/` | 2 | 0.33 GB | yes — PROD |

**Six large models are referenced by exactly zero files of our code** (`git grep`, excluding
`references/`): `z_image_turbo_bf16` (12.31 GB), `minimax_h3_fl2va_pruned_int8_convrot`
(20.97 GB), `triposplat_fp16`, `stable_audio_3_medium` (9.22 GB), `dino_v3_vit_h`,
`flux2-vae`. That is **~57 GB of weights nothing on this box loads.** They are not defects —
they are unclassified inventory, and until something references them they cannot be called
capability.

**This contradicts `extra_model_paths.yaml`'s own stated policy**, which says new downloads
"belong in `ComfyUI/models/` where they are gitignored and disposable" and that
`backend/models/image/` is "a curated directory that the rest of the stack reads". `ComfyUI/`
does not exist (§3.1), so downloads landed in the curated tree instead. The policy needs
restating against a directory that exists.

### 1.4 AUDIT — a byte-identical duplicate VAE

```
5c8c2087d13d0951b36be6dfbd3cd157  backend/models/vae/ae.safetensors
5c8c2087d13d0951b36be6dfbd3cd157  backend/models/image/symoneural-image-vae.safetensors
```

Same md5, same 335,304,388 bytes, two names, two directories. `ae.safetensors` is the upstream
name; the branded copy is what `workflows.py` loads. This is precisely the *"which copy is
current"* failure `extra_model_paths.yaml` was written to prevent, now present on disk. 335 MB,
and the risk is not the disk — it is that a future loader picks the unbranded one and nothing
notices.

### 1.5 AUDIT — SD-era config scaffold

`backend/models/configs/` holds eleven Stable Diffusion v1/v2 inference YAMLs
(`v1-inference.yaml`, `v2-inpainting-inference.yaml`, `anything_v3.yaml`, …). Vendored ComfyUI
scaffold for a family this box does not run. Harmless, unreferenced, and **not** evidence of an
SDXL baseline.

---

## 2. GPU and runtime

### 2.1 PROD — the CUDA/NVIDIA path

```
NVIDIA GeForce RTX 5070 Ti, 16303 MiB, driver 610.57.04
nvcc: Cuda compilation tools, release 13.3, V13.3.73
```

One card, matching the `rtx5070ti-16gb` profile in `docs/ops/HARDWARE-PROFILES.md`.

`scripts/gpu-governor.sh:210` resolves the render surface to
`$ROOT/engines/symoneural-ui/main.py` — the real path, anchored, not a bare process-name match.
The governor's own comment explains why the anchored form is required: *"a bare
`engines/symoneural-ui/main.py` would answer yes to any"* process merely mentioning the name.

### 2.2 PROD — no CPU fallback in any GPU serving path

Eight CPU-device sites exist. **All eight are in `training/`**, none in a serving path:

```
training/probe_27b.py:81,87,128,436     training/train_lora.py:109,115,125,306
```

Every one is a deliberate offload — `safe_open(..., device="cpu")` to stream shards, and
`head.weight.detach().to("cpu").pin_memory()` to keep the LM head off the card during QLoRA.
That is the documented memory strategy, not a fallback, and it never runs for an image job.

**Zero CPU fallback sites in `backend/apps/`.** The `REMOVED` classification for "CPU fallback
for image/GPU workloads" is therefore already true of the code, not an aspiration.

### 2.3 PROD — behaviour when the GPU surface or model files are missing

Honest failure, verified in source. `routes.py:462`: when ComfyUI is unreachable the
route returns **503** with the URL it tried, the exception type, and the fix
(`scripts/symoneural-ui.sh start`) — not a fabricated success and not a silent CPU render.

`backend/apps/test_governor_paths.py` is a live guard on exactly this class of bug: it asserts
the governor never invokes a path that is not on disk, because *"a `||` fallback makes a
missing primary invisible."* Its `RETIRED` tuple lists names the project may not kill by,
including `ComfyUI/main.py`, with the reason recorded — *"the directory that pattern named is
not on disk under any spelling — so the `comfy)` fallback would have matched nothing while
reporting success."*

---

## 3. Paths

### 3.1 REMOVED — `ComfyUI/` does not exist

**The repo-root `ComfyUI/` directory is absent under any spelling.** The render UI is
`engines/symoneural-ui/`, a rebranded fork produced by `tools/fork_render_ui.sh`. The rename is
already recorded at `scripts/lib/archive-guard.sh:94`.

Consequences, and **`ComfyUI/models/checkpoints/` is not a baseline** — it is not a directory:

| Site | Class | Note |
|---|---|---|
| `apps/test_governor_paths.py:46` | **PROD** | `ComfyUI/main.py` is in `RETIRED` — the guard *against* the stale path, not an instance of it |
| `apps/studio/workflows.py:25` | **AUDIT** | Says `ComfyUI/models/checkpoints/` "is empty apart from its placeholder". Doubly stale: the dir does not exist, and its live equivalent `backend/models/checkpoints/` is **not** empty (9.22 GB of `stable_audio_3_medium`). The *conclusion* — don't use `CheckpointLoaderSimple` — remains correct. |
| `apps/studio/comfy.py:7`, `graph.py:24`, `routes.py:320`, `tools_impl/comfy_tool.py:27` | **AUDIT** | Upstream source citations (`ComfyUI/server.py:686` etc.). The claims are checkable only if the reader knows to look in `engines/symoneural-ui/`. Re-point the prefix; do not delete the line numbers, they are the evidence. |
| `tools/fork_render_ui.sh:16,139` | **AUDIT** | Greps for shebangs `#!/home/google/Symoneural/ComfyUI/.venv/bin/`. Correct for re-forking *from* the old layout; can never match today. |

### 3.2 PROD — `backend/models/image` references resolve

Every `backend/models/image` reference in our code resolves to the real directory. No dead
reference to the baseline.

### 3.3 AUDIT — dead paths, triaged

84 raw hits reduced to **6 genuine** ones. The rest are: runtime artefacts absent until first
run (`run/*.pid`, `run/accounts.db`, `*.venv`), deliberately fake test fixtures
(`snapshots/deadbeef`, `7b.gguf`), download **URLs** not local paths
(`scripts/fetch-models.sh`, `news/feeds.py:90`), vendored SDK tests under `backend/vendor/`,
and regex truncation of `$MODELS/...` shell variables. **None of those is a defect** and they
are recorded here so the next audit does not re-report them.

The 6 real ones are the `ComfyUI/` prefixes in §3.1.

---

## 4. Apps and routes

**149 route declarations across 21 files — 141 shipped, 8 declared inside tests. No route is
changed by this report.**

| App | Routes | Class |
|---|---|---|
| `studio` (incl. `plugins/exp`, `plugins/reinforce`) | 46 | **PROD**, with the caveats in §5 |
| `backend/api.py` | 31 | **PROD** — the public surfaces, `/v1`, `/state`, `/local`, `/docs` |
| `project` | 17 | **PROD** |
| `streamer` | 14 | **PROD** |
| `accounts` | 8 | **PROD** — and it refuses to carry a price column |
| `remix` | 8 | **PROD** |
| `live` | 5 | **PROD** |
| `sigils` | 5 | **PROD** |
| `voice` | 3 | **PROD** |
| `controlboard` | 2 | **PROD** |
| `gateway` | 1 | **PROD** |
| `news` | 1 | **PROD** |
| **shipped total** | **141** | across `backend/api.py` and eleven apps |
| `coder/tests/test_coder_surface.py` (2), `test_caddy_delegation.py` (2), `test_deploy_routes.py` (2), `test_studio_models.py` (1), `tests/live-harness.py` (1) | 8 | **AUDIT** — declared inside tests, not shipped surface. Listed so the 149 reconciles. |

`coder` declares no shipped route of its own: its two are inside its own surface test.

### 4.1 REMOVED — there are no stable operation ids anywhere

```
files declaring tags=        : 17
files declaring operation_id :  0
```

**Zero `operation_id` declarations in the entire tracked tree.** Studio's routers are bare
`APIRouter()` twice (`routes.py:63-64`) with neither `tags=` nor `operation_id`. So every
`api_href` / `openapi_operation_id` field in the committed node-system spec currently points at
nothing. This confirms §3.3 of `symoneural-studio-upgrade-scope.md` repo-wide, and it is the
smallest first increment of #103.

### 4.2 AUDIT — `GET /nodes` already exists and means something else

`routes.py:450` already serves `GET /api/studio/nodes`, and it returns **ComfyUI's
`/object_info`, proxied** — ~2 MB of *Comfy's* node catalogue. The planned
`GET /api/studio/nodes` in the spec returns **our** registry.

**Same path, opposite meaning.** This is a name collision that has to be resolved deliberately
— our registry at a different path, or the proxy retired first — and it is exactly the kind of
thing a folder migration would bury.

---

## 5. Studio

**Classification: existing implementation, needs upgrade — not a placeholder.**

`backend/apps/studio/` is 46 routes, 873 lines across `graph.py` (308), `workflows.py` (143)
and `comfy.py` (422), two plugin trees (`exp`, `reinforce`), a real custom-node package
(`custom_nodes/symoneural_gguf`), and two committed smoke records (`SMOKE-bench.md`,
`SMOKE-cleanroom.md`). Calling it scaffold would be wrong.

**Garrett's classification, 2026-08-22, verified against disk and git.** All eight core files
are tracked; 3,418 lines between them.

| Component | Class | Lines | Evidence |
|---|---|---|---|
| `agent.py` | **PROD** | 451 | the tool-calling loop |
| `comfy.py` | **PROD** | 422 | HTTP/WS bridge + GPU lease, documented against upstream source lines |
| `graph.py` | **PROD** | 308 | works, 3 live callers, **no page** — its own docstring says the format "may change", which #103 freezes. PROD as code, unfrozen as a format. |
| `inference.py` | **PROD** | 220 | |
| `routes.py` | **PROD** | 932 | 46 routes — with the two caveats below |
| `registry.py` | **PROD** | 352 | the **tool** registry (MCP schemas from `inspect.signature`) — not the model registry |
| `page.html` / `page.js` | **PROD** | 247 / 486 | |
| `workflows.py` | **PROD** | 143 | matches the disk exactly (§1.1); every node name read from the installed set |
| tests at studio root | **PROD** | 6 files | `test_agent`, `test_cleanroom`, `test_comfy_port`, `test_plugin_contract`, `test_status_probe`, `test_studio` |
| `plugins/*` | **AUDIT** | 112 tracked | `exp` + `reinforce`: real and routed, unclassified against the graph surface. `reinforce/registry.py`'s `plan_fit()` is **LLM-only** (`GGUF_DIR = MODELS_DIR/"llm"`; `arch_from_config` raises for a non-causal-LM), so it does not compute diffusion fit. |
| `custom_nodes/*` | **AUDIT** | 2 tracked | Garrett's call. Noting the evidence rather than arguing it: `symoneural_gguf` supplies the GGUF loaders the FLUX baseline cannot load without, so **AUDIT here means "not yet classified", not "unused"** — retiring it would break §1.1. |
| `.venv/` presence in tree | **AUDIT → local-only** | 0 tracked | See §5.1 |
| `/studio/editor/*` raw-frontend proxy | **AUDIT** | — | Reclassified from REMOVED on Garrett's instruction: **AUDIT unless intentionally retained behind SyMoNeuRaL controls.** What is not in question is the current posture — published by `ops/Caddyfile:150`, gated only by the operator token whose own module calls that *"not a cleared posture"*. Retaining it is a decision that must be made explicitly and written down; leaving it as-is by default is not that decision. |
| `GET /nodes` | **AUDIT** | — | §4.2 collision |

### 5.1 `.venv` — ignored, never tracked. Local-only.

Checked before this report was committed, because a tracked venv is a commit nobody can
review:

```
$ git ls-files backend/apps/studio/.venv          -> 0 files
$ git status --short --ignored backend/apps/studio/.venv
!! backend/apps/studio/.venv/                      -- "!!" = ignored
$ git ls-files | grep -cF '.venv/'                 -> 0   (repo-wide)
```

It exists on disk and is covered by `.gitignore:24` `**/.venv/`. `.gitignore:30`
`**/symoneural-*.venv/` covers the per-app naming convention separately, because `**/.venv/`
matches only the literal name and a directory called `symoneural-discovery.venv` would
otherwise be stageable.

**Verdict: local-only, left alone, not committed.** Nothing to stop and report — the tracked
count is zero repo-wide.

### FLUX/Schnell rules preserved

Binding on any node claiming this family, from `workflows.py:31-35, 71`:

1. **`cfg` is 1.0** — schnell is guidance-distilled.
2. **The negative prompt is inert at cfg 1.0** — no unconditional branch to steer; it is wired
   only to satisfy `KSampler`. A `negative` port here is a control that cannot reach the
   engine.
3. **Raising `cfg` is not a quality improvement** — it destroys the image.
4. **FLUX guidance is embedded conditioning**, via `FluxGuidance`, not classifier-free.
5. **No SDXL baseline unless installed later.** None is installed.

---

## 6. What must be fixed before Studio implementation

In order. None of these is authorized by this report.

1. **Resolve the `GET /api/studio/nodes` collision** (§4.2). Ours vs Comfy's proxy, same path.
   Decide before any node registry is written.
2. **Give Studio's routers `tags=["Studio"]` and stable `operation_id`s** (§4.1). Until this
   exists, every `api_href` in the spec is a dead link. Smallest useful increment.
3. **Freeze `graph.py`'s document format** and version it (§5). Its "may change" caveat is
   what makes it unusable as a save format today.
4. **Remove the raw editor from the public surface before #88 drops the token.** In that order,
   or dropping the token publishes a ComfyUI admin surface.
5. **Classify `plugins/exp` and `plugins/reinforce`** against the graph surface, and decide
   whether the badge engine extends `plan_fit()` to diffusion or gets its own arithmetic.
6. **Restate the download-target policy** in `extra_model_paths.yaml` against a directory that
   exists (§1.3), and classify or relocate the ~57 GB of unreferenced weights.
7. **Resolve the duplicate VAE** (§1.4) — one file, one name, or an explicit note saying which
   is canonical.
8. **Re-point the `ComfyUI/` source citations** to `engines/symoneural-ui/` (§3.1), keeping the
   line numbers.

**`backend/apps/studio/` must be audited component-by-component before implementation or
migration.** This report is the first pass and it classifies seven components; the two plugin
trees remain **AUDIT** and a migration that moves them before they are classified would move
code nobody has decided to keep.

---

## 7. Summary classification

**PROD — proven on this box**

- the four `backend/models/image/` FLUX/Schnell files, with `PROVENANCE.json` lineage
- `workflows.py`, matching the disk exactly
- the studio core, all tracked, 3,418 lines: `agent.py`, `comfy.py`, `graph.py`,
  `inference.py`, `routes.py`, `registry.py`, `page.html`, `page.js`, and the six root tests
- the CUDA path: RTX 5070 Ti / 16303 MiB / driver 610.57.04 / CUDA 13.3
- `gpu-governor.sh`'s anchored `engines/symoneural-ui/main.py`, and `test_governor_paths.py`
- 503-with-a-fix when the render surface is down
- no CPU fallback in any serving path
- 141 shipped routes across `backend/api.py` and eleven apps

**AUDIT — needs a decision**

- `backend/models/{checkpoints,diffusers}` placeholder layout (0 tracked files each)
- ~57 GB of unreferenced weights under `diffusion_models`, `text_encoders`, `checkpoints`,
  `loras`, `clip_vision`
- the duplicate `vae/ae.safetensors`
- the SD-era `configs/` scaffold
- `graph.py`'s unfrozen *format* (the code is PROD); `plugins/*`; `custom_nodes/*`; `GET /nodes`
- **the `/studio/editor/*` raw-frontend proxy** — AUDIT unless intentionally retained behind
  SyMoNeuRaL controls, and that retention has to be an explicit written decision
- `backend/apps/studio/.venv` — ignored, 0 tracked, local-only (§5.1)
- the four `ComfyUI/` source citations and `fork_render_ui.sh`'s shebang grep

**REMOVED — do not assume**

- SDXL as the current baseline — none installed
- `ComfyUI/models/checkpoints` as a baseline — the whole `ComfyUI/` tree is absent
- raw public ComfyUI exposure **as the product** (the proxy's own fate is AUDIT, above —
  what is REMOVED is treating it as the thing customers get)
- CPU fallback for image/GPU workloads — and the code already has none
- stable `operation_id`s existing anywhere today — there are zero

---

## 8. Runtime inventory — added 2026-08-22 for the Studio/Runtime scope (#104)

Requested so no spec can claim a runtime is running when it is not. **The maturity ladder is
in `docs/ops/RUNTIME-PROFILES.md`**: `absent` / `source-only` / `built` / `running` /
`measured`.

### 8.1 What is running right now

```
:8800  python3         the FastAPI API
:8000  symon-gateway   the OpenAI-compatible gateway
```

**The API is running. No model runtime is resident.** Nothing on 8188 (Comfy), no
`symoneural-llm`, `symoneural-diffuse`, `whisper` or `vllm` process anywhere in `ps`. The
governor agrees and is honest about the stale marker:

```
resident surface   image (not running -- stale marker)
lock               free
  of which compute 0 MiB
vram free          14900 MiB
```

That distinction — API up, runtimes down — is load-bearing for `GPU-GOVERNOR.md`, and the
`(not running -- stale marker)` string is R-172's fix working rather than a defect.

### 8.2 The seven families, measured

| Family | Level | Evidence |
|---|---|---|
| **llama.cpp** → `symoneural-llm` | **built** | `engines/symoneural-llm/build/bin/symoneural-llm` and `symoneural-llm-cli`, plus `libsymoneural_tensor_cuda.so.0.20.0` — **CUDA compiled in**. Not running. |
| **stable-diffusion.cpp** → `symoneural-diffuse` | **built** | `engines/symoneural-diffuse/build/bin/symoneural-diffuse`. Not running. |
| **ComfyUI** → `symoneural-ui` | **source-only** | `engines/symoneural-ui/main.py`, `folder_paths.py`, `custom_nodes/ComfyUI-GGUF`, `.venv` with `comfyui_frontend_package`. No build step needed, but nothing listening. |
| **whisper.cpp** | **absent** | See §8.3 |
| **vLLM** | **absent** | Not installed. The only references are `--rollout {transformers,vllm}` and `--vllm-base-url` in `plugins/reinforce/runner.py:280-281` — a trainer option pointing at an *external* server that does not exist here. |
| **NVIDIA samples/tools** | **absent** | No `contrib/cuda-samples`. `references/` holds `apex`, `cosmos`, `cudf`, `cuml`, `DALI`, `DeepLearningExamples`, `FasterTransformer`, `nvidia-{aws,azure,gcp,oci}-samples` — INSPIRE_ONLY, and `test_references_boundary.py:70` already enforces that boundary in a test. |
| **TensorRT-LLM / Triton** | **absent** | Nothing on disk. Future/AUDIT only. |

**`bin/` holds no runtime binary.** It has `claude`, `symoneural-cli`, `symoneural-code`,
`symoneural-discovery`. This is **not** a defect: the governor's kill anchors are *substrings* —
`pkill -f 'bin/symoneural-llm'` (`gpu-governor.sh:272-273,281`) — which match the real path
`engines/symoneural-llm/build/bin/symoneural-llm`. Recorded so a future reader does not "fix"
a working anchor.

### 8.3 REMOVED — `contrib/` does not exist, and two live things cite it

`contrib/` is **not present at any depth**. Two consequences, both real:

**1. `docs/ENGINEERING.md` gives a check that cannot run.** Its "Python environments" section
pins the CUDA sample venv at exactly seven packages:

```bash
contrib/cuda-samples/python/.venv/bin/pip freeze | wc -l    # expect exactly 7
```

The path is absent, so the rule is unverifiable. Worth naming precisely because the passage is
otherwise careful — it corrects an earlier, wronger version of itself in the same paragraph.
**Not fixed here:** `ENGINEERING.md` is the authority document and is outside this scope's
allowed file list.

**2. `apps/voice` cannot transcribe, and mostly says so.** `WHISPER_CLI` lives under
`contrib/`, and there is **no `whisper-cli` binary anywhere on this box**. The honest half is
real and should be preserved: `asr.installed()` (`asr.py:103-114`) checks the binary, its
executable bit, the weights and `ffmpeg`, and returns the exact missing path; `status()` then
reports `state: offline` with that reason. The weights *are* present
(`backend/models/whisper/symoneural-listen-base-en.bin`, 148 MB), so the inventory is real
even though the runtime is not.

**The dishonest half is two fields emitted unconditionally**, beside `available: false`, in
`GET /api/voice/state` (`routes.py:107,117`):

- `"engine": "whisper.cpp, CPU build (GGML_CUDA=OFF)"` — a claim about a build whose
  `CMakeCache.txt` is not on disk to support it.
- `"measured_ms_short_utterance": 650` — labelled *"Measured on this machine"* and carrying
  **no SHA and no date**, describing a binary that is absent.

That second one is the exact shape of the failure `.claude/CLAUDE.md` opens by warning about: a
figure with no commit beside it, carried forward. **AUDIT, and the smallest honest fix is to
gate both behind `ready`** — not to delete the measurement, which may well have been true when
taken. Scope: this is `apps/voice`, not #104, and no code changed here.

### 8.4 What this means for the ASR and LLM baselines

- **ASR inventory: PROD (weights). ASR runtime: absent.** So there is no production ASR route
  to claim, and the code already reports `offline` rather than pretending otherwise.
- **LLM inventory: PROD.** Six GGUF files, 39.64 GB, in `backend/models/llm/`. llama.cpp
  (`symoneural-llm`) is **built** and is the likely local/owner/customer runtime for them.
- **vLLM: candidate only.** No running service, and this report does not claim one.
