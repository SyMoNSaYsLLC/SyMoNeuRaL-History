# `text_gen` — a Runner-based Bento, built and containerized by CI

A BentoML service that generates text, packaged into an OCI image by `bentoml containerize`.
**There is no Dockerfile here and there must not be one** — BentoML generates it from
`bentofile.yaml`, and a hand-written one beside it would be a second source of truth that
drifts from the Bento's own manifest.

`DECISIONS.md` is the pull-request description for this change: what was decided, what the
repository said that contradicted the request's defaults, what broke on the way, and — since
this repository has **no git remote** — which claims here were verified by running them and
which could not be.

| File | |
|---|---|
| `bentoml_service_runner.py` | the service: `text_gen_runner`, `/generate`, `/status` |
| `text_gen_stub.py` | the offline fallback class — kept out of `save_model.py` on purpose |
| `save_model.py` | puts `text_gen:latest` in the local Bento store; run before every build |
| `bentofile.yaml` | what gets packed, and the image's Python and distro |
| `requirements.txt` | `bentoml==1.4.39`, pinned deliberately |
| `../../.github/workflows/bento-containerize.yml` | build → containerize → **smoke-test** → push to GHCR |

## Local development

The venv is `deploy/bento/.venv` and is gitignored (`**/.venv/`). It exists because CLAUDE.md
forbids installing into the system interpreter — that is the serving path.

```bash
cd deploy/bento
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python save_model.py                 # -> text_gen:<tag> in ~/bentoml
.venv/bin/bentoml build -f bentofile.yaml      # -> Bento
.venv/bin/bentoml serve text_gen:latest --port 3000
```

```bash
curl -s localhost:3000/status -H 'content-type: application/json' -d 'null'
curl -s localhost:3000/generate -H 'content-type: application/json' \
     -d '{"prompt": "hello", "max_tokens": 16}'
```

## Building the image on this box

This machine has **podman and buildah, no Docker** — the docker service is inactive. That is
fine; `containerize` takes a backend:

```bash
.venv/bin/bentoml containerize text_gen:latest --backend podman \
  -t localhost/symoneural-text-gen:bentoml-latest

podman run --rm -p 3000:3000 localhost/symoneural-text-gen:bentoml-latest
```

929 MB, and it holds no weights. Note that `--push` is a **buildx** passthrough, so it is not
available under `--backend podman`; push with `podman push` as a separate step. The CI workflow
uses `--backend buildx` because GitHub's runners have Docker, and separates the push for a
different reason — see decision C.

Beware: the repo's *other* image is built the house way,
`podman build -t symoneural-api -f ops/Containerfile .`, and is a different thing entirely (it
bind-mounts the repo and takes the GPU through CDI). Do not conflate them.

## Running it against the real model

The container generates nothing on its own. Point it at an OpenAI-compatible endpoint and it
forwards; leave `SYMONEURAL_LLAMA_URL` unset and it answers from a stub that says `[stub]` in its own
output and `"backend": "stub"` in the response.

Do not hand-start a `llama-server` for this. `backend/api.py` already owns that process: it
spawns `contrib/llama.cpp/build/bin/llama-server` on **127.0.0.1:8081** (`LLAMA_PORT`, api.py:164)
with the chat model and the persona LoRA, per job, taking and releasing the `chat` lease around
it. A second server started by hand would be a second tenant on a 15.92 GiB card that already
budgets ~8.2 GiB for chat, and the governor cannot arbitrate a process that never asked it for
anything.

So: bring chat up the normal way (`scripts/symoneural.sh on`, then send one request to
`/api/chat` so the server is resident), and point the container at it.

```bash
podman run --rm --network host \
  -e SYMONEURAL_LLAMA_URL=http://127.0.0.1:8081 \
  localhost/symoneural-text-gen:bentoml-latest
```

`--network host` because the endpoint is loopback-only by design — nothing in this repo opens
a port to the GPU. Without it, `127.0.0.1` inside the container is the container.

Then `"backend": "llama.cpp"` comes back in every response, with the model name the server
reports. If the server stops answering, the response says so in a `note` field rather than
quietly degrading — a silent fallback is how a broken deployment reads as a working one.

**Nothing in this container takes a GPU lease, and nothing in it may.** CLAUDE.md: *"Hold the
lock for a job, never for a process lifetime."* The lease belongs to the `llama-server` process
this forwards to. A resident Bento worker holding `chat` would lock out image and train for as
long as the container ran.

There is no GPU in CI (decision E) and no GPU in this image. `SUPPORTED_RESOURCES` on the
runnable lists `nvidia.com/gpu` only so the same Bento can be *scheduled* onto a GPU worker
later without a rebuild.

## What CI does

`.github/workflows/bento-containerize.yml`, on pushes touching `deploy/bento/**`:

1. Python 3.11, `pip install -r requirements.txt`
2. probe `bentoml --version` and whether `containerize` offers `--push`
3. lowercase the image name — GHCR rejects uppercase, and this repo is named `Symoneural`
4. `save_model.py`, then `bentoml build -f bentofile.yaml`
5. `bentoml containerize --backend buildx --load` — **load, not push**
6. run the image and call `/healthz`, `/status` **and `/generate`**
7. only then log in to GHCR and `docker push`

Step 6 is load-bearing rather than diligence-theatre. Four separate bugs in this change
produced a completely green `bentoml build`, and three of them produced a container that came
up, passed liveness, and returned a correct-looking `/status` while being unable to generate a
single token. Under `containerize --push` all four would have been published under a green
check. The table in `DECISIONS.md` lists them.

No repository secret is required: `GITHUB_TOKEN` plus `permissions: packages: write` is enough
for GHCR. A PAT is needed only if org policy forbids `GITHUB_TOKEN` package writes.

**This workflow has never run.** There is no git remote on this box, so there is no Actions
runner and no GHCR to push to. Add a remote and dispatch it manually before trusting the
`push:` trigger — and audit what is tracked first, per CLAUDE.md, because
`training/corpus.jsonl` and `training/build_dataset.py` must never leave this machine.
