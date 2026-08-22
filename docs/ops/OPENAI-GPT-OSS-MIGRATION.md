# SyMoNeuRaL OpenAI 20B — the LLM candidate, and what has to be true before it runs

**Opened 2026-08-22.** **Weights downloaded 2026-08-22 on Garrett's explicit authorization —
see §3a. Nothing converted. Nothing activated. Qwen unchanged and not deleted. No deploy.**

| | |
|---|---|
| internal id | **`symon-openai-20b`** |
| display name | **SyMoNeuRaL OpenAI 20B** |
| short name | **SyMon OpenAI 20B** |
| upstream | **`openai/gpt-oss-20b`** |
| status | **AUDIT / CANDIDATE** |
| downloaded | **yes — 2026-08-22, 32 GiB staged, see §3a** |
| converted | **no — this is the next gated step** |
| active | **no** |

## 0. Scope, stated first because it is the thing most likely to be over-read

**This is an LLM candidate. It replaces nothing else.**

- **Image stays FLUX/Schnell.** There is no local open-weight OpenAI image model in this repo's
  scope, and `docs/ops/COMFY-FLUX-BUNDLE.md` formalises the existing stack rather than migrating
  it. **Any claim that an OpenAI weight replaces FLUX is false.**
- **Audio stays whisper.cpp.** An OpenAI Whisper *API* is not a local open-weight replacement for
  a local model. If it is ever wanted it is a separate, clearly-marked **API/FUTURE** provider.
- **`openai/gpt-oss-120b` is FUTURE only** — not staged, not planned, not sized for this card.

## 1. What it would replace, measured

| | |
|---|---|
| active chat | `backend/models/llm/symon-1.0-7b-q4_k_m.gguf` — 4.36 GiB, `bartowski/Qwen2.5-7B-Instruct-GGUF`, Apache-2.0, licence text on disk |
| active draft | `backend/models/llm/symon-1.0-draft-0.5b-q4_k_m.gguf` — 0.37 GiB, speculative decode |
| set at | `backend/api.py:187`, `:191` |
| runtime | llama.cpp-family engine, `-ngl 99` (`api.py:1163`) |

**Qwen remains active and is not deleted.** It becomes `rollback` **only** after a smoke record
exists and Garrett approves activation — two conditions, not one.

## 2. The runtime gate — ANSWERED 2026-08-22. Verdict: **NEEDS CONVERSION**

**Everything required is present in this tree. A conversion step is required because upstream
ships safetensors and the engine consumes GGUF.** That is the whole of the verdict.

### What upstream actually ships — read from the HF API, not from memory

| | |
|---|---|
| `original/model.safetensors` | **13,761,300,984 B = 12.81 GiB**, single file |
| top-level shards | `model-0000{0,1,2}-of-00002.safetensors` — **13,761,316,904 B = 12.81 GiB** total |
| GGUF in the repo | **none** |
| parameters | 21,511,953,984 |
| quantisation | **MXFP4**, with attention, router and embedding/output head **not** converted |
| licence | **Apache-2.0** |

**Apache-2.0 closes the licence question** that §5 had open as `unknown-blocked` — the text
still has to be stored on disk before activation, but the answer is no longer unknown.

### What this box can do — measured from the engine source

| Capability | State |
|---|---|
| engine | `engines/symoneural-llm/build/bin/symoneural-llm` — **`build 296, commit 2246ab7`** |
| `gpt-oss` architecture | ✅ `LLM_ARCH_OPENAI_MOE` → `"gpt-oss"`, `llama-arch.cpp:121` |
| Harmony chat template | ✅ `LLM_CHAT_TEMPLATE_OPENAI_MOE`, `llama-chat.cpp:75` |
| **MXFP4 as a ggml type** | ✅ **`GGML_TYPE_MXFP4 = 39`**, `ggml.h:429`; `GGML_FTYPE_MOSTLY_MXFP4` |
| **MXFP4 on CUDA** | ✅ `convert.cu`, `getrows.cu`, MMQ configs — **the GPU path, not just CPU** |
| GGUF writer support | ✅ `gguf-py/gguf/constants.py`: `GPT_OSS`, tensor map, `MXFP4 = 39`, `MOSTLY_MXFP4_MOE = 38` |
| **converter module** | ✅ **`engines/symoneural-llm/conversion/gpt_oss.py`** — `@ModelBase.register("GptOssForCausalLM")`, with **`repack_mxfp4()`** |

