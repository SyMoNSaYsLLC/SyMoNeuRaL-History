#!/usr/bin/env python3
"""QLoRA fine-tune: turn a stock Qwen2.5-7B-Instruct into the SyMoNeuRaL admin model.

This is Playbook 04 applied to the machine the playbook was written on. The base model is
loaded in 4-bit NF4 and only the adapter is trained, which is what makes a 7B tunable at all
on a 15.92 GiB card -- full fine-tuning would need roughly an order of magnitude more.

Two choices here matter more than the hyperparameters.

**Loss is computed on the assistant turn only.** The prompt and system message are masked
out. Training on the prompt teaches the model to predict questions, which is not the job and
which dilutes the gradient that actually carries the persona. With a corpus this small,
spending capacity on the wrong tokens is the difference between a model that has a character
and a model that has an accent.

**The persona buckets are oversampled in the corpus, not here.** See build_dataset.py --
identity and refusal examples repeat, so they carry real weight against the much larger
technical bucket. The refusals are the ones worth watching: a support model that invents a
price is a liability, and "I won't quote that" has to be learned as firmly as any fact.

The adapter is kept separate rather than merged, because llama.cpp can load a GGUF LoRA at
serve time. That keeps the base weights shared, makes the fine-tune auditable as a diff
rather than a new 15 GB artifact, and means reverting is a flag rather than a redeploy.

    ./.venv/bin/python train_lora.py --epochs 3
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent

# Keep every downloaded weight inside the project's models directory rather than scattering
# them through ~/.cache, so "where are the models" has one answer.
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))

BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(HERE / "corpus.jsonl"))
    ap.add_argument("--out", default=str(HERE / "adapter"))
    ap.add_argument("--base", default=BASE_MODEL)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--seq-len", type=int, default=1024)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              DataCollatorForSeq2Seq, Trainer, TrainingArguments)

    print(f"torch {torch.__version__}  cuda {torch.version.cuda}  "
          f"device {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    if torch.cuda.is_available():
        cap = torch.cuda.get_device_capability(0)
        print(f"compute capability sm_{cap[0]}{cap[1]}")

    rows = [json.loads(line) for line in pathlib.Path(args.corpus).read_text().splitlines() if line]
    print(f"corpus: {len(rows)} examples")

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def encode(row: dict) -> dict:
        """Render with the model's own chat template, then mask everything but the answer."""
        msgs = row["messages"]
        prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
        answer = msgs[-1]["content"] + tok.eos_token

        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        a_ids = tok(answer, add_special_tokens=False)["input_ids"]
        ids = (p_ids + a_ids)[: args.seq_len]
        # -100 is the ignore index: these positions contribute nothing to the loss.
        labels = ([-100] * len(p_ids) + a_ids)[: args.seq_len]
        return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)}

    ds = Dataset.from_list(rows).map(encode, remove_columns=["messages", "kind"])

    model = AutoModelForCausalLM.from_pretrained(
        args.base,
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
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        # Attention and MLP both. Attention-only adapters pick up style but are noticeably
        # worse at absorbing facts, and half this corpus is facts.
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        train_dataset=ds,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
        args=TrainingArguments(
            output_dir=str(HERE / "runs"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            gradient_checkpointing=True,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            # transformers 5.x dropped warmup_ratio in favour of an explicit step count.
            # Computed from the corpus so it stays ~5% of the run if either changes.
            warmup_steps=max(3, int(0.05 * (len(ds) * args.epochs) / 8)),
            logging_steps=10,
            save_strategy="no",
            bf16=True,
            optim="paged_adamw_8bit",
            report_to=[],
        ),
    )
    trainer.train()

    out = pathlib.Path(args.out)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    print(f"\nadapter -> {out}")
    print("next: convert_lora_to_gguf.py, then serve with llama-server --lora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
