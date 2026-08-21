# SyMoNeuRaL — working agreements

Repo for symoneural.com: the public site, the live API behind it, the CUDA engine, and
the engineering manual the site's numbers come from.

## START HERE — you have just been opened in this repo and Garrett said "hi"

Do not ask him what to work on. He has already answered, standing, 2026-08-20: *"i want to
be able to cd /Symoneural lauch claude and say hi and the agent already know what we need to
do"*. Everything you need is on disk. Read it, then say what you are picking up and why.

**Three commands, in this order.** They take about a minute and they answer "what is the
state of this project" without a single question.

```bash
python3 tools/build_progress.py     # rebuild the page from the disk -- never trust a stale one
xdg-open run/progress.html          # or open file:///home/google/Symoneural/run/progress.html
sed -n '1,80p' PROJECT-TASKS.md     # the standing rules for the task list itself
```

`run/progress.html` is the handover artefact and it is deliberately complete. Garrett:
*"with our progress.html even if my computer blows up the next agent will have exactly what
it needs to pick up the project and not miss a beat"*. It renders every open task with a
**measured** percentage, every assignment waiting on him, the request ledger's depth, the
four test suites with the commit each count was read on, and the comments people have left
on individual tasks. It is generated from the files below, so it cannot drift from them; if
it looks wrong, the file it reads is wrong and that is the bug.

**Then pick up work like this:**

1. Open **`PROJECT-TASKS.md`**. That is the only place work comes from. Take the lowest-
   numbered open task whose blockers are clear, or the one Garrett just named.
2. Anything not on that list is **not yours to start**, however obviously useful. The way in
   is `INTAKE.md`, and the gate is Garrett ticking a box — not your judgement that it is
   worth doing. This is the one rule that keeps the list meaning what it says.
3. Work the task. When behaviour changes, prove it changed: break it on purpose and watch a
   test fail, then fix it. A test that passes before and after your change tested nothing.
4. Regenerate and commit — see *Completing a task*, below.

**The one thing to be suspicious of on arrival:** a figure with no commit SHA beside it. This
project has published a test count that was never true of the commit it sat next to, because
somebody carried it forward and re-dated it. Re-measure anything you are about to rely on.

## The two surfaces, and how to complete a task

There are exactly two lists, they have different owners, and conflating them is the failure
this structure exists to prevent.

```
INTAKE.md         assignments: requests, questions, audit findings.   GARRETT ticks.
PROJECT-TASKS.md  numbered tasks.                                     THE AGENT works.

assignment  ->  (answer, if it is a question)  ->  [x] Ready  ->  task #NN  ->  done
```

**Every entry is in exactly one of three states: `done`, `task`, or `intake`.** There is no
fourth. "Pending" is a marker on a task, not a place to put something. An assignment that is
neither carried by a task nor dropped is a **barrier** — recorded and uncarried — and the
page counts them in red at the top, because an uncounted barrier is how work goes missing.
The count was 58 on 2026-08-20 and is 0; keep it there.

### Working a task

Tasks live in `PROJECT-TASKS.md` as `◻ #41 — Title` with an **indented** detail block. The
indentation is structural, not cosmetic: `tools/archive_tasks.py` ends a task's block at the
first non-blank column-zero line, so an unindented line silently truncates its own task and
takes every line under it out of the task.

Declare machine checks so the percentage is measured rather than asserted:

```
◻ #62 — Per-app artefacts
        owner: coder                        coder | garrett; unlabelled means coder
        check: exists backend/apps          also: absent <path>
        check: grep <pat> -- <path>         also: ngrep (true when NOT found)
        check: maxcount <n> <pat> -- <path>
        resolve: OLD -> NEW                 state read from disk: NEW present, OLD gone
        note: 2026-08-20 garrett — comment  append-only; see the comments box below
```

The percentage is passing checks over declared checks, recomputed from the disk every two
minutes. A task with no checks reads `—`, never `0%`, because an unmeasured task is not an
unstarted one. **Choose checks where 100% genuinely means done** — a check that can pass
without the work being finished is worse than no check, since it will archive the task.

**If the deliverable is a program that runs, one check must be something only a real run can
turn green.** `exists`, `grep` and `ngrep` ask what is written on disk; none of them can ask
whether the thing works. #94 shipped a desktop client whose eighteen checks all went green and
whose chat surface was dead on arrival — a missing Tauri capability meant the page was never
permitted to hear the stream it had asked for, so it rendered a turn and then nothing, with no
error to read. The timer archived it two minutes later. #74 did the same at `87c4042` with two
of seven items not started. The cheap fix is a stamped smoke record committed beside the code —
`check: exists <dir>/SMOKE.md` — because that file cannot be written honestly without running
the thing. Note that a `note:` explaining the checks are insufficient does **not** help:
`archive_tasks.py` reads checks, not notes, and #94's note said exactly that and was ignored.

At 100% `archive_tasks.py` moves the block to `review/CLOSED-TASKS.md` verbatim with a line
saying what judged it finished. Nothing is deleted; the list stays a reading of what is left.

### Completing a task — the sequence, every time

```bash
python3 tools/build_intake.py        # assignments  -> INTAKE.md (+ review/RETIRED-*.md)
python3 tools/build_progress.py      # everything   -> run/progress.html
# run BOTH twice and diff: these generators re-read their own output, and one that does
# not recognise something it emits will accumulate it, one copy per run. That bug has
# now happened three times in this repo. Two runs with no diff is the check that catches it.
cd backend && python3 -m pytest apps/test_build_progress.py -q
```

