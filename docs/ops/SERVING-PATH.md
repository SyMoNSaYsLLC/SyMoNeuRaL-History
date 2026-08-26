# Serving path — canonical runtime under `/home/google/Symoneural`

**Migration completed 2026-08-26. Verified on the live box.** Supersedes the audit-only
version of this file.

The boundary and the machine baseline live in **`docs/ops/BUILD-BOUNDARY.md`**; this file is
the completion record — final paths, the coded path that produced them, and the evidence.

Classified with the Repo Update Audit System (`docs/ops/REPOSITORY-PURPOSE.md`): **PROD** =
proven working on this box · **AUDIT** = unverified or scaffold · **REMOVED** = wrong, dead,
or contradicted by the box.

---

## PROD — proven on this box

### Canonical paths, all live

| what | path |
|---|---|
| Repository / runtime root | `/home/google/Symoneural` |
| Models | `/home/google/Symoneural/backend/models` |
| Chat model | `/home/google/Symoneural/backend/models/llm/symon-1.0-7b-q4_k_m.gguf` |
| **Inference engine** | `/home/google/Symoneural/engines/symoneural-llm/build/bin/symoneural-llm` |
| Gateway | `/home/google/Symoneural/backend/apps/gateway/target/release/symon-gateway` |
| Deploy script | `/home/google/Symoneural/scripts/deploy.sh` |
| Webroot | `/var/www/symoneural` (unchanged) |

### Services

All three carry `WorkingDirectory=/home/google/Symoneural`, and **no enabled unit references
`/yocto` in any directive**:

    symoneural-api      ExecStart=/usr/bin/python3 /home/google/Symoneural/backend/api.py
    symoneural-gateway  ExecStart=/home/google/Symoneural/backend/apps/gateway/target/release/symon-gateway
    symoneural-deploy   ExecStart=/usr/bin/env bash /home/google/Symoneural/scripts/deploy.sh --prune
    caddy               unchanged — it never referenced /yocto

**A reboot cannot republish `/yocto` content**: `symoneural-deploy` is enabled and both its
`ExecStart` and `ConditionPathIsDirectory` name the canonical tree.

### Live processes — zero `/yocto`

| process | cwd | exe | fds | maps | env |
|---|---|---|---|---|---|
| `symoneural-api` | `/home/google/Symoneural` | `/usr/bin/python3.13` | 0 | 0 | 0 |
| `symoneural-gateway` | `/home/google/Symoneural` | canonical gateway binary | 0 | 0 | 0 |
| `symoneural-llm` (engine) | `/home/google/Symoneural` | canonical engine | 0 | 0 | 0 |

`PYTHONPATH` unset; no `.py` open from `/yocto`; no mount over the canonical tree; no symlink
under it pointing into `/yocto`.

### ELF artifacts

| artifact | interpreter | RPATH | RUNPATH | unresolved | `st_nlink` |
|---|---|---|---|---|---|
| gateway | `/lib64/ld-linux-x86-64.so.2` | none | none | 0 | 1 |
| engine | `/lib64/ld-linux-x86-64.so.2` | none | `…/engines/symoneural-llm/build/bin:` | 0 | 1 |

Neither resolves a library from `/yocto`. The engine's RUNPATH is inside the canonical tree.

### The engine on the GPU — no CPU fallback

    exe    /home/google/Symoneural/engines/symoneural-llm/build/bin/symoneural-llm
    argv   -m /home/google/Symoneural/backend/models/llm/symon-1.0-7b-q4_k_m.gguf
           -ngl 99 --host 127.0.0.1 --port 8081 -c 65536 --no-warmup -cb -np 2
           --lora /home/google/Symoneural/training/adapter/symoneural-lora.gguf
    VRAM   8330 MiB on the RTX 5070 Ti      GPU util 96%      178.39 W
    CUDA   libcuda.so.610.57.04  libcudart.so.13.3.29  libcublas.so.13.6.0.2  libcublasLt.so.13.6.0.2
    GGUF   canonical path mapped into the process

`-ngl 99` offloads every layer; the mapped CUDA libraries match the audited driver
(610.57.04) and toolkit (13.3) exactly. **PROD.**

### The real model round trip — `model: true`

Seeded booking `DX-5CD40A`, *Harbour Street → Central rail station*, pax 3, bags 1:

    Q  Which pickup address is on the board for the rail station trip?
    model: true   0.42 s
    A  "Harbour Street. The rider is Smoke Rider and the quote is blank…"

    Q  How many passengers are on the Friday evening job?
    model: true   0.44 s
    A  "The Friday evening job has three passengers. The job board states 'pax 3 bags 1'
        for the job DX-5CD40A…"

**Why this is not the fallback, beyond the flag.** `ai.local_answer()` can only ever emit one
of three fixed shapes — *"On the board right now: …"*, *"The live job is X: A to B, …"*, or
the "not available" sentence. It cannot read a pickup address, a rider name, or `pax 3 bags 1`
out of the board. These answers quote all of them. Chat also measured **90.9 tok/s** on a
67-token generation, which is GPU throughput.

### Health

    local  http://127.0.0.1:8800/api/status   200
    public https://symoneural.com/api/status  200
    public https://symoneural.com/overview    200
    public https://symoneural.com/demo/dispatchos  401 unauthenticated (edge auth intact)

