#!/usr/bin/env python3
"""Slice 2 calibration suite: 2/4/6/8/10 concurrent users, mixed ride lifecycle.

Concurrency is per WAVE. Each wave releases exactly N synthetic users on a
barrier; waves repeat until the measurement window is defensible. Repetitions do
NOT increase concurrency -- "4 users x 12 waves" is 4 concurrent users, 48
sessions, and it is reported that way.

For AI ON the model is loaded ONCE for the whole suite: cold start is measured
separately, one warm-up inference is discarded, and every concurrency level is
then a steady-state measurement of the same resident worker.

The 2-user arm is measured FIRST and FROZEN before 4/6/8/10 run, so degradation
criteria cannot be tuned after seeing the results.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capacity_lab.core import (NOT_AVAILABLE, Sampler, host_identity,  # noqa: E402
                              known_run_ids, new_run_id, percentiles, repo_commit,
                              summarise, REPORT_DIR)
from capacity_lab import lifecycle                                     # noqa: E402
from capacity_lab.harness import _legacy_engine_pids                   # noqa: E402
from capacity_lab.players import NullPlayer                            # noqa: E402
from capacity_lab.scenario import LifecycleScenario, SessionResult     # noqa: E402

BASE = "http://127.0.0.1:8811"
LEVELS = (2, 4, 6, 8, 10)
SAMPLE_INTERVAL = 0.05

# Minimum measurement window. Whichever takes longest wins -- a level that
# finishes fast keeps running waves until its telemetry is defensible.
MIN_SECONDS = 5.0
MIN_SAMPLES = 30
MIN_WAVES_AI_OFF = 5
MIN_WAVES_AI_ON = 3
MAX_WAVES = 200                # runaway guard

# FROZEN before 4/6/8/10 are seen. Engineering calibration criteria, not an SLA.
DEGRADE_LATENCY_RATIO = 2.0
DEGRADE_AI_RATIO = 2.0


def _proc_cpu_ram(pid: int) -> dict:
    """Load-generator accounting. The harness runs on the same host as the server,
    and pretending otherwise would overstate the server's headroom."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            p = fh.read().split()
        utime, stime = int(p[13]), int(p[14])
        with open(f"/proc/{pid}/status") as fh:
            rss = next(int(l.split()[1]) for l in fh if l.startswith("VmRSS"))
        return {"cpu_ticks": utime + stime, "rss_mib": round(rss / 1024, 1)}
    except Exception:
        return {}


def measure_sampler_overhead(seconds=2.0) -> dict:
    """How much CPU the telemetry collector itself costs. If the measurer is a
    material load generator, the measurement is contaminated."""
    pid = os.getpid()
    a = _proc_cpu_ram(pid)
    t0 = time.monotonic()
    s = Sampler(interval=SAMPLE_INTERVAL).start()
    time.sleep(seconds)
    s.stop()
    dt = time.monotonic() - t0
    b = _proc_cpu_ram(pid)
    ticks = b.get("cpu_ticks", 0) - a.get("cpu_ticks", 0)
    hz = os.sysconf("SC_CLK_TCK")
    cpu_s = ticks / hz
    return {"interval_s": SAMPLE_INTERVAL, "window_s": round(dt, 2),
            "samples": len(s.samples),
            "sampler_cpu_seconds": round(cpu_s, 3),
            "sampler_cpu_pct_of_one_core": round(100.0 * cpu_s / dt, 2),
            "note": ("cost of the telemetry collector itself, measured not assumed")}


