#!/usr/bin/env python3
"""tfctl -- SyMoNeuRaL trusted GPU firmware/stack control.

Scaffold gate: `inventory`, `verify` and `test --dry` are real and read-only.
`stage`, `promote` and `rollback` deliberately refuse to act and print the plan
they WOULD execute, because nothing in this system promotes itself.

Absolutely nothing here installs, signs, loads, unloads or replaces anything.
There is no modprobe, no rmmod, no dkms build, no initramfs write, no package
manager call, and no bootloader touch. `verify` does not even import torch --
trust checking must not itself create a CUDA context.

  tfctl inventory [--json]              read the live stack
  tfctl inventory --emit-manifest SLOT  write a measured manifest slot
  tfctl verify [--slot PRIMARY]         live stack vs manifest -> TRUSTED/...
  tfctl test [--dry]                    execution checks (dry by default)
  tfctl stage|promote|rollback          refuse; print the intended plan
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest" / "trusted-stack.json"
UPSTREAM = Path("/home/google/Symoneural/references/open-gpu-kernel-modules")

TRUSTED, UNTRUSTED, MISMATCH, UNKNOWN = "TRUSTED", "UNTRUSTED", "MISMATCH", "UNKNOWN"


# ----------------------------------------------------------------- helpers
def _run(argv: list[str], timeout: int = 20) -> str | None:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def _read(path: str | Path) -> str | None:
    try:
        return Path(path).read_text()
    except Exception:
        return None


def _sha256(path: str | Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# --------------------------------------------------------------- inventory
def inventory() -> dict:
    """Measure the live stack. Read-only; no CUDA context is created."""
    inv: dict = {"schema": 1}

    # 1. Linux kernel
    inv["kernel"] = {
        "release": (_run(["uname", "-r"]) or "").strip() or None,
        "version": (_run(["uname", "-v"]) or "").strip() or None,
        "arch": (_run(["uname", "-m"]) or "").strip() or None,
    }

    # 2. NVIDIA open kernel modules
    nvrm = _read("/proc/driver/nvidia/version") or ""
    m = re.search(r"NVIDIA UNIX (\S+) Kernel Module for (\S+)\s+(\S+)", nvrm)
    mods = {}
    for name in ("nvidia", "nvidia_uvm", "nvidia_drm", "nvidia_modeset"):
        v = _read(f"/sys/module/{name}/version")
        if v:
            mods[name] = v.strip()
    kmod_files = {}
    kr = inv["kernel"]["release"]
    if kr:
        base = Path(f"/lib/modules/{kr}")
        for p in sorted(base.rglob("nvidia*.ko*")):
            if "wmi" in p.name:            # unrelated platform driver
                continue
            kmod_files[p.name] = {"path": str(p), "size": p.stat().st_size,
                                  "sha256": _sha256(p)}
    inv["nvidia_kmd"] = {
        "nvrm_banner": nvrm.strip().splitlines()[0] if nvrm else None,
        "flavour": m.group(1) if m else None,          # "Open" vs proprietary
        "version": m.group(3) if m else None,
        "module_versions": mods,
        "modules": kmod_files,
        "taint": {n: (_read(f"/sys/module/{n}/taint") or "").strip() for n in mods},
    }

    # 3. GSP firmware
    q = _run(["nvidia-smi", "-q"]) or ""
    gsp = re.search(r"GSP Firmware Version\s*:\s*(\S+)", q)
    fw = {}
    for p in sorted(Path("/lib/firmware/nvidia").glob("*/gsp*.bin")) if Path("/lib/firmware/nvidia").exists() else []:
        fw[str(p)] = {"size": p.stat().st_size, "sha256": _sha256(p)}
    inv["gsp_firmware"] = {"version": gsp.group(1) if gsp else None, "blobs": fw}

    # 4. NVIDIA userspace driver
    libcuda = None
    for p in Path("/usr/lib/x86_64-linux-gnu").glob("libcuda.so.*"):
        if p.is_file() and re.match(r"libcuda\.so\.\d", p.name):
            libcuda = {"path": str(p), "size": p.stat().st_size, "sha256": _sha256(p)}
    drv = (_run(["nvidia-smi", "--query-gpu=driver_version",
                 "--format=csv,noheader"]) or "").strip() or None
    inv["nvidia_userspace"] = {"driver_version": drv, "libcuda": libcuda}

    # 5. CUDA runtime / toolkit
    smi = _run(["nvidia-smi"]) or ""
    umd = re.search(r"CUDA UMD Version:\s*([0-9.]+)", smi)
    nvcc = _run(["nvcc", "--version"]) or ""
    nvcc_v = re.search(r"release ([0-9.]+), V(\S+)", nvcc)
    inv["cuda"] = {
        "umd_version": umd.group(1) if umd else None,
        "nvcc_release": nvcc_v.group(1) if nvcc_v else None,
        "nvcc_build": nvcc_v.group(2) if nvcc_v else None,
    }

    # 6/7. GPU identity + SM
    fields = ("name,uuid,pci.bus_id,pci.device_id,pci.sub_device_id,"
              "vbios_version,compute_cap,memory.total")
    row = (_run(["nvidia-smi", f"--query-gpu={fields}",
                 "--format=csv,noheader"]) or "").strip()
    gpu = {}
    if row:
        vals = [v.strip() for v in row.splitlines()[0].split(", ")]
        gpu = dict(zip(fields.split(","), vals))
    inv["gpu"] = gpu
    cc = gpu.get("compute_cap")
    inv["sm"] = {"compute_cap": cc,
                 "arch": f"sm_{cc.replace('.', '')}" if cc else None}

    # 8. Secure Boot / module signing
    sb = _run(["mokutil", "--sb-state"]) or ""
    inv["secure_boot"] = {
        "state": sb.strip().splitlines()[0] if sb.strip() else None,
        "kernel_lockdown": (_read("/sys/kernel/security/lockdown") or "").strip() or None,
        # Signature extraction is NOT implemented -- see README "Unimplemented".
        "module_signatures": None,
    }

    # upstream source pin
    up = {"path": str(UPSTREAM), "present": UPSTREAM.exists()}
    if (UPSTREAM / ".git").exists():
        up["remote"] = (_run(["git", "-C", str(UPSTREAM), "remote", "get-url", "origin"]) or "").strip() or None
        up["commit"] = (_run(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"]) or "").strip() or None
        up["describe"] = (_run(["git", "-C", str(UPSTREAM), "describe", "--tags", "--always"]) or "").strip() or None
        dirty = _run(["git", "-C", str(UPSTREAM), "status", "--porcelain"])
        up["clean"] = (dirty is not None and dirty.strip() == "")
    vm = _read(UPSTREAM / "version.mk") or ""
    mv = re.search(r"NVIDIA_VERSION\s*=\s*(\S+)", vm)
    up["nvidia_version"] = mv.group(1) if mv else None
    inv["upstream"] = up

    # 10. optional higher-level runtimes. Recorded as metadata only -- these are
    # userspace Python packages, NOT NVIDIA kernel modules, and must never be
    # conflated with them. In particular Hugging Face `kernels` is a pip package
    # for fused model ops; it has nothing to do with the GPU KMD.
    inv["higher_level_runtimes"] = {
        "_note": ("userspace only; 'kernels' here would mean the Hugging Face pip "
                  "package, which is NOT an NVIDIA kernel module"),
        "torch": None, "torch_cuda": None, "triton": None,
    }
    return inv


def inventory_with_torch(inv: dict) -> dict:
    """Fill the torch fields. Separate on purpose: importing torch initialises
    CUDA, and `verify` must stay GPU-neutral."""
    py = "/home/google/.venvs/vllm/bin/python"
    out = _run([py, "-c",
                "import json,torch,importlib.metadata as md;"
                "print(json.dumps({'torch':torch.__version__,"
                "'torch_cuda':torch.version.cuda,"
                "'arch_list':torch.cuda.get_arch_list(),"
                "'triton':(md.version('triton') if md else None)}))"], timeout=180)
    if out:
        try:
            inv["higher_level_runtimes"].update(json.loads(out.strip().splitlines()[-1]))
        except Exception:
            pass
    return inv


# ------------------------------------------------------------------ verify
def _cmp(name: str, live, want) -> dict:
    if want is None or live is None:
        return {"check": name, "result": UNKNOWN, "live": live, "expected": want}
    return {"check": name, "result": TRUSTED if live == want else MISMATCH,
            "live": live, "expected": want}


def verify(slot: str = "PRIMARY") -> dict:
    if not MANIFEST.exists():
        return {"verdict": UNKNOWN, "error": f"no manifest at {MANIFEST}"}
    man = json.loads(MANIFEST.read_text())
    want = (man.get("slots") or {}).get(slot)
    if not want:
        return {"verdict": UNKNOWN, "error": f"slot {slot} is empty"}
    live = inventory()
    checks = [
        _cmp("KMD_VERSION_MATCH", live["nvidia_kmd"]["version"],
             want["nvidia_kmd"]["version"]),
        _cmp("GSP_VERSION_MATCH", live["gsp_firmware"]["version"],
             want["gsp_firmware"]["version"]),
        _cmp("USERSPACE_VERSION_MATCH", live["nvidia_userspace"]["driver_version"],
             want["nvidia_userspace"]["driver_version"]),
        _cmp("CUDA_VERSION_MATCH", live["cuda"]["umd_version"],
             want["cuda"]["umd_version"]),
        _cmp("KERNEL_RELEASE_MATCH", live["kernel"]["release"],
             want["kernel"]["release"]),
        _cmp("GPU_ID_MATCH", live["gpu"].get("uuid"), want["gpu"].get("uuid")),
        _cmp("GPU_PCI_MATCH", live["gpu"].get("pci.device_id"),
             want["gpu"].get("pci.device_id")),
        _cmp("VBIOS_MATCH", live["gpu"].get("vbios_version"),
             want["gpu"].get("vbios_version")),
        _cmp("SM_CAPABILITY_MATCH", live["sm"]["arch"], want["sm"]["arch"]),
        _cmp("UPSTREAM_COMMIT_MATCH", live["upstream"].get("commit"),
             want["upstream"].get("commit")),
    ]

    # module hashes, one entry per module
    lm, wm = live["nvidia_kmd"]["modules"], want["nvidia_kmd"]["modules"]
    bad = [n for n in wm if lm.get(n, {}).get("sha256") != wm[n]["sha256"]]
    missing = [n for n in wm if n not in lm]
    checks.append({
        "check": "MODULE_HASH_MATCH",
        "result": TRUSTED if (not bad and not missing and wm) else (UNKNOWN if not wm else MISMATCH),
        "modules_checked": len(wm), "mismatched": bad, "missing": missing,
    })

    # GSP blob hashes
    lf, wf = live["gsp_firmware"]["blobs"], want["gsp_firmware"]["blobs"]
    fbad = [n for n in wf if lf.get(n, {}).get("sha256") != wf[n]["sha256"]]
    checks.append({
        "check": "GSP_BLOB_HASH_MATCH",
        "result": TRUSTED if (wf and not fbad) else (UNKNOWN if not wf else MISMATCH),
        "blobs_checked": len(wf), "mismatched": fbad,
    })

    # NVIDIA's own coupling rule: KMD, GSP and userspace ship as one release and
    # must be the same version. This is the check that catches a partial upgrade.
    trio = {live["nvidia_kmd"]["version"], live["gsp_firmware"]["version"],
            live["nvidia_userspace"]["driver_version"]}
    trio.discard(None)
    checks.append({
        "check": "RELEASE_TRIPLE_COHERENT",
        "result": TRUSTED if len(trio) == 1 else (UNKNOWN if not trio else MISMATCH),
        "versions": sorted(trio),
        "note": "NVIDIA requires KMD == GSP firmware == userspace driver release",
    })

    # not implemented yet -- declared, never silently skipped
    for name in ("MODULE_SIGNATURE_MATCH", "SM120_EXECUTION_PASS",
                 "CUDA_SAMPLE_PASS", "PYTORCH_SM120_PASS"):
        checks.append({"check": name, "result": UNKNOWN, "note": "not implemented in this gate"})

    results = [c["result"] for c in checks]
    if MISMATCH in results:
        verdict = MISMATCH
    elif all(r == TRUSTED for r in results):
        verdict = TRUSTED
    else:
        verdict = UNKNOWN          # some checks could not be evaluated
    return {"slot": slot, "verdict": verdict, "checks": checks}


# ------------------------------------------------------- refusing verbs
def _refuse(verb: str, plan: list[str]) -> int:
    print(f"REFUSED: `{verb}` does not act in the scaffold gate.")
    print("Nothing promotes itself. The plan it would execute, for review:")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")
    print("\nNo module was installed, loaded, unloaded, signed or replaced.")
    return 3


def main() -> int:
    ap = argparse.ArgumentParser(prog="tfctl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inventory"); p.add_argument("--json", action="store_true")
    p.add_argument("--with-torch", action="store_true")
    p.add_argument("--emit-manifest", metavar="SLOT")

    p = sub.add_parser("verify"); p.add_argument("--slot", default="PRIMARY")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("test"); p.add_argument("--dry", action="store_true", default=True)
    for verb in ("stage", "promote", "rollback"):
        sub.add_parser(verb)

    a = ap.parse_args()

    if a.cmd == "inventory":
        inv = inventory()
        if a.with_torch or a.emit_manifest:
            inv = inventory_with_torch(inv)
        if a.emit_manifest:
            man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {
                "schema": 1, "slots": {"PRIMARY": None, "CANDIDATE": None, "RECOVERY": None},
            }
            inv["promotion"] = {"state": "MEASURED", "promoted_by": None,
                                "promoted_at": None, "rollback_source": None}
            man.setdefault("slots", {})[a.emit_manifest] = inv
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(json.dumps(man, indent=2, sort_keys=False) + "\n")
            print(f"wrote slot {a.emit_manifest} -> {MANIFEST}")
            return 0
        print(json.dumps(inv, indent=2) if a.json else
              json.dumps(inv, indent=2))
        return 0

    if a.cmd == "verify":
        r = verify(a.slot)
        if a.json:
            print(json.dumps(r, indent=2)); return 0
        print(f"slot    : {r.get('slot')}")
        print(f"VERDICT : {r['verdict']}")
        if "error" in r:
            print(f"error   : {r['error']}"); return 1
        for c in r["checks"]:
            extra = ""
            if c["result"] == MISMATCH:
                extra = f"   live={c.get('live')!r} expected={c.get('expected')!r}"
                if c.get("mismatched"):
                    extra = f"   mismatched={c['mismatched']}"
            elif c.get("note"):
                extra = f"   ({c['note']})"
            print(f"  {c['result']:9s} {c['check']}{extra}")
        return 0 if r["verdict"] == TRUSTED else 1

    if a.cmd == "test":
        return _refuse("test", [
            "run tools/checks: SM120_EXECUTION_PASS via a child torch process",
            "run the prebuilt CUDA vectorAdd sample and assert VRAM returns to baseline",
            "record results into the CANDIDATE slot's validation block",
            "NOTE: these are execution checks, not mutations -- they are gated here "
            "only because this scaffold gate forbids running them",
        ])

    if a.cmd == "stage":
        return _refuse("stage", [
            "clone/checkout NVIDIA/open-gpu-kernel-modules at a pinned commit",
            "build kernel-open modules against the running kernel",
            "record source tree hash, build flags and module hashes",
            "write the result into the CANDIDATE slot -- WITHOUT installing it",
        ])

    if a.cmd == "promote":
        return _refuse("promote", [
            "require verify(CANDIDATE) == TRUSTED",
            "require all execution checks PASS",
            "copy the current PRIMARY slot into RECOVERY",
            "install + sign the candidate modules, rebuild initramfs",
            "require an explicit human confirmation token",
            "reboot and re-verify before marking PRIMARY",
        ])

    if a.cmd == "rollback":
        return _refuse("rollback", [
            "read the RECOVERY slot",
            "restore its modules, GSP firmware and userspace driver",
            "rebuild initramfs and re-verify",
            "mark PRIMARY = RECOVERY only after a passing verify",
        ])

    return 2


if __name__ == "__main__":
    sys.exit(main())
