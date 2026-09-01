# control/ — the board

Everything you need to run and test this server from one folder. **Nothing here implements
behaviour.** Each script is a thin wrapper over the tool that already does the job
(`scripts/`, `ops/`, systemd), so there is one implementation of everything and this folder
cannot drift from it. Delete `control/` and the server is unaffected.

## Start here

```bash
control/status-all.sh          # one screen: units, surfaces, GPU, engines, disk
```

## Launchers

| Command | What it does |
|---|---|
| `launch-api.sh start\|stop\|status\|log` | The inference API — chat, image, ravencalc, remix. Prefers the systemd unit. |
| `launch-llm-server.sh status\|warm\|release` | Chat surface + the card it runs on. |
| `launch-image-server.sh status\|test\|release` | Image surface. `test` evicts chat from the GPU. |
| `launch-dispatchos.sh status\|open\|enable` | DispatchOS surface (lives in the API process). |
| `launch-studio.sh start\|stop\|status\|open\|enable` | Studio routes + the render UI on :8188. |
| `gpu.sh status\|release <surface>\|release-all\|nvidia` | Who holds the card, and take it back. |
| `test-all.sh py\|node\|progress\|all` | Run the suites. |

## The one thing that will confuse you

**Most "servers" here are not separate processes.** chat, image, dispatchos, studio and the
rest are surfaces *inside* the single API process, gated by `SYMONEURAL_*_ENABLED`. So:

* "launch the LLM server" = have the API up; the engine is spawned on demand under the governor.
* "launch dispatchos" = have the flag on and the API up.

The genuinely separate processes are the **API** (:8800), the **render UI** (:8188), and
**Caddy**, which proxies the public site to the API.

Turning a surface on is a systemd drop-in written by `scripts/enable-surfaces.sh` (needs
sudo) — the `enable` subcommands above just call it.

## One GPU, one job

The card does one thing at a time and the queue is a property of the hardware, not a policy.
Generating an image evicts chat. If something is wedged, `gpu.sh status` names the holder and
`gpu.sh release-all` takes it back.

## Where the real things live

| | |
|---|---|
| API source | `backend/api.py`, surfaces in `backend/apps/` |
| Utilities | `scripts/` — `gpu-governor.sh`, `symoneural.sh`, `fetch-models.sh`, … |
| Ops & units | `ops/` — `Caddyfile`, `*.service` templates, `install-runtime.sh` |
| Engines | `engines/` — `symoneural-llm`, `symoneural-diffuse`, `symoneural-ui` (derived, gitignored) |
| Runtime state | `run/` — logs, `dispatchos.db`, pidfiles |
| Rules | `.claude/CLAUDE.md`; build/GPU/env → `docs/ENGINEERING.md`; test counts → `docs/ops/MEASUREMENTS.md` |
