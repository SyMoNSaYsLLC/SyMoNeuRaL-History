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

# `flag` and `override` are captured SEPARATELY rather than swallowed, because both were
# being stripped and then applied as if they were the base variable. Two real corruptions
# came from that, both found by querying the corpus rather than by reading this regex:
#
#   PN:class-devupstream = "linux-yocto-upstream"   in oe-core's linux-yocto_6.18.bb
#       made the kernel recipe index under the name of its devupstream VARIANT, so the
#       corpus held linux-yocto-dev, -rt, -tiny, -fitimage and -upstream and no
#       `linux-yocto` at all -- the main kernel recipe of the main layer, missing.
#   SRC_URI[sha256sum] = "4261dc90..."              in nginx
#       made SRC_URI a bare checksum, so the recipe could never be found by its URL.
VAR_RE = re.compile(
    r'^\s*(?P<key>[A-Za-z0-9_\-\.]+?)'
    r'(?P<flag>\[[^\]]*\])?'
    r'(?P<override>(?::[A-Za-z0-9_\-\.${}]+)*)'
    r'\s*(?P<op>\?\?=|\?=|:=|\+=|=\+|\.=|=\.|=)\s*"(?P<val>(?:[^"\\]|\\.|\\\n)*)"',
    re.M,
)
# Variables whose identity an override changes rather than extends. `RDEPENDS:${PN}` is
# still RDEPENDS and should be collected; `PN:class-devupstream` names a DIFFERENT recipe
# and must never be collected as this one's PN.
IDENTITY = {"PN", "PV"}
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


INCLUDE_RE = re.compile(r"^\s*(?:require|include)\s+(\S+)\s*$", re.M)


def _resolve_include(spec, recipe_dir: Path, layer_root: Path):
    """Where a `require`/`include` line points, or None.

    bitbake resolves these against BBPATH, which this tool does not have. The two places
    that actually matter are the recipe's own directory (`require nginx.inc`) and the
    layer root (`require recipes-kernel/linux/linux-yocto.inc`), so both are tried. A
    ${VAR} anywhere in the path is unresolvable without bitbake and is skipped rather
    than guessed at.
    """
    if "${" in spec:
        return None
    for base in (recipe_dir, layer_root):
        if base is None:
            continue
        cand = (base / spec).resolve()
        try:
            cand.relative_to(layer_root.resolve() if layer_root else base.resolve())
        except ValueError:
            continue          # never read outside the layer
        if cand.is_file():
            return cand
    return None


def _read_with_includes(path: Path, layer_root, depth=0, seen=None):
    """Recipe text with its `require`/`include` files appended.

    Without this, every recipe using the common .bb/.inc split carries NO metadata at
    all: `nginx_1.29.7.bb` is one `require nginx.inc` line, so HOMEPAGE, LICENSE and
    SRC_URI all read empty and the recipe cannot be found by its URL or reported with its
    licence. boost, qtbase and busybox were all empty for the same reason.

    Included text is appended AFTER the recipe's own, and `vals.setdefault` below means
    first-seen wins -- so a value set in the .bb still overrides the .inc it requires,
    which is the direction bitbake resolves them in.
    """
    seen = seen if seen is not None else {path.resolve()}
    text = path.read_text(errors="replace")
    if depth >= 4:
        return text
    for spec in INCLUDE_RE.findall(text):
        inc = _resolve_include(spec, path.parent, layer_root)
        if inc is None or inc.resolve() in seen:
            continue
        seen.add(inc.resolve())
        try:
            text += "\n" + _read_with_includes(inc, layer_root, depth + 1, seen)
        except OSError:
            continue
    return text


def parse_bb(path: Path, layer_root: Path = None) -> dict:
    text = _read_with_includes(path, layer_root)
    vals = {}
    for m in VAR_RE.finditer(text):
        k = m.group("key")
        if k not in CAPTURE:
            continue
        if m.group("flag"):
            # SRC_URI[sha256sum] is a checksum, not a source URL.
            continue
        if m.group("override") and k in IDENTITY:
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
            r = parse_bb(bb, layer_dir)
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
