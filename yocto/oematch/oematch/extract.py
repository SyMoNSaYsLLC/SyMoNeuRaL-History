"""Fingerprint an artifact into searchable signals.

Supported: .deb, .tar(.gz|.xz|.bz2|.zst), .zip, .whl, .AppImage, bare ELF, directories.
Signals are the same things `apt`, `ldd`, `readelf`, and `strings` already expose.
There is deliberately no disassembly or decompilation stage.
"""
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

KNOWN_TOOLS = {
    "ffmpeg", "ffprobe", "gst-launch-1.0", "git", "curl", "wget", "rsync", "ssh", "scp", "openssl",
    "python3", "python", "node", "npm", "npx", "bun", "deno", "rg", "ripgrep", "fd", "fzf", "jq",
    "yq", "sqlite3", "psql", "mysql", "redis-cli", "docker", "podman", "systemctl", "journalctl",
    "dbus-send", "busctl", "gpg", "tar", "xz", "zstd", "unzip", "7z", "make", "cmake", "ninja",
    "gcc", "clang", "rustc", "cargo", "go", "java", "mvn", "gradle", "qemu-system-x86_64",
    "nmcli", "iw", "ip", "iptables", "nft", "ethtool", "udevadm", "mount", "losetup", "mkfs.ext4",
    "v4l2-ctl", "alsamixer", "aplay", "pactl", "pw-cli", "wpa_supplicant", "hostapd", "dnsmasq",
    "nginx", "haproxy", "mosquitto_pub", "mosquitto_sub", "avahi-browse", "bluetoothctl",
}
SONAME_RE = re.compile(r"^lib([A-Za-z0-9_+\-.]+?)(?:-[0-9.]+)?\.so(?:\.[0-9]+)*$")
URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}")
PYIMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", re.M)
JSIMPORT_RE = re.compile(r"""(?:require\(|from\s+|import\s+)['"]([@A-Za-z0-9_\-/\.]+)['"]""")
ELF_MAGIC = b"\x7fELF"


@dataclass
class Signals:
    source: str
    kind: str = ""
    pkg_deps: set = field(default_factory=set)      # dpkg/pip/npm/cargo dep names
    sonames: set = field(default_factory=set)       # libfoo.so.N
    lib_stems: set = field(default_factory=set)     # foo
    tools: set = field(default_factory=set)         # external binaries referenced
    urls: set = field(default_factory=set)
    imports: set = field(default_factory=set)       # python/js module names
    binaries: set = field(default_factory=set)      # ELF files found inside
    file_names: set = field(default_factory=set)
    strings_sample: list = field(default_factory=list)

    def to_json(self):
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, set):
                d[k] = sorted(v)
        return json.dumps(d, indent=2)


# ---------------------------------------------------------------- helpers

def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120).stdout
    except Exception:
        return ""


def _is_elf(p: Path):
    try:
        with open(p, "rb") as f:
            return f.read(4) == ELF_MAGIC
    except Exception:
        return False


def _elf_needed(p: Path):
    out = _run(["readelf", "-d", str(p)])
    return set(re.findall(r"Shared library: \[([^\]]+)\]", out))


def _strings(p: Path, minlen=6, cap=20000):
    out = _run(["strings", "-n", str(minlen), str(p)])
    return out.splitlines()[:cap]


def _norm_dep(name: str):
    name = name.strip().split(" ")[0].split("(")[0].split(":")[0]
    name = re.sub(r"(-dev|-dbg|-doc|-bin|-common|-data)$", "", name)
    name = re.sub(r"^(lib)?(.+?)([0-9.]+)?$", r"\2", name) if name.startswith("lib") else name
    return name.lower()


def _soname_stem(soname: str):
    m = SONAME_RE.match(soname)
    return m.group(1).lower() if m else soname.lower()


def _harvest_strings(sig: Signals, lines):
    for s in lines:
        sb = s.encode(errors="ignore")
        for u in URL_RE.findall(sb):
            sig.urls.add(u.decode(errors="ignore").rstrip(").,;'\""))
        st = s.strip()
        if st in KNOWN_TOOLS:
            sig.tools.add(st)
        else:
            head = st.split(" ")[0].rsplit("/", 1)[-1]
            if head in KNOWN_TOOLS:
                sig.tools.add(head)
        if SONAME_RE.match(st):
            sig.sonames.add(st)
    # keep a sample of "interesting" strings for manual review / embeddings later
    keep = [s for s in lines if 12 <= len(s) <= 120 and " " in s and not s.startswith(("_", "."))]
    sig.strings_sample = keep[:300]


# ---------------------------------------------------------------- per-type

