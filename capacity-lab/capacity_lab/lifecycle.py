"""Mixed ride-lifecycle workload.

At any instant a real dispatch business has customers doing different things: one
requesting, one confirming a quote, one changing a dropoff mid-ride, one paying.
Firing N identical requests would measure one code path N times and call it
capacity, so each synthetic concurrent user is assigned a different lifecycle
PROFILE, and the assignment ROTATES between waves.

Rotation matters for two reasons. Binding "button 7 = quick stop" permanently
would mean slot 7's operation is only ever measured at concurrencies >= 7. And at
low concurrency, always taking the first N profiles would leave the rest of the
lifecycle unmeasured entirely. Rotating by wave index fixes both, deterministically
-- the same wave number always produces the same assignment, so a run is
reproducible.

Every profile drives the ride to the state its operation needs using legitimate
application calls, then performs that operation and reports its latency
separately. Nothing writes state directly to make a benchmark pass.
"""

from __future__ import annotations

import time

# Each profile: the operation class it measures, and the state it must reach
# first. `setup` transitions are legitimate application calls, timed separately
# from the operation under measurement so setup cost never inflates the number.
PROFILES = (
    "REQUESTED",        # create a ride request
    "QUOTE_CONFIRM",    # inspect quote, confirm it
    "SCHEDULING",       # schedule / reschedule
    "EN_ROUTE_STATUS",  # driver en route, inspect state
    "ARRIVED_WAITING",  # arrived, waiting
    "CONFIRM_PICKUP",   # pickup confirmed, into active trip
    "QUICK_STOP",       # add an intermediate stop mid-ride
    "CHANGE_DROPOFF",   # change destination mid-ride
    "PAYMENT",          # internal payment state
    "COMPLETION_REVIEW",# complete the ride, mark review
)

# Representative customer utterances, per profile. Used only when AI is enabled;
# SyMon may interpret or assist, but DispatchOS remains authoritative for every
# transactional fact.
AI_PROMPTS = {
    "REQUESTED":         "I need a ride from the airport with 2 bags. What should I confirm?",
    "QUOTE_CONFIRM":     "Is my quote still valid if I leave a little later?",
    "SCHEDULING":        "Can I move my pickup to 3:30?",
    "EN_ROUTE_STATUS":   "What is the current status of my ride?",
    "ARRIVED_WAITING":   "The driver is here. How long will they wait?",
    "CONFIRM_PICKUP":    "We are in the car now. Anything I should confirm?",
    "QUICK_STOP":        "Add a quick stop.",
    "CHANGE_DROPOFF":    "I need to change my destination.",
    "PAYMENT":           "How do I settle up at the end of the ride?",
    "COMPLETION_REVIEW": "The ride is finished. What happens next?",
}


def assign(slots: list[int], wave: int) -> dict[int, str]:
    """Deterministic rotating assignment of profiles to selected slots.

    Slot -> profile, rotated by wave so that across enough waves every selected
    slot exercises every profile. Deterministic in (slots, wave), so a run can be
    reproduced exactly.
    """
    ordered = sorted(slots)
    return {slot: PROFILES[(i + wave) % len(PROFILES)]
            for i, slot in enumerate(ordered)}


def coverage(slots: list[int], waves: int) -> dict[str, int]:
    """How many times each profile will be exercised. Reported so an uneven mix
    is visible rather than assumed away."""
    counts = {p: 0 for p in PROFILES}
    for w in range(waves):
        for prof in assign(slots, w).values():
            counts[prof] += 1
    return counts


