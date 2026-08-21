"""Answer "which layer carries this upstream project?" from a repository URL.

This exists because `match` cannot answer it. `match` fingerprints a FILE -- an ELF, a
.deb, a wheel -- and there is no file here: the question is asked about a project, named
by its git remote. The two are different queries and only one of them was implemented.

## Why the URL alone is not enough

`Matcher._by_homepage` compares host+path against every recipe's HOMEPAGE and SRC_URI.
Measured against the 46 upstream repositories in `UPSTREAM_GROUPS`, that resolved **4**,
and three of the four were wrong -- `sqlite/sqlite` came back as `lemon`, `curl/curl` as
`libcurl-vendor` in three ROS layers, `FFmpeg/FFmpeg` as `omxplayer` in
meta-raspberrypi. The reason is structural, not a tuning problem: OE recipes point at
the RELEASE address, not the development mirror.

    zlib      HOMEPAGE http://zlib.net/            SRC_URI https://zlib.net/${BP}.tar.gz
    openssl   HOMEPAGE http://www.openssl.org/     SRC_URI http://www.openssl.org/source/...
    nodejs    HOMEPAGE http://nodejs.org           SRC_URI https://nodejs.org/dist/v${PV}/...
    redis     HOMEPAGE http://redis.io             SRC_URI http://download.redis.io/releases/...

Not one of those mentions github.com, so no amount of URL comparison finds them from a
github.com URL. What survives across both addresses is the PROJECT NAME, which is why
this module derives candidate names from the URL and matches those against PN and
PROVIDES. The URL comparison is kept and ranked ABOVE the name match, because when a
recipe does cite the same address that is the stronger evidence.
"""
import re
from urllib.parse import urlparse

from .match import Matcher

# Path segments that name a checkout rather than a project. `chromium/src` is the whole
# reason: the last segment is `src`, and a query for a recipe named `src` is meaningless.
_CONTAINER_SEGMENTS = {"src", "source", "sources", "repo", "git", "code",
                       "main", "master", "trunk", "tree"}

# Suffixes an upstream repository adds and a recipe usually does not.
_TRAILING_NOISE = ("-server", "-project", "-core", "-src", "-source", "-sdk", "-lib", "-git")

# Names no rule reaches, because upstream and OE simply chose different words. Kept
# deliberately short: every entry is a claim that can rot, so it has to be worth making.
# The ones here were each verified against the corpus rather than assumed.
PROJECT_ALIASES = {
    "logging-log4j2": ("log4j2", "log4j"),      # Apache repo name carries the org prefix
    "sdl": ("libsdl2", "libsdl"),               # OE prefixes the library, upstream does not
    "webkit": ("webkitgtk", "webkitgtk3"),      # OE ships the GTK port, not the umbrella
    "mongo": ("mongodb",),
    "postgres": ("postgresql",),
    "node": ("nodejs",),
    "linux": ("linux-yocto",),                  # there is no recipe called plain `linux`
    "chromium": ("chromium-x11", "chromium-ozone-wayland"),
    "opensearch": ("opensearch",),
    "three.js": ("threejs",),
    "core-js": ("core-js",),
}


def project_names(url):
    """Candidate project names for an upstream repo URL, most specific first.

    Deliberately returns several: `mysql-server` is `mysql` in OE, `three.js` is
    `threejs` or `three`, and a `lib` prefix appears on one side or the other about
    half the time. The caller ranks by which candidate hit, so a variant match is
    reported as a variant rather than being passed off as an exact one.
    """
    u = urlparse(url if "//" in url else "//" + url)
    segs = [s for s in u.path.split("/") if s]
    if not segs:
        return []
    segs = [re.sub(r"\.git$", "", s) for s in segs]

    last = segs[-1]
    if last.lower() in _CONTAINER_SEGMENTS and len(segs) >= 2:
        last = segs[-2]
    # chromium.googlesource.com/chromium/src -- the host carries the name too, and after
    # the container hop above `last` is already `chromium`. Nothing more to do.

    out = []

    def add(n):
        n = n.strip().lower()
        if n and n not in out and n not in _CONTAINER_SEGMENTS:
            out.append(n)

    add(last)
    for alias in PROJECT_ALIASES.get(last.lower(), ()):
        add(alias)

    # `three.js` -> `threejs`, `three`
    if "." in last:
        add(last.replace(".", ""))
        add(last.split(".")[0])

    for suffix in _TRAILING_NOISE:
        if last.lower().endswith(suffix) and len(last) > len(suffix) + 2:
            add(last[: -len(suffix)])

    if last.lower().startswith("lib") and len(last) > 5:
        add(last[3:])
    else:
        add("lib" + last)

    return out


