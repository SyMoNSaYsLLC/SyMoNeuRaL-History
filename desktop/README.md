# SyMoNeuRaL Code — the desktop client

**Status: the runtime is chosen and the choice is measured. The client itself is not built
yet.** What exists today is the terminal client (`bin/symoneural-code` →
`bin/symoneural-cli repl`) and the protocol it speaks, specified in
`docs/specs/code-client-spec.md`. This file records one decision — *what the desktop window
should be made of* — and the measurements that decided it, so that nobody has to take the
download twice.

Garrett, 2026-08-20, lifting an earlier browser-only restriction: *"If an Electron or
lightweight native build is what it takes to get the right feel for the desktop client, go
for it. Just keep the footprint reasonable and ensure it integrates cleanly with the engine
you've already built in bin/symoneural-cli."*

"Keep the footprint reasonable" is a measurable instruction, so it was measured rather than
argued.

## The decision

> **Revised 2026-08-20, before anything was built. See *The decision, revised* below.** The
> window is GTK3 in Python as stated here, and every measurement in this file stands and was
> not re-taken. What changed is what goes *inside* the window: a VTE terminal running the real
> client, not a WebKit view rendering a page. The reason is in that section, and it is a
> consequence of this file's own argument in *How it integrates with the engine* — it just was
> not followed through to the runtime when this was written.

**A GTK3 + WebKit2GTK 4.1 shell, in Python, driving the same `bin/symoneural-cli` engine.**
Not Electron. The reasons are all in the table below: it is the lightest windowed option by
some distance, it adds **zero** new bytes to this machine because both libraries are already
installed as Debian packages, and being Python it calls the existing engine directly instead
of shelling out across a language boundary.

Two things that decision gives up, stated rather than buried:

- **It is Linux-only.** Electron would be cross-platform. That is an acceptable trade *today*
  because the client's only user runs it in an xrdp session on this box, and
  `docs/specs/coder-spec.md` §2g is the reason it runs there rather than anywhere reachable.
  A cross-platform build is a real requirement change and would reopen this file, not
  contradict it.
- **WebKit is not Chromium.** The site is tested against Chrome (`tests/*.mjs` drive system
  Chrome via Playwright), so a WebKit shell is a second engine that nothing currently
  asserts against. If the desktop client ships, it needs its own smoke assertion; that is
  a task, not a footnote.

## What was measured, and how

**All figures below were measured on this machine on 2026-08-20 at `ebef4fc`.** Each window
was pointed at the live API on `http://127.0.0.1:8800/`, left to settle for 14 s, and then
sampled; the terminal-client row is a `repl` session held open under a pty instead. Two runs
each, both printed, so the spread is visible rather than averaged away.

Memory is **PSS**, summed over the real process tree — not RSS. Every one of these candidates
is multi-process and they share their mapped libraries heavily, so summed RSS double-counts
the shared pages and flatters nothing consistently.

| option | processes | memory (PSS) | new bytes on disk |
|---|---|---|---|
| terminal client, `repl` under a pty | 3 | **12.8 MiB** | 0 |
| **GTK3 + WebKit2GTK 4.1** | 3 | **226.7 / 227.0 MiB** | **0** — already apt-installed |
| Electron 43.4.1 | 9 | 366.5 / 367.5 MiB | **312.3 MiB** unpacked dist |
| system Chrome, `--app=` | 17 / 18 | 423.2 / 436.6 MiB | 0 — already installed |

Disk, in more detail, because "new bytes" is the number that decided it:

    electron/dist unpacked            312.3 MiB
    the whole npm tree                325.0 MiB
    plus ~/.cache/electron (the zip)  119.8 MiB   -- kept, so a reinstall is not a redownload
    libwebkit2gtk-4.1-0                94.4 MiB   -- ALREADY INSTALLED (Debian package)
    python3-gi                          0.8 MiB   -- already installed
    gir1.2-webkit2-4.1                  0.6 MiB   -- already installed

The WebKit rows are not free in absolute terms; they are free *here*, which is the only
comparison that answers Garrett's question. This also lands where he pointed on packaging —
*"i didnt mean binaries i meant debian packages"* — without any extra work: the runtime is
already a `.deb` this machine trusts, so the desktop client is a script plus a `.desktop`
file, not a bundle.

Two results worth keeping because they are counter-intuitive:

- **Electron is lighter at runtime than reusing the installed Chrome.** 367 MiB across 9
  processes against 436 MiB across 18. `--app=` mode still starts a full browser — network
  service, GPU process, utility processes, profile machinery — where an Electron app starts
  only what it declares. If Electron were chosen, "just use the browser they already have"
  would be the *worse* option on memory as well as on feel.
- **The window is where the cost is, not the client.** The engine that does all the work runs
  in 12.8 MiB. Every figure above it is the price of rendering, which is the honest way to
  read the table: the desktop client is a viewport bolted to a 12.8 MiB program.

### Caveats on these numbers

- **Software rendering, all four.** Every launch logged
  `MESA-LOADER: failed to open dri: .../gbm/dri_gbm.so: cannot open shared object file:
  Permission denied`, so none of them had GPU compositing. It applies equally to all four, so
  the ranking holds, but the absolute figures would move with hardware acceleration and
  should be re-measured before anyone quotes them for a machine that has it.
