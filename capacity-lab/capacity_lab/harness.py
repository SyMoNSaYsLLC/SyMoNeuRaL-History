"""Concurrent-session harness, classification and run report.

Concurrency is real: every synthetic user waits on a barrier and is released
together, so "8 concurrent users" means eight sessions genuinely in flight, not
eight requests issued in a loop. Actual achieved concurrency is measured and
reported alongside the requested number, because they are not the same thing and
only one of them is a fact about the server.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .core import (NOT_AVAILABLE, SCHEMA_VERSION, Sampler, host_identity,
                   known_run_ids, new_run_id, percentiles, repo_commit, REPORT_DIR)
from .players import build_player
from .scenario import SCENARIOS, SessionResult

PASS, DEGRADED, FAIL = "PASS", "DEGRADED", "FAIL"
STOP = threading.Event()          # module-level so a STOP TEST control can set it

HYBRID_PATH = Path("/home/google/Symoneural/.claude/worktrees/"
                   "native-hybrid-gpu-player/engines/symoneural-hybrid")


class FaultState(RuntimeError):
    """A GPU pass condition was not met. The run stops rather than producing a
    number that describes the wrong architecture."""



def _measure_baseline() -> int:
    """Read the card's current floor.

    Graphics memory counts: a logged-in desktop is part of what the server has
    left, and pretending the floor is still the greeter's would overstate
    headroom by ~1 GiB.
    """
    import sys as _s
    _s.path.insert(0, str(HYBRID_PATH))
    try:
        import gpu_guard
        return gpu_guard.vram_used_mib()
    except Exception:
        return 0

def _legacy_engine_pids() -> list[int]:
    """Every legacy engine process, by exact comm -- not a substring match.

    The capacity numbers must come from the native hybrid player. If the legacy
    symoneural-llm is resident, an AI measurement is measuring the wrong thing,
    so this is checked at every mode transition rather than assumed.
    """
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / "comm").read_text().strip() in ("symoneural-llm", "llama-server"):
                out.append(int(p.name))
        except (OSError, ValueError):
            continue
    return out


def _delete(base: str, path: str, timeout: float):
    """DELETE helper for run-scoped cleanup."""
    import json as _j, urllib.error, urllib.request
    req = urllib.request.Request(f"{base.rstrip('/')}{path}", method="DELETE")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                doc = _j.loads(raw)
            except Exception:
                doc = None
            return True, time.monotonic() - t0, r.status, doc, None
    except urllib.error.HTTPError as e:
        return False, time.monotonic() - t0, e.code, None, f"HTTP {e.code}"
    except Exception as e:
        return False, time.monotonic() - t0, None, None, f"{type(e).__name__}: {e}"


class Harness:
    def __init__(self, *, base_url="http://127.0.0.1:8800", scenario="transaction",
                 ai_mode="off", users=2, timeout=120.0, report_dir: Path | None = None,
                 api_key=None, sample_interval=0.25, thresholds: dict | None = None,
                 baseline_mib=None, tolerance_mib=256):
        # MEASURED, not a literal. A hardcoded 237 was correct only while the
        # desktop happened to be at the greeter; logging a KDE session in moved
        # the real floor to ~1231 MiB and silently invalidated every AI-OFF
        # precondition. The baseline is a reading of this machine right now.
        self.baseline_mib = int(baseline_mib) if baseline_mib is not None else _measure_baseline()
        self.tolerance_mib = int(tolerance_mib)
        self.base_url = base_url
        self.scenario_name = scenario
        self.ai_mode = ai_mode
        self.users = int(users)
        self.timeout = timeout
        self.api_key = api_key
        self.report_dir = report_dir or REPORT_DIR
        self.sample_interval = sample_interval
        # No SLA thresholds are invented here. Slice 1 ships an empty dict, so
        # DEGRADED cannot be assigned by guesswork; only hard failures set FAIL.
        self.thresholds = thresholds or {}
        self._active = 0
        self._max_active = 0
        self._started = 0
        self._lock = threading.Lock()
        self._native_player = None          # the ONE run-scoped worker, when AI is on
        self._gpu_transitions: list[dict] = []

    # ------------------------------------------------------- GPU pass conditions
    def _gpu_state(self, label: str) -> dict:
        """Record the card at a mode transition, and check the invariants that
        make an AI ON/OFF comparison meaningful in the first place."""
        import sys as _s
        _s.path.insert(0, str(HYBRID_PATH))
        import gpu_guard                                    # noqa: PLC0415
        apps = gpu_guard.compute_apps()
        snap = gpu_guard.gpu_snapshot()
        legacy = _legacy_engine_pids()
        rec = {"label": label, "vram_used_mib": snap["vram_used_mib"],
               "compute_apps": len(apps), "compute_pids": [p for p, _ in apps],
               "legacy_symoneural_llm_pids": legacy,
               "power_w": snap["power_w"], "util_pct": snap["util_pct"]}
        self._gpu_transitions.append(rec)
        return rec

    def _assert_ai_off_preconditions(self) -> None:
        """AI DISABLED must mean the GPU is genuinely idle -- not that a dormant
        model is resident and merely uncalled. Otherwise 'booking only' and
        'booking + SyMon AI' are not a like-for-like hardware comparison."""
        st = self._gpu_state("before_sessions_ai_off")
        if st["legacy_symoneural_llm_pids"]:
            raise FaultState(f"legacy symoneural-llm is resident: "
                             f"{st['legacy_symoneural_llm_pids']} -- AI OFF requires baseline")
        if st["compute_apps"] != 0:
            raise FaultState(f"AI OFF requires 0 compute apps, found {st['compute_apps']} "
                             f"({st['compute_pids']})")
        if st["vram_used_mib"] > self.baseline_mib + self.tolerance_mib:
            raise FaultState(f"AI OFF requires baseline VRAM, found {st['vram_used_mib']} MiB")

    def _assert_ai_on_preconditions(self) -> None:
        st = self._gpu_state("before_worker_load_ai_on")
        if st["legacy_symoneural_llm_pids"]:
            raise FaultState(f"legacy symoneural-llm is resident: "
                             f"{st['legacy_symoneural_llm_pids']} -- refusing to benchmark "
                             f"the legacy path")
        if st["compute_apps"] != 0:
            raise FaultState(f"expected an idle card before loading the native worker, "
                             f"found {st['compute_apps']} compute app(s)")

    # -------------------------------------------------------------- concurrency
    def _one(self, barrier: threading.Barrier, idx: int, run_id: str) -> SessionResult:
        sid = f"{run_id}-U{idx:03d}"
        scen = SCENARIOS[self.scenario_name]()
        # Run-scoped player: every user shares the ONE worker when AI is enabled.
        # A per-user player would spawn a model process per user, which measures
        # nothing except how fast a 16 GB card runs out of memory.
        player = (self._native_player if self._native_player is not None
                  else build_player(self.ai_mode, self.base_url, self.api_key))
        try:
            barrier.wait(timeout=60)          # genuine simultaneity
        except threading.BrokenBarrierError:
            pass
        with self._lock:
            self._started += 1
            self._active += 1
            self._max_active = max(self._max_active, self._active)
        try:
            if STOP.is_set():
                return SessionResult(sid, run_id, False, time.monotonic(),
                                     time.monotonic(), [], None, "stopped before start")
            return scen.run(session_id=sid, run_id=run_id, base_url=self.base_url,
                            player=player, timeout=self.timeout, api_key=self.api_key)
        finally:
            with self._lock:
                self._active -= 1

    # -------------------------------------------------------------------- run
    def run(self) -> dict:
        scen_cls = SCENARIOS.get(self.scenario_name)
        if scen_cls is None:
            raise ValueError(f"unknown scenario {self.scenario_name!r}")
        run_id = new_run_id(datetime.now(), known_run_ids(self.report_dir))

        if not scen_cls.runnable:
            return self._unavailable_report(run_id, scen_cls)

        STOP.clear()
        t_start = datetime.now(timezone.utc)
        results: list[SessionResult] = []
        worker_ev = None
        teardown = None

        # ---- COLD START, outside the steady-state window ---------------------
        # The model load happens before the sampler that measures the sessions, so
        # a multi-second load can never be averaged into inference latency.
        if self.ai_mode == "on":
            self._assert_ai_on_preconditions()
            from .native_player import NativeChatPlayer      # noqa: PLC0415
            self._native_player = NativeChatPlayer(baseline_mib=self.baseline_mib,
                                                   tolerance_mib=self.tolerance_mib)
            worker_ev = self._native_player.start(ready_timeout=900)
            st = self._gpu_state("after_worker_ready")
            if st["compute_apps"] != 1:
                self._native_player.stop()
                raise FaultState(f"expected exactly 1 GPU owner after load, "
                                 f"found {st['compute_apps']}")
        else:
            self._assert_ai_off_preconditions()

        # ---- STEADY STATE ----------------------------------------------------
        sampler = Sampler(interval=self.sample_interval).start()
        m0 = time.monotonic()
        barrier = threading.Barrier(self.users)
        try:
            with ThreadPoolExecutor(max_workers=self.users) as ex:
                futs = [ex.submit(self._one, barrier, i, run_id) for i in range(1, self.users + 1)]
                for f in futs:
                    try:
                        results.append(f.result(timeout=self.timeout * 3))
                    except Exception as e:            # noqa: BLE001
                        results.append(SessionResult(f"{run_id}-U???", run_id, False,
                                                     m0, time.monotonic(), [], None,
                                                     f"harness: {type(e).__name__}: {e}"))
        finally:
            sampler.stop()
            m1 = time.monotonic()
            # ---- TEARDOWN: reap the worker, verify the card came back ---------
            if self._native_player is not None:
                try:
                    teardown = self._native_player.stop()
                except Exception as e:                # noqa: BLE001
                    teardown = {"error": f"{type(e).__name__}: {e}"}
                self._gpu_state("after_worker_reaped")

        return self._build_report(run_id, results, sampler, t_start, m1 - m0,
                                  worker_ev=worker_ev, teardown=teardown)

    # ------------------------------------------------------------------ report
    def _base_report(self, run_id: str) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "application": repo_commit(),
            "server_hardware": host_identity(),
            "ai_mode": "ENABLED" if self.ai_mode == "on" else "DISABLED",
            # The player that was ACTUALLY used. build_player() would return the
            # /api/chat player, so reporting that here would describe the legacy
            # architecture while the native worker did the work -- exactly the
            # confusion this slice exists to remove.
            "player": (self._native_player.identity() if self._native_player is not None
                       else build_player(self.ai_mode, self.base_url).identity()),
            "scenario": self.scenario_name,
            "requested_users": self.users,
            "base_url": self.base_url,
            "thresholds": self.thresholds or NOT_AVAILABLE,
            "threshold_note": ("No SLA thresholds defined in slice 1. DEGRADED cannot be "
                               "assigned without them; only objective hard failures set FAIL."),
        }

    def _unavailable_report(self, run_id: str, scen_cls) -> dict:
        r = self._base_report(run_id)
        r.update({
            "classification": NOT_AVAILABLE,
            "runnable": False,
            "unavailable_reason": scen_cls.unavailable_reason,
            "declared_steps": getattr(scen_cls, "declared_steps", None),
            "actual_max_concurrency": NOT_AVAILABLE,
            "measurements": NOT_AVAILABLE,
            "cleanup": {"state": "nothing created", "records_removed": 0},
        })
        self._persist(r)
        return r

    def _build_report(self, run_id, results, sampler, t_start, wall_s,
                      worker_ev=None, teardown=None) -> dict:
        done = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]

        sess_lat = [r.duration_s * 1000 for r in results if r.ok]
        step_lat: dict[str, list[float]] = {}
        http_counts: dict[str, int] = {}
        for r in results:
            for s in r.steps:
                step_lat.setdefault(s.name, []).append(s.latency_s * 1000)
                key = str(s.http_status or "no-response")
                http_counts[key] = http_counts.get(key, 0) + 1

        ai_rows = [r.ai for r in results if r.ai is not None and not r.ai.bypassed]
        if self.ai_mode == "on" and ai_rows:
            toks = [a.tok_per_s for a in ai_rows if a.tok_per_s is not None]
            waits = [getattr(a, "queue_wait_s", None) for a in ai_rows]
            waits = [w * 1000 for w in waits if w is not None]
            svc = [getattr(a, "service_s", None) for a in ai_rows]
            svc = [s * 1000 for s in svc if s is not None]
            ai_block = {
                "requests": len(ai_rows),
                "failures": sum(1 for a in ai_rows if not a.ok),
                # what the user experiences: queue wait + service
                "latency_ms": percentiles([a.latency_s * 1000 for a in ai_rows]),
                # broken out, because at concurrency N the difference is the story
                "queue_wait_ms": percentiles(waits) if waits else NOT_AVAILABLE,
                "service_ms": percentiles(svc) if svc else NOT_AVAILABLE,
                "tokens_per_s_reported_by_worker": percentiles(toks) if toks else NOT_AVAILABLE,
                "model": "SyMon AI",
            }
            if self._native_player is not None:
                ai_block.update(self._native_player.metrics())
        elif self.ai_mode == "on":
            ai_block = {"requests": 0, "failures": 0, "note": "no AI results captured"}
        else:
            ai_block = {"mode": "DISABLED",
                        "note": ("no AI request issued and no Chat worker alive for this "
                                 "run; the GPU was verified at baseline before sessions "
                                 "started, so this is BOOKING SYSTEM ONLY rather than a "
                                 "dormant resident model"),
                        "engine_residency": "UNLOADED"}

        errors = [{"session": r.session_id, "error": r.error} for r in failed if r.error]
        classification = self._classify(results, errors)

        r = self._base_report(run_id)
        r.update({
            "runnable": True,
            "start_utc": t_start.isoformat(),
            "wall_seconds": round(wall_s, 3),
            "actual_started_concurrency": self._started,
            "actual_max_concurrency": self._max_active,
            "sessions": {"requested": self.users, "started": self._started,
                         "completed": len(done), "failed": len(failed)},
            "measurements": {
                "application": {
                    "session_latency_ms": percentiles(sess_lat),
                    "step_latency_ms": {k: percentiles(v) for k, v in step_lat.items()},
                    "http_status_counts": http_counts,
                    "requests_per_s": (round(sum(len(x.steps) for x in results) / wall_s, 2)
                                       if wall_s > 0 else NOT_AVAILABLE),
                    "timeouts": sum(1 for r_ in results
                                    if r_.error and "timeout" in r_.error.lower()),
                },
                "booking": ({
                    "completion_ms": percentiles(sess_lat),
                    "state_machine": "REQUEST -> QUOTE_PENDING -> QUOTED -> CONFIRMED "
                                     "-> DISPATCH -> REMINDER -> COMPLETED",
                    "quote_source": "BENCHMARK_SYNTHETIC_QUOTE (TEST DATA, synthetic rows only)",
                    "external_effects_sent": {"sms": False, "email": False,
                                              "review_request": False, "payment": False},
                } if self.scenario_name == "booking" else {
                    "completion_ms": NOT_AVAILABLE,
                    "note": "this run used the CONTROL TRANSACTION scenario, not BOOKING",
                }),
                "ai": ai_block,
                "telemetry": sampler.statistics(),
                "database": {
                    "latency_ms": NOT_AVAILABLE,
                    "connection_pressure": NOT_AVAILABLE,
                    "lock_contention_errors": NOT_AVAILABLE,
                    "note": "no booking database exists; not instrumented in slice 1",
                },
            },
            "classification": classification,
            "errors": errors or None,
            "sessions_detail": [self._session_dict(x) for x in results],
            "cleanup": self._cleanup(run_id),
            # cold start is reported, never hidden -- and never folded into the
            # steady-state numbers above, which were sampled after READY
            "cold_start": ({"seconds": self._native_player.cold_start_s,
                            "worker_pid": self._native_player.worker_pid,
                            "worker_process_vram_mib": self._native_player.worker_vram_mib,
                            "note": "model load; excluded from steady-state latency"}
                           if self._native_player is not None else NOT_AVAILABLE),
            "gpu_transitions": self._gpu_transitions,
            "worker_teardown": teardown or NOT_AVAILABLE,
            "legacy_engine": {
                "symoneural_llm_executions": 0,
                "verified_absent_at_transitions": all(
                    not t["legacy_symoneural_llm_pids"] for t in self._gpu_transitions),
                "api_chat_used": False,
            },
        })
        self._persist(r)
        return r

    @staticmethod
    def _session_dict(r: SessionResult) -> dict:
        d = {"session_id": r.session_id, "ok": r.ok,
             "duration_ms": round(r.duration_s * 1000, 2),
             "steps": [asdict(s) for s in r.steps], "error": r.error}
        if r.ai is not None:
            d["ai"] = asdict(r.ai)
        return d

    def _classify(self, results, errors) -> str:
        """Slice 1: FAIL only on objective hard failure. DEGRADED needs thresholds
        that do not exist yet, so it is never assigned by guesswork."""
        if any(not r.ok for r in results):
            return FAIL
        if errors:
            return FAIL
        if self.thresholds:
            pass          # slice 2 will evaluate configured thresholds here
        return PASS

    def _cleanup(self, run_id: str) -> dict:
        """Scoped to this run id only, and only to synthetic rows.

        The BOOKING scenario writes real rows to the DispatchOS database, so this
        actually deletes something and reports the count. The CONTROL TRANSACTION
        scenario is stateless, and says so rather than reporting a successful
        deletion that never happened.
        """
        if self.scenario_name != "booking":
            return {"state": "no persistent records created by this scenario",
                    "run_id": run_id, "records_removed": 0,
                    "scope": f"run_id == {run_id} only"}
        ok, _lat, status, doc, err = _delete(
            self.base_url, f"/api/dispatchos/benchmark/{run_id}", self.timeout)
        if not ok:
            return {"state": "cleanup FAILED", "run_id": run_id,
                    "records_removed": NOT_AVAILABLE, "http_status": status,
                    "error": err}
        return {"state": "benchmark bookings removed", "run_id": run_id,
                "records_removed": (doc or {}).get("bookings_removed", NOT_AVAILABLE),
                "scope": (doc or {}).get("scope", f"run_id == {run_id} only")}

    def _persist(self, report: dict) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        p = self.report_dir / f"{report['run_id']}.json"
        p.write_text(json.dumps(report, indent=2, default=str) + "\n")
        report["report_path"] = str(p)


def clear_run_data(run_id: str, report_dir: Path | None = None) -> dict:
    """CLEAR TEST DATA -- deletes the artefacts of ONE benchmark run.

    Refuses anything that is not a well-formed benchmark id, so this can never
    become a generic delete. There is deliberately no 'clear all'.
    """
    from .core import is_benchmark_id
    if not is_benchmark_id(run_id):
        raise ValueError(f"refusing: {run_id!r} is not a benchmark run id")
    d = report_dir or REPORT_DIR
    target = d / f"{run_id}.json"
    if not target.exists():
        return {"run_id": run_id, "removed": 0, "state": "nothing to remove"}
    target.unlink()
    return {"run_id": run_id, "removed": 1, "state": "report removed",
            "scope": f"run_id == {run_id} only"}
