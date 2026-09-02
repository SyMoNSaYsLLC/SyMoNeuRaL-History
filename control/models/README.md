# control/models — model inspection and lifecycle, from one place

Thin wrappers over the model authorities that already exist. **Nothing here implements model
management.** Every launcher delegates to `tools/modelops_inventory.py`,
`scripts/modelops/symoneural-modelops-stage.sh`, `scripts/gpu-governor.sh`, or
`training/train_lora.py`. Delete this folder and the server is unaffected.

## The state this box is actually in

```
LEARNED MODEL PAYLOADS: 0
```

**That is a valid state, not an error.** Every launcher reports it explicitly rather than
degrading to a CPU fallback or returning an empty success that reads like a pass.

## The distinction that matters most

`backend/models/PROVENANCE.json` holds 11 records. There are 0 payloads on disk. A tool that
counts records and calls them models reports eleven installed models on a machine with none.

| Term | Meaning |
|---|---|
| **PAYLOAD** | Learned-model bytes on disk. The only thing that can serve a request. |
| **METADATA** | Config, tokeniser, scaffolding. Present without a payload means nothing is installed. |
| **PROVENANCE** | A historical origin record. Says nothing about whether the artefact is here now. |
| **CONFIGURATION** | Which model a surface *selects*. A selection is not a presence. |
| **ABSENT** | Measured, and measured as not here. |
| **UNKNOWN** | Could not be established. Never collapsed into ABSENT or into a guess. |

`ABSENT` and `UNKNOWN` stay distinct: "I looked and there is nothing" and "I could not look"
are different answers.

## Launchers

### Read-only

| Command | Answers |
|---|---|
| `models-list.sh` | What payloads are on disk |
| `models-active.sh` | Which model each surface *selects* (configuration) |
| `models-loaded.sh` | What is *resident* right now (live API + governor) |
| `models-provenance.sh` | Origin records — printed separately from payload count |
| `models-license.sh` | Licence status; reports UNVERIFIED, never a conclusion |
| `models-checksums.sh` | Recorded digests; says so when there is nothing to verify |
| `models-compat.sh` | Runtime/engine/CUDA compatibility — answerable with no model present |
| `models-adapters.sh` | Adapter presence; contents never printed (protected) |
| `models-rebrand.sh` | House-naming compliance |
| `models-gpu.sh` | GPU state — delegates to `control/gpu.sh` |

### Write-mode — all refuse without an explicit flag

| Command | Guard |
|---|---|
| `models-stage.sh` | Pass-through; the authority refuses to download or activate without a flag |
| `models-verify.sh` | Stops if the governor reports another holder, or if there is no payload |
| `models-activate.sh` | Forwards to the six downstream gates; never bypasses them |
| `models-rollback.sh` | The one mode safe to reach for in a hurry |
| `models-release.sh` | Hands the card back via `control/gpu.sh` |
| `models-finetune.sh` | Needs `--execute`; stops if the corpus is absent; never echoes it |

## Deliberately absent

**`models-acquire.sh` does not exist.** Acquisition semantics depend on an unresolved
decision (D-2), and a launcher that looked operational but refused would be worse than none.
Acquisition remains `scripts/fetch-models.sh`, run deliberately and separately authorized.

**No conversion or quantization launcher.** No CLI authority exists to wrap; proposing one
would violate the thin-wrapper rule. Excluded by D-6.

## Rule for anyone extending this folder

A launcher may **wrap** an authority. It may not **become** one. If you find yourself parsing
model files or implementing lifecycle logic here, the logic belongs in the authority and this
folder should call it.
