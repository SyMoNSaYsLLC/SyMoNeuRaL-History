"""DispatchOS HTTP surface.

An APIRouter, mounted with a prefix by whoever hosts it -- the same shape as
`accounts_routes.router`, `project.router` and the other apps in this repo.

In slice 1.5 the host is the local experimental control service, NOT production
api.py: mounting a new public surface is a separate, explicit gate. The benchmark
therefore exercises the real routes and the real data model; only the host
differs, and the report says so rather than implying production coverage.

Synthetic and real bookings share these routes on purpose -- a benchmark that
exercises a parallel code path measures the parallel code path. They are
distinguished by `synthetic` and `benchmark_run_id`, nothing else.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import (ACTIONS, BookingError, QUOTE_MANUAL, QUOTE_SYNTHETIC,
               BENCHMARK_SYNTHETIC_QUOTE_CENTS, NOT_IMPLEMENTED_EFFECTS,
               TRANSITIONS, VEHICLE_TYPES, add_quick_stop, advance,
               change_dropoff, clear_benchmark_run, create_booking, get_booking,
               list_bookings, mark_payment, reschedule, set_quote)

router = APIRouter()


class BookingCreate(BaseModel):
    """The lean first-version booking. Every field here is operationally required;
    nothing has been added for a dashboard that does not exist."""
    pickup: str = Field(..., max_length=500, examples=["Terminal 2, Pittsburgh Intl"])
    dropoff: str = Field(..., max_length=500, examples=["1200 Smallman St"])
    scheduled_utc: float = Field(..., description="epoch seconds")
    passengers: int = Field(..., ge=1, le=16)
    bags: int = Field(..., ge=0, le=32)
    vehicle_type: Literal["sedan", "suv", "van", "wheelchair_accessible"]
    instructions: str | None = Field(None, max_length=1000)
    # minimal contact -- only what the booking and its reminder need
    customer_name: str | None = Field(None, max_length=200)
    customer_phone: str | None = Field(None, max_length=40)
    # benchmark isolation
    synthetic: bool = False
    benchmark_run_id: str | None = None


class QuoteSet(BaseModel):
    """A quote is ENTERED, never computed. There is no pricing engine in this
    application because the pricing rules have not been defined."""
    amount_cents: int = Field(..., ge=0)
    currency: str = Field("USD", max_length=8)
    source: Literal["MANUAL", "BENCHMARK_SYNTHETIC_QUOTE"] = "MANUAL"


class Advance(BaseModel):
    to_status: str
    note: str | None = Field(None, max_length=500)


def _wrap(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except BookingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/meta")
def meta() -> dict:
    """What this application can and cannot do. Explicit about the effects that
    are state-only, so nothing here implies an SMS was sent."""
    return {
        "app": "dispatchos",
        "scope": "lean first version: booking record + state machine",
        "states": list(TRANSITIONS),
        "actions": list(ACTIONS),
        "transitions": {k: list(v) for k, v in TRANSITIONS.items()},
        "vehicle_types": list(VEHICLE_TYPES),
        "effects_not_implemented": NOT_IMPLEMENTED_EFFECTS,
        "pricing_engine": None,
        "pricing_note": ("No pricing rules are implemented. Quotes are entered "
                         "manually; quote_status stays PENDING until then."),
        "benchmark_synthetic_quote_cents": BENCHMARK_SYNTHETIC_QUOTE_CENTS,
        "benchmark_quote_note": "TEST DATA -- never a business quote; synthetic bookings only",
        "excluded_from_first_version": [
            "customer dashboard", "customer database/CRM", "revenue tracker",
            "repeat-rider memory", "spend/payment history", "call/text summaries",
            "marketing automation", "payment gateway", "vehicle tracking",
        ],
    }


@router.post("/bookings", status_code=201)
def create(body: BookingCreate) -> dict:
    return _wrap(create_booking, **body.model_dump())


@router.get("/bookings/{booking_id}")
def read(booking_id: str) -> dict:
    b = get_booking(booking_id)
    if b is None:
        raise HTTPException(status_code=404, detail="no such booking")
    return b


@router.post("/bookings/{booking_id}/quote")
def quote(booking_id: str, body: QuoteSet) -> dict:
    src = QUOTE_MANUAL if body.source == "MANUAL" else QUOTE_SYNTHETIC
    return _wrap(set_quote, booking_id, amount_cents=body.amount_cents,
                 currency=body.currency, source=src)


@router.post("/bookings/{booking_id}/advance")
def advance_state(booking_id: str, body: Advance) -> dict:
    return _wrap(advance, booking_id, body.to_status, body.note)



class QuickStop(BaseModel):
    stop: str = Field(..., max_length=500, examples=["Pharmacy on Penn Ave"])


class Dropoff(BaseModel):
    dropoff: str = Field(..., max_length=500)


class Reschedule(BaseModel):
    scheduled_utc: float


class Payment(BaseModel):
    """INTERNAL payment state only. No processor is called and no money moves."""
    state: Literal["NONE", "PENDING", "RECORDED", "MANUAL"] = "RECORDED"


@router.post("/bookings/{booking_id}/quick-stop")
def quick_stop(booking_id: str, body: QuickStop) -> dict:
    return _wrap(add_quick_stop, booking_id, body.stop)


@router.post("/bookings/{booking_id}/dropoff")
def dropoff(booking_id: str, body: Dropoff) -> dict:
    return _wrap(change_dropoff, booking_id, body.dropoff)


@router.post("/bookings/{booking_id}/reschedule")
def reschedule_ride(booking_id: str, body: Reschedule) -> dict:
    return _wrap(reschedule, booking_id, body.scheduled_utc)


@router.post("/bookings/{booking_id}/payment")
def payment(booking_id: str, body: Payment) -> dict:
    """Records an internal payment state. NO payment processor is contacted."""
    return _wrap(mark_payment, booking_id, body.state)


@router.get("/bookings")
def index(benchmark_run_id: str | None = None, synthetic: bool | None = None,
          limit: int = 100) -> dict:
    rows = list_bookings(benchmark_run_id=benchmark_run_id, synthetic=synthetic,
                         limit=min(limit, 500))
    return {"count": len(rows), "bookings": rows}


@router.delete("/benchmark/{run_id}")
def clear_run(run_id: str) -> dict:
    """Scoped to one benchmark run. Refuses anything that is not a run id, and the
    delete itself is additionally constrained to synthetic rows."""
    return _wrap(clear_benchmark_run, run_id)
