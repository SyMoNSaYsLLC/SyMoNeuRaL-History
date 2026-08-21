"""Rank OpenEmbedded recipes against extracted signals.

Scoring (per recipe, summed over evidence):
  homepage URL host+path match ........ 9
  exact PN / PROVIDES / RPROVIDES ..... 8
  soname stem -> PN ................... 7
  known soname map .................... 7
  dep name -> python3-<dep> / <dep> ... 6
  tool name -> PN ..................... 5
  FTS hit on summary/description ...... 1 per term (capped)
"""
import re
from collections import defaultdict
from urllib.parse import urlparse

from . import db

# sonames whose stem does not equal the recipe name
SONAME_MAP = {
    "crypto": "openssl", "ssl": "openssl", "z": "zlib", "m": "glibc", "c": "glibc", "dl": "glibc",
    "pthread": "glibc", "rt": "glibc", "stdc++": "gcc-runtime", "gcc_s": "gcc-runtime",
    "glib-2.0": "glib-2.0", "gobject-2.0": "glib-2.0", "gio-2.0": "glib-2.0", "gmodule-2.0": "glib-2.0",
    "avcodec": "ffmpeg", "avformat": "ffmpeg", "avutil": "ffmpeg", "swscale": "ffmpeg", "swresample": "ffmpeg",
    "gstreamer-1.0": "gstreamer1.0", "gstbase-1.0": "gstreamer1.0", "gstapp-1.0": "gstreamer1.0-plugins-base",
    "gstvideo-1.0": "gstreamer1.0-plugins-base", "gstaudio-1.0": "gstreamer1.0-plugins-base",
    "curl": "curl", "sqlite3": "sqlite3", "ncursesw": "ncurses", "ncurses": "ncurses", "tinfo": "ncurses",
    "readline": "readline", "ffi": "libffi", "uuid": "util-linux", "blkid": "util-linux", "mount": "util-linux",
    "udev": "systemd", "systemd": "systemd", "dbus-1": "dbus", "expat": "expat", "xml2": "libxml2",
    "png16": "libpng", "png": "libpng", "jpeg": "jpeg", "turbojpeg": "libjpeg-turbo", "webp": "libwebp",
    "freetype": "freetype", "fontconfig": "fontconfig", "harfbuzz": "harfbuzz", "cairo": "cairo",
    "pango-1.0": "pango", "gtk-3": "gtk+3", "gtk-4": "gtk4", "wayland-client": "wayland", "wayland-server": "wayland",
    "X11": "libx11", "xcb": "libxcb", "EGL": "virtual/egl", "GLESv2": "virtual/libgles2", "GL": "virtual/libgl",
    "drm": "libdrm", "gbm": "mesa", "vulkan": "vulkan-loader", "asound": "alsa-lib", "pulse": "pulseaudio",
    "pipewire-0.3": "pipewire", "bluetooth": "bluez5", "nl-3": "libnl", "nl-genl-3": "libnl", "pcap": "libpcap",
    "usb-1.0": "libusb1", "gpiod": "libgpiod", "i2c": "i2c-tools", "mosquitto": "mosquitto", "paho-mqtt3c": "paho-mqtt-c",
    "protobuf": "protobuf", "grpc": "grpc", "grpc++": "grpc", "boost_system": "boost", "boost_filesystem": "boost",
    "opencv_core": "opencv", "opencv_imgproc": "opencv", "onnxruntime": "onnxruntime", "tensorflow-lite": "tensorflow-lite",
    "python3.11": "python3", "python3.12": "python3", "python3.13": "python3", "node": "nodejs",
    "lua5.4": "lua", "lua": "lua", "archive": "libarchive", "zstd": "zstd", "lzma": "xz", "bz2": "bzip2",
    "lz4": "lz4", "brotlidec": "brotli", "nghttp2": "nghttp2", "ssh2": "libssh2", "gnutls": "gnutls",
    "gcrypt": "libgcrypt", "sodium": "libsodium", "jansson": "jansson", "json-c": "json-c", "yaml": "libyaml",
    "cap": "libcap", "seccomp": "libseccomp", "selinux": "libselinux", "pam": "libpam", "crypt": "libxcrypt",
    "attr": "attr", "acl": "acl", "event": "libevent", "uv": "libuv", "ev": "libev", "mnl": "libmnl",
    "xtables": "iptables", "nftnl": "libnftnl", "tpm2": "tpm2-tss", "tss2-esys": "tpm2-tss",
}
TOOL_MAP = {
    "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "gst-launch-1.0": "gstreamer1.0", "git": "git", "curl": "curl",
    "wget": "wget", "rsync": "rsync", "ssh": "openssh", "scp": "openssh", "openssl": "openssl",
    "python3": "python3", "python": "python3", "node": "nodejs", "npm": "nodejs", "rg": "ripgrep",
    "ripgrep": "ripgrep", "fd": "fd-find", "jq": "jq", "sqlite3": "sqlite3", "psql": "postgresql",
    "mysql": "mariadb", "redis-cli": "redis", "docker": "docker", "podman": "podman", "systemctl": "systemd",
    "journalctl": "systemd", "dbus-send": "dbus", "busctl": "systemd", "gpg": "gnupg", "tar": "tar",
    "xz": "xz", "zstd": "zstd", "unzip": "unzip", "make": "make", "cmake": "cmake", "ninja": "ninja",
    "nmcli": "networkmanager", "iw": "iw", "ip": "iproute2", "iptables": "iptables", "nft": "nftables",
    "ethtool": "ethtool", "udevadm": "systemd", "mount": "util-linux", "losetup": "util-linux",
    "mkfs.ext4": "e2fsprogs", "v4l2-ctl": "v4l-utils", "alsamixer": "alsa-utils", "aplay": "alsa-utils",
    "pactl": "pulseaudio", "pw-cli": "pipewire", "wpa_supplicant": "wpa-supplicant", "hostapd": "hostapd",
    "dnsmasq": "dnsmasq", "nginx": "nginx", "haproxy": "haproxy", "mosquitto_pub": "mosquitto",
    "mosquitto_sub": "mosquitto", "avahi-browse": "avahi", "bluetoothctl": "bluez5",
    "qemu-system-x86_64": "qemu", "gcc": "gcc", "clang": "clang", "rustc": "rust", "cargo": "cargo", "go": "go",
}
# python dist name -> OE recipe name quirks
PY_MAP = {"pyyaml": "python3-pyyaml", "pillow": "python3-pillow", "attrs": "python3-attrs",
          "typing-extensions": "python3-typing-extensions", "opencv-python": "opencv"}


