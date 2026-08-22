# SyMoNeuRaL Runtime Profiles — the contract

**Status: stub. A contract for something not yet built.**

**Authority boundary.** `docs/ops/HARDWARE-PROFILES.md` says what the *machine* is;
this file says what can *serve* on it. `docs/ops/BOX-REALITY-AUDIT.md` §8 is the authority on
which of these runtimes actually exists on this box today — and the answer for most of them is
"not yet". Nothing in this file may be read as a claim that a service is running.

Consumers: `docs/specs/symoneural-runtime-registry.md`,
`docs/specs/symoneural-model-hot-swap.md`, and the planned `GET /api/runtimes`.

---

## The maturity ladder — used everywhere in these docs

The ladder, in one line: **`absent` / `source-only` / `built` / `running` / `measured`.**

A runtime is at exactly one level. **Naming the level is mandatory**; "supported" is not a
level and never appears alone.

| Level | Means |
|---|---|
| `absent` | Not on disk |
| `source-only` | Source tree present, not built |
| `built` | Binary exists; not running |
| `running` | A process is serving right now |
| `measured` | A stamped figure from a real run exists, with the SHA it was read on |

**Nothing is called green above the level the disk supports.** This ladder exists because the
one thing this project has published untruthfully before is a figure that outran its evidence.

## Runtime families

Roles are Garrett's, 2026-08-22. Current levels are measured — see the audit for evidence.

| Family | Role | Level today |
|---|---|---|
| **llama.cpp** → `symoneural-llm` | primary GGUF/local LLM runtime candidate — local/customer/owner, quantized, smaller edge models, OpenAI-compatible local service where applicable | **built** |
| **stable-diffusion.cpp** → `symoneural-diffuse` | local/customer/owner image runtime candidate — lower-level image generation, GGUF/quantized workflows, a simpler runtime beside Comfy | **built** |
| **ComfyUI** → `symoneural-ui` | **private** workflow/image runner: complex image/audio/video graph execution, the current FLUX/Schnell bridge. **Not a public raw product surface.** | **source-only** |
| **whisper.cpp** | primary ASR runtime candidate — local/customer/owner speech-to-text | **absent** |
| **vLLM** | primary **cloud** LLM runtime candidate — high-throughput serving, OpenAI-compatible API, future dynamic adapter/LoRA serving where supported | **absent** |
| **NVIDIA samples/tools** (`nvidia-diagnostics`) | diagnostic and benchmark **reference only** — GPU diagnostics, CUDA benchmarking, memory/concurrency experiments. **Not blindly copied into app logic.** | **absent** on disk |
| **TensorRT-LLM, Triton, CUDA graphs / MPS** | future NVIDIA-optimized path, **after proof** | **absent** — future/AUDIT only |

**On NVIDIA sample code specifically:** do not import sample source into product logic without
a license and security review. That is not only a rule here — `backend/apps/test_references_boundary.py:70`
already enforces the `references/` boundary in a test, and a rule with a test behind it is
stronger than a rule in a document.

## Profile fields

Each runtime profile entry:

| Field | Notes |
|---|---|
| `runtime_id` | stable, ours — e.g. `symoneural-llm`, `comfy-private` |
| `family` | one of the families above |
| `maturity` | the ladder value, mandatory |
| `model_formats` | `gguf` \| `safetensors` \| `diffusers` \| `onnx` \| `bin` |
| `api_styles` | `openai-compatible` \| `comfy-prompt` \| `native-cli` \| `http-json` |
| `targets` | `cloud` \| `local_customer` \| `local_owner_nvidia` \| `auto` |
| `health_endpoint` | how "is it up" is answered |
| `model_list_endpoint` | how "what can it serve" is answered |
| `load_strategy` | how a model becomes resident |
| `unload_strategy` | how it stops being resident |
| `hot_swap_support` | `native` \| `restart` \| `none` \| `unknown` |
| `multi_model_support` | `concurrent` \| `one-at-a-time` \| `unknown` |
| `gpu_memory_requirements` | derived, labelled measured / vendor / projected |
| `concurrency_class` | `llm` \| `image` \| `asr` \| `embedding` \| `utility` |
| `docs_href`, `api_href`, `openapi_operation_id` | where applicable |

## Rules

- **`maturity` is not optional and not inferred.** A profile with no maturity is invalid.
- **`hot_swap_support: unknown` is a legitimate value.** Guessing `native` because a runtime
  *looks* like it should support it is how a swap becomes a crash.
- **No CPU fallback for GPU workloads on the owner profile unless explicitly authorized.**
- **`multi_model_support: concurrent` must be measured before it is claimed.** On one 16 GB
  card, a large image model and a large LLM co-resident is not an assumption anyone gets for
  free — see `docs/ENGINEERING.md`: chat ~5 GB, image ~7 GB, a QLoRA run ~12 GB, and they
  "cannot coexist".
- **Every runtime goes through the governor.** A runtime that takes the card without a lease is
  the failure `scripts/gpu-governor.sh` exists to prevent, whatever its family.
