"""The `text_gen_runner` Bento service.

This is deliberately written against BentoML's **Runner** API -- `bentoml.legacy.Runner`,
`bentoml.legacy.Runnable`, `bentoml.legacy.Service` and `bentoml.io` -- because a runner named
`text_gen_runner` is what was asked for. All four are present and working in BentoML 1.4.39 and
all four emit `BentoMLDeprecationWarning`: they moved under `bentoml.legacy` in 1.4 and the
warnings say they will be removed. `requirements.txt` therefore pins `bentoml==1.4.39` rather
than a range. An unpinned install picks up the release that finally deletes them and the build
fails at import with `AttributeError: module 'bentoml' has no attribute 'legacy'` -- from a file
nobody edited, which is the worst way for this to break.

The modern equivalent is `@bentoml.service` on a class with `@bentoml.api` methods, and there
are no runners in it at all; the class *is* the unit of scaling. If this outlives the 1.4 line,
that is the port, and it is small: the Runnable becomes the service class and `svc.api`
decorators become `bentoml.api`.

## What actually generates text

Two backends, and the response always names which one answered:

* **`llama.cpp`** -- if `SYM_LLAMA_URL` points at a reachable OpenAI-compatible endpoint, the
  runner POSTs `/v1/chat/completions` to it. That is the repo's real inference path
  (`contrib/llama.cpp/build/bin/llama-server`, Qwen2.5-7B-Instruct-Q4_K_M + persona LoRA).
* **`stub`** -- otherwise, the deterministic echo saved by `save_model.py`. No weights are in
  this image; a CPU-only CI runner builds it and a 4.4 GB GGUF is not going in.

Nothing here loads the GGUF itself, and nothing here takes a GPU lease. CLAUDE.md is explicit
that everything touching the card goes through `scripts/gpu-governor.sh` and that the lock is
held for a job, never for a process lifetime -- a resident Bento worker holding `chat` would
lock out image and train for as long as the container ran. The lease belongs to the
`llama-server` process this talks to, not to this.

Serve locally:

    .venv/bin/bentoml serve bentoml_service_runner:svc --port 3000
    curl -s localhost:3000/generate -H 'content-type: application/json' \
         -d '{"prompt": "hello", "max_tokens": 16}'
"""
from __future__ import annotations

import json
import os
import typing
import urllib.error
import urllib.request
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Import the stub class *now*, at module import, and never mind that nothing on this line uses
# it. The saved model pickles `StubTextGen` by reference, so unpickling it runs
# `__import__("text_gen_stub")` -- and by the time that happens, `text_gen_stub` is no longer
# importable.
#
# Inside a built Bento this file lives in `/home/bentoml/bento/src`, and BentoML puts that
# directory on `sys.path` only *while* it imports this module: the insert is scoped to the load
# and removed on the way out. So a sibling import works here and fails later, and "later" is
# when the runner worker unpickles the model:
#
#   File ".../bentoml_service_runner.py", line 100, in __init__
#   ModuleNotFoundError: No module named 'text_gen_stub'
#
# Importing eagerly puts the module in `sys.modules`, where `__import__` finds it without
# consulting `sys.path` at all -- which is the only version of this that does not depend on
# BentoML's path bookkeeping.
#
# The obvious-looking fix does not work, and it is worth writing down why. This:
#
#     _HERE = os.path.dirname(os.path.abspath(__file__))
#     if _HERE not in sys.path:              # <- BentoML's own insert is already there
#         sys.path.insert(0, _HERE)          # <- so this never runs
#
# is a no-op, because the guard sees the string BentoML inserted, skips, and then BentoML's
# context manager removes that one entry on exit. The path is restored to not containing it and
# the import fails exactly as before. An unguarded second insert would survive; an eager import
# is simpler and does not leave a duplicate on the path.
#
# The failure mode this produces is worth knowing: the runner worker exits, and the API server
# process stays up answering `/healthz` and `/status` perfectly well, because neither touches
# the runner. A smoke test that stops at "the container responds" calls that image healthy.
# `/generate` is the only request that proves otherwise, which is why the workflow sends one.
import text_gen_stub  # noqa: F401  -- registers the class for unpickling; see above

import bentoml  # noqa: E402
from bentoml.io import JSON  # noqa: E402

MODEL_TAG = os.environ.get("SYM_BENTO_MODEL", "text_gen:latest")
LLAMA_URL = os.environ.get("SYM_LLAMA_URL", "").rstrip("/")
LLAMA_TIMEOUT = float(os.environ.get("SYM_LLAMA_TIMEOUT", "60"))

text_gen_model = bentoml.picklable_model.get(MODEL_TAG)


