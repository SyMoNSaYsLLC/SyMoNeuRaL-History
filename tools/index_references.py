#!/usr/bin/env python3
r"""Bind `references/` to `PROJECT-TASKS.md`, so reference material becomes behaviour.

`references/` is 109 GB across 88 entries and nothing in this repo pointed at any of it.
The standing rule is *"we cannot use code in references its for reference only we must
rebrand if we want to use it"* -- so this reads and indexes, it never copies. What it
indexes is the part that is already machine-readable: **1785 `SKILL.md` files** shipped by
twelve of those repos (TensorRT-LLM, NemoClaw, OpenShell, Model-Optimizer, Megatron-LM,
nx-master, deepseek-harness, warp, playwright, vllm, DALI, backstage, plus the NVIDIA
`skills/` catalogue and `anthropics/`).

A skill's frontmatter `description:` is written as a **trigger**: "use when <problem>".
That is the same shape as a task title, which is what makes the join possible at all --
score every skill against every open task, and the highest scorers are the shapes to read
before writing a line of our own code.

Two modes, because indexing and asking are different jobs:

    python3 tools/index_references.py                    # rebuild docs/REFERENCE-INDEX.md
    python3 tools/index_references.py find <words...>    # ad-hoc, writes nothing
    python3 tools/index_references.py adopt <project>    # references/ -> incoming/

**Nothing here reads a file body.** Only frontmatter is parsed, which caps the work at a
few hundred bytes per skill and keeps a 109 GB tree scannable in seconds. It also means
this file cannot accidentally lift an implementation into our tree: it has never seen one.
"""
from __future__ import annotations

import math
import os
import pathlib
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
REFS = REPO / "references"
TASKS = REPO / "PROJECT-TASKS.md"
OUT = REPO / "docs" / "REFERENCE-INDEX.md"

# Directories that cannot hold a skill worth indexing and cost minutes to walk. `.git`
# alone is most of the 109 GB.
PRUNE = {".git", "node_modules", ".venv", "venv", "__pycache__", "site-packages",
         "third_party", "build", "dist", ".mypy_cache", ".pytest_cache", "target"}

# Words that appear in nearly every skill AND nearly every task title, so they carry no
# signal and would rank a random skill against a random task. Kept short on purpose: an
# aggressive stoplist hides real joins.
STOP = set("""a an and are as at be by for from how in into is it its of on or that the
this to use used using when with what which your you we our not only if but do does done
run runs running make makes made new set get put via per one two all any each other than
skill skills agent agents code file files project task tasks work working""".split())


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9+_-]{2,}", text.lower())
            if w not in STOP}


# ----------------------------------------------------------------- frontmatter

def frontmatter(path: pathlib.Path) -> dict[str, str]:
    """Parse just enough YAML to read a skill header, with no dependency.

    Handles the three shapes actually present in `references/`: `key: value`,
    folded scalars (`key: >-` / `key: >` / `key: |`) with an indented block under them,
    and nested mappings, which are skipped rather than half-parsed. Written by hand
    because pulling PyYAML in would put a package on the **serving** interpreter, which
    the working agreements bar outright.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
            if first.strip() != "---":
                return {}
            raw = []
            for line in fh:
                if line.strip() == "---":
                    break
                raw.append(line.rstrip("\n"))
                if len(raw) > 200:      # a runaway file is not frontmatter
                    return {}
    except OSError:
        return {}

    out: dict[str, str] = {}
    key: str | None = None
    folded: list[str] = []
    for line in raw:
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if key is not None:
                out[key] = " ".join(folded).strip()
            key, rest = m.group(1), m.group(2).strip()
            folded = [] if rest in (">", ">-", "|", "|-", "") else [rest]
        elif key is not None and line.startswith((" ", "\t")):
            folded.append(line.strip())
    if key is not None:
        out[key] = " ".join(folded).strip()
    return out


def walk_skills(root: pathlib.Path):
    """Yield every `SKILL.md` under `root`, pruning as we descend rather than after."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in PRUNE]
        if "SKILL.md" in filenames:
            yield pathlib.Path(dirpath) / "SKILL.md"


