# SWEEP-READY — §3/§4/§6 pre-resolved, apply-only

Companion to `REVIEW-LOG.md`. Two reviewing agents re-read every item against the tree as of
**2026-08-19 08:45 UTC** and produced the replacement text below, so this is an **apply** pass,
not an investigate pass. Every `CURRENT:` block was quoted off disk; several items had already
been fixed and are marked so.

Read `REVIEW-LOG.md` for status; read this for the text.

Six items turned out to be real defects rather than prose problems and are marked **NEW BUG**.
Those need mutation checks like the §1 items got. The pure-prose ones do not.

---

# PART A — `symoneuralstudio`

## A1. `tools_impl/__init__.py:6` — write the assertion, keep the comment

The comment ("`test_studio.py` asserts the resulting tool count rather than trusting it") is
correct about intent; the assertion does not exist. Real count from the decorators: `fs.py` 7
`workspace`, `host.py` 7 `host`, `stack.py` 6 `stack`, `comfy_tool.py` 6 `comfyui` = **26**,
independently confirmed by `tests/studio.mjs:59,66`. Leave `__init__.py` alone. Insert into
`class RegistryTests` in `test_studio.py` after `test_names_are_unique` (ends line 75):

```python
    def test_the_registry_has_every_tool_every_module_defines(self):
        """`tools_impl/__init__.py` says this count is asserted rather than trusted -- this is
        where that happens. A module dropped from that import list registers nothing and raises
        nothing: the agent simply comes up with fewer tools and the system prompt renders a
        shorter list. Adding or removing a tool is meant to fail this test once, deliberately;
        a module quietly failing to import is what it exists to catch.
        """
        self.assertEqual(len(registry.TOOLS), 26,
                         "the tool count changed. If that was intended, update this number and "
                         "the other places that state it: the `Tools` heading and group table "
                         "in README.md, and the two `26`s in tests/studio.mjs")
        per_group: dict[str, int] = {}
        for entry in registry.TOOLS.values():
            per_group[entry.group] = per_group.get(entry.group, 0) + 1
        self.assertEqual(per_group,
                         {"workspace": 7, "host": 7, "stack": 6, "comfyui": 6},
                         "a tool moved group, or one tools_impl module registered nothing")
```


**LANDED — not as written above, and stronger.** `backend/apps/symoneuralstudio/test_studio.py`
carries two class constants and two tests inside `RegistryTests`:

| What | Where |
|---|---|
| `EXPECTED_TOOLS` — keyed by *defining module*, membership sets | `test_studio.py:78` |
| `test_the_whole_tool_inventory_is_registered` | `test_studio.py:89` |
| `EXPECTED_GROUPS` — keyed by *group*, the README table transcribed | `test_studio.py:110` |
| `test_the_group_each_tool_reports_is_the_one_the_readme_documents` | `test_studio.py:121` |

Three differences from the prescription, all deliberate. The test names differ, so grepping
this file's literal `test_the_registry_has_every_tool_every_module_defines` finds nothing and
mis-reads A1 as open — which is why this note exists. It compares **names**, not counts, so a
failure says which tool went missing rather than that one did. And it is keyed two ways because
`fs.py` defines the `workspace` group: module and group are not the same question, and the
prescription above only asked the second one.

One thing the landed version does **not** do: assert the literal `26`. The total is checked as
`sum(len(v) for v in EXPECTED_TOOLS.values())` (`test_studio.py:102`), so the `26` in
`README.md` and the two in `tests/studio.mjs:59,66` are guarded only transitively — change a
membership set and the sum follows it silently. Recorded rather than fixed; it is a weaker guard
than the prescription on exactly one axis while being stronger on two others.

## A2. `tools_impl/comfy_tool.py` — drop the dead `on_event`

Nothing passes it. The only `execute` call is `routes.py:504`, `execute(prompt, timeout_s=...)`.
Wiring it is redundant: `/events` (routes.py:588) already relays ComfyUI's own socket carrying
the same frames, and `POST /queue` blocks with nowhere to stream from.

Delete `from typing import Any` at `comfy_tool.py:44` (`Any` has no other use).

`comfy_tool.py:88-95`:

```python
async def execute(prompt_graph: dict, *, timeout_s: int = 900) -> dict:
    """Run one compiled graph end to end under the GPU lease. Shared by every tool here.

    Not registered as a tool itself -- `run_workflow` is the registered wrapper. `routes.py`
    calls this directly from `POST /queue`, which blocks and returns the finished images; a
    browser that wants per-node progress while a job runs reads the relay at
    `/api/studio/events`, which forwards ComfyUI's own socket and carries the same frames this
    loop consumes below.
    """
```

`comfy_tool.py:149-152`, drop the two callback lines:

```python
            async for ev in client.watch(ws, prompt_id, idle_timeout=timeout_s):
                etype, data = ev.get("type"), (ev.get("data") or {})
```

## A3. `registry.py:174` — half true

`test_studio.py:51` does call `schema_for`. `mcp_server.py` does not — it imports only
`gate, registry, workspace` and relies on `functools.wraps` letting FastMCP's own
`inspect.signature` follow `__wrapped__` (mcp_server.py:100-121). There is no explicit-schema
path anywhere.

```python
    """(description, JSON Schema object) for one callable. Exported because `test_studio.py`
    asserts against it directly. `mcp_server.py` deliberately does *not* use it: it relies on
    `functools.wraps` so FastMCP's own `inspect.signature` pass reaches the original function,
    which means the MCP client and this registry read the same signature rather than two
    schemas that can drift."""
```

## A4. `routes.py:421` — the frame key is `event`, not `type`

Every yield in `agent.py` (260, 263, 280, 285, 295, 296, 302, 313, 329, 349, 352, 353) is
`{"event": ...}`. Only the ComfyUI relay uses `type` — hence the confusion.

```python
    Server-sent events rather than a WebSocket because this is strictly one-directional and
    SSE reconnects by itself. Each frame is one JSON object keyed `event`, exactly as
    `agent.run()` yields it -- the transport adds nothing and interprets nothing, so what the
    browser renders is what the loop actually did. `event`, not `type`: `type` is what the
    ComfyUI relay on `/events` uses, and mixing the two is how a client ends up needing two
    parsers for one page.
```

