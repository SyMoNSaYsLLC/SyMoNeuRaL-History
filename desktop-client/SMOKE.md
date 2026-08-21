# Smoke readings — the desktop client, driven in a real window

`backend/apps/test_desktop_client.py` is structural: it reads the two sources and asserts what
they may and may not contain. Nothing in it can tell you the program starts, and nothing in it
noticed that chat was completely broken. This file is the other half, and it exists because of
that: **every reading below was taken by driving the actual window**, and the readings are
stamped with the tree they were taken on rather than carried forward.

**Measured 2026-08-21 at `7079933`**, which is the commit this file was written for. Chat,
image and RavenCalc were each driven through the UI — not through `curl`, and not by reasoning
about `api.py`.

One qualification, because the rule here is that a figure names the tree it was read on and
this one has a seam in it: the **two RavenCalc timings were read before
`capabilities/default.json` existed**, on the tree that was `709478d` plus the client. That
file grants `core:event:allow-listen` and RavenCalc does not listen for events — it is a
request and a reply — so it is unaffected, and the readings are left as taken rather than
re-dated to `7079933`. Chat and image were both read after the grant landed, which is the only
reason there is a chat reading at all.

## How it was driven, and why on a private display

The client ran under `Xvfb :99` and was driven with `xdotool`, then photographed with
`import -window`. The private display is not fastidiousness. The first attempt ran it on `:0`
next to the agent's own terminal and two things went wrong, both structural:

* `xdotool mousemove` takes **screen** coordinates. The window was at `+400+490`, so clicks
  aimed at the window's own origin landed 400px away and silently did nothing. The screenshot
  looked like a client that ignored its own tabs.
* `xdotool type` goes to whatever holds **keyboard focus**, which was the terminal. The two
  prompts meant for the chat box were typed into the operating agent's session instead.

On `:99` the window is at `0,0` and is the only thing that can hold focus, so neither is
possible. If you drive this client again, do it there.

## What it does, measured

| Surface | Reading |
|---|---|
| `/api/status` | Read automatically at startup. Header showed `chat ready · image ready · ravencalc ready`, indicator green. |
| RavenCalc | `simplify` of `x**2*sin(x)`, two runs: **0.0878 s** and **0.0046 s**, both labelled `(measured, CPU — no GPU lock taken)`. Check rendered `verified — subtracted the simplified form from the original`; `exact: no`; `assumed: nothing — every symbol treated as an arbitrary complex number`; `engine sympy 1.13.3`. |
| Chat | One turn, streamed. Meta line: **54 tokens · 0.5 s · 108.3 tok/s · measured server-side · symon-1.0-7b-q4_k_m · fine-tuned adapter loaded**. Tokens appeared progressively; the whole turn was on screen within 12 s of pressing Send, of which the surface start was 3 s (`starting chat surface` 04:34:29 → `chat surface up` 04:34:32 in `run/api.log`). |
| Image | 768×768, 4 steps, seed 1378475153. **11.13 s (measured, queue excluded)**, 994825 bytes, model `SymonImage F1 q4_k`, served from `/api/gen/gen-1787301709668-1378475153.png`. **The PNG decoded in the window** — that is the assertion, not that the endpoint answered. |

The governor behaved as designed across the run: chat resident at 9028 MiB, evicted when the
render asked for the card (`lock HELD by image (pid 165177)`, 7492 MiB), released afterwards,
VRAM back to 677 MiB. The client takes no lease of its own and never calls the governor.

## The bug this run found, and the reason to distrust the checks that closed #94

Chat rendered its turn scaffold and then **nothing** — no tokens, no error box, no failed
request. `curl` proved `/api/chat` was streaming `data: {"delta": ...}` frames immediately and
correctly, so the endpoint was never in doubt.

The cause: **Tauri v2 gates the core plugins, and there was no `capabilities/` directory at
all.** The four commands in `main.rs` are the app's own and invoke without a grant, which is
why `/api/status` and RavenCalc worked perfectly and hid the problem. `listen()` is
`core:event` — a core plugin — so the listen was refused, and the stream ran to completion into
a window that had never been allowed to hear it. `src-tauri/capabilities/default.json` now
grants `core:event:allow-listen` and `core:event:allow-unlisten`, and
`TheCapabilityGrantsExactlyWhatThePageUsesTests` asserts the coupling so it cannot come loose
again.

