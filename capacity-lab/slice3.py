#!/usr/bin/env python3
"""Slice 3: adaptive full-server limit finder.

Three separable questions, reported separately because they have three
different answers:

    FUNCTIONAL CAPACITY   highest concurrency where every session completes
    ENGINEERING CAPACITY  highest concurrency inside the FROZEN Slice 2 criteria
    HARD FAILURE          first concurrency with an objective failure

Slice 2 measured through 10 and found the binding constraint was queueing at a
single AI worker, not GPU compute or VRAM. Slice 3 pushes past 10 to find where
the machine actually stops, and it is built to notice three ways the answer can
be a lie:

  * The load generator runs on this host. Above some concurrency the harness is
    itself a first-order consumer and the number stops being a server limit.
  * Requested concurrency is not achieved concurrency. Releasing 128 threads on
    a barrier does not mean 128 sessions ran at once, and a level that did not
    achieve its concurrency may not support a claim at that number.
  * The server admits a bounded number of concurrent sync handlers. Above that
    bound, arrivals at the AI queue are staggered by HTTP admission rather than
    by the AI queue, which makes queue depth read LOWER than the concurrency.
    That is distortion, not headroom.

Criteria are the ones frozen in Slice 2. They are not re-frozen here: the
corrected 480-session AI-OFF re-measurement is reported as a measurement-quality
delta alongside them, never substituted for them.
"""

from __future__ import annotations

import glob
import json
import math
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capacity_lab.core import (NOT_AVAILABLE, Sampler, host_identity,  # noqa: E402
                               known_run_ids, new_run_id, percentiles,
                               repo_commit, REPORT_DIR)
from capacity_lab import lifecycle                                     # noqa: E402
from capacity_lab.harness import _legacy_engine_pids                   # noqa: E402
from capacity_lab.players import NullPlayer                            # noqa: E402
from capacity_lab.scenario import LifecycleScenario, SessionResult     # noqa: E402

BASE = "http://127.0.0.1:8811"
SAMPLE_INTERVAL = 0.05

# Constant total sessions per level. Slice 2 used constant DURATION, which gave
# each level a different session count and produced a non-monotonic AI-OFF
# result at 6 users that cannot support a limit claim. 480 divides 2/4/6/8/10.
TARGET_SESSIONS_AI_OFF = 480

MIN_SAMPLES = 30

# Exploratory wave budgets: the point of a probe is to bracket the next level,
# not to spend an hour confirming that a deep queue is deep.
def waves_for_ai(users: int) -> tuple[int, str]:
    if users <= 32:
        return 3, "MEASURED"
    if users <= 96:
        return 2, "MEASURED"
    return 1, "EXPLORATORY"


# FROZEN IN SLICE 2. Not recomputed here. Tuning these after seeing Slice 3
# would make the knee an opinion instead of a measurement.
SLICE2_REPORT = ("/home/google/experiments/capacity-lab/reports/"
                 "SUITE-slice2-20260824-123839.json")

# Configured request timeout. The safety rule brackets rather than jumping when
# the PROJECTED next level would exceed 80% of it.
REQUEST_TIMEOUT = 300.0
TIMEOUT_SAFETY_FRACTION = 0.80

# Load-generator materiality. nproc cores of host capacity; the harness becomes
# material at 10% of the HOST, which is 10% x nproc x one core.
HOST_CORES = os.cpu_count() or 1
LOADGEN_MATERIAL_PCT_OF_HOST = 10.0

# Explicit maximum test cap for this slice.
MAX_USERS = 256

AI_OFF_CANDIDATES = [16, 24, 32, 48, 64, 96, 128, 192, 256]
AI_ON_CANDIDATES = [12, 16, 24, 32, 48, 64, 96, 128, 192, 256]

REPEATS = 3


def log(*a, **kw):
    print(*a, **kw, flush=True)


# ------------------------------------------------------------- server identity
def server_pid() -> int | None:
    """The control service under test, found by listening socket rather than by
    a command-line substring match."""
    try:
        out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=10)
        for line in out.stdout.splitlines():
            if "127.0.0.1:8811" in line and "pid=" in line:
                return int(line.split("pid=")[1].split(",")[0])
    except Exception:
        pass
    return None


def server_admission_limit() -> dict:
    """The server runs sync route handlers on anyio's default thread limiter, so
    it admits a bounded number of concurrent requests regardless of how many
    clients arrive. Measured from the installed library, not recalled."""
    code = ("import anyio, anyio.to_thread, importlib.metadata as md\n"
            "async def m():\n"
            "    print(md.version('anyio'), "
            "anyio.to_thread.current_default_thread_limiter().total_tokens)\n"
            "anyio.run(m)\n")
    try:
        pid = server_pid()
        # argv[0], not /proc/<pid>/exe: exe resolves through the venv symlink to
        # the base interpreter, which cannot import the venv's anyio.
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            exe = fh.read().split(b"\0")[0].decode()
        out = subprocess.run([exe, "-c", code], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip()[-300:] or "probe failed")
        ver, tokens = out.stdout.split()
        return {"mechanism": "anyio default thread limiter (FastAPI sync route handlers)",
                "anyio_version": ver,
                "max_concurrent_sync_handlers": int(float(tokens)),
                "overridden_by_application": False,
                "label": "MEASURED SERVER CONFIGURATION",
                "implication": ("above this many concurrent HTTP requests the server "
                                "admits only this many at a time; the rest wait for a "
                                "thread token. This is an APPLICATION limit, not CPU, "
                                "RAM, GPU or database.")}
    except Exception as e:                                          # noqa: BLE001
        return {"mechanism": "anyio default thread limiter",
                "max_concurrent_sync_handlers": NOT_AVAILABLE,
                "error": f"{type(e).__name__}: {e}"}


SERVER_LOG = Path("/tmp/control-service.log")


class ProcessIdentityObserver:
    """Continuously observe which engines are actually executing.

    Slice 2 and the first Slice 3 attempt HARDCODED the legacy and image-worker
    execution counts to 0 and called that a finding. A constant is not an
    observation. This samples /proc for the real argv of every process and
    counts DISTINCT pids per engine class, so a respawn shows up as two.

    Limitation, stated rather than hidden: this is sampling. A process that
    lived entirely between two samples would be missed, so the count is
    reported together with the achieved sample interval. The systemd unit state
    captured separately is the authoritative channel for the legacy engine.
    """

    CLASSES = {"chat_worker.py": "native_chat_worker",
               "image_worker.py": "image_worker"}

    def __init__(self, interval=SAMPLE_INTERVAL):
        self.interval = interval
        self.seen: dict[str, set[int]] = {v: set() for v in self.CLASSES.values()}
        self.seen["symoneural_llm"] = set()
        self.samples = 0
        self.started_at: float | None = None
        self.stopped_at: float | None = None
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def _scan(self) -> None:
        for d in glob.glob("/proc/[0-9]*"):
            try:
                with open(d + "/cmdline", "rb") as fh:
                    argv = [x.decode("utf-8", "replace")
                            for x in fh.read().split(b"\0") if x]
                if not argv:
                    continue
                pid = int(d.rsplit("/", 1)[1])
                # argv[1] is the SCRIPT. Matching a substring anywhere in the
                # command line makes this harness match itself, which is how the
                # Slice 2 check once reported a worker that was not running.
                script = os.path.basename(argv[1]) if len(argv) > 1 else ""
                cls = self.CLASSES.get(script)
                if cls:
                    self.seen[cls].add(pid)
                if os.path.basename(argv[0]).startswith("symoneural-llm"):
                    self.seen["symoneural_llm"].add(pid)
            except Exception:
                continue

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._scan()
            self.samples += 1
            self._stop.wait(self.interval)

    def start(self):
        self.started_at = time.monotonic()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._t:
            self._t.join(timeout=5)
        self.stopped_at = time.monotonic()

    def report(self) -> dict:
        if not self.samples:
            return {"observed": False,
                    "native_chat_worker_executions": NOT_AVAILABLE,
                    "image_worker_executions": NOT_AVAILABLE,
                    "symoneural_llm_executions": NOT_AVAILABLE,
                    "why": "the process observer never took a sample"}
        span = (self.stopped_at or time.monotonic()) - (self.started_at or 0)
        achieved = round(span / self.samples, 4) if self.samples else NOT_AVAILABLE
        return {
            "observed": True,
            "method": "continuous /proc argv[1] scan for distinct pids",
            "samples": self.samples,
            "span_s": round(span, 1),
            "nominal_interval_s": self.interval,
            "achieved_interval_s": achieved,
            "native_chat_worker_executions": len(self.seen["native_chat_worker"]),
            "native_chat_worker_pids": sorted(self.seen["native_chat_worker"]),
            "image_worker_executions": len(self.seen["image_worker"]),
            "image_worker_pids": sorted(self.seen["image_worker"]),
            "symoneural_llm_executions": len(self.seen["symoneural_llm"]),
            "symoneural_llm_pids": sorted(self.seen["symoneural_llm"]),
            "limitation": (f"sampled every ~{achieved}s; a process living entirely "
                           f"between two samples would not be counted"),
        }


