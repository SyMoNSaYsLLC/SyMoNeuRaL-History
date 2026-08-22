# SyMoNeuRaL OpenAI 20B — the LLM candidate, and what has to be true before it runs

**Opened 2026-08-22.** Docs and staging plan only. **Nothing downloaded. Nothing activated.
Qwen unchanged and not deleted. No deploy.**

| | |
|---|---|
| internal id | **`symon-openai-20b`** |
| display name | **SyMoNeuRaL OpenAI 20B** |
| short name | **SyMon OpenAI 20B** |
| upstream | **`openai/gpt-oss-20b`** |
| status | **AUDIT / CANDIDATE** |
| downloaded | **no** |
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

## 2. The runtime question, which is the real gate

**`gpt-oss-20b` is not obviously loadable by what is running here, and this is unrecorded rather
than assumed.** The current path is a llama.cpp-family engine consuming **GGUF**. The upstream
repo publishes weights in its own layout, and the staging command in §3 fetches `original/*`.

**Five things must be recorded before activation, and none is measured yet:**

| Question | State |
|---|---|
| what format does the current engine require? | **GGUF** — measured, from the active files |
| what format does `gpt-oss-20b` ship? | **UNRECORDED** — read the repo, do not assume |
| is a conversion needed? | **UNRECORDED.** If yes, the conversion is its own reviewed step with its own provenance |
| tokenizer / chat template compatible? | **UNRECORDED.** A model that loads and answers in the wrong template is worse than one that fails to load |
| VRAM on RTX 5070 Ti (15.92 GiB) | **UNRECORDED.** A projection is not a measurement |

**The MXFP4 question is the one to answer first.** `gpt-oss` is distributed with a
mixed-precision quantisation that a stock llama.cpp build may not support. **If the engine cannot
read it, no amount of staging helps** — and finding that out after a multi-tens-of-GB download is
the avoidable version of that discovery. **Read the upstream model card before fetching.**

**The fallback is not a plan, it is the current state:** Qwen keeps serving. There is no window
in which the box has no chat model, because activation is a source edit that has not happened.

## 3. Staging — recorded, not run

```bash
scripts/modelops/symoneural-modelops-stage.sh --stage-openai-gpt-oss-20b
```

Writes `backend/models/staging/openai-gpt-oss-20b/STAGED-MANIFEST.json` and `ROLLBACK.md`, and
**prints** the download command:

```bash
huggingface-cli download openai/gpt-oss-20b \
  --include "original/*" \
  --local-dir backend/models/staging/openai-gpt-oss-20b/
```

**It will not run it.** Even with `SYMONEURAL_MODELOPS_CONFIRM` set to the phrase, the script
declines and says why: tens of GB onto a disk already holding **194 GB** should not be one
environment variable away from being spent. **The download is Garrett's to run by hand**, after
he says so.

**Staging is gitignored** (`.gitignore:5`, `backend/models/*`), so neither the weights nor the
staged manifest can be committed. Structural, not a promise.

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

**Nothing is recorded about `gpt-oss-20b`'s licence**, so by `docs/ops/LICENSE-AUDIT.md`'s
vocabulary it is **`unknown-blocked`** — and gate 4 refuses activation on exactly that.

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
