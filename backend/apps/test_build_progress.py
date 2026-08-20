"""tools/build_progress.py, held to its two promises: deterministic, and driven by the rows.

The page is Garrett's bookmark (run/progress.html); its regression contract from the spec:
  * byte-identical output on an unchanged tree — idempotence, EXCLUDING the one marked
    generated-at line, the only clock read in the whole script;
  * every task number in PROJECT-TASKS.md renders — and the mutation form of that claim:
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
INTAKE_GENERATOR = ROOT / "tools" / "build_intake.py"
TASK_ROW = re.compile(r"^([◼◻▶]) ((?:\(unnumbered[^)]*\))|#\d+) — (.+)$", re.M)
SOURCES = ("PROJECT-TASKS.md", "GARRETT-REQUESTS.md", "AUDIT-SURFACE-2026-08-19.md",
           "GARRETT-INBOX.md")


def run_generator(root: Path, out: Path) -> str:
    r = subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(root), "--out", str(out)],
        capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(f"generator failed rc={r.returncode}\n{r.stderr}")
    return out.read_text()


def run_intake(root: Path) -> None:
    """Build INTAKE.md in a temp root.

    The ledger no longer reaches the page directly: it is one of three sources merged into
    INTAKE.md, which is what build_progress.py renders. So a test about how a ledger entry
    appears has to run BOTH generators, in the order the systemd unit runs them. Asserting on
    build_progress.py alone would be asserting on a stage the data no longer passes through.
    """
    r = subprocess.run([sys.executable, str(INTAKE_GENERATOR), "--root", str(root)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(f"build_intake failed rc={r.returncode}\n{r.stderr}")


def strip_generated_line(html: str) -> str:
    return "\n".join(l for l in html.splitlines() if 'id="generated-at"' not in l)


def copy_tree(dst: Path, skip: str | tuple[str, ...] | None = None):
    skipped = (skip,) if isinstance(skip, str) else (skip or ())
    for name in SOURCES:
        src = ROOT / name
        if src.exists() and name not in skipped:
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
        ids = [m.group(2) for m in TASK_ROW.finditer((ROOT / "PROJECT-TASKS.md").read_text())]
        self.assertGreaterEqual(len(ids), 20, "task-row extraction went blind")
        with tempfile.TemporaryDirectory() as td:
            page = run_generator(ROOT, Path(td) / "p.html")
        for tid in ids:
            self.assertIn(f">{tid}<", page.replace("&#x27;", "'"),
                          f"task {tid} is in PROJECT-TASKS.md but not on the page")
        # The two sections the page is, and the ONLY two. Each name that used to be here --
        # "Phase tracker", "Request ledger", "Audit surface", "Suites" -- was a separate panel
        # listing work in its own vocabulary, and every one of them was removed on Garrett's
        # instruction: "i dont need a bullshit list at the top and a full list at the bottom i
        # just need the full list in one location". Asserting they are ABSENT is the same
        # contract inverted, and it is the one that stops them growing back.
        for anchor in ("Tasks — PROJECT-TASKS.md", "Assignments — INTAKE.md"):
            self.assertIn(anchor, page)
        for gone in ("Phase tracker", "Request ledger", "Audit surface"):
            self.assertNotIn(gone, page,
                             f"the {gone!r} panel is back — one list, in one location")
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
            tasks = root / "PROJECT-TASKS.md"
            kept = [l for l in tasks.read_text().splitlines()
                    if not l.startswith("◻ #24 — ")]
            self.assertNotIn("#24", "\n".join(l for l in kept if TASK_ROW.match(l)),
                             "the #24 row survived the deletion; fixture is wrong")
            tasks.write_text("\n".join(kept) + "\n")
            page = run_generator(root, root / "p.html")
        self.assertNotIn(">#24<", page, "a deleted row still renders — the table is static")
        self.assertIn(">#23<", page, "the control row vanished with it — over-deletion")

    def test_missing_ledger_and_missing_git_degrade_to_labels(self):
        """The worst day still renders. Missing sources are a label, never a traceback."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip="GARRETT-REQUESTS.md")
            run_intake(root)
            page = run_generator(root, root / "p.html")
        self.assertIn("no-git", page, "a temp root is not a repo; the header must say so")
        self.assertIn("Assignments — INTAKE.md", page,
                      "the section vanished with its ledger; it has two other sources")
        self.assertNotIn(">A-R", page,
                         "request assignments rendered from a ledger that is not there")

    def test_no_intake_file_says_so_rather_than_rendering_an_empty_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root)
            page = run_generator(root, root / "p.html")   # deliberately no run_intake
        self.assertIn("INTAKE.md not present", page)
        self.assertIn("build_intake.py", page, "the note must name the command that fixes it")


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


