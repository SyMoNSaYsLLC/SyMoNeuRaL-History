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

Building it. The window, the `.desktop` entry, the smoke assertion named above, and the
decision about whether the desktop client renders the site's own chat surface or a purpose-
built one are all outstanding, and they are #78's remaining items rather than this file's.
