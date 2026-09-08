# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""The per-surface rate budgets. One dict, published from and enforced from.

Created 2026-09-08 because there were three answers to "what is chat's hourly limit" and
no two agreed:

    appdocs.py prose          120 requests/min, 3,000/hour     <- what visitors were told
    api.py _RATE_SUGGESTED    120, 2000                        <- what the code suggested
    the running process       no bucket at all                 <- what was enforced

Three of the four published hourly figures were wrong against the table beside them, and
none of the four was applied: `_rate_for` returned `(0, 0)` unless an env var was set, and
`check_rate` treats a missing limiter as "allow". A burst of 150 posts to `ravencalc` in
1.64 seconds drew no 429.

So the numbers live here, `api.py` defaults to them instead of to no limit, `appdocs.py`
renders its prose from them, and `test_rate_limits_are_real.py` asserts the three agree.
`SYMONEURAL_RATE_<SURFACE>=N/N` still overrides, which is what an operator needs.
"""
from __future__ import annotations

#: (per_minute, per_hour) per surface. Reasoning per line is in api.py where these were
#: first written down; the values are unchanged from that table.
BUDGETS: dict[str, tuple[int, int]] = {
    "ravencalc": (240, 6000),
    "chat":      (120, 2000),
    "remix":     (40,   600),
    "image":     (20,   300),
    "sigil":     (20,   300),
    "voice":     (60,   900),
    "studio":    (60,   900),
    "exp":       (60,   900),
}


def prose(surface: str) -> str:
    """The published sentence for a surface, built from the enforced numbers."""
    per_min, per_hour = BUDGETS[surface]
    return f"{per_min:,} requests/min per address, {per_hour:,}/hour."
