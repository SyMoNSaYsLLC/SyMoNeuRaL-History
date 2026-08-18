#!/usr/bin/env python3
"""Measure -- do not project -- the QLoRA footprint of Qwen3.6-27B on this card.

docs/specs/qlora-upgrade.md 4.2 projects 12.31 GiB of weights for the plan below and
~15.4 GiB peak once LoRA, logits and checkpointed activations are added. The card has
15,620 MiB free. A projection whose error bars straddle the answer is not an answer, so
this loads the thing and reads torch.cuda.max_memory_allocated().

Everything this prints is MEASURED on this machine.

Run it under the governor, which is the only way to touch the card:

    scripts/gpu-governor.sh with train -- training/.venv/bin/python training/probe_27b.py

The plan under test ("D" in the projection):
  * vision tower on CPU -- Qwen3.6 is multimodal and config.language_model_only is a Qwen
    knob transformers does not read, so the tower gets built regardless. It is placed, not
    prevented. (mtp is never built: ForConditionalGeneration has no such attribute, so
    those 15 checkpoint tensors are simply unexpected and dropped.)
  * lm_head quantised -- bitsandbytes skips it by default, and at a 248,320 vocab that
    default costs 1.76 GiB.
  * embed_tokens on CPU -- 7.7 says CPU offload is not a rescue, and for optimizer state
    crossing PCIe every step that is right. An embedding lookup is a gather with no
    gradient, so it is not the transaction 7.7 rules out.

Each of those three is a --flag, so the ladder can be measured rung by rung rather than
asserted.
"""
import argparse
import gc
import json
import os
import sys
from pathlib import Path

# Fragmentation is what bites at 95% occupancy, and this costs nothing.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert (ROOT / "backend" / "api.py").is_file(), f"repo root wrong: {ROOT}"
os.environ.setdefault("HF_HOME", str(ROOT / "backend" / "models" / "hf"))

import torch  # noqa: E402  (after HF_HOME)
from transformers import AutoConfig, AutoModelForImageTextToText, BitsAndBytesConfig  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402

MODEL = "Qwen/Qwen3.6-27B"
GIB = 1024 ** 3

# 48 of 64 layers are linear_attn and carry no q/k/v/o_proj; only 16 are full self_attn.
# The 7B's target list reaches attention in 16 layers here and misses the other 48
# entirely -- which produces no error, just a quarter-adapted model.
TARGETS_7B = ["q_proj", "k_proj", "v_proj", "o_proj",
              "gate_proj", "up_proj", "down_proj"]
TARGETS_HYBRID = TARGETS_7B + ["in_proj_qkv", "out_proj"]
# in_proj_a / in_proj_b are [48, 5120]: r=16 is a third of full rank on a 48-wide output,
# which is not a low-rank adaptation but a badly-conditioned dense one. Left out.


def gib(n):
    return n / GIB


class CPUEmbedding(torch.nn.Module):
    """Embedding lookup executed on the CPU, returning a tensor on the GPU.

    accelerate's device_map offload does NOT do this, and the difference is the whole
    budget. Its AlignDevicesHook copies the *entire* weight to the execution device before
    every forward -- measured here at 4.74 GiB, in fp32 (llm_int8_enable_fp32_cpu_offload
    upcasts CPU-placed modules), which OOMs the card the offload was supposed to save.

    A gather needs one row per token. Doing it here moves seq x 5120 x 2 bytes -- 6.8 MiB at
    the corpus's longest example -- instead of 4.74 GiB, and the weight never lands on the
    card at all. This is the transaction 7.7 of the spec does not rule out: no gradient
    crosses PCIe, because the table is frozen.
    """

    def __init__(self, weight: torch.Tensor, out_device, out_dtype=torch.bfloat16):
        super().__init__()
        self.weight = torch.nn.Parameter(weight.detach().to("cpu", out_dtype),
                                         requires_grad=False)
        self.out_device = out_device

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.embedding(
            ids.to("cpu"), self.weight).to(self.out_device)


EMBED_KEY = "model.language_model.embed_tokens.weight"


