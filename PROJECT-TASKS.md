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
however obviously useful it looks — the exit from `INTAKE.md` is a ticked box, not my
judgement. The obligation that comes back the other way is real and is written down as #64:
*"you must give me information and help on getting the boxes checked"*. A box cannot be
ticked on a title alone, so every assignment carries a brief.

**Intake is immediate.** *"as soon as i send a prompt it should quickly added to
coder-task.md"*. A prompt becomes a task in the same turn it arrives.

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

◻ #20 — Rebrand ComfyUI as symoneural-ui, keeping GPL-3.0 compliance

◻ #21 — Move the agent harness into studio as a plugin (was: name it symoneural-harness)
        REWRITTEN 2026-08-20 per R-134. Naming it was the smaller half; the harness lands
        under backend/apps/studio/plugins/harness like exp, discovery and reinforce, and
        is gated on the studio plugin interface being written first.

◻ #22 — Demote exp from a rack row to a symoneural-studio plugin

◻ #23 — Take reinforce out of the live stack and into symoneural-studio

◻ #24 — Build symoneural-invest: a hardware configurator for server upgrade decisions

◻ #25 — Apply the SymonSays naming system across code and site
        SCOPE ADDITION (Garrett, this turn, 2026-08-20): the site's user-facing action
        phrases are IN SCOPE, not preserved prose. "talk to the box", "chat to the box",
        "make it draw something" and sibling phrases update to the SymonSay(s) naming
        system. Sweep greps: "the box" and "draw something" across site/ AND tools/
        generators. Generators are the source of truth: edit generator, regenerate,
        build_cachebust.py LAST, per the standing rule.

◻ #26 — Route rack applications under /livestack/<name> instead of /app.html

◻ #27 — Fix Live Stack typography and promote the app brand icons

◻ #28 — Fold tuner + guide into Symoneural Streamer; sigils stays its own application
        REWRITTEN 2026-08-20. The original wording — "Rename to Symoneural IPTV; merge
        Sigils into Chat" — is contradicted on BOTH points by R-132 and R-137: the name
        is streamer, not IPTV, and sigils keeps its own rack row rather than being
        absorbed by chat. Kept under #28 because it is the same work, renamed.

◻ #31 — Serve the studio render from disk instead of proxying GET /view

◻ #33 — Rebrand the four engines: llama.cpp, stable-diffusion.cpp, kawpowminer, whisper.cpp
        R-150, and the highest-value item on this list because it is also the fix for #34.
        `llama-server` → `symoneural-llm`, `sd-cli` → `symoneural-diffuse`,
        `kawpowminer` → `symoneural-miner`, `whisper` → `symoneural-listen`. Our tree, our
        build script, our binary names, MIT copyright notice carried (LICENSES.md:119-120
        records both engines as MIT, so renaming is permitted). Then repoint
        `backend/api.py:154-155`.

◻ #34 — Bring every application back online, and keep it online
        R-147, standing: *"THEY ONLY GO OFFLINE WHILE YOU WORK ON THEM"*. chat, remix, image
        and sigils are dark for ONE reason — `api.py:1545-1546` gates them on
        `LLAMA_SERVER.exists()` and `SD_CLI.exists()`, and both binaries are absent from the
        paths api.py names. Every weight file is present. #33 lights all four. The rest
        (gateway, miner, exp) are env-switch work and independent of it.

◻ #35 — Automate the deploy
        R-114, and Garrett has already approved it once: *"already approved, do not ask
        again"*. Do not re-ask.

◻ #36 — Close the live-wrong claim the deploy was blocking
        R-115. Blocked by #35 — the claim is only false until the deploy runs.

◻ #37 — Automate secret rotation, split by who issues the secret
        R-116, and the split is the requirement, not a detail: *"do not report the halves as
        one"*. Secrets I can rotate are a different report from secrets only Garrett can
        (SPOTIFY_CLIENT_SECRET is a dashboard action and is still NOT rotated).

◻ #38 — Extend the leak guard to every archive path
        R-117: rotation does not fix the source. `scripts/lib/archive-guard.sh` is currently
        modified, incomplete and uncommitted — `_AG_PRUNE_DIRS` is added but never consumed,
        and `--exclude='*.md'` has not been removed. Finish the wiring or revert it; a
        half-wired guard is worse than none because it reads as present.

◻ #39 — Build symoneuralcredentials, CLI-driven
        R-89. Terminal paste flow, NOT DOM scraping. `run/credentials.env` mode 600.
        Path-refusal must be mutation-checked. `X-Symoneural-Token`. A `/run` endpoint is
        explicitly NO.

◻ #40 — Finish the symoneural-cli interface polish
        R-81, flagged in the ledger itself as *"the interface-polish remainder has no task
        number"* — this task is that number.

◻ #41 — Fix audit item 26: gpu-governor.sh:200 labels a historical record as a live one
        R-113, and Garrett was explicit that his own authorship is not a reason to leave it:
        *"fix it; Garrett's authorship is not a reason to leave it"*. Not Garrett-only.

