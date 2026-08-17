#!/usr/bin/env python3
"""SyMoNeuRaL production API -- FastAPI over one consumer GPU.

Four surfaces, and they are not alike:

    POST /api/chat    GPU. Proxied to llama-server, streamed token by token.
    POST /api/image   GPU. Evicts chat, runs stable-diffusion.cpp, returns a PNG url.
    POST /api/calc    CPU. RavenCalc/SymPy. Exact, and never queues behind anything.
    POST /api/remix   GPU indirectly -- a client of the chat surface, not its own tenant.
    GET  /api/status  Per-unit state for the rack display on the home page.

Binds loopback only; Caddy reverse-proxies to it. Nothing here opens a port to the GPU
and nothing here trusts the client.

**Every bound is enforced on this side.** The browser sends suggestions -- steps, size,
temperature, token count -- and pydantic clamps each one before it reaches an engine. A
field arriving out of range is clamped rather than rejected, because arguing with a caller
about a slider is not worth an error path. The exception is an oversized prompt, which
hard-fails: truncating someone's input and answering the truncation is worse than refusing.

**One GPU job at a time, globally.** Not per-IP, not per-surface. The card genuinely
cannot do two things, so the queue is a property of the hardware rather than a policy.

Runs on the system interpreter -- fastapi, uvicorn and sympy are already present as OS
packages, so there is no virtualenv anywhere in the serving path.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import re
import secrets
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import (Depends, FastAPI, HTTPException, Request, Response, WebSocket,
                     WebSocketDisconnect, status as http)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

HERE = pathlib.Path(__file__).resolve().parent
# backend/ sits one level below the repo root. models/, site/, run/, scripts/ and
# contrib/ all hang off the root, not off here. This calculation has been wrong four
# times in this repo and it fails silently, because the wrong parent usually exists.
ROOT = HERE.parent
assert (ROOT / "scripts" / "gpu-governor.sh").is_file(), f"repo root not found at {ROOT}"
# ROOT, emphatically not HERE. gpu-governor.sh takes its mkdir lock in <root>/run,
# so pointing this at backend/run would give the API and the governor two different
# lock directories -- both would acquire, both would load weights, and ~12 GB of
# models would hit a 16 GB card. It is the failure this repo documents most loudly
# and it was one character away from happening during the backend/ move.
RUN = ROOT / "run"
RUN.mkdir(exist_ok=True)
# RavenCalc is an app, not a helper module: 648 self-contained lines whose only
# dependency is sympy. It lives in backend/apps/calc/ alongside the other surfaces
# rather than loose in backend/, which is where it sat purely because it was written
# before there was an apps/ directory to put it in.
sys.path.insert(0, str(HERE / "apps" / "ravencalc"))

GOVERNOR = ROOT / "scripts" / "gpu-governor.sh"
LLAMA_SERVER = ROOT / "contrib" / "llama.cpp" / "build" / "bin" / "llama-server"
SD_CLI = ROOT / "contrib" / "stable-diffusion.cpp" / "build" / "bin" / "sd-cli"
MODELS = HERE / "models"  # weights are a backend concern; backend/models/
SITE = ROOT / "site"          # the website: static files Caddy serves and deploy.sh publishes
# Renders are API output, not site content. They used to be written into site/, which meant
# deploy.sh copied every one of them into the public webroot -- 19 dead PNGs were sitting
# there -- even though nothing links to them: they are served by GET /api/gen/<name>.
RENDERS = HERE / "output"
RENDERS.mkdir(exist_ok=True)

CHAT_MODEL = MODELS / "llm" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
CHAT_ADAPTER = ROOT / "training" / "adapter" / "symoneural-lora.gguf"
# Draft model for speculative decoding. Measured on this box: shallow drafting wins and
# deep drafting loses badly -- see SPEC_DRAFT_MAX.
DRAFT_MODEL = MODELS / "llm" / "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"
# Two, not the default. Speculative decoding trades compute for bandwidth, and this box has
# spare compute but no spare bandwidth -- the draft model reads its own weights through the
# same 752 GB/s everything else is queuing for. Measured here at 150 tokens, temp 0.2:
#   depth 2 -> 157.4 t/s (43.8% accepted)   +5% over baseline
#   depth 3 -> 155.1 t/s (39.0% accepted)
#   depth 5 -> 121.4 t/s (27.1% accepted)   -19%
#   default -> 139.1 t/s (32.9% accepted)   -7%
# The default configuration is a net loss on this hardware. Depth 2 is a modest real win.
SPEC_DRAFT_MAX = 2
FLUX = {
    "unet": MODELS / "image" / "flux1-schnell-q4_k.gguf",
    "vae": MODELS / "image" / "ae.safetensors",
    "clip": MODELS / "image" / "clip_l.safetensors",
    "t5": MODELS / "image" / "t5xxl-Q8_0.gguf",
}

PORT = int(os.getenv("SYMONEURAL_PORT", "8800"))
LLAMA_PORT = 8081

MAX_PROMPT_CHARS = 4000
QUEUE_DEPTH = 24
JOB_TIMEOUT_S = 180

# Per-endpoint limits, because the endpoints do not cost remotely the same thing.
#
# A single global number had to be set for the most expensive case, which throttled the
# cheap ones for no reason: RavenCalc is ~0.1 s of CPU and never touches the card, so
# limiting it like a 9-second image render was pure lost utility.
#
# These are deliberately not unlimited. On one GPU an unlimited per-IP rate does not give
# anyone more throughput -- the queue is one-job-deep and rations the card by itself. All it
# would do is let one client fill the queue and lock everyone else out. The limiter exists
# to prevent monopolisation, not to ration hardware.
#
#                    per-minute, per-hour
LIMITS = {
    "calc":  (240, 6000),   # CPU only, never queues, ~0.1 s -- effectively "go ahead"
    "chat":  (120, 2000),   # ~1-3 s of GPU, and the queue is the real backstop
    "remix": (40,  600),    # a longer generation, one per few seconds is already plenty
    "image": (20,  300),    # ~9 s of exclusive GPU each; 20/min from one IP is already
                            # 3x more card-time than a minute contains
}
RATE_PER_MIN, RATE_PER_HOUR = LIMITS["chat"]
# Mirrors ACQUIRE_TIMEOUT_S in gpu-governor.sh. A serving request waits this long
# behind a CLI job or a fine-tune before telling the visitor to try RavenCalc.
ACQUIRE_TIMEOUT_S = 300

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s",
    handlers=[logging.FileHandler(RUN / "api.log"), logging.StreamHandler()],
)
log = logging.getLogger("symoneural.api")

DENY = re.compile(
    r"\b(nude|nudity|naked|nsfw|porn|pornographic|explicit|erotic|sexual|sex|"
    r"underage|child|minor|loli|cp|gore|beheading|execution|corpse|mutilat|"
    r"swastika|nazi|isis|terrorist)\w*", re.I)


# ======================================================================== models

class ChatRequest(BaseModel):
    """A question for the local model."""
    prompt: str = Field(..., max_length=MAX_PROMPT_CHARS,
                        description="What to ask. Longer than the cap is refused, not truncated.",
                        examples=["Why is decode memory-bandwidth bound on this card?"])
    temperature: float = Field(0.7, ge=0.0, le=1.5,
                               description="Low keeps it factual; high makes it wander.")
    max_tokens: int = Field(512, ge=16, le=2048,
                            description="Upper bound on the reply length.")


class ImageRequest(BaseModel):
    """A prompt for FLUX.1-schnell."""
    prompt: str = Field(..., max_length=MAX_PROMPT_CHARS,
                        examples=["a raven perched on a server rack, volumetric light"])
    steps: int = Field(4, ge=4, le=8,
                       description="schnell is distilled for four. More costs time and buys little.")
    size: Literal[512, 768] = Field(768, description="Square edge length in pixels.")
    seed: int | None = Field(None, ge=0, le=2**31 - 1,
                             description="Omit for random. Supply to reproduce an earlier image.")


class ImageResult(BaseModel):
    url: str = Field(..., description="Path to the rendered PNG, served from this site.")
    seconds: float = Field(..., description="Wall-clock the card actually took, queue excluded.")
    seed: int
    steps: int
    size: int
    model: str
    bytes: int


class CalcRequest(BaseModel):
    """A symbolic computation. Exact in, exact out -- no floats that lost the argument."""
    expression: str = Field(..., max_length=1000, examples=["x**2*sin(x)"])
    operation: Literal["differentiate", "integrate", "limit", "series",
                       "solve", "simplify", "evaluate"] = "simplify"
    variable: str | None = Field("x", max_length=64)
    point: str | None = Field(None, max_length=64,
                              description="Only meaningful for `limit`.")


class RemixRequest(BaseModel):
    """A brief for a sequenced tracklist."""
    prompt: str = Field(..., max_length=MAX_PROMPT_CHARS,
                        examples=["late-night drive through a rainy city, building slowly"])
    count: int = Field(12, ge=5, le=20)


class Track(BaseModel):
    artist: str = ""
    title: str = ""
    why: str = ""


class RemixResult(BaseModel):
    tracks: list[Track]
    seconds: float
    note: str


class Unit(BaseModel):
    id: str
    label: str
    slot: str
    state: Literal["ready", "busy", "queued", "offline"]
    bus: Literal["gpu", "cpu"]
    href: str
    spec: str
    detail: str


class GpuState(BaseModel):
    name: str
    vram_free_mib: int | None = None
    vram_total_mib: int | None = None
    vram_used_pct: int | None = None
    power_w: float | None = None
    temp_c: int | None = None
    holder: str | None = None
    queued: int = 0


class Status(BaseModel):
    """What the rack on the home page renders. Every field is read from the machine."""
    units: list[Unit]
    gpu: GpuState
    link: dict


# ======================================================================== plumbing

class RateLimiter:
    """Token bucket per client key.

    The bucket logic is the RavenCalc service's, already in this repo and already correct;
    the only change is that the window is a parameter. The original hardcoded 60 seconds,
    and two buckets are needed here -- a burst limit and an hourly one. Reusing it with the
    minute window for both would make the hourly cap refill sixty times too fast, which is a
    limiter that looks present and enforces nothing.

    Resets on restart, deliberately.
    """

    def __init__(self, rate: int, window_s: float = 60.0):
        self.rate = max(1, int(rate))
        self.capacity = float(self.rate)
        self.refill_per_sec = float(self.rate) / float(window_s)
        self.state: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.time()
        async with self._lock:
            tokens, last = self.state.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens >= 1.0:
                self.state[key] = (tokens - 1.0, now)
                return True
            self.state[key] = (tokens, now)
            return False


_limiters = {
    name: (RateLimiter(per_min, 60.0), RateLimiter(per_hour, 3600.0))
    for name, (per_min, per_hour) in LIMITS.items()
}


def client_key(request: Request) -> str:
    """Caddy sits in front, so the real client is in the forwarded header."""
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


async def check_rate(surface: str, key: str) -> bool:
    """Both buckets must allow, and the minute bucket is charged first.

    Ordering matters slightly: if the hourly bucket is the one that denies, the minute token
    is still spent. That is deliberate -- refunding it would mean tracking partial charges,
    and the drift is a token an hour.
    """
    minute, hour = _limiters.get(surface, _limiters["chat"])
    return await minute.allow(key) and await hour.allow(key)


def throttled_for(surface: str):
    """A dependency that rate-limits against this endpoint's own budget."""
    async def dep(request: Request) -> None:
        key = client_key(request)
        if not await check_rate(surface, key):
            per_min, per_hour = LIMITS[surface]
            log.warning("rate limited %s on %s", key, surface)
            raise HTTPException(
                429,
                f"Easy — {surface} is capped at {per_min}/min and {per_hour}/hour per "
                f"address. RavenCalc runs on the CPU and is far less restricted.")
    return dep


