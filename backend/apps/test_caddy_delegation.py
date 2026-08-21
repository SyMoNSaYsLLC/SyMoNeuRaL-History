"""Every page path `api.py` owns must be delegated to it by `ops/Caddyfile`, or Caddy 404s it.

Caddy's last block is `handle { file_server }`. Any path that reaches it is looked up in
`/var/www/symoneural` and answered from disk -- **without ever asking the API**. So a route
that exists in `api.py` and has no matching file in the webroot is dead code on the public
origin, however perfectly it answers on `127.0.0.1:8800`.

That defect has now shipped four separate times, once per surface, and each was found in
production rather than by a test:

  * `/overview /livestack /controlboard /receipts` -- the Caddyfile's own comment records it:
    *"That is exactly what happened when they were first deployed."*
  * `/studio` -- same, and `/studio.js` loaded off the webroot while the page did not.
  * `/exp` -- added with its own block only because @sections had written the lesson down.
  * `/tuner.html` and `/tuner-watch.html` -- **found 2026-08-20, and the interesting one.**
    Its delegation was missing from the day the redirect was written, but the retired files
    were still sitting in the webroot, so `file_server` answered them with stale 200s and
    everything looked healthy. The first unattended `deploy.sh --prune` deleted both, and the
    paths went from stale-200 straight to hard-404. `api.py`'s comment states the stake:
    these two get a redirect precisely because *"a bookmark is permanent"* and, unlike a
    stale cached page, a dead bookmark *"does NOT resolve itself on a reload"*.

The last one is why this test reads the webroot rule rather than a list of known paths: the
bug was latent for as long as a file happened to mask it, and no amount of curling the site
would have shown it.

## Why this cannot be a browser test

`tests/frontend.mjs` is normally run against a spare-port API, where FastAPI answers every one
of these paths directly and **this entire block of Caddy config is not exercised**. The
Caddyfile says so twice, in @sections and again in @studio: *"against localhost the API
answers directly and this block is not exercised at all."* A green browser suite is not
evidence about delegation. Neither is `curl 127.0.0.1:8800`, which was the mistake that let
the tuner 404 be reported as fixed -- the API had always answered it; Caddy had never asked.

So this asserts on the two files against each other, which is checkable without a running
Caddy, without root, and without the site being deployed.

Nothing here imports `api.py` -- it is the serving module, and importing it builds every rate
limiter, resolves the GPU governor and mounts `site/`. It is read as text, the same way
`test_rack_probes.py` and `test_deploy_routes.py` read it.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
API = REPO / "backend" / "api.py"
CADDYFILE = REPO / "ops" / "Caddyfile"
SITE = REPO / "site"


def _api_page_paths() -> set[str]:
    """Paths `api.py` serves that a visitor types, so `/api/*` and `/local/*` are excluded.

    Three declaration forms, and the second is the reason this is not a one-line regex:
    `SECTION_PAGES` is registered in a `for` loop at the bottom of `api.py`, so a decorator-
    only scan silently misses all four section pages -- the very paths whose delegation block
    is the oldest one in the Caddyfile.
    """
    src = API.read_text()
    paths = {m.group(1) for m in
             re.finditer(r'@app\.(?:get|post)\(\s*"(/[^"{]*)"', src)}

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if "SECTION_PAGES" in names:
            # keys are slugs -- the route is the slug with a leading slash
            paths |= {f"/{k.value}" for k in node.value.keys}
        if "_RETIRED_PAGES" in names:
            # keys are already full paths
            paths |= {k.value for k in node.value.keys}

    return {p for p in paths
            if not p.startswith("/api") and not p.startswith("/local")}


def _caddy_matchers() -> tuple[set[str], set[str]]:
    """(exact paths, prefixes) that Caddy hands to the API.

    Two forms are in use and both count: a named matcher (`@exp path /exp`) and an inline
    one (`handle /docs* { ... }`). A trailing `*` makes a prefix.
    """
    exact: set[str] = set()
    prefix: set[str] = set()
    for line in CADDYFILE.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"@\w+\s+path\s+(.+)$", line) or re.match(r"handle\s+(/\S*)\s*\{", line)
        if not m:
            continue
        for tok in m.group(1).replace("{", " ").split():
            if not tok.startswith("/"):
                continue
            (prefix if tok.endswith("*") else exact).add(tok.rstrip("*") or "/")
    return exact, prefix


def _is_delegated(path: str) -> bool:
    exact, prefix = _caddy_matchers()
    return path in exact or any(path.startswith(p) for p in prefix)


def _shadowed_by_a_real_file(path: str) -> bool:
    """True when `file_server` would find something at this exact webroot path anyway.

    Tested against `site/`, which is what `deploy.sh` publishes -- the webroot is not readable
    without root and would make this test depend on a deploy having run.

    `/` is deliberately never shadowed. A bare `/` does resolve, to `index.html`, which is the
    whole problem: `api.py` redirects `/` to `/overview` and the Caddyfile's own comment says
    that without an explicit exact match *"the redirect route in api.py is dead code."*
    Serving something is not the same as serving the right thing.
    """
    if path == "/":
        return False
    return (SITE / path.lstrip("/")).is_file()


class CaddyDelegationTests(unittest.TestCase):

    def test_the_extraction_found_the_forms_that_are_easy_to_miss(self):
        """The vacuity guard. Every assertion below passes against an empty set, and this repo
        has already retired checks that scored green on an empty file."""
        paths = _api_page_paths()
        self.assertIn("/studio", paths, "decorator form not parsed out of api.py")
        self.assertIn("/overview", paths, "SECTION_PAGES loop not parsed -- see the docstring")
        self.assertIn("/tuner.html", paths, "_RETIRED_PAGES not parsed out of api.py")
        exact, prefix = _caddy_matchers()
        self.assertTrue(exact and prefix, "no matchers parsed out of ops/Caddyfile")

    def test_every_api_page_path_reaches_the_api(self):
        """The invariant. A path api.py serves, with no file to mask it, must be delegated."""
        stranded = sorted(p for p in _api_page_paths()
                          if not _is_delegated(p) and not _shadowed_by_a_real_file(p))
        self.assertEqual(stranded, [], (
            f"backend/api.py serves {stranded}, ops/Caddyfile does not delegate them, and no "
            "file in site/ answers them. Caddy's final `handle {{ file_server }}` will 404 "
            "every one WITHOUT asking the API -- while 127.0.0.1:8800 answers them perfectly. "
            "Add a matcher block beside @studio/@exp."))

    def test_the_retired_bookmarks_are_delegated(self):
        """The 2026-08-20 regression itself, pinned by name.

        Covered by the invariant above, and written out separately anyway: this pair was
        masked for weeks by two stale files, so it is the case most likely to be re-broken by
        someone reasoning about which paths *look* like they need a block."""
        for path in ("/tuner.html", "/tuner-watch.html"):
            with self.subTest(path=path):
                self.assertFalse(_shadowed_by_a_real_file(path),
                                 f"site/{path.lstrip('/')} is back -- the redirect is shadowed")
                self.assertTrue(_is_delegated(path))

    def test_the_matchers_do_not_swallow_the_static_site(self):
        """Coverage would be vacuous if the extraction over-matched.

        These are ordinary files Caddy must keep serving off disk; if the parser reports them
        delegated, `test_every_api_page_path_reaches_the_api` proves nothing."""
        for path in ("/symoneural.css", "/ui.js", "/streamer.html", "/art-1.png"):
            with self.subTest(path=path):
                self.assertFalse(_is_delegated(path),
                                 f"{path} parsed as delegated to the API; it is a static file")


if __name__ == "__main__":
    unittest.main()
