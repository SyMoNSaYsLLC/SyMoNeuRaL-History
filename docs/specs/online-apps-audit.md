# Online applications — test pass and audit, 2026-08-17

**Findings, not state.** `.claude/HANDOVER.md` is the one state document and `.claude/CLAUDE.md`
the one rulebook; read this as an argument to evaluate. One fix was made and is described in §4;
everything else here is a report, and several items are explicitly somebody else's file.

**Brief:** *"review all online applications, test them and upgrade them if possible. They seem to
be working but have slight bugs here and there."*

**Short answer: they are working.** 652 backend tests across eleven suites, 26 browser
assertions against the local origin and against production, and a crawl of every reference on
eighteen pages. One genuine defect was found on a public route, diagnosed to its root cause and
fixed with tests (§4). The rest of what looked wrong was either designed, already fixed on disk,
or a fault in my own probe — three of those, recorded in §6 because that is the more useful half.

**Eight other agents were writing this repo during this pass.** Per HANDOVER §0c, files another
agent holds are reported rather than edited. §5 is that list.

---

## 1. Method, so the numbers can be re-taken

| What | How |
|---|---|
| Backend suites | `python3 -m unittest discover -s backend/apps/<app> -p 'test_*.py'`, all eleven |
| Browser, local | `node tests/frontend.mjs` |
| Browser, production | `node tests/frontend.mjs https://symoneural.com` |
| Every route | probed each path in `/openapi.json`, reading the body and not only the status |
| Every reference | a crawler over eighteen pages, both origins, checking each `href`/`src` |

All timings and counts below are **measured on this box**, 2026-08-17 between 13:45 and 14:20.

**One fact that reframes "local versus production", and it is not in HANDOVER:** for anything
under `/api`, *there is only one process*. Caddy reverse-proxies `/api/*` to `127.0.0.1:8800`,
which is the same uvicorn the loopback tests hit — verified by comparing `/api/status` and
`/openapi.json` across both origins, and by the GPU panel reading the same VRAM from each. So the
four states an agent has to keep apart are really **working tree → running API process** for
backend behaviour and **`site/` → deployed webroot** for pages. An API change is invisible to both
origins until a restart; a page change is invisible to production only. Reasoning about
`/api/...` as "local versus live" is what produces the hour-long confusions §0c describes.

---

## 2. Result per surface

Twelve rack units, read from `/api/status`. "Online" below means the surface answers; whether it
has a page of its own is a separate column because those two have been conflated.

| Unit | State | Answers correctly | Note |
|---|---|---|---|
| `chat` | ready | yes | 12-unit rack, GPU panel live |
| `image` | ready | yes | a render decodes end to end in the browser suite |
| `remix` | ready | yes | client of the chat surface, not its own tenant |
| `ravencalc` | ready | **one defect, fixed — §4** | exact SymPy; `x**3/3` verified on the page |
| `train` | ready | yes | never evicted for a page view |
| `asicminer` | offline | by design | fail-closed: needs `SYM_ASIC_ENABLED=1` **and** `SYM_ASIC_TOKEN` |
| `gpuminer` | ready | yes | control gated: `401` without `SYM_MINER_TOKEN`, correct |
| `tuner` | ready | yes | suite caught mid-edit by another agent — §3 |
| `coder` | offline | by design | deliberately has **no HTTP route** at all; see `api.py:1493` |
| `gateway` | offline | by design | needs network + contract configured |
| `guide` | ready | yes | **already in the live stack**; see below |
| `project` | offline | by design | needs `SYM_PROJECT_ENABLED=1` and a token |

### The four `503`s are correct, and this is worth stating rather than assuming

Each one is fail-closed *and* actionable — it names the environment variables that would switch
it on and, in `project`'s case, the README to read first:

```
/api/gateway/state      503  "gateway surface is off — set SYM_GATEWAY_ENABLED=1, SYM_GATEWAY_NETWORK
                              and SYM_GATEWAY_CONTRACT, then restart the service"
/api/project/state      503  {"ok":false,"code":"disabled","error":"surface disabled — set
                              SYM_PROJECT_ENABLED=1 and SYM_PROJECT_TOKEN, and read
                              backend/apps/project/README.md first"}
/api/accounts/me        503  "accounts are not switched on for this box"
/api/asicminer/firmware 503  "the miner surface is disabled on this installation"
```