class Level:
    """One concurrency level: N users x repeated synchronized waves."""

    def __init__(self, run_id, users, ai_mode, player, timeout=300.0):
        self.run_id, self.users, self.ai_mode = run_id, users, ai_mode
        self.player, self.timeout = player, timeout
        self.sessions: list[SessionResult] = []
        self.waves = 0
        self.max_active = 0
        self._active = 0
        self._lock = threading.Lock()
        self.assignments: list[dict] = []

    def _one(self, barrier, slot, wave, profile) -> SessionResult:
        sid = f"{self.run_id}-W{wave:02d}U{slot:02d}"
        scen = LifecycleScenario(profile=profile, wave=wave)
        try:
            barrier.wait(timeout=60)
        except threading.BrokenBarrierError:
            pass
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
        min_waves = MIN_WAVES_AI_OFF if self.ai_mode == "off" else MIN_WAVES_AI_ON
        sampler = Sampler(interval=SAMPLE_INTERVAL).start()
        harness_pid = os.getpid()
        lg0 = _proc_cpu_ram(harness_pid)
        t0 = time.monotonic()

        while True:
            wave = self.waves
            assign = lifecycle.assign(slots, wave)
            self.assignments.append({"wave": wave, "assignment": dict(assign)})
            barrier = threading.Barrier(self.users)
            with ThreadPoolExecutor(max_workers=self.users) as ex:
                futs = [ex.submit(self._one, barrier, s, wave, assign[s]) for s in slots]
                for f in futs:
                    try:
                        self.sessions.append(f.result(timeout=self.timeout * 3))
                    except Exception as e:                       # noqa: BLE001
                        self.sessions.append(SessionResult(
                            f"{self.run_id}-W{wave:02d}Uxx", self.run_id, False,
                            t0, time.monotonic(), [], None,
                            f"harness: {type(e).__name__}: {e}"))
            self.waves += 1
            elapsed = time.monotonic() - t0
            enough = (self.waves >= min_waves and elapsed >= MIN_SECONDS
                      and len(sampler.samples) >= MIN_SAMPLES)
            if enough or self.waves >= MAX_WAVES:
                break

        sampler.stop()
        wall = time.monotonic() - t0
        lg1 = _proc_cpu_ram(harness_pid)
        hz = os.sysconf("SC_CLK_TCK")
        lg_cpu_s = (lg1.get("cpu_ticks", 0) - lg0.get("cpu_ticks", 0)) / hz
        return self._summarise(sampler, wall, lg_cpu_s, lg1)

    def _summarise(self, sampler, wall, lg_cpu_s, lg1) -> dict:
        done = [s for s in self.sessions if s.ok]
        failed = [s for s in self.sessions if not s.ok]

        sess_ms = [s.duration_s * 1000 for s in done]
        # per-operation-class latency: only the measured operation step
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
        if ai_rows:
            waits = [w * 1000 for w in
                     (getattr(a, "queue_wait_s", None) for a in ai_rows) if w is not None]
            svc = [x * 1000 for x in
                   (getattr(a, "service_s", None) for a in ai_rows) if x is not None]
            toks = [a.tok_per_s for a in ai_rows if a.tok_per_s is not None]
            ai = {"requests": len(ai_rows),
                  "errors": sum(1 for a in ai_rows if not a.ok),
                  "latency_ms": percentiles([a.latency_s * 1000 for a in ai_rows]),
                  "queue_wait_ms": percentiles(waits) if waits else NOT_AVAILABLE,
                  "service_ms": percentiles(svc) if svc else NOT_AVAILABLE,
                  "tokens_per_s": percentiles(toks) if toks else NOT_AVAILABLE,
                  "time_to_first_token_ms": NOT_AVAILABLE,
                  "ttft_note": "worker returns a completed generation; no first-token event"}
            if hasattr(self.player, "metrics"):
                m = self.player.metrics()
                active = m.get("max_active_ai_requests", 0)
                depth = m.get("max_queue_depth", 0)
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

        return {
            "requested_concurrency": self.users,
            "achieved_max_concurrency": self.max_active,
            "waves": self.waves,
            "sessions_total": len(self.sessions),
            "concurrency_per_wave": self.users,
            "operation_mix": lifecycle.coverage(list(range(1, self.users + 1)), self.waves),
            "wave_assignments": self.assignments,
            "completed": len(done), "failed": len(failed),
            "wall_seconds": round(wall, 3),
            "throughput_sessions_per_s": round(len(done) / wall, 2) if wall > 0 else NOT_AVAILABLE,
            "application": {
                "session_latency_ms": percentiles(sess_ms),
                "operation_latency_ms": percentiles(op_ms),
                "operation_latency_by_class_ms": {k: percentiles(v) for k, v in sorted(by_op.items())},
                "setup_latency_ms": percentiles(setup_ms),
                "http_status_counts": http,
                "timeouts": sum(1 for s in self.sessions
                                if s.error and "timeout" in s.error.lower()),
            },
            "ai": ai,
            "telemetry": sampler.statistics(),
            "load_generator": {
                "location": "LOCAL / SAME HOST",
                "harness_cpu_seconds": round(lg_cpu_s, 3),
                "harness_cpu_pct_of_one_core": round(100.0 * lg_cpu_s / wall, 2) if wall > 0 else NOT_AVAILABLE,
                "harness_rss_mib": lg1.get("rss_mib", NOT_AVAILABLE),
                "note": ("the synthetic clients run on the server under test; this "
                         "consumption is included in the CPU/RAM figures above"),
            },
            "errors": [{"session": s.session_id, "error": s.error} for s in failed] or None,
        }


