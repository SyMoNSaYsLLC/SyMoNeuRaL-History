"""Ranking defects that were measured against the real corpus, reproduced in four rows.

Each class here names a wrong answer the tool actually gave, not a property it ought to
have. `oematch match /usr/bin/ffmpeg` put twelve `aws-c-*` recipes at 7.0 -- above `gcc`
at 6.0 -- for every binary linked against libc, which is every binary.
"""
from ..extract import Signals
from ..match import Matcher
from .corpusfixture import DbCase


class AShortSonameStemMatchesNothingTests(DbCase):
    """`libc.so.6` must score glibc and must not score `aws-c-auth`.

    SQLite's FTS5 tokenizer splits on hyphens, so `provides MATCH 'c'` matches the token
    `c` inside `aws-c-auth`. SONAME_MAP maps stem `c` to glibc, but the loop used to fall
    through to the guess anyway, and the guess is what scored the aws recipes.
    """

    def setUp(self):
        super().setUp()
        self.recipe("openembedded-core", "glibc", provides="glibc virtual/libc")
        self.recipe("openembedded-core", "gcc", provides="gcc")
        for pn in ("aws-c-auth", "aws-c-io", "aws-c-common"):
            self.recipe("meta-amazon", pn, provides=pn, rprovides=pn)
        # The OTHER libcs. These are why the `continue` is the load-bearing half of the
        # fix and the length guard is only half: with the guard in place but the loop
        # still falling through, `_by_pn("c")` returns nothing, the `_by_pn("lib" + stem)`
        # arm fires, and every one of these is scored 7 as if the binary linked to it.
        # Measured on the real corpus: 13 wrong recipes, musl and newlib among them.
        self.recipe("openembedded-core", "musl", provides="musl virtual/libc libc")
        self.recipe("meta-oe", "newlib", provides="newlib libc")
        self.recipe("meta-zephyr", "picolibc", provides="picolibc libc")

    def _run(self):
        sig = Signals(source="test")
        sig.sonames = {"libc.so.6"}
        return Matcher(self.con).run(sig)

    def test_glibc_is_scored_from_the_map_and_nothing_else_is(self):
        # SONAME_MAP is an ANSWER, not a hint. A mapped soname must not also be guessed
        # at, or `libc.so.6` reports musl, newlib and picolibc alongside glibc, each at
        # the same 7 points, for a binary that is linked against exactly one of them.
        res = self._run()
        self.assertEqual(["glibc"], [r["pn"] for r in res])
        self.assertIn("soname:libc.so.6→glibc", res[0]["evidence"])

    def test_no_aws_recipe_is_scored_at_all(self):
        # Not "ranks lower": absent. There is no length at which `c` identifies
        # `aws-c-auth`, so this is a wrong answer removed, not a weight adjusted.
        self.assertEqual([], [r["pn"] for r in self._run() if r["pn"].startswith("aws-")])

    def test_a_one_character_name_reaches_no_fallback(self):
        self.assertEqual([], Matcher(self.con)._by_pn("c"))

    def test_a_long_enough_name_still_reaches_the_fallback(self):
        # The guard must not cost us the case it exists to serve: PROVIDES is how
        # `virtual/libc` is found, and that lookup goes through the same fallback.
        self.assertTrue(Matcher(self.con)._by_pn("virtual"))


class HomepageContainmentRunsBothWaysTests(DbCase):
    """A recipe's SRC_URI is usually a release artefact UNDER the project URL.

    Only `candidate in query` was tested, which is the rarer direction, so `xz` -- whose
    SRC_URI is `github.com/tukaani-project/xz/releases/download/v${PV}/...` -- was missed
    by a query for `github.com/tukaani-project/xz`.
    """

    def setUp(self):
        super().setUp()
        self.recipe("openembedded-core", "xz",
                    src_uri="https://github.com/tukaani-project/xz/releases/download/v5.6.2/xz-5.6.2.tar.gz")
        self.recipe("openembedded-core", "zlib", homepage="http://zlib.net/",
                    src_uri="https://zlib.net/zlib-1.3.1.tar.xz")
        self.recipe("meta-oe", "lemon", src_uri="https://github.com/sqlite/sqlite")

    def _ids(self, url):
        m = Matcher(self.con)
        return {self.con.execute("SELECT pn FROM recipes WHERE id=?", (i,)).fetchone()[0]
                for i in m._by_homepage(url)}

    def test_a_project_url_finds_a_release_artefact_under_it(self):
        self.assertEqual({"xz"}, self._ids("https://github.com/tukaani-project/xz"))

    def test_an_exact_homepage_still_matches(self):
        self.assertEqual({"zlib"}, self._ids("http://zlib.net/"))

    def test_containment_does_not_leak_between_projects(self):
        self.assertEqual(set(), self._ids("https://github.com/tukaani-project/other-thing"))
        self.assertEqual({"lemon"}, self._ids("https://github.com/sqlite/sqlite"))


class AnAppendIsNotARecipeTests(DbCase):
    """meta-clang carries 0 .bb and 20 .bbappend files.

    Indexing only .bb made an active layer read as empty; indexing appends as recipes
    would have it answer "meta-clang provides ffmpeg", which is false. `match` ranks
    providers, so every one of its queries filters to kind='bb'.
    """

    def setUp(self):
        super().setUp()
        self.recipe("openembedded-core", "ffmpeg", provides="ffmpeg",
                    homepage="https://ffmpeg.org", summary="video conversion")
        self.recipe("meta-clang", "ffmpeg", kind="bbappend",
                    filepath="recipes-multimedia/ffmpeg/ffmpeg_%.bbappend")

    def test_by_pn_returns_only_the_provider(self):
        ids = Matcher(self.con)._by_pn("ffmpeg")
        self.assertEqual(1, len(ids))
        self.assertEqual("openembedded-core", self.con.execute(
            "SELECT l.name FROM recipes r JOIN layers l ON l.id=r.layer_id WHERE r.id=?",
            (ids[0],)).fetchone()[0])

    def test_no_append_is_reachable_by_url_or_text(self):
        m = Matcher(self.con)
        self.assertEqual(1, len(m._by_homepage("https://ffmpeg.org")))
        m._fts(["ffmpeg", "video"])
        layers = {self.con.execute(
            "SELECT l.name FROM recipes r JOIN layers l ON l.id=r.layer_id WHERE r.id=?",
            (i,)).fetchone()[0] for i in m.scores}
        self.assertEqual({"openembedded-core"}, layers)

    def test_an_append_ranked_as_a_provider_would_be_a_wrong_answer(self):
        # Stated as an assertion so the intent survives: a match result must never name
        # a layer that only appends. This is the check that fails if the kind='bb'
        # filter is dropped from any one of the three queries.
        sig = Signals(source="test")
        sig.tools = {"ffmpeg"}
        sig.urls = {"https://ffmpeg.org"}
        res = Matcher(self.con).run(sig)
        self.assertTrue(res)
        self.assertNotIn("meta-clang", [r["layer"] for r in res])