Throttled = Annotated[None, Depends(throttled_for("chat"))]


class GpuQueue:
    """Serialises GPU work.

    The lock is global rather than per-surface because the constraint is physical: 15.92
    GiB does not hold both weight sets, so 'chat is busy' and 'image is busy' are the same
    condition wearing different names.
    """

    def __init__(self, depth: int):
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(depth)
        self.waiting = 0
        self.current: str | None = None

    @asynccontextmanager
    async def hold(self, surface: str):
        """Hold the card for the duration of one job -- and only that.

        This used to be an in-process lock only, while the *governor* lock was taken once
        when llama-server started and kept for as long as the weights stayed loaded. The
        card was therefore marked busy during the 99% of the time chat was merely resident
        and idle, and nothing outside this process could ever get in: a CLI image request
        sat behind it until the 300 s acquire timeout expired.

        Residency and work are different things. llama-server staying loaded is residency,
        tracked by the governor's `resident` file. Holding the lock is work. So the
        governor lock is now taken here, per job, and released the moment the job ends --
        which is what lets `symoneural image` from a terminal take its turn like any other
        tenant, and lets the governor evict a resident-but-idle surface to make room.
        """
        if not _try(self._slots):
            raise HTTPException(
                http.HTTP_503_SERVICE_UNAVAILABLE,
                "The box is busy and the queue is full. Try again shortly.")
        contended = self._lock.locked()
        # Count waiters, not the holder. Incrementing before taking the lock meant a single
        # job with nobody behind it reported queued=1, which tripped the rack into an amber
        # "1 job(s) waiting" banner while the queue was in fact empty.
        if contended:
            self.waiting += 1
        try:
            if contended:
                # Say so before blocking. A client that knows it is third in line behind an
                # image render can show that, or go use RavenCalc, instead of watching a
                # spinner that explains nothing.
                await bus.announce(surface, "queued", behind=self.current, depth=self.waiting)
            async with self._lock:
                # Now take the cross-process lock. This can block on a CLI job or a
                # fine-tune, so it gets the full acquire timeout and reports honestly if it
                # loses the race rather than proceeding onto a card somebody else owns.
                rc, _out, _err = await run(str(GOVERNOR), "acquire", surface,
                                           timeout=ACQUIRE_TIMEOUT_S + 15, env_owner=True)
                if rc != 0:
                    raise HTTPException(
                        http.HTTP_503_SERVICE_UNAVAILABLE,
                        "Something else is using the GPU right now -- RavenCalc is on the "
                        "CPU and still available.")
                self.current = surface
                await bus.announce(surface, "acquired")
                await push_rack()
                try:
                    yield
                finally:
                    self.current = None
                    await run(str(GOVERNOR), "release", surface, timeout=90)
                    await bus.announce(surface, "released")
                    await push_rack()
        finally:
            if contended:
                self.waiting -= 1
            self._slots.release()


def _try(sem: asyncio.Semaphore) -> bool:
    try:
        sem.acquire_nowait()  # type: ignore[attr-defined]
        return True
    except AttributeError:
        # asyncio.Semaphore has no acquire_nowait; emulate it.
        if sem._value <= 0:  # noqa: SLF001
            return False
        sem._value -= 1      # noqa: SLF001
        return True
    except Exception:
        return False


gpu = GpuQueue(QUEUE_DEPTH)


