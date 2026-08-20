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
        check: exists backend/apps/studio/plugins/__init__.py
        check: exists backend/apps/studio/plugins/exp/__init__.py
        check: exists backend/apps/studio/plugins/reinforce/__init__.py
        check: exists backend/apps/studio/plugins/discovery/__init__.py
        check: absent backend/apps/streamer/routesmergemewithotherroutes.py
        check: absent backend/apps/streamer/READMEmergemewithotherreadme.md
        check: grep "include_router" -- backend/apps/streamer/__init__.py
        check: exists site/streamer.html
        check: absent site/tuner.html
        check: grep "/api/streamer" -- backend/api.py
        check: ngrep "/api/tuner" -- backend/api.py
        check: ngrep ROW_OF_MODULE -- backend/apps/test_status_rack.py
        check: grep 8188 -- backend/apps/studio/registry.py
        check: exists ops/symoneural-deploy.service
        note: `grep tuner_router` used to stand here, and it has been REMOVED rather than kept.
        note: It was a good check for the file merge — the loose `grep tuner` passed on guide's
        note: docstring while tuner's exports were still missing — but it became an anti-check the
        note: moment the task grew the namespace half: finishing the merge properly *deletes*
        note: `tuner_router` in favour of one `router`, so the check would go false as the work
        note: got more done, and a re-run would read as a regression. `grep "include_router"` in
        note: `__init__.py` replaces it and is true only when the package composes the two halves
        note: itself instead of handing api.py two routers to wire.
        note: The `resolve:` lines that closed #51, #53 and #55 read the filesystem, which is
        note: why they could close themselves the moment the folders moved. The checks above
        note: are chosen the same way — each one is false today and can only be made true by
        note: doing the thing. Two parts of this task have no honest predicate and are
        note: deliberately unmeasured: "every application online" (a reading of a live
        note: process, not of the disk) and the voice/adapter work, which has no single
        note: artefact. Do not invent a check for them; the percentage is allowed to top out
        note: below the work.

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