Then commit, with the reason in the message — `git log` is the answer to "why is the code
like this" and is load-bearing here. Commit **between** items, not in one batch at the end.

### Ready and Drop — the two controls on the page, and nothing else

`run/progress.html` renders each assignment with two buttons, which POST to
`/local/intake` and write `INTAKE.md` directly.

- **Ready** (`[x]`) — Garrett judges it ready to become work. You then give it a task number.
- **Drop** (`[-]`) — not needed. The entry is **removed** from the list and written to
  `review/RETIRED-ASSIGNMENTS.md` with everything typed on it. Removed, not struck through:
  *"i click drop and it doesnt remove from intake list"* was reported as a bug and fixed.

**Do not invent a third state.** A "frozen"/"deferred"/"parked" bucket was proposed and
rejected outright, and the reason generalises: a third state takes the decision away from
Garrett while looking like it recorded one. If something cannot be carried, it is dropped
with a reason, and the reason goes in the file.

His standing test for whether an assignment should exist at all: *"if it isnt going to break
our project and its something that will resolve itself naturally DROP IT"*. A rule already
written down is not outstanding work. A request already satisfied is not outstanding work.

### Assigning work to another agent

Tasks are labelled `owner: coder` or `owner: garrett`, and **a coder-owned task can be handed
to any coding agent** — that is what the label is for. Unlabelled means coder: the default
claims work rather than parking it on Garrett.

`owner: garrett` is reserved for exactly five things, and nothing else qualifies: physical
hardware access, credentials only he holds, third-party dashboards with no API, money, and
legal or business decisions. The standing rule is **FIX, not FILE** — filing a task back to
him because it is awkward is the failure mode this list is guarding against.

An agent picking up a `garrett` task should read its `[ ]` checkbox as a handoff: he ticks it
when he has done his half, which sets the state to `ready for review` — deliberately **not**
`done`, so the task cannot archive itself before anyone reads his answer.

### The comments box

Every task on the page has one. A comment is stored as an indented, append-only `note:` line
in that task's own detail block, so it lives beside the thing it is about and travels with it
in `git log`. Append-only means two people cannot overwrite each other and no generator run
can eat a comment. Keep the `note:` prefix on **every** line of a multi-line comment: an
unindented continuation would truncate the task, and a continuation reading `owner: garrett`
would be parsed as a directive instead of as somebody's words.

### Never do these to the task surface

- **Never create a second state document.** Three files once claimed to describe current
  state and agents kept acting on the stale one. If a harness offers you its own task list,
  it is a second state document; `PROJECT-TASKS.md` is the canonical one.
- **Never carry a figure forward and re-date it.** Re-run it or drop it.
- **Never hand-edit `INTAKE.md`'s skeleton** — it is generated. Ticks, answers, task numbers,
  briefs and prose are merged back over the top and preserved; everything else is rewritten.
- `INTAKE.md` and `GARRETT-REQUESTS.md` are **mode 600** and stay that way. `/api*` is proxied
  to the public internet by `ops/Caddyfile`, which is why the write endpoints are `/local/*`
  behind a peer-address check that also refuses proxy headers.

## Where to look — there is exactly one of each

Three files once all claimed to describe "current state" and agents kept acting on the stale
one. There is now one of each, and everything superseded lives in `docs/archive/` behind a
README that says so.

| Question | File |
|---|---|
| What are the rules? | **this file** |
| What is the state, what is left to do, what will bite me? | **`.claude/HANDOVER.md`** |
| What does the hardware actually do? | `docs/symoneural-manual.md`, and `docs/` |
| Why is the code like this? | **`git log`** — every commit states its reason |

Do not create a second state document. Update `.claude/HANDOVER.md`.

**`demo/` no longer exists.** It was flattened into the repo root: `demo/api.py` is `api.py`,
`demo/playground.sh` is `scripts/symoneural.sh`. Any path with `demo/` in it is from before that and
is wrong.

## Parallelise builds

**Run as many agents concurrently as quality allows.** Compiles, model downloads and fine-tunes
occupy the machine for tens of minutes; that wall-clock should be filled with independent work,
not spent watching a progress bar. Launch subagents in one message so they actually run in
parallel. The GPU is available to agents that genuinely need it.

Scope agents to files nobody else is writing. The real hazard here is the generator scripts:
`tools/build_pages.py`, `tools/build_rack.py`, `tools/build_console.py`, `tools/build_cost.py`, `tools/build_stack.py`,
`tools/build_training.py` and `tools/build_gallery.py` all rewrite files under `site/`, so two writers in
that directory will clobber each other. Safe parallel
tracks are read-only audits, brand-new standalone files, docs, and tests.

## The GPU is a single, contended resource

One RTX 5070 Ti, 15.92 GiB. Chat (~5 GB), image (~7 GB) and a QLoRA run (~12 GB) cannot coexist.

- Everything touching the GPU goes through `scripts/gpu-governor.sh`, ideally as
  `gpu-governor.sh with <surface> -- <cmd>`, which always releases even on crash.
- **Hold the lock for a job, never for a process lifetime.** Residency (weights loaded) and
  work (using the card) are separate. Holding the lock while a model is merely resident and
  idle locks every other process out — including the CLI — until the acquire timeout.
- **Never call a bare `release`.** Name the surface (`release chat`). An unscoped release once
  destroyed a running fine-tune's lock from the API's shutdown hook.
