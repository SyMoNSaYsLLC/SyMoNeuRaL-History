#!/usr/bin/env python3
"""Render run/progress.html — the one page Garrett bookmarks to see where everything stands.

Sources, all read-only:
  * CODER-TASKS.md          — the canonical task list (marker chars are the status: ◼ done,
                              ◻ pending, ▶ in progress) and the "## Suite readings (latest)"
                              section this script defines the shape of;
  * GARRETT-REQUESTS.md     — the request ledger (mode 600, never committed; the page renders
                              counts and titles, never the file itself);
  * AUDIT-SURFACE-2026-08-19.md — item headings carry their status token after "N.";
  * GARRETT-INBOX.md        — only for whether "## v3 MILESTONE" exists at a line start;
  * git rev-parse           — HEAD short SHA, "no-git" when the root is not a repository
                              (a fresh clone's tarball, or the test suite's tmp roots).

The output is one self-contained file: inline CSS, no external fetches, file:// friendly,
<meta refresh> every 60 s. Deterministic by construction — the ONLY clock read lands on the
single line marked id="generated-at", which the regression test strips before comparing runs.
Missing sources degrade to a labelled note, never a crash: the page must render on the worst
day, because that is the day Garrett looks at it.

Discipline (from the standing rule): every update to CODER-TASKS.md, GARRETT-REQUESTS.md or
the audit surface re-runs this script in the same step. The page is never more than one
state-change stale.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import time
from pathlib import Path

TASK_ROW = re.compile(r"^([◼◻▶]) ((?:\(unnumbered[^)]*\))|#\d+) — (.+)$")
SHA_IN_TEXT = re.compile(r"`([0-9a-f]{7,40})`")
SUITE_ROW = re.compile(r"^- ([^:]+): (.+?) @ `([0-9a-f]{7,40})`$")
AUDIT_HEAD = re.compile(r"^#{2,3}\s*(\d+)\.\s+(.*)$")
REQUEST_HEAD = re.compile(r"^## (R-\d+) — (.+)$")

MARKER_STATE = {"◼": "done", "◻": "pending", "▶": "in progress"}

# The MERGED-EXECUTION-PLAN's step → task mapping, static on purpose: the plan is frozen
# prose in GARRETT-INBOX.md, so a table here is the honest encoding, not a parser guessing.
PHASES = [
    ("Phase 0 — reconcile the inboxes", [("0.1 read + reconcile", "PLAN-RECORDED-DONE")]),
    ("Phase 1 — cut and archive v3", [
        ("1.1 four suites at HEAD", "#13"),
        ("1.2 upgrade path committed", "#11"),
        ("1.3 .deb + repo tarball", "#14"),
        ("1.4 hardlink staging + index", "#15"),
        ("1.5 allv3 archives to Desktop", "#16"),
        ("1.6 milestone records", "MILESTONE"),
    ]),
    ("Phase 2 — the restructure train", [
        ("2.1 studio render from disk", "#31"),
        ("2.2 /livestack/<name> routes", "#26"),
        ("2.3 Live Stack typography", "#27"),
        ("2.4 IPTV rename + Sigils merge", "#28"),
        ("2.5 SymonSays naming sweep", "#25"),
        ("2.6 symoneural-harness", "#21"),
        ("2.7 exp → studio plugin", "#22"),
        ("2.8 reinforce → studio", "#23"),
        ("2.9 ComfyUI → symoneural-ui", "#20"),
        ("2.10 symoneural-invest", "#24"),
    ]),
    ("Phase 3 — credentials, audit close-out, stop", [
        ("3.1 symoneuralcredentials (CLI-driven)", "AUDIT-DONE-IMPLIES"),
        ("3.2 audit items 7 9 10 11 12 18 19, then 15", "AUDIT-OPEN-SET"),
        ("3.3 four suites at final HEAD", "AUDIT-DONE-IMPLIES"),
        ("3.4 AUDIT-DONE-2026-08-19.md", "AUDIT-DONE-FILE"),
    ]),
]
AUDIT_CLOSEOUT_ITEMS = {"7", "9", "10", "11", "12", "15", "18", "19"}

CSS = """
:root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --fg:#e6edf3; --dim:#8b949e;
        --ok:#3fb950; --warn:#d29922; --run:#58a6ff; --bad:#f85149; }
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--fg); margin:0; padding:1.2rem;
       font:15px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif; max-width:1100px;
       margin-inline:auto; }