## A5a. `routes.py:341` — no tool inspector exists

`page.js` makes five API calls: `/agent` (220), `/queue` (287), `/state` (369), `/tools` (379),
`/workflows` (385). It renders `GET /tools` read-only; nothing POSTs to `/tool/{name}`.

```python
    """Run one tool directly, bypassing the model. This is what makes the tool layer testable
    by hand -- `curl -H "$HEADER" -d '{"path":"."}' .../tool/list_dir` -- and it is how an
    external client drives a single tool without an agent turn. Nothing in this repo calls it:
    `page.js` renders `GET /tools` as a read-only table and has no inspector that fires one."""
```

## A5b. `routes.py:377` — "so the editor can open it" is false on both counts

The editor is ComfyUI's own frontend in an iframe; it loads graphs through its own API under
`/studio/comfy/` and has never heard of this route or of `graph.from_prompt`'s shape.

```python
    """The prompt graph, plus the same graph run back through `graph.from_prompt`.

    Nothing in this repo calls it. The embedded editor is ComfyUI's own frontend and loads
    graphs through its own API under `/studio/comfy/`; it does not read this route and does not
    understand the canvas shape. This is here for a client that wants a stored workflow in both
    formats without importing the package -- and it is the only surface `from_prompt` has.
    """
```

## A5c. `/interrupt` (536) and `/nodes` (391) — no change

Neither makes a consumer claim. Both are unreferenced by `page.js` and `tests/studio.mjs` —
worth knowing, nothing to correct.

## A6. `routes.py:590` — **ALREADY FIXED**

The `/events` docstring now says nothing in the repo consumes it and that the chrome reads
`/state`. Verified accurate: `page.js` has no `WebSocket` and no `EventSource`; its SSE read at
231 is a hand-rolled `fetch` reader for `/agent`, and the status strip polls `/state` every 15 s.

## A7. `graph.py:5` — the owner moved, the shape is still live

`page.js` never produces or consumes this shape — it posts `{workflow, params}` to `/queue`. The
shape is now an input contract on two surfaces: the `canvas` argument of `run_workflow`
(`comfy_tool.py:275,284-285`) and the `canvas` field of `POST /queue` (`routes.py:493-494`).
`to_prompt`, `validate`, `inject`, `cycles` all have live callers; `from_prompt` is reachable only
from `GET /workflow/{name}`, which has none.

`graph.py:5`:

```
What the `canvas` argument accepts (ours, and it may change -- nothing in a browser produces
it any more, so the producers are the agent calling `run_workflow` and any client POSTing
`{"canvas": ...}` to `/api/studio/queue`):
```

`routes.py:471-473`, which still calls it "an editor document":

```python
    Accepts, in order of precedence: `prompt` (a ComfyUI prompt graph), `canvas` (this
    package's own node/link document, converted by `graph.to_prompt` -- see there, and note the
    embedded editor does not emit it), or `workflow` (a name from the library). `params` is
    applied through `graph.inject` either way.
```

## A8. `inference.py:188` — user-facing string on tokenless `/state`

The only spawner is `backend/api.py:start_llama()`, called from the chat paths at 1899, 1971,
2151, each inside `gpu.hold("chat")`. A Studio agent turn does the opposite: `agent.py:257-262`
gets `None` from `inference.pick()` and yields `no_backend`.

```python
            row["detail"] = ("llama-server is down. Only the chat surface starts it -- send a "
                             "message to /api/chat, which spawns it inside the GPU lease. The "
                             "Studio agent probes and rides it; it never spawns one, so an "
                             "agent turn made now returns no_backend rather than warming it")
```

## A9. **NEW BUG** — `scripts/comfyui.sh` `stop` waits for the pid, not the card

No `nvidia-smi` anywhere in the file. `stop` (84-96) calls `free_vram`, kills, then loops 20×1 s
on `running` — the *process*. The guard already exists and takes no argument:
`gpu-governor.sh drain` polls against `DRAIN_FLOOR_MIB=1500` for `DRAIN_TIMEOUT_S=60`
(gpu-governor.sh:67-81, dispatched at 231). Wire it; then the header line at :5 is true as
written and needs no change.

Replace the whole `stop)` case:

```bash
  stop)
    if running; then
      free_vram
      kill "$(cat "$PIDFILE")" 2>/dev/null
      for _ in $(seq 1 20); do running || break; sleep 1; done
      running && kill -9 "$(cat "$PIDFILE")" 2>/dev/null
    else
      # Started outside this script, or the pidfile was lost.
      pkill -f "$COMFY/main.py" 2>/dev/null
    fi
    rm -f "$PIDFILE"
    # The process exiting is not the memory coming back: SIGTERM returns the process before
    # the driver returns the device allocation, and the next tenant OOMs at step 0. The loop
    # above waited for the pid; this waits for the card, against the governor's own floor so
    # there is one definition of "drained" in the repo rather than two.
    if "$ROOT/scripts/gpu-governor.sh" drain; then
      echo "comfyui stopped"
    else
      echo "comfyui stopped, but the card did not drain -- see gpu-governor.sh status" >&2
      exit 1
    fi
    ;;
```

## A10. **NEW BUG** — `tools_impl/fs.py` `max_results` bounds nothing

`search` runs grep to completion (`subprocess.run`, line 200) and slices at 204; `find_files`
same at 233/238. `search("def", "/")` walks the whole host and materialises every match in the
serving process before the slice. Byte-for-byte the bug already fixed in `read_file`.

`fs.py:20`, extend imports:

```python
import signal
import subprocess
import threading
```

New helper after `_stat` ends (`fs.py:47`):

