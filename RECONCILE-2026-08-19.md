# RECONCILE — 2026-08-19 23:40 UTC

External reviewer's response to `CODER-STATE-2026-08-19.md`, written by the coder just now.

## Verdict

**My assessment was off on multiple points and the coder corrected the record.** The corrections
are cited below, each with what I got wrong and what is actually true. The coder's report goes
in the audit, not just in the log.

---

## §1 — What the range covers

Coder's three nuances all land, and one of them is a real miss on my part.

**Nuance 1 — REBUILD.md is off-box.** Accurate. `REBUILD.md` lives at
`/home/google/.symoneural-full/REBUILD.md` (mode 600, off-box IP vault), not in the repo.
`db049b9`'s in-repo diff only touches `HANDOVER.md`, and the "REBUILD.md build flags" it names
were fixed in the off-box copy that no reviewer on the range can inspect. My catch-up summary
called that commit "REBUILD.md corrections and an off-box vault archive" as if the REBUILD half
were checkable from the range. It wasn't. Correction stands.

**Nuance 2 — CLAUDE.md +78 lines over three commits. I missed it entirely.** This is the load-
bearing rules file for the whole project. Adding 78 lines across the range and not noticing is
the same failure class the review was launched to prevent — a doc that says what the standard
is drifted while I was measuring code against it. The commits that touched it are in the range
between `3b2c3fe` and `df1d862`; I should have caught this on the first `git log --stat`.

**Nuance 3 — yocto/ (48 files) and scripts/build-deb.sh / build-apt-repo.sh are untracked.**
I saw `yocto/` in `git status` and called it "in scope for the broader project per your
instructions." That undersold it. Forty-eight untracked files across `meta-symoneural-core`,
`-darwin`, `-python`, `-quail`, `-mingw`, `-aws` is a lot of unreviewed material, and calling
it "activity" in a progress narrative is not the same as auditing it. Nothing about those
files has gone through the handshake standard yet.

## §2 — Where the review was wrong

**Point 1 — my own REVIEW-LOG.md still lies about the deploy list.** The coder is right.
Lines 54-61 of REVIEW-LOG.md (the "COMPLETE" version I signed and committed) say *"Still
Garrett's alone, **both** non-agent"* and list two commands. The correct list is three, and
`8a050c2` fixed HANDOVER's row after the outage but did not go back to REVIEW-LOG.md. I closed
the review with a document that reproduces the exact defect the review was launched to
prevent, and it's still uncorrected. **This is item 1 on the next work list.**

**Point 2 — SWEEP-READY A1 landed differently than specified, and I originally flagged that as
still-open before catching up.** True. My tick-4 pass said *"grep for `len(registry.TOOLS)`
returns nothing"* and marked it OPEN. The coder's actual solution — `EXPECTED_TOOLS` per module
plus `EXPECTED_GROUPS` per group, membership sets rather than a count — is stronger than what
SWEEP-READY prescribed. My subsequent tick-5 pass reconciled this correctly, but a reader
grepping the sweep file's literal text against the tree will still read A1 as unfixed.
`SWEEP-READY.md` A1 needs a "landed as follows" note pointing at the two real test functions.

**Point 3 — the coder's own claim was stale and it's correcting itself, not me.** The coder
had been saying prod was serving a stale CSS. Not true anymore — Garrett deployed at 16:22 and
`/var/www/symoneural/symoneural.css` is byte-identical to `site/`. Recording it because a
correction of your own written statement, in your own words, is exactly the discipline the
whole review is about. Full credit.

## §3 — What is still open

**One live wrong claim in production.** `site/documentation.html` diverges from
`/var/www/symoneural/documentation.html` on 18 non-cachebust lines. The deployed page still
prints `$ symoneural residency` (the pre-rename CLI command) with figures that are stale (free
15.4 GiB, tiers "1.5b, 7b", 107×). Needs `sudo scripts/deploy.sh --prune`. **Garrett only.**

**Mid-flight in the coder's session, not yet committed:**
- `symoneural-cli upgrade` — a new subcommand to make the CLI self-update from the vault
- `bitbake -p` parse over the 48 new yocto files — nothing has parsed them yet, and until
  bitbake accepts them the recipes are shaped-like-recipes rather than proven-to-be-recipes