# =========================================================== degradation criteria
def freeze_criteria(ref2: dict, ai_mode: str) -> dict:
    """Frozen from the 2-user arm BEFORE 4/6/8/10 run.

    These are ENGINEERING CALIBRATION CRITERIA, not a contractual SLA and not a
    certified customer capacity. They are relative to this server's own 2-user
    behaviour because Donnie has defined no absolute targets.
    """
    app = ref2["application"]
    crit = {
        "kind": "ENGINEERING CALIBRATION CRITERIA",
        "not": "contractual SLA / certified customer capacity",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_concurrency": 2,
        "latency_ratio_threshold": DEGRADE_LATENCY_RATIO,
        "operation_p95_ms_ref": app["operation_latency_ms"].get("p95"),
        "session_p95_ms_ref": app["session_latency_ms"].get("p95"),
        "cpu_max_ref": ref2["telemetry"]["system"]["cpu_pct"].get("max")
                       if ref2["telemetry"]["system"] != NOT_AVAILABLE else NOT_AVAILABLE,
        "ram_max_ref": ref2["telemetry"]["system"]["ram_used_mib"].get("max")
                       if ref2["telemetry"]["system"] != NOT_AVAILABLE else NOT_AVAILABLE,
    }
    if ai_mode == "on" and isinstance(ref2["ai"].get("latency_ms"), dict):
        crit.update({
            "ai_ratio_threshold": DEGRADE_AI_RATIO,
            "ai_p95_ms_ref": ref2["ai"]["latency_ms"].get("p95"),
            "ai_queue_wait_p95_ms_ref": (ref2["ai"]["queue_wait_ms"].get("p95")
                                         if isinstance(ref2["ai"].get("queue_wait_ms"), dict)
                                         else NOT_AVAILABLE),
            "ai_service_p95_ms_ref": (ref2["ai"]["service_ms"].get("p95")
                                      if isinstance(ref2["ai"].get("service_ms"), dict)
                                      else NOT_AVAILABLE),
            "queue_dominant_rule": "queue_wait_p95 >= service_time_p95",
        })
    return crit


def classify(level: dict, crit: dict) -> dict:
    """PASS / DEGRADED-* / FAIL. FAIL only on objective hard failure."""
    flags, hard = [], []
    if level["failed"] > 0:
        hard.append(f"{level['failed']} session(s) failed")
    for code, n in level["application"]["http_status_counts"].items():
        if code.isdigit() and code.startswith("5"):
            hard.append(f"HTTP {code} x{n}")
    if level["application"]["timeouts"]:
        hard.append(f"{level['application']['timeouts']} timeout(s)")
    if isinstance(level["ai"], dict) and level["ai"].get("errors"):
        hard.append(f"{level['ai']['errors']} AI error(s)")
    t = level["telemetry"]
    if t.get("series_sufficient") is False:
        flags.append("SERIES INSUFFICIENT -- not usable for a capacity conclusion")
    if isinstance(t.get("gpu"), dict) and t["gpu"].get("max_simultaneous_compute_apps", 0) > 1:
        hard.append("more than one GPU owner")

    # relative degradation vs the frozen 2-user reference
    ratios = {}
    ref = crit.get("operation_p95_ms_ref")
    cur = level["application"]["operation_latency_ms"].get("p95")
    if isinstance(ref, (int, float)) and isinstance(cur, (int, float)) and ref > 0:
        ratios["operation_p95_ratio"] = round(cur / ref, 2)
        if cur / ref >= crit["latency_ratio_threshold"]:
            flags.append(f"DEGRADED - LATENCY ({cur/ref:.2f}x the 2-user reference)")
    aref = crit.get("ai_p95_ms_ref")
    acur = (level["ai"].get("latency_ms") or {}).get("p95") if isinstance(level["ai"], dict) else None
    if isinstance(aref, (int, float)) and isinstance(acur, (int, float)) and aref > 0:
        ratios["ai_p95_ratio"] = round(acur / aref, 2)
        if acur / aref >= crit.get("ai_ratio_threshold", 2.0):
            flags.append(f"DEGRADED - AI LATENCY ({acur/aref:.2f}x)")
    if isinstance(level["ai"], dict):
        qw = (level["ai"].get("queue_wait_ms") or {})
        sv = (level["ai"].get("service_ms") or {})
        if isinstance(qw, dict) and isinstance(sv, dict):
            q95, s95 = qw.get("p95"), sv.get("p95")
            if isinstance(q95, (int, float)) and isinstance(s95, (int, float)):
                ratios["queue_wait_over_service_p95"] = round(q95 / s95, 2) if s95 else None
                if q95 >= s95:
                    flags.append(f"DEGRADED - QUEUE (queue wait p95 {q95} ms >= "
                                 f"service p95 {s95} ms)")
    # resource markers: reported, never auto-converted to FAIL
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
            "ratios": ratios}