```python
#: Wall-clock ceiling on one `search` or `find_files`. A bound on the result count does not
#: bound a grep that matches nothing across a large tree, so both limits are needed.
SEARCH_TIMEOUT_S = 60


def _bounded(cmd: list[str], want: int, timeout: int) -> tuple[list[str], bool, str | None]:
    """Run `cmd`, read at most `want + 1` output lines, then kill it. -> (lines, expired, error)

    Slicing the output afterwards is what this replaces, and the slice was a lie in the same
    way `read_file`'s was before it read `want + 1` bytes: `max_results` is documented as
    "stop after this many", and a slice stops nothing -- `search("def", "/")` ran grep over the
    whole host and brought every match into this process first. The extra line is how
    `truncated` stays honest without a second pass.

    `start_new_session=True` plus `killpg`, for the reason `host.run_command` documents at
    length: a kill that reaches only the child leaves grandchildren holding the stdout pipe and
    the read that follows never returns. `grep` and `find` do not fork, but the deadline timer
    has to be able to end whatever is on the other end of that pipe.

    `expired` is reported separately from truncation because they mean different things to the
    caller: truncated says "there is more", expired says "we stopped looking before we knew".
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, start_new_session=True)
    except OSError as e:
        return [], False, str(e)

    expired = False

    def kill_group() -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()                     # group already gone, or never got one

    def on_deadline() -> None:
        nonlocal expired
        expired = True
        kill_group()

    timer = threading.Timer(max(1, timeout), on_deadline)
    timer.start()
    lines: list[str] = []
    try:
        for raw in proc.stdout:
            raw = raw.rstrip("\n")
            if raw:
                lines.append(raw)
            if len(lines) > want:
                break
    finally:
        timer.cancel()
        proc.stdout.close()
        # Unconditional. The loop above normally leaves the child mid-tree with a closed pipe;
        # a child that already exited on its own makes this a no-op.
        kill_group()
        proc.wait()
    return lines, expired, None
```

`fs.py:181-211`, whole `search`:

```python
@tool("workspace")
def search(pattern: str, path: str = ".", glob: str = "", regex: bool = False,
           max_results: int = 100) -> dict:
    """Search file contents recursively. Uses grep, so it is fast on a large tree.

    Args:
        pattern: The text to find.
        path: Directory to search under. Relative paths are against the project root.
        glob: Restrict to matching filenames, e.g. "*.py".
        regex: Treat the pattern as an extended regular expression rather than a literal.
        max_results: Stop after this many matching lines. grep is killed once one more than
            this has arrived, so this bounds the search and not just the reply.
    """
    p = workspace.resolve(path)
    if not p.exists():
        return {"error": "not_found", "path": str(p)}
    cmd = ["grep", "-rnI", "-E" if regex else "-F", "--", pattern, str(p)]
    if glob:
        cmd[2:2] = [f"--include={glob}"]
    want = max(0, max_results)
    # grep's exit code is never consulted: it exits 1 for "no matches", which is a result and
    # not a failure, and an empty `matches` list already says so truthfully.
    lines, expired, failure = _bounded(cmd, want, SEARCH_TIMEOUT_S)
    if failure is not None:
        return {"error": "search_failed", "detail": failure}
    truncated = len(lines) > want
    hits = []
    for ln in lines[:want]:
        parts = ln.split(":", 2)
        hits.append({"file": parts[0], "line": int(parts[1]), "text": parts[2]}
                    if len(parts) == 3 and parts[1].isdigit() else {"raw": ln})
    out = {"pattern": pattern, "root": str(p), "count": len(hits),
           "truncated": truncated, "matches": hits}
    if expired:
        out["timed_out_after_s"] = SEARCH_TIMEOUT_S
        out["detail"] = ("grep was still running at the deadline and was killed; these are the "
                         "matches it had produced, not all of them")
    return out
```

`fs.py:214-238`, whole `find_files`:

```python
@tool("workspace")
def find_files(name: str, path: str = ".", max_results: int = 200) -> dict:
    """Find files by name pattern, e.g. "build_*.py".

    Args:
        name: A shell glob matched against the filename only.
        path: Directory to search under.
        max_results: Stop after this many. find is killed once one more than this has arrived,
            so this bounds the walk and not just the reply.
    """
    p = workspace.resolve(path)
    if not p.is_dir():
        return {"error": "not_a_directory", "path": str(p)}
    # Pruning the heavy directories is what makes this usable here: an unpruned find over
    # this tree walks .git, three .venvs and the HF cache, and times out.
    cmd = ["find", str(p),
           "(", "-name", ".git", "-o", "-name", "node_modules", "-o", "-name", ".venv",
           "-o", "-name", "__pycache__", ")", "-prune", "-o",
           "-name", name, "-print"]
    want = max(0, max_results)
    lines, expired, failure = _bounded(cmd, want, SEARCH_TIMEOUT_S)
    if failure is not None:
        return {"error": "find_failed", "detail": failure}
    truncated = len(lines) > want
    found = lines[:want]
    # `count` is the length of `files`, which is what it was not before: it used to report the
    # total found while `files` was sliced, so the two disagreed on every truncated result.
    out = {"name": name, "root": str(p), "count": len(found),
           "truncated": truncated, "files": found}
    if expired:
        out["timed_out_after_s"] = SEARCH_TIMEOUT_S
        out["detail"] = ("find was still walking at the deadline and was killed; these are the "
                         "paths it had produced, not all of them")
    return out
```

Behaviour change to note in the commit message: `find_files`' `count` used to be the total
matched while `files` was the truncated slice, so the two disagreed whenever truncation bit.
`count` is now `len(files)`, with `truncated` carrying the rest.

## A11. `tools_impl/host.py:19-20` — characters, not bytes

`_clip` (58-61) uses `len(s)` against `MAX_OUTPUT`, and `Popen(text=True)` returns decoded
`str`, so `stdout_bytes_dropped` understates real bytes on any multi-byte output. Consumer check
for the rename: `grep -rn "bytes_dropped\|chars_dropped"` across the repo matches **only**
host.py:116 — nothing in `page.js`, `test_studio.py` or `tests/studio.mjs` reads these keys, so
renaming is free. Renaming is also the right direction: the cut is a character cut.

`host.py:19-20`:

```
- **Output truncation.** A `find /` returning 40 MB into a 7B context window helps nobody.
  Truncation is reported with the character count that was dropped. Characters, not bytes:
  `Popen(text=True)` hands back decoded `str`, so `MAX_OUTPUT` and the dropped figure are both
  measured in what the model will actually be charged for, and the keys say `chars` so nobody
  reads a UTF-8 byte total off them.
```

`host.py:58-61`:

```python
def _clip(s: str) -> tuple[str, int]:
    """(kept, dropped). Both measured in characters -- `s` is already decoded text, and
    `MAX_OUTPUT` is a context-window budget rather than a wire limit."""
    if len(s) <= MAX_OUTPUT:
        return s, 0
    return s[:MAX_OUTPUT], len(s) - MAX_OUTPUT
```

`host.py:114-116`:

```python
    return {"command": command, "cwd": str(where), "exit_code": proc.returncode,
            "stdout": out, "stderr": err,
            "stdout_chars_dropped": out_dropped, "stderr_chars_dropped": err_dropped}
```

## A12. `README.md` — group table and test counts

`read_image_file` is registered `@tool("comfyui")` at `comfy_tool.py:393`, not `workspace`.
`fs.py` defines exactly 7 `workspace` tools, `comfy_tool.py` exactly 6 `comfyui`. The headline
26 on line 114 is correct and stays.

`README.md:120` and `:123`:

```
| `workspace` | `workspace_root` `list_dir` `read_file` `write_file` `delete_path` `search` `find_files` |
| `comfyui` | `generate_image` `run_workflow` `list_workflows` `list_comfy_nodes` `comfy_status` `read_image_file` |
```

`test_studio.py` now holds **52** test methods (`grep -c "^    def test_"` = 52; no
`parametrize`, and the seven `subTest` blocks add no collected items). So "32" is stale in both
places and the arithmetic behind "941 before, 973 after" no longer holds. The whole-suite total
was not re-measurable from the review sandbox, so drop the pair rather than restate it.

`README.md:239`:

```
cd backend && python3 -m pytest apps/symoneuralstudio/test_studio.py -q     # 52
```

`README.md:243-247`:

```
`test_studio.py` holds **52 tests** and they all pass. The whole-suite before/after pair that
used to sit here was measured against a tree that has since moved on, so it is gone rather than
restated as though it still held — run the second command above for the current total.
`test_studio.py` imports nothing outside the serving path, deliberately: a third `--ignore`
would turn a four-figure collection into "collected 12" and read exactly like a broken suite.
```

Line 253's "taking all 26 down together" is still correct.

---

# PART B — `symoneuralexp`

## B1. `loader.py:110-111` — `resolve_ref` docstring

Only the bare-dotted-name branch (132) names all three forms. The `module:attr` branch raises
`cannot import ...` or `has no attribute`; the path branch raises `no such plugin file`.

```python
def resolve_ref(ref: str):
    """`use:` string to a plugin object. Raises `ContextError` on every path -- but only the
    last of the three names all three forms, and that asymmetry is deliberate:

    * `package.module:attribute` -- the colon is the author saying which form they meant, so the
      error names that module or that attribute and stops. Listing the other two forms would be
      noise: `plugins:clock` is not a path and was never going to be tried as one.
    * a path ending in `.py`, or anything containing `/` -- `_from_path` reports the absolute
      path it resolved to, which is the one fact the author cannot read off the manifest.
    * a bare dotted name -- genuinely ambiguous, because a typo'd module path, a forgotten colon
      and a missing `.py` all arrive here looking identical. That error names all three.
    """
```

## B2. `page.html:218-222` — USER-FACING, measured

`registry.describe` on all seven: `bus, clock, echo_llm, memory, gpu, explode` = `module`;
`recorder` = `class`. No plugin resolves as `function` or `object`, because `routes.py:178`
reaches every one as `apps.symoneuralexp.plugins.<name>` — always a module. Correcting the page
is far cheaper than adding two shapes (two new files, two `CATALOGUE` entries, the catalogue test
at `test_exp.py:195-205`, plus `presets/dev.yaml`).

```html
    <p class="ex-note" style="margin:0 0 10px">
      Seven of them, each demonstrating one mechanism rather than doing anything useful. All seven
      are reached as a module path, so the registry sees a module every time: six report
      <b>Kind</b> <code class="ex-mono">module</code>, and
      <code class="ex-mono">recorder</code> reports <code class="ex-mono">class</code> because its
      <code class="ex-mono">apply</code> is a class. The two other shapes the runtime accepts
      &mdash; a plain function, and an object with <code class="ex-mono">apply</code> &mdash; have
      no file here; they are exercised from <code class="ex-mono">test_exp.py</code>.
      <b>Kind</b> is what the registry decided by looking at the object it resolved.
    </p>
```

## B3. `plugins/__init__.py:1-17` — whole docstring

Grepped `plugins/`: only `ctx.provide` (bus, clock, memory, echo_llm, gpu), `ctx.effect` (clock,
explode) and `ctx.get` (recorder) are used. **All six** of `ctx.on`, `ctx.emit`, `ctx.plugin`,
`ctx.isolate`, `ctx.inject`, `ctx.intercept` have no worked example. `bus.py`'s own
`subscribe`/`publish` is a service's API, not the runtime bus.

```python
"""Example plugins -- one per mechanism.

These are meant to be read, so "how do I do X" has one answer and it is a file you can open:

    bus.py        provide a service                        module plugin (`apply`)
    clock.py      an effect that must be cleaned up        module plugin, async `apply`
    echo_llm.py   a service `intercept` is shaped for      module plugin (`apply`)
    memory.py     a service worth isolating per session    module plugin (`apply`)
    recorder.py   state that lives as long as the mount    class plugin (`apply` is a class)
    gpu.py        a service that reads the real machine    module plugin (`apply`)
    explode.py    what failure looks like                  module plugin (`apply`)

Every one is reached as `use: apps.symoneuralexp.plugins.<name>`, so the registry resolves a
module in all seven cases: `kind` is `module` for six and `class` for `recorder`. The function
and object-with-`apply` shapes are accepted by `registry.resolve` but no file here is one.

What they cover between them is `ctx.provide`, `ctx.effect`, `ctx.get`, and declared injection
in both its forms -- required and optional. What they do *not* cover is `ctx.on`, `ctx.emit`,
`ctx.plugin`, `ctx.isolate`, `ctx.inject` and `ctx.intercept`: none of those six has a worked
example in this directory. `isolate` and `intercept` appear declaratively in
`presets/sessions.yaml`, which is a manifest and not a plugin. `bus.py`'s own `subscribe` and
`publish` are that service's API, not the runtime's event bus -- `ctx.on` and `ctx.emit` are a
different mechanism and nothing here shows them.

They are also the fixtures for `test_exp.py` and five of the seven entries in
`presets/dev.yaml`. That is deliberate: an example that nothing exercises rots, and an example
that is only a fixture reads like one.
"""
```