# Shortest term allowed to reach the FTS fallback in `_by_pn`. Three, because the
# tokenizer splits hyphens: at one or two characters a term matches recipe-name segments
# (`c` in `aws-c-auth`, `io` in `aws-c-io`) rather than recipes.
FTS_MIN_TERM = 3


def _fts_escape(term):
    return '"' + term.replace('"', '""') + '"'


class Matcher:
    def __init__(self, con):
        self.con = con
        self.scores = defaultdict(float)
        self.evidence = defaultdict(list)

    def _hit(self, recipe_id, pts, why):
        self.scores[recipe_id] += pts
        self.evidence[recipe_id].append(why)

    def _by_pn(self, name):
        rows = self.con.execute("SELECT id FROM recipes WHERE pn=? COLLATE NOCASE", (name,)).fetchall()
        if not rows and len(name) >= FTS_MIN_TERM:
            # The fallback is here to catch a name that is a PROVIDES/RPROVIDES rather than
            # a PN -- `virtual/egl` is provided by mesa, not named it. It is a TOKEN match,
            # though, and SQLite's FTS tokenizer splits on hyphens, so a one- or two-
            # character term matches every hyphenated recipe containing it as a segment and
            # scores them all as if the name had been exact. Short terms are barred rather
            # than down-weighted: there is no length at which `c` legitimately identifies
            # `aws-c-auth`, so this is a wrong answer being removed, not a ranking tweak.
            rows = self.con.execute(
                "SELECT rowid AS id FROM recipes_fts WHERE provides MATCH ? OR rprovides MATCH ?",
                (_fts_escape(name), _fts_escape(name))).fetchall()
        return [r["id"] for r in rows]

    def _by_homepage(self, url):
        u = urlparse(url)
        if not u.netloc:
            return []
        key = (u.netloc + u.path).lower().rstrip("/")
        rows = self.con.execute("SELECT id, homepage, src_uri FROM recipes WHERE homepage != '' OR src_uri != ''").fetchall()
        out = []
        for r in rows:
            for cand in (r["homepage"], r["src_uri"]):
                for c in cand.split():
                    cu = urlparse(c.split(";")[0])
                    ck = (cu.netloc + cu.path).lower().rstrip("/")
                    # Both directions. Only `ck in key` was tested, which is the RARER
                    # case: a recipe's SRC_URI is a release artefact UNDER the project
                    # URL, so the queried key is a prefix of the candidate, not the
                    # reverse. `xz` carries
                    # `github.com/tukaani-project/xz/releases/download/v${PV}/...` and
                    # was missed by a query for `github.com/tukaani-project/xz`.
                    if ck and (ck == key or (len(ck) > 12 and ck in key)
                               or (len(key) > 12 and key in ck)):
                        out.append(r["id"])
                        break
        return out

    def _fts(self, terms, cap=3):
        terms = [t for t in terms if len(t) >= 3][:50]
        if not terms:
            return
        q = " OR ".join(_fts_escape(t) for t in terms)
        for r in self.con.execute(
                "SELECT rowid AS id, bm25(recipes_fts) AS rank FROM recipes_fts WHERE recipes_fts MATCH ? ORDER BY rank LIMIT 200",
                (q,)):
            self._hit(r["id"], min(cap, 1.0), "fts")

    def run(self, sig):
        for url in sig.urls:
            for rid in self._by_homepage(url):
                self._hit(rid, 9, f"homepage:{url}")
        for so in sig.sonames:
            stem = so
            m = re.match(r"^lib(.+?)\.so", so)
            stem = m.group(1) if m else so
            target = SONAME_MAP.get(stem)
            if target:
                for rid in self._by_pn(target):
                    self._hit(rid, 7, f"soname:{so}→{target}")
                # The map is an answer, not a hint, so stop here. Falling through to the
                # guess below is what put twelve `aws-c-*` recipes at 7.0 -- above `gcc`
                # at 6.0 -- in every match against a binary linked to libc: stem `c` is
                # not a recipe, so `_by_pn` fell back to FTS, and FTS tokenizes hyphens,
                # so `provides MATCH 'c'` matched the token `c` inside `aws-c-auth`.
                continue
            for rid in self._by_pn(stem) or self._by_pn("lib" + stem):
                self._hit(rid, 7, f"soname:{so}")
        for dep in sig.pkg_deps:
            cands = [dep, PY_MAP.get(dep, f"python3-{dep}"), f"python3-{dep.replace('_', '-')}",
                     f"lib{dep}", dep.replace("-", "")]
            seen = set()
            for c in cands:
                for rid in self._by_pn(c):
                    if rid not in seen:
                        seen.add(rid)
                        self._hit(rid, 6, f"dep:{dep}")
        for mod in sig.imports:
            for c in (f"python3-{mod}", f"python3-{mod.replace('_', '-')}", mod, f"nodejs-{mod}"):
                for rid in self._by_pn(c):
                    self._hit(rid, 4, f"import:{mod}")
        for tool in sig.tools:
            t = TOOL_MAP.get(tool, tool)
            for rid in self._by_pn(t):
                self._hit(rid, 5, f"tool:{tool}")
        self._fts(list(sig.lib_stems | sig.pkg_deps | sig.imports | sig.tools))
        return self.results()

    def results(self, limit=60):
        ids = sorted(self.scores, key=lambda i: -self.scores[i])[:limit]
        out = []
        for rid in ids:
            r = self.con.execute(
                "SELECT r.pn, r.pv, r.license, r.summary, r.homepage, r.filepath, l.name AS layer, "
                "l.license AS layer_license, l.vcs_url FROM recipes r JOIN layers l ON l.id=r.layer_id WHERE r.id=?",
                (rid,)).fetchone()
            if not r:
                continue
            out.append({
                "score": round(self.scores[rid], 1), "pn": r["pn"], "pv": r["pv"], "layer": r["layer"],
                "layer_license": r["layer_license"], "recipe_license": r["license"], "summary": r["summary"],
                "homepage": r["homepage"], "recipe": r["filepath"], "vcs_url": r["vcs_url"],
                "evidence": sorted(set(self.evidence[rid])),
            })
        return out


def emit_yocto(results, min_score=5):
    """Produce a bblayers list and a DEPENDS/RDEPENDS stub from ranked results."""
    layers, pns = {}, []
    seen = set()
    for r in results:
        if r["score"] < min_score or r["pn"] in seen:
            continue
        seen.add(r["pn"])
        pns.append(r["pn"])
        layers[r["layer"]] = r["vcs_url"]
    lines = ["# layers to add to bblayers.conf"]
    lines += [f"#   {n:28s} {u}" for n, u in layers.items()]
    lines += ["", "# candidate build-time deps (verify each; runtime ones go in RDEPENDS:${PN})",
              'DEPENDS += "\\']
    lines += [f"    {pn} \\" for pn in pns]
    lines += ['"']
    return "\n".join(lines)
