# The rack roster

The rack has **thirteen rows**, and this file is where they are written down. It exists
because the roster was living in four places that could disagree — `backend/apps/` on disk,
the hand-written `Unit(...)` rows in `api.py:build_status()`, `apps/controlboard`'s
`TOGGLEABLE`, and `apps/test_status_rack.py`'s hand-typed `EXPECTED` — and three lists that
disagree is the three-state-documents failure with a different filename.

This file does **not** replace those. It is the fourth copy made deliberate: read by
`tools/build_rack.py` so the pre-JS fallback stops carrying rows by hand, and reconciled
against `api.py` and the directory by `apps/test_roster.py`. The other copies stay
independent on purpose — a tripwire wired to the thing it is watching is not a tripwire.

Live state is **not** here and must never be. Every reading a visitor sees comes from
`/api/status`, which measures it. This file carries identity only: what the row is, where it
points, how much rack it occupies.

## The rows

Read in the order `build_status()` emits them, which is the order the rack renders.

| id | label | slot | bus | href | implementation | toggle |
|---|---|---|---|---|---|---|
| chat | SyMoNeuRaL Chat | 1U | gpu | /chat.html | backend/api.py | yes |
| image | SyMoNeuRaL Image | 2U | gpu | /image.html | backend/api.py | yes |
| remix | SyMoNeuRaL Remix | 1U | gpu | /remix.html | backend/apps/remix | yes |
| ravencalc | SyMoNeuRaL RavenCalc | 1U | cpu | /ravencalc.html | backend/apps/ravencalc | yes |
| train | SyMoNeuRaL Reinforce | 2U | gpu | /reinforce.html | backend/api.py | no |
| miner | SyMoNeuRaL Miner | 6U | gpu | /miner.html | backend/apps/cryptominer | no |
| streamer | SyMoNeuRaL Streamer | 1U | net | /streamer.html | backend/apps/streamer | no |
| coder | SyMoNeuRaL Coder | 1U | cpu | /documentation.html | backend/apps/coder | no |
| gateway | SyMoNeuRaL Gateway | 1U | net | /gateway.html | backend/apps/gateway | no |
| project | SyMoNeuRaL Project | 1U | cpu | /project.html | backend/apps/project | no |
| sigils | SyMoNeuRaL Sigils | 1U | gpu | /sigils.html | backend/apps/sigils | yes |
| studio | SyMoNeuRaL Studio | 1U | gpu | /studio | backend/apps/studio | no |
| exp | SyMoNeuRaL Exp | 1U | cpu | /exp | backend/apps/studio/plugins/exp | no |

Thirteen rows, twenty rack units. The slot figures are what the one-screen budget is spent
on; `.claude/HANDOVER.md` §0 has the viewport table and says fourteen rows fit everywhere.

### Things that column will mislead you about if you read it too fast

**`bus` for `streamer` is `net` here and `cpu` in the module.** `apps/streamer.status()`
returns `bus="cpu"` and `api.py` overrides it at the call site with
`Unit(**{**streamer.status(), "bus": "net"})`. `net` is the truth about the row — an IPTV
surface is bound by the network, not by this box's cores — so `net` is what is written down.
The override is the disagreement, not a bug, and `test_roster.py` knows about it by name
rather than skipping the row.

**`implementation` is where the code is, not a package name.** Four rows are served straight
out of `backend/api.py` and have no directory under `backend/apps/` at all: `chat`, `image`
and `train` are the GPU tenants the API owns directly, and `miner` is one row over two
directories (see below). Two more have a directory that is deliberately **not** a Python
package: `ravencalc/` holds a bare `ravencalc.py` that `api.py` reaches by inserting the
directory on `sys.path`, and `remix/` is a whole sub-project with its own `pyproject.toml`
and its own test suite. Neither has an `__init__.py`, and a roster built by looking for
`__init__.py` files silently drops both — which is exactly how this file came to be needed.

**`toggle` is a cross-check, not the source.** The authority is `TOGGLEABLE` in
`apps/controlboard/__init__.py`, which carries the reasoning for every exclusion:
`train` because interrupting a fine-tune mid-epoch is destructive, `miner` because one row
spans a GPU half and an ASIC half, and coder/gateway/project because they are already
config-gated and an operator override would be a second source of truth for the same LED.
`test_roster.py` asserts the column and the tuple agree. Two hand-maintained copies and a
test that they match is the point; deriving one from the other would delete the check.

## What is under `backend/apps/` and is deliberately not a rack row

A directory here is not a claim to a row on the front page. These are not omissions:

- **`voice`** — `status()` is written and correct, but its `href` is `/voice.html` and that
  page does not exist, so the row would be a dead link on the front page. `api.py` says so
  at its `include_router` call. It gets a row when the page lands.
- **`cryptominer`** and **`asicminer`** — the two halves of the single `miner` row. The row
  reports one state derived from both, and the detail line always names both in the same
  order, so a reading from one can never be mistaken for a reading from the other.
- **`discovery`** and **`reinforce`** (under `studio/plugins/`) — Studio plugins. `exp` is
  the only plugin with a row of its own.
- **`accounts`**, **`capture`**, **`controlboard`**, **`licensing`**, **`news`** —
  infrastructure behind the surfaces, not surfaces. `controlboard` *drives* the rack's
  operator overrides; a row for it would be the rack reporting on itself. `news` renders the
  site's ticker, which is a site surface rather than a rack unit — that is why it moved out
  of `apps/symoneuralnews` and why it has no row.

## Adding a row

1. Add the `Unit(...)` to `build_status()` in `backend/api.py`, or the `status()` to the
   module, and make sure the page in `href` exists first. A row pointing at a 404 is worse
   than no row.
2. Add the line here, in emit order.
3. Type the new id into `EXPECTED` in `apps/test_status_rack.py` **and** the new count into
   the comment above it. That is the tripwire, and typing the number is the point of it.
4. Run `python3 tools/build_rack.py` twice, diff, then `python3 tools/build_cachebust.py`.
5. Check the one-screen budget: `.claude/HANDOVER.md` §0. Measure with a cloned `.unit`,
   never with `scrollHeight` — it floors at `clientHeight`, so it says "fits" and nothing
   about by how much.