class Bus:
    """The three-way channel: frontend <-> backend, agent <-> agent, agent <-> user.

    Polling was the alternative and it is genuinely wasteful. The rack asked /api/status
    every 2.5 seconds per open tab and almost always learned nothing -- a full request,
    response, and header set to be told the state had not changed. One upgraded connection
    plus a push when something actually happens is fewer bytes, fewer wakeups, and less
    power on both ends.

    Two rules keep it that way:

    **Only on change.** Every publish is diffed against the last frame sent and dropped if
    identical. A socket that chatters on a timer is just polling with extra steps.

    **Agents publish, they do not address.** A surface announces what it did -- acquired the
    card, started a render, released -- and every listener decides what that means to it.
    The rack redraws, a waiting client learns why it is waiting, and another agent can react,
    all from one event and one send.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last: str | None = None
        # Baseline per connection, not one global. A single shared snapshot let a late
        # joiner reset the diff baseline for everybody: the delta against the newer
        # baseline came out empty, so clients already connected never learned about the
        # change and stayed wrong for those fields forever.
        self._snapshots: dict[int, dict] = {}

    async def join(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
            self._snapshots.pop(id(ws), None)

    @property
    def listeners(self) -> int:
        return len(self._clients)

    def seed(self, ws: WebSocket, snapshot: dict) -> None:
        """Record the baseline this particular client was just given."""
        self._snapshots[id(ws)] = snapshot

    async def publish_delta(self, snapshot: dict) -> None:
        """Send only what moved since the last push.

        The client holds the rack state and patches it, so the wire carries the change
        rather than the world. A chat request starting is genuinely four fields --
        one unit's state, the holder, the queue depth, a VRAM figure -- and re-sending the
        whole rack to say that is most of a kilobyte to communicate about forty bytes of
        news. Over a night of traffic with several tabs open that is the difference between
        a socket that whispers and one that shouts the same sentence repeatedly.

        The baseline comes from the snapshot sent at handshake, so a client is never asked
        to patch state it does not have.
        """
        async with self._lock:
            targets = list(self._clients)
        dead = []
        for ws in targets:
            baseline = self._snapshots.get(id(ws))
            delta = _diff(baseline, snapshot) if baseline else {}
            self._snapshots[id(ws)] = snapshot
            if not delta:
                continue
            try:
                await ws.send_text(json.dumps({"t": "patch", **delta}, separators=(",", ":")))
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
                    self._snapshots.pop(id(ws), None)

    async def publish(self, frame: dict, *, dedupe_key: str | None = None) -> None:
        """Broadcast a frame. If dedupe_key is given, skip identical consecutive frames."""
        text = json.dumps(frame, separators=(",", ":"))
        if dedupe_key is not None:
            if text == self._last:
                return
            self._last = text
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    async def announce(self, source: str, event: str, **fields) -> None:
        """An agent saying what it just did, to whoever is listening."""
        await self.publish({"t": "bus", "from": source, "event": event, **fields})


def _diff(old: dict, new: dict) -> dict:
    """Structural difference, keyed the way the client stores it.

    Units are diffed by id rather than by list position, so the patch says
    `{"units": {"chat": {"state": "busy"}}}` -- addressed, not ordinal. A positional patch
    breaks silently the day a unit is added or reordered, and it breaks in the worst way:
    the client applies it to the wrong row and shows a confident wrong answer.
    """
    if not old:
        return {}
    out: dict = {}

    old_units = {u["id"]: u for u in old.get("units", [])}
    unit_delta = {}
    for unit in new.get("units", []):
        was = old_units.get(unit["id"])
        if was is None:
            unit_delta[unit["id"]] = unit
            continue
        changed = {k: v for k, v in unit.items() if was.get(k) != v}
        if changed:
            unit_delta[unit["id"]] = changed
    if unit_delta:
        out["units"] = unit_delta

    old_gpu, new_gpu = old.get("gpu") or {}, new.get("gpu") or {}
    gpu_delta = {k: v for k, v in new_gpu.items() if old_gpu.get(k) != v}
    if gpu_delta:
        out["gpu"] = gpu_delta
    return out


bus = Bus()


async def run(*argv: str, timeout: int = JOB_TIMEOUT_S,
              env_owner: bool = False) -> tuple[int, bytes, bytes]:
    """Run a subprocess in its own session, and kill the whole group on timeout.

    Killing only the direct child is not enough: the governor is a wrapper script and the
    engine (sd-cli, llama-server) is its child. SIGKILL to the wrapper leaves the engine
    orphaned, still holding several gigabytes of VRAM, and skips the wrapper's release trap
    so the lock leaks too. A process group makes "stop this job" mean all of it.
    """
    env = dict(os.environ)
    if env_owner:
        # Name ourselves as the lock owner so the holder pid is a process that will still
        # exist while the card is held.
        env["SYMONEURAL_OWNER_PID"] = str(os.getpid())
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True, env=env)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
        raise HTTPException(504, "That took too long and was stopped.")
    return proc.returncode or 0, out, err


_TELEMETRY_FIELDS = ("memory.free", "memory.total", "power.draw", "temperature.gpu")
_telemetry: dict[str, float | int | None] = {}
_telemetry_at = 0.0
_TELEMETRY_TTL = 1.0


def _read_smi() -> dict[str, float | int | None]:
    """All four telemetry fields in ONE nvidia-smi call.

    This used to be four separate synchronous `subprocess.run` calls made from inside async
    request handlers, each with an 8 second timeout. Every status poll therefore blocked the
    event loop across four process spawns -- and the loop it was blocking is the one
    streaming chat tokens, so a visitor watching the rack could stall someone else's
    generation. One exec, off the loop, cached for a second.

    Float for fractional fields (power.draw reads '11.42'), int for the rest. Casting
    everything to int silently turned power draw into None, which the rack rendered as a
    dead sensor -- a display that quietly shows nothing is worse than one showing a wrong
    number, because nobody goes looking for the bug.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={','.join(_TELEMETRY_FIELDS)}",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8)
        parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        values: dict[str, float | int | None] = {}
        for name, raw in zip(_TELEMETRY_FIELDS, parts):
            try:
                values[name] = float(raw) if "." in raw else int(raw)
            except ValueError:
                values[name] = None
        return values
    except Exception:
        return dict.fromkeys(_TELEMETRY_FIELDS)


def smi(field: str):
    """One telemetry field, from a short-lived cache."""
    global _telemetry, _telemetry_at
    now = time.monotonic()
    if now - _telemetry_at > _TELEMETRY_TTL:
        _telemetry = _read_smi()
        _telemetry_at = now
    return _telemetry.get(field)


GALLERY_KEEP = 60


def prune_gallery(keep: int = GALLERY_KEEP) -> None:
    """Keep the most recent renders, delete the rest.

    Newest-first by mtime rather than by the timestamp in the filename: the name is
    generated by us and could drift, the mtime is what the filesystem actually knows.
    """
    try:
        shots = sorted(RENDERS.glob("gen-*.png"), key=lambda p: p.stat().st_mtime,
                       reverse=True)
        for stale in shots[keep:]:
            stale.unlink(missing_ok=True)
    except Exception:
        log.exception("gallery prune failed")


async def refresh_telemetry() -> None:
    """Refresh the cache off the event loop."""
    global _telemetry, _telemetry_at
    _telemetry = await asyncio.to_thread(_read_smi)
    _telemetry_at = time.monotonic()


# ======================================================================== chat surface

SYSTEM_PROMPT = (
    "You are SyMoNeuRaL, the admin representative and resident expert for SyMoNeuRaL, a "
    "SymonSays LLC company that builds custom local AI infrastructure. You run locally on "
    "the machine you are describing. Be concise, concrete and never oversell. "
    "Measured facts about this machine, which you may cite: NVIDIA RTX 5070 Ti, Blackwell "
    "sm_120, 70 SMs x 128 = 8,960 CUDA cores, 15.92 GiB VRAM (15,858 MB), 256-bit bus at "
    "14,001 MHz, 896.1 GB/s theoretical DRAM bandwidth, ~752 GB/s measured (~84% of peak), "
    "48 MB L2, PCIe Gen 3 x8 host cap (the GPU supports Gen 5) giving ~6.94 GB/s H2D and "
    "~7.20 GB/s D2H pinned. Decode is memory-bandwidth bound: every token reads the full "
    "weight set once, so tokens/second is roughly bandwidth divided by weight bytes. "
    "Never invent a number you were not given, and never quote a price -- direct pricing "
    "questions to symonsayadmin@symoneural.com."
)

