"""Stickers over the real HTTP surface: all three inputs, and every refusal.

`tests/stickers.mjs` drives the browser and asserts on what the page *shows*. This asserts
on what a client *receives*, which is not the same coverage: the refusals (strength above
the measured cap, silence, rubbish base64) never reach the DOM, and a phone app talking to
this API sees only what is here.

Run it against a throwaway API rather than the live one -- an agent cannot restart the
service, so the recipe is to bring the app up on a spare port and point this at it:

    python3 -m uvicorn backend.api:app --port 8877 &
    python3 tests/sigils_http.py

    SYMONEURAL_TEST_BASE=http://127.0.0.1:8877   where the API is (default: the above)
    SYMONEURAL_RATE_SIGIL=2/100                  set on the *API's* environment to also exercise
                                          the rate lane; see the rate section at the end

The decode assertion is the one that matters. `tests/frontend.mjs` has an image assertion
because a render once succeeded server-side and still showed as a broken image to every
visitor. The sticker version of that failure is a PNG that decodes perfectly and is a solid
opaque square -- so decoding is not enough, and channel four is checked too.

No fixture image is committed. The photograph stand-in is drawn here, which is not a
compromise: because it is an ellipse of known radii, its true area is arithmetic, so the
segmentation assertion can compare the returned matte against ground truth instead of
merely checking that some alpha exists. A real photograph could never assert that.
"""
import base64
import json
import math
import os
import pathlib
import struct
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from apps.sigils import png  # noqa: E402

BASE = os.getenv("SYMONEURAL_TEST_BASE", "http://127.0.0.1:8877").rstrip("/")
API = BASE + "/api/sigils"

#: Speech needs a sample with real words in it. This read whisper.cpp's bundled sample,
#: which arrived as a side effect of building that project and now lives under
#: `external/` -- where task #74 says nothing may read from. One fixture path now, ours,
#: shared with `tests/stickers.mjs` and `apps/voice/test_voice.py`. Absent by default:
#: see `tests/fixtures/README.md` for what is needed and why a tone will not do.
#: Missing means SKIP AND SAY SO -- never a silent pass.
SPEECH_SAMPLES = [
    pathlib.Path(os.environ["SYMONEURAL_SPEECH_FIXTURE"])
    if os.getenv("SYMONEURAL_SPEECH_FIXTURE")
    else ROOT / "tests/fixtures/speech.wav",
]

W = H = 512
#: The subject ellipse, as a fraction of the frame. Its area is pi*rx*ry, and that number is
#: what the u2net matte is checked against.
RX, RY = 0.26, 0.32
TRUE_AREA = math.pi * RX * RY

passed, failed, skipped = 0, [], []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name}  {detail}")


def skip(name: str, why: str) -> None:
    skipped.append(name)
    print(f"  skip {name}  -- {why}")


def post(path: str, body: dict, timeout: int = 600) -> tuple[int, dict]:
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:200].decode("utf-8", "replace")}


def get_json(path: str, timeout: int = 30) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def get_bytes(url_path: str) -> bytes:
    with urllib.request.urlopen(BASE + url_path, timeout=120) as r:
        return r.read()


def alpha_report(blob: bytes) -> dict:
    """Decode the delivered PNG with this package's own codec and look at channel four."""
    w, h, planes = png.read(blob)
    if len(planes) < 4:
        return {"channels": len(planes), "transparent": 0.0, "opaque": 0.0}
    a = planes[3]
    n = w * h
    return {"channels": len(planes), "w": w, "h": h,
            "transparent": round(a.count(0) / n, 4),
            "opaque": round(a.count(255) / n, 4)}