- The governor waits for VRAM to drain below a 1.5 GB floor between tenants. Killing a process
  returns the lock before CUDA has torn down, and the next tenant OOMs at step 0.
- `train` is never evicted to serve a page view.
- RavenCalc (SymPy, CPU) deliberately never takes the lock. That is what lets it speculatively
  pre-compute while the GPU is loading.

## Python environments

The **CUDA sample venv** at `contrib/cuda-samples/python/.venv` is pinned at exactly **7 packages** and
must never be extended:

```bash
contrib/cuda-samples/python/.venv/bin/pip freeze | wc -l    # expect exactly 7
```

`numba-cuda` silently downgrades numpy, and three other packages pin conflicting
`cuda-core`/`cuda-python` versions. (Earlier revisions of this file said "the base interpreter
is pinned at 7 packages, check with `pip freeze | wc -l`". That is wrong twice over: the bare
command runs against the **system** interpreter, which is a Debian install carrying 212
packages, and the count would never have been 7. Use the full path above.)

- The serving API deliberately uses only the **system** interpreter: fastapi, uvicorn, pydantic
  and sympy are already OS packages, so there is no virtualenv in the serving path. Do not
  `pip install` into it — the deny rules in `.claude/settings.local.json` block the bare forms
  precisely because a stray install there is hard to notice and hard to undo.
- Training has its own venv at `training/.venv` (torch cu128 — Blackwell sm_120 needs it).
- Anything else that conflicts gets its own isolated venv.

## Honesty rules for anything user-facing

These are the product, not decoration. The site's entire argument is that its numbers are real.

- Label every figure: **measured** on this machine, **vendor** specification, or **projected**
  arithmetic. Never present a projection as a result.
- Never invent pricing. Direct pricing questions to symonsayadmin@symoneural.com.
- No decorative status indicators. Every LED and gauge on the site reflects a real reading; a
  fake activity light is the one dishonest pixel on a page arguing for measurement.
- Publish negative results too — the PCIe Gen 3 ×8 ceiling and the failed multi-stream overlap
  are on the site deliberately.
- Layout changes must not drop data. Fold long content into `<details>`; do not trim it.
  **This includes CSS.** `text-overflow:ellipsis` on a detail line is data loss with extra
  steps — the control board was showing `~84% of 896.1 p…` and the rack was cutting
  `built on Qwen2.5-7B-Instruct` down to `…7B-Ins…`, and that attribution is an Apache-2.0
  licence condition. Every ellipsis rule has been removed. Do not add one back; let it wrap.

## What is SyMoNeuRaL's, and must never be published

The stack is off-the-shelf and permissively licensed, so nothing here is protected by a
licence. Two artefacts are protected only by not being public, and trade secret — unlike
copyright — exists only while reasonable measures are taken to keep it that way. Once it is
out, it cannot be pulled back.

- **`training/corpus.jsonl`** — 327 hand-authored examples: the company voice, what the model
  may claim, and what it must refuse to invent (the pricing refusal is trained in, not
  prompted).
- **`training/build_dataset.py`** — the method that produces it.
- **`training/adapter/`** weights — already gitignored (`*.safetensors`, `*.gguf`).

**Never copy any of these into `site/`, never serve them from an endpoint, and never quote
their contents into a page or a commit message.** An agent asked to "publish the manual" could
reasonably mistake the corpus for documentation. It is not: it is the recipe for the product.
`docs/symoneural-manual.md` is the manual and is publishable; the corpus is not.

The line that resolves this against the site's transparency argument: **publish the numbers,
keep the methods.** "151 tok/s on a 7B Q4_K_M, measured here" is the sales argument and gives
away nothing. How the adapter was built is the asset. The site promises measurement, not open
source, and has never promised the recipe.

There is currently **no git remote** — history never leaves this box, which is doing a lot of
the protecting. If one is ever added, audit what is tracked first.

## Build and deploy

```bash
./scripts/fetch-models.sh            # weights -> models/ (ungated, Apache-2.0 sources)
python3 tools/build_pages.py       # chat/image/calc/remix   -> site/*.html
python3 tools/build_rack.py        # live rack               -> site/index.html
python3 tools/build_console.py     # control board           -> site/index.html
python3 tools/build_cost.py        # Owned vs Rented         -> site/documentation.html
python3 tools/build_stack.py       # Inference Architecture  -> site/documentation.html
python3 tools/build_training.py    # manual                  -> site/training.html
python3 tools/build_tabs.py        # one-screen front page   -> site/index.html
python3 tools/build_gallery.py     # homepage art (uses GPU) -> site/art-*.png
python3 tools/build_gallery.py --restamp   # redraw the watermark bar only -- NO GPU
python3 tools/build_cachebust.py   # ALWAYS LAST -- see below
./scripts/symoneural.sh on|off|status   # the live API (off is the kill switch)
sudo ./scripts/deploy.sh                # site/ -> /var/www/symoneural (needs a password)
```

**`build_cachebust.py` runs last, and every generator run un-does it.** The generators emit
plain `href="/symoneural.css"`; the stamper rewrites those to `?v=<content hash>` so a week-old
cached stylesheet can never be served against new markup. That means any generator you run
*strips the stamps off every page it writes*, and a commit made at that moment ships pages whose
assets are cacheable for a week with no way to invalidate them. This is not theoretical: a run of
`build_pages.py` here silently destamped seven pages, and the diff read like a harmless refresh.
So: **regenerate, then stamp, then look at `git status`** — if a page you did not touch is still
modified, you skipped the stamper. It is idempotent and cheap; there is no reason not to run it.

