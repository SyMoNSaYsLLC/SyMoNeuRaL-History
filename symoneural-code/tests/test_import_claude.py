# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""The Claude importer. Every refusal is tested against something that actually does it.

The importer is the boundary between somebody else's product and ours. A boundary that is
documented but not enforced is decoration, so each exclusion here is exercised with real
malformed input, a real symlink, a real traversal and a real credential shape.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest


def _find_root(start: pathlib.Path) -> pathlib.Path:
    for cand in (start, *start.parents):
        if (cand / "backend" / "api.py").is_file():
            return cand
    raise RuntimeError(f"no repo root above {start}")


ROOT = _find_root(pathlib.Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "symoneural-code" / "src"))
from symoneural_import import claude as I                            # noqa: E402


class Bed(unittest.TestCase):
    """A throwaway source tree and two destinations, per test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = pathlib.Path(self.tmp.name)
        self.src = base / "claude"
        self.proj = base / "project"
        self.priv = base / "private"
        for p in (self.src, self.proj, self.priv):
            p.mkdir(parents=True)

    def sess(self, name: str, lines: list[str]) -> pathlib.Path:
        d = self.src / "projects" / "-home-x"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{name}.jsonl"
        f.write_text("\n".join(lines) + "\n")
        return f

    def run_it(self, dry=False) -> I.Result:
        return I.run_import(self.src, project_dest=self.proj,
                            private_dest=self.priv, dry_run=dry)


class SecretsAreRefused(Bed):

    def test_a_key_named_like_a_credential_is_caught_at_any_depth(self):
        for obj in ({"token": "x"}, {"a": {"b": {"access_token": "x"}}},
                    {"list": [{"oauthAccount": {}}]}, {"apiKey": 1},
                    {"nested": {"client_secret": "s"}}):
            with self.subTest(obj=obj):
                self.assertIsNotNone(I.contains_secret(obj))

    def test_a_credential_shaped_value_under_an_innocent_key_is_caught(self):
        for v in ("sk-ant-abcdefgh12345678",
                  "Bearer abcdefghijklmnopqrstuvwx",
                  "-----BEGIN RSA PRIVATE KEY-----",
                  "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk"):
            with self.subTest(v=v[:20]):
                self.assertIsNotNone(I.contains_secret({"note": v}))

    def test_ordinary_prose_is_not_flagged(self):
        """A false positive here would silently drop the owner's own notes."""
        self.assertIsNone(I.contains_secret(
            {"content": "we authorised the deploy and the token bucket was empty"}))

    def test_the_detector_never_returns_the_value(self):
        hit = I.contains_secret({"password": "hunter2"})
        self.assertNotIn("hunter2", str(hit))

    def test_a_memory_containing_a_credential_shape_is_skipped(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "bad.md").write_text("key: sk-ant-abcdefgh12345678\n")
        (d / "good.md").write_text("the api restart drops the resident model\n")
        res = self.run_it()
        by = {r.source.split("/")[-1]: r for r in res.rows}
        self.assertEqual("SKIPPED_SECRET", by["bad.md"].disposition)
        self.assertEqual("MIGRATED", by["good.md"].disposition)
        self.assertFalse((self.priv / "memory" / "bad.md").exists())
        self.assertTrue((self.priv / "memory" / "good.md").exists())

    def test_a_conversation_turn_carrying_a_credential_is_dropped(self):
        self.sess("s1", [
            json.dumps({"message": {"role": "user", "content": "hello"}}),
            json.dumps({"message": {"role": "assistant",
                                    "content": "here: sk-ant-abcdefgh12345678"}}),
        ])
        turns = I.convert_session((self.src / "projects" / "-home-x" / "s1.jsonl")
                                  .read_text().splitlines())
        self.assertEqual(1, len(turns))
        self.assertEqual("hello", turns[0]["content"])