◻ #76 — Close the audit, and anchor every published figure to a SHA
        owner: coder
        Folds #36 #41 #42 #47 #49 #50 #56 #67. Read those blocks in
        `review/CONSOLIDATED-TASKS-2026-08-20.md` before working any part.

        1. **The remaining audit items** (#47, #41). Items 7, 9, 10, 11, 12, 18, 19, then 15;
           and item 26, where `gpu-governor.sh:200` labels a historical record as a live one.
        2. **Reclassify every Garrett-only item** (#42) against the five categories — hardware,
           credentials, third-party dashboard with no API, money, legal or business. The
           standing rule is FIX, not FILE, and anything that fails all five categories comes
           back to me. Report what moved rather than just moving it.
        3. **A machine check per audit item** (#56), so the surface reports a reading instead
           of a claim — the same discipline as the task percentages.
        4. **Anchor every figure** (#67). Sweep `docs/` and `.claude/HANDOVER.md`; every
           measured number gets the commit it was read on plus a label: measured, vendor, or
           projected. Where the tree is no longer identifiable, re-measure or delete. **Never
           carry a number forward and re-date it** — a published 1063 turned out never to have
           been true of the commit beside it, and that is the exact defect this closes.
        5. **Re-measure all four suites at the final HEAD** (#49) and write the result up
           (#50, #36). The suite counts in `.claude/CLAUDE.md` are stale by construction after
           the plugin restructure: they were read at `d3a4040`, before `backend/apps` moved,
           and the `--ignore=apps/reinforce/tests` path no longer matches anything now that
           reinforce lives under `studio/plugins/`. Re-read them and stamp the new SHA; do not
           reprint 1229.

        check: exists AUDIT-DONE-2026-08-19.md
        check: grep ^check: -- AUDIT-SURFACE-2026-08-19.md
        check: exists docs/FIGURES.md

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

◻ #78 — SyMoNeuRaL Code: an interactive terminal client, and a desktop client for it
        owner: coder
        From A-R151 / GARRETT-REQUESTS.md R-151. Garrett, 2026-08-20, three messages that
        together are the whole specification: *"well just make everything as close as you can
        to the claude sources bc I want to be users to get a similar experience"*, then *"we
        should be able to make it just like claude using playwright"*, then — lifting the
        browser-only scope that the ledger entry had assumed was still in force — *"Restriction
        lifted. If an Electron or lightweight native build is what it takes to get the right
        feel for the desktop client, go for it. Just keep the footprint reasonable and ensure
        it integrates cleanly with the engine you've already built in bin/symoneural-cli. Let's
        get it done."*

        **The licence line, because it decides the method and is not a judgement call.** Both
        references are first-party Anthropic PBC and `License: Proprietary` — checked in the
        `.deb`'s own copyright file rather than assumed, at Garrett's instruction to check.
        MIT permits renaming with the notice carried, which is the route we took for the
        engines; a proprietary licence permits neither renaming, deriving, nor
        decompiling-and-renaming. So "as close as you can" is a specification for the
        **experience**, written fresh. An interaction model — a REPL, a slash-command
        vocabulary, a permission prompt before a side effect, a resumable session — is not what
        a copyright covers. Nothing from `references/` or `bin/claude` is read, extracted,
        decompiled or shipped, and `apps/test_references_boundary.py` is the standing check.

        This is the position Garrett took himself: *"reason i deleted them was because i was
        worried i had copyrighted stuff so i started all over"*.

        **Playwright is how "just like claude" becomes measurable** rather than a matter of
        taste — his own suggestion. It drives our client and asserts the observable behaviours
        below. Observing behaviour is the clean-room half; the code is ours either way.

        The engine half already exists and is not rebuilt: `bin/symoneural-cli` carries
        `agent` (SSE-rendered, `-c` to continue from `run/agent-<session>.json`), `tools`,
        `tool`, `state` and `mcp --serve`, with native tool calling on our own engine. The gap
        is everything a user touches.

        1. **A bare invocation opens a session.** Today every path needs a subcommand, and this
           is most of the difference in feel. The existing subcommands keep working unchanged —
           a REPL that breaks `symoneural-cli status` in a script is a regression, not a
           feature.
        2. **In-session slash commands**: help, clear, status, tools, model, resume. Named the
           same as the subcommands they mirror, so there is one vocabulary and not two.
        3. **A permission prompt before any tool with a side effect**, and a mode that skips
           it. The prompt is the honest part: a tool that mutates the box must say so before
           it does, and the skip mode must be chosen explicitly rather than defaulted into.
        4. **Resume by session id**, with a picker over the transcripts already written to
           `run/agent-<session>.json`. The store exists; nothing reads it back.
        5. **@-file references, multi-line paste, Ctrl-C interrupt.** Ctrl-C must abort the
           turn in flight and keep the session, not kill the process.
        6. **Markdown rendered in the terminal, streaming as it arrives.** Note what the engine
           can actually do: `inference.Backend.chat` sends `"stream": False`, so the loop's
           granularity is SSE *events*, not tokens. Do not print a first-token latency for it
           and do not fake a token stream — publish the event timings that are real.
        7. **A status line.**

        Then the desktop client, on the scope he has just opened. Keep the footprint
        reasonable, which is the whole reason to look at anything other than Electron: the
        reference `.deb` is Electron and carries a ~300 MB runtime for a UI that is HTML, CSS
        and JS. Measure two or three candidates on this box and write the reading down before
        choosing — a footprint claim with no number beside it is the thing this repo bars. It
        talks to the same engine as the terminal client and does not grow a second one.

        note: 2026-08-20 — promoted on Garrett's instruction rather than on a tick: *"You
        note: should be able to resolve A-R151 with that last prompt i sent"*. Recording that
        note: here because the standing rule is that the box is the gate; a direct instruction
        note: from him IS the decision the box represents, and the rule exists to stop me
        note: starting work on my own judgement, not to make me decline an order.

        Every check below names a symbol or a sentence that cannot exist unless the behaviour
        does. The seven this block opened with -- `exists bin/symoneural-code`, `grep slash`,
        `grep permission`, `exists desktop/README.md` -- were satisfiable by a docstring and an
        empty file, which under the archiving rule means this task would have filed itself as
        finished off four placeholders. That is the failure CLAUDE.md names outright: *"a check
        that can pass without the work being finished is worse than no check, since it will
        archive the task."* Tightened before any of the files were written, so the percentage
        was never inflated. One survived a round anyway: `grep permission_required --
        bin/symoneural-cli` went green the moment `/permissions` *mentioned* the frame in the
        sentence explaining that it does not exist yet. It now reads `grep def approve`, which
        is the function that answers the gate and cannot be a sentence about one.

        check: grep def cmd_repl -- bin/symoneural-cli
        check: grep stdin.isatty -- bin/symoneural-cli
        check: grep /resume -- bin/symoneural-cli
        check: grep dangerously-allow-all -- bin/symoneural-cli
        check: grep def approve -- bin/symoneural-cli
        check: grep permission_required -- backend/apps/studio/agent.py
        check: grep symoneural-cli -- bin/symoneural-code
        check: grep a bare invocation with no stdin tty -- tests/code_cli.mjs
        check: grep events, not tokens -- docs/specs/code-client-spec.md
        check: grep permission_required -- docs/specs/code-client-spec.md
        check: grep measured on this machine -- desktop/README.md
        check: grep \d+(\.\d+)? MiB -- desktop/README.md
        check: grep def render_markdown -- bin/symoneural-cli
        check: grep def status_line -- bin/symoneural-cli
        check: grep record\("the gate: -- tests/code_cli.mjs
        note: 2026-08-20 coder — the check that stood here was `grep permission_required --
        note: tests/code_cli.mjs`, which is the exact trap the note above records one file over:
        note: `permission_required` is the natural word for prose ABOUT the gate, so a comment
        note: saying there is no gate test yet turns it green. Measured, not assumed — a
        note: comment-only line naming it made the check PASS on a file with no gate assertion
        note: in it. It now names a test registration, `record("the gate: `, which is not a
        note: sentence anybody writes. Honest limit: a comment containing that exact string
        note: still satisfies it. grep on a source file cannot prove a test ran; the most it
        note: can do is stop being satisfied by the explanation of its own absence.
        note: 2026-08-20 coder — writing the gate tests found two live bugs, both one wrong
        note: assumption about `api_json`, which answers `(status, body)`. `/permissions`
        note: treated the call as a dict and traced back EVERY time, taking the session with
        note: it. Worse, the post-approval execution path bound the tuple to `result`, so the
        note: model was handed `[200, {...}]` where the tool's output belongs, and a 403
        note: `denied` from the router reached it shaped exactly like success. Nothing caught
        note: it because the fake in test_symoneural_cli.py returned a bare dict and so agreed
        note: with the mistake — a stub that does not match the signature it stands in for
        note: tests the stub. Also fixed a red this file's own suite was carrying: an assertion
        note: that `/permissions` must say nothing is gated yet, true when written and stale
        note: the moment item 3 landed. A test asserting the absence of a feature has to be
        note: deleted by the commit that adds it.
        check: exists desktop/shell.py
        check: grep Vte.Terminal -- desktop/shell.py
        check: grep spawn_async -- desktop/shell.py
        check: exists desktop/symoneural-code.desktop
        note: 2026-08-20 coder — UNARCHIVED, and the reason is the whole point of this note.
        note: The two documents above went in, every one of the twelve declared checks passed,
        note: and symoneural-progress.timer -- a USER-level systemd timer, two-minute cadence,
        note: which is why `systemctl list-timers` without --user shows nothing -- ran
        note: archive_tasks.py at 18:09:13 and filed this task as finished. It is not. There is
        note: no desktop client, no markdown rendering (item 6), no status line (item 7), and
        note: not one gate assertion in tests/code_cli.mjs. Twelve checks, all genuinely true,
        note: none of them measuring four of the items. That is exactly what CLAUDE.md means by
        note: *"a check that can pass without the work being finished is worse than no check,
        note: since it will archive the task"* -- and it did, thirty seconds after the last one
        note: went green, with nobody watching. The six checks above name symbols and files
        note: that cannot exist unless the work does, so the reading is 12/18. Restored
        note: verbatim, the ARCHIVED stamp dropped because it was not true.
        note: Two things to carry: the archiver is on a timer, so a check going green while
        note: you are still working is not a note-to-self for later -- the task is gone within
        note: two minutes. And a block coming BACK from review/CLOSED-TASKS.md is a legitimate
        note: move, not a rules violation: nothing is deleted, and the open list is supposed to
        note: be a reading of what is left.
        note: 2026-08-20 coder — tightened the last two checks before writing the documents
        note: they gate. `grep MiB` was satisfiable by the word MiB in a sentence, and just as
        note: satisfiable by a projected figure as by a measured one, which is the failure the
        note: honesty rule names outright. It is now a real number AND the label, and the spec
        note: check now also wants a frame name from the implementation, so a paragraph *about*
        note: the protocol cannot pass for the protocol. No grep can tell a measurement from an
        note: invention; these only make the cheap fabrications fail, and the label is what puts
        note: the claim on the record for whoever writes it.
        note: 2026-08-20 coder — items 6 and 7 landed, and item 7 found a third live bug of
        note: the same family as the two above. `render_markdown` renders the loop's answer for
        note: a terminal and returns it BYTE-IDENTICAL to a pipe, which is the half of the
        note: contract that protects the record: the same string is what --output-format json
        note: carries and what run/agent-<session>.json stores, so a renderer that edits it for
        note: a terminal has edited the transcript. Nothing truncates, nothing elides, no line
        note: is re-wrapped, and a link keeps its target as well as its label — the terminal
        note: side of the no-text-overflow rule. `status_line` was extracted from the inline
        note: print in cmd_repl and now carries the permission mode, which the old line omitted:
        note: it is the one setting that decides whether a tool runs without anybody being
        note: asked, and an operator who typed /permissions allow forty turns ago had nothing on
        note: screen to say so. Extracting it meant asking where the mode comes from, and the
        note: answer was THREE longhand copies of one resolution — cmd_agent (the copy the
        note: server is actually told), the /permissions report, and the new line. A structural
        note: test now pins it at one resolver and three callers, because the drift in a
        note: duplicated rule like this is silent and runs in exactly the wrong direction: a
        note: client reporting a safer mode than the one it is asking for.
        note: Four mutations confirmed to bite, each restored and diffed: render on a pipe,
        note: a link dropping its url, the status line dropping the mode, and code spans
        note: rendered after emphasis instead of lifted out first (which would render the markup
        note: inside `**not bold**`, the one place it has to survive verbatim).
        note: 2026-08-20 coder — `grep WebKit2 -- desktop/shell.py` is REPLACED by `grep
        note: Vte.Terminal` and `grep spawn_async`, and the check moved because the design did.
        note: desktop/README.md chose GTK3 + WebKit2GTK on a footprint measurement, and that
        note: measurement stands. What changed it is a stronger argument found while writing the
        note: gate tests: a web client is a SECOND implementation of the permission gate. The
        note: two bugs recorded above lived at exactly that seam, and approve() reads /dev/tty
        note: on purpose, because in `agent "..."` stdin is a pipe carrying the query and in the
        note: repl it is the transcript — neither is a human. A JS client has no pty and would
        note: need its own fresh answer to "who is the human here", which is one more place to
        note: fail open. VTE hands the real client a real pty, so approve(), APPROVE_KEYS, the
        note: re-ask and the closed-terminal refusal are the code already covered by seven tests
        note: rather than a parallel copy. One gate, one engine. Leaving the WebKit2 check in
        note: place and adding a token import to satisfy it would have been the check driving
        note: the design, which is the failure this whole check block exists to prevent.
        note: Measured before deciding, not after: WebKit2GTK 4.1 does render this site's real
        note: surface — site/livestack came back with 13 units built client-side from
        note: /api/status, the dark theme applied, zero JS errors and `OPEN
        note: ws://127.0.0.1:8877/api/ws`, an actual upgrade confirmed on both ends of the wire.
        note: So the runtime was not ruled out on capability. site/studio.html scores 0 on every
        note: agent-protocol marker (api/studio/agent, permission_required, EventSource,
        note: tool_call) across its 311 lines, so pointing a window at an existing surface was
        note: never going to produce an agent client either way.