The generator scripts are idempotent and must stay that way — `tools/build_console.py` once nested
folds inside folds when run twice. **Run every generator twice and `diff` before committing.**
The BEGIN/END marker strings are the contract: change a marker in a generator and you must
change it in the HTML in the same commit, or the generator stops finding its block and appends
a second one.

`scripts/deploy.sh`'s reference check **can** fail the build — the loop reads from a process
substitution, so `missing` survives into the exit test. It used to pipe into `while read`,
which put the counter in a subshell and threw it away; that was fixed in `aa424d3` and
verified by running the block against a fake webroot with one missing reference. Earlier
revisions of this file said the bug was still live. It is not.

The general lesson stands and is what to carry forward: **a counter incremented inside a
piped `while read` is discarded.** The orphan-scan loop above it is still in a subshell, and
that is fine, because it only writes to stdout and sets nothing its caller reads.

## Test in a real browser, not with curl

```bash
node tests/frontend.mjs             # every page, against a running API on :8800
node tests/streamer_failpaths.mjs   # streamer.html, self-contained -- starts its own fake provider
node tests/streamer_watch.mjs       # streamer-watch.html, ditto -- no account, no real stream
node tests/studio.mjs               # /studio -- needs the surface on, ComfyUI up, and the GPU
node tests/streamer_guide.mjs       # the guide grid on streamer.html -- own API, no GPU, no provider
node tests/project.mjs              # /project -- needs tests/project-harness.py, no GPU
node tests/live.mjs                 # /livestack/live -- needs tests/live-harness.py, no GPU, no OBS
cd backend && python3 -m pytest apps/ -q \
    --ignore=apps/studio/plugins/reinforce/tests --ignore=apps/remix/tests
cd backend/apps/remix && python3 -m pytest -q   # the 28 the line above has to exclude
```

**1625 pass, 0 fail and 14 skip at `79d139b`, measured 2026-08-21 from `backend/` in
122.50 s, with `--collect-only` collecting 1639 in 1.22 s; the two `--ignore`s are not optional
and not a failure you introduced.** 1625 + 14 = 1639, which is the arithmetic that says nothing
aborted. `backend/apps/remix` is **28/28 in 0.43 s** on the same tree, so this tree carries
**1667 across the two invocations**.

The 13 over the reading below it are attributable in full, counted per file rather than
inferred from the total: **+5** `apps/studio/test_comfy_port.py` (4 → 9,
`TheEditorMountAndItsCookieAgreeTests` at `79d139b` — the editor's mount prefix and its
session-cookie path read off `api.py` and `gate.py` and compared, because a rename that moves
one and not the other breaks the framed editor with nothing in any log to read), **+3**
`apps/test_build_progress.py` (25 → 28, `AResolveIsEvidenceNotAVerdict` at `8c70d9b`), **+4**
`apps/test_desktop_client.py` (32 → 36 at `f1e8e51`), **+1** `apps/test_brand_boundary.py`
(12 → 13 at `e2da088`). 5 + 3 + 4 + 1 = 13. `apps/test_governor_paths.py` and
`apps/studio/test_studio.py` were both edited in this range and moved the count by nothing —
the first had its retired-path list and launcher names updated, the second had a URL literal
changed. That is the usual case and the reason a count is a weak signal on its own.

The previous reading was **1612 pass, 0 fail and 14 skip at `7079933`**, measured 2026-08-21
in 124.13 s with `--collect-only` collecting 1626, and `apps/remix` 28/28 in 0.42 s.

The 32 over the reading below it are one file: `apps/test_desktop_client.py`, landed whole by
`7079933` with #94's client. 1580 + 32 = 1612. Three of those 32 were written *after* the
client had already been declared finished by its checks, and are the more useful part of the
delta: `TheCapabilityGrantsExactlyWhatThePageUsesTests` exists because Tauri v2 gates its core
plugins, the client shipped with no `capabilities/` directory, and so chat rendered its turn
and then silently received nothing while every check on the task read green. See
`desktop-client/SMOKE.md`.

The reading before that was **1580 pass, 0 fail and 14 skip at `87c4042`**, measured
2026-08-21 in 122.01 s with `--collect-only` collecting 1594, and `apps/remix` 28/28 in 0.41 s.

The 16 over the reading below it are attributable in full, which is the second time running and
still not what to expect: 9 are `apps/test_api_reference.py`, new at `ad9b9fa`; 4 are
`apps/test_weight_names.py` going 10 → 14 at `f3ed5ab`; 3 are `apps/test_brand_boundary.py`
going 9 → 12 at `6542932`. 9 + 4 + 3 = 16. `5299200` is the fourth commit in that range to
touch a test file and it moved the count by nothing — it rewrote `WindowSmokeTests` to wait on
the shell instead of on a stopwatch, which is a fix to *what* 15 tests assert, not to how many
there are. That distinction is why a count is a weak signal on its own.

The reading before that was **1564 pass, 0 fail and 14 skip at `0d51b09`** in 127.85 s with
`--collect-only` collecting 1578; the 9 over the one below it were all
`apps/test_brand_boundary.py`, landed by that commit as #74 item 7.

The reading before that was **1555 pass, 0 fail and 14 skip at `2f97a3b`**, measured
2026-08-21 in 126.41 s with `--collect-only` collecting 1569.

