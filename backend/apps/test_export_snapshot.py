"""tools/export_snapshot.sh -- allow-list construction and fail-closed refusal.

`docs/ops/EXPORTS.md` rule 4 makes this script the only sanctioned way a snapshot leaves
this box, so the thing worth testing is not that it can write a zip. It is that it REFUSES,
and that a path nobody classified does not ship.

## Everything here is synthetic

No test touches a real protected artefact. The fixture tree is built in a fresh `mktemp`
directory on every run and contains files this repo has never had -- `corpus.jsonl` here
holds the bytes `SYNTHETIC-FIXTURE-NOT-REAL-DATA`, not the 327 examples. Planting a sentinel
into a real protected path to see whether the exporter notices would be the same mistake the
exporter exists to prevent.

## The unclassified-path test is the one that matters

Allow-list and deny-list architectures agree on the easy cases: both ship an allowed file
and both refuse a known-protected one. They give OPPOSITE answers for a harmless file that
nobody classified -- deny-list ships it, allow-list does not. So `test_unclassified_path_
is_excluded` is what actually distinguishes the implemented architecture from the one the
A-2 contract forbids, and it asserts absence is caused by the allow-list rather than by an
ignore rule: the file is inside the manifest-named directory's sibling, plainly visible to
the exporter, and simply never named.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORTER = ROOT / "tools" / "export_snapshot.sh"

SENTINEL = "SYNTHETIC-FIXTURE-NOT-REAL-DATA"


class ExportSnapshotTests(unittest.TestCase):
    """Every test builds its own fixture root and removes only what it created."""

    def setUp(self):
        self.assertTrue(EXPORTER.is_file(), f"exporter missing at {EXPORTER}")
        self.assertTrue(os.access(EXPORTER, os.X_OK), "exporter is not executable")
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="a2-export-fixture-"))
        self.root = self.tmp / "fixture-root"
        (self.root / "deliverable").mkdir(parents=True)
        (self.root / "deliverable" / "app.txt").write_text(f"{SENTINEL} allowed\n")
        (self.root / "deliverable" / "readme.md").write_text(f"{SENTINEL} allowed\n")
        # Harmless, present, and deliberately NOT named in any manifest.
        (self.root / "unlisted").mkdir()
        (self.root / "unlisted" / "notes.txt").write_text(f"{SENTINEL} unclassified\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------------------
    def _manifest(self, *lines: str) -> pathlib.Path:
        p = self.tmp / "fixture-scope.manifest"
        p.write_text("# synthetic A-2 test fixture -- not a production manifest\n"
                     + "\n".join(lines) + "\n")
        return p

    def _run(self, manifest: pathlib.Path, out: pathlib.Path | None, *extra: str):
        argv = ["bash", str(EXPORTER), "--manifest", str(manifest), "--root", str(self.root)]
        if out is not None:
            argv += ["--out", str(out)]
        argv += list(extra)
        return subprocess.run(argv, capture_output=True, text=True)

    # -- positive --------------------------------------------------------------------
    def test_allowed_path_is_exported(self):
        """An explicitly named path ships, and the archive is inspectable."""
        out = self.tmp / "export.zip"
        r = self._run(self._manifest("deliverable"), out)
        self.assertEqual(r.returncode, 0, f"expected success, got {r.returncode}: {r.stderr}")
        self.assertTrue(out.is_file(), "no archive was produced")

        names = zipfile.ZipFile(out).namelist()
        self.assertIn("deliverable/app.txt", names)
        self.assertIn("deliverable/readme.md", names)
        self.assertIn("EXPORT-MANIFEST", names)

        manifest_text = zipfile.ZipFile(out).read("EXPORT-MANIFEST").decode()
        self.assertIn("source-sha:", manifest_text, "manifest must name the source SHA")
        self.assertIn("deliverable/app.txt", manifest_text)
        # A checksum per file, so a recipient can verify what they received.
        self.assertIn("sha256", manifest_text)

    # -- the architecture-distinguishing test ----------------------------------------
    def test_unclassified_path_is_excluded(self):
        """A harmless unnamed file must NOT ship. Deny-list would ship it; allow-list does not."""
        out = self.tmp / "export.zip"
        # Prove the file is really there and visible to the exporter before we assert absence.
        self.assertTrue((self.root / "unlisted" / "notes.txt").is_file())

        r = self._run(self._manifest("deliverable"), out)
        self.assertEqual(r.returncode, 0, r.stderr)

        names = zipfile.ZipFile(out).namelist()
        self.assertNotIn("unlisted/notes.txt", names,
                         "unclassified path leaked -- this is deny-list behaviour")
        # Absence must be caused by the allow-list, not by an ignore rule: naming it ships it.
        out2 = self.tmp / "export2.zip"
        r2 = self._run(self._manifest("deliverable", "unlisted"), out2)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("unlisted/notes.txt", zipfile.ZipFile(out2).namelist(),
                      "file is ignorable, so the first absence proved nothing")

    # -- negative / fail-closed --------------------------------------------------------
    def test_protected_path_is_refused(self):
        """A synthetic protected artefact in the candidate set aborts the export."""
        # Synthetic file at a path that matches a protected CLASS. Contents are a marker.
        (self.root / "training").mkdir()
        (self.root / "training" / "corpus.jsonl").write_text(f'{{"{SENTINEL}": true}}\n')
        planted = self.root / "training" / "corpus.jsonl"
        self.assertTrue(planted.is_file(), "precondition: prohibited artefact must be present")

        out = self.tmp / "must-not-exist.zip"
        # An over-broad manifest entry -- exactly the stage-1 mistake stage 2 exists to catch.
        r = self._run(self._manifest("deliverable", "training"), out)

        self.assertNotEqual(r.returncode, 0, "exporter did not refuse a protected path")
        self.assertFalse(out.exists(), "an archive was emitted despite refusal")
        self.assertIn("PROTECTED", r.stderr, "refusal must name the offending class")
        self.assertIn("corpus.jsonl", r.stderr, "refusal must name the offending path")
        self.assertNotIn(SENTINEL, r.stderr, "refusal must not print file contents")

    def test_refusal_precedes_archive_creation(self):
        """No partial archive survives a refusal."""
        (self.root / "run").mkdir()
        (self.root / "run" / "state.db").write_text(f"{SENTINEL}\n")
        out = self.tmp / "partial.zip"
        r = self._run(self._manifest("deliverable", "run"), out)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(out.exists(), "partial archive left on disk after refusal")

    # -- interface safety --------------------------------------------------------------
    def test_no_manifest_is_refused(self):
        """There is no implicit whole-repo export."""
        r = subprocess.run(["bash", str(EXPORTER), "--out", str(self.tmp / "x.zip")],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--manifest is required", r.stderr)

    def test_traversal_is_refused(self):
        """A manifest cannot escape the root."""
        r = self._run(self._manifest("../../etc/passwd"), self.tmp / "x.zip")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("traversal", r.stderr)

    def test_missing_manifest_path_is_refused(self):
        """A manifest that no longer matches the tree must not silently ship less."""
        r = self._run(self._manifest("deliverable", "gone"), self.tmp / "x.zip")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not exist", r.stderr)


if __name__ == "__main__":
    unittest.main()
