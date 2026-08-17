#!/usr/bin/env python3
"""Turn the front page into one screen: the page stops scrolling, a panel scrolls instead.

    python3 tools/build_tabs.py        # site/index.html

Runs AFTER build_masthead / build_rack / build_console and BEFORE build_cachebust. It does
not move anything: it inserts a tab strip and lets JavaScript show one section at a time.
The sections stay exactly where the other generators put them, so this composes with them
instead of fighting them.

## Why tabs rather than trimming

Measured at 1440x900 before this existed: header 67px, masthead 436, rack 1009, control
board 1044, receipts 698, footer 105 -- 3,358px, or 3.7 screens. After the header and
masthead there are ~397px left and the rack alone is 1,009. There is no amount of tightening
that fits four full sections into one viewport, so the choice is fold or drop, and
`.claude/CLAUDE.md` is explicit: **fold long content, never trim it.** A tab is a fold. Every
section is still in the DOM, still reachable, still printed, still found by ctrl-F once its
tab is open.

## Why it only applies on a big enough screen

The no-scroll layout is gated behind `@media (min-width:1100px) and (min-height:780px)`.
Below that the page scrolls exactly as it did. Two reasons, and the second is the important
one:

- At 390px the front page is 9,161px tall. Ten screens do not become one, and pretending
  otherwise means hiding things a phone visitor will never find.
- **Browser zoom shrinks the effective viewport.** At 200% zoom the query stops matching and
  the page reverts to scrolling on its own, which is what someone who has zoomed in actually
  needs. A no-scroll layout that survives zoom by clipping is an accessibility bug.

## Idempotency

The strip is written between BEGIN/END markers and replaced in place on a second run. The
marker strings are the contract with this file -- change one here and you must change it in
`site/index.html` in the same commit, or this appends a second strip instead of finding the
first.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"
SITE = ROOT / "site"

BEGIN = "<!-- BEGIN tabs (build_tabs.py) -->"
END = "<!-- END tabs -->"

# id -> (tab label, short description read by screen readers and shown on hover)
PANELS = [
    ("rack", "Live stack", "The rack, reading its own sensors"),
    ("console", "Control board", "Instrument panel for the machine"),
    ("more", "Receipts", "Every claim, and what backs it"),
]


def strip() -> str:
    tabs = "\n".join(
        f'      <button type="button" class="ns-tab{" on" if i == 0 else ""}" '
        f'role="tab" id="nstab-{pid}" aria-controls="{pid}" '
        f'aria-selected="{"true" if i == 0 else "false"}" '
        f'data-panel="{pid}" title="{desc}">{label}</button>'
        for i, (pid, label, desc) in enumerate(PANELS)
    )
    return f"""{BEGIN}
<div class="ns-tabs" role="tablist" aria-label="Sections of this page">
  <div class="wrap ns-tabwrap">
{tabs}
    <span class="ns-tabnote">One screen. Nothing is hidden &mdash; every section is still
      here, one tab away.</span>
  </div>
</div>
{END}"""


SCRIPT = """<!-- BEGIN tabs-js (build_tabs.py) -->
<script>
(function () {
  'use strict';
  var strip = document.querySelector('.ns-tabs');
  if (!strip) return;
  var tabs = [].slice.call(strip.querySelectorAll('.ns-tab'));
  var ids = tabs.map(function (t) { return t.dataset.panel; });

  // The no-scroll layout is a CSS media query, so ASK THE BROWSER whether it is on rather
  // than re-deriving the breakpoint here. Two copies of a breakpoint drift, and the one in
  // JavaScript is always the one that gets forgotten.
  var mq = window.matchMedia('(min-width:1100px) and (min-height:780px)');

  function applyLayout() {
    // The class is what switches the CSS on. Adding it from JS rather than styling `html`
    // directly means a browser with JavaScript disabled never gets a clipped page -- it
    // scrolls, which is the safe way for this to fail.
    document.documentElement.classList.toggle('ns', mq.matches);
  }

  function show(id) {
    applyLayout();
    ids.forEach(function (p) {
      var el = document.getElementById(p);
      if (!el) return;
      // Only hide when the one-screen layout is active. When the page scrolls normally
      // every section must be visible, or a phone visitor loses two thirds of the page.
      el.hidden = mq.matches && p !== id;
    });
    tabs.forEach(function (t) {
      var on = t.dataset.panel === id;
      t.classList.toggle('on', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    if (mq.matches && location.hash !== '#' + id) {
      history.replaceState(null, '', '#' + id);
    }
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () { show(t.dataset.panel); });
    // Left/right arrows move between tabs, which is what a tablist is expected to do.
    t.addEventListener('keydown', function (e) {
      var i = tabs.indexOf(t);
      if (e.key === 'ArrowRight') { e.preventDefault(); tabs[(i + 1) % tabs.length].focus(); tabs[(i + 1) % tabs.length].click(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); tabs[(i - 1 + tabs.length) % tabs.length].focus(); tabs[(i - 1 + tabs.length) % tabs.length].click(); }
    });
  });

  // A link to #console from anywhere else must open that tab rather than scroll to a
  // section that is currently hidden.
  function fromHash() {
    var want = (location.hash || '').replace(/^#/, '');
    show(ids.indexOf(want) >= 0 ? want : ids[0]);
  }
  window.addEventListener('hashchange', fromHash);
  // When the layout flips -- resize, rotate, or the user zooms -- re-run so nothing is left
  // hidden on a page that has gone back to scrolling.
  mq.addEventListener ? mq.addEventListener('change', fromHash) : mq.addListener(fromHash);
  fromHash();
})();
</script>
<!-- END tabs-js -->"""


def main() -> int:
    f = SITE / "index.html"
    html = f.read_text()

    # ---- the strip goes immediately after the masthead, so the hero always stays put
    block = strip()
    if BEGIN in html:
        html = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, html, flags=re.S)
    else:
        anchor = '<section id="rack">'
        if anchor not in html:
            print("  could not find #rack -- run build_rack.py first")
            return 1
        html = html.replace(anchor, block + "\n\n" + anchor, 1)

    # ---- the script goes last, after the sections it controls exist
    if "<!-- BEGIN tabs-js" in html:
        html = re.sub(r"<!-- BEGIN tabs-js.*?<!-- END tabs-js -->", SCRIPT, html, flags=re.S)
    else:
        html = html.replace("</body>", SCRIPT + "\n</body>", 1)

    f.write_text(html)
    print(f"  index.html: {len(PANELS)} tabs ({', '.join(p[0] for p in PANELS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
