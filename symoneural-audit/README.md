# symoneural-audit

Finds code that breaks when a directory moves. **First-party, tracked** — like
`symoneural-code/` and unlike the five derived engine trees.

## Why it exists

The 2026-09-08 restructure moved the five runtimes out of `engines/` and the interactive
client out of `bin/`. The client broke instantly and loudly:

```
ROOT = HERE.parent
assert (ROOT / "backend" / "api.py").is_file()
AssertionError: repo root not found at /home/google/Symoneural/symoneural-code
```

`HERE.parent` encodes the file's **depth in the tree**, so every move is a breaking change
— and normally a *silent* one, because the wrong parent is usually a directory that exists.
That file's own comment already said the calculation *"has been wrong four times in this
repo"*. The promotion made it five.

`bin/symoneural-discovery` had been walking up to find `backend/api.py` all along. The
correct pattern was one file away from the one that broke, and nothing could tell you which
files used which. This is that thing.

## What it found on the first run

| Class | Count | |
|---|---|---|
| `depth-root` | **81 silent** | counts parents with no marker assertion — the class that broke the client, and it breaks quietly |
| `depth-root` | 44 loud | counts parents *but* asserts a marker. Same bug, a fraction of the cost, because it fails at startup instead of misbehaving |
| `absolute-repo-path` | 5 | hardcodes `/home/google/Symoneural/…` in executable code; correct on one machine in one checkout |
| `stale-dir` | 21 | names `demo/`, `engines/`, `references/` or `archives/` — directories that were renamed or flattened |

## Use it

```bash
bin/symoneural-audit                            # human-readable
bin/symoneural-audit --json                     # machine-readable
bin/symoneural-audit --only depth-root
bin/symoneural-audit --strict depth-root        # exit 1 on silent findings
```

`--strict` gates only the **silent** findings, because a loud one is already telling you.

## The ratchet

`backend/apps/test_path_fragility.py` pins the silent `depth-root` count at its measured
baseline. New code cannot add to it, and every file repaired lowers the number — the test
tells you to lower the baseline when it does. The 81 are not fixed by this tool; they are
*counted* by it, which is the difference between "we fixed the one we tripped over" and
"we know how many are left".

## The fix, in one line

```python
def find_root(start):                       # not: ROOT = HERE.parent
    for cand in (start, *start.parents):
        if (cand / "backend" / "api.py").is_file():
            return cand
```

Counting parents encodes where a file sits. Searching for a marker encodes what the root
**is**. The second one survives every move.
