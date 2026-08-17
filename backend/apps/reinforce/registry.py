"""SyMoNeuRaL Reinforce -- the model registry and the VRAM arithmetic behind the picker.

The owner's complaint was that the training surface *"doesn't even give a place to load the
model"*. This module is that place: it enumerates what is genuinely on this box, reads the
shape of each candidate out of the file itself, and derives -- rather than looks up -- what a
run would cost in VRAM.

## Two rules this file exists to enforce

**Scan, never hardcode.** A hardcoded model table goes stale the first time somebody drops a
directory into the cache. Every row below is produced by reading `config.json` (HF format) or
the GGUF key/value header (llama.cpp format) off disk. If the file is not there, the row is
not there.

**Derive, never look up.** `plan_fit()` computes the memory cost from the architecture
numbers just read, using the four-term model in §4.2 of `docs/specs/qlora-upgrade.md`. That
means a model nobody anticipated still gets an honest estimate, and it means the estimate
moves when the preset moves.

## Labelling, which is the product and not decoration

`.claude/CLAUDE.md`: *"Label every figure: measured on this machine, vendor specification, or
projected arithmetic. Never present a projection as a result."* Every figure this module
emits carries a `label` field, and the three values are used strictly:

* **measured** -- read off this box right now. File sizes, quantisation types, tensor counts,
  parameter counts derived from real tensor shapes, free VRAM from the driver.
* **vendor** -- a published figure from somebody else's paper or docs. Exactly one is used
  here: **4.127 bits/parameter** for 4-bit NF4 with double quantisation, from the QLoRA paper
  (Dettmers et al., arXiv:2305.14314 §3). It is not measured here and is not called measured.
* **projected** -- arithmetic. Every peak-VRAM number is projected until a run records a real
  `torch.cuda.max_memory_allocated()` for that exact (model x preset) pair, at which point
  `jobs.measured_peaks()` supplies the measured value for *that cell only*. Scaling one
  measurement across the other cells would be a projection wearing a measurement's label,
  which is the specific dishonesty the rule names.

## Trade-secret guard

This module enumerates **weights**. It never enumerates datasets, and in particular it never
looks inside `training/`. `training/corpus.jsonl` and `training/build_dataset.py` are trade
secret per `.claude/CLAUDE.md`, and a model picker that helpfully scanned the sibling
directory for `.jsonl` files would publish the recipe. Dataset admission is handled in
`datasets.py`, behind an explicit refusal, and nothing here calls it.

Stdlib only. This module is imported by the serving API, which runs on the system interpreter
by deliberate policy -- no torch, no transformers, no numpy. The GGUF reader below is a
few hundred bytes of `struct` rather than a dependency for exactly that reason.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import struct
import subprocess
from dataclasses import dataclass, field, asdict

HERE = pathlib.Path(__file__).resolve().parent
# backend/apps/reinforce -> backend/apps -> backend -> repo root.
ROOT = HERE.parent.parent.parent
# This calculation has been wrong three times in this repo's history (the demo/ flatten, the
# tools/ move, and `train_lora.py`'s HF_HOME, which is still wrong today -- it resolves to
# /home/google/models/hf, a path that does not exist). It fails silently, because the wrong
# parent is usually a directory that does exist. So assert, the way tools/build_training.py
# does, and turn a silent misresolution into an import-time crash.
assert (ROOT / "backend" / "api.py").is_file(), f"repo root misresolved to {ROOT}"

MODELS_DIR = ROOT / "backend" / "models"
HF_HOME = MODELS_DIR / "hf"
HF_HUB = HF_HOME / "hub"
GGUF_DIR = MODELS_DIR / "llm"

GIB = 1024 ** 3

# ---------------------------------------------------------------- the one vendor constant
#
# NF4 + double quantisation stores 4 bits per weight plus ~0.127 bits/weight of quantisation
# constants (the absmax scales, themselves quantised). QLoRA paper §3, "Double Quantization".
# VENDOR figure. Not measured on this box and never to be presented as if it were.
NF4_BITS_PER_PARAM = 4.127

# Bytes of optimiser/adapter state per *trainable* parameter:
#   4  fp32 master weight (LoRA matrices are trained in fp32)
# + 4  fp32 gradient
# + 2  paged AdamW 8-bit state (two moments at one byte each)
# PROJECTED. It is the standard accounting, not a reading from this card.
TRAINABLE_BYTES_PER_PARAM = 4 + 4 + 2

# Bytes per *resident, non-quantised* parameter -- embeddings, lm_head, norms and biases.
#
# This is 4, not 2, and getting it wrong cost a 2.03 GiB underestimate that a real run caught.
# The model is loaded at bf16, so 2 looks right and the arithmetic reads correctly. But peft's
# `prepare_model_for_kbit_training()` -- which every 4-bit recipe calls, including this one --
# then casts every non-quantised parameter to fp32:
#
#     peft/utils/other.py:197-202     # cast all non INT8 parameters to fp32
#         if (param.dtype == torch.float16) or (param.dtype == torch.bfloat16):
#             param.data = param.data.to(torch.float32)
#
# On a 152k-vocabulary model that is 1.09B parameters going from 2 bytes to 4: **+2.03 GiB**.
# MEASURED consequence: the Smoke preset on the 7B was projected at 6.29 GiB and peaked at
# 8.39 GiB allocated. The gap is this constant, and the corrected arithmetic lands within ~1%
# of the measurement. Kept as a named constant with the citation attached, because "2 bytes for
# a bf16 parameter" is the obvious wrong answer and somebody will try to simplify it back.
#
# The lever that would recover the 2.03 GiB is `peft.utils.other.cast_mixed_precision_params`,
# which casts non-trainable parameters back to half precision. It is NOT used here and has not
# been tested on this box; changing the recipe on the strength of a docstring is how a run OOMs
# at step 0 in a new way.
RESIDENT_BYTES_PER_PARAM = 4

# The allocator reserves more than it allocates -- cached blocks and fragmentation.
# MEASURED on the one run that exists: 10,158,604,288 reserved against 9,009,202,688
# allocated, a factor of 1.128. Used at 1.25 rather than 1.128 deliberately: one reading is
# not a distribution, and under-projecting is the failure mode that OOMs a run, so the rounding
# goes toward caution. PROJECTED.
ALLOCATOR_RESERVE_FACTOR = 1.25

# CUDA context + cuBLAS/cuBLASLt workspaces, which sit outside torch's own counters entirely --
# neither `max_memory_allocated()` nor `max_memory_reserved()` can see them, so this term can
# only ever be projected. On this box `nvidia-smi` reports ~1,027 MiB in use with nothing of
# ours running. PROJECTED.
CONTEXT_OVERHEAD_BYTES = int(0.6 * GIB)

# The budget to plan against. `nvidia-smi` reports 16,303 MiB total on this card and ~14,7xx
# MiB free at idle; the Reinforce engine's own registry docstring settled on ~14.2 GiB free
# in practice. Budgeting against the 15.92 GiB nameplate is how a run OOMs at step 0.
PRACTICAL_BUDGET_BYTES = int(14.2 * GIB)

# How much headroom a projection has to leave before this surface will call it a fit.
#
# `headroom > 0` is the wrong test and it is worth being explicit about why. The projection
# has known unmodelled terms -- cuBLAS workspace growth, allocator fragmentation, the
# dataloader, the tokeniser, and an activation estimate that is arithmetic rather than a
# reading. Its own error bar is comfortably wider than a gibibyte. So a run projected to fit
# by 0.9 GiB is not a run that fits; it is a run whose OOM is inside the noise.
#
# PROJECTED policy, not a measurement. Once real peaks exist for a cell these thresholds
# should be revisited against them -- and the measured value should replace the projection
# for that cell rather than adjusting the threshold to make the projection look better.
REFUSE_BELOW_BYTES = int(1.0 * GIB)     # below this, the answer is "this box cannot"
TIGHT_BELOW_BYTES = int(2.0 * GIB)      # below this, it may run, and it may not


# ---------------------------------------------------------------- GGUF header reader
#
# Enough of the GGUF spec to answer "what shape is this model and how is it quantised",
# without pulling in the `gguf` package (which lives in the training venv, not the serving
# interpreter). Arrays are skipped by seeking rather than materialised -- the tokeniser
# vocabulary is 152k strings and reading it to learn nothing would be silly.

_GGUF_MAGIC = b"GGUF"

# value type -> (struct format, byte width). None means variable-width, handled by hand.
_SCALAR = {
    0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
    4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1),
    10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8),
}
_STRING = 8
_ARRAY = 9

# ggml tensor types we can actually meet in these files. The name is what gets reported as
# the quantisation, and it is MEASURED -- it is read out of the tensor table, not guessed
# from the filename. (A file called `...Q4_K_M.gguf` that is secretly Q8_0 would be caught.)
_GGML_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1",
    10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K",
    16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S", 20: "IQ4_NL",
    21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32",
    27: "I64", 28: "F64", 29: "IQ1_M", 30: "BF16",
}

# `general.file_type`, the llama.cpp quantisation *recipe* name. Q4_K_M mixes Q4_K and Q6_K
# tensors, so the recipe is the honest label for the file as a whole and the per-tensor
# histogram is the evidence for it.
_FILE_TYPE_NAMES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1",
    10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S", 15: "Q4_K_M",
    16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS",
    32: "BF16",
}


class GGUFError(Exception):
    """The file is not a GGUF we can read. Never carries file *contents* in its message."""


def _read(fh, fmt: str, size: int):
    raw = fh.read(size)
    if len(raw) != size:
        raise GGUFError("truncated header")
    return struct.unpack(fmt, raw)[0]


def _read_str(fh) -> str:
    n = _read(fh, "<Q", 8)
    if n > 1 << 20:
        raise GGUFError("implausible string length in header")
    return fh.read(n).decode("utf-8", "replace")


def _skip_value(fh, vtype: int) -> None:
    if vtype in _SCALAR:
        fh.seek(_SCALAR[vtype][1], os.SEEK_CUR)
    elif vtype == _STRING:
        fh.seek(_read(fh, "<Q", 8), os.SEEK_CUR)
    elif vtype == _ARRAY:
        etype = _read(fh, "<I", 4)
        count = _read(fh, "<Q", 8)
        if etype in _SCALAR:
            fh.seek(_SCALAR[etype][1] * count, os.SEEK_CUR)   # one seek, not 152k reads
        elif etype == _STRING:
            for _ in range(count):
                fh.seek(_read(fh, "<Q", 8), os.SEEK_CUR)
        else:
            raise GGUFError(f"unsupported array element type {etype}")
    else:
        raise GGUFError(f"unsupported value type {vtype}")


def _read_value(fh, vtype: int):
    if vtype in _SCALAR:
        fmt, size = _SCALAR[vtype]
        return _read(fh, fmt, size)
    if vtype == _STRING:
        return _read_str(fh)
    _skip_value(fh, vtype)
    return None      # arrays are never a value we want; we only ever want their absence


def read_gguf_header(path: pathlib.Path) -> dict:
    """Architecture + quantisation, read off the file. Every field here is MEASURED.

    Returns keys: `arch`, `kv` (scalar/string metadata only), `file_type`, `tensor_types`
    (a histogram), `tensor_count`, and `tensors` (name -> dims) for the handful of tensors
    whose *presence* answers a real question -- `output.weight` tells us whether the
    embedding is tied, which changes the resident-bf16 term by a gibibyte on a 14B.
    """
    with path.open("rb") as fh:
        if fh.read(4) != _GGUF_MAGIC:
            raise GGUFError("not a GGUF file")
        version = _read(fh, "<I", 4)
        if version not in (2, 3):
            raise GGUFError(f"unsupported GGUF version {version}")
        tensor_count = _read(fh, "<Q", 8)
        kv_count = _read(fh, "<Q", 8)

        kv: dict[str, object] = {}
        for _ in range(kv_count):
            key = _read_str(fh)
            vtype = _read(fh, "<I", 4)
            val = _read_value(fh, vtype)
            if val is not None:
                kv[key] = val

        tensors: dict[str, list[int]] = {}
        types: dict[str, int] = {}
        for _ in range(tensor_count):
            name = _read_str(fh)
            ndims = _read(fh, "<I", 4)
            dims = [_read(fh, "<Q", 8) for _ in range(ndims)]
            ttype = _read(fh, "<I", 4)
            _read(fh, "<Q", 8)                       # offset, unused
            tname = _GGML_TYPE_NAMES.get(ttype, f"type{ttype}")
            types[tname] = types.get(tname, 0) + 1
            # Only the tensors whose shape or presence we actually reason about. Keeping the
            # whole table would be ~600 entries of noise in an API response.
            if name in ("token_embd.weight", "output.weight"):
                tensors[name] = dims

    arch = str(kv.get("general.architecture", "unknown"))
    ft = kv.get("general.file_type")
    return {
        "arch": arch,
        "kv": kv,
        "file_type": _FILE_TYPE_NAMES.get(ft, f"file_type{ft}") if ft is not None else None,
        "tensor_types": dict(sorted(types.items(), key=lambda kv_: -kv_[1])),
        "tensor_count": tensor_count,
        "tensors": tensors,
    }


# ---------------------------------------------------------------- the architecture record


@dataclass(frozen=True)
class Arch:
    """The seven numbers the VRAM arithmetic needs, however the model was described.

    Populated from an HF `config.json` or from GGUF KV metadata. Both paths land on the same
    record so `plan_fit()` never has to know which kind of file it came from.
    """
    layers: int
    hidden: int
    ffn: int
    heads: int
    kv_heads: int
    vocab: int
    tied_embeddings: bool

    @property
    def head_dim(self) -> int:
        return self.hidden // self.heads if self.heads else 0

    @property
    def kv_width(self) -> int:
        return self.head_dim * self.kv_heads

    @property
    def linear_params(self) -> int:
        """Parameters that bitsandbytes will actually quantise to 4 bits.

        Per decoder layer: q and o are hidden x hidden; k and v are hidden x kv_width
        (grouped-query attention, so they are much smaller than q); gate, up and down are
        each hidden x ffn. That is the seven `nn.Linear` leaves a Qwen2 decoder layer
        contains -- verified in the spec by instantiating the model on the meta device --
        which is also exactly the target-module list every preset uses.
        """
        per_layer = (2 * self.hidden * self.hidden          # q_proj, o_proj
                     + 2 * self.hidden * self.kv_width      # k_proj, v_proj
                     + 3 * self.hidden * self.ffn)          # gate_proj, up_proj, down_proj
        return per_layer * self.layers

    @property
    def resident_bf16_params(self) -> int:
        """Parameters that stay at bf16 no matter what `load_in_4bit` is set to.

        `nn.Embedding` is not a `Linear4bit`, and bitsandbytes skips `lm_head` by default.
        With a 152k vocabulary that is over a billion parameters and two gibibytes -- the
        term a naive `params * 0.5 bytes` estimate silently throws away, and the single most
        common reason a 'this fits' estimate OOMs.
        """
        embeddings = self.vocab * self.hidden * (1 if self.tied_embeddings else 2)
        # RMSNorm weights (two per layer plus a final) and the q/k/v biases Qwen2 carries.
        norms_and_biases = (2 * self.layers + 1) * self.hidden + self.layers * (
            self.hidden + 2 * self.kv_width)
        return embeddings + norms_and_biases

    @property
    def total_params(self) -> int:
        return self.linear_params + self.resident_bf16_params

    def lora_params(self, rank: int, modules: tuple[str, ...]) -> int:
        """Trainable parameters for a given rank over a given module set.

        A LoRA pair on a d_in x d_out projection is rank*(d_in + d_out) parameters. Summed
        per layer over whichever of the seven projections the preset targets, which is why
        a q,v-only preset is genuinely cheaper and not just nominally so.
        """
        widths = {
            "q_proj": (self.hidden, self.hidden),
            "k_proj": (self.hidden, self.kv_width),
            "v_proj": (self.hidden, self.kv_width),
            "o_proj": (self.hidden, self.hidden),
            "gate_proj": (self.hidden, self.ffn),
            "up_proj": (self.hidden, self.ffn),
            "down_proj": (self.ffn, self.hidden),
        }
        per_layer = sum(rank * (widths[m][0] + widths[m][1]) for m in modules if m in widths)
        return per_layer * self.layers


def arch_from_hf_config(cfg: dict) -> Arch:
    """Build an `Arch` from an HF `config.json`. Raises KeyError if it is not a causal LM
    config -- the TAO rejection-criteria pattern: qualify before offering, do not offer and
    then fail at load."""
    heads = int(cfg["num_attention_heads"])
    return Arch(
        layers=int(cfg["num_hidden_layers"]),
        hidden=int(cfg["hidden_size"]),
        ffn=int(cfg["intermediate_size"]),
        heads=heads,
        kv_heads=int(cfg.get("num_key_value_heads", heads)),
        vocab=int(cfg["vocab_size"]),
        tied_embeddings=bool(cfg.get("tie_word_embeddings", False)),
    )


def arch_from_gguf(header: dict) -> Arch:
    """Build an `Arch` from GGUF KV metadata.

    Two things are not in the KV block and are read off the tensor table instead:
    the vocabulary size (from `token_embd.weight`'s shape, rather than by materialising a
    152k-entry token array) and whether the embedding is tied (`output.weight` present means
    untied). The 0.5B here carries no `output.weight` and is tied; the 14B carries one and
    is not -- which is worth ~0.9 GiB on the 14B's resident-bf16 term.
    """
    arch = header["arch"]
    kv = header["kv"]

    def g(key: str) -> int:
        full = f"{arch}.{key}"
        if full not in kv:
            raise GGUFError(f"GGUF metadata has no {full}")
        return int(kv[full])

    heads = g("attention.head_count")
    embd = header["tensors"].get("token_embd.weight")
    if embd and len(embd) == 2:
        vocab = int(embd[1])            # GGUF dims are [hidden, vocab]
    elif f"{arch}.vocab_size" in kv:
        vocab = int(kv[f"{arch}.vocab_size"])
    else:
        raise GGUFError("cannot determine vocabulary size")
    return Arch(
        layers=g("block_count"),
        hidden=g("embedding_length"),
        ffn=g("feed_forward_length"),
        heads=heads,
        kv_heads=int(kv.get(f"{arch}.attention.head_count_kv", heads)),
        vocab=vocab,
        tied_embeddings="output.weight" not in header["tensors"],
    )


# ---------------------------------------------------------------- the catalogue entry


@dataclass
class Entry:
    """One row in the picker.

    `trainable` is the field the whole surface turns on, and `reason` says *why* when it is
    false. "Unsupported" on its own is what makes an operator file a bug report; "GGUF has no
    torch state dict, so peft has no modules to attach to" is what makes them pick the other
    row.
    """
    id: str
    label: str
    kind: str                    # "hf" | "gguf"
    path: str                    # display path, relative to the repo root -- never absolute
    present: bool
    trainable: bool
    reason: str = ""
    bytes_on_disk: int = 0
    quantisation: str = ""
    quant_label: str = ""        # measured / vendor / projected, for the quantisation figure
    tensor_types: dict = field(default_factory=dict)
    arch: dict | None = None
    arch_label: str = ""
    params: dict | None = None
    fetch_bytes: int = 0         # projected download size when `present` is false

    def to_dict(self) -> dict:
        return asdict(self)


def _rel(p: pathlib.Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return p.name


def _params_block(a: Arch) -> dict:
    """The parameter split, with each number labelled at the point it is produced."""
    return {
        "total": a.total_params,
        "quantised_4bit": a.linear_params,
        "resident_bf16": a.resident_bf16_params,
        "label": "measured",
        "note": ("derived from the architecture metadata read off this file; the 7B lands on "
                 "its safetensors index total_size byte-for-byte"),
    }


def scan_hf_cache(hub: pathlib.Path = HF_HUB) -> list[Entry]:
    """Enumerate HF-format models in the local cache.

    The sd-webui `list_models()` pattern (§3.4 of the spec): one directory scan, refreshed on
    demand, no hardcoded list. A snapshot qualifies only if it has a `config.json` we can
    parse into an `Arch` and at least one `.safetensors` shard -- a `.no_exist` marker
    directory in the same cache carries a `config.json`-shaped absence and must not be
    offered.
    """
    out: list[Entry] = []
    if not hub.is_dir():
        return out
    for repo_dir in sorted(hub.glob("models--*")):
        snapshots = repo_dir / "snapshots"
        if not snapshots.is_dir():
            continue
        for snap in sorted(snapshots.iterdir()):
            cfg_path = snap / "config.json"
            if not cfg_path.is_file():
                continue
            repo_id = repo_dir.name.removeprefix("models--").replace("--", "/", 1).replace("--", "/")
            try:
                cfg = json.loads(cfg_path.read_text())
                a = arch_from_hf_config(cfg)
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                out.append(Entry(
                    id=repo_id, label=repo_id, kind="hf", path=_rel(snap), present=True,
                    trainable=False,
                    reason=(f"config.json is not a causal-LM config this surface can qualify "
                            f"({type(exc).__name__}); rejected before load rather than after"),
                ))
                continue
            shards = sorted(snap.glob("*.safetensors"))
            if not shards:
                out.append(Entry(
                    id=repo_id, label=repo_id, kind="hf", path=_rel(snap), present=False,
                    trainable=False,
                    reason="config.json present but no safetensors shards -- metadata-only cache entry",
                ))
                continue
            # Resolve symlinks: the HF cache snapshots are links into blobs/, and the link
            # itself is 60-odd bytes. Reporting that as the model size would be a lie the
            # first operator to check `du` would catch.
            size = sum(s.resolve().stat().st_size for s in shards)
            out.append(Entry(
                id=repo_id, label=repo_id, kind="hf", path=_rel(snap), present=True,
                trainable=True,
                reason="", bytes_on_disk=size,
                quantisation=str(cfg.get("torch_dtype", "bfloat16")),
                quant_label="measured",
                tensor_types={f"{len(shards)} safetensors shards": len(shards)},
                arch=asdict(a), arch_label="measured", params=_params_block(a),
            ))
    return out


def scan_gguf(directory: pathlib.Path = GGUF_DIR) -> list[Entry]:
    """Enumerate GGUF weights, all of which are offered as *rejected* rows with the reason.

    They are listed rather than hidden on purpose. Three of the four largest model files on
    this box are GGUF; a picker that showed none of them would look broken, and an operator
    who has just watched the chat surface serve a GGUF is owed an explanation of why the
    training bay will not take one.
    """
    out: list[Entry] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.gguf")):
        size = path.stat().st_size
        entry = Entry(
            id=path.stem, label=path.stem, kind="gguf", path=_rel(path), present=True,
            trainable=False,
            reason=("GGUF is a serving format, not a training format: it carries no torch "
                    "state dict and no module tree, so there is nothing for a low-rank "
                    "adapter to attach to. llama.cpp can serve an adapter; it cannot "
                    "produce one."),
            bytes_on_disk=size,
        )
        try:
            header = read_gguf_header(path)
            entry.quantisation = header["file_type"] or "unknown"
            entry.quant_label = "measured"
            entry.tensor_types = header["tensor_types"]
            a = arch_from_gguf(header)
            entry.arch = asdict(a)
            entry.arch_label = "measured"
            entry.params = _params_block(a)
        except (GGUFError, OSError, struct.error) as exc:
            # Deliberately reports the exception *class*, not its message. Nothing in a GGUF
            # header is secret, but the habit is: an error path is the easiest place in a
            # training surface for file contents to escape into an API response.
            entry.reason += f" (header not readable: {type(exc).__name__})"
        out.append(entry)
    return out


def fetchable() -> list[Entry]:
    """Models this box could train but does not have, with the download size stated up front.

    This exists because of a specific honesty problem: exactly one model on this box is
    fine-tunable, and *a dropdown with one item is a UI that lies about choice*. The honest
    fix is to offer the others and say what they cost, not to pad the list.

    The architecture rows here are **measured** -- they are read from the GGUF of the same
    model that is already on disk, which is the same architecture in a different container.
    The download sizes are **projected**: they are the safetensors totals published by the
    source repository, arithmetic on the parameter count, not a transfer this box has run.

    Fetching is NOT implemented. `jobs.start()` refuses a model with `present=False` rather
    than kicking off a 27.5 GiB download from an HTTP handler. See the module note in
    routes.py.
    """
    out: list[Entry] = []
    have = {e.id for e in scan_hf_cache() if e.trainable}
    for gguf_name, repo_id in (
        ("Qwen2.5-0.5B-Instruct-Q4_K_M.gguf", "Qwen/Qwen2.5-0.5B-Instruct"),
        ("Qwen2.5-14B-Instruct-Q4_K_M.gguf", "Qwen/Qwen2.5-14B-Instruct"),
    ):
        if repo_id in have:
            continue
        src = GGUF_DIR / gguf_name
        if not src.is_file():
            continue
        try:
            a = arch_from_gguf(read_gguf_header(src))
        except (GGUFError, OSError, struct.error):
            continue
        out.append(Entry(
            id=repo_id, label=repo_id, kind="hf", path="backend/models/hf (not fetched)",
            present=False, trainable=False,
            reason=("not on this box in HF format; the training stack needs safetensors plus "
                    "a config.json. Fetch-on-demand is not implemented -- this row states the "
                    "cost so the choice is informed, it is not a button."),
            quantisation="bfloat16 (once fetched)", quant_label="projected",
            arch=asdict(a),
            arch_label="measured (architecture read from the GGUF of the same model on disk)",
            params=_params_block(a),
            # bf16 safetensors: two bytes per parameter, plus a few per-shard headers.
            fetch_bytes=a.total_params * 2,
        ))
    return out


def catalogue() -> list[Entry]:
    """Everything the picker shows, trainable rows first.

    NOTE FOR ANYONE EXTENDING THIS: do not add a dataset scan here, and specifically never
    glob `training/*.jsonl`. `training/corpus.jsonl` and `training/build_dataset.py` are
    trade secret under `.claude/CLAUDE.md`; enumerating them into a dropdown publishes the
    product's recipe, and it is the single most likely accident on a surface like this one.
    Datasets are admitted by `datasets.py`, which refuses those two paths by name.
    """
    rows = scan_hf_cache() + fetchable() + scan_gguf()
    rows.sort(key=lambda e: (not e.trainable, not e.present, e.id))
    return rows


def find(model_id: str) -> Entry | None:
    """Resolve a model id to an entry, tolerating the short form.

    The fuzzy half of sd-webui's `get_closet_checkpoint_match`: a preset saved as
    `Qwen2.5-7B-Instruct` still resolves after somebody writes the full `Qwen/...` repo id,
    and vice versa. Exact match always wins, so a suffix collision cannot shadow a real id.
    """
    rows = catalogue()
    for e in rows:
        if e.id == model_id:
            return e
    lowered = model_id.lower()
    hits = [e for e in rows if e.id.lower().endswith("/" + lowered) or e.label.lower() == lowered]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- the fit calculation


def free_vram_bytes() -> tuple[int | None, str]:
    """Free VRAM from the driver. MEASURED when it answers, `None` when it does not.

    Not called from `status()` -- that runs on every rack poll and must not fork a process.
    This is for preflight, where one `nvidia-smi` in exchange for not OOMing at step 0 is a
    trade worth making.
    """
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None, "nvidia-smi not on PATH"
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True).stdout
        return int(out.strip().splitlines()[0].strip()) * 1024 * 1024, "measured"
    except (subprocess.SubprocessError, ValueError, IndexError) as exc:
        return None, f"nvidia-smi unreadable ({type(exc).__name__})"


def activation_bytes(a: Arch, seq_len: int, batch: int, checkpointing: bool = True) -> dict:
    """Activation memory, broken into the three terms that matter, all PROJECTED.

    The interesting result -- and the reason this is a function and not a constant -- is that
    on a 152k-vocabulary model the **logits dominate**. At sequence 1024 the checkpointed
    hidden states are ~205 MiB while the logit tensor and its fp32 upcast for cross-entropy
    are ~890 MiB together. That is why `max_length` moves the peak so much more than layer
    count does, and why Long-form (seq 2048) is the preset closest to the ceiling.
    """
    hidden_states = a.layers * seq_len * a.hidden * batch * 2 if checkpointing else 0
    # Without checkpointing every intermediate in every layer is kept; roughly an order of
    # magnitude more. Every preset here enables checkpointing, so this branch is the
    # arithmetic that justifies the rule rather than a configuration anyone can pick.
    if not checkpointing:
        hidden_states = a.layers * seq_len * batch * (a.hidden * 6 + a.ffn * 3) * 2
    recompute = seq_len * batch * (a.ffn * 3 + a.hidden * 4) * 2
    logits = seq_len * batch * a.vocab * (2 + 4)      # bf16 logits + fp32 upcast for the loss
    return {
        "hidden_states": hidden_states,
        "recompute_peak": recompute,
        "logits": logits,
        "total": hidden_states + recompute + logits,
        "label": "projected",
    }


def plan_fit(a: Arch, *, rank: int, target_modules: tuple[str, ...], seq_len: int,
             batch: int, gradient_checkpointing: bool = True,
             free_bytes: int | None = None) -> dict:
    """The four-term VRAM projection, itemised so a refusal can show its working.

    Reinforce's `plan_residency(free_bytes)` decides what fits *before* anything is loaded;
    this is the training-shaped version of that. A refusal returns the sum, because "won't
    fit" with no arithmetic is indistinguishable from a bug, and because the OOM ladder can
    only name a rung if it knows which term is the large one.

    Every figure here is **projected** except `free_bytes`, which is measured, and the
    4.127 bits/param NF4 constant, which is vendor.
    """
    weights_4bit = int(a.linear_params * NF4_BITS_PER_PARAM / 8)
    weights_resident = a.resident_bf16_params * RESIDENT_BYTES_PER_PARAM
    lora_n = a.lora_params(rank, target_modules)
    trainable = lora_n * TRAINABLE_BYTES_PER_PARAM
    acts = activation_bytes(a, seq_len, batch, gradient_checkpointing)

    # Two figures, because they answer two different questions and conflating them is what
    # produced the first bad estimate. `content` is what torch will report as allocated -- it
    # is comparable against `max_memory_allocated()` and is the number the arithmetic can be
    # checked against. `total` is what the process takes off the card, which is what decides
    # whether it fits: allocator reservation on top of content, plus a CUDA context that
    # torch's counters cannot see at all.
    content = weights_4bit + weights_resident + trainable + acts["total"]
    total = int(content * ALLOCATOR_RESERVE_FACTOR) + CONTEXT_OVERHEAD_BYTES

    budget = free_bytes if free_bytes is not None else PRACTICAL_BUDGET_BYTES
    headroom = budget - total
    trainable_pct = 100.0 * lora_n / a.total_params if a.total_params else 0.0

    if headroom < REFUSE_BELOW_BYTES:
        verdict = "refused"
    elif headroom < TIGHT_BELOW_BYTES:
        verdict = "tight"
    else:
        verdict = "fits"

    # The OOM ladder, from TAO's error playbook, minus the rungs this box has already spent.
    # Batch is 1 in every preset and gradient checkpointing is always on, so "halve the batch"
    # and "enable checkpointing" are not available here. Saying which rung is being offered,
    # in these words, is the difference between a refusal and a shrug.
    ladder: list[str] = []
    if verdict != "fits":
        if seq_len > 512:
            ladder.append(f"shorten max_length from {seq_len} to {seq_len // 2} "
                          f"(saves ~{(acts['logits'] + acts['hidden_states']) // 2 / GIB:.2f} GiB, projected)")
        if rank > 8:
            ladder.append(f"lower rank from {rank} to {rank // 2} "
                          f"(saves ~{trainable // 2 / GIB:.2f} GiB, projected)")
        ladder.append("choose a smaller base model -- the weights term is the large one and "
                      "rank does not touch it")

    return {
        "terms": {
            "weights_4bit": {"bytes": weights_4bit, "label": "projected",
                             "basis": f"{a.linear_params:,} params x {NF4_BITS_PER_PARAM} bits "
                                      f"(NF4 + double quant, vendor: QLoRA arXiv:2305.14314 §3)"},
            "weights_resident_fp32": {"bytes": weights_resident, "label": "projected",
                                      "basis": f"{a.resident_bf16_params:,} params x "
                                               f"{RESIDENT_BYTES_PER_PARAM} bytes -- embeddings, "
                                               f"lm_head, norms and biases are not quantised, and "
                                               f"peft upcasts them from bf16 to fp32 before "
                                               f"training (peft/utils/other.py:197-202). Assuming "
                                               f"2 bytes here understated a real run by 2.03 GiB"},
            "adapter_and_optimiser": {"bytes": trainable, "label": "projected",
                                      "basis": f"{lora_n:,} trainable x "
                                               f"{TRAINABLE_BYTES_PER_PARAM} bytes "
                                               f"(fp32 weight + fp32 grad + 8-bit AdamW)"},
            "activations": {"bytes": acts["total"], "label": "projected",
                            "basis": f"checkpointed hidden states {acts['hidden_states'] / GIB:.2f} GiB "
                                     f"+ one-layer recompute {acts['recompute_peak'] / GIB:.2f} GiB "
                                     f"+ logits {acts['logits'] / GIB:.2f} GiB "
                                     f"at seq {seq_len} x batch {batch}"},
            "allocator_reserve": {"bytes": int(content * (ALLOCATOR_RESERVE_FACTOR - 1)),
                                  "label": "projected",
                                  "basis": f"x{ALLOCATOR_RESERVE_FACTOR} on the content above. The "
                                           f"one run measured here reserved 1.128x what it "
                                           f"allocated; rounded up because one reading is not a "
                                           f"distribution and under-projecting is what OOMs"},
            "cuda_context": {"bytes": CONTEXT_OVERHEAD_BYTES, "label": "projected",
                             "basis": "CUDA context and cuBLAS workspace, which sit outside "
                                      "torch's own memory counters entirely"},
        },
        "projected_allocated_bytes": content,
        "projected_allocated_gib": round(content / GIB, 2),
        "projected_allocated_note": ("comparable against torch.cuda.max_memory_allocated(); this "
                                     "is the figure the arithmetic can be checked against"),
        "projected_peak_bytes": total,
        "projected_peak_gib": round(total / GIB, 2),
        "budget_bytes": budget,
        "budget_gib": round(budget / GIB, 2),
        "budget_label": "measured" if free_bytes is not None else "projected",
        "budget_basis": ("free VRAM read from the driver just now"
                         if free_bytes is not None else
                         "~14.2 GiB practical budget; the 15.92 GiB nameplate is not free"),
        "headroom_bytes": headroom,
        "headroom_gib": round(headroom / GIB, 2),
        "verdict": verdict,
        "verdict_why": {
            "fits": f"projected to leave at least {TIGHT_BELOW_BYTES / GIB:.1f} GiB spare",
            "tight": (f"projected headroom is under {TIGHT_BELOW_BYTES / GIB:.1f} GiB, which is "
                      f"inside the error bar on the projection itself. It may complete; treat an "
                      f"OOM as expected rather than as a fault"),
            "refused": (f"projected headroom is under {REFUSE_BELOW_BYTES / GIB:.1f} GiB. This is "
                        f"a capability this box does not have for this configuration -- not a "
                        f"fault, and not something a retry fixes"),
        }[verdict],
        "fits": verdict != "refused",
        "trainable_params": lora_n,
        "trainable_pct": round(trainable_pct, 3),
        # TAO's error playbook: an adapter outside 0.1-1% of the base usually means the target
        # regex is too broad. Worth surfacing, not worth refusing over -- r=32 on a 7B lands
        # at ~1.06%, which is deliberate for the Recall preset and not a mistake.
        "trainable_pct_note": ("inside the 0.1-1% band a low-rank adapter is expected to occupy"
                               if 0.1 <= trainable_pct <= 1.0 else
                               "outside the usual 0.1-1% band -- expected at high rank, but check "
                               "the target module list if you did not intend it"),
        "ladder": ladder,
        "label": "projected",
        "note": ("arithmetic, not a measurement. A cell becomes measured only when a run of "
                 "that exact model and preset records torch.cuda.max_memory_allocated()."),
        "accuracy": ACCURACY,
    }


# How well this arithmetic has actually done, stated rather than implied.
#
# There is exactly ONE measurement behind it: the Smoke preset on the 7B, eight steps, which
# reported 9,009,202,688 bytes allocated and 10,158,604,288 reserved. Publishing a projection
# without publishing how far off it was the one time it could be checked would be the same
# class of dishonesty as an unlabelled figure.
#
# The content term still runs ~7% UNDER the measurement. The unmodelled remainder is transient
# copies during the fp32 cast, the paged optimiser's own state, and the evaluation forward
# pass. It is NOT tuned away with a fudge constant, because a constant fitted to one data point
# is a projection that has stopped being arithmetic. What protects a run instead is that the
# figure the fit decision uses -- `projected_peak_bytes` -- sits above the measured reservation
# by design, and a regression test asserts that it does.
ACCURACY = {
    "runs_measured": 1,
    "cell": "Qwen/Qwen2.5-7B-Instruct | smoke | 8 steps",
    "measured_allocated_bytes": 9_009_202_688,
    "measured_reserved_bytes": 10_158_604_288,
    "content_term_error": "projection ran about 7% under the measured allocation",
    "direction": ("the fit decision uses the peak figure, which projects ABOVE the measured "
                  "reservation -- deliberately, because under-projecting is the failure that "
                  "OOMs a run at step 0 and over-projecting only refuses one that might have fit"),
    "first_correction": ("the first version of this arithmetic charged 2 bytes for each resident "
                         "parameter and was 2.03 GiB under. peft upcasts them to fp32; the run "
                         "found it, the constant was corrected, and the comment carries the "
                         "citation so it does not get simplified back"),
    "label": "measured",
}