#: Entries under `references/` that are *collections* of repos rather than one repo.
#: Detected rather than guessed: a directory with no `.git` of its own whose children
#: mostly do. Naming them keeps `anthropics/skilling-up` distinct from `anthropics/xlsx`.
COLLECTIONS = {"anthropics", "openai", "bitmaintech", "contrib", "sdk", "reading", "bin"}


def origin(path: pathlib.Path) -> str:
    """The reference *project* a skill came from, one level deeper inside a collection."""
    rel = path.relative_to(REFS)
    if not rel.parts:
        return "?"
    head = rel.parts[0]
    if head in COLLECTIONS and len(rel.parts) > 2:
        return f"{head}/{rel.parts[1]}"
    return head


def collect() -> list[dict]:
    seen: dict[str, dict] = {}
    for p in walk_skills(REFS):
        fm = frontmatter(p)
        name = fm.get("name") or p.parent.name
        desc = fm.get("description", "").strip()
        if not desc:
            continue
        rec = {
            "name": name,
            "desc": re.sub(r"\s+", " ", desc),
            "origin": origin(p),
            "path": str(p.relative_to(REPO)),
            "license": fm.get("license", ""),
            "tools": fm.get("allowed-tools", ""),
            "bag": words(name.replace("-", " ")) | words(desc),
        }
        # Same skill vendored into several repos: keep the one with the fullest trigger,
        # because the description is the only thing the join scores against.
        prev = seen.get(name)
        if prev is None or len(rec["desc"]) > len(prev["desc"]):
            seen[name] = rec
    return sorted(seen.values(), key=lambda r: (r["origin"], r["name"]))


# ----------------------------------------------------------------- projects

#: A route decorator in any of the three web frameworks present in `references/`, plus
#: the express/fastify shape. Captures the PATH only -- never the handler body. That
#: restraint is the licence position: a list of URLs a project exposes is a description
#: of its surface, and copying a handler would be taking its implementation.
ROUTE_RE = re.compile(
    r"""@(?:app|router|api|bp)\.(?:get|post|put|patch|delete|websocket)\(\s*["']([^"']{1,80})["']"""
    r"""|(?:app|router)\.(?:get|post|put|use|ws)\(\s*["'](/[^"']{0,79})["']""")

#: Files worth opening when fingerprinting a project. Anything else is counted, not read.
SURFACE_FILES = ("routes.py", "api.py", "app.py", "main.py", "server.py", "run.py",
                 "index.ts", "server.ts", "routes.ts")

MARKERS = (("pyproject.toml", "python"), ("setup.py", "python"),
           ("requirements.txt", "python"), ("package.json", "node"),
           ("Cargo.toml", "rust"), ("CMakeLists.txt", "cmake"),
           ("go.mod", "go"), ("Makefile", "make"))


def readme_line(root: pathlib.Path) -> str:
    """The first sentence of prose a project offers about itself.

    Read from the README rather than inferred from the directory name, because the names
    in `references/` are download artefacts -- `drive-download-20260817T185705Z-1-001`
    tells you nothing and `RavenCalcServer_Christmas_20251224-1007` tells you a date.
    """
    for name in ("README.md", "README.rst", "README.txt", "README", "AGENTS.md"):
        f = root / name
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "!", "<", "[!", "---", "|", "=")):
                continue
            return re.sub(r"[*`_]", "", line)[:220]
    return ""


