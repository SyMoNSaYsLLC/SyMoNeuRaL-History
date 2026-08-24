"""Capacity Lab tests: identity, isolation, cleanup scoping, classification,
telemetry honesty, and the AI ON/OFF routing distinction.

None of these need a GPU or a running server except where explicitly marked.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capacity_lab import core, harness, players, scenario  # noqa: E402


# ------------------------------------------------------------------ run identity
def test_run_id_shape_and_sequence():
    d = datetime(2026, 8, 24, 11, 0, 0)
    assert core.new_run_id(d, []) == "BENCH-20260824-0001"
    assert core.new_run_id(d, ["BENCH-20260824-0001"]) == "BENCH-20260824-0002"
    # a different day restarts the sequence
    assert core.new_run_id(d, ["BENCH-20260823-0009"]) == "BENCH-20260824-0001"


def test_is_benchmark_id_rejects_anything_else():
    assert core.is_benchmark_id("BENCH-20260824-0001")
    for bad in ("", "BENCH-2026-0001", "bench-20260824-0001", "BENCH-20260824-1",
                "../../etc/passwd", "BENCH-20260824-0001x", None):
        assert not core.is_benchmark_id(bad), bad


# ---------------------------------------------------------------- cleanup scoping
def test_clear_refuses_non_benchmark_ids(tmp_path):
    """CLEAR TEST DATA must never become a generic delete."""
    for bad in ("all", "*", "customers", "../secrets", "BENCH-bad"):
        with pytest.raises(ValueError):
            harness.clear_run_data(bad, tmp_path)


def test_clear_removes_only_the_named_run(tmp_path):
    a, b = tmp_path / "BENCH-20260824-0001.json", tmp_path / "BENCH-20260824-0002.json"
    a.write_text("{}"); b.write_text("{}")
    out = harness.clear_run_data("BENCH-20260824-0001", tmp_path)
    assert out["removed"] == 1
    assert not a.exists(), "target not removed"
    assert b.exists(), "an unrelated run was destroyed"


def test_clear_is_idempotent_and_reports_honestly(tmp_path):
    out = harness.clear_run_data("BENCH-20260824-0007", tmp_path)
    assert out["removed"] == 0 and out["state"] == "nothing to remove"


# ------------------------------------------------------------------- statistics
def test_percentiles_report_not_available_rather_than_zero():
    """An empty sample set must not read as 0 ms -- that is a fabricated number."""
    p = core.percentiles([])
    assert all(v == core.NOT_AVAILABLE for v in p.values())


def test_percentiles_are_real_observations():
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    p = core.percentiles(vals)
    assert p["n"] == 10 and p["min"] == 10 and p["max"] == 100
    for k in ("p50", "p95", "p99"):
        assert p[k] in vals, f"{k}={p[k]} is not a value any session measured"


def test_summarise_empty_is_not_available():
    s = core.summarise([], "MiB")
    assert s["min"] == s["avg"] == s["max"] == core.NOT_AVAILABLE


# ---------------------------------------------------------------------- players
def test_null_player_bypasses_inference_entirely():
    r = players.NullPlayer().invoke("anything", timeout=5)
    assert r.ok and r.bypassed and r.latency_s == 0.0
    assert players.NullPlayer.uses_gpu is False


def test_chat_player_is_the_gpu_path_and_is_named_for_customers():
    p = players.SymonChatPlayer("http://127.0.0.1:8800")
    assert p.uses_gpu is True
    assert p.name == "SyMon AI", "business view must not carry upstream model branding"


def test_build_player_routing():
    assert isinstance(players.build_player("off", "http://x"), players.NullPlayer)
    assert isinstance(players.build_player("on", "http://x"), players.SymonChatPlayer)
    with pytest.raises(ValueError):
        players.build_player("maybe", "http://x")


def test_no_inference_library_is_imported_by_the_lab():
    """The lab measures a player over the wire; it must not host one."""
    src = "".join((ROOT / "capacity_lab" / f).read_text()
                  for f in ("core.py", "players.py", "scenario.py", "harness.py"))
    for banned in ("import torch", "from torch", "import transformers",
                   "import diffusers", "import vllm"):
        assert banned not in src, f"lab imports {banned}"


# --------------------------------------------------------------------- scenarios
def test_booking_scenario_is_now_the_real_one():
    """Slice 1.5 replaced the NOT AVAILABLE stub with the real DispatchOS flow."""
    assert scenario.BookingScenario.runnable is True
    assert scenario.DISPLAY_NAMES["booking"] == "BOOKING"


def test_control_transaction_is_kept_and_named_accurately():
    """RavenCalc stays as an engineering control -- but it is never presented as
    booking capacity."""
    assert scenario.TransactionScenario.runnable is True
    assert scenario.DISPLAY_NAMES["transaction"] == "CONTROL TRANSACTION"


def test_booking_session_walks_the_real_state_machine():
    """The scenario must drive the real routes, not a parallel benchmark path."""
    src = (ROOT / "capacity_lab" / "scenario.py").read_text()
    for route in ("/api/dispatchos/meta", "/api/dispatchos/bookings"):
        assert route in src, route
    for state in ("QUOTE_PENDING", "CONFIRMED", "DISPATCH", "REMINDER", "COMPLETED"):
        assert state in src, state
    # and it must mark its rows as synthetic
    assert '"synthetic": True' in src
    assert '"benchmark_run_id": run_id' in src


def test_booking_uses_the_synthetic_quote_fixture_not_a_price_rule():
    src = (ROOT / "capacity_lab" / "scenario.py").read_text()
    assert "BENCHMARK_SYNTHETIC_QUOTE" in src
    assert '"TEST_DATA": True' in src


# ---------------------------------------------------------------- classification
def test_slice1_cannot_assign_degraded_without_thresholds():
    h = harness.Harness(users=1)
    assert h.thresholds == {}
    ok = [scenario.SessionResult("s", "BENCH-20260824-0001", True, 0.0, 1.0)]
    assert h._classify(ok, []) == harness.PASS


def test_hard_failure_is_reported_as_fail_not_hidden():
    h = harness.Harness(users=1)
    bad = [scenario.SessionResult("s", "BENCH-20260824-0001", False, 0.0, 1.0,
                                  error="HTTP 500")]
    assert h._classify(bad, [{"session": "s", "error": "HTTP 500"}]) == harness.FAIL


# ------------------------------------------------------------------- concurrency
def test_barrier_makes_sessions_genuinely_simultaneous(monkeypatch, tmp_path):
    """Requested concurrency must mean simultaneous sessions, not a request loop."""
    seen = []

    class Fake(scenario.Scenario):
        name, runnable = "fake", True

        def run(self, *, session_id, run_id, base_url, player, timeout, api_key=None):
            t0 = time.monotonic()
            seen.append(t0)
            time.sleep(0.3)
            return scenario.SessionResult(session_id, run_id, True, t0, time.monotonic())

    monkeypatch.setitem(scenario.SCENARIOS, "fake", Fake)
    monkeypatch.setitem(harness.SCENARIOS, "fake", Fake)
    h = harness.Harness(scenario="fake", users=4, report_dir=tmp_path)
    rep = h.run()
    assert rep["actual_max_concurrency"] == 4, "sessions were not concurrent"
    assert rep["sessions"]["completed"] == 4
    assert max(seen) - min(seen) < 0.25, "release was not synchronised"


def test_stop_control_aborts_pending_sessions(monkeypatch, tmp_path):
    class Fake(scenario.Scenario):
        name, runnable = "fake2", True

        def run(self, **kw):
            raise AssertionError("must not run once STOP is set")

    monkeypatch.setitem(harness.SCENARIOS, "fake2", Fake)
    h = harness.Harness(scenario="fake2", users=2, report_dir=tmp_path)
    harness.STOP.set()
    try:
        # STOP is checked after the barrier; sessions must abort, not execute
        rep = h.run()
        assert rep["sessions"]["failed"] == 2
        assert rep["classification"] == harness.FAIL
    finally:
        harness.STOP.clear()


# --------------------------------------------------------------------- telemetry
def test_sampler_collects_a_timestamped_series_not_a_snapshot():
    s = core.Sampler(interval=0.1).start()
    time.sleep(0.65)
    s.stop()
    assert len(s.samples) >= 3, "a single reading is not a series"
    st = s.statistics()
    assert st["sample_count"] == len(s.samples)
    assert st["span_s"] > 0
    if st["gpu"] != core.NOT_AVAILABLE:
        for k in ("vram_used_mib", "utilization_pct", "power_w", "temperature_c"):
            assert st["gpu"][k]["n"] >= 1
        assert "max_simultaneous_compute_apps" in st["gpu"]


def test_host_identity_has_no_secrets():
    ident = json.dumps(core.host_identity()).lower()
    for banned in ("token", "password", "secret", "api_key", "bearer"):
        assert banned not in ident


def test_report_carries_no_credentials(tmp_path):
    h = harness.Harness(scenario="booking", users=2, report_dir=tmp_path,
                        api_key="super-secret-value")
    blob = json.dumps(h.run()).lower()
    assert "super-secret-value" not in blob
    for banned in ("bearer ", "api_key", "password"):
        assert banned not in blob


# ------------------------------------------- slice 1.5: native player + AI modes
def test_native_player_is_the_h3_proven_configuration():
    """The benchmark must measure the H3/H5 architecture, not the legacy engine."""
    from capacity_lab import native_player as np
    assert np.CHAT_QUANT == "bitsandbytes-nf4"
    assert "Qwen2.5-7B-Instruct" in np.CHAT_MODEL
    assert "a09a35458c702b33eeacc393d103063234e8bc28" in np.CHAT_MODEL
    assert np.NativeChatPlayer.name == "SyMon AI"
    assert np.NativeChatPlayer.uses_gpu is True


def test_native_player_never_references_legacy_paths():
    """Executable code only.

    The module's own docstring names the legacy paths in order to say it does not
    use them, so a raw substring search flags the documentation rather than the
    behaviour. Strip comments and string literals via the AST and check what
    actually runs.
    """
    import ast
    src = (ROOT / "capacity_lab" / "native_player.py").read_text()
    tree = ast.parse(src)

    # Identify docstring nodes by identity -- ast.get_docstring() returns a
    # cleaned/dedented string that will not compare equal to the raw constant.
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                doc_nodes.add(id(body[0].value))

    # Also exclude keys of a dict that maps them to False -- identity() reports
    # `legacy_paths_used = {"llama_cpp": False, ...}`, which NAMES the legacy
    # paths precisely in order to declare they are unused. That is the opposite
    # of a violation, and a check that failed on it would punish the disclosure.
    declared_false = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                        and isinstance(v, ast.Constant) and v.value is False):
                    declared_false.add(id(k))

    code_literals = [n.value for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and id(n) not in doc_nodes and id(n) not in declared_false]

    # NOTE on the vLLM interpreter path: CHAT_PY is
    # /home/google/.venvs/vllm/bin/python. That venv is named after vLLM because
    # vLLM was installed there first, but it is simply the environment in which
    # the H3 chat player was proven -- vLLM itself is never imported or served.
    # The check below is therefore about *invoking* vLLM, not about a directory
    # name. (H4-F already recommended moving the chat player to its own venv to
    # remove this ambiguity; that remains an open decision, not a defect here.)
    INTERPRETER_PATH = "/home/google/.venvs/vllm/bin/python"

    for banned in ("/api/chat", "symoneural-llm", "llama_cpp", "vllm serve", "gpt-oss"):
        for lit in code_literals:
            if lit == INTERPRETER_PATH:
                continue
            assert banned not in lit, f"native player uses {banned} in code: {lit[:60]!r}"

    # No import of any legacy runtime, at any depth.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = (getattr(node, "module", "") or "").lower()
            names = [a.name.lower() for a in node.names]
            for bad in ("vllm", "llama_cpp", "llamacpp"):
                assert bad not in mod, f"imports {mod}"
                for n in names:
                    assert bad not in n, f"imports {n}"

    # And the interpreter path is the ONLY place the string appears.
    assert sum(1 for lit in code_literals if "vllm" in lit) == 1, \
        "vllm appears somewhere other than the H3 interpreter path"


def test_one_worker_per_run_not_per_user():
    """A model process per user would measure nothing but OOM.

    Asserted BEHAVIOURALLY. The previous version looked for a constructor local
    named `_gate`, which pinned an implementation detail rather than the
    property: renaming the gate broke the test while the guarantee was intact,
    and a rename in the other direction would have satisfied it while
    serialisation was broken. This drives real concurrent traffic through the
    player and checks the supervisor never sees two requests at once.
    """
    src = (ROOT / "capacity_lab" / "harness.py").read_text()
    assert "self._native_player if self._native_player is not None" in src

    from capacity_lab import native_player as np

    class CountingSup:
        """Fails the test if the player ever lets two requests overlap."""
        def __init__(self):
            self.inflight = 0
            self.max_inflight = 0
            self.calls = 0
            self._l = threading.Lock()

        def request(self, payload, timeout):
            with self._l:
                self.inflight += 1
                self.calls += 1
                self.max_inflight = max(self.max_inflight, self.inflight)
            time.sleep(0.02)
            with self._l:
                self.inflight -= 1
            return {"type": "result", "completion_tokens": 4, "tok_per_s": 10.0}

    p = np.NativeChatPlayer.__new__(np.NativeChatPlayer)
    p._cv = threading.Condition()
    p._next_ticket = p._now_serving = 0
    p._abandoned = set()
    p._waiting = p._active = 0
    p._max_depth = p._max_active = p._max_in_system = 0
    p._queue_waits, p._samples = [], []
    p.sup = CountingSup()
    p.name = "SyMon AI"
    p.cold_start_s = p.worker_pid = p.worker_vram_mib = None
    p.ready_report = None

    n = 8
    barrier = threading.Barrier(n)

    def go():
        barrier.wait(timeout=10)
        p.invoke("hi", timeout=30)

    threads = [threading.Thread(target=go) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert p.sup.calls == n, f"expected {n} inferences, got {p.sup.calls}"
    assert p.sup.max_inflight == 1, (
        f"{n} concurrent users drove {p.sup.max_inflight} simultaneous inferences; "
        "the run-scoped worker is not serialising")
    assert p.metrics()["max_active_ai_requests"] == 1


def test_legacy_engine_detector_uses_exact_comm_not_substring():
    src = (ROOT / "capacity_lab" / "harness.py").read_text()
    assert '(p / "comm").read_text().strip() in ("symoneural-llm", "llama-server")' in src
    assert harness._legacy_engine_pids() == [] or isinstance(harness._legacy_engine_pids(), list)


def test_ai_off_requires_a_genuinely_idle_card():
    """AI DISABLED must mean baseline, not a dormant resident model."""
    src = (ROOT / "capacity_lab" / "harness.py").read_text()
    assert "_assert_ai_off_preconditions" in src
    assert "AI OFF requires 0 compute apps" in src
    assert "AI OFF requires baseline VRAM" in src


def test_cold_start_is_separated_from_steady_state():
    src = (ROOT / "capacity_lab" / "harness.py").read_text()
    i_load = src.index("self._native_player.start(")
    i_sampler = src.index("sampler = Sampler(interval=self.sample_interval).start()")
    assert i_load < i_sampler, "the model load must happen before the steady-state sampler"


def test_report_identifies_the_player_that_actually_ran():
    """A report that names the legacy /api/chat player while the native worker did
    the work would describe the wrong architecture -- the exact confusion slice
    1.5 exists to remove."""
    src = (ROOT / "capacity_lab" / "harness.py").read_text()
    assert "self._native_player.identity() if self._native_player is not None" in src


# ================================================= slice 2: lifecycle + queue
def test_lifecycle_has_all_ten_profiles():
    from capacity_lab import lifecycle as L
    assert len(L.PROFILES) == 10
    assert set(L.AI_PROMPTS) == set(L.PROFILES)
    assert set(L.SETUP) == set(L.PROFILES)


def test_operation_is_never_permanently_bound_to_a_button():
    """Binding 'button 7 = quick stop' would mean slot 7's operation is only ever
    measured at concurrency >= 7."""
    from capacity_lab import lifecycle as L
    seen = {1: set(), 2: set()}
    for w in range(10):
        for slot, prof in L.assign([1, 2], w).items():
            seen[slot].add(prof)
    for slot in (1, 2):
        assert len(seen[slot]) == 10, f"slot {slot} saw only {len(seen[slot])} profiles"


def test_rotation_is_deterministic_and_order_independent():
    from capacity_lab import lifecycle as L
    assert L.assign([1, 2, 3], 4) == L.assign([1, 2, 3], 4)
    assert L.assign([3, 1, 2], 0) == L.assign([1, 2, 3], 0)


def test_low_concurrency_still_covers_the_whole_lifecycle():
    from capacity_lab import lifecycle as L
    cov = L.coverage([1, 2], 10)
    assert all(v > 0 for v in cov.values()), f"uncovered: {cov}"
    assert len(set(cov.values())) == 1, f"uneven: {cov}"


def test_queue_depth_semantics_documented_and_total_is_labelled_calculated():
    import suite
    src = Path(suite.__file__).read_text()
    # the literal is split across two source lines, so match the pieces
    assert "waiting requests BEHIND the request in" in src
    assert "not total in flight" in src
    assert '"label": "CALCULATED"' in src
    assert "active servicing + waiting queue" in src


def test_measurement_window_requires_all_three_minimums():
    import suite
    assert suite.MIN_SECONDS >= 5.0 and suite.MIN_SAMPLES >= 30
    assert suite.MIN_WAVES_AI_OFF >= 5 and suite.MIN_WAVES_AI_ON >= 3
    src = Path(suite.__file__).read_text()
    assert "self.waves >= min_waves and elapsed >= MIN_SECONDS" in src
    assert "len(sampler.samples) >= MIN_SAMPLES" in src


def test_waves_do_not_inflate_concurrency():
    import suite
    src = Path(suite.__file__).read_text()
    assert '"concurrency_per_wave": self.users' in src
    assert '"requested_concurrency": self.users' in src


def test_criteria_frozen_from_two_user_arm_and_not_called_an_sla():
    import suite
    src = Path(suite.__file__).read_text()
    assert "if users == 2:" in src and "criteria = freeze_criteria(lvl, ai_mode)" in src
    assert "ENGINEERING CALIBRATION CRITERIA" in src
    assert "contractual SLA" in src and "certified customer capacity" in src
    assert suite.DEGRADE_LATENCY_RATIO == 2.0 and suite.DEGRADE_AI_RATIO == 2.0


def test_resource_markers_are_reported_not_auto_failed():
    import suite
    lvl = {"failed": 0, "application": {"http_status_counts": {"200": 10}, "timeouts": 0,
                                        "operation_latency_ms": {"p95": 100}},
           "ai": {}, "telemetry": {"series_sufficient": True,
                                   "gpu": {"utilization_pct": {"avg": 99},
                                           "max_simultaneous_compute_apps": 1},
                                   "system": {"cpu_pct": {"avg": 99}}}}
    out = suite.classify(lvl, {"operation_p95_ms_ref": 100, "latency_ratio_threshold": 2.0})
    assert out["result"] == "DEGRADED" and out["hard_failures"] is None
    assert any("RESOURCE" in f for f in out["flags"])


def test_hard_failures_are_never_hidden():
    import suite
    cases = [
        ({"failed": 1}, "session failure"),
        ({"http": {"500": 2}}, "HTTP 5xx"),
        ({"timeouts": 3}, "timeouts"),
        ({"apps": 2}, "two GPU owners"),
    ]
    for spec, why in cases:
        lvl = {"failed": spec.get("failed", 0),
               "application": {"http_status_counts": spec.get("http", {}),
                               "timeouts": spec.get("timeouts", 0),
                               "operation_latency_ms": {}},
               "ai": {},
               "telemetry": {"series_sufficient": True,
                             "gpu": {"utilization_pct": {"avg": 1},
                                     "max_simultaneous_compute_apps": spec.get("apps", 1)}}}
        assert suite.classify(lvl, {})["result"] == "FAIL", why


def test_insufficient_series_blocks_a_capacity_conclusion():
    import suite
    out = suite.classify({"failed": 0,
                          "application": {"http_status_counts": {}, "timeouts": 0,
                                          "operation_latency_ms": {}},
                          "ai": {}, "telemetry": {"series_sufficient": False}}, {})
    assert any("SERIES INSUFFICIENT" in f for f in out["flags"])


def test_load_generator_is_disclosed_as_local():
    import suite
    src = Path(suite.__file__).read_text()
    assert '"location": "LOCAL / SAME HOST"' in src
    assert "harness_cpu_pct_of_one_core" in src


def test_cold_start_excluded_and_warmup_discarded():
    import suite
    src = Path(suite.__file__).read_text()
    assert "excluded from every steady-state figure" in src
    assert '"discarded": True' in src
    assert src.index("player.start(ready_timeout=900)") < src.index("lvl = Level(")


def test_one_worker_for_the_whole_arm_not_per_level():
    import suite
    src = Path(suite.__file__).read_text()
    assert src.count("NativeChatPlayer(baseline_mib=baseline)") == 1
    assert src.index("NativeChatPlayer(baseline_mib=baseline)") < src.index("for users in LEVELS:")
