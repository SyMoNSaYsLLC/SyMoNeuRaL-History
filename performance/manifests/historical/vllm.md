# Historical: vLLM

**Recovered 2026-08-24. Read-only forensic pass. Nothing was installed, loaded or run.**

> ## HISTORICAL VLLM EXECUTION CONFIRMED
> ## NUMERIC PERFORMANCE BASELINE NOT RECOVERED
>
> The evidence supports this distinction precisely, and the two halves have very
> different grades. **Installation and configuration are Grade A/B. There is no
> benchmark result at any grade.** Not a weak one — none.

## IDENTITY

| Field | Value | Grade |
|---|---|---|
| project | vLLM | **A** |
| **installed version** | **0.25.1** | **A** |
| install path | `/home/google/.venvs/vllm` | **A** |
| dist-info | `vllm-0.25.1.dist-info` present | **A** |
| Python | 3.12.13 | **A** |
| torch | **2.11.0+cu130** (CUDA 13.0) | **A** |
| created | 2026-07-20 by `uv 0.11.27` | **B** |
| upstream commit | not recorded — installed as a wheel, not a source checkout | **E** |

Read directly off disk: `vllm.__version__` → `0.25.1`, `torch.__version__` →
`2.11.0+cu130`. This is Grade **A** — a live interpreter reporting its own
package metadata.

**Note the CUDA mismatch, recorded rather than resolved:** torch in this venv is
built against **CUDA 13.0** while the system toolkit is **13.3**. That is
normally fine (the driver is newer than the runtime), but it is a real
configuration fact and belongs in any P2 result that uses this venv.

## RUNTIME STATE — the decisive finding

`docs/ops/RUNTIME-PROFILES.md:43` classifies vLLM as:

> **`installed-not-serving`**

And `:47-50` carries a **correction record** that is itself the strongest single
piece of evidence in this file:

> *"The vLLM row read **absent** — 'Not on disk' — and that was **false when it
> was written**, on 2026-08-22 at `7a4e5c98`. **vLLM 0.25.1** lives in
> `/home/google/.venvs/vllm`, created 2026-07-20 (three weeks earlier) by
> `uv 0.11.27`. It imports, `torch 2.11.0+cu130`,
> `torch.cuda.is_available()` **True**, device **RTX 5070 Ti**."*

Grade **B** (documented, machine-verified at the time, and independently
re-verified today). It establishes: vLLM is installed, it imports, it can see the
GPU. It establishes **nothing about throughput**.

## MODEL / WORKLOAD

| Field | Value | Grade |
|---|---|---|
| model id served | **`symon`** | **B** |
| model file / revision / quantisation | **not recorded anywhere** | **E** |
| max-model-len | not recorded | **E** |
| gpu-memory-utilization | not recorded | **E** |
| tensor-parallel size | not recorded | **E** |
| KV-cache configuration | not recorded | **E** |
| scheduler / batching settings | not recorded | **E** |
| speculative decoding | not recorded | **E** |

## RUNTIME / SERVICE CONFIGURATION

This is the part that survives well, and it survives in *client* code rather than
in a launch script.

| Field | Value | Grade | Source |
|---|---|---|---|
| API shape | OpenAI-compatible | **B** | `backend/apps/remix/README.md:4` |
| port | **9001**, loopback only | **B** | `symoneural_dj/config.py:41` — `SYMON_URL` default `http://127.0.0.1:9001` |
| model id | `symon` | **B** | `remix/README.md:10` |
| auth | `VLLM_API_KEY` **env lookup** | **B** | see credentials below |
| topology | `iOS → symoneural_dj :8090 → symon :9001 (loopback)` | **B** | `remix/README.md:10` |
| **launch command** | **NOT RECOVERED** | **E** | — |
| gpu-governor interaction | *"Nothing listens on :8080 or :9001 between"* runs — the GPU mutex gates it | **B** | `backend/apps/gateway/README.md:130` |

**No `vllm serve` invocation survives anywhere on this box.** The port, the model
id and the API shape are all recoverable from the *consumer* side; the server
side is not. That is why launch configuration is graded **PARTIAL**.

## CREDENTIALS

**CREDENTIAL-LIKE MATERIAL: NONE FOUND WITH A LITERAL VALUE.**

`VLLM_API_KEY` is referenced in 18 files. Every one is an **environment lookup or
prose reference** — no literal assignment with an inline value exists in any of
them. Checked with a pattern matching `VLLM_API_KEY=<6+ chars>`; zero hits.

No `.env` file containing vLLM material exists. The two `.env*` files on the box
are `src/oss/sentry/.envrc` and an unrelated `.env.example`, neither vLLM.

No value was printed, copied or committed during this recovery. **No rotation
action is indicated** on the basis of this evidence, because no key was found.

## RESULTS

| Measurement | Value | Grade |
|---|---|---|
| throughput | **NOT AVAILABLE** | **E** |
| latency (any percentile) | **NOT AVAILABLE** | **E** |
| TTFT | **NOT AVAILABLE** | **E** |
| concurrency tested | **NOT AVAILABLE** | **E** |
| tokens/sec | **NOT AVAILABLE** | **E** |
| any numeric benchmark at all | **NOT AVAILABLE** | **E** |

Searched: every `.md`, `.json`, `.csv`, `.py`, `.sh` in the production repo
outside `references/`; the frozen research repo; `experiments/`; the venv itself.
**No vLLM benchmark output, report, CSV or logged figure exists.**

**No number is invented here.** The brief was explicit that no defensible
historical vLLM figure exists in the trusted record, and this recovery confirms
it independently rather than restating it.

## MISSING

- every performance figure — **E**
- `vllm serve` launch command and all serving flags — **E**
- which model file `symon` resolved to, and its quantisation — **E**
- context length, memory utilisation, batching, KV, speculative settings — **E**
- upstream commit (wheel install, so none exists) — **E**
- when it last actually served — **E**

## REPRODUCTION STATUS

**INSUFFICIENT EVIDENCE** for a performance comparison.
**MOSTLY RECONSTRUCTABLE** as a *service configuration*.

Concretely:

- **Can we stand up an OpenAI-compatible vLLM on :9001 with model id `symon`?**
  Yes — port, model id, API shape and auth mechanism are all evidenced, and the
  package is installed and imports.
- **Can we compare that against a historical vLLM baseline?** **No.** There is
  no baseline. Any vLLM number produced in P2 is a *first* measurement.

That asymmetry is the useful conclusion. vLLM does not arrive at P2 with a
number to beat; it arrives needing one.