class SessionConversion(Bed):

    def test_only_user_and_assistant_roles_survive(self):
        lines = [json.dumps({"message": {"role": r, "content": f"c-{r}"}})
                 for r in ("system", "user", "tool", "assistant", "developer")]
        turns = I.convert_session(lines)
        self.assertEqual(["user", "assistant"], [t["role"] for t in turns])

    def test_malformed_and_partial_lines_are_skipped_not_fatal(self):
        turns = I.convert_session([
            "{not json",
            '{"message":{"role":"user","content":"kept"}}',
            '{"message":{"role":"user"',                       # truncated
            "",
            "[]",                                              # wrong top-level type
            '{"message":{"role":"user","content":null}}',
        ])
        self.assertEqual(1, len(turns))
        self.assertEqual("kept", turns[0]["content"])

    def test_block_content_is_flattened_to_text_only(self):
        turns = I.convert_session([json.dumps({"message": {"role": "assistant", "content": [
            {"type": "text", "text": "visible"},
            {"type": "tool_use", "input": {"token": "leak"}},
            {"type": "text", "text": "also"},
        ]}})])
        self.assertEqual(1, len(turns))
        self.assertEqual("visible\nalso", turns[0]["content"])
        self.assertNotIn("leak", json.dumps(turns))

    def test_an_oversized_record_is_skipped(self):
        big = json.dumps({"message": {"role": "user", "content": "x" * (I.MAX_RECORD_BYTES + 10)}})
        self.assertEqual([], I.convert_session([big]))

    def test_the_turn_cap_is_enforced(self):
        lines = [json.dumps({"message": {"role": "user", "content": str(i)}})
                 for i in range(I.MAX_TURNS_PER_SESSION + 50)]
        self.assertEqual(I.MAX_TURNS_PER_SESSION, len(I.convert_session(lines)))

    def test_a_session_with_no_representable_turns_is_backup_only(self):
        self.sess("empty", [json.dumps({"message": {"role": "system", "content": "hidden"}})])
        res = self.run_it()
        row = next(r for r in res.rows if r.source.endswith("empty.jsonl"))
        self.assertEqual("BACKUP_ONLY", row.disposition)

    def test_two_sessions_with_the_same_name_do_not_collide_silently(self):
        """Duplicate stems from different project dirs must both survive."""
        for proj in ("-home-a", "-home-b"):
            d = self.src / "projects" / proj
            d.mkdir(parents=True, exist_ok=True)
            (d / "dup.jsonl").write_text(
                json.dumps({"message": {"role": "user", "content": proj}}) + "\n")
        res = self.run_it()
        self.assertEqual(1, len(res.collisions), res.collisions)
        self.assertTrue((self.priv / "sessions" / "agent-dup.json").exists())
        self.assertTrue((self.priv / "sessions" / "agent-dup.json.imported-1").exists())


class PathContainment(Bed):

    def test_an_absolute_destination_is_refused(self):
        with self.assertRaises(I.ImportError_):
            I._contain(self.priv, "/etc/passwd")

    def test_a_traversal_is_refused(self):
        for rel in ("../escape", "a/../../escape", "../../etc/shadow"):
            with self.subTest(rel=rel):
                with self.assertRaises(I.ImportError_):
                    I._contain(self.priv, rel)

    def test_a_symlink_whose_target_leaves_the_root_is_refused(self):
        """The escape a string check cannot see."""
        outside = pathlib.Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.priv / "link").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(I.ImportError_):
            I._contain(self.priv, "link/file.json")

    def test_a_legitimate_nested_destination_is_allowed(self):
        p = I._contain(self.priv, "sessions/agent-x.json")
        self.assertTrue(str(p).startswith(str(self.priv)))


class NoSilentOverwrite(Bed):

    def test_an_existing_destination_is_never_replaced(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "m.md").write_text("new content\n")
        (self.priv / "memory").mkdir(parents=True)
        (self.priv / "memory" / "m.md").write_text("PRE-EXISTING\n")
        res = self.run_it()
        self.assertEqual("PRE-EXISTING\n", (self.priv / "memory" / "m.md").read_text())
        self.assertTrue((self.priv / "memory" / "m.md.imported-1").exists())
        self.assertIn(str(self.priv / "memory" / "m.md"), res.collisions)


