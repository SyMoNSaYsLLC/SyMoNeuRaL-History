"""`scripts/deploy.sh`'s reference check must not report a working route as a missing file.

The check walks every local asset reference in the published tree and asserts the file is on
disk. Routes FastAPI serves through the proxy are not files and never will be, so `is_route()`
exempts them -- and the script's own comment states the stake: *"a check that cries wolf is
worse than no check, because the next real failure gets ignored."*

`studio` and `exp` were missing from that list, and the consequence was not cosmetic. Measured
2026-08-20: a deploy reported `MISSING exp` and `MISSING studio` and **exited non-zero**, while
both answered 200 on the running service. `ops/symoneural-deploy.service` deliberately carries
no `SuccessExitStatus`, so once that unit is armed a boot-time deploy goes red every single
boot -- for two pages that are working. That is the state `systemctl --failed` is supposed to
mean something in.

## Why this is a test and not just a longer allowlist

The allowlist is the kind of thing that rots silently: a surface lands, `api.py` grows a route,
nobody touches this shell script, and the next deploy fails for a page that works. So the test
below does not hardcode a blessed list -- it reads the extensionless `@app.get` routes out of
`api.py` and requires the script to know about every one that a page actually links to. A new
surface added the ordinary way makes this go red, which is the cheapest possible place to find
out.

The opposite failure is guarded too, and matters just as much: an allowlist that over-matches
stops catching genuinely absent files. `studio.js` and `studio-64.png` must still be checked
against the disk, and `livestack.html` must still be checked even though `livestack` is a
route. That asymmetry is deliberate and `deploy.sh` documents it.

Nothing here imports `api.py` -- it is the serving module, and importing it builds every rate
limiter, resolves the GPU governor and mounts `site/`. It is read as text, the same way
`test_rack_probes.py` reads it.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
DEPLOY = REPO / "scripts" / "deploy.sh"
API = REPO / "backend" / "api.py"
INDEX = REPO / "site" / "index.html"


def _is_route(ref: str) -> bool:
    """Run deploy.sh's own `is_route()` against one reference.

    The function is extracted and sourced rather than reimplemented in Python. A copy of the
    case statement here would be a second thing to keep in step, and it would keep passing
    after somebody edited the shell -- testing the copy, not the script.
    """
    body = re.search(r"^is_route\(\) \{.*?^\}", DEPLOY.read_text(), re.M | re.S)
    assert body, "is_route() not found in deploy.sh -- it was renamed, not deleted; fix this"
    out = subprocess.run(
        ["bash", "-c", f'{body.group(0)}\nif is_route "$1"; then echo route; else echo file; fi',
         "_", ref],
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip() == "route"


def _extensionless_page_routes() -> set[str]:
    """Top-level `@app.get("/name")` paths in api.py: one segment, no dot, no parameter."""
    return {m.group(1) for m in
            re.finditer(r'@app\.get\(\s*"/([A-Za-z][\w-]*)"', API.read_text())
            if "." not in m.group(1)}


def _linked_extensionless() -> set[str]:
    """Extensionless local hrefs on the front page -- what the check would actually look up."""
    return {m.group(1) for m in re.finditer(r'href="/([A-Za-z][\w-]*)"', INDEX.read_text())}


class ReferenceCheckTests(unittest.TestCase):

    def test_the_extraction_found_something_to_test(self):
        """The vacuity guard. Every assertion below passes against empty sets, and this repo has
        already retired checks that scored green on an empty file."""
        self.assertTrue(_extensionless_page_routes(), "no @app.get routes parsed out of api.py")
        self.assertTrue(_linked_extensionless(), "no extensionless hrefs parsed out of index.html")

    def test_studio_and_exp_are_not_reported_missing(self):
        """The regression itself. Both were `MISSING` on a deploy where both answered 200."""
        self.assertTrue(_is_route("studio"))
        self.assertTrue(_is_route("exp"))

    def test_every_linked_api_route_is_known_to_the_deploy_check(self):
        """A new surface that api.py serves and a page links must not fail the next deploy."""
        unknown = sorted(r for r in _linked_extensionless() & _extensionless_page_routes()
                         if not _is_route(r))
        self.assertEqual(unknown, [], (
            f"scripts/deploy.sh reports {unknown} as MISSING files, but api.py serves them as "
            "routes and site/index.html links them. The next deploy will exit non-zero for a "
            "page that works. Add them to is_route()."))

    def test_the_allowlist_does_not_swallow_real_files(self):
        """An exemption that over-matches stops the check catching a genuinely absent asset.

        `livestack` is the documented asymmetry: the route is exempt, the file is not."""
        for ref in ("studio.html", "exp.html", "studio.js", "studio-64.png",
                    "livestack.html", "nonesuch"):
            with self.subTest(ref=ref):
                self.assertFalse(_is_route(ref), f"{ref} is exempted; a missing one would pass")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(REPO / "backend"))
    unittest.main()
