"""DispatchOS — the lean first-version booking/dispatch core.

Scope is deliberately narrow. This is a booking record and a state machine, and
nothing else. There is no customer dashboard, no customer database, no revenue
tracker, no repeat-rider memory, no spend history, no call/text summaries and no
marketing automation: those were explicitly excluded from the lean first version
and adding them "while we are here" is how a lean scope stops being one.

PRICING RULES DO NOT EXIST HERE, ON PURPOSE.
Donnie has not defined mileage/time/airport/wait/vehicle rules, so this module
cannot compute a quote and does not try. A booking sits at QUOTE_PENDING until a
human enters an amount. The only automatic amount in this file is the synthetic
benchmark fixture, which is fenced behind `synthetic=1` and stamped TEST DATA so
it can never be mistaken for a business quote.

External effects are not faked. REMINDER means "this booking reached the point
where a reminder would be sent"; it does not send SMS, because no SMS integration
exists. Same for REVIEW and email. DISPATCH is internal assignment state with no
vehicle tracking. There is no payment gateway.

Storage follows the accounts app: sqlite, schema applied on every connection so a
truncated file self-heals, WAL, one connection per operation rather than a
module-level singleton.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager

SCHEMA_VERSION = 1

# ------------------------------------------------------------------ state machine
REQUEST = "REQUEST"
QUOTE_PENDING = "QUOTE_PENDING"
QUOTED = "QUOTED"
CONFIRMED = "CONFIRMED"
SCHEDULED = "SCHEDULED"
DISPATCH = "DISPATCH"
EN_ROUTE = "EN_ROUTE"
ARRIVED = "ARRIVED"
WAITING = "WAITING"
IN_TRIP = "IN_TRIP"
PAYMENT_PENDING = "PAYMENT_PENDING"
REMINDER = "REMINDER"
COMPLETED = "COMPLETED"
REVIEW = "REVIEW"
CANCELLED = "CANCELLED"

# The only legal moves. A transition not on this map is refused rather than
# silently applied -- a booking that can jump from REQUEST to COMPLETED is not a
# state machine, it is a status field.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    REQUEST:         (QUOTE_PENDING, CANCELLED),
    QUOTE_PENDING:   (QUOTED, CANCELLED),
    QUOTED:          (CONFIRMED, CANCELLED),
    CONFIRMED:       (SCHEDULED, DISPATCH, CANCELLED),
    SCHEDULED:       (DISPATCH, CANCELLED),
    DISPATCH:        (EN_ROUTE, REMINDER, COMPLETED, CANCELLED),
    EN_ROUTE:        (ARRIVED, CANCELLED),
    ARRIVED:         (WAITING, IN_TRIP, CANCELLED),
    WAITING:         (IN_TRIP, CANCELLED),
    IN_TRIP:         (PAYMENT_PENDING, COMPLETED, CANCELLED),
    PAYMENT_PENDING: (COMPLETED, CANCELLED),
    REMINDER:        (COMPLETED, CANCELLED),
    COMPLETED:       (REVIEW,),
    REVIEW:          (),
    CANCELLED:       (),
}

# States whose real-world effect is NOT implemented. Recorded so the UI and the
# report can say so instead of implying an SMS went out.
NOT_IMPLEMENTED_EFFECTS = {
    DISPATCH: "internal assignment state only; no vehicle tracking",
    EN_ROUTE: "internal state only; no driver GPS, no maps/ETA integration",
    ARRIVED: "internal state only; no arrival notification is sent",
    WAITING: "internal state only; no wait-time billing (no pricing rules exist)",
    PAYMENT_PENDING: ("internal state only; NO payment processor is called and no "
                      "money moves -- there is no payment gateway in this application"),
    REMINDER: "state only; no SMS/email is sent -- no messaging integration exists",
    REVIEW: "state only; no external review request is sent",
}

# ---------------------------------------------------------------------- actions
# An ACTION is what a customer or dispatcher does; a STATE is where the ride is.
# Actions execute legitimate transitions or legitimate field mutations -- the
# benchmark never writes state directly to make itself pass.
ACTIONS = (
    "CREATE_REQUEST", "INSPECT_QUOTE", "CONFIRM_QUOTE", "SCHEDULE", "RESCHEDULE",
    "GO_EN_ROUTE", "INSPECT_STATE", "MARK_ARRIVED", "MARK_WAITING",
    "CONFIRM_PICKUP", "ADD_QUICK_STOP", "CHANGE_DROPOFF", "MARK_PAYMENT",
    "COMPLETE_RIDE", "MARK_REVIEW",
)

# Mutations that do NOT change state -- they change the ride in flight. Each is
# only legal in the states where it makes operational sense.
QUICK_STOP_STATES = (CONFIRMED, SCHEDULED, DISPATCH, EN_ROUTE, ARRIVED, WAITING, IN_TRIP)
CHANGE_DROPOFF_STATES = (CONFIRMED, SCHEDULED, DISPATCH, EN_ROUTE, ARRIVED, WAITING, IN_TRIP)
RESCHEDULE_STATES = (REQUEST, QUOTE_PENDING, QUOTED, CONFIRMED, SCHEDULED)

QUOTE_PENDING_STATUS = "PENDING"
QUOTE_MANUAL = "MANUAL"
QUOTE_SYNTHETIC = "BENCHMARK_SYNTHETIC_QUOTE"

# Fixed, obviously-not-real, and only reachable when synthetic=1. Its purpose is
# to let a load test walk the state machine, nothing else.
BENCHMARK_SYNTHETIC_QUOTE_CENTS = 12345      # TEST DATA -- never a business quote

VEHICLE_TYPES = ("sedan", "suv", "van", "wheelchair_accessible")

RUN_ID_RE = re.compile(r"^BENCH-\d{8}-\d{4}$")


class BookingError(ValueError):
    """Refused by the booking core. The message is safe to show a caller."""


def is_run_id(value) -> bool:
    return isinstance(value, str) and bool(RUN_ID_RE.fullmatch(value))


# ----------------------------------------------------------------------- storage
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    id               TEXT PRIMARY KEY,
    created          REAL NOT NULL,
    updated          REAL NOT NULL,
    status           TEXT NOT NULL,
    -- operational fields, the lean first version and no more
    pickup           TEXT NOT NULL,
    dropoff          TEXT NOT NULL,
    scheduled_utc    REAL NOT NULL,
    passengers       INTEGER NOT NULL,
    bags             INTEGER NOT NULL,
    vehicle_type     TEXT NOT NULL,
    instructions     TEXT,
    -- in-flight ride mutations. quick stops are a JSON list of plain strings;
    -- there is no route engine, no ETA and no distance calculation anywhere.
    quick_stops      TEXT,
    dropoff_changes  INTEGER NOT NULL DEFAULT 0,
    reschedules      INTEGER NOT NULL DEFAULT 0,
    payment_state    TEXT NOT NULL DEFAULT 'NONE',
    -- quote. amount is NULL until a human enters one; there is no pricing engine.
    quote_status     TEXT NOT NULL,
    quote_amount_cents INTEGER,
    quote_currency   TEXT,
    quote_source     TEXT,
    -- minimal contact, only what a booking and its reminder need
    customer_name    TEXT,
    customer_phone   TEXT,
    -- benchmark isolation. synthetic=0 rows are real bookings and are never
    -- reachable by benchmark cleanup.
    synthetic        INTEGER NOT NULL DEFAULT 0,
    benchmark_run_id TEXT
);
CREATE INDEX IF NOT EXISTS bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS bookings_bench  ON bookings(benchmark_run_id);
CREATE TABLE IF NOT EXISTS booking_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id  TEXT NOT NULL,
    at          REAL NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    note        TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS events_booking ON booking_events(booking_id);
"""