def legacy_unit_state(label: str) -> dict:
    """Authoritative, not sampled: systemd's own restart counter and start
    timestamp for the legacy engine. If NRestarts and the start timestamp are
    unchanged across the suite, the unit demonstrably did not run -- which
    sampling can only ever fail to disprove."""
    try:
        out = subprocess.run(
            ["systemctl", "show", "symoneural-llm",
             "-p", "NRestarts", "-p", "ExecMainStartTimestamp",
             "-p", "ActiveState", "-p", "ExecMainPID"],
            capture_output=True, text=True, timeout=30)
        d = dict(l.split("=", 1) for l in out.stdout.strip().splitlines() if "=" in l)
        d["label"] = label
        d["source"] = "systemctl show -- AUTHORITATIVE, not sampled"
        return d
    except Exception as e:                                          # noqa: BLE001
        return {"label": label, "error": f"{type(e).__name__}: {e}"}


def read_server_log_delta(offset: int) -> tuple[str, int]:
    """New server-log bytes since `offset`. This is the only channel through
    which a 5xx can be attributed to a subsystem: the client sees an opaque
    500, the server writes the traceback."""
    try:
        size = SERVER_LOG.stat().st_size
        if size < offset:            # rotated/truncated
            offset = 0
        with SERVER_LOG.open("r", errors="replace") as fh:
            fh.seek(offset)
            return fh.read(), size
    except Exception:
        return "", offset


def server_log_offset() -> int:
    try:
        return SERVER_LOG.stat().st_size
    except Exception:
        return 0


DB_MARKERS = ("sqlite3.", "database is locked", "database table is locked",
              "disk I/O error", "OperationalError", "IntegrityError")


def subsystem_evidence(log_delta: str) -> dict:
    """What the server actually said. Absence of DB markers is reported as
    absence of evidence, never as evidence of a different cause."""
    if not log_delta.strip():
        return {"server_log_bytes": 0, "database_evidence": False,
                "traceback_present": False,
                "note": "server log produced no output during this level"}
    hits = sorted({m for m in DB_MARKERS if m in log_delta})
    return {"server_log_bytes": len(log_delta),
            "database_evidence": bool(hits),
            "database_markers": hits or None,
            "traceback_present": "Traceback (most recent call last)" in log_delta,
            "excerpt": log_delta[-2000:]}


class ServerThreadSampler:
    """Direct evidence of server-side admission: the thread count of the server
    process. A configured limiter is a claim; the observed thread high-water
    mark is a measurement."""

    def __init__(self, pid: int | None, interval=SAMPLE_INTERVAL):
        self.pid, self.interval = pid, interval
        self.counts: list[int] = []
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def start(self):
        if self.pid:
            self._t = threading.Thread(target=self._loop, daemon=True)
            self._t.start()
        return self

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.counts.append(len(os.listdir(f"/proc/{self.pid}/task")))
            except Exception:
                pass
            self._stop.wait(self.interval)

    def stop(self) -> dict:
        self._stop.set()
        if self._t:
            self._t.join(timeout=5)
        if not self.counts:
            return {"server_threads": NOT_AVAILABLE}
        return {"server_pid": self.pid,
                "server_threads_min": min(self.counts),
                "server_threads_max": max(self.counts),
                "server_threads_samples": len(self.counts),
                "note": ("OS thread count of the server process under load; the "
                         "high-water mark bounds how many requests it served "
                         "concurrently")}


# ----------------------------------------------------------------- accounting
def _proc_cpu_ram(pid: int) -> dict:
    try:
        with open(f"/proc/{pid}/stat") as fh:
            p = fh.read().split()
        with open(f"/proc/{pid}/status") as fh:
            rss = next(int(l.split()[1]) for l in fh if l.startswith("VmRSS"))
        return {"cpu_ticks": int(p[13]) + int(p[14]), "rss_mib": round(rss / 1024, 1),
                "threads": int(p[19])}
    except Exception:
        return {}


