"""tools/build_progress.py, held to its two promises: deterministic, and driven by the rows.

The page is Garrett's bookmark (run/progress.html); its regression contract from the spec:
  * byte-identical output on an unchanged tree — idempotence, EXCLUDING the one marked
    generated-at line, the only clock read in the whole script;
  * every task number in CODER-TASKS.md renders — and the mutation form of that claim:
    delete a row from a temp copy of the tree and the number disappears from the output,
    proving the table derives from the parsed rows and not from anything static.

The generator is run via subprocess (never imported): it is a tool, not a module of the
serving path, and --root/--out exist precisely so tests can point it at temp trees without
touching the real run/progress.html. Temp roots are not git repositories, which also
exercises the "no-git" header arm the spec demands for fresh clones.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools" / "build_progress.py"
TASK_ROW = re.compile(r"^([◼◻▶]) ((?:\(unnumbered[^)]*\))|#\d+) — (.+)$", re.M)
SOURCES = ("CODER-TASKS.md", "GARRETT-REQUESTS.md", "AUDIT-SURFACE-2026-08-19.md",
           "GARRETT-INBOX.md")


def run_generator(root: Path, out: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(root), "--out", str(out)],
        capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(f"generator failed rc={r.returncode}\n{r.stderr}")
    return out.read_text()


def strip_generated_line(html: str) -> str:
    return "\n".join(l for l in html.splitlines() if 'id="generated-at"' not in l)


def copy_tree(dst: Path, skip: str | None = None):
    for name in SOURCES:
        src = ROOT / name
        if src.exists() and name != skip:
            shutil.copy(src, dst / name)


class DeterministicOnAnUnchangedTree(unittest.TestCase):

    def test_two_runs_differ_only_on_the_generated_at_line(self):
        with tempfile.TemporaryDirectory() as td:
            a = run_generator(ROOT, Path(td) / "a.html")
            b = run_generator(ROOT, Path(td) / "b.html")
        self.assertIn('id="generated-at"', a, "the marked clock line is the contract")
        self.assertEqual(strip_generated_line(a), strip_generated_line(b),
                         "output varies on an unchanged tree beyond the generated-at line")


class TheRowsDriveTheRender(unittest.TestCase):

    def test_every_task_number_in_the_canonical_list_renders(self):
        ids = [m.group(2) for m in TASK_ROW.finditer((ROOT / "CODER-TASKS.md").read_text())]
        self.assertGreaterEqual(len(ids), 20, "task-row extraction went blind")
        with tempfile.TemporaryDirectory() as td:
            page = run_generator(ROOT, Path(td) / "p.html")
        for tid in ids:
            self.assertIn(f">{tid}<", page.replace("&#x27;", "'"),
                          f"task {tid} is in CODER-TASKS.md but not on the page")
        for anchor in ("Phase tracker", "Request ledger", "Audit surface", "Suites"):
            self.assertIn(anchor, page)
        self.assertIn('http-equiv="refresh"', page)

    def test_deleting_a_row_from_a_temp_copy_deletes_it_from_the_page(self):
        """The mutation check: #24's row removed from a copied tree → #24 gone, #23 stays.

        This is what proves the table is parsed, not pasted: a generator that embedded a
        stale snapshot of the task list would keep rendering #24 and go green above while
        lying here.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root)
            tasks = root / "CODER-TASKS.md"
            kept = [l for l in tasks.read_text().splitlines()
                    if not l.startswith("◻ #24 — ")]
            self.assertNotIn("#24", "\n".join(l for l in kept if TASK_ROW.match(l)),
                             "the #24 row survived the deletion; fixture is wrong")
            tasks.write_text("\n".join(kept) + "\n")
            page = run_generator(root, root / "p.html")
        self.assertNotIn(">#24<", page, "a deleted row still renders — the table is static")
        self.assertIn(">#23<", page, "the control row vanished with it — over-deletion")

    def test_missing_ledger_and_missing_git_degrade_to_labels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip="GARRETT-REQUESTS.md")
            page = run_generator(root, root / "p.html")
        self.assertIn("GARRETT-REQUESTS.md not present yet", page)
        self.assertIn("no-git", page, "a temp root is not a repo; the header must say so")


LEDGER = """# GARRETT-REQUESTS.md

## R-1 — a held one
status: {held}

## R-2 — a captured one
status: captured — ordinary open work

## R-3 — a superseded one
status: superseded(the ground moved under it)

## R-4 — an adopted one
status: adopted

## R-5 — a done one
status: done(abc1234)
"""


def run_raw(root: Path, out: Path):
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(root), "--out", str(out)],
        capture_output=True, text=True, timeout=60)


def render_ledger(td: str, held_status: str) -> str:
    root = Path(td)
    copy_tree(root, skip="GARRETT-REQUESTS.md")
    (root / "GARRETT-REQUESTS.md").write_text(LEDGER.format(held=held_status))
    return run_generator(root, root / "p.html")


class HeldEntriesRenderAsFrozenAndNeverAsDone(unittest.TestCase):
    """The status vocabulary and this parser are one contract, and the page is the claim.

    Garrett froze R-11, R-52 and R-98 on 2026-08-20. Before this, `parse_requests` matched a
    fixed five-token prefix list and fell through to `captured` for anything else, so a `held`
    entry rendered as ordinary un-actioned work: the page would have offered up, as available,
    the three items he had just said not to touch. The pair below is the mutation check — the
    FROZEN marker has to follow the status and nothing else.
    """

    def test_a_held_entry_renders_frozen_and_counts_as_outstanding(self):
        with tempfile.TemporaryDirectory() as td:
            page = render_ledger(td, "held(2026-08-20, awaiting re-scope)")
        self.assertIn("[FROZEN]", page, "a held entry rendered with no frozen marker")
        self.assertIn("R-1", page, "the held entry vanished from the page entirely")
        self.assertIn("held", page)
        self.assertRegex(page, r"Un-actioned \(2\)",
                         "held + captured are the two outstanding entries; superseded, "
                         "adopted and done must not be counted as open")

    def test_the_same_entry_marked_done_loses_the_marker(self):
        """The mutation: only the status line changes, and FROZEN must disappear with it."""
        with tempfile.TemporaryDirectory() as td:
            page = render_ledger(td, "done(deadbee)")
        self.assertNotIn("[FROZEN]", page,
                         "FROZEN survived the status changing to done — the marker is not "
                         "derived from the status")
        self.assertRegex(page, r"Un-actioned \(1\)")

    def test_superseded_and_adopted_are_not_offered_as_open_work(self):
        with tempfile.TemporaryDirectory() as td:
            page = render_ledger(td, "held(2026-08-20, awaiting re-scope)")
        opened = page.split("Un-actioned", 1)[1].split("</ul>", 1)[0]
        self.assertNotIn("R-3", opened, "a superseded entry is closed, not un-actioned")
        self.assertNotIn("R-4", opened, "an adopted entry is a standing rule, not work")
        for bucket in ("superseded", "adopted"):
            self.assertIn(bucket, page, f"{bucket} vanished from the summary counts")

    def test_an_unknown_status_fails_the_build_instead_of_rendering(self):
        """The silent fallback this replaces is exactly how a frozen item read as available."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip="GARRETT-REQUESTS.md")
            (root / "GARRETT-REQUESTS.md").write_text(
                LEDGER.format(held="marinating — a status nobody declared"))
            r = run_raw(root, root / "p.html")
        self.assertNotEqual(r.returncode, 0, "an undeclared status rendered anyway")
        self.assertIn("STATUS_BUCKETS", r.stderr, "the failure must name the fix")


if __name__ == "__main__":
    unittest.main()