# Columns added after the first release, with the type/default each needs. The
# schema block above uses CREATE TABLE IF NOT EXISTS, which is a NO-OP on a table
# that already exists -- so adding a column there does nothing to a database
# created by an earlier version. That gap shipped once: Slice 2 added four ride
# columns, every unit test passed because tests use a fresh tmp_path database,
# and the first real request against the existing file returned HTTP 500 with
# "table bookings has no column named quick_stops". This is the migration that
# closes it, and `test_an_old_database_is_migrated_not_broken` proves it.
_ADDED_COLUMNS = (
    ("quick_stops", "TEXT"),
    ("dropoff_changes", "INTEGER NOT NULL DEFAULT 0"),
    ("reschedules", "INTEGER NOT NULL DEFAULT 0"),
    ("payment_state", "TEXT NOT NULL DEFAULT 'NONE'"),
)


def _migrate(c) -> list[str]:
    """Add any missing column. Idempotent, additive, and never drops anything.

    Returns the columns it added, so a caller (or a test) can see that a
    migration actually happened rather than trusting that it must have.
    """
    have = {r[1] for r in c.execute("PRAGMA table_info(bookings)")}
    added = []
    for name, decl in _ADDED_COLUMNS:
        if name not in have:
            c.execute(f"ALTER TABLE bookings ADD COLUMN {name} {decl}")
            added.append(name)
    return added

