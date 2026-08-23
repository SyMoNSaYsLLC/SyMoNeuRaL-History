"""The Control Plane Matrix, held to its own claims.

A matrix of ratings and reachability cells is prose, and prose drifts. These tests exist so the
four documents cannot quietly stop being true:

  * `docs/specs/symoneural-control-plane-matrix.md`
  * `docs/ops/APPLICATION-MODEL-CAPABILITY-MATRIX.md`
  * `docs/ops/MODEL-BENCHMARKS.md`
  * `docs/ops/VLLM-BENCH-PARITY.md`

**Everything here is pure parse plus `stat`.** Nothing is imported from the app, no subprocess is
launched, and in particular nothing under `scripts/modelops/` is invoked -- that script rewrites
`ROLLBACK.md` on its refusal path, so a test that shelled out to it would have a filesystem side
effect. Measured 2026-08-23: running `test_modelops.py` does exactly that, by design.

The four assertions worth having are the ones a document cannot satisfy by being well written:

  1. every app module a capability cell names actually exists;
  2. the instance count in prose equals the number of table rows (the "19 vs 20" class of drift);
  3. every benchmark figure appears in BOTH the ledger and its narrative source, so duplication is
     enforced rather than trusted;
  4. a claim contradicted by the disk fails -- specifically the two claims this batch corrected.

Each was verified by sabotage, not by going green: see the commit message.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

MATRIX = DOCS / "specs" / "symoneural-control-plane-matrix.md"
CAPABILITY = DOCS / "ops" / "APPLICATION-MODEL-CAPABILITY-MATRIX.md"
BENCHMARKS = DOCS / "ops" / "MODEL-BENCHMARKS.md"
PARITY = DOCS / "ops" / "VLLM-BENCH-PARITY.md"
BOOTCAMP = DOCS / "specs" / "symoneural-bootcamp.md"
MIGRATION = DOCS / "ops" / "OPENAI-GPT-OSS-MIGRATION.md"

APPS = ROOT / "backend" / "apps"
MODELS = ROOT / "backend" / "models"

#: The whisper runtime both `voice` and `sigils` resolve. Absent on this box, which is the whole
#: point of `test_no_document_claims_asr_is_serving_while_its_runtime_is_absent`.
WHISPER_CLI = ROOT / "contrib" / "whisper.cpp" / "build" / "bin" / "whisper-cli"

#: vLLM lives outside the repo, so no in-repo search can find it -- which is how four documents
#: called it `absent` for three weeks. Detected by directory rather than by import: importing vLLM
#: costs seconds and pulls in torch, and this test only needs to know it is installed.
VLLM_VENV = pathlib.Path.home() / ".venvs" / "vllm"


def read(path):
    return path.read_text(encoding="utf-8")


class DocumentsExist(unittest.TestCase):
    def test_all_four_matrix_documents_are_present(self):
        for path in (MATRIX, CAPABILITY, BENCHMARKS, PARITY):
            with self.subTest(doc=path.name):
                self.assertTrue(path.is_file(), f"{path} is missing")


class CapabilityCellsNameRealThings(unittest.TestCase):
    """A reachability cell that names a module which does not exist is worse than no cell."""

    def test_every_app_module_named_in_the_capability_matrix_exists(self):
        text = read(CAPABILITY)
        # The row labels are `**`name`**`-style backticked module names in the leftmost column.
        named = set(re.findall(r"\*\*`([a-z_]+)`\*\*", text))
        # `api.py` is a file, not a package; every other name must be a directory under apps/.
        named.discard("api.py")
        self.assertTrue(named, "parsed no module names -- the parser broke, not the doc")
        for mod in sorted(named):
            with self.subTest(module=mod):
                self.assertTrue((APPS / mod).is_dir(),
                                f"capability matrix names backend/apps/{mod}, which is not a directory")

    def test_every_source_line_citation_points_at_a_file_that_exists(self):
        """`sigils/render.py:86-89` is a checkable claim. An unresolvable path is a dead citation.

        Requires a `/` in the path on purpose: a bare `asr.py:106` is ambiguous across the tree,
        and this test caught exactly that in the first draft of the capability doc.
        """
        text = read(CAPABILITY)
        cites = set(re.findall(r"`((?:backend/)?[a-z_]+(?:/[a-z_0-9]+)+\.py):[0-9]", text))
        self.assertTrue(cites, "parsed no source citations")
        for cite in sorted(cites):
            with self.subTest(cite=cite):
                candidates = [ROOT / cite, ROOT / "backend" / cite, APPS / cite]
                self.assertTrue(any(c.is_file() for c in candidates),
                                f"citation {cite} resolves to no file on disk")


class CountsMatchTheTables(unittest.TestCase):
    """The "19 vs 20" class of bug: a number in prose that stopped matching the table under it."""

    def test_the_stated_instance_count_equals_the_number_of_matrix_rows(self):
        text = read(MATRIX)
        stated = re.search(r"\*\*(\d+) instances across (\d+) app modules\.?\*\*", text)
        self.assertIsNotNone(stated, "the matrix no longer states its instance count")
        claimed_instances = int(stated.group(1))

        section = text[text.index("## 4. The matrix"):text.index("## 5. What the Runtime")]
        # A data row starts with `| **Name**`; the header and separator do not.
        rows = re.findall(r"^\| \*\*", section, flags=re.M)
        self.assertEqual(claimed_instances, len(rows),
                         f"matrix claims {claimed_instances} instances but the table has {len(rows)} rows")

    def test_the_stated_app_module_count_equals_the_tree(self):
        text = read(MATRIX)
        stated = re.search(r"\*\*(\d+) instances across (\d+) app modules\.?\*\*", text)
        self.assertIsNotNone(stated)
        claimed_modules = int(stated.group(2))
        # Directories, which is how `tools/bootcamp_scout.py` counts and therefore what every
        # document quotes. Measured 2026-08-23: 17 directories, of which only 15 hold an
        # `__init__.py` -- `ravencalc` and `remix` are not importable packages. Counting packages
        # here would silently disagree with the Scout by two, which is the drift this class exists
        # to catch, so the definition is pinned rather than left to taste.
        actual = sorted(p.name for p in APPS.iterdir()
                        if p.is_dir() and p.name != "__pycache__")
        self.assertEqual(claimed_modules, len(actual),
                         f"matrix claims {claimed_modules} app modules; the tree has {len(actual)}: {actual}")


class DepthChartsKeepExactlyThreeOptions(unittest.TestCase):
    """Bootcamp §5 declares "exactly three primary options" per position. Measured 2026-08-23:
    19 positions, all 3. A fourth option is not a richer chart -- it means the format that makes
    positions comparable has been abandoned in one place and nowhere else."""

    def positions(self):
        text = read(BOOTCAMP)
        body = text[text.index("## 5. Depth charts"):text.index("## 6. What this chart")]
        return [s for s in re.split(r"\n### ", body)[1:]]

    def test_every_depth_chart_position_declares_exactly_three_options(self):
        positions = self.positions()
        self.assertGreaterEqual(len(positions), 19, "depth chart positions vanished")
        for section in positions:
            title = section.split("\n")[0].strip()
            with self.subTest(position=title[:48]):
                opts = sorted(set(re.findall(r"\*\*Option (\d)", section)))
                self.assertEqual(["1", "2", "3"], opts,
                                 f"{title[:48]!r} declares options {opts}, not exactly 1/2/3")


class BenchmarkFiguresAgreeWithTheirSource(unittest.TestCase):
    """MODEL-BENCHMARKS.md transcribes figures whose narrative lives in OPENAI-GPT-OSS-MIGRATION.md.

    Duplication across two files is how a figure gets carried forward and re-dated -- the one
    thing this repo says never to do. So the duplication is made safe by being enforced: every
    figure must appear in BOTH files, and editing one without the other goes red.
    """

    #: Rows shared by the ledger's §1 table and the narrative's benchmark table. Compared as
    #: whole rows, NOT as "does this number appear somewhere in the file" -- the first draft of
    #: this test did the latter and a deliberate mutation of the `generation` cell went GREEN,
    #: because `166.3` also occurs in prose two sections later. A substring search over a whole
    #: document cannot tell a table cell from a mention of it.
    ROW_LABELS = ("load", "peak VRAM", "prompt", "generation",
                  "tokens for a one-sentence answer", "wall clock")

    @staticmethod
    def numbers_in(text):
        return re.findall(r"[0-9][0-9,]*\.?[0-9]*", text)

    def row(self, text, label):
        """The numbers on the table row whose first cell is `label`, in order."""
        for line in text.splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip().strip("*") for c in line.strip("|").split("|")]
            if cells and cells[0].strip("*").strip() == label:
                return [self.numbers_in(c) for c in cells[1:]]
        return None

    def test_every_benchmark_row_matches_its_narrative_source_cell_for_cell(self):
        ledger, narrative = read(BENCHMARKS), read(MIGRATION)
        for label in self.ROW_LABELS:
            with self.subTest(row=label):
                a, b = self.row(ledger, label), self.row(narrative, label)
                self.assertIsNotNone(a, f"row {label!r} missing from the benchmark ledger")
                self.assertIsNotNone(b, f"row {label!r} missing from its narrative source")
                self.assertEqual(a, b,
                                 f"row {label!r} disagrees between the ledger and its source: "
                                 f"{a} vs {b}")

    def test_the_probe_and_smoke_figures_appear_in_both_files(self):
        """These live in prose rather than a shared table, so presence is the honest check."""
        for fig in ("14,297", "14,229", "15,409", "164.4", "165.4", "454.0", "12,664", "5,261",
                    "16,303", "239"):
            with self.subTest(figure=fig):
                self.assertIn(fig, read(BENCHMARKS), f"{fig} missing from the ledger")
                self.assertIn(fig, read(MIGRATION), f"{fig} missing from its narrative source")

    def test_each_benchmark_section_attributes_its_figures_to_a_sha(self):
        """A figure with no SHA cannot be checked. This repo has published one that was never true
        of the commit beside it, so the SHA is not decoration.

        Requires the SHA on an explicit `SHA `<hex>`` attribution line rather than anywhere in the
        section: the first draft accepted the section HEADING's copy of the SHA, so deleting the
        attribution line entirely still passed.
        """
        text = read(BENCHMARKS)
        bounds = ("## 1. LLM benchmark", "## 2. Production-argv probes", "## 3. Candidate smoke",
                  "## 4. What is NOT measured")
        for i, heading in enumerate(bounds[:-1]):
            self.assertIn(heading, text, f"{heading} is gone")
            body = text[text.index(heading):text.index(bounds[i + 1])]
            with self.subTest(section=heading):
                self.assertRegex(body, r"\*\*SHA `[0-9a-f]{8}`",
                                 f"{heading} states figures with no `**SHA <hex>`` attribution")


class ClaimsContradictedByTheDiskFail(unittest.TestCase):
    """The two corrections this batch made, locked so they cannot be re-introduced."""

    def test_no_document_calls_vllm_absent_while_it_is_installed(self):
        if not VLLM_VENV.is_dir():
            self.skipTest(f"no vLLM venv at {VLLM_VENV}; nothing to contradict")
        installed = list(VLLM_VENV.glob("lib/*/site-packages/vllm")) or [VLLM_VENV / "vllm"]
        if not any(p.exists() for p in installed):
            self.skipTest("vLLM venv exists but holds no vllm package")

        offenders = []
        for doc in sorted(DOCS.rglob("*.md")):
            for i, line in enumerate(read(doc).splitlines(), 1):
                low = line.lower()
                if "vllm" not in low:
                    continue
                # Blockquote lines are skipped: a dated correction block has to be able to QUOTE
                # the false claim it is retracting, and flagging that quotation would make the
                # repo's own correction style untestable. This test caught its own author doing
                # exactly that, which is why the exemption is narrow -- blockquotes only.
                if line.lstrip().startswith(">"):
                    continue
                # "no service is running" / "candidate only" are TRUE and must stay allowed.
                if re.search(r"\bnot installed\b", low) or re.search(
                        r"vllm[^|\n]{0,80}\|\s*\*\*absent\*\*", low) or re.search(
                        r"maturity:\s*absent", low):
                    offenders.append(f"{doc.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
        self.assertEqual([], offenders,
                         "vLLM is installed and importable; these lines still say otherwise:\n"
                         + "\n".join(offenders))

    def test_no_document_claims_asr_is_serving_while_its_runtime_is_absent(self):
        if WHISPER_CLI.is_file():
            self.skipTest("whisper-cli is present; the ASR claim would be legitimate")
        # Bootcamp only: it owns the depth chart, so it is the file where "proof: serving" would be
        # read as a capability claim. The other documents legitimately QUOTE the retracted wording
        # when explaining the correction, and blockquotes are skipped here for the same reason.
        offenders = []
        for doc in (BOOTCAMP,):
            for i, line in enumerate(read(doc).splitlines(), 1):
                low = line.lower()
                if line.lstrip().startswith(">"):
                    continue
                if ("asr" in low or "whisper" in low) and re.search(
                        r"\*\*proof\*\* serving", low):
                    offenders.append(f"{doc.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
        self.assertEqual([], offenders,
                         f"{WHISPER_CLI} is absent, so ASR cannot be serving:\n" + "\n".join(offenders))

    def test_the_matrix_records_the_asr_runtime_as_absent(self):
        """Not just the absence of a false claim -- the presence of the true one."""
        if WHISPER_CLI.is_file():
            self.skipTest("whisper-cli is present")
        self.assertRegex(read(MATRIX), r"whisper\.cpp\*\* \*\*absent\*\*|`whisper\.cpp` \*\*absent\*\*",
                         "the matrix no longer records the ASR runtime as absent")


class WeightNamesResolve(unittest.TestCase):
    """Skips rather than fails where the weights are not present -- the convention
    `test_weight_names.py` already uses, and necessary because `backend/models` is gitignored and
    is empty in a fresh worktree."""

    #: The persona adapter lives under `training/`, not `backend/models` -- it is protected and
    #: reported separately -- so both roots are searched. Getting this wrong made the first draft
    #: of this test report a missing weight that was simply somewhere else.
    WEIGHT_ROOTS = (MODELS, ROOT / "training")

    def test_every_weight_filename_named_in_the_capability_matrix_exists(self):
        # Count only files with a weight extension. Keying the skip on "is the directory empty"
        # was wrong: in a worktree, `training/` holds tracked JSON and scripts while every actual
        # weight is gitignored and absent -- so the guard never fired and the test failed on a
        # clone that legitimately has no weights.
        suffixes = {".gguf", ".safetensors", ".bin", ".onnx"}
        present = set()
        for root in self.WEIGHT_ROOTS:
            if root.is_dir():
                present |= {p.name for p in root.rglob("*")
                            if p.is_file() and p.suffix in suffixes}
        if not present:
            self.skipTest("no weight files in this clone (backend/models is gitignored)")

        named = set(re.findall(r"`([a-z0-9._-]+\.(?:gguf|safetensors|bin|onnx))`", read(CAPABILITY)))
        # Guard against the assertion going vacuous. The first draft of this test parsed ZERO
        # filenames -- the doc named weights by column header, not by filename -- so it passed
        # without checking anything. A test that cannot fail is worse than no test, because it
        # reports confidence it never earned.
        self.assertGreaterEqual(len(named), 10,
                                f"parsed only {len(named)} weight filenames from the capability "
                                f"matrix; it should name at least 10 in full")
        for name in sorted(named):
            with self.subTest(weight=name):
                self.assertIn(name, present,
                              f"capability matrix names {name}, absent from "
                              f"{[str(r) for r in self.WEIGHT_ROOTS]}")


class ForbiddenModeStaysForbidden(unittest.TestCase):
    def test_off_the_record_is_listed_and_forbidden_not_available(self):
        """Requested as one mode among ten. Bootcamp §4a forbids it, so the matrix lists it as
        FORBIDDEN -- present in the table so its absence cannot read as an oversight."""
        text = read(MATRIX)
        self.assertIn("off-the-record", text, "the forbidden mode is not even listed")
        row = [ln for ln in text.splitlines() if "off-the-record" in ln and ln.startswith("|")]
        self.assertTrue(row, "off-the-record is mentioned but not in the modes table")
        self.assertRegex(" ".join(row), r"FORBIDDEN",
                         "off-the-record must be marked FORBIDDEN, not offered as available")


class CaveatsAreCarriedForward(unittest.TestCase):
    def test_every_new_document_carries_the_unaudited_commit_caveat(self):
        """The 404-commit gap is the standing caveat on every reading in this batch. A document
        that quietly drops it is claiming more confidence than the audit supports."""
        for doc in (MATRIX, CAPABILITY, BENCHMARKS, PARITY):
            with self.subTest(doc=doc.name):
                self.assertIn("404 commits", read(doc),
                              f"{doc.name} dropped the unaudited-range caveat")

    def test_every_new_document_states_the_commit_it_was_read_at(self):
        for doc in (MATRIX, CAPABILITY, BENCHMARKS, PARITY):
            with self.subTest(doc=doc.name):
                self.assertIn("507e09ee", read(doc), f"{doc.name} states no read-at commit")


if __name__ == "__main__":
    unittest.main()