`GET /api/accounts/status` answering **200** beside `/api/accounts/me` answering 503 looks
inconsistent and is right: `status` is the public "are accounts open here?" question, and it
answers honestly — `{"enabled":false, "note":"this box has not been given a session secret, so
accounts are closed"}`. A gate that cannot be interrogated without authenticating is a gate
nobody can debug.

### SyMoNeuRaL Guide is already in the live stack — nothing to add

Asked directly during this pass. Production `/api/status` returns it as unit 11 of 12:

```json
{"id":"guide","label":"SyMoNeuRaL Guide","slot":"1U","state":"ready","bus":"cpu",
 "href":"/tuner.html","spec":"question → channel filter · CPU",
 "detail":"CPU/stdlib matching — no weights of its own, never takes the GPU lock; the optional
           model pass borrows the chat surface"}
```

`grep Guide` against the deployed `/livestack` **returns nothing**, which is not a contradiction
and is the trap worth knowing: the rack is rendered client-side by `console.js` from
`/api/status`, so no unit label exists in the static HTML for any of the twelve. The browser suite
is the check that means anything here, and it reads `SyMoNeuRaL Guide=CPU` off the rendered bus
plate. Its `href` points at `/tuner.html` because Guide is the tuner's question-to-filter pass
rather than a surface with a page of its own.

Verified working rather than merely present:

```
POST /api/guide/filter  {"question":"live football tonight", channels:[ESPN HD, CNN, SKY SPORTS PL]}
  -> {"match":["football","tonight"], "kind":"live", "source":"fallback", "model_used":false,
      "why":"no model was available, so this matched your own words directly: football, tonight"}
```

Note `source` and `model_used`: the surface says outright when it fell back to plain word
matching instead of the model, which is the §2c-bis lesson (a feature whose happy path never runs
looks fine until someone measures it) encoded as a field. `POST /api/guide/catalogue` refuses with
*"send the channel list to filter; this box stores none"* — the no-storage claim enforced rather
than asserted.

---

## 3. Test results

### Backend — 652 tests, eleven suites

```
accounts     46 OK       asicminer    42 OK       coder        46 OK
cryptominer  72 OK       gateway      57 OK       guide        50 OK
licensing    21 OK       project     102 OK       reinforce    69 -- 1 failure
sigils       24 -- 1 failure           tuner      123 -- 1 failure, 1 error
```

Three reds, and **none of them is a new regression**:

1. **`reinforce`** — the documented `test_alpha_is_twice_rank_everywhere` failure (`48 != 64` for
   `preset='recall'`). HANDOVER §1 says explicitly: ask before choosing which side is wrong. Left
   alone. **A discovery artifact to discount:** `unittest discover` also imports `bench/`,
   `symoneural/` and `tests/` as packages, and those `import cupy`, which is not installed — so
   my run showed *six extra ImportErrors* that are an artifact of the invocation, not code
   faults. Run `test_reinforce.py` directly to see the real picture. Recorded because six
   fabricated errors landing in a report would read as six regressions to the agent who owns
   that file.
2. **`sigils`** — the documented despill boundary (`230 not less than 230`). HANDOVER says settle
   it by deciding what the correct despill output *is*, not by moving the threshold. Nobody held
   this file during the pass, and that is still not permission. Left alone.
3. **`tuner`** — 123 tests where HANDOVER records 121. Another agent was mid-build on the
   EPG work (`backend/apps/tuner/epg.py` did not exist when the running API started). This is a
   snapshot of somebody's work in progress, timestamped, **not a bug report**.

### Browser — the assertion that counts

```
local        26/26   13:55
production   25/26   13:58   -- before Garrett's 14:01 deploy
production   26/26   14:20   -- after it. The two origins now agree.
```

The single production failure, measured before the deploy, was the Live stack section
overflowing its panel:

```
livestack @1855x745   595 / 592     (3px over)
livestack @1301x740   619 / 587     (32px over)
```

against `587/587` and `589/589` locally at the same viewports. Same API process, so this was the
deployed stylesheet being older than `site/symoneural.css` — the pending-deploy state, not a code
defect. **The deploy confirmed the diagnosis**: re-running against production afterwards gives
26/26 with no change to any file. That is exactly why HANDOVER insists the two runs must agree —
the disagreement *was* the finding, and it named its own cause.

### Every reference on every page resolves — both origins

```
local        18 pages, 58 distinct references, 373 checks -- all resolve
production   18 pages, 58 distinct references, 373 checks -- all resolve   (after the 14:01 deploy)
```

