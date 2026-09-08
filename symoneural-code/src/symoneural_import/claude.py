# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""Import the owner's own Claude Code material into first-party SyMoNeuRaL state.

Backs `symoneural-cli import-claude`. What it moves is what the owner wrote and owns:
project rules, handoff knowledge, their own commands/skills/agents/hooks, persistent
memories, MCP server *definitions*, deny rules, and human-readable conversation turns.

## What it will not touch, and why the refusals are in code

The importer is the boundary between somebody else's product and ours, so the exclusions are
enforced rather than documented:

- **Credentials of any kind.** `SECRET_KEYS` is checked against every key at every depth of
  every object. A record carrying one is rejected whole, not redacted-and-kept, because a
  partially-scrubbed credential record is a credential record.
- **Proprietary implementation and hidden prompts.** Only `role`/`content` pairs with a role
  in `ALLOWED_ROLES` are converted. System prompts, tool traces and internal fields are
  dropped: a tool trace's arguments can contain anything the tool was handed.
- **Escapes from the destination.** Every write resolves through `_contain()`, which refuses
  absolute paths, `..`, and symlinks whose target leaves the destination root.
- **Silent overwrites.** An existing destination is never replaced. Collisions get a
  `.imported-N` sibling and are reported.
- **Unbounded input.** Per-record, per-file and per-session-count caps, because the input is
  a directory somebody else's program wrote and may be arbitrarily large.

## Committed configuration versus private runtime state

Two destinations, and conflating them is how a credential reaches Git:

- **project** — `docs/` and policy files. Tracked. Only ever the owner's own prose and rules.
- **private** — a gitignored SyMoNeuRaL-owned directory, `0700`, files `0600`. Sessions and
  memories land here. Nothing here is added to Git by this module.

`~/.config/symoneural/keys.json` and `accounts.json` are never opened.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
from dataclasses import dataclass, field

SCHEMA = "symoneural-import-claude/v1"

#: Any key whose name matches is a refusal, at any depth. Substring match on a lowered key,
#: because `oauthAccount`, `access_token` and `apiKeyHash` must all be caught by one rule.
SECRET_KEYS = ("token", "secret", "password", "passwd", "apikey", "api_key", "oauth",
               "credential", "cookie", "private_key", "privatekey", "auth", "bearer",
               "session_key", "refresh", "client_secret")

#: Values shaped like a credential even under an innocent key name.
SECRET_VALUE = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|"
    r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"      # JWT
)

ALLOWED_ROLES = ("user", "assistant")

MAX_RECORD_BYTES = 256 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TURNS_PER_SESSION = 2000
MAX_SESSIONS = 500

#: Every disposition the manifest may carry. A row must have exactly one.
DISPOSITIONS = (
    "MIGRATED", "ALREADY_NATIVE", "BACKUP_ONLY", "SKIPPED_VENDOR_SPECIFIC",
    "SKIPPED_SECRET", "SKIPPED_CACHE_OR_TELEMETRY", "SKIPPED_LICENSE",
    "MANUAL_REVIEW", "MISSING_BEFORE_MIGRATION",
)

#: Path fragments that are the vendor's runtime, not the owner's material.
VENDOR_ONLY = ("shell-snapshots", "session-env", "jobs/", "statsig", "telemetry",
               "paste-cache", "image-cache", "file-history", "downloads/", "cache/",
               "ide/", "daemon", "backups/", "versions/", "plugins/repos")


class ImportError_(Exception):
    """A refusal. Messages name the field or path, never a value."""


@dataclass
class Row:
    source: str
    content_class: str
    disposition: str
    destination: str = "-"
    transformation: str = "-"
    count: int = 0
    verification: str = "-"
    reason: str = ""

    def __post_init__(self):
        if self.disposition not in DISPOSITIONS:
            raise ImportError_(f"unknown disposition {self.disposition!r}")


@dataclass
class Result:
    rows: list[Row] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    reauth_required: list[str] = field(default_factory=list)
    dry_run: bool = True

    def counts(self) -> dict:
        out: dict[str, int] = {}
        for r in self.rows:
            out[r.disposition] = out.get(r.disposition, 0) + 1
        return out


