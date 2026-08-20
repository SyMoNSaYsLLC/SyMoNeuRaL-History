"""The rack count in `api.py:build_status()`, asserted instead of described.

The 2026-08-19 closeout review found the comment above that list claiming TWELVE units in the
same change that took it from eleven to thirteen. Nothing caught it: `tests/frontend.mjs`
asserts `units.length >= 5` and an invariant about duplicate pages, on purpose, so the count
existed only in prose -- which is exactly the kind of number that drifts.

`api.py` is **read as source, never imported**, the same discipline as
`apps/test_studio_models.py`: importing the serving module builds every rate limiter, resolves
the GPU governor and mounts `site/`.

This is a tripwire, not a design constraint. A thirteenth surface is welcome; typing the new
number here is the point, the way `test_the_router_count_is_unchanged` works for routers.

**Green here is not proof the rack is live, and cannot be.** Everything below compares the
number, the names and the comment *with each other*, inside one file on disk. All three can agree
and all three be undeployed: `build_status()` is code, so a new row reaches `/api/status` only
after `sudo systemctl restart symoneural-api`. That gap was real on 2026-08-19 -- `api.py` gained
`studio` and `exp` at 08:37 UTC and the endpoint kept answering eleven until the restart, while
`HANDOVER.md` published thirteen. The live check is `curl -s http://127.0.0.1:8800/api/status`
and nothing in this file substitutes for it.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
API_PY = BACKEND / "api.py"
SOURCE = API_PY.read_text()
TREE = ast.parse(SOURCE)

#: The rows, in the order `build_status()` builds them. Read from `/api/status` on the running
#: API for the live truth; this is the source's own order and is what the comment must match.
EXPECTED = ["chat", "image", "remix", "ravencalc", "train", "miner", "streamer", "coder",
            "gateway", "project", "sigils", "studio", "exp"]


#: There is deliberately NO module->row map here any more. There used to be one, holding a
#: single entry, `{"streamer": "tuner"}`: `apps/tuner` and `apps/guide` had been merged into
#: `apps/streamer` (Garrett: "you need to migrate tuner and guide to be 1") while the merged
#: package went on publishing `id="tuner"`, on the reasoning that the id reaches
#: `site/console.js` and the page, so renaming the row would be a visitor-facing change made
#: for an internal reason.
#:
#: That reasoning was overtaken by the instruction, not refuted by it: Garrett then said "i
#: said tuner and guide needed to be merged and migrated to streamer" -- the migration is the
#: namespace and the visitor-facing surfaces, not just the Python package. So the row is
#: `streamer`, the page is `site/streamer.html`, and module name and row id agree again. A map
#: that exists to preserve a retired name is a place for the next one to hide, which is why it
#: is deleted rather than emptied. Read the id from `apps/streamer/routes.py::status()`.


def _build_status() -> ast.FunctionDef:
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "build_status":
            return node
    raise AssertionError(f"{API_PY} no longer defines build_status()")


def _unit_calls() -> list:
    return [n for n in ast.walk(_build_status())
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "Unit"]


def _row_id(call: ast.Call) -> str:
    """The row a `Unit(...)` call builds, from the source alone.

    Three forms appear in `build_status()`, and all three have to be read here or the assertion
    silently covers only some of the rack:

        Unit(id="chat", ...)                        a literal
        Unit(**project.status())                    the app package's own row
        Unit(**{**tuner.status(), "bus": "net"})    the same, with one field overridden
    """
    for kw in call.keywords:
        if kw.arg == "id" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    for kw in call.keywords:
        if kw.arg is not None:
            continue
        value = kw.value
        if isinstance(value, ast.Dict):
            # `{**tuner.status(), "bus": "net"}` -- the merged-in call is the row.
            calls = [v for k, v in zip(value.keys, value.values)
                     if k is None and isinstance(v, ast.Call)]
            value = calls[0] if calls else value
        if isinstance(value, ast.Call):
            func = value.func
            while isinstance(func, ast.Attribute):
                func = func.value          # `sigils.status` -> `sigils`
            if isinstance(func, ast.Name):
                return func.id
    raise AssertionError(f"cannot tell which row line {call.lineno} builds")


class RackCountTests(unittest.TestCase):
    def test_the_rack_is_thirteen_units(self):
        self.assertEqual(len(_unit_calls()), len(EXPECTED))

    def test_the_comment_above_the_list_says_the_same_number(self):
        """The defect that was actually shipped: the code and its own comment disagreeing.

        Matched as a word, because that is how the comment is written -- "THIRTEEN units" -- and
        because a digit would let `13` in an unrelated line pass for the claim.
        """
        words = {11: "ELEVEN", 12: "TWELVE", 13: "THIRTEEN", 14: "FOURTEEN", 15: "FIFTEEN"}
        count = len(_unit_calls())
        said = [word for number, word in words.items()
                if f"{word} units" in SOURCE or f"{word.title()} units" in SOURCE]
        self.assertEqual(said, [words[count]],
                         f"build_status() builds {count} units; the comment says {said}")

    def test_every_row_the_comment_names_is_a_row_that_is_built(self):
        """The names, not only the number. A row can be swapped without the count moving."""
        self.assertEqual([_row_id(call) for call in _unit_calls()], EXPECTED)


class EmittedIdMatchesTheModuleTests(unittest.TestCase):
    """The gap the deleted `ROW_OF_MODULE` was hiding.

    Everything in `RackCountTests` reads `api.py` as *source* and infers each row from the
    **module name** in the `Unit(...)` call. That says nothing about the `id` the module
    actually puts on the wire. Proven, not assumed: with `status()` returning `id="tuner"`
    and this file expecting `streamer`, `RackCountTests` was still 3 passed -- because the
    AST sees `streamer.status()` either way. The map made that agreement look checked.

    So this is the assertion that was missing. It imports the package, which is cheap and
    allowed -- the no-import discipline in this file's docstring is about `api.py`, whose
    import builds rate limiters and mounts `site/`, not about a surface module.
    """

    def test_the_streamer_publishes_the_row_id_its_module_name_implies(self):
        from apps import streamer
        row = streamer.status()
        self.assertEqual(row["id"], "streamer",
                         "the module is apps/streamer, so the row id must be `streamer`; "
                         "a mismatch here is what ROW_OF_MODULE used to paper over")
        self.assertIn("streamer", EXPECTED)

    def test_the_row_href_points_at_the_page_that_exists(self):
        """A row whose href 404s is a dead link on the front page of a live site.

        This is the half of the migration that a namespace rename forgets: the id moved,
        the page was regenerated under a new name, and the href has to move with both.
        """
        from apps import streamer
        href = streamer.status()["href"]
        self.assertEqual(href, "/streamer.html")
        page = pathlib.Path(__file__).resolve().parents[2] / "site" / href.lstrip("/")
        self.assertTrue(page.is_file(), f"the rack links to {href}, which is not in site/")


if __name__ == "__main__":
    unittest.main()
