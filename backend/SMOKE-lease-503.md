# The chat lease: 503 with a body, and the card comes back — smoke record

Written after running it, not before. Every reading below was taken on this box on
**2026-08-21**, on the tree this file lands in, against the parent commit `95e02c5` for the
A/B column. Task #100.

The rule this file exists for: `archive_tasks.py` reads checks, not notes, and `exists`,
`grep` and `ngrep` all ask what is *written on disk*. None of them can ask whether the thing
works. #94 shipped a desktop client whose eighteen checks went green over a chat surface that
was dead on arrival, and its `note:` saying the checks were insufficient was ignored. So
`check: exists backend/SMOKE-lease-503.md` is on the task, and this file cannot be written
honestly by anybody who did not run the four things below.

## The harness, and why the card is never touched

`tests/chat-contention-harness.py` runs the **real** `api:app` under real uvicorn on a real
socket, and replaces exactly one thing: `api.GOVERNOR`, repointed at a stub script.

That substitution is not a shortcut, it is the safety property. There is one GPU, one
cross-process lock, and the live service on :8800 shares both — so contending the card for
real would answer 503 to every actual visitor for as long as the run lasted, which is the
failure R-171 already caused here once for an afternoon. Nothing below took the lock, and
`gpu-governor.sh` was never executed.

Two modes:

- **`refuse`** — the stub exits 1 on `acquire`. That is precisely the condition
  `GpuQueue.hold()` turns into a 503, so it reproduces "somebody else has the card".
- **`grant`** — the stub exits 0 and appends `"$1 $2"` to `$SYMONEURAL_HARNESS_LOG` on every
  call. An `acquire chat` with no matching `release chat` is a leaked lease, **readable from
  outside the process** — which is the point, because nothing inside the app can be trusted to
  report its own leak. The engine is stubbed too, to a token stream that never ends on its
  own: a generator that finishes by itself cannot demonstrate anything about one that does not.

## 1. A contended card answers 503 with a body — R-173

`refuse` mode, port 8896, `curl -i`:

```
HTTP/1.1 503 Service Unavailable
date: Fri, 21 Aug 2026 22:49:39 GMT
server: uvicorn
content-length: 102
content-type: application/json

{"detail":"Something else is using the GPU right now -- RavenCalc is on the CPU and still available."}
```

The A/B, measured earlier in this task against the tree before `a944fae` (`c2df4aa`): the same
request read **`HTTP/1.1 500`, `content-length: 21`**. The lease was acquired *inside* the
streaming generator there, so the 200 headers had already gone out and the only thing left was
to hang up mid-stream. **Precisely:** it is not literally bodyless — uvicorn substitutes a
generic 21-byte body — but nothing in it names the GPU, and a visitor could not tell a busy
card from a broken server.

`GET /api/status` on the same instance answered **200**, i.e. the rack gate below did not
start refusing traffic on its way past.

## 2. The card comes back when the visitor closes the tab

`grant` mode. The client sends a well-formed `/api/chat` request with `max_tokens: 4096` and
closes the socket 0.05 s later without reading a byte.

| tree | governor log, 10 s after the client left | |
|---|---|---|
| `95e02c5` (before this fix) | `acquire chat` | **LEAKED** |
| this tree | `acquire chat` / `release chat` | **RELEASED** |

and in the API's own log, on this tree only:

```
2026-08-21 18:47:59,602 INFO  chat client disconnected mid-stream; returning the card
```

On `95e02c5` the lease is held until the process dies. There is no timeout that recovers it:
the next tenant waits out `ACQUIRE_TIMEOUT_S = 300` and then fails.

### Why `finally` was not enough

uvicorn's `send` **silently discards on a dead client** — it does not raise. So the streaming
generator is resumed forever, yields into nothing, and its `finally` never runs. `/api/chat`
therefore arms a watchdog polling `request.is_disconnected()` every `DISCONNECT_POLL_S` (0.25 s;
one ASGI receive poll, so it costs nothing).

**Two other shapes were built and measured and do not work.** They are written down because
both are the obvious thing to reach for:

- **Subclassing `StreamingResponse` and releasing in `try/finally` around `__call__`.** Never
  entered at all when the client is already gone.
- **Arming the watchdog on "has the generator started yet".** The generator *does* start —
  that was the wrong trigger, and it disarmed the watchdog immediately.

## 3. The middleware that was actually causing it

The watchdog above was correct in isolation and still leaked in the shipped app. Isolated to
one cause: `rack_power_gate` was registered with `@app.middleware("http")`, which is
Starlette's **`BaseHTTPMiddleware`**, and that runs the endpoint against a *substitute* receive
channel — so `http.disconnect` never reaches the endpoint's own `Request` and
`is_disconnected()` never answers True.