def chunked_ce(head, hidden, labels, chunk):
    """Cross-entropy that never materialises [T, 248320] logits.

    The stock path builds the full logits tensor, a fp32 copy of it, and a fp32 gradient of
    it -- at the corpus's longest answer that is ~1.34 GiB of transient for a scalar. Here
    each chunk's logits are built inside torch.utils.checkpoint and thrown away; backward
    recomputes them one chunk at a time, so peak is one chunk's worth.

    Summed, not averaged, per chunk: chunks have different numbers of unmasked tokens, so a
    mean of means is not the mean. Divided once at the end by the true unmasked count.
    """
    def one(h, y):
        return torch.nn.functional.cross_entropy(head(h).float(), y, reduction="sum")

    total = None
    for i in range(0, hidden.shape[0], chunk):
        part = torch.utils.checkpoint.checkpoint(
            one, hidden[i:i + chunk], labels[i:i + chunk], use_reentrant=False)
        total = part if total is None else total + part
    return total / (labels != -100).sum().clamp(min=1)


def load_embedding_weight(base: str) -> "torch.Tensor":
    """Read the embedding straight out of its shard.

    Not from the loaded module: a device_map entry of "cpu" leaves the parameter as a *meta*
    tensor with the real data in accelerate's weights_map ("Some parameters are on the meta
    device because they were offloaded to the cpu"), so `.to()` on it raises. Going to the
    file is both simpler and independent of accelerate's offload internals.
    """
    from safetensors import safe_open
    from transformers.utils import cached_file

    index = json.loads(Path(cached_file(base, "model.safetensors.index.json")).read_text())
    shard = cached_file(base, index["weight_map"][EMBED_KEY])
    with safe_open(shard, framework="pt", device="cpu") as f:
        return f.get_tensor(EMBED_KEY)


def install_cpu_embedding(model, base: str, device=0):
    """Swap embed_tokens for the shim, dropping whatever hook accelerate attached to it."""
    lang = model.model.language_model
    lang.embed_tokens = CPUEmbedding(load_embedding_weight(base), device)
    return model


class StreamedCE(torch.autograd.Function):
    """Cross-entropy against an output embedding that never lives on the GPU.

    lm_head is 248,320 x 5120. Resident bf16 that is 2.37 GiB, and measurement says the run
    is ~0.3 GiB short in the forward alone with it there -- so it has to go, and NF4 cannot
    take its place (bitsandbytes dequantises the whole weight in backward regardless of the
    forward kernel; see trap 3).

    The head is frozen, so no weight gradient is ever needed -- only grad wrt hidden. That is
    what makes streaming sound: the weight is a constant that can be visited in slices.

    Chunked over the VOCAB, not over tokens. A vocab slice serves every token at once, so one
    sweep of the weight covers the whole sequence: 2.37 GiB of PCIe per pass, two passes per
    micro-step. Chunking over tokens instead would drag the whole weight across for each
    chunk. Neither the full [T, 248320] logits nor the full weight is ever resident.

    forward  : online logsumexp (Milakov-Gimelshein rescaling) accumulates logZ in one sweep.
    backward : a second sweep rebuilds each slice's probabilities and accumulates
               grad_hidden = sum_j (p_j - onehot_j) @ W_j.
    """

    @staticmethod
    def forward(ctx, hidden, labels, weight_cpu, chunk):
        dev = hidden.device
        # Custom autograd Functions are excluded from autocast, so under a bf16 autocast
        # (which is what Trainer runs) the hidden states arrive fp32 -- the final norm is
        # fp32 after the kbit prepare -- while the head is bf16, and the matmul raises on
        # the mismatch. Match the weight explicitly rather than depend on the caller, and
        # remember what came in: autograd wants the gradient back in the input's dtype.
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
            # -100 never falls in [j0, j0+chunk), so masked rows simply never get written.
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