_DB_OVERRIDE: pathlib.Path | None = None


def db_path() -> pathlib.Path:
    """`run/dispatchos/dispatchos.db`, overridable for tests.

    Order: an explicit `using_db()` binding, then SYMONEURAL_DISPATCHOS_DB, then
    the default. The binding wins so a caller holding an explicit path is never
    redirected by a variable someone exported for another reason.
    """
    if _DB_OVERRIDE is not None:
        return _DB_OVERRIDE
    env = os.environ.get("SYMONEURAL_DISPATCHOS_DB", "").strip()
    if env:
        return pathlib.Path(env)
    root = pathlib.Path(__file__).resolve().parents[3]
    return root / "run" / "dispatchos" / "dispatchos.db"


@contextmanager
def using_db(path):
    global _DB_OVERRIDE
    prev, _DB_OVERRIDE = _DB_OVERRIDE, pathlib.Path(path)
    try:
        yield _DB_OVERRIDE
    finally:
        _DB_OVERRIDE = prev


@contextmanager
def _conn():
    """One connection per operation -- not a module singleton.

    uvicorn runs handlers on a thread pool once anything goes through
    asyncio.to_thread, and a shared sqlite3 connection across threads is either an
    error or a data race depending on check_same_thread.
    """
    path = db_path()
    first = not path.exists()
    if first:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    c = sqlite3.connect(str(path), timeout=10.0, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA busy_timeout=10000")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        if first:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        # On every connection, as accounts does: an empty-but-present file
        # self-heals instead of raising `no such table` three calls deep.
        c.executescript(_SCHEMA)
        _migrate(c)
        c.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema',?)",
                  (str(SCHEMA_VERSION),))
        yield c
    finally:
        c.close()


def init_db() -> pathlib.Path:
    with _conn():
        pass
    return db_path()


# ------------------------------------------------------------------- validation
def _need(v, name: str) -> str:
    s = (v or "").strip() if isinstance(v, (str, type(None))) else str(v)
    if not s:
        raise BookingError(f"{name} is required")
    if len(s) > 500:
        raise BookingError(f"{name} is too long")
    return s


def _count(v, name: str, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise BookingError(f"{name} must be a whole number") from None
    if not lo <= n <= hi:
        raise BookingError(f"{name} must be between {lo} and {hi}")
    return n


# ---------------------------------------------------------------------- create
def create_booking(*, pickup, dropoff, scheduled_utc, passengers, bags,
                   vehicle_type, instructions=None, customer_name=None,
                   customer_phone=None, synthetic=False, benchmark_run_id=None) -> dict:
    """Create a booking in REQUEST. No quote is computed -- there is no pricing engine."""
    if synthetic and not is_run_id(benchmark_run_id):
        raise BookingError("synthetic bookings require a valid benchmark_run_id")
    if benchmark_run_id is not None and not synthetic:
        raise BookingError("benchmark_run_id is only valid on synthetic bookings")
    if vehicle_type not in VEHICLE_TYPES:
        raise BookingError(f"vehicle_type must be one of {VEHICLE_TYPES}")
    try:
        sched = float(scheduled_utc)
    except (TypeError, ValueError):
        raise BookingError("scheduled_utc must be an epoch timestamp") from None

    now = time.time()
    row = {
        "id": ("bk_" + secrets.token_hex(8)) if not synthetic
              else f"bk_{benchmark_run_id}_{secrets.token_hex(4)}",
        "created": now, "updated": now, "status": REQUEST,
        "pickup": _need(pickup, "pickup"), "dropoff": _need(dropoff, "dropoff"),
        "scheduled_utc": sched,
        "passengers": _count(passengers, "passengers", 1, 16),
        "bags": _count(bags, "bags", 0, 32),
        "vehicle_type": vehicle_type,
        "instructions": (instructions or "").strip()[:1000] or None,
        "quick_stops": None, "dropoff_changes": 0, "reschedules": 0,
        "payment_state": "NONE",
        "quote_status": QUOTE_PENDING_STATUS,
        "quote_amount_cents": None, "quote_currency": None, "quote_source": None,
        "customer_name": (customer_name or "").strip()[:200] or None,
        "customer_phone": (customer_phone or "").strip()[:40] or None,
        "synthetic": 1 if synthetic else 0,
        "benchmark_run_id": benchmark_run_id if synthetic else None,
    }
    with _conn() as c:
        c.execute(
            "INSERT INTO bookings (id,created,updated,status,pickup,dropoff,"
            "scheduled_utc,passengers,bags,vehicle_type,instructions,quick_stops,"
            "dropoff_changes,reschedules,payment_state,quote_status,"
            "quote_amount_cents,quote_currency,quote_source,customer_name,"
            "customer_phone,synthetic,benchmark_run_id) VALUES "
            "(:id,:created,:updated,:status,:pickup,:dropoff,:scheduled_utc,"
            ":passengers,:bags,:vehicle_type,:instructions,:quick_stops,"
            ":dropoff_changes,:reschedules,:payment_state,:quote_status,"
            ":quote_amount_cents,:quote_currency,:quote_source,:customer_name,"
            ":customer_phone,:synthetic,:benchmark_run_id)", row)
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (row["id"], now, None, REQUEST, "created"))
    return get_booking(row["id"])


