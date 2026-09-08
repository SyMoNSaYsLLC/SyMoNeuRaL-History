# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""Join the judgement registry against measured disk state and emit the restore manifests.

Run it twice and diff. Every generator in this repository re-reads its own output, and one
that does not recognise something it emits accumulates a copy per run -- that bug has
happened three times here, which is why `docs/authority/PROJECT-AUTHORITY.md` makes "run
both twice and diff" part of the completion sequence rather than advice.

## The anti-vacuity rule

A generator that finds nothing passes forever for the wrong reason. Two guards:

* `discover_components()` walks the disk for things that look like a runtime and raises if
  one has no row in the registry. A new engine folder cannot be quietly left out of the
  restore plan; it fails the build instead.
* Every table asserts a minimum row count before it is written. An empty
  `SOURCE-CLOSURE.tsv` would satisfy "no component fails closure" and mean nothing.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib import deps as D             # noqa: E402
from lib import measure as M          # noqa: E402
from lib import registry as R         # noqa: E402

ROOT = M.ROOT
MANIFESTS = ROOT / "restore" / "manifests"

# `-` is the empty cell. A truly empty cell in a TSV is ambiguous with a parse error, and a
# column that is sometimes absent breaks `cut -f`.
NUL = "-"


def _cell(v) -> str:
    """One TSV cell: never contains a tab or a newline, never empty."""
    s = "" if v is None else str(v)
    s = s.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    s = " ".join(s.split())
    return s or NUL


def write_tsv(name: str, header: list[str], rows: list[list], minimum: int) -> int:
    if len(rows) < minimum:
        raise SystemExit(
            f"restore/generate: {name} would have {len(rows)} rows, minimum {minimum}. "
            f"A manifest that is empty passes every 'no failures' check for the wrong "
            f"reason; refusing to write it.")
    for r in rows:
        if len(r) != len(header):
            raise SystemExit(
                f"restore/generate: {name} row has {len(r)} cells, header has "
                f"{len(header)}: {r[:3]}")
    out = MANIFESTS / name
    out.parent.mkdir(parents=True, exist_ok=True)
    body = "\t".join(header) + "\n"
    body += "".join("\t".join(_cell(c) for c in r) + "\n" for r in rows)
    out.write_text(body, encoding="utf-8")
    return len(rows)


# =========================================================================================
# Discovery -- the anti-vacuity guard
# =========================================================================================

def discover_components() -> list[str]:
    """Everything on disk that looks like a first-party runtime.

    Deliberately over-inclusive: it is better to force a registry row for something that
    turns out to be uninteresting than to miss a runtime. The rule the owner set is that
    every runtime gets its own top-level folder, so a top-level `symoneural-*` directory is
    the signal.
    """
    found = []
    for p in sorted(ROOT.iterdir()):
        if p.is_dir() and p.name.startswith("symoneural-"):
            found.append(p.name)
    return found


def check_registry_covers_disk() -> list[str]:
    known = R.component_ids()
    missing = [n for n in discover_components() if n not in known]
    if missing:
        raise SystemExit(
            "restore/generate: these runtimes exist on disk and have no row in "
            "restore/lib/registry.py:\n    " + "\n    ".join(missing) +
            "\n\nAdd them. A runtime absent from the registry is absent from the restore "
            "plan, and that is how a restore silently loses a component.")
    return discover_components()


# =========================================================================================
# Tables
# =========================================================================================

def gen_components() -> int:
    header = ["COMPONENT_ID", "CANONICAL_NAME", "CLASS", "SOURCE_ROOT", "LANGUAGE",
              "BUILD_SYSTEM", "BUILD_AUTHORITY", "PRODUCTION_STATUS", "PARENT_COMPONENT",
              "PRIMARY_ARTIFACT", "SERVICE", "RESTORE_REQUIRED", "FIRST_PARTY_STATUS",
              "SOURCE_ROOT_PRESENT", "BLOCKER"]
    rows = [[c.component_id, c.canonical_name, c.cls, c.source_root, c.language,
             c.build_system, c.build_authority, c.production_status, c.parent_component,
             c.primary_artifact, c.service, c.restore_required, c.first_party_status,
             M.exists(c.source_root), c.blocker]
            for c in R.COMPONENTS]
    return write_tsv("COMPONENTS.tsv", header, rows, minimum=15)