class Level:
    """One concurrency level: N users released together on a barrier, repeated
    for a fixed number of waves.

    Fixed session count, not fixed duration. Fixed duration let a fast path run
    far more sessions at low concurrency than at high, which is how Slice 2's
    AI-OFF percentiles ended up non-monotonic.
    """

    def __init__(self, run_id, users, ai_mode, player, waves, label,
                 timeout=REQUEST_TIMEOUT, expected_worker_pid=None):
        self.run_id, self.users, self.ai_mode = run_id, users, ai_mode
        self.player, self.timeout = player, timeout
        self.expected_worker_pid = expected_worker_pid
        self.target_waves, self.label = waves, label
        self.sessions: list[SessionResult] = []
        self.waves = 0
        self.max_active = 0
        self._active = 0
        self._lock = threading.Lock()
        self.broken_barriers = 0
        # Barrier timeout scales with N: 60 s is ample for 10 threads and not
        # obviously ample for 256, and a silently broken barrier means the level
        # never achieved its concurrency.
        self.barrier_timeout = max(60.0, users * 1.0)

    def _one(self, barrier, slot, wave, profile) -> SessionResult:
        sid = f"{self.run_id}-W{wave:03d}U{slot:03d}"
        scen = LifecycleScenario(profile=profile, wave=wave)
        try:
            barrier.wait(timeout=self.barrier_timeout)
        except threading.BrokenBarrierError:
            with self._lock:
                self.broken_barriers += 1
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            return scen.run(session_id=sid, run_id=self.run_id, base_url=BASE,
                            player=self.player, timeout=self.timeout)
        finally:
            with self._lock:
                self._active -= 1

    def run(self) -> dict:
        slots = list(range(1, self.users + 1))
        if hasattr(self.player, "reset_level_counters"):
            self.player.reset_level_counters()
        sampler = Sampler(interval=SAMPLE_INTERVAL).start()
        srv = ServerThreadSampler(server_pid()).start()
        procs = ProcessIdentityObserver().start()
        log_offset = server_log_offset()
        hp = os.getpid()
        lg0 = _proc_cpu_ram(hp)
        t0 = time.monotonic()

        extra_for_telemetry = 0
        while True:
            wave = self.waves
            assign = lifecycle.assign(slots, wave)
            barrier = threading.Barrier(self.users)
            with ThreadPoolExecutor(max_workers=self.users) as ex:
                futs = [ex.submit(self._one, barrier, s, wave, assign[s]) for s in slots]
                for f in futs:
                    try:
                        self.sessions.append(f.result(timeout=self.timeout * 3))
                    except Exception as e:                       # noqa: BLE001
                        self.sessions.append(SessionResult(
                            f"{self.run_id}-W{wave:03d}Uxxx", self.run_id, False,
                            t0, time.monotonic(), [], None,
                            f"harness: {type(e).__name__}: {e}"))
            self.waves += 1
            if self.waves < self.target_waves:
                continue
            # Extra waves ONLY to satisfy telemetry sufficiency -- concurrency is
            # never changed to reach a sample count.
            if len(sampler.samples) >= MIN_SAMPLES or extra_for_telemetry >= 20:
                break
            extra_for_telemetry += 1

        sampler.stop()
        procs.stop()
        wall = time.monotonic() - t0
        delta, _ = read_server_log_delta(log_offset)
        lg1 = _proc_cpu_ram(hp)
        hz = os.sysconf("SC_CLK_TCK")
        lg_cpu_s = (lg1.get("cpu_ticks", 0) - lg0.get("cpu_ticks", 0)) / hz
        return self._summarise(sampler, srv.stop(), wall, lg_cpu_s, lg1,
                               extra_for_telemetry, procs.report(),
                               subsystem_evidence(delta))

    def _gpu_ownership(self, stats: dict) -> dict:
        """Who owned the GPU during this level, checked against who was supposed to.

        AI OFF must have ZERO compute owners -- any owner means the arm was not
        measuring an idle card. AI ON must have EXACTLY the expected worker pid:
        a different pid is a respawn or a stranger, and either invalidates
        "one GPU owner at a time".
        """
        g = stats.get("gpu") if isinstance(stats.get("gpu"), dict) else {}
        seen = sorted(g.get("compute_pids_seen") or [])
        exp = self.expected_worker_pid
        if self.ai_mode == "off":
            ok = not seen
            rule = "AI OFF requires ZERO GPU compute owners"
        else:
            ok = seen == [exp] if exp is not None else False
            rule = f"AI ON requires EXACTLY the expected Chat worker pid {exp}"
        return {"rule": rule, "expected_worker_pid": exp,
                "compute_pids_seen": seen,
                "max_simultaneous_compute_apps": g.get("max_simultaneous_compute_apps"),
                "ok": ok}

    # ------------------------------------------------------------- summarising
    def _summarise(self, sampler, srv, wall, lg_cpu_s, lg1, extra,
                   procs, evidence) -> dict:
        done = [s for s in self.sessions if s.ok]
        failed = [s for s in self.sessions if not s.ok]

        sess_ms = [s.duration_s * 1000 for s in done]
        by_op: dict[str, list[float]] = {}
        setup_ms: list[float] = []
        for s in self.sessions:
            for st in s.steps:
                if st.name.startswith("operation:"):
                    by_op.setdefault(st.name.split(":", 1)[1], []).append(st.latency_s * 1000)
                elif st.name == "setup":
                    setup_ms.append(st.latency_s * 1000)
        op_ms = [v for vals in by_op.values() for v in vals]

        http: dict[str, int] = {}
        for s in self.sessions:
            for st in s.steps:
                k = str(st.http_status or "no-response")
                http[k] = http.get(k, 0) + 1

        ai_rows = [s.ai for s in self.sessions if s.ai is not None and not s.ai.bypassed]
        ok_ai = [a for a in ai_rows if a.ok]
        if ai_rows:
            waits = [w * 1000 for w in
                     (getattr(a, "queue_wait_s", None) for a in ok_ai) if w is not None]
            svc = [x * 1000 for x in
                   (getattr(a, "service_s", None) for a in ok_ai) if x is not None]
            toks = [a.tok_per_s for a in ok_ai if a.tok_per_s is not None]
            faults: dict[str, int] = {}
            for a in ai_rows:
                if not a.ok:
                    fc = getattr(a, "fault_class", None) or "UNCLASSIFIED"
                    faults[fc] = faults.get(fc, 0) + 1
            ai = {"requests": len(ai_rows),
                  "completed": len(ok_ai),
                  "errors": len(ai_rows) - len(ok_ai),
                  "fault_classification": faults or None,
                  "latency_ms": percentiles([a.latency_s * 1000 for a in ok_ai])
                                if ok_ai else NOT_AVAILABLE,
                  "queue_wait_ms": percentiles(waits) if waits else NOT_AVAILABLE,
                  "service_ms": percentiles(svc) if svc else NOT_AVAILABLE,
                  "tokens_per_s": percentiles(toks) if toks else NOT_AVAILABLE,
                  "time_to_first_token_ms": NOT_AVAILABLE,
                  "ttft_note": "worker returns a completed generation; no first-token event"}
            if hasattr(self.player, "metrics"):
                m = self.player.metrics()
                active, depth = m.get("max_active_ai_requests", 0), m.get("max_queue_depth", 0)
                ai["active_ai_requests_max"] = active
                ai["queue_depth_max"] = depth
                ai["queue_depth_definition"] = ("waiting requests BEHIND the request in "
                                                "service; not total in flight")
                ai["total_ai_in_system_max"] = {
                    "value": (active + depth) if isinstance(active, int)
                             and isinstance(depth, int) else NOT_AVAILABLE,
                    "label": "CALCULATED",
                    "formula": "active servicing + waiting queue"}
        else:
            ai = {"mode": "DISABLED", "engine_residency": "UNLOADED",
                  "note": "no inference request issued; no Chat worker alive for this arm"}

        lg_pct_core = round(100.0 * lg_cpu_s / wall, 2) if wall > 0 else NOT_AVAILABLE
        lg_pct_host = (round(lg_pct_core / HOST_CORES, 2)
                       if isinstance(lg_pct_core, float) else NOT_AVAILABLE)

        return {
            "requested_concurrency": self.users,
            "achieved_max_concurrency": self.max_active,
            "concurrency_achieved": self.max_active >= self.users,
            "broken_barrier_events": self.broken_barriers,
            "measurement_label": self.label,
            "waves": self.waves,
            "target_waves": self.target_waves,
            "extra_waves_for_telemetry": extra,
            "sessions_total": len(self.sessions),
            "concurrency_per_wave": self.users,
            "operation_mix": lifecycle.coverage(list(range(1, self.users + 1)), self.waves),
            "completed": len(done), "failed": len(failed),
            "wall_seconds": round(wall, 3),
            "throughput_sessions_per_s": round(len(done) / wall, 2) if wall > 0 else NOT_AVAILABLE,
            "application": {
                "session_latency_ms": percentiles(sess_ms) if sess_ms else NOT_AVAILABLE,
                "operation_latency_ms": percentiles(op_ms) if op_ms else NOT_AVAILABLE,
                "operation_latency_by_class_ms": {k: percentiles(v) for k, v in sorted(by_op.items())},
                "setup_latency_ms": percentiles(setup_ms) if setup_ms else NOT_AVAILABLE,
                "http_status_counts": http,
                "timeouts": sum(1 for s in self.sessions
                                if s.error and "timeout" in s.error.lower()),
            },
            "ai": ai,
            "telemetry": _with_achieved_interval(sampler.statistics()),
            "process_identity": procs,
            "gpu_ownership": self._gpu_ownership(sampler.statistics()),
            "subsystem_evidence": evidence,
            "server_process": srv,
            "load_generator": {
                "location": "LOCAL / SAME HOST",
                "host_cpu_capacity_cores": HOST_CORES,
                "harness_cpu_seconds": round(lg_cpu_s, 3),
                "harness_cpu_pct_of_one_core": lg_pct_core,
                "harness_cpu_pct_of_host": lg_pct_host,
                "materiality_threshold_pct_of_host": LOADGEN_MATERIAL_PCT_OF_HOST,
                "material": (isinstance(lg_pct_host, float)
                             and lg_pct_host >= LOADGEN_MATERIAL_PCT_OF_HOST),
                "harness_rss_mib": lg1.get("rss_mib", NOT_AVAILABLE),
                "harness_threads": lg1.get("threads", NOT_AVAILABLE),
                "note": ("the synthetic clients run on the server under test; this "
                         "consumption is included in the CPU/RAM figures above"),
            },
            "errors": [{"session": s.session_id, "error": s.error} for s in failed][:50] or None,
            "error_count_truncated": max(0, len(failed) - 50) or None,
        }


def _with_achieved_interval(stats: dict) -> dict:
    """The Sampler reports its REQUESTED interval. Each sample spawns two
    nvidia-smi processes, so the achieved rate is slower -- and every "a short
    process could slip between samples" caveat is sized by the achieved rate,
    not the requested one."""
    n, span = stats.get("sample_count"), stats.get("span_s")
    if isinstance(n, int) and n > 0 and isinstance(span, (int, float)):
        stats = dict(stats)
        stats["nominal_interval_s"] = stats.get("sample_interval_s")
        stats["achieved_interval_s"] = round(span / n, 4)
    return stats


