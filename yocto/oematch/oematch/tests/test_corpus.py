"""Recipe parsing and layer licensing, against .bb trees written into a temp directory.

Every case here is a shape that exists in the real corpus and that the parser got wrong.
The licence cases name the layer each was found on, because "a layer whose LICENSE is a
pointer to COPYING" reads as hypothetical and is meta-cryptocurrency.
"""
import tempfile
import unittest
from pathlib import Path

from .. import corpus


class BbTreeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def parse(self, rel):
        return corpus.parse_bb(self.root / rel, self.root)


class AVarflagIsNotAValueTests(BbTreeCase):
    """`SRC_URI[sha256sum]` is a checksum. It was being stored as the SRC_URI."""

    def test_the_checksum_does_not_become_the_source_url(self):
        r = self.write("recipes-x/foo/foo_1.0.bb", '''
SRC_URI = "https://example.org/foo-${PV}.tar.gz"
SRC_URI[sha256sum] = "6f4b1b6a1f0d3f8ba6ed4d6cbbd08a2b0f5e2c0d9a8b7c6d5e4f3a2b1c0d9e8f"
''')
        self.assertEqual("https://example.org/foo-${PV}.tar.gz", corpus.parse_bb(r, self.root)["src_uri"])

    def test_a_recipe_with_only_a_checksum_has_no_source_url(self):
        r = self.write("recipes-x/bar/bar_1.0.bb",
                       'SRC_URI[md5sum] = "d41d8cd98f00b204e9800998ecf8427e"\n')
        self.assertEqual("", corpus.parse_bb(r, self.root)["src_uri"])


class AnOverrideOnPnNamesAVariantTests(BbTreeCase):
    """`PN:class-devupstream` is a DIFFERENT recipe, so it must not rename this one.

    An override on an identity variable was being read as the value, so a recipe called
    `bar` reported itself as `bar-dev` and could not be found by its own name. Overrides
    on other variables are legitimate values and must still be captured -- almost every
    recipe in the corpus writes `RDEPENDS:${PN}` and nothing else.
    """

    def test_an_override_does_not_rename_the_recipe(self):
        r = self.write("recipes-x/bar/bar_1.0.bb", '''
PN:class-devupstream = "bar-dev"
PV:class-devupstream = "1.1"
''')
        got = corpus.parse_bb(r, self.root)
        self.assertEqual("bar", got["pn"])
        self.assertEqual("1.0", got["pv"])

    def test_an_override_on_rdepends_is_still_a_value(self):
        r = self.write("recipes-x/baz/baz_2.0.bb", 'RDEPENDS:${PN} = "libc6 zlib"\n')
        self.assertEqual("libc6 zlib", corpus.parse_bb(r, self.root)["rdepends"])

    def test_an_unoverridden_pn_is_honoured(self):
        r = self.write("recipes-x/qux/qux_3.0.bb", 'PN = "qux-renamed"\n')
        self.assertEqual("qux-renamed", corpus.parse_bb(r, self.root)["pn"])


