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

        check: ngrep llama\.cpp -- backend/api.py
        check: ngrep stable-diffusion\.cpp -- backend/api.py
        check: grep symoneural-llm -- backend/api.py
        check: grep symoneural-diffuse -- backend/api.py
        check: exists backend/models/NAMES.md
        check: grep upstream -- backend/models/NAMES.md
        check: exists backend/DEPENDENCIES.md
        check: grep replacing it would cost -- backend/DEPENDENCIES.md
        check: ngrep swagger -- backend/api.py
        check: ngrep SymPy -- site/ravencalc.html
        check: ngrep SymPy -- site/chat.html
        check: ngrep SymPy -- site/exp.html
        check: ngrep SymPy -- site/gateway.html
        check: ngrep SymPy -- site/image.html
        check: ngrep SymPy -- site/index.html
        check: ngrep SymPy -- site/livestack.html
        check: ngrep SymPy -- site/miner.html
        check: ngrep SymPy -- site/project.html
        check: ngrep SymPy -- site/reinforce.html
        check: ngrep SymPy -- site/remix.html
        check: ngrep SymPy -- site/sigils.html
        check: ngrep SymPy -- site/streamer.html
        check: ngrep SymPy -- site/studio.html
        check: ngrep sympy -- site/ravencalc.html
        check: grep SymPy -- site/credits.html
        check: grep BSD-3-Clause -- site/credits.html
        check: ngrep spec="SymPy -- backend/api.py
        check: grep symbolic core -- backend/apps/ravencalc/ravencalc.py
        check: exists backend/apps/test_brand_boundary.py

        note: 2026-08-21 — **item 7's single check could not see the worst occurrence and
        note: would have archived this task with the vendor name still printing on screen.**
        note: `ngrep SymPy -- site/ravencalc.html` covered one page of fifteen, so fixing that
        note: one file flipped it green while thirteen other pages still said SymPy. It is now
        note: one line per page. A directory target does not work as a wildcard —
        note: `build_progress.py` returns False for anything that is not a file, so
        note: `ngrep SymPy -- site/` would be permanently red rather than broad.
        note: Worse, and the reason the last two checks above exist: `ravencalc.py` returned
        note: `"engine": f"sympy {version}"` and `build_pages.py` renders that field into the
        note: readout, so the page printed `eng sympy 1.13.3` after **every** calculation. No
        note: grep of `site/` can see a runtime string. Same for `note`, which carried "sympy
        note: cannot integrate that" and "sympy returned this unevaluated". The engine line now
        note: reads `RavenCalc (symbolic core 1.13.3)` — the vendor name goes, the real version
        note: stays, and it is not presented as RavenCalc's own version number, which would name
        note: a release that does not exist.
        note: `backend/apps/test_brand_boundary.py` is what actually holds this: it scans every
        note: shipped page, every `tools/build_*.py`, and computes real expressions to read the
        note: fields a browser displays. It asserts `credits.html` **keeps** the notice, because
        note: BSD-3-Clause requires it in accompanying documentation and a slightly-too-broad
        note: sweep would satisfy every other assertion here while stripping it.
        note: The generator list is globbed, not hand-written, because that was the second trap:
        note: the shared "RavenCalc is the exception" sentence is emitted by **eight** generators,
        note: not the two that a grep of `site/` pointed at, and six pages kept the vendor name
        note: through a full rebuild because nobody ran the generator that owns them.

        note: 2026-08-20 — **the quotes came off five patterns above, and three of them were
        note: passing on work that was not done.** `run_check` hands the pattern straight to
        note: `re.search`, so `"SymPy"` searched for the seven characters `"SymPy"` WITH the
        note: double quotes. Measured before changing anything: that check was green while
        note: `site/ravencalc.html` said `RavenCalc is SymPy underneath` and contained the
        note: word **ten** times. `ngrep "swagger"` and `ngrep "stable-diffusion\.cpp"` were
        note: green the same way. Three of the ten checks on this task were reporting done.
        note: This is the exact failure the note above already records for these same two
        note: engine ngreps — it happened twice, in opposite directions, which is why the
        note: quoting is now called out rather than just fixed. The earlier agent added the
        note: quotes for a real reason: `api.py` built its paths as `ROOT / "contrib" /
        note: "llama.cpp"`, so the bare pattern only matched the string literal anyway and
        note: quoting made the check sharper. Item 1 then rebranded those paths away, and the
        note: same quotes that had sharpened the check turned it vacuous.
        note: `grep "would cost"` was not yet vacuous only because the file does not exist —
        note: it is a trap set for whoever writes it, who would have had to type the phrase in
        note: quotes to score. It now reads `replacing it would cost`, which is the sentence
        note: item 5 actually asks each row to contain.
        note: Not a blanket rule, and #87's `ngrep href="/documentation.html"` is the proof:
        note: there the quotes ARE the thing being matched, and stripping them would break a
        note: correct check. Checked all seven quoted patterns in this file, changed these
        note: five, left #87 and #83 alone.

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

        note: 2026-08-21 — **the check below was pointed at `backend/tests/`, which does not
        note: exist.** That path is where #93 will move the cross-app suites; until it runs,
        note: pytest collects from `backend/apps/`, so the check was red for a file nobody
        note: could have made green without doing #93 first — and had it been made green by
        note: creating the file at that path, the class would have sat somewhere the
        note: documented invocation never collects. Re-pointed to where tests actually run.
        note: #93 owns the move and carries `resolve:` lines for it; this check travels then.
        note: **The two `ngrep`s beside it were green on a leak.** They are one token per
        note: file — `dsw-` in the CSS, `deepseek` in the JS — and each file was checked for
        note: the token it happened not to contain: `site/symoneural.css` named the upstream
        note: twice, in served comments, and no declared check could see it. Same shape as
        note: `ngrep SymPy -- site/ravencalc.html` covering one page of fifteen. They are
        note: left in place because they are cheap and true, but the thing that actually
        note: holds this is the test class, which scans every served asset for both tokens
        note: and the generators as well. It found those two lines on the first run.
        note: They were quotations of Garrett's own words, so the fix is a bracketed
        note: substitution rather than a deletion — an unmarked edit to a quote misreports it.

        check: ngrep dsw- -- site/symoneural.css
        check: ngrep deepseek -- site/ui.js
        check: ngrep import sympy -- backend/apps/ravencalc/ravencalc.py
        check: exists backend/apps/ravencalc/symbolic.py
        check: ngrep import httpx -- backend/apps/studio/inference.py
        check: ngrep import httpx -- backend/apps/studio/comfy.py
        check: ngrep import httpx -- backend/apps/studio/routes.py
        check: ngrep import httpx -- backend/apps/remix/symoneural_dj/symon_client.py
        check: ngrep import httpx -- backend/apps/remix/symoneural_dj/pipeline.py
        check: ngrep import httpx -- backend/apps/remix/symoneural_dj/connectors/ytmusic.py
        check: ngrep import httpx -- backend/apps/remix/symoneural_dj/connectors/spotify.py
        check: ngrep from fastmcp -- backend/apps/studio/mcp_server.py
        resolve: scripts/comfyui.sh -> scripts/symoneural-ui.sh
        check: ngrep ComfyUI -- scripts/gpu-governor.sh
        check: ngrep /studio/comfy -- backend/api.py
        check: grep ComfyUI -- LICENSES.md
        note: 2026-08-21 coder — REOPENED. This task archived at 32/32 on 2026-08-21 with items
        note: 2 and 5 untouched, and the archive line "every declared check passes" was true.
        note: That is the failure this file warns about in its own words -- "a check that can
        note: pass without the work being finished is worse than no check, since it will
        note: archive the task" -- and it is now the FOURTH instance recorded on this task.
        note: The first three are in the notes above: ngrep SymPy covered one page of fifteen,
        note: and ngrep dsw- / ngrep deepseek each checked the file that happened not to hold
        note: its token. The new one is different in kind and worth naming separately:
        note: `check: grep NoUpstreamIdentifiersTests -- backend/apps/test_brand_boundary.py`,
        note: added by me at 6542932, goes green the moment the class name is TYPED. It was
        note: green while that very class was red and finding two real CSS leaks. A grep for a
        note: test measures that a test was written, never that it passes; build_progress.py's
        note: vocabulary (exists/absent/grep/ngrep/maxcount/resolve) cannot run a test, so a
        note: test-backed invariant is NOT expressible as a check. That line is deleted rather
        note: than kept, and no check on this task points at a test file any more. The two
        note: ngreps it sat beside measure the artifact and stay.
        note:
        note: 2026-08-21 coder — what is actually left, measured not asserted. Items 1, 3, 4, 6
        note: and 7 are done and their checks are green. Items 2 and 5 are not started, and the
        note: 14 lines added above were each verified RED before being declared.
        note:
        note: Item 2, narrowed by evidence. The GPL-3.0 source-offer half never attached and no
        note: work is owed on it: ComfyUI/ is absent from disk, gitignored entire (.gitignore
        note: :127-142), excluded from the deb (build-deb.sh:16) and never deployed. The offer
        note: attaches on DISTRIBUTION, and we do not distribute it, so LICENSES.md:24 "nothing
        note: in this stack is copyleft ... in anything shipped" is accurate as written. But it
        note: never NAMES ComfyUI, so a reader cannot tell the question was considered rather
        note: than missed -- a vanished notice and a stripped one read identically. Hence
        note: `grep ComfyUI -- LICENSES.md`: state the non-distribution, the way Swagger UI got
        note: "RETIRED 2026-08-21, no longer distributed" instead of silence. What remains of
        note: item 2 is the rebrand: scripts/comfyui.sh (name is in the filename, so `resolve:`
        note: is the instrument), the pkill fallback at gpu-governor.sh:119, and /studio/comfy/*
        note: at api.py:2720 -- that last one is a URL a VISITOR sees, which is exactly what
        note: this task's standard forbids. Note backend/apps/studio/test_comfy_port.py:44 pins
        note: scripts/comfyui.sh by path and moves with it.
        note:
        note: Separately, and not part of this task: with ComfyUI/ absent, the Studio surface
        note: and tests/studio.mjs cannot run at all right now. The 16/16 in .claude/CLAUDE.md
        note: is not re-runnable on this tree. Recorded here because it is load-bearing for
        note: anyone who believes that figure.
        note:
        note: Item 5 is ~25 packages, not sympy. An ast scan of every non-vendored module under
        note: backend/apps (excluding .venv, site-packages, node_modules, stdlib and local
        note: names) finds application code naming third-party packages directly at these
        note: counts: fastapi 48, pytest 12, cuda 11, cryptography 10, pydantic 9, httpx 8,
        note: numpy 7, cupy 6, playwright 4, pyasic 4, gi 4, bs4 3, sympy 3, then torch, peft,
        note: trl, dotenv, PIL and websockets at 2 each and anyio, datasets, transformers,
        note: fastmcp, gguf, psutil, rembg and yaml at 1. A sympy-only facade would not satisfy
        note: item 5, and a sympy-only CHECK would be the one-token-one-file failure above for
        note: the fifth time. The checks declared are scoped by the verdicts already argued in
        note: backend/DEPENDENCIES.md rather than by the raw scan: sympy, httpx and fastmcp are
        note: the three rows that file marks Facade, and every site of each is enumerated on
        note: its own line. fastapi and pydantic are marked Keep there and are deliberately not
        note: checked -- the framework is the application's own vocabulary, not a vendor name
        note: leaking through it.
        note:
        note: One contradiction left standing rather than silently resolved: item 5's text above
        note: puts sympy in the Recreate bucket, while backend/DEPENDENCIES.md:56 argues it as
        note: "Facade now, recreate incrementally". The checks follow DEPENDENCIES.md because
        note: that is where the argument was actually made. If Garrett wants Recreate, the
        note: `exists backend/apps/ravencalc/symbolic.py` check still holds and only what is
        note: behind that module changes.

        note: 2026-08-21 coder — FIFTH instance of one-token-one-file on this task, found
        note: while scoping #94. `sd-cli` — the upstream name item 1 renamed to
        note: `symoneural-diffuse` — survives at backend/api.py:114, :375, :844 and :2389.
        note: :375 is the one that matters: it is the `ImageRequest.size` Field description,
        note: so it renders into the public API reference and a visitor reads it. The other
        note: three are internal comments in the serving source and nobody has asked for
        note: those to change. That asymmetry is exactly why this is NOT being added as a
        note: check: `ngrep sd-cli -- backend/api.py` would fail on the three comments and
        note: read red forever on work nobody wants done — the mirror image of the vacuous
        note: check deleted above. A grep cannot tell a rendered Field description from a
        note: comment; a test that reads the OpenAPI payload can. So this belongs in
        note: NoUpstreamIdentifiersTests in backend/apps/test_brand_boundary.py, asserting
        note: over app.openapi() rather than over the file text. Recorded here so it is not
        note: lost, and deliberately left uncarried by a check until that test exists.
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

◻ #94 — SyMoNeuRaL Desktop Client: a native window over the local API
        owner: coder
        Garrett, 2026-08-21: "Create a clean, lightweight Electron or Tauri shell that
        connects to our local API backends (supporting chat, image generation, and
        RavenCalc)... Ensure everything is written under our own clean licensing terms with
        zero proprietary baggage."

        **This is NOT desktop/shell.py and must not touch it.** That program already exists,
        passes 15/15 in backend/apps/test_desktop_shell.py, and is a GTK3+VTE terminal window
        around bin/symoneural-cli. Its governing test asserts the shell never speaks to the
        API itself — `for forbidden in ("urllib", "requests", "httpx", "api_json", "/api/",
        "WebSocket")` — because a web client would be a second implementation of the
        permission gate, and approve() opens /dev/tty rather than reading stdin. A client that
        calls /api/chat can therefore never make that file pass; they are two programs with
        opposite architectures. Asked which he wanted, Garrett chose to keep both: shell.py
        and its 15 tests untouched, this one a distinct program with its own test file.

        **Tauri v2, not Electron, and no npm at all.** Tauri on Linux renders through the
        system WebKitGTK rather than bundling a Chromium, which is the only reading of
        "lightweight" that survives measurement. Verified present on this box before choosing:
        webkit2gtk-4.1 2.52.5, javascriptcoregtk-4.1 2.52.5, libsoup-3.0 3.6.5, gtk+-3.0
        3.24.49, glib-2.0 2.84.4, cargo/rustc 1.97.1, and crates.io resolving (a probe crate
        added serde 1.0.229 and linked a binary — the earlier 403 was a bucket root and proved
        nothing about the index). The scaffold is hand-written and built with plain `cargo
        build`; tauri-build reads tauri.conf.json from build.rs, so the Tauri CLI is not
        required and there is no package.json, no bundler and no node_modules. Frontend is
        static HTML/CSS/JS under desktop-client/ui/, which is also what makes the checks below
        greppable.

        The four endpoints it drives, read from backend/api.py rather than assumed:
        /api/chat is SSE, not JSON — each event {"delta": "..."} and a final {"done": true,
        "tokens", "seconds", "tok_per_s", "model", "adapter"}. /api/image returns ImageResult
        whose url is /api/gen/<name>, which is a second fetch. /api/ravencalc returns a
        ravencalc/result/v1 document whose check.passed is THREE-valued.

        The honesty rules are load-bearing here and are what most of the checks measure:
        check.passed == null renders "unconfirmed", never a tick — null is reported, not
        rounded up. tok_per_s is displayed as the server measured it and never recomputed
        client-side. No text-overflow anywhere in the CSS; long content wraps or folds, per
        the standing rule that an ellipsis is data loss with extra steps. Any connection
        indicator reflects a real /api/status read — no decorative LEDs. And the client binds
        127.0.0.1 only, which is why `ngrep 0\.0\.0\.0` is a check.

        check: exists desktop-client/src-tauri/tauri.conf.json
        check: exists desktop-client/src-tauri/Cargo.toml
        check: exists desktop-client/src-tauri/src/main.rs
        check: exists desktop-client/ui/index.html
        check: exists desktop-client/ui/app.js
        check: exists desktop-client/ui/app.css
        check: exists desktop-client/README.md
        check: exists desktop-client/LICENSE
        check: exists backend/apps/test_desktop_client.py
        check: grep /api/chat -- desktop-client/ui/app.js
        check: grep /api/image -- desktop-client/ui/app.js
        check: grep /api/gen/ -- desktop-client/ui/app.js
        check: grep /api/ravencalc -- desktop-client/ui/app.js
        check: grep /api/status -- desktop-client/ui/app.js
        check: grep unconfirmed -- desktop-client/ui/app.js
        check: grep tok_per_s -- desktop-client/ui/app.js
        check: ngrep text-overflow -- desktop-client/ui/app.css
        check: ngrep 0\.0\.0\.0 -- desktop-client/ui/app.js

        note: 2026-08-21 coder — all 18 checks verified red before being declared, using
        note: tools/build_progress.run_check itself rather than by eye. Worth knowing why the
        note: two ngrep checks are honest rather than vacuous: run_check fails BOTH grep and
        note: ngrep on a file that does not exist (build_progress.py:138-142), deliberately,
        note: so a rename cannot reach 100% by deleting the file it was meant to edit. So
        note: `ngrep text-overflow` is red now and goes green only once app.css exists AND
        note: lacks the token. A check that would have been green from the start —
        note: `absent desktop-client/package.json` — was considered and dropped for that
        note: reason: it encodes a real constraint but measures no progress, so it belongs in
        note: the test file, not here.
        note: 2026-08-21 coder — what these checks deliberately do NOT measure: that the
        note: thing compiles, launches, or renders. build_progress's vocabulary cannot run a
        note: build, so `cargo build` passing is not expressible and 18/18 will read 100%
        note: on a client that has never been opened. Do not treat the percentage as the
        note: definition of done for this one; the reading to trust is a real window, and
        note: `cd backend && python3 -m pytest apps/test_desktop_client.py -q`.
