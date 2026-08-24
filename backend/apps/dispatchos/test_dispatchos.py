"""DispatchOS booking core: state machine, quote handling, benchmark isolation.

The isolation tests are the ones that matter most. A benchmark that can reach a
real booking is not a benchmark, it is a data-loss incident.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.dispatchos import (  # noqa: E402
    BENCHMARK_SYNTHETIC_QUOTE_CENTS, BookingError, CANCELLED, COMPLETED, CONFIRMED,
    DISPATCH, NOT_IMPLEMENTED_EFFECTS, QUOTED, QUOTE_MANUAL, QUOTE_PENDING,
    QUOTE_PENDING_STATUS, QUOTE_SYNTHETIC, REMINDER, REQUEST, REVIEW, TRANSITIONS,
    advance, clear_benchmark_run, create_booking, get_booking, is_run_id,
    list_bookings, set_quote, using_db)

RUN_A = "BENCH-20260824-0001"
RUN_B = "BENCH-20260824-0002"


@pytest.fixture(autouse=True)
def _db(tmp_path):
    with using_db(tmp_path / "dispatchos.db"):
        yield


def _fields(**over):
    d = dict(pickup="Terminal 2", dropoff="1200 Smallman St",
             scheduled_utc=time.time() + 3600, passengers=2, bags=3,
             vehicle_type="suv", instructions="car seat")
    d.update(over)
    return d


def _synth(run_id=RUN_A, **over):
    return create_booking(**_fields(synthetic=True, benchmark_run_id=run_id, **over))


def _real(**over):
    return create_booking(**_fields(**over))


# ------------------------------------------------------------------- creation
def test_create_starts_in_request_with_no_quote():
    b = _real()
    assert b["status"] == REQUEST
    assert b["quote_status"] == QUOTE_PENDING_STATUS
    assert b["quote_amount_cents"] is None, "a booking must not arrive pre-priced"
    assert b["synthetic"] == 0 and b["benchmark_run_id"] is None


def test_all_lean_first_version_fields_persist():
    b = _real(customer_name="Rider", customer_phone="+1-555-0100")
    for f in ("pickup", "dropoff", "scheduled_utc", "passengers", "bags",
              "vehicle_type", "instructions", "customer_name", "customer_phone"):
        assert b[f] not in (None, ""), f


def test_no_pricing_engine_exists():
    """The whole point: nothing computes a quote, because the rules are undefined."""
    import apps.dispatchos as d
    src = Path(d.__file__).read_text()
    for banned in ("def calculate_price", "def compute_quote", "per_mile",
                   "mileage_rate", "airport_fee", "wait_charge"):
        assert banned not in src, f"a pricing rule appeared: {banned}"


def test_bad_vehicle_type_and_counts_refused():
    with pytest.raises(BookingError):
        _real(vehicle_type="submarine")
    with pytest.raises(BookingError):
        _real(passengers=0)
    with pytest.raises(BookingError):
        _real(bags=-1)
    with pytest.raises(BookingError):
        _real(pickup="")


# --------------------------------------------------------------- state machine
def test_full_happy_path_walks_every_state():
    b = _synth()
    b = advance(b["id"], QUOTE_PENDING)
    b = set_quote(b["id"], amount_cents=BENCHMARK_SYNTHETIC_QUOTE_CENTS,
                  source=QUOTE_SYNTHETIC)
    assert b["status"] == QUOTED
    for target in (CONFIRMED, DISPATCH, REMINDER, COMPLETED, REVIEW):
        b = advance(b["id"], target)
        assert b["status"] == target
    assert [e["to_status"] for e in b["events"]][0] == REQUEST


def test_illegal_transitions_are_refused_not_applied():
    b = _synth()
    with pytest.raises(BookingError, match="illegal transition"):
        advance(b["id"], COMPLETED)          # REQUEST -> COMPLETED must not exist
    assert get_booking(b["id"])["status"] == REQUEST, "state changed despite refusal"


def test_confirm_from_quote_pending_is_refused_by_the_transition_map():
    """First layer: the state machine itself has no QUOTE_PENDING -> CONFIRMED edge."""
    b = _synth()
    advance(b["id"], QUOTE_PENDING)
    with pytest.raises(BookingError, match="illegal transition"):
        advance(b["id"], CONFIRMED)
    assert get_booking(b["id"])["status"] == QUOTE_PENDING


def test_quote_guard_is_defence_in_depth_and_actually_works():
    """Second layer, proven independently.

    The transition map already blocks the only route to CONFIRMED without a
    quote, so the `no quote` guard in advance() is unreachable through the public
    API. That makes it easy to believe it works without ever executing it -- so
    this test reaches past the API, forces the exact state the guard exists for
    (QUOTED with the quote wiped), and confirms the guard fires.
    """
    import sqlite3
    from apps.dispatchos import db_path
    b = _synth()
    advance(b["id"], QUOTE_PENDING)
    set_quote(b["id"], amount_cents=500, source=QUOTE_SYNTHETIC)

    c = sqlite3.connect(str(db_path()))
    c.execute("UPDATE bookings SET quote_status=? WHERE id=?",
              (QUOTE_PENDING_STATUS, b["id"]))
    c.commit(); c.close()

    assert get_booking(b["id"])["status"] == QUOTED     # legal edge to CONFIRMED
    with pytest.raises(BookingError, match="no quote"):
        advance(b["id"], CONFIRMED)
    assert get_booking(b["id"])["status"] == QUOTED, "state changed despite refusal"


def test_terminal_states_are_terminal():
    assert TRANSITIONS[REVIEW] == ()
    assert TRANSITIONS[CANCELLED] == ()


def test_states_with_unimplemented_effects_say_so():
    """REMINDER must not imply an SMS was sent."""
    b = _synth()
    advance(b["id"], QUOTE_PENDING)
    set_quote(b["id"], amount_cents=1, source=QUOTE_SYNTHETIC)
    advance(b["id"], CONFIRMED); advance(b["id"], DISPATCH)
    b = advance(b["id"], REMINDER)
    assert "no SMS" in b["effect_not_implemented"]
    # Slice 2 added ride states, each of which must also declare its unimplemented
    # effect. The set grows; what must not change is that every state with a
    # real-world effect we have NOT built says so.
    assert {DISPATCH, REMINDER, REVIEW} <= set(NOT_IMPLEMENTED_EFFECTS)
    for state, text in NOT_IMPLEMENTED_EFFECTS.items():
        assert text and ("no " in text.lower() or "internal" in text.lower()), state


def test_events_are_recorded_for_every_transition():
    b = _synth()
    advance(b["id"], QUOTE_PENDING)
    b = advance(b["id"], CANCELLED)
    assert [e["to_status"] for e in b["events"]] == [REQUEST, QUOTE_PENDING, CANCELLED]


# --------------------------------------------------------------------- quotes
def test_manual_quote_is_the_production_path():
    b = _real()
    advance(b["id"], QUOTE_PENDING)
    b = set_quote(b["id"], amount_cents=8500, source=QUOTE_MANUAL)
    assert b["quote_status"] == QUOTE_MANUAL
    assert b["quote_amount_cents"] == 8500 and b["quote_source"] == QUOTE_MANUAL


def test_synthetic_quote_is_refused_on_a_real_booking():
    """The benchmark fixture must never become production pricing."""
    b = _real()
    advance(b["id"], QUOTE_PENDING)
    with pytest.raises(BookingError, match="synthetic quote refused"):
        set_quote(b["id"], amount_cents=BENCHMARK_SYNTHETIC_QUOTE_CENTS,
                  source=QUOTE_SYNTHETIC)


def test_quote_only_settable_in_quote_pending():
    b = _synth()
    with pytest.raises(BookingError):
        set_quote(b["id"], amount_cents=100, source=QUOTE_SYNTHETIC)


def test_negative_quote_refused():
    b = _synth()
    advance(b["id"], QUOTE_PENDING)
    with pytest.raises(BookingError):
        set_quote(b["id"], amount_cents=-1, source=QUOTE_SYNTHETIC)


# ---------------------------------------------------------- benchmark isolation
def test_synthetic_requires_a_valid_run_id():
    for bad in ("all", "*", "", "bench-20260824-0001", "../../etc/passwd", None):
        with pytest.raises(BookingError):
            create_booking(**_fields(synthetic=True, benchmark_run_id=bad))


def test_run_id_on_a_real_booking_is_refused():
    with pytest.raises(BookingError, match="only valid on synthetic"):
        create_booking(**_fields(synthetic=False, benchmark_run_id=RUN_A))


def test_is_run_id_rejects_everything_malformed():
    assert is_run_id(RUN_A)
    for bad in ("all", "*", "", "BENCH-2026-0001", "BENCH-20260824-1",
                "../secrets", "BENCH-20260824-0001x", None, 42):
        assert not is_run_id(bad), bad


def test_cleanup_refuses_malformed_wildcard_and_traversal():
    for bad in ("all", "*", "", "../../etc/passwd", "BENCH-bad", "%"):
        with pytest.raises(BookingError, match="refusing"):
            clear_benchmark_run(bad)


def test_clearing_run_a_cannot_touch_run_b():
    a1, a2 = _synth(RUN_A), _synth(RUN_A)
    b1 = _synth(RUN_B)
    out = clear_benchmark_run(RUN_A)
    assert out["bookings_removed"] == 2
    assert get_booking(a1["id"]) is None and get_booking(a2["id"]) is None
    assert get_booking(b1["id"]) is not None, "an unrelated run was destroyed"


def test_benchmark_cleanup_can_never_remove_a_real_booking():
    """The delete is constrained to synthetic=1, so even a matching run id on a
    real row -- which create_booking already refuses -- could not remove it."""
    real = _real()
    _synth(RUN_A)
    clear_benchmark_run(RUN_A)
    assert get_booking(real["id"]) is not None, "a real booking was deleted"
    assert len(list_bookings(synthetic=False)) == 1


def test_no_generic_clear_all_exists():
    import apps.dispatchos as d
    assert not hasattr(d, "clear_all")
    assert not hasattr(d, "delete_all_bookings")
    src = Path(d.__file__).read_text()
    assert "DELETE FROM bookings\n" not in src, "an unconstrained delete exists"


def test_cleanup_is_idempotent():
    _synth(RUN_A)
    assert clear_benchmark_run(RUN_A)["bookings_removed"] == 1
    assert clear_benchmark_run(RUN_A)["bookings_removed"] == 0


def test_synthetic_and_real_are_separable():
    _synth(RUN_A); _real()
    assert len(list_bookings(synthetic=True)) == 1
    assert len(list_bookings(synthetic=False)) == 1
    assert len(list_bookings(benchmark_run_id=RUN_A)) == 1


def test_synthetic_ids_carry_the_run_id():
    b = _synth(RUN_A)
    assert RUN_A in b["id"], "a synthetic row should be identifiable by id alone"


# ------------------------------------------------- slice 2: ride lifecycle actions
from apps.dispatchos import (  # noqa: E402
    ARRIVED, EN_ROUTE, IN_TRIP, PAYMENT_PENDING, SCHEDULED, WAITING,
    ACTIONS, CHANGE_DROPOFF_STATES, QUICK_STOP_STATES, RESCHEDULE_STATES,
    add_quick_stop, change_dropoff, mark_payment, reschedule)


def _to(b, *targets):
    for t in targets:
        b = advance(b["id"], t)
    return b


def _ready_for_ride(run=RUN_A):
    b = _synth(run)
    advance(b["id"], QUOTE_PENDING)
    set_quote(b["id"], amount_cents=1, source=QUOTE_SYNTHETIC)
    return advance(b["id"], CONFIRMED)


def test_full_ride_lifecycle_reaches_review():
    b = _ready_for_ride()
    b = _to(b, SCHEDULED, DISPATCH, EN_ROUTE, ARRIVED, WAITING, IN_TRIP,
            PAYMENT_PENDING, COMPLETED, REVIEW)
    assert b["status"] == REVIEW
    seen = [e["to_status"] for e in b["events"]]
    for s in (EN_ROUTE, ARRIVED, WAITING, IN_TRIP, PAYMENT_PENDING):
        assert s in seen, s


def test_slice15_happy_path_still_works():
    """The Slice 1.5 path must not have been broken by adding ride states."""
    b = _ready_for_ride()
    b = _to(b, DISPATCH, REMINDER, COMPLETED, REVIEW)
    assert b["status"] == REVIEW


def test_quick_stop_appends_and_is_state_guarded():
    b = _ready_for_ride()
    b = _to(b, DISPATCH, EN_ROUTE)
    b = add_quick_stop(b["id"], "Pharmacy on Penn Ave")
    b = add_quick_stop(b["id"], "ATM")
    import json as _j
    assert _j.loads(b["quick_stops"]) == ["Pharmacy on Penn Ave", "ATM"]
    assert b["status"] == EN_ROUTE, "a quick stop must not change ride state"


def test_quick_stop_refused_before_the_ride_exists():
    b = _synth()
    with pytest.raises(BookingError, match="cannot add a quick stop"):
        add_quick_stop(b["id"], "nope")


def test_quick_stop_is_bounded():
    b = _to(_ready_for_ride(), DISPATCH, EN_ROUTE)
    for i in range(5):
        add_quick_stop(b["id"], f"stop {i}")
    with pytest.raises(BookingError, match="too many"):
        add_quick_stop(b["id"], "one too many")


def test_change_dropoff_updates_and_counts():
    b = _to(_ready_for_ride(), DISPATCH, EN_ROUTE)
    b = change_dropoff(b["id"], "5000 Forbes Ave")
    assert b["dropoff"] == "5000 Forbes Ave" and b["dropoff_changes"] == 1
    assert b["status"] == EN_ROUTE


def test_change_dropoff_refused_after_completion():
    b = _to(_ready_for_ride(), DISPATCH, EN_ROUTE, ARRIVED, IN_TRIP, COMPLETED)
    with pytest.raises(BookingError, match="cannot change dropoff"):
        change_dropoff(b["id"], "too late")


def test_reschedule_only_before_the_ride_is_under_way():
    b = _ready_for_ride()
    b = reschedule(b["id"], time.time() + 7200)
    assert b["reschedules"] == 1
    b = _to(b, DISPATCH, EN_ROUTE)
    with pytest.raises(BookingError, match="cannot reschedule"):
        reschedule(b["id"], time.time() + 9999)


def test_payment_state_is_internal_only_and_state_guarded():
    b = _to(_ready_for_ride(), DISPATCH, EN_ROUTE, ARRIVED, IN_TRIP)
    b = mark_payment(b["id"], "RECORDED")
    assert b["payment_state"] == "RECORDED"
    assert any("no processor called" in (e["note"] or "") for e in b["events"])


def test_payment_refused_before_the_trip():
    b = _ready_for_ride()
    with pytest.raises(BookingError, match="cannot record payment"):
        mark_payment(b["id"], "RECORDED")


def test_no_payment_processor_is_ever_contacted():
    import apps.dispatchos as d
    src = Path(d.__file__).read_text()
    for banned in ("stripe", "braintree", "paypal", "requests.post", "urllib.request",
                   "httpx", "twilio", "sendgrid"):
        assert banned not in src, f"dispatchos reaches an external service: {banned}"


def test_every_new_state_declares_its_unimplemented_effect():
    for s in (EN_ROUTE, ARRIVED, WAITING, PAYMENT_PENDING):
        assert s in NOT_IMPLEMENTED_EFFECTS, s
    assert "NO payment processor" in NOT_IMPLEMENTED_EFFECTS[PAYMENT_PENDING]


def test_action_and_state_vocabularies_are_distinct():
    """An ACTION is what someone does; a STATE is where the ride is."""
    assert set(ACTIONS).isdisjoint(set(TRANSITIONS)), \
        "an action name collides with a state name"
    for a in ("CONFIRM_PICKUP", "ADD_QUICK_STOP", "CHANGE_DROPOFF", "RESCHEDULE",
              "MARK_PAYMENT", "COMPLETE_RIDE"):
        assert a in ACTIONS, a


def test_in_flight_mutations_never_change_state():
    b = _to(_ready_for_ride(), DISPATCH, EN_ROUTE)
    before = b["status"]
    assert add_quick_stop(b["id"], "x")["status"] == before
    assert change_dropoff(b["id"], "y")["status"] == before


def test_state_guard_lists_are_coherent():
    for s in QUICK_STOP_STATES + CHANGE_DROPOFF_STATES + RESCHEDULE_STATES:
        assert s in TRANSITIONS, f"{s} is not a real state"


# --------------------------------------------------------- schema migration
def test_an_old_database_is_migrated_not_broken(tmp_path):
    """The regression that cost a whole calibration run.

    `CREATE TABLE IF NOT EXISTS` does nothing to a table that already exists, so
    adding a column to _SCHEMA does not reach a database written by an earlier
    version. Every unit test passed -- they all use a fresh tmp_path db -- while
    the real file returned HTTP 500 on the first insert. This builds a
    pre-migration database on purpose and proves the migration repairs it.
    """
    import sqlite3
    from apps.dispatchos import _ADDED_COLUMNS, _migrate

    db = tmp_path / "old.db"
    c = sqlite3.connect(str(db))
    # the Slice 1.5 shape: everything except the four ride columns
    c.executescript("""
        CREATE TABLE bookings (
            id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
            status TEXT NOT NULL, pickup TEXT NOT NULL, dropoff TEXT NOT NULL,
            scheduled_utc REAL NOT NULL, passengers INTEGER NOT NULL,
            bags INTEGER NOT NULL, vehicle_type TEXT NOT NULL, instructions TEXT,
            quote_status TEXT NOT NULL, quote_amount_cents INTEGER,
            quote_currency TEXT, quote_source TEXT, customer_name TEXT,
            customer_phone TEXT, synthetic INTEGER NOT NULL DEFAULT 0,
            benchmark_run_id TEXT);
        CREATE TABLE booking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id TEXT NOT NULL,
            at REAL NOT NULL, from_status TEXT, to_status TEXT NOT NULL, note TEXT);
    """)
    c.execute("INSERT INTO bookings (id,created,updated,status,pickup,dropoff,"
              "scheduled_utc,passengers,bags,vehicle_type,quote_status) VALUES "
              "('bk_old',1,1,'REQUEST','a','b',1,1,0,'suv','PENDING')")
    c.commit()
    before = {r[1] for r in c.execute("PRAGMA table_info(bookings)")}
    for name, _ in _ADDED_COLUMNS:
        assert name not in before, "fixture is not actually a pre-migration schema"

    added = _migrate(c)
    c.commit()
    assert sorted(added) == sorted(n for n, _ in _ADDED_COLUMNS), added
    after = {r[1] for r in c.execute("PRAGMA table_info(bookings)")}
    for name, _ in _ADDED_COLUMNS:
        assert name in after, name
    # the pre-existing row survived and got the declared defaults
    row = dict(zip([d[0] for d in c.execute("SELECT * FROM bookings").description],
                   c.execute("SELECT * FROM bookings").fetchone()))
    assert row["id"] == "bk_old", "an existing booking was lost by the migration"
    assert row["payment_state"] == "NONE" and row["dropoff_changes"] == 0
    assert _migrate(c) == [], "migration is not idempotent"
    c.close()

    # and the real code path works end to end against that upgraded file
    with using_db(db):
        b = create_booking(**_fields(synthetic=True, benchmark_run_id=RUN_A))
        assert b["status"] == REQUEST
        advance(b["id"], QUOTE_PENDING)
        set_quote(b["id"], amount_cents=1, source=QUOTE_SYNTHETIC)
        b = advance(b["id"], CONFIRMED)
        b = advance(b["id"], DISPATCH)
        b = advance(b["id"], EN_ROUTE)
        b = add_quick_stop(b["id"], "works")
        import json as _j
        assert _j.loads(b["quick_stops"]) == ["works"]