The reading before it was **1526 pass, 0 fail, 14 skip at `c847b64`** in 126.78 s, and for once
the whole jump is accounted for rather than estimated: 21 are `apps/capture/test_capture.py`
(`1ec7cbe`), 4 are `apps/test_caddy_delegation.py` (`e5ca567`) and 4 are
`apps/test_deploy_routes.py` (`180cb60`) — 29 exactly, which is 1555 − 1526. That is unusual and
you should not expect it; the paragraphs below exist because most deltas span many commits and
cannot be attributed this way.

**The suite is green, and the three deliberate failures that stood here are gone for the right
reason.** This paragraph said for two days that `apps/test_rack_probes.py` fails three times
because `api.py` probes `contrib/llama.cpp` and `contrib/stable-diffusion.cpp`, which are not on
disk — Garrett having moved the engines to `references/`, and *"we cannot use code in
references its for reference only we must rebrand if we want to use it"*. That was true and it
is no longer: `d6b7838` forked both engines under our own names and repointed every consumer,
which is #74's work, so the probes now find what they look for and all five pass. **Nothing was
repointed at `references/` to make them green** — that was and remains barred. If those three go
red again, read them: red there means chat and image are offline, and it is the honest signal.

The published figure before this one was **1376 pass, 3 fail, 12 skip at `0c0f969`**. It is
left here rather than overwritten because the difference is instructive and not a mystery: of
the 149 between the two collections, three are the rack probes turning green, thirteen landed
with #73's four retired checks (`ComfyPortAgreementTests` 4, `PluginRowsMatchRosterTests` 4,
`RowCoverageTests` 5, plus 2 more skips for the live half of `test_server_ready.py`, which is
why the skip count moved 12 → 14), and the rest arrived across the commits between. As
everywhere else in this file: a count moves when tests land, not when a task closes.

**Note the `--ignore` paths changed at `0c0f969` and the old ones matched nothing.** They were
`apps/reinforce/tests` and `apps/remix/tests`; reinforce is now a studio plugin, so the first is
`apps/studio/plugins/reinforce/tests`. A stale `--ignore` is silent — pytest does not warn that
a path you excluded does not exist — so it stops excluding and you get a collection error
instead of a count. The ladder behind the figure, each read on the tree it names: **1085 at
`df1d862`**, **1093 at `e81ffa4`**, **1200 at `74dee33`**, **1229 at `d3a4040`**, **1391 at
`0c0f969`**, **1540 at `c847b64`**, **1569 at `2f97a3b`**, **1578 at `0d51b09`**, **1594 at
`87c4042`**, **1626 at `7079933`**, **1639 at `79d139b`**. Do not
attribute a jump to one task from these numbers alone: the 107 between `e81ffa4` and `74dee33`
spans **25 commits** across most of two days' work, while the 29 from `74dee33` to `d3a4040` is
a single commit. A count moves when tests land, not when a task closes. `df1d862` read 110.38 s
then 111.55 s on that tree: two readings of one tree, so treat the wall time as a range and the
count as the reading. The count drifts upward as apps land — it was 682, then 941, then 973,
then 981, then 1084, then 1085 — so treat the absolute number as a date-stamped reading, not a
contract, and put a commit SHA beside it. A published 1063 turned out never to have been true of
the commit it sat beside: the tree it named collects 1084, so the figure was carried forward
from an earlier one. A number with no SHA cannot be checked, only believed. `--collect-only`
should report the same figure; that comparison is what catches a collection abort, which is not
a smaller number but no number at all. Without them pytest stops at *collection* — `Interrupted:
2 errors`, zero tests run, which reads exactly like you broke the suite.

`apps/studio/plugins/reinforce/tests` imports `cupy`, which is not installed on the **system**
interpreter and may not be, since that is the serving path (see *Python environments*). That one
is a genuine per-project suite with a genuine environment problem, and it stays excluded.

**`apps/remix/tests` is excluded for an entirely different reason, and the reason this file gave
until 2026-08-21 was wrong.** It said the suite imports `symon_capture` and that the module is
not installed. There is no such module anywhere on disk any more: `apps/remix/symoneural_dj/app.py:30`
imports `from apps.capture import CaptureStore`, which resolves perfectly well from `backend/`.
What actually breaks is **configuration, not environment**. `apps/remix/pyproject.toml:44` sets
`pythonpath = [".", "../.."]`, and pytest applies a `[tool.pytest.ini_options]` block only from
the directory it selects as **rootdir**. Run `pytest apps/` and rootdir is not `apps/remix`, so
that `pythonpath` is never added, `symoneural_dj` is unimportable, and you get one collection
error and zero tests. The `--ignore` is therefore still required for the `apps/` invocation — but
the suite is not dead, needs no venv, and runs on the system interpreter:

```bash
cd backend/apps/remix && python3 -m pytest -q     # 28 passed in 0.43 s
```

**28/28, measured 2026-08-21 at `0d51b09`.** Those 28 are not inside the 1578 and never have
been, so the tree really carries **1592 tests across two invocations**, not 1578 across one. Run
both before claiming the backend is green. The lesson generalises past this suite: an exclusion
outlives the reason it was added, and *"it needs its own environment"* is the most comfortable
reason to leave sitting there, because it reads as a policy decision rather than as a bug nobody
re-checked. Re-check the reason, not just the count.

