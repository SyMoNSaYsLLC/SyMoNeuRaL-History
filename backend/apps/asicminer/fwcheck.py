#!/usr/bin/env python3
"""Pre-flight a Bitmain firmware package the way the miner's own `runme.sh` will.

Flashing a package that fails verification costs an hour and, at worst, a rig. The check
that decides it is a 40-line shell script *inside the package*, and it runs on the miner
after the upload -- by which point you are already committed. This runs the same checks
here, before anything is pushed, and reports the exact exit code `runme.sh` would produce.

## The package format, confirmed against the real archives

A signed Antminer package is a tarball of seven files:

    cert.pem  cert.pem.sig  fw.tar.gz  fw.tar.gz.sig  runme.sh  runme.sh.sig  version_number

`cert.pem` is a bare RSA public key -- **not** an X.509 certificate, despite the name and
the `.pem` extension, so `openssl x509` on it fails and that failure means nothing. The
signatures are raw RSA over SHA-256; at RSA-4096 they are 512 bytes.

## What runme.sh actually checks, in order, with its own exit codes

    1  cert.pem missing
    2  cert.pem.sig missing
    3  cert.pem fails to verify against /etc/bitmain-pub.pem   <-- CONDITIONAL, see below
    4  fw.tar.gz.sig missing
    5  fw.tar.gz fails to verify against cert.pem

**Step 3 only runs `if [ -e /etc/bitmain-pub.pem ]`.** That conditional is the whole story
for custom firmware: a miner that still has Bitmain's public key on disk requires the
package's cert to be signed by Bitmain, so a self-signed package is rejected. Custom
firmware images generally do not ship that file, so on a rig already running one, step 3 is
skipped entirely -- but **step 5 always runs**, against the `cert.pem` inside the package
itself. So a repackager self-signs with their own key and the chain is internally
consistent.

The practical consequence, and the reason this tool reports the two separately: step 5 is
checkable here with certainty, and step 3 depends on the state of the target rig. Reporting
one number for both would be a guess presented as a verdict.

    python3 fwcheck.py <package.tar.gz> [--bitmain-pub /path/to/bitmain-pub.pem]

Prints JSON. Exit 0 means the tool ran, not that the package passed -- read `would_pass`.
Nothing is extracted outside a temporary directory and nothing is ever executed: the inner
`runme.sh` is read and reported on, never run.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

REQUIRED = ["cert.pem", "cert.pem.sig", "fw.tar.gz", "fw.tar.gz.sig"]
EXPECTED = REQUIRED + ["runme.sh", "runme.sh.sig", "version_number"]

# runme.sh's own exit codes, so the report speaks the miner's language rather than ours.
CODES = {
    1: "cert.pem missing from the package",
    2: "cert.pem.sig missing from the package",
    3: "cert.pem is not signed by Bitmain's key (only checked on rigs that still have "
       "/etc/bitmain-pub.pem)",
    4: "fw.tar.gz.sig missing from the package",
    5: "fw.tar.gz does not verify against the package's own cert.pem",
}


def _openssl_verify(pub: pathlib.Path, sig: pathlib.Path, payload: pathlib.Path) -> bool:
    """One `openssl dgst -sha256 -verify`, exactly as runme.sh invokes it."""
    if not (pub.is_file() and sig.is_file() and payload.is_file()):
        return False
    r = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(pub), "-signature", str(sig),
         str(payload)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def _safe_extract(pkg: pathlib.Path, dest: pathlib.Path) -> list[str]:
    """Extract, refusing any member that would escape `dest`.

    A firmware package is an untrusted archive from the internet. `tar` happily writes
    `../../etc/cron.d/x` if a member says so, and this tool runs as whoever is checking the
    file. Python 3.12+ has `filter='data'` for exactly this; the manual check keeps the
    behaviour identical on older interpreters rather than depending on the version.
    """
    names = []
    with tarfile.open(pkg, "r:*") as tf:
        for m in tf.getmembers():
            p = (dest / m.name).resolve()
            if not str(p).startswith(str(dest.resolve()) + "/"):
                raise ValueError(f"archive member escapes the extraction directory: {m.name!r}")
            if m.issym() or m.islnk():
                raise ValueError(f"archive contains a link, refusing: {m.name!r}")
            names.append(m.name)
        try:
            tf.extractall(dest, filter="data")           # py3.12+
        except TypeError:
            tf.extractall(dest)                          # names already validated above
    return names


def check(pkg: pathlib.Path, bitmain_pub: pathlib.Path | None = None) -> dict:
    out = {
        "package": pkg.name,
        "bytes": pkg.stat().st_size if pkg.is_file() else None,
        "contents": [], "missing": [], "unexpected": [],
        "version": None,
        "fw_verifies_against_cert": None,   # runme.sh step 5 -- always runs on the rig
        "cert_signed_by_bitmain": None,     # step 3 -- only on rigs with the Bitmain key
        "would_pass": None,
        "would_exit": None,
        "verdict": "",
        "notes": [],
        "error": None,
    }
    if not pkg.is_file():
        out["error"] = f"no such file: {pkg}"
        return out
    if not shutil.which("openssl"):
        out["error"] = "openssl not on PATH; cannot verify signatures"
        return out

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fwcheck-"))
    try:
        try:
            out["contents"] = sorted(_safe_extract(pkg, tmp))
        except (tarfile.TarError, ValueError) as e:
            out["error"] = f"not a readable tar package: {e}"
            return out

        out["missing"] = [f for f in REQUIRED if not (tmp / f).is_file()]
        out["unexpected"] = [f for f in out["contents"] if f not in EXPECTED]
        vn = tmp / "version_number"
        if vn.is_file():
            out["version"] = vn.read_text().strip()

        # Missing files short-circuit, in runme.sh's own order.
        for name, code in (("cert.pem", 1), ("cert.pem.sig", 2), ("fw.tar.gz.sig", 4)):
            if not (tmp / name).is_file():
                out.update(would_pass=False, would_exit=code, verdict=CODES[code])
                return out
        if not (tmp / "fw.tar.gz").is_file():
            out.update(would_pass=False, would_exit=5,
                       verdict="fw.tar.gz missing from the package")
            return out

        # Step 5 -- the one that always runs, so the one we can be certain about.
        out["fw_verifies_against_cert"] = _openssl_verify(
            tmp / "cert.pem", tmp / "fw.tar.gz.sig", tmp / "fw.tar.gz")

        # Step 3 -- only meaningful with Bitmain's public key to hand.
        if bitmain_pub and bitmain_pub.is_file():
            out["cert_signed_by_bitmain"] = _openssl_verify(
                bitmain_pub, tmp / "cert.pem.sig", tmp / "cert.pem")
        else:
            out["notes"].append(
                "No Bitmain public key supplied, so step 3 was not evaluated. On a rig that "
                "still has /etc/bitmain-pub.pem an unsigned or self-signed cert exits 3; on "
                "a rig already running custom firmware that file is usually absent and the "
                "step is skipped. Pass --bitmain-pub to check it.")

        if not out["fw_verifies_against_cert"]:
            out.update(would_pass=False, would_exit=5, verdict=CODES[5])
        elif out["cert_signed_by_bitmain"] is False:
            out.update(would_pass=False, would_exit=3, verdict=CODES[3])
        else:
            out["would_pass"] = True
            out["would_exit"] = 0
            out["verdict"] = ("passes every check this package can be judged on"
                             + ("" if out["cert_signed_by_bitmain"]
                                else "; step 3 depends on the target rig — see notes"))
        if out["unexpected"]:
            out["notes"].append(
                f"Package carries files runme.sh does not expect: {out['unexpected']}. Not "
                "fatal — runme.sh ignores them — but worth knowing what you are flashing.")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-flight a Bitmain firmware package.")
    ap.add_argument("package", type=pathlib.Path)
    ap.add_argument("--bitmain-pub", type=pathlib.Path, default=None,
                    help="Bitmain public key, to evaluate runme.sh step 3 as well")
    a = ap.parse_args()
    print(json.dumps(check(a.package, a.bitmain_pub), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
