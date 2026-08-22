# HANDOFF — R-94 / R-96 done outside your session (2026-08-20, Cowork)

Written by the Cowork session (Claude in the desktop app, `/home/google/Symoneural` mounted),
at Garrett's instruction, while your terminal session was mid-turn. **Nothing you own was
touched.** Read this before you re-plan R-94/R-96.

## What landed

- **`tools/build_progress.py`** — NEW file, untracked, yours to commit or move.
- **`run/progress.html`** — 151 rows, generated at HEAD `d6d1e63`. `run/` is gitignored
  (`.gitignore:25`), so it never ships.

Verified: `file:///home/google/Symoneural/run/progress.html` renders with zero console
errors; search, status filters and stream filters all narrow correctly; no network requests
of any kind, so it works with the API down and over `file://`.

## What it is

One page over the three ledgers, parsed — not re-authored:

| Source | Rows | Parse rule |
|---|---|---|
| `GARRETT-REQUESTS.md` | 100 | `## R-N — title` + the `status:` line, read verbatim from the mandated vocabulary |
| `CODER-TASKS.md` | 24 | the glyph on the line (`◼ ◻ ▶`), **not** the section heading |
| `AUDIT-SURFACE-2026-08-19.md` | 27 | `### N. STATUS — title`, incl. 25–27 at `##` depth |

Counts at generation: 50 still open — 14 tasks pending/in-flight, 9 audit open,
16 requests queued, 13 `captured` (logged, never delivered), 1 declined.

Three decisions worth your review, each in a comment in the script:

1. **`captured` is not folded into done.** It counts as open. Your ledger uses it for asks
   that were logged and never delivered; blurring that is the one thing a progress page
   must not do.
2. **The task glyph beats the task heading.** `CODER-TASKS.md`'s own headings say
   "Completed (8) / Pending (12)"; the glyphs say 9 done and 13 pending, and #12/#13 carry
   the done glyph under "Pending". The page shows the glyph and tags the row
   `heading says pending`. **Your headings are stale — fix them at the source and the page
   follows.**
3. **Zero-row streams are fatal, not silent.** The script `return 2`s rather than write a
   page missing a whole stream. This already earned itself: the first version parsed your
   *previous* `GARRETT-REQUESTS.md` format (`- **R-01** …`), you rewrote the file to the
   `status:`/`source:`/`detail:` block format mid-build, and the guard caught the 0-row
   parse instead of publishing a confidently blank Requests section.

## What this costs you

The parser is coupled to the format of all three files. Change a heading shape or the
status vocabulary and the run fails loudly (by design) — re-read `parse_requests` /
`parse_tasks` / `parse_audit`, they are ~40 lines each. Row counts are cross-checked
against a grep of each source and any mismatch prints a WARNING.

The page is a **snapshot**, not live: `file://` blocks `fetch`, so there is no API call.
It stamps each source file's mtime, the git HEAD, and whether the tree is dirty. Per
R-94 ("rebuilt on every state change") the rebuild is one line, and it belongs at the end
of your existing per-item routine, next to `build_cachebust.py`:

```bash
python3 tools/build_progress.py
```

It does not touch `site/`, so it cannot collide with the generator family
(`build_pages.py`, `build_rack.py`, …) and is safe to run while other agents work.

## Over to you

- **R-96** ("can you please get this running") — satisfied; the URL renders now.
- **R-94** (the progress page itself) — the artifact exists; mark it as you see fit and
  decide whether `tools/build_progress.py` gets committed.
- I did **not** edit `GARRETT-REQUESTS.md`, `CODER-TASKS.md`, or any audit document — you
  were writing to them in the same minutes and a second writer there clobbers. Both status
  updates are yours to make.
- Item 15 of the audit surface archives the root review documents. **This file is one of
  them.** Sweep it up with the rest.
