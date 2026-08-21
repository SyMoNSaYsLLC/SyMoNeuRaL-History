"""The gateway unit's ExecStart has to name the crate that is actually on disk.

This exists because the string in that one line took the **public API** down for four hours
and nothing went red. `712e15b` moved the Rust crate to `backend/apps/gateway/` with every
other app -- Garrett: *"all applications should be in /backend/apps"* -- and
`ops/symoneural-gateway.service` kept pointing at `@@ROOT@@/symon-gateway/target/release/`.
The unit stayed `enabled`, so `systemctl is-active` reported `activating` against a path with
no binary at it, `ops/Caddyfile`'s `/api/*` hop to `127.0.0.1:8000` had nothing to reach, and
every visitor got **502** -- while `api.py` was healthy on :8800 and all thirteen rack units
read correctly on the loopback. The whole suite was green throughout, because every suite in
this repo exercises `api.py` and no check anywhere read this file.

Deliberately NOT asserting that the binary exists. `target/` is gitignored, so on a fresh
clone the honest state is "crate present, not built" and `install-gateway.sh` already refuses
in that case with the command to build it. What is invariant, build or no build, is that the
path names *this repo's crate*: the directory holds a `Cargo.toml` whose package name is the
binary the unit launches. That is the half that went stale, and it is checkable dry.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
UNIT = ROOT / "ops" / "symoneural-gateway.service"
INSTALLER = ROOT / "scripts" / "install-gateway.sh"


def _exec_start():
    for line in UNIT.read_text().splitlines():
        if line.startswith("ExecStart="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"{UNIT} has no ExecStart line at all")


class GatewayUnitPathTests(unittest.TestCase):
    def test_exec_start_is_rooted_on_the_installer_placeholder(self):
        """`install-gateway.sh` substitutes @@ROOT@@; a literal path would install wrong."""
        self.assertTrue(_exec_start().startswith("@@ROOT@@/"), _exec_start())

    def test_exec_start_names_a_crate_that_exists_in_this_repo(self):
        exec_start = _exec_start()
        m = re.fullmatch(r"@@ROOT@@/(.+)/target/release/([\w-]+)", exec_start)
        self.assertIsNotNone(
            m, f"ExecStart is not a cargo release binary path: {exec_start!r}")
        crate_dir, binary = ROOT / m.group(1), m.group(2)
        cargo = crate_dir / "Cargo.toml"
        self.assertTrue(
            cargo.is_file(),
            f"ExecStart launches {exec_start}, but there is no crate at {crate_dir} -- "
            "the unit points somewhere the source is not, which is a 502 on the public "
            "site and a green test suite at the same time")
        name = re.search(r'^name = "([^"]+)"', cargo.read_text(), re.M)
        self.assertIsNotNone(name, f"{cargo} declares no package name")
        self.assertEqual(
            name.group(1), binary,
            f"{cargo} builds {name.group(1)!r} but the unit launches {binary!r}; cargo "
            "writes the package name, so the unit would ENOENT on every start")

    def test_the_installer_and_the_unit_agree_on_the_path(self):
        """Two files holding one path is how the stale one went unnoticed for four hours."""
        m = re.search(r'^BIN="\$ROOT/(.+)"$', INSTALLER.read_text(), re.M)
        self.assertIsNotNone(m, "install-gateway.sh no longer sets BIN in the expected form")
        self.assertEqual(
            m.group(1), _exec_start().removeprefix("@@ROOT@@/"),
            "the installer checks for one path and the unit launches another, so the "
            "installer's refuse-rather-than-crash-loop guard guards the wrong file")


class GatewayHopTests(unittest.TestCase):
    """The Caddyfile's hop and the unit's bind are the same port, or the site is a 502.

    Written as a pair on purpose: each file is individually plausible, and the failure only
    exists between them. This is the same shape as the ExecStart bug one class up.
    """

    def test_caddy_proxies_api_to_the_port_the_gateway_binds(self):
        caddy = (ROOT / "ops" / "Caddyfile").read_text()
        bind = re.search(r"^Environment=SYMON_GATEWAY_BIND=(\S+)$", UNIT.read_text(), re.M)
        self.assertIsNotNone(bind, "the unit does not set SYMON_GATEWAY_BIND")
        self.assertIn(f"reverse_proxy {bind.group(1)}", caddy,
                      f"Caddy does not proxy to {bind.group(1)}, which is where the gateway "
                      "listens; /api/* would 502 for every visitor")

    def test_the_gateway_forwards_to_the_api_port_api_py_serves(self):
        api_port = re.search(r'SYMONEURAL_PORT", "(\d+)"',
                             (ROOT / "backend" / "api.py").read_text())
        self.assertIsNotNone(api_port, "api.py's default port is no longer readable")
        self.assertIn(f"SYMON_API_UPSTREAM=http://127.0.0.1:{api_port.group(1)}",
                      UNIT.read_text(),
                      "the gateway forwards to a port api.py does not default to")


if __name__ == "__main__":
    # At the END of the file, and with backend/ on the path: see the block at the foot of
    # test_streamer_migration.py for what a misplaced one of these hides.
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    unittest.main()