def resolve(con, url, limit=8):
    """Rank recipes that plausibly carry `url`. Returns a list of dicts, best first.

    Evidence is ranked, not summed, because these are alternative identifications of one
    project rather than accumulating signals about a binary: a recipe citing the same
    URL is not "one point better" than a name match, it is a different kind of answer.
    """
    m = Matcher(con)
    layers = {r["id"]: (r["name"], r["license"]) for r in con.execute(
        "SELECT id, name, license FROM layers")}
    names = project_names(url)
    primary = names[0] if names else None

    ranked = {}

    def offer(rid, rank, why):
        if rid not in ranked or ranked[rid][0] < rank:
            ranked[rid] = (rank, why)

    for rid in m._by_homepage(url):
        offer(rid, 10, f"url:{url}")
    for i, n in enumerate(names):
        for rid in m._by_pn(n):
            offer(rid, 8 if n == primary else 6, f"name:{n}" + ("" if n == primary else " (variant)"))

    if not ranked:
        return []

    ids = list(ranked)
    rows = con.execute(
        f"SELECT id, pn, pv, license, layer_id FROM recipes WHERE id IN ({','.join('?' * len(ids))})",
        ids).fetchall()
    out = []
    for r in rows:
        rank, why = ranked[r["id"]]
        lname, llic = layers.get(r["layer_id"], ("?", ""))
        # An exact PN match is the answer people mean; surface it above a recipe that
        # merely PROVIDES the name or wraps it (`libcurl-vendor`, `rpidistro-ffmpeg`).
        exact = r["pn"].lower() == primary
        out.append({"pn": r["pn"], "pv": r["pv"], "recipe_license": r["license"],
                    "layer": lname, "layer_license": llic,
                    "rank": rank + (2 if exact else 0), "why": why, "exact_pn": exact})
    out.sort(key=lambda d: (-d["rank"], d["layer"] != "openembedded-core", d["pn"]))
    return out[:limit]


