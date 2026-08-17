#!/usr/bin/env python3
"""Stamp a content hash onto every local CSS and JS link in site/.

Why this exists: the Caddyfile sets `Cache-Control: public, max-age=604800` on .css and
.js, which is correct for assets that never change and wrong for a site under active
development. It produced a genuinely broken page in front of a visitor -- the deploy
shipped new HTML with the constellation band while the browser kept a week-old stylesheet
that had no rules for it, so nineteen full-size renders stacked down the left of the page.
New markup, old CSS, and no way for the visitor to know.

Appending ?v=<hash of the file> makes the URL change whenever the file changes, so a stale
copy can never be served for new markup. The long cache stays, which is the point: the
asset is immutable *for that hash*.

Idempotent: any existing ?v= is stripped before the current hash is applied, so running
this twice is a no-op. Run it last, after every other generator.
"""
from __future__ import annotations

import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"
SITE = ROOT / "site"

ASSET = re.compile(r'(?P<attr>href|src)="/(?P<file>[A-Za-z0-9._-]+\.(?:css|js))(?:\?v=[0-9a-f]+)?"')


def digest(name: str) -> str | None:
    f = SITE / name
    if not f.is_file():
        return None
    return hashlib.sha256(f.read_bytes()).hexdigest()[:10]


def main() -> int:
    pages = sorted(SITE.glob("*.html")) + sorted(SITE.glob("*/*.html"))
    stamped = skipped = 0
    for page in pages:
        html = page.read_text()

        def sub(m: re.Match[str]) -> str:
            nonlocal stamped, skipped
            d = digest(m.group("file"))
            if d is None:                       # not ours -- leave it exactly as found
                skipped += 1
                return m.group(0)
            stamped += 1
            return f'{m.group("attr")}="/{m.group("file")}?v={d}"'

        new = ASSET.sub(sub, html)
        if new != html:
            page.write_text(new)

    print(f"cache-bust: {stamped} asset links stamped across {len(pages)} pages"
          + (f", {skipped} left alone" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
