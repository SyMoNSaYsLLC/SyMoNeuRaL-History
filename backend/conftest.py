"""Make a repository-wide `pytest` collect this tree the way production imports it.

TWO problems, one file, and both were path problems rather than product defects.

1. `from apps.X import ...` -- what production actually does
------------------------------------------------------------
`backend/apps/**` imports its siblings as `apps.something`. That works when pytest's
rootdir is `backend/`, which is what the documented invocation gives you, and it is also
exactly what the running service gets: `symoneural-api.service` is

    WorkingDirectory=/home/google/Symoneural
    ExecStart=/usr/bin/python3 /home/google/Symoneural/backend/api.py

and Python puts the *script's own directory* -- `backend/` -- at `sys.path[0]`. So `apps`
is a top-level package at runtime, by construction.

A run rooted at the repository root does not reproduce that, so `pytest` from the repo root
reported `ModuleNotFoundError: No module named 'apps'` as a collection ERROR for
`apps/controlboard`, `apps/dispatchos`, `apps/live` and `apps/streamer/guide` -- 169 tests
that pass perfectly, presented as if four modules were broken. A collection error and a
real failure look identical at a glance, which is the part that costs time.

Inserting `backend/` here fixes both invocations at once, because pytest imports the
conftest of every collected directory before the tests beneath it. It is the same fix, at
the same level, as `apps/remix/conftest.py` -- and it mirrors production rather than
inventing a test-only layout, which is the reason to prefer it over a `pythonpath` setting
in a new config file: if this line were ever wrong, the service would be wrong too.

Prepending is deliberate. `apps` is a first-party name and must not be shadowed by an
installed distribution that happens to share it.

2. `vendor/` is not ours to run
-------------------------------
`backend/vendor/` holds the vendored Anthropic and OpenAI SDKs -- 15,297 tracked files
carrying their own suites, including `e2e-tests/` that expect network access and provider
credentials. Collecting them aborted the entire first-party run at 48 errors before a
single first-party test executed, so the suite could not report on itself.

`collect_ignore_glob` makes the exclusion self-enforcing rather than an `--ignore` flag
every operator has to remember -- the same reasoning `apps/studio/plugins/reinforce/tests`
applies to cupy, where the documented exclusion had silently gone stale. Their tests are
still runnable deliberately, by pointing pytest straight at `backend/vendor/...`; what is
excluded is their appearance in *our* result.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Relative to this directory, which is what pytest resolves these against.
collect_ignore_glob = ["vendor/*"]