# ================================================================ orchestration
#: Declared but refuses to run -- the same shape `BookingScenario` uses, and for the same
#: reason: the dependency is absent, so every field it would fill reports NOT AVAILABLE
#: rather than a guess.
#:
#: As recovered on 2026-09-10 this function did:
#:
#:     sys.path.insert(0, str(Path("/home/google/Symoneural/.claude/worktrees/"
#:                                 "native-hybrid-gpu-player/engines/symoneural-hybrid")))
#:     import gpu_guard
#:
#: Measured that day, and all three are independently fatal:
#:
#:   - that worktree does not exist. `.claude/worktrees/` holds only `authority-plane-plan/`
#:   - `gpu_guard` was **never committed on any ref** -- `git log --glob=refs/*` over the
#:     whole history returns nothing for it, and it is nowhere on disk. It was not lost in
#:     a merge; it was never in this repository
#:   - `engines/symoneural-<name>/` is the superseded layout. Engines live at
#:     `symoneural-<name>/` in the repo root now
#:
#: So the import raised `ModuleNotFoundError` three layers down, which is a worse failure
#: than an honest refusal: a caller reading a traceback about a missing module learns
#: nothing about why the reading is unavailable.
#:
#: The hardcoded path is not preserved even in a broken form. A first-party file reaching
#: into `.claude/worktrees/` is the defect class `symoneural-audit` exists to catch, and
#: its README carries the rule directly -- never count parents to find the repository root.
#:
#: **The first-party replacement already exists** and is not wired in here, because that is
#: past the path fix this recovery authorises: `tools/lease_proof_2p.py:75` `compute_apps()`
#: returns pid -> MiB from `nvidia-smi --query-compute-apps`, and `:91` `vram()` returns the
#: card reading. Between them they are exactly what `gpu_guard.compute_apps()` and
#: `gpu_guard.gpu_snapshot()` supplied. Wiring them up is a real change with a real test,
#: and it belongs in its own commit.
GPU_STATE_UNAVAILABLE = (
    "gpu_guard was never committed on any ref and is not on disk; "
    "see the note above suite.gpu_state and tools/lease_proof_2p.py"
)


def gpu_state(label: str) -> dict:
    """The GPU reading around a run. Declared, refuses, reports why.

    `_legacy_engine_pids()` is first-party and still answers, so it is still reported --
    zero-filling a field that *can* be measured would be the mirror of the mistake this
    function is avoiding.
    """
    return {"label": label,
            "available": False,
            "reason": GPU_STATE_UNAVAILABLE,
            "vram_used_mib": NOT_AVAILABLE,
            "compute_apps": NOT_AVAILABLE,
            "compute_pids": NOT_AVAILABLE,
            "legacy_symoneural_llm_pids": _legacy_engine_pids(),
            "power_w": NOT_AVAILABLE,
            "util_pct": NOT_AVAILABLE}


def clear_run(run_id: str) -> dict:
    from capacity_lab.harness import _delete
    ok, _l, st, doc, err = _delete(BASE, f"/api/dispatchos/benchmark/{run_id}", 60)
    return ({"state": "removed", **(doc or {})} if ok
            else {"state": "cleanup FAILED", "http_status": st, "error": err})