def fingerprint(root: pathlib.Path, cap: int = 6000) -> dict:
    """What surfaces does this project expose, and what is it built out of?

    Deliberately shallow and capped. The point is to make 109 GB *navigable*, not to
    understand it -- an index that takes twenty minutes to build is an index nobody
    regenerates, and a stale index is the second state document this repo bans.
    """
    exts: dict[str, int] = {}
    routes: list[str] = []
    kinds: set[str] = set()
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in PRUNE]
        here = pathlib.Path(dirpath)
        for fn in filenames:
            seen += 1
            if seen > cap:
                break
            ext = pathlib.Path(fn).suffix.lower()
            if ext in (".py", ".ts", ".tsx", ".js", ".cu", ".cpp", ".c", ".h", ".rs",
                       ".sh", ".html", ".css", ".md"):
                exts[ext] = exts.get(ext, 0) + 1
            for marker, kind in MARKERS:
                if fn == marker:
                    kinds.add(kind)
            if fn in SURFACE_FILES and len(routes) < 40:
                try:
                    body = (here / fn).read_text(encoding="utf-8", errors="replace")[:200_000]
                except OSError:
                    continue
                for m in ROUTE_RE.finditer(body):
                    path = m.group(1) or m.group(2)
                    if path and path not in routes:
                        routes.append(path)
        if seen > cap:
            break
    return {"exts": exts, "routes": routes[:24], "kinds": sorted(kinds), "files": seen}


def project_roots() -> list[pathlib.Path]:
    """Top-level reference entries, descending one level into the known collections."""
    out = []
    for child in sorted(REFS.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in COLLECTIONS:
            out.extend(sorted(g for g in child.iterdir()
                              if g.is_dir() and not g.name.startswith(".")))
        else:
            out.append(child)
    return out


def collect_projects(only: set[str] | None = None) -> list[dict]:
    projects = []
    for root in project_roots():
        rel = str(root.relative_to(REFS))
        if only is not None and rel not in only:
            continue
        fp = fingerprint(root)
        if not fp["files"]:
            continue
        blurb = readme_line(root)
        projects.append({
            "name": rel,
            "path": str(root.relative_to(REPO)),
            "blurb": blurb,
            **fp,
            "bag": words(rel.replace("-", " ").replace("_", " ")) | words(blurb)
                   | words(" ".join(fp["routes"]).replace("/", " ").replace("-", " ")),
        })
    return projects


# ----------------------------------------------------------------- the join

TASK_RE = re.compile(r"^◻ (#\d+) — (.+)$")


def open_tasks() -> list[dict]:
    """Title plus the indented detail block, which is where the real vocabulary lives.

    A title is five words; the block below it names the surfaces, the file paths and the
    failure being fixed. Scoring on the title alone joined almost nothing.
    """
    tasks, cur = [], None
    for line in TASKS.read_text().splitlines():
        m = TASK_RE.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "body": []}
            tasks.append(cur)
        elif cur is not None:
            if line.strip() and not line.startswith((" ", "\t")):
                cur = None                      # column zero ends the block
            elif line.strip():
                cur["body"].append(line.strip())
    for t in tasks:
        t["bag"] = words(t["title"]) | words(" ".join(t["body"][:40]))
    return tasks


def idf(skills: list[dict]) -> dict[str, float]:
    """How much is one shared word worth? Inverse document frequency answers it.

    The first cut of this scorer counted raw overlap and it produced nonsense that is
    worth recording: `jira-api`, `notion-api` and `xlsx` ranked top against **every**
    task, including "SyMoNeuRaL Image: image-to-image". Those skills have 90-word
    descriptions full of *manage*, *update*, *search*, *page* -- words this repo's task
    blocks also use constantly -- so raw overlap was measuring description length, not
    subject. `cuda`, `hls`, `lora`, `antminer` appear in a handful of skills each and are
    the words that actually mean something; IDF is what tells them apart, and it needs no
    stoplist tuning to do it.
    """
    n = len(skills) or 1
    df: dict[str, int] = {}
    for s in skills:
        for w in s["bag"]:
            df[w] = df.get(w, 0) + 1
    return {w: math.log(n / c) for w, c in df.items()}