This is HANDOVER §0c item 5 ("verify every link works") discharged. Identical reference counts
across the two origins is itself a useful signal — it means the cache-bust stamps agree, i.e.
the webroot and `site/` are in step.

### Seven pages are live and unreachable by clicking

The broken-link check passes on these *because* no reference to them exists to be broken, so it
needs saying separately:

```
/index.html  /image.html  /ravencalc.html  /remix.html  /miner.html  /gateway.html  /sigils.html
```

`/index.html` is deliberate and documented (HANDOVER §5 item 0b — `/` redirects to `/overview`
and the tabbed page survives as a build input). The other six are not documented as deliberate.
A concurrent session reported the same six independently and is adding image, ravencalc and remix
to the nav in `tools/build_pages.py`; miner, gateway and sigils belong to other active sessions.
**Not edited here** — three writers in one generator is the clobber CLAUDE.md warns about.

Related trap, confirmed by that session and consistent with everything measured here:
`/sigils.html` answers 200 but **`/sigils` 404s**, because Caddy serves `*.html` off disk with no
config while an extensionless top-level path only reaches FastAPI if `ops/Caddyfile` delegates it.
No page links to an undelegated extensionless path today — the crawl above would have caught it.

---

## 4. The one real defect, and the fix

**`POST /api/ravencalc` returned `500 Internal Server Error` on ordinary mathematics a visitor
can type.** Public, unauthenticated, and the only 5xx found anywhere in the pass.

```
{"expression":"factorial(99999)"}  -> 500   (12 ms -- it fails immediately, so not a slow path)
{"expression":"factorial(3000)"}   -> 500
{"expression":"2**200000"}         -> 500
```

Every *other* bad input was already handled well, which is what made this stand out rather than
look like a general absence of error handling:

```
"x**"                            -> 400  "cannot parse that expression"
""                               -> 422  "request document is not valid"
'__import__("os").system("id")'  -> 400  "expression contains characters this engine does not accept"
"1/0"                            -> 200  zoo          (correct: complex infinity)
```

### Root cause

Not sympy, and not the parser. **CPython 3.11+ refuses to convert an integer wider than 4,300
digits to a string** — `sys.get_int_max_str_digits()`, the CVE-2020-10735 mitigation, because the
conversion is quadratic. It is an *interpreter* limit, so it fires inside sympy's printer, which
is **after** the mathematics has already succeeded:

```
File "sympy/printing/str.py", line 679, in _print_Integer
    return str(expr.p)
ValueError: Exceeds the limit (4300 digits) for integer string conversion
```

`factorial(3000)` is 9,131 digits. The engine computed it exactly and correctly, then died on the
way out. `run_request`'s own docstring is the standard this breaks: *"Raises `RavenCalcError` for
anything a caller can fix … and lets nothing else out silently."*

### What was changed — `backend/apps/ravencalc/ravencalc.py` only

`api.py` already maps `RavenCalcError` to a 400, so the whole fix fits inside the engine and the
coordinate-first file was not touched.

- **`_rendered` refuses, and names both numbers.** All three renderings (`text`, `latex`, `tree`)
  go through the integer printer, so one guard covers them. The refusal says the answer is about
  9,131 digits *and* that this interpreter prints 4,300 — "too wide" alone gives a caller nothing
  to act on.
- **`_evaluate`'s note degrades instead of refusing.** `evaluate` at `x: 3000` with `digits: 20`
  returns a 20-digit Float that prints perfectly; only the exact pre-rounding form behind it is
  too wide. Refusing the whole request there would discard a good answer, so the note says what
  it could not show and how wide it was. A note reading `exact form before rounding:` followed by
  nothing would be the `text-overflow:ellipsis` bug wearing a different hat.
- **The width is estimated from `bit_length`, never measured.** This is the part worth keeping:
  the obvious exact count, `Decimal(n).adjusted() + 1`, **takes 11.8 s on 99999! measured on this
  box**, so counting the digits exactly in order to refuse would hand a visitor the denial of
  service the interpreter's limit exists to prevent. `bit_length` is O(1). It agreed exactly with
  the independent `Decimal` count (both 9,131), and can sit one digit either side near a power of
  ten — which is why every message says **"about"**. An engine whose argument is exactness does
  not quote an estimate as a measurement.
- **Raising the interpreter's limit was the other available fix and is deliberately not taken.**
  `sys.set_int_max_str_digits()` would make the 500 into a 200 and re-open the quadratic cost on
  an unauthenticated public route. A visitor can type `2**200000` as easily as `2+2`.