## B4. `presets/failures.yaml:1-5` — measured

`python3 -m apps.symoneuralexp.cli --preset failures` prints `active=1 failed=3 pending=1`.
Exactly **one** entry ends active (`bus`).

```yaml
# Every way a manifest entry can go wrong, in one file, so the states have somewhere to be seen.
#
# Nothing here is a trap: mounting this preset is safe. Exactly one entry ends ACTIVE -- `bus` --
# and that is the demonstration, because the four broken ones do not take it down with them: one
# bad `use:`, one config error, one plugin that raises, one that reaches for what it did not
# declare, plus one entry waiting in PENDING for a service its group isolated away, one group and
# one disabled entry. The service `bus` provides stays up and readable throughout.
#
# `python3 -m apps.symoneuralexp.cli --preset failures` prints `active=1  failed=3  pending=1`.
# The fiber count says three failed where the table shows four entries: `no-such-module` fails
# while *resolving*, so it never gets a fiber at all.
```

## B5. `presets/dev.yaml:1`

Listed: `bus, memory, gpu, clock, recorder` — five of seven. `explode` is the deliberate
omission; `echo_llm` is also absent and unmentioned. `clock` is listed but `disabled: true`.

```yaml
# The default manifest. Five of the seven plugins in `plugins/`: `explode` is left out because it
# fails on purpose, and `echo_llm` because nothing in this preset injects an `llm` for it to
# serve. `clock` is listed but disabled -- the note on that entry says why.
```

## B6. `page.js:360-362` and `routes.py:193-194` — the example restarts

Measured: `dev` gives `bus` `config: {history: 200}`; `failures` gives it none, so `_reconcile`
takes the changed-config branch and `_patch_fiber` restarts it — `reloads 0 -> 1`. The id
survives, the process does not. `sessions` -> `failures` **is** genuinely untouched: both name
`bus` with the same `use` and no config, `reloads` stays 0.

`page.js:360-362`:

```js
    /* A diff, not a rebuild: switching from `sessions` to `failures` leaves the `bus` both
     * presets name alone -- same fiber, same id, not restarted, because both name it with the
     * same `use` and no config. Saying so on the button is worth the words, because "mount"
     * otherwise reads as "restart everything". A shared id is not sufficient on its own, which
     * is why this example is not `dev` -> `failures`: `dev` gives `bus` a `history` of 200 and
     * `failures` gives it none, so that switch patches the entry and restarts the fiber. The id
     * survives either way; the running body does not. */
```

`routes.py:193-194`:

```python
    """Mount a named preset. A diff against what is already running, not a rebuild -- switching
    from `sessions` to `failures` leaves the `bus` both presets name alone: same fiber, same id,
    never restarted. An entry both presets name with a *different* config is patched and
    restarted instead, so `dev` -> `failures` does restart `bus` -- `dev` sets `history: 200` and
    `failures` sets no config at all. The id survives either way."""
```

## B7. `presets/sessions.yaml:7-8` — the interception is never exercised

`session-b`'s children are `b.llm` (provides `llm`) and `b.memory` (provides `memory`); neither
injects. Nothing in the package injects `llm`, so no call passes through `_Intercepted`. Grepped
`test_exp.py`: zero occurrences of `intercept`, `_Intercepted` or `temperature` — the proxy has
no test either. A preset-only fix is impossible: no plugin declares `inject = ["llm"]`.

Honest, preset-only:

```yaml
# `intercept` on session-b declares that any child reaching for `llm` gets `temperature: 0.0`
# merged into every call it makes, without the plugin carrying a config field for it -- the value
# lives on the group. Nothing in this preset exercises that: `b.llm` *provides* `llm` and
# `b.memory` provides `memory`, and neither injects the other, so no call goes through the
# interception proxy. Exercising it needs a plugin that declares `inject = ["llm"]` and calls it,
# and no example in `plugins/` does.
```

**Preferred: write the guard instead.** New `plugins/asker.py`, add `"asker"` to
`plugins/__init__.py`'s `CATALOGUE`, one line under each session group:

```python
"""A plugin that consumes a service instead of providing one -- and the only way to see
`intercept` work.

Every other example here provides something. This one injects `llm` and calls it, which is what
`ctx.intercept` shapes: mounted under a group that says `intercept: {llm: {temperature: 0.0}}`,
the keyword arrives in the call this file makes without this file naming it or being able to see
it. Mounted at the top level, the same code gets the plugin's own default. That difference is the
mechanism, and without a consumer it cannot be observed.
"""
from __future__ import annotations

name = "asker"
inject = ["llm"]
schema = {"prompt": (str, "hello")}


class Asker:
    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt
        self.answers: list[dict] = []

    async def ask(self, prompt: str | None = None) -> dict:
        # No `temperature=` here on purpose. Whatever the group intercepted is what the `llm`
        # service receives; `EchoLLM.complete` records it, so `GET /api/exp/call` on this
        # service shows the interception rather than asserting it.
        answer = await self.llm.complete(prompt or self.prompt)
        self.answers.append(answer)
        return answer


def apply(ctx, config):
    ctx.provide("asker", Asker(ctx.llm, config["prompt"]))
```

```yaml
      - {id: b.ask,    use: apps.symoneuralexp.plugins.asker}
```

## B8. `page.js:458-464` — the file-sink claim is a guess

`/events` returns only `events`, `seq`, `buffered` — no sink information at all, so the sentence
is printed on `buffered < seq` alone. `trace_path` and `dropped_writes` arrive on `/state` and
are already in the module-level `last` (page.js:37, set at 581).