class TextGenRunnable(bentoml.legacy.Runnable):
    """The unit BentoML schedules. One instance per worker.

    `SUPPORTED_RESOURCES` lists the GPU even though nothing here allocates one: it is what lets
    the same Bento be scheduled onto a GPU worker later without a rebuild, and it costs nothing
    on a CPU-only runner. `SUPPORTS_CPU_MULTI_THREADING` is true because both backends are
    I/O-bound -- an HTTP call or a string split -- so threads are not fighting over a GIL doing
    arithmetic.

    The name is `SUPPORTED_RESOURCES`, not `SUPPORTED_RESOURCE_TYPES`. This was written wrong
    the first time and `bentoml build` accepted it happily; the scheduling strategy reads the
    attribute at *serve* time, so the failure was `AttributeError: type object
    'TextGenRunnable' has no attribute 'SUPPORTED_RESOURCES'` from inside `strategy.py`, after
    a green build. That is the entire argument for the smoke-test step in the workflow: a Bento
    that builds is not a Bento that serves, and only one of those two facts is worth a green
    check.
    """

    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self) -> None:
        super().__init__()
        self.model = bentoml.picklable_model.load_model(text_gen_model)

    @bentoml.legacy.Runnable.method(batchable=False)
    def generate(self, prompt: str, max_tokens: int = 64) -> dict:
        """Answer from llama.cpp if it is there, from the stub if it is not, and say which.

        `batchable=False` is not a placeholder. Batching here would mean holding request A
        while request B arrives, and the backend it forwards to serves one stream at a time
        behind a GPU mutex -- so the queue would form twice, once in BentoML and once in
        `llama-server`, and the first queue would only add latency.
        """
        if LLAMA_URL:
            answered = self._via_llama(prompt, max_tokens)
            if answered is not None:
                return answered
        out = dict(self.model.generate(prompt, max_tokens))
        if LLAMA_URL:
            # Say so. A silent fallback is how a broken deployment reads as a working one.
            out["note"] = f"SYM_LLAMA_URL={LLAMA_URL} did not answer; this is stub output"
        return out

    def _via_llama(self, prompt: str, max_tokens: int) -> dict | None:
        body = json.dumps({
            "messages": [{"role": "user", "content": str(prompt)}],
            "max_tokens": int(max_tokens),
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{LLAMA_URL}/v1/chat/completions", data=body,
            headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=LLAMA_TIMEOUT) as fh:
                payload = json.load(fh)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            # Unreachable, refused, timed out, or answering something that is not JSON. All
            # four mean the same thing to a caller: this backend is not available right now.
            return None
        usage = payload.get("usage") or {}
        choice = (payload.get("choices") or [{}])[0]
        return {
            "text": (choice.get("message") or {}).get("content", ""),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "backend": "llama.cpp",
            "model": payload.get("model"),
        }


#: The name is load-bearing -- it is what the workflow, the smoke test and the request all say.
text_gen_runner = bentoml.legacy.Runner(
    TextGenRunnable, name="text_gen_runner", models=[text_gen_model])

svc = bentoml.legacy.Service("text_gen", runners=[text_gen_runner])


@svc.api(input=JSON(), output=JSON(), route="/generate")
async def generate(payload: typing.Any) -> dict:
    """`{"prompt": str, "max_tokens": int}` in, the runner's dict out.

    A non-dict body is answered with an error object rather than a 500 traceback: the first
    thing anyone does with a new endpoint is curl it with a bare string, and a stack trace is a
    poor way to learn the shape.
    """
    if not isinstance(payload, dict):
        return {"error": "expected a JSON object like "
                         '{"prompt": "hello", "max_tokens": 64}',
                "got": type(payload).__name__}
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "'prompt' is required and must be a non-empty string"}
    try:
        max_tokens = int(payload.get("max_tokens", 64))
    except (TypeError, ValueError):
        return {"error": f"'max_tokens' must be an integer, got "
                         f"{payload.get('max_tokens')!r}"}
    return await text_gen_runner.generate.async_run(prompt, max(1, max_tokens))


@svc.api(input=JSON(), output=JSON(), route="/status")
async def status(_: typing.Any = None) -> dict:
    """What is wired up, without generating anything.

    Not `/healthz`: BentoML reserves that name, along with `/livez`, `/readyz` and `/metrics`,
    and `bentoml build` refuses the Bento outright rather than shadowing one -- "Reserved API
    name: 'healthz' is reserved for infra endpoints". Its `/healthz` answers whether the server
    process is up. This answers a different and more useful question -- whether the runner
    loaded its model and which backend it will use -- and the smoke test reads both, because
    "the container starts" and "the runner works" are separate claims.
    """
    return {
        "service": "text_gen",
        "runner": "text_gen_runner",
        "model": str(text_gen_model.tag),
        "llama_url": LLAMA_URL or None,
        "backend": "llama.cpp" if LLAMA_URL else "stub",
        "bentoml": bentoml.__version__,
    }