def get_booking(booking_id: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["events"] = [dict(e) for e in c.execute(
            "SELECT at,from_status,to_status,note FROM booking_events "
            "WHERE booking_id=? ORDER BY id", (booking_id,))]
    d["effect_not_implemented"] = NOT_IMPLEMENTED_EFFECTS.get(d["status"])
    return d


# ----------------------------------------------------------------------- quote
def set_quote(booking_id: str, *, amount_cents: int, currency="USD",
              source=QUOTE_MANUAL) -> dict:
    """Attach a manually-entered quote and move QUOTE_PENDING -> QUOTED.

    `source` records who decided the number. There is no formula in this file and
    there must not be one until Donnie defines the rules.
    """
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    if b["status"] != QUOTE_PENDING:
        raise BookingError(f"quote can only be set in {QUOTE_PENDING}, not {b['status']}")
    if source == QUOTE_SYNTHETIC and not b["synthetic"]:
        raise BookingError("synthetic quote refused on a real booking")
    if source not in (QUOTE_MANUAL, QUOTE_SYNTHETIC):
        raise BookingError("quote source must be manual or the benchmark fixture")
    try:
        cents = int(amount_cents)
    except (TypeError, ValueError):
        raise BookingError("amount_cents must be a whole number of cents") from None
    if cents < 0:
        raise BookingError("amount_cents cannot be negative")

    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET quote_status=?, quote_amount_cents=?, "
                  "quote_currency=?, quote_source=?, status=?, updated=? WHERE id=?",
                  (QUOTE_MANUAL if source == QUOTE_MANUAL else QUOTE_SYNTHETIC,
                   cents, currency, source, QUOTED, now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, QUOTE_PENDING, QUOTED,
                                         f"quote set by {source}"))
    return get_booking(booking_id)


# ------------------------------------------------------------------ transitions
def advance(booking_id: str, to_status: str, note: str | None = None) -> dict:
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    cur = b["status"]
    allowed = TRANSITIONS.get(cur, ())
    if to_status not in allowed:
        raise BookingError(
            f"illegal transition {cur} -> {to_status}; allowed from {cur}: "
            f"{allowed or '(terminal)'}")
    if to_status == CONFIRMED and b["quote_status"] == QUOTE_PENDING_STATUS:
        raise BookingError("cannot confirm a booking that has no quote")
    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET status=?, updated=? WHERE id=?",
                  (to_status, now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, cur, to_status, note))
    return get_booking(booking_id)


def list_bookings(*, benchmark_run_id=None, synthetic=None, limit=100) -> list[dict]:
    q = "SELECT * FROM bookings"
    where, args = [], []
    if benchmark_run_id is not None:
        where.append("benchmark_run_id=?"); args.append(benchmark_run_id)
    if synthetic is not None:
        where.append("synthetic=?"); args.append(1 if synthetic else 0)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created DESC LIMIT ?"
    args.append(int(limit))
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args)]



# ---------------------------------------------------------------- ride actions
# Every function here performs a legitimate application operation. None of them
# writes an arbitrary state to make a benchmark pass, and each refuses the states
# in which the operation would be meaningless.

