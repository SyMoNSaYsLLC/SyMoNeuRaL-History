# SyMoNeuRaL Desktop Client

A native window over the local API: **chat**, **image generation** and **RavenCalc**, against
`127.0.0.1:8800`. Task #94.

```bash
cd desktop-client/src-tauri && cargo run          # dev
cd desktop-client/src-tauri && cargo build --release
cd backend && python3 -m pytest apps/test_desktop_client.py -q
cd desktop-client/src-tauri && cargo test          # the Rust half's own three tests
```

The API has to be up for the window to show anything: `./scripts/symoneural.sh on`, or your
own instance on a spare port — but note the port is compiled in, so a spare-port instance
needs `API` in `src-tauri/src/main.rs` changed and a rebuild. That is a deliberate cost; see
*The host is not configurable*, below.

## This is not `desktop/shell.py`, and it does not replace it

There are two desktop programs in this repository and they have opposite architectures. That
is not duplication, and the difference is worth understanding before touching either.

| | `desktop/shell.py` | `desktop-client/` |
|---|---|---|
| what it is | GTK3 + VTE terminal window | Tauri window over the HTTP API |
| wraps | `bin/symoneural-cli`, in a pty | nothing — it *is* the client |
| speaks to the API | **never** | that is its whole job |
| tests | `backend/apps/test_desktop_shell.py`, 15 | `backend/apps/test_desktop_client.py` |

`test_desktop_shell.py` asserts that the shell contains none of `urllib`, `requests`,
`httpx`, `api_json`, `/api/` or `WebSocket`. That is deliberate and `desktop/README.md` gives
the reason: a web client would be a second implementation of the permission gate, and
`approve()` in `bin/symoneural-cli` opens `/dev/tty` rather than reading stdin, so a browser
cannot answer it. A program that calls `/api/chat` therefore cannot ever make that test pass.

Asked which one he wanted, Garrett kept both: `shell.py` and its 15 tests untouched, this as
a separate program with its own test file. **Do not edit `desktop/shell.py` or its tests from
here**, and do not add a permission gate to this client — the pty one is the only one, and a
second would be the exact failure that argument was written to prevent.

## Tauri, not Electron

Chosen on a measurement, not a preference. On Linux Tauri renders through the system
WebKitGTK instead of bundling a Chromium, which is the only reading of "lightweight" that
survives being checked. Everything it needs was verified present on this box **before** the
choice was made rather than discovered afterwards: webkit2gtk-4.1 2.52.5, javascriptcoregtk-4.1
2.52.5, libsoup-3.0 3.6.5, gtk+-3.0 3.24.49, glib-2.0 2.84.4, cargo/rustc 1.97.1, and
crates.io resolving — a throwaway crate added serde 1.0.229 and linked a binary. The 403 seen
earlier was a bucket root and proved nothing about the index.

The scaffold is hand-written and builds with plain `cargo build`; `tauri-build` reads
`tauri.conf.json` from `build.rs`, so the Tauri CLI is not required. **There is no
`package.json`, no bundler and no `node_modules`** — the frontend is three static files under
`ui/`.

Full dependency-licence reading — 433 crates, no GPL, five MPL-2.0 — is in `LICENSE`.

## Every request is made by Rust, and the page names no host

`ui/app.js` contains no `fetch()`. It calls four commands in `src-tauri/src/main.rs`:
`api_get`, `api_post`, `api_bytes` and `api_chat`. Three reasons, in order of how much they
matter:

1. **`backend/api.py` mounts no CORS middleware, and it should not gain one for us.** `/api*`
   is proxied to the public internet by `ops/Caddyfile`. A `fetch()` from the webview's origin
   would need an `Access-Control-Allow-Origin` on the public serving path, added to suit a
   private consumer. Routing through Rust means no browser origin policy is involved at all,
   because no browser is making the request.
2. **The host is not configurable.** `API` is a constant in compiled code that the page cannot
   reach. `app.js` names *paths* — `/api/chat` — and never a host, so there is no base URL to
   edit and no config file that could point this at a remote box. `reqwest` is built with
   `default-features = false` and no TLS backend, so the binary structurally cannot open an
   `https` connection to a remote host either. A guarantee that survives someone editing a
   file is worth more than a constant nobody re-reads.
3. **`checked()` refuses anything not under `/api/`**, so a bug in the page becomes a refusal
   rather than an arbitrary request. `//example.com/api/x` is a valid relative URL to a
   browser and is not a valid argument here; `cargo test` covers that case and six others.

The window's content-security-policy names **no network origin at all** —
`connect-src ipc: http://ipc.localhost`, `img-src 'self' data:`. Renders come back through
`api_bytes` as data URLs for exactly that reason.

### Streaming

`/api/chat` is Server-Sent Events, so it cannot be a command that returns a value. Rust parses
the stream — accumulating across chunk boundaries, since a frame can be split at any byte —
and re-emits each frame on a Tauri event that `app.js` listens for. **Frames are forwarded
unchanged.** Nothing on the Rust side invents, rounds or recomputes a field.

## The honesty rules, and where they show up in the code

These are the product, per `.claude/CLAUDE.md`, and most of #94's checks measure them.

- **`check.passed` is three-valued.** RavenCalc returns `true`, `false` or `null`, and `null`
  means the engine could not confirm the result. It renders as **"unconfirmed"** in its own
  colour — never a tick, never a cross. `performed: false` renders as "not performed" rather
  than as blank space, because a gap where a verdict belongs reads as "fine".
- **`tok_per_s` is the server's measurement and is displayed as sent.** This client never
  divides tokens by seconds itself; a rate computed against a browser clock is a different
  quantity wearing the same name. When the server reports `null` the line says "rate not
  reported".
- **No decorative status indicators.** The dot in the header has an `unread` state that is
  deliberately not a colour, and it is only ever set by a completed `/api/status` read. The
  text beside it names the units and their real states.
- **No `text-overflow` anywhere in `app.css`, and no `nowrap` on anything carrying a
  reading.** An ellipsis is data loss with extra steps. Long content wraps, or folds into a
  `<details>` — which is what the exact-tree block on the RavenCalc panel does.

## What the checks on #94 do *not* measure

They confirm the files exist and say what they should say. `build_progress.py`'s vocabulary
cannot run a build, so **18/18 will read 100% on a client that has never been opened**. The
readings to trust are a real window, `cargo test`, and
`cd backend && python3 -m pytest apps/test_desktop_client.py -q`.

That sentence was written as a caution and then came true the same day: **#94 archived itself
at 18/18 while chat did not work at all.** Tauri v2 gates its core plugins, there was no
`capabilities/` directory, and so the page's `listen()` was refused — the four commands in
`main.rs` are the app's own and need no grant, which is exactly why `/api/status` and RavenCalc
worked and hid it. The turn scaffold rendered and no token ever arrived, with no error anywhere
to read. `src-tauri/capabilities/default.json` is the fix and
`TheCapabilityGrantsExactlyWhatThePageUsesTests` is the assertion that keeps it.

**`SMOKE.md` is the missing half of the evidence** — every panel driven in a real window, with
the figures each one reported and the recipe for re-running it. Read that before trusting a
percentage on this task.
