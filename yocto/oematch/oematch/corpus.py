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


# Ordered most specific first: "gnu lesser general public" also contains "general
# public", and "apache license" appears inside several dual-licence preambles, so a
# first-match-wins scan has to see the narrow patterns before the broad ones. Each
# pattern is text that appears in the licence body itself, not in a header a project
# may or may not have pasted in.
LICENSE_PATTERNS = [
    ("LGPL-2.1-only",  ("gnu lesser general public license", "version 2.1")),
    ("LGPL-3.0-only",  ("gnu lesser general public license", "version 3")),
    ("LGPL-2.1-only",  ("gnu library general public license",)),
    ("AGPL-3.0-only",  ("gnu affero general public license",)),
    ("GPL-2.0-only",   ("gnu general public license", "version 2")),
    ("GPL-3.0-only",   ("gnu general public license", "version 3")),
    # meta-cryptocurrency's LICENSE says "GNU Public License version 2" -- not the
    # official name, so the pattern above misses it and the old code returned the
    # FILENAME. This is why every candidate file is now scanned and why a filename is
    # never a return value.
    ("GPL-2.0-only",   ("gnu public license", "version 2")),
    ("GPL-3.0-only",   ("gnu public license", "version 3")),
    ("Apache-2.0",     ("apache license", "version 2.0")),
    ("MPL-2.0",        ("mozilla public license", "version 2.0")),
    ("MIT",            ("permission is hereby granted, free of charge",)),
    ("MIT",            ("mit license",)),
    ("ISC",            ("permission to use, copy, modify, and/or distribute",)),
    ("BSD-3-Clause",   ("redistributions in binary form", "name of the copyright holder")),
    ("BSD-3-Clause",   ("redistributions in binary form", "neither the name")),
    ("BSD-2-Clause",   ("redistributions in binary form",)),
    ("Zlib",           ("altered source versions must be plainly marked",)),
    ("CC0-1.0",        ("cc0 1.0 universal",)),
    ("CC-BY-4.0",      ("creative commons attribution 4.0 international",)),
    ("CC-BY-SA-4.0",   ("attribution-sharealike 4.0 international",)),
    ("Unlicense",      ("this is free and unencumbered software released into the public domain",)),
]

# A licence file may encode the answer in its own name. Used only as a fallback when the
# text is inconclusive, and mapped to a real SPDX identifier -- the old code returned the
# bare filename, which is how 17 layers came to report a licence of "LICENSE".
FILENAME_HINTS = {
    "mit": "MIT", "gpl2": "GPL-2.0-only", "gplv2": "GPL-2.0-only",
    "gpl-2.0": "GPL-2.0-only", "gpl-2.0-only": "GPL-2.0-only",
    "gpl3": "GPL-3.0-only", "gplv3": "GPL-3.0-only", "gpl-3.0": "GPL-3.0-only",
    "lgpl": "LGPL-2.1-only", "lgpl-2.1": "LGPL-2.1-only", "lgplv2.1": "LGPL-2.1-only",
    "apache": "Apache-2.0", "apache-2.0": "Apache-2.0",
    "bsd": "BSD-3-Clause", "bsd-2-clause": "BSD-2-Clause", "bsd-3-clause": "BSD-3-Clause",
    "mpl-2.0": "MPL-2.0", "isc": "ISC", "zlib": "Zlib",
}

LICENSE_FILE_RE = re.compile(r"^(LICEN[CS]E|COPYING|COPYRIGHT)([.\-_].*)?$", re.I)


def _identify_license_text(text):
    """SPDX identifier for a licence body, or None. Never returns a filename."""
    t = re.sub(r"\s+", " ", text).lower()
    for spdx, needles in LICENSE_PATTERNS:
        if all(n in t for n in needles):
            return spdx
    return None


def _license_files(d: Path):
    try:
        return sorted(p for p in d.iterdir() if p.is_file() and LICENSE_FILE_RE.match(p.name))
    except OSError:
        return []


