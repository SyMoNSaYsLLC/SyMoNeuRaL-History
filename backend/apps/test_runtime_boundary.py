"""The runtime must not require /yocto. These tests fail if anything reintroduces it.

Task #108. Garrett, 2026-08-26, setting the rule precisely:

    "The rule is not 'never touch /yocto.' The rule is: Build from /yocto when appropriate,
    but never require /yocto at runtime."

So this file is deliberately narrow. It does **not** grep the repository for the string
`/yocto` -- the `yocto/` layer directory, BitBake recipes, build logs and CMake caches all
contain it legitimately, and a test that fails on those is a test people learn to ignore.
What it checks is the two places a runtime dependency can actually be created:

1. **The installable artifacts in this repository** -- the unit templates. If a template
   hardcodes `/yocto` instead of `@@ROOT@@`, then `ops/install-runtime.sh` will install a
   live dependency on the next run, on this box or any other. That is catchable here, with
   no root and no running services, which is why it is the part that lives in the test suite.

2. **The live system**, when this suite happens to run on the serving box with the units
   installed. Those assertions SKIP rather than fail when the units are absent or unreadable,
   because a developer checkout is not a broken deployment and a suite that cannot pass off
   the serving box is a suite that gets excluded from CI.

The deep live checks -- process cwd/argv/fds/maps, ELF RPATH/RUNPATH, boot behaviour -- live
in `ops/verify-runtime.sh`, which the installer runs and refuses to finish without. This file
asserts that script exists and is wired in, rather than duplicating it into Python where the
two would drift.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
OPS = REPO / "ops"
UNIT_NAMES = ("symoneural-api", "symoneural-gateway", "symoneural-deploy")
UNIT_DIR = pathlib.Path("/etc/systemd/system")

#: The canonical runtime root. Hardcoded on purpose: the whole point is that it is not
#: configurable at runtime, and a test that reads the answer from the thing under test
#: asserts nothing.
CANON = "/home/google/Symoneural"

#: Directives that make a path a RUNTIME dependency. `Documentation=` is not one -- it is a
#: URL for a human -- but it is included anyway, because these units are generated from
#: templates and a stale Documentation= line means the template was not re-rendered, which is
#: the defect worth catching even though the line itself is inert.
PATH_DIRECTIVES = re.compile(
    r"^\s*(WorkingDirectory|ExecStart|ExecStartPre|ExecStartPost|ExecStop|ExecStopPost|"
    r"ExecReload|Environment|EnvironmentFile|ConditionPathExists|ConditionPathIsDirectory|"
    r"ReadOnlyPaths|ReadWritePaths|BindPaths|BindReadOnlyPaths|RootDirectory|Documentation)"
    r"\s*=\s*(.*)$")


def directive_lines(text: str):
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = PATH_DIRECTIVES.match(line)
        if m:
            yield m.group(1), m.group(2)


class UnitTemplateTests(unittest.TestCase):
    """The installable artifacts. These run anywhere, need no root, and are the real guard."""

    def test_every_unit_template_exists(self):
        for u in UNIT_NAMES:
            self.assertTrue((OPS / f"{u}.service").is_file(),
                            f"ops/{u}.service is missing; ops/install-runtime.sh installs from it")

    def test_no_template_hardcodes_yocto_in_a_path_directive(self):
        """The one that would put /yocto back on every box the installer touches."""
        for u in UNIT_NAMES:
            text = (OPS / f"{u}.service").read_text(encoding="utf-8")
            for name, value in directive_lines(text):
                self.assertNotIn(
                    "/yocto", value,
                    f"ops/{u}.service has /yocto in {name}=. Templates must use @@ROOT@@ so "
                    f"install-runtime.sh can render the canonical root.")

    def test_templates_use_the_placeholder(self):
        """A template with no @@ROOT@@ has a path baked in, which is the same bug earlier."""
        for u in UNIT_NAMES:
            text = (OPS / f"{u}.service").read_text(encoding="utf-8")
            self.assertIn("@@ROOT@@", text,
                          f"ops/{u}.service has no @@ROOT@@ placeholder, so its paths are fixed")

    def test_rendering_a_template_produces_no_yocto_and_no_leftover_placeholder(self):
        """Render exactly as install-runtime.sh does, then assert on the result."""
        for u in UNIT_NAMES:
            text = (OPS / f"{u}.service").read_text(encoding="utf-8").replace("@@ROOT@@", CANON)
            self.assertNotRegex(text, r"@@[A-Z_]+@@",
                                f"ops/{u}.service still has a placeholder after rendering")
            for name, value in directive_lines(text):
                self.assertNotIn("/yocto", value,
                                 f"rendered {u}.service has /yocto in {name}=")
            self.assertIn(CANON, text, f"rendered {u}.service does not mention {CANON}")


class OpsScriptTests(unittest.TestCase):
    """The coded migration path exists, is executable, and is wired together."""

    SCRIPTS = ("install-runtime.sh", "rollback-runtime.sh", "verify-runtime.sh",
               "build-gateway.sh")

    def test_the_scripts_exist_and_are_executable(self):
        for s in self.SCRIPTS:
            p = OPS / s
            self.assertTrue(p.is_file(), f"ops/{s} is missing")
            self.assertTrue(p.stat().st_mode & 0o111, f"ops/{s} is not executable")

    def test_the_scripts_are_syntactically_valid(self):
        if not shutil.which("bash"):
            self.skipTest("bash not available")
        for s in self.SCRIPTS:
            r = subprocess.run(["bash", "-n", str(OPS / s)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"ops/{s} has a syntax error: {r.stderr}")

    def test_the_installer_runs_the_verifier(self):
        """An installer that does not verify is an installer that can succeed while wrong."""
        text = (OPS / "install-runtime.sh").read_text(encoding="utf-8")
        self.assertIn("verify-runtime.sh", text)

    def test_the_installer_backs_up_and_can_roll_back(self):
        text = (OPS / "install-runtime.sh").read_text(encoding="utf-8")
        self.assertIn("unit-backups", text, "the installer takes no backup")
        self.assertIn("rolling back", text.lower(), "the installer has no rollback path")

    def test_the_installer_supports_a_dry_run(self):
        self.assertIn("--dry-run", (OPS / "install-runtime.sh").read_text(encoding="utf-8"))


class ManifestTests(unittest.TestCase):
    """The model manifest is what makes an uncommitted weight file verifiable."""

    def test_the_chat_model_manifest_is_present_and_complete(self):
        p = OPS / "manifests" / "llm-chat-model.json"
        self.assertTrue(p.is_file(), "ops/manifests/llm-chat-model.json is missing")
        m = json.loads(p.read_text(encoding="utf-8"))
        for key in ("relative_path", "size_bytes", "sha256", "gguf_version",
                    "architecture", "model_identity", "file_type"):
            self.assertIn(key, m, f"the manifest has no {key!r}")
        self.assertEqual(m["relative_path"],
                         "backend/models/llm/symon-1.0-7b-q4_k_m.gguf")
        self.assertEqual(len(m["sha256"]), 64)
        self.assertNotIn("/yocto", m["canonical_absolute_path"])
        self.assertTrue(m["canonical_absolute_path"].startswith(CANON))

    def test_the_manifest_records_a_real_identity_not_a_filename(self):
        """A rename would be caught by comparing these against the file's own header."""
        m = json.loads((OPS / "manifests" / "llm-chat-model.json").read_text(encoding="utf-8"))
        self.assertEqual(m["architecture"], "qwen2")
        self.assertEqual(m["file_type"], 15)          # MOSTLY_Q4_K_M
        self.assertEqual(m["model_identity"]["size_label"], "7B")