class TheBbAndIncSplitTests(BbTreeCase):
    """`nginx_1.29.7.bb` is one `require nginx.inc` line.

    Without following includes the recipe carries NO metadata at all -- no HOMEPAGE, no
    LICENSE, no SRC_URI -- so it cannot be found by its URL or reported with its licence.
    nginx, boost, qtbase and busybox were all empty for this reason.
    """

    def test_metadata_comes_through_from_the_include(self):
        self.write("recipes-x/nginx/nginx.inc", '''
HOMEPAGE = "http://nginx.org/"
LICENSE = "BSD-2-Clause"
SRC_URI = "http://nginx.org/download/nginx-${PV}.tar.gz"
''')
        r = self.write("recipes-x/nginx/nginx_1.29.7.bb", "require nginx.inc\n")
        got = corpus.parse_bb(r, self.root)
        self.assertEqual("http://nginx.org/", got["homepage"])
        self.assertEqual("BSD-2-Clause", got["license"])
        self.assertIn("nginx.org/download", got["src_uri"])

    def test_the_recipe_wins_over_the_file_it_requires(self):
        # bitbake resolves in that direction, and the parser relies on `setdefault` plus
        # appending the included text AFTER to get it. Easy to invert by accident.
        self.write("recipes-x/a/a.inc", 'HOMEPAGE = "http://old.example/"\n')
        r = self.write("recipes-x/a/a_1.0.bb",
                       'HOMEPAGE = "http://new.example/"\nrequire a.inc\n')
        self.assertEqual("http://new.example/", corpus.parse_bb(r, self.root)["homepage"])

    def test_a_pv_in_the_include_path_resolves_from_the_filename(self):
        # boost's HOMEPAGE and LICENSE are in `boost-${PV}.inc`, reached by
        # `require boost-${PV}.inc`. PV is not unknown -- the filename fixes it before
        # any line is read, which is where bitbake gets it too.
        self.write("recipes-x/boost/boost-1.90.0.inc", 'HOMEPAGE = "http://www.boost.org/"\n')
        r = self.write("recipes-x/boost/boost_1.90.0.bb", "require boost-${PV}.inc\n")
        self.assertEqual("http://www.boost.org/", corpus.parse_bb(r, self.root)["homepage"])

    def test_an_unknown_variable_in_the_path_is_skipped_not_guessed(self):
        r = self.write("recipes-x/c/c_1.0.bb", "require ${MACHINE}/c.inc\n")
        self.assertEqual("", corpus.parse_bb(r, self.root)["homepage"])   # and no exception

    def test_a_require_cycle_terminates(self):
        self.write("recipes-x/d/d.inc", 'require d-more.inc\nLICENSE = "MIT"\n')
        self.write("recipes-x/d/d-more.inc", "require d.inc\n")
        r = self.write("recipes-x/d/d_1.0.bb", "require d.inc\n")
        self.assertEqual("MIT", corpus.parse_bb(r, self.root)["license"])

    def test_nothing_outside_the_layer_is_read(self):
        (self.root.parent / "outside.inc").write_text('HOMEPAGE = "http://leaked/"\n')
        try:
            r = self.write("recipes-x/e/e_1.0.bb", "require ../../outside.inc\n")
            self.assertEqual("", corpus.parse_bb(r, self.root)["homepage"])
        finally:
            (self.root.parent / "outside.inc").unlink()

    def test_the_layer_root_is_searched_as_well_as_the_recipe_directory(self):
        self.write("recipes-kernel/linux/linux-yocto.inc", 'LICENSE = "GPL-2.0-only"\n')
        r = self.write("recipes-kernel/linux/custom_6.12.bb",
                       "require recipes-kernel/linux/linux-yocto.inc\n")
        self.assertEqual("GPL-2.0-only", corpus.parse_bb(r, self.root)["license"])


GPL2_BODY = ("GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n\n"
             "This program is free software; you can redistribute it")
MIT_BODY = ("MIT License\n\nPermission is hereby granted, free of charge, to any person "
            "obtaining a copy of this software")
BSD2_BODY = ("Redistribution and use in source and binary forms, with or without "
             "modification, are permitted provided that the following conditions are met:\n"
             "1. Redistributions of source code must retain the above copyright notice\n"
             "2. Redistributions in binary form must reproduce the above copyright notice")


