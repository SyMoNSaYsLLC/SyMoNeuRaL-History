# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
"""Interruption/resume tests for `tools/storage_reorg.py`.

Every one of these covers a state the storage reorganisation actually stopped in, and each
asserts the thing that costs real money to get wrong: that resuming does NOT re-send bytes
over a ~5 MB/s link, and that a source is never retired on the strength of an unconfirmed
destination.

The tests drive the state machine directly with a fake remote. They never touch Drive and
never touch the real `.private/storage-reorg` ledger -- module paths are redirected into
`tmp_path` first, so a test run cannot disturb a live migration.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def _load(tmp: pathlib.Path):
    """Load storage_reorg with all of its state redirected into a temp tree."""
    spec = importlib.util.spec_from_file_location(
        "storage_reorg_under_test", REPO / "tools" / "storage_reorg.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = tmp
    m.STATE_DIR = tmp / ".private" / "storage-reorg"
    m.STATE = m.STATE_DIR / "state.json"
    m.OPS = m.STATE_DIR / "operations.tsv"
    m.VERIFY_DIR = m.STATE_DIR / "verification"
    m.LOCK = m.STATE_DIR / "owner.lock"
    m.STAGE = tmp / ".private" / "offload-stage"
    m.STAGE.mkdir(parents=True, exist_ok=True)
    m.STATE_DIR.mkdir(parents=True, exist_ok=True)
    m.VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    return m


class Spy:
    """Stands in for every outbound side effect, and counts what was attempted."""

    def __init__(self, remote: dict[str, str]):
        self.remote = remote
        self.uploads: list[str] = []
        self.packs = 0

    def remote_md5(self, path: str):
        return self.remote.get(path)

    def sh(self, args, timeout=0):
        import subprocess
        if args and args[0] == "rclone" and len(args) > 1 and args[1] == "copy":
            self.uploads.append(args[2])
        if args and args[0] == "tar":
            self.packs += 1
        return subprocess.CompletedProcess(args, 0, "", "")


def _wire(m, spy, monkeypatch):
    monkeypatch.setattr(m, "remote_md5", spy.remote_md5)
    monkeypatch.setattr(m, "sh", spy.sh)
    monkeypatch.setattr(m, "du_bytes", lambda p: 4096)
    # A real content manifest needs a real tree; these tests assert transitions, not
    # manifest contents (test_content_manifest_is_content_addressed covers that).
    monkeypatch.setattr(m, "write_manifest", lambda src, out: (out.write_text(
        "TYPE\tRELPATH\tSIZE_BYTES\tSHA256\tMODE\tLINK_TARGET\n"), (1, 4096))[1])


def _src(tmp: pathlib.Path, name="leaf") -> pathlib.Path:
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "payload.bin").write_bytes(b"payload")
    return d


def test_complete_is_never_replayed(tmp_path, monkeypatch):
    m = _load(tmp_path)
    spy = Spy({})
    _wire(m, spy, monkeypatch)
    src = _src(tmp_path)
    st = {"ops": {"op": {"state": "COMPLETE"}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is True
    assert spy.uploads == [], "a COMPLETE operation must not re-upload"
    assert spy.packs == 0, "a COMPLETE operation must not repack"
    assert src.exists(), "a COMPLETE operation must not re-retire anything"


def test_failed_fails_closed_and_leaves_source(tmp_path, monkeypatch):
    m = _load(tmp_path)
    spy = Spy({})
    _wire(m, spy, monkeypatch)
    src = _src(tmp_path)
    st = {"ops": {"op": {"state": "FAILED", "detail": "upload rc=1"}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is False
    assert src.exists(), "a FAILED operation must never retire its source"
    assert spy.uploads == [], "a FAILED operation must not silently retry destructively"


def test_dest_verified_retires_without_repack_or_reupload(tmp_path, monkeypatch):
    """The expensive one: 5 GB already verified on Drive must not be sent twice."""
    m = _load(tmp_path)
    spy = Spy({"Dest/leaf.tar.zst": "abc123"})
    _wire(m, spy, monkeypatch)
    src = _src(tmp_path)
    st = {"ops": {"op": {"state": "DEST_VERIFIED", "dest": "Dest/leaf.tar.zst",
                         "remote_md5": "abc123", "raw_bytes": 4096}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is True
    assert spy.uploads == [], "DEST_VERIFIED resume must not re-upload"
    assert spy.packs == 0, "DEST_VERIFIED resume must not repack"
    assert not src.exists(), "DEST_VERIFIED resume must retire the source"
    assert st["ops"]["op"]["state"] == "COMPLETE"


def test_dest_verified_but_remote_changed_keeps_source(tmp_path, monkeypatch):
    m = _load(tmp_path)
    spy = Spy({"Dest/leaf.tar.zst": "DIFFERENT"})
    _wire(m, spy, monkeypatch)
    src = _src(tmp_path)
    st = {"ops": {"op": {"state": "DEST_VERIFIED", "dest": "Dest/leaf.tar.zst",
                         "remote_md5": "abc123", "raw_bytes": 4096}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is False
    assert src.exists(), "a destination that no longer matches must not retire the source"
    assert st["ops"]["op"]["state"] == "FAILED"


def test_uploading_promotes_when_remote_already_holds_the_object(tmp_path, monkeypatch):
    """Interrupted mid-upload, but the object landed: promote, do not re-send."""
    m = _load(tmp_path)
    src = _src(tmp_path)
    staged = m.STAGE / "leaf.tar.zst"
    staged.write_bytes(b"artifact-bytes")
    real_md5 = m.md5_of(staged)
    spy = Spy({"Dest/leaf.tar.zst": real_md5})
    _wire(m, spy, monkeypatch)
    st = {"ops": {"op": {"state": "UPLOADING", "dest": "Dest/leaf.tar.zst",
                         "local_md5": real_md5, "raw_bytes": 4096}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is True
    assert spy.uploads == [], "UPLOADING resume must not re-upload a complete object"
    assert spy.packs == 0
    assert not src.exists()
    assert st["ops"]["op"]["state"] == "COMPLETE"


def test_source_retired_closes_out_when_destination_reconfirms(tmp_path, monkeypatch):
    m = _load(tmp_path)
    spy = Spy({"Dest/leaf.tar.zst": "abc123"})
    _wire(m, spy, monkeypatch)
    src = tmp_path / "leaf"          # already gone, which is what SOURCE_RETIRED means
    st = {"ops": {"op": {"state": "SOURCE_RETIRED", "dest": "Dest/leaf.tar.zst",
                         "remote_md5": "abc123"}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is True
    assert st["ops"]["op"]["state"] == "COMPLETE"
    assert spy.uploads == []


def test_source_retired_with_lost_destination_is_flagged_not_hidden(tmp_path, monkeypatch):
    """Source gone AND destination gone is the one unrecoverable shape. It must be loud."""
    m = _load(tmp_path)
    spy = Spy({})
    _wire(m, spy, monkeypatch)
    src = tmp_path / "leaf"
    st = {"ops": {"op": {"state": "SOURCE_RETIRED", "dest": "Dest/leaf.tar.zst",
                         "remote_md5": "abc123"}}}

    assert m._pack_upload_retire("op", src, "Dest", "why", st) is False
    assert st["ops"]["op"]["state"] == "FAILED"


def test_unrouted_leaf_is_left_in_place(tmp_path, monkeypatch):
    """A leaf the route table does not name is unclassified. It must stay put and be
    reported, never swept into a default bucket."""
    m = _load(tmp_path)
    spy = Spy({})
    _wire(m, spy, monkeypatch)
    parent = tmp_path / "tree"
    (parent / "known").mkdir(parents=True)
    (parent / "unknown").mkdir(parents=True)
    (parent / "unknown" / "f").write_bytes(b"x")
    calls: list[str] = []
    monkeypatch.setattr(m, "_pack_upload_retire",
                        lambda oid, s, d, w, st, retire=True: calls.append(s.name) or True)
    st = {"ops": {}}
    m.do_move_leaves({"id": "op", "src": str(parent), "routes": {"known": "Dest"},
                      "why": "w"}, st, apply=True)

    assert calls == ["known"]
    assert (parent / "unknown").exists(), "an unrouted leaf must not be moved"


def test_content_manifest_is_content_addressed_not_size_only(tmp_path):
    """The manifest must carry SHA256 and must not dereference symlinks -- size alone
    cannot distinguish two same-length files, so a size-only manifest cannot support
    dedupe or prove an archived collection is what it claims."""
    import subprocess
    src = tmp_path / "leaf"
    src.mkdir()
    (src / "a.txt").write_bytes(b"AAAA")
    (src / "b.txt").write_bytes(b"BBBB")          # same size, different content
    (src / "link").symlink_to("a.txt")
    out = tmp_path / "CONTENTS.tsv"
    r = subprocess.run(["python3", str(REPO / "tools" / "sym_content_manifest.py"),
                        "make", str(src), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = [l.split("\t") for l in out.read_text().splitlines()[1:]]
    by = {r[1]: r for r in rows}
    assert "SHA256" in out.read_text().splitlines()[0]
    assert by["a.txt"][3] != by["b.txt"][3], "equal-size files must hash differently"
    assert by["a.txt"][2] == by["b.txt"][2] == "4"
    assert by["link"][0] == "SYMLINK", "symlinks must be recorded, not followed"
    assert by["link"][5] == "a.txt", "the link target itself is the identity"