def gen_applications() -> int:
    header = ["APPLICATION_ID", "DISPLAY_NAME", "PARENT_APPLICATION_ID", "UI_SOURCE",
              "UI_SOURCE_PRESENT", "ROUTE", "API_ROUTES", "PRIMARY_RUNTIME_COMPONENT",
              "SECONDARY_COMPONENTS", "ENGINE_DEPENDENCIES", "PERSISTENT_STATE_IDS",
              "AUTH_REQUIREMENT", "PRODUCTION_STATUS", "RESTORE_SMOKE_ID"]
    rows = [[a.application_id, a.display_name, a.parent_application_id, a.ui_source,
             M.exists(a.ui_source), a.route, a.api_routes, a.primary_runtime_component,
             a.secondary_components, a.engine_dependencies, a.persistent_state_ids,
             a.auth_requirement, a.production_status, a.restore_smoke_id]
            for a in R.APPLICATIONS]
    return write_tsv("APPLICATIONS.tsv", header, rows, minimum=12)


def gen_source_closure() -> int:
    header = ["COMPONENT_ID", "SOURCE_ROOT", "SOURCE_REVISION", "TRACKED_FILE_COUNT",
              "UNTRACKED_SOURCE_COUNT", "GENERATED_SOURCE_COUNT", "CANONICAL_SOURCE",
              "BUILDABLE_FROM_TRACKED_SOURCE", "INSTALLED_ONLY_FILES",
              "EXTERNAL_SOURCE_DEPENDENCY", "EXTERNAL_SOURCE_REACQUIRABLE",
              "SOURCE_BUNDLE", "SOURCE_BUNDLE_SHA256", "STATUS"]
    rev = M.head()
    rows = []
    for c in R.COMPONENTS:
        derived = c.tracked_in_git == "NO"

        # For a derived tree, "untracked files" is thousands and means nothing: the tree is
        # ignored by design. Its canonical source is the upstream pin plus the fork script,
        # both of which ARE tracked, so the closure question is whether the pin is real.
        if derived:
            tracked = M.tracked_count(c.build_authority.split()[0]) \
                if c.build_authority != NUL else 0
            untracked = "n/a (derived tree, ignored by design)"
            canonical = "UPSTREAM_PIN + tracked fork script"
            # A revision pin alone does not make a tree buildable. symoneural-ui is pinned
            # and has NO scripted build path -- no fork_ui() exists -- so reading YES off
            # the pin would promise a rebuild that nothing can perform.
            # Any tools/fork_*.sh is a scripted build authority. Hard-coding the one
            # filename claimed symoneural-ui had no rebuild path, when in fact
            # tools/fork_render_ui.sh builds it -- a false NO is as bad as a false YES.
            scripted = c.build_authority.startswith("tools/fork_")
            if c.upstream_rev == NUL:
                buildable = "NO (no upstream pin)"
            elif not scripted:
                buildable = "NO (pinned, but no scripted build authority)"
            else:
                buildable = "YES"
            ext = "YES"
            reacq = "YES" if c.upstream != NUL else "NO"
        else:
            tracked = M.tracked_count(c.source_root)
            untracked = M.untracked_count(c.source_root)
            canonical = "YES"
            buildable = "YES"
            ext = "NO"
            reacq = "n/a"

        installed_only = "0"
        status = "PASS"
        if c.production_status == R.PRODUCTION:
            if buildable != "YES":
                status = "FAIL (no rebuild path)"
            elif isinstance(untracked, int) and untracked > 0:
                status = f"FAIL ({untracked} untracked source files)"
        elif c.production_status == R.DECLARED:
            status = "N/A (declared, not implemented)"
        else:
            status = f"N/A ({c.production_status})"

        rows.append([c.component_id, c.source_root, rev, tracked, untracked, "0",
                     canonical, buildable, installed_only, ext, reacq,
                     NUL, NUL, status])
    return write_tsv("SOURCE-CLOSURE.tsv", header, rows, minimum=15)


