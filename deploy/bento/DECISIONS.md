# BentoML build + containerize — decision record

This file is the pull-request description. There is no pull request, and there cannot be one:
`git remote -v` in this repository is empty, and CLAUDE.md says that is on purpose — *"There is
currently **no git remote** — history never leaves this box, which is doing a lot of the
protecting."* No remote means no GitHub Actions run, no GHCR push, and no PR to attach a green
check to. The request allowed for exactly this outcome — *"a green CI run or a documented reason
why CI could not push"* — and this is the documented reason.

So the workflow file is written and committed, and it has never executed. Everything below
distinguishes **verified here** from **written but unrun**, because the difference is the whole
value of the document.

---

## What the repository said that the request's defaults did not expect

Five things, found by the inspection the request specified, in the order it specified.

1. **No git remote, and no `.github/` directory before this change.** Covered above. The
   `.github/workflows/` directory is created by this change and this is its only file.

2. **No Docker on this box.** `/usr/bin/podman` (5.4.2) and `/usr/bin/buildah` are installed;
   the docker service is `inactive`. `bentoml containerize` shells out to a builder backend and
   accepts `--backend podman`, so the local path works — that is how the image below was built
   and smoke-tested. The workflow uses `buildx` because `ubuntu-latest` has Docker and does not
   have podman configured; the two are not in conflict, they are the same command with a
   different `--backend`.

3. **This repository already builds containers, and not this way.** `ops/Containerfile` +
   `podman build -t symoneural-api -f ops/Containerfile .` + `scripts/container-run.sh` is the
   house convention, and that Containerfile is hand-written with a long comment explaining
   exactly why it is Debian trixie and not an NVIDIA Ubuntu image. The request says not to add a
   hand-written Dockerfile and none was added — but note that this image is now the *second*
   container convention in the repo, one generated and one hand-written. They are for different
   things (the API image bind-mounts the repo and takes the GPU via CDI; this one is a
   self-contained service) and both are defensible, but somebody should decide whether that
   stays true.

4. **BentoML was already evaluated and rejected for this stack.** `docs/integration-sources.md`,
   lines 34–35, records the verdicts: LLM serving went to *"llama.cpp `llama-server` + persona
   LoRA, started on demand inside `gpu.hold(\"chat\")`"* over "vLLM, Triton, **BentoML**,
   KServe", and the model registry went to *"`run/registry.json`, built out-of-band by
   `tools/build_registry.py`"* over "MLflow, **BentoML**". Both are marked done. This change does
   not reverse either decision and does not touch the serving path: nothing in `backend/`
   imports anything here, `api.py` is unmodified, and no rack row was added. It is a build
   pipeline that produces an artefact, sitting beside the stack rather than inside it.

5. **The GPU is a mutex, so this service must not hold one.** CLAUDE.md: *"Hold the lock for a
   job, never for a process lifetime."* A resident Bento worker holding `chat` would lock out
   image and train for as long as the container ran. The runner therefore loads no weights and
   takes no lease; it forwards to a `llama-server` that has its own lease, or falls back to a
   labelled stub.

---

## Decisions A–E

### A — Image name and registry

**`ghcr.io/<owner>/<repo>:bentoml-latest`**, as defaulted, plus a second immutable tag
`:<git sha>`. One adaptation, and it is not cosmetic: the workflow lowercases
`${{ github.repository }}` before using it.

GHCR rejects any uppercase component of an image path, and this repository is named
**`Symoneural`**. `ghcr.io/${{ github.repository }}:bentoml-latest` would therefore fail with
`invalid reference format` — at the push step, after a full build, which is a slow and confusing
place to learn it. `tr '[:upper:]' '[:lower:]'` in the `Derive image name` step.

The `:<git sha>` tag exists because `bentoml-latest` is mutable and a rollback needs something
that is not.

### B — FAST vs BAKE

**FAST.** The image is built inside the job, from the checkout, by one `bentoml containerize`
call. BAKE buys multi-target matrices and shared build contexts across targets; there is one
target and one context, so it would be indirection with nothing on the other end of it. Revisit
if a GPU variant is added — two targets is where BAKE starts paying.

### C — Does `bentoml containerize` support `--push`?

**Yes in 1.4.39 — and the workflow deliberately does not use it.**