# ---------------------------------------------------------------------- steps
# (state to reach before the measured operation, list of advance() targets)
SETUP: dict[str, tuple[str, ...]] = {
    "REQUESTED":         (),
    "QUOTE_CONFIRM":     ("QUOTE_PENDING",),
    "SCHEDULING":        ("QUOTE_PENDING", "_QUOTE", "CONFIRMED"),
    "EN_ROUTE_STATUS":   ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH"),
    "ARRIVED_WAITING":   ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH", "EN_ROUTE"),
    "CONFIRM_PICKUP":    ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH", "EN_ROUTE",
                          "ARRIVED"),
    "QUICK_STOP":        ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH", "EN_ROUTE"),
    "CHANGE_DROPOFF":    ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH"),
    "PAYMENT":           ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH", "EN_ROUTE",
                          "ARRIVED", "IN_TRIP"),
    "COMPLETION_REVIEW": ("QUOTE_PENDING", "_QUOTE", "CONFIRMED", "DISPATCH", "EN_ROUTE",
                          "ARRIVED", "IN_TRIP", "PAYMENT_PENDING"),
}


def operation(profile: str, booking_id: str, base: str, post, get, timeout,
              wave: int) -> tuple[str, bool, float, int | None, str | None]:
    """Execute the measured operation for a profile.

    Returns (action_name, ok, latency_s, http_status, error). Only this call is
    timed as the operation; setup transitions are timed separately.
    """
    B = f"/api/dispatchos/bookings/{booking_id}"
    if profile == "REQUESTED":
        # the create already happened; the measured operation is reading it back
        ok, lat, st, err = get(base, B, timeout)
        return "INSPECT_STATE", ok, lat, st, err
    if profile == "QUOTE_CONFIRM":
        ok, lat, st, _d, err = post(base, f"{B}/quote",
                                    {"amount_cents": 12345, "currency": "USD",
                                     "source": "BENCHMARK_SYNTHETIC_QUOTE"}, timeout)
        return "CONFIRM_QUOTE", ok, lat, st, err
    if profile == "SCHEDULING":
        ok, lat, st, _d, err = post(base, f"{B}/reschedule",
                                    {"scheduled_utc": time.time() + 7200}, timeout)
        return "RESCHEDULE", ok, lat, st, err
    if profile == "EN_ROUTE_STATUS":
        ok, lat, st, _d, err = post(base, f"{B}/advance",
                                    {"to_status": "EN_ROUTE", "note": f"wave {wave}"},
                                    timeout)
        return "GO_EN_ROUTE", ok, lat, st, err
    if profile == "ARRIVED_WAITING":
        ok, lat, st, _d, err = post(base, f"{B}/advance",
                                    {"to_status": "ARRIVED", "note": f"wave {wave}"},
                                    timeout)
        return "MARK_ARRIVED", ok, lat, st, err
    if profile == "CONFIRM_PICKUP":
        ok, lat, st, _d, err = post(base, f"{B}/advance",
                                    {"to_status": "IN_TRIP", "note": "pickup confirmed"},
                                    timeout)
        return "CONFIRM_PICKUP", ok, lat, st, err
    if profile == "QUICK_STOP":
        ok, lat, st, _d, err = post(base, f"{B}/quick-stop",
                                    {"stop": f"Pharmacy on Penn Ave (wave {wave})"},
                                    timeout)
        return "ADD_QUICK_STOP", ok, lat, st, err
    if profile == "CHANGE_DROPOFF":
        ok, lat, st, _d, err = post(base, f"{B}/dropoff",
                                    {"dropoff": f"5000 Forbes Ave (wave {wave})"}, timeout)
        return "CHANGE_DROPOFF", ok, lat, st, err
    if profile == "PAYMENT":
        # internal state only -- no processor is contacted, no money moves
        ok, lat, st, _d, err = post(base, f"{B}/payment", {"state": "RECORDED"}, timeout)
        return "MARK_PAYMENT", ok, lat, st, err
    if profile == "COMPLETION_REVIEW":
        ok, lat, st, _d, err = post(base, f"{B}/advance",
                                    {"to_status": "COMPLETED", "note": "ride complete"},
                                    timeout)
        return "COMPLETE_RIDE", ok, lat, st, err
    raise ValueError(f"unknown profile {profile!r}")
