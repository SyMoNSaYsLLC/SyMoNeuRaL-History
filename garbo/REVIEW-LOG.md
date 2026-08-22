# REVIEW-LOG — external verification of the CLOSEOUT-2026-08-19 punch list

**COMPLETE — closed 2026-08-19 11:39 UTC.**

Range: `48fc731..3b2c3fe`, twenty-two commits. Suite: **1085 passed, 0 failed**, measured at
`5e68ea3` and recorded at `HANDOVER.md:1062` with method, wall-time range, `--collect-only`
cross-check, per-app breakdown (studio + exp = 141 = 63 + 78), and previous reading for
contrast.

---

## The last commit is worth reading

`3b2c3fe`: *"docs: replace every published test number with a reading taken today"*.

Not a "bump 1063 to 1085" edit — a re-audit of every pytest figure in the state document.
Along the way the coder:

- Anchored the new reading to the SHA it was measured on (`5e68ea3`).
- Reported wall time as a **range** — 110.38 s and 111.55 s from two runs on the same tree —
  "the count is the reading, the wall time is a range, and quoting one second-precision figure
  as *the* runtime is how the last one went stale."
- Checked the collect-only count separately (1085 in both runs).
- Investigated why the delta from 1063 was **+22** when the source diff added only **+1**
  test. Checked out `0f247cd` in a detached worktree and measured: it actually collected
  **1084**, not 1063. So the real HEAD-to-HEAD movement is **1084 → 1085, +1**, matching the
  source diff. Conclusion: *"1063 was never true of the tree it was written beside."*
- Then rewrote every test-count claim elsewhere in the document, because the same failure
  mode had produced other stale numbers.

That is the discipline of this review reproduced in one commit — verify by measurement, not
inference; publish the number with its provenance; when the numbers don't add up, chase down
the reason before writing.

---

## Everything closed

- CLOSEOUT-2026-08-19.md §1 (twelve correctness bugs)
- CLOSEOUT-2026-08-19.md §2 (rack count in three documents)
- CLOSEOUT-2026-08-19.md §3 (comment sweep, both apps)
- CLOSEOUT-2026-08-19.md §4 (lower-priority defects — coder went further than the list)
- CLOSEOUT-2026-08-19.md §5 (six security-boundary misdescriptions — coder opened this one)
- CLOSEOUT-2026-08-19.md §6 (build_studio destamp warning + test)
- CLOSEOUT-2026-08-19.md §8 (pytest run recorded with method)
- SWEEP-READY.md Part A (all twelve items)
- SWEEP-READY.md Part B (all eighteen items)
- REVIEW-LOG.md N1, N2, N3 (retracted), N4

**Nothing is open.**

---

## Still Garrett's alone (updated 2026-08-19 23:45 UTC after the coder found the missing third)

Order matters — `deploy.sh` first, THEN `install-gateway.sh`, THEN `install-caddy.sh`:

```bash
sudo scripts/deploy.sh --prune            # /var/www/symoneural/ static content
sudo ./scripts/install-gateway.sh         # symon-gateway on :8000 — WITHOUT THIS, install-caddy TAKES /api DOWN
sudo ./scripts/install-caddy.sh           # the @studio and @exp delegation blocks
```

**Correction record:** this row previously said "both non-agent" for a two-command list and put
`install-caddy.sh` second. That list was wrong — the Caddyfile routes `/api/*` to `:8000`
(symon-gateway), not `:8800` (the API), and the gateway had never been installed. When Garrett
ran the two-command version at 2026-08-19 08:03 EDT, every `/api` path returned 502 for the
window between installs. Fixed in commit `8a050c2` in HANDOVER but not here until now. The
review closed with the same defect the review was launched to prevent, which is worth naming
plainly rather than quietly patching.

The API restart already happened at 05:22:39 EDT. All three deploys have since run — the
outage was resolved at 08:03 EDT the same day per `8ecd842`.

---

## For the reader-of-record

`SWEEP-READY.md`, `REVIEW-LOG.md`, `CLOSEOUT-2026-08-19.md` and the pasted transcript are
session state and were not committed. They can stay in the working tree or be deleted; the
history is entirely in `git log 48fc731..HEAD`.