- **The guard is layered**, matching how `parse` is written: the estimate refuses before the
  printer is asked, and a narrow `except` catches an integer the estimate failed to find rather
  than letting a bare `ValueError` escape.

### Tests — a new file, because this app was the one with none

Every other surface in `backend/apps/` carries a `test_<app>.py`; `ravencalc` did not, which is
plausibly why this survived. `backend/apps/ravencalc/test_ravencalc.py`, **14 tests, all green**,
covering the defect, the note that must survive, and the refusals that were already right so the
new guard cannot loosen them.

**Verified non-vacuous.** With the fix stashed and the tests unchanged: **3 failures and 6
errors**. With it: 14/14. The suite asserts `RavenCalcError` *specifically* rather than
`ValueError`, because `RavenCalcError` subclasses `ValueError` — so `assertRaises(ValueError)`
would have passed before and after the fix and proved nothing. That is the vacuous-assertion trap
§3.0 records three times, met in a fourth costume.

---

## 5. Reported, not touched — other agents hold these files

| Finding | Whose |
|---|---|
| `reinforce` alpha/rank red test — needs Garrett's decision, not an edit | reinforce session |
| `tuner` suite red mid-EPG-build — a work-in-progress snapshot | tuner session |
| miner, gateway, sigils pages have no inbound links | those sessions |
| `sigils` despill boundary — settle the correct output first | unowned, still not licence to guess |

Nothing under `backend/api.py`, `ops/Caddyfile` or `scripts/deploy.sh` was edited: HANDOVER §0c
marks all three coordinate-first, and the ravencalc fix was deliberately shaped to stay out of
`api.py`.

**The generator chain was deliberately not run**, so no idempotency check was performed this pass.
`tools/build_*.py` rewrite files under `site/` and a typography/spacing session was editing that
directory throughout; two writers there lose one of the two edits silently. Whoever next has
`site/` to themselves should run the eleven-generator double-run diff from HANDOVER §6.

---

## 6. Three of my own probes failed on healthy input

HANDOVER §3.0d lists five verification steps that shouted while the system was correct, and notes
that the damage is cumulative — a check that cries wolf trains the reader to skip the block. Three
more, caught before they reached this report:

1. **`data-src="measured"` matched as `src="measured"`.** A regex of `(?:href|src)="([^"]+)"`
   matches the tail of any `data-src` attribute, so the crawler reported five broken links on the
   control board. Those are the provenance tags — `measured` / `vendor` / `projected`, the ones
   CLAUDE.md forbids folding away — and they are data attributes, not references. Fixed with a
   boundary: `(?:^|[\s"'])`.
2. **A `HEAD` probe reported `/docs`, `/livestack` and `/controlboard` as 404** while all three
   answer `GET` with 200. Measure the method a visitor actually uses.
3. **`/sigils.html` 404ing on production** was true when measured at 13:50 and false by 14:01,
   because Garrett deployed in between. Re-measured rather than reported.

The generalisation, which is the same one that file already draws: **a probe is a claim about the
system and needs its own evidence.** Both halves, every time — that it goes red on the real bug
*and* green on healthy input.

---

## 7. The tuner video failure — measured, not yet solved

Reported during this pass: *"you video isnt working"*, then *"ive noticed most the issues are with
the adult live tv"*. **The tuner is another session's file and none of it was edited here.** What
follows is measurement handed to that session.

### The pipeline is sound; the failure is channel-specific

A working channel, probed by fetching every segment the playlist advertises and running `ffprobe`
on one:

```
AMC (WEST)   6/6 segments served, ~1.1 MB each
             h264 High 1280x720  +  aac LC 48 kHz stereo      segment_s 2.002
```

A failing channel, from `/api/tuner/state` while it was live:

```
STARS EXCLUSIVE: LENA PAUL   state live · vcodec h264 · 87.0 MB in over 5 min · segments 6
                             segment_s 6.54          <- the one number that differs
browser:                     0 frames decoded, player at 0:00, and NO error banner
```

So data flows, the session is healthy, and the video codec is the one codec every browser plays.

### The prime suspect is audio, and it is unpublished

`sessions.py` parses `acodec` and its own comment says it is *"parsed but not published … three
lines cheaper to have ready than to add later"*. `public()` publishes `vcodec` only, and
`build_pages.py`'s `UNPLAYABLE` map is video-only — `{hevc, h265, av1, mpeg2video, vc1}`.