def score(task_bag: set[str], skill: dict, weights: dict[str, float]) -> float:
    """IDF-weighted overlap, with the skill *name* counted three times over.

    A name match ("cuda-kernel-profiling" against a CUDA task) is a much stronger signal
    than the same word buried in a trigger sentence -- the name is what the skill's author
    chose when they had four words to spend.
    """
    name_bag = words(skill["name"].replace("-", " "))
    shared = task_bag & skill["bag"]
    total = sum(weights.get(w, 0.0) for w in shared)
    total += 2 * sum(weights.get(w, 0.0) for w in (task_bag & name_bag))
    # Normalise by the skill's own length. IDF alone was not enough: `claude-api` and
    # `xlsx` still topped every task, because a 90-word description simply *contains*
    # more rare words and collects a little credit from each. Dividing by sqrt(len)
    # asks the question that was meant all along -- what fraction of THIS skill is about
    # THIS task -- instead of how much ground it covers. Cosine, in one line.
    return total / math.sqrt(len(skill["bag"]) or 1)


def rank(task_bag: set[str], skills: list[dict], weights: dict[str, float],
         n: int = 6, floor: float = 1.6) -> list[tuple[float, dict]]:
    """Ranked, and floored *relative to the best match* rather than absolutely.

    A fixed floor either admits noise on a well-matched task or hides the one real hit on
    a thin one. Anything under a third of the top score is not in the same conversation.
    """
    scored = [(score(task_bag, s, weights), s) for s in skills]
    scored.sort(key=lambda p: (-p[0], p[1]["name"]))
    scored = scored[:n]
    if not scored or scored[0][0] < floor:
        return []
    cut = scored[0][0] / 3.0
    return [(sc, s) for sc, s in scored if sc >= cut]


# ----------------------------------------------------------------- output

#: The twenty entries named explicitly as the set to work from. Written down rather than
#: inferred, because the reason they are the set is not visible from the tree: they are
#: the bleeding-edge betas and the first-party work, and `references/` also holds 68 other
#: things. A name here that no longer exists on disk is a red test, not a silent skip.
FOCUS = ["vllm", "deepseek-harness", "Comfy-Desktop", "symoneural (1)", "ComfyUI (1)",
         "ComfyUI (1) (1)", "ComfyUI (2)", "ComfyUI-Shared", "ComfyUI", "bitmaintech",
         "anthropics", "openai", "cuda-python", "Model-Optimizer", "k8s-device-plugin",
         "cuml", "apex", "TensorRT", "SkillSpector", "DeepLearningExamples"]


def in_focus(name: str) -> bool:
    head = name.split("/", 1)[0]
    return head in FOCUS


def project_rows(projects: list[dict]) -> list[str]:
    L = ["| project | built of | surfaces it exposes | what it says it is |",
         "|---|---|---|---|"]
    for pr in sorted(projects, key=lambda r: r["name"].lower()):
        top = sorted(pr["exts"].items(), key=lambda kv: -kv[1])[:3]
        built = ", ".join(f"{n}&nbsp;`{e}`" for e, n in top) or "—"
        if pr["kinds"]:
            built += " · " + "/".join(pr["kinds"])
        routes = ", ".join(f"`{r}`" for r in pr["routes"][:6]) or "—"
        blurb = pr["blurb"].replace("|", "\\|")[:150] or "—"
        L.append(f"| **`{pr['name']}`** | {built} | {routes} | {blurb} |")
    return L


