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
        check: exists scripts/SMOKE-credentials.md
        note: 2026-08-22 coder -- the SMOKE check above was added BEFORE any work started, and
        note: it is the check that stops this task archiving itself. The other four all go green
        note: on a `mv` plus two new files, and item 1 says the order that matters out loud:
        note: "Rotate, then untrack -- untracking a key that is still valid moves it out of
        note: sight without making it harmless." So four-of-four is reachable with every
        note: credential still live, which is #94's failure exactly. SMOKE-credentials.md cannot
        note: be written honestly without a rotation having happened, and it must name what was
        note: NOT rotated: SPOTIFY_CLIENT_ID/SECRET are third-party-dashboard credentials, one
        note: of the five owner:garrett categories, so this task cannot legitimately reach 100%
        note: on coder work alone and needs a [ ] handoff for the Spotify half.
        note: 2026-08-22 garrett -- PAUSED at 0/4. "Pause before committing #75 if it changes
        note: Remix/DJ naming or credentials." Containment may DOCUMENT the current secret
        note: names; it may not rename app modules, tokens or routes. The DJ -> Remix rename is
        note: recorded as AUDIT.md Q12 and is not a task until he scopes it. Nothing was read,
        note: moved or renamed: both .env files are still on disk at mode 600 and untracked.
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
        check: exists .claude/hooks/SMOKE-capture.md
        note: 2026-08-26 coder — the SMOKE check above is declared BEFORE any of the other five
        note: was worked, and it is the check that stops this task archiving itself. The other
        note: five are `exists`, `grep` and `maxcount`: every one of them goes green on a file
        note: written to disk, and none of them can ask whether the hook ever FIRED. That is
        note: #94 exactly — eighteen green checks on a client whose chat surface was dead, and
        note: the timer archived it two minutes later. The timer is live here too:
        note: `systemctl --user list-timers` shows symoneural-progress.timer on a 2-minute
        note: period, measured 2026-08-26 08:02. SMOKE-capture.md cannot be written honestly
        note: without a prompt having been captured end to end, and it must record the
        note: fail-open proof as well: item 1 says a broken hook must never block a prompt, so
        note: the smoke record names the deliberate break and what happened to the prompt.
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

        check: grep local_bypass -- backend/apps/studio/gate.py
        check: grep switched_on -- backend/apps/studio/gate.py
        check: grep local_bypass -- backend/apps/studio/routes.py
        check: grep token_ok -- backend/apps/studio/routes.py
        check: grep StudioLocalBypassTests -- backend/apps/studio/test_studio.py
        check: grep PER-SURFACE DECISION -- docs/ops/SECURITY-AUDIT.md
        note: 2026-08-22 coder — CHOSEN PATH IMPLEMENTED, and the two original checks were
        note: REPLACED rather than satisfied. They were `ngrep SYMONEURAL_STUDIO_TOKEN=devtest --
        note: tests/studio.mjs` and `grep TokenNotRequiredTests -- .../test_studio.py`, and both
        note: encoded one definition of done: the token requirement removed outright. Garrett
        note: chose a different resolution on 2026-08-22 -- keep the public gate, add a
        note: local-only bypass -- so those checks would now go green for work nobody wants
        note: done. Recorded here rather than deleted quietly, because a rewritten check is a
        note: changed definition of done and that is the kind of edit that should be visible.
        note: tests/studio.mjs is deliberately UNTOUCHED for the same reason.
        note: What was built: gate.local_bypass(peer, headers), true only when all three hold --
        note: SYMONEURAL_STUDIO_LOCAL_BYPASS == "1" (absent means off, the default),
        note: gate.switched_on(), and gate.local_request(peer, headers) which requires a
        note: loopback peer AND no proxy header. Applied at three call sites in routes.py --
        note: _guard, the /api/studio/events websocket, and the /studio/editor/ws websocket --
        note: consulted FIRST and only ever returning early, so every line below it is
        note: unchanged and the public path meets the same enabled() + token_ok() pair.
        note: THE INVARIANT: it bypasses the SECRET, never the SWITCH. switched_on() was
        note: factored out of enabled() to make that legible -- enabled() is the switch AND a
        note: token, so calling it in the bypass would have left the friction exactly where it
        note: was. A switched-off Studio denies every caller, local or not, flag or not.
        note: Proven by sabotage rather than by assertion: removing the switched_on() guard
        note: failed test_disabled_studio_refuses_even_with_the_bypass_flag and only that one;
        note: removing the proxy-header rejection failed the two local_request tests. 402
        note: passed across apps/studio/.
        note: WHY THIS TASK IS STILL OPEN at 5/6. Its body says the instruction is standing and
        note: "not Studio-only: everything, while testing" -- eight surfaces share the double
        note: gate. Studio's half is done; Reinforce, Exp, Project, Coder, Miner, ASIC and
        note: Discovery still carry it, and BLOCKER-2 is explicit that the risk type differs per
        note: surface and they must be decided one at a time rather than in one sweep. The sixth
        note: check greens when that per-surface decision is written into SECURITY-AUDIT.md
        note: under a PER-SURFACE DECISION heading. Until then this task is not finished, and
        note: it must not archive itself on the Studio half alone.
        note: NOT closed by this work: HIGH-1. /studio/editor/* still proxies ComfyUI's own
        note: editor to authenticated operators over a public hostname, and #103 records the
        note: ordering that fixes it -- "#88 comes AFTER the raw editor is gone". That still
        note: stands; this implementation makes the wait affordable, it does not replace it.
        note: Caddy unchanged: /studio and /studio/* are still delegated.
        note: 2026-08-22 coder — SECURITY AUDIT, BLOCKER-1 and BLOCKER-2. Read
        note: docs/ops/SECURITY-AUDIT.md before writing any code for this task. Three facts
        note: that are each fine alone and are not fine together: ops/Caddyfile:150 delegates
        note: `/studio` AND `/studio/*` to the API, so the whole subtree is internet-facing --
        note: not just /api; `/studio/editor/*` is a same-origin reverse proxy in front of
        note: ComfyUI's own editor, whose catch-all at apps/studio/routes.py:878 forwards GET,
        note: POST, PUT, PATCH, DELETE, HEAD and OPTIONS to 127.0.0.1:8188 plus a WebSocket at
        note: :823, on a bare APIRouter() with no dependencies=; and the only thing in front of
        note: it is `_guard` at :90-101, which is exactly the 401 this task removes. Drop the
        note: token naively and ComfyUI's full editor API is unauthenticated on the public
        note: internet. `_intercept_prompt` protects the GPU LEASE, not access.
        note: The same double gate protects eight surfaces, not one: Studio (incl. the editor),
        note: Reinforce /api/train (7 routes), Exp /api/exp (13), Project /api/project (19,
        note: with POST/PATCH/DELETE), Coder, Miner, ASIC and Discovery. Removing the ASIC and
        note: Miner tokens exposes rig control, the emulator and the network scanner -- the
        note: scanner refuses non-private ranges (asicminer/__init__.py:129) so it cannot be
        note: aimed at the internet, but a stranger could still enumerate and control hardware
        note: on his LAN. Project's path containment is independent of its token, so the
        note: training artefacts stay protected either way; what goes public is arbitrary
        note: project mutation. The RISK TYPE DIFFERS PER SURFACE and must not be flattened into
        note: "tokens off = everything leaked" -- Studio's editor is the worst case, ASIC is a
        note: LAN not the internet, Reinforce is inert today because torch is not installed, Exp
        note: gates mutations only, Coder's root and denylist are independent of its token, and
        note: Discovery exposes nothing because it has no router. The per-surface table is in
        note: docs/ops/SECURITY-AUDIT.md under BLOCKER-2; decide per surface, not in one sweep.
        note: His complaint is legitimate and this note is not a refusal -- exporting a secret
        note: to use your own site is the whole grievance. Four ways to satisfy it, and the
        note: choice is his: (a) loopback-only instead of token-only, reusing _require_local,
        note: which refuses proxy headers and cannot be widened; (b) exclude /studio/editor/*
        note: from the drop, so product surfaces open and the raw vendor editor does not;
        note: (c) remove Caddy's /studio/* delegation while testing; (d) accept the exposure
        note: in writing, with a date. Do not pick one silently.

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

◻ #95 — What `train` reports on the rack when SyMoNeuRaL Reinforce is switched off
        owner: garrett
        [ ]
        Carries AUDIT.md Q10. Garrett's answer there — "try all - check proxy, logs, and
        restart" — has been carried out in full and it closed the investigation without
        answering the question, which is why this is a task and not a fix.

        What the three checks established, so nobody repeats them: the proxy is clear
        (`ops/Caddyfile` forwards `/api` verbatim, `/reinforce.html` answers 200); the
        `ImportError: cannot import name 'reinforce' from 'apps'` restart loop in the journal
        is historical and already fixed, last seen 14:54:16 against a service start of
        17:22:55 with zero errors since; and a restart on spare port 8879 with
        `SYMONEURAL_REINFORCE_ENABLED=1` answers 200 with a real completed job
        (20260817-102314-8e6000, 48 rows, state finished). **Nothing is broken.** The row read
        `ready` with the switch on and it reads `ready` with the switch off, which is the
        proof that it never consults the switch at all.

        So the whole of what is left is one judgement: what a visitor-facing LED means.

        - **(a) The row reads its switch** — `offline`, detail naming
          `SYMONEURAL_REINFORCE_ENABLED`, exactly as miner, coder, gateway and studio already
          do. One state expression changes, and `tests/frontend.mjs` must be re-read because
          it asserts on what `/api/status` renders and is in the past tense since `0c0f969`.
        - **(b) `ready` means the weights are installed** — the LED keeps its meaning and the
          detail line carries the truth (`adapter loaded · surface off`). Then miner and coder
          are the inconsistent ones and those three change the other way.
        - **(c) Something else** — say what.

        **Why this is owner: garrett and not FIX-not-FILE.** The code states the choice in the
        repo's own voice and hands it over by name: the comment immediately above the row
        argues (b) — *"Splatting one over the other would flip a unit that reads `ready` to
        `offline` the moment the env vars are unset, which is not what a visitor is being told
        here"* — and ends *"The merge is available and is a separate decision."* Overriding a
        written decision because it is awkward to wait is not fixing, and the honesty rule it
        turns on ("every LED and gauge reflects a real reading") is satisfiable both ways.
        Tick the box when you have chosen; that sets `ready for review`, not `done`.

        The row is at `backend/api.py:1946`. AUDIT.md Q10 says 1671 and that line number is
        stale — 1671 is inside the API-doc renderer now, and following it wastes ten minutes.

        note: 2026-08-21 coder — the two checks are the decision, not the implementation. The
        note: implementation check for (a) and the one for (b) are different checks, so
        note: declaring both would make 100% unreachable whichever way you go; the second one
        note: is added in the commit that implements the chosen option. The `ngrep` is green
        note: under (a) and under (b) alike, because both replace today's constant detail
        note: string, and green under nothing else.

        check: exists docs/train-row-decision.md
        check: ngrep for model/adapter tuning -- backend/api.py

◻ #97 — The spec-mediated reimplementation pipeline, and what it measures rather than claims
        owner: coder
        check: exists backend/apps/studio/tools_impl/cleanroom.py
        check: exists backend/apps/studio/custom_nodes/symoneural_cleanroom/__init__.py
        check: exists backend/apps/studio/test_cleanroom.py
        check: exists backend/apps/studio/SMOKE-cleanroom.md
        check: grep FUNCTIONAL_SPEC -- backend/apps/studio/custom_nodes/symoneural_cleanroom/__init__.py
        check: grep license_determined -- backend/apps/studio/tools_impl/cleanroom.py
        check: grep cleanroom -- backend/apps/studio/tools_impl/__init__.py
        check: ngrep litellm -- backend/apps/studio/tools_impl/cleanroom.py

        Garrett's script, 2026-08-21: a Pydantic `FunctionalSpec` used as a "firewall" between
        a Dirty Room analyst that reads source and a Clean Room engineer prompted to have
        "never seen the original source code", both on `litellm.acompletion` against
        `ollama/SyMoNeuRaL32b`, then *"expose the two agents as FastMCP tools ... represented
        as drag-and-drop visual nodes, using the Pydantic schema as the connection wire"*.

        His schema and his two roles are kept. Three parts of the plumbing could not be:
        Ollama is not installed on this box and litellm cannot enter the serving interpreter,
        so both halves ride `inference.Backend`; and a `pydantic.BaseModel` renders as an
        untyped object through `registry._json_type`, so the wire is a stdlib dataclass and
        the MCP schema carries a real `$ref` to it. `SMOKE-cleanroom.md` has the readings.

        **The framing is the part that had to change, and it is the point of the task.** A
        clean room is an institutional barrier -- one team writes the spec, a second team that
        has never seen the source implements it, and the separation is auditable. Here both
        turns are one model in one process on one box, so "do not output any original variable
        names" is a string with nothing verifying it. The module therefore *measures* leakage
        instead of asserting a barrier, and the first real run is the argument: CGMiner's own
        globals `g_chain_tmp`, `g_fan_cfg` and `g_tmp_cfg` went source -> spec -> generated
        Swift, past that instruction, in a turn that never saw the C. Every artefact it emits
        says "Not a clean-room reimplementation" in those words.

        The `exists ... SMOKE-cleanroom.md` check is the only one of the nine that a real run
        has to turn green, and it is here because the other eight would all have gone green
        over #94's dead chat surface. What the run found, each of which is a fixed defect:

        - a GPL-3.0-or-later file reported `copyleft: false`, because oematch was the only
          licence source and oematch answers `unsupported artifact` for a single `.c` file.
          The file's own header is now the primary signal and an undetermined licence reports
          copyleft with a sentence saying it was undetermined.
        - a licence paragraph wrapped so the licence name straddled a line break was invisible
          to a substring search, which is where an 80-column GPL header wraps about half the
          time.
        - queueing extract -> generate ran *neither* node: ComfyUI executes backwards from
          output nodes only, and `execution_success` with an empty output set reads as a
          broken editor.

        note: 2026-08-21 coder -- the two leak figures err in opposite directions on purpose
        note: and both say so: the spec figure over-counts (domain vocabulary a fan-controller
        note: spec cannot avoid is counted), the residual figure under-counts and labels
        note: itself a lower bound. Neither is stable -- three runs of one file at
        note: temperature 0.2 gave 15, 21 and 22. It is a reading of one run, never a
        note: property of the file, and it must not be published as one.

◻ #101 — ssh and rdp: the forwards, and what actually closes them
        owner: garrett
        [ ]

        A-R167, and he gated it himself: *"i should prob have you do the same for ssh and rdp
        but we cant do that until we have the apple ssh and rdp application made"*. The gate is
        recorded as a precondition on this task rather than as a reason to leave the assignment
        uncarried -- there is no parked state, and this is what a number is for.

        Two things in the ledger outlive the gate and are the reason this is not simply waiting.

        **The gate is not what stands between him and closing those rows.** A WireGuard or
        Tailscale tunnel closes all three forwards today with no application written. The Apple
        app is a separate want, and answering it does not require answering this.

        **The design does not transfer from R-166.** OBS avoids a tunnel because FastAPI can be
        the client and re-publish a summary. There is no summary of an SSH session: ssh and rdp
        need a real byte stream, so any such endpoint becomes the entire boundary for shell
        access to this box, on the same origin as the public site. That argument has to be made
        on its own terms, not inherited.

        note: 2026-08-21 coder -- the live posture, read from `sshd -T` on 2026-08-21 and
        note: reported to him in the same sitting: `port 22222`, `permitrootlogin yes`,
        note: `passwordauthentication yes`. That is root login by password over an
        note: internet-forwarded port, and rdp is listening on 28673 and forwarded as well.
        note: `PermitRootLogin prohibit-password` and `PasswordAuthentication no` are his to
        note: run and not mine: a lockout is not a risk to take on his behalf, and the key has
        note: to be confirmed working in a second session before sshd is reloaded. Ticking the
        note: box sets this to ready for review, deliberately not done.

◻ #102 — Rotate the spent Studio token
        owner: garrett
        [ ]

        A-R174. The live `SYMONEURAL_STUDIO_TOKEN` was displayed in an agent transcript, and
        the rule R-168 produced is general: **a credential that has been displayed is spent.**
        No value is written into the ledger, into this file, or into any commit message.

        The fix is a new value into `/etc/symoneural/api.env` (root:root, 0600) and a service
        restart. That is his because the file is root-owned and the credential is one he holds
        -- two of the five `owner: garrett` categories -- and `a944fae` claimed to have done it
        in its commit message while changing no file that could have.

        note: 2026-08-21 coder -- I have not read the current value and will not. R-174 says it
        note: directly: **do not read a whole process environment to answer a narrow question**,
        note: and reading `/proc/<pid>/environ` to confirm a rotation would put the new secret
        note: in a transcript exactly as the old one got there. The only thing needing checking
        note: is whether the surface is up, and that is available unauthenticated:
        note: `/api/studio/tools` answers 401 when Studio is on and 503 when it is off.

◻ #103 — SyMoNeuRaL Studio Upgrade / Graph Surface: a ComfyUI-shaped Studio that we own
        owner: coder
        2026-08-22. "SyMoNeuRaL Studio should look and feel like ComfyUI ... But SyMoNeuRaL
        Studio must not simply expose raw ComfyUI as the product." The direction is captured in
        `docs/specs/symoneural-studio-upgrade-scope.md` (product, targets, boundaries) and
        `docs/specs/symoneural-studio-node-system.md` (registry, schema, validator, compiler),
        with contracts in `docs/ops/MODEL-REGISTRY.md` and `docs/ops/HARDWARE-PROFILES.md`.
        Read the scope spec before writing anything, and its §2 before a single line of canvas.

        Normalized from the scope packet at
        `review/symoneural-studio-upgrade-scope-2026-08-22/`, which is untracked and stays
        that way (`.gitignore:166`). Nothing under `review/`, no transcript history, no
        archive and no weights entered this commit.

        The product rule: ComfyUI look yes, ComfyUI workflow backend yes, raw public ComfyUI
        admin surface no. Ours: graph UI, workflow schema, model registry, hardware detector,
        queue/accounts/credits. ComfyUI is an optional runner; Diffusers, vLLM, local and
        cloud runners are allowed later.

        **§2 is the gate on this task, not a preamble.** A node canvas for this page was
        already built and deleted -- ~1000 lines, snap-to-grid, SVG wires, port-type checking
        -- and the recorded reason (`tools/build_studio.py:13-22`, called "the largest single
        decision in this app") is still true: a replica of ComfyUI's editor inherits every
        upstream node change as a bug. The only thing that justifies rebuilding is that our
        schema has compile targets upstream's format structurally cannot reach. Any node type
        that only ever compiles to Comfy is a node ComfyUI's own editor should have drawn.

        Not starting from zero. `apps/studio/graph.py` (308 lines) is already the compile
        target in one-target form, with three live callers and no page; freezing its document
        format is the first deliverable and is real work. `workflows.py` is the seed of the
        templates, `comfy.py` is the runner bridge, and `plugins/reinforce/registry.py` is the
        model-registry concept already implemented. The badge engine EXTENDS its `plan_fit()`
        to diffusion weights -- that function is LLM-only today (`GGUF_DIR = MODELS_DIR/"llm"`,
        `arch_from_config` raises for anything that is not a causal LM), so no check and no
        page may imply the diffusion arithmetic already exists.

        Two product modes, scope §4, and they share one execution path: Simple mode keeps the
        original single-input principle (one text box; SyMon builds the graph behind it), Graph
        mode is the Comfy-like canvas, and generated-graph mode is the bridge -- prompt to
        SyMon-built graph to editable graph to validated job to result.

        Four execution targets, scope §5, a field on every job rather than four systems: CLOUD
        (our GPU; the customer never touches raw ComfyUI, CUDA, filesystem or card; allowlist,
        admission check, gallery, credits hook later), LOCAL_CUSTOMER (unknown hardware -- the
        browser can only ever be **approximate**, a local helper is what makes a reading
        **measured**, and conflating the two in the UI is the labelling failure this repo
        already bans), LOCAL_OWNER_NVIDIA (profile `rtx5070ti-16gb`, known not guessed, same
        queue contract, no silent CPU fallback, and NOT a raw GPU endpoint), and AUTO, which is
        resolved once and recorded on the job rather than being a fourth place to run.

        Scope §6 is one resolver: graph + requested target + detected profile + registry
        metadata in, and status / chosen backend / badges / **reason** out. §7 fixes the
        SyMoNeuRaL graph as the canonical save format and names the four compile targets --
        Comfy API JSON, Diffusers job, vLLM job, local hardware job -- with a backend payload
        never being the save format. §8 is **ten** badges, superseding the seven named earlier
        the same day (`NEEDS_VRAM`, `NEEDS_CUDA`, `NEEDS_QUEUE` were added). §9 names the ten
        planned `/api/studio/*` routes and the docs/API hyperlink contract.

        Model families, scope §3.5 -- the correction that matters most before implementation.
        The node system is **family-aware**, and SDXL/FLUX/Diffusers/Comfy/vLLM are all
        supportable later, but the baseline on this box is the FLUX/Schnell-style stack in
        `backend/models/image/` (unet q4_k, t5 q8_0, clip, vae). `ComfyUI/models/checkpoints/`
        is **absent** and there is no SDXL here, so the first spec requires neither, implies
        neither, and downloads nothing. The packet's illustrations said `sdxl-base`,
        `steps: 25`, `cfg: 7`; all three are corrected in the node-system spec. For flux, from
        `workflows.py:31-35, 71`: cfg is 1.0, the negative prompt is inert at cfg 1.0, raising
        cfg degrades rather than sharpens, and guidance is embedded conditioning. A `negative`
        port on a flux sampler is therefore a control that cannot reach the engine, which is
        barred by the same rule #79 turns on.

        The smallest useful first increment, and it is in scope §9: Studio's routers are bare
        `APIRouter()` twice (`routes.py:63-64`) with no `tags=` and no `operation_id`, so there
        is no Studio group in Swagger and nothing for `api_href` to point at. `/docs` itself is
        real and public already -- hand-registered at `api.py:1808`, which is why the
        `FastAPI(...)` call sets `docs_url=None`.

        Ordering that is not negotiable: the raw editor at `/studio/editor/*` is proxied to
        the public internet by `ops/Caddyfile:150` and gated only by the operator token, whose
        own module says that is "not a cleared posture". So #88 (take the token off Studio)
        comes AFTER the raw editor is gone, or removing the token publishes a ComfyUI admin
        surface. #89 is the plugin host; this surface is one plugin inside it, not a rival.

        The MVP is five nodes -- `image.model_loader`, `image.prompt`, `image.sampler`,
        `image.vae_decode`, `image.output` -- bound to the GGUF loaders `workflows.py` already
        enumerates (`UnetLoaderGGUF`, `DualCLIPLoaderGGUF`, `VAELoader`), not
        `CheckpointLoaderSimple`, which has nothing to load here. Not authorised by this
        commit.

        **`docs/ops/BOX-REALITY-AUDIT.md` is the gate before implementation OR migration.**
        Garrett, 2026-08-22: the existing `backend/apps/studio` tree must be audited before
        either. That report classifies it PROD / AUDIT / REMOVED against the actual box and
        ends with eight things to fix first; three of them were not visible from the spec:

        - `GET /api/studio/nodes` **already exists** (`routes.py:450`) and returns ComfyUI's
          `/object_info` proxied -- the planned route of the same name returns OUR registry.
          Same path, opposite meaning. Resolve before a node registry is written.
        - **Zero `operation_id` declarations exist in the entire tracked tree.** 17 files carry
          `tags=`; none carries an operation id. So every `api_href` in the node-system spec
          points at nothing today. Smallest first increment.
        - ~57 GB of weights under `diffusion_models`, `text_encoders`, `checkpoints`, `loras`
          and `clip_vision` are referenced by **zero** files of our code, and
          `vae/ae.safetensors` is a byte-identical duplicate of the baseline VAE (same md5).
          Unclassified inventory is not capability, and a migration would move it blind.

        `plugins/exp` and `plugins/reinforce` are still **AUDIT** in that report. A folder
        migration that moves them before they are classified moves code nobody has decided to
        keep. Confirmed by the audit and NOT to be assumed away: no SDXL is installed, the
        whole `ComfyUI/` tree is absent (the render UI is `engines/symoneural-ui`), and there
        is no CPU fallback in any serving path -- all eight CPU-device sites are in `training/`
        and are deliberate offload, not fallback.

        No implementation beyond the spec until Garrett authorises it explicitly -- said four
        times on 2026-08-22. The checks below are therefore expected to read low: four of eleven
        pass at a191dba7, and that is the honest reading of a task whose direction is captured
        and whose build has not started. The three that pass are the direction-lock documents
        themselves; every other check needs code that runs.

        note: 2026-08-22 coder -- repository purpose captured in
        note: `docs/ops/REPOSITORY-PURPOSE.md`, and it gates this work. This repo is the
        note: SyMoNeuRaL backend/server **proving ground**: applications are incubated and
        note: classified here (PROD/AUDIT/REMOVED) before promotion to Linux, Apple, Android
        note: or Windows. Garrett's seven-rule stack is the migration gate, rule 7 being "no
        note: folder migration until 1-6 are captured cleanly". A migration must NOT treat
        note: this repo as only a frontend app, only a backend API, only a ComfyUI wrapper or
        note: only a single model server. The platform gate itself lives in `GUARDRAILS.md`
        note: and is not restated: all four native platforms are individually held and only
        note: Garrett naming one clears it. Toolchains are the carve-out and are not held.

        check: exists docs/specs/symoneural-studio-upgrade-scope.md
        check: exists docs/specs/symoneural-studio-node-system.md
        check: exists docs/ops/HARDWARE-PROFILES.md
        check: exists docs/ops/BOX-REALITY-AUDIT.md
        check: exists docs/ops/REPOSITORY-PURPOSE.md
        check: exists docs/specs/symoneural-application-lab.md
        check: exists docs/specs/symoneural-platform-targets.md
        check: grep StudioGraphSchemaFrozenTests -- backend/apps/studio/test_studio.py
        check: grep StudioGraphCompileTargetTests -- backend/apps/studio/test_studio.py
        check: grep StudioTargetResolverTests -- backend/apps/studio/test_studio.py
        check: grep StudioNodeContractDocsLinkTests -- backend/apps/studio/test_studio.py
        check: grep StudioEditorNotPubliclyExposedTests -- backend/apps/studio/test_studio.py
        check: grep StudioHardwareBadgeTests -- backend/apps/studio/test_studio.py
        check: exists backend/apps/studio/SMOKE-graph-surface.md
        note: 2026-08-22 coder — pre-migration scope batch landed in ten commits, 9479cee2
        note: through 5d5724be: application lab, platform targets, live stack, control board, API
        note: surface, website look/feel, Parameters, MoE, Cloud/Local, Generic contracts, seven
        note: per-surface scopes, the security audit, the licence/model/Yocto/SBOM/provenance
        note: audits, and the commercial-mode and revenue specs. Docs and one page's copy only.
        note: THIS DOES NOT CLOSE PHASE 0.6b. 0.6b is the CLAUDE.md migration (R-180) and is a
        note: different workstream: the migration has landed -- ENGINEERING.md, MEASUREMENTS.md
        note: and EXPORTS.md each say so in their own headers -- but neither this file nor
        note: docs/specs/scope-of-work-2026-08-22.md records it CLOSED, so it is a candidate.
        note: Phase 1 is NOT STARTED and Deploy is NOT STARTED. The Scope Parking Lot REMAINS
        note: QUEUED per Garrett's standing statement, and it has no artefact in this repo -- a
        note: grep across tracked files finds no mention of one. Recorded both ways on purpose:
        note: the status is his, and the absence of a file is the measurement.
        note: Two figures deliberately left unreconciled rather than restated: BOX-REALITY-AUDIT
        note: §7 says 141 shipped routes and SECURITY-AUDIT measures 123. Reconcile before either
        note: is published -- this project has already published a count that was never true of
        note: the commit it sat beside.

◻ #104 — SyMoNeuRaL ModelOps/RuntimeOps: runtime registry, router, hot swap, governor
        owner: coder
        2026-08-22, pre-migration scope alongside #103. "The Studio upgrade must generalize
        beyond ComfyUI into a full SyMoNeuRaL ModelOps + RuntimeOps architecture." Studio is
        the visual surface; the core is the model registry, the runtime registry, the target
        resolver, the hot swap manager, the GPU governor, the job queue and the node/API/docs
        link contract.

        Split from #103 rather than folded into it. #103 is the graph surface; this is the
        core underneath. They complete independently -- a runtime registry and hot swap can
        land with no canvas, and a canvas can land on the runtimes that already exist -- so
        one task whose 100% meant both would mean neither.

        Specs: `docs/specs/symoneural-runtime-registry.md` (registry + router),
        `docs/specs/symoneural-model-hot-swap.md` (residency operations and multi-model
        serving). Contracts: `docs/ops/RUNTIME-PROFILES.md`, `docs/ops/GPU-GOVERNOR.md`,
        and `docs/ops/MODEL-REGISTRY.md` extended with model_family/format/load_policy/
        eviction_priority/hrefs.

        **Two registries, not one.** The model registry answers what can be served; the runtime
        registry answers what can serve it. The router joins them. Collapsing the tables either
        duplicates every model per runtime or loses the difference, and it is the single most
        likely way this design goes wrong.

        **The maturity ladder is mandatory on every runtime claim** -- absent / source-only /
        built / running / measured. Measured on this box at 41524770 and recorded in
        `docs/ops/BOX-REALITY-AUDIT.md` §8: symoneural-llm (llama.cpp) and symoneural-diffuse
        (stable-diffusion.cpp) are **built** with CUDA compiled in; symoneural-ui (Comfy) is
        **source-only**; whisper.cpp, vLLM, TensorRT-LLM, Triton and the NVIDIA samples are
        **absent**. The API is running (:8800, and the gateway on :8000) but **no model runtime
        is resident** -- nothing on 8188. No document may claim otherwise.

        Three findings from the runtime audit that change the work:

        - `contrib/` **does not exist**, and two live things cite it. `docs/ENGINEERING.md`
          gives a pinned-venv check at `contrib/cuda-samples/python/.venv/bin/pip` that cannot
          run, and `apps/voice`'s whisper binary lives there. Voice is honest about
          availability (`asr.installed()` names the missing path, `/state` reports offline) but
          emits `"engine": "whisper.cpp, CPU build (GGML_CUDA=OFF)"` and
          `"measured_ms_short_utterance": 650` unconditionally -- a measured figure with no SHA
          and no date, about an absent binary. AUDIT; the fix is to gate both behind `ready`.
        - `run/resident` reads `image` with no image process alive, and `gpu-governor.sh status`
          **says so itself**: `image (not running -- stale marker)`. That is R-172's fix working.
          The hot swap manager must reconcile residency against the process table rather than
          trusting its own bookkeeping -- see `symoneural-model-hot-swap.md` §4.
        - The planned `/api/hardware/*` and `/api/models` overlap #103's
          `/api/studio/hardware/*` and `/api/studio/model-registry`. One of each, not both.
          Same class of collision the audit already found at `GET /api/studio/nodes`, caught
          before it was built this time.

        Owner profile stays `rtx5070ti-16gb` -- the audit confirms RTX 5070 Ti / 16303 MiB /
        driver 610.57.04 / CUDA 13.3. No CPU fallback for GPU workloads unless authorised
        (the code has none today: all eight CPU-device sites are in `training/` and are
        deliberate shard offload). VRAM admission mandatory. Large image + large LLM
        concurrency is NOT assumed and multi-model residency must be measured before it is
        called green -- `docs/ENGINEERING.md`: chat ~5 GB, image ~7 GB, QLoRA ~12 GB "cannot
        coexist".

        Backstage catalog and Nx workspace boundaries are captured in
        `symoneural-studio-upgrade-scope.md` §11-12 as **future direction only**. Do not
        install Backstage. Do not migrate folders. A catalog entry without a maturity level
        reads as an inventory of things that exist, and four of the named components describe
        runtimes that are absent.

        No implementation, no deploy, no migration, no model downloads, no weight commits, no
        .venv commits, and the current Studio files do not move. `.venv` was checked: 0 tracked
        files, 0 repo-wide, ignored by `.gitignore:24`.

        note: 2026-08-22 coder -- repository purpose captured in
        note: `docs/ops/REPOSITORY-PURPOSE.md`, and it gates this work. This repo is the
        note: SyMoNeuRaL backend/server **proving ground**: applications are incubated and
        note: classified here (PROD/AUDIT/REMOVED) before promotion to Linux, Apple, Android
        note: or Windows. Garrett's seven-rule stack is the migration gate, rule 7 being "no
        note: folder migration until 1-6 are captured cleanly". A migration must NOT treat
        note: this repo as only a frontend app, only a backend API, only a ComfyUI wrapper or
        note: only a single model server. The platform gate itself lives in `GUARDRAILS.md`
        note: and is not restated: all four native platforms are individually held and only
        note: Garrett naming one clears it. Toolchains are the carve-out and are not held.

        check: exists docs/specs/symoneural-runtime-registry.md
        check: exists docs/specs/symoneural-model-hot-swap.md
        check: exists docs/ops/RUNTIME-PROFILES.md
        check: exists docs/ops/GPU-GOVERNOR.md
        check: grep RuntimeRegistryMaturityTests -- backend/apps/studio/test_studio.py
        check: grep RuntimeRouterDecisionTests -- backend/apps/studio/test_studio.py
        check: grep HotSwapAdmissionTests -- backend/apps/studio/test_studio.py
        check: grep HotSwapResidencyReconcileTests -- backend/apps/studio/test_studio.py
        check: exists backend/apps/studio/SMOKE-hot-swap.md
        note: 2026-08-22 coder — ModelOps future-proofing landed: tools/modelops_inventory.py,
        note: scripts/modelops/symoneural-modelops-stage.sh, backend/apps/test_modelops.py, and
        note: four ops docs. Docs/script/inventory only -- NO model downloaded, no active default
        note: changed, no weight deleted, moved or committed.
        note: THE FINDING: PROVENANCE.json covers 11 of 28 weight files. The other 17 are
        note: 78.26 GiB -- 61% of the weight bytes on this box -- with no upstream, no licence, no
        note: role and no runtime recorded. All 17 classified unknown-blocked. BOX-REALITY-AUDIT
        note: §7 had this as "~57 GB of unreferenced weights"; nobody had counted, because no
        note: document was measuring. Now re-runnable: python3 tools/modelops_inventory.py.
        note: Active defaults are read from source, not assumed: chat is
        note: llm/symon-1.0-7b-q4_k_m.gguf with the 0.5b draft (api.py:187,:191), the image bundle
        note: is the four FLUX/Schnell components (api.py:202-205 == workflows.py:48-51), and asr
        note: is whisper/symoneural-listen-base-en.bin (voice/asr.py:56). That last one is a bug
        note: this work found: the first draft of the tool read only api.py and reported the listen
        note: model idle while voice was loading it. One loader site missed is one active model
        note: misclassified, so the sites are an explicit list with a test.
        note: symon-openai-20b (openai/gpt-oss-20b) is a CANDIDATE only -- not downloaded, not
        note: staged on disk, not active. Qwen stays active and is not deleted; it becomes rollback
        note: only after a smoke record exists AND Garrett approves. Six activation gates, exit 3
        note: on any failure. The script refuses to download even with the confirm phrase set:
        note: tens of GB onto a disk already holding 194 GB should not be one env var away.
        note: The runtime question is the real gate and is UNRECORDED on purpose -- the engine
        note: wants GGUF and gpt-oss ships MXFP4-quantised weights a stock llama.cpp build may not
        note: read. Read the upstream card BEFORE fetching; finding that out after the download is
        note: the avoidable version of the discovery.
        note: 2026-08-22 coder — gpt-oss RUNTIME GATE ANSWERED. Verdict: NEEDS CONVERSION.
        note: Everything required is in this tree; one conversion step stands between upstream's
        note: format and the engine's. Measured, not recalled: upstream ships safetensors only
        note: (original/model.safetensors 12.81 GiB, or three shards of the same total, NO GGUF)
        note: and is Apache-2.0, read from the HF API. The engine (build 296, commit 2246ab7)
        note: registers LLM_ARCH_OPENAI_MOE as "gpt-oss", carries the Harmony chat template, and
        note: supports GGML_TYPE_MXFP4 = 39 on the CUDA path -- convert.cu, getrows.cu, MMQ.
        note: conversion/gpt_oss.py is a real converter with repack_mxfp4(), which repacks the
        note: 4-bit blocks rather than dequantising them; without that the GGUF would inflate to
        note: bf16 and would not fit this card at all.
        note: Conversion needs torch and the INTERPRETER MATTERS: /usr/bin/python3 has none,
        note: training/.venv/bin/python3 has 2.11.0+cu128 with cuda available and sm_120
        note: recognised. The isolated smoke needs no torch -- it is the C++ engine binary.
        note: VRAM finding that changes the smoke command: 12.81 GiB of weights plus ~3.9 GiB of
        note: KV at the production -c 65536 -np 2 is ~16.7 GiB on a 16,303 MiB card. It will NOT
        note: fit at production context, so --smoke-candidate uses -c 8192 -np 1 and says why --
        note: an OOM nobody predicted reads like an incompatible model rather than a greedy argv.
        note: ISOLATED SMOKE added: --smoke-candidate <id>. Isolation is structural, not a flag.
        note: It launches the engine directly against the candidate on port 8099, in its own
        note: process, and never invokes the production API module -- the only thing that knows
        note: the production defaults. So a fallback is not disabled, it is unreachable.
        note: Garrett's sharpening is what the test now enforces: a function that cannot NAME the
        note: fallback cannot load it. The forbidden symbols and filenames are absent from that
        note: function's body entirely and the body explains isolation in neutral terms. My first
        note: version allowed prose mentions and forbade only dereferences; his is stricter and
        note: grep-verifiable, so it replaced mine.
        note: Exit 5 with REFUSED on a missing candidate or engine. No adapter flag, no draft
        note: model, own port. Nothing downloaded, no default changed, Qwen present and untouched.

◻ #105 — SyMoNeuRaL Control Plane Matrix: the 16-dimension record, and three open rulings
        owner: coder
        2026-08-23, opened at 507e09ee alongside the Bootcamp framework (#not-numbered, landed
        c0ee30e3/507e09ee). Bootcamp owns the roster vocabulary, the starter gate and the depth
        charts. This task owns the NORMALIZED record -- App x Instance x Team x Starter x
        Candidate x Captain x Model x Tool x Agent x Data x Runtime x Gate x Meter x State x
        Risk x Runbook -- and the machine-checkable rows that fill it.

        DELIVERED at 507e09ee: four documents plus a test with teeth.
        docs/specs/symoneural-control-plane-matrix.md   -- the schema, 20 instance rows, ratings
        docs/ops/APPLICATION-MODEL-CAPABILITY-MATRIX.md -- app x weight reachability, measured
        docs/ops/MODEL-BENCHMARKS.md                    -- the benchmark ledger, SHA per figure
        docs/ops/VLLM-BENCH-PARITY.md                   -- the parity contract, unmeasured
        backend/apps/test_control_plane_matrix.py       -- 16 tests, 9 sabotage cases verified

        THE FINDING THAT MATTERS. Filling the Runtime column against the disk, rather than
        against a document, caught a claim no file-based check could: ASR's weight is present
        and 1/1 manifested while `whisper-cli` is ABSENT -- contrib/ does not exist, /contrib is
        gitignored, and a filesystem sweep found no whisper binary anywhere. Two apps name it,
        `voice` and `sigils`, and neither can transcribe.

        The repo already knew. RUNTIME-PROFILES.md:42 and symoneural-runtime-registry.md:90 both
        say `absent`, and #104 above states contrib/ does not exist, measured at 41524770, 13:12
        on 2026-08-22. The Bootcamp depth chart said `proof: serving` at 507e09ee, 22:21 -- NINE
        HOURS LATER. So this was not a stale doc nobody re-measured; it was a newer document
        contradicting an older measurement, same repo, same day. The mechanism: the Model row
        was filled from PROVENANCE.json ("1/1 manifested") and the Runtime row was never filled
        at all. That is the whole argument for a Runtime column.

        Corrected in place, dated, quoting what each line said: bootcamp (4 places),
        RUNTIME-PROFILES.md, BOX-REALITY-AUDIT.md, symoneural-runtime-registry.md,
        symoneural-studio-node-system.md.

        SECOND FINDING: vLLM is NOT absent. vLLM 0.25.1 lives in /home/google/.venvs/vllm,
        imports, torch 2.11.0+cu130, cuda True, sees the 5070 Ti, created 2026-07-20 -- three
        weeks BEFORE 7a4e5c98 wrote "absent" into RUNTIME-PROFILES.md:43. Outside the repo, so
        no in-repo search could find it. NO service runs, so MODEL-REGISTRY.md:108 and
        BOX-REALITY-AUDIT.md:507 ("candidate only, no service running") stay untouched and true.
        "Not installed" and "not serving" got conflated; only the first was ever wrong.

        THREE OPEN RULINGS -- owner: garrett on the first two, and they are why this is not done:

        1. The maturity ladder has no word for "installed, importable, no service". absent is
           false, built is misleading (we compiled nothing; a third-party venv is not our
           artefact), running is false. Either add a rung, or rule the ladder repo-scoped so an
           external venv is out of scope. Placeholder `installed-not-serving` is in the files
           now and is explicitly NOT a ladder level.
        2. symoneural-ui (Comfy): RUNTIME-PROFILES says source-only; measured is source PLUS a
           working .venv with torch 2.13.0+cu130, cuda True. A Python app has no compile step, so
           `built` may be wrong too. Left as source-only, measurement recorded, not reclassified.
        3. voice/routes.py:107,116 emit "engine" and "measured_ms_short_utterance": 650
           UNCONDITIONALLY -- a measured figure, no SHA, about an absent binary. The route is
           otherwise honest (available:false, problem names the missing path) and the surface is
           disabled, so nobody is told this today. Already filed under #104; the check below
           tracks it so it cannot be forgotten twice.

        check: exists docs/specs/symoneural-control-plane-matrix.md
        check: exists docs/ops/APPLICATION-MODEL-CAPABILITY-MATRIX.md
        check: exists docs/ops/MODEL-BENCHMARKS.md
        check: exists docs/ops/VLLM-BENCH-PARITY.md
        check: exists backend/apps/test_control_plane_matrix.py
        check: exists engines/symoneural-listen/build/bin/symoneural-listen
        check: ngrep ruling pending -- docs/specs/symoneural-runtime-registry.md
        check: ngrep measured_ms_short_utterance -- backend/apps/voice/routes.py

        The last three checks are RED on purpose and each names real remaining work: build the
        ASR runtime into engines/symoneural-listen/ AND track its build script, land the ladder
        ruling, gate the unconditional ASR figure. 5 of 8 passing is the honest reading of
        "matrix delivered, three follow-ups open" -- and it keeps archive_tasks.py from filing
        this at 100% two minutes after it was written.

        WHY engines/ AND NOT contrib/. The check deliberately does NOT target
        contrib/whisper.cpp/build/bin/whisper-cli, because that path is BANNED:
        test_references_boundary.py:70 bans references/<tree>/ and the contrib/whisper.cpp/
        spelling both, and its failure message says "Put what you need in our own tree." Two
        whisper-cli binaries (973,872 B each) do exist under references/ and are quarantined by
        that same rule -- so a naive "rebuild contrib/" recreates a rule violation the grep
        happens not to see. d6b7838a already forked the other two GPU runtimes under our own
        names into engines/ (symoneural-llm, symoneural-diffuse) and
        symoneural-runtime-registry.md:88 already reserves runtime_id: symoneural-listen. Two
        call sites to repoint, voice/asr.py:53-54 and sigils/listen.py:44, and no others.

        note: 2026-08-23 coder -- MY OWN OVERCLAIM, corrected same day. The first draft of these
        note: documents said "a filesystem sweep found no whisper-cli anywhere on the box". I
        note: wrote that before the sweep finished. Two exist, both under references/, one dated
        note: Aug 17 14:04 -- the same hour voice-spec.md:28 recorded the build. The conclusion
        note: held (ASR cannot serve) but the reason was wrong: quarantined, not missing. That
        note: distinction is the whole difference between "rebuild it" and "rebuild it somewhere
        note: else", so it changed the recommendation and the check above.
        note: Why no test caught the rule/code disagreement: the boundary check skips prose and
        note: requires a quote character, so asr.py:4's backticked mention is correctly ignored,
        note: and asr.py:54 plus sigils/listen.py:44 assemble the path from SEGMENTS
        note: (ROOT / "contrib" / "whisper.cpp" / ...) so the banned literal never appears on a
        note: line. The rule and the code disagree and the grep cannot see it.

        note: 2026-08-23 coder -- the test was verified by SABOTAGE, not by going green, and the
        note: harness is TRACKED at tools/sabotage_matrix.py so the proof is reproducible rather
        note: than asserted: `python3 tools/sabotage_matrix.py` (--list to inspect without
        note: mutating). It refuses to start on a dirty tree, restores in a finally and asserts
        note: the restore is byte-exact; apps/test_sabotage_matrix.py keeps it honest without
        note: running it, so `pytest apps/` stays side-effect free. TWELVE cases now -- the nine
        note: below, two added by the pre-merge review (a Safety cell hand-typed against the
        note: derivation table, an exposure cell contradicting api.py's mount table), and one
        note: added after the POST-MERGE failure: the published app-module count desyncing from
        note: the tree. That failure was a test bug, not a doc bug -- backend/apps/.pytest_cache,
        note: a leftover from an earlier pytest run, was counted as an 18th app module. It passed
        note: in the worktree, which had no such directory, and failed on main, which did. The
        note: filter now lives in is_app_module_dir() and matches tools/bootcamp_scout.py:189
        note: (skip __-prefixed AND .-prefixed names) -- and a test pins the two together, because
        note: the old comment CLAIMED to match the Scout while the code did something looser.
        note: The nine, each landing on the test written for it: 4th option added to a depth
        note: chart; benchmark cell changed in the ledger only; SHA attribution line deleted;
        note: instance count desynced from the table; off-the-record marked available; vLLM
        note: called "not installed" outside a blockquote; ASR re-claimed as serving; a
        note: nonexistent app module named; the 404-commit caveat dropped. All nine went red,
        note: all files restored byte-for-byte, suite green after.
        note: TWO of those assertions were DECORATION on the first pass and the sabotage run is
        note: the only reason that is known. "Every figure appears in both files" passed while a
        note: table cell read 999.9, because 166.3 also occurs in prose two sections down -- a
        note: substring search over a whole document cannot tell a cell from a mention of it. It
        note: now compares table rows cell-for-cell. And the SHA check accepted the section
        note: HEADING's copy of the SHA, so deleting the attribution line entirely still passed;
        note: it now requires an explicit **SHA `<hex>` line. A third was VACUOUS: the weight
        note: check parsed zero filenames because the doc named weights by column header, so it
        note: asserted nothing. The doc now spells all ten out and the test refuses to run on
        note: fewer than ten.
        note: 2026-08-23 coder -- CAVEAT CARRIED: 404 commits between 2026-08-17 and 7a4e5c98
        note: are not audited. Every runtime, route, rating and live-state reading in these four
        note: documents is measured at 507e09ee on 2026-08-23 and is NOT historical proof. The
        note: unaudited range touched backend/api.py (53 commits), Studio (16), site/ (90) and
        note: ops/Caddyfile (9), so a cell here could have been different last week with nothing
        note: in the audited range saying so. A test asserts all four docs keep this caveat.
        note: 2026-08-23 coder -- no app code was touched. No starter changed, gpt-oss NOT
        note: activated, Qwen still CHAT_MODEL, commercial mode off, Phase 1 not started,
        note: nothing deployed, auth unchanged, no weight moved/deleted/committed.