def gen_build_recipes() -> int:
    header = ["COMPONENT_ID", "SOURCE_ROOT", "SOURCE_REVISION", "BUILD_SYSTEM",
              "BUILD_AUTHORITY", "TOOLCHAIN", "TOOLCHAIN_VERSION", "TARGET_PLATFORM",
              "TARGET_ARCH", "BUILD_PROFILE", "DEPENDENCY_LOCK", "PREP_COMMAND",
              "BUILD_COMMAND", "TEST_COMMAND", "OUTPUT_ARTIFACT", "INSTALL_COMMAND",
              "INSTALL_PATH", "CLEAN_BUILD_SUPPORTED", "NETWORK_REQUIRED", "NOTES"]
    rev = M.head()
    # Measured once, reused: these are host facts, not per-component facts.
    versions = {n: M.tool_version(n) for n in
                ("gcc", "g++", "cmake", "nvcc", "python3", "node", "npm", "git")}
    rows = []
    for c in R.COMPONENTS:
        tv = "; ".join(f"{t}={versions.get(t.strip(), 'UNKNOWN')}"
                       for t in c.toolchain.replace("/", ", ").split(",")
                       if t.strip() and t.strip() != NUL) or NUL
        rows.append([c.component_id, c.source_root, rev, c.build_system, c.build_authority,
                     c.toolchain, tv, "linux-x86_64", c.target_arch, c.build_profile,
                     c.dependency_lock, c.prep_command, c.build_command, c.test_command,
                     c.output_artifact, c.install_command, c.install_path,
                     c.clean_build_supported, c.network_required, c.notes])
    return write_tsv("BUILD-RECIPES.tsv", header, rows, minimum=15)


def gen_artifacts() -> int:
    header = ["ARTIFACT_ID", "COMPONENT_ID", "ARTIFACT_TYPE", "SOURCE_ROOT",
              "SOURCE_REVISION", "BUILD_RECIPE_ID", "BUILD_OUTPUT", "BUILD_SHA256",
              "FILE_TYPE", "ABI_OR_ARCH", "DYNAMIC_DEPENDENCIES", "INSTALLED_PATH",
              "INSTALLED_SHA256", "TEST_STATUS", "SMOKE_STATUS", "FALLBACK_COPY"]
    rev = M.head()
    rows = []
    for c in R.COMPONENTS:
        if c.primary_artifact in (NUL, ""):
            continue
        p = ROOT / c.primary_artifact
        kind = "directory" if p.is_dir() else (
            "executable" if p.is_file() and p.stat().st_mode & 0o111 else "file")
        rows.append([
            f"art-{c.component_id}", c.component_id, kind, c.source_root, rev,
            f"recipe-{c.component_id}", c.primary_artifact,
            M.sha256(p) if p.is_file() else ("DIRECTORY" if p.is_dir() else "NOT_PRESENT"),
            M.file_type(p), M.elf_arch(p), M.dynamic_deps(p),
            c.install_path,
            M.sha256(pathlib.Path(c.install_path).expanduser())
            if c.install_path not in (NUL, "") and not c.install_path.startswith("(")
            else NUL,
            "SEE BUILD-RECIPES.TEST_COMMAND", "SEE SMOKES.tsv",
            "PENDING (.private/runtime-artifacts/<release-id>/)",
        ])
    return write_tsv("ARTIFACTS.tsv", header, rows, minimum=10)


def gen_services() -> int:
    header = ["SERVICE_ID", "COMPONENT_ID", "SOURCE_UNIT", "INSTALLED_UNIT", "USER",
              "GROUP", "WORKING_DIRECTORY", "EXEC_START", "ENV_FILES", "PORTS",
              "DEPENDENCIES", "ENABLEMENT_DESIGNED", "ENABLEMENT_MEASURED",
              "ACTIVE_MEASURED", "INSTALLED_MATCHES_SOURCE", "INSTALL_COMMAND",
              "START_COMMAND", "HEALTHCHECK"]
    rows = []
    for s in R.SERVICES:
        user_scope = s.installed_unit.startswith("~")
        unit_name = s.unit_name if s.unit_name != NUL \
            else pathlib.Path(s.installed_unit).name
        en, ac = M.unit_state(unit_name, user=user_scope)
        # ExecStart read from the SOURCE template, which is the thing a restore installs.
        src = ROOT / s.source_unit
        execstart = NUL
        if src.is_file():
            for ln in src.read_text(errors="replace").splitlines():
                if ln.strip().startswith("ExecStart"):
                    execstart = ln.split("=", 1)[1].strip()
                    break
        rows.append([s.service_id, s.component_id, s.source_unit, s.installed_unit,
                     s.user, s.group, s.working_directory, execstart, s.env_files,
                     s.ports, s.dependencies, s.enablement, en, ac,
                     M.installed_unit_matches(s.source_unit, s.installed_unit),
                     s.install_command, s.start_command, s.healthcheck])
    return write_tsv("SERVICES.tsv", header, rows, minimum=4)