One handler, one abandoned socket, four stacks, each event list as the app recorded it:

| stack | events | |
|---|---|---|
| bare app | `['saw disconnect', 'released']` | RELEASED |
| + `GZipMiddleware` | `['saw disconnect', 'released']` | RELEASED |
| + `BaseHTTPMiddleware` | `[]` | **LEAKED** |
| + the rack gate as raw ASGI | `['saw disconnect', 'released']` | RELEASED |

Note the **empty list** on the third row: neither the watchdog nor the generator's `finally`
ran at all, so there is nothing in any log to read — which is why this took four probes to
find rather than one. Row two exonerates `GZipMiddleware`, which sits above the gate in the
real stack and was the other suspect; it is pure ASGI and passes `receive` straight through.

`rack_power_gate` is now the class `RackPowerGate`, mounted in the same position (added after
GZip, so still the outer of the two). **What it decides is unchanged** — same prefix walk over
`rackpower.ROUTES`, same 503, same `Retry-After: 300`, same pairing with `build_status()` that
`controlboard/test_rackpower.py` enforces. Only the mounting changed.

## 4. A live but unhurried reader is never dropped

This is the failure mode the fix could have introduced, and it would be worse than the leak:
a watchdog that false-positives would drop the lease mid-answer and truncate a real visitor's
reply. `grant` mode, a client that reads the stream slowly for 8 s and then closes cleanly:

```
read 1468 bytes, first at 0.01s, last at 8.02s, still open at 8.00s
client closed cleanly
--- governor log ---
acquire chat
release chat
```

Bytes flowed for the whole window, `recv` never returned empty, and the release came only
*after* the clean close. Neither run logged `Task exception was never retrieved` or any
traceback (`grep -c` on both harness logs: 0) — the orphaned `anticipate()` task is cancelled
on the acquire-failure path.

## What this is asserted by, from now on

`backend/apps/test_chat_lease.py` — **9 tests, all passing on this tree in 5.61 s**. Its live
half is not optional and not env-gated: it starts the harness on an ephemeral port, abandons a
real socket, and reads the stub governor's log. No GPU, no lock, no network.

Red-first, as the working agreements require — the same file against `95e02c5`:

```
8 failed, 1 passed in 29.72s
```

The one that passes there is `test_the_gate_still_decides_exactly_what_it_decided_before`,
which is the point of it: the conversion must not change the gate's verdict, so that assertion
is green on both trees.

One of the eight was green on `95e02c5` when first written, and the fix is worth recording
because it is this repo's own warning arriving in my own test file:
`test_the_orphaned_anticipate_task_is_cancelled_when_the_lease_is_refused` originally asserted
`"thinking.cancel()" in src`. The handler has **always** cancelled that task on the RavenCalc
branch (`api.py` at `95e02c5`, line 2335), so the loose form passed over the bug it was written
to catch. It now matches the `except BaseException:` block around `__aenter__` specifically.
A check that can pass without the work being finished is worse than no check, because it
archives the task.

**A second one was loose in the same way, found by review after the above was written, and it
is the more interesting of the two because the *live* test does not cover it.**
`test_the_release_is_idempotent` asserted that `async def drop_lease():` and
`if released.is_set():` appear in the source. Both are substrings of prose I wrote, and they
survive the one reordering that actually breaks idempotence — moving `released.set()` to
*after* `await lease.__aexit__(...)`. That opens a real window: the watchdog enters
`drop_lease`, suspends on the await with the flag still clear, the generator's `finally` calls
in behind it and passes the guard, and the card is released twice — a second `release chat`
against a lease that no longer exists, which is how one surface hands another's lock away.

Measured on this tree, 2026-08-21, by making exactly that edit to `api.py` and running the file:

```
reordered: await lease.__aexit__(None, None, None)   <- first
           released.set()                            <- second

.....F...
FAILED apps/test_chat_lease.py::TheWatchdogIsWiredTests::test_the_release_is_idempotent
1 failed, 8 passed in 5.40s
```

**Eight passed — including both live tests.** The abandoned-socket run still logged exactly
`["acquire chat", "release chat"]`, because whether the two callers actually collide is a
timing question and on this box they did not. So the live half, which is the strongest thing
in this file, is silent on this defect by construction: a race that does not happen this run
is indistinguishable from one that cannot. That is the argument for asserting the *ordering*
in source rather than only the *outcome* at runtime — the outcome test is better evidence when
it is red and no evidence at all when the race loses. `api.py` was restored from a copy and
verified byte-identical to HEAD (`git status --porcelain -- backend/api.py`, empty) before the
suite was re-run: **9 passed in 5.65 s**.
