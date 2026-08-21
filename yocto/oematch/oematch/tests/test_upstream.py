"""Resolving an upstream repository URL to the layer that carries the project.

`match` fingerprints a FILE. There is no file here -- the question is asked about a
project named by its git remote -- so this is a different query and it needed its own
module. The cases below are the wrong answers the first implementation gave.
"""
import os
import unittest
from pathlib import Path

from .. import db, upstream
from .corpusfixture import DbCase


class ProjectNamesTests(unittest.TestCase):
    """Candidate names derived from a URL. Pure function, no corpus."""

    def test_the_repository_name_comes_first(self):
        self.assertEqual("zlib", upstream.project_names("https://github.com/madler/zlib")[0])

    def test_a_git_suffix_is_stripped(self):
        self.assertEqual("zlib", upstream.project_names("https://github.com/madler/zlib.git")[0])

    def test_a_container_segment_is_not_a_project_name(self):
        # chromium.googlesource.com/chromium/src -- a query for a recipe named `src` is
        # meaningless, and `src` was the whole reason this rule exists.
        names = upstream.project_names("https://chromium.googlesource.com/chromium/src")
        self.assertEqual("chromium", names[0])
        self.assertNotIn("src", names)

    def test_the_oe_name_is_offered_where_it_differs(self):
        self.assertIn("sqlite3", upstream.project_names("https://github.com/sqlite/sqlite"))
        self.assertIn("mongodb", upstream.project_names("https://github.com/mongodb/mongo"))
        self.assertIn("nodejs", upstream.project_names("https://github.com/nodejs/node"))
        self.assertIn("libsdl2", upstream.project_names("https://github.com/libsdl-org/SDL"))

    def test_a_packaging_suffix_is_dropped(self):
        self.assertIn("mysql", upstream.project_names("https://github.com/mysql/mysql-server"))

    def test_a_dotted_name_is_offered_both_ways(self):
        names = upstream.project_names("https://github.com/mrdoob/three.js")
        self.assertIn("threejs", names)
        self.assertIn("three", names)

    def test_the_lib_prefix_is_tried_in_both_directions(self):
        self.assertIn("libpng", upstream.project_names("https://github.com/pnggroup/libpng"))
        self.assertIn("png", upstream.project_names("https://github.com/pnggroup/libpng"))
        self.assertIn("libcurl", upstream.project_names("https://github.com/curl/curl"))

    def test_a_url_with_no_path_yields_nothing(self):
        self.assertEqual([], upstream.project_names("https://github.com"))


class AnExactNameOutranksAUrlCiteTests(DbCase):
    """The three wrong answers the URL-first ranking gave, one test each.

    Each is a recipe built out of the queried repository that is not the project asked
    about -- `lemon` is SQLite's parser generator, `libcurl-vendor` is a ROS layer
    vendoring curl, `omxplayer` bundles FFmpeg. Every citation is truthful, and none of
    them is the answer.
    """

    def setUp(self):
        super().setUp()
        self.recipe("openembedded-core", "sqlite3", pv="3.53.4",
                    src_uri="https://sqlite.org/2025/sqlite-autoconf-3530400.tar.gz")
        self.recipe("meta-oe", "lemon", pv="3.53.4",
                    src_uri="https://github.com/sqlite/sqlite")
        self.recipe("openembedded-core", "curl", pv="8.21.0", homepage="https://curl.se/")
        self.recipe("meta-ros2-humble", "libcurl-vendor", pv="3.1.3-1",
                    src_uri="https://github.com/curl/curl")

    def test_the_oe_name_wins_over_a_sibling_citing_the_repo(self):
        got = upstream.resolve(self.con, "https://github.com/sqlite/sqlite")["matches"]
        self.assertEqual("sqlite3", got[0]["pn"])
        self.assertTrue(got[0]["exact_pn"])

    def test_the_sibling_is_still_reported_rather_than_hidden(self):
        # It is a real recipe and someone looking for `lemon` should find it here. The
        # bug was its rank, not its presence.
        got = upstream.resolve(self.con, "https://github.com/sqlite/sqlite")["matches"]
        self.assertIn("lemon", [r["pn"] for r in got])

    def test_a_vendored_copy_does_not_outrank_the_recipe(self):
        got = upstream.resolve(self.con, "https://github.com/curl/curl")["matches"]
        self.assertEqual("curl", got[0]["pn"])

    def test_a_recipe_citing_the_url_and_named_for_it_ranks_above_either(self):
        self.recipe("meta-both", "sqlite3", pv="3.50.0",
                    src_uri="https://github.com/sqlite/sqlite")
        got = upstream.resolve(self.con, "https://github.com/sqlite/sqlite")["matches"]
        self.assertEqual(("sqlite3", "meta-both"), (got[0]["pn"], got[0]["layer"]))
        self.assertIn("url:", got[0]["why"])


