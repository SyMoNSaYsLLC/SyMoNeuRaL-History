"""Put a `text_gen` model in the local BentoML store, offline, in about a second.

`bentoml build` packs models from the store, not from the working directory, so a build
against an empty store fails with "model text_gen:latest not found" rather than producing a
Bento with a missing tensor -- which is the correct failure, but it means CI has to run this
first. That is the whole reason this file exists as a separate step in the workflow.

**What is saved is a generation *policy*, not weights.** The real language model on this box is
`contrib/llama.cpp/build/bin/llama-server` serving symon-1.0-7b-q4_k_m with the persona
LoRA, behind `scripts/gpu-governor.sh`; it is 4.4 GB and it is not going into a container image
built by a CPU-only CI runner. The runner in `bentoml_service_runner.py` calls that server when
one is reachable and falls back to the deterministic stub saved here when one is not, and it
says which of the two answered in every response. Per CLAUDE.md's honesty rules, stub output is
never returned as if a model produced it.

The class itself lives in `text_gen_stub.py`, not here, and that is load-bearing rather than
tidiness -- cloudpickle pickles a `__main__`-defined class by value, which shipped host
bytecode into an image with a different Python and broke the first real request. The reasoning
is written out in full at the top of that file.

Run:  .venv/bin/python save_model.py
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import bentoml  # noqa: E402

from text_gen_stub import StubTextGen  # noqa: E402


def main() -> str:
    saved = bentoml.picklable_model.save_model(
        "text_gen",
        StubTextGen(),
        signatures={"generate": {"batchable": False}},
        metadata={
            "role": "offline fallback for text_gen_runner",
            "real_backend": "llama.cpp llama-server, OpenAI-compatible, via SYMONEURAL_LLAMA_URL",
            "weights_included": False,
        },
    )
    print(saved.tag)
    return str(saved.tag)


if __name__ == "__main__":
    main()
