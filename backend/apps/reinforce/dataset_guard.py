"""SyMoNeuRaL Reinforce -- dataset admission, and the trade-secret guard.

## Read this before changing anything in this file

`.claude/CLAUDE.md` names two artefacts on this box that are protected **only** by not being
public, and trade secret -- unlike copyright -- exists only while reasonable measures are
taken to keep it that way. Once it is out it cannot be pulled back:

* `training/corpus.jsonl` -- the hand-authored examples that are the company voice, what the
  model may claim, and what it must refuse to invent.
* `training/build_dataset.py` -- the method that produces it.

A training bay is **the single most likely surface in this repo to leak them**, and it will
not be by malice. It will be because the obvious implementation of a dataset picker is to
glob the sibling directory for `.jsonl` files, and that one line publishes the recipe. It
could equally be a validation error that quotes the offending line back, or a job log that
echoes a training example, or an upload directory that `deploy.sh` happens to copy.

So this module is written as a set of refusals rather than a set of features:

1. **Nothing is ever enumerated from `training/`.** There is no scan of that directory
   anywhere in this package. `registry.catalogue()` enumerates weights and carries the same
   warning at its own enumeration site.
2. **`DENIED` below is checked by resolved path**, so a symlink, a `..` traversal or a
   relative spelling all land on the same refusal. It is checked *first*, before the file is
   opened, before its size is read, before it is known to exist.
3. **No route returns dataset contents, and neither does any error.** A validation failure
   reports a line *number* and a *reason*. It never reports the line. `_reject()` exists to
   make that hard to get wrong: it takes a reason code, not a message built from data.
4. **Admitted datasets are staged under `run/reinforce/datasets/`.** `run/` is gitignored and
   `scripts/deploy.sh` publishes `site/` only, so nothing here can reach the webroot. Renders
   already taught this repo that lesson the expensive way -- 19 unreferenced PNGs sat in the
   public webroot because they were written into `site/`. A corpus there would be worse by
   orders of magnitude.
5. **The default is nothing.** There is no "use the SyMoNeuRaL corpus" option in any UI
   reachable from the web, not as a default, not as an example, not greyed out. A run with no
   dataset named is refused; it does not fall back.

The reconciliation with the site's transparency argument is the repo's own line: **publish
the numbers, keep the methods.** Peak VRAM, epoch time, the preset table and the parameter
arithmetic are all publishable and give nothing away. The corpus is the product.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

from .registry import ROOT

# Where admitted datasets live. Under run/, which `.gitignore` already excludes wholesale and
# which `scripts/deploy.sh` never reads -- deploy publishes site/ only.
STAGE = ROOT / "run" / "reinforce" / "datasets"

# The two paths that must never be read, listed, counted, previewed or served by anything in
# this package. Resolved once at import so the comparison is against a real inode path and not
# against a string an operator can spell differently.
DENIED = (
    (ROOT / "training" / "corpus.jsonl").resolve(),
    (ROOT / "training" / "build_dataset.py").resolve(),
)
# The adapter directory is output, not input, and it also carries the tokeniser and the
# trained weights. Refusing the whole directory is cheaper than reasoning about which file
# inside it is safe.
DENIED_TREES = ((ROOT / "training" / "adapter").resolve(),)

MAX_BYTES = 256 * 1024 * 1024      # structural cap: an unbounded read is a memory bug
MAX_ROWS = 200_000


class Refused(Exception):
    """A dataset was refused.

    Carries a stable `code` and a message written by us. It never carries a line of file
    content, and it never carries the *reason a specific line was bad* beyond a category --
    because "line 41 said X" is a leak with a helpful tone of voice.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _reject(code: str, message: str) -> None:
    raise Refused(code, message)