# ----------------------------------------------------------------- classification
def classify(level: dict, crit: dict, admission: dict) -> dict:
    flags, hard = [], []
    if level["failed"] > 0:
        hard.append(f"{level['failed']} session(s) failed")

    # D1: benchmark data that does not get removed is a hard failure, not a
    # footnote. The first Slice 3 attempt recorded the cleanup result and then
    # never looked at it; when it was killed mid-level it left 32 synthetic
    # bookings behind and nothing in the harness noticed.
    cu = level.get("cleanup") or {}
    if cu.get("state") != "removed":
        hard.append(f"benchmark cleanup FAILED: {cu.get('error') or cu}")
    else:
        # Bookings created, not sessions run: a session that failed before its
        # create legitimately removes nothing, so comparing against
        # sessions_total would manufacture a failure.
        created = int(level["application"]["http_status_counts"].get("201", 0))
        removed = cu.get("bookings_removed")
        if isinstance(removed, int) and removed != created:
            flags.append(f"CLEANUP MISMATCH: {created} booking(s) created, "
                         f"{removed} removed")

    # D3: GPU ownership must match the arm's contract.
    own = level.get("gpu_ownership") or {}
    if own and not own.get("ok"):
        hard.append(f"GPU OWNERSHIP VIOLATION: {own.get('rule')}; "
                    f"observed {own.get('compute_pids_seen')}")
    for code, n in level["application"]["http_status_counts"].items():
        if code.isdigit() and code.startswith("5"):
            hard.append(f"HTTP {code} x{n}")
    if level["application"]["timeouts"]:
        hard.append(f"{level['application']['timeouts']} timeout(s)")
    if isinstance(level["ai"], dict) and level["ai"].get("errors"):
        hard.append(f"{level['ai']['errors']} AI error(s): "
                    f"{level['ai'].get('fault_classification')}")
    t = level["telemetry"]
    if t.get("series_sufficient") is False:
        flags.append("SERIES INSUFFICIENT -- not usable for a capacity conclusion")
    if isinstance(t.get("gpu"), dict) and t["gpu"].get("max_simultaneous_compute_apps", 0) > 1:
        hard.append("more than one GPU owner")

    # Two different things, deliberately not merged.
    #
    # VALIDITY defects mean the level did not measure what it claims to measure,
    # so it cannot support a capacity claim at its requested number.
    #
    # CAVEATS mean the level is valid but one figure inside it must not be read
    # naively. Admission distortion is a caveat, not a defect: if 48 sessions all
    # completed, 48 users were served, and the fact that the server internally
    # admitted 40 at a time is the server's own measured behaviour -- it is the
    # answer, not a reason to discard the level.
    validity, caveats = [], []
    if not level["concurrency_achieved"]:
        validity.append(
            f"CONCURRENCY NOT ACHIEVED: requested {level['requested_concurrency']}, "
            f"achieved {level['achieved_max_concurrency']}")
    if level["broken_barrier_events"]:
        validity.append(f"{level['broken_barrier_events']} broken barrier event(s)")
    if level["load_generator"]["material"]:
        validity.append(
            f"LOAD-GENERATOR LIMITED: harness used "
            f"{level['load_generator']['harness_cpu_pct_of_host']}% of host CPU "
            f"(>= {LOADGEN_MATERIAL_PCT_OF_HOST}%); SERVER LIMIT NOT ISOLATED")
    lim = admission.get("max_concurrent_sync_handlers")
    if isinstance(lim, int) and level["requested_concurrency"] > lim:
        caveats.append(
            f"ADMISSION-DISTORTED: requested concurrency {level['requested_concurrency']} "
            f"exceeds the server's {lim} concurrent sync handlers, so arrivals at the "
            f"AI queue are staggered by HTTP admission. Queue depth below "
            f"{level['requested_concurrency'] - 1} here is distortion, not headroom.")

    ratios = {}
    ref = crit.get("operation_p95_ms_ref")
    cur = (level["application"]["operation_latency_ms"] or {})
    cur = cur.get("p95") if isinstance(cur, dict) else None
    if isinstance(ref, (int, float)) and isinstance(cur, (int, float)) and ref > 0:
        ratios["operation_p95_ratio"] = round(cur / ref, 2)
        if cur / ref >= crit["latency_ratio_threshold"]:
            flags.append(f"DEGRADED - LATENCY ({cur/ref:.2f}x the frozen 2-user reference)")
    aref = crit.get("ai_p95_ms_ref")
    acur = (level["ai"].get("latency_ms") or {}) if isinstance(level["ai"], dict) else {}
    acur = acur.get("p95") if isinstance(acur, dict) else None
    if isinstance(aref, (int, float)) and isinstance(acur, (int, float)) and aref > 0:
        ratios["ai_p95_ratio"] = round(acur / aref, 2)
        if acur / aref >= crit.get("ai_ratio_threshold", 2.0):
            flags.append(f"DEGRADED - AI LATENCY ({acur/aref:.2f}x)")
    if isinstance(level["ai"], dict):
        qw, sv = level["ai"].get("queue_wait_ms") or {}, level["ai"].get("service_ms") or {}
        if isinstance(qw, dict) and isinstance(sv, dict):
            q95, s95 = qw.get("p95"), sv.get("p95")
            if isinstance(q95, (int, float)) and isinstance(s95, (int, float)) and s95:
                ratios["queue_wait_over_service_p95"] = round(q95 / s95, 2)
                if q95 >= s95:
                    flags.append(f"DEGRADED - QUEUE (queue wait p95 {q95} ms >= "
                                 f"service p95 {s95} ms)")
    if isinstance(t.get("gpu"), dict):
        gu = t["gpu"]["utilization_pct"]
        if isinstance(gu.get("avg"), (int, float)) and gu["avg"] >= 90:
            flags.append(f"DEGRADED - RESOURCE (GPU util sustained {gu['avg']}%)")
    if isinstance(t.get("system"), dict):
        cp = t["system"]["cpu_pct"]
        if isinstance(cp.get("avg"), (int, float)) and cp["avg"] >= 90:
            flags.append(f"DEGRADED - RESOURCE (CPU sustained {cp['avg']}%)")

    result = "FAIL" if hard else ("DEGRADED" if any(f.startswith("DEGRADED") for f in flags)
                                  else "PASS")
    return {"result": result, "hard_failures": hard or None, "flags": flags or None,
            "validity": validity or None, "caveats": caveats or None,
            "supports_capacity_claim": not hard and not validity,
            "ratios": ratios}


def bottleneck(level: dict, admission: dict) -> dict:
    """First limiting subsystem, from measured evidence only."""
    ev, cls = [], "UNKNOWN"
    t = level["telemetry"]
    g = t.get("gpu") if isinstance(t.get("gpu"), dict) else {}
    sy = t.get("system") if isinstance(t.get("system"), dict) else {}
    # The Sampler reports per-sample series as {min,avg,max} dicts but capacity
    # TOTALS as bare scalars -- they do not vary, so a series would be noise.
    # Reading a scalar as a dict is how this function crashed the first time it
    # met real telemetry.
    def stat(d, key, which):
        v = d.get(key)
        return v.get(which) if isinstance(v, dict) else v

    gu = stat(g, "utilization_pct", "avg")
    vram = stat(g, "vram_used_mib", "max")
    vtot = stat(g, "vram_total_mib", "max")
    cpu = stat(sy, "cpu_pct", "avg")
    ram = stat(sy, "ram_used_mib", "max")
    ramt = stat(sy, "ram_total_mib", "max")

    if level["load_generator"]["material"]:
        return {"classification": "LOCAL LOAD GENERATOR",
                "evidence": [f"harness {level['load_generator']['harness_cpu_pct_of_host']}% "
                             f"of host CPU"],
                "server_limit_isolated": False}

    ai = level["ai"] if isinstance(level["ai"], dict) else {}
    fc = ai.get("fault_classification") or {}
    if any("TIMEOUT POLICY" in k for k in fc):
        cls = "TIMEOUT POLICY"
        ev.append(f"AI faults by class: {fc}")
    elif isinstance(ai.get("queue_wait_ms"), dict) and isinstance(ai.get("service_ms"), dict):
        q95, s95 = ai["queue_wait_ms"].get("p95"), ai["service_ms"].get("p95")
        if isinstance(q95, (int, float)) and isinstance(s95, (int, float)) and s95 and q95 >= s95:
            cls = "AI QUEUE / SERIAL SERVICE"
            ev.append(f"queue wait p95 {q95} ms vs service p95 {s95} ms "
                      f"({q95/s95:.2f}x); service time flat")
    if cls == "UNKNOWN":
        codes = level["application"]["http_status_counts"]
        if any(c.isdigit() and c.startswith("5") for c in codes):
            # A 500 tells you the request failed, NOT which subsystem failed:
            # the client sees an opaque body. Only the server's own log can
            # attribute it, so DATABASE is claimed only on positive evidence
            # and APPLICATION otherwise. Calling every 5xx a database problem
            # would have sent Donnie shopping for a bigger database.
            se = level.get("subsystem_evidence") or {}
            if se.get("database_evidence"):
                cls = "DATABASE"
                ev.append(f"HTTP 5xx present: {codes}; server log shows "
                          f"{se.get('database_markers')}")
            else:
                cls = "APPLICATION"
                ev.append(f"HTTP 5xx present: {codes}; NO database evidence in the "
                          f"server log -- cause not attributed to the database")
                if not se.get("traceback_present"):
                    ev.append("no server-side traceback captured; subsystem "
                              "attribution is UNCONFIRMED")
        else:
            lim = admission.get("max_concurrent_sync_handlers")
            srv_max = level["server_process"].get("server_threads_max")
            if isinstance(lim, int) and level["requested_concurrency"] > lim:
                cls = "APPLICATION"
                ev.append(f"server admits {lim} concurrent sync handlers; observed server "
                          f"thread high-water {srv_max}; requested {level['requested_concurrency']}")

    if isinstance(gu, (int, float)):
        ev.append(f"GPU util avg {gu}% -- {'saturated' if gu >= 90 else 'NOT saturated'}")
    if isinstance(vram, (int, float)) and isinstance(vtot, (int, float)):
        ev.append(f"VRAM max {vram}/{vtot} MiB -- {vtot - vram} MiB free; "
                  f"{'exhausted' if vtot - vram < 256 else 'NOT exhausted'}")
    if isinstance(cpu, (int, float)):
        ev.append(f"CPU avg {cpu}% -- {'saturated' if cpu >= 90 else 'NOT saturated'}")
    if isinstance(ram, (int, float)) and isinstance(ramt, (int, float)):
        ev.append(f"RAM max {ram}/{ramt} MiB -- {'exhausted' if ramt - ram < 1024 else 'NOT exhausted'}")
    return {"classification": cls, "evidence": ev, "server_limit_isolated": True}