def run_arm(ai_mode: str, baseline: int, log) -> dict:
    """One full arm: 2/4/6/8/10 at a single AI mode.

    For AI ON the worker is loaded ONCE before level 2 and reaped after level 10,
    so 4/6/8/10 are steady-state measurements of the same resident model.
    """
    arm = {"ai_mode": "ENABLED" if ai_mode == "on" else "DISABLED",
           "levels": {}, "gpu_transitions": []}
    player = None
    run_ids = []

    arm["gpu_transitions"].append(gpu_state(f"arm_start_ai_{ai_mode}"))
    if ai_mode == "off":
        st = arm["gpu_transitions"][-1]
        if st["compute_apps"] or st["legacy_symoneural_llm_pids"]:
            raise RuntimeError(f"AI OFF requires an idle card: {st}")
    else:
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
                             "note": "measured once; excluded from every steady-state figure"}
        arm["gpu_transitions"].append(gpu_state("after_worker_ready"))
        log(f"  cold start {player.cold_start_s}s pid={player.worker_pid} "
            f"proc={player.worker_vram_mib} MiB")
        log("  warm-up inference (DISCARDED, not in any percentile)…")
        w0 = time.monotonic()
        wr = player.invoke("Warm up. Reply with one short word.", timeout=300)
        arm["warmup"] = {"ok": wr.ok, "seconds": round(time.monotonic() - w0, 3),
                         "discarded": True,
                         "note": "not included in measured percentiles"}
        log(f"  warm-up {arm['warmup']['seconds']}s ok={wr.ok} (discarded)")
    if player is None:
        player = NullPlayer()

    criteria = None
    for users in LEVELS:
        rid = new_run_id(datetime.now(), known_run_ids() + run_ids)
        run_ids.append(rid)
        log(f"  level {users:2d} users … ", end="")
        lvl = Level(rid, users, ai_mode, player).run()
        lvl["run_id"] = rid
        lvl["cleanup"] = clear_run(rid)
        if users == 2:
            criteria = freeze_criteria(lvl, ai_mode)
            arm["frozen_2_user_reference"] = lvl
            arm["frozen_criteria"] = criteria
            log("(2-user reference FROZEN) ", end="")
        lvl["classification"] = classify(lvl, criteria or {})
        arm["levels"][str(users)] = lvl
        t = lvl["telemetry"]
        log(f"waves={lvl['waves']:3d} sessions={lvl['sessions_total']:4d} "
            f"ok={lvl['completed']:4d} fail={lvl['failed']:3d} "
            f"op_p95={lvl['application']['operation_latency_ms'].get('p95')} ms "
            f"samples={t['sample_count']} -> {lvl['classification']['result']}")
        if lvl["classification"]["flags"]:
            for f in lvl["classification"]["flags"]:
                log(f"        flag: {f}")
        if lvl["classification"]["result"] == "FAIL":
            log("        HARD FAILURE -- stopping this arm")
            arm["stopped_early"] = f"hard failure at {users} users"
            break

    if ai_mode == "on":
        log("  reaping the native Chat worker…")
        arm["teardown"] = player.stop()
        arm["gpu_transitions"].append(gpu_state("after_worker_reaped"))
    arm["gpu_transitions"].append(gpu_state(f"arm_end_ai_{ai_mode}"))
    arm["run_ids"] = run_ids
    return arm


