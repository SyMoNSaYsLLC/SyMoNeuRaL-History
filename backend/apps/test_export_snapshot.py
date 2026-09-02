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


class _ExporterFixture(unittest.TestCase):
    """Shared synthetic fixture + invocation helpers.

    Split out from the test cases so the P1 class below can reuse the fixture WITHOUT
    inheriting -- and therefore re-running -- the A-2 cases. Subclassing a TestCase to get
    at its setUp silently doubles every inherited test, which inflates the pass count and
    makes a regression report say 29 when it means 22.
    """

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


class ExportSnapshotTests(_ExporterFixture):
    """A-2 contract: allow-list construction and fail-closed refusal."""

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



# ==========================================================================================
# P1 (D-11) -- signing-material exclusions.
#
# WHY THIS EXISTS BEFORE ANY KEY DOES. Measured 2026-09-02 against the then-live 17 patterns:
# `ops/keys/release.asc`, `.gnupg/pubring.kbx`, `ops/release.gpg`, `ops/release.minisig`,
# `ops/signing/release_ed25519` and its `.pub` ALL passed stage 2. That was harmless only
# because zero keys existed. Generating a key first would have opened a window in which the
# private half was exportable, so P1 is a prerequisite of the key ceremony, not a follow-up.
#
# NO REAL KEY MATERIAL IS USED. Every fixture below is a synthetic armor header over the
# bytes SYNTHETIC-FIXTURE-NOT-REAL-DATA. There is no key to extract from this file, and
# generating a real one to test with would be the exact mistake the control exists to prevent.
#
# Note the consequence of content-based detection: a manifested file that merely QUOTES a
# private-key header now refuses. That is correct fail-closed behaviour. It also means this
# test file must never appear in an export manifest -- and it does not.
# ==========================================================================================

# Synthetic armor headers. Real keys are ~1.6 KB of base64 after the header; these are the
# header line only, which is what the control matches on.
PRIVATE_PGP = f"-----BEGIN PGP PRIVATE KEY BLOCK-----\n{SENTINEL}\n-----END PGP PRIVATE KEY BLOCK-----\n"
PRIVATE_SSH = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{SENTINEL}\n-----END OPENSSH PRIVATE KEY-----\n"
PRIVATE_PEM = f"-----BEGIN RSA PRIVATE KEY-----\n{SENTINEL}\n-----END RSA PRIVATE KEY-----\n"
# The carve-out. Note PUBLIC: none of the three private patterns match this line, which is
# why P1-c needs no special case in the exporter -- only a test that keeps it that way.
PUBLIC_PGP = f"-----BEGIN PGP PUBLIC KEY BLOCK-----\n{SENTINEL}\n-----END PGP PUBLIC KEY BLOCK-----\n"


