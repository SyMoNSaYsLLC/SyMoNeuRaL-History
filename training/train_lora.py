#!/usr/bin/env python3
"""QLoRA fine-tune: turn a stock Qwen instruct model into the SyMoNeuRaL admin model.

This is Playbook 04 applied to the machine the playbook was written on. The base model is
loaded in 4-bit NF4 and only the adapter is trained, which is what makes a 7B tunable at all
on a 15.92 GiB card -- full fine-tuning would need roughly an order of magnitude more.

**Two bases, two shapes.** Qwen2.5-7B-Instruct is a plain causal LM and needs none of the
machinery below. Qwen3.6-27B is a multimodal wrapper around a *hybrid* text model, and three
things about it are load-bearing:

  * 48 of its 64 layers are `linear_attn` and carry no q/k/v/o_proj at all; only the 16 where
    `(i+1) % 4 == 0` are full `self_attn`. The 7B target list reaches attention in those 16
    and silently misses the other 48 -- no error, just a quarter-adapted model.
  * The vision tower is built whether or not you want it. `config.language_model_only` is a
    Qwen knob transformers does not read, and `Qwen3_5ForCausalLM` cannot be loaded directly
    because the checkpoint keys are `model.language_model.*` and it expects `model.*` -- it
    would match nothing and randomly initialise 27B of weights without complaint. So the
    tower is *placed* on the CPU rather than prevented.
  * The vocab is 248,320 tokens and `tie_word_embeddings` is false, so `embed_tokens` and
    `lm_head` are two separate 2.37 GiB bf16 tensors. bitsandbytes skips `lm_head` by
    default; at this vocab that default alone is 1.76 GiB, and the pair is what breaks the
    budget.

See training/probe_27b.py for the measurement that settled the residency plan, and
docs/specs/qlora-upgrade.md 4.2 for the arithmetic it was checked against.

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
import gc
import json
import os
import pathlib

# Fragmentation is what bites at 95% card occupancy, and this costs nothing. Set before
# torch is imported, because the allocator reads it once at init.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

HERE = pathlib.Path(__file__).resolve().parent
# training/ sits at the repo root, so the root is ONE level up, not two. This said
# `HERE.parent.parent` until it was caught, which resolved to the directory *containing* the
# repo and sent every download to ~/models/hf -- outside the project, ungitignored, and
# invisible until you went looking for a 50 GB checkout that was never where it claimed.
# Same class of silent breakage as the repo-root calculation in scripts/fetch-models.sh, and
# the same fix: assert the answer instead of trusting the arithmetic.
ROOT = HERE.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root not found at {ROOT}"

# Keep every downloaded weight inside the project's models directory rather than scattering
# them through ~/.cache, so "where are the models" has one answer. That directory moved to
# backend/models/ in the backend restructure.
os.environ.setdefault("HF_HOME", str(ROOT / "backend" / "models" / "hf"))

BASE_MODEL = "Qwen/Qwen3.6-27B"

# Attention and MLP both. Attention-only adapters pick up style but are noticeably worse at
# absorbing facts, and half this corpus is facts.
TARGETS_DENSE = ["q_proj", "k_proj", "v_proj", "o_proj",
                 "gate_proj", "up_proj", "down_proj"]
# The hybrid's linear_attn layers project through in_proj_qkv/out_proj instead. in_proj_a and
# in_proj_b are deliberately absent: they are [48, 5120], so r=16 is a third of full rank on a
# 48-wide output. That is not a low-rank adaptation, it is a badly-conditioned dense one.
TARGETS_HYBRID = TARGETS_DENSE + ["in_proj_qkv", "out_proj"]


EMBED_KEY = "model.language_model.embed_tokens.weight"


def _install_cpu_embedding(model, base: str, device=0):
    """Run the embedding lookup on the CPU, returning a tensor on the GPU.

    A `device_map` entry of "cpu" does NOT do this, and the difference is the whole budget.
    accelerate's AlignDevicesHook copies the *entire* weight to the execution device before
    every forward -- measured here at 4.74 GiB, in fp32, because
    llm_int8_enable_fp32_cpu_offload upcasts CPU-placed modules. That OOMs the card the
    offload was supposed to save, at the first forward, after a four-minute load.

    A gather needs one row per token. Doing it here moves seq x 5120 x 2 bytes -- 6.8 MiB at
    the corpus's longest example -- and the 2.37 GiB table never lands on the card. This is
    the transaction 7.7 of docs/specs/qlora-upgrade.md does not rule out: 7.7 is about
    optimizer state crossing PCIe Gen 3 x8 every step, and this table is frozen, so no
    gradient crosses anything.
    """
    import torch

    class CPUEmbedding(torch.nn.Module):
        def __init__(self, weight, out_device, out_dtype=torch.bfloat16):
            super().__init__()
            self.weight = torch.nn.Parameter(weight.detach().to("cpu", out_dtype),
                                             requires_grad=False)
            self.out_device = out_device

        def forward(self, ids):
            return torch.nn.functional.embedding(
                ids.to("cpu"), self.weight).to(self.out_device)

    # The weight is read from its shard rather than from the loaded module: a device_map
    # entry of "cpu" leaves the parameter a *meta* tensor with the data in accelerate's
    # weights_map, so .to() on it raises "Cannot copy out of meta tensor; no data!".
    from safetensors import safe_open
    from transformers.utils import cached_file

    index = json.loads(pathlib.Path(cached_file(base, "model.safetensors.index.json")).read_text())
    with safe_open(cached_file(base, index["weight_map"][EMBED_KEY]),
                   framework="pt", device="cpu") as f:
        weight = f.get_tensor(EMBED_KEY)

    lang = model.model.language_model
    lang.embed_tokens = CPUEmbedding(weight, device)
    # If this ever stops resolving, enable_input_require_grads hooks the wrong module and
    # gradient checkpointing silently produces no gradient for the first layer.
    assert model.get_input_embeddings() is lang.embed_tokens, "embedding swap did not take"
    return model


def _prepare_kbit_keep_embeddings(model):
    """Freeze the base and upcast the norms to fp32 -- but not the embeddings.

    This is prepare_model_for_kbit_training with one line changed. PEFT casts *every*
    non-Params4bit bf16 parameter to fp32 (peft/utils/other.py:196-202); on the norms that is
    the QLoRA recipe and costs kilobytes, but on Qwen3.6's 248,320 x 5120 output embedding it
    is 2.37 -> 4.74 GiB and raises OutOfMemoryError inside the prepare call itself, with
    14.07 GiB already resident. Both embeddings are frozen and never receive a gradient, so
    fp32 buys no numerical stability here -- only the norms need it.

    The caller does the gradient_checkpointing_enable / enable_input_require_grads half.
    """
    import torch

    skip = set()
    for mod in (model.get_output_embeddings(), model.get_input_embeddings()):
        if mod is not None:
            skip.update(id(p) for p in mod.parameters(recurse=False))

    for p in model.parameters():
        p.requires_grad = False
        if p.dtype in (torch.float16, torch.bfloat16) and type(p).__name__ != "Params4bit":
            if id(p) not in skip:
                p.data = p.data.to(torch.float32)
    torch.cuda.empty_cache()
    return model


def _assert_checkpoint_covers(loader, cfg, base: str) -> None:
    """Refuse to train a model whose weights the checkpoint does not actually supply.

    Transformers reports a key mismatch as a warning, not an error, so picking the wrong
    class for a multimodal checkpoint costs an hour of GPU time and yields a randomly
    initialised model that trains and saves without complaint. Building on the meta device
    allocates nothing and reads no shard, so this check is effectively free.
    """
    import torch
    from transformers import AutoConfig  # noqa: F811
    from transformers.utils import cached_file

    try:
        index = cached_file(base, "model.safetensors.index.json")
    except Exception:
        return  # single-shard checkpoints have no index; nothing cheap to check against
    ckpt = set(json.loads(pathlib.Path(index).read_text())["weight_map"])

    klass = loader._model_mapping[type(cfg)]
    with torch.device("meta"):
        skeleton = klass(cfg)
    expected = set(dict(skeleton.named_parameters()))
    missing = expected - ckpt
    if missing:
        raise SystemExit(
            f"{klass.__name__} expects {len(expected)} parameters and the checkpoint supplies "
            f"{len(expected) - len(missing)} of them. {len(missing)} would be randomly "
            f"initialised, e.g. {sorted(missing)[:3]}. This is a wrong-class error, not a "
            f"corrupt download -- check the auto class against the checkpoint's key prefixes."
        )


_STREAMED_CE = None


def _streamed_loss_class():
    """Cross-entropy against an `lm_head` that is not on the card, chunked over the VOCAB.

    Why it exists: with the head resident in bf16 the 27B OOMs 22 MiB short *in the forward*,
    and neither a bf16 adapter nor a paged 8-bit optimizer moves that (measured: 0.08 GiB).
    Evicting the head returns 2.37 GiB and turns a ~0.3 GiB deficit into 1.17 GiB of driver
    headroom. See docs/specs/qlora-27b-measured.md.

    Chunked over the vocab, not over tokens: a vocab slice serves every token at once, so one
    sweep of the weight covers the whole sequence -- 2.37 GiB of PCIe per pass, two passes per
    micro-step. Chunking over tokens instead would drag the whole weight across for each chunk.
    Neither the full [T, 248320] logits nor the full weight is ever resident.

    forward  : online logsumexp (Milakov-Gimelshein rescaling) accumulates logZ in one sweep.
    backward : a second sweep rebuilds each slice's probabilities and accumulates
               grad_hidden = sum_j (p_j - onehot_j) @ W_j. The head is frozen, so there is no
               weight gradient to return.

    Verified against F.cross_entropy on CPU before it was ever run on the card: loss delta
    4.768e-07, grad delta 6.985e-10, over a ragged final chunk, a masked prefix, a target
    landing in the last chunk, and the single-chunk degenerate case.

    Built lazily so `import torch` stays inside the run path, after PYTORCH_CUDA_ALLOC_CONF.
    """
    global _STREAMED_CE
    if _STREAMED_CE is not None:
        return _STREAMED_CE
    import torch

    class StreamedCE(torch.autograd.Function):
        @staticmethod
        def forward(ctx, hidden, labels, weight_cpu, chunk):
            dev = hidden.device
            # Custom autograd Functions are excluded from autocast, so under Trainer's
            # bf16 the hidden states arrive fp32 (the final norm is fp32 after the kbit
            # prepare) while the head is bf16, and the matmul raises on the dtype mismatch.
            # Match the weight explicitly rather than depend on the caller's context, and
            # remember what came in -- autograd wants the gradient back in the input's dtype.
            in_dtype = hidden.dtype
            hidden = hidden.to(weight_cpu.dtype)
            T, V = hidden.shape[0], weight_cpu.shape[0]
            run_max = torch.full((T,), float("-inf"), device=dev, dtype=torch.float32)
            run_sum = torch.zeros(T, device=dev, dtype=torch.float32)
            tgt = torch.zeros(T, device=dev, dtype=torch.float32)

            for j0 in range(0, V, chunk):
                wj = weight_cpu[j0:j0 + chunk].to(dev, non_blocking=True)
                zj = (hidden @ wj.T).float()
                new_max = torch.maximum(run_max, zj.amax(dim=1))
                run_sum = run_sum * torch.exp(run_max - new_max) \
                    + torch.exp(zj - new_max[:, None]).sum(dim=1)
                run_max = new_max
                # -100 never falls in [j0, j0+chunk), so masked rows are simply never written.
                sel = (labels >= j0) & (labels < j0 + chunk)
                if bool(sel.any()):
                    rows = sel.nonzero(as_tuple=True)[0]
                    tgt[rows] = zj[rows, labels[rows] - j0].float()
                del zj, wj

            log_z = run_max + run_sum.log()
            valid = labels != -100
            n = valid.sum().clamp(min=1)
            loss = ((log_z - tgt) * valid).sum() / n

            ctx.save_for_backward(hidden, labels, log_z, valid)
            ctx.weight_cpu, ctx.chunk, ctx.n = weight_cpu, chunk, n
            ctx.in_dtype = in_dtype
            return loss

        @staticmethod
        def backward(ctx, grad_out):
            hidden, labels, log_z, valid = ctx.saved_tensors
            weight_cpu, chunk = ctx.weight_cpu, ctx.chunk
            dev = hidden.device
            V = weight_cpu.shape[0]
            row_scale = (valid.float() * (grad_out / ctx.n))[:, None]
            grad_hidden = torch.zeros_like(hidden, dtype=torch.float32)

            for j0 in range(0, V, chunk):
                wj = weight_cpu[j0:j0 + chunk].to(dev, non_blocking=True)
                pj = torch.exp((hidden @ wj.T).float() - log_z[:, None])
                sel = (labels >= j0) & (labels < j0 + chunk)
                if bool(sel.any()):
                    rows = sel.nonzero(as_tuple=True)[0]
                    pj[rows, labels[rows] - j0] -= 1.0
                grad_hidden += (pj * row_scale).to(wj.dtype) @ wj
                del pj, wj

            return grad_hidden.to(ctx.in_dtype), None, None, None

    _STREAMED_CE = StreamedCE
    return StreamedCE


def _evict_lm_head(model):
    """Move `lm_head` to pinned CPU bf16 and empty its GPU storage. Returns the CPU copy.

    Emptying the storage in place, rather than dropping the module, is what actually returns
    the memory. Swapping in an Identity and deleting the local freed *nothing* (measured:
    -0.19 GiB, i.e. the allocation went up by the adapter and the head stayed resident),
    because other references survive -- locals here, and accelerate's hooks. Zeroing the
    storage does not care who else is pointing at the module.
    """
    import torch

    inner = model.get_base_model() if hasattr(model, "get_base_model") else model
    head = inner.lm_head
    head_cpu = head.weight.detach().to("cpu", torch.bfloat16).pin_memory()
    before = torch.cuda.memory_allocated()
    head.weight.data = torch.empty(0, device=head.weight.device, dtype=head.weight.dtype)
    # With an Identity here the model returns hidden states in the `logits` slot, which is
    # what lets the head be applied a slice at a time. The head is frozen and is not a LoRA
    # target, so nothing trainable is bypassed by the swap.
    inner.lm_head = torch.nn.Identity()
    del head
    gc.collect()
    torch.cuda.empty_cache()
    freed = before - torch.cuda.memory_allocated()
    print(f"lm_head streamed from CPU: {freed / 2**30:.2f} GiB freed on the card")
    if freed < 2.0 * 2**30:
        raise SystemExit(
            f"lm_head did not leave the GPU ({freed / 2**30:.2f} GiB freed, expected ~2.37). "
            "Something still holds a reference to its storage; training would OOM in the "
            "forward pass of layer 0 rather than here.")
    return head_cpu


def _streamed_head_trainer_class(Trainer):
    """Trainer for the hybrid 27B, whose `lm_head` is no longer on the card.

    `_evict_lm_head` leaves an Identity in the head's place, so the model's `logits` are
    hidden states and passing `labels=` would compute cross-entropy against the wrong tensor
    entirely. The loss is computed here instead. Everything else -- scheduler, accumulation,
    checkpointing, saving -- is stock Trainer.
    """

    class StreamedHeadTrainer(Trainer):
        def __init__(self, *a, head_cpu=None, vocab_chunk=16384, **kw):
            super().__init__(*a, **kw)
            self.head_cpu = head_cpu
            self.vocab_chunk = vocab_chunk
            # PeftModel.forward takes **kwargs, so Trainer's signature sniff concludes the
            # model accepts loss kwargs and stops dividing by gradient_accumulation_steps --
            # it then expects a sum the caller normalises. compute_loss returns a mean, so
            # leaving this True multiplies the effective learning rate by 8.
            self.model_accepts_loss_kwargs = False

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            if labels.shape[0] != 1:
                raise SystemExit("the streamed head assumes per_device_train_batch_size=1; "
                                 f"got a batch of {labels.shape[0]}")
            row = labels[0]
            answered = (row != -100).nonzero(as_tuple=True)[0]
            if answered.numel() == 0:
                raise SystemExit("an example has no unmasked label position")
            i0 = int(answered[0])
            if i0 == 0:
                raise SystemExit("the answer starts at position 0, so nothing precedes it to "
                                 "predict from -- encode() should always emit a prompt first")
            # Position t predicts token t+1, so predicting labels[i0:] needs hidden states
            # [i0-1 : T-1] -- the last (T-i0)+1 of them, minus the final one, which would
            # predict past the end of the sequence.
            T = row.shape[0]
            keep = T - i0 + 1
            out = model(input_ids=inputs["input_ids"],
                        attention_mask=inputs.get("attention_mask"),
                        logits_to_keep=keep)
            hidden = out.logits[0, :-1]
            # If logits_to_keep were dropped anywhere on the way through PEFT's forward
            # wrapper it would default to 0 -- slice(0, None), every position -- and the
            # labels would silently misalign against a loss that still looks plausible.
            if hidden.shape[0] != T - i0:
                raise SystemExit(f"logits_to_keep ignored: got {hidden.shape[0]} positions, "
                                 f"want {T - i0}")
            loss = _streamed_loss_class().apply(
                hidden, row[i0:], self.head_cpu, self.vocab_chunk)
            return (loss, out) if return_outputs else loss

    return StreamedHeadTrainer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(HERE / "corpus.jsonl"))
    ap.add_argument("--out", default=None,
                    help="default is adapter/ for the 7B and adapter-qwen36/ for the 27B -- "
                         "they are NOT interchangeable, and backend/api.py serves adapter/")
    ap.add_argument("--base", default=BASE_MODEL)
    ap.add_argument("--epochs", type=float, default=3.0)
    # The corpus was measured, not guessed, under both tokenizers: 327 examples, max 665
    # tokens on Qwen2.5 and 662 on Qwen3.6. 768 truncates nothing under either; 1024 buys no
    # coverage. This only ever truncates -- batch size is 1 and the collator pads to the
    # longest row in the batch, so a short example costs short-example activations.
    ap.add_argument("--seq-len", type=int, default=768)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoConfig, AutoModelForCausalLM, AutoModelForImageTextToText,
                              AutoTokenizer, BitsAndBytesConfig, DataCollatorForSeq2Seq,
                              Trainer, TrainingArguments)

    cfg = AutoConfig.from_pretrained(args.base)
    # A multimodal wrapper keeps the causal-LM shape under text_config, not at the top level.
    text_cfg = getattr(cfg, "text_config", cfg)
    hybrid = getattr(text_cfg, "full_attention_interval", None) is not None
    if args.out is None:
        args.out = str(HERE / ("adapter-qwen36" if hybrid else "adapter"))

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

    quant = dict(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    device_map = {"": 0}
    if hybrid:
        # Leave bitsandbytes' default skip list alone: lm_head stays bf16. Quantising it
        # looks like a 1.76 GiB saving and measured as a net loss -- bnb's 4-bit backward
        # ALWAYS dequantises the whole weight (autograd/_functions.py:384), and the forward
        # falls back to the same for M > 1536 tokens. At a 248,320 vocab that transient is
        # 2.37 GiB, which is more than the residency it saves, and it OOMs at step 0.
        # Measured: docs/specs/qlora-27b-measured.md, trap 3.
        quant["llm_int8_skip_modules"] = ["lm_head"]
        # Required before accelerate will honour a "cpu" entry in device_map below.
        quant["llm_int8_enable_fp32_cpu_offload"] = True
        # 7.7 of the spec says CPU offload is not a rescue, and for optimizer state crossing
        # PCIe Gen 3 x8 every step that is exactly right. An embedding lookup is a gather
        # with no gradient and one 13 MB transfer per step, so it is not that transaction.
        # The vision tower is frozen and never called at all on a text-only corpus.
        device_map = {
            "model.visual": "cpu",
            "model.language_model.embed_tokens": "cpu",
            "model.language_model.layers": 0,
            "model.language_model.norm": 0,
            "model.language_model.rotary_emb": 0,
            "lm_head": 0,
        }

    # AutoModelForCausalLM is the WRONG entry point for the 27B and it fails *silently*. It
    # maps Qwen3_5Config -> Qwen3_5ForCausalLM, whose parameters are named model.layers.*
    # while the checkpoint ships model.language_model.layers.*. Measured on the real
    # checkpoint, that class matches 1 of its 853 tensors and random-initialises the other
    # 852 -- and with a plain device_map={"": 0} nothing raises. You get a missing-keys
    # warning in a wall of loading output and an hour spent fine-tuning noise.
    # AutoModelForImageTextToText maps to Qwen3_5ForConditionalGeneration, which matches every
    # weight in the checkpoint (3 rotary inv_freq buffers are computed, not loaded; the 15
    # mtp.* tensors are unused by this class and dropped).
    loader = AutoModelForImageTextToText if hybrid else AutoModelForCausalLM
    _assert_checkpoint_covers(loader, cfg, args.base)
    model = loader.from_pretrained(
        args.base,
        quantization_config=BitsAndBytesConfig(**quant),
        dtype=torch.bfloat16,
        device_map=device_map,
    )
    if hybrid:
        _install_cpu_embedding(model, args.base)
    model.config.use_cache = False
    if hybrid:
        # NOT prepare_model_for_kbit_training: it casts every non-Params4bit bf16 parameter
        # to fp32 (peft/utils/other.py:196-202). On the norms that is the QLoRA recipe and
        # costs kilobytes; on a 248,320 x 5120 output embedding it is 2.37 -> 4.74 GiB and
        # OOMs the load outright, with 14.07 GiB already resident. Measured:
        # docs/specs/qlora-27b-measured.md, trap 4. The embeddings are frozen and never see
        # a gradient, so fp32 buys no stability here.
        _prepare_kbit_keep_embeddings(model)
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    else:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=TARGETS_HYBRID if hybrid else TARGETS_DENSE,
    )
    if hybrid:
        # autocast_adapter_dtype=True (the default) puts the 100M adapter params in fp32.
        # At this size that is 0.19 GiB against 1.17 GiB of headroom -- affordable, but it
        # buys nothing here: the base compute dtype is bf16 either way, and the optimizer is
        # paged 8-bit. The 7B path keeps the default, because that is what produced the
        # shipped adapter and there is no reason to re-roll it.
        model = get_peft_model(model, lora, autocast_adapter_dtype=False)
    else:
        model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    # print_trainable_parameters reports a total, which cannot tell a fully-adapted model from
    # one where 48 of 64 layers were never matched. Count the sites instead, and refuse to
    # spend an hour of GPU time producing a quarter-adapted adapter.
    sites = [n for n, _ in model.named_parameters() if n.endswith("lora_A.default.weight")]
    n_lin = sum(1 for n in sites if "linear_attn" in n)
    print(f"adapted sites: {len(sites)} total, {n_lin} on linear_attn layers")
    if hybrid and n_lin == 0:
        raise SystemExit("target_modules matched no linear_attn layer -- 48 of 64 layers "
                         "would train nothing. Check TARGETS_HYBRID against the checkpoint.")

    # The head comes off the card AFTER the adapter is attached: get_peft_model walks the
    # module tree, and the eviction leaves an Identity where lm_head was.
    trainer_cls, trainer_kw = Trainer, {}
    if hybrid:
        trainer_cls = _streamed_head_trainer_class(Trainer)
        trainer_kw = {"head_cpu": _evict_lm_head(model)}

    trainer = trainer_cls(
        model=model,
        train_dataset=ds,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
        **trainer_kw,
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
    print("next: contrib/llama.cpp/convert_lora_to_gguf.py --base <base> --outtype f16 "
          f"{out}")
    if hybrid:
        # The converter resolves the architecture from the top-level "architectures" key,
        # because Qwen3.6's text_config has no architectures of its own -- and
        # Qwen3_5ForConditionalGeneration is registered for both the text and mmproj paths
        # (conversion/__init__.py:225, :321). Checked before training, not after.
        print("      then serve with llama-server --lora; note the serving base is a Q2_K_XL\n"
              "      GGUF while this adapter was trained against NF4, which is a wider\n"
              "      quantisation gap than the 7B's NF4 -> Q4_K_M and is not yet evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