◻ #42 — Reclassify every Garrett-only item against the five categories, and report what moved
        R-112. Three are already known misclassified: audit 24 and 27 are missing commands,
        26 is git-blame reasoning. None match the five categories (physical hardware,
        credentials only he holds, third-party dashboards with no API, money, legal).

◻ #43 — Resolve the three "gateway" namespaces into one
        R-130. Three things now carry the name: `backend/apps/gateway` (Python: abi, chain,
        keccak, routes), `backend/apps/symon-gateway` (Rust, and currently showing as deleted
        in the working tree), and `ops/gateway/`. R-128/R-129 say one app per
        `backend/apps/<name>`; this is that convention applied.

◻ #44 — Make site/account.html an application
        R-131, first half. Recorded as two asks *"sized very differently; do not conflate
        them"* — so they are two tasks.

◻ #45 — Give every application a model adapter
        R-131, second half. The larger of the two by a wide margin.

◻ #46 — Migrate symoneural voice into every app for voice input
        R-136. Category 4: not a live-stack row of its own, a capability that lands in each
        app. `whisper.cpp` → `symoneural-listen` from #33 is the engine underneath it, so
        this is gated on #33.

◻ #47 — Close audit items 7, 9, 10, 11, 12, 18, 19, then 15
        R-84, the bypass-mode audit loop, exit condition AUDIT-DONE. Currently 13 DONE,
        9 OPEN. Item 15 goes last because it counts the untracked review documents, and the
        other items' closure changes that count.

◻ #48 — Rotate VLLM_API_KEY and DJ_TOKEN, and untrack the .env
        R-121. The *"then cut v3"* half of that request is cancelled with #14; the rotation
        half stands on its own. Names and lengths only, never values.

◻ #49 — Run all four suites at the final HEAD
        Phase 3.3. Every figure SHA-anchored, no count carried forward as a re-run.

◻ #50 — Write AUDIT-DONE-2026-08-19.md
        Phase 3.4, and the audit loop's exit condition. Cannot land before #47.

◻ #51 — Migrate settlement into gateway
        R-139, which closes the destination table.
        resolve: backend/apps/settlement -> backend/apps/gateway/settlement

◻ #53 — Fold rackpower, the live stack and the control board into controls
        R-138.
        resolve: backend/apps/rackpower -> backend/apps/controls

◻ #54 — Write the studio plugin interface
        Gates #21, #22, #23 and #55 — all four land as studio plugins and none of them can
        land before the interface they plug into exists. Do this one first.
        resolve: -> backend/apps/studio/plugins/__init__.py

◻ #55 — Migrate symoneuraldiscovery into studio as a plugin
        R-137. Blocked by #54.
        resolve: backend/apps/symoneuraldiscovery -> backend/apps/studio/plugins/discovery
### Intake from Garrett's prompts, 2026-08-20

Added the same turn they were sent, per the intake rule above. The prompts that were
satisfied within that turn (the progress-page timer, the phase-tracker deletion, the
questionnaire, the closed-task move, the status percentage) are already in
`review/CLOSED-TASKS.md` rather than sitting here as work.

◻ #56 — Give every audit item a machine check, so the surface reports a reading
        Garrett: *"Audit surface needs to be automated"*. Half of it is done — `AUDIT.md`
        carries the questions and `run/progress.html` generates the answered count. The
        remaining half is the surface itself: several items ARE predicates and should be
        tested rather than asserted. Item 10 is "does `docs/upgrading.md` exist", item 11 is
        `yocto/README.md`, item 15 is a count of untracked root documents, item 19 parses
        `BBFILE_PATTERN`. Give each one a `check:` line and report agree/disagree against the
        recorded disposition, so a stale DONE cannot survive.
        check: grep ^check: -- AUDIT-SURFACE-2026-08-19.md

◻ #57 — Make prompt-to-task intake verifiable, not just promised
        Garrett: *"as soon as i send a prompt it should quickly added to coder-task.md"*.
        The rule is written down; nothing enforces it. The ledger coverage panel is the
        first half (an open ledger entry naming no task is now flagged red). The second half
        is the other direction: a prompt that never reached the ledger at all is invisible to
        that check. Cheapest honest version is a session-transcript sweep that lists user
        turns with no matching ledger entry.
        check: exists tools/check_intake.py

◻ #58 — Drain the request ledger to four or fewer open entries
        Garrett: *"our request ledger should hardly ever exceed 3 or 4 items"*. It is at 148
        entries with 58 not-done. The ledger is an inbox: an entry that has become a task
        should close, standing rules belong in the working agreements rather than in the
        inbox, and history belongs in `review/`. The page now renders the depth against a
        target of four, so this task is measurable the moment it starts moving.
        check: maxcount 4 ^status: (captured|queued|in-progress|held) -- GARRETT-REQUESTS.md

