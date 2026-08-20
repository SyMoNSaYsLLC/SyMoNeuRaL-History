"""The type scale in site/symoneural.css is enforceable, so enforce it.

site/symoneural.css carries a comment saying "EVERY font-size in this file references one
of these seven. Adding an eighth here, or writing a raw px size anywhere below, defeats
the point: the scale is meant to be enforceable, and it is checked by re-running the type
audit and counting the distinct sizes the DOM reports."

Re-running a browser type audit is a manual act that happens when someone remembers. This
parses the file instead, so the constraint holds on every commit rather than on every
review. It exists because the commit that added the depth-and-motion layer at the tail of
that file was working from a reference design whose display type is much larger than ours,
and reaching for a raw `font-size:56px` there is the single most likely way the scale gets
broken.

It also pins the specific invalid form that already bit this file once: twelve
declarations were written `font:600 12.5px/1 inherit`, and `inherit` is a CSS-wide keyword
rather than a font-family, so the entire shorthand was dropped and those elements silently
rendered at the UA's default control size. Any `font:` shorthand whose size part is not a
scale token now fails here.

Stdlib only, on purpose -- backend/apps/ tests are collected by the main pytest run.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CSS = ROOT / "site" / "symoneural.css"

# `var(--t3)`, optionally `!important`.
TOKEN = re.compile(r"^var\(--t[1-7]\)(\s*!important)?$")
# `clamp(var(--t3),3.4vw,var(--t1))` -- a fluid size is still expressed in scale tokens at
# both ends, which is what keeps the rendered range inside the scale.
CLAMP = re.compile(
    r"^clamp\(\s*var\(--t[1-7]\)\s*,[^,]+,\s*var\(--t[1-7]\)\s*\)(\s*!important)?$"
)


def _source():
    """The file with comments removed.

    Required, not cosmetic: the comments in this file quote font sizes as prose --
    `14.5px` and `Npx` both appear inside them -- so a scan of the raw text reports
    offenders that do not exist.
    """
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def _ok(size: str) -> bool:
    size = size.strip()
    return bool(TOKEN.match(size) or CLAMP.match(size))


def test_the_scale_has_exactly_seven_steps():
    defined = sorted(set(re.findall(r"(--t[1-7])\s*:", _source())))
    assert defined == [f"--t{n}" for n in range(1, 8)]
    assert not re.search(r"--t[089]\s*:", _source()), "an eighth step was added to the scale"


def test_every_font_size_declaration_uses_a_scale_token():
    offenders = [v for v in re.findall(r"font-size\s*:([^;}]*)", _source()) if not _ok(v)]
    assert offenders == [], f"font-size values outside the scale: {offenders}"


def test_every_font_shorthand_sizes_itself_from_the_scale():
    # `font:inherit` is the whole shorthand as a CSS-wide keyword and is legal. It is the
    # only form without a size part.
    offenders = []
    for raw in re.findall(r"(?<![-\w])font\s*:([^;}]*)", _source()):
        value = raw.strip()
        if value in ("inherit", "initial", "unset", "revert"):
            continue
        # Strip an optional leading weight/style/variant run, then take the size, which
        # ends at the line-height slash or at the space before the family list.
        # `clamp\((?:[^()]|\([^()]*\))*\)` matches one level of nesting, which is what a
        # `clamp(var(--t6),1.02vw,var(--t4))` size part needs -- three nested var() calls
        # inside the clamp. A plain `[^)]*` stops at the first inner `)` and reports every
        # fluid shorthand in this file as an offender.
        m = re.match(
            r"^(?:[\w-]+\s+)*?(var\(--t[1-7]\)|clamp\((?:[^()]|\([^()]*\))*\))", value
        )
        if not m or not _ok(m.group(1)):
            offenders.append(value)
    assert offenders == [], f"font: shorthands not sized from the scale: {offenders}"


def test_no_font_shorthand_names_inherit_as_the_family():
    # The bug this file records: `font:600 12.5px/1 inherit` parses as invalid and is
    # dropped wholesale, which is why it went unnoticed.
    bad = [
        v.strip()
        for v in re.findall(r"(?<![-\w])font\s*:([^;}]*)", _source())
        if v.strip() != "inherit" and re.search(r"(^|[\s/])inherit\s*$", v)
    ]
    assert bad == [], f"`inherit` used as the font-family inside a shorthand: {bad}"


def test_no_raw_pixel_font_sizes_anywhere():
    raw = re.findall(r"font(?:-size)?\s*:[^;}]*?\b\d+(?:\.\d+)?px", _source())
    assert raw == [], f"raw px font sizes: {raw}"


@pytest.mark.parametrize(
    "token",
    ["--sf1", "--sfline", "--glass-blur", "--r-pill", "--ease", "--lift", "--el2", "--glow"],
)
def test_the_depth_layer_tokens_are_defined(token):
    # The depth layer's rules reference these; an undefined custom property does not error,
    # it silently drops the declaration that uses it, which is a look-and-feel regression
    # with no symptom at build time.
    assert re.search(re.escape(token) + r"\s*:", _source()), f"{token} is not defined"


def test_every_added_animation_has_a_reduced_motion_path():
    src = _source()
    # `reveal` and `ring` are the two keyframes the depth layer added. Both are applied
    # only inside a prefers-reduced-motion:no-preference block, so a reader who has asked
    # for less motion gets the finished state and no animation at all.
    for name in ("reveal", "ring"):
        assert f"@keyframes {name}" in src, f"@keyframes {name} went missing"
        for use in re.findall(r"animation\s*:[^;}]*\b" + name + r"\b[^;}]*", src):
            before = src[: src.index(use)]
            opened = before.count("prefers-reduced-motion:no-preference")
            assert opened >= 1, f"`{use}` is not behind a reduced-motion guard"