def write_index(skills: list[dict], tasks: list[dict],
                weights: dict[str, float], projects: list[dict]) -> str:
    by_origin: dict[str, int] = {}
    for s in skills:
        by_origin[s["origin"]] = by_origin.get(s["origin"], 0) + 1

    L = []
    L.append("# What is in `references/`, and which open task each part bears on")
    L.append("")
    L.append("**Generated by `tools/index_references.py`. Do not hand-edit — regenerate.**")
    L.append("")
    L.append("`references/` is read-only material: *\"we cannot use code in references its for")
    L.append("reference only we must rebrand if we want to use it\"*. This index exists so that")
    L.append("reading it is cheap enough to actually happen. It records **where a shape lives and")
    L.append("what problem it claims to solve** — never an implementation, and nothing here has")
    L.append("read a file body: only YAML frontmatter is parsed.")
    L.append("")
    L.append(f"**{len(skills)} distinct skills** across **{len(by_origin)} reference repos**,")
    L.append("indexed by their frontmatter trigger.")
    L.append("")
    L.append("| reference repo | skills |")
    L.append("|---|---|")
    for o, n in sorted(by_origin.items(), key=lambda p: -p[1]):
        L.append(f"| `{o}` | {n} |")
    L.append("")
    focus = [pr for pr in projects if in_focus(pr["name"])]
    rest = [pr for pr in projects if not in_focus(pr["name"])]
    L.append("## The twenty named as the set to work from")
    L.append("")
    L.append("Bleeding-edge betas and first-party work, named explicitly. `surfaces it exposes`")
    L.append("is route paths lifted from `routes.py`/`app.py`/`server.ts` and nothing else — a")
    L.append("URL list describes a surface; a handler body would be taking the implementation.")
    L.append("")
    L.extend(project_rows(focus))
    L.append("")
    L.append("## Every other reference project")
    L.append("")
    L.extend(project_rows(rest))
    L.append("")
    L.append("## Per task: read these before writing our own")
    L.append("")
    L.append("Scored on vocabulary overlap between the task's title-plus-detail block and the")
    L.append("skill's own trigger sentence, name matches weighted 3x. A task with no rows scored")
    L.append("nothing above the floor — that is a real answer, not a gap to paper over.")
    L.append("")
    hits = 0
    for t in tasks:
        rows = rank(t["bag"], skills, weights)
        if not rows:
            continue
        hits += 1
        L.append(f"### {t['id']} — {t['title']}")
        L.append("")
        L.append("| skill | from | score | trigger |")
        L.append("|---|---|---|---|")
        for sc, s in rows:
            trig = s["desc"][:170].replace("|", "\\|")
            L.append(f"| `{s['name']}` | `{s['origin']}` | {sc:.1f} | {trig} |")
        L.append("")
    L.append(f"_{hits} of {len(tasks)} open tasks matched at least one skill._")
    L.append("")
    L.append("## Every skill, by origin")
    L.append("")
    cur = None
    for s in skills:
        if s["origin"] != cur:
            cur = s["origin"]
            L.append("")
            L.append(f"### `{cur}`")
            L.append("")
        lic = f" · {s['license']}" if s["license"] else ""
        L.append(f"- **`{s['name']}`**{lic} — {s['desc'][:200]}")
        L.append(f"  <br>`{s['path']}`")
    L.append("")
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------- adopt

INCOMING = REPO / "incoming"

LICENCE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING",
                 "LICENSE-APACHE", "LICENSE-MIT")


def licence_of(root: pathlib.Path) -> tuple[str, str]:
    """(filename, first meaningful line) of whatever licence the project ships.

    Recorded at the moment of adoption rather than looked up later, because the thing
    that makes a licence checkable is knowing *which* text shipped with *which* copy.
    A project with no licence file returns `("", "")` and that is written down as such --
    an unlicensed adoption is a decision someone has to make knowingly.
    """
    for name in LICENCE_FILES:
        f = root / name
        if f.is_file():
            try:
                text = f.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                return name, ""
            for line in text.splitlines():
                line = line.strip()
                if len(line) > 12 and not line.startswith(("=", "-", "#")):
                    return name, line[:160]
            return name, ""
    return "", ""