◻ #64 — Give every assignment the brief Garrett needs to tick its box
        owner: coder
        Garrett: *"until i check the box you have nothing to do except what is in the project
        task however you must give me information and help on getting the boxes checked. You
        must be thorough on things you have dissed me on"*.

        That is the other half of the two-surface split. If ticking is the only thing asked of
        him, then a title is not enough to tick on — an entry reading "R-39 — try harder to
        avoid venvs" gives him nothing to decide with. Every assignment needs, in the file:
        what it is, what it would cost, what I recommend and why, and what happens if it is
        never ticked. Automatic where the source has the prose; hand-written where it needs a
        recommendation, because a generated recommendation would be a guess in a confident
        voice.

        The second sentence is the sharper one and names a real pattern: items I deferred,
        marked LOW, or filed as Garrett-only got a disposition and no argument. Those get the
        fullest briefs — audit 23 (LOW), 24 and 27 (Garrett-only), 26 (NOT MINE), and every
        ledger entry I marked `captured` and left. Where I was wrong to park it, the brief says
        so instead of restating the disposition.
        check: grep ^brief: -- INTAKE.md
        check: grep RECOMMEND -- tools/build_intake.py

◻ #59 — Declare checks on every task that can carry one
        The percentage is only as honest as its checks, and most tasks currently read `—`.
        That is the correct rendering for an unmeasured task, but it is not a good resting
        state: Garrett asked for percentages he can rely on, and a list where most rows are
        blank does not deliver that. Work through the open tasks and give each one a check
        set where 100% genuinely means done. Where it cannot — "apply a naming system
        tastefully" has no predicate — say so in the task rather than inventing a number.

◻ #68 — Build the full stack: debian backend and four frontends
        owner: coder
        R-11, and it is the largest single item on this list. Garrett: *"build the FULL
        stack"* — a debian backend plus FOUR frontends: web, android/firestick, debian
        desktop, and Darwin/swift.

        Held per platform, deliberately, and R-118 is the carve-out that makes it actionable
        now: the SDKs and toolchains ARE in scope even while the app builds are held. So the
        work that can start today is the toolchain matrix — what compiles each target, where
        it runs, and what is missing — not four app skeletons nobody asked for yet.

        The web frontend already exists and ships; do not rebuild it. The honest reading of
        this task is "three more frontends and the toolchains to build them", and the first
        deliverable is the matrix that says which of the three this box can build at all.

◻ #69 — Multi-environment servers: prod, sandbox, development, testing, tuning
        owner: coder
        R-55, with easy promotion of an app between environments. One box and one GPU is the
        binding constraint — five live stacks cannot coexist in 15.92 GiB — so this is an
        environment SELECTOR over one stack, not five stacks. Design it as a config layer
        (which port, which weights, which surfaces enabled) that `scripts/symoneural.sh` can
        switch between, and promotion becomes copying a config, not moving a service.

        Do not start this before #34 and #35: promoting an app between environments is
        meaningless while four applications are dark and the deploy is manual.

◻ #70 — Make the Studio row tell the truth about ComfyUI
        owner: coder
        R-102, audit item 27. The Studio row renders green while nothing on this box starts
        ComfyUI, so the row survives exactly one reboot before it is a lie. This is a direct
        breach of the honesty rule that the whole site argues from — *"no decorative status
        indicators"* — which is why it is a task and not a preference.

        Two options were offered. Take option 2: fix the CLAIM, not the process. Auto-starting
        ComfyUI at boot would put a 13 GiB-peak GPU tenant on the card with nobody asking for a
        render, which contradicts the governor rule about holding for a job rather than a
        lifetime. So the row must read from a real probe of :8188 and say `offline` when
        nothing answers. Garrett's question A-Q6 (*"should ComfyUI start itself?"*) is answered
        by this task rather than left open: no, it should not, and the row must stop implying
        it does.

◻ #66 — The live-stack application roster, and backend/apps made to match it
        owner: coder
        R-132. The roster is the authority on what an application IS; `backend/apps/` is
        currently a superset of it and the rack renders a third list. Three lists that
        disagree is the same failure as three state documents, and the fix is the same one:
        pick the authority, make the others read from it.

        Deliverable: the roster written down once, `backend/apps/` reconciled against it, and
        the rack's rows generated from that single source rather than maintained by hand.
        Related, and do not duplicate their work: #43 (gateway namespaces), #52 (studio
        rename), #53 (fold rackpower/livestack/controls).

◻ #67 — Anchor every figure in docs/ and .claude/HANDOVER.md to a SHA
        owner: coder
        Audit item 16, and Garrett's A-Q9 asked whether this was in scope. It is: the standing
        rule is that a number with no SHA cannot be checked, only believed, and this project
        has already published a test count (1063) that turned out never to have been true of
        the commit beside it.

        Sweep every measured figure in `docs/` and `.claude/HANDOVER.md`, and give each one
        the commit it was read on plus a label — measured, vendor, or projected. Where the
        tree it was read on is no longer identifiable, re-measure or delete the figure. Do not
        carry a number forward and re-date it; that is the exact defect this closes.