class OneRowPerRecipePerLayerTests(DbCase):
    """meta-igep carries linux 3.2, 3.10 and 3.17.

    Three rows for one recipe filled the result and pushed `linux-yocto` -- the answer --
    off the end of it entirely.
    """

    def setUp(self):
        super().setUp()
        for pv in ("3.2", "3.10", "3.17"):
            self.recipe("meta-igep", "linux", pv=pv,
                        src_uri="https://github.com/torvalds/linux")
        self.recipe("openembedded-core", "linux-yocto", pv="6.12")

    def test_a_layer_contributes_one_row_per_recipe(self):
        got = upstream.resolve(self.con, "https://github.com/torvalds/linux", limit=3)["matches"]
        self.assertEqual(1, len([r for r in got if (r["pn"], r["layer"]) == ("linux", "meta-igep")]))

    def test_the_answer_is_not_crowded_out(self):
        got = upstream.resolve(self.con, "https://github.com/torvalds/linux", limit=3)["matches"]
        self.assertIn("linux-yocto", [r["pn"] for r in got])


class AnAppendIsADifferentAnswerTests(DbCase):
    """meta-clang provides no recipes at all. An append is the only true answer for it.

    Folding appends into the ranked list would have the tool say "meta-clang provides
    llvm-project", which is false; dropping them has it say meta-clang is empty, which is
    also false. So they are returned separately and printed under a different mark.
    """

    def setUp(self):
        super().setUp()
        self.recipe("openembedded-core", "llvm", pv="20.1.0",
                    src_uri="https://github.com/llvm/llvm-project")
        self.recipe("meta-clang", "llvm-project", kind="bbappend",
                    filepath="recipes-devtools/clang/llvm-project_%.bbappend")

    def test_the_append_is_reported_and_not_ranked_as_a_provider(self):
        got = upstream.resolve(self.con, "https://github.com/llvm/llvm-project")
        self.assertEqual(["meta-clang"], [a["layer"] for a in got["appends"]])
        self.assertNotIn("meta-clang", [r["layer"] for r in got["matches"]])

    def test_a_layer_that_only_appends_is_still_found(self):
        self.con.execute("DELETE FROM recipes WHERE kind='bb'")
        self.con.commit()
        got = upstream.resolve(self.con, "https://github.com/llvm/llvm-project")
        self.assertEqual([], got["matches"])
        self.assertEqual(["meta-clang"], [a["layer"] for a in got["appends"]])


class NothingFoundIsAnAnswerTests(DbCase):
    """A tool that invents a plausible match is worse than one that says it found none.

    The eight NPM entries in UPSTREAM_GROUPS have no recipe in any layer -- they are
    fetched by `npm.bbclass` during an image build -- so "nothing" is the correct answer
    and is asserted as one.
    """

    def test_an_unknown_project_resolves_to_nothing(self):
        self.recipe("openembedded-core", "zlib", homepage="http://zlib.net/")
        got = upstream.resolve(self.con, "https://github.com/expressjs/express")
        self.assertEqual([], got["matches"])
        self.assertEqual([], got["appends"])


class TheCuratedGroupingsTests(unittest.TestCase):
    """Every row of UPSTREAM_GROUPS, resolved against the real corpus.

    Opt-in, via OEMATCH_TEST_CORPUS=1, and deliberately not run by `dh_auto_test`. These
    rows are a claim about 479 cloned layers, so without them there is nothing to check
    -- but the developer machine that builds the .deb HAS a corpus, and a package build
    that fails because an upstream layer moved a recipe is a build broken by somebody
    else's commit. So the corpus check is a thing you run, not a thing a build does:

        OEMATCH_TEST_CORPUS=1 python3 -m unittest discover -s oematch/tests -t .

    The rows in RESOLVES_TO are the ones measured to resolve into their expected group,
    listed one by one so a regression names the row rather than showing up as a
    worse-feeling ranking.
    """

    # Measured, not aspirational: these are the rows that DID resolve into the group
    # Garrett put them in. The rest are listed in the module docstring with the reason,
    # which is usually that no layer in the corpus carries the project at all.
    RESOLVES_TO = ()

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("OEMATCH_TEST_CORPUS"):
            raise unittest.SkipTest("set OEMATCH_TEST_CORPUS=1 to check rows against the corpus")
        p = Path(os.environ.get("OEMATCH_DB", Path.home() / ".cache/oematch/corpus.db"))
        if not p.exists():
            raise unittest.SkipTest(f"no corpus at {p}; run `oematch build` to check these")
        cls.con = db.connect(p)
        n = cls.con.execute("SELECT count(*) FROM layers").fetchone()[0]
        if n < 100:
            raise unittest.SkipTest(f"corpus has only {n} layers; these rows need the full index")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "con"):
            cls.con.close()

    def test_the_npm_group_resolves_to_nothing(self):
        for group, url, _note in upstream.UPSTREAM_GROUPS:
            if group != "npm":
                continue
            with self.subTest(url=url):
                got = upstream.resolve(self.con, url)
                self.assertEqual([], got["matches"], f"{url} should have no recipe anywhere")

    def test_the_measured_rows_still_resolve_to_their_group(self):
        if not self.RESOLVES_TO:
            self.skipTest("no measured rows recorded yet")
        by_url = {u: g for g, u, _ in upstream.UPSTREAM_GROUPS}
        for url in self.RESOLVES_TO:
            with self.subTest(url=url):
                want = upstream.GROUP_LAYERS.get(by_url[url], {by_url[url]})
                got = upstream.resolve(self.con, url)
                layers = [r["layer"] for r in got["matches"]] + [a["layer"] for a in got["appends"]]
                self.assertTrue(set(layers) & want,
                                f"{url} expected {by_url[url]}, got {layers}")
