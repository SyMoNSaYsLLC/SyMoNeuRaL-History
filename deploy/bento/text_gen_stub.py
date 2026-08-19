"""The offline stand-in the runner falls back to, in its own importable module.

**This class must not live in `save_model.py`.** `bentoml.picklable_model` serialises with
cloudpickle, and cloudpickle's rule is: a class defined in `__main__` is pickled *by value* --
its compiled bytecode goes into the model file -- while a class importable from a real module
is pickled *by reference*, as "import text_gen_stub, take StubTextGen".

`save_model.py` is run as a script, so `__main__` is what it was, and by-value is what happened.
The host that built the model runs Python 3.13; the image runs 3.11 (see bentofile.yaml,
decision D). Bytecode is not portable across minor versions, so the container came up healthy,
answered `/status` correctly, and then failed the first real request with

    SystemError: no locals when deleting 'split'

out of `self.model.generate(...)` -- an error that says nothing whatsoever about pickling and
points at a line that is fine. Moving the class here makes the pickle a reference, the source
travels in the Bento as source, and the image's own interpreter compiles it.

The general form, worth remembering beyond this file: **never define a class you intend to
pickle in the module you run as a script.**
"""
from __future__ import annotations


class StubTextGen:
    """A deterministic, offline stand-in for a language model.

    It does not attempt to sound like one. It echoes the prompt back with a fixed frame and
    reports its token accounting honestly, so a caller that gets stub output can tell at a
    glance that it did. A stub that produced plausible prose would make "is the real backend
    wired up?" unanswerable, and that is the one question a smoke test of this image exists to
    answer.
    """

    version = 1

    def generate(self, prompt: str, max_tokens: int = 64) -> dict:
        words = str(prompt).split()
        kept = words[: max(1, int(max_tokens))]
        return {
            "text": "[stub] " + " ".join(kept),
            "prompt_tokens": len(words),
            "completion_tokens": len(kept),
            "backend": "stub",
        }
