"""`scripts/enable-surfaces.sh` -- does the operator tool know about every gated surface?

Written because it did not. Thirteen `SYMONEURAL_<NAME>_ENABLED` switches gate the serving path,
and the script that exists to set exactly those could set four. Studio was one of the seven it
could not, which is why the live rack showed Studio `offline` with no sanctioned command an
operator could run to change it: not a bug in Studio, a gap in the tool. With the `studio)` and
`asic)` arms added the split is six switchable to seven unswitchable, which is the count
`test_the_surfaces_this_script_cannot_switch_are_exactly_the_known_seven` holds it at. This
docstring said "eleven ... six" until 2026-08-20 and named a test that had already been
renamed twice; the figures below are re-measured at `ba523b0`, and the rule that catches this
class of rot is that a docstring naming a test must name one that exists.

Thirteen switches, not thirteen apps: the thirteen are read across fourteen packages and the
mapping is neither one-to-one nor onto. `SYMONEURAL_ASIC_ENABLED` is checked in `asicminer` and `voice`,
`SYMONEURAL_MINING_ENABLED` in `asicminer` and `cryptominer`, `SYMONEURAL_GATEWAY_ENABLED` in `gateway` and
`settlement`. `gated_surfaces()` below counts switches because switches are what the script
writes; no assertion here depends on a package count.

That class of gap is invisible to every existing test, because Studio's own tests pass with
the surface off and the script had no tests at all.

## Why this file reads the script instead of running it

`enable-surfaces.sh:46` refuses to run as anything but root, before it parses a single
argument -- so not even `--show` executes unprivileged. That check is correct and stays: the
file it reads is `/etc/symoneural/api.env`, root-owned 0600, and a non-root `--show` could only
report "absent", which is a lie in the one direction that matters. `ENV_FILE` is likewise a
plain assignment at `:38` rather than an overridable default. Making either one testable would
mean loosening a privilege boundary to suit a test, so these assertions read the script's text.

That makes them structural, and structural assertions rot silently, so each one below states
what it would catch and the vacuity guard asserts its own regexes still match.

One exception, and it is the important one: `WriteLoopBehaviourTests` extracts the write loop
and runs it against stubs. Reading the loop cannot tell `${pair#* }` from `${pair%* }`, and
that one character decides whether the file gets `SYMONEURAL_STUDIO_ENABLED=1` or `SYMONEURAL_0_ENABLED=1`.
Nothing textual, and no `bash -n`, sees the difference.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "enable-surfaces.sh"
APPS = Path(__file__).resolve().parent

# Every surface the backend gates on, read from the code that does the gating.
GATE = re.compile(r"\bSYMONEURAL_([A-Z0-9]+)_ENABLED\b")

# `coder)   WANT_CODER=1 ;;` -- the argument the operator types, and the flag it sets.
CASE_ARM = re.compile(r"^\s{4}([a-z]+)\)\s*WANT_([A-Z0-9]+)=1\s*;;", re.M)

# The pair list the write loop iterates: "$WANT_CODER CODER".
LOOP_PAIR = re.compile(r'"\$WANT_([A-Z0-9]+)\s+([A-Z0-9]+)"')

# The loop itself, start to `done`, so it can be run instead of merely read.
LOOP_SRC = re.compile(r"^for pair in\b.*?^done$", re.M | re.S)

# Gateway cannot share the loop body -- it writes two more values -- so it is matched on its
# own literal branch rather than being special-cased in the test's expectations.
GATEWAY_SET = re.compile(r"^\s*set_kv\s+SYMONEURAL_GATEWAY_ENABLED\s+1\s*$", re.M)

# The drop-in heredoc line. Compiled with re.M because it is one line inside the script,
# not the whole file -- assertRegex takes no flags, so this cannot be inlined there.
ENV_FILE_LINE = re.compile(r"^EnvironmentFile=-\$ENV_FILE$", re.M)


def gated_surfaces() -> set[str]:
    found: set[str] = set()
    for py in APPS.rglob("*.py"):
        if py.name.startswith("test_") or "/tests/" in py.as_posix():
            continue
        found |= set(GATE.findall(py.read_text(encoding="utf-8", errors="replace")))
    return found


class EnableSurfacesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text()
        cls.arms = dict(CASE_ARM.findall(cls.text))          # "coder" -> "CODER"
        cls.loop = {name for _flag, name in LOOP_PAIR.findall(cls.text)}
        cls.gated = gated_surfaces()
        cls.writable = set(cls.loop)
        if GATEWAY_SET.search(cls.text):
            cls.writable.add("GATEWAY")

    def test_the_regexes_in_this_file_still_match_the_script(self):
        """The guard against every other test in this file passing vacuously. If the script is
        reformatted so `CASE_ARM` or `LOOP_PAIR` stops matching, the sets go empty and the
        subset assertions below all succeed against nothing. This fails first and loudly."""
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is gone")
        self.assertGreaterEqual(len(self.arms), 6,
                                f"CASE_ARM matched {len(self.arms)} arms; the script has 6")
        self.assertGreaterEqual(len(self.loop), 5,
                                f"LOOP_PAIR matched {len(self.loop)}; the loop carries 5")
        self.assertTrue(GATEWAY_SET.search(self.text), "the gateway write branch is gone")
        self.assertGreaterEqual(len(self.gated), 12,
                                f"only {len(self.gated)} gated surfaces found in apps/")

    def test_studio_is_switchable_by_the_sanctioned_tool(self):
        """The regression proper. Before this landed, `enable-surfaces.sh studio` died with
        "Unknown argument: studio" and there was no supported way to bring the Studio rack row
        out of `offline`. Both halves are asserted, because the argument existing and the key
        being written are separate failures: an arm with no write is a script that reports
        success and changes nothing."""
        self.assertEqual(self.arms.get("studio"), "STUDIO",
                         "no `studio)` case arm -- the argument is rejected by the parser")
        self.assertIn("STUDIO", self.loop,
                      "`studio` parses but writes no SYMONEURAL_STUDIO_ENABLED")

    def test_every_argument_the_parser_accepts_writes_something(self):
        """Generalises the above to all five, so the next surface added cannot repeat the
        half-fix. A `WANT_X` flag that no write path reads is a silent no-op."""
        for arg, flag in sorted(self.arms.items()):
            with self.subTest(surface=arg):
                self.assertIn(flag, self.writable,
                              f"`{arg}` sets WANT_{flag} and nothing ever reads it")

    def test_the_surfaces_this_script_cannot_switch_are_exactly_the_known_seven(self):
        """The gap this file exists to make visible, pinned in both directions.

        This was six, then five, six again, and is now seven -- and the way NEWS and DISCOVERY
        joined it is the point of the test. ASIC came off because its rack row was in exactly the
        state Studio\'s had been -- SubUnit `asicminer` (api.py:1655) telling an operator to set
        SYMONEURAL_ASIC_ENABLED and SYMONEURAL_ASIC_TOKEN with nothing sanctioned that would do it
        -- and the earlier version of this docstring got its reason wrong: it said ASIC "points at
        hardware that may not be present", which is true and is not an argument against a switch.
        Absent hardware reads `offline · no rigs configured`, which is honest; an unset switch the
        operator was told to set and given no command for is not.

        NEWS was never on the list and should have been from the day it landed. `GATE` above
        searched for `SYM_([A-Z0-9]+)_ENABLED`, and the news ticker was the first surface
        named in the house style ahead of the rename -- its gate has always been
        `SYMONEURAL_NEWS_ENABLED` (apps/news/__init__.py:53). So this test, whose
        whole job is to notice a gated surface with no switch, could not see it: the surface
        was invisible to the regex rather than exempted by a decision. The rename made it
        visible, which is the second time in this repo that a naming change has surfaced a
        tripwire that was quietly matching nothing. Its reason for having no arm is in the
        script with the others.

        DISCOVERY is the first name this test caught on the way in rather than after the fact.
        apps/symoneuraldiscovery reads SYMONEURAL_DISCOVERY_ENABLED, so it joined `gated` the
        moment the package existed, and this assertion failed in the same run that first
        collected that package's own 37 tests -- before its first commit, not after an
        operator found a rack row stuck on `offline`. That is the whole intended behaviour of
        this test, and the resolution was to write the reason into the script, not to widen
        the literal below and move on.

        Each reason is recorded in the script rather than here, and
        `test_the_script_records_why_each_unswitchable_one_has_no_arm` below asserts the
        record still names them. This test fails when a fourteenth gated surface appears with
        no switch AND when one of these seven quietly gains one, and either way the fix is to
        make the decision there rather than discover it from a rack row reading `offline`."""
        known_unswitchable = {"ACCOUNTS", "DISCOVERY", "EXP", "MINING", "NEWS", "REINFORCE",
                              "VOICE"}
        self.assertEqual(self.gated - self.writable, known_unswitchable)
        self.assertEqual(self.writable - self.gated, set(),
                         "the script writes an ENABLED key no app reads")

    def test_the_script_records_why_each_unswitchable_one_has_no_arm(self):
        """A set assertion cannot tell a decision from an omission.

        The test above pins WHICH surfaces have no arm. Nothing pinned WHY, so the next author
        to add a `voice` arm would widen one set literal and never meet the argument against
        it -- api.py:2317-2319 saying the row is deliberately absent because /voice.html does
        not exist. The script carries that argument in a block under a stable heading; this
        asserts every name in it is still there, so deleting the reasoning is a test failure
        and not a tidy-up."""
        head = "# ## The gated surfaces this script deliberately does not switch"
        self.assertIn(head, self.text, "the record of why is gone, or its heading changed")
        block = self.text.split(head, 1)[1].split("\ninstall -d", 1)[0]
        for surface in sorted({"ACCOUNTS", "DISCOVERY", "EXP", "MINING", "NEWS",
                               "REINFORCE", "VOICE"}):
            with self.subTest(surface=surface):
                self.assertIn(surface.lower(), block,
                              f"{surface} has no arm and the script no longer says why")
        # Vacuity guard for this test specifically: an empty block would pass every `assertIn`
        # above if the split ever stopped matching.
        self.assertGreater(len(block), 900, "the block matched but is too short to be it")

    def test_the_network_names_the_script_offers_are_the_ones_the_code_accepts(self):
        """Two files had to agree and nothing made them.

        `--network` is validated by a `case` list here; the value is resolved by
        `chain.OPERATOR_NETWORKS` there. A name in one and not the other is either an argument
        the script accepts and the surface refuses, or a working value nobody can discover.
        Read rather than executed, for the reason the module docstring gives."""
        from apps.gateway import chain          # noqa: PLC0415 -- see module docstring
        for name in chain.OPERATOR_NETWORKS:
            with self.subTest(network=name):
                self.assertIn(name, self.text,
                              f"{name} resolves in chain.py but --network rejects it")
        # The canonical TRON names must not be ACCEPTED. They do appear in the script -- it
        # has an arm that refuses them by name with a useful message, which is worth keeping --
        # so this reads the accepting arm specifically rather than the whole file.
        accept = [ln for ln in self.text.splitlines()
                  if ln.strip().endswith(") ;;") and "symoneural-" in ln]
        self.assertEqual(len(accept), 1, f"expected one accepting --network arm, got {accept}")
        for canonical in chain.NODES:
            with self.subTest(canonical=canonical):
                self.assertNotIn(canonical, accept[0],
                                 f"--network accepts {canonical}, which the code refuses")

    def test_every_switchable_surface_is_named_in_the_usage_header(self):
        """A switch nobody can discover is barely a switch. The header block is the only
        documentation an operator reads before running this with sudo."""
        header = "\n".join(self.text.splitlines()[:40])
        for arg in sorted(self.arms):
            with self.subTest(surface=arg):
                self.assertIn(arg, header, f"`{arg}` is switchable but undocumented")

    def test_tokens_are_never_written_to_an_Environment_line(self):
        """The script's own header argues this at :20-23: `systemctl show symoneural-api`
        prints `Environment=` to any user on the box, so a token there is a shared secret
        readable by an unprivileged command. The drop-in must use `EnvironmentFile=` with the
        leading `-`. Asserted against the heredoc, not against the comment claiming it."""
        self.assertTrue(ENV_FILE_LINE.search(self.text),
                        "the drop-in no longer references the env file, or dropped the "
                        "leading '-' that keeps a missing file from bricking the service")
        offenders = [ln for ln in self.text.splitlines()
                     if ln.strip().startswith("Environment=") and "SYMONEURAL_" in ln]
        self.assertEqual(offenders, [], "a SYMONEURAL_ value is written to an Environment= line")


class WriteLoopBehaviourTests(unittest.TestCase):
    """The write loop, extracted and executed with `set_kv` and `gen_token` stubbed.

    This needs no root and writes no file, so it is not the boundary the module docstring
    declines to loosen -- the loop reads four variables and calls two functions, none of
    which is privileged. What it catches is the whole class of defect that the textual tests
    are blind to by construction: a parameter expansion that still parses.
    """

    def run_loop(self, **wants) -> list[str]:
        found = LOOP_SRC.search(SCRIPT.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            found, "the write loop is no longer a `for pair in ... done` block; this class "
                   "silently stops testing anything if that regex is left unfixed")
        body = found.group(0)
        # Every flag the PARSER sets, defaulted off, with the caller\'s overrides on top.
        #
        # The defaults deliberately come from `CASE_ARM` -- the `coder) WANT_CODER=1` arms --
        # and not from the loop being tested. Reading them off the loop would define whatever
        # the loop mentions, which is exactly what `set -u` is here to catch: rename the
        # loop\'s `$WANT_CODER` to `$WANT_KODER` and this still fails, because the parser
        # never sets WANT_KODER. Before this, each test listed the flags by hand and adding a
        # sixth surface broke three tests that were not about the sixth surface.
        flags = {flag: 0 for flag in CASE_ARM.findall(SCRIPT.read_text())}
        flags = {f: 0 for _arg, f in CASE_ARM.findall(SCRIPT.read_text())}
        flags.update(wants)
        # `set -u` so a WANT_ variable the loop reads but the parser never sets is an error
        # here rather than an empty write.
        program = "\n".join([
            "set -u",
            "set_kv() { printf '%s=%s\\n' \"$1\" \"$2\"; }",
            "gen_token() { printf TOK; }",
            *(f"WANT_{name}={value}" for name, value in flags.items()),
            body,
        ])
        out = subprocess.run(["bash", "-c", program], capture_output=True, text=True,
                             timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.splitlines()

    def test_the_loop_writes_the_key_names_the_backend_actually_reads(self):
        """The `${pair#* }`/`${pair%* }` test. Under `%` this reads SYMONEURAL_0_ENABLED and the
        surface stays offline after Garrett runs the command and is told it worked."""
        self.assertEqual(
            self.run_loop(CODER=1, PROJECT=0, RACK=0, STUDIO=1),
            ["SYMONEURAL_CODER_ENABLED=1", "SYMONEURAL_CODER_TOKEN=TOK",
             "SYMONEURAL_STUDIO_ENABLED=1", "SYMONEURAL_STUDIO_TOKEN=TOK"])

    def test_each_enabled_surface_gets_its_own_token(self):
        """Four surfaces on at once, which is what `--all` amounts to. Asserts the full
        product rather than a subset, so a fifth pair added without a matching case arm
        shows up here as an unexpected line."""
        self.assertEqual(
            self.run_loop(CODER=1, PROJECT=1, RACK=1, STUDIO=1),
            [line for name in ("CODER", "PROJECT", "RACK", "STUDIO")
             for line in (f"SYMONEURAL_{name}_ENABLED=1", f"SYMONEURAL_{name}_TOKEN=TOK")])

    def test_a_surface_not_asked_for_is_never_written(self):
        """The `[ "$want" -eq 1 ] || continue` arm. Rewriting it as `[ ... ] && set_kv ...`
        would make the loop's last iteration decide the script's exit status under `set -e`;
        this asserts the skip, and the exit-status check is in `run_loop`."""
        self.assertEqual(self.run_loop(CODER=0, PROJECT=0, RACK=0, STUDIO=0), [])

if __name__ == "__main__":
    unittest.main()
