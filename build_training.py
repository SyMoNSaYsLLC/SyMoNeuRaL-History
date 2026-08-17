#!/usr/bin/env python3
"""Produce site/training.html: the manual, rebranded as SyMoNeuRaL Training.

The source is the already-generated MIT_AI_Training.html rather than the markdown, and
that is a deliberate choice. That file carries a purpose-built long-form layout, a nested
contents nav, and 749 heading anchors -- including the ones already linked from elsewhere.
Re-converting the markdown without pandoc would mean rebuilding all of that and quietly
breaking every saved deep link. Transforming the rendered document keeps the structure
exactly and changes only what has to change.

Three transformations, in order of how much care each needs:

**Branding.** Purged, but surgically. Most 'MIT' matches in this corpus are substrings of
ordinary words -- limits, limited, submit, emits -- so a blind replace would corrupt the
prose. Only the whole-phrase brand and the local filesystem paths are rewritten.

**Theme.** The document already ships a dark mode keyed on a data-theme attribute, so it
is pinned to dark and its tokens are remapped onto the SyMoNeuRaL palette. Nothing about
its layout is touched.

**Zero data loss.** No table, figure, measurement or provenance marker is altered. The
filesystem paths that change are incidental local paths, never a number.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "MIT_AI_Training.html"
DST = ROOT / "site" / "training.html"

# Remap the document's own design tokens onto the SyMoNeuRaL palette, and bolt the site
# header on top so this reads as part of the site rather than an attachment to it.
OVERRIDE = """
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0e100f">
<style>
/* SyMoNeuRaL palette, mapped onto the manual's existing token names. The document is
   pinned to its dark theme below, so only the dark values need to agree with the site. */
:root, :root[data-theme="dark"]{
  --paper:#0e100f; --surface:#161a18; --sunk:#12151300;
  --ink:#f2f6f3; --muted:#a8b3ac; --rule:#28302b; --rule-soft:#1f2622;
  --copper:#ffab3d; --copper-soft:#241c12;
  --teal:#2ee08a;  --teal-soft:#0f1f18;
  --pass:#2ee08a;  --flag:#ffab3d; --waive:#a8b3ac;
  --shadow:0 1px 2px rgba(0,0,0,.5);
}
html{background:#0e100f}
body{background:#0e100f; color:#f2f6f3}

/* A slim bar back to the site, matching the other pages. */
.sn-bar{
  position:sticky; top:0; z-index:60; display:flex; align-items:center; gap:14px;
  padding:11px 22px; background:rgba(14,16,15,.9); backdrop-filter:blur(14px);
  border-bottom:1px solid #28302b;
  font:15px/1 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Inter,sans-serif;
}
.sn-bar a{color:#a8b3ac; text-decoration:none; font-size:14.5px}
.sn-bar a:hover{color:#f2f6f3}
.sn-bar .brand{display:flex; align-items:center; gap:10px; color:#f2f6f3; font-weight:650}
.sn-bar .brand i{font-style:normal; color:#2ee08a}
.sn-bar .sp{margin-left:auto}
.sn-bar .live{
  display:inline-flex; align-items:center; gap:7px; background:rgba(46,224,138,.13);
  border:1px solid rgba(46,224,138,.4); color:#2ee08a; border-radius:999px;
  padding:5px 12px; font-size:13.5px; font-weight:600;
}
.sn-bar .live s{width:7px;height:7px;border-radius:50%;background:#2ee08a;
  text-decoration:none; display:block; animation:snpulse 2.2s ease-in-out infinite}
@keyframes snpulse{0%,100%{opacity:1}50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){.sn-bar .live s{animation:none}}
@media (max-width:760px){ .sn-bar .hide{display:none} }
</style>
"""

BAR = """<div class="sn-bar">
  <a class="brand" href="/"><img src="/mark-32.png" alt="" width="22" height="22">
    SyMoNeu<i>RaL</i></a>
  <a class="hide" href="/#rack">Live stack</a>
  <a class="hide" href="/#hardware">Hardware</a>
  <span class="sp"></span>
  <a class="live" href="/chat.html"><s></s>Talk to the box</a>
</div>
"""


def main() -> int:
    if not SRC.exists():
        print(f"source missing: {SRC}")
        return 1
    html = SRC.read_text(errors="ignore")
    before = len(html)

    # --- branding -------------------------------------------------------------------
    # Whole phrases and paths only. A bare 'MIT' replace would eat 'limits' and 'submit'.
    subs = [
        (r"MIT AI Training\s*&mdash;\s*Consolidated Manual", "SyMoNeuRaL Training"),
        (r"MIT AI Training\s*—\s*Consolidated Manual", "SyMoNeuRaL Training"),
        (r"\bMIT AI Training\b", "SyMoNeuRaL Training"),
        (r"\bConsolidated manual\b", "Local AI engineering"),
        (r"\bConsolidated Manual\b", "Local AI Engineering"),
        # Scrub whatever absolute path this checkout happens to live at, rather than a
        # hardcoded one -- hardcoding meant the scrub silently stopped working the
        # moment the repo moved, which is exactly when a dev path would leak.
        (re.escape(str(ROOT)), "/opt/symoneural"),
        (r"~/MIT_AI_Training/MIT_AI_Training", "~/symoneural"),
        (r"\bMIT_AI_Training\b", "symoneural"),
    ]
    for pattern, replacement in subs:
        html = re.sub(pattern, replacement, html)

    # Anchors are load-bearing -- people link to them. The only id that carried the old
    # brand gets an invisible alias so existing deep links still land.
    html = html.replace(
        'id="mit-ai-training-consolidated-manual"',
        'id="symoneural-training"><span id="mit-ai-training-consolidated-manual"></span'
        , 1) if 'id="mit-ai-training-consolidated-manual"' in html else html

    # --- broken contents links ------------------------------------------------------
    # Five TOC entries carry a double dash where the heading id has a single one
    # (#part-i--your-machine vs id="part-i-your-machine"), so those links have always
    # silently done nothing. Repair by pointing each href at an id that actually exists
    # rather than by renaming ids, which would break anything already linking to them.
    ids = set(re.findall(r'id="([^"]+)"', html))
    repaired = 0
    for anchor in set(re.findall(r'href="#([^"]+)"', html)):
        if anchor in ids:
            continue
        collapsed = re.sub(r"-{2,}", "-", anchor)
        if collapsed in ids:
            html = html.replace(f'href="#{anchor}"', f'href="#{collapsed}"')
            repaired += 1
    if repaired:
        print(f"  repaired {repaired} broken contents links")

    # --- theme ----------------------------------------------------------------------
    html = re.sub(r"<html([^>]*)>", r'<html\1 data-theme="dark">', html, count=1)
    html = html.replace("</head>", OVERRIDE + "</head>", 1)
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + BAR, html, count=1)

    # The masthead still describes the old artefact; say what this is now.
    html = html.replace(
        "Eleven playbooks and thirty-four CUDA Python sample documents,",
        "The engineering reference behind the SyMoNeuRaL stack &mdash; playbooks and CUDA "
        "sample documents,")

    DST.write_text(html)
    remaining = len(re.findall(r"\bMIT AI Training\b|\bMIT_AI_Training\b", html))
    print(f"training.html written: {before:,} -> {len(html):,} bytes")
    print(f"  brand references remaining: {remaining}")
    print(f"  heading anchors preserved:  {len(re.findall(r'id=\"[^\"]+\"', html))}")
    print(f"  runnability-matrix anchor:  {'yes' if 'id=\"runnability-matrix\"' in html else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
