"""Shared markup for a render lifted out of site/art-*.png.

Three generators place these now -- the masthead, the rack, and the constellation on
/build.html -- and each was building the same anchor by hand with its own copy of the
prompt/seed/seconds lookup. One of those copies had already drifted.

Every render is a link to its own full-size file. That is not decoration: each PNG carries
a watermark strip naming the model, the quantisation, the resolution, the step count, the
seed and the wall-clock it took on this card, and at any size that fits in a page gutter
that strip is roughly four pixels tall. The claim the images make -- drawn here, on the
machine you are reading about -- is only checkable at full size, so the click has to be
obvious and it has to work without JavaScript. ui.js upgrades it to an overlay; with
scripting off the link still opens the PNG.
"""
from __future__ import annotations

import json
import pathlib

SITE = pathlib.Path(__file__).resolve().parent.parent / "site"


def meta(slug: str) -> tuple[str, str, str]:
    """(prompt, seed, seconds) for a render, or empty strings if it has no sidecar."""
    f = SITE / f"art-{slug}.json"
    if not f.is_file():
        return "", "", ""
    d = json.loads(f.read_text())
    return d.get("prompt", ""), str(d.get("seed", "")), str(d.get("seconds", ""))


def attrs(slug: str) -> str:
    """The href and data-* an <a class="art"> needs for the lightbox."""
    prompt, seed, secs = meta(slug)
    esc = prompt.replace('"', "&quot;")
    return (f'href="/art-{slug}.png" title="{esc}" data-prompt="{esc}" '
            f'data-seed="{seed}" data-secs="{secs}" '
            f'aria-label="Open the full render, watermark and all: {esc}"')


def gutter(slug: str, alt: str, question: str, rot: float = 0.0) -> str:
    """A render sized for a page gutter, with the question it answers underneath."""
    return f"""<a class="gart" {attrs(slug)} style="--rot:{rot}deg">
      <span class="gwrap">
        <img src="/art-{slug}.png" alt="{alt}, rendered by SyMoNeuRaL Image"
             loading="lazy" width="768" height="802">
        <span class="gzoom">Click to read the watermark</span>
      </span>
      <span class="gq">{question}</span>
    </a>"""
