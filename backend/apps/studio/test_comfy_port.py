"""The Python bridge and the shell that starts the server must agree on where ComfyUI is.

Two files hold this one address. `scripts/symoneural-ui.sh` *starts* ComfyUI on a host and port;
`apps/studio/comfy.py` *talks to it* on a host and port. Nothing makes them agree, and they
are edited by different kinds of change -- an ops tweak touches the shell, a bridge fix
touches the Python -- which is the same shape as the ExecStart path that took the public API
down for four hours: two plausible files, and the defect living only in the gap between them.

The failure mode if they drift is not a crash. `scripts/symoneural-ui.sh start` reports success and
writes a pidfile, the server really is up, and every Studio render then fails with
`comfyui_unreachable` against the port nothing is listening on. That reads as a Studio bug and
is not one.

## Why this is not `grep 8188 -- registry.py`

`PROJECT-TASKS.md` #73 carried `check: grep 8188 -- backend/apps/studio/registry.py`, on the
reading that the port was "hard-coded somewhere other than the registry that is supposed to
own it". `registry.py` is not that registry: it is the agent **tool** registry -- signature
introspection and JSON Schema generation -- and it holds no addresses of any kind. Satisfying
that check would have meant writing a port constant into a file with no business holding one,
purely to turn a percentage green. The module that owns this address is `comfy.py`, which
already does it correctly: `base_url()` reads `SYMONEURAL_COMFY_URL`, then
`SYMONEURAL_COMFY_HOST`/`SYMONEURAL_COMFY_PORT`, then falls back to the constants below, and
`api.py:87` calls `symoneuralenv.promote()` so the legacy `SYM_COMFY_PORT` spelling the shell
still accepts arrives on the Python side under its new name.

So the honest invariant is not "the literal appears in file X". It is "the two defaults are
the same number, and both files read the same variable to override it" -- which is checkable
dry, on any machine, with no ComfyUI running and no GPU.

Read as text rather than imported on purpose. `comfy.py` imports `httpx` and `websockets` at
module scope, and this assertion has nothing to do with whether those are installed; a test
that can only run where the bridge's dependencies are present is a test that skips exactly
where an ops change is most likely to have been made.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "backend" / "apps" / "studio" / "comfy.py"
LAUNCHER = ROOT / "scripts" / "symoneural-ui.sh"

# The variable both sides must read. `comfy.py` reads it directly; `symoneural-ui.sh` reads it first
# and only then falls back to the legacy `SYM_` spelling, which `symoneuralenv.promote()`
# rewrites for the Python side at startup.
PORT_ENV = "SYMONEURAL_COMFY_PORT"


def _bridge_defaults(text: str) -> tuple[str, str]:
    """(host, port) as the Python bridge falls back to them. Raises if either is gone."""
    host = re.search(r'^DEFAULT_HOST\s*=\s*"([^"]+)"', text, re.M)
    port = re.search(r"^DEFAULT_PORT\s*=\s*(\d+)", text, re.M)
    if host is None or port is None:
        raise AssertionError(
            f"{BRIDGE} no longer declares DEFAULT_HOST/DEFAULT_PORT at module scope; "
            "this comparison has stopped comparing anything and must be rewritten, not "
            "deleted")
    return host.group(1), port.group(1)


def _launcher_defaults(text: str) -> tuple[str, str]:
    """(host, port) as the shell starts the server. Raises if either is gone."""
    # PORT="${SYMONEURAL_COMFY_PORT:-${SYM_COMFY_PORT:-8188}}"  -- the last literal is the
    # default, whatever the fallback chain in front of it looks like.
    port = re.search(r'^PORT="\$\{.*?(\d+)\}*"\s*$', text, re.M)
    host = re.search(r'^HOST="?([\d.]+)"?\s*$', text, re.M)
    if host is None or port is None:
        raise AssertionError(
            f"{LAUNCHER} no longer sets HOST/PORT in the expected form; same warning as "
            "above -- rewrite this parse, do not drop the assertion")
    return host.group(1), port.group(1)


def _disagreement(bridge_text: str, launcher_text: str) -> str | None:
    """None if the two files address the same ComfyUI, else what differs."""
    b_host, b_port = _bridge_defaults(bridge_text)
    l_host, l_port = _launcher_defaults(launcher_text)
    if (b_host, b_port) != (l_host, l_port):
        return (f"comfy.py talks to {b_host}:{b_port} but symoneural-ui.sh starts the server on "
                f"{l_host}:{l_port}; every Studio render would fail with "
                "`comfyui_unreachable` while the launcher reported success")
    if PORT_ENV not in bridge_text:
        return f"comfy.py no longer reads {PORT_ENV}, so the launcher's override is ignored"
    if PORT_ENV not in launcher_text:
        return (f"symoneural-ui.sh no longer reads {PORT_ENV}, so setting it moves the bridge "
                "without moving the server")
    return None


class ComfyPortAgreementTests(unittest.TestCase):

    def test_the_comparison_catches_a_drifted_port(self):
        """Runs on the text, so it runs everywhere -- including where the files are correct.

        Without this the class is one assertion that passes today and would still pass if
        `_disagreement` were quietly rewritten to `return None`. A check that cannot fail is
        the thing #73's own notes have now retired twice.
        """
        bridge = f'DEFAULT_HOST = "127.0.0.1"\nDEFAULT_PORT = 8188\n{PORT_ENV}\n'
        drifted = f'PORT="${{{PORT_ENV}:-8199}}"\nHOST="127.0.0.1"\n'
        why = _disagreement(bridge, drifted)
        self.assertIsNotNone(why, "a drifted port was reported as agreeing")
        self.assertIn("8199", why)

        agreeing = f'PORT="${{{PORT_ENV}:-8188}}"\nHOST="127.0.0.1"\n'
        self.assertIsNone(_disagreement(bridge, agreeing))

    def test_the_comparison_catches_a_dropped_override(self):
        """Equal defaults are not enough: the override has to reach both sides."""
        bridge = 'DEFAULT_HOST = "127.0.0.1"\nDEFAULT_PORT = 8188\n'  # no PORT_ENV
        launcher = f'PORT="${{{PORT_ENV}:-8188}}"\nHOST="127.0.0.1"\n'
        why = _disagreement(bridge, launcher)
        self.assertIsNotNone(why, "a bridge that ignores the override was reported as fine")
        self.assertIn(PORT_ENV, why)

    def test_a_parse_that_stopped_parsing_is_an_error_not_a_pass(self):
        """The vacuity guard. If either file is restructured, this class must go red rather
        than silently comparing two things it no longer found."""
        with self.assertRaises(AssertionError):
            _bridge_defaults("nothing that looks like a constant\n")
        with self.assertRaises(AssertionError):
            _launcher_defaults("nothing that looks like an assignment\n")

    def test_the_bridge_and_the_launcher_agree_on_disk(self):
        why = _disagreement(BRIDGE.read_text(), LAUNCHER.read_text())
        self.assertIsNone(why, why)


if __name__ == "__main__":
    # At the END of the file, with backend/ on the path: see the block at the foot of
    # apps/test_streamer_migration.py for what a misplaced one of these hides.
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    unittest.main()