Measured, not assumed: `bentoml containerize --help` lists `--push` as *"(Equivalent to
`--opt push`): Shorthand …"*. That wording is the important part. `--push` is a passthrough to
buildx, not a BentoML feature, so it exists only when the backend is buildx or docker. With
`--backend podman` — the only backend available on this box — it is not accepted, and the push
is a separate `podman push`. The workflow probes for it anyway (`Bento CLI version and
containerize capabilities`) and surfaces the answer in the job summary, so the fallback
condition is visible rather than inferred.

The reason it is not used: **a `--push` build never holds the image locally, so nothing between
the build and the registry can test it.** That is not a theoretical concern here. See *What
broke* below — three separate bugs in this change produced a completely green `bentoml build`
and an image that did not work, and two of them produced a container that answered `/healthz`
and `/status` correctly while being unable to generate a single token. Under `--push` all three
would have been published under a green check.

So: `containerize --backend buildx --load`, then smoke-test, then `docker push`. Same tooling,
same generated Dockerfile, no hand-written Dockerfile anywhere, with the one gate that matters
inserted in the middle.

### D — Python version

**3.11**, in both `bentofile.yaml` (`docker.python_version`) and the workflow's
`setup-python`. Not 3.13, which is what this box runs.

BentoML's published base images and the wheels it resolves are best-covered on 3.11, and the
service itself is stdlib plus `bentoml` and runs on either. The two must match each other: the
model in the store is pickled by the builder and unpickled by the image, and pickle
compatibility across minor versions is not something to leave to luck — which is precisely how
the second bug below happened.

### E — CI hardware

**CPU-only.** GitHub-hosted runners have no GPU, and nothing in this image needs one: no weights
are packed, and the GPU path is an HTTP call to a `llama-server` that lives elsewhere. GPU run
instructions are in `README.md` under *Running it against the real model*.

---

## Adaptations not in the request

### F — Runner-based, on a version where Runners are deprecated

The request names a **Runner**-based service (`text_gen_runner`), and that is what was built:
`bentoml.legacy.Runner`, `bentoml.legacy.Runnable`, `bentoml.legacy.Service`, `bentoml.io.JSON`.
All four work in 1.4.39 and all four emit `BentoMLDeprecationWarning` — they moved under
`bentoml.legacy` in 1.4 and the warnings say they will be removed.

`requirements.txt` therefore pins `bentoml==1.4.39` rather than a range. An unpinned install
eventually picks up the release that deletes them, and the build fails at import with
`AttributeError: module 'bentoml' has no attribute 'legacy'` from a file nobody edited. Bump the
pin deliberately, with the port in the same commit; the modern form is `@bentoml.service` on a
class with `@bentoml.api` methods and no runners at all.

### G — The files live in `deploy/bento/`, not the repo root

The request lists `bentofile.yaml`, `bentoml_service_runner.py`, `save_model.py` and
`requirements.txt` without a directory, which reads as the repo root. This repo's root is
already 20-odd entries and everything else of this kind is namespaced (`ops/`, `tools/`,
`scripts/`, `backend/apps/<app>/`). Four loose files at the root — including a
`requirements.txt` that is *not* the repo's requirements and would be read as if it were —
is the larger change to repo structure, not the smaller one. One new directory, five files,
nothing at the root.

### H — `/status`, not `/healthz`

`bentoml build` refuses a Bento with an API named `healthz`: *"Reserved API name: 'healthz' is
reserved for infra endpoints"* (also `livez`, `readyz`, `metrics`). BentoML's own `/healthz`
answers whether the server process is up. The service's `/status` answers a different question —
did the runner load its model, and which backend will answer — and the smoke test reads both.

### I — There are no weights in this image

`save_model.py` saves a generation *policy*, not a model: a deterministic echo that prefixes its
output with `[stub]`. The real model is 4.4 GB and is not going into an image built by a
CPU-only runner. The runner prefers a real `llama-server` when `SYM_LLAMA_URL` is set and
**names the backend that answered in every response**, including a `note` field when it fell
back. Per CLAUDE.md's honesty rules, stub output is never returned as if a model produced it,
and the stub deliberately does not try to sound like one — a stub that produced plausible prose
would make "is the real backend wired up?" unanswerable.

