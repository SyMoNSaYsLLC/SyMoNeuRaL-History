# Third-party licences — SyMoNeuRaL

Every entry below was verified against what is actually installed and served on this machine,
not copied from an upstream README. Where a claim could not be verified it says so.

**Last verified:** 2026-08-16.
**Regenerate/re-verify** when models, engines or the vendored Swagger UI change.

---

## The rule that decides everything here

**Obligations attach to what you *distribute*, not to what is installed on the server.**
That gives two very different modes:

| Mode | What leaves your control | Obligations |
|---|---|---|
| **Running symoneural.com** (a service) | only `site/` — HTML, CSS, JS, images | attribution for the vendored Swagger UI. Nothing else. |
| **Shipping a customer a server** | the whole stack: engines, weights, adapter | full attribution for everything in §2–§4 below |

Debian packages on the box (FastAPI, uvicorn, SymPy, Pillow, certifi…) are the operator's
dependencies. You are not redistributing them by running them, so §5 is informational.

**Nothing in this stack is copyleft.** No GPL, no AGPL, no MPL in anything shipped. Your own
code, your adapter and your training corpus can be proprietary and closed. See §6.

---

## 1. Shipped to every visitor today

### Swagger UI 5.17.14 — Apache-2.0
`site/swagger-ui-bundle.js` (1.45 MB) and `site/swagger-ui.css`, served on `/docs`.
Version identified by SHA-256 match against `swagger-ui-dist@5.17.14`, not by guesswork.

- **Attribution shipped:** `site/swagger-ui-LICENSE.txt`, `site/swagger-ui-NOTICE.txt`
  (`swagger-ui — Copyright 2020-2021 SmartBear Software Inc.`)
- The bundle's own banner points at `swagger-ui-bundle.js.LICENSE.txt`, which upstream does
  **not** publish — it is a webpack/terser artifact. `LICENSE` + `NOTICE` from the dist package
  is the correct and complete attribution.
- The bundle embeds **core-js** (MIT) and **normalize.css v7.0.0** (MIT); both are covered by
  the shipped NOTICE.

### Our own site assets — proprietary
`symoneural.css`, `rack-detail.css`, `swagger-dark.css`, `console.js`, `ui.js`, the generated
HTML, and the `art-*.png` renders. © SymonSays LLC. All rights reserved.

---

## 2. Model weights — served now, distributed if you ship a box

| Model | Role | Licence | Verified how |
|---|---|---|---|
| **Qwen2.5-7B-Instruct** | chat | **Apache-2.0** | `LICENSE` fetched from the model repo |
| **Qwen2.5-14B-Instruct** | chat (larger) | **Apache-2.0** | identical SHA-256 to the above |
| **Qwen2.5-0.5B-Instruct** | speculative draft | **Apache-2.0** | identical SHA-256 to the above |
| **FLUX.1-schnell** (+ VAE) | image | **Apache-2.0** | model card declares it; explicitly permits commercial use |
| **T5-XXL**, **CLIP-L** | FLUX text encoders | **Apache-2.0** as redistributed | the GGUF repos we fetched from are Apache-2.0 tagged |

Licence texts are saved to **`models/licenses/`** by `scripts/fetch-models.sh`. `models/` is gitignored
(40 GB), so those files live on disk beside the weights rather than in git — **they must be
included in any customer image.**

> **FLUX.1-schnell only.** FLUX.1-**dev** is *not* Apache-2.0 — it is non-commercial. Never
> substitute it into anything customer-facing. This is the single most dangerous swap in the
> stack, and `scripts/fetch-models.sh` pulls schnell deliberately.

> **Qwen licences vary by model size.** 7B, 14B and 0.5B are Apache-2.0 (verified). Other sizes
> in the family ship under Qwen's own licence with extra terms. Check the specific model card
> every time you change models; do not assume the family is uniform.

**Model output** is not restricted by these licences.

---

## 3. Inference engines — distributed if you ship a box

| Component | Licence | Copyright |
|---|---|---|
| **llama.cpp** (`llama-server`, and 100+ binaries) | **MIT** | Copyright (c) 2023-2026 The ggml authors |
| **stable-diffusion.cpp** (`sd-cli`) | **MIT** | Copyright (c) 2023 leejet |