def timeout_projection(prev: dict, next_users: int) -> dict:
    """PROJECTED SAFETY ESTIMATE -- never a substitute for a measured result.

    Uses only the previous MEASURED level. If the projection exceeds 80% of the
    configured timeout, the ramp brackets instead of jumping.
    """
    ai = prev.get("ai") or {}
    lat = ai.get("latency_ms")
    if not isinstance(lat, dict) or not isinstance(lat.get("p95"), (int, float)):
        return {"label": "PROJECTED SAFETY ESTIMATE", "available": False,
                "reason": "no measured AI latency at the previous level"}
    p95_s = lat["p95"] / 1000.0
    n = prev["requested_concurrency"]
    per_user = p95_s / max(1, n)
    proj = per_user * next_users
    budget = REQUEST_TIMEOUT * TIMEOUT_SAFETY_FRACTION
    return {"label": "PROJECTED SAFETY ESTIMATE",
            "available": True,
            "basis": f"measured p95 {lat['p95']} ms at {n} users",
            "projected_p95_s_at_next": round(proj, 1),
            "timeout_s": REQUEST_TIMEOUT,
            "safety_budget_s": budget,
            "safe_to_jump": proj < budget,
            "caution": "PROJECTED, NOT MEASURED -- used only to choose the next step size"}


# ---------------------------------------------------------------- orchestration
def gpu_state(label: str) -> dict:
    sys.path.insert(0, str(Path("/home/google/Symoneural/.claude/worktrees/"
                                "native-hybrid-gpu-player/engines/symoneural-hybrid")))
    import gpu_guard
    apps = gpu_guard.compute_apps()
    snap = gpu_guard.gpu_snapshot()
    return {"label": label, "at_utc": datetime.now(timezone.utc).isoformat(),
            "vram_used_mib": snap["vram_used_mib"],
            "compute_apps": len(apps), "compute_pids": [p for p, _ in apps],
            "legacy_symoneural_llm_pids": _legacy_engine_pids(),
            "power_w": snap["power_w"], "util_pct": snap["util_pct"]}


def final_synthetic_check() -> dict:
    """Benchmark data must never outlive the benchmark."""
    import json as _j
    import urllib.request as _u
    try:
        with _u.urlopen(f"{BASE}/api/dispatchos/bookings?synthetic=true", timeout=120) as r:
            syn = _j.loads(r.read())["count"]
        with _u.urlopen(f"{BASE}/api/dispatchos/bookings", timeout=120) as r:
            allb = _j.loads(r.read())["count"]
        return {"synthetic_remaining": syn, "all_remaining": allb, "clean": syn == 0,
                "note": "benchmark records must never outlive the benchmark"}
    except Exception as e:                                          # noqa: BLE001
        return {"synthetic_remaining": NOT_AVAILABLE, "clean": False,
                "error": f"{type(e).__name__}: {e}"}


def clear_run(run_id: str) -> dict:
    from capacity_lab.harness import _delete
    ok, _l, st, doc, err = _delete(BASE, f"/api/dispatchos/benchmark/{run_id}", 120)
    return ({"state": "removed", **(doc or {})} if ok
            else {"state": "cleanup FAILED", "http_status": st, "error": err})


def run_level(users, ai_mode, player, crit, admission, waves, label,
              run_ids, expected_worker_pid=None) -> dict:
    rid = new_run_id(datetime.now(), known_run_ids() + run_ids)
    run_ids.append(rid)
    log(f"  {users:4d} users x {waves:3d} waves [{label:11s}] … ", end="")
    lvl = Level(rid, users, ai_mode, player, waves, label,
                expected_worker_pid=expected_worker_pid).run()
    lvl["run_id"] = rid
    # cleanup BEFORE classification: classify() hard-fails on a cleanup failure,
    # so the result must already be present.
    lvl["cleanup"] = clear_run(rid)
    lvl["classification"] = classify(lvl, crit, admission)
    lvl["bottleneck"] = bottleneck(lvl, admission)
    op = lvl["application"]["operation_latency_ms"]
    ap = lvl["ai"].get("latency_ms") if isinstance(lvl["ai"], dict) else None
    log(f"n={lvl['sessions_total']:5d} ok={lvl['completed']:5d} fail={lvl['failed']:4d} "
        f"ach={lvl['achieved_max_concurrency']:4d} "
        f"op_p95={(op or {}).get('p95') if isinstance(op, dict) else 'NA'} "
        f"ai_p95={(ap or {}).get('p95') if isinstance(ap, dict) else '-'} "
        f"srv_thr={lvl['server_process'].get('server_threads_max')} "
        f"lg={lvl['load_generator']['harness_cpu_pct_of_host']}%host "
        f"-> {lvl['classification']['result']}")
    for f in (lvl["classification"]["flags"] or []):
        log(f"          flag: {f}")
    for v in (lvl["classification"]["validity"] or []):
        log(f"          VALIDITY: {v}")
    for cv in (lvl["classification"]["caveats"] or []):
        log(f"          CAVEAT: {cv}")
    for h in (lvl["classification"]["hard_failures"] or []):
        log(f"          HARD: {h}")
    return lvl


def waves_for_off(users: int) -> tuple[int, str]:
    """Constant session count, not constant duration. 480 divides 2/4/6/8/10
    exactly; above that the wave count is rounded up so every level still runs
    at least 480 sessions and the actual count is reported."""
    return max(1, math.ceil(TARGET_SESSIONS_AI_OFF / users)), "MEASURED"


def adaptive_ramp(ai_mode, player, crit, admission, candidates, wave_fn,
                  run_ids, levels: dict, prev_level: dict | None,
                  expected_worker_pid=None) -> dict:
    """Walk the candidate ladder, stopping on the first objective stop condition.

    The ladder is a list of candidates, not a mandatory sequence: the timeout
    safety projection can insert a smaller intermediate step, and any stop
    condition ends the ramp so the boundary can be bracketed.
    """
    outcome = {"candidates": list(candidates), "executed": [], "projections": [],
               "stopped": None, "last_pass": None, "first_fail": None}
    prev = prev_level
    for cand in candidates:
        if cand > MAX_USERS:
            outcome["stopped"] = f"explicit maximum test cap {MAX_USERS} reached"
            break
        step_users = cand
        if prev is not None:
            proj = timeout_projection(prev, cand)
            proj["from_users"] = prev["requested_concurrency"]
            proj["to_users"] = cand
            outcome["projections"].append(proj)
            if proj.get("available") and not proj["safe_to_jump"]:
                mid = (prev["requested_concurrency"] + cand) // 2
                if mid > prev["requested_concurrency"]:
                    log(f"  PROJECTED SAFETY ESTIMATE: {cand} users would reach "
                        f"~{proj['projected_p95_s_at_next']}s p95 vs a "
                        f"{proj['safety_budget_s']}s budget -- bracketing to {mid}")
                    step_users = mid
                else:
                    outcome["stopped"] = ("projected p95 exceeds 80% of the configured "
                                          "timeout and no smaller step remains")
                    break
        waves, label = wave_fn(step_users)
        lvl = run_level(step_users, ai_mode, player, crit, admission, waves, label,
                        run_ids, expected_worker_pid)
        levels[step_users] = lvl
        outcome["executed"].append(step_users)
        c = lvl["classification"]
        if c["result"] == "FAIL":
            outcome["first_fail"] = step_users
            outcome["stopped"] = f"objective hard failure at {step_users} users"
            break
        if lvl["load_generator"]["material"]:
            outcome["stopped"] = (f"LOAD-GENERATOR LIMITED at {step_users} users -- "
                                  f"SERVER LIMIT NOT ISOLATED")
            break
        if c["supports_capacity_claim"]:
            outcome["last_pass"] = step_users
        prev = lvl
    else:
        outcome["stopped"] = "candidate ladder exhausted with no stop condition"
    return outcome


def bracket(lo, hi, ai_mode, player, crit, admission, wave_fn, run_ids,
            levels: dict, min_gap=4, expected_worker_pid=None) -> dict:
    """Localise a boundary instead of declaring the last passing rung the limit.

    `lo` passed and `hi` failed; bisect on integers until the gap is small enough
    that the remaining uncertainty is stated rather than hidden.
    """
    steps = []
    log(f"  bracketing boundary between {lo} (pass) and {hi} (fail)…")
    while hi - lo > min_gap:
        mid = (lo + hi) // 2
        if mid in levels:
            break
        waves, label = wave_fn(mid)
        lvl = run_level(mid, ai_mode, player, crit, admission, waves, label,
                        run_ids, expected_worker_pid)
        levels[mid] = lvl
        ok = lvl["classification"]["result"] != "FAIL"
        steps.append({"users": mid, "result": lvl["classification"]["result"]})
        if ok:
            lo = mid
        else:
            hi = mid
    return {"highest_passing": lo, "lowest_failing": hi, "steps": steps,
            "residual_uncertainty_users": hi - lo,
            "note": ("the boundary lies in this interval; it is not claimed to be a "
                     "single sharp number")}