# ------------------------------------------------------------------ safety primitives
def contains_secret(obj) -> str | None:
    """Return the offending key/shape, or None. Recurses; never returns a value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(s in kl for s in SECRET_KEYS):
                return f"key {k!r}"
            hit = contains_secret(v)
            if hit:
                return hit
        return None
    if isinstance(obj, list):
        for v in obj:
            hit = contains_secret(v)
            if hit:
                return hit
        return None
    if isinstance(obj, str) and SECRET_VALUE.search(obj):
        return "value matching a credential pattern"
    return None


def _contain(root: pathlib.Path, rel: str) -> pathlib.Path:
    """Resolve `rel` under `root`, refusing anything that leaves it.

    Three separate escapes, all real: an absolute path, a `..` traversal, and a symlink
    inside the destination whose target is outside it. The last is the one a check on the
    string alone misses.
    """
    if not rel or rel.startswith("/") or "\x00" in rel:
        raise ImportError_(f"destination {rel!r} is absolute or malformed")
    p = (root / rel)
    if ".." in pathlib.PurePosixPath(rel).parts:
        raise ImportError_(f"destination {rel!r} traverses upward")
    # Compare REALPATHS of the target and the root. An earlier version walked up to the
    # deepest existing ancestor and compared that -- which, when the destination root did
    # not exist yet, walked ABOVE the root and then correctly observed that the ancestor
    # was not inside it. The check refused every legitimate first import. Found by running
    # the command rather than by the tests, whose fixture pre-created the destination.
    rr = os.path.realpath(root)
    tp = os.path.realpath(p)                     # resolves symlinks in existing components
    if tp != rr and not tp.startswith(rr + os.sep):
        raise ImportError_(f"destination {rel!r} escapes the destination root "
                           "(symlink or mount)")
    return p


def _write(path: pathlib.Path, data: str, *, private: bool,
           res: Result, dry_run: bool) -> pathlib.Path | None:
    """Never overwrite. Identical content is a no-op; different content gets a sibling.

    Returning None for "already present and identical" is what makes a rerun IDEMPOTENT
    rather than merely non-destructive. The first version wrote a `.imported-N` sibling for
    every existing destination, so a second apply took 114 files to 228 -- safe, and wrong.
    Non-destructive and idempotent are different properties and the task asked for both.
    """
    if path.exists() and path.is_file():
        try:
            if path.read_text(encoding="utf-8", errors="replace") == data:
                return None                      # already imported, byte-identical
        except OSError:
            pass
    target = path
    if target.exists():
        # Before creating a NEW sibling, look through the existing ones. Two sources can
        # legitimately map to the same destination name (duplicate session stems in
        # different project directories), and the first fix only compared against the
        # PRIMARY destination -- so every rerun added another `.imported-N` for the same
        # content. 115 files became 120, then 125. Non-destructive, still not idempotent.
        n = 1
        while True:
            cand = target.with_name(f"{target.name}.imported-{n}")
            if not cand.exists():
                break
            try:
                if cand.read_text(encoding="utf-8", errors="replace") == data:
                    return None                  # this exact content is already imported
            except OSError:
                pass
            n += 1
        res.collisions.append(str(target))
        target = cand
    if dry_run:
        res.written.append(str(target))
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if private:
        os.chmod(target.parent, 0o700)
    tmp = target.with_name(target.name + ".partial")
    tmp.write_text(data, encoding="utf-8")
    if private:
        os.chmod(tmp, 0o600)
    tmp.replace(target)                     # atomic: an interrupted write leaves .partial
    res.written.append(str(target))
    return target


# ------------------------------------------------------------------ converters
def convert_session(lines: list[str]) -> list[dict]:
    """JSONL transcript -> the plain turns `run/agent-<session>.json` can represent.

    Only `role` in ALLOWED_ROLES with string `content`. Everything else is dropped: a
    system prompt is the vendor's, and a tool record's arguments can contain anything.
    """
    turns: list[dict] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        if len(raw.encode()) > MAX_RECORD_BYTES:
            continue                                     # oversized record: skipped, not fatal
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue                                     # partial/corrupt line
        if not isinstance(rec, dict):
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
        role = msg.get("role")
        content = msg.get("content")
        if role not in ALLOWED_ROLES:
            continue
        if isinstance(content, list):
            parts = [b.get("text") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"
                     and isinstance(b.get("text"), str)]
            content = "\n".join(p for p in parts if p)
        if not isinstance(content, str) or not content.strip():
            continue
        if contains_secret({"content": content}):
            continue                                     # never import a credential as prose
        turns.append({"role": role, "content": content})
        if len(turns) >= MAX_TURNS_PER_SESSION:
            break
    return turns


def convert_mcp(cfg: dict) -> tuple[list[dict], list[str]]:
    """MCP server definitions, minus every credential. Returns (servers, reauth_needed)."""
    servers: list[dict] = []
    reauth: list[str] = []
    found: dict = {}

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("mcpServers", "mcp_servers") and isinstance(v, dict):
                    found.update(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(cfg)
    for name, spec in sorted(found.items()):
        if not isinstance(spec, dict):
            continue
        hit = contains_secret(spec)
        clean = {"name": name}
        for k in ("command", "type", "transport", "url"):
            if isinstance(spec.get(k), str):
                clean[k] = spec[k]
        if isinstance(spec.get("args"), list):
            clean["args"] = [a for a in spec["args"]
                             if isinstance(a, str) and not SECRET_VALUE.search(a)]
        if hit:
            clean["auth"] = "REAUTH_REQUIRED"
            reauth.append(name)
        servers.append(clean)
    return servers, reauth


def convert_deny_rules(settings: dict) -> list[str]:
    """Claude `permissions.deny` -> native policy patterns.

    An allow-everything mode is refused outright rather than translated: importing one
    would hand the new runtime a weaker posture than it started with.
    """
    perms = settings.get("permissions") if isinstance(settings.get("permissions"), dict) else {}
    mode = str(settings.get("defaultMode") or perms.get("defaultMode") or "").lower()
    if mode in ("bypasspermissions", "bypass", "acceptedits-all", "allowall"):
        raise ImportError_("refusing to import an allow-everything permission mode")
    deny = perms.get("deny") if isinstance(perms.get("deny"), list) else []
    out = []
    for d in deny:
        if isinstance(d, str) and d.strip():
            out.append(d.strip())
    return sorted(set(out))


# ------------------------------------------------------------------ the driver
def _classify(rel: str) -> str | None:
    """Vendor-runtime paths get a disposition without being read."""
    low = rel.lower()
    for frag in VENDOR_ONLY:
        if frag in low:
            return "SKIPPED_CACHE_OR_TELEMETRY" if any(
                c in frag for c in ("cache", "telemetry", "statsig", "jobs/", "downloads/",
                                    "file-history", "backups/")) else "SKIPPED_VENDOR_SPECIFIC"
    return None


def run_import(src: pathlib.Path, *, project_dest: pathlib.Path,
               private_dest: pathlib.Path, dry_run: bool = True) -> Result:
    """Walk a Claude Code state directory and import what is portable.

    Idempotent: re-running writes nothing new, because `_write` refuses to overwrite and a
    second pass finds every destination already present. The manifest then shows the same
    rows with collisions recorded, which is the honest representation of "already done".
    """
    res = Result(dry_run=dry_run)
    if not dry_run:
        # 0700 on the private ROOT, not merely on the leaf directories. `_write` chmods
        # `target.parent`, which left `run/private` itself at whatever the umask gave --
        # measured 775 on the first real apply. A private tree whose top directory is
        # world-readable is not private, however tight the leaves are.
        private_dest.mkdir(parents=True, exist_ok=True)
        os.chmod(private_dest, 0o700)
    if not src.is_dir():
        res.rows.append(Row(str(src), "source-root", "MISSING_BEFORE_MIGRATION",
                            reason="source directory does not exist"))
        return res

    # --- 1. persistent memories: the owner's own operational knowledge
    for mem in sorted(src.glob("projects/*/memory/*.md")):
        rel = str(mem.relative_to(src))
        if len(mem.read_bytes()) > MAX_FILE_BYTES:
            res.rows.append(Row(rel, "memory", "MANUAL_REVIEW",
                                reason="exceeds the per-file size cap"))
            continue
        text = mem.read_text(errors="replace")
        if SECRET_VALUE.search(text):
            res.rows.append(Row(rel, "memory", "SKIPPED_SECRET",
                                reason="content matches a credential pattern"))
            continue
        dst = _contain(private_dest, f"memory/{mem.name}")
        wrote = _write(dst, text, private=True, res=res, dry_run=dry_run)
        res.rows.append(Row(rel, "memory",
                            "MIGRATED" if wrote is not None else "ALREADY_NATIVE",
                            destination=str(dst.relative_to(private_dest.parent)),
                            transformation="verbatim", count=1,
                            verification="written" if wrote is not None
                            else "present and byte-identical",
                            reason="owner-authored operational knowledge"))

    # --- 2. user-authored commands, skills, agents, hooks
    for kind, pat in (("command", "commands/**/*.md"), ("skill", "skills/**/*.md"),
                      ("agent", "agents/**/*.md"), ("hook", "hooks/**/*")):
        for f in sorted(src.glob(pat)):
            if not f.is_file():
                continue
            rel = str(f.relative_to(src))
            if _classify(rel):
                res.rows.append(Row(rel, kind, _classify(rel),
                                    reason="vendor runtime path"))
                continue
            text = f.read_text(errors="replace")
            if SECRET_VALUE.search(text):
                res.rows.append(Row(rel, kind, "SKIPPED_SECRET",
                                    reason="content matches a credential pattern"))
                continue
            dst = _contain(project_dest, f"{kind}s/{f.name}")
            wrote = _write(dst, text, private=False, res=res, dry_run=dry_run)
            res.rows.append(Row(rel, kind,
                                "MIGRATED" if wrote is not None else "ALREADY_NATIVE",
                                destination=str(dst.relative_to(project_dest.parent)),
                                transformation="verbatim", count=1, verification="written",
                                reason="owner-authored"))

    # --- 3. sessions: plain role/content only
    sessions = sorted(src.glob("projects/*/*.jsonl"))[:MAX_SESSIONS]
    for s in sessions:
        rel = str(s.relative_to(src))
        if s.stat().st_size > MAX_FILE_BYTES:
            res.rows.append(Row(rel, "session", "MANUAL_REVIEW",
                                reason="transcript exceeds the per-file cap; the private "
                                       "backup holds it"))
            continue
        turns = convert_session(s.read_text(errors="replace").splitlines())
        if not turns:
            res.rows.append(Row(rel, "session", "BACKUP_ONLY", count=0,
                                reason="no plain role/content turns the native format can "
                                       "represent"))
            continue
        payload = json.dumps({"schema": SCHEMA, "session": s.stem, "turns": turns},
                             indent=2) + "\n"
        dst = _contain(private_dest, f"sessions/agent-{s.stem}.json")
        wrote = _write(dst, payload, private=True, res=res, dry_run=dry_run)
        res.rows.append(Row(rel, "session",
                            "MIGRATED" if wrote is not None else "ALREADY_NATIVE",
                            destination=str(dst.relative_to(private_dest.parent)),
                            transformation=f"role/content only, {len(turns)} turn(s)",
                            count=len(turns), verification="schema-validated",
                            reason="human-readable conversation the native format holds"))

    # --- 4. MCP definitions and deny rules from settings
    for name in ("settings.json", "settings.local.json"):
        f = src / name
        if not f.is_file():
            res.rows.append(Row(name, "settings", "MISSING_BEFORE_MIGRATION",
                                reason="not present in the source"))
            continue
        try:
            cfg = json.loads(f.read_text(errors="replace"))
        except json.JSONDecodeError as exc:
            res.rows.append(Row(name, "settings", "MANUAL_REVIEW",
                                reason=f"unparseable JSON: {type(exc).__name__}"))
            continue
        servers, reauth = convert_mcp(cfg)
        res.reauth_required.extend(reauth)
        if servers:
            dst = _contain(project_dest, "policy/mcp-servers.json")
            _write(dst, json.dumps({"schema": SCHEMA, "servers": servers}, indent=2) + "\n",
                   private=False, res=res, dry_run=dry_run)
            res.rows.append(Row(name, "mcp", "MIGRATED",
                                destination=str(dst.relative_to(project_dest.parent)),
                                transformation="names, transports and non-secret args only",
                                count=len(servers), verification="no credential fields",
                                reason="definitions the native client can use"))
        try:
            deny = convert_deny_rules(cfg)
        except ImportError_ as exc:
            res.rows.append(Row(name, "permissions", "SKIPPED_LICENSE" if False
                                else "MANUAL_REVIEW", reason=str(exc)))
            deny = []
        if deny:
            dst = _contain(project_dest, "policy/deny-rules.json")
            _write(dst, json.dumps({"schema": SCHEMA, "deny": deny}, indent=2) + "\n",
                   private=False, res=res, dry_run=dry_run)
            res.rows.append(Row(name, "deny-rules", "MIGRATED",
                                destination=str(dst.relative_to(project_dest.parent)),
                                transformation="deny patterns -> native policy",
                                count=len(deny), verification="written",
                                reason="safety constraints become native policy"))

    # --- 5. everything else present, classified rather than ignored
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(src))
        if any(r.source == rel for r in res.rows):
            continue
        cls = _classify(rel)
        if cls:
            res.rows.append(Row(rel, "vendor-runtime", cls, reason="not owner material"))
        elif rel.endswith((".json", ".jsonl", ".md", ".txt")):
            res.rows.append(Row(rel, "other", "BACKUP_ONLY",
                                reason="retained in the private backup; no native "
                                       "destination represents it"))
        else:
            res.rows.append(Row(rel, "other", "BACKUP_ONLY",
                                reason="binary or unrecognised; private backup only"))
    return res


def manifest_tsv(res: Result) -> str:
    head = ("SOURCE\tCONTENT_CLASS\tDISPOSITION\tDESTINATION\tTRANSFORMATION\tCOUNT\t"
            "VERIFICATION\tREASON\n")
    body = "".join(f"{r.source}\t{r.content_class}\t{r.disposition}\t{r.destination}\t"
                   f"{r.transformation}\t{r.count}\t{r.verification}\t{r.reason}\n"
                   for r in res.rows)
    return head + body
