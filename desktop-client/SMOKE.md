# Smoke readings — the desktop client, driven in a real window

`backend/apps/test_desktop_client.py` is structural: it reads the two sources and asserts what
they may and may not contain. Nothing in it can tell you the program starts, and nothing in it
noticed that chat was completely broken. This file is the other half, and it exists because of
that: **every reading below was taken by driving the actual window**, and the readings are
stamped with the tree they were taken on rather than carried forward.

**Measured 2026-08-21 on the tree committed as `709478d` plus the working changes that became
the commit this file sits beside.** Chat, image and RavenCalc were each driven through the UI —
not through `curl`, and not by reasoning about `api.py`.

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

## What is still not covered

* Only the `deb` bundle target is configured, and no bundle has been built or installed. The
  readings above are all from `cargo run`, i.e. the dev binary.
* No test drives the window automatically. The `xdotool` scripts that produced these readings
  were throwaway; re-running them means writing them again from the recipe above.
* The API host and port are a compiled constant, so the client cannot be pointed at a spare-port
  instance without editing `main.rs` and rebuilding. Everything above was therefore measured
  against the **live service on :8800**, which is the one thing here that is not isolated.
