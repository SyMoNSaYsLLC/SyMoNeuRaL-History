# `symon-gateway`

The front-door HTTP gateway. Axum + Tokio + Reqwest, with payload validation in a Wasmtime
sandbox.

```
client ──▶ Caddy :443 (TLS, static) ──▶ symon-gateway :8000 ──▶ FastAPI :8800 ──▶ gpu-governor.sh
```

## Why it is here and not in `ops/gateway/`

**`ops/gateway/` is the blockchain licence gateway** — Solidity contracts, `gateway-cli.py`,
and the half of that system that holds a TRON signing key. `backend/apps/gateway/` is its
web-process half. Neither has anything to do with HTTP routing. Writing a Rust crate over
either would have destroyed working, key-bearing code.

"Gateway" now means three things in this repo. When you write it down, say which:

| Path | What it is |
|---|---|
| `symon-gateway/` | **this** — the HTTP front door |
| `ops/gateway/` | blockchain licensing, operator side (holds the key) |
| `backend/apps/gateway/` | blockchain licensing, web side (cannot sign anything) |

## Build and run

```bash
cd symon-gateway && cargo build --release
./target/release/symon-gateway
```

| Variable | Default | Meaning |
|---|---|---|
| `SYMON_GATEWAY_BIND` | `127.0.0.1:8000` | listen address |
| `SYMON_API_UPSTREAM` | `http://127.0.0.1:8800` | where `/api/*` goes |
| `SYMON_ENGINE_UPSTREAM` | `http://127.0.0.1:8800` | where `/v1/*` goes — see below |
| `SYMON_WASM_LIMITER` | `ops/middleware/limiter.wasm` | validator module |
| `SYMON_MAX_TOKENS` | `100000` | ceiling, estimated by whitespace |
| `SYMON_LOG` / `SYMON_LOG_JSON` | `info` / unset | filter; set the second for JSON records |

## Routes

| Route | Behaviour |
|---|---|
| `GET /healthz` | this process only — deliberately does **not** poll the upstream |
| `ANY /api`, `/api/{*path}` | forwarded verbatim to FastAPI, streamed |
| `POST /v1/chat/completions` | validated, then forwarded to the engine upstream |
| `ANY /v1/{*path}` | forwarded to the engine upstream |
| `GET /swagger-ui/` | Swagger UI, assets vendored into the binary |
| `GET /api-docs/openapi.json` | the OpenAPI document |

## Measured on this box, 2026-08-18

| Check | Result |
|---|---|
| `/api/status` through the gateway vs direct | **3818 B both**, same keys |
| `/api/chat` SSE through the gateway | deltas ~10 ms apart, **not batched** — passthrough confirmed |
| oversized payload (100,001 words) | **413** before anything reached the GPU |
| `/swagger-ui/` | **200**, `text/html`, vendored assets |
| GPU lock after a streamed chat | released; `run/gpu.lock.d` absent |
| graceful SIGTERM | logged `symon-gateway stopped`; `:8000` freed |

## Two things that are NOT done, and you should know before trusting this

### 1. There is no `/v1/chat/completions` upstream to forward to

`SYMON_ENGINE_UPSTREAM` defaults to the FastAPI control plane, which has **no OpenAI-compatible
surface**. `POST /v1/chat/completions` therefore currently returns **405** — that is FastAPI's
static mount answering, not a route.

The reason it cannot simply point at llama.cpp is the important part. On this machine
`llama-server` is **not a service**: `backend/api.py:113` spawns it as a child process per job,
while holding the mutex in `scripts/gpu-governor.sh`. Nothing listens on :8080 or :9001 between
jobs. A gateway forwarding straight to :8080 would connect to nothing most of the time, and
when it did connect it would be using the GPU **without the lock** — which `.claude/CLAUDE.md`
forbids outright, and which would contend with a QLoRA run for VRAM that cannot be shared.

The fix is a `/v1/chat/completions` route in `backend/api.py` that wraps the existing governed
chat path in the OpenAI response shape. The governor is Python's; the gateway should not learn
to take the lock.

### 2. The WASM validator is not compiled

Go is not installed here, so `ops/middleware/limiter.wasm` does not exist. The gateway loads it
if present and otherwise enforces the same ceiling natively, reporting
`"validator": "native-fallback"` on `/healthz` rather than quietly appearing to be sandboxed.

Build it with **`GOOS=wasip1`**, not `GOOS=js`:

```bash
GOOS=wasip1 GOARCH=wasm go build -o ops/middleware/limiter.wasm ./ops/middleware
```

`GOOS=js GOARCH=wasm` emits a module that imports the `gojs` namespace and expects
`wasm_exec.js`; Wasmtime has no JavaScript to give it, so that build fails at *instantiation*
with unknown-import errors rather than at build time. `//go:wasmexport` also needs **Go 1.24+**.

## The open topology question

Whether Caddy stays in front of this or is replaced by it is **not decided**, and nothing here
assumes either answer. Replacing Caddy means this process takes on:

- **ACME/TLS** with automatic renewal (Caddy does this with no configuration and no cron),
- **static file serving** from `/var/www/symoneural`,
- **the WebSocket upgrade on `/api/ws`** — which is precisely why Apache was dropped for Caddy.
  Under Apache that needed `mod_proxy_wstunnel`, which was never enabled, so the rack's "pushed
  live over one socket" claim silently degraded to polling. Anything replacing Caddy must carry
  the upgrade or that claim breaks again.

Until that is settled, the safe deployment is Caddy in front, which is also the only shape that
does not risk the live site.
