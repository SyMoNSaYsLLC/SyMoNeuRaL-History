"""A four-recipe corpus, built in a temp directory, for tests that need a database.

Deliberately hand-built rather than a copy of the real one: every row here exists to
reproduce one measured defect, and a test that reads ~/.cache cannot run on a build
machine and cannot be trusted to still contain what it did when it was written.
"""
import tempfile
import unittest
from pathlib import Path

from .. import db


class DbCase(unittest.TestCase):
    """Base class giving each test a fresh on-disk corpus in self.con."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.con = db.connect(self.root / "corpus.db")
        self.layers = {}

    def tearDown(self):
        self.con.close()
        self._tmp.cleanup()

    def layer(self, name, license="MIT"):
        if name not in self.layers:
            self.layers[name] = db.upsert_layer(self.con, name, license=license)
        return self.layers[name]

    def recipe(self, layer, pn, **kw):
        db.insert_recipe(self.con, self.layer(layer), dict(pn=pn, **kw))
        self.con.commit()
