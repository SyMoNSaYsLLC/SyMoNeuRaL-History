"""Build the OpenEmbedded corpus.

Two sources:
  1. OE Layer Index (https://layers.openembedded.org) -> list of every registered layer + git URL.
  2. Local clones of those layers -> regex-parse every .bb/.bbappend for metadata the API
     doesn't expose well (DEPENDS, SRC_URI, RPROVIDES).

Regex parsing is approximate (no bitbake eval, no ${VAR} expansion). Good enough for matching.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import db

LAYERINDEX = "https://layers.openembedded.org/layerindex/api"
DEFAULT_ROOT = Path(os.environ.get("OEMATCH_LAYERS", Path.home() / ".cache/oematch/layers"))

VAR_RE = re.compile(
    r'^\s*(?P<key>[A-Za-z0-9_\-\.\:]+?)(?:\[[^\]]*\])?\s*(?P<op>\?\?=|\?=|:=|\+=|=\+|\.=|=\.|=)\s*"(?P<val>(?:[^"\\]|\\.|\\\n)*)"',
    re.M,
)
CAPTURE = {"SUMMARY", "DESCRIPTION", "HOMEPAGE", "LICENSE", "SRC_URI", "DEPENDS", "RDEPENDS",
           "PROVIDES", "RPROVIDES", "PV", "PN"}


def _get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def fetch_layer_list(branch="master"):
    """Return [{name, vcs_url, subdir, branch, description}] from the layer index."""
    branches = {b["id"]: b["name"] for b in _get(f"{LAYERINDEX}/branches/")}
    items = {i["id"]: i for i in _get(f"{LAYERINDEX}/layerItems/")}
    out = []
    for lb in _get(f"{LAYERINDEX}/layerBranches/"):
        if branches.get(lb["branch"]) != branch:
            continue
        it = items.get(lb["layer"])
        if not it:
            continue
        out.append({
            "name": it["name"], "vcs_url": it["vcs_url"], "subdir": lb.get("vcs_subdir", ""),
            "branch": lb.get("actual_branch") or branch, "description": it.get("description", ""),
        })
    return out


def clone_or_update(vcs_url, dest: Path, branch):
    if (dest / ".git").exists():
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth=1", "origin", branch],
                       check=False, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "reset", "--hard", "FETCH_HEAD"],
                       check=False, capture_output=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth=1", "--branch", branch, vcs_url, str(dest)],
                       check=False, capture_output=True)
    return (dest / ".git").exists()


def parse_bb(path: Path) -> dict:
    text = path.read_text(errors="replace")
    vals = {}
    for m in VAR_RE.finditer(text):
        k = m.group("key").split(":")[0]  # strip overrides (RDEPENDS:${PN} -> RDEPENDS)
        if k not in CAPTURE:
            continue
        v = m.group("val").replace("\\\n", " ")
        v = re.sub(r"\s+", " ", v).strip()
        if m.group("op") in ("+=", "=+", ".=", "=."):
            vals[k] = (vals.get(k, "") + " " + v).strip()
        else:
            vals.setdefault(k, v)
    stem = path.stem
    pn, pv = (stem.split("_", 1) + [""])[:2] if "_" in stem else (stem, "")
    inherits = " ".join(re.findall(r"^\s*inherit\s+(.+)$", text, re.M))
    return {
        "pn": vals.get("PN", pn), "pv": vals.get("PV", pv), "summary": vals.get("SUMMARY", ""),
        "description": vals.get("DESCRIPTION", ""), "homepage": vals.get("HOMEPAGE", ""),
        "license": vals.get("LICENSE", ""), "src_uri": vals.get("SRC_URI", ""),
        "depends": vals.get("DEPENDS", ""), "rdepends": vals.get("RDEPENDS", ""),
        "provides": vals.get("PROVIDES", ""), "rprovides": vals.get("RPROVIDES", ""),
        "inherits": inherits,
    }


def layer_license(layer_dir: Path) -> str:
    for name in ("LICENSE", "COPYING", "COPYING.MIT", "LICENSE.MIT", "COPYING.GPLv2"):
        p = layer_dir / name
        if p.exists():
            head = p.read_text(errors="replace")[:400].lower()
            if "mit license" in head or "permission is hereby granted" in head:
                return "MIT"
            if "gnu general public license" in head:
                return "GPL"
            if "apache license" in head:
                return "Apache-2.0"
            return name
    return "unknown"


def index_layer(con, name, layer_dir: Path, vcs_url="", branch="", subdir="", description=""):
    lic = layer_license(layer_dir)
    lid = db.upsert_layer(con, name, vcs_url, branch, subdir, lic, description, str(layer_dir))
    db.clear_layer_recipes(con, lid)
    n = 0
    for bb in layer_dir.rglob("*.bb"):
        try:
            r = parse_bb(bb)
        except Exception as e:  # noqa
            print(f"  ! {bb}: {e}", file=sys.stderr)
            continue
        r["filepath"] = str(bb.relative_to(layer_dir))
        db.insert_recipe(con, lid, r)
        n += 1
    con.commit()
    return n


def build(root: Path = DEFAULT_ROOT, branch="master", only=None, db_path=db.DEFAULT_DB, no_fetch=False):
    con = db.connect(db_path)
    layers = fetch_layer_list(branch)
    if only:
        layers = [l for l in layers if l["name"] in only]
    print(f"{len(layers)} layers on branch {branch}")
    for l in layers:
        repo_dir = root / re.sub(r"[^A-Za-z0-9_.-]", "_", l["vcs_url"].rstrip("/").rsplit("/", 1)[-1])
        if not no_fetch:
            ok = clone_or_update(l["vcs_url"], repo_dir, l["branch"])
            if not ok:
                print(f"  skip {l['name']} (clone failed)", file=sys.stderr)
                continue
        layer_dir = repo_dir / l["subdir"] if l["subdir"] else repo_dir
        if not layer_dir.exists():
            continue
        n = index_layer(con, l["name"], layer_dir, l["vcs_url"], l["branch"], l["subdir"], l["description"])
        print(f"  {l['name']:30s} {n:5d} recipes")
    con.close()


def add_local(paths, db_path=db.DEFAULT_DB):
    """Index layers you already have checked out (no network)."""
    con = db.connect(db_path)
    for p in paths:
        p = Path(p).resolve()
        n = index_layer(con, p.name, p)
        print(f"  {p.name:30s} {n:5d} recipes")
    con.close()
