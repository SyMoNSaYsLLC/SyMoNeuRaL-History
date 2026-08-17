# SyMoNeuRaL — working agreements

Repo for symoneural.com: the public site, the live playground behind it, the CUDA engine, and
the engineering manual the site's numbers come from.

## Parallelise builds

**Run as many agents concurrently as quality allows.** Compiles, model downloads and fine-tunes
occupy the machine for tens of minutes; that wall-clock should be filled with independent work,
not spent watching a progress bar. Launch subagents in one message so they actually run in
parallel. The GPU is available to agents that genuinely need it.

Scope agents to files nobody else is writing. The real hazard here is the generator scripts:
`build_pages.py`, `build_rack.py`, `build_console.py` and `build_training.py` all rewrite
files under `site/`, so two writers in that directory will clobber each other. Safe parallel
tracks are read-only audits, brand-new standalone files, docs, and tests.

## The GPU is a single, contended resource

One RTX 5070 Ti, 15.92 GiB. Chat (~5 GB), image (~7 GB) and a QLoRA run (~12 GB) cannot coexist.

- Everything touching the GPU goes through `gpu-governor.sh`, ideally as
  `gpu-governor.sh with <surface> -- <cmd>`, which always releases even on crash.
- **Hold the lock for a job, never for a process lifetime.** Residency (weights loaded) and
  work (using the card) are separate. Holding the lock while a model is merely resident and
  idle locks every other process out — including the CLI — until the acquire timeout.
- **Never call a bare `release`.** Name the surface (`release chat`). An unscoped release once
  destroyed a running fine-tune's lock from the API's shutdown hook.
- The governor waits for VRAM to drain below a 1.5 GB floor between tenants. Killing a process
  returns the lock before CUDA has torn down, and the next tenant OOMs at step 0.
- `train` is never evicted to serve a page view.
- RavenCalc (SymPy, CPU) deliberately never takes the lock. That is what lets it speculatively
  pre-compute while the GPU is loading.

## Python environments

The base interpreter is pinned at exactly **7 packages** and must never be extended — check with
`pip freeze | wc -l`. `numba-cuda` silently downgrades numpy, and three other packages pin
conflicting `cuda-core`/`cuda-python` versions.

- The serving API deliberately uses only the **system** interpreter: fastapi, uvicorn and sympy
  are already OS packages, so there is no virtualenv in the serving path.
- Training has its own venv at `training/.venv` (torch cu128 — Blackwell sm_120 needs it).
- Anything else that conflicts gets its own isolated venv.

## Honesty rules for anything user-facing

These are the product, not decoration. The site's entire argument is that its numbers are real.

- Label every figure: **measured** on this machine, **vendor** specification, or **projected**
  arithmetic. Never present a projection as a result.
- Never invent pricing. Direct pricing questions to symonsayadmin@symoneural.com.
- No decorative status indicators. Every LED and gauge on the site reflects a real reading; a
  fake activity light is the one dishonest pixel on a page arguing for measurement.
- Publish negative results too — the PCIe Gen 3 ×8 ceiling and the failed multi-stream overlap
  are on the site deliberately.
- Layout changes must not drop data. Fold long content into `<details>`; do not trim it.

## Build and deploy

```bash
./fetch-models.sh                 # weights -> models/ (ungated, Apache-2.0 sources)
python3 build_pages.py          # playground pages
python3 build_rack.py           # live rack -> site/index.html
python3 build_console.py        # control board + folds -> site/index.html
python3 build_training.py       # manual -> site/training.html
./playground.sh on|off|status     # the live API (off is the kill switch)
sudo ./deploy.sh                  # site/ -> /var/www/symoneural (needs a password)
```

The generator scripts are idempotent and must stay that way — `build_console.py` once nested
folds inside folds when run twice.

## Branding

"MIT AI Training" is purged everywhere user-facing. Watch out: most `MIT` substring matches in
this corpus are ordinary words — limits, limited, submit, emits — so never blind-replace. Only
whole phrases and local filesystem paths.
