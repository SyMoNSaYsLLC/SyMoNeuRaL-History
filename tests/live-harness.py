"""Serve ONLY the live router plus the static site, for driving `site/live.html`.

    python3 tests/live-harness.py &      # 127.0.0.1:8897
    node tests/live.mjs

Why this exists rather than pointing the browser test at the live API on 8800:

* Pointing it at the running service would test what is DEPLOYED rather than what you wrote,
  which `.claude/CLAUDE.md` calls out as the way to spend an afternoon hunting a bug you
  already fixed.
* Importing `backend/api.py` pulls in the governor, the resident marker and the model
  loaders. `tests/live.mjs` must never take the GPU -- `frontend.mjs` and `studio.mjs`
  already both take the card and must not run beside each other, and a third suite in that
  set is a third scheduling constraint nobody will remember. Nothing here imports the
  governor.
* It needs OBS not to be running. The whole point of `apps/live`'s import graph is that the
  video path holds no credential and makes no connection, so a browser test of the video
  path must be able to run on a box that has never had OBS installed. No bridge is started
  here and `SYMONEURAL_OBS_PASSWORD` is never read.

## The fixture

`tests/fixtures/live/` holds six seconds of 320x180 test pattern as three real MPEG-TS
segments and a real playlist -- 76 KB, generated once with ffmpeg and checked in. It is a
real one on purpose: a hand-written `.m3u8` pointing at empty files would satisfy every DOM
assertion in `live.mjs` and prove nothing, which is #94's shape and the exact failure this
suite exists to catch. `live.mjs` asserts that the video element reaches `readyState >= 3`
and that `currentTime` advances, and only actual decodable video does that.

Every start builds a fresh temporary directory holding three sessions, because the three
states are what `hls.py` classifies and a test that only ever sees one of them is not
testing the classifier:

    finished    the fixture with its #EXT-X-ENDLIST intact
    live        the same segments, playlist with the trailer stripped, mtime now
    unservable  a playlist whose name contains a space, which is what OBS's DEFAULT
                Filename Formatting produces and what this API refuses to put in a URL

The temporary directory is never `backend/output/live`, so a run cannot delete, overwrite or
list one of his actual recordings.
"""
import os
import pathlib
import shutil
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"

FIXTURE = ROOT / "tests" / "fixtures" / "live"
assert (FIXTURE / "fixture.m3u8").is_file(), f"fixture playlist missing at {FIXTURE}"

# Explicitly ON. The surface defaults on, but a harness that relies on a default is a harness
# that goes red the day the default changes for a good reason.
os.environ["SYMONEURAL_LIVE_ENABLED"] = "1"

sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI                      # noqa: E402
from fastapi.staticfiles import StaticFiles      # noqa: E402
from apps import live                            # noqa: E402
from apps import news                            # noqa: E402

VOD_STEM = "2026-08-21_09-00-00"
LIVE_STEM = "2026-08-21_10-00-00"
BAD_STEM = "2026-08-21 11-00-00"                 # the space is the point


def _build_store() -> pathlib.Path:
    """Three sessions in a fresh temp directory. Returns the directory."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="symoneural-live-test-"))
    body = (FIXTURE / "fixture.m3u8").read_text()
    segments = sorted(FIXTURE.glob("fixture*.ts"))

    def lay(stem: str, *, ended: bool) -> None:
        text = body
        for i, src in enumerate(segments):
            shutil.copyfile(src, d / f"{stem}{i}.ts")
            text = text.replace(src.name, f"{stem}{i}.ts")
        if not ended:
            # Strip the trailer. This is what a playlist ffmpeg is still writing looks like,
            # and it is the ONLY difference between a live session and a finished one --
            # which is the claim the suite goes on to check from the browser.
            text = text.replace("#EXT-X-ENDLIST\n", "").replace("#EXT-X-ENDLIST", "")
        (d / f"{stem}.m3u8").write_text(text)

    lay(VOD_STEM, ended=True)
    lay(LIVE_STEM, ended=False)
    lay(BAD_STEM, ended=False)

    # The finished one is backdated so "newest first" has something to sort. The live one is
    # left at now: `hls.LIVE_WINDOW_S` is 20 s and a playlist not written to inside that
    # window is classified `abandoned`, not `live` -- so a long test run would reclassify it
    # underneath the browser. live.mjs keeps its live-state assertions early for that reason,
    # and this comment is here so the next person does not "fix" it by widening the window.
    old = time.time() - 7200
    for p in d.glob(f"{VOD_STEM}*"):
        os.utime(p, (old, old))
    return d


STORE = _build_store()
live.hls.OUTPUT_DIR = STORE          # read at call time by scan()/resolve(), never cached

app = FastAPI()
app.include_router(live.router, prefix="/api/live", tags=["live"])
# Mounted even though this harness is "only the live router", because `site/ui.js` fetches
# `/api/news/ticker` on EVERY page load -- the bar is shared page chrome, not a news-page
# feature. Without it the browser logs a 404 and the "no uncaught JavaScript errors"
# assertion goes red for something this page does not own, which is exactly what made
# `tests/project.mjs` 15/16. `.claude/CLAUDE.md`: "If you write a harness, mount news in it."
app.include_router(news.routes.router, prefix="/api/news", tags=["news"])


@app.get("/livestack/live", include_in_schema=False)
async def live_page():
    """The real page route's address, reproduced so the suite exercises the real URL.

    Deliberately not a redirect, for the same reason `api.py`'s is not: a redirect would
    break a <video> mid-playlist, since the player resolves segment URIs relative to the
    manifest it was handed.
    """
    from fastapi.responses import FileResponse
    return FileResponse(ROOT / "site" / "live.html", media_type="text/html")


# Mounted LAST, exactly as api.py does, so it never shadows an API route.
app.mount("/", StaticFiles(directory=str(ROOT / "site"), html=True), name="site")

if __name__ == "__main__":
    import uvicorn
    print(f"live harness: store at {STORE}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8897, log_level="warning")