def layer_license(layer_dir: Path) -> str:
    """Every licence the layer's own licence files declare, or "unknown".

    Four defects this replaces, each measured against the 477-layer corpus rather than
    reasoned about:

    * it returned `name` -- a FILENAME -- when no pattern matched, which is why 17
      layers reported a licence of literally "LICENSE" and one reported "COPYING".
    * it returned on the FIRST candidate file that existed, so a layer whose LICENSE is
      a pointer ("see COPYING for details") never had its COPYING read. That is exactly
      meta-cryptocurrency, which is GPL-2.0 and reported "LICENSE".
    * it had no BSD pattern at all, so meta-buildutils -- BSD-2-Clause -- reported
      "LICENSE", and no pattern for any GPL variant.
    * a sub-layer inside a multi-layer repo never looked at the repo root, where the
      licence files usually live. meta-agl-app-framework reported "unknown" while its
      parent holds LICENSE, LICENSE.GPL-2.0-only and LICENSE.MIT.

    Several licences are reported joined by " AND ", meaning the layer contains files
    under each -- which is the honest reading of a layer holding both LICENSE.MIT and
    LICENSE.GPL-2.0-only, and better than picking whichever the old loop reached first.
    """
    found, hinted = [], []

    def scan(d: Path):
        for p in _license_files(d):
            try:
                spdx = _identify_license_text(p.read_text(errors="replace")[:20000])
            except OSError:
                continue
            if spdx:
                if spdx not in found:
                    found.append(spdx)
                continue
            # No recognisable body. The name may still say, e.g. an empty or
            # pointer-only COPYING.MIT.
            suffix = p.name.split(".", 1)[1].lower() if "." in p.name else ""
            hint = FILENAME_HINTS.get(suffix)
            if hint and hint not in hinted:
                hinted.append(hint)

    scan(layer_dir)
    if not found and not hinted:
        # Walk up to the repository root for sub-layers (meta-foo inside a repo whose
        # licence files sit beside the .git directory), stopping there rather than
        # wandering into ~/.cache/oematch/layers and reading a sibling layer's licence.
        d = layer_dir
        for _ in range(4):
            parent = d.parent
            if parent == d:
                break
            scan(parent)
            if found or hinted or (parent / ".git").exists():
                break
            d = parent

    # Sorted, so a layer holding LICENSE.MIT and LICENSE.GPL-2.0-only reports one value
    # rather than two orderings of it -- `MIT AND GPL-2.0-only` and `GPL-2.0-only AND
    # MIT` both appeared in the first run of this function, five layers each.
    out = sorted(found or hinted)
    return " AND ".join(out) if out else "unknown"


def index_layer(con, name, layer_dir: Path, vcs_url="", branch="", subdir="", description=""):
    lic = layer_license(layer_dir)
    lid = db.upsert_layer(con, name, vcs_url, branch, subdir, lic, description, str(layer_dir))
    db.clear_layer_recipes(con, lid)
    n = 0
    # `.bbappend` too. Indexing only `.bb` made meta-clang -- which carries 0 recipes and
    # 20 appends -- index as an empty layer, so the tool could never answer "which layer
    # adds clang support to ffmpeg", which is the entire reason that layer exists. They
    # are stored with kind='bbappend' and never mixed into recipe lookups: an append does
    # not PROVIDE ffmpeg, it modifies the recipe that does.
    for bb in sorted(layer_dir.rglob("*.bb")) + sorted(layer_dir.rglob("*.bbappend")):
        try:
            r = parse_bb(bb, layer_dir)
        except Exception as e:  # noqa
            print(f"  ! {bb}: {e}", file=sys.stderr)
            continue
        r["kind"] = "bbappend" if bb.suffix == ".bbappend" else "bb"
        if r["kind"] == "bbappend":
            # `ffmpeg_%.bbappend` -> pn ffmpeg, and the `%` is a version WILDCARD, not a
            # version. Recording it as a PV would put a literal `%` in the output.
            if "%" in r["pv"] or "${" in r["pv"]:
                r["pv"] = ""
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