**Task #94 had already archived itself at 18/18 before any of this was known.** Every one of
its eighteen checks was green while a third of the client did not work. That is not bad luck
with a check set; it is the failure mode `.claude/CLAUDE.md` names — *"a check that can pass
without the work being finished is worse than no check, since it will archive the task"* — and
it is the second time in this repo, after `87c4042`. The eighteen checks ask whether files
exist and whether strings appear in them. **Not one of them could observe that the program
runs.** The task's own note said as much and the note was correct; a note is not a check, and
`tools/archive_tasks.py` does not read notes.

The general lesson, worth more than this client: *a task whose deliverable is a running program
needs at least one check that only a real run can turn green.* This file is that check for
#94 — but it was written after the archiver had already acted, which is exactly one run too
late.

## Second run — the branches the first run never touched

**Measured 2026-08-21 on `f6b053a` plus the fixes in the commit that carries this section.**
Everything above was one happy turn per panel. That is the shape of smoke test that agrees with
you: three panels, three successes, nothing exercised twice and nothing exercised wrong. This
run drove the two branches that were left, and **both of them were broken** — neither in a way
any check on #94, or any test in `test_desktop_client.py`, could have seen.

### Multi-turn, which had never been run at all

The `pendingUser` change decides *when* a turn joins `history`, and the only thing that can
exercise it is a **second** turn. The first run drove one. The structural test asserts there is
exactly one `history.push(` call site, which proves the shape of the fix and would pass just as
happily against a `pendingUser` that is never read.

Three turns, each answered from the transcript rather than from the prompt in front of it:

| Turn | Asked | Answered | Reading |
|---|---|---|---|
| 1 | "my rig ID is RAVEN-41 … reply with only the word noted" | `Ravensnest-41` | 7 tokens · 0.15 s · 46.8 tok/s |
| 2 | "What rig ID did I just give you?" | `Ravensnest-41` | 7 tokens · 0.1 s · 70.7 tok/s |
| 3 | "In my first message, what single word did I ask you to reply with?" | `Noted.` | 3 tokens · 0.06 s · 48.5 tok/s |

Turn 2 and turn 3 are deliberately different questions. Turn 2's answer is a string that appears
nowhere in turn 2's own prompt, so it can only have come from the stored **assistant** half.
Turn 3's answer appears nowhere in any assistant output — "noted" was only ever in turn 1's
**user** half — so it is the one that proves the user role carried too, and carried in the right
order. One of those two turns on its own would not have distinguished the halves.

### A failed turn, which is what `pendingUser` exists for

Driven with a 100,001-character prompt against `MAX_PROMPT_CHARS = 100_000`, so the API refuses
it and the client takes the `catch` branch. Three things were true afterwards and all three
needed checking:

* the error rendered, **Send came back enabled** — no wedge;
* the next turn still answered `Ravensnest-41` (7 tokens · 0.12 s · 59.3 tok/s), so the failed
  turn left no half-written pair behind. That is the fix working, measured;
* the message itself was wrong, and it is the reason this run was worth doing.

### Three bugs this run found

**1. Every validation error read "HTTP 422" and nothing else.** `describe()` in `main.rs` read
`detail` as a string. FastAPI answers an `HTTPException` that way but answers a *validation*
failure with `detail` as a **list of objects** — so the one status code that always knows
exactly what is wrong was the one status code the window could say nothing about. It now reads
`HTTP 422: body.prompt — String should have at most 100000 characters`. Three Rust tests cover
it, and `input` is deliberately never read: it echoes the rejected value in full, so quoting it
would answer a too-long prompt by printing the too-long prompt.

