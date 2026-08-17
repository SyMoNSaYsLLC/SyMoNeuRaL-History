"""Minimal ABI encoding and decoding for read-only TVM calls. Stdlib, no I/O, no keys.

Scope is deliberately narrow: the four types a licensing read actually needs -- `address`,
`uint256`, `bool` and `string`. It is not a general ABI codec and does not pretend to be;
tuples, arrays and fixed-point are absent rather than half-implemented, and an unknown type
raises rather than being guessed at.

Encoding a call needs no wallet and no private key. **Signing does** -- and signing is
secp256k1, which is not in the standard library and does not belong in a public-facing web
process at all (`__init__.py` docstring). Nothing here signs anything, and nothing here can:
a constant call is evaluated by the node and never broadcast.

TRON's node API takes `function_selector` as a text signature and computes the selector
itself, so `selector()` is not strictly required to make a call. It is here because computing
it locally lets the test suite check our understanding against the published values for
`transfer(address,uint256)` and `balanceOf(address)`, and because a locally derived selector
is what a `data` payload would need if the call ever moved off the convenience endpoint.
"""
from __future__ import annotations

from .keccak import keccak256

WORD = 32
UINT_MAX = (1 << 256) - 1
SUPPORTED = ("address", "uint256", "bool", "string")


class AbiError(ValueError):
    pass


def selector(signature: str) -> str:
    """`transfer(address,uint256)` -> `a9059cbb`. Keccak-256, not SHA3-256."""
    if "(" not in signature or not signature.endswith(")"):
        raise AbiError(f"{signature!r} is not a function signature")
    return keccak256(signature.encode()).hex()[:8]


def _word(b: bytes) -> bytes:
    return b.rjust(WORD, b"\x00")


def encode_params(types: list[str], values: list) -> str:
    """ABI-encode arguments to the hex string TRON's `parameter` field takes (no `0x`)."""
    from . import address as _addr

    if len(types) != len(values):
        raise AbiError(f"{len(types)} types for {len(values)} values")
    head, tail = [], []
    tail_at = WORD * len(types)
    for t, v in zip(types, values):
        if t == "address":
            head.append(_word(_addr.evm(v) if isinstance(v, str) else bytes(v)))
        elif t == "uint256":
            n = int(v)
            if n < 0 or n > UINT_MAX:
                raise AbiError(f"uint256 out of range: {n}")
            head.append(n.to_bytes(WORD, "big"))
        elif t == "bool":
            head.append(_word(b"\x01" if v else b"\x00"))
        elif t == "string":
            raw = v.encode() if isinstance(v, str) else bytes(v)
            head.append((tail_at + sum(len(x) for x in tail)).to_bytes(WORD, "big"))
            padded = raw + b"\x00" * (-len(raw) % WORD)
            tail.append(len(raw).to_bytes(WORD, "big") + padded)
        else:
            raise AbiError(f"unsupported type {t!r}; this codec handles {SUPPORTED}")
    return (b"".join(head) + b"".join(tail)).hex()


def decode_params(types: list[str], data: str) -> list:
    """Decode a `constant_result` word string. Raises on anything it cannot read exactly."""
    from . import address as _addr

    raw = bytes.fromhex(data.removeprefix("0x")) if data else b""
    if len(raw) < WORD * len(types):
        raise AbiError(f"{len(raw)} bytes is short for {len(types)} value(s)")
    out = []
    for i, t in enumerate(types):
        w = raw[i * WORD:(i + 1) * WORD]
        if t == "address":
            out.append(_addr.from_hex(w[-20:].hex()))
        elif t == "uint256":
            out.append(int.from_bytes(w, "big"))
        elif t == "bool":
            n = int.from_bytes(w, "big")
            if n not in (0, 1):
                raise AbiError(f"bool word is {n}, expected 0 or 1")
            out.append(bool(n))
        elif t == "string":
            off = int.from_bytes(w, "big")
            if off + WORD > len(raw):
                raise AbiError("string offset points past the end of the data")
            ln = int.from_bytes(raw[off:off + WORD], "big")
            if off + WORD + ln > len(raw):
                raise AbiError("string length runs past the end of the data")
            body = raw[off + WORD:off + WORD + ln]
            try:
                out.append(body.decode())
            except UnicodeDecodeError as e:
                raise AbiError(f"string is not valid UTF-8: {e}") from e
        else:
            raise AbiError(f"unsupported type {t!r}; this codec handles {SUPPORTED}")
    return out