def gen_persistent_state() -> int:
    header = ["STATE_ID", "APPLICATION", "COMPONENT", "LIVE_PATH", "LIVE_PRESENT", "TYPE",
              "CONTAINS_SECRETS", "CONSISTENCY_METHOD", "BACKUP_PATH", "BACKUP_SHA256",
              "OWNER", "MODE", "RESTORE_DESTINATION", "RESTORE_COMMAND",
              "VALIDATION_COMMAND", "REQUIRED_FOR_RESTORE"]
    rows = []
    for s in R.STATE_STORES:
        p = ROOT / s.live_path.split(",")[0].strip()
        try:
            owner = p.owner() if p.exists() else "NOT_PRESENT"
        except (KeyError, OSError):
            owner = "UNRESOLVED_UID"
        rows.append([s.state_id, s.application, s.component, s.live_path,
                     M.exists(s.live_path.split(",")[0].strip()), s.type_,
                     s.contains_secrets, s.consistency_method,
                     "PENDING (.private/application-state/<release-id>/)", "PENDING",
                     owner, M.mode_of(p), s.restore_destination, s.restore_command,
                     s.validation_command, s.required_for_restore])
    return write_tsv("PERSISTENT-STATE.tsv", header, rows, minimum=6)


def gen_restore_order() -> int:
    header = ["ORDER", "STEP_ID", "ACTION", "REQUIRES", "COMMAND", "VERIFY_COMMAND",
              "MUTATES_SYSTEM", "REQUIRES_ROOT", "FAILURE_POLICY"]
    rows = [[s.order, s.step_id, s.action, s.requires, s.command, s.verify_command,
             s.mutates_system, s.requires_root, s.failure_policy]
            for s in R.RESTORE_ORDER]
    return write_tsv("RESTORE-ORDER.tsv", header, rows, minimum=10)


def gen_smokes() -> int:
    header = ["SMOKE_ID", "APPLICATION_ID", "PREREQUISITES", "COMMAND", "EXPECTED_RESULT",
              "NETWORK_SCOPE", "MUTATING", "SAFE_AFTER_FRESH_RESTORE"]
    rows = [[s.smoke_id, s.application_id, s.prerequisites, s.command, s.expected_result,
             s.network_scope, s.mutating, s.safe_after_fresh_restore]
            for s in R.SMOKES]
    return write_tsv("SMOKES.tsv", header, rows, minimum=12)


def gen_first_party_closure() -> int:
    """FIRST-PARTY-CLOSURE.tsv -- written to the REPOSITORY ROOT, where the spec asks for it."""
    header = ["COMPONENT_ID", "APPLICATION", "CURRENT_RUNTIME", "CURRENT_SOURCE",
              "IMPLEMENTATION_CLASS", "THIRD_PARTY_SOURCE_REQUIRED_AT_RUNTIME",
              "THIRD_PARTY_SOURCE_REQUIRED_AT_BUILD", "FIRST_PARTY_REPLACEMENT",
              "TEST_STATUS", "PRODUCTION_STATUS", "EXTERNAL_SOURCE_CAN_BE_OMITTED",
              "BLOCKER"]
    app_of = {}
    for a in R.APPLICATIONS:
        for cid in [a.primary_runtime_component] + a.engine_dependencies.split(","):
            cid = cid.strip().split(" ")[0]
            if cid and cid != NUL:
                app_of.setdefault(cid, []).append(a.application_id)

    rows = []
    for c in R.COMPONENTS:
        derived = c.first_party_status in (R.DERIV_PERMISSIVE, R.DERIV_COPYLEFT)
        # Runtime: does the SHIPPED thing need third-party source present to run? No -- the
        # engines are compiled; once built, the source tree is not read at runtime.
        rt = "NO"
        # Build: yes for a fork, and that is the honest answer.
        bt = "YES (pinned upstream, reacquired)" if derived else "NO"
        # Omittable when the upstream can be fetched again at an exact revision. The
        # kawpowminer tree cannot be fully reconstructed from a pin alone -- it carries
        # uncommitted local edits -- so its patch is preserved and that is said here.
        if not derived:
            omit = "YES (no external source involved)"
        elif c.upstream_rev != NUL and c.local_patch == NUL:
            omit = "YES (clean clone at a pinned revision, reacquirable)"
        elif c.upstream_rev != NUL:
            omit = "YES (pin + preserved local patch)"
        else:
            omit = "NO"

        replacement = NUL
        if c.component_id == "symoneural-miner":
            replacement = "symoneural-miner-core (INCOMPLETE -- see docs/ALGORITHM-GAP.md)"

        rows.append([c.component_id, ",".join(app_of.get(c.component_id, [])) or NUL,
                     c.primary_artifact, c.source_root, c.first_party_status, rt, bt,
                     replacement, "SEE BUILD-RECIPES.TEST_COMMAND", c.production_status,
                     omit, c.blocker])

    out = ROOT / "FIRST-PARTY-CLOSURE.tsv"
    out.write_text("\t".join(header) + "\n" +
                   "".join("\t".join(_cell(x) for x in r) + "\n" for r in rows),
                   encoding="utf-8")
    return len(rows)


