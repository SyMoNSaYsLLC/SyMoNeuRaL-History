"""`ROSTER.md` reconciled against everything else that names a rack row.

The roster used to live in four places that could disagree: `backend/apps/` on disk, the
hand-written `Unit(...)` rows in `api.py:build_status()`, `TOGGLEABLE` in
`apps/controlboard`, and `EXPECTED` in `apps/test_status_rack.py`. Nothing compared them, so
each was believed on its own -- and three lists that disagree is the three-state-documents
failure with a different filename.

`ROSTER.md` is the fifth copy, and adding a copy only helps if something checks them against
each other. That is this file. Note what it deliberately does **not** do: it does not derive
`EXPECTED` from the roster, and it does not derive `TOGGLEABLE` from it either. Both are
hand-typed on purpose -- a tripwire wired to the thing it is watching stops being a tripwire,
and the defect that started all of this was code disagreeing with its own comment. Two
independent copies plus a test that they match is the check. One copy plus a derivation is a
tautology that passes forever.

`api.py` is read as source, never imported, for the reason `test_status_rack.py` gives: the
import builds every rate limiter, resolves the GPU governor and mounts `site/`. Its AST
helpers are imported from there rather than copied, so there is one reader of
`build_status()` and not two of them drifting apart.
"""
from __future__ import annotations

import pathlib
import unittest

from apps import roster
from apps.test_status_rack import EXPECTED, _row_id, _unit_calls

REPO = pathlib.Path(__file__).resolve().parents[2]
APPS = REPO / "backend" / "apps"

#: `api.py` overrides exactly one field on one row at the call site:
#: `Unit(**{**streamer.status(), "bus": "net"})`. The roster records the row as it renders --
#: `net`, because an IPTV surface is bound by the network -- so the module's own `cpu` is a
#: known disagreement rather than a failure. Named here so that a SECOND override, or this one
#: moving to another field, fails instead of being absorbed.
KNOWN_OVERRIDES = {("streamer", "bus"): ("cpu", "net")}


def _module_rows() -> dict:
    """The rows a surface module publishes, read from what `api.py` actually spreads in.

    Which rows those are is a reading of `build_status()`, not a guess from what happens to
    be importable: `Unit(**sigils.status())` is a module row, `Unit(id="coder", ...)` is one
    `api.py` builds itself out of `coder.unit_state()`. Guessing by importability gets that
    wrong -- `apps.coder` has a `status()` and it is the CLI session view, which takes a
    token and a peer address and is not a rack row at all.
    """
    import importlib
    published = {}
    for call in _unit_calls():
        if not any(kw.arg is None for kw in call.keywords):
            continue                          # a literal row; nothing to compare against
        row_id = _row_id(call)
        module = None
        for dotted in (f"apps.{row_id}", f"apps.studio.plugins.{row_id}"):
            try:
                module = importlib.import_module(dotted)
                break
            except ImportError:
                continue
        assert module is not None, f"api.py spreads {row_id}.status() but it will not import"
        published[row_id] = module.status()
    return published


class RosterParsesTests(unittest.TestCase):
    def test_the_roster_reads_and_is_not_empty(self):
        rows = roster.rows()
        self.assertEqual(len(rows), 13)
        self.assertEqual(roster.slots(), 20)

    def test_a_malformed_row_raises_instead_of_being_skipped(self):
        """The failure mode that would make the roster a fourth disagreeing list.

        A parser that skips a line it cannot read loses a rack row silently: the symptom is
        a row missing from the fallback, not an error anybody sees.
        """
        head = "| id | label | slot | bus | href | implementation | toggle |\n"
        good = "| chat | C | 1U | gpu | /c.html | backend/api.py | yes |\n"
        for bad, why in [
            ("| chat | C | 1U | gpu | /c.html | backend/api.py |\n", "six columns"),
            ("| chat | C | 1X | gpu | /c.html | backend/api.py | yes |\n", "slot not NU"),
            ("| chat | C | 1U | usb | /c.html | backend/api.py | yes |\n", "unknown bus"),
            ("| chat | C | 1U | gpu | c.html | backend/api.py | yes |\n", "relative href"),
            ("| chat | C | 1U | gpu | /c.html | backend/api.py | maybe |\n", "toggle"),
            ("| Chat | C | 1U | gpu | /c.html | backend/api.py | yes |\n", "capital in id"),
            ("| chat |  | 1U | gpu | /c.html | backend/api.py | yes |\n", "empty label"),
            (good + good, "duplicate id"),
            ("", "header and no rows"),
        ]:
            with self.subTest(why=why):
                tmp = pathlib.Path(self.enterContext(_tempfile()))
                tmp.write_text(head + bad)
                with self.assertRaises(roster.RosterError):
                    roster.rows(tmp)

    def test_a_file_with_no_table_raises(self):
        tmp = pathlib.Path(self.enterContext(_tempfile()))
        tmp.write_text("# not a roster\n\nprose only.\n")
        with self.assertRaises(roster.RosterError):
            roster.rows(tmp)
        with self.assertRaises(roster.RosterError):
            roster.excluded(tmp)


