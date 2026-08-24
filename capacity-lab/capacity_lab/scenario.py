"""APPLICATION scenarios: what one synthetic concurrent user actually does.

A concurrent user is a simultaneous synthetic application SESSION -- a sequence
of real HTTP steps against real endpoints -- not a single request.

BOOKING IS NOT IMPLEMENTED HERE, AND THAT IS NOT AN OVERSIGHT.
The repo audit (2026-08-24, main @ 7d1a5529) found no booking application:
zero routes matching book/appoint/dispatch/slot/schedul across all 32 route
decorators and every app, no booking tables, and site/share-dispatchos.html
carries 0 fetch calls, 0 forms and 0 /api references because it was built as a
deliberately backend-free preview. Inventing a booking endpoint in order to
benchmark it would produce numbers describing code written only to be measured.

So `BookingScenario` exists, declares its steps, and refuses to run -- reporting
NOT AVAILABLE with the reason. When the booking application is built, it becomes
runnable without touching the harness, the samplers or the report schema.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .core import NOT_AVAILABLE
from .players import Player, PlayerResult


@dataclass
class StepResult:
    name: str
    ok: bool
    latency_s: float
    http_status: int | None = None
    error: str | None = None
    detail: dict | None = None


@dataclass
class SessionResult:
    session_id: str
    run_id: str
    ok: bool
    started_mono: float
    ended_mono: float
    steps: list[StepResult] = field(default_factory=list)
    ai: PlayerResult | None = None
    error: str | None = None

    @property
    def duration_s(self) -> float:
        return self.ended_mono - self.started_mono


def _post(base: str, path: str, payload: dict, timeout: float,
          api_key: str | None = None) -> tuple[bool, float, int | None, dict | None, str | None]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{base.rstrip('/')}{path}", data=body, method="POST",
                                 headers={"content-type": "application/json"})
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                doc = json.loads(raw)
            except Exception:
                doc = None
            return True, time.monotonic() - t0, r.status, doc, None
    except urllib.error.HTTPError as e:
        return False, time.monotonic() - t0, e.code, None, f"HTTP {e.code}"
    except Exception as e:                            # noqa: BLE001
        return False, time.monotonic() - t0, None, None, f"{type(e).__name__}: {e}"


def _get(base: str, path: str, timeout: float) -> tuple[bool, float, int | None, str | None]:
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}{path}", timeout=timeout) as r:
            r.read()
            return True, time.monotonic() - t0, r.status, None
    except urllib.error.HTTPError as e:
        return False, time.monotonic() - t0, e.code, f"HTTP {e.code}"
    except Exception as e:                            # noqa: BLE001
        return False, time.monotonic() - t0, None, f"{type(e).__name__}: {e}"


class Scenario:
    name = "abstract"
    runnable = False
    unavailable_reason: str | None = None

    def run(self, *, session_id, run_id, base_url, player, timeout, api_key=None) -> SessionResult:
        raise NotImplementedError


class TransactionScenario(Scenario):
    """A real application session against endpoints that exist today.

    Steps mirror the shape of a booking session -- open, read state, perform a
    deterministic server-side transaction, optionally consult SyMon AI, confirm --
    using the real surfaces this server actually has. The transaction step is
    /api/ravencalc, documented in api.py as "Exact symbolic mathematics. No GPU,
    no lock, no queue": genuinely deterministic, genuinely server-side, and
    genuinely unaffected by whether the AI is on. That is what makes it a valid
    control for the AI ON/OFF differential.

    This is explicitly NOT a booking flow and is never reported as one.
    """
    name = "transaction"
    runnable = True

    def run(self, *, session_id, run_id, base_url, player: Player, timeout,
            api_key=None) -> SessionResult:
        t0 = time.monotonic()
        steps: list[StepResult] = []
        ai_res: PlayerResult | None = None
        ok = True

        # 1. SESSION START -- read server state, as a client opening the surface would
        good, lat, status, err = _get(base_url, "/api/status", timeout)
        steps.append(StepResult("session_start", good, lat, status, err))
        ok &= good

        # 2. AI step (or deliberate server-side bypass)
        if ok:
            ai_res = player.invoke(
                f"[{run_id}/{session_id}] In one short sentence, confirm you are ready.",
                timeout)
            steps.append(StepResult("ai_assist", ai_res.ok, ai_res.latency_s,
                                    ai_res.http_status, ai_res.error,
                                    {"bypassed": ai_res.bypassed}))
            ok &= ai_res.ok

        # 3. DETERMINISTIC TRANSACTION -- must succeed regardless of AI mode, and
        #    the AI is never the source of truth for it.
        if ok:
            good, lat, status, doc, err = _post(
                base_url, "/api/ravencalc",
                {"expression": "x**2*sin(x)", "operation": "differentiate", "variable": "x"},
                timeout, api_key)
            detail = None
            if isinstance(doc, dict):
                detail = {"has_result": "result" in doc or "value" in doc,
                          "keys": sorted(doc.keys())[:6]}
            steps.append(StepResult("transaction", good, lat, status, err, detail))
            ok &= good

        # 4. CONFIRMATION -- re-read state, closing the session
        if ok:
            good, lat, status, err = _get(base_url, "/api/status", timeout)
            steps.append(StepResult("confirm", good, lat, status, err))
            ok &= good

        return SessionResult(session_id=session_id, run_id=run_id, ok=ok,
                             started_mono=t0, ended_mono=time.monotonic(),
                             steps=steps, ai=ai_res,
                             error=None if ok else next(
                                 (s.error for s in steps if s.error), "step failed"))


class BookingScenario(Scenario):
    """The real DispatchOS booking flow -- the scenario Donnie's question is about.

    One synthetic concurrent user walks the actual state machine over the actual
    routes and the actual data model. The ONLY difference from a real booking is
    `synthetic=true` and `benchmark_run_id`; there is no parallel benchmark code
    path, because a benchmark that exercises a parallel path measures the
    parallel path.

    Nothing external is sent. REMINDER and REVIEW are internal states whose
    real-world effects are not implemented, and the booking core says so in its
    own /meta rather than letting a passing test imply an SMS went out.

    The quote is the benchmark fixture: a fixed, obviously-fake value the core
    accepts only on synthetic rows. It exists to let the state machine reach
    CONFIRMED during load, and it is never business pricing.
    """
    name = "booking"
    runnable = True

    def run(self, *, session_id, run_id, base_url, player: Player, timeout,
            api_key=None) -> SessionResult:
        t0 = time.monotonic()
        steps: list[StepResult] = []
        ai_res: PlayerResult | None = None
        ok = True
        bid = None

        # 1. SESSION START -- what the application can do, read from the app itself
        good, lat, status, err = _get(base_url, "/api/dispatchos/meta", timeout)
        steps.append(StepResult("session_start", good, lat, status, err))
        ok &= good

        # 2. CREATE BOOKING REQUEST -- every lean first-version field
        if ok:
            payload = {
                "pickup": "Terminal 2, Pittsburgh Intl",
                "dropoff": "1200 Smallman St, Pittsburgh",
                "scheduled_utc": time.time() + 86400,
                "passengers": 2, "bags": 3, "vehicle_type": "suv",
                "instructions": f"benchmark session {session_id}; car seat required",
                "customer_name": f"Synthetic Rider {session_id[-4:]}",
                "customer_phone": "+1-555-0100",
                "synthetic": True, "benchmark_run_id": run_id,
            }
            good, lat, status, doc, err = _post(base_url, "/api/dispatchos/bookings",
                                                payload, timeout, api_key)
            if good and isinstance(doc, dict):
                bid = doc.get("id")
            steps.append(StepResult("create_booking_request", good, lat, status, err,
                                    {"booking_id": bid, "status": (doc or {}).get("status")}))
            ok &= good and bool(bid)

        # 3. AI assistance (or deliberate server-side bypass)
        if ok:
            ai_res = player.invoke(
                "A rider needs an airport pickup for 2 passengers with 3 bags. "
                "In one short sentence, suggest what to confirm with them.", timeout)
            steps.append(StepResult("ai_assist", ai_res.ok, ai_res.latency_s,
                                    ai_res.http_status, ai_res.error,
                                    {"bypassed": ai_res.bypassed,
                                     "queue_wait_s": getattr(ai_res, "queue_wait_s", None)}))
            ok &= ai_res.ok

        # 4. QUOTE_PENDING -> QUOTED via the benchmark fixture (TEST DATA)
        if ok:
            good, lat, status, doc, err = _post(
                base_url, f"/api/dispatchos/bookings/{bid}/advance",
                {"to_status": "QUOTE_PENDING", "note": "benchmark"}, timeout, api_key)
            steps.append(StepResult("await_quote", good, lat, status, err))
            ok &= good
        if ok:
            good, lat, status, doc, err = _post(
                base_url, f"/api/dispatchos/bookings/{bid}/quote",
                {"amount_cents": 12345, "currency": "USD",
                 "source": "BENCHMARK_SYNTHETIC_QUOTE"}, timeout, api_key)
            steps.append(StepResult("synthetic_quote", good, lat, status, err,
                                    {"TEST_DATA": True,
                                     "quote_status": (doc or {}).get("quote_status")}))
            ok &= good

        # 5. CONFIRM, then advance far enough to validate the workflow
        for step_name, target in (("confirm_booking", "CONFIRMED"),
                                  ("dispatch", "DISPATCH"),
                                  ("reminder", "REMINDER"),
                                  ("complete", "COMPLETED")):
            if not ok:
                break
            good, lat, status, doc, err = _post(
                base_url, f"/api/dispatchos/bookings/{bid}/advance",
                {"to_status": target, "note": f"benchmark {session_id}"}, timeout, api_key)
            detail = {"status": (doc or {}).get("status")}
            if isinstance(doc, dict) and doc.get("effect_not_implemented"):
                detail["effect_not_implemented"] = doc["effect_not_implemented"]
            steps.append(StepResult(step_name, good, lat, status, err, detail))
            ok &= good

        # 6. READ CONFIRMATION
        if ok:
            good, lat, status, err = _get(base_url,
                                          f"/api/dispatchos/bookings/{bid}", timeout)
            steps.append(StepResult("read_confirmation", good, lat, status, err))
            ok &= good

        return SessionResult(session_id=session_id, run_id=run_id, ok=ok,
                             started_mono=t0, ended_mono=time.monotonic(),
                             steps=steps, ai=ai_res,
                             error=None if ok else next(
                                 (s.error for s in steps if s.error), "step failed"))


# Presentation names. The control transaction is kept as an engineering control
# for isolating server/framework overhead from DispatchOS booking overhead -- but
# Donnie's capacity numbers come from BOOKING, never from RavenCalc.
DISPLAY_NAMES = {
    "transaction": "CONTROL TRANSACTION",
    "booking": "BOOKING",
}

SCENARIOS = {
    "transaction": TransactionScenario,   # CONTROL TRANSACTION (engineering only)
    "booking": BookingScenario,           # BOOKING -- the customer-facing number
}


class LifecycleScenario(Scenario):
    """MIXED RIDE-LIFECYCLE workload -- the Slice 2 calibration scenario.

    One synthetic concurrent user = one active customer session somewhere in the
    ride lifecycle. The profile is assigned per wave and rotates, so across waves
    every selected slot exercises every operation class.

    Setup transitions and the measured operation are timed separately: driving a
    ride to IN_TRIP costs seven calls, and folding that into the latency of
    MARK_PAYMENT would report the setup, not the operation.
    """
    name = "lifecycle"
    runnable = True

    def __init__(self, profile=None, wave=0, ai_prompt=None):
        self.profile = profile
        self.wave = wave
        self.ai_prompt = ai_prompt

    def run(self, *, session_id, run_id, base_url, player: Player, timeout,
            api_key=None) -> SessionResult:
        from . import lifecycle
        t0 = time.monotonic()
        steps: list[StepResult] = []
        ai_res: PlayerResult | None = None
        ok = True
        prof = self.profile or lifecycle.PROFILES[0]

        # ---- create the ride (synthetic, tagged to this run) -----------------
        payload = {
            "pickup": "Terminal 2, Pittsburgh Intl",
            "dropoff": "1200 Smallman St, Pittsburgh",
            "scheduled_utc": time.time() + 86400,
            "passengers": 2, "bags": 3, "vehicle_type": "suv",
            "instructions": f"{prof} wave{self.wave} {session_id}",
            "customer_name": f"Synthetic Rider {session_id[-4:]}",
            "customer_phone": "+1-555-0100",
            "synthetic": True, "benchmark_run_id": run_id,
        }
        good, lat, status, doc, err = _post(base_url, "/api/dispatchos/bookings",
                                            payload, timeout, api_key)
        bid = (doc or {}).get("id") if good else None
        steps.append(StepResult("create_request", good, lat, status, err,
                                {"booking_id": bid, "profile": prof}))
        ok &= good and bool(bid)

        # ---- setup: reach the state this operation needs ---------------------
        setup_s = 0.0
        if ok:
            for target in lifecycle.SETUP[prof]:
                if target == "_QUOTE":
                    g, l, st, _d, e = _post(
                        base_url, f"/api/dispatchos/bookings/{bid}/quote",
                        {"amount_cents": 12345, "currency": "USD",
                         "source": "BENCHMARK_SYNTHETIC_QUOTE"}, timeout, api_key)
                else:
                    g, l, st, _d, e = _post(
                        base_url, f"/api/dispatchos/bookings/{bid}/advance",
                        {"to_status": target, "note": "setup"}, timeout, api_key)
                setup_s += l
                if not g:
                    steps.append(StepResult(f"setup:{target}", False, l, st, e))
                    ok = False
                    break
            if ok:
                steps.append(StepResult("setup", True, setup_s, 200, None,
                                        {"transitions": list(lifecycle.SETUP[prof])}))

        # ---- AI assistance (or deliberate server-side bypass) ----------------
        if ok:
            prompt = self.ai_prompt or lifecycle.AI_PROMPTS[prof]
            ai_res = player.invoke(prompt, timeout)
            steps.append(StepResult("ai_assist", ai_res.ok, ai_res.latency_s,
                                    ai_res.http_status, ai_res.error,
                                    {"bypassed": ai_res.bypassed, "profile": prof,
                                     "queue_wait_s": getattr(ai_res, "queue_wait_s", None),
                                     "service_s": getattr(ai_res, "service_s", None)}))
            ok &= ai_res.ok

        # ---- THE MEASURED OPERATION -----------------------------------------
        action = None
        if ok:
            action, aok, alat, ast, aerr = lifecycle.operation(
                prof, bid, base_url,
                lambda b, p, d, t, k=None: _post(b, p, d, t, api_key),
                _get, timeout, self.wave)
            steps.append(StepResult(f"operation:{action}", aok, alat, ast, aerr,
                                    {"profile": prof, "measured_operation": True}))
            ok &= aok

        return SessionResult(session_id=session_id, run_id=run_id, ok=ok,
                             started_mono=t0, ended_mono=time.monotonic(),
                             steps=steps, ai=ai_res,
                             error=None if ok else next(
                                 (s.error for s in steps if s.error), "step failed"))


DISPLAY_NAMES["lifecycle"] = "MIXED RIDE LIFECYCLE"
SCENARIOS["lifecycle"] = LifecycleScenario