def prepare_kbit_keep_embeddings(model):
    """prepare_model_for_kbit_training, minus its blanket bf16 -> fp32 upcast.

    PEFT casts *every* non-Params4bit bf16 parameter to fp32 (peft/utils/other.py:196-202).
    On the norms that is the QLoRA recipe and costs kilobytes. On a 248,320 x 5120 output
    embedding it is 2.37 -> 4.74 GiB, and it OOMs the load before a step exists -- measured,
    with 14.07 GiB already resident. The embeddings are frozen and never receive a gradient,
    so there is nothing here for fp32 to stabilise.

    The rest of what that function does -- freezing the base, enable_input_require_grads,
    gradient_checkpointing_enable -- is done explicitly by the caller.
    """
    skip = set()
    for mod in (model.get_output_embeddings(), model.get_input_embeddings()):
        if mod is not None:
            skip.update(id(p) for p in mod.parameters(recurse=False))

    upcast = held = 0
    for p in model.parameters():
        p.requires_grad = False
        if p.dtype in (torch.float16, torch.bfloat16) and type(p).__name__ != "Params4bit":
            if id(p) in skip:
                held += p.numel()
                continue
            p.data = p.data.to(torch.float32)
            upcast += p.numel()
    torch.cuda.empty_cache()
    print(f"upcast to fp32: {upcast:,} params; left bf16: {held:,} (embeddings)")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--seq", type=int, default=665,
                    help="longest example in the corpus; peak is set by the longest "
                         "sequence because batch is 1 and nothing is padded")
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--vision-cpu", action="store_true", default=True)
    ap.add_argument("--vision-gpu", dest="vision_cpu", action="store_false")
    ap.add_argument("--embed-cpu", action="store_true", default=True)
    ap.add_argument("--embed-gpu", dest="embed_cpu", action="store_false")
    ap.add_argument("--quant-lm-head", action="store_true", default=True)
    ap.add_argument("--keep-lm-head", dest="quant_lm_head", action="store_false")
    ap.add_argument("--targets", choices=("hybrid", "7b"), default="hybrid")
    ap.add_argument("--ans", type=int, default=578,
                    help="answer tokens in the worst-case example, measured from the "
                         "corpus. Only these carry a label; the prompt is masked to -100, "
                         "so only these need to reach lm_head. They are the TRAILING "
                         "segment, which is what makes logits_to_keep exact rather than "
                         "approximate.")
    ap.add_argument("--loss", choices=("streamed", "chunked", "stock"), default="streamed")
    ap.add_argument("--loss-chunk", type=int, default=128,
                    help="tokens per chunk, --loss chunked")
    ap.add_argument("--vocab-chunk", type=int, default=16384,
                    help="vocab rows per slice, --loss streamed. 16384 rows is 168 MiB of "
                         "weight and a [T, 16384] fp32 slab, so ~0.2 GiB live at a time.")
    ap.add_argument("--adapter-dtype", choices=("bf16", "fp32"), default="bf16",
                    help="PEFT's autocast_adapter_dtype defaults to fp32 adapters. At 100M "
                         "trainable that is 0.37 GiB of weights plus 0.37 of gradient; bf16 "
                         "halves both, and the compute dtype is bf16 either way.")
    ap.add_argument("--optim", choices=("paged8bit", "adamw"), default="paged8bit",
                    help="paged8bit is what train_lora.py actually uses. Plain AdamW keeps "
                         "two fp32 moments -- 8 bytes per trainable param -- and measuring "
                         "with it would price an optimizer the run does not use.")
    args = ap.parse_args()

    free, total = torch.cuda.mem_get_info()
    print(f"card: {gib(total):.2f} GiB total, {gib(free):.2f} GiB free at start")
    print(f"plan: vision={'cpu' if args.vision_cpu else 'gpu'} "
          f"embed={'cpu' if args.embed_cpu else 'gpu'} "
          f"lm_head={'nf4' if args.quant_lm_head else 'bf16'} "
          f"r={args.rank} seq={args.seq} ans={args.ans} targets={args.targets} "
          f"loss={args.loss}\n")

    cfg = AutoConfig.from_pretrained(MODEL)
    text = cfg.text_config

    device_map = {
        "model.visual": "cpu" if args.vision_cpu else 0,
        "model.language_model.embed_tokens": "cpu" if args.embed_cpu else 0,
        "model.language_model.layers": 0,
        "model.language_model.norm": 0,
        "model.language_model.rotary_emb": 0,
        "lm_head": 0,
    }

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        # Default is ["lm_head"]. At a 248,320-token vocab that default is 1.76 GiB.
        llm_int8_skip_modules=[] if args.quant_lm_head else ["lm_head"],
        # Required before accelerate will honour a "cpu" entry in device_map.
        llm_int8_enable_fp32_cpu_offload=True,
    )

    # AutoModelForCausalLM is the WRONG entry point here and fails silently. It maps
    # Qwen3_5Config -> Qwen3_5ForCausalLM, whose parameters are named model.layers.* while the
    # checkpoint ships model.language_model.layers.*; measured, that class matches 1 of its 853
    # tensors and random-initialises the other 852. With device_map={"": 0} there is no error
    # at all -- just a missing-keys warning and an hour spent training noise.
    # AutoModelForImageTextToText maps to Qwen3_5ForConditionalGeneration, which matches
    # every weight in the checkpoint.
    print("loading (55.6 GiB off disk, quantising as it goes -- minutes, not seconds)")
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL, config=cfg, quantization_config=quant,
        device_map=device_map, dtype=torch.bfloat16,
    )
    assert type(model).__name__ == "Qwen3_5ForConditionalGeneration", type(model).__name__
    if args.embed_cpu:
        install_cpu_embedding(model, MODEL, 0)
    model.config.use_cache = False
    after_load = torch.cuda.memory_allocated()
    print(f"\nweights resident: {gib(after_load):.2f} GiB "
          f"({gib(torch.cuda.max_memory_allocated()):.2f} GiB peak during load)")

    # ---- verify the plan actually happened, rather than trusting the flags -----------
    import bitsandbytes as bnb

    checks = []
    lm_head = model.get_output_embeddings()
    is4 = isinstance(lm_head, bnb.nn.Linear4bit)
    checks.append(("lm_head is Linear4bit", is4 == args.quant_lm_head,
                   f"{type(lm_head).__name__}"))

    devs = {}
    for name, p in model.named_parameters():
        devs.setdefault(str(p.device), 0)
        devs[str(p.device)] += p.numel()
    print("\nparameters by device (numel, pre-LoRA -- 4-bit params count as uint8 halves):")
    for d, n in sorted(devs.items()):
        print(f"  {d:<8} {n:>16,}")

    vis = [p for n, p in model.named_parameters() if n.startswith("model.visual")]
    # "not on cuda", not "on cpu": accelerate leaves offloaded params as *meta* tensors with
    # the real data in its weights_map, so a device.type == "cpu" test fails a tower that is
    # in fact costing zero VRAM. The question this check exists to answer is only ever
    # whether the tower is on the card.
    vis_devs = sorted({str(p.device) for p in vis})
    checks.append(("vision tower off the GPU",
                   all(p.device.type != "cuda" for p in vis) == args.vision_cpu,
                   f"{len(vis)} tensors, {sum(p.numel() for p in vis):,} numel, on {vis_devs}"))

    emb_mod = model.model.language_model.embed_tokens
    emb = emb_mod.weight
    checks.append(("embed_tokens off the GPU",
                   (emb.device.type == "cpu") == args.embed_cpu,
                   f"{type(emb_mod).__name__} on {emb.device}, {emb.numel():,} numel, {emb.dtype}"))
    # enable_input_require_grads hooks whatever this resolves to; if the swap did not take,
    # gradient checkpointing silently stops producing gradients for the first layer.
    checks.append(("get_input_embeddings sees the shim",
                   (model.get_input_embeddings() is emb_mod),
                   type(model.get_input_embeddings()).__name__))

    # ---- LoRA ------------------------------------------------------------------------
    model = prepare_kbit_keep_embeddings(model)
    # The upcast is the thing that bites here -- checked AFTER the call, not before: an
    # fp32 lm_head at this vocab is 4.74 GiB, not 2.37 -- the difference between fitting
    # and not.
    head_after = model.get_output_embeddings()
    head_dtype = getattr(head_after, "weight", None)
    head_dtype = head_dtype.dtype if head_dtype is not None else None
    checks.append(("lm_head still bf16 after prepare",
                   args.quant_lm_head or head_dtype == torch.bfloat16,
                   f"{type(head_after).__name__} weight {head_dtype}"))

    targets = TARGETS_HYBRID if args.targets == "hybrid" else TARGETS_7B
    model = get_peft_model(model, LoraConfig(
        r=args.rank, lora_alpha=args.rank * 2, lora_dropout=0.05,
        bias="none", task_type="CAUSAL_LM", target_modules=targets,
    ), autocast_adapter_dtype=(args.adapter_dtype == "fp32"))
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    adapted = sorted({n.rsplit(".lora_A", 1)[0].rsplit(".", 1)[-1]
                      for n, _ in model.named_parameters() if ".lora_A." in n})
    n_adapted = sum(1 for n, _ in model.named_parameters() if ".lora_A." in n and n.endswith(".weight"))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nadapted module kinds: {adapted}")
    print(f"adapted sites: {n_adapted}   trainable params: {trainable:,}")
    # Every linear_attn layer must be reached, or 48 of 64 layers get no adapter at all
    # and nothing anywhere reports an error.
    n_lin = sum(1 for n, _ in model.named_parameters()
                if ".lora_A." in n and "linear_attn" in n and n.endswith(".weight"))
    checks.append(("linear_attn layers reached",
                   (n_lin > 0) == (args.targets == "hybrid"),
                   f"{n_lin} linear_attn sites adapted"))

    # ---- two micro-steps at the worst-case length ------------------------------------
    # Worst case is one example: batch is 1 and nothing is padded, so the longest sequence
    # in the corpus sets the peak. seq=662 total, ans=578 of them the assistant turn.
    torch.cuda.reset_peak_memory_stats()
    ids = torch.randint(0, text.vocab_size, (1, args.seq))
    trainable_ps = [p for p in model.parameters() if p.requires_grad]
    if args.optim == "paged8bit":
        import bitsandbytes.optim as bnb_optim
        opt = bnb_optim.PagedAdamW8bit(trainable_ps, lr=1e-4)
    else:
        opt = torch.optim.AdamW(trainable_ps, lr=1e-4)
    adapter_dtypes = {str(p.dtype) for p in trainable_ps}
    want_dtype = {"bf16": "torch.bfloat16", "fp32": "torch.float32"}[args.adapter_dtype]
    checks.append(("adapter dtype as asked", adapter_dtypes == {want_dtype},
                   f"{sorted(adapter_dtypes)}"))
    model.train()

    inner = model.get_base_model() if hasattr(model, "get_base_model") else model
    head = inner.lm_head
    head_cpu = None
    if args.loss in ("chunked", "streamed"):
        # Identity in place of the head makes forward return hidden states in the logits
        # slot, so the head can be applied a piece at a time instead. The head is frozen and
        # is not a LoRA target, so nothing is bypassed by the swap.
        if args.loss == "streamed":
            head_cpu = head.weight.detach().to("cpu", torch.bfloat16).pin_memory()
            # Emptying the storage in place, rather than just dropping the module, is what
            # actually returns the 2.37 GiB. Swapping in an Identity and deleting the local
            # freed nothing (measured: -0.19 GiB, i.e. the adapter, and the head still
            # resident) because other references survive -- the dtype check above holds one,
            # and accelerate's hooks hold more. Zeroing the storage does not care who else
            # is pointing at the module.
            before_free = torch.cuda.memory_allocated()
            head.weight.data = torch.empty(
                0, device=head.weight.device, dtype=head.weight.dtype)
        inner.lm_head = torch.nn.Identity()
        if args.loss == "streamed":
            del head
            gc.collect()
            torch.cuda.empty_cache()
            # Diffed across the free itself, not against after_load: after_load predates the
            # norm upcast and the adapter, so it would conflate three separate deltas and
            # the gate below would pass or fail for the wrong reason.
            freed = before_free - torch.cuda.memory_allocated()
            print(f"lm_head off the card: {gib(freed):.2f} GiB freed, "
                  f"{gib(torch.cuda.memory_allocated()):.2f} GiB resident")
            checks.append(("lm_head actually left the GPU", freed > 2.0 * GIB,
                           f"{gib(freed):.2f} GiB freed"))

    for step in range(args.steps):
        x = ids.to(0)
        if args.loss in ("chunked", "streamed"):
            # position t predicts token t+1, so predicting the last `ans` tokens needs the
            # last ans+1 hidden states, minus the final one (which predicts past the end).
            keep = args.ans + 1
            hidden = model(input_ids=x, logits_to_keep=keep).logits[0, :-1]
            # If logits_to_keep were dropped anywhere on the way through PEFT's forward
            # wrapper it would default to 0 -- slice(0, None), i.e. every position -- and
            # the labels below would silently misalign by (seq - ans) tokens against a loss
            # that still looks plausible. Assert the shape rather than trust the kwarg.
            assert hidden.shape[0] == args.ans, (
                f"logits_to_keep ignored: got {hidden.shape[0]} positions, want {args.ans}")
            labels = x[0, -args.ans:]
            loss = (StreamedCE.apply(hidden, labels, head_cpu, args.vocab_chunk)
                    if args.loss == "streamed"
                    else chunked_ce(head, hidden, labels, args.loss_chunk))
        else:
            labels = x.clone()
            labels[0, :-args.ans] = -100      # prompt is masked, exactly as encode() does
            loss = model(input_ids=x, labels=labels).loss
        loss.backward()
        opt.step()
        opt.zero_grad(set_to_none=True)
        print(f"  step {step}: loss {loss.item():.4f}  "
              f"allocated {gib(torch.cuda.memory_allocated()):.2f} GiB  "
              f"peak {gib(torch.cuda.max_memory_allocated()):.2f} GiB")

    peak = torch.cuda.max_memory_allocated()
    reserved = torch.cuda.max_memory_reserved()
    free_now, _ = torch.cuda.mem_get_info()

    # The CUDA context is not in memory_allocated() -- the earlier runs showed a steady
    # ~0.33 GiB between "allocated by PyTorch" and "in use". Judge the fit on what the
    # driver says is left, not on the allocator's own total.
    used_real = total - free_now
    print(f"\n{'='*66}")
    print(f"MEASURED peak allocated : {gib(peak):>6.2f} GiB")
    print(f"MEASURED peak reserved  : {gib(reserved):>6.2f} GiB   (what the card must hold)")
    print(f"driver-reported in use  : {gib(used_real):>6.2f} GiB   (includes CUDA context)")
    print(f"card total              : {gib(total):>6.2f} GiB")
    print(f"headroom on reserved    : {gib(total - reserved):>6.2f} GiB")
    print(f"headroom, driver        : {gib(free_now):>6.2f} GiB")
    print(f"{'='*66}")
    checks.append(("fits with the context counted", free_now > 0,
                   f"{gib(free_now):.2f} GiB free at peak"))

    print("\nplan assertions:")
    ok = True
    for label, passed, detail in checks:
        print(f"  [{'ok ' if passed else 'FAIL'}] {label:<28} {detail}")
        ok &= passed

    summary = {
        "model": MODEL, "rank": args.rank, "seq": args.seq, "targets": args.targets,
        "vision_cpu": args.vision_cpu, "embed_cpu": args.embed_cpu,
        "quant_lm_head": args.quant_lm_head, "ans": args.ans,
        "loss": args.loss, "loss_chunk": args.loss_chunk,
        "free_at_peak_gib": round(gib(free_now), 3),
        "weights_resident_gib": round(gib(after_load), 3),
        "peak_allocated_gib": round(gib(peak), 3),
        "peak_reserved_gib": round(gib(reserved), 3),
        "card_total_gib": round(gib(total), 3),
        "trainable_params": trainable, "adapted_sites": n_adapted,
        "linear_attn_sites": n_lin, "checks_passed": bool(ok),
    }
    out_path = ROOT / "run" / "probe_27b.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nwritten to {out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
