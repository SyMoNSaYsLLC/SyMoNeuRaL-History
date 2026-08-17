#!/usr/bin/env python3
"""SyMoNeuRaL Reinforce -- the training runner. Runs in `training/.venv`, NOT in the API.

This is the only file in this package that imports torch, and it is never imported by the
serving API. It is exec'd as a subprocess:

    scripts/gpu-governor.sh with train -- training/.venv/bin/python runner.py --preset voice ...

Three boundaries meet here and all three are deliberate:

* **Interpreter.** The serving API runs on the system interpreter, which carries fastapi,
  uvicorn, pydantic and sympy and nothing else, on purpose. The training stack is torch
  cu128 because Blackwell sm_120 needs it. A subprocess is what lets both be true.
* **Process.** A crashed fine-tune cannot take the API down with it, and the API restarting
  cannot take the fine-tune down with it. `jobs.py` detaches the session for the second half
  of that.
* **Lock.** This process never talks to the governor. It is *run underneath* the governor's
  `with train` form, which acquires before it starts and releases after it exits, including
  on a crash. Nothing here calls acquire, and nothing here calls release -- a bare release
  once destroyed a running fine-tune's lock, and the fix is that the only code releasing the
  card is the code that took it.

## What this runner does that the existing trainer does not

`training/train_lora.py` produced the shipped adapter, and two of its choices are carried
forward here verbatim because they are right (see `_encode`). But it has no validation split,
no eval, no checkpoints, no seed and no run manifest, so nothing it produced can be measured
or reproduced. This runner adds exactly those:

* a held-out validation split, per the repo manual's *"hold out 5-10% BEFORE looking at
  training loss"*;
* a seed, recorded;
* `save_strategy` from the preset;
* a **run manifest** written beside the adapter with every hyperparameter, the seed, and the
  measured peak VRAM -- which is what lets a projected figure ever become a measured one;
* `--max-steps`, so a smoke test is genuinely a handful of steps rather than a short run.

## Output protocol -- read this before adding a print

Everything this process writes to stdout is captured into a log that feeds an API response.
`jobs.parse_log()` reads it with an **allowlist**: only lines of the exact form

    REINFORCE key=value key=value ...

with keys from a fixed set and values matching `[A-Za-z0-9_.:+-]{1,64}` are parsed; every
other line is discarded unparsed. That is the guard, and it is an allowlist rather than a
denylist because a denylist would have to anticipate every shape a leaked training example
could take.

**Which is why errors here report a class name and a stage, never a message.** A traceback out
of the tokeniser or the collator can carry a training example verbatim, and the corpus is the
trade secret this whole surface is most likely to leak. `_fail()` is the only error path and
it prints `kind=<ExceptionClassName> stage=<stage>` and nothing else. The full traceback goes
to stderr, into a log file under `run/` that no route serves.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent

# Take this script's own directory OFF sys.path before importing anything third-party.
#
# This is a real bug that happened, not a precaution. Python puts a script's directory at
# sys.path[0], so `from datasets import Dataset` -- the Hugging Face package -- resolved to the
# sibling module in this directory instead, which is a serving-path module full of relative
# imports, and the run died at `ImportError: attempted relative import with no known parent
# package` after waiting 74 seconds for the GPU. The sibling has since been renamed
# `dataset_guard.py`, but the rename fixes one collision and this line fixes the class of them:
# any future module here named `torch.py`, `peft.py` or `accelerate.py` would do the same
# thing, and the failure surfaces only after the card has been acquired.
sys.path[:] = [p for p in sys.path if pathlib.Path(p or ".").resolve() != HERE]
# backend/apps/reinforce -> backend/apps -> backend -> repo root. This calculation has been
# wrong three times in this repo and it fails silently, because the wrong parent is usually a
# directory that exists -- `training/train_lora.py` has it wrong right now, producing an
# HF_HOME of /home/google/models/hf, which does not exist. Assert, the way
# tools/build_training.py does, so a misresolution is immediate and obvious.
ROOT = HERE.parent.parent.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root misresolved to {ROOT}"

HF_HOME = ROOT / "backend" / "models" / "hf"
os.environ.setdefault("HF_HOME", str(HF_HOME))
# Offline by default. A path slip that would otherwise start a silent ~14 GiB re-download
# becomes an immediate, legible error instead.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# The two artefacts that must never be read by this surface. Duplicated from `datasets.py`
# rather than imported, on purpose: this process runs in a different interpreter under a
# different working directory, and a guard that depends on an import path is a guard that can
# be lost to a refactor. Both copies must agree, and the test suite asserts that they do.
DENIED = {
    (ROOT / "training" / "corpus.jsonl").resolve(),
    (ROOT / "training" / "build_dataset.py").resolve(),
}

STAGES = ("load_dataset", "load_model", "build_adapter", "train", "evaluate", "save")


def emit(**fields) -> None:
    """Print one allowlisted line. Values are coerced to the shape the parser accepts.

    Anything that would not survive `jobs.parse_log()` is dropped here rather than printed and
    silently discarded on the other side, so the two ends cannot drift without a test noticing.
    """
    parts = []
    for key, val in fields.items():
        if val is None:
            continue
        if isinstance(val, float):
            text = f"{val:.6g}"
        else:
            text = str(val)
        # The value character class the parser enforces. A value that does not fit is dropped,
        # never truncated into something that might still carry content.
        if not text or len(text) > 64 or any(c not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:+-" for c in text):
            continue
        parts.append(f"{key}={text}")
    if parts:
        print("REINFORCE " + " ".join(parts), flush=True)


def _fail(stage: str, exc: BaseException) -> int:
    """The only error path. Class name and stage to stdout; traceback to stderr only."""
    emit(event="error", kind=type(exc).__name__, stage=stage if stage in STAGES else "train")
    print("--- traceback (stderr only; not served by any route) ---", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    return 1


def _write_atomic(path: pathlib.Path, payload: dict) -> None:
    """Write JSON so a reader never sees a half-written file.

    `jobs.py` reads `progress.json` on a timer while this process is writing it; without the
    rename the API would intermittently parse a truncated document and report `state: none`
    over a live run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="SyMoNeuRaL Reinforce training runner")
    ap.add_argument("--model", required=True, help="path to the HF snapshot directory")
    ap.add_argument("--model-id", default="")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preset", default="custom")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--scheduler", default="cosine")
    ap.add_argument("--max-length", type=int, default=1024)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--val-split", type=float, default=0.1)
    ap.add_argument("--save-strategy", default="no")
    ap.add_argument("--seed", type=int, default=20260817)
    ap.add_argument("--target-modules",
                    default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    ap.add_argument("--max-examples", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--progress-file", default="")
    ap.add_argument("--measured-file", default="")
    args = ap.parse_args()

    # ---- guards, before anything is opened -------------------------------------------
    if not HF_HOME.is_dir():
        print(f"HF_HOME does not resolve: {HF_HOME}", file=sys.stderr)
        emit(event="error", kind="MissingWeightCache", stage="load_model")
        return 2
    dataset_path = pathlib.Path(args.dataset).resolve(strict=False)
    if dataset_path in DENIED or (ROOT / "training" / "adapter").resolve() in dataset_path.parents:
        # Refused, and refused loudly. This is the second of two independent checks -- the API
        # refuses in `datasets.admit()` before it ever launches this process -- because a
        # single guard is a guard that a future caller can bypass by not going through the API.
        print("refusing a protected SyMoNeuRaL artefact as a dataset", file=sys.stderr)
        emit(event="error", kind="ProtectedArtefact", stage="load_dataset")
        return 3

    progress_file = pathlib.Path(args.progress_file) if args.progress_file else None
    started = time.time()
    stage = "load_dataset"

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                                  DataCollatorForSeq2Seq, Trainer, TrainerCallback,
                                  TrainingArguments)

        random.seed(args.seed)
        torch.manual_seed(args.seed)

        rows = []
        with dataset_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        if args.max_examples:
            rows = rows[: args.max_examples]
        random.Random(args.seed).shuffle(rows)

        # The validation split the shipped trainer does not have. The repo manual is explicit:
        # hold out 5-10% BEFORE looking at training loss. Without it a loss curve is a report
        # on memorisation, which is why no figure from the existing adapter means anything.
        n_val = max(1, int(len(rows) * args.val_split)) if args.val_split > 0 and len(rows) > 4 else 0
        val_rows, train_rows = rows[:n_val], rows[n_val:]
        emit(event="start", rows=len(train_rows), val_rows=len(val_rows), seed=args.seed)

        stage = "load_model"
        tok = AutoTokenizer.from_pretrained(args.model)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token

        def _encode(row: dict) -> dict:
            """Render with the model's own chat template, then mask everything but the answer.

            Carried forward verbatim from `training/train_lora.py`, and deliberately NOT
            replaced by trl's `assistant_only_loss`. That flag needs `{% generation %}` markers
            in the chat template so trl can find the assistant span; the stock Qwen2.5 template
            has none, so it would fail rather than silently mis-mask. The hand-rolled -100 mask
            is a workaround for a real gap, not legacy cruft.

            Why mask at all: training on the prompt teaches the model to predict questions,
            which dilutes the gradient that carries the behaviour being taught.
            """
            msgs = row["messages"]
            prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
            answer = msgs[-1]["content"] + tok.eos_token
            p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            a_ids = tok(answer, add_special_tokens=False)["input_ids"]
            ids = (p_ids + a_ids)[: args.max_length]
            labels = ([-100] * len(p_ids) + a_ids)[: args.max_length]
            return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)}

        keep = ["input_ids", "labels", "attention_mask"]
        train_ds = Dataset.from_list(train_rows).map(
            _encode, remove_columns=[c for c in Dataset.from_list(train_rows).column_names
                                     if c not in keep])
        eval_ds = (Dataset.from_list(val_rows).map(
            _encode, remove_columns=[c for c in Dataset.from_list(val_rows).column_names
                                     if c not in keep]) if val_rows else None)

        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            ),
            dtype=torch.bfloat16,
            device_map={"": 0},
        )
        model.config.use_cache = False

        stage = "build_adapter"
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        model = get_peft_model(model, LoraConfig(
            r=args.rank, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none",
            task_type="CAUSAL_LM",
            target_modules=[m for m in args.target_modules.split(",") if m],
        ))
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        emit(event="start", trainable=trainable, total_params=total)

        stage = "train"
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

        class Progress(TrainerCallback):
            """Emit a real reading per logging step. No smoothing, no interpolation.

            The VRAM figures are `torch.cuda.max_memory_allocated()` and
            `max_memory_reserved()` -- measured inside the process that is doing the
            allocating, which is the only place they can be measured honestly. `nvidia-smi`
            from outside would see this process's reservation plus everything else on the card.
            """

            def on_log(self, targs, state, control, logs=None, **kw):
                logs = logs or {}
                alloc = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
                reserved = int(torch.cuda.max_memory_reserved()) if torch.cuda.is_available() else 0
                if "loss" in logs:
                    payload = {
                        "event": "step", "step": state.global_step,
                        "total_steps": state.max_steps,
                        "epoch": round(float(state.epoch or 0), 4),
                        "loss": logs.get("loss"), "lr": logs.get("learning_rate"),
                        "elapsed_s": round(time.time() - started, 1),
                        "vram_alloc": alloc, "vram_reserved": reserved,
                    }
                    emit(**payload)
                    if progress_file:
                        _write_atomic(progress_file,
                                      {k: v for k, v in payload.items() if k != "event"})
                if "eval_loss" in logs:
                    emit(event="eval", step=state.global_step, val_loss=logs["eval_loss"])

        targs = dict(
            output_dir=str(pathlib.Path(args.out) / "checkpoints"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=args.grad_accum,
            gradient_checkpointing=True,
            learning_rate=args.lr,
            lr_scheduler_type=args.scheduler,
            # Steps, never `warmup_ratio`: that argument is absent from transformers 5.15.0 and
            # trl 1.10.0 on this box, and code copied from older guides raises TypeError here.
            warmup_steps=max(1, int(0.05 * len(train_rows) * args.epochs / max(1, args.grad_accum))),
            logging_steps=1,
            save_strategy=args.save_strategy,
            bf16=True,
            optim="paged_adamw_8bit",
            seed=args.seed,
            report_to=[],
        )
        if args.max_steps:
            # `max_steps` overrides the epoch count outright, which is what makes a smoke test
            # a fixed handful of steps regardless of how large the dataset happens to be.
            targs["max_steps"] = args.max_steps
        if eval_ds is not None:
            targs["eval_strategy"] = "epoch" if not args.max_steps else "no"
            targs["per_device_eval_batch_size"] = 1

        trainer = Trainer(
            model=model, train_dataset=train_ds, eval_dataset=eval_ds,
            data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
            args=TrainingArguments(**targs), callbacks=[Progress()],
        )
        trainer.train()

        stage = "evaluate"
        val_loss = None
        if eval_ds is not None:
            metrics = trainer.evaluate()
            val_loss = metrics.get("eval_loss")
            emit(event="eval", step=trainer.state.global_step, val_loss=val_loss)

        stage = "save"
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(out))
        tok.save_pretrained(str(out))

        peak_alloc = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
        peak_reserved = int(torch.cuda.max_memory_reserved()) if torch.cuda.is_available() else 0
        elapsed = time.time() - started

        # The run manifest. The shipped adapter has none -- no seed, no hyperparameters, no
        # results -- which is why it is not reproducible and why nothing about it can be
        # quoted. Every run from this surface writes one, beside its own weights.
        #
        # It records the DATASET'S SHAPE (name, row counts) and never its contents. It also
        # records the resolved path, which is fine here: the manifest sits beside the adapter
        # under run/, and no route in this package serves it.
        manifest = {
            "run": {"preset": args.preset, "model": args.model_id or args.model,
                    "seed": args.seed, "started_at": started, "elapsed_s": round(elapsed, 1),
                    "elapsed_label": "measured"},
            "hyperparameters": {
                "epochs": args.epochs, "max_steps": args.max_steps or None,
                "rank": args.rank, "lora_alpha": args.alpha, "lora_dropout": args.dropout,
                "learning_rate": args.lr, "lr_scheduler_type": args.scheduler,
                "max_length": args.max_length, "per_device_train_batch_size": 1,
                "gradient_accumulation_steps": args.grad_accum,
                "effective_batch": args.grad_accum,
                "target_modules": args.target_modules.split(","),
                "gradient_checkpointing": True, "bf16": True,
                "optim": "paged_adamw_8bit",
                "quantisation": "4-bit NF4 + double quantisation, bf16 compute",
                "warmup_steps": targs["warmup_steps"],
            },
            "dataset": {"name": dataset_path.name, "train_rows": len(train_rows),
                        "val_rows": len(val_rows), "label": "measured",
                        "note": "shape only; contents are never recorded in a manifest"},
            "results": {
                "trainable_params": trainable, "total_params": total,
                "trainable_pct": round(100.0 * trainable / total, 4) if total else None,
                "final_train_loss": trainer.state.log_history[-1].get("train_loss")
                                    if trainer.state.log_history else None,
                "val_loss": val_loss,
                "steps": trainer.state.global_step,
                "peak_vram_alloc_bytes": peak_alloc,
                "peak_vram_reserved_bytes": peak_reserved,
                "label": "measured",
                "note": ("peak VRAM read from torch inside this process. This retires the "
                         "projection for THIS model and THIS preset only -- scaling it to "
                         "another cell would be a projection wearing a measurement's label."),
            },
            "serving": ("this adapter is PEFT safetensors. The chat surface loads a GGUF "
                        "adapter, so it is not served until somebody converts it deliberately. "
                        "Nothing here promotes a run to the serving adapter."),
        }
        (out / "run-manifest.json").write_text(json.dumps(manifest, indent=2))

        # The measured-peaks ledger, keyed by the exact cell that was measured.
        if args.measured_file and peak_alloc:
            mf = pathlib.Path(args.measured_file)
            try:
                ledger = json.loads(mf.read_text())
            except (OSError, json.JSONDecodeError):
                ledger = {}
            ledger[f"{args.model_id or args.model}|{args.preset}"] = {
                "peak_alloc": peak_alloc, "peak_reserved": peak_reserved,
                "steps": trainer.state.global_step, "at": time.time(),
            }
            _write_atomic(mf, ledger)

        emit(event="done", peak_alloc=peak_alloc, peak_reserved=peak_reserved,
             elapsed_s=round(elapsed, 1), step=trainer.state.global_step)
        return 0

    except BaseException as exc:            # noqa: BLE001 -- every exit goes through _fail
        return _fail(stage, exc)


if __name__ == "__main__":
    raise SystemExit(main())
