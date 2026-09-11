"""Capacity Lab core: run identity, isolation, continuous telemetry, statistics.

Nothing in this module fabricates a number. Every value is either read from the
machine or computed from values read from the machine, and anything that cannot
be proven is returned as NOT_AVAILABLE rather than guessed or zero-filled.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1
NOT_AVAILABLE = "NOT AVAILABLE"

# Every synthetic record this harness creates carries this prefix. It is the
# isolation boundary: nothing without it belongs to a benchmark, and nothing
# with it is a real customer.
BENCH_PREFIX = "BENCH-"
SYNTHETIC_MARK = "symoneural-capacity-lab"

REPORT_DIR = Path(os.environ.get(
    "CAPACITY_LAB_REPORTS",
    "/home/google/experiments/capacity-lab/reports"))


# ----------------------------------------------------------------- run identity
def new_run_id(now: datetime, existing: list[str] | None = None) -> str:
    """BENCH-YYYYMMDD-NNNN, sequential within the day.

    `now` is injected rather than read here so a run id is reproducible in tests
    and so the caller owns the clock.
    """
    day = now.strftime("%Y%m%d")
    seq = 0
    for r in (existing or []):
        m = re.fullmatch(rf"{BENCH_PREFIX}{day}-(\d{{4}})", r)
        if m:
            seq = max(seq, int(m.group(1)))
    return f"{BENCH_PREFIX}{day}-{seq + 1:04d}"


def is_benchmark_id(value: str) -> bool:
    return bool(re.fullmatch(rf"{BENCH_PREFIX}\d{{8}}-\d{{4}}", value or ""))


def known_run_ids(report_dir: Path | None = None) -> list[str]:
    d = report_dir or REPORT_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob(f"{BENCH_PREFIX}*.json"))


# ----------------------------------------------------------------- statistics
def percentiles(values: list[float]) -> dict:
    """p50/p95/p99 plus min/max/mean. Empty input yields NOT AVAILABLE, never 0."""
    if not values:
        return {k: NOT_AVAILABLE for k in ("n", "min", "mean", "p50", "p95", "p99", "max")}
    s = sorted(values)

    def q(p: float) -> float:
        # nearest-rank; exact and defensible on small samples, where interpolation
        # would invent a value that no session actually experienced.
        idx = max(0, min(len(s) - 1, int(round(p * len(s) + 0.5)) - 1))
        return s[idx]

    return {"n": len(s), "min": round(s[0], 3), "mean": round(statistics.fmean(s), 3),
            "p50": round(q(0.50), 3), "p95": round(q(0.95), 3),
            "p99": round(q(0.99), 3), "max": round(s[-1], 3)}


def summarise(samples: list[float], unit: str) -> dict:
    if not samples:
        return {"unit": unit, "n": 0, "min": NOT_AVAILABLE,
                "avg": NOT_AVAILABLE, "max": NOT_AVAILABLE}
    return {"unit": unit, "n": len(samples),
            "min": round(min(samples), 2),
            "avg": round(statistics.fmean(samples), 2),
            "max": round(max(samples), 2)}


# ----------------------------------------------------------------- telemetry
@dataclass
class Sampler:
    """Continuous timestamped sampling for the duration of a run.

    Deliberately a sampler and not a snapshot: a single nvidia-smi reading is not
    a peak, and calling it one is how a capacity claim becomes fiction.
    """
    interval: float = 0.25
    samples: list[dict] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _err: list[str] = field(default_factory=list)

    def _read_gpu(self) -> dict | None:
        try:
            q = ("memory.used,memory.total,utilization.gpu,power.draw,"
                 "temperature.gpu")
            out = subprocess.run(
                ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10)
            if out.returncode != 0:
                return None
            v = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",")]
            apps = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10)
            pids = [int(p.strip()) for p in apps.stdout.split() if p.strip().isdigit()]
            return {"vram_used_mib": int(v[0]), "vram_total_mib": int(v[1]),
                    "util_pct": int(v[2]), "power_w": float(v[3]),
                    "temp_c": int(v[4]), "compute_pids": pids}
        except Exception as exc:                      # noqa: BLE001
            self._err.append(f"gpu: {type(exc).__name__}")
            return None

    def _read_system(self) -> dict:
        d: dict = {}
        try:
            with open("/proc/loadavg") as fh:
                p = fh.read().split()
            d["load1"], d["load5"], d["load15"] = float(p[0]), float(p[1]), float(p[2])
        except Exception:
            pass
        try:
            mem = {}
            with open("/proc/meminfo") as fh:
                for line in fh:
                    k, _, v = line.partition(":")
                    mem[k] = int(v.split()[0])          # kB
            total, avail = mem.get("MemTotal", 0), mem.get("MemAvailable", 0)
            d["ram_total_mib"] = round(total / 1024, 1)
            d["ram_used_mib"] = round((total - avail) / 1024, 1)
            st, sf = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
            d["swap_used_mib"] = round((st - sf) / 1024, 1)
        except Exception:
            pass
        try:
            d["cpu_pct"] = self._cpu_pct()
        except Exception:
            pass
        return d

    _prev_cpu: tuple | None = None

    def _cpu_pct(self) -> float | None:
        with open("/proc/stat") as fh:
            parts = [int(x) for x in fh.readline().split()[1:]]
        idle = parts[3] + parts[4]
        total = sum(parts)
        prev = self._prev_cpu
        self._prev_cpu = (idle, total)
        if prev is None:
            return None
        di, dt = idle - prev[0], total - prev[1]
        if dt <= 0:
            return None
        return round(100.0 * (1.0 - di / dt), 1)

    def _loop(self) -> None:
        while not self._stop.is_set():
            rec = {"t": time.time(), "mono": time.monotonic()}
            gpu = self._read_gpu()
            if gpu:
                rec["gpu"] = gpu
            rec["sys"] = self._read_system()
            self.samples.append(rec)
            self._stop.wait(self.interval)

    def start(self) -> "Sampler":
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> "Sampler":
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return self

    # -- derived statistics, all MEASURED from the sample series ---------------
    def statistics(self) -> dict:
        g = [s["gpu"] for s in self.samples if "gpu" in s]
        y = [s["sys"] for s in self.samples if s.get("sys")]
        span = (self.samples[-1]["mono"] - self.samples[0]["mono"]) if len(self.samples) > 1 else 0.0
        out = {
            "sample_count": len(self.samples),
            "sample_interval_s": self.interval,
            "span_s": round(span, 2),
            "errors": sorted(set(self._err)) or None,
        }
        # A one- or two-sample series is a snapshot wearing a distribution's clothes.
        # Say so in the report rather than letting min==avg==max read as a measured
        # range. This fires on very short runs, where the run ends before the
        # sampler can characterise anything.
        if len(self.samples) < 3:
            out["series_warning"] = (
                f"only {len(self.samples)} sample(s) over {span:.2f}s -- too short to "
                f"characterise a distribution. Treat min/avg/max as a snapshot, not a range.")
            out["series_sufficient"] = False
        else:
            out["series_sufficient"] = True
        if g:
            out["gpu"] = {
                "vram_used_mib": summarise([x["vram_used_mib"] for x in g], "MiB"),
                "vram_total_mib": g[0]["vram_total_mib"],
                "utilization_pct": summarise([x["util_pct"] for x in g], "%"),
                "power_w": summarise([x["power_w"] for x in g], "W"),
                "temperature_c": summarise([x["temp_c"] for x in g], "C"),
                "max_simultaneous_compute_apps": max(len(x["compute_pids"]) for x in g),
                "compute_pids_seen": sorted({p for x in g for p in x["compute_pids"]}),
            }
        else:
            out["gpu"] = NOT_AVAILABLE
        if y:
            cpu = [x["cpu_pct"] for x in y if x.get("cpu_pct") is not None]
            out["system"] = {
                "cpu_pct": summarise(cpu, "%"),
                "load1": summarise([x["load1"] for x in y if "load1" in x], "load"),
                "ram_used_mib": summarise([x["ram_used_mib"] for x in y if "ram_used_mib" in x], "MiB"),
                "ram_total_mib": y[0].get("ram_total_mib", NOT_AVAILABLE),
                "swap_used_mib": summarise([x["swap_used_mib"] for x in y if "swap_used_mib" in x], "MiB"),
                "disk_io": NOT_AVAILABLE,      # not instrumented in slice 1
                "network_io": NOT_AVAILABLE,   # not instrumented in slice 1
            }
        else:
            out["system"] = NOT_AVAILABLE
        return out


# ----------------------------------------------------------------- host identity
def host_identity() -> dict:
    def _first(path: str, pat: str) -> str:
        try:
            for line in open(path):
                if line.startswith(pat):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return NOT_AVAILABLE

    def _smi(q: str) -> str:
        try:
            r = subprocess.run(["nvidia-smi", f"--query-gpu={q}",
                                "--format=csv,noheader"], capture_output=True,
                               text=True, timeout=10)
            return r.stdout.strip().splitlines()[0].strip() if r.returncode == 0 else NOT_AVAILABLE
        except Exception:
            return NOT_AVAILABLE

    try:
        ram = round(int([l for l in open("/proc/meminfo") if l.startswith("MemTotal")][0]
                        .split()[1]) / 1024 / 1024, 1)
    except Exception:
        ram = NOT_AVAILABLE
    return {
        "hostname": os.uname().nodename,
        "kernel": os.uname().release,
        "cpu_model": _first("/proc/cpuinfo", "model name"),
        "cpu_threads": os.cpu_count(),
        "system_ram_gib": ram,
        "gpu_model": _smi("name"),
        "gpu_vram_total_mib": _smi("memory.total"),
        "gpu_driver": _smi("driver_version"),
    }


def repo_commit(repo: str = "/home/google/Symoneural") -> dict:
    def g(*a) -> str:
        try:
            r = subprocess.run(["git", "-C", repo, *a], capture_output=True,
                               text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else NOT_AVAILABLE
        except Exception:
            return NOT_AVAILABLE
    return {"repo": repo, "commit": g("rev-parse", "HEAD"),
            "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_tracked_files": len([x for x in g("status", "--porcelain",
                                                     "--untracked-files=no").splitlines() if x])}
