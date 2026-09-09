# NVIDIA and upstream toolchain — licence ledger

**Recorded 2026-08-24 (P1.5).** Source acquisition only: nothing here was
installed, built, benchmarked or deployed.

> ## Source availability is not a production right.
>
> Every row below records what the **public repository** licence permits. Several
> of these components additionally require an **NVIDIA SDK download under a
> separate EULA**, and NIM containers are licensed separately again. A permissive
> licence on a GitHub tree says nothing about the terms attached to the binary
> SDK, the container image, or the model weights that component runs.
>
> **Do not infer hosted-production rights from any row in this table.** Where a
> row says "development/evaluation", that is what has been established — not a
> limit that has been proven, and not a permission that has been granted.

---

## Acquired public source trees

| Component | Tag | Commit | Licence |
|---|---|---|---|
| cuda-samples | `v13.3` | `b7c5481c556c3fe98db060207ecaa41a4b9a9abc` | NVIDIA BSD-3-Clause style |
| nvbandwidth | `v0.10.0` | `82fc4e8c6afa0babb8687793678f615b3b8d793e` | **Apache-2.0** |
| nvbench | main (no stable tag) | `66212f1da71cc9afb2894a46fa8f234cbdd6c0d8` | **Apache-2.0** |
| CUTLASS | `v4.7.0` | `dcf215af68a2d08d305076c152a06f201728cd53` | **BSD-3-Clause** |
| Model Optimizer | `0.46.0` | `43fd41a58d52c4e6e5dec1d1ff5989ecc737ae1a` | **Apache-2.0** |
| TensorRT (OSS) | `v11.1` | `82d1dca801c8318a5605399d5240780d0679e4e1` | **Apache-2.0** (OSS components) |
| TensorRT-RTX (OSS) | `v1.6.1.120` | `058c78afdd026df518529e859605501e2a72a5ac` | **Apache-2.0** (OSS components) |
| TensorRT-LLM | `v1.2.1` | `376f7e1bd8ed543f75014309e3fd4b237e9b0e73` | **Apache-2.0** |
| vLLM | `v0.27.1` | `6e448d0ea9bf3d88d898b65449ca6dc2aec170ac` | **Apache-2.0** |
| SGLang | `v0.5.18` | `71de97b264b04dcd514cf904003028aefe9775c8` | **Apache-2.0** |
| llama.cpp | master `b10612-3-gf280b2698` | `f280b26983ad0fdb705a0d9ebf0503e76f2899b0` | **MIT** |
| stable-diffusion.cpp | master `master-827-97d2990` | `97d2990807fe6d558e395f8764198d7c7e7b411c` | **MIT** |

All twelve trees are clean (`dirty=0`) and all live under **git-ignored**
`sources/`. **No third-party source is committed to this repository** — only the
commit hashes above, from which any tree can be recreated.

---

## Per-component obligations

### Permissive, low-friction — Apache-2.0 / BSD / MIT

**nvbandwidth · nvbench · CUTLASS · Model Optimizer · vLLM · SGLang ·
TensorRT-LLM · llama.cpp · stable-diffusion.cpp · cuda-samples**

| Question | Answer |
|---|---|
| Source distribution | permitted with licence + notice retained |
| Hosted service (network use) | **no network-use clause** in Apache-2.0, BSD-3-Clause or MIT |
| Distribution obligations | Apache-2.0: retain NOTICE, state changes. BSD/MIT: retain copyright + disclaimer |
| Separate SDK/EULA needed | **no** |
| Developer Program required | **no** |
| Production licensing | none *from the code licence* |

**The caveat that actually matters for these.** The licence covers the *code*, not
what it loads. A model served through vLLM or llama.cpp carries **its own** terms,
and those are frequently the binding constraint for a hosted service. Model
licensing is a separate ledger and is not addressed here.

Apache-2.0 also carries a **patent grant** and requires **stating significant
changes** — relevant if any of these are ever patched rather than used as-is. The
`modified / unmodified` field in `licenses/README.md` exists for exactly this and
is the field nobody can reconstruct later.

### Requires a separate NVIDIA SDK download — beyond GitHub

#### TensorRT

| | |
|---|---|
| GitHub tree | Apache-2.0 — **OSS components, parsers and plugins** |
| What is missing | the **TensorRT runtime libraries and `trtexec`** are *not* in the OSS repo |
| Local state | `libnvinfer` **absent**, 0 Debian packages, `trtexec` **absent** |
| Separate EULA | **YES** — the binary SDK ships under the NVIDIA TensorRT licence |
| Hosted-service implication | **governed by the SDK EULA, not by Apache-2.0** — must be read before production |
| Verdict | **development/evaluation established; production terms NOT established** |

Submodules pull in third-party code with their own licences: **protobuf**
(BSD-3-Clause), **cub** (BSD-3-Clause), **onnx-tensorrt** (Apache-2.0), plus
googletest and google-benchmark under protobuf.

