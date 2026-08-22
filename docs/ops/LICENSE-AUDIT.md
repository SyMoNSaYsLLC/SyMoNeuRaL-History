# SyMoNeuRaL Licence + Provenance Upgrade — the audit, and what is already done

**Opened 2026-08-22.** Docs only. **No distribution change, no dependency added or removed, no
licence text edited by this document.**

**Classification: PROD direction — required before commercial distribution. AUDIT until
complete.**

## This is a gap analysis, not a second licence file

**`LICENSES.md` is the authority** and it is already substantial — nine sections, including §8
*"Obligations by licence, in one place"* and §9 *"Checklist for a customer build"*. A second file
restating its verdicts would drift from it on the first dependency change, which is the failure
`.claude/CLAUDE.md`'s first *never* exists to prevent.

So this file holds **status, gaps and the promotion path**. Verdicts stay in `LICENSES.md`.

| Question | File |
|---|---|
| what is the licence of a shipped thing? | **`LICENSES.md`** |
| what may leave this box? | **`docs/ops/EXPORTS.md`** |
| which weight came from where? | **`backend/models/PROVENANCE.json`** (+ `NAMES.md`) |
| per-model licence status | `docs/ops/MODEL-LICENSES.md` |
| Yocto layers and recipes | `docs/ops/YOCTO-LAYER-LICENSES.md` |
| SBOM plan | `docs/ops/SBOM.md` |
| provenance plan | `docs/ops/PROVENANCE.md` |
| what is the audit state? | **this file** |

## Licence status vocabulary

`first-party` · `permissive-ok` · `copyleft-ok-with-obligations` · `source-offer-required` ·
`notice-required` · `attribution-required` · `no-commercial-use` · `redistribution-restricted` ·
`proprietary-reference-only` · `unknown-blocked` · `removed`

**`unknown` is `unknown-blocked`.** An unrecorded licence is not a small gap — it is a blocker
until provenance exists, because you cannot ship what you cannot describe.

## What is already true — measured 2026-08-22

- **`LICENSES.md` exists** with the nine sections above, and it carries the decision rule at the
  top rather than only a table.
- **`backend/models/PROVENANCE.json` exists** — `{schema, note, weights}` — and is **tracked
  deliberately**: `.gitignore` re-includes it through the `backend/models/*` exclusion because *the
  weights are fetched, so if the manifest is not in git it is not anywhere.*
- **`backend/models/NAMES.md` is tracked as a licence obligation, not documentation.** `.gitignore`
  says it plainly: Apache-2.0 and MIT let us rename what we redistribute and **do not** let us drop
  the notice, so *"untracking it is the one way to lose the notice without deleting it."*
- **Two items are already retired from distribution**, and recorded as retired rather than deleted:
  Swagger UI 5.17.14 (Apache-2.0, retired 2026-08-21) and **ComfyUI (GPL-3.0)** — the latter being
  the one that would otherwise put a copyleft tree inside a repo whose `LICENSES.md` says nothing
  shipped is copyleft.
- **NVIDIA CUDA is named as "the one genuinely restrictive item"** (§6), which is the right posture
  for the component most likely to be waved through.
- **No archive is tracked anywhere.** `git ls-files | grep -E '\.(tar\.gz|tgz|zip)$'` returns
  nothing, and `/references` is excluded wholesale.
- **`yocto/oematch/` is the licence-detection tool** #97 depends on, and #97 fixed two real defects
  in how it was used — see §Findings.

## Gaps — the reason this is AUDIT

| Gap | State |
|---|---|
| **`NOTICE.md`** | **does not exist** |
| **`THIRD-PARTY-NOTICES.md`** | **does not exist** |
| generated third-party notices | not generated; §8 of `LICENSES.md` is hand-maintained |
| SBOM | none produced. `docs/ops/SBOM.md` is the plan |
| SLSA-style build provenance | not started |
| per-model licence status table | `docs/ops/MODEL-LICENSES.md`, opened, incomplete |
| Yocto licence manifest / SPDX output | **cannot exist yet** — see `YOCTO-LAYER-LICENSES.md`: no image has ever been built |
| source-offer obligations | recorded in `LICENSES.md` §8; **no offer mechanism exists** |

**`LICENSES.md` §8 and §9 already carry the obligations and a customer-build checklist**, so the
gap is machinery and artefacts, not knowledge. That is the honest framing: the thinking is done,
the generated evidence is not.

## Findings

### LA-1 — `AUDIT.md` Q1's premise is stale; the recipe was already fixed

**Q1 asks what licence `symoneural-stack` carries, on the stated basis that the recipe *"declares
`LICENSE = "CLOSED"`"*.** It no longer does. Measured at
`yocto/meta-symoneural-core/recipes-symoneural/symoneural/symoneural-stack_git.bb:7-9`:

```
LICENSE = "LicenseRef-symoneural-stack-CLOSED"
LIC_FILES_CHKSUM = "file://LICENSES.md;md5=016512c94fb7b74a60da5fb6e40337be"
NO_GENERIC_LICENSE[LicenseRef-symoneural-stack-CLOSED] = "LICENSES.md"
```

Changed in **`97b92770`**, and the recipe's own comment explains it: the bare `CLOSED` *"used to
say the same thing and warned as deprecated"*, so this is the `LicenseRef-` form the warning asked
for, `NO_GENERIC_LICENSE` points the ref at the file in this tree, and **`LIC_FILES_CHKSUM` carries
that file's real md5 so the build stops if the terms change.**

**That is Q1 option (a), already implemented.** What may still stand is Q1's second half — whether
this contradicts the claim that the stack is *"off-the-shelf and permissively licensed"*, a
sentence that has since moved out of `.claude/CLAUDE.md` into `docs/ENGINEERING.md` under R-180.
**Recorded on Q1 in `AUDIT.md` rather than answered here** — the question is Garrett's, but it
should not be answered against a premise that has changed.

### LA-2 — the reference archives are third-party source, and one is proprietary

`@symoneural code.tar.gz` was **inspected** (listing only) and contains **no first-party code**:
3,598 entries across eleven Anthropic projects. Licence readings taken from inside the archive:

- **`claude-code` — `© Anthropic PBC. All rights reserved.`**, use subject to Anthropic's
  Commercial Terms of Service. Status: **`proprietary-reference-only`.**
- **`anthropic-sdk-python` — MIT.** Status: `permissive-ok` *legally*, and **still not vendored** —
  `references/` is untracked on purpose and `LICENSES.md` governs what ships.
- the remaining nine each carry a `LICENSE` file; **not individually read.** Status:
  `unknown-blocked` until they are, which costs nothing because none is imported.

**Behaviour may be reimplemented. Source may not be copied.** Full reading:
`docs/specs/symoneural-coder-project-cli-scope.md` §1, §5.

The other four archives are **unopened** and therefore `unknown-blocked`:
`simpy.tar.gz` (3.8 MiB) · `symoneural streamer.tar.gz` (271 MiB) · `miner.tar.gz` (**ambiguous —
two files match**) · `oematch.tar.gz` (16 KiB).

### LA-3 — `NOTICE.md` and `THIRD-PARTY-NOTICES.md` are missing, and one obligation depends on them

`LICENSES.md` §8 records notice and attribution obligations, but **there is no notice artefact to
ship.** For a repo that currently distributes little this is latent; **for a customer build or an
appliance it is a blocker**, because a notice obligation is discharged by delivering the notice, not
by having written down that one is owed.

`NAMES.md`'s existence shows the pattern is understood — it exists *because* renaming a
redistributed weight does not remove the attribution duty.

### LA-4 — no SBOM, and no build provenance

Neither exists. Both are prerequisites for `docs/specs/symoneural-trust-report.md` and for
`docs/specs/symoneural-appliance.md`, which is why those are FUTURE rather than scheduled.

## Inventory areas, and where each stands

| Area | Where | State |
|---|---|---|
| **A. repo code** | `LICENSES.md` §7 *"What is ours"* | recorded |
| **B. models/weights** | §2 + `PROVENANCE.json` + `MODEL-LICENSES.md` | partly; per-model status table incomplete |
| **C. engines/runtimes** | §3, §5, §6 | recorded; `RUNTIME-PROFILES.md` carries maturity |
| **D. frontend/static** | §1 | recorded; two items retired |
| **E. reference archives** | LA-2 | one inspected, four unopened |

**Per-model fields required** before any model is called ready or commercial: model id · source ·
licence · provenance · local path · **redistribution allowed?** · **commercial use allowed?** ·
**modification allowed?** · **output restrictions?** · attribution required? · gated access?

**An unknown licence blocks that model**, and blocks the build that includes it.

## Promotion path — what closes this audit

| To claim | Proof |
|---|---|
| "licence clean" | every shipped dependency, source, model and runtime has a status from the vocabulary above — **and none is `unknown-blocked`** |
| notices discharged | `NOTICE.md` and `THIRD-PARTY-NOTICES.md` exist **and are generated**, not hand-typed |
| model licences recorded | `MODEL-LICENSES.md` complete, cross-checked against `PROVENANCE.json` |
| Yocto ready | `YOCTO-LAYER-LICENSES.md` complete **and a licence manifest produced by a real build** |
| SBOM | an SBOM artefact exists for a specific commit |
| source-offer satisfiable | a mechanism exists, not only a recorded obligation |

**No "licence clean" claim until the audit completes.** And per `EXPORTS.md`, nothing leaves the
box on this document's authority.

## Not authorized

No dependency added or removed · no licence text edited · no notice file generated · no model
downloaded · no archive imported · no distribution or deploy · no Yocto build.