# ---------------------------------------------------------------- anticipation
#
# RavenCalc observing the chat surface, and having the answer ready before it is asked for.
#
# This only works because of an asymmetry in the hardware. Speculation costs whatever the
# speculating agent consumes, so a GPU agent guessing ahead would take the card away from
# the request actually in flight and make the queue worse. RavenCalc is SymPy on the CPU:
# it contends for nothing the serving surfaces want. So while the chat surface is loading
# ~5 GB of weights across a Gen 3 x8 link -- hundreds of milliseconds during which the GPU
# path can do nothing useful -- the calculator has already parsed the question, decided
# whether there is real mathematics in it, and computed the exact answer.
#
# What the model then receives is not a hint. It is a verified result with its own check
# attached, which the model is told to quote rather than recompute. That is the difference
# between a language model that is usually right about algebra and a system that is exactly
# right: the model routes, the algebra engine answers.

_OPERATION_WORDS = [
    (re.compile(r"\b(integrat\w*|antideriv\w*)\b", re.I), "integrate"),
    (re.compile(r"\b(differentiat\w*|derivat\w*|d/d[a-z])\b", re.I), "differentiate"),
    (re.compile(r"\blimit\b", re.I), "limit"),
    (re.compile(r"\b(solve|roots?\s+of|solutions?\s+(?:to|of))\b", re.I), "solve"),
    (re.compile(r"\b(simplif\w*|reduce)\b", re.I), "simplify"),
    (re.compile(r"\b(expand|series|taylor)\b", re.I), "series"),
    (re.compile(r"\b(evaluat\w*|compute|calculate|what\s+is)\b", re.I), "evaluate"),
]

# A run of characters that could plausibly be an expression. Deliberately conservative:
# it must contain an operator or a function call, so ordinary prose does not qualify.
_EXPR_CANDIDATE = re.compile(r"[0-9A-Za-z_+\-*/^().,\s]{3,120}")
_HAS_MATH = re.compile(r"[+\-*/^]|\b[a-z]+\s*\(")
_VARIABLE = re.compile(r"\b(?:with respect to|wrt|in terms of|for)\s+([a-zA-Z])\b", re.I)


def extract_math(prompt: str) -> tuple[str, str, str] | None:
    """Find (operation, expression, variable) in a natural-language question.

    Returns None far more often than not, and that is the correct behaviour -- a false
    positive here means an irrelevant "verified result" is handed to the model and it
    dutifully works it into an answer about something else. The parser is the gate: a
    candidate only survives if RavenCalc's own strict whitelist parser accepts it, so
    prose, code and pasted logs fall out on their own.
    """
    try:
        import ravencalc
    except ImportError:
        return None

    operation = next((op for pattern, op in _OPERATION_WORDS if pattern.search(prompt)), None)
    if operation is None:
        return None

    variable = "x"
    if match := _VARIABLE.search(prompt):
        variable = match.group(1)

    # Fenced text wins outright -- if someone put it in backticks they meant it literally.
    for fenced in re.findall(r"`([^`]{2,120})`", prompt):
        if _parses(ravencalc, fenced):
            return operation, fenced.strip(), variable

    # Otherwise search word spans, longest first, and let the parser decide. Trying to
    # strip English with a regex does not survive contact with real phrasing: "integrate
    # x**2 with respect to x" has prose on both sides, and one pass of prefix-removal
    # leaves the tail behind. Testing spans costs nothing on a sentence and is simply
    # correct -- the strict whitelist parser is a far better judge of "is this an
    # expression" than any pattern of mine.
    # Drop the operation words before searching. SymPy's namespace contains functions with
    # exactly these names, so "simplify (x**2-1)/(x-1)" parses happily as a call to
    # simplify() -- and "integrate (x)" would parse as an integral that we then integrate a
    # second time. The verb belongs to the request, not to the expression.
    cleaned = re.sub(r"\b(integrate|integral|antiderivative|differentiate|derivative|"
                     r"diff|limit|solve|simplify|expand|factor|series|taylor|evaluate|"
                     r"compute|calculate)\b", " ", prompt, flags=re.I)
    words = re.sub(r"[?]", " ", cleaned).split()
    n = len(words)
    for length in range(min(n, 14), 0, -1):
        for start in range(0, n - length + 1):
            candidate = " ".join(words[start:start + length]).strip(" .,?:;")
            if len(candidate) < 3 or not _HAS_MATH.search(candidate):
                continue
            if not any(ch.isalnum() for ch in candidate):
                continue
            if _parses(ravencalc, candidate):
                return operation, candidate, variable
    return None


def _parses(ravencalc, text: str) -> bool:
    """Does RavenCalc's strict parser accept this as an expression?

    This is the gate that keeps prose out. The parser whitelists characters and refuses
    attribute access, so ordinary English, pasted logs and code all fail it without any
    heuristic of ours having to recognise them.
    """
    text = text.strip()
    if not text or len(text) > 200:
        return False
    try:
        expr = ravencalc.parse(text)
    except Exception:
        return False
    # A bare number or a lone symbol parses fine but is not what anyone meant by
    # "integrate this" -- require some actual structure.
    return bool(getattr(expr, "args", ()))


def _compute_exact(operation: str, expression: str, variable: str) -> dict | None:
    import ravencalc
    doc = {"schema": "ravencalc/request/v1", "operation": operation, "expression": expression}
    if operation in {"differentiate", "integrate", "limit", "series", "solve"}:
        doc["variable"] = variable
    if operation == "limit":
        doc["point"] = "0"
    try:
        return ravencalc.run_request(doc)
    except Exception:
        return None


async def anticipate(prompt: str) -> dict | None:
    """Speculatively solve any mathematics in the prompt, on the CPU, in parallel.

    Started before the GPU surface is ready and awaited after, so on a cold chat the whole
    computation happens inside time that was going to be spent loading weights anyway.
    """
    found = extract_math(prompt)
    if not found:
        return None
    operation, expression, variable = found
    started = time.time()
    result = await asyncio.to_thread(_compute_exact, operation, expression, variable)
    if not result:
        return None
    result["_anticipated_ms"] = round((time.time() - started) * 1000, 1)
    result["_operation"] = operation
    await bus.announce("calc", "anticipated", operation=operation,
                       expression=expression, ms=result["_anticipated_ms"])
    log.info("anticipated %s(%s) in %sms", operation, expression, result["_anticipated_ms"])
    return result


def exact_context(result: dict) -> str:
    """Phrase the verified result for the model, with instructions not to second-guess it."""
    check = result.get("check") or {}
    verdict = ("verified by back-substitution" if check.get("passed") is True
               else "computed but unconfirmed" if check.get("performed")
               else "computed")
    return (
        "\n\nRavenCalc, the exact symbolic engine running alongside you, has already "
        f"computed this and you should quote its result rather than deriving your own:\n"
        f"  operation: {result.get('_operation')}\n"
        f"  input:     {result['input'].get('text')}\n"
        f"  result:    {result['result'].get('text')}\n"
        f"  status:    {verdict} ({result.get('engine')})\n"
        "State that result exactly as written. You may explain the method, but do not "
        "recompute it and do not present a different answer -- this one is exact and yours "
        "would be a guess. Mention that RavenCalc computed it."
    )


_llama: asyncio.subprocess.Process | None = None
_llama_lock = asyncio.Lock()