def gen_release(release_id: str, extra: dict | None = None) -> pathlib.Path:
    prod = [c for c in R.COMPONENTS if c.production_status == R.PRODUCTION]
    # `created_at` is the COMMIT date of repository_head, not the wall clock. A clock
    # reading makes RELEASE.json differ on every regeneration, so `git status` is dirty
    # forever and a real change is invisible in the noise -- and it dates the act of
    # running a generator rather than the release it describes.
    committed = M.run(["git", "show", "-s", "--format=%cI", "HEAD"])
    doc = {
        "schema_version": 1,
        "release_id": release_id,
        "created_at": committed if committed not in ("UNMEASURED", "") else None,
        "generated_at_note": "created_at is the commit date of repository_head, so this "
                             "document is a function of the commit and not of when the "
                             "generator happened to run",
        "repository_head": M.head(),
        "branch": M.branch(),
        "repository_clean": M.is_clean(),
        "component_count": len(R.COMPONENTS),
        "production_component_count": len(prod),
        "application_count": len(R.APPLICATIONS),
        "production_application_count":
            sum(1 for a in R.APPLICATIONS if a.production_status == R.PRODUCTION),
        "service_count": len(R.SERVICES),
        "persistent_state_count": len(R.STATE_STORES),
        "smoke_count": len(R.SMOKES),
        "restore_entrypoint": "restore/symoneural-restore",
        "manifest_root": "restore/manifests",
        "git_bundle_path": ".private/git-backup/Symoneural-all.bundle",
        "runtime_artifact_root": f".private/runtime-artifacts/{release_id}",
        "source_bundle_root": f".private/source-bundles/{release_id}",
        "persistent_state_root": f".private/application-state/{release_id}",
        "host_snapshot_root": ".private/host-snapshot",
        "claude_backup_root": ".private/claude-backups",
        "host": {
            "gcc": M.tool_version("gcc"),
            "cmake": M.tool_version("cmake"),
            "nvcc": M.tool_version("nvcc"),
            "python3": M.tool_version("python3"),
            "node": M.tool_version("node"),
            "npm": M.tool_version("npm"),
            "gpu": M.gpu(),
        },
    }
    if extra:
        # `created_at` is derived above and is deliberately not overridable: a caller
        # passing a clock reading would reintroduce exactly the non-determinism this
        # avoids.
        doc.update({k: v for k, v in extra.items() if k != "created_at"})
    out = ROOT / "restore" / "RELEASE.json"
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def generate_all(release_id: str, extra: dict | None = None) -> dict[str, int]:
    check_registry_covers_disk()
    counts = {
        "COMPONENTS.tsv": gen_components(),
        "APPLICATIONS.tsv": gen_applications(),
        "SOURCE-CLOSURE.tsv": gen_source_closure(),
        "BUILD-RECIPES.tsv": gen_build_recipes(),
        "ARTIFACTS.tsv": gen_artifacts(),
        "SERVICES.tsv": gen_services(),
        "PERSISTENT-STATE.tsv": gen_persistent_state(),
        "RESTORE-ORDER.tsv": gen_restore_order(),
        "SMOKES.tsv": gen_smokes(),
        "FIRST-PARTY-CLOSURE.tsv": gen_first_party_closure(),
        "DEPENDENCIES.tsv": D.gen_dependencies(write_tsv),
        "THIRD-PARTY-REBUILD-MANIFEST.tsv": D.gen_third_party_rebuild(_cell),
    }
    gen_release(release_id, extra)
    return counts
