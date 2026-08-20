"""The Tuner/Guide -> Streamer migration, asserted rather than assumed.

Garrett: *"i said tuner and guide needed to be merged and migrated to streamer"* -- the
migration is the namespace and the visitor-facing surfaces, not just the Python package.
This file guards the two halves of that which a rename sweep gets wrong, and it exists
because **both of them were got wrong here first**, within minutes of each other:

1. **The storage shim inverted itself.** The pages carry the visitor's playlist,
   favourites and credentials in `localStorage`, under keys that were `symoneural.tuner*`.
   A read-old-write-new shim was written into `tools/build_pages.py` and then the very
   same pass renamed every `symoneural.tuner` literal in the file -- including the shim's
   own `_OLD`. The result read `_OLD = 'symoneural.streamer'`: syntactically perfect, and
   a no-op that would have silently emptied every visitor's saved playlist. Nothing on the
   page would look broken. `node --check` was happy. That is why the assertion below is on
   the *retired* spelling: it is the one string in the file a rename must NOT touch.

2. **The rack row and the page name have to move together.** `apps/test_status_rack.py`
   infers each row from the module name in the AST, so it stayed green while `status()`
   published `id="tuner"` -- see the note there where `ROW_OF_MODULE` used to be.

Reads generated output, not the generator: what ships is what a visitor gets.
"""
from __future__ import annotations

import pathlib
import unittest

SITE = pathlib.Path(__file__).resolve().parents[2] / "site"
PAGES = ("streamer.html", "streamer-watch.html")

#: The prefix the visitor's data was stored under before the merge. Spelled out rather than
#: derived, because deriving it from anything is how it got overwritten the first time.
RETIRED_PREFIX = "symoneural." + "tuner"
LIVE_PREFIX = "symoneural.streamer"


class StorageMigrationTests(unittest.TestCase):
    def test_both_pages_carry_the_visitor_data_across_the_rename(self):
        for name in PAGES:
            with self.subTest(page=name):
                src = (SITE / name).read_text()
                self.assertIn(f"_OLD = '{RETIRED_PREFIX}'", src,
                              f"{name} does not read the retired key prefix, so a visitor's "
                              "playlist, favourites and credentials are dropped on the floor. "
                              "This is exactly the inert-shim bug in this file's docstring.")
                self.assertIn(f"_NEW = '{LIVE_PREFIX}'", src)

    def test_the_shim_does_not_overwrite_newer_data(self):
        """Idempotent, or a reload rolls the visitor back to what they had before."""
        for name in PAGES:
            with self.subTest(page=name):
                self.assertIn("getItem(_nk) === null", (SITE / name).read_text())

    def test_the_live_pages_store_under_the_new_prefix(self):
        for name in PAGES:
            with self.subTest(page=name):
                src = (SITE / name).read_text()
                # Every key literal except the shim's own _OLD must be the new prefix.
                stale = [ln.strip() for ln in src.splitlines()
                         if RETIRED_PREFIX in ln and "_OLD" not in ln]
                self.assertEqual(stale, [], f"{name} still stores under the retired prefix")


class NamespaceTests(unittest.TestCase):
    def test_no_page_calls_the_retired_api_prefix(self):
        """A page calling /api/tuner/* gets a 404: api.py mounts /api/streamer now.

        Deliberately no alias is kept for the API. A stale *bookmark* is permanent and gets
        a redirect; a stale *cached page* resolves itself on the next reload, which is
        Garrett's own test for whether something needs handling at all -- "if it isnt going
        to break our project and its something that will resolve itself naturally DROP IT".
        """
        for page in SITE.glob("*.html"):
            with self.subTest(page=page.name):
                self.assertNotIn("/api/" + "tuner", page.read_text())

    def test_the_retired_pages_are_gone_not_merely_superseded(self):
        for gone in ("tuner.html", "tuner-watch.html"):
            with self.subTest(page=gone):
                self.assertFalse((SITE / gone).exists(),
                                 f"site/{gone} still exists; two pages for one surface is "
                                 "the duplicate-href defect the merge was ordered to fix")

    def test_the_pages_the_migration_produces_exist(self):
        for name in PAGES:
            with self.subTest(page=name):
                self.assertTrue((SITE / name).is_file())


if __name__ == "__main__":
    unittest.main()