async def llama_up() -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", LLAMA_PORT), timeout=2)
        writer.write(b"GET /health HTTP/1.0\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        head = await asyncio.wait_for(reader.read(64), timeout=3)
        writer.close()
        return b"200" in head
    except Exception:
        return False


async def start_llama() -> bool:
    global _llama
    async with _llama_lock:
        if await llama_up():
            return True
        if not CHAT_MODEL.exists() or not LLAMA_SERVER.exists():
            return False
        # No acquire here: every caller is already inside gpu.hold("chat"), so the card
        # is ours. Taking a second, longer-lived lock here is exactly what locked the CLI
        # out for the lifetime of the process.
        argv = [str(LLAMA_SERVER), "-m", str(CHAT_MODEL), "-ngl", "99",
                "--host", "127.0.0.1", "--port", str(LLAMA_PORT), "-c", "8192", "--no-warmup",
                # Continuous batching: one pass over the weights serves every slot in
                # flight, which is the single highest-value lever measured on this card
                # (47.3x from batch 1 to batch 64).
                "-cb", "-np", "4"]
        if DRAFT_MODEL.exists():
            argv += ["-md", str(DRAFT_MODEL), "-ngld", "99",
                     "--spec-draft-n-max", str(SPEC_DRAFT_MAX)]
        if CHAT_ADAPTER.exists():
            argv += ["--lora", str(CHAT_ADAPTER)]
        log.info("starting chat surface")
        _llama = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        for _ in range(120):
            if await llama_up():
                log.info("chat surface up")
                return True
            await asyncio.sleep(1)
        log.error("chat surface failed to come up")
        return False


async def stop_llama() -> None:
    global _llama
    async with _llama_lock:
        if _llama and _llama.returncode is None:
            _llama.terminate()
            try:
                await asyncio.wait_for(_llama.wait(), timeout=20)
            except asyncio.TimeoutError:
                _llama.kill()
        _llama = None


async def chat_deltas(messages: list[dict], max_tokens: int, temperature: float):
    """Yield content deltas from llama-server's OpenAI-compatible endpoint."""
    body = json.dumps({"model": "symoneural", "messages": messages, "stream": True,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    reader, writer = await asyncio.open_connection("127.0.0.1", LLAMA_PORT)
    writer.write(
        b"POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\n"
        b"Content-Type: application/json\r\nConnection: close\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    await writer.drain()
    try:
        while True:
            raw = await asyncio.wait_for(reader.readline(), timeout=JOB_TIMEOUT_S)
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0].get("delta", {})
            except Exception:
                continue
            if piece := delta.get("content"):
                yield piece
    finally:
        writer.close()


# ======================================================================== app

async def telemetry_loop() -> None:
    """Keep the live modules actually live.

    push_rack only fired when a job started or ended, so between jobs the VRAM, power and
    temperature readings sat frozen -- on modules badged `live`, on a page whose argument is
    that its numbers are real. Worse, the HTTP polling fallback was fresher than the
    WebSocket we tell clients to prefer.

    Only runs while somebody is listening, and the delta filter means an idle machine still
    sends nothing: temperature that has not moved produces no frame.
    """
    while True:
        try:
            await asyncio.sleep(3)
            if bus.listeners:
                await refresh_telemetry()
                await push_rack()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("telemetry loop hiccup")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("symoneural api on 127.0.0.1:%d (loopback only)", PORT)
    log.info("caps: prompt<=%d, queue %d, %d/min, %d/hr",
             MAX_PROMPT_CHARS, QUEUE_DEPTH, RATE_PER_MIN, RATE_PER_HOUR)
    ticker = asyncio.create_task(telemetry_loop())
    yield
    ticker.cancel()
    await stop_llama()


app = FastAPI(
    title="SyMoNeuRaL API",
    version="1.0",
    lifespan=lifespan,
    # Served through Caddy at symoneural.com; the assets are local, see /docs below.
    docs_url=None, redoc_url=None,
    openapi_url="/openapi.json",
    description=(
        "The production API behind [symoneural.com](https://symoneural.com) — four "
        "surfaces on one RTX 5070 Ti.\n\n"
        "**Chat**, **Image** and **Remix** all want the same GPU, and the chat and image "
        "weight sets do not both fit in 15.92 GiB. So exactly one holds the card at a time "
        "and the others queue. **RavenCalc** is SymPy on the CPU and never queues — which "
        "is why it is always available even when the rack shows everything else busy.\n\n"
        "Rate limits are per endpoint, scaled to cost: **calc** 240/min, **chat** 120/min, "
        "**remix** 40/min, **image** 20/min (hourly budgets are 25x the minute). Every "
        "parameter is clamped server-side; the values documented here are the real "
        "bounds.\n\n"
        "This is a demonstration on the smallest machine we would ever ship, not a "
        "statement of capacity."
    ),
    openapi_tags=[
        {"name": "surfaces", "description": "The four things you can actually run."},
        {"name": "status", "description": "What the rack on the home page reads."},
    ],
)


app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)


DOCS_HEADER = """
<div class="status">
  <div class="wrap">
    <b><s></s>Under Construction</b>
    <span>Active infrastructure development in progress. This API runs on one consumer GPU.</span>
  </div>
</div>
<header>
  <div class="wrap bar">
    <a class="logo" href="/">
      <img src="/mark-64.png" srcset="/mark-32.png 1x, /mark-64.png 2x" alt="SyMoNeuRaL"
           width="30" height="30">
      <b>SyMoNeu<i>RaL</i></b>
    </a>
    <nav>
      <a class="live" href="/chat.html"><s></s>Talk to the box</a>
      <a class="live" href="/image.html"><s></s>Make it draw</a>
      <a href="/calc.html">RavenCalc</a>
      <a href="/#rack">Stack</a>
      <a class="cta ghost" href="/openapi.json">openapi.json</a>
    </nav>
  </div>
</header>
<div class="wrap" style="padding-top:26px">
  <p class="eyebrow"><img src="/terminal-64.png" alt="" width="20" height="20"
     style="display:inline-block;vertical-align:-4px;margin-right:8px">API Reference</p>
  <h1 style="margin:0;font-size:clamp(26px,3.4vw,38px);letter-spacing:-.022em;font-weight:680">
    SyMoNeuRaL API</h1>

  <div class="console" style="margin-top:20px">
    <div class="mod" data-src="live"><div class="tag"><s></s>VRAM free</div>
      <div class="val" id="m-vram">&mdash;</div><div class="sub">of 15.92 GiB</div>
      <div class="meter" id="m-vrambar"><i style="width:0%"></i></div></div>
    <div class="mod" data-src="live"><div class="tag"><s></s>Power draw</div>
      <div class="val" id="m-pwr">&mdash;</div><div class="sub">300 W limit</div>
      <div class="meter" id="m-pwrbar"><i style="width:0%"></i></div></div>
    <div class="mod" data-src="live"><div class="tag"><s></s>Resident</div>
      <div class="val sm" id="m-holder">idle</div><div class="sub">one surface at a time</div></div>
    <div class="mod" data-src="live"><div class="tag"><s></s>Queue</div>
      <div class="val" id="m-queue">0</div><div class="sub">jobs waiting</div></div>
    <div class="mod" data-src="measured"><div class="tag"><s></s>Rate limit</div>
      <div class="val">6<u>/min</u></div><div class="sub">60/hour &middot; per address</div></div>
    <div class="mod" data-src="measured"><div class="tag"><s></s>Prompt cap</div>
      <div class="val">1,200</div><div class="sub">chars &middot; refused, not truncated</div></div>
  </div>

  <div class="callout" style="margin-top:22px">
    <h3>Prefer the socket to the poller</h3>
    <p>
      <code style="color:var(--dim)">GET /api/ws</code> upgrades to a WebSocket and then stays
      quiet until the machine actually changes &mdash; one handshake, one baseline snapshot,
      then patches of a few dozen bytes. Polling <code style="color:var(--dim)">/api/status</code>
      works too and supports <code style="color:var(--dim)">If-None-Match</code>, so an
      unchanged rack costs a bare <code style="color:var(--dim)">304</code> with no body.
    </p>
    <p>
      <strong>Frames.</strong> Server sends <code style="color:var(--dim)">welcome</code> &rarr;
      <code style="color:var(--dim)">rack</code> (full) &rarr;
      <code style="color:var(--dim)">patch</code> (deltas, units addressed by id) and
      <code style="color:var(--dim)">bus</code> (an agent announcing what it did).
      Client may send <code style="color:var(--dim)">ping</code>,
      <code style="color:var(--dim)">rack</code>,
      <code style="color:var(--dim)">chat</code>, <code style="color:var(--dim)">calc</code>,
      <code style="color:var(--dim)">remix</code> &mdash; rate limited exactly like the REST
      routes, because holding a socket open is not a way around the caps.
    </p>
  </div>
</div>
"""


@app.get("/docs", include_in_schema=False)
async def docs() -> HTMLResponse:
    """Swagger UI, with its assets served from this box.

    FastAPI's default points at a CDN. On a site whose entire argument is that nothing
    leaves the machine, loading the documentation UI from someone else's server would be a
    small but real contradiction -- so the bundle is served from our own webroot.
    """
    page = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="SyMoNeuRaL API",
        swagger_js_url="/swagger-ui-bundle.js",
        swagger_css_url="/swagger-ui.css",
        swagger_favicon_url="/favicon-32.png",
    ).body.decode()

    # Brand it: our palette over Swagger's, plus the site header and a live status strip so
    # the docs page shows the same machine state as every other page rather than being a
    # detached reference.
    page = page.replace(
        "</head>",
        '<link rel="stylesheet" href="/swagger-dark.css">'
        '<link rel="stylesheet" href="/symoneural.css">'
        '<link rel="stylesheet" href="/rack-detail.css">'
        '<meta name="theme-color" content="#0e100f">'
        "</head>", 1)
    page = page.replace("<body>", "<body>" + DOCS_HEADER, 1)
    page = page.replace("</body>", '<script src="/console.js" defer></script></body>', 1)
    return HTMLResponse(page)


def external_holder() -> str | None:
    """Who holds the governor lock, if it is not us.

    The lock directory only exists while held, and the holder file names the surface and
    its pid. A stale entry whose process is gone is treated as free -- the governor breaks
    those itself, and reporting a dead holder would wedge the display long after the card
    was actually released.
    """
    holder_file = RUN / "gpu.lock.d" / "holder"
    try:
        surface, pid = holder_file.read_text().split()
        os.kill(int(pid), 0)
        return surface
    except Exception:
        return None


def build_status() -> Status:
    """Per-unit state for the rack.

    Four states, and they mean different things: `ready` (take it now), `busy` (this unit
    holds the card), `queued` (something else holds it and this unit would wait), `offline`
    (weights or engine missing). `queued` is the one worth being careful about -- a visitor
    stuck behind someone's render should be able to see why, and see that RavenCalc is free.
    """
    # The API's own queue is not the only thing that can own the card. A training run or a
    # CLI invocation takes the governor directly, and a rack that reports "ready" while a
    # fine-tune is mid-epoch is lying to the visitor -- they click, wait five minutes behind
    # a lock, and conclude the site is broken. So the governor's own record wins.
    holder = gpu.current or external_holder()
    chat_ok = CHAT_MODEL.exists() and LLAMA_SERVER.exists()
    image_ok = all(p.exists() for p in FLUX.values()) and SD_CLI.exists()

    def gpu_unit(name: str, ok: bool) -> str:
        if not ok:
            return "offline"
        if holder == name:
            return "busy"
        return "queued" if holder else "ready"

    free, total = smi("memory.free"), smi("memory.total")
    return Status(
        units=[
            Unit(id="chat", label="SyMoNeuRaL Chat", slot="1U", state=gpu_unit("chat", chat_ok),
                 bus="gpu", href="/chat.html",
                 # Product names first -- these are our builds: our quantization, our
                 # adapter, our serving stack. The upstream model stays visible in the
                 # detail line because both bases are Apache-2.0 and attribution is a
                 # licence condition, not a courtesy -- and because a page arguing that
                 # its numbers are real cannot hide where its weights came from.
                 spec="SymonChat S1-7B" + (" + persona adapter" if CHAT_ADAPTER.exists()
                                           else " · Q4_K_M"),
                 detail="~5 GB resident · built on Qwen2.5-7B-Instruct"),
            Unit(id="image", label="SyMoNeuRaL Image", slot="2U",
                 state=gpu_unit("image", image_ok), bus="gpu", href="/image.html",
                 spec="SymonImage F1 · q4_k",
                 detail="~7 GB resident · built on FLUX.1-schnell" if image_ok
                        else "weights loading"),
            Unit(id="remix", label="SyMoNeuRaL Remix", slot="1U",
                 state=gpu_unit("remix", chat_ok), bus="gpu", href="/remix.html",
                 spec="client of the chat surface", detail="no weights of its own"),
            Unit(id="calc", label="SyMoNeuRaL RavenCalc", slot="1U", state="ready",
                 bus="cpu", href="/calc.html", spec="SymPy, exact symbolic",
                 detail="cpu only, never queues"),
            # The adapter bay. Idle most of the time, but when a fine-tune is running it
            # owns the card outright and every serving surface waits behind it -- so it
            # belongs on the rack rather than being invisible infrastructure.
            Unit(id="train", label="SyMoNeuRaL Quantized Low-Rank Adaptation Tool", slot="2U",
                 state="busy" if holder == "train" else
                       ("ready" if CHAT_ADAPTER.exists() else "offline"),
                 bus="gpu", href="/training.html",
                 spec="SymonChat persona adapter · QLoRA",
                 detail="fine-tune in progress — serving surfaces queue" if holder == "train"
                        else ("adapter loaded · for model/adapter tuning"
                              if CHAT_ADAPTER.exists() else "no adapter built")),
        ],
        gpu=GpuState(
            name="RTX 5070 Ti", vram_free_mib=free, vram_total_mib=total,
            vram_used_pct=round(100 * (1 - free / total)) if free and total else None,
            power_w=smi("power.draw"), temp_c=smi("temperature.gpu"),
            holder=holder, queued=gpu.waiting,
        ),
        link={"gen": 3, "width": 8, "note": "Gen 3 x8 -- host capped"},
    )


def semantic_etag(body: dict) -> str:
    """Hash what a caller actually cares about, not every drifting sensor.

    Hashing the whole payload produced a tag that changed on every single request, because
    power draw and temperature never hold still -- 37.9 W becomes 38.1 W and the cache is
    busted for a difference nobody is waiting on. The result was an ETag that cost a hash
    and saved nothing, which is worse than having none at all.

    So the tag covers the semantic state: which units exist, what state each is in, who
    holds the card, how deep the queue is, and VRAM rounded to the nearest 256 MiB. While
    the machine is genuinely idle -- which is most of the time -- this is stable and every
    poll costs a bare 304 instead of the full body. Telemetry still rides along in the body
    for anyone who fetches it; it just does not get a vote on freshness.
    """
    gpu_body = body.get("gpu") or {}
    free = gpu_body.get("vram_free_mib")
    stable = {
        "units": [(u["id"], u["state"]) for u in body.get("units", [])],
        "holder": gpu_body.get("holder"),
        "queued": gpu_body.get("queued"),
        "vram_bucket": round(free / 256) if isinstance(free, int) else None,
    }
    return hashlib.sha1(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


async def push_rack() -> None:
    """Push what changed, and nothing at all if nothing did."""
    if bus.listeners:
        await bus.publish_delta(build_status().model_dump())


@app.get("/api/status", response_model=Status, tags=["status"],
         responses={304: {"description": "Unchanged since the ETag you sent."}})
async def get_status(request: Request, response: Response) -> Status | Response:
    """Rack state over plain HTTP, for clients that cannot hold a socket.

    Supports conditional requests. Send back the `ETag` from a previous response as
    `If-None-Match` and an unchanged rack costs a bare `304` instead of the full body --
    which is most of the time, since the machine is idle more than it is busy.

    Prefer the WebSocket at `/api/ws` if you can: it costs one handshake and then sends
    nothing at all until something changes, rather than a request every few seconds to be
    told the same thing.
    """
    payload = build_status()
    body = payload.model_dump()
    etag = '"' + semantic_etag(body) + '"'

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=http.HTTP_304_NOT_MODIFIED,
                        headers={"ETag": etag, "Cache-Control": "no-cache"})

    response.headers["ETag"] = etag
    # no-cache means "revalidate", not "do not store" -- the client keeps the body and
    # spends a conditional request instead of a full one.
    response.headers["Cache-Control"] = "no-cache"
    return payload


@app.websocket("/api/ws")
async def websocket(ws: WebSocket) -> None:
    """The three-way channel. See the protocol table in the API description above.

    Handshake: connect, receive `welcome`, then `rack` frames arrive whenever the machine
    changes. Send `{"t":"chat","prompt":"..."}` to generate over the same socket -- deltas
    come back as `{"t":"delta"}` and finish with `{"t":"done"}` carrying the measured rate.
    """
    await ws.accept()
    await bus.join(ws)
    try:
        await ws.send_text(json.dumps({
            "t": "welcome", "proto": 1,
            "caps": ["rack", "chat", "calc", "remix", "ping"],
            "limits": {"prompt_chars": MAX_PROMPT_CHARS, "per_min": RATE_PER_MIN,
                       "per_hour": RATE_PER_HOUR, "queue_depth": QUEUE_DEPTH},
            "note": "One GPU. chat/image/remix take turns; calc never queues.",
        }, separators=(",", ":")))
        # One full snapshot, once. Everything after this is a patch against it -- so the
        # baseline is established here and the wire stays quiet until something moves.
        snapshot = build_status().model_dump()
        bus.seed(ws, snapshot)
        await ws.send_text(json.dumps({"t": "rack", **snapshot}, separators=(",", ":")))

        key = client_key_ws(ws)
        while True:
            raw = await ws.receive_text()
            if len(raw) > 8000:
                await ws.send_text(json.dumps({"t": "error", "code": 413,
                                               "error": "Frame too large."}))
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"t": "error", "code": 400,
                                               "error": "Not JSON."}))
                continue

            kind = msg.get("t")
            if kind == "ping":
                await ws.send_text('{"t":"pong"}')
                continue
            if kind == "rack":
                await ws.send_text(json.dumps({"t": "rack", **build_status().model_dump()},
                                              separators=(",", ":")))
                continue

            # Everything below spends the GPU or the CPU, so it is rate limited exactly
            # like the REST routes. Holding a socket open is not a way around the caps.
            if not await check_rate(kind if kind in LIMITS else "chat", key):
                per_min, per_hour = LIMITS.get(kind, LIMITS["chat"])
                await ws.send_text(json.dumps({
                    "t": "error", "code": 429,
                    "error": f"Easy -- {kind} is capped at {per_min}/min, "
                             f"{per_hour}/hour per address."}))
                continue

            if kind == "chat":
                await ws_chat(ws, msg)
            elif kind == "calc":
                await ws_calc(ws, msg)
            elif kind == "remix":
                await ws_remix(ws, msg)
            else:
                await ws.send_text(json.dumps({
                    "t": "error", "code": 400, "error": f"Unknown frame type {kind!r}."}))
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("websocket failed")
    finally:
        await bus.leave(ws)


