# Recovered 2026-09-11

Taken by path from `experiment/native-hybrid-gpu-player` (tip `44863110`, also tipped by
`research/custom-runtime-freeze-20260824` — two branch names, one pair of commits), where it
had sat unmerged since **2026-08-24**.

**By path, not merged**, for the same reason `capacity-lab/` was: those two commits also touch
`backend/apps/dispatchos/` and `test_control_plane_matrix.py`, which `main` has moved past.
Merging would have quietly reverted them.

## How it was nearly lost

The repo-disposition pass (Q3) asked whether the unmerged branches carried anything not already
present, superseded or dead. It found two things — the authority-plane spec and `capacity-lab/`
— and **missed this one**, because it checked a handful of distinctive paths rather than the
full file-level diff against `main`. Both branches were then described as "adds `capacity-lab/`",
which was true and incomplete.

It surfaced only when the branches were about to be deleted and every file on each was compared
against `main` one at a time. **The lesson is the same one `control/` taught an hour earlier:
the check has to be exhaustive, not representative.**

## What it is, and what it is not

Four files, **stdlib only** — no dependency to install, and `verify` deliberately does not
import torch, because trust checking must not itself create a CUDA context.

Its own gate, quoted from `--help`:

> *"`inventory`, `verify` and `test --dry` are real and read-only. `stage`, `promote` and
> `rollback` deliberately refuse to act and print the plan they WOULD execute, because nothing
> in this system promotes itself. Absolutely nothing here installs, signs, loads, unloads or
> replaces anything. There is no modprobe, no rmmod, no dkms build, no initramfs write, no
> package manager call, and no bootloader touch."*

## Verified on recovery, by running it

`inventory` read the live box correctly — kernel `6.12.107+deb13-amd64`, NVIDIA open kernel
module **615.71.09**, which matches the driver this box was upgraded to on 2026-09-09.

`promote` refused, and printed the plan it would have run:

```
REFUSED: `promote` does not act in the scaffold gate.
Nothing promotes itself. The plan it would execute, for review:
  1. require verify(CANDIDATE) == TRUSTED
  2. require all execution checks PASS
  3. copy the current PRIMARY slot into RECOVERY
  4. install + sign the candidate modules, rebuild initramfs
```

So the safety gate is real and exercised, not merely documented.

## Not done here

Nothing in `ops/RUNTIMES.tsv`, `restore/manifests/` or any unit references this yet. It is
recovered source, not a wired component — and wiring it would mean deciding whether a tool that
can (in a later gate) rebuild an initramfs belongs in the restore path at all. That is an owner
decision with `BLAST=boot` written on it.