**Version note recorded rather than acted on:** NVIDIA documentation establishes
**11.1 GA with CUDA 13.3** as the default path, and that is what is checked out.
**`v11.2` exists upstream** (`1dade062a4e796c14ab6b3f32461ad694ec58951`,
2026-08-04) and is newer. It is **not selected** — being newer is not a selection
criterion, and its CUDA 13.3 pairing has not been verified here.

#### TensorRT-RTX

| | |
|---|---|
| GitHub tree | Apache-2.0 — **`demo/` and `samples/` only**, verified by listing the tree |
| What is missing | **the entire SDK** — runtime, libraries, JIT compiler |
| Separate EULA | **YES** |
| Access | requires **NVIDIA Developer Program** membership |
| Verdict | **NOT INSTALLED. NOT PRESENT.** |

> **The trap this row exists to prevent:** the OSS tree is small and clones
> cleanly, which makes it easy to record "TensorRT-RTX acquired" and later read
> that as "TensorRT-RTX available". It is neither installed nor present. Only
> samples were acquired.

### Requires NGC authentication — not configured

#### NVIDIA NIM (LLM and Visual GenAI)

| | |
|---|---|
| Delivery | container images from `nvcr.io` |
| Licence | **NVIDIA AI Enterprise / NIM terms — entirely separate from any OSS licence above** |
| Local state | **`ngc` CLI ABSENT · no `nvcr.io` auth configured · nothing pulled** |
| Container runtime | **podman 5.4.2** (docker is absent) — any NIM work must target podman |
| Development vs production | NIM commonly separates free development/evaluation from paid production entitlement |
| Verdict | **NO ENTITLEMENT ESTABLISHED. Requires user action and then confirmation.** |

**No entitlement is claimed here.** Nothing was pulled, no credential was
requested, read, printed or stored.

### Bundled under the CUDA Toolkit EULA — already installed

| Component | Version | Licence |
|---|---|---|
| CUDA Toolkit | 13.3.1 (nvcc V13.3.73) | NVIDIA CUDA Toolkit EULA |
| **Nsight Systems** | 2026.1.3.425 | NVIDIA EULA, bundled |
| **Nsight Compute** | 2026.2.1.0 | NVIDIA EULA, bundled |
| cuBLAS / cuFFT / cuRAND / cuSPARSE / cuSOLVER / cuFILE / NPP | 13.3-series | CUDA Toolkit EULA |

Both Nsight tools arrived as `cuda-nsight-systems-13-3` and
`cuda-nsight-compute-13-3`. **No separate download or Developer Program access is
needed for them** — a useful finding, since profiling tools are often assumed to
require a portal login.

The CUDA EULA permits use of the toolkit and redistribution of specified runtime
components; it is **not** a grant covering anything the toolkit compiles.

### Installed as pip wheels — easy to miss at system level

| Component | Version | Licence | Note |
|---|---|---|---|
| **cuDNN** | 9.19.0.56 | NVIDIA cuDNN licence | **wheel `nvidia-cudnn-cu13`, not a Debian package** |
| **NCCL** | 2.28.9 | BSD-3-Clause | wheel `nvidia-nccl-cu13` |
| PyTorch | 2.11.0 / +cu130 | BSD-3-Clause | |
| Triton (kernel language) | 3.6.0 | MIT | **not** NVIDIA Triton Inference Server |
| Diffusers | 0.40.0 | Apache-2.0 | already present in `symoneural-hybrid` |
| vLLM | 0.25.1 | Apache-2.0 | installed-not-serving |
| cuda-python / cuda-bindings / cuda-core | 13.3.1 / 13.3.1 / 1.0.1 | Apache-2.0 / NVIDIA | |

> **A system-level `dpkg` check reports cuDNN and NCCL as absent.** They are
> present, inside venvs, as wheels. Any statement about what this host has must
> check both layers or it will be wrong in one direction or the other — and the
> cuDNN licence applies wherever the library actually is.

---

## What is NOT covered here

- **Model weights.** Every model carries its own terms, and for a hosted service
  those are usually the binding constraint. Separate ledger, not yet written.
- **Production entitlement for TensorRT, TensorRT-RTX and NIM.** Requires reading
  the applicable NVIDIA agreements, which has not been done.
- **Modification status.** All twelve trees are pristine today (`dirty=0`). If any
  is ever patched, record it at the time — see `licenses/README.md`.

## Bottom line for hosted production

| Component class | Hosted-production licence risk |
|---|---|
| llama.cpp, stable-diffusion.cpp (MIT) | **lowest** — retain notice |
| vLLM, SGLang, TensorRT-LLM, ModelOpt, nvbandwidth, nvbench, CUTLASS | **low** — Apache-2.0/BSD, no network-use clause |
| CUDA + Nsight | **known** — CUDA EULA, already accepted in practice |
| cuDNN | **read before production** — NVIDIA-specific terms |
| **TensorRT** | **UNRESOLVED** — SDK EULA not read |
| **TensorRT-RTX** | **UNRESOLVED** — SDK not even present |
| **NIM** | **UNRESOLVED** — no entitlement established |

The three UNRESOLVED rows are the ones to settle **before** any of them becomes a
P6 selection candidate, not after.