def repeat_level(users, ai_mode, player, crit, admission, wave_fn, run_ids,
                 n=REPEATS, expected_worker_pid=None) -> dict:
    """Independent repeats. A boundary observed once is an anecdote."""
    runs = []
    waves, label = wave_fn(users)
    log(f"  repeatability at {users} users, {n} independent runs:")
    for i in range(n):
        lvl = run_level(users, ai_mode, player, crit, admission, waves,
                        f"{label}/R{i+1}", run_ids, expected_worker_pid)
        runs.append({"run_id": lvl["run_id"], "result": lvl["classification"]["result"],
                     "sessions": lvl["sessions_total"], "completed": lvl["completed"],
                     "failed": lvl["failed"],
                     "achieved_max_concurrency": lvl["achieved_max_concurrency"],
                     "op_p95_ms": (lvl["application"]["operation_latency_ms"] or {}).get("p95")
                                  if isinstance(lvl["application"]["operation_latency_ms"], dict)
                                  else NOT_AVAILABLE,
                     "ai_p95_ms": (lvl["ai"].get("latency_ms") or {}).get("p95")
                                  if isinstance(lvl["ai"], dict)
                                  and isinstance(lvl["ai"].get("latency_ms"), dict)
                                  else NOT_AVAILABLE,
                     "hard_failures": lvl["classification"]["hard_failures"],
                     "supports_capacity_claim": lvl["classification"]["supports_capacity_claim"]})
    # A run that did not FAIL is not the same as a run that PROVES capacity: a
    # level whose concurrency was not achieved, or whose load generator was
    # material, is not evidence for the number on its label.
    passes = sum(1 for r in runs if r["supports_capacity_claim"])
    not_failed = sum(1 for r in runs if r["result"] != "FAIL")
    return {"users": users, "runs": runs, "successful_runs": passes, "total_runs": n,
            "runs_without_hard_failure": not_failed,
            "summary": f"{passes}/{n} PROVE CAPACITY",
            "counting_rule": ("a repeat counts only when supports_capacity_claim "
                              "is true, not merely when it avoided a hard failure"),
            "repeatable": passes == n or passes == 0,
            "note": ("intermittent boundaries are reported as successes/total rather "
                     "than rounded to a sharp number")}


def load_frozen_criteria() -> dict:
    """Slice 2's criteria, read from the Slice 2 report. Deliberately loaded
    rather than recomputed: a criterion recomputed after seeing the data it
    judges is not frozen."""
    d = json.loads(Path(SLICE2_REPORT).read_text())
    return {"source_report": SLICE2_REPORT,
            "ai_off": d["ai_off"]["frozen_criteria"],
            "ai_on": d["ai_on"]["frozen_criteria"],
            "provenance": "FROZEN IN SLICE 2 -- not recomputed, not tuned in Slice 3"}


def run_ai_off(crit, admission, baseline, run_ids) -> dict:
    arm = {"ai_mode": "DISABLED", "levels": {}, "gpu_transitions": []}
    arm["gpu_transitions"].append(gpu_state("ai_off_start"))
    st = arm["gpu_transitions"][-1]
    if st["compute_apps"] or st["legacy_symoneural_llm_pids"]:
        raise RuntimeError(f"AI OFF requires an idle card: {st}")
    player = NullPlayer()
    levels: dict[int, dict] = {}

    log("\nPART 1 -- corrected AI-OFF baseline, CONSTANT SESSION COUNT "
        f"({TARGET_SESSIONS_AI_OFF} sessions per level)")
    for users in (2, 4, 6, 8, 10):
        waves, label = waves_for_off(users)
        levels[users] = run_level(users, "off", player, crit, admission,
                                  waves, label, run_ids)

    log("\nPART 1b -- AI-OFF adaptive ramp")
    ramp = adaptive_ramp("off", player, crit, admission, AI_OFF_CANDIDATES,
                         waves_for_off, run_ids, levels, levels.get(10))
    arm["ramp"] = ramp

    if ramp["first_fail"] and ramp["last_pass"]:
        arm["bracket"] = bracket(ramp["last_pass"], ramp["first_fail"], "off", player,
                                 crit, admission, waves_for_off, run_ids, levels)

    _confirm_capacity(arm, levels, "off", player, crit, admission,
                      waves_for_off, run_ids, None)
    fails = [u for u, lv in sorted(levels.items())
             if lv["classification"]["result"] == "FAIL"]
    if fails:
        arm["repeatability_first_failure"] = repeat_level(
            min(fails), "off", player, crit, admission, waves_for_off, run_ids)

    arm["levels"] = {str(k): v for k, v in sorted(levels.items())}
    arm["gpu_transitions"].append(gpu_state("ai_off_end"))
    return arm


def run_ai_on(crit, admission, baseline, run_ids) -> dict:
    arm = {"ai_mode": "ENABLED", "levels": {}, "gpu_transitions": []}
    arm["gpu_transitions"].append(gpu_state("ai_on_start"))
    st = arm["gpu_transitions"][-1]
    if st["compute_apps"] or st["legacy_symoneural_llm_pids"]:
        raise RuntimeError(f"AI ON requires an idle card before load: {st}")

    from capacity_lab.native_player import NativeChatPlayer
    player = NativeChatPlayer(baseline_mib=baseline)
    log("  loading ONE native Chat worker for the whole arm…")
    ev = player.start(ready_timeout=900)
    arm["cold_start"] = {"seconds": player.cold_start_s, "worker_pid": player.worker_pid,
                         "worker_process_vram_mib": player.worker_vram_mib,
                         "total_vram_at_ready_mib": ev["vram_used_mib"],
                         "measured_baseline_before_load_mib": baseline,
                         "note": "measured once; excluded from every steady-state figure"}
    arm["gpu_transitions"].append(gpu_state("after_worker_ready"))
    log(f"  cold start {player.cold_start_s}s pid={player.worker_pid} "
        f"proc={player.worker_vram_mib} MiB total={ev['vram_used_mib']} MiB")
    log("  warm-up inference (DISCARDED)…")
    w0 = time.monotonic()
    wr = player.invoke("Warm up. Reply with one short word.", timeout=300)
    arm["warmup"] = {"ok": wr.ok, "seconds": round(time.monotonic() - w0, 3),
                     "discarded": True}
    log(f"  warm-up {arm['warmup']['seconds']}s ok={wr.ok} (discarded)")

    levels: dict[int, dict] = {}
    log("\nPART 2 -- AI-ON adaptive ramp (Slice 2 already measured through 10)")
    ramp = adaptive_ramp("on", player, crit, admission, AI_ON_CANDIDATES,
                         waves_for_ai, run_ids, levels, None,
                         expected_worker_pid=player.worker_pid)
    arm["ramp"] = ramp

    if ramp["first_fail"] and ramp["last_pass"]:
        arm["bracket"] = bracket(ramp["last_pass"], ramp["first_fail"], "on", player,
                                 crit, admission, waves_for_ai, run_ids, levels,
                                 expected_worker_pid=player.worker_pid)

    _confirm_capacity(arm, levels, "on", player, crit, admission,
                      waves_for_ai, run_ids, player.worker_pid)
    fails = [u for u, lv in sorted(levels.items())
             if lv["classification"]["result"] == "FAIL"]
    if fails:
        arm["repeatability_first_failure"] = repeat_level(
            min(fails), "on", player, crit, admission, waves_for_ai, run_ids,
            expected_worker_pid=player.worker_pid)

    arm["levels"] = {str(k): v for k, v in sorted(levels.items())}
    arm["player_identity"] = player.identity()
    log("  reaping the native Chat worker…")
    arm["teardown"] = player.stop()
    arm["gpu_transitions"].append(gpu_state("after_worker_reaped"))
    arm["gpu_transitions"].append(gpu_state("ai_on_end"))
    return arm


MAX_FALLBACK_RUNGS = 2


def _confirm_capacity(arm, levels, ai_mode, player, crit, admission, wave_fn,
                      run_ids, worker_pid) -> None:
    """Repeat the highest single-run-clean level; if it does not confirm, walk
    DOWN a bounded number of rungs looking for one that does.

    Without the walk-down the headline would either crash or be quoted from a
    level whose own repeats failed. The bound is explicit and what it skipped is
    logged, because a silent cap reads as 'we covered everything'.
    """
    clean = sorted((u for u, lv in levels.items()
                    if lv["classification"]["supports_capacity_claim"]), reverse=True)
    if not clean:
        arm["repeatability_note"] = "no level supported a capacity claim; nothing to repeat"
        log("  no level supported a capacity claim -- no repeats to run")
        return
    top = clean[0]
    arm["repeatability_highest_clean"] = repeat_level(
        top, ai_mode, player, crit, admission, wave_fn, run_ids,
        expected_worker_pid=worker_pid)
    r = arm["repeatability_highest_clean"]
    if r["successful_runs"] == r["total_runs"]:
        return
    log(f"  {top} users did NOT confirm ({r['summary']}); walking down at most "
        f"{MAX_FALLBACK_RUNGS} rung(s)")
    tried = []
    for cand in clean[1:1 + MAX_FALLBACK_RUNGS]:
        tried.append(cand)
        fb = repeat_level(cand, ai_mode, player, crit, admission, wave_fn, run_ids,
                          expected_worker_pid=worker_pid)
        arm["repeatability_fallback"] = fb
        if fb["successful_runs"] == fb["total_runs"]:
            log(f"  highest CONFIRMED level: {cand} ({fb['summary']})")
            break
    else:
        skipped = [u for u in clean[1 + MAX_FALLBACK_RUNGS:]]
        arm["repeatability_walkdown_exhausted"] = {
            "tried": tried, "not_tried": skipped,
            "note": (f"bounded at {MAX_FALLBACK_RUNGS} rungs; {len(skipped)} lower "
                     f"level(s) were NOT repeat-confirmed and are reported as "
                     f"unconfirmed rather than assumed good")}
        log(f"  walk-down exhausted after {tried}; {len(skipped)} lower level(s) "
            f"left UNCONFIRMED (not assumed good)")