- **One blank window each, no session open.** These are startup footprints, not the cost of a
  long conversation with rendered output.
- **A discarded reading, recorded so nobody trusts it from a scrollback:** the first pass
  reported *92 processes, PSS 7226.9 MiB* for one Electron window. That was an instrument bug,
  not a result — `pstree -p` lists threads as well as processes, and `/proc/<tid>/smaps_rollup`
  reports the whole process, so each process was counted once per thread. Roughly 8× the truth
  and plausible enough to publish. The fixed instrument walks `PPid` from `ps -eo pid=,ppid=`
  and counts processes only.

## The decision, revised

**GTK3 + VTE 2.91, in Python, hosting `bin/symoneural-cli repl` in a real terminal.** WebKit
is not used. The footprint table above is unaffected — VTE is smaller than WebKit on every
axis in it and is likewise already installed (`gir1.2-vte-2.91`, alongside the WebKit
typelib) — so this revision does not overturn a measurement. It overturns an assumption.

**The argument that moved it: a web client is a second implementation of the permission
gate.** *How it integrates with the engine*, below, already says a second implementation of
that handshake is a second place for it to be wrong. That was written about the session and
the event loop and it applies with far more force to the gate, because the gate is the part
where being wrong means a command runs that nobody agreed to. Three things make it concrete:

- **The seam has already produced bugs — two of them, in one afternoon.** `api_json` answers
  `(status, body)`, and the client treated that pair as a dict in two places: `/permissions`
  traced back and took the whole session down, and the post-approval path handed the model
  `[200, {...}]` where a tool's output belongs — so a `403 denied` from the router reached it
  looking exactly like success. Both are fixed. Both lived at precisely the join a second
  client would have to re-cross.
- **`approve()` opens `/dev/tty` on purpose, and a browser has no equivalent.** It does not
  read stdin, because in `agent "..."` stdin may be a pipe carrying the query and in the repl
  it is the transcript — neither is a human. A JS client would need its own fresh answer to
  *who is the human here*, and every fresh answer to that question is a new way to fail open.
  VTE gives the real client a real pty, so `approve()`, `APPROVE_KEYS`, the re-ask on an
  unrecognised key and the refusal when the terminal goes away are the code already under
  test rather than a parallel copy.
- **There was no page to point at anyway.** `site/studio.html` is 311 lines and contains zero
  occurrences of `api/studio/agent`, `permission_required`, `EventSource` or `tool_call`. It
  describes the Studio; it does not speak the protocol. So "render the site's own chat
  surface" — named as an open question in *Not done here* — was never actually on the table,
  and the alternative was always a purpose-built page, which is to say a whole second client.

**WebKit was not ruled out on capability, and the reading that shows it is worth keeping.**
Before this was decided, the runtime was pointed at the real surface rather than at a test
page: `site/livestack` in WebKit2GTK 4.1, **measured 2026-08-20**, returned 13 rack units
built client-side from `/api/status`, the dark theme applied (`rgb(14, 16, 15)`), zero JS
errors, and `OPEN ws://127.0.0.1:8877/api/ws` — a real WebSocket upgrade, confirmed on the
server side too. That answers the *"WebKit is not Chromium"* caveat above for the site's own
pages: the shell would have worked. It is set aside for the gate argument, not for a defect.

The cost of this revision, stated rather than buried: **the desktop client renders a
terminal**, so it cannot show an image the way a browser can. `bin/symoneural-cli` renders
markdown for a terminal (headings, emphasis, code blocks, both halves of every link), which
covers text, but a render from `/api/gen/<name>` stays a path on screen. If that becomes the
thing worth fixing, the honest fix is a WebKit pane that displays *renders* — a pane that
exists to justify a word in a check would be the decorative-status-light rule with extra
steps, and this file is not going to add one on spec.

## How it integrates with the engine

The shell owns the window and nothing else. It does not reimplement a session, a permission
prompt, or the event loop — those are `bin/symoneural-cli`'s, and
`docs/specs/code-client-spec.md` §3 is emphatic about why the *client* must run an approved
tool call with the exact arguments it displayed. A second implementation of that handshake is
a second place for it to be wrong.

So the intended shape is: the shell renders, the engine decides, and they talk over the same
`--output-format stream-json` interface any other program would use. That keeps one
implementation of a session, which is the same argument `bin/symoneural-code`'s header already
makes for itself.

## Not done here

Building it. The window, the `.desktop` entry and the smoke assertion named above are
outstanding, and they are #78's remaining items rather than this file's.

The third thing on this list — *whether the desktop client renders the site's own chat surface
or a purpose-built one* — is **answered and struck**, by *The decision, revised*: neither. It
hosts the terminal client. `site/studio.html` was measured and does not speak the protocol, so
the first option did not exist, and the second is a second gate. The WebKit smoke assertion
that this file called "a task, not a footnote" is therefore not needed for the shell; the
assertion the shell does need is that the pty it allocates is a real one, which is what the
prompt in `approve()` depends on and what the existing `ApprovePromptTests` already proves
against `script(1)`.
