# `restore/` — the control plane

This directory answers one question: **after reinstalling Linux, how does SyMoNeuRaL come
back?**

Not "where are the files" — Git answers that. The things that do not survive a reinstall are
the decisions: which upstream revision an engine forks from, which of seven Python
environments a component runs in, which database cannot be copied with `cp`, which systemd
unit is deliberately disabled and which is merely stale, and what order any of it happens
in. Those lived in commit messages and in the owner's head. They are here now.

If you are restoring from bare metal, read **[`../RESTORE-FROM-BARE-METAL.md`](../RESTORE-FROM-BARE-METAL.md)**, which
is the step-by-step. This file explains how the machinery works so you can trust it.

---

## The one program

```bash
restore/symoneural-restore inventory          # what exists and what class it is
restore/symoneural-restore verify             # is the plan internally coherent
restore/symoneural-restore dependencies --check
restore/symoneural-restore dependencies --instructions
restore/symoneural-restore build   <component|all>  [--apply]
restore/symoneural-restore test    <component|all>  [--apply]
restore/symoneural-restore install <component|all>  [--apply]
restore/symoneural-restore restore-state --dry-run | --apply
restore/symoneural-restore services --check | --install [--apply]
restore/symoneural-restore smoke   <application|all> [--apply] [--allow-mutating]
restore/symoneural-restore status             # the release gate figures
```

It uses the **standard library only**. It has to run on a machine where nothing has been
installed yet — including, necessarily, before the thing that installs the dependencies has
run. Importing a third-party package here would make the bootstrapper depend on the
bootstrap.

**Everything that can change the machine is dry by default** and prints the exact command it
would run. `--apply` is the only way to make anything happen. The privileged steps go
further and refuse to run themselves: `services --install` prints a root command for a human
to execute rather than calling `sudo` on its own authority. A restore tool that silently
escalates is one nobody can audit before running, and these commands write systemd units.

It **refuses rather than guesses**. An unknown component id is an error, not an empty
selection. A missing manifest is an error, not an empty result. The failure this is written
against is a tool that returns `0` having done nothing, on a machine where the operator
cannot tell the difference.

---

## Where the facts come from

```
restore/lib/registry.py   ─┐
   judgements                │
                             ├──►  tools/build_restore_manifests.py  ──►  restore/manifests/*.tsv
restore/lib/measure.py    ─┘                                              restore/RELEASE.json
   measurements                                                           FIRST-PARTY-CLOSURE.tsv
                                                                          THIRD-PARTY-REBUILD-MANIFEST.tsv
```

**The manifests are generated. Do not hand-edit them.** Edit `registry.py` and regenerate.

The split is deliberate. Half of each row is something no measurement can decide — *is this
component production, is this implementation ours, may this external tree be omitted from
the backup* — and that half lives in `registry.py` where a human can argue with it. The
other half is read off the disk at generation time: file counts, revisions, checksums,
whether a binary a recipe promises is actually where the recipe says.

This repository has published a test count that was never true of the commit beside it,
reported a service as disabled off a table row while the unit file said enabled, and
recorded an engine as unbuilt because a probe looked in the wrong directory. Each was the
same failure — acting on a row rather than on the thing. So everything measurable is
measured, every time, and a measurement that cannot be taken returns a string saying so
rather than a plausible default.

### The manifests

| File | What it settles |
|---|---|
| `COMPONENTS.tsv` | every restorable unit, its class, and whether it is production |
| `APPLICATIONS.tsv` | each user-facing surface → its runtime, engines, state and smoke |
| `SOURCE-CLOSURE.tsv` | is each component buildable, and from what |
| `BUILD-RECIPES.tsv` | literal prep/build/test/install commands and toolchain versions |
| `ARTIFACTS.tsv` | every built binary, its checksum, architecture and link table |
| `SERVICES.tsv` | units: designed enablement vs **measured**, and installed-vs-template |
| `DEPENDENCIES.tsv` | platform, toolchain and 196 Python distributions with licences |
| `PERSISTENT-STATE.tsv` | what Git cannot restore, and how to take it consistently |
| `RESTORE-ORDER.tsv` | the dependency-ordered sequence, with failure policy per step |
| `SMOKES.tsv` | one real exercise per production application |
| `../FIRST-PARTY-CLOSURE.tsv` | implementation class per component; is external source omittable |
| `../THIRD-PARTY-REBUILD-MANIFEST.tsv` | the upstream pins that replace 149 GB of source |

`restore/locks/` holds one pinned dependency lock per Python environment — 594 pins across
seven. There is deliberately no single `requirements.txt`: the API runs on the Debian system
interpreter with no virtualenv, and six applications have their own. Pretending there is one
environment would make the file wrong.

---

## The thing most worth understanding

**`external/` is 149 GB and is not in the backup, but three production engines are built out
of it.** That is not a contradiction and it is not hidden.