def capacity_certificate(suite: dict) -> dict:
    """Four distinct concepts, never collapsed into one number.

    Headline FUNCTIONAL CAPACITY and HARD FAILURE values are only emitted when
    the required independent repeats actually passed. Attaching a repeat summary
    beside a number taken from one run would look like confirmation without
    being it.
    """
    def repeats_for(arm, users):
        for key in ("repeatability_highest_clean", "repeatability_first_failure",
                    "repeatability_fallback"):
            r = arm.get(key)
            if r and r.get("users") == users:
                return r
        return None

    def confirmed(arm, users, want_capacity=True):
        """Did `users` survive the required independent repeats?"""
        r = repeats_for(arm, users)
        if not r or r.get("total_runs", 0) < REPEATS:
            return False, (f"requires {REPEATS} independent repeats; "
                           f"{(r or {}).get('total_runs', 0)} were run")
        if want_capacity:
            ok = r["successful_runs"] == r["total_runs"]
            return ok, r["summary"]
        # for a hard-failure boundary, "confirmed" means it repeatably failed
        ok = r["runs_without_hard_failure"] == 0
        return ok, (f"{r['total_runs'] - r['runs_without_hard_failure']}"
                    f"/{r['total_runs']} FAILED")

    def summarise(arm_key):
        arm = suite.get(arm_key) or {}
        levels = {int(k): v for k, v in (arm.get("levels") or {}).items()}
        functional = [u for u, lv in levels.items()
                      if lv["failed"] == 0 and lv["classification"]["supports_capacity_claim"]]
        engineering = [u for u in functional
                       if levels[u]["classification"]["result"] == "PASS"]
        knee = sorted(u for u, lv in levels.items()
                      if lv["classification"]["result"] == "DEGRADED")
        fails = sorted(u for u, lv in levels.items()
                       if lv["classification"]["result"] == "FAIL")
        lgl = sorted(u for u, lv in levels.items() if lv["load_generator"]["material"])

        # ---- D6: a headline requires the repeats, it does not merely carry them
        fc_single = max(functional) if functional else None
        fc_value, fc_basis = NOT_AVAILABLE, "no level supported a capacity claim"
        if fc_single is not None:
            ok, why = confirmed(arm, fc_single, want_capacity=True)
            if ok:
                fc_value, fc_basis = fc_single, f"confirmed by repeats: {why}"
            else:
                fc_basis = (f"{fc_single} passed a single run but is NOT confirmed "
                            f"({why}); see repeatability_fallback")
                for cand in sorted((u for u in functional if u < fc_single), reverse=True):
                    ok2, why2 = confirmed(arm, cand, want_capacity=True)
                    if ok2:
                        fc_value = cand
                        fc_basis += f"; highest CONFIRMED level is {cand} ({why2})"
                        break

        # ---- D5: a timeout-policy failure is not a server hard limit
        hf_value, hf_basis = NOT_AVAILABLE, "no hard failure was reached"
        timeout_limited = []
        server_fail = []
        for u in fails:
            hs = levels[u]["classification"]["hard_failures"] or []
            # Require at least one hard failure that is NOT solely a timeout
            # policy outcome. Deriving this from the single `bottleneck` label
            # would hide a real 5xx behind a co-occurring timeout.
            non_timeout = [h for h in hs if "TIMEOUT POLICY" not in h]
            (server_fail if non_timeout else timeout_limited).append(u)
        if fails:
            hf_value = min(fails)
            ok, why = confirmed(arm, hf_value, want_capacity=False)
            hf_basis = (f"confirmed by repeats: {why}" if ok else
                        f"observed once at {hf_value} but NOT confirmed ({why})")
            if not ok:
                hf_value = NOT_AVAILABLE

        shl_ok = bool(server_fail) and not lgl
        return {
            "functional_capacity": {
                "value": fc_value,
                "highest_single_run_clean": fc_single if fc_single is not None else NOT_AVAILABLE,
                "basis": fc_basis,
                "definition": ("highest tested concurrency at which every synthetic "
                               "session completed, the level supported a claim at "
                               f"that number, and {REPEATS} independent repeats "
                               "all proved it"),
                "repeat_runs": (repeats_for(arm, fc_value) or {}).get("summary", NOT_AVAILABLE)},
            "engineering_capacity": {
                "value": max(engineering) if engineering else NOT_AVAILABLE,
                "definition": ("highest tested concurrency still inside the Slice 2 "
                               "frozen engineering calibration criteria"),
                "not": "a customer SLA"},
            "engineering_knee": {
                "value": min(knee) if knee else NOT_AVAILABLE,
                "definition": "first concurrency flagged DEGRADED against frozen criteria"},
            "hard_failure": {
                "value": hf_value,
                "first_observed_single_run": min(fails) if fails else NOT_AVAILABLE,
                "basis": hf_basis,
                "definition": "first concurrency with a repeatably objective hard failure",
                # Parenthesised deliberately: `X if C else {} or {}` binds as
                # `X if C else ({} or {})`, so when `fails` is truthy a None
                # from repeats_for() reached .get() and crashed the certificate.
                "repeat_runs": ((repeats_for(arm, min(fails)) if fails else None)
                                or {}).get("summary", NOT_AVAILABLE)},
            "timeout_policy_limit": {
                "value": min(timeout_limited) if timeout_limited else NOT_AVAILABLE,
                "definition": ("first concurrency whose only hard failures were "
                               "request-timeout outcomes"),
                "note": ("a configured timeout expiring is a POLICY boundary. The "
                         "server did not break; it was told to stop waiting. "
                         "Raising the timeout moves this number.")},
            "load_generator_limit": {
                "value": min(lgl) if lgl else NOT_AVAILABLE,
                "definition": (f"first concurrency at which the local harness used "
                               f">= {LOADGEN_MATERIAL_PCT_OF_HOST}% of host CPU")},
            "server_hard_limit": {
                "value": (min(server_fail) if shl_ok else NOT_AVAILABLE),
                "isolated": shl_ok,
                "definition": ("claimed only when a hard failure that was NOT solely a "
                               "timeout-policy outcome was reached, repeatably, without "
                               "the local load generator being material"),
                "excluded_timeout_policy_levels": timeout_limited or None},
            "levels_tested": sorted(levels),
        }

    return {
        "kind": "SLICE 3 CAPACITY FINDINGS",
        "not": "a certified customer capacity",
        "ai_off": summarise("ai_off"),
        "ai_on": summarise("ai_on"),
        "customer_acceptable_capacity": {
            "value": "NOT YET DETERMINED",
            "reason": ("Donnie has not specified an acceptable maximum booking or AI "
                       "wait, nor a contractual response-time target. The engineering "
                       "calibration criteria used here are relative to this server's "
                       "own 2-user behaviour and are not a substitute for a business "
                       "SLA.")},
    }


