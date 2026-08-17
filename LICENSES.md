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

### hls.js — Apache-2.0
`site/hls.js` (384 KB, the **light** build) and `site/hls-LICENSE.txt`, served on `/tuner.html`.

- Fetched from `cdn.jsdelivr.net/npm/hls.js@1/dist/hls.light.min.js`; the licence text is the
  project's own `LICENSE` from `video-dev/hls.js`.
- **Verified by reading the file, not the metadata.** GitHub's API reports `NOASSERTION` for
  this repo, which is not a licence — the `LICENSE` file itself is plainly Apache-2.0,
  copyright 2017 Dailymotion.
- Needed because Chrome and Firefox will not play an `.m3u8` natively. Safari will, and the
  page uses the native path there.

**VLC was considered and rejected.** `references/IPTV/vlc-master/` is **GPLv2**, and the only
web path is `extras/package/wasm-emscripten` — an hours-long build producing a GPL-licensed
WASM blob that would then be part of what we distribute in `site/`, making the site itself
GPL-encumbered. hls.js does the same job in 384 KB under a permissive licence.

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
| **ggml-base.en** (Whisper) | speech → text for Stickers | **MIT** | `ggerganov/whisper.cpp` model card declares `license: mit`; it is a conversion of `openai/whisper`, whose repo `LICENSE` is MIT (both texts fetched) |
| **u2net.onnx** (U²-Net) | photograph cut-out for Stickers | **Apache-2.0** | see the provenance note below — the text is the source repo's, not the file's |

> **u2net's provenance, stated precisely rather than flattened to "verified".** The `.onnx`
> we fetch is a **release asset republished by rembg** and carries no licence file of its own.
> The Apache-2.0 grant lives in the architecture's source repository, `xuebinqin/U-2-Net`,
> whose `LICENSE` was fetched and read on 2026-08-17. So the honest claim is *"upstream
> U-2-Net is Apache-2.0 and rembg redistributes these weights"* — not *"the artefact we
> downloaded declares Apache-2.0"*, which it does not. Same measured/vendor/projected
> discipline the site applies to numbers.

> **Two rembg models were checked and rejected**, and the reasons are worth keeping because
> the next person will see them in rembg's list and wonder. **`bria-rmbg-2.0` is CC BY-NC 4.0**
> — non-commercial, and the best-known model rembg offers, so it is the likeliest wrong
> choice in the whole surface. **`isnet-general-use`** comes from `xuebinqin/DIS`, which has
> **no `LICENSE` file at all** and whose README scopes Apache-2.0 to "our code and evaluation
> metric" while sending the DIS5K *dataset* — what those weights are trained on — to a
> separate terms-of-use PDF. **`silueta`** is a third-party derivative with no licensed source
> repo this box could find. The last two are not asserted to be non-permissive; they are
> **unverified**, which inside a licence gate is worse. The allowed set in
> `backend/apps/sigils/cutout_worker.py` is therefore `u2net` and `u2netp` only, and
> `scripts/fetch-cutout.sh` refuses anything else.

Licence texts are saved to **`backend/models/licenses/`** by `scripts/fetch-models.sh`,
`scripts/fetch-whisper.sh` and `scripts/fetch-cutout.sh` — all three write to the one
directory so a customer build has a single place to look. `models/` is gitignored
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
| **whisper.cpp** (`whisper-cli`) | **MIT** | Copyright (c) 2023-2026 The ggml authors |

MIT obliges only that the copyright line and permission notice travel with the code. Ship
`contrib/llama.cpp/LICENSE`, `contrib/stable-diffusion.cpp/LICENSE` and
`contrib/whisper.cpp/LICENSE` alongside the binaries.

> whisper.cpp is built here with `-DGGML_CUDA=OFF`. That is a performance decision, not a
> licence one, but it is a **modification of build configuration only** — no source is
> patched, so there is nothing to declare beyond the MIT notice.

### The Stickers cut-out venv — also redistributed

`backend/apps/sigils/.venv` is reached across a subprocess boundary by `cutout_worker.py` and
is **not** part of the serving interpreter. It is listed here rather than in §5 for one
concrete reason: §5 is explicitly *informational, not redistributed*, and these packages **are**
redistributed if a customer box does photograph cut-outs. Populated by `scripts/fetch-cutout.sh`.

| Package | Licence |
|---|---|
| rembg | **MIT** — Copyright (c) 2020 Daniel Gatis |
| onnxruntime | **MIT** — Copyright (c) Microsoft Corporation |
| pymatting | MIT |
| Pillow | MIT-CMU |
| numpy | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0-1.0 components) |
| scikit-image, pooch | BSD-3-Clause |

