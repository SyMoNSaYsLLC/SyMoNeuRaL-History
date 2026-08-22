# SyMoNeuRaL export policy — what may leave this box, and how

Written 2026-08-22 (R-180, Phase 0.6b), from the #75 finding the same day: every whole-repo
zip shared for review carried `training/corpus.jsonl` (the 327 hand-authored examples) and
`training/build_dataset.py`, because both are tracked and the zips were built from tracked
files. Trade secret exists only while reasonable measures keep it in.

## The rules

1. **No whole-repo zip exports, ever.** Not for review, not for backup, not "just this once".
   History never leaves this box; there is no git remote, and that is a protection, not a gap.
2. **The protected artefacts** (full reasoning in `docs/ENGINEERING.md`, trade-secret
   section): `training/corpus.jsonl`, `training/build_dataset.py`, `training/adapter/`
   weights. Never in an export, never served, never quoted into a page or commit message.
3. **Also excluded from any export:** the mode-600 ledgers (`GARRETT-REQUESTS.md`,
   `INTAKE.md`), anything under `review/`, `.env` files, tokens, `run/`, session transcripts.
4. **The only sanctioned path** is `tools/export_snapshot.sh` — Phase 1 work, specified in
   `docs/specs/scope-of-work-2026-08-22.md` — which excludes the above, writes an
   EXPORT-MANIFEST naming the source SHA, and FAILS if a protected path is present.

## The acceptance check, until the script exists

```bash
unzip -l export.zip | grep -E 'corpus\.jsonl|build_dataset\.py|GARRETT-REQUESTS|INTAKE\.md|\.env' \
  && echo "UNSAFE — do not send" || echo "safe export"
```
