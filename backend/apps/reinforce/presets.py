"""SyMoNeuRaL Reinforce -- the predetermined tuning methods.

The owner's second complaint: no *"predetermined professional tuning methods"*. Four named
profiles live here. They are named for the job they do, not for their rank, because a rank is
not a decision an operator can make and "Voice" is.

## Why presets rather than a settings page

A settings page that exposes every knob is not a tuning method; it is a form. The value of a
preset is that somebody already spent the run finding out which combination works, and every
value below carries a **`why`** and a **`provenance`** field saying where it came from. If a
value has no defensible source it does not belong in a preset.

## Provenance vocabulary, and why none of these says "measured"

`.claude/CLAUDE.md` allows exactly three labels for a figure: measured on this machine,
vendor specification, or projected arithmetic. Hyperparameters are not figures of that kind,
so they carry a fourth vocabulary describing where the *choice* came from:

* `published` -- somebody else's paper or a library default (QLoRA, peft, TAO)
* `manual` -- `docs/symoneural-manual.md`, Playbook 04, written on this box
* `as-shipped` -- what the existing trainer already does, unvalidated
* `hardware` -- forced by one 16 GiB card, not chosen
* `convention` -- a ratio kept fixed so one knob stays one knob
* `measured` -- used for exactly one entry, `warmup_steps`, because the reason for expressing
  warmup in steps is a fact checked against the installed library on this box:
  `warmup_ratio` is absent from transformers 5.15.0.

**No quality claim appears here and none may be added without a run behind it.** Nothing about
training quality or throughput has ever been measured on this box: one adapter exists, from an
unlogged run with no validation split. So there is no "this preset scores better" field, and
the VRAM figures are projected until `jobs.measured_peaks()` has a real reading for that exact
(model x preset) pair.

## What is deliberately absent

Preference tuning -- DPO, GRPO, KTO, reward modelling. The library is installed and the
trainers exist, but DPO needs paired preference data, which does not exist here, and a
reference model resident beside the policy on a card with no headroom is a second design
problem. `NOT_IN_V1` below says so in text. A greyed-out tab would be a decorative control,
which is the same dishonesty as a decorative status light.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from . import registry

# The seven `nn.Linear` leaves in a Qwen2-family decoder layer, and the only seven there are.
# peft's `all-linear` shorthand resolves to exactly this set on this architecture (it excludes
# lm_head by design), so offering both would be two spellings of one thing -- a knob that does
# nothing, which an operator would burn a run discovering. The explicit list is used because
# it is readable in a run manifest and it survives peft changing its mind about `all-linear`.
ALL_SEVEN = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
ATTENTION_ONLY = ("q_proj", "v_proj")

# Fixed across every preset, because the hardware decides them rather than the operator.
SHARED = {
    "quantisation": {"value": "4-bit NF4 + double quantisation, bf16 compute",
                     "provenance": "published",
                     "why": ("4-bit low-rank adaptation is not a cost optimisation on this box, "
                             "it is the only thing that makes a 7B trainable here at all -- "
                             "full fine-tuning of 7.6B parameters needs roughly 8x this card")},
    "gradient_checkpointing": {"value": True, "provenance": "hardware",
                               "why": ("mandatory at 7B on 16 GiB: without it the stored "
                                       "activations alone exceed the budget. Not offered as a "
                                       "choice because there is no configuration here where "
                                       "turning it off fits")},
    "bf16": {"value": True, "provenance": "hardware",
             "why": "Blackwell sm_120; bf16 compute is native and fp16 loss scaling is avoidable"},
    "optim": {"value": "paged_adamw_8bit", "provenance": "published",
              "why": ("QLoRA's paged optimiser. Two bytes of moment state per trainable "
                      "parameter instead of eight, and the paging is what stops an allocator "
                      "spike from OOMing a card with no headroom")},
    "lora_dropout": {"value": 0.05, "provenance": "published",
                     "why": "peft's common default; also what the existing trainer uses"},
    "bias": {"value": "none", "provenance": "published",
             "why": "training biases adds parameters that carry almost no adaptation"},
    "per_device_train_batch_size": {"value": 1, "provenance": "hardware",
                                    "why": ("batch is the term that multiplies the activation "
                                            "cost, and the activation cost is dominated by a "
                                            "152k-wide logit tensor. Batch 2 at seq 1024 adds "
                                            "roughly a gibibyte for nothing that gradient "
                                            "accumulation cannot buy more cheaply")},
    "warmup": {"value": "expressed in steps, never warmup_ratio", "provenance": "measured",
               "why": ("checked against the installed transformers 5.15.0 and trl 1.10.0 on "
                       "this box: `warmup_ratio` is absent from both TrainingArguments and "
                       "SFTConfig. Code copied from older guides raises TypeError here")},
    "loss_masking": {"value": "assistant turn only, hand-rolled -100 mask",
                     "provenance": "as-shipped",
                     "why": ("training on the prompt teaches the model to predict questions. "
                             "trl's `assistant_only_loss` is NOT a drop-in replacement on this "
                             "model: it needs {% generation %} markers in the chat template and "
                             "the stock Qwen2.5 template has none, so it would fail rather than "
                             "silently mis-mask. The hand-rolled mask is a workaround for a real "
                             "gap, not legacy cruft")},
    "seed": {"value": 20260817, "provenance": "convention",
             "why": ("the shipped adapter is not reproducible -- no seed was set and no run "
                     "config was written beside the weights. Every run from this surface writes "
                     "a manifest with its seed")},
}


@dataclass
class Preset:
    id: str
    label: str
    when: str                       # when this preset is the right one
    epochs: float
    rank: int
    lora_alpha: int
    target_modules: tuple[str, ...]
    learning_rate: float
    lr_scheduler_type: str
    max_length: int
    gradient_accumulation_steps: int
    val_split: float
    save_strategy: str
    max_examples: int = 0           # 0 means the whole dataset
    max_steps: int = 0              # 0 means run the epochs out
    rationale: dict = field(default_factory=dict)

    @property
    def effective_batch(self) -> int:
        return self.gradient_accumulation_steps      # per-device batch is 1 on this card

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_modules"] = list(self.target_modules)
        d["effective_batch"] = self.effective_batch
        return d


PRESETS: dict[str, Preset] = {}


def _add(p: Preset) -> None:
    PRESETS[p.id] = p


_add(Preset(
    id="smoke",
    label="Smoke",
    when=("Prove the pipeline runs end to end before spending an hour on it. Not a training "
          "method -- a test of one. Nothing it produces should be served."),
    epochs=1.0, rank=8, lora_alpha=16, target_modules=ATTENTION_ONLY,
    learning_rate=2e-4, lr_scheduler_type="cosine", max_length=512,
    gradient_accumulation_steps=4, val_split=0.1, save_strategy="no",
    max_examples=32, max_steps=8,
    rationale={
        "rank": ("8 -- the bottom of the manual's 8-32 band. This preset is not trying to "
                 "learn anything, it is trying to finish. (provenance: manual)"),
        "target_modules": ("q,v only. The existing trainer's docstring is explicit that "
                           "attention-only adapters pick up style but are worse at absorbing "
                           "facts -- which is exactly why it is the right choice here and the "
                           "wrong one everywhere else. (provenance: as-shipped)"),
        "max_steps": ("8. A capped step count is what makes this a smoke test rather than a "
                      "short run: it reaches the optimiser, the backward pass and the peak "
                      "allocation, then stops. (provenance: convention)"),
        "base_model": ("defaults to the 7B, which is the only model on this box in a trainable "
                       "format. Defaulting the fastest-feedback preset to a smaller base would "
                       "gate it behind a download, which is backwards for a preset whose job is "
                       "to fail fast. (provenance: hardware)"),
        "learning_rate": "2e-4 -- top of the manual's 1e-4 to 3e-4 band. (provenance: manual)",
    },
))

_add(Preset(
    id="voice",
    label="Voice",
    when=("Teach style, persona and refusals -- behaviour rather than facts. This is the "
          "profile that produced the adapter the chat surface serves."),
    epochs=3.0, rank=16, lora_alpha=32, target_modules=ALL_SEVEN,
    learning_rate=1e-4, lr_scheduler_type="cosine", max_length=1024,
    gradient_accumulation_steps=16, val_split=0.1, save_strategy="epoch",
    rationale={
        "rank": ("16 with alpha 32. The most-cited low-rank configuration, and it arrives here "
                 "three times independently: the existing trainer, this repo's own Playbook 04, "
                 "and NVIDIA TAO's preflight defaults. (provenance: published + manual)"),
        "alpha": ("2x rank, held as a fixed ratio so that rank is genuinely the single knob it "
                  "appears to be. (provenance: convention)"),
        "learning_rate": ("1e-4 -- the low end of the band, because behaviour is learned from a "
                          "small number of examples repeated, and a high rate on a small corpus "
                          "overwrites more than it teaches. (provenance: as-shipped)"),
        "epochs": ("3. The manual's stated priority order is data quality > learning rate > "
                   "epochs (1-3, watch val loss) > rank. Three epochs is the top of that band "
                   "and is where the validation split earns its keep. (provenance: manual)"),
        "effective_batch": ("16, reached as batch 1 x 16 accumulation. This CHANGES the existing "
                            "trainer, which uses 8. The manual's snippet targets 16 (as 2 x 8); "
                            "batch must stay at 1 on this card, so the accumulation carries it. "
                            "(provenance: manual)"),
        "val_split": ("10%. The manual says to hold out 5-10% BEFORE looking at training loss. "
                      "The shipped trainer does not do this, which is why no loss curve on this "
                      "box means anything yet. (provenance: manual)"),
    },
))

_add(Preset(
    id="recall",
    label="Recall",
    when=("Absorb domain vocabulary and facts the base model does not have. Product names, "
          "part numbers, procedures -- content, not character."),
    epochs=2.0, rank=32, lora_alpha=64, target_modules=ALL_SEVEN,
    learning_rate=2e-4, lr_scheduler_type="cosine", max_length=1024,
    gradient_accumulation_steps=16, val_split=0.1, save_strategy="epoch",
    rationale={
        "rank": ("32 -- the top of the manual's 8-32 band, for the case the manual says rank "
                 "actually matters for. Roughly doubles the trainable parameters against Voice "
                 "over the identical module set. (provenance: manual)"),
        "why_not_more_modules": ("Rank is what separates Recall from Voice, NOT module coverage. "
                                 "There is no larger module set to escalate to: the seven are "
                                 "every linear leaf in the decoder layer. A preset advertising "
                                 "'more coverage' would be a knob that does nothing. "
                                 "(provenance: published)"),
        "trainable_pct": ("lands at roughly 1.06% of the base at r=32 on a 7B, just outside the "
                          "0.1-1% band TAO's error playbook uses to catch an over-broad target "
                          "list. Here it is deliberate and the module list is exactly right, so "
                          "the preflight flags it rather than refusing. (provenance: published)"),
        "epochs": ("2. Facts need fewer passes than character does, and a third pass on a small "
                   "corpus at rank 32 is where memorisation stops being recall. (provenance: manual)"),
        "learning_rate": "2e-4 -- the manual's own snippet value. (provenance: manual)",
    },
))

_add(Preset(
    id="longform",
    label="Long-form",
    when=("Documents longer than a chat turn: manuals, transcripts, incident logs. Anything "
          "where the answer depends on context that will not fit in 1024 tokens."),
    epochs=2.0, rank=16, lora_alpha=32, target_modules=ALL_SEVEN,
    learning_rate=1e-4, lr_scheduler_type="cosine", max_length=2048,
    gradient_accumulation_steps=8, val_split=0.1, save_strategy="epoch",
    rationale={
        "max_length": ("2048, and this is a VRAM decision rather than a model limit -- the base "
                       "supports 32,768 tokens of context. Doubling the sequence roughly doubles "
                       "the activation term, and on a 152k-vocabulary model that term is "
                       "dominated by the logit tensor: seq 2048 costs about 1.78 GiB of logits "
                       "alone. This is the preset closest to the ceiling. (provenance: manual)"),
        "gradient_accumulation_steps": ("8 rather than 16, so that a doubled sequence length does "
                                        "not also double the wall-clock per optimiser step. "
                                        "(provenance: convention)"),
        "rank": ("16, not 32. At seq 2048 the headroom belongs to activations, and rank is the "
                 "cheapest thing to give back. (provenance: hardware)"),
    },
))


# Named in the UI as text, not built as a disabled control.
NOT_IN_V1 = {
    "preference_tuning": (
        "Preference tuning -- DPO, GRPO, KTO and reward modelling -- is not offered. The library "
        "on this box ships all four trainers, so this is a deliberate omission and not a missing "
        "dependency. Two reasons: it needs paired preference data, which does not exist here, and "
        "it needs a reference model alongside the policy on a card that has no room for one. "
        "There is no greyed-out tab for it, because a control that cannot be used is a decorative "
        "control."),
    "full_fine_tuning": (
        "Full fine-tuning is not offered at any model size. 7.6B parameters under AdamW needs "
        "weights, gradients and two optimiser moments -- about 113 GiB at fp32, and mixed "
        "precision with an fp32 master copy lands in the same place. Against a ~14.2 GiB budget "
        "the shortfall is roughly 8x. This is a capability this box does not have, not a feature "
        "that has not been built."),
    "multi_gpu": (
        "No FSDP, no ZeRO-3, no tensor parallelism. One card, no NVLink. Optimiser offload to "
        "host memory is not a rescue either: this host is capped at PCIe Gen 3 x8, which turns a "
        "VRAM problem into a wall-clock one."),
}


def fit_table(model_id: str = "Qwen/Qwen2.5-7B-Instruct",
              free_bytes: int | None = None) -> list[dict]:
    """Every preset costed against one model. The picker's whole argument in one table.

    Returns one row per preset with the itemised projection from `registry.plan_fit`. Rows for
    a model that is not on this box still compute -- the arithmetic only needs the architecture,
    and refusing to show the cost of a model you cannot yet run is exactly the information an
    operator needs to decide whether to fetch it.
    """
    entry = registry.find(model_id)
    if entry is None or entry.arch is None:
        return []
    arch = registry.Arch(**entry.arch)
    rows = []
    for p in PRESETS.values():
        plan = registry.plan_fit(
            arch, rank=p.rank, target_modules=p.target_modules, seq_len=p.max_length,
            batch=1, gradient_checkpointing=True, free_bytes=free_bytes)
        rows.append({"preset": p.id, "label": p.label, "model": entry.id,
                     "model_trainable": entry.trainable, "plan": plan})
    return rows