class RosterMatchesApiTests(unittest.TestCase):
    def test_the_ids_and_their_order_match_build_status(self):
        """Order matters: it is the order the rack renders, so the fallback and the live
        markup agree only if both walk the same sequence."""
        self.assertEqual([r["id"] for r in roster.rows()],
                         [_row_id(call) for call in _unit_calls()])

    def test_the_ids_match_the_hand_typed_tripwire(self):
        """Two hand-typed lists, compared. Adding a row means editing both, on purpose --
        see this file's docstring on why neither is derived from the other."""
        self.assertEqual([r["id"] for r in roster.rows()], EXPECTED)

    def test_every_field_matches_the_module_that_publishes_the_row(self):
        published_rows = _module_rows()
        self.assertEqual(sorted(published_rows),
                         ["exp", "project", "sigils", "streamer", "studio"],
                         "the set of rows api.py spreads from a module changed")
        for row in roster.rows():
            published = published_rows.get(row["id"])
            if published is None:
                continue                     # a row `api.py` builds itself; covered above
            for field in ("label", "slot", "bus", "href"):
                expected, actual = row[field], published.get(field)
                override = KNOWN_OVERRIDES.get((row["id"], field))
                with self.subTest(row=row["id"], field=field):
                    if override:
                        self.assertEqual((actual, expected), override,
                                         "the one known call-site override changed; read "
                                         "KNOWN_OVERRIDES before editing either side")
                    else:
                        self.assertEqual(actual, expected)


class RosterMatchesDiskTests(unittest.TestCase):
    def test_every_implementation_path_exists(self):
        for row in roster.rows():
            with self.subTest(row=row["id"]):
                self.assertTrue((REPO / row["implementation"]).exists(),
                                f"{row['id']} says it lives at {row['implementation']}")

    def test_every_href_resolves_to_a_page_or_a_route(self):
        """The reason `voice` has no row: `status()` is correct and `/voice.html` does not
        exist, so the row would be a dead link on the front page of a live site."""
        source = (REPO / "backend" / "api.py").read_text()
        for row in roster.rows():
            href = row["href"]
            with self.subTest(row=row["id"], href=href):
                if href.endswith(".html"):
                    self.assertTrue((REPO / "site" / href.lstrip("/")).is_file(),
                                    f"the rack links to {href}, which is not in site/")
                else:
                    self.assertIn(f'"{href}"', source,
                                  f"the rack links to {href}, which api.py does not route")

    def test_every_directory_under_apps_is_a_row_or_is_written_up_as_not_one(self):
        """A new directory that is neither a rack row nor explained is the ambiguity this
        file exists to remove -- it is how `ravencalc` and `remix` went missing from a
        roster built by looking for `__init__.py` files, since neither has one."""
        rows = roster.rows()
        accounted = roster.excluded() | {pathlib.Path(r["implementation"]).name for r in rows}
        found = {d.name for parent in (APPS, APPS / "studio" / "plugins")
                 for d in parent.iterdir()
                 if d.is_dir() and not d.name.startswith((".", "__"))}
        found -= {"plugins"}                 # the plugin container, not a plugin
        self.assertEqual(sorted(found - accounted), [],
                         "add these to ROSTER.md: as rows, or to the section saying why not")


class RosterMatchesControlboardTests(unittest.TestCase):
    def test_the_toggle_column_and_TOGGLEABLE_agree(self):
        """`TOGGLEABLE` stays the authority -- it carries the reasoning for every exclusion.
        This compares the two hand-maintained copies; deriving either would delete the check.
        """
        from apps import controlboard
        self.assertEqual(sorted(r["id"] for r in roster.rows() if r["toggle"]),
                         sorted(controlboard.TOGGLEABLE))

    def test_nothing_toggleable_is_absent_from_the_rack(self):
        ids = {r["id"] for r in roster.rows()}
        from apps import controlboard
        self.assertEqual(sorted(set(controlboard.TOGGLEABLE) - ids), [])


class GeneratedFallbackTests(unittest.TestCase):
    """`site/index.html`'s pre-JS fallback, which `tools/build_rack.py` writes from the roster.

    This is the assertion that catches the half of the work that is easy to forget: the row
    was added to the roster and `build_rack.py` was never re-run, so the committed page still
    lists the old rack. The generator is idempotent and cheap; there is no reason for the page
    to be behind, and this says so out loud rather than trusting it.
    """

    def _fallback(self) -> str:
        html = (REPO / "site" / "index.html").read_text()
        self.assertIn("<noscript>", html)
        return html.split("<noscript>", 1)[1].split("</noscript>", 1)[0]

    def test_the_fallback_lists_every_roster_row_and_nothing_else(self):
        block = self._fallback()
        rows = roster.rows()
        for row in rows:
            with self.subTest(row=row["id"]):
                self.assertIn(f'href="{row["href"]}"', block)
                self.assertIn(f'<b>{row["label"]}</b>', block)
                self.assertIn(f'<span class="slot">{row["slot"]}</span>', block)
        self.assertEqual(block.count('class="unit"'), len(rows),
                         "re-run tools/build_rack.py, then tools/build_cachebust.py")

    def test_the_fallback_claims_no_state_it_has_not_measured(self):
        """The defect this replaced: one row hardcoded `data-state="ready"`.

        A state word in a static file is a decorative indicator by CLAUDE.md's rule, and it
        is worse in the fallback than anywhere else -- the fallback renders precisely when
        the socket that could have measured it is unavailable.
        """
        block = self._fallback()
        self.assertNotIn("data-state", block)
        for word in ("ready", "busy", "queued", "offline"):
            self.assertNotIn(f'class="txt">{word}', block)
        self.assertNotIn('class="led on"', block)


def _tempfile():
    """A context manager yielding a temp path, so `enterContext` cleans it up."""
    import contextlib
    import tempfile

    @contextlib.contextmanager
    def _cm():
        with tempfile.TemporaryDirectory() as d:
            yield str(pathlib.Path(d) / "ROSTER.md")
    return _cm()


if __name__ == "__main__":
    unittest.main()