**2. The transcript's scroller was on the wrong element.** `.transcript` declares
`overflow-y: auto` and could never use it, because `body` was `min-height: 100vh` — the flex
column is then free to grow past the viewport, every child grows with it, and the box is always
exactly as tall as its content. The page scrolled instead. With one long turn the composer and
the Send button went off the bottom of the window, and `transcript.scrollTop =
transcript.scrollHeight` in `app.js` — the line that keeps a stream in view — was writing to an
element that does not move. `height: 100vh` plus `min-height: 0` down the chain fixes it, and
`.panel` gained `overflow-y: auto` in the same change: bounding the page without that would put
the bottom of a tall render out of reach, which is the data loss the house rule bars. Verified
after the fix on all three panels, including that the image panel still scrolls to its
measurement block.

**3. An error could render below the fold.** The transcript is scrolled on send and on each
delta; an error arrives after both. The 422 above landed twelve wheel clicks down, so the window
showed a sent turn, no reply and no error — which reads as *still thinking*, not as *refused*.
`fail()` now calls `scrollIntoView`.

None of these is a bug a reader would have found in the source. All three needed the program run.

### Re-read on the same tree

* `cargo test` — **6/6**. It was 3/3, and that figure had been taken **before**
  `capabilities/default.json` and the window `label` existed, so it was carried, not measured.
  Three of the six are new and cover `describe()`.
* `apps/test_desktop_client.py` — **36 passed** (was 32).
* RavenCalc, `simplify` of `x**2*sin(x)` — **0.0051 s (measured, CPU — no GPU lock taken)**,
  `verified — subtracted the simplified form from the original`, `exact: no`, `engine sympy
  1.13.3`.
* Image, 768×768, 4 steps, seed 1497065716 — **11.37 s (measured, queue excluded)**, 461071
  bytes, `SymonImage F1 q4_k`, `/api/gen/gen-1787307359933-1497065716.png`, decoded in the
  window.

### One test was wrong, and it went red for an innocent word

`NoSecondPermissionGateTests` forbids the substring `pty` in either half. `pty` is inside
`empty`, so a `parts.is_empty()` in the new `describe()` turned it red — the same trap as the
`MIT` rule in `.claude/CLAUDE.md`, where most matches are limits/limited/submit/emits. The fix
subtracts the colliding word rather than switching to a word boundary, and the reason is worth
keeping: `\b/dev/tty` never matches at all, and every real spelling of the forbidden thing
(`openpty`, `portable_pty`) is glued to another word, so a boundary would skip exactly the cases
worth catching while still reading as strict. Checked against all five spellings.

### Two more notes for whoever drives this next

* **`pkill -f` and `pgrep -f` match their own wrapper.** Both killed the driving shell here
  (exit 144), twice, including with the `[s]ymoneural-desktop` bracket trick — the script's
  *other* lines still contain the literal path. Put the kill in its own invocation, or resolve
  the pid through `/proc/<pid>/cmdline` and `kill` that.
* A 100 kB prompt is ~900 rendered lines. `xdotool click --repeat 1200 --delay 2 5` reaches the
  bottom; clicking one wheel event per process does not, and takes minutes.

## What is still not covered

* Only the `deb` bundle target is configured, and no bundle has been built or installed. The
  readings above are all from `cargo run`, i.e. the dev binary.
* No test drives the window automatically. The `xdotool` scripts that produced these readings
  were throwaway; re-running them means writing them again from the recipe above. Both runs
  found a real bug, so the case for a sixth `tests/*.mjs` suite is now made by evidence rather
  than by principle — but a Tauri window is not a browser page and `frontend.mjs`'s harness does
  not reach it, so this is not a small piece of work and is not pretended to be one.
* The API host and port are a compiled constant, so the client cannot be pointed at a spare-port
  instance without editing `main.rs` and rebuilding. Everything above was therefore measured
  against the **live service on :8800**, which is the one thing here that is not isolated.
* The in-stream `{"error"}` frame — `api.py:2308`, emitted when the chat surface will not
  start — is still only **read**, not driven. The `catch` branch above is the neighbouring path
  and shares the guard that matters (`fail()` does not clear `streaming`, so `finally` always
  re-enables the button), but driving the frame itself would mean taking the public API down,
  and it is proxied to the internet by `ops/Caddyfile`. Recorded as read rather than claimed as
  measured.
