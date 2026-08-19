"""A service that reports a real reading, or says it cannot.

The module form: no class, no decorator, just a module-level `apply`. This is what the loader's
`use: apps.symoneuralexp.plugins.gpu` resolves to.

It is here because every other example in this directory is synthetic, and a plugin runtime
whose examples all invent their data teaches the wrong habit. This one shells out to
`nvidia-smi` and to `scripts/gpu-governor.sh status`, and when either is absent it returns
`available: False` rather than a plausible number. CLAUDE.md's rule -- no decorative readings,
where there is no measurement show nothing -- applies inside a plugin exactly as it does on a
page.

It takes no GPU lease. Reading VRAM is not using the card, and a plugin that acquires the mutex
for the lifetime of a mount is the exact failure that file warns about.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

name = "gpu"
schema = {"timeout": (float, 3.0)}

_ROOT = pathlib.Path(__file__).resolve().parents[4]      # .../Symoneural


class GPU:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def vram(self) -> dict:
        smi = shutil.which("nvidia-smi")
        if smi is None:
            return {"available": False, "reason": "nvidia-smi not on PATH"}
        try:
            out = subprocess.run(
                [smi, "--query-gpu=memory.used,memory.total,name",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=self.timeout, check=True).stdout
        except (subprocess.SubprocessError, OSError) as exc:
            return {"available": False, "reason": str(exc)}
        used, total, model = (part.strip() for part in out.strip().splitlines()[0].split(","))
        return {"available": True, "used_mib": int(used), "total_mib": int(total),
                "model": model, "source": "measured"}

    def lease(self) -> dict:
        governor = _ROOT / "scripts" / "gpu-governor.sh"
        if not governor.exists():
            return {"available": False, "reason": f"no governor at {governor}"}
        try:
            out = subprocess.run([str(governor), "status"], capture_output=True, text=True,
                                 timeout=self.timeout)
        except (subprocess.SubprocessError, OSError) as exc:
            return {"available": False, "reason": str(exc)}
        return {"available": True, "text": out.stdout.strip(), "rc": out.returncode}


def apply(ctx, config):
    ctx.provide("gpu", GPU(config["timeout"]))