### J — Secrets

**None required.** `GITHUB_TOKEN` is minted per run and the `packages: write` permission in the
workflow is what makes it sufficient for GHCR. A repository secret is needed only if an org
policy forbids `GITHUB_TOKEN` package writes, in which case swap in a PAT as `GHCR_TOKEN`. This
could not be checked — there is no remote and therefore no org policy to read.

---

## What broke, and what caught it

Four bugs, all of which produced a completely green `bentoml build`.

| Bug | Symptom | Caught by |
|---|---|---|
| `SUPPORTED_RESOURCE_TYPES` written where BentoML's scheduler reads `SUPPORTED_RESOURCES` | `AttributeError` from inside BentoML's `strategy.py`, at **serve** time | `bentoml serve` locally |
| `StubTextGen` defined in `save_model.py`, so cloudpickle pickled it **by value** — host 3.13 bytecode loaded by a 3.11 image | `SystemError: no locals when deleting 'split'`, pointing at a line that is fine | running the container and calling `/generate` |
| `text_gen_stub` not importable at runner-init time — BentoML puts `src/` on `sys.path` only *while* it imports the service module, then removes it | `ModuleNotFoundError` in the runner worker; **the API process stayed up and answered `/healthz` and `/status` normally** | calling `/generate` |
| The first fix for that — `if _HERE not in sys.path: sys.path.insert(0, _HERE)` — is a **no-op**: the guard sees the string BentoML itself inserted, skips, and BentoML then removes that entry on the way out | byte-identical symptom to the row above, from code that looks like it fixes it | calling `/generate` again |

The last three are the argument for the shape of the smoke test. Three of these four images
came up, passed liveness, and returned a correct-looking `/status` — including the model tag
and the runner name — while being unable to generate a single token. Only a real `/generate`
call told them apart from a working image.

The fix that holds is an eager `import text_gen_stub` at the top of the service module: it puts
the module in `sys.modules`, where unpickling's `__import__` finds it without consulting
`sys.path` at all.

---

## Verified here / not verifiable here

**Verified on this box**, by running it:

- `bentoml --version` → `1.4.39`
- `bentoml containerize --help` lists `--push`; backends `buildctl, podman, buildah, docker, nerdctl, buildx`
- `python save_model.py` → `text_gen:<tag>` in the local store
- `bentoml build -f bentofile.yaml` → `Successfully built Bento(tag="text_gen:…")`
- `bentoml serve` → `/status` and `/generate` answer; the `llama.cpp` branch was exercised
  against a fake OpenAI-compatible endpoint and returned `"backend":"llama.cpp"`; killing that
  endpoint returned `"backend":"stub"` **with the `note` field saying so**
- `bentoml containerize --backend podman` → `localhost/symoneural-text-gen:bentoml-latest`, 929 MB
- `podman run` + `/healthz` + `/status` + `/generate` against the built image
- **the whole chain again from an empty model store**, which is the state CI starts in: `~/bentoml`
  moved aside, then `save_model.py` → `bentoml build` → tag extraction *via the exact
  `bentoml list … -o json | python -c …` the workflow runs* → `containerize` → `podman run`. The
  fresh image answered `/healthz` 200 and returned
  `{"text":"[stub] ci smoke test","prompt_tokens":3,"completion_tokens":3,"backend":"stub"}`, and
  `/status` reported the newly-saved model tag rather than a stale one. This matters because two of
  the four bugs below were invisible against a store that already had a good artefact in it.

**Not verifiable here**, because there is no remote:

- that the workflow's YAML is accepted by GitHub's parser (it parses as YAML, which is weaker)
- `actions/checkout@v4`, `setup-python@v5`, `setup-buildx-action@v3`, `login-action@v3` resolving
- GHCR authentication, the `packages: write` scope, and org package policy
- the `docker push` itself, and therefore the pushed image's digest
- `--backend buildx` specifically; only `--backend podman` was exercised

To make it verifiable: add a remote, push the branch, and run the workflow on `workflow_dispatch`
before trusting the `push:` trigger. CLAUDE.md asks for an audit of what is tracked *before* a
remote is ever added — `training/corpus.jsonl` and `training/build_dataset.py` must never leave
this box.