```js
    /* The ring is capped. When it holds fewer events than the runtime has recorded, the page is
     * no longer showing everything that ever happened and says so rather than implying the
     * runtime went quiet. Where the older events went is a separate question with three answers,
     * and only `/state` knows which one holds: no file sink configured, a sink that took every
     * write, or a sink that dropped some. `/events` carries none of that, so claiming the file
     * has the rest off `buffered < seq` alone is a guess -- and wrong in two of the three
     * cases. */
    var note;
    if (!payload.seq) {
      note = 'Nothing has happened yet.';
    } else {
      note = payload.buffered + ' events in the ring, ' + payload.seq + ' recorded since boot';
      if (payload.buffered < payload.seq) {
        if (!last) {
          note += ' — the ring has wrapped; where the older events went is not known until '
                + '/state answers';
        } else if (!last.trace_path) {
          note += ' — the ring has wrapped and there is no file sink, so the older events '
                + 'are gone';
        } else if (last.dropped_writes) {
          note += ' — the ring has wrapped; ' + last.trace_path + ' has the rest except for '
                + last.dropped_writes + ' write'
                + (last.dropped_writes === 1 ? '' : 's') + ' it could not make';
        } else {
          note += ' — the ring has wrapped; ' + last.trace_path + ' has the rest';
        }
      }
    }
    $('ex-feed-note').textContent = note;
```

## B9. `page.js:232-236` — three conditions, one message

`writable` is `enabled() and token_ok(...)` (`routes.py:66-67`), false in three distinct
situations. The page already knows `s.enabled` and can ask `token()` (page.js:47).

```js
    var entries = s.entries || [];
    /* Three conditions produce a withheld config and they need three different fixes: the switch
     * is off, the token this tab holds was refused, or no token was presented. `writable` is one
     * boolean covering all three, so it cannot be the whole message -- telling an operator they
     * presented no token while the switch is off sends them to the wrong fix, which is the same
     * failure the gate is drawn two ways to avoid. */
    var withheld = '';
    if (!s.writable) {
      if (!s.enabled) {
        withheld = 'Config values are withheld: the mutation surface is switched off, so no '
                 + 'token opens it. Every other column is the whole truth.';
      } else if (token()) {
        withheld = 'Config values are withheld: the API refused the token this tab is holding. '
                 + 'Every other column is the whole truth.';
      } else {
        withheld = 'Config values are withheld: this reader presented no token. Every other '
                 + 'column is the whole truth.';
      }
    }
    $('ex-entries-note').textContent = entries.length ? withheld
      : 'Nothing is mounted. The container is up and empty, which is a state and not an error.';
```

## B10. **NEW BUG** — `trace.py` `since` silently drops the oldest unseen events

Measured: with ten events recorded, `since(0, 3)` returns seqs `[8, 9, 10]`. `page.js:446` then
sets `seq = 10`, so seqs 1-7 are never delivered and never will be. Separately, `add`'s
`except OSError` does not cover `json.dumps`: a circular field raises `ValueError`, a non-string
dict key raises `TypeError`, and either escapes into the code being traced.

`trace.py`, both methods plus one new one:

```python
    def add(self, event: str, **fields) -> Event:
        """Record one. Never raises: a runtime whose tracing can break the thing it is tracing
        is worse than no tracing, and a full disk is a real state this box has been in.

        The ring append happens first and unconditionally, so the event is in memory whatever
        the file sink does. Serialisation is *inside* the guarded block because it is one of the
        ways this fails and it is not an `OSError`: a field carrying a circular structure raises
        `ValueError`, a non-string dict key raises `TypeError`, and a deeply nested one raises
        `RecursionError`. `default=str` covers unknown types and none of those three. Any of
        them escaping here would take down the plugin being traced, which is the one thing this
        method promises not to do. A dropped write is counted and `page.js` shows the count.
        """
        self.seq += 1
        record: Event = {"seq": self.seq, "t": round(time.time(), 3), "event": event}
        record.update(fields)
        self.ring.append(record)
        if self.path is not None:
            try:
                line = json.dumps(record, default=str) + "\n"
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            except (OSError, TypeError, ValueError, RecursionError):
                self.dropped_writes += 1
        return record

    def since(self, seq: int = 0, limit: int = 200) -> list[Event]:
        """The `limit` **oldest** events after `seq`, oldest first.

        Oldest and not newest, and that is the whole correctness argument. A caller polls with
        the last `seq` it rendered and advances that cursor to the last event it was handed, so
        a caller handed the *newest* `limit` has moved its cursor past everything older it never
        saw -- and those events are gone from its view for good, silently, exactly when a burst
        makes them interesting. Handing back the oldest means the cursor only ever advances over
        events the caller has actually taken. `unseen()` is how it learns there are more, so it
        can poll again at once rather than wait out its interval.

        A sequence and not a timestamp, because two events can share a millisecond and a
        timestamp cursor either re-delivers one or drops it.
        """
        return [e for e in self.ring if e["seq"] > seq][:limit]

    def unseen(self, seq: int = 0) -> int:
        """How many events after `seq` are still in the ring. `since()` returns at most `limit`
        of them; this is what tells the caller it has to come back."""
        return sum(1 for e in self.ring if e["seq"] > seq)
```

`routes.py:155-166`, so the page can act on it:

```python
@router.get("/events")
async def events(since: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=2000)):
    """The trace from a sequence cursor. The page polls with the last `seq` it saw.

    A sequence, not a timestamp: two events can share a millisecond, and a timestamp cursor
    either re-delivers them or drops one. Neither is acceptable in the feed you debug reloads
    from.

    `remaining` is how many events past the cursor did not fit in `limit`. A caller that sees a
    non-zero value must poll again immediately rather than wait out its interval: its cursor has
    advanced only over what it was handed, so nothing is lost, but the feed is behind.
    """
    loader = await _loaded()
    trace = loader.runtime.trace
    page = trace.since(since, limit)
    return {"events": page,
            "remaining": max(trace.unseen(since) - len(page), 0),
            "seq": trace.seq,
            "buffered": len(trace)}
```

`page.js:594-598`:

```js
  function pollEvents() {
    getJSON('/events?since=' + seq).then(function (r) {
      if (!r.ok) return;
      renderEvents(r.body);
      /* The cursor advanced only over the events that came back, so whatever the limit cut off
       * is still waiting. Come straight back for it: otherwise a burst larger than one page
       * takes minutes to drain and the feed reads as if the runtime went quiet. Bounded,
       * because every pass moves `seq` forward. */
      if (r.body.remaining) setTimeout(pollEvents, 0);
    });
  }
```

