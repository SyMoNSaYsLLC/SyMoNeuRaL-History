"""Slice 3 tests: the guards that stop an adaptive limit finder from lying.

Every test here corresponds to a specific way the headline number could be wrong
and no later pass would recover it:

  * a level that did not achieve its requested concurrency still being quoted
  * the local load generator being material and the number still called a
    server limit
  * per-level queue peaks carried backwards by a downward bracket
  * three different timeout causes aggregated into one figure
  * a projection presented as a measurement
  * four distinct capacity concepts collapsed into one

None of these need a GPU or a running server.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import slice3                                                  # noqa: E402
from capacity_lab.core import NOT_AVAILABLE                     # noqa: E402


# --------------------------------------------------------------- session count
def test_the_ai_off_session_count_is_constant_not_the_duration():
    """Slice 2's non-monotonic 6-user result came from constant DURATION giving
    low concurrency far more sessions. Every level must now run at least the
    same number of sessions."""
    for users in (2, 4, 6, 8, 10, 16, 24, 32, 48, 64, 96, 128, 192, 256):
        waves, _ = slice3.waves_for_off(users)
        sessions = waves * users
        assert sessions >= slice3.TARGET_SESSIONS_AI_OFF, (users, sessions)


def test_the_five_calibration_levels_land_on_exactly_the_target():
    """2/4/6/8/10 all divide 480, so those five are exact and directly
    comparable rather than merely 'at least'."""
    for users in (2, 4, 6, 8, 10):
        waves, _ = slice3.waves_for_off(users)
        assert waves * users == slice3.TARGET_SESSIONS_AI_OFF


def test_a_single_wave_probe_is_labelled_exploratory():
    assert slice3.waves_for_ai(32) == (3, "MEASURED")
    assert slice3.waves_for_ai(96) == (2, "MEASURED")
    assert slice3.waves_for_ai(128)[1] == "EXPLORATORY"
    assert slice3.waves_for_ai(256)[1] == "EXPLORATORY"


# ------------------------------------------------------------------- fixtures
def _level(**over):
    """A minimal PASSing level dict, shaped exactly like Level._summarise."""
    lv = {
        "requested_concurrency": 8, "achieved_max_concurrency": 8,
        "concurrency_achieved": True, "broken_barrier_events": 0,
        "measurement_label": "MEASURED", "waves": 3, "target_waves": 3,
        "extra_waves_for_telemetry": 0, "sessions_total": 24,
        "concurrency_per_wave": 8, "operation_mix": {}, "completed": 24, "failed": 0,
        "wall_seconds": 10.0, "throughput_sessions_per_s": 2.4,
        "application": {
            "session_latency_ms": {"p50": 100.0, "p95": 150.0, "p99": 160.0},
            "operation_latency_ms": {"p50": 10.0, "p95": 20.0, "p99": 25.0},
            "operation_latency_by_class_ms": {}, "setup_latency_ms": {},
            "http_status_counts": {"201": 24, "200": 48}, "timeouts": 0},
        "ai": {"mode": "DISABLED"},
        # A level with no cleanup record hard-fails by design, so the baseline
        # fixture carries a successful one. 24 creates (201) == 24 removed.
        "cleanup": {"state": "removed", "bookings_removed": 24,
                    "run_id": "BENCH-20260824-0001"},
        "subsystem_evidence": {"server_log_bytes": 0, "database_evidence": False,
                               "traceback_present": False},
        "telemetry": {"series_sufficient": True, "sample_count": 60,
                      "gpu": {"utilization_pct": {"avg": 5.0, "max": 9},
                              "vram_used_mib": {"max": 1200, "min": 1180},
                              "vram_total_mib": 16303,
                              "power_w": {"avg": 20.0}, "temperature_c": {"max": 44},
                              "max_simultaneous_compute_apps": 0},
                      "system": {"cpu_pct": {"avg": 10.0, "max": 25.0},
                                 "ram_used_mib": {"max": 8000.0},
                                 "ram_total_mib": 96360.0}},
        "server_process": {"server_threads_max": 12},
        "load_generator": {"location": "LOCAL / SAME HOST", "host_cpu_capacity_cores": 20,
                           "harness_cpu_pct_of_one_core": 7.4,
                           "harness_cpu_pct_of_host": 0.37,
                           "materiality_threshold_pct_of_host": 10.0,
                           "material": False, "harness_rss_mib": 30.0},
        "errors": None,
    }
    for k, v in over.items():
        lv[k] = v
    return lv


CRIT = {"latency_ratio_threshold": 2.0, "operation_p95_ms_ref": 20.913,
        "session_p95_ms_ref": 169.146}
ADM = {"max_concurrent_sync_handlers": 40}


# -------------------------------------------------------- load-generator units
def test_load_generator_materiality_is_per_host_not_per_core():
    """The trap: 7.4% of ONE core on a 20-core host is 0.37% of the host. A
    threshold of 10% compared against the per-core figure would fire falsely and
    void a perfectly good measurement."""
    lg = _level()["load_generator"]
    assert lg["harness_cpu_pct_of_one_core"] == pytest.approx(7.4)
    assert lg["harness_cpu_pct_of_host"] == pytest.approx(7.4 / 20, abs=0.01)
    assert lg["material"] is False


def test_a_material_load_generator_voids_the_server_limit_claim():
    lv = _level(load_generator={**_level()["load_generator"],
                                "harness_cpu_pct_of_host": 42.0, "material": True})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["supports_capacity_claim"] is False
    assert any("LOAD-GENERATOR LIMITED" in v for v in c["validity"])
    assert any("SERVER LIMIT NOT ISOLATED" in v for v in c["validity"])
    assert slice3.bottleneck(lv, ADM)["classification"] == "LOCAL LOAD GENERATOR"
    assert slice3.bottleneck(lv, ADM)["server_limit_isolated"] is False


def test_both_cpu_units_are_emitted_so_neither_can_be_misread():
    lg = _level()["load_generator"]
    assert "harness_cpu_pct_of_one_core" in lg
    assert "harness_cpu_pct_of_host" in lg
    assert lg["host_cpu_capacity_cores"] == 20


# ------------------------------------------------------- achieved concurrency
def test_a_level_that_did_not_achieve_its_concurrency_cannot_support_a_claim():
    """Releasing 128 threads on a barrier is not 128 concurrent sessions. Without
    this gate the report would publish '128 users PASS' for a test that never ran
    128 at once."""
    lv = _level(requested_concurrency=128, achieved_max_concurrency=91,
                concurrency_achieved=False)
    c = slice3.classify(lv, CRIT, ADM)
    assert c["result"] == "PASS"          # nothing objectively failed
    assert c["supports_capacity_claim"] is False
    assert any("CONCURRENCY NOT ACHIEVED" in v for v in c["validity"])
    assert "requested 128" in " ".join(c["validity"])
    assert "achieved 91" in " ".join(c["validity"])


def test_broken_barriers_are_counted_not_swallowed():
    lv = _level(broken_barrier_events=5)
    c = slice3.classify(lv, CRIT, ADM)
    assert c["supports_capacity_claim"] is False
    assert any("broken barrier" in v for v in c["validity"])


def test_a_clean_level_does_support_a_claim():
    c = slice3.classify(_level(), CRIT, ADM)
    assert c["result"] == "PASS"
    assert c["supports_capacity_claim"] is True
    assert c["validity"] is None and c["caveats"] is None


# ------------------------------------------------------------ admission limit
def test_above_the_admission_limit_a_shallow_queue_is_flagged_as_distortion():
    """The AI gate is client-side; HTTP admission is server-side and bounded. So
    above the limit arrivals at the AI queue are staggered and queue depth reads
    LOWER than concurrency. That must never be read as headroom."""
    lv = _level(requested_concurrency=128, achieved_max_concurrency=128)
    c = slice3.classify(lv, CRIT, ADM)
    v = " ".join(c["caveats"])
    assert "ADMISSION-DISTORTED" in v
    assert "distortion, not headroom" in v
    # A CAVEAT, not a VALIDITY defect: 128 sessions completing means 128 users
    # were served. That the server admitted 40 at a time is the measured answer,
    # not a reason to discard the level.
    assert c["validity"] is None
    assert c["supports_capacity_claim"] is True


def test_at_or_below_the_admission_limit_there_is_no_distortion_flag():
    lv = _level(requested_concurrency=40, achieved_max_concurrency=40)
    c = slice3.classify(lv, CRIT, ADM)
    assert c["validity"] is None and c["caveats"] is None


def test_the_admission_limit_is_classified_as_application_not_cpu_or_vram():
    """'Needs a bigger GPU' would be the wrong answer to a threadpool bound."""
    lv = _level(requested_concurrency=128, achieved_max_concurrency=128,
                server_process={"server_threads_max": 47})
    b = slice3.bottleneck(lv, ADM)
    assert b["classification"] == "APPLICATION"
    assert any("40 concurrent sync handlers" in e for e in b["evidence"])
    # and the evidence must positively record that the resources did NOT run out
    joined = " ".join(b["evidence"])
    assert "NOT saturated" in joined and "NOT exhausted" in joined


# ------------------------------------------------------------ hard failures
def test_http_5xx_is_a_hard_failure():
    lv = _level(application={**_level()["application"],
                             "http_status_counts": {"200": 20, "500": 4}})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["result"] == "FAIL"
    assert any("HTTP 500" in h for h in c["hard_failures"])


def test_a_failed_session_is_a_hard_failure():
    c = slice3.classify(_level(failed=3, completed=21), CRIT, ADM)
    assert c["result"] == "FAIL"


def test_more_than_one_gpu_owner_is_a_hard_failure():
    lv = _level()
    lv["telemetry"]["gpu"]["max_simultaneous_compute_apps"] = 2
    assert slice3.classify(lv, CRIT, ADM)["result"] == "FAIL"


def test_degraded_is_not_failure():
    """A slow answer is not a broken one, and conflating them would hand Donnie a
    capacity number far below what the machine actually does."""
    lv = _level(application={**_level()["application"],
                             "operation_latency_ms": {"p50": 40.0, "p95": 80.0, "p99": 90.0}})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["result"] == "DEGRADED"
    assert c["hard_failures"] is None
    assert c["ratios"]["operation_p95_ratio"] == pytest.approx(80.0 / 20.913, abs=0.01)


# ------------------------------------------------------ timeout discrimination
def test_the_three_timeout_causes_are_reported_separately():
    """Queue admission, inference budget and worker fault look identical in an
    aggregate error count and mean completely different things."""
    lv = _level(ai={"requests": 30, "completed": 27, "errors": 3,
                    "fault_classification": {"TIMEOUT POLICY / QUEUE ADMISSION": 2,
                                             "AI WORKER FAULT": 1}})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["result"] == "FAIL"
    assert "TIMEOUT POLICY / QUEUE ADMISSION" in str(c["hard_failures"])
    assert slice3.bottleneck(lv, ADM)["classification"] == "TIMEOUT POLICY"


def test_a_queue_dominant_level_is_classified_as_serial_service():
    lv = _level(ai={"requests": 30, "completed": 30, "errors": 0,
                    "fault_classification": None,
                    "latency_ms": {"p95": 7423.0},
                    "queue_wait_ms": {"p95": 6642.0},
                    "service_ms": {"p95": 792.0}})
    b = slice3.bottleneck(lv, ADM)
    assert b["classification"] == "AI QUEUE / SERIAL SERVICE"
    assert any("service p95" in e for e in b["evidence"])


def test_the_native_player_labels_a_queue_admission_timeout():
    """The player must tag which timeout fired; classification depends on it."""
    src = (ROOT / "capacity_lab" / "native_player.py").read_text()
    assert "TIMEOUT POLICY / QUEUE ADMISSION" in src
    assert "TIMEOUT POLICY / INFERENCE BUDGET" in src
    assert "AI WORKER FAULT" in src


# ------------------------------------------------------------ counter resetting
def test_per_level_queue_peaks_are_resettable():
    """Bracketing walks downward (48 then 40). A cumulative high-water mark would
    report level 40 as having queued 47 deep.

    Built through `_fake_player()` rather than a hand-rolled subclass: the old
    version constructed `_state`, which the FIFO rewrite removed, so it was
    testing a shape the code no longer has.
    """
    import capacity_lab.native_player as np
    assert hasattr(np.NativeChatPlayer, "reset_level_counters")

    f = _fake_player()
    f._max_depth, f._max_active, f._max_in_system = 47, 1, 48
    f._queue_waits, f._samples = [1.0, 2.0], [object()]
    f.reset_level_counters()
    assert f._max_depth == 0 and f._max_active == 0 and f._max_in_system == 0
    assert f._queue_waits == [] and f._samples == []


# --------------------------------------------------------------- projections
def test_a_projection_is_labelled_and_never_called_a_measurement():
    prev = _level(requested_concurrency=10,
                  ai={"latency_ms": {"p95": 7423.2}, "requests": 30})
    p = slice3.timeout_projection(prev, 20)
    assert p["label"] == "PROJECTED SAFETY ESTIMATE"
    assert "PROJECTED, NOT MEASURED" in p["caution"]
    assert p["basis"].startswith("measured p95 7423.2 ms at 10 users")


def test_the_projection_permits_a_jump_well_inside_the_timeout_budget():
    prev = _level(requested_concurrency=10, ai={"latency_ms": {"p95": 7423.2}})
    p = slice3.timeout_projection(prev, 32)
    assert p["projected_p95_s_at_next"] == pytest.approx(23.8, abs=0.5)
    assert p["safe_to_jump"] is True


def test_the_projection_refuses_a_jump_that_would_reach_the_timeout():
    prev = _level(requested_concurrency=10, ai={"latency_ms": {"p95": 7423.2}})
    p = slice3.timeout_projection(prev, 512)
    assert p["projected_p95_s_at_next"] > slice3.REQUEST_TIMEOUT * 0.8
    assert p["safe_to_jump"] is False


def test_a_projection_without_a_measured_basis_reports_unavailable():
    p = slice3.timeout_projection(_level(), 32)          # AI DISABLED level
    assert p["available"] is False
    assert "no measured" in p["reason"]


# ------------------------------------------------------- capacity certificate
def _suite(levels_off, levels_on=None):
    return {"ai_off": {"levels": {str(k): v for k, v in levels_off.items()}},
            "ai_on": {"levels": {str(k): v for k, v in (levels_on or {}).items()}}}


def test_the_certificate_reports_four_distinct_concepts_not_one_number():
    ok = _level(requested_concurrency=32, achieved_max_concurrency=32)
    ok["classification"] = slice3.classify(ok, CRIT, ADM)
    deg = _level(requested_concurrency=48, achieved_max_concurrency=48,
                 application={**_level()["application"],
                              "operation_latency_ms": {"p50": 40.0, "p95": 80.0, "p99": 90.0}})
    deg["classification"] = slice3.classify(deg, CRIT, ADM)
    bad = _level(requested_concurrency=64, achieved_max_concurrency=64, failed=9)
    bad["classification"] = slice3.classify(bad, CRIT, ADM)

    # Both headline values require their repeatability runs (fix G), so supply
    # them. Without these the certificate correctly reports NOT AVAILABLE --
    # that path is pinned separately by the D6 tests below.
    suite = _suite({32: ok, 48: deg, 64: bad})
    suite["ai_off"]["repeatability_highest_clean"] = {
        "users": 48, "total_runs": 3, "successful_runs": 3,
        "runs_without_hard_failure": 3, "summary": "3/3 PROVE CAPACITY"}
    suite["ai_off"]["repeatability_first_failure"] = {
        "users": 64, "total_runs": 3, "successful_runs": 0,
        "runs_without_hard_failure": 0, "summary": "3/3 FAILED"}

    cert = slice3.capacity_certificate(suite)
    off = cert["ai_off"]
    # The point of this test: four concepts, four DIFFERENT answers.
    assert off["functional_capacity"]["value"] == 48       # degraded but complete
    assert off["engineering_capacity"]["value"] == 32      # inside frozen criteria
    assert off["engineering_knee"]["value"] == 48
    assert off["hard_failure"]["value"] == 64
    assert off["engineering_capacity"]["not"] == "a customer SLA"
    assert len({off["functional_capacity"]["value"],
                off["engineering_capacity"]["value"],
                off["hard_failure"]["value"]}) == 3, "these must not collapse"


def test_customer_acceptable_capacity_is_never_inferred_from_our_own_threshold():
    cert = slice3.capacity_certificate(_suite({}))
    cac = cert["customer_acceptable_capacity"]
    assert cac["value"] == "NOT YET DETERMINED"
    assert "has not specified" in cac["reason"]
    assert "not a substitute for a business" in cac["reason"]


def test_a_server_hard_limit_is_not_claimed_when_the_generator_was_material():
    bad = _level(requested_concurrency=64, failed=9,
                 load_generator={**_level()["load_generator"],
                                 "harness_cpu_pct_of_host": 55.0, "material": True})
    bad["classification"] = slice3.classify(bad, CRIT, ADM)
    cert = slice3.capacity_certificate(_suite({64: bad}))
    shl = cert["ai_off"]["server_hard_limit"]
    assert shl["isolated"] is False
    assert shl["value"] == NOT_AVAILABLE
    assert cert["ai_off"]["load_generator_limit"]["value"] == 64


def test_a_server_hard_limit_is_claimed_when_the_generator_was_not_material():
    bad = _level(requested_concurrency=64, failed=9)
    bad["classification"] = slice3.classify(bad, CRIT, ADM)
    cert = slice3.capacity_certificate(_suite({64: bad}))
    assert cert["ai_off"]["server_hard_limit"]["isolated"] is True
    assert cert["ai_off"]["server_hard_limit"]["value"] == 64


def test_an_empty_arm_reports_not_available_rather_than_zero():
    cert = slice3.capacity_certificate(_suite({}))
    for key in ("functional_capacity", "engineering_capacity", "hard_failure"):
        assert cert["ai_off"][key]["value"] == NOT_AVAILABLE


# ------------------------------------------------------------------- criteria
def test_the_frozen_criteria_come_from_the_slice_2_report_not_from_this_run():
    """A criterion recomputed after seeing the data it judges is not frozen."""
    f = slice3.load_frozen_criteria()
    assert f["provenance"].startswith("FROZEN IN SLICE 2")
    assert f["ai_off"]["operation_p95_ms_ref"] == 20.913
    assert f["ai_on"]["ai_p95_ms_ref"] == 1549.905
    assert f["ai_on"]["queue_dominant_rule"] == "queue_wait_p95 >= service_time_p95"
    assert f["ai_on"]["reference_concurrency"] == 2


def test_slice3_does_not_recompute_or_reassign_the_thresholds():
    src = (ROOT / "slice3.py").read_text()
    assert "freeze_criteria" not in src, "Slice 3 must not re-freeze the criteria"


# ------------------------------------------------------------------- caps
def test_the_maximum_test_cap_is_enforced_and_explicit():
    assert slice3.MAX_USERS == 256
    assert max(slice3.AI_OFF_CANDIDATES) <= slice3.MAX_USERS
    assert max(slice3.AI_ON_CANDIDATES) <= slice3.MAX_USERS


def test_the_ai_ramp_starts_above_what_slice_2_already_measured():
    assert min(slice3.AI_ON_CANDIDATES) == 12


# ------------------------------------------------- fixture fidelity (live-ish)
def test_the_test_fixture_matches_the_real_sampler_shape():
    """The fixture above once used {'max': ...} dicts for vram_total_mib and
    ram_total_mib, which the real Sampler reports as bare scalars. Every test in
    this file passed while `bottleneck()` crashed on the first real telemetry it
    ever saw. Pin the fixture to the real shape so that cannot recur."""
    from capacity_lab.core import Sampler
    import time as _t
    s = Sampler(interval=0.05).start()
    _t.sleep(0.4)
    s.stop()
    real = s.statistics()
    fake = _level()["telemetry"]
    for section in ("gpu", "system"):
        if not isinstance(real.get(section), dict):
            pytest.skip(f"no {section} telemetry on this host")
        for key, val in fake[section].items():
            assert key in real[section], f"fixture invents {section}.{key}"
            assert type(val) is type(real[section][key]), (
                f"{section}.{key}: fixture is {type(val).__name__}, "
                f"reality is {type(real[section][key]).__name__}")


def test_bottleneck_survives_real_telemetry():
    """The crash this file failed to catch: a scalar total read as a stat dict."""
    from capacity_lab.core import Sampler
    import time as _t
    s = Sampler(interval=0.05).start()
    _t.sleep(0.4)
    s.stop()
    lv = _level(telemetry=s.statistics())
    b = slice3.bottleneck(lv, ADM)
    assert b["classification"] in {"UNKNOWN", "APPLICATION", "AI QUEUE / SERIAL SERVICE",
                                   "TIMEOUT POLICY", "DATABASE", "LOCAL LOAD GENERATOR"}
    assert b["evidence"]


# =====================================================================
# CERTIFICATE / MEASUREMENT INTEGRITY DEFECTS (audit round 2)
# Each test below names the defect it pins. Every one of these passed
# review once already and was still wrong.
# =====================================================================

# ------------------------------------------------- D1 cleanup must hard-fail
def test_a_failed_cleanup_is_a_hard_failure():
    """The aborted first Slice 3 run left 32 synthetic bookings behind and
    nothing in the harness noticed: the cleanup result was recorded and never
    read."""
    lv = _level(cleanup={"state": "cleanup FAILED", "http_status": 500,
                         "error": "HTTP 500"})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["result"] == "FAIL"
    assert any("cleanup FAILED" in h for h in c["hard_failures"])
    assert c["supports_capacity_claim"] is False


def test_a_successful_cleanup_does_not_fail_the_level():
    lv = _level(cleanup={"state": "removed", "bookings_removed": 24})
    assert slice3.classify(lv, CRIT, ADM)["result"] == "PASS"


def test_cleanup_is_measured_against_bookings_created_not_sessions_run():
    """A session that failed BEFORE creating a booking legitimately removes
    nothing. Comparing against sessions_total would manufacture a failure."""
    lv = _level(sessions_total=100, completed=90, failed=10,
                application={**_level()["application"],
                             "http_status_counts": {"201": 90, "200": 180}},
                cleanup={"state": "removed", "bookings_removed": 90})
    c = slice3.classify(lv, CRIT, ADM)
    assert c["flags"] is None or not any("CLEANUP MISMATCH" in f for f in c["flags"])


def test_a_cleanup_count_mismatch_is_flagged():
    lv = _level(application={**_level()["application"],
                             "http_status_counts": {"201": 24, "200": 48}},
                cleanup={"state": "removed", "bookings_removed": 20})
    c = slice3.classify(lv, CRIT, ADM)
    assert any("CLEANUP MISMATCH" in f for f in c["flags"])
    assert any("24 booking(s) created, 20 removed" in f for f in c["flags"])


def test_the_suite_checks_for_orphaned_synthetic_data_at_the_end():
    src = (ROOT / "slice3.py").read_text()
    assert "final_synthetic_check" in src
    assert "suite_hard_failure" in src


# ------------------------------------- D2 execution counts must be observed
def test_engine_execution_counts_are_never_hardcoded_to_zero():
    """`"symoneural_llm_executions": 0` as a literal is an assertion, not a
    measurement, and it was published as a finding twice."""
    src = (ROOT / "slice3.py").read_text()
    assert '"symoneural_llm_executions": 0' not in src
    assert '"image_worker_executions": 0' not in src


def test_an_observer_that_never_sampled_reports_not_available_not_zero():
    obs = slice3.ProcessIdentityObserver()
    r = obs.report()
    assert r["observed"] is False
    for k in ("symoneural_llm_executions", "image_worker_executions",
              "native_chat_worker_executions"):
        assert r[k] == NOT_AVAILABLE, f"{k} must not be 0 when nothing was observed"


def test_the_observer_counts_distinct_pids_and_states_its_sampling_limit():
    obs = slice3.ProcessIdentityObserver(interval=0.01).start()
    import time as _t
    _t.sleep(0.2)
    obs.stop()
    r = obs.report()
    assert r["observed"] is True
    assert r["samples"] > 0
    assert isinstance(r["symoneural_llm_executions"], int)
    assert "achieved_interval_s" in r
    assert "between two samples would not be counted" in r["limitation"]


def test_the_observer_finds_this_very_process_by_argv_not_by_substring():
    """Guards the self-match bug: a substring scan matches the scanner."""
    obs = slice3.ProcessIdentityObserver()
    obs._scan()
    obs.samples = 1
    # pytest is argv[1]-agnostic here; what matters is that scanning does not
    # invent workers out of its own command line.
    assert obs.report()["native_chat_worker_executions"] == 0


def test_there_is_an_authoritative_systemd_channel_for_the_legacy_engine():
    d = slice3.legacy_unit_state("test")
    assert d.get("label") == "test"
    if "error" not in d:
        assert "NRestarts" in d
        assert "AUTHORITATIVE" in d["source"]


# ---------------------------------------------------- D3 GPU ownership rules
def _own_level(ai_mode, pids, expected=None):
    lv = _level()
    lv["telemetry"]["gpu"]["compute_pids_seen"] = pids
    L = slice3.Level.__new__(slice3.Level)
    L.ai_mode, L.expected_worker_pid = ai_mode, expected
    lv["gpu_ownership"] = L._gpu_ownership(lv["telemetry"])
    return lv


def test_ai_off_requires_zero_gpu_compute_owners():
    ok = _own_level("off", [])
    assert ok["gpu_ownership"]["ok"] is True
    assert slice3.classify(ok, CRIT, ADM)["result"] == "PASS"

    bad = _own_level("off", [4242])
    assert bad["gpu_ownership"]["ok"] is False
    c = slice3.classify(bad, CRIT, ADM)
    assert c["result"] == "FAIL"
    assert any("GPU OWNERSHIP VIOLATION" in h for h in c["hard_failures"])


def test_ai_on_requires_exactly_the_expected_worker_pid():
    ok = _own_level("on", [51088], expected=51088)
    assert ok["gpu_ownership"]["ok"] is True
    assert slice3.classify(ok, CRIT, ADM)["result"] == "PASS"


def test_ai_on_fails_on_a_stranger_or_a_respawn():
    stranger = _own_level("on", [99999], expected=51088)
    assert slice3.classify(stranger, CRIT, ADM)["result"] == "FAIL"
    # a respawn shows up as two distinct pids over the level
    respawn = _own_level("on", [51088, 51099], expected=51088)
    assert respawn["gpu_ownership"]["ok"] is False
    assert slice3.classify(respawn, CRIT, ADM)["result"] == "FAIL"


def test_ai_on_fails_when_no_worker_was_ever_seen():
    none_seen = _own_level("on", [], expected=51088)
    assert slice3.classify(none_seen, CRIT, ADM)["result"] == "FAIL"


# ------------------------------- D4 5xx must not auto-classify as DATABASE
def _5xx(evidence):
    return _level(application={**_level()["application"],
                               "http_status_counts": {"200": 20, "500": 4}},
                  subsystem_evidence=evidence)


def test_a_5xx_without_database_evidence_is_not_called_a_database_problem():
    """The client sees an opaque 500. Calling every 5xx DATABASE would send
    Donnie shopping for a bigger database he does not need."""
    lv = _5xx({"server_log_bytes": 0, "database_evidence": False,
               "traceback_present": False})
    b = slice3.bottleneck(lv, ADM)
    assert b["classification"] == "APPLICATION"
    assert b["classification"] != "DATABASE"
    joined = " ".join(b["evidence"])
    assert "NO database evidence" in joined
    assert "UNCONFIRMED" in joined


def test_a_5xx_with_real_database_evidence_is_classified_as_database():
    lv = _5xx({"server_log_bytes": 900, "database_evidence": True,
               "database_markers": ["database is locked", "sqlite3."],
               "traceback_present": True})
    b = slice3.bottleneck(lv, ADM)
    assert b["classification"] == "DATABASE"
    assert any("database is locked" in e for e in b["evidence"])


def test_database_evidence_comes_from_the_server_log_not_from_guessing():
    assert slice3.subsystem_evidence("")["database_evidence"] is False
    e = slice3.subsystem_evidence(
        "Traceback (most recent call last):\n"
        "sqlite3.OperationalError: database is locked\n")
    assert e["database_evidence"] is True
    assert e["traceback_present"] is True
    assert "database is locked" in e["database_markers"]
    # an unrelated traceback is NOT database evidence
    e2 = slice3.subsystem_evidence("Traceback (most recent call last):\nKeyError: 'x'\n")
    assert e2["database_evidence"] is False
    assert e2["traceback_present"] is True


# ------------------- D5 timeout policy is not a server hard limit
def _fail_level(users, hard):
    lv = _level(requested_concurrency=users, achieved_max_concurrency=users, failed=5)
    lv["classification"] = {"result": "FAIL", "hard_failures": hard, "flags": None,
                            "validity": None, "caveats": None,
                            "supports_capacity_claim": False, "ratios": {}}
    return lv


def _arm(levels, **extra):
    return {"levels": {str(k): v for k, v in levels.items()}, **extra}


def test_a_timeout_policy_failure_is_not_promoted_to_a_server_hard_limit():
    """A configured timeout expiring is a policy boundary. The server did not
    break; it was told to stop waiting."""
    lv = _fail_level(64, ["12 AI error(s): {'TIMEOUT POLICY / QUEUE ADMISSION': 12}"])
    cert = slice3.capacity_certificate({"ai_off": _arm({64: lv}), "ai_on": _arm({})})
    off = cert["ai_off"]
    assert off["server_hard_limit"]["isolated"] is False
    assert off["server_hard_limit"]["value"] == NOT_AVAILABLE
    assert off["timeout_policy_limit"]["value"] == 64
    assert "Raising the timeout moves this number" in off["timeout_policy_limit"]["note"]
    assert off["server_hard_limit"]["excluded_timeout_policy_levels"] == [64]


def test_a_genuine_failure_alongside_a_timeout_still_counts_as_a_server_limit():
    """Deriving this from the single `bottleneck` label would hide a real 5xx
    behind a co-occurring timeout, because bottleneck() checks timeouts first."""
    lv = _fail_level(64, ["HTTP 500 x9",
                          "3 AI error(s): {'TIMEOUT POLICY / QUEUE ADMISSION': 3}"])
    lv2 = dict(lv)
    cert = slice3.capacity_certificate({"ai_off": _arm(
        {64: lv2}, repeatability_first_failure={
            "users": 64, "total_runs": 3, "successful_runs": 0,
            "runs_without_hard_failure": 0, "summary": "3/3 FAILED"}),
        "ai_on": _arm({})})
    assert cert["ai_off"]["server_hard_limit"]["isolated"] is True
    assert cert["ai_off"]["server_hard_limit"]["value"] == 64
    assert cert["ai_off"]["timeout_policy_limit"]["value"] == NOT_AVAILABLE


# ---------------------- D6 headlines must REQUIRE the repeatability runs
def _pass_level(users):
    lv = _level(requested_concurrency=users, achieved_max_concurrency=users)
    lv["classification"] = slice3.classify(lv, CRIT, ADM)
    return lv


def test_functional_capacity_is_not_claimed_without_the_required_repeats():
    """Attaching a repeat summary beside a number taken from a single run looks
    like confirmation without being it."""
    cert = slice3.capacity_certificate(
        {"ai_off": _arm({32: _pass_level(32)}), "ai_on": _arm({})})
    fc = cert["ai_off"]["functional_capacity"]
    assert fc["value"] == NOT_AVAILABLE
    assert fc["highest_single_run_clean"] == 32
    assert "NOT confirmed" in fc["basis"]
    assert f"{slice3.REPEATS} independent repeats" in fc["basis"] or "repeats" in fc["basis"]


def test_functional_capacity_is_claimed_when_the_repeats_all_prove_it():
    cert = slice3.capacity_certificate({"ai_off": _arm(
        {32: _pass_level(32)},
        repeatability_highest_clean={"users": 32, "total_runs": 3,
                                     "successful_runs": 3,
                                     "runs_without_hard_failure": 3,
                                     "summary": "3/3 PROVE CAPACITY"}),
        "ai_on": _arm({})})
    fc = cert["ai_off"]["functional_capacity"]
    assert fc["value"] == 32
    assert "confirmed by repeats" in fc["basis"]


def test_partial_repeats_do_not_confirm_a_headline():
    cert = slice3.capacity_certificate({"ai_off": _arm(
        {32: _pass_level(32)},
        repeatability_highest_clean={"users": 32, "total_runs": 3,
                                     "successful_runs": 2,
                                     "runs_without_hard_failure": 3,
                                     "summary": "2/3 PROVE CAPACITY"}),
        "ai_on": _arm({})})
    assert cert["ai_off"]["functional_capacity"]["value"] == NOT_AVAILABLE


def test_when_the_top_level_fails_repeats_a_confirmed_lower_rung_is_used():
    cert = slice3.capacity_certificate({"ai_off": _arm(
        {24: _pass_level(24), 32: _pass_level(32)},
        repeatability_highest_clean={"users": 32, "total_runs": 3,
                                     "successful_runs": 1,
                                     "runs_without_hard_failure": 3,
                                     "summary": "1/3 PROVE CAPACITY"},
        repeatability_fallback={"users": 24, "total_runs": 3, "successful_runs": 3,
                                "runs_without_hard_failure": 3,
                                "summary": "3/3 PROVE CAPACITY"}),
        "ai_on": _arm({})})
    fc = cert["ai_off"]["functional_capacity"]
    assert fc["value"] == 24
    assert fc["highest_single_run_clean"] == 32
    assert "NOT confirmed" in fc["basis"] and "highest CONFIRMED level is 24" in fc["basis"]


def test_an_unrepeated_hard_failure_is_not_a_headline_hard_failure():
    lv = _fail_level(64, ["HTTP 500 x9"])
    cert = slice3.capacity_certificate({"ai_off": _arm({64: lv}), "ai_on": _arm({})})
    hf = cert["ai_off"]["hard_failure"]
    assert hf["value"] == NOT_AVAILABLE
    assert hf["first_observed_single_run"] == 64
    assert "NOT confirmed" in hf["basis"]


def test_the_walkdown_is_bounded_and_says_what_it_skipped():
    src = (ROOT / "slice3.py").read_text()
    assert "MAX_FALLBACK_RUNGS" in src
    assert "repeatability_walkdown_exhausted" in src
    assert "not_tried" in src


# ------------- D7 a repeat proves capacity only if it supports a claim
def test_a_repeat_that_did_not_achieve_concurrency_does_not_prove_capacity():
    """'Did not FAIL' is not 'proved the number on its label'."""
    runs = [{"result": "DEGRADED", "supports_capacity_claim": False},
            {"result": "PASS", "supports_capacity_claim": True},
            {"result": "PASS", "supports_capacity_claim": True}]
    passes = sum(1 for r in runs if r["supports_capacity_claim"])
    not_failed = sum(1 for r in runs if r["result"] != "FAIL")
    assert passes == 2 and not_failed == 3, "the two counts must not be conflated"


def test_repeat_level_counts_only_capacity_proving_runs():
    src = (ROOT / "slice3.py").read_text()
    assert 'passes = sum(1 for r in runs if r["supports_capacity_claim"])' in src
    assert '"summary": f"{passes}/{n} PROVE CAPACITY"' in src
    assert "runs_without_hard_failure" in src


def test_repeat_level_itself_separates_proving_runs_from_merely_not_failing(monkeypatch):
    """The behavioural half of D7, and the reason it is not only a source grep.

    The two tests above assert on the *text* of `repeat_level` and on arithmetic
    re-implemented inside the test. Both pass without `repeat_level` ever being
    called, so neither would notice the counter being changed to
    `r["result"] != "FAIL"` -- which is precisely the conflation D7 exists to
    prevent, and precisely the mutation the source grep is standing in for.
    Assert on the returned record instead: this fails if the real function ever
    counts a DEGRADED run, or a run that missed its concurrency, as proof.

    `run_level` is stubbed because the real one needs a server, a GPU and a
    booking store. What is under test is the counting rule, not the level.
    """
    # Three levels, none of which FAILED, and the distinction between them is
    # the whole point:
    #
    #   * `short` did not achieve its requested concurrency. That is a VALIDITY
    #     defect, so it does not support a claim at 32 -- but its result is
    #     PASS, because a validity defect is not a DEGRADED flag and not a hard
    #     failure. This is the run a "did not FAIL" counter wrongly credits.
    #   * `degraded` is slow against the frozen reference but every session
    #     completed at the requested concurrency, so it DOES support a claim.
    #     `supports_capacity_claim` is `not hard and not validity` -- DEGRADED
    #     is a flag, not a validity defect. Asserted here so nobody later
    #     "fixes" that by folding flags in: 32 users really were served.
    #   * `clean` is an unremarkable PASS.
    short = _level(requested_concurrency=32, achieved_max_concurrency=19)
    short["concurrency_achieved"] = False
    degraded = _level(requested_concurrency=32, achieved_max_concurrency=32)
    degraded["application"]["operation_latency_ms"] = {"p50": 40.0, "p95": 90.0, "p99": 99.0}
    clean = _level(requested_concurrency=32, achieved_max_concurrency=32)

    scripted = []
    for i, lv in enumerate((short, degraded, clean)):
        lv["classification"] = slice3.classify(lv, CRIT, ADM)
        lv["run_id"] = f"BENCH-20260824-100{i}"
        scripted.append(lv)

    # The fixture is only meaningful if it really is the conflation case: three
    # runs where none FAILED but not all prove the number.
    results = [lv["classification"]["result"] for lv in scripted]
    supports = [lv["classification"]["supports_capacity_claim"] for lv in scripted]
    assert results == ["PASS", "DEGRADED", "PASS"], results
    assert supports == [False, True, True], supports

    calls = iter(scripted)
    monkeypatch.setattr(slice3, "run_level",
                        lambda *a, **k: next(calls))
    monkeypatch.setattr(slice3, "log", lambda *a, **k: None)

    rep = slice3.repeat_level(32, "off", None, CRIT, ADM,
                              lambda users: (3, "cal"), [], n=3)

    # None of the three FAILED, so a "did not fail" counter would say 3/3.
    assert rep["runs_without_hard_failure"] == 3
    # Only two of them actually prove 32 users. This is the assertion that dies
    # if the counter is ever changed to `r["result"] != "FAIL"`.
    assert rep["successful_runs"] == 2, (
        "a run that missed its requested concurrency must not count as proof of "
        f"the number on its label; got {rep['summary']}")
    assert rep["summary"] == "2/3 PROVE CAPACITY"
    # 2 of 3 is neither all nor none, so the boundary is intermittent and must
    # not be rounded to a sharp number.
    assert rep["repeatable"] is False
    # And the per-run record keeps the two facts separable for a reader.
    assert [r["supports_capacity_claim"] for r in rep["runs"]] == [False, True, True]


# ------------------------------------------- D8 queue depth semantics
def _fake_player():
    """A NativeChatPlayer with the supervisor replaced by a sleep, so the queue
    discipline can be tested without a GPU."""
    import capacity_lab.native_player as np

    class FakeSup:
        def __init__(self, delay): self.delay = delay
        def request(self, payload, timeout):
            import time as _t
            _t.sleep(self.delay)
            return {"type": "result", "completion_tokens": 4, "tok_per_s": 10.0}

    p = np.NativeChatPlayer.__new__(np.NativeChatPlayer)
    import threading as _th
    p._cv = _th.Condition()
    p._next_ticket = p._now_serving = 0
    p._abandoned = set()
    p._waiting = p._active = 0
    p._max_depth = p._max_active = p._max_in_system = 0
    p._queue_waits, p._samples = [], []
    p.sup = FakeSup(0.05)
    p.name = "SyMon AI"
    p.cold_start_s = p.worker_pid = p.worker_vram_mib = None
    p.ready_report = None
    return p


@pytest.mark.parametrize("n", [2, 4, 8])
def test_max_queue_depth_is_requests_waiting_behind_the_one_in_service(n):
    """queue_depth must be N-1, not N. The old code incremented `waiting` before
    acquiring the gate and decremented it after, so a request that already held
    the worker was still counted as waiting."""
    import threading as _th
    p = _fake_player()
    start = _th.Barrier(n)

    def go():
        start.wait(timeout=10)
        p.invoke("hi", timeout=30)

    ts = [_th.Thread(target=go) for _ in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=30)

    m = p.metrics()
    assert m["max_active_ai_requests"] == 1, "only one request may be in service"
    assert m["max_queue_depth"] == n - 1, (
        f"{n} concurrent requests must show {n-1} waiting BEHIND the active one, "
        f"got {m['max_queue_depth']}")
    assert m["max_total_ai_in_system_observed"] == n


def test_total_in_system_is_observed_not_summed_from_separate_maxima():
    """max(active) + max(depth) is not max(active + depth): the two peaks can
    occur at different instants, so the sum is a figure no request experienced."""
    p = _fake_player()
    m = p.metrics()
    assert "max_total_ai_in_system_observed" in m
    src = (ROOT / "capacity_lab" / "native_player.py").read_text()
    assert "_max_in_system" in src


def test_service_is_strictly_serialised_and_fifo():
    import threading as _th
    p = _fake_player()
    n = 6
    order, lock = [], _th.Lock()
    start = _th.Barrier(n)

    def go(i):
        start.wait(timeout=10)
        # stagger arrival so ticket order is well defined
        import time as _t
        _t.sleep(0.02 * i)
        with lock:
            order.append(("enq", i))
        p.invoke("hi", timeout=30)
        with lock:
            order.append(("done", i))

    ts = [_th.Thread(target=go, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
    done = [i for tag, i in order if tag == "done"]
    assert done == sorted(done), f"service order was not FIFO: {done}"
    assert p.metrics()["max_active_ai_requests"] == 1


def test_queue_wait_latency_semantics_are_unchanged():
    """The fix must not redefine what queue wait MEANS: still enqueue -> start
    of service, still excluding inference time."""
    p = _fake_player()
    r = p.invoke("hi", timeout=30)
    assert r.ok
    assert getattr(r, "queue_wait_s") < 0.02, "an idle worker must have ~no queue wait"
    assert getattr(r, "service_s") >= 0.05, "service time must cover the inference"
    assert r.latency_s >= getattr(r, "service_s")


def test_an_abandoned_ticket_does_not_wedge_the_queue_behind_it():
    """A middle request timing out must not block everyone after it -- that
    would read in the report as a worker hang rather than as a timeout."""
    import threading as _th
    p = _fake_player()
    p.sup.delay = 0.30
    results = {}

    def go(i, tmo):
        results[i] = p.invoke("hi", timeout=tmo)

    a = _th.Thread(target=go, args=(0, 30.0))     # holds the worker
    a.start()
    import time as _t
    _t.sleep(0.05)
    b = _th.Thread(target=go, args=(1, 0.05))     # will give up while queued
    c = _th.Thread(target=go, args=(2, 30.0))     # must still be served
    b.start(); _t.sleep(0.01); c.start()
    for t in (a, b, c):
        t.join(timeout=30)

    assert results[0].ok
    assert results[1].ok is False
    assert getattr(results[1], "fault_class") == "TIMEOUT POLICY / QUEUE ADMISSION"
    assert results[2].ok, "the request behind an abandoned ticket was never served"


def test_resetting_level_counters_clears_the_ticket_state():
    p = _fake_player()
    p.invoke("hi", timeout=30)
    assert p._next_ticket > 0
    p.reset_level_counters()
    assert p._max_depth == 0 and p._max_active == 0 and p._max_in_system == 0
    assert p._next_ticket == 0 and p._now_serving == 0 and p._abandoned == set()


def test_tickets_are_not_rewound_while_work_is_in_flight():
    """Rewinding ticket numbers with a request in service would hand two
    requests the same turn."""
    p = _fake_player()
    p._waiting, p._active = 0, 1
    p._next_ticket, p._now_serving = 7, 7
    p.reset_level_counters()
    assert p._next_ticket == 7 and p._now_serving == 7


# --------------------------------------- achieved vs nominal sample interval
def test_the_achieved_sample_interval_is_reported_next_to_the_nominal_one():
    """Every 'a short-lived process could slip between samples' caveat is sized
    by the ACHIEVED rate. nvidia-smi spawns twice per sample, so the achieved
    interval is slower than the requested one."""
    stats = slice3._with_achieved_interval(
        {"sample_count": 50, "span_s": 5.0, "sample_interval_s": 0.05})
    assert stats["nominal_interval_s"] == 0.05
    assert stats["achieved_interval_s"] == 0.1
    assert stats["achieved_interval_s"] > stats["nominal_interval_s"]


def test_achieved_interval_is_skipped_when_there_are_no_samples():
    stats = slice3._with_achieved_interval({"sample_count": 0, "span_s": 0})
    assert "achieved_interval_s" not in stats
