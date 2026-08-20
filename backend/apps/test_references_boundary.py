"""`references/` is read by people, never by code. This is that rule stated as a test.

Garrett's instruction is verbatim: *"we cannot use code in references its for reference only
we must rebrand if we want to use it"*, and task #74's acceptance test is *"nothing under
`references/` is imported, built or linked"*. A rule written in a document is a rule until
somebody forgets it; the reason this is a test is that the repo had already broken it in
eleven places without anybody noticing.

**What went wrong, and why grepping for `references/` is not the check.** Nine suites
imported Playwright from `contrib/llama.cpp/tools/ui/node_modules/playwright` and three more
call sites read `contrib/whisper.cpp/samples/jfk.wav`. Both paths moved under `references/`
in the restructure, so every one of them was *already broken* -- eight browser suites could
not start at all, and four published figures with commit SHAs beside them had quietly become
unreproducible. The tempting fix was to add the `references/` prefix, which would have made
them run and broken the rule. So the check below looks for **both** spellings: a bare
`contrib/` path (stale, and a repointing waiting to happen) and a `references/` one (the
rule, broken outright).

Kept deliberately narrow. It reads source text and asserts on paths, so it cannot tell a
real import from the word appearing in a sentence -- which is why prose mentions are allowed
through by requiring a path separator and a quote-ish context, and why the exemptions below
are listed one by one rather than pattern-matched. A check that fires on its own explanatory
comment is a check people delete.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Where code lives. `references/` itself is excluded -- it is allowed to refer to itself.
SEARCH_DIRS = ("tests", "backend", "tools", "scripts", "engines", "ops")
SUFFIXES = (".py", ".mjs", ".js", ".sh", ".cmake", ".txt", ".json")

#: Skipped wholesale: installed trees and generated output are not ours to police here.
SKIP_PARTS = {"node_modules", ".venv", "build", "__pycache__", "dist", ".git"}

#: Files allowed to name these paths, each with the reason. Documentation of a deleted path
#: is how the next reader learns why it is deleted, so the files that explain the boundary
#: are the ones that must be able to spell it.
ALLOWED = {
    "backend/apps/test_references_boundary.py": "this file states the rule",
    "tests/browser.mjs": "explains the path it replaced",
    "tests/fixtures/README.md": "explains the fixture it replaced",
    # Exempted with the reason stated, not by weakening the pattern above. This script reads
    # Bitmain's own firmware archives out of `references/Projects_Crypto/` -- vendor blobs
    # that are the *subject* of the emulation, not a library it links, and the one thing in
    # the tree that genuinely cannot be recreated, the same argument that exempts NVIDIA's
    # sources. It is still the wrong home for an input a script reads at runtime, so where
    # those archives should live is recorded as a question for Garrett rather than answered
    # here. Narrow on purpose: this names one file, so the next offender still fails.
    "scripts/qemu-antminer.sh": "reads vendor firmware archives; relocation is an open question",
}

#: A path into a third-party working tree, in either spelling. `\b` on the left so that
#: `our-contrib/` and `symoneural_references/` do not match.
BAD = re.compile(r"""\b(?:references/[A-Za-z0-9._-]+/|contrib/(?:llama\.cpp|whisper\.cpp|cuda-samples|stable-diffusion\.cpp)/)""")


def _candidates() -> list[pathlib.Path]:
    out = []
    for d in SEARCH_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SUFFIXES:
                continue
            if SKIP_PARTS & set(p.parts):
                continue
            out.append(p)
    return out


class ReferencesAreNotOnAnyCodePath(unittest.TestCase):
    def test_no_source_file_names_a_third_party_working_tree(self):
        offenders = []
        for p in _candidates():
            rel = p.relative_to(ROOT).as_posix()
            if rel in ALLOWED:
                continue
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                m = BAD.search(line)
                if not m:
                    continue
                # A comment is prose, and prose about a removed path is the point of a
                # comment. Only flag it when it is being used: quoted, or after an import.
                stripped = line.lstrip()
                if stripped.startswith(("#", "//", "*", "#:")):
                    continue
                if not re.search(r"""['"]""", line):
                    continue
                offenders.append(f"{rel}:{n}: {stripped[:110]}")
        self.assertEqual(
            offenders, [],
            "code names a path under references/ (or the pre-restructure contrib/ spelling "
            "of one). Both are wrong and for different reasons: the bare contrib/ form no "
            "longer exists, and adding the references/ prefix to make it resolve breaks the "
            "rule that nothing under references/ is imported, built or linked. Put what you "
            "need in our own tree.\n  " + "\n  ".join(offenders))

    def test_the_check_can_actually_fail(self):
        # A pattern that matches nothing passes this suite forever. Prove it bites.
        self.assertTrue(BAD.search("from '../references/playwright/index.mjs'"))
        self.assertTrue(BAD.search("join(REPO, 'contrib/llama.cpp/tools/ui/node_modules')"))
        self.assertIsNone(BAD.search("our-contrib/thing/x"))
        self.assertIsNone(BAD.search("backend/apps/studio/plugins/reinforce"))


if __name__ == "__main__":
    unittest.main()