def client_key_ws(ws: WebSocket) -> str:
    fwd = ws.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (ws.client.host if ws.client else "unknown")


async def ws_chat(ws: WebSocket, msg: dict) -> None:
    try:
        body = ChatRequest(**{k: v for k, v in msg.items() if k != "t"})
    except Exception as exc:
        await ws.send_text(json.dumps({"t": "error", "code": 422, "error": str(exc)[:300]}))
        return
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": body.prompt}]
    async with gpu.hold("chat"):
        if not await start_llama():
            await ws.send_text(json.dumps({"t": "error", "code": 503,
                                           "error": "Chat surface is not available."}))
            return
        started, tokens = time.time(), 0
        async for piece in chat_deltas(messages, body.max_tokens, body.temperature):
            tokens += 1
            await ws.send_text(json.dumps({"t": "delta", "d": piece}, separators=(",", ":")))
        elapsed = time.time() - started
        await ws.send_text(json.dumps({
            "t": "done", "tokens": tokens, "seconds": round(elapsed, 2),
            "tok_per_s": round(tokens / elapsed, 1) if elapsed else None,
            "model": CHAT_MODEL.stem, "adapter": CHAT_ADAPTER.exists()},
            separators=(",", ":")))


async def ws_calc(ws: WebSocket, msg: dict) -> None:
    try:
        body = CalcRequest(**{k: v for k, v in msg.items() if k != "t"})
    except Exception as exc:
        await ws.send_text(json.dumps({"t": "error", "code": 422, "error": str(exc)[:300]}))
        return
    try:
        import ravencalc
    except ImportError:
        await ws.send_text(json.dumps({"t": "error", "code": 503,
                                       "error": "RavenCalc is unavailable."}))
        return
    doc = {"schema": "ravencalc/request/v1", "operation": body.operation,
           "expression": body.expression}
    if body.variable:
        doc["variable"] = body.variable
    if body.point:
        doc["point"] = body.point
    started = time.time()
    try:
        result = await asyncio.to_thread(ravencalc.run_request, doc)
    except ravencalc.RavenCalcError as exc:
        await ws.send_text(json.dumps({"t": "error", "code": 400, "error": exc.message}))
        return
    result["seconds"] = round(time.time() - started, 4)
    await ws.send_text(json.dumps({"t": "calc.result", **json.loads(json.dumps(result, default=str))},
                                  separators=(",", ":")))


