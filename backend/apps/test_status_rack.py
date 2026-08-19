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
EXPECTED = ["chat", "image", "remix", "ravencalc", "train", "miner", "tuner", "coder",
            "gateway", "project", "sigils", "studio", "exp"]


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


if __name__ == "__main__":
    unittest.main()