def add_quick_stop(booking_id: str, stop: str) -> dict:
    """Add an intermediate stop to a ride already in flight.

    A plain string, appended to a JSON list. There is deliberately no routing,
    no distance, no ETA and no price effect -- adding a stop cannot change a
    quote, because no pricing rules exist.
    """
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    if b["status"] not in QUICK_STOP_STATES:
        raise BookingError(f"cannot add a quick stop in {b['status']}")
    text = _need(stop, "stop")
    stops = json.loads(b["quick_stops"] or "[]")
    if len(stops) >= 5:
        raise BookingError("too many quick stops")
    stops.append(text)
    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET quick_stops=?, updated=? WHERE id=?",
                  (json.dumps(stops), now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, b["status"], b["status"],
                                         f"ADD_QUICK_STOP: {text[:80]}"))
    return get_booking(booking_id)


def change_dropoff(booking_id: str, dropoff: str) -> dict:
    """Change the destination of a ride in flight. State is unchanged."""
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    if b["status"] not in CHANGE_DROPOFF_STATES:
        raise BookingError(f"cannot change dropoff in {b['status']}")
    new = _need(dropoff, "dropoff")
    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET dropoff=?, dropoff_changes=dropoff_changes+1, "
                  "updated=? WHERE id=?", (new, now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, b["status"], b["status"],
                                         f"CHANGE_DROPOFF: {new[:80]}"))
    return get_booking(booking_id)


def reschedule(booking_id: str, scheduled_utc: float) -> dict:
    """Move the pickup time. Only before the ride is under way."""
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    if b["status"] not in RESCHEDULE_STATES:
        raise BookingError(f"cannot reschedule in {b['status']}")
    try:
        sched = float(scheduled_utc)
    except (TypeError, ValueError):
        raise BookingError("scheduled_utc must be an epoch timestamp") from None
    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET scheduled_utc=?, reschedules=reschedules+1, "
                  "updated=? WHERE id=?", (sched, now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, b["status"], b["status"],
                                         "RESCHEDULE"))
    return get_booking(booking_id)


def mark_payment(booking_id: str, state: str = "RECORDED") -> dict:
    """Record an INTERNAL payment state.

    NO payment processor is called. No money moves. There is no payment gateway
    in this application, and this function exists so the lifecycle can reach a
    payment state during a load test -- not to represent a real transaction.
    """
    b = get_booking(booking_id)
    if b is None:
        raise BookingError("no such booking")
    if state not in ("NONE", "PENDING", "RECORDED", "MANUAL"):
        raise BookingError("unknown payment state")
    if b["status"] not in (IN_TRIP, PAYMENT_PENDING, COMPLETED):
        raise BookingError(f"cannot record payment in {b['status']}")
    now = time.time()
    with _conn() as c:
        c.execute("UPDATE bookings SET payment_state=?, updated=? WHERE id=?",
                  (state, now, booking_id))
        c.execute("INSERT INTO booking_events (booking_id,at,from_status,to_status,note) "
                  "VALUES (?,?,?,?,?)", (booking_id, now, b["status"], b["status"],
                                         f"MARK_PAYMENT: {state} (internal only, "
                                         f"no processor called)"))
    return get_booking(booking_id)


# -------------------------------------------------------------------- cleanup
def clear_benchmark_run(run_id: str) -> dict:
    """Delete the bookings of ONE benchmark run.

    Every guard here exists because the alternative is a generic delete:
      * the id must match BENCH-YYYYMMDD-NNNN exactly, so 'all', '*', '' and
        '../secrets' are refused before any SQL runs;
      * the DELETE is additionally constrained to synthetic=1, so even a run id
        that somehow reached a real row could not remove it.
    There is deliberately no clear-all.
    """
    if not is_run_id(run_id):
        raise BookingError(f"refusing: {run_id!r} is not a benchmark run id")
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM bookings WHERE benchmark_run_id=? "
                      "AND synthetic=1", (run_id,)).fetchone()[0]
        c.execute("DELETE FROM booking_events WHERE booking_id IN "
                  "(SELECT id FROM bookings WHERE benchmark_run_id=? AND synthetic=1)",
                  (run_id,))
        c.execute("DELETE FROM bookings WHERE benchmark_run_id=? AND synthetic=1",
                  (run_id,))
    return {"run_id": run_id, "bookings_removed": n,
            "scope": f"synthetic=1 AND benchmark_run_id == {run_id}"}