async def ws_remix(ws: WebSocket, msg: dict) -> None:
    try:
        body = RemixRequest(**{k: v for k, v in msg.items() if k != "t"})
    except Exception as exc:
        await ws.send_text(json.dumps({"t": "error", "code": 422, "error": str(exc)[:300]}))
        return
    result = await remix(body, None)  # type: ignore[arg-type]
    await ws.send_text(json.dumps({"t": "remix.result", **result.model_dump()},
                                  separators=(",", ":")))


@app.post("/api/chat", tags=["surfaces"])
async def chat(body: ChatRequest,
                _: Annotated[None, Depends(throttled_for("chat"))]) -> StreamingResponse:
    """Ask the local model. Streams Server-Sent Events as the card produces tokens.

    Each event is `{"delta": "..."}`; the last is
    `{"done": true, "tokens": N, "seconds": S, "tok_per_s": R, "model": "...", "adapter": bool}`.
    The rate in that final event is measured, not claimed.
    """
    async def stream():
        # Kick RavenCalc off first, then take the card. The calculator runs on the CPU, so
        # it does its work inside the time the GPU surface spends loading -- by the time the
        # model can speak, the exact answer is already sitting here waiting for it.
        thinking = asyncio.create_task(anticipate(body.prompt))

        async with gpu.hold("chat"):
            if not await start_llama():
                thinking.cancel()
                yield f"data: {json.dumps({'error': 'Chat surface is not available.'})}\n\n"
                return

            system = SYSTEM_PROMPT
            try:
                exact = await asyncio.wait_for(thinking, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                exact = None
            if exact:
                system += exact_context(exact)
                yield "data: " + json.dumps({
                    "assist": {
                        "from": "ravencalc",
                        "operation": exact.get("_operation"),
                        "input": exact["input"].get("text"),
                        "result": exact["result"].get("text"),
                        "check": exact.get("check"),
                        "ms": exact.get("_anticipated_ms"),
                    }}) + "\n\n"

            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": body.prompt}]
            started, tokens, out = time.time(), 0, []
            async for piece in chat_deltas(messages, body.max_tokens, body.temperature):
                tokens += 1
                out.append(piece)
                yield f"data: {json.dumps({'delta': piece})}\n\n"
            elapsed = time.time() - started
            yield "data: " + json.dumps({
                "done": True, "tokens": tokens, "seconds": round(elapsed, 2),
                "tok_per_s": round(tokens / elapsed, 1) if elapsed else None,
                "model": CHAT_MODEL.stem, "adapter": CHAT_ADAPTER.exists(),
            }) + "\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/image", response_model=ImageResult, tags=["surfaces"])
