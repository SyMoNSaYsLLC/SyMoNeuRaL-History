"""The HTTP surface. Mounted at `/api/sigils` by `api.py`; nothing here assumes that prefix.

A sigil is one small themed sticker: single subject, hard edges, **transparent background**.
The engine is the image surface's, the new part is the alpha channel, and the shape of this
module follows from two constraints that are not negotiable on this box.

**The card is held for a job, never for a process lifetime.** The render runs under
`scripts/gpu-governor.sh with sigil -- ...`, which releases on the way out even if the
engine crashes, and names its surface when it does. Everything after the render -- the
decode, the key, the despill, the encode, the write -- happens with the lock already given
back, in a worker thread. A CPU post-process that kept the next tenant off the GPU would be
the same mistake as holding the lock for residency instead of for work.

**No content policy lives here.** The operator's instruction is explicit: there are to be no
filters or safeguards on this project until he has decided himself what should pass. The
bounds in this file are structural -- one job at a time, a canvas the card can actually
decode, a time budget so a wedged engine cannot hold the queue forever -- and they exist to
stop the box falling over, not to stop a prompt. `PROMPT_GATE` below is a seam and is
`None`; it is left empty deliberately rather than filled in with a policy nobody asked for.

**Written for a phone app as much as for this website.** No session, no cookie, no CSRF, no
referer check: every field a client needs is in the response body. The response carries a
`schema` tag so a client can branch on it forever, and new fields may be added but existing
names and types do not change meaning.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import secrets
import time
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import matte, png, render

log = logging.getLogger("symoneural.sigils")

router = APIRouter(tags=["sigils"])

#: An optional prompt gate, for the wiring engineer, and empty on purpose.
#:
#: `backend/api.py` applies one single condition to `/api/image` -- the intersection of a
#: child term and a sexual term, which is the one output that is illegal to produce -- and
#: nothing else. This surface reaches the same engine by a different route, so if that one
#: condition is wanted here too it is one line at the mount site:
#:
#:     sigils.routes.PROMPT_GATE = denied
#:
#: It is left unset here rather than copied, because copying it would be this package
#: deciding a content question that belongs to the operator, and he has said plainly that he
#: sets those himself. Unset means every prompt reaches the engine.
PROMPT_GATE: Callable[[str], bool] | None = None

#: One sigil job at a time in this process. The governor is the real, cross-process mutex --
#: this only stops a single client from queueing a dozen renders inside one worker and
#: turning the lock wait into a thundering herd. It is a resource cap, not a rate limit.
_JOB = asyncio.Lock()
_inflight = 0

#: The last completed job, as a real reading for `/state` and for the rack detail line.
#: `None` until something has actually run: an unmeasured surface reports that it has no
#: measurement, it does not invent an encouraging one.
_last: dict | None = None

MAX_PROMPT_CHARS = 100_000

#: Themed starting points. These are prompt text and nothing more -- no hidden model, no
#: separate weights, no curation of what else may be asked for. The page shows them as
#: buttons because "what do I type" is the real first obstacle on a generative surface.
PACKS: dict[str, list[str]] = {
    "rack": ["a server rack with glowing status lights",
             "a single GPU card, three fans, seen head on",
             "a coiled network cable",
             "a cooling fan blade"],
    "raven": ["a raven perched, wings folded",
              "a raven in flight, wings wide",
              "a raven's head in profile"],
    "bench": ["a torque screwdriver",
              "a thermal paste syringe",
              "a power supply with braided cables",
              "a mechanical keyboard keycap"],
    "weather": ["a storm cloud with one lightning bolt",
                "a crescent moon",
                "a sun with sharp rays"],
}


class SigilRequest(BaseModel):
    """One sticker. Bounds are clamped rather than refused, except an oversized prompt."""
    model_config = ConfigDict(extra="ignore")
    prompt: str = Field(..., max_length=MAX_PROMPT_CHARS,
                        description="The subject, and only the subject. A fixed sticker "
                                    "suffix is appended; the composed prompt comes back in "
                                    "the response so you can see exactly what was sent.",
                        examples=["a raven perched, wings folded"])
    key: Literal["magenta", "green"] = Field(
        "magenta",
        description="The field colour the subject is drawn on and keyed out of. Magenta is "
                    "far from foliage; green is far from skin and warm tones. Neither wins "
                    "on every subject, which is why both are here.")
    steps: int = Field(4, ge=1, le=100,
                       description="This engine is distilled for four. More costs time.")
    size: int = Field(512, ge=256, le=1024, multiple_of=64,
                      description="Square edge in pixels, and the canvas of the returned "
                                  "PNG. Must be a multiple of 64: the decoder downsamples "
                                  "by 8 and the transformer patches by 2.")
    seed: int | None = Field(None, ge=0, le=2**31 - 1,
                             description="Omit for random. Supply to reproduce a sticker.")


@router.get("/packs", summary="Themed starting prompts")
async def packs() -> dict:
    """The presets the page offers. Text only -- nothing here constrains what may be asked."""
    return {"schema": "sigil/packs/v1", "packs": PACKS,
            "suffix": render.SUFFIX, "keys": sorted(matte.KEYS)}


@router.post("/render", summary="Render one sticker with a transparent background")
async def make(body: SigilRequest) -> dict:
    """Render, release the card, then key the field out and write an RGBA PNG.

    The returned `url` is served by the image surface's `/api/gen/<name>` route, so the file
    is named in that route's shape deliberately: it is an exact-match regex against an
    attacker-controlled path segment and inventing a new prefix would 404 every sticker.

    **The URL is ephemeral and the contract says so.** Renders in that directory are pruned
    to the newest sixty, so a client that wants to keep a sticker must keep the bytes, not
    the link. That is stated here rather than discovered by a user whose saved sticker
    turned into a 404.
    """
    global _inflight, _last

    subject = body.prompt.strip()
    if not subject:
        raise HTTPException(400, "Say what the sticker should be of.")
    if not render.weights_present():
        raise HTTPException(503, "The image engine is not installed on this box.")
    prompt = render.compose(subject, body.key)
    if PROMPT_GATE is not None and PROMPT_GATE(prompt):
        raise HTTPException(400, "That prompt was refused by the gate this box is running.")

    # secrets, not the clock: seeding from int(time.time()) gave every render inside the
    # same wall-clock second an identical "random" seed.
    seed = body.seed if body.seed is not None else secrets.randbelow(2**31 - 1)
    stamp = int(time.time() * 1000)
    # The intermediate is the raw render: a subject on a solid field, which is precisely the
    # image that must never be served. It is named outside /api/gen's regex so it cannot be
    # fetched even by guessing, kept outside the `gen-*` glob so it does not count against
    # the gallery's retention, and unlinked in `finally` whatever happens.
    raw = render.RENDERS / render.raw_name(stamp, seed)
    out = render.RENDERS / render.output_name(stamp, seed)

    async with _JOB:
        _inflight += 1
        try:
            try:
                rc, err, wait_s, render_s = await render.run(
                    render.build_argv(prompt, raw, seed, body.steps, body.size))
            except render.Busy as exc:
                raise HTTPException(
                    503, f"Something else is using the GPU right now: {exc}") from None
            if rc != 0 or not raw.is_file():
                log.error("sigil render failed rc=%s: %s", rc,
                          err.decode("utf-8", "replace")[-800:])
                raise HTTPException(500, "The render failed.")
            # The card is already back: `with` released it when sd-cli exited. Everything
            # below is CPU work and it runs in a thread, because a quarter of a second of
            # byte-plane arithmetic on the event loop stalls the live status socket.
            result = await asyncio.to_thread(
                _finish, raw, out, body.key,
                {"model": render.MODEL_NAME, "seed": seed, "steps": body.steps,
                 "size": body.size, "prompt": prompt})
        finally:
            _inflight -= 1
            raw.unlink(missing_ok=True)

    doc = {
        "schema": "sigil/result/v1",
        "url": f"/api/gen/{out.name}",
        "subject": subject,
        "prompt": prompt,
        "suffix": render.SUFFIX.format(key=body.key, hex=render.KEY_HEX[body.key]),
        "model": render.MODEL_NAME,
        "seed": seed,
        "steps": body.steps,
        "size": body.size,
        "bytes": result["bytes"],
        # Kept apart on purpose: `queued_seconds` is how long another tenant had the card,
        # `render_seconds` is what this box actually took, and `matte_seconds` is CPU work
        # done with the card already handed back. Their sum is the visitor's wait; none of
        # the three means what either of the others means.
        "queued_seconds": round(wait_s, 2),
        "render_seconds": round(render_s, 2),
        "matte_seconds": result["matte_seconds"],
        "note": "the url is ephemeral -- renders are pruned to the newest 60, so keep the "
                "bytes rather than the link",
        **result["stats"],
    }
    _last = {k: doc[k] for k in ("key", "size", "steps", "render_seconds", "matte_seconds",
                                 "transparent_fraction", "degenerate", "bytes")}
    _last["at"] = time.time()
    return doc


def _finish(raw: pathlib.Path, out: pathlib.Path, key: str, provenance: dict) -> dict:
    """Decode, key, encode, write. Synchronous on purpose -- the caller puts it in a thread."""
    started = time.monotonic()
    width, height, planes = png.read(raw.read_bytes())
    rgba, stats = matte.cut(width, height, planes, key)
    # Provenance rides in the file's metadata, not in its pixels. `tools/build_gallery.py`
    # stamps a bar naming the model, size and seed onto homepage art; burning that into a
    # sticker would deface the thing being made, so the same facts go into tEXt chunks
    # instead and the sticker itself is untouched.
    blob = png.write_rgba(width, height, rgba, {
        "Software": "SyMoNeuRaL Sigils",
        "Model": str(provenance["model"]),
        "Seed": str(provenance["seed"]),
        "Steps": str(provenance["steps"]),
        "Canvas": f"{width}x{height}",
        "Key": key,
        "Prompt": provenance["prompt"],
    })
    out.write_bytes(blob)
    elapsed = time.monotonic() - started
    return {"bytes": len(blob), "matte_seconds": round(elapsed, 3), "stats": stats}


@router.get("/state", summary="What this surface can do, and what it last did")
async def state() -> dict:
    """Real readings only.

    `installed` is the weights and the engine actually being on disk, not this module being
    importable. `last` is `null` until a sticker has genuinely been made here -- an empty
    measurement is reported as empty rather than filled in with a plausible number.
    """
    return {
        "schema": "sigil/state/v1",
        "installed": render.weights_present(),
        "surface": render.SURFACE,
        "busy": _inflight > 0,
        "keys": sorted(matte.KEYS),
        "matte": "chroma key, CPU, standard library only",
        "last": _last,
    }


def status() -> dict:
    """The rack unit, as a plain dict. Called on every rack poll -- synchronous and cheap.

    Deliberately **not** built from `api.py`'s `Unit` model: importing it would put this
    module inside `api.py`'s import graph and outside the scope this module was built in.
    The keys match `Unit`'s fields so the wiring engineer can splat it in as
    `Unit(**sigils.status())`.

    The state is a reading, not a decoration:
      * `offline` when the engine or a weight file is missing -- the surface genuinely
        cannot work, and says so rather than showing an encouraging light;
      * `busy` while a render is actually in flight;
      * `ready` otherwise.
    It is never `ready` on the strength of the module importing.
    """
    if not render.weights_present():
        state_, detail = "offline", "image engine not installed on this box"
    elif _inflight:
        state_, detail = "busy", "keying one sticker · the card is released before the matte"
    else:
        state_, detail = "ready", ("512px stickers with a real alpha channel · "
                                   "the matte is CPU work and never takes the card")
    return {
        "id": "sigils",
        "label": "SyMoNeuRaL Sigils",
        "slot": "1U",
        "state": state_,
        "bus": "gpu",
        "href": "/sigils.html",
        "spec": "SymonImage F1 → chroma key → RGBA PNG",
        "detail": detail,
    }