class P1SigningMaterialExclusionTests(_ExporterFixture):
    """P1-a path/name rules, P1-b content detection, P1-c public-material carve-out."""

    def _refused(self, r, out: pathlib.Path, *, expect_in_stderr: str):
        """Every P1 refusal owes the same three things: non-zero, diagnosable, no archive."""
        self.assertNotEqual(r.returncode, 0, f"exporter did NOT refuse: {r.stdout}")
        self.assertFalse(out.exists(), "an archive was emitted despite refusal")
        self.assertIn("PROTECTED", r.stderr, "refusal must name a protected class")
        self.assertIn(expect_in_stderr, r.stderr,
                      f"refusal must be diagnosable; stderr was: {r.stderr}")
        self.assertNotIn(SENTINEL, r.stderr, "refusal must never print file contents")

    # -- P1-a: unambiguously private by path or name -----------------------------------
    def test_p1a_kbx_keybox_refused(self):
        (self.root / "deliverable" / "pubring.kbx").write_text(f"{SENTINEL}\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="pubring.kbx")

    def test_p1a_private_keys_v1d_refused(self):
        d = self.root / "deliverable" / "private-keys-v1.d"
        d.mkdir()
        (d / "ABCD1234.key").write_text(f"{SENTINEL}\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="private-keys-v1.d")

    def test_p1a_gnupg_home_refused(self):
        d = self.root / "deliverable" / ".gnupg"
        d.mkdir()
        (d / "trustdb.gpg").write_text(f"{SENTINEL}\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr=".gnupg")

    def test_p1a_minisig_refused(self):
        (self.root / "deliverable" / "release.minisig").write_text(f"{SENTINEL}\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="release.minisig")

    def test_p1a_ops_keys_dir_refused(self):
        """Refused by LOCATION: the custody directory is protected whatever the file is named."""
        d = self.root / "ops" / "keys"
        d.mkdir(parents=True)
        # Deliberately innocuous name and innocuous contents -- location alone must refuse.
        (d / "notes.txt").write_text(f"{SENTINEL} not actually a key\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable", "ops"), out), out,
                      expect_in_stderr="ops/keys/notes.txt")

    def test_p1a_ops_signing_dir_refused(self):
        d = self.root / "ops" / "signing"
        d.mkdir(parents=True)
        (d / "notes.txt").write_text(f"{SENTINEL} not actually a key\n")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable", "ops"), out), out,
                      expect_in_stderr="ops/signing/notes.txt")

    # -- P1-b: content detection, independent of name ----------------------------------
    # Each fixture sits under deliverable/ at a name that NO P1-a pattern matches. If one
    # were placed at ops/keys/*.asc it would refuse for the wrong reason and prove nothing
    # about content inspection.
    def test_p1b_armored_pgp_private_key_content_refused(self):
        (self.root / "deliverable" / "release.asc").write_text(PRIVATE_PGP)
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="(content)")

    def test_p1b_openssh_private_key_content_refused(self):
        """Named .gpg, contents are OpenSSH. Name says one thing, bytes say another."""
        (self.root / "deliverable" / "thing.gpg").write_text(PRIVATE_SSH)
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="OpenSSH private key (content)")

    def test_p1b_generic_pem_private_key_content_refused(self):
        """EXTENSIONLESS. No name pattern can reach this without refusing arbitrary files."""
        (self.root / "deliverable" / "nokey").write_text(PRIVATE_PEM)
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="deliverable/nokey")

    def test_p1b_detection_is_extension_independent(self):
        """The SAME bytes must refuse under every name, including a .txt web asset."""
        for name in ("release.asc", "thing.gpg", "nokey", "innocuous.txt", "notes.md"):
            with self.subTest(name=name):
                target = self.root / "deliverable" / name
                target.write_text(PRIVATE_SSH)
                out = self.tmp / f"must-not-exist-{name}.zip"
                self._refused(self._run(self._manifest("deliverable"), out), out,
                              expect_in_stderr="(content)")
                target.unlink()

    def test_p1b_leading_nul_does_not_bypass(self):
        """A binary prefix must not turn a private key into 'binary file, skipped'."""
        (self.root / "deliverable" / "padded").write_bytes(
            b"\x00\x00\x00binary junk\n" + PRIVATE_SSH.encode())
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="(content)")

    def test_p1b_large_file_does_not_bypass(self):
        """The header sits ~4 MB in, AFTER the padding.

        This is the test that fails if anyone 'optimises' the scan with `head -c`. A byte
        cap is not a performance tweak, it is the bypass: pad past the cap and the key ships.
        """
        big = self.root / "deliverable" / "big.bin"
        with big.open("wb") as fh:
            fh.write(b"padding padding padding\n" * 175_000)   # ~4 MB of noise first
            fh.write(PRIVATE_SSH.encode())                      # header near the END
        self.assertGreater(big.stat().st_size, 4_000_000, "fixture is not actually large")
        out = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable"), out), out,
                      expect_in_stderr="(content)")

    def test_p1b_uninspectable_candidate_is_refused(self):
        """An inspection that could NOT run has not passed.

        grep exits >=2 on an unreadable file. The naive `if grep -q ...; then refuse; fi`
        reads that error as 'no match' and exports the file uninspected. Verified on this
        host: unreadable -> rc 2, clean miss -> rc 1, match -> rc 0.
        """
        blocked = self.root / "deliverable" / "unreadable.bin"
        blocked.write_text(f"{SENTINEL}\n")
        blocked.chmod(0o000)
        try:
            if os.access(blocked, os.R_OK):
                self.skipTest("running as root; file modes do not restrict reads")
            out = self.tmp / "must-not-exist.zip"
            self._refused(self._run(self._manifest("deliverable"), out), out,
                          expect_in_stderr="uninspectable")
        finally:
            blocked.chmod(0o644)

    # -- P1-c: the carve-out that keeps P1 from over-blocking ---------------------------
    def test_p1c_public_armored_keyring_is_exportable(self):
        """A PUBLIC keyring .asc MUST still export.

        This is the load-bearing test of P1-c, in the same sense that
        `test_unclassified_path_is_excluded` is load-bearing for A-2. P1 is only correct if
        it discriminates private signing material from public verification material. A
        recipient cannot verify anything without the public key, so refusing it would break
        the very release chain D-11 exists to build.

        It will FAIL LOUDLY if a future change adds a blanket ``.asc`` suffix prohibition
        -- which
        is exactly why it is written as a positive assertion about archive contents rather
        than a comment asking people not to do that.
        """
        keyring = self.root / "deliverable" / "symoneural-archive-keyring.asc"
        keyring.write_text(PUBLIC_PGP)
        out = self.tmp / "export.zip"
        r = self._run(self._manifest("deliverable"), out)
        self.assertEqual(r.returncode, 0,
                         f"public keyring was refused -- P1 is over-blocking: {r.stderr}")
        self.assertTrue(out.is_file(), "no archive produced for a legitimate public export")
        self.assertIn("deliverable/symoneural-archive-keyring.asc",
                      zipfile.ZipFile(out).namelist(),
                      "public verification material must be present in the archive")

    # -- scope: a refusal control, not a repository scanner ----------------------------
    def test_p1_inspects_only_manifested_candidates(self):
        """An UNMANIFESTED private key must not even be looked at.

        If P1 were a repository-wide secret scanner it would find this and refuse, which
        would be the wrong architecture: it would make every export depend on the state of
        files nobody asked to export. Stage 2b iterates the same CANDIDATES array stage 1
        built, so an unnamed path is never opened.
        """
        (self.root / "unlisted" / "stray.asc").write_text(PRIVATE_SSH)
        out = self.tmp / "export.zip"
        r = self._run(self._manifest("deliverable"), out)
        self.assertEqual(r.returncode, 0,
                         f"unmanifested key caused a refusal -- P1 became a scanner: {r.stderr}")
        names = zipfile.ZipFile(out).namelist()
        self.assertNotIn("unlisted/stray.asc", names, "unmanifested file leaked into archive")
        # And naming it DOES refuse -- proving the pass above was scope, not a blind spot.
        out2 = self.tmp / "must-not-exist.zip"
        self._refused(self._run(self._manifest("deliverable", "unlisted"), out2), out2,
                      expect_in_stderr="(content)")


if __name__ == "__main__":
    unittest.main()