## B11. `__init__.py:82`, `context.py:165` — **ALREADY FIXED**

Both check out against `cli.py`. `python3 -m apps.symoneuralexp.cli` is exact (`cli.py:156`
`__main__` guard, `cli.py:132` same string as `prog`); `--trace N` matches `cli.py:145`. No
`exp events` reference survives anywhere in the package.

## B12a. `context.py` — **ALREADY FIXED**

No `first version` / `earlier version` / `used to` / `previously` anywhere. The `settle()`
docstring (128-143) argues the design directly.

## B12b. `fiber.py:236-241` — drop the uncheckable history

```python
        1. **Fibers that depend on this one.** Without this step there is a window in which a
           consumer is still ACTIVE while the service it started against has already been
           revoked -- the settle pass notices and sends it to PENDING, but only *after*, and the
           trace records the revoke before the consumer's unwind. Anything the consumer does in
           between reads a service the container no longer holds. Reverse-order teardown is
           worthless if it only holds within one plugin.
```

## B12c. `loader.py:470-476` — present tense

```python
        The guard is `entry.disabled != (not on)` -- the state being asked for, not the state
        held. Inverting that comparison inverts the whole method: disabling would do nothing, and
        enabling an already-enabled entry would mount a *second* fiber over the first. The second
        one's `provide` is refused -- `Context.provide` will not take a second live owner -- so it
        fails, the entry points at that failure, and the original fiber goes on running with
        nothing holding its handle. That is the shape of leak this class exists to prevent, which
        is why `_mount` refuses to run over a live fiber as well rather than relying on this
        guard alone.
```

## B13. `registry.py:105-109` — fix the line, not the comment

Both arms are `plugin`, so the line is `target = plugin` with three redundant comparisons. Intent
is sound and already satisfied: the shapes differ in what `entry` becomes (104), never in
`target`. All downstream uses want the passed object.

```python
    # `target` is where metadata is read from and what the loader reloads; `entry` is what gets
    # called. For a module they differ, which is the whole reason the two names exist -- the
    # manifest points at `plugins.recorder`, the code to run is `plugins.recorder.apply`, and
    # `inject`/`schema` are module globals sitting between them. `target` is unconditional: the
    # four shapes differ in what `entry` becomes, never in this.
    target = plugin
```

## B14. **NEW BUG** — `loader.py:160-165` `_module_of` reports a reload that did not happen

Measured on 3.10.12 and 3.13: `types.SimpleNamespace(apply=...)` has **no** `__module__` on 3.10
and `None` on 3.13, so `_module_of` returns `None`, `loader.reload` skips `reload_module`
entirely (535), clears `entry.error`, rebinds and restarts, and `POST /reload` answers 200 having
re-executed nothing. For a class instance, `__module__` names where the *type* was defined, not
where `apply` lives.

Add `import inspect` to the import block at `loader.py:80-84`, then:

```python
def _module_of(target) -> object | None:
    """The module `reload` should re-execute, or None when there is nothing safe to re-execute.

    Three of the four shapes have an answer. A module is its own. A function or a class carries
    `__module__`, and that is where its source lives, so re-executing it is exactly right.

    The object-with-`apply` shape has no answer, and this is the guard for it. `__module__` on an
    instance names the module its *type* was defined in, which is not where `apply` came from --
    for `types.SimpleNamespace` that is the standard library, and on Debian's 3.10 the attribute
    is absent altogether. So the choice for that shape is between re-executing `types` and
    reloading nothing; both report success, and the second is the reload lie `Fiber.rebind`
    exists to prevent. Returning None makes it the caller's business to say so.

    `__module__` is also only a string the object carries, not a fact the module confirms, so the
    module is asked whether it actually holds this object under this name. A class defined inside
    a function, or moved between modules, would otherwise send `reload_module` at a file that has
    never held the code being reloaded.
    """
    if isinstance(target, type(sys)):
        return target
    if not (inspect.isclass(target) or inspect.isroutine(target)):
        return None
    module = sys.modules.get(getattr(target, "__module__", "") or "")
    if module is None or getattr(module, getattr(target, "__name__", ""), None) is not target:
        return None
    return module
```

In `Loader.reload`, replace `loader.py:534-535` so the no-op is not reported as a reload (the
existing `try: reload_module(module) ... return entry` block becomes the body of the `else`):

```python
        module = _module_of(entry.fiber.runner.target)
        if module is None:
            # No module to re-execute -- an object-with-`apply`, or a callable its own module
            # does not hold under its name. Rebinding and restarting below is still worth doing,
            # but calling it a reload would be the lie: nothing was re-read from disk.
            self.runtime.trace.add("loader/skip", entry=entry.id, phase="reload",
                                   reason="no module owns this plugin object")
            entry.error = ("nothing was re-imported: this plugin is an object, not a module "
                           "member, so there is no file to re-execute. Restarted against the "
                           "code already loaded.")
        else:
```

## B15. **NEW BUG** — `loader.py:217-223` a boolean id becomes the string `"False"`

Measured: `yaml.safe_load("id: off")` gives `{'id': False}`, and the entry ends up named
`"False"` — which `POST /remove {"id": "off"}` will fail to find. It is not recoverable here,
because `False` could have been written `off`, `no`, `false` or `False`.

```python
        # `raw["id"]`, and a boolean is refused outright. YAML 1.1 parses the bare words `on`,
        # `off`, `yes` and `no` as booleans, so `id: off` arrives here as `False`. An `or` chain
        # would fall through to `use` and give the entry a module path for a name; `str(given)`
        # names it `"False"`, which is no better -- the author writes `off`, the API answers "no
        # entry 'off'", and nothing on the page says why. It is not recoverable either, because
        # `False` could have been spelled `off`, `no`, `false` or `False` and picking one is a
        # guess. Raise, name the fix, and let the manifest quote it -- `presets/failures.yaml`
        # does.
        given = raw.get("id")
        if isinstance(given, bool):
            raise ContextError(
                f"manifest entry has a boolean id ({given!r}), which YAML 1.1 produces for the "
                f"bare words on/off/yes/no -- so an id written `off` parses as `False`. Quote "
                f"it (`id: \"off\"`) to keep the name you wrote.")
        self.id = str(given) if given is not None else str(self.use or f"entry-{index}")