`rembg.LICENSE.txt` and `onnxruntime.LICENSE.txt` are fetched to `backend/models/licenses/`.
The remainder are ordinary MIT/BSD wheels whose texts ship inside their own `dist-info`, which
is where a customer image will find them.

> **`backend/apps/asicminer/.venv` exists and is not documented anywhere in this file.** It
> predates the Stickers work and was found while writing this section. Noted rather than
> quietly covered: if that surface ships on a customer box, its packages need the same
> treatment as the table above.

---

## 4. Web server

**Caddy 2.6.2 — Apache-2.0.** Installed from Debian, not redistributed by us. If a customer
image bundles it, include `/usr/share/doc/caddy/copyright`.

---

## 5. Serving stack — informational, not redistributed

Debian OS packages on the system interpreter. **The serving interpreter still has no
virtualenv, and nothing below is reached through one** — but that sentence used to read "there
is no virtualenv in the serving path", and Stickers made it misleading. A *request* for a
photograph cut-out does now cross into `backend/apps/sigils/.venv`; it crosses by
`subprocess`, which is exactly what keeps this interpreter pinned. Those packages are in §3,
because unlike the ones below they are redistributed.

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
- `backend/apps/reinforce/` (the CUDA engine) and `backend/apps/remix/`
- **`training/corpus.jsonl`** and **`training/build_dataset.py`** — the authored identity
  corpus and the method that produces it
- **`training/adapter/`** — the LoRA weights

A LoRA adapter is a derived work of an Apache-2.0 base model, and Apache-2.0 imposes **no
obligation to publish fine-tunes**. The adapter and the corpus can stay closed indefinitely.
If you distribute the adapter you still owe the base-model attribution — which the rack already
carries as `built on Qwen2.5-7B-Instruct`. That line is a licence condition, not decoration.

The corpus and its generator are protected only by not being public. Trade secret, unlike
copyright, exists only while reasonable measures are taken to keep it secret, and it cannot be
recovered once disclosed. See the never-publish rule in `.claude/CLAUDE.md`.

---

## 8. Obligations by licence, in one place

**Apache-2.0** (Qwen2.5, FLUX.1-schnell, T5-XXL, CLIP-L, **u2net**, Swagger UI, Caddy)
- ship the licence text; preserve copyright, patent, trademark and attribution notices
- include upstream's `NOTICE` file if there is one, and carry its contents forward
- **state that you modified files, if you did** — quantising a model counts; say so
- grants patent rights, which **terminate if you initiate patent litigation** against a contributor
- grants **no trademark rights**: build on Qwen and FLUX, do not brand as them

**MIT** (llama.cpp, stable-diffusion.cpp, **whisper.cpp**, **Whisper ggml weights**, **rembg**,
**onnxruntime**, **pymatting**, FastAPI, core-js, normalize.css, Pillow)
- reproduce the copyright line and the permission notice. That is the entire obligation.

**CC BY-NC 4.0** — nothing in this stack, and that is deliberate
- **`bria-rmbg-2.0` would have put it here.** It is non-commercial, it is the default many
  rembg examples reach for, and it is blocked at two layers (§2). If a future change makes
  this heading non-empty, the product has a problem, not a footnote.

**BSD-3-Clause** (uvicorn, SymPy, numpy, scikit-image, pooch)
- as MIT, plus: do not use the authors' names to endorse or promote your product.

**NVIDIA EULA** (CUDA)
- redistribution is conditional. Read it before baking CUDA into an image you hand over.

---

## 9. Checklist for a customer build

- [ ] `models/licenses/` included beside the weights
- [ ] `contrib/llama.cpp/LICENSE`, `contrib/stable-diffusion.cpp/LICENSE` and
      `contrib/whisper.cpp/LICENSE` included beside the binaries
- [ ] if the box does Stickers cut-outs: `backend/apps/sigils/.venv` packages carried with
      their `dist-info`, and `rembg`/`onnxruntime` texts present in `models/licenses/`
- [ ] confirm the cut-out model in use is **`u2net`** or **`u2netp`** — never **`bria-rmbg-2.0`**,
      which is non-commercial. This is the Stickers equivalent of the schnell/dev trap below
- [ ] `site/swagger-ui-LICENSE.txt` and `site/swagger-ui-NOTICE.txt` present in the webroot
- [ ] this file included
- [ ] modifications stated (quantisation, fine-tuning) for every Apache-2.0 component
- [ ] confirm the image model is **schnell**, never **dev**
- [ ] confirm the Qwen size in use is Apache-2.0 on its own model card
- [ ] CUDA not bundled, or its EULA redistribution clause reviewed
- [ ] contract carries the use-don't-extract terms for the adapter — technical secrecy ends the
      moment the weights are on hardware you do not control