def _scan_dir(sig: Signals, root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        sig.file_names.add(p.name)
        name = p.name.lower()
        if name == "requirements.txt" or name.startswith("requirements"):
            for ln in p.read_text(errors="replace").splitlines():
                ln = ln.split("#")[0].strip()
                if ln and not ln.startswith("-"):
                    sig.pkg_deps.add(re.split(r"[<>=!~\[; ]", ln)[0].lower())
        elif name == "pyproject.toml":
            txt = p.read_text(errors="replace")
            for m in re.finditer(r'^\s*"([A-Za-z0-9_\-\.]+)[^"]*",?\s*$', txt, re.M):
                sig.pkg_deps.add(m.group(1).lower())
        elif name == "package.json":
            try:
                j = json.loads(p.read_text(errors="replace"))
                for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    sig.pkg_deps.update(map(str.lower, (j.get(k) or {}).keys()))
            except Exception:
                pass
        elif name == "cargo.toml":
            txt = p.read_text(errors="replace")
            for m in re.finditer(r"^\s*([A-Za-z0-9_\-]+)\s*=", txt, re.M):
                sig.pkg_deps.add(m.group(1).lower())
        elif name == "go.mod":
            for m in re.finditer(r"^\s*([a-z0-9\.\-]+/[A-Za-z0-9_\./\-]+)\s+v", p.read_text(errors="replace"), re.M):
                sig.pkg_deps.add(m.group(1).lower())
        elif name.endswith(".py"):
            for a, b in PYIMPORT_RE.findall(p.read_text(errors="replace")):
                sig.imports.add((a or b).split(".")[0].lower())
        elif name.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")):
            for mod in JSIMPORT_RE.findall(p.read_text(errors="replace")):
                if not mod.startswith("."):
                    sig.imports.add(mod.split("/")[0] if not mod.startswith("@") else "/".join(mod.split("/")[:2]))
        elif _is_elf(p):
            sig.binaries.add(rel)
            sig.sonames.update(_elf_needed(p))
            _harvest_strings(sig, _strings(p))
    # control file if present (extracted deb)
    ctrl = root / "DEBIAN" / "control"
    if ctrl.exists():
        _parse_control(sig, ctrl.read_text(errors="replace"))


def _parse_control(sig: Signals, text: str):
    for fld in ("Depends", "Pre-Depends", "Recommends"):
        m = re.search(rf"^{fld}:\s*(.+)$", text, re.M)
        if m:
            for d in m.group(1).split(","):
                for alt in d.split("|"):
                    sig.pkg_deps.add(_norm_dep(alt))
    m = re.search(r"^Homepage:\s*(\S+)", text, re.M)
    if m:
        sig.urls.add(m.group(1))


def _scan_deb(sig: Signals, p: Path, tmp: Path):
    sig.kind = "deb"
    _parse_control(sig, _run(["dpkg-deb", "-f", str(p)]))
    out = tmp / "deb"
    out.mkdir()
    subprocess.run(["dpkg-deb", "-R", str(p), str(out)], check=False, capture_output=True)
    _scan_dir(sig, out)


def _scan_archive(sig: Signals, p: Path, tmp: Path):
    out = tmp / "arch"
    out.mkdir()
    if zipfile.is_zipfile(p):
        sig.kind = "wheel" if p.suffix == ".whl" else "zip"
        with zipfile.ZipFile(p) as z:
            z.extractall(out)
        for meta in out.rglob("METADATA"):
            for m in re.finditer(r"^Requires-Dist:\s*([A-Za-z0-9_\-\.]+)", meta.read_text(errors="replace"), re.M):
                sig.pkg_deps.add(m.group(1).lower())
    else:
        sig.kind = "tar"
        with tarfile.open(p) as t:
            t.extractall(out, filter="data")
    _scan_dir(sig, out)


def _scan_elf(sig: Signals, p: Path):
    sig.kind = "elf"
    sig.binaries.add(p.name)
    sig.sonames.update(_elf_needed(p))
    _harvest_strings(sig, _strings(p))


# ---------------------------------------------------------------- entry

def fingerprint(target: str) -> Signals:
    p = Path(target).expanduser().resolve()
    sig = Signals(source=str(p))
    with tempfile.TemporaryDirectory(prefix="oematch-") as td:
        tmp = Path(td)
        if p.is_dir():
            sig.kind = "dir"
            _scan_dir(sig, p)
        elif p.suffix == ".deb":
            _scan_deb(sig, p, tmp)
        elif p.suffix in (".whl", ".zip") or tarfile.is_tarfile(p):
            _scan_archive(sig, p, tmp)
        elif _is_elf(p):
            _scan_elf(sig, p)
        else:
            raise SystemExit(f"unsupported artifact: {p}")
    sig.lib_stems = {_soname_stem(s) for s in sig.sonames}
    sig.pkg_deps = {d for d in sig.pkg_deps if d and len(d) > 1}
    return sig