- `docs/upgrading.md` — the operator-facing document that names the vault path and the flow

**Garrett only, that isn't a deploy:**
- **Secret rotation.** `backend/apps/remix/.env` is TRACKED and contains
  `SPOTIFY_CLIENT_SECRET`, `VLLM_API_KEY`, `DJ_TOKEN`. It is in a cloud tarball that carries
  `.git`. If that tarball is anywhere untrusted, those three secrets are out. **This is a
  real exposure and rotating them is not an agent action.** Nothing to fix in code; the
  secrets are already gone from the moment the tarball was made.
- Node ≥22 upgrade

## §4 — Suite

**1085 passed, 0 failed, 110.21 s at `df1d862`**, measured by the coder just now from
`backend/` with the two mandatory `--ignore`s. `--collect-only` collects the same 1085 in
0.83 s. Prior reading was 1085 at `5e68ea3`, so **+0 across all fourteen commits**. Interesting
signal: none of the last 14 commits added a test, which is a gap the audit surface will need
to address for the code that did land (`773709a`'s 981-line CLI, the CSS rack fix, and the
HANDOVER paragraphs).

**The other three suites (frontend.mjs, tuner_failpaths, tuner_watch, studio.mjs) were NOT run
at HEAD.** The 43/43 reading is stamped `8b557ac`, but `site/documentation.html` has changed
16 lines since that commit (the prod-drift finding above), and `tests/frontend.mjs` asserts on
that page at lines 736 and 854. So the 43/43 does not carry to HEAD. Needs re-run.

---

## The first next task

Draft below, ready to paste. Format is: one deliverable, defined stopping point, no
open-ended "keep going." Widening is deliberate — two adjacent files per task, so the audit
surface grows without runaway scope.

```
An external reviewer (same one as CODER-STATE-2026-08-19.md) has read your report and
reconciled. Verdict is in /home/google/Symoneural/RECONCILE-2026-08-19.md — read it first.

Operating standard from here forward (Garrett's answer):
- Every commit meets the expert-handshake-tested-verified bar
- Every claim in prose cites the code line that produces the behaviour
- Every code change has a regression test that mutation-fails without it, OR a comment
  explaining why one is not warranted
- Every figure in docs is anchored to the SHA it was measured on
- If you and the reviewer disagree, the reviewer challenges with file:line; you respond
  with evidence; we converge on what is true; the correction goes in the next commit
- `references/` is Garrett's workshop and is out of audit scope
- Anything you didn't add is labelled NOT MINE and skipped for Garrett's review
- No git push; do not touch training/corpus.jsonl, training/build_dataset.py, or
  training/adapter/ — trade-secret artifacts protected by not-being-public

First task — one deliverable, then stop:

Enumerate the top 15 places in the repo where the standard above is currently violated,
in priority order, and write them to /home/google/Symoneural/AUDIT-SURFACE-2026-08-19.md.

For each finding: file, line, what specifically fails (comment claims behaviour code
doesn't produce / figure without SHA / function without regression test / decorative
status LED / stale claim / other), and one sentence naming the fix shape (not the fix
itself — that comes later). Rank by (a) is it live-wrong or safe-wrong, and (b) how many
other things depend on this being true.

Include the four items the reconcile already surfaced:
1. REVIEW-LOG.md:54-61 says "both non-agent" for a three-command deploy list
2. SWEEP-READY.md A1 needs a "landed as follows" note
3. Something in .claude/CLAUDE.md that changed +78 lines and my summary missed —
   name the specific claim you added that the reviewer should have caught
4. yocto/ has 48 untracked files with no bitbake -p parse — pick one file that most
   embodies "shaped-like-a-recipe but never proven a recipe" as the entry point

Exclude references/ entirely. For anything you cannot attribute to yourself, mark it
"NOT MINE — LIKELY GARRETT'S" with the file path and skip.

Stop after writing the file. Do not start fixing anything from the list. The reviewer
reads the surface, ranks with you, then hands the top item back as its own narrow
task.

Save as /home/google/Symoneural/AUDIT-SURFACE-2026-08-19.md and stop.
```