def adopt(rel: str) -> int:
    """Copy one reference project into `incoming/`, where it stops being read-only.

    The standing rule is *"we cannot use code in references its for reference only we
    must rebrand if we want to use it"* -- so the rule is about **where a file lives**,
    and the way past it is to move the thing, not to argue with the rule. `incoming/` is
    that somewhere else: a staging area whose whole contract is that everything in it is
    on its way to being rebranded and is not shipped from where it lands.

    Copy, never move. `references/` is the provenance; destroying it to satisfy a rule
    about it would leave nothing to check the rebrand against.
    """
    src = REFS / rel
    if not src.is_dir():
        print(f"no such reference project: {rel}", file=sys.stderr)
        return 1
    dst = INCOMING / pathlib.Path(rel).name.replace(" ", "-")
    if dst.exists():
        print(f"already adopted: {dst.relative_to(REPO)}", file=sys.stderr)
        return 1

    lic_file, lic_line = licence_of(src)
    fp = fingerprint(src)
    INCOMING.mkdir(exist_ok=True)
    shutil.copytree(src, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(*PRUNE), dirs_exist_ok=False)

    routes = "\n".join(f"- `{r}`" for r in fp["routes"]) or "_none found_"
    built = ", ".join(f"{n} `{e}`" for e, n in
                      sorted(fp["exts"].items(), key=lambda kv: -kv[1])[:6]) or "—"
    (dst / "PROVENANCE.md").write_text(f"""# Where this came from, and what still has to happen to it

**Adopted from `references/{rel}` by `tools/index_references.py adopt`.**

`references/` is read-only material -- *"we cannot use code in references its for
reference only we must rebrand if we want to use it"*. That rule is about **where a file
lives**, so this copy exists to get past it honestly: everything under `incoming/` is on
its way to being rebranded, and nothing here is shipped from where it sits.

The original is still at `references/{rel}` and was **copied, not moved**. That is
deliberate: the reference copy is what a rebrand gets checked against, and deleting it to
satisfy a rule about it would leave nothing to check.

| | |
|---|---|
| origin | `references/{rel}` |
| built of | {built} |
| licence file | {lic_file or "**none shipped**"} |
| licence line | {lic_line or "—"} |

## Surfaces it exposes

{routes}

## Before anything here ships

1. **Rebrand.** Names, paths, user-visible strings. Not a blind replace -- most `MIT`
   substrings in this corpus are ordinary words (limits, submit, emits).
2. **Keep the attribution the licence requires.** If the table above says a licence
   shipped, its terms travel with the code; if it says none shipped, that is a decision
   to make knowingly rather than a gap to fill in silently.
3. **Give it a task number.** `PROJECT-TASKS.md` is where work comes from, and an
   adoption is not itself permission to build -- `INTAKE.md` is the way in.
""")
    print(f"{rel} -> {dst.relative_to(REPO)}  (licence: {lic_file or 'NONE'})")
    return 0


def main(argv: list[str]) -> int:
    if not REFS.is_dir():
        print(f"no references/ at {REFS}", file=sys.stderr)
        return 1
    skills = collect()

    if len(argv) > 1 and argv[1] == "adopt":
        if len(argv) < 3:
            print("adopt what? (a path under references/)", file=sys.stderr)
            return 2
        return adopt(" ".join(argv[2:]))

    if len(argv) > 1 and argv[1] == "find":
        bag = words(" ".join(argv[2:]))
        if not bag:
            print("find what?", file=sys.stderr)
            return 2
        for sc, s in rank(bag, skills, idf(skills), n=12, floor=0.0):
            print(f"{sc:>6.1f}  {s['name']:<44} {s['origin']}")
            print(f"      {s['desc'][:150]}")
            print(f"      {s['path']}")
        return 0

    tasks = open_tasks()
    projects = collect_projects()
    missing = [f for f in FOCUS if not (REFS / f).exists()]
    if missing:
        print(f"WARNING: named but not on disk: {missing}", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(write_index(skills, tasks, idf(skills), projects))
    print(f"{len(skills)} skills, {len(projects)} projects, {len(tasks)} open tasks "
          f"-> {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
