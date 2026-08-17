#!/usr/bin/env python3
"""Render the homepage artwork on this machine, then watermark it with how it was made.

The band on the front page argues that a business can own its AI outright. Stock photos
would undercut that on the first scroll, so every image there is produced by the image
surface this site is selling -- same card, same weights, same four steps a visitor gets.

The watermark is not decoration or branding varnish: it prints the model, the size, the
step count and the seed. Anyone can paste that seed into /image.html and get the same
picture back. That is the whole argument of the site applied to its own artwork.

    python3 build_gallery.py            # render anything missing
    python3 build_gallery.py --force    # re-render everything

Writes site/art-<slug>.png and site/art-<slug>.json (the provenance the page prints).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

SITE = pathlib.Path(__file__).resolve().parent / "site"
API = "http://127.0.0.1:8800/api/image"
GEN = "http://127.0.0.1:8800/api/gen/"

# Seeds are pinned so a rebuild reproduces the same page rather than quietly redesigning
# it, and so the seed printed in the watermark stays true.
ART = [
    ("owns", 2517,
     "a lone server rack glowing green in a small dark office at night, warm desk lamp, "
     "clean product photography, deep blacks, emerald accent light"),
    ("cost", 8841,
     "a single graphics card resting on a workbench beside a coffee cup, macro shot, "
     "dark background, green circuit traces catching the light"),
    ("private", 4402,
     "a locked steel door inside a server room, dim corridor, green indicator lights, "
     "cinematic, moody, high contrast"),
    ("fast", 1195,
     "long exposure light trails flowing through a dark data centre aisle, emerald and "
     "teal streaks, abstract, minimal"),
    ("yours", 6730,
     "a hand holding a small labelled hard drive over a dark desk, shallow depth of "
     "field, green rim light, documentary photography"),
    ("build", 3364,
     "an engineer's desk covered in cables, a multimeter and an open server chassis, "
     "top down, dark tones, green accents"),
]

FOOT = 34  # watermark bar height


def render(seed: int, prompt: str) -> tuple[bytes, dict]:
    body = json.dumps({"prompt": prompt, "steps": 4, "size": 768, "seed": seed}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        meta = json.load(r)
    with urllib.request.urlopen(GEN + meta["url"].rsplit("/", 1)[-1], timeout=120) as r:
        return r.read(), meta


def stamp(png: bytes, meta: dict, out: pathlib.Path) -> None:
    """Add a bar printing exactly how the image above it was produced."""
    im = Image.open(_spool(png, out)).convert("RGB")
    w, h = im.size
    canvas = Image.new("RGB", (w, h + FOOT), "#0b0d0c")
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)

    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 12)
    except OSError:                                    # font package missing
        f = fb = ImageFont.load_default()

    d.line([(0, h), (w, h)], fill="#1d241f", width=1)
    d.text((13, h + 11), "SyMoNeuRaL Image", font=fb, fill="#2ee08a")
    tail = (f"{meta['model']} · {meta['size']}×{meta['size']} · {meta['steps']} steps · "
            f"seed {meta['seed']} · {meta['seconds']}s on an RTX 5070 Ti")
    d.text((13 + int(d.textlength("SyMoNeuRaL Image", font=fb)) + 12, h + 11),
           tail, font=f, fill="#5d6b63")
    canvas.save(out, "PNG", optimize=True)


def _spool(png: bytes, out: pathlib.Path) -> pathlib.Path:
    tmp = out.with_suffix(".raw")
    tmp.write_bytes(png)
    return tmp


def main() -> int:
    force = "--force" in sys.argv
    made = 0
    for slug, seed, prompt in ART:
        out = SITE / f"art-{slug}.png"
        side = SITE / f"art-{slug}.json"
        if out.exists() and not force:
            print(f"  keep    art-{slug}.png")
            continue
        print(f"  render  art-{slug}.png (seed {seed}) ...", end="", flush=True)
        started = time.time()
        try:
            png, meta = render(seed, prompt)
        except urllib.error.URLError as e:
            print(f" FAILED: {e}")
            return 1
        stamp(png, meta, out)
        (SITE / f"art-{slug}.raw").unlink(missing_ok=True)
        side.write_text(json.dumps({**meta, "prompt": prompt, "slug": slug}, indent=2))
        print(f" {time.time() - started:.1f}s  ({meta['seconds']}s on the card)")
        made += 1
    print(f"\n{made} rendered, {len(ART) - made} kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