**`repack_mxfp4` is the detail that makes this workable.** It repacks the MXFP4 blocks rather
than dequantising them — `dequant_model()` returns early when `_is_mxfp4` — so the conversion
preserves the 4-bit weights instead of inflating them to bf16. Without that the output would be
several times larger and would not fit this card at all.

### Why the verdict is NEEDS CONVERSION and not READY

The engine reads **GGUF**. Upstream publishes **safetensors only**. So one step stands between
them, and it is supported in-tree.

**The conversion needs PyTorch, and the interpreter matters:**

| Interpreter | torch |
|---|---|
| `/usr/bin/python3` | **absent** |
| **`training/.venv/bin/python3`** | **2.11.0+cu128, `cuda available: True`, sm_120 recognised** |

**Use `training/.venv/bin/python3` for the conversion.** The system interpreter cannot run it.

### Footprints — measured, not projected

**Disk — re-measured 2026-08-22 after the download, because the pre-download projection was
already wrong.** The projection said ~26 GiB peak on the assumption of one 12.81 GiB download.
**Two trees were fetched** (§3a), so staging is **32 GiB** before any GGUF exists:

| | |
|---|---|
| `original/` (unconvertible, retained) | 13 GiB |
| `hf/` (convertible) | 19 GiB |
| dead `.incomplete` leftovers, reclaimable | 6,574,559,947 B |
| GGUF still to come | ~13 GiB if MXFP4 is preserved |
| **peak, both trees kept** | **~45 GiB** |
| available on `/home`, which holds the models | **793 GB** |

**Disk is still not a constraint**, but note the mount: `df /` reports **277 GB** and is the
*wrong* filesystem. `backend/models` lives on `/home` (`/dev/nvme0n1p5`, 1.4T). A capacity check
run against `/` would be off by a factor of three in the reassuring direction.

**VRAM — and this is the finding that changes the smoke command.** The card is **16,303 MiB**,
972 MiB used at idle. The production launch argv is `-c 65536 -cb -np 2`, and the module's own
measured comment records **9,485 MiB total for a 4.36 GiB model** — so **KV and overhead cost
~3.9 GiB at that context**.

> **12.81 GiB of weights + ~3.9 GiB of KV ≈ 16.7 GiB on a 16,303 MiB card. It will not fit.**

**So the candidate cannot be smoked at the production context.** `--smoke-candidate` uses
**`-c 8192 -np 1`**, and says why in its own output — because *an OOM nobody predicted reads like
an incompatible model rather than an argv that was too greedy.*

## 2a. Isolated smoke — the candidate proves itself or fails

```bash
scripts/modelops/symoneural-modelops-stage.sh --smoke-candidate symon-openai-20b
```

**Isolation is structural, not a flag.** The mode launches the engine binary directly against the
candidate file, on port **8099** (not the production 8081), in its own process, and **never
imports or invokes the production API module** — which is the only thing that knows what the
production defaults are. A fallback is therefore not *disabled*; it is **unreachable**.

**A flag that disables a fallback can be wrong. A function that cannot name the fallback cannot
load it** — and the function is held to exactly that by
`test_the_smoke_mode_cannot_NAME_what_it_must_not_load`, which forbids the production symbols and
filenames from appearing **anywhere in its body**. The body explains the isolation in neutral
terms for that reason.

| Property | How |
|---|---|
| no adapter | the printed argv carries no adapter flag; asserted |
| no draft model | no draft flag; speculative decode is a pairing trained for the production default |
| own port | 8099; the production port never appears in the body |
| **fails when the candidate is missing** | **exit 5**, `REFUSED`, and it says the active model was not consulted |
| fails when the engine is missing | exit 5 |
| reports what ran | candidate path, engine path, **engine `--version`**, and the exact argv |
| production default | **unchanged.** Rollback weights present and untouched; asserted against the disk |

**The smoke path does not need PyTorch** — it is the C++ engine binary. Only the conversion does.

**"Disabled for smoke" means disabled in the test path.** It does not mean deleted, moved, or
that the production default changed.

## 3. Staging — recorded, not run

```bash
scripts/modelops/symoneural-modelops-stage.sh --stage-openai-gpt-oss-20b
```

Writes `backend/models/staging/openai-gpt-oss-20b/STAGED-MANIFEST.json` and `ROLLBACK.md`, and
**prints** the download command:

```bash
hf download openai/gpt-oss-20b \
  --exclude "original/*" --exclude "metal/*" \
  --local-dir backend/models/staging/openai-gpt-oss-20b/hf/
```