def is_denied(path: pathlib.Path) -> bool:
    """True if this path is one of the protected artefacts, however it was spelled.

    Compares resolved paths, so `training/../training/corpus.jsonl`, a symlink pointing at it,
    and an absolute path all resolve to the same refusal. `strict=False` matters: a path that
    does not exist still has to be judged, or a race between the check and the open becomes
    the bypass.

    **A relative path is judged against BOTH the repo root and the current directory, and
    denied if either lands on a protected artefact.** This was a live bug, caught by the test
    suite when it was run from a different directory: `is_denied("training/corpus.jsonl")`
    resolved against the process's cwd, so the guard passed from the repo root and silently
    failed from anywhere else -- while `admit()` resolved the same string against the repo root
    and would have opened the file. A guard whose answer depends on where the process was
    started is not a guard. Judging both interpretations costs one extra comparison and removes
    the whole class of question.
    """
    candidates = []
    for base in (ROOT, None):
        p = (base / path) if (base is not None and not path.is_absolute()) else path
        try:
            candidates.append(p.resolve(strict=False))
        except (OSError, RuntimeError):
            return True          # unresolvable means unjudgeable means refused
    for resolved in candidates:
        if resolved in DENIED:
            return True
        if any(resolved == tree or tree in resolved.parents for tree in DENIED_TREES):
            return True
    return False


@dataclass
class DatasetInfo:
    """What is safe to say about a dataset: its shape, never its content."""
    name: str
    path: str
    bytes_on_disk: int
    rows: int
    label: str = "measured"

    def to_dict(self) -> dict:
        return {"name": self.name, "path": self.path, "bytes_on_disk": self.bytes_on_disk,
                "rows": self.rows, "label": self.label,
                "note": ("row count and size only -- no route in this package returns dataset "
                         "content, and no error message quotes a line")}


def admit(path_str: str) -> DatasetInfo:
    """Validate an operator-named JSONL file and return its shape.

    Order matters and is the whole security property: **deny first**, then existence, then
    size, then structure. Checking existence first would let a caller probe for the corpus by
    the difference between "denied" and "not found".
    """
    if not path_str or not path_str.strip():
        _reject("no_dataset", "No dataset named. This surface has no default dataset and does "
                              "not fall back to one.")
    candidate = pathlib.Path(path_str.strip())
    if not candidate.is_absolute():
        candidate = (ROOT / candidate)

    if is_denied(candidate):
        # Deliberately says *that* it is protected without describing it. The refusal is the
        # feature; a helpful explanation of what is inside would defeat it.
        _reject("protected", "That path is a protected SyMoNeuRaL artefact and cannot be used, "
                             "listed or read by this surface.")

    if not candidate.is_file():
        _reject("not_found", "No such file. Name a JSONL file of chat examples.")
    size = candidate.stat().st_size
    if size == 0:
        _reject("empty", "That file is empty.")
    if size > MAX_BYTES:
        _reject("too_large", f"That file is larger than the {MAX_BYTES // (1024 * 1024)} MiB "
                             f"structural cap on a single dataset.")

    rows = 0
    bad = 0
    first_bad_line = 0
    with candidate.open("r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            if rows >= MAX_ROWS:
                _reject("too_many_rows", f"More than {MAX_ROWS:,} rows.")
            try:
                row = json.loads(line)
                msgs = row["messages"]
                if not isinstance(msgs, list) or len(msgs) < 2:
                    raise ValueError
                for m in msgs:
                    if not isinstance(m, dict) or "role" not in m or "content" not in m:
                        raise ValueError
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                # NOTE: the exception is swallowed on purpose. json's own error message
                # includes a slice of the offending document, and that slice is exactly the
                # thing that must not reach an API response. Only the line NUMBER survives.
                bad += 1
                first_bad_line = first_bad_line or lineno
                continue
            rows += 1

    if rows == 0:
        _reject("no_valid_rows", "No usable rows. Each line must be a JSON object with a "
                                 "\"messages\" list of {role, content} pairs.")
    if bad:
        _reject("malformed", f"{bad} line(s) are not valid chat examples, the first at line "
                             f"{first_bad_line}. Each line must be a JSON object with a "
                             f"\"messages\" list of {{role, content}} pairs. "
                             f"(The line itself is deliberately not quoted back.)")

    return DatasetInfo(name=candidate.name, path=str(candidate), bytes_on_disk=size, rows=rows)


def staged() -> list[DatasetInfo]:
    """Datasets previously staged by an operator. Never includes anything from `training/`.

    This scans `run/reinforce/datasets/` and nothing else. It is the *only* directory scan in
    this package that touches data rather than weights, and it is pointed at a directory that
    exists for this purpose. Do not widen it.
    """
    out: list[DatasetInfo] = []
    if not STAGE.is_dir():
        return out
    for p in sorted(STAGE.glob("*.jsonl")):
        if is_denied(p):
            continue      # belt and braces: a symlink into training/ staged by hand
        try:
            out.append(admit(str(p)))
        except Refused:
            continue
    return out
