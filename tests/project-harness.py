"""Serve ONLY the project router plus the static site, for driving `site/project.html`.

    python3 tests/project-harness.py &      # 127.0.0.1:8899
    node tests/project.mjs

Why this exists rather than pointing the browser test at the live API on 8800:

* The surface is off unless `SYMONEURAL_PROJECT_ENABLED` and `SYMONEURAL_PROJECT_TOKEN` are set, and
  those belong in the systemd unit environment on a configured box. A test that needed
  the production token could not run on a clean clone.
* Importing `backend/api.py` pulls in the governor, the resident marker and the model
  loaders. A second full instance could contend for `run/gpu.lock.d`, and
  `.claude/CLAUDE.md` is clear that two holders of that mutex is a silent OOM that looks
  like a CUDA fault. Nothing here imports the governor.
* The store is a fresh temporary directory on every start, so a run cannot pollute
  `run/project/store.db` and cannot inherit rows from the previous run.

The router mounted here is the real one. Unlike `apps/project/test_project.py`, which
mounts it on a bare app, this harness also mounts `StaticFiles` at `/` -- which is the
production shape, and the reason `/api/project` must be used without a trailing slash.
"""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"

# Set before importing the package: `enabled()` reads the environment when it is called,
# but the store resolves its default database path at import time.
os.environ["SYMONEURAL_PROJECT_ENABLED"] = "1"
os.environ["SYMONEURAL_PROJECT_TOKEN"] = "harness-token-not-a-secret"
os.environ["SYMONEURAL_PROJECT_DB"] = str(pathlib.Path(tempfile.mkdtemp()) / "store.db")
os.environ["SYMONEURAL_PROJECT_ROOT"] = str(ROOT)

sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI                      # noqa: E402
from fastapi.staticfiles import StaticFiles      # noqa: E402
from apps import project                         # noqa: E402

app = FastAPI()
app.include_router(project.router, prefix="/api/project", tags=["project"])
# Mounted LAST, exactly as api.py does, so it never shadows an API route.
app.mount("/", StaticFiles(directory=str(ROOT / "site"), html=True), name="site")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")