> **Not `huggingface-cli`.** That entrypoint is **deprecated and no longer works**, and its
> failure mode is the one worth writing down: it prints a deprecation notice and **exits 0
> without downloading anything.** A caller that checks the exit code sees success and an empty
> directory. Found by running it — this document recorded the dead command until 2026-08-22,
> when the first authorized download produced 12 KB and a zero exit. `hf` is the replacement
> and is already installed. Measured against `huggingface_hub 1.23.0`.

**It will not run it.** Even with `SYMONEURAL_MODELOPS_CONFIRM` set to the phrase, the script
declines and says why: tens of GB onto a disk already holding **194 GB** should not be one
environment variable away from being spent. **The download is Garrett's to run by hand**, after
he says so.

**Staging is gitignored** (`.gitignore:5`, `backend/models/*`), so neither the weights nor the
staged manifest can be committed. Structural, not a promise.

## 3a. What was actually downloaded — 2026-08-22, and the correction it forced

**Two downloads happened, and the first one fetched the wrong thing.** Recording both, because the
mistake is the useful part.

| Tree | Bytes | Convertible? |
|---|---|---|
| `original/` | 13 GiB, single `model.safetensors` | **NO** |
| **`hf/`** | **19 GiB, 3 shards + tokenizer** | **yes** |

**Why `original/` cannot be converted** — three independent blockers, all found by reading the
downloaded files *before* running the converter rather than after it failed:

1. `original/config.json` has **no `architectures` key**, so `ModelBase` cannot dispatch to the
   `@ModelBase.register("GptOssForCausalLM")` handler at all.
2. Its tensors are named `block.0.attn.qkv.weight` — the **original OpenAI layout**. The converter
   expects the HF names (`gate_up_proj`, `down_proj`).
3. **No tokenizer.** `original/` ships weights only.

> **The `--include "original/*"` in §3's printed command was wrong**, and it was wrong in a way
> that costs 13 GiB to discover. `original/` is the OpenAI *reference* checkpoint, not the HF one.
> The correct filter is `--exclude "original/*" --exclude "metal/*"`.

**The root download, verified byte-exact against the HF API's reported sizes:**

| File | Bytes |
|---|---|
| `model-00000-of-00002.safetensors` | 4,792,272,488 |
| `model-00001-of-00002.safetensors` | 4,798,702,184 |
| `model-00002-of-00002.safetensors` | 4,170,342,232 |
| `tokenizer.json` | 27,868,174 |
| `model.safetensors.index.json` | 36,355 — names **3 shards / 459 tensors**, all present |
| `LICENSE` | 11,357 |

All three conversion blockers are now closed: `architectures: ["GptOssForCausalLM"]`,
`quant_method: mxfp4`, full tokenizer.

### Two operational findings worth keeping

**The download stalled, and an unauthenticated fetch is why.** Two shards sat idle 932 s and 669 s,
2.81 GiB short. `hf auth whoami` → **not logged in**; no `HF_TOKEN`, no `HUGGINGFACE_HUB_TOKEN`, no
`~/.cache/huggingface/token`. So every byte here came down anonymous, against a rate limit, which
matches the warning the client printed. **Re-running `hf download` resumed from the `.incomplete`
files** and moved 5,271 MiB in 60 s. Nothing was re-fetched from zero.

**6,574,559,947 bytes of dead `.incomplete` files remain** under `hf/.cache/huggingface/download/`.
The resume wrote into fresh temp files rather than continuing those two, so they are reclaimable —
measured static over a 10 s window, with no writer process alive. **Not deleted**: no mode of this
workflow deletes without authorization.

### Shard integrity — because a resumed download can be the right length and the wrong bytes

Two of the three shards were completed by **resuming from `.incomplete` files after a stall**, and
a resume that appends onto a corrupt prefix produces a file of exactly the expected size. **Byte
count is therefore not sufficient evidence here.** Each shard's safetensors header was parsed and
its offsets checked — seconds of work, no torch required:

| Shard | Header | Tensors | Last tensor ends | Payload | |
|---|---|---|---|---|---|
| `model-00000-of-00002` | 22,240 | 196 | 4,792,250,240 | 4,792,250,240 | ✅ |
| `model-00001-of-00002` | 22,304 | 197 | 4,798,679,872 | 4,798,679,872 | ✅ |
| `model-00002-of-00002` | 7,568 | 66 | 4,170,334,656 | 4,170,334,656 | ✅ |