class ALayerLicenceIsNeverAFilenameTests(BbTreeCase):
    """Four measured defects, one class each. 17 layers reported a licence of "LICENSE"."""

    def layer(self, name, files):
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        for fn, text in files.items():
            (d / fn).write_text(text)
        return d

    def test_an_unrecognised_body_reports_unknown_not_the_filename(self):
        d = self.layer("meta-mystery", {"LICENSE": "See the vendor agreement, section 4."})
        self.assertEqual("unknown", corpus.layer_license(d))

    def test_a_pointer_licence_does_not_stop_the_scan(self):
        # meta-cryptocurrency: LICENSE says "see COPYING", so returning on the first
        # candidate file that existed meant its COPYING was never read.
        d = self.layer("meta-cryptocurrency",
                       {"LICENSE": "See COPYING for details.", "COPYING": GPL2_BODY})
        self.assertEqual("GPL-2.0-only", corpus.layer_license(d))

    def test_an_unofficial_gpl_wording_is_recognised(self):
        d = self.layer("meta-informal", {"LICENSE": "GNU Public License version 2\n\n" + GPL2_BODY})
        self.assertEqual("GPL-2.0-only", corpus.layer_license(d))

    def test_bsd_is_recognised(self):
        # meta-buildutils is BSD-2-Clause and reported "LICENSE": there was no BSD
        # pattern at all.
        d = self.layer("meta-buildutils", {"LICENSE": BSD2_BODY})
        self.assertEqual("BSD-2-Clause", corpus.layer_license(d))

    def test_a_sublayer_reads_the_repository_root(self):
        # meta-agl-app-framework reported "unknown" while its parent repo holds the
        # licence files.
        (self.root / "agl-repo").mkdir()
        (self.root / "agl-repo" / ".git").mkdir()
        (self.root / "agl-repo" / "LICENSE.MIT").write_text(MIT_BODY)
        (self.root / "agl-repo" / "LICENSE.GPL-2.0-only").write_text(GPL2_BODY)
        sub = self.root / "agl-repo" / "meta-agl-app-framework"
        sub.mkdir()
        self.assertEqual("GPL-2.0-only AND MIT", corpus.layer_license(sub))

    def test_two_licences_report_in_one_order(self):
        # Both `MIT AND GPL-2.0-only` and `GPL-2.0-only AND MIT` came out of the first
        # run of this function, five layers each: one fact wearing two values.
        a = self.layer("meta-a", {"LICENSE.MIT": MIT_BODY, "LICENSE.GPL-2.0-only": GPL2_BODY})
        b = self.layer("meta-b", {"LICENSE.GPL-2.0-only": GPL2_BODY, "LICENSE.MIT": MIT_BODY})
        self.assertEqual(corpus.layer_license(a), corpus.layer_license(b))
        self.assertEqual("GPL-2.0-only AND MIT", corpus.layer_license(a))

    def test_a_filename_hint_is_mapped_to_spdx_not_returned_raw(self):
        d = self.layer("meta-empty-licence", {"COPYING.MIT": ""})
        self.assertEqual("MIT", corpus.layer_license(d))

    def test_a_layer_with_no_licence_file_reports_unknown(self):
        d = self.layer("meta-bare", {"README.md": "hello"})
        self.assertEqual("unknown", corpus.layer_license(d))


class BothRecipeSuffixesAreIndexedTests(BbTreeCase):
    """meta-clang has 0 .bb and 20 .bbappend files, and indexed as an empty layer."""

    def test_an_append_is_indexed_and_marked_as_one(self):
        from .. import db
        self.write("recipes-devtools/clang/clang_%.bbappend", 'DEPENDS += "clang"\n')
        self.write("recipes-core/thing/thing_1.0.bb", 'LICENSE = "MIT"\n')
        con = db.connect(self.root / "corpus.db")
        corpus.index_layer(con, "meta-clang", self.root)
        rows = dict(con.execute("SELECT pn, kind FROM recipes"))
        con.close()
        self.assertEqual({"clang": "bbappend", "thing": "bb"}, rows)

    def test_an_appends_version_wildcard_is_not_stored_as_a_version(self):
        from .. import db
        self.write("recipes-devtools/clang/clang_%.bbappend", "\n")
        con = db.connect(self.root / "corpus.db")
        corpus.index_layer(con, "meta-clang", self.root)
        pv = con.execute("SELECT pv FROM recipes WHERE pn='clang'").fetchone()[0]
        con.close()
        self.assertEqual("", pv)