def main() -> int:
    suite = {"schema_version": 1, "kind": "SLICE 3 ADAPTIVE FULL-SERVER LIMIT FINDER",
             "not": "certified customer capacity",
             "started_utc": datetime.now(timezone.utc).isoformat(),
             "application": repo_commit(), "server_hardware": host_identity(),
             "scenario": "MIXED RIDE LIFECYCLE",
             "lifecycle_profiles": list(lifecycle.PROFILES),
             "session_count_policy": {
                 "ai_off": f"waves = ceil({TARGET_SESSIONS_AI_OFF} / users); "
                           f"sessions = waves x users >= {TARGET_SESSIONS_AI_OFF}",
                 "ai_on": "3 waves <=32 users, 2 waves <=96, 1 EXPLORATORY wave above",
                 "why": ("Slice 2 used constant duration, which gave low-concurrency "
                         "levels far more sessions than high-concurrency levels and "
                         "produced a non-monotonic AI-OFF result at 6 users")},
             "max_users_cap": MAX_USERS,
             "request_timeout_s": REQUEST_TIMEOUT}

    log("=" * 96)
    log("SLICE 3 — ADAPTIVE FULL-SERVER LIMIT FINDER — MIXED RIDE LIFECYCLE")
    log("=" * 96)

    pre = gpu_state("preflight")
    suite["preflight"] = pre
    log(f"preflight: VRAM {pre['vram_used_mib']} MiB, compute apps {pre['compute_apps']}, "
        f"legacy {pre['legacy_symoneural_llm_pids']}")
    if pre["compute_apps"] or pre["legacy_symoneural_llm_pids"]:
        log("ABORT: unexpected GPU compute ownership"); return 2
    baseline = pre["vram_used_mib"]
    suite["baseline_vram_mib"] = {"value": baseline, "label": "MEASURED AT THIS RUN",
                                  "note": ("re-measured every run; a KDE/X11 desktop "
                                           "session holds graphics memory and that is "
                                           "part of the real machine state")}

    suite["server_admission"] = server_admission_limit()
    a = suite["server_admission"]
    log(f"server admission: {a.get('max_concurrent_sync_handlers')} concurrent sync "
        f"handlers (anyio {a.get('anyio_version')}) — MEASURED SERVER CONFIGURATION")
    log(f"host: {HOST_CORES} logical CPUs; load-generator materiality at "
        f"{LOADGEN_MATERIAL_PCT_OF_HOST}% of host")

    frozen = load_frozen_criteria()
    suite["frozen_criteria"] = frozen
    log(f"frozen criteria loaded from {Path(SLICE2_REPORT).name} (NOT re-frozen)")

    run_ids: list[str] = []
    suite["legacy_unit_before"] = legacy_unit_state("before_suite")
    log(f"legacy unit before: {suite['legacy_unit_before'].get('ActiveState')} "
        f"NRestarts={suite['legacy_unit_before'].get('NRestarts')}")

    # Suite-wide process identity, running across BOTH arms. Per-level observers
    # answer "during this level"; this one answers "at any point in the suite".
    suite_procs = ProcessIdentityObserver().start()

    log("\n" + "-" * 96)
    log("ARM 1: AI OFF")
    log("-" * 96)
    suite["ai_off"] = run_ai_off(frozen["ai_off"], a, baseline, run_ids)

    mid = gpu_state("between_arms")
    suite["between_arms"] = mid
    log(f"\nbetween arms: VRAM {mid['vram_used_mib']} MiB, apps {mid['compute_apps']}")
    if mid["vram_used_mib"] > baseline + 256 or mid["compute_apps"]:
        suite["error"] = "baseline not restored between arms"
        _persist(suite); return 3

    log("\n" + "-" * 96)
    log("ARM 2: AI ON")
    log("-" * 96)
    try:
        suite["ai_on"] = run_ai_on(frozen["ai_on"], a, baseline, run_ids)
    except Exception as e:                                          # noqa: BLE001
        suite["ai_on_error"] = f"{type(e).__name__}: {e}"
        log(f"AI ON arm raised: {e}")
        _persist(suite); return 5

    post = gpu_state("final")
    suite["final"] = post
    suite["finished_utc"] = datetime.now(timezone.utc).isoformat()
    suite["run_ids"] = run_ids
    suite_procs.stop()
    observed = suite_procs.report()
    suite["legacy_unit_after"] = legacy_unit_state("after_suite")
    before, after = suite["legacy_unit_before"], suite["legacy_unit_after"]
    unit_unchanged = (before.get("NRestarts") == after.get("NRestarts")
                      and before.get("ExecMainStartTimestamp")
                      == after.get("ExecMainStartTimestamp")
                      and "NRestarts" in before)

    # OBSERVED, never asserted. The previous version wrote 0 into these fields
    # as a literal and presented it as a finding.
    suite["engine_executions"] = {
        "method": ("continuous /proc observation across the whole suite, plus the "
                   "systemd unit's own restart counter for the legacy engine"),
        "process_observation": observed,
        "symoneural_llm_executions": observed["symoneural_llm_executions"],
        "symoneural_llm_unit_unchanged": unit_unchanged,
        "symoneural_llm_unit_before": before,
        "symoneural_llm_unit_after": after,
        "image_worker_executions": observed["image_worker_executions"],
        "native_chat_worker_executions": observed["native_chat_worker_executions"],
        "api_chat_used": False,
        "api_chat_basis": ("the native player has no code path to /api/chat; see "
                           "player_identity.legacy_paths_used"),
        "gpu_transitions_clear": all(
            not t["legacy_symoneural_llm_pids"]
            for arm in ("ai_off", "ai_on")
            for t in suite[arm]["gpu_transitions"]) and not post["legacy_symoneural_llm_pids"],
    }
    suite["baseline_restored"] = (post["vram_used_mib"] <= baseline + 256
                                  and post["compute_apps"] == 0)

    # The check nothing in the harness previously performed: after every level
    # cleaned up, is the store actually empty? The aborted first run left 32
    # synthetic bookings behind and no code noticed.
    suite["synthetic_data_final"] = final_synthetic_check()
    sd = suite["synthetic_data_final"]
    log(f"synthetic data remaining: {sd.get('synthetic_remaining')} "
        f"(all bookings: {sd.get('all_remaining')}) -> {'CLEAN' if sd.get('clean') else 'DIRTY'}")

    suite["capacity"] = capacity_certificate(suite)
    if not sd.get("clean"):
        suite["suite_hard_failure"] = (
            f"benchmark data isolation FAILED: {sd.get('synthetic_remaining')} "
            f"synthetic booking(s) remained after cleanup")
    log(f"\nfinal: VRAM {post['vram_used_mib']} MiB, apps {post['compute_apps']}, "
        f"legacy {post['legacy_symoneural_llm_pids']}, "
        f"baseline_restored={suite['baseline_restored']}")
    _persist(suite)
    _csv(suite)
    if suite.get("suite_hard_failure"):
        return 6
    return 0 if suite["baseline_restored"] else 4


STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")


def _persist(suite) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = REPORT_DIR / f"SUITE-slice3-{STAMP}.json"
    p.write_text(json.dumps(suite, indent=2, default=str) + "\n")
    suite["suite_report_path"] = str(p)
    print(f"\nsuite report: {p}", flush=True)


def _csv(suite) -> None:
    rows = ["ai_mode,users,label,waves,sessions,completed,failed,achieved_concurrency,"
            "concurrency_achieved,throughput_sps,op_p50_ms,op_p95_ms,op_p99_ms,"
            "session_p95_ms,ai_p50_ms,ai_p95_ms,ai_p99_ms,queue_wait_p95_ms,"
            "service_p95_ms,queue_depth_max,tok_per_s_p50,gpu_util_avg,gpu_util_max,"
            "vram_max_mib,power_avg_w,power_max_w,temp_max_c,cpu_avg,cpu_max,"
            "ram_max_mib,server_threads_max,loadgen_pct_host,error_rate_pct,samples,"
            "result,bottleneck"]
    for mode in ("ai_off", "ai_on"):
        arm = suite.get(mode) or {}
        for users, lv in sorted((arm.get("levels") or {}).items(), key=lambda x: int(x[0])):
            t, ai = lv["telemetry"], lv["ai"]
            g = t.get("gpu") if isinstance(t.get("gpu"), dict) else {}
            sy = t.get("system") if isinstance(t.get("system"), dict) else {}
            def v(d, k, s="p95"):
                x = d.get(k) if isinstance(d, dict) else None
                return x.get(s, "") if isinstance(x, dict) else ""
            n = lv["sessions_total"] or 1
            rows.append(",".join(str(x) for x in [
                mode, users, lv["measurement_label"], lv["waves"], lv["sessions_total"],
                lv["completed"], lv["failed"], lv["achieved_max_concurrency"],
                lv["concurrency_achieved"], lv["throughput_sessions_per_s"],
                v(lv["application"], "operation_latency_ms", "p50"),
                v(lv["application"], "operation_latency_ms", "p95"),
                v(lv["application"], "operation_latency_ms", "p99"),
                v(lv["application"], "session_latency_ms", "p95"),
                v(ai, "latency_ms", "p50"), v(ai, "latency_ms", "p95"),
                v(ai, "latency_ms", "p99"), v(ai, "queue_wait_ms", "p95"),
                v(ai, "service_ms", "p95"),
                ai.get("queue_depth_max", "") if isinstance(ai, dict) else "",
                v(ai, "tokens_per_s", "p50"),
                (g.get("utilization_pct") or {}).get("avg", ""),
                (g.get("utilization_pct") or {}).get("max", ""),
                (g.get("vram_used_mib") or {}).get("max", ""),
                (g.get("power_w") or {}).get("avg", ""),
                (g.get("power_w") or {}).get("max", ""),
                (g.get("temperature_c") or {}).get("max", ""),
                (sy.get("cpu_pct") or {}).get("avg", ""),
                (sy.get("cpu_pct") or {}).get("max", ""),
                (sy.get("ram_used_mib") or {}).get("max", ""),
                lv["server_process"].get("server_threads_max", ""),
                lv["load_generator"]["harness_cpu_pct_of_host"],
                round(100.0 * lv["failed"] / n, 2),
                t["sample_count"], lv["classification"]["result"],
                lv["bottleneck"]["classification"]]))
    p = REPORT_DIR / f"SUITE-slice3-{STAMP}.csv"
    p.write_text("\n".join(rows) + "\n")
    print(f"graph csv    : {p}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
