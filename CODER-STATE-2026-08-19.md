# CODER-STATE — 2026-08-19

## 1. What I have been doing

Your summary of `3b2c3fe..HEAD` (14 commits, HEAD `df1d862`) is accurate on subject matter.
Three nuances. `REBUILD.md` is **not tracked** — it lives at
`/home/google/.symoneural-full/REBUILD.md` (mode 600, off-box vault), so `db049b9` edits
`HANDOVER.md` only and you cannot verify the flag fix from the range. Your six-item list omits
the range's largest documentation change: **`.claude/CLAUDE.md`, +78 lines over three
commits** — the rules file moved under you, so read it before rewriting either document. And
the range **ends before this session's work**: `yocto/` (48 files, the `meta-symoneural-*`
family) and `scripts/build-{deb,apt-repo}.sh` are untracked and unreviewed.

## 2. Where the review was wrong

- **`REVIEW-LOG.md:54-61` carries the same defect you found in HANDOVER.** "Still Garrett's
  alone, **both** non-agent" lists two commands; `scripts/install-gateway.sh` exists and was
  the third. `8a050c2` fixed HANDOVER's row, not this one.
- **`SWEEP-READY.md` A1 was applied in substance, not verbatim.** Neither the specified
  `test_the_registry_has_every_tool_every_module_defines` nor a literal `26` is present. It
  landed as `test_studio.py:89` + `:121`, comparing per-module and per-group **membership
  sets** rather than a count. Stronger than specified; a grep reopens it wrongly.
- **My own claim went stale, and it was mine, not yours.** I said production served a
  145,795-byte CSS with no `160ch` rule. False — Garrett deployed at 16:22.
  `/var/www/symoneural/symoneural.css` is byte-identical to `site/` (148,593, 3× `160ch`).

## 3. Open

- **Live wrong claim.** `documentation.html` is the *only* remaining webroot drift (18
  non-cachebust diff lines) and substantive: the deployed page prints
  `$ symoneural residency` — the pre-rename command — with stale figures (free 15.4 GiB,
  tiers "1.5b, 7b", 107×). Needs `sudo scripts/deploy.sh --prune`.
- **`/opt/node22` does not exist.** Node is v20.19.2; `@anthropic-ai` is at
  `/home/google/.npm-global/lib/node_modules/`.
- Mid-flight: `symoneural-cli upgrade`, a real `bitbake -p` parse (nothing has parsed those 48
  files), `docs/upgrading.md`.

**Garrett only:** the deploy above; rotating `SPOTIFY_CLIENT_SECRET`, `VLLM_API_KEY`,
`DJ_TOKEN` (tracked in `backend/apps/remix/.env`, already in a cloud tarball carrying `.git`);
the node ≥22 upgrade.

## 4. Suite

**1085 passed, 0 failed, 110.21 s at `df1d862`**, measured just now from `backend/` with the
two mandatory `--ignore`s; `--collect-only` collects the same **1085** in 0.83 s. Prior
reading was 1085 at `5e68ea3`, so +0 across fourteen commits. Tree dirty with the untracked
files above; none affect collection.

The other three suites were **not** run at HEAD. The 43/43 does not carry: stamped
`8b557ac`, and `site/documentation.html` changed 16 lines since — a page that suite asserts
on (`tests/frontend.mjs:736`, `:854`).