**459 tensors, matching `model.safetensors.index.json` exactly.** Dtypes are **`BF16` and `U8`** —
and the `U8` is the load-bearing observation: **the MXFP4 blocks are still packed 4-bit in uint8,
not dequantised.** If these read as all-BF16 the weights would already have been inflated upstream
of us and the size projection below would be wrong.

### The corrected conversion command

```bash
training/.venv/bin/python3 engines/symoneural-llm/convert_hf_to_gguf.py \
  backend/models/staging/openai-gpt-oss-20b/hf \
  --outfile backend/models/staging/openai-gpt-oss-20b/symon-openai-20b.gguf \
  --outtype auto
```

**Note the input path is `hf/`, not the staging root.** Pointed at the root, the converter would
find `original/` and hit blocker 1.

#### Judge the result by output size, not by the exit code

`--outtype auto` is the untested part of that command. **MXFP4 preservation comes from
`_is_mxfp4` short-circuiting `dequant_model()`, not from `--outtype`** — so if `auto` resolves to
bf16 in this fork, the conversion *succeeds*, exits 0, and writes an inflated model.

| Output size | Verdict |
|---|---|
| **~12–13 GiB** | **MXFP4 preserved — correct** |
| ~40+ GiB | dequantised to bf16 — **wrong; redo with an explicit outtype** |

**This has to be checked at conversion time, not at smoke time.** 793 GB free means disk will not
stop a 40 GiB write, and the failure would surface as a smoke OOM — which reads as *"the candidate
is incompatible"* rather than *"the file is three times the size it should be."* That is the exact
misdiagnosis the `-c 8192` note in §2a exists to prevent, arriving by a different route.

## 4. The six activation gates

`--activate-candidate symon-openai-20b` exits **3** and prints REFUSED unless **all** hold:

1. candidate staged — `STAGED-MANIFEST.json` exists
2. **`SMOKE-PASSED.txt` exists**
3. `ROLLBACK.md` exists
4. licence recorded — the manifest no longer says `UNRECORDED`
5. runtime compatibility recorded — likewise
6. `SYMONEURAL_MODELOPS_APPROVE=symon-openai-20b` in the environment

**Gate 2 is the one that matters.** `exists` and `grep` ask what is on disk; **neither can ask
whether a model works.** That is #94's lesson — eighteen green checks over a dead surface —
applied to models. `--smoke-plan` prints the six readings the marker must contain: runtime load,
tokenizer round-trip, one real generation, **measured** VRAM, a governor lease taken and
released, and **the previous default proven to still load afterwards.**

**Even with all six passing, the script does not rewrite `CHAT_MODEL`.** It backs up `api.py` and
stops, saying why: promotion edits a source file the API reads at import, and **that belongs in a
reviewed commit with a test, not a shell one-liner.** The gate's job is to say whether promotion
is *allowed* — not to get it past review.

## 5. Licence — unrecorded, and therefore blocking

**Answered 2026-08-22: the upstream licence is Apache-2.0**, read from the HF API rather than
recalled. So it is no longer `unknown-blocked` on the *question* — but gate 4 still refuses
activation, because the **text is not on disk** and the manifest still says `UNRECORDED`.

Before it can be anything else: the upstream licence read, its **text stored on disk** beside the
others in `backend/models/licenses/`, and the four commercial fields recorded that
`MODEL-LICENSES.md` ML-2 says are missing for **every** model here — redistribution, commercial
use, modification, output restrictions.

**This is not pedantry about a candidate.** Three weights already on this box are
`redistribution-restricted` in practice because their licence text is absent (ML-1). Adding a
fourth unrecorded model would repeat a known-open finding on purpose.

## 6. Naming — house name is display, upstream is recorded exactly

**SyMoNeuRaL OpenAI 20B** / **SyMon OpenAI 20B** are display names. The manifest records
`openai/gpt-oss-20b` verbatim.

**Never rename a licence file. Never hide upstream origin.** `PROVENANCE.json`'s own reason:
*"a house name with no recorded origin is an unfalsifiable claim about what the bytes are."*

## 7. Not authorized

No download · no activation · no `CHAT_MODEL` edit · no Qwen deletion or move · no weight
committed · no licence file renamed · no claim that this is active, working, or better · no
claim it replaces the image or audio stacks · no deploy.

**Until Garrett says otherwise: Qwen 7B is the chat model, and `symon-openai-20b` is a name in a
document.**
