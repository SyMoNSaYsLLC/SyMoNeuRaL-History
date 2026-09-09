# `backend/vendor` classification — measured 2026-09-09

Required by the storage reorganisation spec, section 1.8: *"It is large (~16k tree entries).
Do not move/delete until actual imports/runtime dependency are measured. Classify every
major vendor subtree."*

## The headline: it is 131M, and nothing imports it

The spec expected an ambiguous multi-gigabyte tree. Measured, `backend/vendor` is **131M**
in two subtrees holding ten public SDK source repositories. The import measurement is the
part that decides its fate, and it is unambiguous:

* **No `__init__.py` exists** at `backend/vendor/`, `backend/vendor/openai/` or
  `backend/vendor/anthropics/`. The tree is not a Python package, so `import` cannot reach
  it regardless of `sys.path`.
* **Nothing manipulates `sys.path` or `PYTHONPATH` to add it** — grepped across
  `backend/*.py` and `backend/apps/*.py`.
* The only `grep -rn vendor` hit in first-party Python is
  `backend/apps/cryptominer/__init__.py:22`, and it is prose about not projecting figures
  "from vendor figures" — a false positive, not an import.
* `scripts/build-deb.sh` already excludes it from the shipped package via
  `NONPROD_RE='^(backend/vendor/|...)'`, annotated *"adopted SDK/reference source; no
  serving module imports it"*.

Four independent measurements, one conclusion.

## Classification — every subtree, no `UNKNOWN`

Section 1.8's vocabulary is `RUNTIME_REQUIRED_LOCAL`, `BUILD_ONLY_REACQUIRABLE`,
`REFERENCE_ONLY`, `UNKNOWN`.

| Subtree | Version pin | Size | Files | Licence | Class |
|---|---|---|---|---|---|
| `anthropics/anthropic-sdk-java` | 2.57.0 | 39M | 2927 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-csharp` | 12.42.0 | 27M | 2734 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-ruby` | 1.65.0 | 21M | 3827 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-php` | 0.43.0 | 15M | 2231 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-python` | 1.0.0 | 12M | 1495 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-go` | 1.66.0 | 6.5M | 332 | permissive | `REFERENCE_ONLY` |
| `openai/apps-sdk-ui` | 0.2.2 | 5.8M | 1059 | permissive | `REFERENCE_ONLY` |
| `anthropics/anthropic-sdk-typescript` | 0.120.0 | 5.6M | 468 | permissive | `REFERENCE_ONLY` |
| `anthropics/claude-agent-sdk-python` | 0.2.143 | 2.2M | 144 | MIT | `REFERENCE_ONLY` |
| `anthropics/agent-sdk-workshop` | **UNPINNED** | 536K | 73 | Apache-2.0 | `REFERENCE_ONLY` |

```
RUNTIME_REQUIRED_LOCAL   = 0 bytes
BUILD_ONLY_REACQUIRABLE  = 0 bytes
REFERENCE_ONLY           = 131M  (all ten subtrees)
UNKNOWN                  = 0 bytes
```

`UNKNOWN=0`, which section 7.10 requires.

## What this does NOT license

These are the **public, permissively licensed SDK repositories** published on GitHub. They
are not the proprietary Claude executable or proprietary Claude Code source, and nothing
here permits copying, decompiling, relabelling or relicensing that. A permissive licence on
a published SDK is a grant from its copyright holders covering that SDK only.

Retaining a permissive notice is also not the same as authorship: none of this becomes
first-party by being stored in a first-party repository.

## Reacquisition, not custody — and the one gap

Nine of the ten carry a version pin, so they can be refetched from their public upstream at
the recorded version. **`agent-sdk-workshop` has no version of any kind** — no
`package.json` version, no `pyproject.toml`, no changelog. None of the ten contains a
`.git`, so no subtree can be pinned by revision.

That gap is why the snapshot is taken rather than the tree simply deleted: an unpinned
reference cannot be reacquired reliably, and "reacquirable" without a pin is an assertion
rather than a plan.

## Disposition, and why it is deliberately NOT executed with the storage moves

Section 7.4 routes reference vendor material to Drive. But **15,297 of these files are
git-tracked**, so retiring the tree is a repository commit that changes the source of
truth — not a storage move like the untracked `archive/` bulk.

Section 11 requires that repository closure happen once, in order: final commit, regenerate
restore manifests, focused tests, full suite if behaviour changed, `git fsck --full`, then a
single bundle regeneration — and explicitly *"do not regenerate the Git bundle after every
cleanup commit"*.

So this classification is recorded now and the removal is batched into that single
repository-change pass. Executing it mid-transfer would force a bundle regeneration this
spec forbids, to reclaim 131M — 0.04% of the ~295 GB actually in flight.
