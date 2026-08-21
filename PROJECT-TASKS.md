# PROJECT-TASKS.md — the canonical task list

**This file is the canonical task list.** The widget and `run/progress.html` are viewports
onto it. It holds only **open** work: done and cancelled entries move to
`review/CLOSED-TASKS.md` verbatim on a two-minute timer, so the length of this file is a
reading of what is left rather than of everything that ever happened.

Renamed from `CODER-TASKS.md` on 2026-08-20 — *"rename Task - Coder task to project task and
then label the task coder or garrett"*. The old name asserted a single owner for a list that
has always held both, which is how an item only Garrett can do ends up reading as unstarted
coder work. Ownership is now a label on the task instead of a claim in the filename.

## Standing rules for this file

**Two surfaces, two owners, one flow.** Garrett, 2026-08-20: *"that way you only work on task
and i just work on checking the box saying i believe its ready to move to task"*, and
*"until i check the box you have nothing to do except what is in the project task"*.

```
INTAKE.md         assignments — requests, questions, findings.  Garrett's surface: he ticks.
PROJECT-TASKS.md  tasks.                                        Mine: I do what is on it.

assignment  ->  (answer, if it is a question)  ->  [x] ready  ->  task #NN
```

So this file is the only thing I work from. An item that is not here is not mine to start,
however obviously useful it looks. The obligation that comes back the other way is real:
*"you must give me information and help on getting the boxes checked"*. A box cannot be ticked
on a title alone, so every assignment carries a brief.

**Ticking is now the exception, not the gate.** Garrett revised this on 2026-08-20: *"make sure
as soon as i send a prompt it gets added to intake.md, automatically get pushed to task if no
barriers and if they do have barriers remain in the intake.md/progress.html with specifics on
the barrier"*. So an assignment with nothing blocking it promotes itself and arrives here with a
number; only a **barrier** keeps something on `INTAKE.md`, and then the page must say what the
barrier is. His later word wins over the earlier ticking rule. This is still three states, not
four — capture, promote, or drop with a reason — and #77 is the task that builds it.

**Intake is immediate.** *"as soon as i send a prompt it should quickly added to
coder-task.md"*. A prompt becomes a task in the same turn it arrives.

**Five tasks, deliberately.** *"consolidate all these tasks plus my recent request into 5
detailed task max"* — 2026-08-20. Forty-three open rows, nearly all reading `no checks`, was an
inventory rather than a list, and it did not answer "what is left". The forty-three are folded
into #73-#77 and reproduced verbatim in `review/CONSOLIDATED-TASKS-2026-08-20.md`; nothing was
dropped. **When you work a fold, read the original block in that file** — the summaries here are
entry points, not replacements. If a sixth task is genuinely needed, fold something first: the
cap is his instruction, not a suggestion.

**Every task is labelled `owner: coder` or `owner: garrett`.** Unlabelled means coder — the
default claims work for me rather than parking it on Garrett, and the standing authority rule
is already FIX, not FILE. `owner: garrett` is reserved for the five categories: physical
hardware access, credentials only he holds, third-party dashboards with no API, money, and
legal or business decisions.

**Questions go in `AUDIT.md`, not into chat.** *"ask questions in the audit.md file"*. They
are non-blocking: *"ill make sure to answer them by the time you get to the pending task in
question"*. So work continues past an unanswered question and the answer is read when the
task comes up. They also appear as assignments in `INTAKE.md`, which is where they get ticked.

**The percentage is measured, never estimated.** Each task may declare `check:` predicates;
the percentage is passing checks over declared checks, recomputed from the disk every two
minutes by `tools/build_progress.py` under a systemd timer. A task with no checks reads
`—`, never `0%` — an unmeasured task is not an unstarted one. Garrett: *"you will keep the
percentages accurate"* and *"as you complete things you shall update the %"*. The way that
promise is kept is by choosing checks where 100% genuinely means done; a percentage that
can be satisfied without doing the work is worse than no percentage.

Syntax, all read from the indented detail block:

```
owner:   coder | garrett   who it is on; unlabelled means coder
resolve: OLD -> NEW        state read from disk: NEW present and OLD gone means done
check:   exists <path>     |  absent <path>
check:   grep <pat> -- <path>  |  ngrep <pat> -- <path>
check:   maxcount <n> <pat> -- <path>
```

A task reaching 100% is archived automatically by `tools/archive_tasks.py` on the same timer —
*"done should automatically leave the list"*, *"you need to make done items like 61 and 62 go
away automatically"*. Nothing is deleted: the block moves to `review/CLOSED-TASKS.md` verbatim
with one `ARCHIVED` line saying what judged it finished.

**There is no phase tracker.** It was deleted 2026-08-20 — *"this phase tracker is bullshit
fix it or get rid of it and just put task in the task"* — because every one of its Phase 2
steps was an alias of a task that already existed, so the page showed the same ten items
twice. Its non-alias steps are tasks #51-#55, #39, #47, #48 and #50. The one thing it did
better, resolving a folder move against the disk, survives as `resolve:`.

---

## Open tasks