class DryRunAndIdempotence(Bed):

    def _seed(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "m.md").write_text("note\n")
        self.sess("s1", [json.dumps({"message": {"role": "user", "content": "hi"}})])

    def test_a_dry_run_writes_nothing(self):
        self._seed()
        res = self.run_it(dry=True)
        self.assertTrue(res.dry_run)
        self.assertTrue(res.written, "a dry run must still report what it would write")
        self.assertFalse((self.priv / "memory" / "m.md").exists())
        self.assertFalse((self.priv / "sessions").exists())

    def test_apply_then_rerun_adds_nothing_new(self):
        self._seed()
        first = self.run_it(dry=False)
        before = sorted(p.name for p in (self.priv / "memory").iterdir())
        second = self.run_it(dry=False)
        after = sorted(p.name for p in (self.priv / "memory").iterdir())
        self.assertEqual(first.counts().get("MIGRATED"),
                         second.counts().get("MIGRATED"),
                         "the same rows must be reported on a rerun")
        self.assertEqual(len(before) + 1, len(after),
                         "a rerun records a collision sibling rather than overwriting")
        self.assertTrue(second.collisions)

    def test_permissions_on_private_state(self):
        self._seed()
        self.run_it(dry=False)
        d = self.priv / "memory"
        f = d / "m.md"
        self.assertEqual(0o700, stat.S_IMODE(d.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(f.stat().st_mode))

    def test_no_partial_file_is_left_behind(self):
        self._seed()
        self.run_it(dry=False)
        self.assertEqual([], list(self.priv.rglob("*.partial")))


class McpAndDenyRules(Bed):

    def test_credentials_are_stripped_and_the_server_is_marked_for_reauth(self):
        cfg = {"mcpServers": {
            "gmail": {"command": "npx", "args": ["-y", "srv"], "type": "stdio",
                      "env": {"OAUTH_TOKEN": "secret-value"}},
            "local": {"command": "./run", "args": ["--port", "1"], "type": "stdio"},
        }}
        servers, reauth = I.convert_mcp(cfg)
        blob = json.dumps(servers)
        self.assertNotIn("secret-value", blob)
        self.assertNotIn("OAUTH_TOKEN", blob)
        self.assertEqual(["gmail"], reauth)
        g = next(s for s in servers if s["name"] == "gmail")
        self.assertEqual("REAUTH_REQUIRED", g["auth"])
        self.assertEqual(["-y", "srv"], g["args"])
        self.assertNotIn("auth", next(s for s in servers if s["name"] == "local"))

    def test_deny_rules_become_a_sorted_unique_list(self):
        got = I.convert_deny_rules({"permissions": {"deny": ["b", "a", "b", " c "]}})
        self.assertEqual(["a", "b", "c"], got)

    def test_an_allow_everything_mode_is_refused(self):
        for mode in ("bypassPermissions", "bypass", "allowAll"):
            with self.subTest(mode=mode):
                with self.assertRaises(I.ImportError_):
                    I.convert_deny_rules({"defaultMode": mode})

    def test_unparseable_settings_are_manual_review_not_a_crash(self):
        (self.src / "settings.json").write_text("{ not json")
        res = self.run_it()
        row = next(r for r in res.rows if r.source == "settings.json")
        self.assertEqual("MANUAL_REVIEW", row.disposition)

    def test_absent_settings_are_recorded_as_missing(self):
        res = self.run_it()
        row = next(r for r in res.rows if r.source == "settings.local.json")
        self.assertEqual("MISSING_BEFORE_MIGRATION", row.disposition)


class ManifestIntegrity(Bed):

    def test_every_row_has_a_known_disposition(self):
        with self.assertRaises(I.ImportError_):
            I.Row("s", "c", "NOT_A_DISPOSITION")

    def test_vendor_runtime_paths_are_classified_without_being_read(self):
        for rel in ("shell-snapshots/x.sh", "jobs/a/b", "statsig/x", "file-history/y"):
            p = self.src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("irrelevant")
        res = self.run_it()
        got = {r.source: r.disposition for r in res.rows}
        self.assertEqual("SKIPPED_VENDOR_SPECIFIC", got["shell-snapshots/x.sh"])
        self.assertIn(got["jobs/a/b"], ("SKIPPED_CACHE_OR_TELEMETRY",))

    def test_every_file_present_receives_a_row(self):
        """Nothing may be silently ignored -- the whole point of the manifest."""
        for rel in ("a.md", "b.json", "sub/c.txt", "sub/d.bin"):
            p = self.src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        res = self.run_it()
        sources = {r.source for r in res.rows}
        for rel in ("a.md", "b.json", "sub/c.txt", "sub/d.bin"):
            self.assertIn(rel, sources, f"{rel} got no manifest row")

    def test_the_manifest_contains_no_secret_values(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "m.md").write_text("sk-ant-abcdefgh12345678\n")
        text = I.manifest_tsv(self.run_it())
        self.assertNotIn("sk-ant-", text)

    def test_a_missing_source_directory_is_reported_not_raised(self):
        res = I.run_import(pathlib.Path("/nonexistent-claude-dir"),
                           project_dest=self.proj, private_dest=self.priv, dry_run=True)
        self.assertEqual(["MISSING_BEFORE_MIGRATION"],
                         [r.disposition for r in res.rows])


if __name__ == "__main__":
    unittest.main()


class ContainmentWorksBeforeTheRootExists(Bed):
    """The case the fixture hid: a first import into a destination that is not there yet.

    The original check walked up to the deepest EXISTING ancestor and compared it to the
    root. With the root absent, that walk went above the root and the comparison correctly
    reported an escape -- refusing every legitimate first import. The tests passed because
    the bed pre-created both destinations; only running the command found it.
    """

    def test_a_destination_root_that_does_not_exist_yet_is_allowed(self):
        fresh = pathlib.Path(self.tmp.name) / "not-created-yet" / "deeper"
        got = I._contain(fresh, "memory/MEMORY.md")
        self.assertTrue(str(got).startswith(str(fresh)))

    def test_an_escape_is_still_refused_when_the_root_is_absent(self):
        fresh = pathlib.Path(self.tmp.name) / "absent"
        with self.assertRaises(I.ImportError_):
            I._contain(fresh, "../../etc/passwd")

    def test_a_full_import_into_absent_destinations_succeeds(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "m.md").write_text("note\n")
        base = pathlib.Path(self.tmp.name)
        res = I.run_import(self.src, project_dest=base / "new-proj",
                           private_dest=base / "new-priv", dry_run=False)
        self.assertEqual(1, res.counts().get("MIGRATED"))
        self.assertTrue((base / "new-priv" / "memory" / "m.md").is_file())


class ThePrivateRootIsAlsoLockedDown(Bed):
    """0700 on the top of the private tree, not only on its leaves.

    `_write` chmods `target.parent`, so `sessions/` and `memory/` were 0700 while the
    enclosing `run/private` kept whatever the umask gave it -- measured 775 on the first
    real apply. A private tree with a world-readable root is not private.
    """

    def test_the_private_root_is_0700_after_an_apply(self):
        d = self.src / "projects" / "-home-x" / "memory"
        d.mkdir(parents=True)
        (d / "m.md").write_text("note\n")
        fresh = pathlib.Path(self.tmp.name) / "priv-root"
        I.run_import(self.src, project_dest=self.proj, private_dest=fresh, dry_run=False)
        self.assertEqual(0o700, stat.S_IMODE(fresh.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE((fresh / "memory").stat().st_mode))

    def test_a_dry_run_does_not_create_the_private_root(self):
        fresh = pathlib.Path(self.tmp.name) / "untouched"
        I.run_import(self.src, project_dest=self.proj, private_dest=fresh, dry_run=True)
        self.assertFalse(fresh.exists(), "a dry run must not create anything")