`tools/fork_engines.sh` builds `symoneural-llm`, `symoneural-diffuse` and `symoneural-listen`
from upstream source in `external/referencestochatgpt/`. It is a real, load-bearing
build-time dependency. Claiming otherwise to make a gate go green would be a lie the next
restore would discover.

What makes the tree omittable is that every one of those checkouts is a **clean clone of a
public remote at a pinned revision** — verified against the checkout while the checkout was
still there to verify against. So the dependency is on an *upstream*, which is reacquirable,
not on a *local directory*, which is not:

```bash
tools/restore-upstream.sh --check     # what is here, what is missing, at which revision
tools/restore-upstream.sh all         # fetch the three MIT engines at their exact pins
```

This was rehearsed, not assumed. A clone taken from the Git bundle alone — no `external/`,
no `.private/`, no working tree — reacquired `whisper.cpp` from GitHub at
`1fe009caeda75f69bc864d6370b10674e45a92bd` and rebuilt the engine from it.

`backend/apps/test_no_external_source_dependency.py` keeps this honest: no production
runtime may resolve a path into a tree that will not survive the reset, and it catches the
split form `ROOT / "external" / "contrib"` as well as the string form, because a substring
search once missed nine files spelled that way and the shims everyone believed were dead
turned out to be load-bearing.

### The exception

`kawpowminer` carries three uncommitted local modifications — including a real
`#include <cstdint>` fix for gcc 13+ no longer leaking `uint8_t` via `<cstring>`. A revision
pin cannot restore work that was never committed anywhere, so the patch is preserved at
`.private/upstream-patches/` and the manifest says the pin alone is not sufficient for that
one. `restore-upstream.sh` applies it and **fails loudly** if it is missing rather than
building something subtly different.

---

## What is deliberately not first-party

No component is called first-party because it was renamed. The classification is:

| Component | Class | Why |
|---|---|---|
| `symoneural-llm`, `-diffuse`, `-listen` | `THIRD_PARTY_DERIVATIVE_PERMISSIVE` | MIT forks. Our patches are ours; the upstream notice travels with the code. |
| `symoneural-miner`, `symoneural-ui` | `THIRD_PARTY_DERIVATIVE_COPYLEFT` | GPL-3.0. **DISABLED**, not relabelled — a licence is a grant from the copyright holders, not a string in a file. |
| `symoneural-miner-core` | `CLEAN_ROOM_FROM_PUBLIC_SPEC` | Keccak written from FIPS PUB 202, round constants *computed* from the standard's LFSR rather than pasted. Incomplete and says so. |
| `symoneural-adaptive-fabric` | `DECLARED_NOT_IMPLEMENTED` | README and LICENCE, no code. The plan must not appear to restore something that was never built. |
| the rest | `FIRST_PARTY` | ours |

`tools/fork_engines.sh` already refuses to stamp the SyMoNeuRaL licence on a copyleft
upstream. Nothing here may undo that refusal by writing a friendlier word in a column.

---

## Regenerating

```bash
python3 tools/build_restore_manifests.py     # then run it AGAIN and diff
python3 tools/build_dependency_locks.py      # or --check
cd backend && python3 -m pytest apps/test_restore_manifests.py \
                                apps/test_no_external_source_dependency.py -q
```

Run the generator twice and diff. Three separate generators in this repository have re-read
their own output and accumulated a copy per run, which is why two clean runs is the check
rather than a courtesy.

One consequence worth knowing: **a generated manifest can never name the commit that
contains it.** It records the revision it was generated from, and committing it produces a
new revision. The tests treat determinism and freshness as separate properties for exactly
this reason — the same impossibility that once had `BACKUP.json` carrying the hash of the
ZIP it was inside.

---

## `.private/` — what Git cannot hold

Not source. Recovery state, `0700` throughout with every file `0600`:

```
.private/application-state/<release>/   consistent SQLite images + env + ledgers
.private/source-bundles/<release>/      one tar.gz per first-party component
.private/runtime-artifacts/<release>/   built binaries as FALLBACK, never authority
.private/git-backup/                    Symoneural-all.bundle, all 31 refs
.private/host-snapshot/rootfs/          installed units and Caddy config
.private/upstream-patches/              edits a revision pin cannot restore
.private/claude-backups/                the owner's retirement backup (hard-linked)
```

Two rules that are easy to get wrong:

**A live SQLite database must not be copied byte-for-byte.** Two of these stores had a `-wal`
and `-shm` beside them when the backup was taken, meaning a writer was attached; a plain copy
mid-transaction produces a file that passes a checksum, restores without error, and is
corrupt. Every one goes through `sqlite3 .backup` and is then proved with
`PRAGMA integrity_check` — a backup that has not been opened is a hope.

**The preferred restore is always a rebuild.** `runtime-artifacts/` exists for the case where
that fails, and for comparing what you built against what ran. It is evidence, never source
authority.