class LiveSystemTests(unittest.TestCase):
    """Assertions about the serving box. SKIP off it -- see the module docstring."""

    def _unit_text(self, name: str) -> str:
        p = UNIT_DIR / f"{name}.service"
        if not p.exists():
            self.skipTest(f"{p} not present -- not the serving box")
        try:
            return p.read_text(encoding="utf-8")
        except PermissionError:
            self.skipTest(f"{p} unreadable without root")

    def test_installed_units_do_not_reference_yocto(self):
        for u in UNIT_NAMES:
            text = self._unit_text(u)
            for name, value in directive_lines(text):
                self.assertNotIn("/yocto", value,
                                 f"installed {u}.service has /yocto in {name}=")

    def test_installed_units_point_at_the_canonical_root(self):
        for u in UNIT_NAMES:
            text = self._unit_text(u)
            wd = [v for n, v in directive_lines(text) if n == "WorkingDirectory"]
            self.assertTrue(wd, f"installed {u}.service has no WorkingDirectory")
            self.assertEqual(wd[0].strip(), CANON,
                             f"installed {u}.service serves from {wd[0]!r}")

    def test_the_deleted_home_yocto_directory_was_not_recreated(self):
        self.assertFalse(pathlib.Path("/home/google/yocto").exists(),
                         "/home/google/yocto was permanently deleted and must not be recreated")


if __name__ == "__main__":
    unittest.main()
