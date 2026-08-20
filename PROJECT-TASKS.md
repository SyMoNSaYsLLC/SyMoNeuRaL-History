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
        2. **Finish the streamer merge** (#28). Guide and tuner were merged by hand and the
           collision was left in the tree: `routesmergemewithotherroutes.py` and
           `READMEmergemewithotherreadme.md` are literally named for the job, and tuner's
           `__init__.py` was overwritten by guide's — its `router`/`status` exports exist only
           in git history now. Merge all three, then delete the placeholders.
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
        check: grep tuner_router -- backend/apps/streamer/__init__.py
        check: grep 8188 -- backend/apps/studio/registry.py
        check: exists ops/symoneural-deploy.service
        note: `grep tuner_router`, not `grep tuner`: the word "tuner" already appears in
        note: guide's docstring, so the loose form passed while tuner's exports were still
        note: missing. A check that passes before the work is done is worse than no check —
        note: this one would have archived the task. Verified by running it before and after.
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