h1 { font-size:1.35rem; margin:.2rem 0 .1rem; }
h2 { font-size:1.05rem; margin:1.6rem 0 .5rem; border-bottom:1px solid var(--line);
     padding-bottom:.25rem; }
p  { margin:.3rem 0; }
.dim { color:var(--dim); }
.mono { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:.92em; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th,td { text-align:left; padding:.3rem .6rem; border-bottom:1px solid var(--line);
        vertical-align:top; }
th { color:var(--dim); font-weight:600; }
.badge { display:inline-block; padding:0 .5em; border-radius:.7em; font-size:.85em;
         border:1px solid var(--line); white-space:nowrap; }
.s-done { color:var(--ok); }  .s-pending { color:var(--warn); }
.s-in-progress { color:var(--run); } .s-open { color:var(--bad); }
.s-other { color:var(--dim); }
ul { margin:.3rem 0 .3rem 1.2rem; padding:0; }
li { margin:.15rem 0; }
.phase { background:var(--panel); border:1px solid var(--line); border-radius:8px;
         padding:.6rem .9rem; margin:.5rem 0; }
.phase.current { border-color:var(--run); }
.steps { display:flex; flex-wrap:wrap; gap:.35rem .6rem; margin-top:.35rem; }
"""


def parse_args():
    default_root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=default_root)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <root>/run/progress.html")
    return ap.parse_args()


def head_sha(root: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "no-git"
    except OSError:
        return "no-git"


def parse_tasks(text: str) -> list[dict]:
    """Every marker row plus its indented detail block; SHA read from either."""
    tasks, current = [], None
    for line in text.splitlines():
        m = TASK_ROW.match(line)
        if m:
            current = {"state": MARKER_STATE[m.group(1)], "id": m.group(2),
                       "title": m.group(3), "detail": ""}
            tasks.append(current)
        elif current is not None and line.startswith((" ", "\t")):
            current["detail"] += line + "\n"
        elif line.strip() == "":
            continue
        else:
            current = None
    for t in tasks:
        m = SHA_IN_TEXT.search(t["title"]) or SHA_IN_TEXT.search(t["detail"])
        t["sha"] = m.group(1) if m else ""
    return tasks


def parse_suites(text: str) -> list[tuple[str, str, str]]:
    rows, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## Suite readings")
            continue
        if inside:
            m = SUITE_ROW.match(line)
            if m:
                rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def parse_audit(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        m = AUDIT_HEAD.match(line)
        if not m:
            continue
        rest = m.group(2)
        if rest.startswith("DONE"):
            bucket = "done"
        elif rest.startswith("OPEN"):
            bucket = "open"
        else:
            bucket = "other"   # SCOPE / LOW / GARRETT-ONLY / NOT MINE — labelled, not hidden
        name = rest.split(" — ", 1)[1] if " — " in rest else rest
        items.append({"n": m.group(1), "bucket": bucket,
                      "label": rest.split(" — ", 1)[0], "name": name})
    return items


# The ledger's status vocabulary, mapped to the bucket each status renders in. Held as data
# rather than the prefix loop this replaces, because two of these are not work at all:
# `adopted` is a standing rule with nothing to do, and `superseded` is closed-without-doing.
# Bucketing either as `captured` would file it under "un-actioned" and invite the next
# iteration to action it.
#
# `held` is why this table exists. Garrett froze R-11, R-52 and R-98 on 2026-08-20. The loop
# here previously fell through to `captured` for any status it did not recognise, so a frozen
# entry rendered as ordinary open work — the page would have advertised, as available, exactly
# the three items he had just told me not to touch. Unknown statuses now raise instead: the
# ledger's vocabulary and this parser are one contract, and a silent default is what let them
# drift apart.
STATUS_BUCKETS = {
    "done": "done",
    "declined": "declined",
    "superseded": "superseded",
    "adopted": "adopted",
    "held": "held",
    "queued": "queued",
    "in-progress": "in-progress",
    "captured": "captured",
}

# Buckets that mean "still on somebody's plate". `held` is in here deliberately: frozen work
# is outstanding work that nobody may pick up, so leaving it out would under-report what is
# open. It is flagged in the render so it cannot be mistaken for available.
OPEN_BUCKETS = ("captured", "queued", "in-progress", "held")


def parse_requests(text: str) -> list[dict]:
    entries, current = [], None
    for line in text.splitlines():
        m = REQUEST_HEAD.match(line)
        if m:
            current = {"id": m.group(1), "title": m.group(2), "status": ""}
            entries.append(current)
        elif current is not None and line.startswith("status:") and not current["status"]:
            current["status"] = line[len("status:"):].strip()
    for e in entries:
        s = e["status"].lower()
        for token, bucket in STATUS_BUCKETS.items():
            if s.startswith(token):
                e["bucket"] = bucket
                break
        else:
            raise ValueError(
                f"{e['id']}: status {e['status']!r} begins with none of "
                f"{sorted(STATUS_BUCKETS)}. Add the new status to STATUS_BUCKETS (and to "
                "OPEN_BUCKETS if it means the item is still outstanding) rather than letting "
                "it render as something it is not. This used to fall back to `captured` "
                "silently, which would have shown Garrett's held items as available work.")
    return entries


def step_state(ref: str, task_by_id: dict, audit: list[dict], root: Path,
               milestone_hit: bool, audit_done_file: bool) -> str:
    if ref == "PLAN-RECORDED-DONE":
        return "done"
    if ref == "MILESTONE":
        return "done" if milestone_hit else "pending"
    if ref == "AUDIT-DONE-FILE":
        return "done" if audit_done_file else "pending"
    if ref == "AUDIT-DONE-IMPLIES":
        # 3.1 and 3.3 have no tracker row of their own; the plan's order means the
        # close-out document cannot exist unless they happened first.
        return "done" if audit_done_file else "pending"
    if ref == "AUDIT-OPEN-SET":
        tracked = [i for i in audit if i["n"] in AUDIT_CLOSEOUT_ITEMS]
        if tracked and all(i["bucket"] == "done" for i in tracked):
            return "done"
        if any(i["bucket"] == "done" for i in tracked):
            return "in progress"
        return "pending"
    t = task_by_id.get(ref)
    return t["state"] if t else "pending"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def badge(state: str) -> str:
    cls = "s-" + state.replace(" ", "-")
    return f'<span class="badge {cls}">{esc(state)}</span>'


def build(root: Path) -> str:
    tasks_file = root / "CODER-TASKS.md"
    ledger_file = root / "GARRETT-REQUESTS.md"
    audit_file = root / "AUDIT-SURFACE-2026-08-19.md"
    inbox_file = root / "GARRETT-INBOX.md"

    tasks = parse_tasks(tasks_file.read_text()) if tasks_file.exists() else []
    suites = parse_suites(tasks_file.read_text()) if tasks_file.exists() else []
    audit = parse_audit(audit_file.read_text()) if audit_file.exists() else []
    requests = parse_requests(ledger_file.read_text()) if ledger_file.exists() else None
    milestone_hit = bool(inbox_file.exists() and
                         re.search(r"^## v3 MILESTONE", inbox_file.read_text(), re.M))
    audit_done_file = (root / "AUDIT-DONE-2026-08-19.md").exists()
    sha = head_sha(root)
    task_by_id = {t["id"]: t for t in tasks}

    phase_blocks, current_phase = [], None
    for title, steps in PHASES:
        states = [(label, step_state(ref, task_by_id, audit, root,
                                     milestone_hit, audit_done_file))
                  for label, ref in steps]
        phase_done = all(s == "done" for _, s in states)
        if not phase_done and current_phase is None:
            current_phase = title
        phase_blocks.append((title, states, phase_done))

    out = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="en"><head><meta charset="utf-8">')
    out.append('<meta http-equiv="refresh" content="60">')
    out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    out.append("<title>Symoneural progress</title>")
    out.append(f"<style>{CSS}</style></head><body>")

    # Header — the one line with a clock on it carries the marker id the test strips.
    out.append("<h1>Symoneural — where everything stands</h1>")
    out.append(f'<p id="generated-at" class="dim">generated '
               f'{time.strftime("%Y-%m-%d %H:%M:%S %Z")} — auto-refreshes every 60&thinsp;s'
               "</p>")
    out.append(f'<p>HEAD <span class="mono">{esc(sha)}</span> &middot; current phase: '
               f"<strong>{esc(current_phase or 'all phases complete')}</strong></p>")

    out.append("<h2>Phase tracker</h2>")
    for title, states, phase_done in phase_blocks:
        cur = " current" if title == current_phase else ""
        out.append(f'<div class="phase{cur}"><strong>{esc(title)}</strong> '
                   f'{badge("done") if phase_done else ""}<div class="steps">')
        for label, state in states:
            out.append(f"<span>{esc(label)} {badge(state)}</span>")
        out.append("</div></div>")

    out.append("<h2>Tasks — CODER-TASKS.md, the canonical list</h2>")
    if tasks:
        out.append('<div class="scroll"><table><tr><th>task</th><th>status</th>'
                   "<th>SHA</th><th>wording</th></tr>")
        for t in tasks:
            sha_cell = f'<span class="mono">{esc(t["sha"])}</span>' if t["sha"] else ""
            out.append(f'<tr><td class="mono">{esc(t["id"])}</td><td>{badge(t["state"])}'
                       f'</td><td>{sha_cell}</td><td>{esc(t["title"])}</td></tr>')
        out.append("</table></div>")
    else:
        out.append('<p class="dim">CODER-TASKS.md not found — nothing to render.</p>')

    out.append("<h2>Request ledger — GARRETT-REQUESTS.md</h2>")
    if requests is None:
        out.append('<p class="dim">GARRETT-REQUESTS.md not present yet; the ledger block '
                   "renders as soon as it exists.</p>")
    else:
        counts = {}
        for e in requests:
            counts[e["bucket"]] = counts.get(e["bucket"], 0) + 1
        summary = " &middot; ".join(f"{b}: <strong>{n}</strong>"
                                    for b, n in sorted(counts.items()))
        out.append(f"<p>{len(requests)} entries — {summary}</p>")
        open_entries = [e for e in requests if e["bucket"] in OPEN_BUCKETS]
        frozen = sum(1 for e in open_entries if e["bucket"] == "held")
        note = (f" &mdash; {frozen} <strong>held</strong>, frozen by Garrett and not available "
                "to pick up" if frozen else "")
        out.append(f"<p>Un-actioned ({len(open_entries)}){note}:</p><ul>")
        for e in open_entries:
            flag = '<span class="mono">[FROZEN]</span> ' if e["bucket"] == "held" else ""
            out.append(f'<li>{flag}<span class="mono">{esc(e["id"])}</span> — {esc(e["title"])} '
                       f'<span class="dim">[{esc(e["status"])}]</span></li>')
        out.append("</ul>")

    out.append("<h2>Audit surface — AUDIT-SURFACE-2026-08-19.md</h2>")
    if audit:
        done_n = sum(1 for i in audit if i["bucket"] == "done")
        open_items = [i for i in audit if i["bucket"] == "open"]
        other_items = [i for i in audit if i["bucket"] == "other"]
        out.append(f"<p>DONE: <strong>{done_n}</strong> &middot; OPEN: "
                   f"<strong>{len(open_items)}</strong> &middot; other dispositions: "
                   f"<strong>{len(other_items)}</strong></p>")
        out.append("<p>OPEN by name:</p><ul>")
        for i in open_items:
            out.append(f'<li><span class="mono">item {esc(i["n"])}</span> — '
                       f'{esc(i["name"])}</li>')
        out.append("</ul><p>Other dispositions:</p><ul>")
        for i in other_items:
            out.append(f'<li><span class="mono">item {esc(i["n"])}</span> '
                       f'<span class="dim">[{esc(i["label"])}]</span> — '
                       f'{esc(i["name"])}</li>')
        out.append("</ul>")
    else:
        out.append('<p class="dim">audit surface not found.</p>')

    out.append("<h2>Suites — latest readings, each anchored to its tree</h2>")
    if suites:
        out.append('<div class="scroll"><table><tr><th>suite</th><th>reading</th>'
                   "<th>SHA</th></tr>")
        for name, reading, s in suites:
            out.append(f'<tr><td class="mono">{esc(name)}</td><td>{esc(reading)}</td>'
                       f'<td class="mono">{esc(s)}</td></tr>')
        out.append("</table></div>")
    else:
        out.append('<p class="dim">no "## Suite readings (latest)" section found in '
                   "CODER-TASKS.md.</p>")

    out.append("</body></html>")
    return "\n".join(out) + "\n"


def main():
    args = parse_args()
    out = args.out or (args.root / "run" / "progress.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.root))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