#: The real audit surface is skipped in every ledger fixture below. INTAKE.md merges three
#: sources, so leaving it in makes the barrier count 13 audit findings plus whatever the
#: ledger contributes — and an assertion about ledger behaviour that moves whenever somebody
#: edits an unrelated file is an assertion that will be deleted rather than fixed.
LEDGER_FIXTURE_SKIP = ("GARRETT-REQUESTS.md", "AUDIT-SURFACE-2026-08-19.md")


def render_ledger(td: str, held_status: str) -> str:
    root = Path(td)
    copy_tree(root, skip=LEDGER_FIXTURE_SKIP)
    (root / "GARRETT-REQUESTS.md").write_text(LEDGER.format(held=held_status))
    run_intake(root)
    return run_generator(root, root / "p.html")


def barrier_count(page: str) -> int:
    m = re.search(r"<strong>(\d+)</strong> barriers", page)
    if not m:
        raise AssertionError("the page states no barrier count")
    return int(m.group(1))


def row_of(page: str, aid: str) -> str:
    m = re.search(rf'<tr[^>]*id="row-{re.escape(aid)}">(.*?)</tr>', page, re.S)
    return m.group(1) if m else ""


class EveryLedgerEntryIsDoneOrTaskOrIntake(unittest.TestCase):
    """Garrett, 2026-08-20: *"they are either done, task or intake"* — a completeness claim.

    Every entry in the ledger is in exactly one of three states and none is in none of them.
    That is stronger than it sounds, and it is what this class exists to hold: the rule it
    replaced named four "open" statuses and exempted two others from needing a task, and
    between them those two defensible-looking rules left 19 entries in no state at all —
    not finished, not carried by any task, and not on the intake list either.

    This class was `HeldEntriesRenderAsFrozenAndNeverAsDone`, asserting on a `[FROZEN]` marker
    and `Un-actioned (N)` counts in a ledger panel. The panel went when the three intake panels
    became one Assignments table; the marker went when Garrett rejected the state behind it —
    *"i never gave you instruction of 'frozen' items"*. He had defined two actions, tick and
    delete, and a page state that accepts neither takes the decision off him.
    """

    def test_a_held_entry_is_an_ordinary_assignment(self):
        with tempfile.TemporaryDirectory() as td:
            page = render_ledger(td, "held(2026-08-20, awaiting re-scope)")
        row = row_of(page, "A-R1")
        self.assertTrue(row, "the held entry is in no state at all — the gap is back")
        self.assertIn("<button", row,
                      "a held entry carries no control, so it can be neither ticked nor "
                      "dropped; that is the invented third state, back again")
        self.assertNotIn("FROZEN", page, "the rejected state name is back on the page")

    def test_adopted_and_superseded_split_correctly(self):
        """`adopted` with no pointer is intake — the word claims the rule landed somewhere and
        does not say where, which is an assertion nobody can check. `superseded` is done: the
        work did not vanish, it moved to the entry that replaced it.
        """
        with tempfile.TemporaryDirectory() as td:
            page = render_ledger(td, "held(2026-08-20, awaiting re-scope)")
        self.assertTrue(row_of(page, "A-R4"),
                        "a bare `adopted` closed the entry — that is the word being trusted "
                        "instead of checked, and it is how 15 entries went missing")
        self.assertEqual(row_of(page, "A-R3"), "",
                         "a superseded entry is closed — its successor holds the work")
        self.assertEqual(row_of(page, "A-R5"), "", "a done entry is not an assignment")

    def test_an_adopted_rule_closes_once_it_names_where_it_lives(self):
        """The mutation that separates the pointer rule from a bucket rule.

        Only R-4's status changes, and only by gaining a path. If the entry still renders as an
        assignment the pointer is being ignored; if the bare form in the test above ALSO closed,
        the bucket is doing the work and the pointer is decoration.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip=LEDGER_FIXTURE_SKIP)
            (root / "GARRETT-REQUESTS.md").write_text(
                LEDGER.format(held="done(deadbee)").replace(
                    "status: adopted",
                    "status: adopted — recorded in .claude/CLAUDE.md"))
            run_intake(root)
            page = run_generator(root, root / "p.html")
        self.assertEqual(row_of(page, "A-R4"), "",
                         "an adopted rule that names the file it lives in is a checkable "
                         "fact about the repo, not an open decision")
        self.assertEqual(barrier_count(page), 1,
                         "R-2 is the only barrier left once the adopted rule is recorded")

    def test_a_pointer_at_the_very_end_of_the_status_line_still_counts(self):
        """The concatenation bug, pinned by position rather than by content.

        `status` and `body` were joined with a bare `+`, so the last word of the status ran
        into the first word of the body with no separator. `RULE_POINTER` ends in `\\b`, so a
        filename sitting at the end of the status line — the most natural place to write one —
        was the one place it could not be seen. R-111 read `recorded durably in GUARDRAILS.md`
        and rendered as intake anyway. The fixture puts the path last on purpose; move it into
        the middle of the sentence and this test stops testing anything.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip=LEDGER_FIXTURE_SKIP)
            (root / "GARRETT-REQUESTS.md").write_text(
                LEDGER.format(held="done(deadbee)").replace(
                    "## R-4 — an adopted one\nstatus: adopted\n",
                    "## R-4 — an adopted one\n"
                    "status: adopted — recorded in GUARDRAILS.md\n"
                    "trailing body text that follows the status line\n"))
            run_intake(root)
            page = run_generator(root, root / "p.html")
        self.assertEqual(row_of(page, "A-R4"), "",
                         "the pointer was at the end of the status line, which is where the "
                         "bare `+` hid it")

    def test_the_three_states_are_exhaustive(self):
        """The completeness claim itself, asserted against the parser rather than the page."""
        sys.path.insert(0, str(ROOT / "tools"))
        from build_progress import parse_requests
        entries = parse_requests((ROOT / "GARRETT-REQUESTS.md").read_text())
        self.assertGreater(len(entries), 100, "ledger parse went blind")
        for e in entries:
            self.assertIn(e["state"], ("done", "task", "intake"),
                          f"{e['id']} is in no state: status {e['status']!r}")
        counted = sum(len([e for e in entries if e["state"] == s])
                      for s in ("done", "task", "intake"))
        self.assertEqual(counted, len(entries), "an entry is in two states at once")

    def test_an_entry_that_names_a_task_is_not_also_an_assignment(self):
        """The anti-duplication rule: carried work lives on the task list, once."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            copy_tree(root, skip=LEDGER_FIXTURE_SKIP)
            (root / "GARRETT-REQUESTS.md").write_text(
                LEDGER.format(held="captured — carried by #41"))
            run_intake(root)
            page = run_generator(root, root / "p.html")
        self.assertEqual(row_of(page, "A-R1"), "",
                         "an entry naming #41 is on the task list; listing it here too is "
                         "the duplicate-listing failure the one-list rule exists to end")

    def test_a_dropped_assignment_stays_visible_and_stops_counting(self):
        """Garrett's delete. `[-]` is a decision, and a decision that leaves no trace on the
        page is indistinguishable from an item that was never recorded."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # The audit surface has to go too, or its thirteen findings arrive as barriers and
            # the count this test reads is measuring the real repo instead of the fixture.
            copy_tree(root, skip=LEDGER_FIXTURE_SKIP)
            (root / "GARRETT-REQUESTS.md").write_text(
                LEDGER.format(held="done(deadbee)"))
            run_intake(root)
            intake = root / "INTAKE.md"
            before = barrier_count(run_generator(root, root / "a.html"))
            intake.write_text(intake.read_text().replace(
                "## A-R2 [request] — a captured one\n[ ]",
                "## A-R2 [request] — a captured one\n[-]"))
            run_intake(root)                     # the drop must survive regeneration
            page = run_generator(root, root / "b.html")
        # Two, not one: R-2 is captured, and R-4's bare `adopted` names no file, so it is
        # intake as well. Both are barriers; the drop below is applied to R-2 only.
        self.assertEqual(before, 2, "fixture: R-2 and R-4 are the barriers before the drop")
        self.assertEqual(barrier_count(page), 1,
                         "dropping R-2 must take exactly one off the count — R-4 is untouched "
                         "and must stay on it, or delete is removing more than it was aimed at")
        self.assertIn(">DROPPED<", row_of(page, "A-R2"),
                      "the dropped entry left no trace — that is deletion, not a decision")

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