◻ #73 — The browser API server: every application online, one roster, one namespace
        owner: coder
        Folds #21 #22 #23 #24 #26 #28 #31 #34 #35 #43 #44 #45 #46 #51 #53 #54 #66 #68 #69 #70.
        Read those blocks in `review/CONSOLIDATED-TASKS-2026-08-20.md` before working any part.

        **Scope, cut by Garrett on 2026-08-20 and binding:** *"we are only building for browser
        api applications right now let me know when the server is complete"*. The debian,
        apple, windows, android and openembedded targets are held by his decision, not deferred
        by my judgement, and they return only after he approves the browser application. The
        last clause is a reporting duty on me: when the server is complete I tell him
        unprompted, rather than waiting to be asked.

        **The shape, also his:** *"all applications should be in /backend/apps all plugins
        should be in /backend/apps/studio/plugins"*. That is now true on disk — exp, reinforce
        and discovery are packages under `backend/apps/studio/plugins/`, which closed #55 and
        the plugin half of #22, #23 and #53 by reading the filesystem rather than by assertion.

        What is left, in the order it unblocks itself:

        1. **One roster, and the rack generated from it** (#66, #43). `backend/apps/` and the
           rack currently disagree. Write the roster down once as `backend/apps/ROSTER.md`,
           reconcile the directory against it, and make `tools/build_rack.py` read it instead
           of carrying rows by hand. Three lists that disagree is the three-state-documents
           failure with a different filename.
        2. **Finish the streamer merge — the namespace, not just the files** (#28). The file
           half is done: `routesmergemewithotherroutes.py` and `READMEmergemewithotherreadme.md`
           are gone, guide is a subpackage, and tuner's clobbered `__init__.py` exports were
           recovered from git history (`0c0f969`). **The namespace half was not**, and Garrett
           corrected it on 2026-08-20: *"i said tuner and guide needed to be merged and
           migrated to streamer"*. The package is `apps/streamer` while everything a visitor
           or a caller touches still says tuner — `/api/tuner/*`, `/api/guide/*`,
           `site/tuner.html`, `site/tuner-watch.html`, `id="tuner"` on the rack, four test
           files, and six `localStorage` keys under `symoneural.tuner.*`. One surface, one
           name: `/api/streamer/*` with guide nested at `/api/streamer/guide/*` — they both
           declare `/state`, so a shared flat prefix would collide — one row reading
           `streamer`, and `site/streamer.html`.
           Two things must survive the rename and are the reason this is not a blind sweep:
           the visitors' `localStorage` (playlists, Xtream credentials, favourites) needs a
           one-time read-old-write-new migration or people lose their setup, and the prose
           explaining *why* the merge happened has to keep saying "tuner" and "guide" —
           renaming the words inside the sentence that records the decision falsifies the
           record. `symon_ml/training/tuner.py` in `docs/specs/symon-ml-review.md` is a
           third-party path and a hyperparameter tuner: different word, leave it.
        3. **The plugin interface** (#54). `backend/apps/studio/plugins/__init__.py` is the
           contract the three plugins load through, and it does not exist yet; exp's CATALOGUE
           is the working prototype to generalise from.
        4. **Routing and surfaces** (#26, #44, #31). Applications move under
           `/livestack/<name>`, `site/account.html` becomes an application rather than a page,
           and the studio render is served from disk instead of proxying `GET /view`.
        5. **The Studio row's readout** (#70). Probe the render engine and publish what comes
           back — `offline` when nothing answers, and queue depth, loaded model and VRAM when
           something does. Do not auto-start the engine to make a green light true; that parks
           a 13 GiB-peak tenant on the card with nobody asking for a render.
        6. **Everything online, and staying online** (#34, #35). Automate the deploy so
           "online" survives a reboot without a person, then the four dark applications come
           back. #35 before #34: bringing an app up by hand is not the same as it being up.
        7. **Per-application model adapters and voice input** (#45, #46), then the environment
           selector (#69) — browser-API environments only — and `symoneural-invest` (#24) last,
           because it is new surface area and everything above it is repair.

        check: exists backend/apps/ROSTER.md
        check: grep ROSTER -- tools/build_rack.py
        check: grep RosterMatchesApiTests -- backend/apps/test_roster.py
        check: grep OPTIONAL_PRESENT -- backend/apps/studio/plugins/__init__.py
        check: grep StatusRowTests -- backend/apps/studio/test_plugin_contract.py
        check: exists backend/apps/studio/plugins/exp/__init__.py
        check: exists backend/apps/studio/plugins/reinforce/__init__.py
        check: exists backend/apps/studio/plugins/discovery/__init__.py
        check: absent backend/apps/streamer/routesmergemewithotherroutes.py
        check: absent backend/apps/streamer/READMEmergemewithotherreadme.md
        check: grep prefix="/api/streamer/guide" -- backend/api.py
        check: grep symoneural\.tuner -- site/streamer.html
        check: grep apps\.streamer\.guide -- tests/streamer_guide.mjs
        check: grep InvocableDocsTests -- backend/apps/test_streamer_migration.py
        check: exists site/streamer.html
        check: absent site/tuner.html
        check: grep "/api/streamer" -- backend/api.py
        check: ngrep "/api/tuner" -- backend/api.py
        check: ngrep \nROW_OF_MODULE\s*= -- backend/apps/test_status_rack.py
        check: grep ComfyPortAgreementTests -- backend/apps/studio/test_comfy_port.py
        check: exists ops/symoneural-deploy.service
        check: grep GatewayUnitPathTests -- backend/apps/test_gateway_unit.py
        check: grep FakeRootTests -- backend/apps/test_service_control.py
        check: grep PluginRowsMatchRosterTests -- backend/apps/test_roster.py
        note: `grep tuner_router` used to stand here, and it has been REMOVED rather than kept.
        note: It was a good check for the file merge — the loose `grep tuner` passed on guide's
        note: docstring while tuner's exports were still missing — but it became an anti-check the
        note: moment the task grew the namespace half: finishing the merge properly *deletes*
        note: `tuner_router` in favour of one `router`, so the check would go false as the work
        note: got more done, and a re-run would read as a regression. `grep "include_router"` in
        note: `__init__.py` replaces it and is true only when the package composes the two halves
        note: itself instead of handing api.py two routers to wire.
        note: 2026-08-20 coder — that replacement was itself unpassable and is now replaced in
        note: turn by the three checks above. Two faults, either one fatal. First, `run_check` hands
        note: the pattern to `re.search` VERBATIM, so `grep "include_router"` demands the quote
        note: characters too and only matches if `include_router` appears inside a string literal —
        note: correct code leaves it red forever. Second, and worse, unquoting it does not save it:
        note: every app in this repo documents its own mount in its docstring, so
        note: `streamer/__init__.py` lines 17-18 already read `app.include_router(...)` in prose and
        note: the check would have gone green on a comment. That is precisely the failure that
        note: retired `grep tuner`, which passed on guide's docstring while the exports were missing.
        note: The composition refactor it was pointing at was NOT done, and deliberately. `api.py`
        note: mounts all thirteen surfaces in one table at 2365-2462 with their `tags=` beside them;
        note: streamer would become the only package mounting itself, and the two mounts carry
        note: DIFFERENT tags — `streamer` and `streamer-guide` — which are the OpenAPI groups the
        note: rebranded Swagger UI renders, so collapsing them changes a visitor-facing page to make
        note: an internal check green. Item 2 asks for the namespace, not for who calls
        note: `include_router`. The three checks measure the namespace: the guide stays NESTED (flat
        note: would register its `/state` where the streamer's already answers), the retired
        note: `localStorage` prefix stays readable (deleting it loses every visitor's playlists and
        note: Xtream credentials), and the browser fixture imports the merged package. Each was
        note: flipped before being written: flatten the prefix, tidy away the old prefix, revert the
        note: fixture import — FAIL, FAIL, FAIL. The first draft of the prefix check was
        note: `grep /api/streamer/guide`, which survived flattening because the comment at api.py:1745
        note: explaining the nesting matched it. Same anti-check shape as `ROW_OF_MODULE`; narrowed
        note: to `prefix="..."` rather than deleted, so the explanation is not what holds it green.
        note: 2026-08-20 coder — item 2 done. The namespace half was already largely landed:
        note: `/api/streamer/*` with the guide nested at `/api/streamer/guide/*`, one rack row
        note: reading `streamer`, `site/streamer.html` and `site/streamer-watch.html` with
        note: `tuner.html` gone and 301'd, the four suites renamed, and the `localStorage`
        note: read-old-write-new shim live in both pages with `_OLD` annotated to stay spelled the
        note: retired way. What was NOT landed was everything that describes it. Four files still
        note: stated a route that no longer answers: `streamer/guide/routes.py` opened "Mounted at
        note: `/api/guide`", `streamer/README.md` and `HANDOVER.md` both said `/api/guide/*` "still
        note: serves the page's filter", and `guide/README.md`'s wiring example was a `from apps
        note: import guide` that raises. Those are false facts, not the protected prose: the rule is
        note: that sentences recording WHY the merge happened keep saying tuner and guide, and every
        note: such sentence is intact — HANDOVER's two decision paragraphs are untouched and carry a
        note: dated reversal beneath them instead, because that decision ("the prefix was
        note: deliberately NOT renamed") was later overturned by this very item and rewriting it
        note: would erase the reversal rather than record it.
        note: 2026-08-20 coder — and the fifth browser suite was down for this exact reason.
        note: `tests/streamer_guide.mjs` writes a throwaway `app.py` that did `sys.path.insert(0,
        note: backend/apps)` then `from guide import routes` — a directory that no longer exists —
        note: so uvicorn died at import, never bound, and 24 s later Chrome reported
        note: ERR_CONNECTION_REFUSED on :8981. It reads as a browser or port fault and is neither.
        note: It also mounted the router at `/api/guide` while the page it drives fetches
        note: `/api/streamer/guide/filter`, so it was wrong twice and the second fault was hidden
        note: behind the first. Fixed: `sys.path` at `backend/` and `from apps.streamer.guide import
        note: routes` (routes.py does `from . import ...`, so it must be imported AS a package),
        note: nested prefix, readiness probe repointed. **17/17 pass, measured 2026-08-20.**
        note: 2026-08-20 coder — the collision the nesting exists to prevent had no test, only
        note: comments. `NestedGuidePrefixTests` in `apps/test_streamer_migration.py` now asserts
        note: both halves declare `/state`, that the two probes resolve to DIFFERENT endpoints, and
        note: that api.py mounts nested. Mounted flat, Starlette does not error — it resolves to the
        note: first match, so the guide's probe returns the STREAMER's state and the rack reports the
        note: guide ready whenever ffmpeg is present. A decorative status indicator reached by
        note: routing instead of by CSS, which is the one thing this repo bars outright. Both
        note: assertions were broken on purpose first (flatten api.py's prefix; mount the two flat in
        note: setUp) and each failed alone, for its own reason.
        note: 2026-08-20 coder — item 2 reopened for one thing and closed again: the rename was
        note: incomplete in the file that ORDERS the rename. `.claude/CLAUDE.md` still told every
        note: session to run `node tests/tuner_failpaths.mjs`, `node tests/tuner_watch.mjs` and
        note: `tests/tuner_fake_provider.py`, all three renamed to `streamer_*` by this item, and it
        note: scoped that rename to item 2 itself ("these become ... under #73 item 2"), so it was
        note: never #76's to fix. The distinction that keeps holding for everything else: #76 owns
        note: the FIGURES, because those need re-measuring against a SHA; this item owns the FILE
        note: NAMES, because a stale count can be re-run by whoever doubts it while a command that
        note: cannot run just fails and reads as a broken suite. The 32/32 and 8/8 keep `e81ffa4`
        note: and stay past-tense; only the paths moved, and the paragraph now says the readings
        note: were taken under the old names rather than re-dating them to today.
        note: 2026-08-20 coder — and CLAUDE.md named four browser suites when there are five.
        note: `streamer_guide.mjs` was not in the list, which is how it sat dead for a fortnight
        note: with nobody running it. Added, ordered last so `studio.mjs` is still "the fourth
        note: suite" the prose below calls it, with its 17/17 and — the part worth having — its
        note: failure mode written down, because ERR_CONNECTION_REFUSED from a suite that generates
        note: its own app.py reads as infrastructure and is this repo's own restructure.
        note: `InvocableDocsTests` generalises it so this cannot recur: every `tests/<file>` inside
        note: a fenced bash block in CLAUDE.md must exist, and every `.mjs` in `tests/` must be
        note: named there. Scoped to the FENCES on purpose — the prose around them deliberately
        note: names retired files, in one place to say out loud that `node tests/tuner_watch.mjs`
        note: cannot run any more, and asserting on the whole file would forbid saying that.
        note: Broken separately: a bash line naming a file that does not exist failed the first and
        note: not the second; deleting the streamer_guide line failed the second and not the first.
        note: `account.mjs`, `stickers.mjs`, `project.mjs` and `code_cli.mjs` are exempted BY NAME
        note: in the test rather than by a loose filter, so it states which suites it is not
        note: holding; the first two are knowingly red and belong to #74's acceptance work.
        note: 2026-08-20 coder — the sweep for this item was route-shaped and missed a class.
        note: Grepping `api/guide` finds route claims; it does not find a sentence that names the
        note: retired SURFACE without naming a path. Five more in HANDOVER, all live claims rather
        note: than dated records: §0's rack list (the seventh row is `streamer` now — the wire
        note: reading itself is left exactly as it came off the wire, with the rename stated
        note: beneath it, because a reading edited to match today stops being a reading), the two
        note: readings tables naming `tuner_*` commands, the frontend.mjs "do not chase these"
        note: line still listing `/api/tuner/{...}`, and the news-bar line saying `tuner-watch.html`
        note: does not load `ui.js`. The remaining 80-odd mentions are dated session records and
        note: why-prose and keep the word. That sweep also caught something not mine: the cell
        note: claiming the only node dependency is vendored at `contrib/llama.cpp/tools/ui/
        note: node_modules` — a path that moved under `references/`, which #74 bars importing. It
        note: is `tests/node_modules`, playwright 1.56.1 pinned in `tests/package.json`, resolved
        note: once in `tests/browser.mjs`; corrected in place with what it used to say, since an
        note: agent reading the old cell would have restored a barred path to fix a suite.
        note: 2026-08-20 coder — `test_no_page_calls_the_retired_api_prefix` guarded `/api/tuner`
        note: and nothing guarded `/api/guide`, so it held one half of a two-half merge. Now both,
        note: and the guide half is the one that can regress quietly: `/api/streamer/guide/...`
        note: does not contain `/api/guide`, so the assertion is silent at the correct prefix and
        note: fires the moment a page reaches for the flat one — which is what the fixture was
        note: doing while it looked like a port fault. Broken by pointing streamer.html's fetch at
        note: `/api/guide/filter`: 1 failed, 8 passed, restored to 9.
        note: 2026-08-20 coder — `ngrep ROW_OF_MODULE` was an anti-check for the same reason
        note: `grep tuner_router` was, and is narrowed rather than deleted. The map IS gone; what
        note: kept the check red is the comment in `test_status_rack.py` explaining why it is gone,
        note: so the only way to turn it green was to delete the explanation. Writing down why a
        note: thing was removed is the behaviour this repo wants, and a check that punishes it is
        note: wrong. It now looks for the ASSIGNMENT — `\nROW_OF_MODULE\s*=` — which is false only
        note: if somebody re-adds the map, which is the thing actually worth catching. Note the
        note: pattern is unquoted on purpose: `run_check` passes it to `re.search` verbatim, so the
        note: quotes in the neighbouring checks are literal characters being matched in the source.
        note: 2026-08-20 coder — item 1 done. `backend/apps/ROSTER.md` is the written roster:
        note: thirteen rows, twenty rack units, identity only — live state stays in /api/status,
        note: which measures it. `apps/roster.py` is the one parser and RAISES on a malformed
        note: row rather than skipping it, because a skipped line loses a rack row silently.
        note: `tools/build_rack.py` now generates the <noscript> fallback from it: every row,
        note: and no `data-state` at all. It carried exactly one row before, chat, hardcoded
        note: `data-state="ready"` — a decorative indicator in the one file nobody looks at,
        note: and worst there, since the fallback renders precisely when the socket that could
        note: have measured it is gone. The state cell reads `&mdash;`, same as the gauges.
        note: The third check above is why `exists` is not enough: `exists` passes on an empty
        note: file, so the gate is `apps/test_roster.py` reconciling the roster against
        note: `build_status()`, the modules' own `status()`, the directory listing,
        note: `controlboard.TOGGLEABLE` and the generated page. All six were broken on purpose
        note: first and each failed for its own reason. `EXPECTED` in `test_status_rack.py` and
        note: `TOGGLEABLE` are deliberately NOT derived from the roster — a tripwire wired to
        note: the thing it watches is not a tripwire — so they stay hand-typed and a test
        note: compares them. `ravencalc` and `remix` are the reason this was needed: neither
        note: has an `__init__.py`, so any roster built by looking for packages drops two live
        note: surfaces without saying so.
        note: The `resolve:` lines that closed #51, #53 and #55 read the filesystem, which is
        note: why they could close themselves the moment the folders moved. The checks above
        note: are chosen the same way — each one is false today and can only be made true by
        note: doing the thing. Two parts of this task have no honest predicate and are
        note: deliberately unmeasured: "every application online" (a reading of a live
        note: process, not of the disk) and the voice/adapter work, which has no single
        note: artefact. Do not invent a check for them; the percentage is allowed to top out
        note: below the work.
        note: 2026-08-20 coder — item 2 verification, and a suite that had rotted for a
        note: reason no rename check would have caught. Advised to prove the two renamed
        note: suites still START rather than trust `exists`, since a check that passes on a
        note: file that dies at startup is precisely the "can pass without the work being
        note: finished" trap. Both are clean: no stale `tuner` string in either, and re-read
        note: 32/32 and 8/8 at f6ed7d3 — the third tree to give that pair and the first
        note: after the rename, which is what makes it evidence rather than repetition.
        note: Those two figures are now current in `.claude/CLAUDE.md` instead of
        note: past-tense, and `e81ffa4` and `c129d81` keep their own stamps beside them.
        note: 2026-08-20 coder — the exemption list inside my own guard was the weak point.
        note: `InvocableDocsTests` exempted four suites and stated a reason for two. An
        note: exemption with no reason is indistinguishable from an oversight, which is how
        note: the next dead suite hides inside the test written to catch dead suites. Fixed
        note: structurally, not by adding two more names: the browser-suite set is now read
        note: off the files' own imports (does it import `./browser.mjs`), so `code_cli.mjs`
        note: falls out as a fact about the file — it drives a PROCESS through
        note: node:child_process, not a browser — rather than as a name somebody typed.
        note: `account.mjs` and `stickers.mjs` stay by name in KNOWN_RED with the reason and
        note: their failure modes written down; they are #74's acceptance work.
        note: 2026-08-20 coder — `project.mjs` was the fourth exemption and it was NOT
        note: knowingly red, so I measured it: 15/16, and the red had nothing to do with the
        note: page. `site/ui.js` fetches /api/news/ticker on EVERY page load — the ticker is
        note: shared page chrome, not a news-page feature — while `tests/project-harness.py`
        note: mounts only the project router, on purpose, because importing backend/api.py
        note: would pull in the governor and could contend for run/gpu.lock.d. Both correct;
        note: together they mean any single-app harness logs a console error on a page it
        note: renders perfectly. apps/news/routes.py already argues this exact case for a
        note: VISITOR (never triggers a fetch, no token, 200 with an empty bar when off,
        note: expressly so an unconfigured box does not put a red line in every console), so
        note: the harness mounts it now and matches production. 16/16 at fdb21b0. It is the
        note: sixth suite in CLAUDE.md and no longer exempt, so the guard holds it.
        note: 2026-08-20 coder — two more stale playwright paths, and this class keeps
        note: recurring because the note is always half-right. `tests/project.mjs`'s header
        note: and `.claude/HANDOVER.md`'s browser-test paragraph both stated as present fact
        note: that Playwright lives in contrib/llama.cpp/tools/ui/node_modules. The HANDOVER
        note: one even recorded correcting that path once before, which makes it read as
        note: freshly checked. That tree is under `references/` now, which #74 bars, so an
        note: agent whose suites would not start could have followed either note to a fix
        note: that went green BY BREAKING THE RULE. Both corrected with the old text quoted
        note: rather than deleted; it is `tests/node_modules`, playwright pinned 1.56.1 in
        note: tests/package.json, resolved only in tests/browser.mjs, which all eight
        note: browser suites import chromium from. Verified both figures before publishing.
        note: 2026-08-20 coder — nothing here changed a task percentage: this is all test
        note: and doc surface. The three remaining #73 FAILs belong to items 3, 4 and 6.
        note: 2026-08-20 coder — ITEM 6, and it was live. Garrett asked whether the live
        note: stack was still down and whether a command would bring most of it online. It was
        note: down and the cause was one string. `712e15b` moved the Rust gateway crate to
        note: `backend/apps/gateway/` with every other app; `ops/symoneural-gateway.service`
        note: kept its ExecStart at `@@ROOT@@/symon-gateway/target/release/symon-gateway`, and
        note: so did `scripts/install-gateway.sh`'s BIN. systemd reported `activating` forever
        note: against a path with no binary at it, `ops/Caddyfile`'s `/api/*` hop to :8000 had
        note: nothing to reach, and the PUBLIC api answered 502 from 13:50 today. Everything
        note: else was healthy the whole time: `symoneural-api.service` active, `/api/status`
        note: 200 on the loopback, all thirteen units reading correctly. The suite was green
        note: throughout, because every suite here exercises `api.py` and nothing read that
        note: unit. Repointed both files, started the binary by hand with the unit's own six
        note: Environment= values, and measured through the public origin: `/api/status` 200,
        note: `/overview` 200, `/api/ws` **101 Switching Protocols**, and 9/13 units ready —
        note: chat image remix ravencalc train streamer coder project sigils. The four dark
        note: ones are dark on purpose: miner and studio are env-gated off, `exp` is queued
        note: (container up, nothing mounted), and `gateway` is the TRON chain-reading app in
        note: `backend/apps/gateway/*.py` needing config — a DIFFERENT thing from the Rust
        note: proxy in the same directory, which is a trap worth knowing about.
        note: 2026-08-20 coder — chat and image are READY and CLAUDE.md still says they are
        note: offline. #74's engine fork landed at `d6b7838`: `engines/symoneural-llm` and
        note: `engines/symoneural-diffuse` are built and on disk, `backend/models/` holds the
        note: gguf and the four FLUX files, and `apps/test_rack_probes.py` is **5 passed**, not
        note: the three deliberate failures documented in CLAUDE.md. That doc paragraph is now
        note: stale in the direction that matters least — it understates the project — but it is
        note: still a figure carried past its tree. Routed to #76 rather than freelanced.
        note: 2026-08-20 coder — a new guard, `backend/apps/test_gateway_unit.py`, 5 tests.
        note: It does NOT assert the binary exists: `target/` is gitignored, so "crate present,
        note: not built" is the honest state of a fresh clone and `install-gateway.sh` already
        note: refuses there with the build command. What it asserts is the pair that actually
        note: broke — ExecStart's directory holds a Cargo.toml whose package name IS the binary
        note: launched, the installer's BIN equals the unit's ExecStart, Caddy's reverse_proxy
        note: target equals SYMON_GATEWAY_BIND, and SYMON_API_UPSTREAM equals api.py's default
        note: port. Every one of those lives between two files and is plausible in each alone.
        note: Proven by breaking: the stale path back in fails 2 of 5, and moving the bind to
        note: :8009 fails the Caddy pair. Both restored, 5 passed.
        note: 2026-08-20 coder — the `__main__` block in test_streamer_migration.py sat ABOVE
        note: `InvocableDocsTests`, so `python3 backend/apps/test_streamer_migration.py` ran
        note: **9 tests** and never collected the guard — an invocation succeeding while doing
        note: less than it says, committed inside the test written to catch exactly that. Moved
        note: to the foot of the file and made to work rather than merely run: 11 tests, OK.
        note: The path insert is worth recording because it is a fact about CLAUDE.md's own
        note: command. There is no `__init__.py` and no pytest config anywhere under `backend/`,
        note: so what puts `backend/` on sys.path is the **`-m`** in `python3 -m pytest`, which
        note: prepends the cwd. Verified both ways: `cd backend && python3 -m pytest
        note: apps/test_roster.py` is 13 passed, and the same line without `-m` is `Interrupted:
        note: 1 error during collection`, zero tests run. That is the no-number-at-all failure
        note: CLAUDE.md warns about, one flag away, and 34 test files carry a `__main__` block
        note: that hits it. Dropping the block would have been the smaller change and the wrong
        note: one: it is repo convention, and a convention that half-works is the thing to fix.
        note: 2026-08-20 coder — `tests/streamer_guide.mjs` generates its own `app.py` and it
        note: does NOT mount news, so it carries the same gap `project-harness.py` had. It is
        note: 17/17 anyway and legitimately: it listens on `pageerror` only, and a 404 on a
        note: fetch raises no page error. So the gap is latent rather than red, and it is a
        note: reason to be careful reading that suite's green — it does not check the thing.
        note: Left alone deliberately: adding a console-error assertion there is item 4's
        note: acceptance work, not this pass's, and it would change what that suite measures.
        note: 2026-08-20 coder — ITEM 6, and the worse half of the same defect. Chasing the
        note: 502 turned up that `scripts/symoneural.sh` keyed every function off `run/api.pid`
        note: while `symoneural-api.service` is `Type=exec` with no `PIDFile=`, so a
        note: systemd-managed API writes none. `status` printed `api        down` and then
        note: printed a correct /api/status JSON underneath it — a readout contradicting itself,
        note: observed while the API had been up 2h38m. Worse: `off` is documented in CLAUDE.md
        note: as THE KILL SWITCH, and it found no pidfile, killed nothing, and printed
        note: "surfaces off. static pages unaffected; the card is free." unconditionally. Even
        note: with a pid it would have lost — the unit is Restart=always / RestartSec=3, so a
        note: kill is a three-second pause. A kill switch reporting success without killing is
        note: the most expensive lie available in this repo, so this was FIXED and not FILED:
        note: ownership is resolved first (unit, then pidfile, then a bare port probe), `off`
        note: uses `systemctl stop` and escalates only with `sudo -n` — a kill switch that
        note: blocks on a password prompt is a kill switch that hangs — and the success line is
        note: now printed only after `port_up` says nothing answers. `status` also gained an
        note: `owner UNKNOWN` reading for a listener with no pidfile and an inactive unit,
        note: because `down` is false there and silently calling it a managed start would hide
        note: a second copy fighting for :8800.
        note: 2026-08-20 coder — `backend/apps/test_service_control.py`, 9 tests, hermetic. It
        note: copies the script into a FAKE repo root with its own `backend/api.py` marker and a
        note: stub `gpu-governor.sh`, and stubs curl/systemctl/pkill/sudo on PATH. That fixture
        note: is not fastidiousness: the first draft ran the script in place, which would have
        note: called the real `gpu-governor.sh release chat` on this machine. A test for a kill
        note: switch must not be able to touch the thing it tests. Proven by breaking — with the
        note: old unconditional success line and pidfile-only status restored, 3 of the 9 fail.
        note: The first draft also asserted the wrong branch and the script was right: with the
        note: unit active and no root it exits 1 saying `sudo systemctl stop ...` rather than
        note: reaching its own kill path, so "refuses loudly" and "verifies nothing is left" are
        note: now two separate tests, because a kill switch owes both.
        note: 2026-08-20 coder — item 3, the plugin interface, is written and asserted:
        note: `backend/apps/studio/plugins/__init__.py` plus `apps/studio/test_plugin_contract.py`
        note: (10 tests). What the disk actually said, which is not what the packages claimed:
        note: exp's docstring opens "Two exports, and they are the whole contract with api.py",
        note: reinforce's opens "Two exports" and discovery's opens "Three exports" — two, two
        note: and three, naming four different sets between them, and nothing checked any of it.
        note: Measured, only `enabled()` and `status()` are present on all three, so those two
        note: are the whole of REQUIRED. `router`, `token_ok` and `LABEL` are RECOGNISED but not
        note: required, because discovery deliberately has no router (its href has no page yet —
        note: apps/voice is the precedent) and reinforce has no module-level token_ok. Requiring
        note: them would have been a contract two of its three subjects fail on the day it was
        note: written, which is CLAUDE.md's "a check that cannot be true is worse than no check".
        note: The gaps are instead pinned in an OPTIONAL_PRESENT map, so gaining or losing one is
        note: a red test rather than silent drift — the tripwire idiom of test_status_rack.py.
        note: 2026-08-20 coder — item 3 is deliberately NOT a loader, and this is the same call
        note: as item 2's abandoned composition refactor. api.py mounts all thirteen surfaces in
        note: one table, each with its own prefix= and tags=, and those tags are the OpenAPI
        note: groups the rebranded Swagger UI renders; a loop either flattens them — changing a
        note: visitor-facing page to make an internal check green — or carries a per-plugin table
        note: of prefix and tags anyway, which is api.py's table with a layer in front of it. A
        note: second reason is written beside each import in api.py: all three are bound to the
        note: PACKAGE name because their bare `enabled`/`status`/`installed` would shadow api.py's
        note: own functions of those names. So the three hand-written imports and three explicit
        note: mounts stay, and what the new file adds is the answer to "what must a fourth package
        note: here provide", plus a test that says whether the three that exist provide it.
        note: 2026-08-20 coder — the row keys are NOT restated in the contract. status() must
        note: return something api.py's Unit model accepts, and copying that field list — plus
        note: its four legal `state` values and four legal `bus` values — into the plugins package
        note: would be a second source of truth with the new file as the stale copy. The test
        note: reads `class Unit` out of api.py as SOURCE via ast, never importing it, the same
        note: discipline as test_status_rack.py and test_studio_models.py, because importing the
        note: serving module builds every rate limiter, resolves the GPU governor and mounts
        note: site/. That assertion earns its place: `state` is a Literal, so a plugin returning a
        note: fifth value is not a nicer label but a pydantic error inside build_status() that
        note: takes the WHOLE rack off the front page. exp and discovery each warn about this in
        note: their own docstring; nothing asserted it for all three at once until now.
        note: 2026-08-20 coder — `check: exists backend/apps/studio/plugins/__init__.py` has been
        note: REPLACED, not supplemented, by `grep OPTIONAL_PRESENT` and `grep StatusRowTests`.
        note: `exists` passes on `touch`, which is exactly the check CLAUDE.md warns can archive a
        note: task before the work is done — and leaving it beside the narrowed greps would still
        note: have added a free pass to the denominator. Same reasoning as item 1's real gate
        note: (`grep RosterMatchesApiTests`) and item 2's three narrowed greps.
        note: 2026-08-20 coder — break-proofs, run before the file was trusted: setting
        note: discovery's bus to "network" and adding a stray key turned exactly two tests red
        note: (the Literal test and the extra-field test) and nothing else; dropping "discovery"
        note: from PLUGINS turned the directory tripwire and the OPTIONAL_PRESENT map red. Both
        note: reverted, 10/10 green. There is also a deliberate vacuity guard —
        note: test_the_unit_model_was_read_at_all — because if the ast walk found nothing, every
        note: row assertion below it would pass on an empty set.
        note: 2026-08-20 coder — one side effect, measured rather than assumed:
        note: apps/studio/plugins/ was the only PEP 420 gap in a chain that has
        note: apps/studio/__init__.py above it and an __init__.py in each plugin below it. Adding
        note: this file makes it a regular package, which changes the module name pytest derives
        note: for the (--ignored, own-venv) suite under plugins/reinforce/tests/, so the whole
        note: suite was re-run across the commit rather than carried forward. The contract imports
        note: NO plugin at import time: api.py imports this package's children during startup, and
        note: a parent that eagerly imported all three siblings would drag discovery — which
        note: api.py neither imports nor mounts — into the serving process for free.
        note: 2026-08-20 coder — fixed in the same commit, both stale since the restructure and
        note: both inside the files item 3 makes you read: exp/__init__.py said `from apps import
        note: symoneuralexp as exp` and discovery/__init__.py said `from apps import
        note: symoneuraldiscovery`. Neither import exists; api.py:137 is `from apps.studio.plugins
        note: import exp`. Same class of defect as the ExecStart path that took the public API
        note: down — a path that does not move with the code it names.

        **Updated 2026-08-20 at `597ec8c`, read from the disk, not carried forward: 21 of 24
        checks pass and these three do not.**
        `grep 8188 -- backend/apps/studio/registry.py` — RETIRED 2026-08-20 at `0cb59d0`; see
        the note below. Replaced by `grep ComfyPortAgreementTests -- .../test_comfy_port.py`.
        `exists ops/symoneural-deploy.service` — nothing yet makes a staged page reach the
        webroot on its own, which is the whole reason a rename shipped to `site/` and stopped
        there.
        `ngrep exp.status() -- backend/api.py` — RETIRED 2026-08-20 at `43c65f4`; satisfying it
        meant deleting a row four other authorities require. See the note below. Replaced by
        `grep PluginRowsMatchRosterTests -- backend/apps/test_roster.py`.

        **Upgraded, because the title promises something the checks never measured.** "Every
        application online" is not proven by twenty-four greps for symbols; it is proven by
        asking the running server what it serves. So this task now owes a reading: every row in
        `ROSTER.md` answers on the address the roster gives for it, taken from a server started
        on a spare port, with the result written down and stamped. That is also the report he
        has been owed since he said "let me know when the server is complete" — which cannot be
        answered honestly out of a task percentage.

        check: exists docs/SERVER-READY.md
        check: grep \n\|\s*gateway\s*\| -- docs/SERVER-READY.md
        check: grep EveryRosterRowAnswersTests -- backend/apps/test_server_ready.py

        note: 2026-08-20 coder — three of this task's checks were replaced before any of them
        note: was satisfied, because all three could have gone green without the work being
        note: done. Same class as the two this block already retired (`grep tuner`, which
        note: matched guide's docstring, and `grep "include_router"`, which matched prose).
        note: (1) `grep ^| docs/SERVER-READY.md -- docs/SERVER-READY.md` was VACUOUS. run_check
        note: hands the pattern to re.search verbatim, and `^|` is alternation with an empty
        note: right-hand side, so it matches every string including "". Verified:
        note: re.search("^| docs/SERVER-READY.md", "") is a match. A bare `touch` of the file
        note: would have turned it green, and with `exists` beside it that is two of the three
        note: for an empty file. Now `\n\|\s*gateway\s*\|`, which needs a real per-row table
        note: line. Written with `\n` and not `^` deliberately: run_check does NOT pass re.M,
        note: so `^` anchors to the start of the whole file — the same reason the
        note: ROW_OF_MODULE check above is spelled with `\n`.
        note: (2) `grep EveryRosterRowAnswersTests -- backend/tests/test_server_ready.py` named
        note: a directory that does not exist AND that nothing collects. The suite runs as
        note: `cd backend && pytest apps/ -q`; `backend/tests/` is not on that path, so the file
        note: could have been created, the check flipped green, and the test never once
        note: executed. Repointed at `backend/apps/`, which the documented invocation does
        note: collect. Verified before repointing: `pytest tests/ -q --collect-only` reports
        note: "no tests collected", and there is no pytest.ini/pyproject anywhere to add it.
        note: (3) `grep 8188 -- backend/apps/studio/registry.py` was MIS-SPECIFIED. Its prose
        note: said the ComfyUI port is "hard-coded somewhere other than the registry that is
        note: supposed to own it" — but registry.py is the agent TOOL registry (signature
        note: introspection, JSON Schema generation) and holds no addresses at all. Satisfying
        note: it meant writing a port constant into a file with no business holding one, to
        note: move a percentage. The module that owns the address is comfy.py, and it already
        note: does it correctly: base_url() reads SYMONEURAL_COMFY_URL, then _HOST/_PORT, then
        note: the constants, and api.py:87 promotes the legacy SYM_ spelling the shell accepts.
        note: The real defect in that area is the one nothing was watching: comfy.py and
        note: scripts/comfyui.sh each carry their own 8188, edited by different kinds of change
        note: — the same two-files-one-value shape as the ExecStart path that took the public
        note: API down. Drift there does not crash: comfyui.sh reports success and writes a
        note: pidfile, and every render then fails `comfyui_unreachable`. Replaced by
        note: apps/studio/test_comfy_port.py, 4 tests, green — and proven to measure something
        note: by editing comfyui.sh to 8199 and watching it go red naming both ports, then
        note: restoring. It carries its own vacuity guard: if either file is restructured so
        note: the parse finds nothing, it raises rather than comparing two absences.
        note: 2026-08-20 coder — a FOURTH, found the same way and worse than the other three,
        note: because this one was actively wrong rather than merely weak.
        note: `ngrep exp.status() -- backend/api.py` said "Exp is still a rack row at
        note: api.py:1783 after being migrated into Studio, so the rack claims a unit that is a
        note: plugin". Turning it green means deleting that row. Four things on disk require it:
        note: ROSTER.md lists `exp` as row 13 and states in prose "exp is the only plugin with a
        note: row of its own"; EXPECTED in apps/test_status_rack.py is a hand-typed 13 ids
        note: including it; tools/build_rack.py emits it into the no-socket fallback; and
        note: site/exp is a live page. A fifth argues the mechanism: apps/studio/plugins/
        note: __init__.py is headed "This is a conformance contract, NOT a loader" and spends a
        note: section on why api.py's three hand-written mounts must stay — a loop either
        note: flattens the OpenAPI tags a visitor-facing Swagger page renders, or re-implements
        note: api.py's table one layer further away. So the check asked for a real unit to be
        note: taken off the front page, and two suites to go red, to move a percentage.
        note: Retired, not replaced in kind — the invariant it groped for is already held by
        note: `grep RosterMatchesApiTests`, which is a check on this same task. What was
        note: genuinely unasserted is the DECISION: nothing anywhere said exp is the only
        note: plugin with a row, so that sentence in ROSTER.md was prose nothing checked, which
        note: is the exact failure the rest of test_roster.py exists to close. PluginRowsMatch
        note: RosterTests now pins it in the direction the disk supports, with a vacuity guard
        note: (two empty sets are equal) and a note saying that folding exp into the studio row
        note: means editing this test, which is where that argument should be made.
        note: Proven: injected `Unit(**discovery.status())` beside exp in api.py, watched both
        note: new assertions go red naming `discovery`, then restored. 22 passed across
        note: test_roster.py and test_status_rack.py after.

◻ #74 — Rebrand everything that ships: engines, models, interface, naming system
        owner: coder
        Folds #20 #25 #27 #33 #40 #71. Read those blocks in
        `review/CONSOLIDATED-TASKS-2026-08-20.md` before working any part.

        **The rule that makes this blocking rather than cosmetic**, Garrett 2026-08-20: *"we
        cannot use code in references its for reference only we must rebrand if we want to use
        it"*, and *"we can put them in the best professional folder location"*. So
        `references/` is a read-only reading room: nothing under it may be imported, built or
        shipped. A rebranded tree lives in its own proper location and is what the build points
        at. Choosing that location is mine to do and to write down here when I do it.

        **The standard, widened 2026-08-20.** Garrett: *"we should have the goal of rebranding
        and/or writing fresh code for everything. You better have a really good and justified
        reason for not doing so and this includes what is in the requirements.txt for python
        modules"*, and then the line that draws the boundary: *"nvidia sources i understand being
        locked down as of right now i see no other sources as 'locked down' and they should be
        recreated"*. So the default for every dependency is **recreate**, and not-recreating is
        the thing that needs an argument written down beside it.

        **The one exemption, in his words:** *"only thing that doesnt get rebranded is CUDA to my
        knowledge"*, and *"CUDA can be moved out of references to the professional repo location
        if needed as well as other nvidia sources"*. CUDA, cuDNN, NVENC, nvidia-smi and the driver
        stay named as they are — they are proprietary, they are the hardware's own interface, and
        renaming them would make every measured figure on the site unverifiable. They may still
        move out of `references/` into the built tree; the exemption is from *renaming*, not from
        the relocation.

        **The method is mine, the outcome is his.** Garrett 2026-08-20: *"i dont care if you
        rebrand, recreate or write it completely from scratch with no references i just put the
        references there to make it easier"*. So there is no question to ask him per dependency,
        and no need for a plan approval before starting one: pick whichever of the three is
        honest for that component and write the choice down in `backend/DEPENDENCIES.md`. What is
        NOT mine is the outcome — nothing ships under a third-party name, and nothing under
        `references/` is imported, built or linked. Those two are the acceptance test.

        1. **The engines** (#33). `llama-server` → `symoneural-llm`, `sd-cli` →
           `symoneural-diffuse`, `kawpowminer` → `symoneural-miner`, `whisper` →
           `symoneural-listen`, and vLLM — *"im cloning vllm into references for reference
           rebranding"* — as the fifth. Our tree, our build script, our binary names, MIT
           notice carried (LICENSES.md:119-120 records the engines as MIT, so renaming is
           permitted). Then repoint `backend/api.py:154-155`, which today reaches straight into
           `contrib/llama.cpp` and `contrib/stable-diffusion.cpp` and is exactly the import
           from a reference tree the rule above forbids.
        2. **The render UI** (#20). ComfyUI → `symoneural-ui`, and it is GPL-3.0, not MIT — so
           unlike the engines this one carries a source-offer obligation. Rebranding is
           permitted; quietly dropping the licence is not.
        3. **The models** (#71). *"same thing goes for models in /backend/models they shall all
           be rebranded"*. A vendor filename on disk becomes a vendor filename in a log, then
           in an error message, then on a page. Rename every artefact and write
           `backend/models/NAMES.md` mapping each SyMoNeuRaL name to its upstream model and
           licence — that table is what the site renders attribution from.
           **`built on Qwen2.5-7B-Instruct` is an Apache-2.0 condition, not decoration.** It
           was once truncated to `…7B-Ins…` by a CSS ellipsis and that was treated as data
           loss. Rebranding must not repeat it: rename the file, keep the attribution.
           `backend/models/PROVENANCE.json` already exists and is the thing to build on.
        4. **The naming system and the interface** (#25, #27, #40). Apply SymonSays across code
           and site, fix Live Stack typography, promote the app brand icons, finish the
           `symoneural-cli` polish. This part is last because it is taste applied over
           substance, and #25 in particular — "apply a naming system tastefully" — has no
           predicate that means done. It is unmeasured on purpose.

        5. **The Python dependency layer** — new, and the widened standard's hardest case.
           Six `requirements.txt` files ship (`backend/apps/remix`, `backend/apps/studio`,
           `studio/plugins/reinforce`, `studio/plugins/discovery`, `apps/cryptominer/…PROD…`,
           `deploy/bento`), and the serving path deliberately has none — it runs on the system
           interpreter's fastapi, uvicorn, pydantic and sympy. Three different jobs hide under one
           word here and they must not be conflated:
           - **Recreate** what is small enough to own and central enough to matter. `sympy`'s use
             here is `sympify`, `diff`, `integrate`, `solve`, `latex` — RavenCalc is a thin surface
             over a handful of calls, and a SyMoNeuRaL symbolic core is a real project rather than
             an impossible one. Same for the SSRF/fetch helpers and anything under 2 kLOC.
           - **Facade** what cannot honestly be recreated. No application module may name a
             third-party package directly; imports go through our own module so the vendor name
             appears in exactly one file per dependency and the swap is a one-file change later.
             This is the answer to "rebrand a library you install from PyPI": the import name *is*
             the package's identity, so the rebranding that is actually available is the boundary.
           - **Argue, in writing, for the rest.** `backend/DEPENDENCIES.md` gets one row per
             package: what it does, what replacing it would cost, and the decision. A row with no
             reason is the failure this item exists to prevent. My standing candidates for *keep*
             are the ASGI stack (fastapi/uvicorn/pydantic) and torch — rewriting an ASGI server or
             an autograd engine would take the site's numbers *down*, which is the opposite of the
             point. That is the argument; it goes in the file to be accepted or overruled.

        6. **Swagger UI** — Garrett 2026-08-20: *"Swagger UI needs to be rebranded also"*. This is
           `backend/api.py:1477-1496`: `get_swagger_ui_html` with our palette laid over it and the
           assets served from this box (`/swagger-ui-bundle.js`, `/swagger-ui.css`,
           `/swagger-dark.css`). Today it is Swagger wearing our colours and it still says Swagger.
           The API reference is a visitor-facing page and should be a SyMoNeuRaL surface: our own
           renderer over `/openapi.json`, our own asset names, no `swagger` in a URL a visitor
           sees. Apache-2.0, so the notice moves to `LICENSES.md` and does not vanish.

        7. **SymPy on the RavenCalc surface** — Garrett 2026-08-20, pasting the live page: *"SymPy
           needs rebranding also this from the https://symoneural.com/ravencalc.html"*. It is named
           in **16 site files** and 3 backend files (`sympy` lowercase in 1 more site file and 9
           backend), including the page's central claims — "RavenCalc is SymPy underneath", "SymPy
           computing it", "The keys type SymPy". Note what survives the rename and what does not:
           the *argument* is "exact symbolic computation, not a language model guessing at algebra",
           and that sentence is true of a SyMoNeuRaL engine word for word. Only the vendor's name
           goes. BSD-3-Clause requires the notice in accompanying documentation, so it moves to
           `LICENSES.md`; it is not deleted. Pairs with item 5's recreate case.

        note: 2026-08-20 — the licence position for the whole task, written once so no part of it
        note: has to re-derive it. Renaming a permissively licensed dependency in what we ship is
        note: allowed by MIT, BSD-3-Clause and Apache-2.0 alike; what none of the three allow is
        note: dropping the copyright notice from the accompanying materials. `LICENSES.md` is that
        note: material and is where every notice lands. Two carry more than a notice: ComfyUI is
        note: GPL-3.0, so a rebranded derivative still owes a source offer and still has to stay
        note: GPL — which is exactly why "recreated" is the cheaper path there, not the dearer one
        note: — and Apache-2.0 §6 grants no trademark rights, which means using the upstream mark
        note: is the legally weaker choice and rebranding is the safer one. The precedent is
        note: already set in this repo: `built on Qwen2.5-7B-Instruct` is called an Apache-2.0
        note: condition in `.claude/CLAUDE.md`, and every `text-overflow:ellipsis` rule was
        note: deleted from the CSS because that attribution had been truncated to `…7B-Ins…`.
        note: So: the presented name is ours to change, the notice is not ours to remove.

        note: The two `ngrep`s match the quoted literals `"llama.cpp"` and
        note: `"stable-diffusion.cpp"`, not the path `contrib/llama.cpp`. `api.py:154-155`
        note: builds those paths from segments — `ROOT / "contrib" / "llama.cpp" / ...` — so
        note: the path form never appears in the file and an ngrep on it was trivially true.
        note: Both checks passed on a tree where nothing had been rebranded, which would have
        note: archived this task at 100% with the whole job outstanding.

        **Never blind-replace `MIT`.** Most matches in this corpus are ordinary words — limits,
        limited, submit, emits. Whole phrases and filesystem paths only.

        check: ngrep "llama\.cpp" -- backend/api.py
        check: ngrep "stable-diffusion\.cpp" -- backend/api.py
        check: grep symoneural-llm -- backend/api.py
        check: grep symoneural-diffuse -- backend/api.py
        check: exists backend/models/NAMES.md
        check: grep upstream -- backend/models/NAMES.md
        check: exists backend/DEPENDENCIES.md
        check: grep "would cost" -- backend/DEPENDENCIES.md
        check: ngrep "swagger" -- backend/api.py
        check: ngrep "SymPy" -- site/ravencalc.html

        **Updated 2026-08-20 at `597ec8c`: 6 of 10 checks pass.** The four engine checks are
        green — `api.py` names `symoneural-llm` and `symoneural-diffuse` and no longer names
        either upstream engine — and so are the Swagger and SymPy ones. What is missing is the
        written half: `backend/models/NAMES.md` and `backend/DEPENDENCIES.md` do not exist, so
        the mapping from our name to the upstream it came from lives nowhere a reader can check.
        A rebrand with no attribution table is the failure mode this task exists to avoid: the
        Apache-2.0 notice for Qwen2.5-7B-Instruct is a licence condition, not a courtesy.

        **Upgraded to cover the interface, which is where the next rebrand leak will come from.**
        Porting `references/deepseek-harness`'s design tokens is now real work (#91), and every
        variable in that file is named `--dsw-static-deepseek-450` and similar. Served CSS and
        JS must not carry `dsw` or `deepseek` in any identifier, class name or comment, and the
        grep that proves it belongs here rather than in the task doing the porting — a task that
        renames things should not also be the task that certifies the renaming.

        check: exists backend/models/NAMES.md
        check: ngrep dsw- -- site/symoneural.css
        check: ngrep deepseek -- site/ui.js
        check: grep NoUpstreamIdentifiersTests -- backend/tests/test_brand_boundary.py


◻ #75 — Secrets, credentials and leak containment
        owner: coder
        Folds #37 #38 #39 #48. Read those blocks in
        `review/CONSOLIDATED-TASKS-2026-08-20.md` before working any part.

        Two live secrets are sitting in the working tree — `backend/apps/remix/.env` and
        `backend/apps/cryptominer/miner.env` — and #48 names `VLLM_API_KEY` and `DJ_TOKEN` for
        rotation. Rotate, then untrack, in that order: untracking a key that is still valid
        moves it out of sight without making it harmless.

        1. **Rotate and untrack** (#48). Both keys, then the `.env` files out of the tree and
           into whatever #39 builds, with `.gitignore` entries so they cannot come back.
        2. **Split rotation by who issues the secret** (#37). Anything I can rotate, I rotate
           on a schedule. Anything only Garrett can issue — a third-party dashboard with no
           API, a payment credential — is his half, and the automation's job there is to tell
           him it is due, not to pretend it rotated.
        3. **`symoneuralcredentials`, CLI-driven** (#39). One place credentials live, one
           command that reads them, nothing in a repo file.
        4. **Extend the leak guard to every archive path** (#38). The guard exists for the
           live tree; `review/`, `docs/archive/` and the retired-assignment files are archive
           paths that receive whatever was typed on an entry, which is precisely where a
           pasted credential would land unnoticed. This matters more now: #77 makes every
           prompt a file, and a prompt is exactly where a key gets pasted by accident.

        **The two protected artefacts are in scope here as a boundary, not as work.**
        `training/corpus.jsonl` and `training/build_dataset.py` are trade secret, protected
        only by not being public, and `corpus.jsonl` **is currently tracked in git**. There is
        no remote, which is doing all of the protecting. If a remote is ever added, that is the
        thing to audit first — publish the numbers, keep the methods.

        check: absent backend/apps/remix/.env
        check: absent backend/apps/cryptominer/miner.env
        check: exists scripts/symoneural-credentials
        check: exists tools/rotate_secrets.sh
        note: There is no check here for "the keys were actually rotated" and there cannot be
        note: one from the disk — a rotated key and a stale key look identical to a grep. The
        note: absence checks prove the files left the tree, which is the part a filesystem can
        note: judge. Do not add a check that reads a secret to prove it changed.

◻ #77 — The task surface: a prompt becomes an assignment becomes a task, automatically
        owner: coder
        Folds #57 #58 #59 #64 #72. Read those blocks in
        `review/CONSOLIDATED-TASKS-2026-08-20.md` before working any part.

        Garrett, 2026-08-20: *"make sure as soon as i send a prompt it gets added to intake.md,
        automatically get pushed to task if no barriers and if they do have barriers remain in
        the intake.md/progress.html with specifics on the barrier and make sure when you
        complete task they auto remove from progress.html"*. And, when #68 still read "four
        frontends" minutes after he had cut it to one: *"i know its not working because i just
        told you to not worry about anything other than the browser api applications and task
        #68 is still in progress.html"*. That second message is the acceptance test: the page
        must reflect an instruction within the turn it arrives, without me being told twice.

        This changes the gate. Ticking `[x]` was his gate on promotion; an assignment with no
        barrier now promotes itself. It does **not** add a fourth state — capture, promote, or
        drop with a reason — and the header of this file has been rewritten to say so.

        1. **Capture.** A prompt hook appends every prompt to a private source file, mode 600
           and gitignored like `GARRETT-REQUESTS.md`. **Fail open**: a broken hook must never
           block a prompt. The file must never be reachable from a public surface — `/api*` is
           proxied to the internet, which is why the write endpoints are `/local/*` behind a
           peer-address check, and a prompt is exactly where a credential gets pasted by
           accident (see #75).
        2. **Filter.** Not every prompt is an assignment; "continue" is not work. The predicate
           is his own standing test: *"if it isnt going to break our project and its something
           that will resolve itself naturally DROP IT"*, plus the two corollaries — a rule
           already written down is not outstanding work, and a request already satisfied is not
           outstanding work. Anything filtered out is dropped to
           `review/RETIRED-ASSIGNMENTS.md` with the reason. Never silently discarded.
        3. **Promote, or state the barrier.** No barrier means a task number, automatically.
           A barrier means the entry stays on `INTAKE.md` and on the page saying **what** blocks
           it, drawn from the five owner-garrett categories that already exist plus "this is a
           question only he can answer". No new taxonomy — a sixth reason invented here is the
           rejected fourth state wearing a different hat.
        4. **Removal on completion.** `tools/archive_tasks.py` already removes a task at 100%,
           and it works: #51, #53 and #55 archived themselves this way when the folders moved.
           But only a task with checks can reach 100%, so this part is gated on the checks
           declared throughout this list (#59). That is a dependency to respect, not a reason
           to loosen a check — an over-loose check archives live work, which is worse than a
           row that reads `no checks`.
        5. **Verify it, don't promise it** (#57, #64). A prompt that never reached the ledger
           at all is invisible to the coverage panel, so `tools/check_intake.py` sweeps the
           transcript for user turns with no matching entry. And every assignment still needs
           the brief he can decide on — what it is, what it costs, what I recommend and why,
           and what happens if it is never ticked.
        6. **Drain the ledger to four** (#58). *"our request ledger should hardly ever exceed 3
           or 4 items"*. An entry that has become a task closes; a standing rule moves into the
           working agreements; history moves to `review/`.

        **Barrier now means something different, and the file has to say so.** "An assignment
        with no `task:` line" described a queue nobody was draining. Under auto-promotion the
        only uncarried assignments are the genuinely blocked ones, so rewrite that paragraph in
        `INTAKE.md`'s header in the same change rather than leaving two meanings in play.

        check: exists tools/check_intake.py
        check: maxcount 4 ^status: (captured|queued|in-progress|held) -- GARRETT-REQUESTS.md
        check: grep RECOMMEND -- tools/build_intake.py
        check: exists .claude/hooks/capture-prompt.sh
        check: grep UserPromptSubmit -- .claude/settings.json
        check: grep barrier -- tools/build_intake.py
◻ #79 — SyMoNeuRaL Image: image-to-image, and parameters the visitor can actually turn
        owner: coder
        R-152. "add image to image as well as parameter adjustment to symoneural image."

        Today the surface takes a prompt and nothing else. No init image, and no exposed steps,
        guidance, seed or size — so a visitor cannot reproduce a render they liked or steer one
        they nearly liked. Both are already parameters of the engine underneath; this is
        surfacing them, not inventing capability.

        The honesty rule bites directly here: **every control shown must reach the engine.** A
        slider that is read and thrown away is the decorative-status-LED failure with extra
        steps, and it is barred. If a parameter cannot be plumbed yet, it does not get a widget.

        Seed is the one to get right first, because it is what makes a render repeatable, and
        repeatable is the whole argument of this site.

        check: grep init_image -- backend/api.py
        check: grep img2img -- backend/api.py
        check: grep ImageParamsTests -- backend/apps/test_image_params.py

◻ #80 — The prompt placeholder on every surface is that surface's Symon Say name
        owner: coder
        R-153. "also replace make it draw something with symonsayimage", then "talk to the box in
        symon chat needs to be replaced with symonsaychat".

        Two instances of one rule, so it is worked as the rule: the input placeholder on a surface
        is the surface's own name in the house `symonsay<thing>` spelling, not a jokey
        instruction. Image's heading is `Make it draw something.` in `tools/build_pages.py:5769`;
        Chat's title is `SyMoNeuRaL Chat — talk to the box` at `5756`. Both are generator strings,
        so the generated page has to be rebuilt in the same commit or the site still says the old
        thing — and then `build_cachebust.py` last, because that rebuild strips the stamps.

        Read the other surfaces and bring them into line rather than leaving a mix of two
        conventions, which is what "replace X with Y" twice in one minute is telling us.

        check: ngrep Make it draw something -- tools/build_pages.py
        check: ngrep talk to the box -- tools/build_pages.py
        check: grep symonsayimage -- tools/build_pages.py
        check: grep symonsaychat -- tools/build_pages.py
        check: ngrep Make it draw something -- site/image.html
        check: ngrep talk to the box -- site/chat.html

◻ #81 — /livestack/<name> for every application, and every app page static HTML + JS + CSS
        owner: coder
        R-154, and it absorbs the URL half of #73 item 4. "the https://symoneural.com/image.html
        needs to be updated to https://symoneural.com/livestack/image and the image html should be
        static with json and css", corrected by him one minute later — "**correction not json it
        was suppose to be js**" — then scoped: "apply this to all applications."

        Two halves. The addresses: `/livestack/<name>` for every application surface, done in
        `api.py` the way `SECTION_PAGES` already does the four front-page sections, because
        FastAPI does all the routing and `ops/Caddyfile` has no rewrites and must not grow any.
        The structure: each page is static HTML with its behaviour in a `.js` file and its styling
        in a `.css` file, rather than markup with logic inlined into it.

        **The old URLs cannot simply stop existing.** `/image.html` is published and shared;
        `SECTION_PAGES` handles this the right way already and says so in its comment — the clean
        URLs "are an addition, not a redirect", and the `.html` files stay reachable. Same here. A
        404 on a link that used to work is the one failure this site cannot afford.

        Do image first, all the way through, and only then repeat it — a pattern proven on one
        page is worth more than nine half-migrations.

        check: grep LIVESTACK_PAGES -- backend/api.py
        check: grep LivestackRouteTests -- backend/apps/test_livestack_routes.py
        check: exists site/image.js
        check: grep /livestack/image -- tests/frontend.mjs

◻ #82 — symoneural-remix: export a playlist in a form YouTube Music and Spotify will take
        owner: coder
        R-155. "symoneural-remix needs to have means of exporting the playlist to a form that can
        be uploaded to youtube music and spotify."

        Export, not integration: a file the visitor downloads and uploads themselves. That
        distinction is what keeps this free of credentials, OAuth apps and third-party API terms —
        nothing here needs Garrett, which is why it is a coder task.

        The work is "which format, and does a real import actually accept it". Answer it by
        testing an import, not by reading a doc: both services take a CSV of track/artist/album
        through the common transfer tools, and Spotify additionally reads a plain list of track
        URIs. Write the exporter as a pure function over the playlist so it can be tested with no
        engine and no `symon_capture` import — `apps/remix/tests` is `--ignore`d from the suite for
        exactly that reason, so a test that lands there is a test nobody runs.

        check: exists backend/apps/remix/playlist_export.py
        check: grep PlaylistExportTests -- backend/apps/test_playlist_export.py


◻ #83 — Remove SyMoNeuRaL Project completely; put a cowork inside SyMoNeuRaL Chat
        owner: coder
        R-161, which supersedes the first half of R-156. He looked at `/project` and said it "is
        not what symoneural project was intended to be", then: "to keep it from being confusing
        remove symoneural project completely and just integrate a "cowork" into the symoneural
        chat".

        The reason he gives is the specification: **to keep it from being confusing.** A separate
        surface that half-does what Chat should do is worse than no surface. So Project goes — rack
        row, page, app package, browser suite, harness — and Chat gains a cowork: the project the
        conversation is about, the files it touches, what happened last time, inside the chat
        surface rather than beside it. Not the old thing mounted inside the new one; that moves
        the confusion instead of removing it.

        Three consequences to handle in the same commit rather than discover afterwards. The rack
        goes thirteen rows to twelve, and `apps/test_status_rack.py` asserts that on purpose —
        typing the new number is the point. `tests/project.mjs` and `tests/project-harness.py` are
        the sixth browser suite and are documented at length in `.claude/CLAUDE.md`, so deleting
        them means deleting what that file says about them in the same change: a paragraph
        describing a suite that cannot run is worse than a stale count, which that file says about
        itself. And the harness lesson survives the deletion — **any single-app harness must mount
        news**, because `site/ui.js` fetches `/api/news/ticker` on every page load.

        check: absent site/project.html
        check: absent backend/apps/project
        check: absent tests/project.mjs
        check: ngrep "project" -- backend/apps/test_status_rack.py
        check: grep cowork -- tools/build_pages.py
        check: grep CoworkTests -- backend/apps/test_cowork.py

◻ #84 — RavenCalc: the calculator at the top of its own page
        owner: coder
        R-157. He pasted the preamble block verbatim, asked for it to be "removed from where it
        is" and merged into the sentence below the heading, and stated the goal plainly: "so that
        the top of the calculator is at the top of the page".

        A visitor arriving at the calculator should land on the calculator. Two blocks currently
        say nearly the same thing twice — one above the tool, one under the heading — and the
        instrument is below both.

        **Not a trim.** Layout changes must not drop data: the CPU-never-queues fact and the
        not-a-language-model claim are both load-bearing arguments about what this surface is, so
        they move and merge, and anything long folds into `<details>`. No `text-overflow` — that
        rule has no exceptions here.

        Same page as the standing SymPy rebrand request, and deliberately not doing it: that is
        its own task, and re-typing the word here is the edit that would hide it.

        check: grep RavenCalcTopTests -- backend/apps/test_page_layout.py
        check: grep ravencalc-instrument-first -- tests/frontend.mjs

◻ #85 — The miner page, embedded the way RavenCalc is
        owner: coder
        R-158, with a screenshot. "this looks terrible make it more embedded like symoneural
        ravencalc".

        The complaint is legible in the picture: a wide prose preamble, then two tall bordered
        cards of label/value rows, code blocks and folds, with the whole thirteen-row rack bolted
        down the right — and the actual instrument, a token field and two buttons, two thirds of
        the way down one card. The page reads as documentation with a control panel hidden in it.

        "Embedded like RavenCalc" is the reference to build to: there, the tool IS the page — one
        inset surface at the top, explanation around and below it. Pairs with #84, which asks for
        exactly that on RavenCalc itself.

        Every telemetry row, every token-required reading, the "starts by itself and holds the
        card" warning and the measured hashrate paragraph survive the restyle — folded, not
        trimmed. And every READY/OFFLINE pill in that rack is a real reading and stays one.

        check: grep MinerEmbeddedTests -- backend/apps/test_page_layout.py
        check: grep miner-instrument-first -- tests/frontend.mjs


◻ #86 — A page can ship to site/ and never reach the webroot, and nothing goes red
        owner: coder
        R-159. "symoneural streamer page cant be found". Reproduced from the public origin
        immediately: `404 /streamer.html`, `200 /tuner.html`, and `/var/www/symoneural/` still
        carrying the old name. `site/` is correct and no page references `tuner.html` — the rename
        (#73 item 2) simply never reached the live tree, because `deploy.sh` needs root and had
        not run since. Visitors following the nav got a 404 on a page that had existed here for
        hours.

        The immediate fix is one command and it is Garrett's, because it needs a password only he
        has: `sudo ./scripts/deploy.sh`. Told to him directly rather than filed.

        **The defect is that nothing noticed.** This is the same shape as the ExecStart that took
        the public API down: a name changed in one place and not the other, with no check
        comparing the two. So `tools/check_deployed.py` compares the staging tree against the live
        webroot and names what is stale, missing or orphaned, and a test covers it. Pairs with #73
        item 6 (`ops/symoneural-deploy.service`), which is what stops it happening again rather
        than just reporting it.

        check: exists tools/check_deployed.py
        check: grep WebrootDriftTests -- backend/apps/test_check_deployed.py

◻ #87 — SyMoNeuRaL Coder: the browser surface first, the terminal inside it, at /live-stack/coder
        owner: coder
        R-160, restated by him on 2026-08-20: "update task 87 to be browser then terminal url
        should be symoneural.com/live-stack/coder". Order and address are both part of the
        instruction and neither is negotiable — **browser then terminal**, and the surface lives
        at `/live-stack/coder`, not at `/coder.html` and not at `/documentation.html`.

        `api.py:1724` gives the Coder row `href="/documentation.html"` — a page about the project
        — so the one surface whose entire point is that you can use it hands you a manual.

        **Two steps, in his order, and the first is not a stub.** The browser surface is the
        deliverable: the page, its layout, its own HTML + JS + CSS per #81, reading as an
        instrument per #91. The terminal is what goes inside it once the page it lives on is
        real. Building the pty first and hanging a page off it is the inversion he has now told
        me to stop doing twice.

        **`live-stack`, hyphenated, is what he typed, and it is not what the code says.**
        `api.py`'s `SECTION_PAGES`/`_section_route()` mount `/livestack`, and #81 is written
        against that spelling. Serve his spelling — it is the address he will type — and keep
        `/livestack/coder` answering as well rather than breaking every existing link on the
        way past. Two routes to one page is not an alias in the Caddy sense the rules bar; the
        rule there is that the web server does no routing, and this is FastAPI doing all of it.
        Fix #81's title in the same commit so the two tasks do not name different addresses.

        Reference only, and the rule has no exception here: "we cannot use code in references
        its for reference only we must rebrand if we want to use it", and "i dont care if you
        rebrand, recreate or write it completely from scratch". `references/deepseek-harness`
        has `TerminalBlock` and `ansi.ts` under `packages/client/ui-primitives/src/`; read them
        for behaviour and build ours. Exceed it, per his standing bar.

        `/api*` is proxied to the public internet, so a browser terminal here is the most
        dangerous surface in this repo. Where the gate lands is #88's decision, not this
        task's, and whatever #88 decides, the two trade-secret training artefacts stay
        unreachable through it.

        check: ngrep href="/documentation.html" -- backend/api.py
        check: grep live-stack/coder -- backend/api.py
        check: exists site/coder.html
        check: grep CoderSurfaceTests -- backend/apps/tests/test_coder_surface.py
        check: grep coder-instrument-first -- tests/frontend.mjs

◻ #88 — No tokens while we are testing: take the token requirement off Studio
        owner: coder
        R-162. "symoneural studio does not need to require SYM_STUDIO_TOKEN we are testing
        everything without keys and tokens."

        Standing, not Studio-only: *everything*, while testing. Today Studio answers 503 unless
        both `SYMONEURAL_STUDIO_ENABLED=1` and `SYMONEURAL_STUDIO_TOKEN` are set, and the same
        double gate sits on Reinforce, Exp, Miner, ASIC and Discovery. Every one is a surface he
        cannot use on his own site without exporting a secret first, which is the whole complaint.

        **Said once, then done as asked.** `ops/Caddyfile` proxies `/api*` to the public internet,
        so an untokened Studio is open to anyone who finds it, and Studio takes the card for a real
        render — a stranger finding it means every other surface queues behind them. Reinforce is
        worse, because it is never evicted. That is the only reason those gates exist. Three ways
        to have both are written out in R-162 for him to pick from; the middle one — nothing on
        read paths, a token only where the card or the disk is at stake — is what I would
        recommend, and it is his exposure and his call.

        Until he says otherwise the instruction is the instruction. The proof it came off rather
        than moved is `tests/studio.mjs`, which passes `SYMONEURAL_STUDIO_TOKEN=devtest` today and
        must pass with nothing set.

        check: ngrep SYMONEURAL_STUDIO_TOKEN=devtest -- tests/studio.mjs
        check: grep TokenNotRequiredTests -- backend/apps/studio/test_studio.py
◻ #89 — SyMoNeuRaL Studio should mirror what DeepSeek Harness provides
        owner: coder
        R-163, second sentence. "Studio needs major work it should mirror what deepseek harness
        provides."

        Studio today is a render bench with an agent loop behind it. The harness he is pointing at
        is a different proposition — its own developer preview is titled *"Everything is a
        plugin"*, which is the same claim `apps/studio/plugins/exp` was built to make and has
        never been asked to keep in public. So this is not a restyle: it is Studio becoming the
        surface where a plugin is mounted, configured, watched and torn down, with the render bench
        as one plugin among them rather than as the whole page.

        Start by reading `references/deepseek-harness` and the two saved `DeepSeek Harness*.mhtml`
        captures beside it and writing down, as a checklist of observable behaviour, what it gives
        a user that we do not. That list is the task; guessing at "major work" is not. Reference
        only — read for behaviour, nothing imported, linked or served, and what ships is ours.

        Depends on the Exp row leaving the rack (#73, which folds #22): Exp migrating INTO Studio
        is the same change as Studio gaining a plugin surface, and doing them in the other order
        means building the surface twice.

        check: exists docs/studio-harness-gap.md
        check: grep StudioPluginSurfaceTests -- backend/apps/studio/test_studio.py

◻ #90 — CLI, Code and Cowork measured against the client he actually uses
        owner: coder
        R-164, extending R-151. "symoneural cli, symoneural code and symoneural cowork must mirror
        look feel and capabilities of claude."

        A standing quality bar across three surfaces, one of which does not exist yet — cowork
        lands inside Chat under #83. So the deliverable here is not a feature: it is the checklist
        R-151 already wrote out (bare invocation opens a session, in-session slash commands, a
        permission prompt before any side-effecting tool and a mode that skips it, resume by
        session id with a picker, @-file references, multi-line paste, Ctrl-C interrupt, markdown
        rendered as it streams, a status line) applied to all three, tracked, and closed item by
        item rather than declared.

        The clean-room position from R-151 is what makes this legitimate and it does not bend:
        behaviour observed and rebuilt, never copied. Nothing under `references/` is imported,
        linked or shipped, and nothing ships under a third-party name.

        Write the checklist down where it can be checked, then work it. A claim of "mirrors Claude"
        with no per-item state is exactly the kind of assertion this list exists to replace with a
        measurement.

        check: exists docs/client-parity.md
        check: grep parity -- bin/symoneural-cli
◻ #91 — Every surface has to read as an instrument, starting with the control board
        owner: coder
        R-165, with a screenshot of /controlboard. "control board looks dumb and needs to be made
        more professional. All of the applications need to be more professional. We have to be
        better than comfyui, deepseek, playwright, llama.cpp, vllm and stablediffusion.cpp. Right
        now it seems like you have just programmed bare minimum; that will not be tolerated."

        The screenshot is the diagnosis: twenty tiles in two ragged rows, every one the same size
        and weight, each with a number, a unit, an explanation and a footnote — and half of them
        mostly empty, because a row's tile height is set by its longest sentence. Nothing grouped
        (VRAM beside CUDA cores beside a projected H200 figure), nothing ranked (die temperature as
        loud as chat decode), six tiles visibly blank where a value should be, and row two ending
        in five tiles of white space. The heading says "Everything this machine is, on one screen"
        and a visitor cannot tell at a glance what the machine is doing.

        He named the cause correctly and it should be written down rather than argued with: a
        uniform grid is the least work. That is what "bare minimum" means here.

        **The bar, stated so it can be judged:** same data, grouped by what it answers and ranked
        by what a visitor came for, with the long tail folded into `<details>`. Nothing on that
        page may be dropped to make it look better — the LIVE / MEASURED / PROJECTED legend, every
        footnote, and "we do not quote a number we have not either measured or shown the arithmetic
        for" are the argument the site is making. No new gauge that is not a real reading, and no
        `text-overflow`. A prettier board that loses a label is a downgrade.

        The comparison set is the specification and all six are in `references/`, so "better than"
        is measurable: read what each one's own surface does well, write it down in
        `docs/surface-bar.md`, and beat it. Behaviour observed, nothing copied — same discipline as
        #90. Control board first because he named it; then every application surface, which is
        where this meets #84, #85 and #81.

        check: exists docs/surface-bar.md
        check: grep ControlBoardGroupTests -- backend/apps/test_page_layout.py
        check: grep controlboard-grouped -- tests/frontend.mjs

◻ #92 — Every published figure carries the SHA it was read on
        owner: coder
        What is left of #76 after he dropped it: "remove task 76 and simplify what this was
        trying to accomplish". #76 folded eight old tasks and had grown into an audit of an
        audit. One thing in it was load-bearing, so it is the whole task now.

        **A number with no commit beside it cannot be checked, only believed.** A published
        1063 turned out never to have been true of the commit it sat next to, because somebody
        carried it forward and re-dated it. That is the defect. Every measured figure in
        `docs/`, `.claude/CLAUDE.md` and `.claude/HANDOVER.md` gets the SHA it was read on and
        a label — measured, vendor, or projected. Where the tree is no longer identifiable,
        re-measure or delete it; never re-date it.

        `tools/check_figures.py` is what makes this stay true rather than be true once: it
        reads those files, finds figures with no SHA within reach, and names them. A rule that
        is only written down is a rule that drifts.

        check: exists tools/check_figures.py
        check: grep UnstampedFigureTests -- backend/tests/test_check_figures.py
        check: grep ^| docs/FIGURES.md -- docs/FIGURES.md

◻ #93 — backend/apps: named after the surface it serves, and no test files in its root
        owner: coder
        Garrett, 2026-08-20, having listed the directory: "these are not named correctly and i
        did not ask for test_* in this folder there is a special place for python test".

        Two faults, both visible in that one `ls`.

        1. **The names do not match the rack.** `backend/apps/ROSTER.md` says the row is
           `miner`, the directory is `cryptominer`; the row is `train`, the code is under
           `api.py` and the docs say Reinforce. `asicminer` and `cryptominer` sit beside each
           other as if they were two products. `capture`, `licensing`, `voice` and `accounts`
           are not rows at all. The roster exists precisely so four lists cannot disagree, and
           the directory is one of the four. Rename so the directory name IS the roster id,
           and reconcile `apps/roster.py`, `api.py`'s `build_status()`, `controlboard`'s
           `TOGGLEABLE` and the roster test in the same commit.
        2. **22 `test_*.py` files are loose in `backend/apps/`.** The repo already has the
           right shape and uses it twice: `apps/remix/tests/` and
           `apps/studio/plugins/reinforce/tests/`. So per-app suites go to
           `backend/apps/<app>/tests/`, and the cross-app ones — `test_build_progress.py`,
           `test_symoneural_cli.py`, `test_roster.py`, `test_desktop_shell.py` and the rest —
           go to `backend/tests/`. `backend/apps/` holds applications.

        **The hazard here is silent and this repo has already been bitten by it.** The
        documented invocation is `cd backend && python3 -m pytest apps/ -q
        --ignore=apps/studio/plugins/reinforce/tests --ignore=apps/remix/tests`. Move the
        files and `apps/` stops being the right target, while pytest says nothing about an
        `--ignore` path that matches nothing — it just stops excluding, and you get a
        collection error where a count used to be. So the invocation in `.claude/CLAUDE.md`
        changes in the same commit as the move, and the count is re-measured and stamped, not
        carried across. Same trap as #92.

        Do not move a test and leave its `__main__` block behind: 34 of these files carry one
        that already cannot import `apps.*` when run as a script, and a move changes the path
        it would need.

        resolve: backend/apps/cryptominer -> backend/apps/miner
        resolve: backend/apps/test_roster.py -> backend/tests/test_roster.py
        resolve: backend/apps/test_build_progress.py -> backend/tests/test_build_progress.py
        check: maxcount 0 apps/reinforce/tests -- .claude/CLAUDE.md
        check: grep AppsRootIsApplicationsOnly -- backend/tests/test_roster.py