async def image(body: ImageRequest,
                _: Annotated[None, Depends(throttled_for("image"))]) -> ImageResult:
    """Render an image with FLUX.1-schnell.

    Taking the card means evicting chat first -- both weight sets do not fit -- so the
    first render after a chat may include a cold load. `seconds` is the render alone.
    """
    if DENY.search(body.prompt):
        log.warning("denied image prompt: %r", body.prompt[:200])
        raise HTTPException(400, "That prompt is outside what this public surface will render.")
    if any(not p.exists() for p in FLUX.values()) or not SD_CLI.exists():
        raise HTTPException(503, "Image surface is still warming up.")

    # secrets, not the clock. int(time.time()) % 100000 gave every render in the same
    # wall-clock second an identical "random" seed -- two visitors prompting at once got
    # correlated images -- and wrapped every ~27 hours.
    seed = body.seed if body.seed is not None else secrets.randbelow(2**31 - 1)
    stamp = f"gen-{int(time.time() * 1000)}-{seed}.png"
    out = RENDERS / stamp
    argv = [str(SD_CLI),
            "--diffusion-model", str(FLUX["unet"]), "--vae", str(FLUX["vae"]),
            "--clip_l", str(FLUX["clip"]), "--t5xxl", str(FLUX["t5"]),
            "-p", body.prompt, "--cfg-scale", "1.0", "--sampling-method", "euler",
            "--steps", str(body.steps), "-W", str(body.size), "-H", str(body.size),
            "--seed", str(seed), "-o", str(out),
            # Without these a 768x768 render dies in VAE decode: it wants a 3.7 GB compute
            # buffer, and with the 5.2 GB T5 encoder also resident there is nothing left.
            # te=cpu moves the text encoder to system RAM (it runs once per prompt, so the
            # PCIe cost is paid once rather than per step), and vae-tiling decodes in tiles
            # instead of allocating the whole buffer at once.
            "--backend", "te=cpu", "--vae-tiling", "--diffusion-fa"]

    async with gpu.hold("image"):
        await stop_llama()
        started = time.time()
        # Run sd-cli directly. gpu.hold already owns the governor lock, and wrapping this
        # in `governor with image` made the process wait on a lock it was already holding --
        # a self-deadlock that only surfaced as the job timeout 120 s later.
        rc, _o, err = await run(*argv)
        elapsed = time.time() - started

    if rc != 0 or not out.exists():
        log.error("image failed: %s", err.decode("utf-8", "replace")[-800:])
        raise HTTPException(500, "The render failed.")

    # Renders land in the served directory, so without this they grow without bound -- a
    # public endpoint producing ~800 KB per request fills a disk quietly and takes the whole
    # site down with it, which is a far worse outcome than an old image disappearing.
    await asyncio.to_thread(prune_gallery)

    return ImageResult(url=f"/api/gen/{stamp}", seconds=round(elapsed, 2), seed=seed,
                       steps=body.steps, size=body.size,
                       model="FLUX.1-schnell q4_k", bytes=out.stat().st_size)



@app.get("/api/gen/{name}", tags=["surfaces"],
         responses={200: {"content": {"image/png": {}}}, 404: {"description": "Gone or never existed"}})
async def gen(name: str) -> FileResponse:
    """Serve a render produced by `POST /api/image`.

    Renders used to be handed back as `/<file>`, a path in the deployed webroot. But the
    API writes them into the staging directory, and the web server serves the webroot -- so every
    image generated on the live site 404'd until somebody ran a deploy, which needs a
    password no process here has. Serving them from `/api` instead means they are visible
    the instant they exist, on the same proxied path as every other surface.

    Renders are pruned to the newest 60, so an old url legitimately becomes a 404.
    """
    # `name` is attacker-controlled and lands in a filesystem path. Match the exact shape
    # the generator emits rather than trying to sanitise traversal out of arbitrary input.
    if not re.fullmatch(r"gen-\d{13}-\d{1,10}\.png", name):
        raise HTTPException(404, "No such render.")
    path = RENDERS / name
    if not path.is_file():
        raise HTTPException(404, "That render has been pruned.")
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})

@app.post("/api/calc", tags=["surfaces"])
async def calc(body: CalcRequest,
                _: Annotated[None, Depends(throttled_for("calc"))]) -> dict:
    """Exact symbolic mathematics. No GPU, no lock, no queue.

    Returns a `ravencalc/result/v1` document. Note `check`: where verification is cheap the
    engine does it -- an antiderivative is differentiated back and simplified against zero --
    and `check.passed` is three-valued. `null` means the check could not confirm the result,
    which is reported rather than rounded up to success.
    """
    try:
        import ravencalc
    except ImportError:
        raise HTTPException(503, "RavenCalc is unavailable.")

    doc = {"schema": "ravencalc/request/v1", "operation": body.operation,
           "expression": body.expression}
    if body.variable:
        doc["variable"] = body.variable
    if body.point:
        doc["point"] = body.point

    started = time.time()
    try:
        result = await asyncio.to_thread(ravencalc.run_request, doc)
    except ravencalc.RavenCalcError as exc:
        raise HTTPException(400, exc.message)
    result["seconds"] = round(time.time() - started, 4)
    return json.loads(json.dumps(result, default=str))


@app.post("/api/remix", response_model=RemixResult, tags=["surfaces"])
async def remix(body: RemixRequest,
                _: Annotated[None, Depends(throttled_for("remix"))]) -> RemixResult:
    """Build a sequenced tracklist.

    Remix has no weights of its own -- it asks the chat surface, which is what "one server
    underneath" means in practice, and why it queues behind chat and image.

    Generation only. Resolving tracks against Spotify and writing a playlist needs OAuth
    against a real account, and a stranger's prompt should not reach one; that half runs on
    the box behind admin auth.
    """
    messages = [
        {"role": "system", "content":
         "You are SyMoNeuRaL Remix, a playlist builder. Return exactly a JSON array of "
         f"{body.count} objects, each {{\"artist\": str, \"title\": str, \"why\": str}}, "
         "ordered so the sequence actually flows -- tempo and key matter, this is an "
         "ordered set rather than a pile of songs. 'why' is at most 12 words. Output the "
         "JSON array and nothing else."},
        {"role": "user", "content": body.prompt},
    ]
    async with gpu.hold("chat"):
        if not await start_llama():
            raise HTTPException(503, "Chat surface is not available.")
        started = time.time()
        text = "".join([p async for p in chat_deltas(messages, 900, 0.8)])
        elapsed = time.time() - started

    match = re.search(r"\[.*]", text, re.S)
    try:
        raw = json.loads(match.group(0)) if match else []
    except json.JSONDecodeError:
        raw = []
    tracks = [Track(**{k: str(t.get(k, ""))[:200] for k in ("artist", "title", "why")})
              for t in raw[:body.count] if isinstance(t, dict)]
    return RemixResult(
        tracks=tracks, seconds=round(elapsed, 2),
        note=("Generated locally. Resolving these against Spotify and writing the playlist "
              "runs on the box behind admin auth, not from this page."))


# ---------------------------------------------------------------------------
# Static site, mounted last so it never shadows an API route.
#
# In production Caddy serves site/ from the webroot and only proxies /api, so
# this mount is not on the public path. It exists so the box can serve the whole
# thing from one origin -- which is the only way to exercise the real frontend:
# console.js opens a WebSocket at /api/ws and falls back to polling /api/status,
# and neither works when the pages are served from a different port than the API.
# Testing the surfaces with curl proves the endpoints answer; it proves nothing
# about the JavaScript that has to render them.
if SITE.is_dir():
    app.mount("/", StaticFiles(directory=str(SITE), html=True), name="site")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info", access_log=False)
