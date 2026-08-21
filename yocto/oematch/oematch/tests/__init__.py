"""Tests for oematch.

These live INSIDE the package, which looks like the wrong place and is not. pybuild runs
`python3 -m unittest discover` from `.pybuild/cpython3_*/build`, and that directory holds
only what the package installs -- a top-level `tests/` is never copied there, so the
build reported `Ran 0 tests in 0.000s / NO TESTS RAN` while a suite sat beside setup.
Putting them in the package means the same command finds them at build time and on an
installed system:

    python3 -m unittest discover -s /usr/lib/python3/dist-packages/oematch/tests -t /

Everything here builds its own throwaway corpus in a temp directory. The one exception
is `test_upstream.TheCuratedGroupingsTests`, which needs the real 479-layer corpus and
skips with a message when it is absent -- a build machine has no corpus and must not
fail for it.
"""