# ---------------------------------------------------------------------------------------
# The curated set, as Garrett grouped it (2026-08-21). Each entry is (layer-group, url,
# note) and the GROUP IS THE CLAIM: it says which OE layer is expected to carry that
# upstream project. That makes the whole table checkable -- `tests/test_upstream.py`
# resolves every row against the corpus and compares, so a regression in URL matching or
# name derivation shows up as a named row rather than as a worse-feeling ranking.
#
# `npm` is not a layer and is not a mistake. Those eight are fetched dynamically by
# `npm.bbclass` during an image build and no layer carries a recipe for them, so the
# expected answer is NOTHING FOUND. That assertion is worth as much as the positive ones:
# it is the difference between a tool that says "no layer carries this" and one that
# invents a plausible-looking match, and the aws-c-* bug fixed in 83eb4a1 was exactly the
# latter.
#
# `flagged` reproduces the bare `#` Garrett left on six rows. Every one of them is a
# project whose LICENCE or governance changed, or whose GitHub presence is a mirror
# rather than the canonical source -- SQLite develops in Fossil, Ghostscript is AGPL with
# a paid alternative, Redis and MongoDB both relicensed away from open source, Valkey is
# the fork that resulted, nginx has had a governance fork of its own. That reading is
# INFERRED from which rows carry the mark, not stated, so it is recorded here as an
# inference and not as his words.
UPSTREAM_GROUPS = [
    # --- openembedded-core: fundamental libraries, runtimes, media, core tools ---
    ("openembedded-core", "https://github.com/sqlite/sqlite", "flagged"),
    ("openembedded-core", "https://github.com/madler/zlib", ""),
    ("openembedded-core", "https://github.com/pnggroup/libpng", ""),
    ("openembedded-core", "https://github.com/libjpeg-turbo/libjpeg-turbo", ""),
    ("openembedded-core", "https://github.com/openssl/openssl", ""),
    ("openembedded-core", "https://github.com/curl/curl", ""),
    ("openembedded-core", "https://github.com/lua/lua", ""),
    ("openembedded-core", "https://github.com/libsdl-org/SDL", ""),
    ("openembedded-core", "https://github.com/WebKit/WebKit", ""),
    ("openembedded-core", "https://github.com/boostorg/boost", ""),
    ("openembedded-core", "https://github.com/FFmpeg/FFmpeg", ""),
    ("openembedded-core", "https://code.videolan.org/videolan/x264", ""),
    ("openembedded-core", "https://git.busybox.net/busybox", ""),
    ("openembedded-core", "https://github.com/torvalds/linux", ""),
    ("openembedded-core", "https://github.com/ArtifexSoftware/ghostpdl", "flagged"),
    ("openembedded-core", "https://github.com/tukaani-project/xz", ""),
    # --- meta-oe: extended user space, databases, frameworks ---
    ("meta-oe", "https://github.com/nodejs/node", ""),
    ("meta-oe", "https://github.com/postgres/postgres", ""),
    ("meta-oe", "https://gitlab.com/libeigen/eigen", ""),
    ("meta-oe", "https://github.com/redis/redis", "flagged"),
    ("meta-oe", "https://github.com/valkey-io/valkey", "flagged"),
    ("meta-oe", "https://github.com/mongodb/mongo", "flagged"),
    ("meta-oe", "https://github.com/mysql/mysql-server", ""),
    # --- meta-webserver ---
    ("meta-webserver", "https://github.com/nginx/nginx", "flagged"),
    # --- meta-clang: full LLVM/Clang toolchain, beyond OE-core's basic llvm ---
    ("meta-clang", "https://github.com/llvm/llvm-project", ""),
    # --- meta-browser: web engines and browsers ---
    ("meta-browser", "https://chromium.googlesource.com/chromium/src", ""),
    ("meta-browser", "https://github.com/v8/v8", "usually built inside Chromium or nodejs"),
    # --- meta-qt5 / meta-qt6 ---
    ("meta-qt5", "https://github.com/qt/qtbase", ""),
    # --- meta-java ---
    ("meta-java", "https://github.com/apache/logging-log4j2", ""),
    # --- meta-virtualization and the cloud-native set. Often containers or compiled Go
    #     binaries rather than conventional C/C++ recipes. ---
    ("meta-virtualization", "https://github.com/hashicorp/terraform", ""),
    ("meta-virtualization", "https://github.com/opentofu/opentofu", ""),
    ("meta-virtualization", "https://github.com/elastic/elasticsearch", ""),
    ("meta-virtualization", "https://github.com/opensearch-project/OpenSearch", ""),
    ("meta-virtualization", "https://github.com/minio/minio", ""),
    ("meta-virtualization", "https://github.com/grafana/grafana", ""),
    ("meta-virtualization", "https://github.com/cockroachdb/cockroach", ""),
    ("meta-virtualization", "https://github.com/getsentry/sentry", ""),
    ("meta-virtualization", "https://github.com/akka/akka", ""),
    # --- npm ecosystem: no dedicated layer, fetched via npm.bbclass at image build ---
    ("npm", "https://github.com/facebook/react", ""),
    ("npm", "https://github.com/expressjs/express", ""),
    ("npm", "https://github.com/jquery/jquery", ""),
    ("npm", "https://github.com/twbs/bootstrap", ""),
    ("npm", "https://github.com/mrdoob/three.js", ""),
    ("npm", "https://github.com/babel/babel", ""),
    ("npm", "https://github.com/webpack/webpack", ""),
    ("npm", "https://github.com/zloirock/core-js", ""),
]

# A layer group is a set of layer names, because OE splits along lines the grouping above
# does not: meta-oe/meta-python/meta-webserver all live in the meta-openembedded repo,
# and meta-qt5 and meta-qt6 are separate layers for one project.
GROUP_LAYERS = {
    "openembedded-core": {"openembedded-core", "oe-core", "meta"},
    "meta-oe": {"meta-oe", "meta-openembedded", "meta-python", "meta-networking",
                "meta-multimedia", "meta-filesystems"},
    "meta-webserver": {"meta-webserver"},
    "meta-clang": {"meta-clang"},
    "meta-browser": {"meta-browser", "meta-chromium"},
    "meta-qt5": {"meta-qt5", "meta-qt6"},
    "meta-java": {"meta-java"},
    "meta-virtualization": {"meta-virtualization", "meta-cloud-services"},
    "npm": set(),        # deliberately empty: the expected answer is "no layer"
}