def main() -> int:
    def log(*a, **kw):
        print(*a, **kw, flush=True)

    suite = {"schema_version": 1, "kind": "SLICE 2 CALIBRATION",
             "not": "certified customer capacity",
             "started_utc": datetime.now(timezone.utc).isoformat(),
             "application": repo_commit(), "server_hardware": host_identity(),
             "scenario": "MIXED RIDE LIFECYCLE",
             "levels_tested": list(LEVELS),
             "measurement_window": {"min_seconds": MIN_SECONDS, "min_samples": MIN_SAMPLES,
                                    "min_waves_ai_off": MIN_WAVES_AI_OFF,
                                    "min_waves_ai_on": MIN_WAVES_AI_ON,
                                    "rule": "whichever requirement takes longest"},
             "lifecycle_profiles": list(lifecycle.PROFILES)}

    log("=" * 92)
    log("SLICE 2 CALIBRATION — MIXED RIDE LIFECYCLE — 2/4/6/8/10 CONCURRENT USERS")
    log("=" * 92)

    pre = gpu_state("suite_preflight")
    suite["preflight"] = pre
    log(f"preflight: VRAM {pre['vram_used_mib']} MiB, compute apps {pre['compute_apps']}, "
        f"legacy {pre['legacy_symoneural_llm_pids']}")
    if pre["compute_apps"] or pre["legacy_symoneural_llm_pids"]:
        log("ABORT: card is not at baseline"); return 2
    baseline = pre["vram_used_mib"]
    suite["baseline_vram_mib"] = baseline

    log("\nmeasuring sampler overhead…")
    suite["sampler_overhead"] = measure_sampler_overhead()
    o = suite["sampler_overhead"]
    log(f"  interval {o['interval_s']}s -> {o['samples']} samples in {o['window_s']}s, "
        f"sampler CPU {o['sampler_cpu_pct_of_one_core']}% of one core")

    log("\n" + "-" * 92)
    log("ARM 1: AI OFF (booking system only, GPU at baseline)")
    log("-" * 92)
    suite["ai_off"] = run_arm("off", baseline, log)

    mid = gpu_state("between_arms")
    suite["between_arms"] = mid
    log(f"\nbetween arms: VRAM {mid['vram_used_mib']} MiB, apps {mid['compute_apps']}")
    if mid["vram_used_mib"] > baseline + 256 or mid["compute_apps"]:
        log("ABORT: baseline not restored between arms"); 
        suite["error"] = "baseline not restored between arms"
        _persist(suite); return 3

    log("\n" + "-" * 92)
    log("ARM 2: AI ON (booking system + SyMon AI, ONE resident native worker)")
    log("-" * 92)
    suite["ai_on"] = run_arm("on", baseline, log)

    post = gpu_state("suite_final")
    suite["final"] = post
    suite["finished_utc"] = datetime.now(timezone.utc).isoformat()
    suite["legacy_engine"] = {
        "symoneural_llm_executions": 0,
        "verified_absent_at_every_transition": all(
            not t["legacy_symoneural_llm_pids"]
            for arm in ("ai_off", "ai_on")
            for t in suite[arm]["gpu_transitions"]) and not post["legacy_symoneural_llm_pids"],
        "api_chat_used": False, "image_worker_executions": 0}
    log(f"\nfinal: VRAM {post['vram_used_mib']} MiB, apps {post['compute_apps']}, "
        f"legacy {post['legacy_symoneural_llm_pids']}")
    suite["baseline_restored"] = (post["vram_used_mib"] <= baseline + 256
                                  and post["compute_apps"] == 0)
    _persist(suite)
    _csv(suite)
    return 0 if suite["baseline_restored"] else 4


def _persist(suite) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = REPORT_DIR / f"SUITE-slice2-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(suite, indent=2, default=str) + "\n")
    suite["suite_report_path"] = str(p)
    print(f"\nsuite report: {p}", flush=True)


def _csv(suite) -> None:
    """Graph-ready data. JSON/CSV is sufficient for Slice 2."""
    rows = ["ai_mode,users,waves,sessions,completed,failed,throughput_sps,"
            "op_p95_ms,session_p95_ms,ai_p95_ms,queue_wait_p95_ms,service_p95_ms,"
            "gpu_util_avg,gpu_util_max,vram_max_mib,power_avg_w,cpu_avg,cpu_max,"
            "ram_max_mib,samples,result"]
    for mode in ("ai_off", "ai_on"):
        arm = suite.get(mode) or {}
        for users, lv in sorted((arm.get("levels") or {}).items(), key=lambda x: int(x[0])):
            t, a = lv["telemetry"], lv["ai"]
            g = t.get("gpu") if isinstance(t.get("gpu"), dict) else {}
            sy = t.get("system") if isinstance(t.get("system"), dict) else {}
            def v(d, k, s="p95"):
                x = d.get(k)
                return x.get(s) if isinstance(x, dict) else ""
            rows.append(",".join(str(x) for x in [
                mode, users, lv["waves"], lv["sessions_total"], lv["completed"],
                lv["failed"], lv["throughput_sessions_per_s"],
                lv["application"]["operation_latency_ms"].get("p95"),
                lv["application"]["session_latency_ms"].get("p95"),
                v(a, "latency_ms"), v(a, "queue_wait_ms"), v(a, "service_ms"),
                (g.get("utilization_pct") or {}).get("avg", ""),
                (g.get("utilization_pct") or {}).get("max", ""),
                (g.get("vram_used_mib") or {}).get("max", ""),
                (g.get("power_w") or {}).get("avg", ""),
                (sy.get("cpu_pct") or {}).get("avg", ""),
                (sy.get("cpu_pct") or {}).get("max", ""),
                (sy.get("ram_used_mib") or {}).get("max", ""),
                t["sample_count"], lv["classification"]["result"]]))
    p = REPORT_DIR / f"SUITE-slice2-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    p.write_text("\n".join(rows) + "\n")
    print(f"graph csv    : {p}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