An AC-3 / E-AC-3 / MP2 / DTS soundtrack on an h264 stream reproduces every observable: server
indicators all green, `vcodec` reassuringly `h264`, hls.js unable to append the source buffer,
zero frames decoded, and **a page with nothing to warn about because it never sees the audio
codec**. That is this repo's recurring shape — a diagnosis that exists, is correct, and is
unreachable on the one axis that was left unpublished.

**Not confirmed**, and the reason is worth recording: a session is reaped 12 s after the tab goes
idle and its temporary directory goes with it, so a probe arriving later finds nothing. One
`ffprobe` on a segment from a failing channel held open ~30 s settles it.

### GPU transcode — approved, and the hardware says it need not take the lock

Garrett was given the trade-off explicitly and chose full GPU transcode over audio-only-on-CPU.
Capability is **measured present**, with nothing to build:

```
encode   h264_nvenc  hevc_nvenc  av1_nvenc
decode   h264_cuvid  hevc_cuvid  mpeg2_cuvid  vc1_cuvid  vp9_cuvid
```

The decode list is the useful half — `hevc_cuvid`, `mpeg2_cuvid` and `vc1_cuvid` are precisely the
codecs the page's `UNPLAYABLE` map exists to apologise for.

**The architectural finding: NVENC and NVDEC are dedicated ASIC blocks, not CUDA compute.**
Measured while the `image` surface held the governor lock with the GPU at 67% compute
utilisation, `nvidia-smi` reported **encoder 0%, decoder 0%**. Those units are idle and
independent of what the governor arbitrates. A transcoding tuner therefore needs a **VRAM budget**
(a few hundred MB per 1080p stream), not exclusive possession of the card — so the "a stream holds
its lease for its whole lifetime" objection, which is real for the miner, probably does not apply
here. Taking the exclusive lock for a transcode would serialise video behind model inference for
no hardware reason, which is the opposite of why "the tuner never takes the lock" was right.

It does still falsify the page's *"Tuner does not use the GPU"*. The honest replacement is that it
uses the **video engine**, not the compute the models share — which is both true and a better
claim.

**No throughput number was taken, deliberately.** The card was busy with another session's image
work throughout, and a contended measurement is a contaminated one. The clean run, to be labelled
`measured` and taken before anything is promised on a page:

```bash
ffmpeg -hwaccel cuda -hwaccel_output_format cuda -c:v hevc_cuvid -i <sample.ts> \
       -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -f null -
nvidia-smi --query-gpu=memory.used,utilization.encoder,utilization.decoder --format=csv -l 1
```

Report it as **x-realtime and MB of VRAM per stream**; that settles the concurrency ceiling.

### yuki-iptv and VLC — references to read, not code to port

Asked for during this pass. Both were checked, because the answer changes the design:

| Reference | Licence | How it plays video |
|---|---|---|
| `references/IPTV/yuki-iptv/` | **GPLv3** (Astroncia / yuki-chan-nya) | **libmpv** — 186 mpv references in `yuki-copy.py` |
| `references/IPTV/vlc-master/` | **GPLv2** | already rejected, HANDOVER §2c-bis and `LICENSES.md` |

They play everything because they are **native players with a complete codec set** — mpv decodes
HEVC, AC-3, MPEG-2 without asking. A browser cannot copy that, so there is no code to port; and
porting it into `site/` would be the copyleft problem the VLC decision already turned down. What
transfers is the approach, and it is the same conclusion as the transcode work: stop assuming the
browser can decode the stream, detect what arrived, and convert the rest.

### One housekeeping leak

**165 empty `/tmp/tuner-run-*` directories.** Segment contents are cleaned when a session is
reaped; the directory itself is not. Harmless today, unbounded over time.

---

## 8. Reproducing this pass

```bash
# backend, all eleven suites
for a in accounts asicminer coder cryptominer gateway guide licensing project reinforce sigils tuner; do
  python3 -m unittest discover -s backend/apps/$a -p 'test_*.py' 2>&1 | tail -3; done

# the new one
python3 -m unittest discover -s backend/apps/ravencalc -p 'test_*.py'

# browser, both origins -- these must agree
node tests/frontend.mjs
node tests/frontend.mjs https://symoneural.com
```

The link/orphan crawler used here was a scratch probe and was not kept; it is ~60 lines of
`fetch` over the eighteen-page list, and §6 item 1 is the only subtlety in writing another.
Worth promoting into `tests/` if link rot becomes a recurring theme, in which case fold the
orphan check in with it — the broken-link pass is silent about orphans by construction.