### Tests

    apps/test_dispatchos.py  test_runtime_boundary.py  test_maintenance_banner.py
    apps/test_build_progress.py                              87 passed

Mutation-proved rather than trusted — each applied, caught, reverted:

| sabotage | caught by |
|---|---|
| unit template hardcodes `/yocto` in `ExecStart` | `test_no_template_hardcodes_yocto_in_a_path_directive` (+1 more) |
| template loses its `@@ROOT@@` placeholder | `test_templates_use_the_placeholder` |
| model manifest SHA truncated | `test_the_chat_model_manifest_is_present_and_complete` |
| installer stops running the verifier | `test_the_installer_runs_the_verifier` |
| customer isolation removed (DispatchOS) | `test_a_customer_sees_only_their_own_trips` |
| a default tariff appears | 6 quote tests |
| `sent_at` populated on a message | `test_a_composed_message_is_never_marked_sent` |
| operator role check dropped | `test_a_customer_cannot_quote_dispatch_or_set_rates` |
| lifecycle order not enforced | 2 lifecycle tests |

### The coded migration path, exercised end to end

Not a description — this was actually run, in this order, on the live box:

1. `ops/rollback-runtime.sh` → production **back onto the `/yocto` units**, health 200.
2. `ops/verify-runtime.sh` → **exit 1**, ten specific violations (cwd, argv, exe, 4 open fds,
   mapped files, deploy would republish from `/yocto`). That is the verifier's own proof.
3. `sudo ops/install-runtime.sh` → preflight, backup to
   `/etc/symoneural/unit-backups/20260826-092957`, atomic install of three units,
   `daemon-reload`, controlled restart (gateway then API), local 200 after ~4 s, public 200,
   verifier **clean**.
4. `ops/install-runtime.sh --dry-run` re-run → *"every unit is already correct — nothing to
   install"*. **Idempotent.**

### The gateway is built, not copied

`ops/build-gateway.sh --force` after deleting the binary **and** cargo's `deps/` copy: a real
43-second relink produced **byte-identical `sha256 41b9eda8…ad74`**, 27,232,992 bytes,
`st_nlink=1`, 0 unresolved deps, 0 `/yocto` linkage, no `/yocto` string in the binary. Record
in `ops/manifests/gateway-build.json`.

Built **natively** (`cargo 1.97.1`, `rustc 1.97.1`, host `x86_64-unknown-linux-gnu`) and not
with the Yocto SDK, because that SDK's `TARGET_SYS` is **`aarch64-oe-linux`** and cannot
produce a binary that runs on this host at all. See `docs/ops/BUILD-BOUNDARY.md`.

### The model is verified, not assumed

4,683,074,240 bytes · `sha256 65b8fcd9…aa1423` · GGUF v3 · 339 tensors · `qwen2` ·
*Qwen2.5 7B Instruct* · `file_type 15` (Q4_K_M) · `st_nlink=1` · not a symlink · different
inode **and different filesystem** from the read-only source, so a hardlink was never
possible. Manifest: `ops/manifests/llm-chat-model.json`. The `/yocto` source copy was **not**
moved, modified or deleted.

---

## REMOVED — wrong, dead, or contradicted by the box

- **`WorkingDirectory=/yocto/Symoneural`** on all three units. Replaced.
- **Gateway executed from `/yocto`.** Now the canonical, independently built artifact.
- **`symoneural-deploy` publishing from `/yocto`** — the one that would have silently reverted
  the site at every boot.
- **`backend/engines/…` as the native engine path.** It does not exist. `backend/api.py:183`
  computes `ROOT / "engines" / …`. Corrected here and in `docs/ops/BUILD-BOUNDARY.md`.
  *(Not to be confused with `.claude/HANDOVER.md`'s planned Python adapter package, also
  called `backend/engines/` — a different thing, correct as written.)*
- **Driver 590.48.01 / CUDA 13.1.** The box reads **610.57.04** and **13.3**.
- **Hand-run migration commands.** Replaced by `ops/install-runtime.sh` and friends. The
  installer's dry run proving "nothing to install" is the evidence that what was done by hand
  and what the repository does are the same thing.

---

## AUDIT — true but not proven here, or deliberately not claimed

- **Reboot behaviour is inferred, not observed.** Every enabled unit names the canonical root
  and the deploy condition path does too, so a reboot cannot republish `/yocto` content. The
  box has not actually been rebooted to watch it happen.
- **The engine is not resident at boot.** It starts on demand from a chat request and
  DispatchOS never starts it — by design, so a rider's question cannot evict a render. After
  any restart the first `/ask` will take the labelled fallback until something warms chat.
  That is correct behaviour, not a regression.
- **Rate rules remain unconfigured**, so every quote shows `——`. Required by the customer
  preview, which states it carries no pricing of any kind.
- **`/etc/symoneural/dispatchos-logins.txt`** holds the four application passwords, root-only
  0600, never printed. Read once, hand over, `shred -u`.
- **The four-status edge check on `/demo/dispatchos`** is 401/401/401 verified; the
  authenticated 200 is Garrett's own login to prove, because this repo holds bcrypt hashes.
- **`/yocto` build workspace continues to run** (BitBake, the 8-cell matrix). Untouched by
  this migration and explicitly allowed.