MIT obliges only that the copyright line and permission notice travel with the code. Ship
`contrib/llama.cpp/LICENSE` and `contrib/stable-diffusion.cpp/LICENSE` alongside the binaries.

---

## 4. Web server

**Caddy 2.6.2 — Apache-2.0.** Installed from Debian, not redistributed by us. If a customer
image bundles it, include `/usr/share/doc/caddy/copyright`.

---

## 5. Serving stack — informational, not redistributed

Debian OS packages on the system interpreter. There is no virtualenv in the serving path.

| Package | Licence |
|---|---|
| FastAPI, Pydantic, Starlette-adjacent tooling | MIT |
| uvicorn, SymPy | BSD-3-Clause |
| Pillow | MIT-CMU |

**`certifi` (MPL-2.0) is present on the box but is not part of this product.** It arrives via
certbot and requests, the serving stack never imports it (verified: importing fastapi, uvicorn
and sympy does not load it), and we do not redistribute it. An earlier note listed MPL-2.0 as a
live obligation; it is not.

---

## 6. NVIDIA CUDA — the one genuinely restrictive item

The CUDA toolkit, cuDNN and the driver are governed by **NVIDIA's EULA**, not an open-source
licence. Today the customer installs the toolkit themselves, so this is a dependency note.

**If you ever ship a container or disk image with CUDA baked in, read the EULA's redistribution
clause first.** It is the only thing in this stack that can stop you shipping.

---

## 7. What is ours

Proprietary to SymonSays LLC, all rights reserved, and **not** covered by any licence above:

- `api.py`, the `build_*.py` generators, `symoneural`, `ravencalc.py`, the shell tooling
- `apps/reinforce/` (the CUDA engine) and `apps/remix/`
- **`training/corpus.jsonl`** and **`training/build_dataset.py`** — the authored identity
  corpus and the method that produces it
- **`training/adapter/`** — the LoRA weights

A LoRA adapter is a derived work of an Apache-2.0 base model, and Apache-2.0 imposes **no
obligation to publish fine-tunes**. The adapter and the corpus can stay closed indefinitely.
If you distribute the adapter you still owe the base-model attribution — which the rack already
carries as `built on Qwen2.5-7B-Instruct`. That line is a licence condition, not decoration.

The corpus and its generator are protected only by not being public. Trade secret, unlike
copyright, exists only while reasonable measures are taken to keep it secret, and it cannot be
recovered once disclosed. See the never-publish rule in `CLAUDE.md`.

---

## 8. Obligations by licence, in one place

**Apache-2.0** (Qwen2.5, FLUX.1-schnell, T5-XXL, CLIP-L, Swagger UI, Caddy)
- ship the licence text; preserve copyright, patent, trademark and attribution notices
- include upstream's `NOTICE` file if there is one, and carry its contents forward
- **state that you modified files, if you did** — quantising a model counts; say so
- grants patent rights, which **terminate if you initiate patent litigation** against a contributor
- grants **no trademark rights**: build on Qwen and FLUX, do not brand as them

**MIT** (llama.cpp, stable-diffusion.cpp, FastAPI, core-js, normalize.css, Pillow)
- reproduce the copyright line and the permission notice. That is the entire obligation.

**BSD-3-Clause** (uvicorn, SymPy)
- as MIT, plus: do not use the authors' names to endorse or promote your product.

**NVIDIA EULA** (CUDA)
- redistribution is conditional. Read it before baking CUDA into an image you hand over.

---

## 9. Checklist for a customer build

- [ ] `models/licenses/` included beside the weights
- [ ] `contrib/llama.cpp/LICENSE` and `contrib/stable-diffusion.cpp/LICENSE` included beside the binaries
- [ ] `site/swagger-ui-LICENSE.txt` and `site/swagger-ui-NOTICE.txt` present in the webroot
- [ ] this file included
- [ ] modifications stated (quantisation, fine-tuning) for every Apache-2.0 component
- [ ] confirm the image model is **schnell**, never **dev**
- [ ] confirm the Qwen size in use is Apache-2.0 on its own model card
- [ ] CUDA not bundled, or its EULA redistribution clause reviewed
- [ ] contract carries the use-don't-extract terms for the adapter — technical secrecy ends the
      moment the weights are on hardware you do not control