```

## B16. **NEW BUG** — `fiber.py:308-318` `restart` on a disposed fiber is a 200 no-op

Measured: after `await fiber.dispose()`, `restart()` returns the same object still `DISPOSED`,
having unwound nothing and mounted nothing — `dispose` removed it from `runtime.fibers` (303-304)
so `settle()` never looks at it again. `reloads` is still incremented. `await loader.reload('bus')`
on that entry returns `state='disposed'`, `error=None`, and `POST /reload` answers 200.

```python
    async def restart(self, config=None) -> "Fiber":
        """Unload and load again, optionally with new config. The fiber object survives, so a
        route handler or a UI row holding a reference keeps pointing at the same thing.

        Refused on a disposed fiber rather than quietly doing nothing. `dispose` removes the
        fiber from `runtime.fibers`, so no settle pass will ever look at it again: a restart
        would unwind nothing, mount nothing, leave the state at DISPOSED and hand back a fiber
        that answers every question as though it had worked -- which is how `POST /reload`
        returns 200 for a no-op. The entry is what outlives a dispose, so the caller has to mount
        it again; `Loader.reload` does exactly that.
        """
        if self.state in (DISPOSING, DISPOSED):
            raise ContextError(
                f"{self.label} is {self.state} and cannot be restarted -- a disposed fiber is no "
                f"longer in the runtime's list, so nothing would start it. Mount the entry "
                f"again instead.")
        if config is not None:
            self.config = config
        self.reloads += 1
        if self.state in (ACTIVE, FAILED):
            await self._unwind(PENDING)
        await self.runtime.emit("hmr/reload", self, "requested")
        await self.runtime.settle()
        return self
```

`DISPOSING`/`DISPOSED` are already defined at `fiber.py:60-61`, so no import change there. In
`loader.py`, replace line 88 and line 530 so `/reload` re-mounts instead of hitting that error
(`ACTIVE` is imported at 88 and never used anywhere in `loader.py` — dropping it is the whole
change to that line):

```python
from .fiber import DISPOSED, FAILED, Fiber
```

```python
        if entry.fiber is None or entry.fiber.state == DISPOSED:
            # A disposed fiber is not restartable -- see `Fiber.restart`. From this side a
            # disposed fiber and no fiber are the same condition: mount the entry again.
            entry.fiber = None
            await self._mount(entry, self._context_for(entry))
            await self.runtime.settle()
            return entry
```

## B17. **NEW BUG** — `plugins/gpu.py:32-45` raises where its docstring promises `available: False`

Measured against real `nvidia-smi` output shapes: two cards silently report only the first row;
`[N/A], [N/A], ...` raises `ValueError: invalid literal for int()`; `Tesla V100-SXM2, 16GB` (a
real product name with a comma) raises `ValueError: too many values to unpack`; empty output
raises `IndexError`. None is caught. Nothing in the repo reads `used_mib`/`total_mib`/`model`, so
the shape can change.

```python
    def vram(self) -> dict:
        smi = shutil.which("nvidia-smi")
        if smi is None:
            return {"available": False, "reason": "nvidia-smi not on PATH"}
        try:
            out = subprocess.run(
                [smi, "--query-gpu=index,memory.used,memory.total,name",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=self.timeout, check=True).stdout
        except (subprocess.SubprocessError, OSError) as exc:
            return {"available": False, "reason": str(exc)}
        # One row per card, and every card is reported. Taking `splitlines()[0]` reads a
        # two-card box as a one-card box and shows half the VRAM on the page as though it were
        # all of it. `name` is queried last and the split is bounded, because a product name can
        # contain a comma -- "Tesla V100-SXM2, 16GB" is a real one, and an unbounded split turns
        # it into an unpacking error.
        cards = []
        for line in out.strip().splitlines():
            parts = [part.strip() for part in line.split(",", 3)]
            if len(parts) != 4:
                continue
            index, used, total, model = parts
            cards.append({"index": _int_or_none(index), "used_mib": _int_or_none(used),
                          "total_mib": _int_or_none(total), "model": model})
        if not cards:
            return {"available": False,
                    "reason": f"nvidia-smi returned nothing parseable: {out.strip()!r}"}
        return {"available": True, "count": len(cards), "gpus": cards, "source": "measured"}
```

```python
def _int_or_none(text: str) -> int | None:
    """`[N/A]` is nvidia-smi saying it could not read that field -- on a card in a bad state, or
    one whose driver does not report it. It is not a zero, and it is not a reason to raise out of
    a method whose contract is to report what it has: the reading is absent, so `None` is what
    goes on the wire and the page shows no figure for it."""
    try:
        return int(text)
    except ValueError:
        return None
```

Add to the module docstring after the `It takes no GPU lease.` paragraph (line 14):

```python
`vram()` reports every card as a row in `gpus`, and a field nvidia-smi could not read comes back
as `None` rather than a zero. A box with two cards is a box with two rows; collapsing it to the
first would put half the VRAM on the page as though it were all of it.
```

## B18. `fiber.py:63` — confirmed dead, remove

`_LIVE = (PENDING, LOADING, ACTIVE, FAILED)`. Grepped the whole package: the only occurrence is
the definition. Not in `__all__` (54), nothing imports it. Delete line 63 and the blank line
above it.

---

# Order to apply

1. **The six NEW BUGs first** — A9, A10, B10, B14, B15, B16, plus A17/B17 (`gpu.py`). These
   change behaviour, so they need regression tests and mutation checks like the §1 items got.
2. **The pure-prose items** — everything else. No tests needed; they are corrections to what the
   code already does.
3. **A1 last but do not skip it** — it is the assertion `tools_impl/__init__.py` has been
   claiming exists, and the original review's headline example.

Then §2 (rack count in `HANDOVER.md` §0 and the table at line 929), §6
(`build_studio.py` cachebust warning plus a destamp test), the full suite, and the commits.