The 162 between `d3a4040` and `0c0f969` is **not 162 new tests**, and reading it that way is
the mistake the paragraph above warns about. `d3a4040` was a healthy tree that genuinely
collected and ran 1229. What happened between the two is the 104-file restructure, and for
several commits in the middle the suite was **899 collected with 10 collection errors — zero
tests run**, which is neither 1229 nor 1391 but no reading at all. `0c0f969` repaired the
imports, and the 1391 is the same tests plus the ones that were never reachable from `apps/`
before the move. So the ladder has a hole in it, on purpose: there is no honest figure for the
trees in between, because a collection error is not a smaller number but no number.

**`frontend.mjs` was 49/49 at `d3a4040`, measured 2026-08-20 against
`http://127.0.0.1:8879`; it was 43/43 at `e81ffa4`, and the rack red that stood here is fixed.
It has NOT been re-read since `0c0f969` and that figure is deliberately in the past tense.**
`0c0f969` moved 104 files under `backend/apps`, and this suite asserts on what `/api/status`
renders, so its tree is not the tree the 49/49 was read on. Two of its assertions are also
known to be affected: the image assertion needs a working render engine, and chat and image are
offline (see the three red probes above). Re-run it and stamp the reading rather than believing
this one — that is the rule this file states everywhere else, and it applies to its own
figures first.
Always on a spare port, never the service — that is the only honest way to run it, see below.
The rack red, for the record: `#rack` on
`/livestack` overflowed its one-screen budget at 1855x745 — `scrollHeight` 599 against
`clientHeight` 584 — because `site/index.html` renders the rack client-side from `/api/status`
and the rack went from eleven units to thirteen when `studio` and `exp` landed (`e27b9c1`).
Nothing in any page source regressed. Two spacing rules closed it, both in the `html.ns` block
of `site/symoneural.css`: the rack note's measure (96ch → 160ch, three line boxes → two) and
the `.rk-fold` pill moved out of the heading's inline run onto the `.shead` row, which was a
whole line box on its own. No word, row or type token changed. **Measure slack with a cloned
`.unit`, not with `scrollHeight`** — it floors at `clientHeight`, so `584/584` says "fits" and
nothing about by how much, and three of the four in-gate viewports read `over=0` before the fix
as well. By that method fourteen units now fit everywhere and fifteen only at 1990x970; the
binding viewport is **1301x740**, not 1855x745, because its rows are 26.6px. `.claude/HANDOVER.md`
§0 has the full table, the retraction of the two-column option it used to recommend, and the one
lever deliberately left unspent. Do not close the next overflow by dropping a row or adding
`text-overflow` — both are barred above. The other two suites are green on the same tree:
`streamer_failpaths.mjs` **32/32** and `streamer_watch.mjs` **8/8**, **re-measured
2026-08-20 at `f6ed7d3` under the names above, which are the names that exist** — so unlike the
49/49 these two are not in the past tense and you can rely on them. They had also read
**32/32 and 8/8 at `e81ffa4`**, the same tree as the 43/43 above, which is what "same tree" has
to mean to be worth writing; that earlier pair was measured while the files were still called
`tuner_failpaths.mjs` and `tuner_watch.mjs`, and it keeps the SHA it was read on rather than
being re-dated to the rename (#73 item 2, Garrett *"i said tuner and guide needed to be merged
and migrated to streamer"*). Both readings are written out rather than one replacing the other
because a rename is exactly the change that can move a file without moving what it references —
so two identical readings, each stamped on the tree it was taken from, is the evidence that
nothing came loose. This paragraph named the old files for a while after they were gone, which
is worse than a stale count: a stale count can be checked, and `node tests/tuner_watch.mjs`
cannot run at all.

System Chrome via Playwright, nothing to download. The failpaths and watch suites need no API
and no provider account: each starts `tests/streamer_fake_provider.py` and stops it again, so the
whole invocation is the one line. **`frontend.mjs` needs an API**, and if you point it at the running
service you are testing what is *deployed*, not what you wrote — start your own on a spare port
and pass the base URL (`node tests/frontend.mjs http://127.0.0.1:8875`), or a red assertion will
send you hunting a bug you already fixed.

**`tests/studio.mjs` is the fourth suite and is deliberately not part of `frontend.mjs`.** That
one runs against any instance and asserts what every visitor sees; this one needs the Studio
surface switched on and it **takes the card for a real render**, so pointing it at the deployed
service would queue a job on the live GPU. Start the render UI and your own API, then run it:

```bash
bash scripts/symoneural-ui.sh start                       # loopback :8188, no lock held
cd backend && SYMONEURAL_STUDIO_ENABLED=1 SYMONEURAL_STUDIO_TOKEN=devtest \
    python3 -m uvicorn api:app --port 8876          # a spare port, not the service
SYMONEURAL_STUDIO_TOKEN=devtest node tests/studio.mjs http://127.0.0.1:8876
bash scripts/symoneural-ui.sh stop                        # /free, THEN SIGTERM -- see below
```

**16/16 passed, re-measured 2026-08-20 at `d3a4040`, and unread since `0c0f969`**, including a 1024x1024 FLUX-schnell
render decoding in the browser in 14.4 s (14.2 s server-side, card back in 4.2 s, lock
released). The same 16/16 stood at `1537262` and, before that, at `d20e09b`; each was re-run
rather than re-dated because `backend/api.py` had changed underneath it, and studio.mjs runs
against `api.py`. Its three `net::ERR_ABORTED` lines are labelled optional and 404 upstream at
:8188 as well; they are not proxy faults. `.claude/HANDOVER.md` has the reading and the VRAM
curve.

**Run this suite and `frontend.mjs` one after the other, never at once.** Both take the card,
and `frontend.mjs`'s image assertion evicted ComfyUI out from under a studio render here — the
lease is released before the browser fetches the PNG, and evicting `comfy` stops the *process*
that serves it, so the render 503s as `comfyui_unreachable`. That reads as a studio bug and is
not one. `.claude/HANDOVER.md` §0a-quater has the governor log and the underlying defect, which
is real for a visitor too. The state document claimed for two days that this suite could not run
because ComfyUI "has no venv and no torch" — it has both (torch **2.13.0+cu130**, sm_120
verified by a real CUDA probe, 223 packages), and the suite had simply never been invoked.

**Stop the render UI with `scripts/symoneural-ui.sh stop`, never by killing the pid.** The script POSTs
`/free` and then waits on `gpu-governor.sh drain` — the process exiting is not the memory coming
back, and the next tenant OOMs at step 0. Measured here: a render peaks at **13,114 MiB of
16,303** and returns to 666 MiB in **4.1 s**, against the governor's 60 s timeout and 1500 MiB
floor. `symoneural-ui.sh` deliberately does **not** hold the lock for its process lifetime; the lease
is taken per render and released after the drain, which is the rule above applied.

**`tests/streamer_guide.mjs` is the fifth suite, and it was dead for a fortnight because
nothing in this file told anyone to run it.** It needs no GPU, no provider account and no
running service — it starts its own uvicorn carrying just the two streamer routers — so there is
no reason to skip it. **17/17 passed, measured 2026-08-20 at `7a5ced5`**, including that the
grid re-ticks to exactly the groups Guide returned, that *both* adult groups are found rather
than only the first, and that nothing overflows at 1440/1301/390px. Its failure mode is the one
worth knowing: it generates its own `app.py`, so a stale import there kills uvicorn before it
binds and Chrome reports `ERR_CONNECTION_REFUSED` twenty-four seconds later. That reads as an
infrastructure fault and is not one — it is this repo's own restructure, unpropagated. It had
been importing `from guide import routes` against a directory that is now
`backend/apps/streamer/guide/`, and mounting at `/api/guide` while the page fetches
`/api/streamer/guide/filter`. Two faults, the second hidden behind the first.

**`tests/project.mjs` is the sixth suite, it needs no GPU and no provider account, and it
was red for a fortnight for a reason that had nothing to do with the page it tests.** The
surface is off unless `SYMONEURAL_PROJECT_ENABLED` and `SYMONEURAL_PROJECT_TOKEN` are set, so
it brings its own harness with a throwaway store and a token that is deliberately not a secret:

```bash
python3 tests/project-harness.py &      # 127.0.0.1:8899, fresh temp store every start
node tests/project.mjs                  # or pass a base URL
kill %1
```

**16/16 passed, measured 2026-08-20 at `fdb21b0`.** It was **15/16** immediately before that,
and the red is the part worth reading, because it is the failure mode of every single-app
harness in this repo: `site/ui.js` fetches `/api/news/ticker` on **every** page load — the
ticker is shared page chrome, not a news-page feature — and the harness mounted only the
project router, so the browser logged a 404 and the *"no uncaught JavaScript errors"* assertion
went red for something this page does not own. `apps/news/routes.py` is explicit that the
endpoint is safe to expose in exactly that situation: it never triggers a fetch (the background
refresher owns the rate), it carries no token because everything it returns is already public,
and it answers 200 with an empty bar rather than 503 when the surface is off — and its stated
reason for that last one is *this same* red-line-in-the-console argument, aimed at a visitor
instead of a test. So the harness mounts it now, which reproduces the production shape rather
than papering over a gap. **If you write a harness, mount news in it.**

**`tests/live.mjs` is the seventh suite, it takes nothing — no GPU, no OBS, no provider
account, no token — and it had never been executed once before 2026-08-21.** Not "was red",
not "was skipped": `node` could not load it. Line 17 read
`import { dirname, fileURLToPath } from 'node:url'` and `node:url` exports neither name, so
the module failed to instantiate with a SyntaxError before a single assertion ran, and both
imported names were unused anywhere else in the file. It landed in `14814e9` beside the code
it was written to gate. A test file on disk satisfies `exists`, satisfies `grep`, and reads
to a human exactly like a suite — and says nothing at all about whether it has ever run.
That is #94's shape arriving from a new direction, and it is the reason this list exists and
the reason `apps/test_streamer_migration.py` fails when a `tests/*.mjs` file is not named
here.

```bash
python3 tests/live-harness.py &      # 127.0.0.1:8897, throwaway store, no OBS, no GPU
node tests/live.mjs                  # or pass a base URL
kill %1
```

**21/21 passed, measured 2026-08-21 at `a616168`.** The assertion it exists for is `video
decodes`: a `<video>` with an HLS URL behind it satisfies every DOM check anybody would think
to write while playing nothing, so the suite asserts `readyState >= 3`, that `videoWidth` and
`videoHeight` are the fixture's own `320x180`, and that `currentTime` advances — read
`readyState=4`, `320x180`, `4.67 -> 5.87`. Only real decoded video produces those three.
`tests/fixtures/live/` is six seconds of real MPEG-TS for the same reason: a hand-written
`.m3u8` pointing at empty files would go green.

**Start the harness immediately before the suite, and do not "fix" a timeout by widening
`hls.LIVE_WINDOW_S`.** `live-harness.py` builds its store at *import*, so the live session's
mtime is frozen at harness start; the window is 20 s, and after that `hls.scan()` correctly
reclassifies that session `abandoned`, `#lv-player` stays hidden and the run times out on its
third assertion. That is the classifier working. The harness carries a comment saying so, and
this is the second place it is written down because the misdiagnosis is so much cheaper than
the diagnosis: nothing in the console, no failed request, no HTTP >= 400 — the page simply
and correctly reports that nothing is being recorded.

It also asserts the trap that `site/streamer.html:1989` measured: Chrome returns the **truthy
string** `'maybe'` from `canPlayType('application/vnd.apple.mpegurl')` and then plays nothing,
so `if (canPlayType(...)) native;` takes a branch that cannot work. hls.js goes first
everywhere and native only where hls.js will not run, which is Safari. Asserting the
measurement means a future Chrome changing it is a red line here rather than folklore rotting
in two comments.

**The Studio agent loop does not stream tokens, so do not quote a first-token latency for
it.** `inference.Backend.chat` sends `"stream": False` and is the loop's only call site;
`Backend.stream()` is unexercised and says so. The loop's granularity is SSE *events*. Measured
2026-08-19 over six turns, warm: the `backend` probe frame lands in **0.015-0.022 s**, the first
frame carrying model output in **0.2 s warm / 1.06 s cold** (the cold penalty is `--no-warmup`
plus first processing of the 26 rendered tool specs), and a whole turn takes **0.53 s** with no
tool, **1.0-1.9 s** with one, **3.1 s** with three. Native tool calling works on this build --
no `notice` downgrade in any turn, and turn 6 returned three tools from one message.

**To measure it, warm the engine through the chat surface, never by spawning llama-server.**
`inference.py` probes and never spawns, because `api.py` owns that process inside
`gpu.hold("chat")` and a second spawner would race it for :8081 and the lease:
```bash
curl -sS -X POST http://127.0.0.1:8800/api/chat -H 'Content-Type: application/json' \
    -d '{"prompt":"ready","max_tokens":8}'   # ~7.1 s of that is spawn + weight load
ss -lntp | grep 8081                            # confirm it stayed resident; chat does not stop it
```
llama-server then holds **~8.1 GiB** and stays up, while `gpu-governor.sh` reads `lock free` --
**the agent loop takes no lease.** Only `api.py` can stop it (shutdown, or an image render at
`api.py:2052`), so expect to leave it resident; that is this box's warm state, not a leak.

These assert on what the DOM *shows*: units render from `/api/status`, the bus plate carries a
real reading, nothing overlaps at 390px, calc returns `x**3/3`, and a generated image actually
decodes. That last assertion exists because a render once succeeded server-side and still
showed as a broken image for every visitor — curl proved the endpoint answered, which was never
in doubt. Add an assertion here whenever you fix a frontend bug.

**Read computed styles rather than reasoning about the cascade.** Three separate bugs have now
come from generic class names colliding across components: `.bar` (collapsed the site header to
7px sitewide), `.live` (the nav badge styling the control board legend), and `#console .sub`
(a section rule outranking `.mod .sub`, rendering a footnote larger than the sentence above it).
Render the page and measure.

## `run/` is runtime state, not logs

`run/` holds `gpu.lock.d` — the GPU mutex — alongside `api.pid`, the resident marker and the
logs. **Do not rename it `logs/`.** `/run` and `/var/run` are the Unix convention for exactly
this (pidfiles, locks, sockets) and the name is load-bearing: call the directory `logs` and
sooner or later someone logrotates it or clears it out, which deletes the lock directory while
a surface is holding the card. The logs happen to live there; the lock is the point.

Renders do **not** live there, and no longer live in `site/` either. They are API output,
written to `backend/output/` and served by `GET /api/gen/<name>`. They were in `site/` until
the backend restructure, which meant `deploy.sh` copied every one into the public webroot —
19 unreferenced PNGs were sitting there — even though nothing links to them.

## Serving architecture

**FastAPI does all the routing. The web server terminates TLS and hands back static files.**
That is the user's stated rule and the config enforces it — no rewrites, no aliases, no
conditional logic in `ops/Caddyfile`.

- **Caddy**, not Apache. Apache is disabled, and its config was deleted rather than left beside
  the Caddyfile. Caddy gives automatic TLS and, crucially, WebSocket upgrades with no directive
  — `mod_proxy_wstunnel` was never enabled under Apache, so the rack's "pushed live over one
  socket" claim had been silently falling back to polling.
- Anything the API generates is served by the API. Renders come back as `/api/gen/<name>`, not
  as a webroot path, because the API writes into the staging `site/` while the web server serves
  `/var/www/symoneural` — so every image generated on the live site used to 404 until somebody
  deployed.
- `api.py` mounts `site/` at `/` **last**, so it never shadows an API route. That is what lets
  the whole thing be exercised from one origin, which is the only way the real frontend works:
  `console.js` opens a WebSocket and falls back to polling, and neither survives a split origin.
- Testing a WebSocket: use `curl --http1.1` (`Upgrade:` does not exist in HTTP/2, and curl
  negotiates h2 with Caddy by default), and read the status line out of `-D` headers rather than
  trusting the exit code — a successful upgrade leaves the socket open, so curl exits 28.

## Branding

"MIT AI Training" is purged everywhere user-facing. Watch out: most `MIT` substring matches in
this corpus are ordinary words — limits, limited, submit, emits — so never blind-replace. Only
whole phrases and local filesystem paths.
