"""Every path `scripts/gpu-governor.sh` names must exist, and its kills must name our engines.

Two defects motivated this file, both found on 2026-08-20 and both of the same shape: a
command whose primary silently could not run, masked by a `||` fallback that could.

    chat)  "$HERE/symoneural" _stop-chat ... || pkill -f 'llama-server'
    comfy) "$HERE/comfyui.sh" stop        ... || pkill -f 'ComfyUI/main.py'

`HERE` is the repo root, so those were `<root>/symoneural` and `<root>/comfyui.sh`. Neither
has ever existed -- the CLI is `bin/symoneural-cli` and the launcher, since 2026-08-21, is
`scripts/symoneural-ui.sh` --
so **every** chat eviction and **every** ComfyUI eviction took the fallback. For comfy that
fallback is the ungraceful kill its own arm spends a paragraph arguing against: the process
exits before the driver returns the memory and the next tenant OOMs at step 0.

Nothing caught it because a `||` chain cannot fail. This does, by reading the script and
checking the filesystem rather than trusting either.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GOVERNOR = ROOT / "scripts" / "gpu-governor.sh"
SOURCE = GOVERNOR.read_text()

#: `"$HERE/<path>"` and `"$ROOT/<path>"` as invoked commands. Comment lines are stripped
#: before this is applied: the header comment on `HERE` quotes the two old broken spellings
#: verbatim so the next reader knows what went wrong, and matching those would make this
#: file fail on its own documentation. (It did, first run.)
INVOKED = re.compile(r'"\$(?:HERE|ROOT)/([A-Za-z0-9._/-]+)"')

#: The script with comments removed, which is what any check on *behaviour* must read.
CODE = "\n".join(l for l in SOURCE.splitlines() if not l.lstrip().startswith("#"))

#: What the engines are actually called. `bin/` anchors these to the binary rather than to a
#: log file or a python process that merely mentions the name.
LLM = "bin/symoneural-llm"
DIFFUSE = "bin/symoneural-diffuse"

#: Names this project may not kill by, because it neither builds nor ships them. Renaming an
#: engine without moving its pkill leaves the kill switch pointing at nothing.
RETIRED = ("llama-server", "sd-cli", "llama.cpp", "stable-diffusion.cpp",
           "ComfyUI/main.py")
#: `ComfyUI/main.py` joined that list on 2026-08-21. The render UI is now
#: `engines/symoneural-ui`, produced by `tools/fork_render_ui.sh` from the vendored tree, and
#: the directory that pattern named is not on disk under any spelling -- so the `comfy)`
#: fallback would have matched nothing while reporting success, which is this file's subject.


class EveryInvokedPathExists(unittest.TestCase):
    def test_the_governor_only_invokes_paths_that_are_on_disk(self):
        """A `||` fallback makes a missing primary invisible. Check the disk instead."""
        found = INVOKED.findall(CODE)
        self.assertGreaterEqual(len(found), 2,
                                "the $HERE/$ROOT invocations vanished -- if they moved, move "
                                "this check with them rather than letting it pass vacuously")
        for rel in found:
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).exists(),
                                f"gpu-governor.sh invokes $HERE/{rel}, which is not on disk. "
                                "Its `||` fallback will run instead and nothing will say so.")

    def test_the_two_graceful_stops_are_still_the_ones_we_expect(self):
        """Named explicitly: these two are the arms whose fallback is *worse* than the
        primary, so losing either to a silent path break is a real regression and not a
        cosmetic one."""
        for rel in ("bin/symoneural-cli", "scripts/symoneural-ui.sh"):
            with self.subTest(path=rel):
                self.assertIn(f'"$HERE/{rel}"', CODE,
                              f"the governor no longer invokes {rel}; the graceful stop it "
                              "guards has been lost or renamed")


class EvictionKillsNameOurEngines(unittest.TestCase):
    def test_no_eviction_arm_kills_by_a_retired_upstream_name(self):
        """`tools/fork_engines.sh` builds both engines under our names. A pkill left on an
        upstream name matches no running process, so the governor logs a successful
        eviction while the tenant keeps the card -- the failure the `miner)` arm records."""
        kills = [l for l in CODE.splitlines() if "pkill" in l]
        self.assertTrue(kills, "no pkill lines found -- this file is reading the wrong script")
        for line in kills:
            for retired in RETIRED:
                with self.subTest(line=line.strip()[:60], retired=retired):
                    self.assertNotIn(retired, line,
                                     f"an eviction still kills by {retired!r}, which this "
                                     "project does not build")

    def test_both_engines_are_reachable_by_the_default_arm(self):
        """The `*)` arm is what an unregistered surface falls through to. It must reach both
        engines, or an unnamed tenant is 'evicted' while it holds the card."""
        default = [l for l in CODE.splitlines()
                   if l.lstrip().startswith("*)") and "pkill" in l]
        self.assertEqual(len(default), 1,
                         "expected exactly one default arm that kills; the script has more "
                         f"than one `*)` case, so match on the killing one: found {default}")
        for name in (LLM, DIFFUSE):
            self.assertIn(name, default[0],
                          f"the default eviction arm does not reach {name}")


if __name__ == "__main__":
    unittest.main()
