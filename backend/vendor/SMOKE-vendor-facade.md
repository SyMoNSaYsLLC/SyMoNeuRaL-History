# The vendor facades: one file names each dependency — smoke record

Written after running it, not before. Every reading below was taken on this box on
**2026-08-21**, on the tree this file lands in. Task #74 item 5.

The rule this file exists for: `archive_tasks.py` reads checks, not notes, and
`exists`, `grep` and `ngrep` all ask what is *written on disk*. #74 declares nine
`ngrep`s for this item and every one of them names a path — so they go green the moment
the seven listed files are repointed and stay green for the eighth file added next week.
That is the one-token-one-file failure this task has already recorded **five** times.

## What landed

| package | vendor | the one file allowed to import it |
|---|---|---|
| `apps/studio` | `httpx` | `apps/studio/httpclient.py` |
| `apps/studio` | `fastmcp` | `apps/studio/mcpframework.py` |
| `apps/remix` | `httpx` | `apps/remix/symoneural_dj/httpclient.py` |
| `apps/ravencalc` | `sympy` | `apps/ravencalc/symbolic.py` (already existed) |

Seven consumers repointed: `studio/{inference,comfy,routes}.py`,
`symoneural_dj/{symon_client,pipeline}.py`, `symoneural_dj/connectors/{ytmusic,spotify}.py`.

**Named `httpclient.py`, not `http.py`.** `backend/DEPENDENCIES.md` says `apps/*/http.py`
and that literal path is a trap: `apps/remix/pyproject.toml:44` sets
`pythonpath = [".", "../.."]`, so `apps/remix` is a `sys.path` root and an `http.py`
there shadows the **stdlib** `http` package for everything under that rootdir — httpx
included, since httpx imports `http`. The symptom would be a collection error with no
obvious cause. DEPENDENCIES.md's row is corrected in the same commit.

**Re-export, do not wrap.** `symbolic.py` wraps sympy's functions because RavenCalc calls
a dozen named functions with stable signatures. `AsyncClient` is a class used as an async
context manager with a wide method surface; wrapping it would be a second HTTP client to
maintain. The names are bound to the upstream objects, so the client
`apps/remix/tests/conftest.py` builds with `MockTransport` and injects into
`SpotifyClient` is the same object on both sides — which is why the 28 did not move.

## The test, and why it is not the nine ngreps

`backend/apps/test_vendor_facade.py` — **6 tests**. It walks the tree rather than a file
list, and it reads the **syntax tree** rather than the text:

- `import httpx as _h` satisfies `ngrep import httpx` and is caught here. That form is
  exactly how somebody makes the check green without doing the work.
- `# httpx recomputes content-length` in a comment is *not* a violation, and a text scan
  cannot tell the difference.

`TheFacadeSurfaceIsCompleteTests` is the second half and it is the `convert_xor` test
generalised: it collects every `httpclient.<name>` the tree actually uses, off the AST,
and asserts each resolves on the facade. That defect is **live in this repo right now** —
`symbolic.py` does not re-export `convert_xor`, `ravencalc.py:89` reaches for it, and
`apps/ravencalc` has collected zero tests since `49185b8`. A facade fails whole and it
fails at *import*, so it presents as a collection abort somewhere unrelated rather than as
a failure where the bug is.

## Red first — automated, because seven breaks by hand is seven chances to leave one in

`tools/prove_vendor_facade.py` applies each break to a copy of the file's text, runs the
suite, and rolls back in a `finally`. It ends by comparing every target byte-for-byte
against the text it read at the start, and exits non-zero if any break came back green or
anything was left behind.

```
BASELINE green  6 passed in 0.30s
BREAK    RED    a shipped module imports the vendor directly
                backend/apps/studio/inference.py: 1 failed, 5 passed in 0.29s
BREAK    RED    ...and the alias form an ngrep cannot see
                backend/apps/studio/inference.py: 1 failed, 5 passed in 0.30s
BREAK    RED    the remix connector reaches past its facade
                backend/apps/remix/symoneural_dj/connectors/spotify.py: 1 failed, 5 passed in 0.29s
BREAK    RED    an incomplete re-export -- the `convert_xor` shape
                backend/apps/studio/httpclient.py: 1 failed, 5 passed in 0.29s
BREAK    RED    the remix facade drops a name its connectors annotate with
                backend/apps/remix/symoneural_dj/httpclient.py: 1 failed, 5 passed in 0.30s
BREAK    RED    the facade stops importing its vendor (rule passes, nothing works)
                backend/apps/studio/mcpframework.py: 1 failed, 5 passed in 0.31s
BREAK    RED    an exemption that no longer applies is left in EXEMPT
                backend/apps/ravencalc/ravencalc.py: 1 failed, 5 passed in 0.30s
RESTORED green  6 passed in 0.29s
TREE     clean  every file byte-identical to where it started
```

## Two of those breaks came back **green** on the first run, and both were real

Neither was a bad test. Both were the automation reporting something true that I would not
have found by reading the file.

1. **`QueryParams` commented out of the studio facade — green.** `QueryParams` is used by
   the remix connectors and by nothing in studio, so removing it from *that* facade breaks
   nothing. The break was repointed at `HTTPStatusError`, which `routes.py:651` actually
   catches. The finding is that a facade's surface is per-package and the proof has to
   remove a name that package really uses.

2. **`FastMCP = object` in `mcpframework.py` — green, and this one was a defect in my own
   facade.** `version()` did `import fastmcp` *inside the function*, so the AST scan still
   found the vendor imported and `test_every_facade_exists_and_does_import_its_vendor`
   stayed green over a facade that no longer had a server class behind it. One import site
   has to mean one import site: the module now does `import fastmcp` at the top and binds
   `FastMCP = fastmcp.FastMCP`, and the break goes red.

## The graceful-degradation path, which is the only way this could break serving

`fastmcp` must never be installed into the system interpreter — that is the serving path.
The facade deliberately does **not** catch `ImportError`; `mcp_server.py` does, and turns
it into the message naming the venv to build, because that is the only place that can name
the entrypoint to re-run. Both halves measured:

```
$ python3 backend/apps/studio/mcp_server.py          # system interpreter, no fastmcp
fastmcp is not importable.
...
    /home/google/Symoneural/backend/apps/studio/.venv/bin/python .../mcp_server.py
--- exit=1

$ backend/apps/studio/.venv/bin/python -c "...from apps.studio.mcpframework import FastMCP, version"
ok 3.4.7 FastMCP
```

## Suites

```
cd backend/apps/remix && python3 -m pytest -q              28 passed in 0.45s
cd backend && python3 -m pytest apps/studio -q ...        392 passed in 49.73s
```

The 28 are the ones that inject their own `httpx` client, and they are the reading that
says the re-export is faithful rather than merely present.

## What is NOT claimed here

`gpu-governor.sh` still says `ComfyUI` three times and that is correct — see the `note:`
on #74. Only the `666 MiB` line was ours; the other three name Garrett's own upstream
render UI out of `references/`, and our brand name would misdescribe a foreign process.
