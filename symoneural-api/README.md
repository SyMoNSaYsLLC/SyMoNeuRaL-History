# symoneural-api

The API and orchestration runtime. **First-party, tracked.**

`docs/architecture/COMPONENT-MAP.tsv` has recorded this as a component all along:

```
symoneural-api  SERVICE_API  IMPLEMENTED  PRODUCTION  backend/api.py  Python
                                          API/orchestration :8800
```

It was the only runtime without a folder of its own. The reasoning for giving it one is the
owner's and it is right: **the API is not the web runtime and not the language runtime**, and
it can be used without either. A runtime that stands alone should be addressable alone.

## What is here, and what is deliberately not

| | |
|---|---|
| `bin/symoneural-api` | first-party entry point. Resolves the repo root by marker search, `chdir`s, and `execv`s the application. |
| `LICENSE` | SyMoNeuRaL Proprietary. Nothing in this folder is derived from anyone. |
| **not** the application | `backend/api.py` (4,097 lines) and `backend/apps/` stay where they are. |

Moving a live production service's 4,097 lines to gain a tidier path is a large change with
no functional gain, and 15,697 tracked files under `backend/` expect it where it is. So this
folder is the **runtime**: the licensed, documented, named way to start it. The application
it starts is a separate concern, which is the same split `symoneural-web` already uses.

## Use it

```bash
bin/symoneural-api --check      # resolve and report; starts nothing
bin/symoneural-api              # foreground
curl -s localhost:8800/api/status
```

## Pointing the live unit at it

The service still runs `python3 backend/api.py` directly. Repointing it needs root, so it is
the owner's to apply:

```bash
sudo mkdir -p /etc/systemd/system/symoneural-api.service.d
sudo tee /etc/systemd/system/symoneural-api.service.d/10-runtime-entry.conf <<'CONF'
[Service]
ExecStart=
ExecStart=/home/google/Symoneural/symoneural-api/bin/symoneural-api
CONF
sudo systemctl daemon-reload && sudo systemctl restart symoneural-api
curl -s -o /dev/null -w '%{http_code}\n' localhost:8800/api/status   # expect 200
```

`Type=exec` keeps supervising the right process because the entry point `execv`s rather than
spawning a child — systemd ends up watching the interpreter it started, not a middleman.

Rollback is `sudo rm -rf /etc/systemd/system/symoneural-api.service.d` plus a reload and
restart. **Restarting the API also drops the resident model**, which the language runtime
reloads on the next request that needs it.