def synthetic_photograph() -> bytes:
    """A shaded ellipse on a textured gradient -- a photograph's problem, not a sticker's.

    The background is deliberately *not* flat. A flat field would be liftable by the chroma
    key, and the whole reason the segmentation path exists is that an uploaded picture has
    no key colour in it. If this fixture ever became keyable the test below would pass for
    the wrong reason.
    """
    n = W * H
    r, g, b = bytearray(n), bytearray(n), bytearray(n)
    a = bytes([255]) * n
    cx, cy = W * 0.5, H * 0.54
    rx, ry = W * RX, H * RY
    for y in range(H):
        t = y / H
        for x in range(W):
            i = y * W + x
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                sh = 1.0 - 0.45 * math.sqrt(d)
                if abs(x - cx) < rx * 0.18 and y < cy:
                    r[i], g[i], b[i] = int(240 * sh), int(200 * sh), int(120 * sh)
                else:
                    r[i], g[i], b[i] = int(210 * sh), int(90 * sh), int(60 * sh)
            else:
                r[i] = max(0, min(255, int(140 - 60 * t) + ((x // 7 + y // 5) % 11)))
                g[i] = max(0, min(255, int(150 - 40 * t) + ((x // 5) % 9)))
                b[i] = max(0, min(255, int(190 - 30 * t)))
    return png.write_rgba(W, H, [bytes(r), bytes(g), bytes(b), a])


def silence_wav(seconds: int = 3, rate: int = 16000) -> bytes:
    """A silent 16 kHz mono WAV, written here rather than shelled out to ffmpeg.

    ffmpeg is not a declared dependency of this repo and the file is 44 bytes of header
    followed by zeros; requiring a media toolchain to assert that silence is refused would
    be the tail wagging the dog.
    """
    data = b"\x00\x00" * (rate * seconds)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


# ---------------------------------------------------------------- the surface is mounted
# This is first because it is the defect the whole surface shipped with: sigils.html was
# live while backend/api.py contained no reference to the app at all, so every route here
# answered 404. A 200 from /state is the mount, proved from outside the process.
print(f"\nGET {API}/state")
code, st = get_json("/state")
check("the surface is mounted at all", code == 200, f"got {code}")
if code == 200:
    check("three inputs reported", set(st["inputs"]) == {"text", "image", "audio"},
          str(st.get("inputs")))
    check("strength cap is the measured one", st["image"]["max_strength"] == 0.80,
          str(st["image"].get("max_strength")))
    check("segmentation model is the permissively licensed one",
          st["segmentation"]["model"] in ("u2net", "u2netp"), str(st["segmentation"]))
    check("two mattes are reported, not one",
          set(st["matte"]) == {"generated", "photographic", "rule"}, str(st["matte"]))
    audio_ok = bool(st["inputs"].get("audio"))
    image_ok = bool(st["inputs"].get("image"))
else:
    audio_ok = image_ok = False

photo = synthetic_photograph()
photo_b64 = base64.b64encode(photo).decode()

# ------------------------------------------------------- image -> sticker, the CPU path
print("\nPOST /from-image  mode=cutout   (segmentation; no GPU at all)")
code, doc = post("/from-image", {"image_base64": photo_b64, "mode": "cutout", "size": 512})
check("200", code == 200, json.dumps(doc)[:300])
if code == 200:
    check("mode is cutout", doc.get("mode") == "cutout", str(doc.get("mode")))
    check("no model is claimed for a cut-out", doc.get("model") is None, str(doc.get("model")))
    check("the card was not taken", doc.get("gpu") is False, str(doc.get("gpu")))
    check("no render time is reported for work that rendered nothing",
          "render_seconds" not in doc, str(sorted(doc)))
    check("a photograph was segmented, not colour-keyed",
          doc.get("matte") == "u2net", str(doc.get("matte")))
    check("no field colour is claimed for a segmented cut",
          doc.get("field_rgb") is None, str(doc.get("field_rgb")))
    check("segment time is reported on its own",
          isinstance(doc.get("segment_seconds"), float), str(doc.get("segment_seconds")))
    rep = alpha_report(get_bytes(doc["url"]))
    check("the delivered PNG has four channels", rep["channels"] == 4, str(rep))
    # The assertion a real photograph could not make. A solid square scores 1.0 here and an
    # empty matte scores 0.0; both fail. The tolerance is wide enough to survive a u2net
    # point release and far too tight to admit either degenerate answer.
    err = abs(rep["opaque"] - TRUE_AREA)
    check("the matte matches the subject's true area",
          err < 0.05, f"opaque={rep['opaque']} true={TRUE_AREA:.4f} err={err:.4f}")
    print(f"       opaque={rep['opaque']} vs true area {TRUE_AREA:.4f} "
          f"(err {err:.4f})  segment={doc.get('segment_seconds')}s "
          f"encode={doc.get('matte_seconds')}s  bytes={doc.get('bytes')}")

# ------------------------------------------------------- image -> sticker, the GPU path
print("\nPOST /from-image  mode=redraw   (GPU)")
if not image_ok:
    skip("redraw", "/state reports the image path unavailable on this box")
else:
    code, doc = post("/from-image", {"image_base64": photo_b64, "mode": "redraw",
                                     "size": 512, "seed": 4242, "strength": 0.6})
    check("200", code == 200, json.dumps(doc)[:300])
    if code == 200:
        check("mode is redraw", doc.get("mode") == "redraw", str(doc.get("mode")))
        check("labelled a re-draw, not a copy of the upload",
              "re-draw" in doc.get("note", ""), doc.get("note", "")[:120])
        check("strength echoed back", doc.get("strength") == 0.6, str(doc.get("strength")))
        rep = alpha_report(get_bytes(doc["url"]))
        check("the redraw has alpha", rep["channels"] == 4 and rep["transparent"] > 0.02,
              str(rep))
        print(f"       {rep}  render={doc.get('render_seconds')}s")

# ------------------------------------------------------------------ text -> sticker
print("\nPOST /render   the generated path must still use the CHEAP matte")
if not image_ok:
    skip("text render", "/state reports the image path unavailable on this box")
else:
    code, doc = post("/render", {"prompt": "a coiled network cable", "size": 512})
    check("200", code == 200, json.dumps(doc)[:300])
    if code == 200:
        # "Key what we painted, segment what we did not." Sending a generated sticker
        # through u2net would spend a second of CPU to answer a question the renderer
        # already knows the answer to, because it chose the field colour itself.
        check("a generated sticker is chroma-keyed, not segmented",
              doc.get("matte") == "chroma", str(doc.get("matte")))
        check("the field it actually painted is reported",
              isinstance(doc.get("field_rgb"), list), str(doc.get("field_rgb")))
        rep = alpha_report(get_bytes(doc["url"]))
        check("the text sticker has alpha",
              rep["channels"] == 4 and rep["transparent"] > 0.05, str(rep))
        print(f"       {rep}  field={doc.get('field_rgb')} render={doc.get('render_seconds')}s")

# ------------------------------------------------------------------ audio -> sticker
print("\nPOST /from-audio   (CPU transcribe, then the same render a typed subject gets)")
sample = next((p for p in SPEECH_SAMPLES if p.exists()), None)
if not audio_ok:
    skip("speech", "/state reports the audio path unavailable on this box")
elif sample is None:
    skip("speech", f"no speech sample on disk; looked for {[str(p) for p in SPEECH_SAMPLES]}")
else:
    code, doc = post("/from-audio",
                     {"audio_base64": base64.b64encode(sample.read_bytes()).decode(),
                      "size": 512})
    check("200", code == 200, json.dumps(doc)[:300])
    if code == 200:
        check("mode is speech", doc.get("mode") == "speech", str(doc.get("mode")))
        check("the transcript comes back verbatim",
              len(doc.get("heard", "")) > 8, doc.get("heard", "")[:120])
        check("a subject was derived from the speech",
              len(doc.get("subject", "")) > 3, doc.get("subject", ""))
        # The honesty assertion: this is ASR then the text path, and the response says so.
        # Nothing here listens to audio and paints; claiming otherwise would be a fiction
        # the API told about its own pipeline.
        check("the route names itself ASR, not audio-native",
              "speech -> text" in doc.get("path", ""), doc.get("path", ""))
        check("transcribe time is reported apart from render time",
              isinstance(doc.get("transcribe_seconds"), float)
              and "render_seconds" in doc, str(sorted(doc)))
        rep = alpha_report(get_bytes(doc["url"]))
        check("the spoken sticker has alpha",
              rep["channels"] == 4 and rep["transparent"] > 0.02, str(rep))
        print(f"       heard: {doc.get('heard', '')[:90]}")
        print(f"       audio={doc.get('audio_seconds')}s "
              f"transcribe={doc.get('transcribe_seconds')}s render={doc.get('render_seconds')}s")

# ------------------------------------------------------------------------ the refusals
# None of these reach the DOM, so the browser suite cannot cover them.
print("\nrefusals")
code, _ = post("/from-image", {"image_base64": photo_b64, "mode": "redraw", "strength": 0.95})
# 0.85 made a cat photo and a guitar photo produce byte-identical stickers -- above the cap
# the upload is not weakly influential, it is ignored. Accepting 0.95 would be accepting a
# parameter that silently does nothing.
check("strength above the measured cap is refused", code == 422, f"got {code}")

if audio_ok:
    code, doc = post("/from-audio", {"audio_base64": base64.b64encode(silence_wav()).decode()})
    # whisper emits "[BLANK_AUDIO]" for silence, and rendering a sticker *of that string*
    # is the kind of confidently wrong output this repo exists to not ship.
    check("silence does not render a sticker of [BLANK_AUDIO]", code == 400,
          f"got {code}: {json.dumps(doc)[:200]}")
else:
    skip("silence refusal", "/state reports the audio path unavailable on this box")

code, _ = post("/from-image", {"image_base64": "not base64 !!"})
check("rubbish base64 is refused", code == 400, f"got {code}")

# --------------------------------------------------------------------- the rate lane
# LIMITS is built at the API's import time, so this can only be exercised when the API was
# started with SYMONEURAL_RATE_SIGIL set. Unset means every surface is unmetered by the operator's
# standing instruction, and there is nothing here to prove. The structural guard that the
# dependency is wired at all lives in backend/apps/sigils/test_sigils.py and needs no server.
print("\nthe rate lane")
lane = os.getenv("SYMONEURAL_RATE_SIGIL", "").strip()
if not lane:
    skip("rate limiting", "SYMONEURAL_RATE_SIGIL unset on the API; the lane is off by design")
else:
    per_min = int(lane.split("/")[0])
    codes = [get_json("/state")[0] for _ in range(per_min + 2)]
    check(f"the {lane} lane actually denies past its budget", 429 in codes,
          f"sent {len(codes)} and saw {sorted(set(codes))}")

print(f"\n{passed} passed, {len(failed)} failed, {len(skipped)} skipped")
if skipped:
    print("skipped: " + ", ".join(skipped))
if failed:
    print("failed: " + ", ".join(failed))
    sys.exit(1)
