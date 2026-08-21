#!/usr/bin/env python3
"""`api:app` on a spare port with a governor that always refuses. R-173.

The request under test is *a visitor asking for chat while something else holds the card*.
On this box that is not a state a test may create: there is one GPU, one cross-process
lock, and the live service on :8800 shares both -- so contending the card for real would
answer 503 to every actual visitor for as long as the test ran, which is the failure R-171
already caused here once.

So the card is left alone and the *governor* is replaced. `api.GOVERNOR` is repointed at a
stub that exits non-zero on `acquire`, which is precisely the condition
`GpuQueue.hold()` turns into a 503:

    rc, _out, _err = await run(str(GOVERNOR), "acquire", surface, ...)
    if rc != 0:
        raise HTTPException(503, "Something else is using the GPU right now -- ...")

Everything else is the shipped path: the real app, the real handler, real uvicorn, a real
socket. What is being asserted is *when* the exception is raised relative to the response
headers, and that is settled by the wire, not by the governor.

    python3 tests/chat-contention-harness.py &     # 127.0.0.1:8896
    curl -i -X POST http://127.0.0.1:8896/api/chat -H 'Content-Type: application/json' \
         -d '{"prompt":"hello","max_tokens":8}'
    kill %1

The stub also makes this harness safe to run with the service up, which is the only way
anyone will actually run it.

`grant` mode is the second half, and it answers a different question: does the card come
back when the *visitor* goes away? There the stub governor succeeds and appends a line per
call to `$SYMONEURAL_HARNESS_LOG`, so `acquire chat` with no matching `release chat` is a
leaked lease, readable from outside the process. The engine is stubbed too -- an endless
token stream that never ends on its own -- because a generator that finishes by itself
cannot demonstrate anything about a generator that does not.

    SYMONEURAL_HARNESS_MODE=grant SYMONEURAL_HARNESS_LOG=/tmp/gov.log \
        python3 tests/chat-contention-harness.py 8896 &
"""
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8896
MODE = os.environ.get("SYMONEURAL_HARNESS_MODE", "refuse")
LOG = os.environ.get("SYMONEURAL_HARNESS_LOG", "")

# The stub. `acquire` fails, `release` and everything else succeed -- a governor that says
# "somebody else has it" and nothing more. It must be written before api is imported only
# for tidiness; GOVERNOR is rebound after the import either way.
_tmp = tempfile.mkdtemp(prefix="symoneural-contention-")
stub = pathlib.Path(_tmp) / "gpu-governor.sh"
if MODE == "grant":
    if not LOG:
        LOG = str(pathlib.Path(_tmp) / "governor.log")
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "# Stub governor: every call succeeds, and every call is written down. The log is\n"
        "# the whole point -- a lease that is never released is an acquire with no release.\n"
        f'printf "%s %s\\n" "${{1:-}}" "${{2:-}}" >> {LOG}\n'
        "exit 0\n")
else:
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "# Stub governor: the card is held by somebody this process cannot see.\n"
        'case "${1:-}" in\n'
        '  acquire) echo "stub: card is held" >&2; exit 1 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n")
stub.chmod(0o755)

import api  # noqa: E402  -- path has to be set first

api.GOVERNOR = stub

if MODE == "grant":
    # The engine, replaced by something that cannot finish. `chat_deltas` normally reads
    # llama-server until [DONE]; here it yields forever at a readable pace, so the only
    # ways this stream can end are the ones under test.
    async def _endless(messages, max_tokens, temperature):
        import asyncio
        while True:
            yield "tok "
            await asyncio.sleep(0.2)

    async def _ready():
        return True

    async def _no_calc(prompt):
        return None

    api.chat_deltas = _endless
    api.start_llama = _ready
    api.anticipate = _no_calc
    print(f"harness: governor stubbed at {stub}, mode=grant, log={LOG}", file=sys.stderr)
else:
    print(f"harness: governor stubbed at {stub}, mode=refuse", file=sys.stderr)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api.app, host="127.0.0.1", port=PORT, log_level="warning")
