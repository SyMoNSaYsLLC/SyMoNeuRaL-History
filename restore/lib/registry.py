# SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
# Copyright (c) 2026 SymonSays LLC. All rights reserved.
# SyMoNeuRaL is a subdivision of SymonSays LLC. Licence: /LICENSE at the repository root.
"""The judgement half of the restore control plane.

Everything in `restore/manifests/` is GENERATED. Half of each row is measured off the disk
at generation time -- file counts, revisions, checksums, whether a binary is where a recipe
says it lands -- and half is a judgement that no measurement can make: is this component
production, is this implementation ours, may this external tree be omitted from the backup.
The measured half lives in `measure.py`. The judged half lives here.

The split exists because this repository has been burned three separate times by a
hand-maintained table drifting away from the thing it described, and `ROSTER.md` opens by
naming that failure. A TSV anybody can edit is a second state document. So the TSVs are
outputs, this file is the input, and `apps/test_restore_manifests.py` fails if a component
appears on disk with no row here -- a new runtime cannot be silently omitted from the
restore plan, which is the only way a restore quietly loses something.

## The classification vocabulary, and why it is not "first-party / not first-party"

`FIRST_PARTY_STATUS` is the field the owner's reset gate turns on, so it is spelled out
rather than reduced to a boolean:

    FIRST_PARTY                      we wrote it; SyMoNeuRaL owns the copyright
    CLEAN_ROOM_FROM_PUBLIC_SPEC      we wrote it from a published standard, not from
                                     somebody's source -- e.g. Keccak from FIPS PUB 202
    THIRD_PARTY_DERIVATIVE_PERMISSIVE   a fork of an MIT/BSD/Apache upstream. Our patches
                                     are ours; the upstream's notice must travel with it.
                                     NOT first-party, and calling it that is the exact
                                     relabelling `fork_engines.sh` refuses to do.
    THIRD_PARTY_DERIVATIVE_COPYLEFT  a fork of a GPL/LGPL/AGPL upstream. Cannot be made
                                     first-party by any amount of editing.
    PLATFORM_DEPENDENCY              the OS, the driver, CUDA, Python. Not our source and
                                     not a thing to carry in a source backup.
    DECLARED_NOT_IMPLEMENTED         a name with a README and no code behind it.

Note what is missing: there is no value meaning "first-party because we renamed it". The
owner's instruction was *"we cannot use code in references its for reference only we must
rebrand if we want to use it"*, and the licence-stamping block in `tools/fork_engines.sh`
already encodes the legal half of that -- it REFUSES to stamp the SyMoNeuRaL licence on a
copyleft upstream. This file must not undo that refusal by writing a friendlier word in a
column.

## `EXTERNAL_SOURCE_CAN_BE_OMITTED` is about reacquisition, not about disuse

The reset gate wants `ACTIVE_EXTERNAL_SOURCE_DEPENDENCIES=0`, and the tempting way to get
there is to claim nothing uses `external/`. That claim is false: `tools/fork_engines.sh`
reads `external/referencestochatgpt/{llama.cpp,stable-diffusion.cpp,whisper.cpp}` and those
three builds are what serve chat, image and ASR.

What is true, and what was measured on 2026-09-08, is that every one of those trees is a
clean `git clone` of a public remote at a known revision with zero local modifications. So
149 GB of source custody collapses into a remote URL and a forty-hex string, and the
component is still rebuildable on a machine that has never seen this disk. That is the
honest reading of "the external tree may be omitted": omitted because it is *reacquirable*,
recorded as a pin in `THIRD-PARTY-REBUILD-MANIFEST.tsv`, not omitted because it is unused.

The one place that reasoning does not reach is a tree with uncommitted local changes, since
a revision pin cannot restore work that was never committed anywhere. `kawpowminer` is in
exactly that position -- three modified files -- so its patch is extracted and preserved
even though the component itself is disabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------------------
# Status vocabulary. `PRODUCTION` is the lever every acceptance rule in the owner's spec
# hangs off -- the gates are written "for every production component" -- so an honest
# DISABLED is not a way of dodging the gate, it is the disposition the spec explicitly
# provides for anything that cannot meet it (its Target 5 and Target 27 both say so).
PRODUCTION = "PRODUCTION"                 # serves users now; must restore
INFRASTRUCTURE = "INFRASTRUCTURE"         # no surface, but production depends on it
DISABLED = "DISABLED"                     # deliberately off; source kept, feature not served
EXPERIMENTAL = "EXPERIMENTAL"             # present and runnable, not depended on
DECLARED = "DECLARED_NOT_IMPLEMENTED"     # a name and a README, no implementation

FIRST_PARTY = "FIRST_PARTY"
CLEAN_ROOM = "CLEAN_ROOM_FROM_PUBLIC_SPEC"
DERIV_PERMISSIVE = "THIRD_PARTY_DERIVATIVE_PERMISSIVE"
DERIV_COPYLEFT = "THIRD_PARTY_DERIVATIVE_COPYLEFT"
PLATFORM = "PLATFORM_DEPENDENCY"


@dataclass(frozen=True)
class Component:
    """One restorable unit. Fields map onto COMPONENTS.tsv and BUILD-RECIPES.tsv."""

    component_id: str
    canonical_name: str
    cls: str
    source_root: str
    language: str
    build_system: str
    build_authority: str
    production_status: str
    first_party_status: str
    primary_artifact: str = "-"
    parent_component: str = "-"
    service: str = "-"
    restore_required: str = "YES"
    blocker: str = "-"

    # ---- build recipe. Commands are literal and runnable from the repository root.
    # "build normally" is not a recipe; the owner's spec says so and it is right.
    toolchain: str = "-"
    target_arch: str = "-"
    build_profile: str = "-"
    dependency_lock: str = "-"
    prep_command: str = "-"
    build_command: str = "-"
    test_command: str = "-"
    output_artifact: str = "-"
    install_command: str = "-"
    install_path: str = "-"
    clean_build_supported: str = "YES"
    network_required: str = "NO"
    notes: str = "-"

    # ---- upstream identity, for derivative components only. `upstream_rev` is what makes
    # the external tree omittable; without it the fork is unreproducible and the source
    # would have to travel.
    upstream: str = "-"
    upstream_rev: str = "-"
    upstream_license: str = "-"
    upstream_local_path: str = "-"
    local_patch: str = "-"

    # ---- source closure inputs
    tracked_in_git: str = "YES"
    generated_from: str = "-"

    # ---- clean-rebuild evidence, MEASURED. The owner's spec is explicit that
    # CLEAN_REBUILD_GATE must not be claimed from a repository inventory test, so this
    # field is only ever set from an actual build performed in the isolated bundle-only
    # rehearsal tree, with the compiler's real exit status captured to a logfile.
    # "-" means no rebuild was attempted, which is different from one that failed.
    clean_rebuild: str = "-"
    reproducible_bytes: str = "-"


# =========================================================================================
# COMPONENTS
# =========================================================================================
#
# Ordered engines -> first-party runtimes -> service surfaces -> planes, which is roughly
# restore order and makes the table readable top to bottom.

COMPONENTS: tuple[Component, ...] = (

    # -------------------------------------------------------------------- the five forks
    #
    # These five are gitignored on purpose. `.gitignore` explains it: they are "derived
    # tree[s] built from somebody else's release tarball", rebuilt by fork_engines.sh, and
    # committing them would be ~11 GB of objects that Git would then be asked to be the
    # authority for. Their restore path is: reacquire the pinned upstream, run the fork
    # script, get the artefact. That path is only real if the pin is real, which is why
    # `upstream_rev` here is a measured value and `test_restore_manifests.py` checks that
    # the recorded pin still matches the tree on disk while the tree is still on disk.

    Component(
        component_id="symoneural-llm",
        canonical_name="SyMoNeuRaL LLM",
        cls="engine",
        source_root="symoneural-llm",
        language="C++/CUDA",
        build_system="cmake",
        build_authority="tools/fork_engines.sh llm",
        production_status=PRODUCTION,
        first_party_status=DERIV_PERMISSIVE,
        primary_artifact="symoneural-llm/build/bin/symoneural-llm",
        service="symoneural-api.service (spawned as a subprocess, not a unit of its own)",
        toolchain="gcc/g++, cmake, nvcc",
        target_arch="x86_64 + sm_120",
        build_profile="Release, -fstack-protector-strong, -Wl,-z,relro -Wl,-z,now",
        prep_command="tools/restore-upstream.sh llama.cpp",
        build_command="tools/fork_engines.sh llm",
        test_command="cd backend && python3 -m pytest apps/test_probes.py -q",
        output_artifact="symoneural-llm/build/bin/symoneural-llm",
        install_command="(none -- api.py execs it in place from the repository)",
        install_path="symoneural-llm/build/bin/symoneural-llm",
        network_required="YES (git clone of the pinned upstream, once)",
        upstream="https://github.com/ggml-org/llama.cpp.git",
        upstream_rev="4df29be4f4c3673f428170fda944a5b19f743bb8",
        upstream_license="MIT",
        upstream_local_path="external/referencestochatgpt/llama.cpp",
        tracked_in_git="NO",
        generated_from="pinned upstream + tools/fork_engines.sh",
        notes="Serves /api/chat. RUNPATH is $ORIGIN so every library it loads is one this "
              "build produced. GGML_BACKEND_DL must stay OFF or the OUTPUT_NAME renaming "
              "makes the CUDA backend undiscoverable at runtime.",
        clean_rebuild="PASS (fork_engines.sh llm rc=0 from reacquired llama.cpp)",
        reproducible_bytes="NO -- identical size and 4 NEEDED, CUDA build metadata differs",
    ),

    Component(
        component_id="symoneural-diffuse",
        canonical_name="SyMoNeuRaL Diffuse",
        cls="engine",
        source_root="symoneural-diffuse",
        language="C++/CUDA",
        build_system="cmake",
        build_authority="tools/fork_engines.sh diffuse",
        production_status=PRODUCTION,
        first_party_status=DERIV_PERMISSIVE,
        primary_artifact="symoneural-diffuse/build/bin/symoneural-diffuse",
        service="symoneural-api.service (subprocess)",
        toolchain="gcc/g++, cmake, nvcc",
        target_arch="x86_64 + sm_120",
        build_profile="Release, hardened",
        prep_command="tools/restore-upstream.sh stable-diffusion.cpp",
        build_command="tools/fork_engines.sh diffuse",
        test_command="cd backend && python3 -m pytest apps/test_probes.py -q",
        output_artifact="symoneural-diffuse/build/bin/symoneural-diffuse",
        install_path="symoneural-diffuse/build/bin/symoneural-diffuse",
        network_required="YES (git clone of the pinned upstream, once)",
        upstream="https://github.com/leejet/stable-diffusion.cpp.git",
        upstream_rev="de298c225bed97c3f9026b73cd7b71e7879bd41b",
        upstream_license="MIT",
        upstream_local_path="external/referencestochatgpt/stable-diffusion.cpp",
        tracked_in_git="NO",
        generated_from="pinned upstream + tools/fork_engines.sh",
        notes="Serves /api/image. Silently rounds unsupported dimensions; api.py "
              "documents the clamp at its call site. RESTORE CONSTRAINT: unlike the other "
              "engines this binary's RUNPATH is the ABSOLUTE path "
              "/usr/local/cuda-13.3/targets/x86_64-linux/lib, not $ORIGIN -- measured on "
              "both the production and the rebuilt artefact, so it is by design. A "
              "restored machine needs the CUDA runtime at that exact location or the "
              "engine builds successfully and then fails to load its libraries at RUN "
              "time, which surfaces only when a visitor asks for an image.",
        clean_rebuild="PASS (fork_engines.sh diffuse rc=0 from reacquired stable-diffusion.cpp)",
        reproducible_bytes="NO -- +20,480 bytes, explained by the embedded git-describe version string the binary prints at startup",
    ),

    Component(
        component_id="symoneural-listen",
        canonical_name="SyMoNeuRaL Listen",
        cls="engine",
        source_root="symoneural-listen",
        language="C++/CUDA",
        build_system="cmake",
        build_authority="tools/fork_engines.sh listen",
        production_status=EXPERIMENTAL,
        first_party_status=DERIV_PERMISSIVE,
        primary_artifact="symoneural-listen/build/bin/symoneural-listen",
        toolchain="gcc/g++, cmake, nvcc",
        target_arch="x86_64 + sm_120",
        build_profile="Release, hardened",
        prep_command="tools/restore-upstream.sh whisper.cpp",
        build_command="tools/fork_engines.sh listen",
        test_command="cd backend && python3 -m pytest apps/test_probes.py -q",
        output_artifact="symoneural-listen/build/bin/symoneural-listen",
        install_path="symoneural-listen/build/bin/symoneural-listen",
        network_required="YES (git clone of the pinned upstream, once)",
        upstream="https://github.com/ggerganov/whisper.cpp.git",
        upstream_rev="1fe009caeda75f69bc864d6370b10674e45a92bd",
        upstream_license="MIT",
        upstream_local_path="external/referencestochatgpt/whisper.cpp",
        tracked_in_git="NO",
        generated_from="pinned upstream + tools/fork_engines.sh",
        notes="ASR. EXPERIMENTAL rather than PRODUCTION: `voice` has no page, so no rack "
              "row points at it and nothing user-facing depends on it today.",
        clean_rebuild="PASS (fork_engines.sh listen rc=0 from reacquired whisper.cpp)",
        reproducible_bytes="YES -- sha256 identical to the production artefact",
    ),

    Component(
        component_id="symoneural-miner",
        canonical_name="SyMoNeuRaL Miner (KawPoW fork)",
        cls="engine",
        source_root="symoneural-miner",
        language="C++/CUDA",
        build_system="cmake",
        build_authority="tools/fork_engines.sh miner",
        production_status=DISABLED,
        first_party_status=DERIV_COPYLEFT,
        primary_artifact="symoneural-miner/build/kawpowminer/symoneural-miner",
        restore_required="NO",
        blocker="GPL-3.0 upstream. Cannot be relabelled first-party; fork_engines.sh "
                "REFUSES to stamp the SyMoNeuRaL licence on it. Disabled for the reset "
                "rather than carried, per the owner's Target 5.",
        toolchain="gcc/g++, cmake, nvcc",
        target_arch="x86_64 + sm_120 (COMPUTE=120)",
        build_profile="Release, HUNTER_ENABLED=OFF, ETHASHCUDA=ON",
        prep_command="tools/restore-upstream.sh kawpowminer  # then build the static "
                     "dependency prefix -- see NOTES",
        build_command="tools/fork_engines.sh miner",
        test_command="-",
        output_artifact="symoneural-miner/build/kawpowminer/symoneural-miner",
        clean_build_supported="NO",
        network_required="YES",
        upstream="https://github.com/RavenCommunity/kawpowminer.git",
        upstream_rev="8bd0d598fa29a77378dbdb184ee8d53be245a89a",
        upstream_license="GPL-3.0",
        upstream_local_path="external/referencestochatgpt/kawpowminer",
        local_patch=".private/upstream-patches/kawpowminer-local.patch",
        tracked_in_git="NO",
        generated_from="pinned upstream + tools/fork_engines.sh",
        notes="Additionally needs external/referencestochatgpt/kawpow-deps, a PREBUILT "
              "static prefix (boost/jsoncpp/ethash) produced by "
              "external/contrib/build-kawpowminer.sh -- so a clean rebuild is a ~40 minute "
              "two-stage job with a network fetch, which is why CLEAN_BUILD_SUPPORTED=NO "
              "is recorded rather than assumed. The upstream checkout carries THREE "
              "uncommitted local modifications; a revision pin cannot restore those, so "
              "the patch is extracted to .private/upstream-patches/ even though the "
              "component is disabled. The honest first-party replacement is "
              "symoneural-miner-core, which is incomplete -- see its ALGORITHM-GAP.md.",
    ),

    Component(
        component_id="symoneural-ui",
        canonical_name="SyMoNeuRaL UI (ComfyUI fork)",
        cls="ui",
        source_root="symoneural-ui",
        language="Python",
        build_system="pip",
        build_authority="tools/fork_render_ui.sh",
        production_status=DISABLED,
        first_party_status=DERIV_COPYLEFT,
        primary_artifact="symoneural-ui/main.py",
        restore_required="NO",
        blocker="GPL-3.0 upstream (ComfyUI). Same refusal as the miner: a copyleft "
                "upstream cannot be relicensed by editing files, so this tree can never "
                "be first-party. DISABLED for the reset rather than carried.",
        toolchain="python3, pip",
        target_arch="x86_64",
        prep_command="tools/restore-upstream.sh ComfyUI",
        build_command="tools/fork_render_ui.sh",
        test_command="-",
        clean_build_supported="NO",
        network_required="YES",
        upstream="https://github.com/comfyanonymous/ComfyUI.git",
        upstream_rev="76135e557da1ec7dcb270160f01e597565e3e003",
        upstream_license="GPL-3.0",
        upstream_local_path="external/referencestochatgpt/ComfyUI",
        tracked_in_git="NO",
        generated_from="pinned upstream, hand-applied changes (unscripted)",
        notes="No rack row points here; Studio's GPU work goes through the API's own "
              "engines, not through this tree. It DOES have a scripted rebuild path -- "
              "tools/fork_render_ui.sh -- which an earlier draft of this registry denied. "
              "Buildable and disabled are different facts and both are recorded.",
    ),

    # ------------------------------------------------------------- first-party runtimes
    #
    # These ARE ours: written here, tracked in Git, no upstream. `.gitignore` calls the
    # distinction out by name for symoneural-code and symoneural-audit -- "these two are
    # what we wrote" -- and it is the same distinction for the rest of this block.

    Component(
        component_id="symoneural-api",
        canonical_name="SyMoNeuRaL API",
        cls="service",
        source_root="backend",
        language="Python",
        build_system="none (interpreted)",
        build_authority="-",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="backend/api.py",
        service="symoneural-api.service",
        toolchain="python3",
        target_arch="any",
        # NOT a venv. `backend/DEPENDENCIES.md`: "the serving path is the system
        # interpreter (Debian, 196 packages, no virtualenv on purpose)". An earlier draft
        # of this row named backend/requirements.lock.txt, which has never existed -- a
        # restore recipe pointing at a file nobody has written is worse than none.
        dependency_lock="restore/locks/serving-system.lock.txt",
        prep_command="sudo python3 -m pip install --break-system-packages -r "
                     "restore/locks/serving-system.lock.txt",
        build_command="(interpreted -- no build step)",
        test_command="cd backend && python3 -m pytest -q",
        output_artifact="backend/api.py",
        install_command="sudo install -m0644 ops/symoneural-api.service "
                        "/etc/systemd/system/ && sudo systemctl daemon-reload",
        install_path="/etc/systemd/system/symoneural-api.service",
        notes="The rack. Serves every /api/* route, owns the GPU lease, and spawns the "
              "llm and diffuse engines as subprocesses. `symoneural-api/` at the "
              "repository root is the RUNTIME FOLDER (a launcher and a README), not the "
              "source; the source is backend/.",
    ),

    Component(
        component_id="symoneural-api-runtime",
        canonical_name="SyMoNeuRaL API runtime launcher",
        cls="cli",
        source_root="symoneural-api",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=INFRASTRUCTURE,
        first_party_status=FIRST_PARTY,
        primary_artifact="symoneural-api/bin/symoneural-api",
        parent_component="symoneural-api",
        test_command="cd backend && python3 -m pytest apps/test_symoneural_cli.py -q",
        install_command="scripts/install-cli.sh",
        install_path="~/.local/bin/symoneural-api",
        notes="The owner asked for the API to have its own runtime folder like the other "
              "runtimes rather than being reachable only as a module of the web stack.",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-web",
        canonical_name="SyMoNeuRaL Web",
        cls="service",
        source_root="web/symoneural-web",
        language="Go",
        build_system="go",
        build_authority="ops/build-symoneural-web.sh",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="web/symoneural-web/build/symoneural-web",
        service="symoneural-web.service",
        toolchain="go",
        target_arch="x86_64",
        build_profile="release (default gc toolchain)",
        dependency_lock="web/symoneural-web/go.sum",
        prep_command="cd web/symoneural-web && go mod download   # needs Go >= 1.25.1",
        build_command="ops/build-symoneural-web.sh",
        test_command="cd web/symoneural-web && go vet ./...",
        output_artifact="web/symoneural-web/build/symoneural-web",
        install_command="sudo install -m0644 ops/symoneural-web.service "
                        "/etc/systemd/system/ && sudo systemctl daemon-reload",
        install_path="/etc/systemd/system/symoneural-web.service",
        network_required="YES -- modules AND possibly the toolchain itself; see NOTES",
        notes="THE PRODUCTION WEB SERVER for symoneural.com, and it has no fallback. "
              "An earlier draft recorded its source as site/ and its build system as "
              "python generators -- conflating the served ASSETS with the SERVER. The "
              "unit's measured ExecStart is web/symoneural-web/build/symoneural-web run "
              "--environ --config /etc/caddy/Caddyfile. Served assets are the separate "
              "symoneural-site component. "
              "CLASSIFICATION: main.go is 146 lines of FIRST-PARTY Go that IMPORTS Caddy "
              "as an Apache-2.0 LIBRARY -- it does not fork, patch or vendor it, and it "
              "explicitly refuses the copy-caddy-under-our-name shortcut as a false "
              "authorship claim. So the application source is ours and Caddy is a package "
              "dependency: THIRD_PARTY_SOURCE_CARRIED_IN_BACKUP=NO, "
              "REBUILDABLE_FROM_LOCKED_MODULES=YES via go.sum (573 entries). "
              "BUILD AUTHORITY is ops/build-symoneural-web.sh, NOT a plain `go build`: it "
              "stamps -ldflags -X main.version/gitCommit/buildID/licenseSHA and emits "
              "THIRD_PARTY_NOTICES.md over 547 modules plus go-modules.tsv and "
              "build-manifest.json. A plain go build produces a binary whose --version "
              "honestly reports `unknown`, which is by design -- verified by building it "
              "both ways. "
              "TOOLCHAIN: go.mod requires go 1.25.1; this host's Debian Go is 1.24.4 and "
              "GOTOOLCHAIN=auto silently fetches golang.org/toolchain@v0.0.1-go1.25.1 as "
              "a module. With GOTOOLCHAIN=local the build FAILS rc=1. A restored machine "
              "therefore needs Go >= 1.25.1 or network access to fetch it; the module and "
              "toolchain caches are NOT carried in the archive.",
        clean_rebuild="PASS (ops/build-symoneural-web.sh rc=0, go vet rc=0)",
        reproducible_bytes="NO -- binary embeds its own git commit and build id",
    ),

    Component(
        component_id="symoneural-site",
        canonical_name="SyMoNeuRaL Site",
        cls="frontend",
        source_root="site",
        language="HTML/CSS/JS",
        build_system="python generators",
        build_authority="tools/build_rack.py, tools/build_cachebust.py",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="site",
        parent_component="symoneural-web",
        service="served by symoneural-web.service",
        toolchain="python3",
        target_arch="any",
        build_command="python3 tools/build_rack.py && python3 tools/build_cachebust.py",
        test_command="cd backend && python3 -m pytest apps/test_build_progress.py "
                     "apps/test_roster.py -q",
        output_artifact="site",
        install_command="(none -- served in place from the repository)",
        install_path="site",
        notes="The pages a visitor sees: chat.html, image.html, sigils.html and the rest. "
              "Hand-authored HTML plus two generators -- build_rack.py emits the pre-JS "
              "rack fallback from backend/apps/ROSTER.md so those rows stop being carried "
              "by hand, and build_cachebust.py stamps asset URLs. Separate from "
              "symoneural-web because assets and the server that serves them fail, build "
              "and restore independently.",
    ),

    Component(
        component_id="symoneural-gateway",
        canonical_name="SyMoNeuRaL Gateway",
        cls="service",
        source_root="backend/apps/gateway",
        language="Rust (service binary) + Python (settlement modules)",
        build_system="cargo",
        build_authority="cargo build --release",
        production_status=DISABLED,
        first_party_status=FIRST_PARTY,
        primary_artifact="backend/apps/gateway/target/release/symoneural-gateway",
        parent_component="symoneural-api",
        service="symoneural-gateway.service (disabled)",
        blocker="No contract, no wallet, no key material. Its rack LED has never been "
                "anything but grey. Disabled by configuration, not by defect -- the "
                "source and build mapping below are truthful regardless.",
        toolchain="cargo, rustc",
        target_arch="x86_64",
        build_profile="release",
        dependency_lock="backend/apps/gateway/Cargo.lock",
        prep_command="cd backend/apps/gateway && cargo fetch --locked",
        build_command="cd backend/apps/gateway && cargo build --release --locked",
        test_command="cd backend/apps/gateway && cargo test --release --locked",
        output_artifact="backend/apps/gateway/target/release/symoneural-gateway",
        install_command="sudo install -m0644 ops/symoneural-gateway.service "
                        "/etc/systemd/system/ && sudo systemctl daemon-reload",
        install_path="/etc/systemd/system/symoneural-gateway.service",
        network_required="YES (cargo fetch, once)",
        notes="TWO runtimes in one directory, and an earlier draft of this registry "
              "recorded only the Python one. The SERVICE executes a Rust binary -- the "
              "unit's measured ExecStart is target/release/symoneural-gateway, built by "
              "cargo from 8 .rs files with 362 crates pinned in Cargo.lock. The thirteen "
              "TRON settlement modules (abi.py, address.py, chain.py, keccak.py, ...) are "
              "Python mounted inside the API and serve /gateway.html's state; they are "
              "not what the unit runs. Describing the deployed gateway as "
              "Python/no-build because Python files are present would have left a "
              "restored machine with a unit pointing at a binary nothing knew how to "
              "build -- which is exactly the defect test_gateway_unit.py was written "
              "after: the ExecStart named a file that did not exist and no test noticed.",
        clean_rebuild="PASS (cargo build --release --locked rc=0 from an empty target/; cargo test rc=0 but RUST_TEST_COUNT=0, which is a passing command and NOT functional coverage)",
        reproducible_bytes="NO -- identical size, arch and 4 NEEDED, but sha differs",
    ),

    Component(
        component_id="symoneural-code",
        canonical_name="SyMoNeuRaL Code",
        cls="cli",
        source_root="symoneural-code",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="symoneural-code/bin/symoneural-code",
        test_command="cd backend && python3 -m pytest apps/test_symoneural_cli.py -q && "
                     "python3 -m pytest symoneural-code/tests -q",
        install_command="scripts/install-cli.sh",
        install_path="~/.local/bin/symoneural-code",
        notes="Also provides symoneural-cli and symoneural-discovery. Carries "
              "src/symoneural_import/claude.py, the provider-neutral importer that took "
              "the owner's portable Claude material into first-party structures.",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-cli",
        canonical_name="SyMoNeuRaL CLI",
        cls="cli",
        source_root="symoneural-code/bin/symoneural-cli",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="symoneural-code/bin/symoneural-cli",
        parent_component="symoneural-code",
        test_command="cd backend && python3 -m pytest apps/test_symoneural_cli.py -q",
        install_command="scripts/install-cli.sh",
        install_path="~/.local/bin/symoneural-cli",
        notes="14 subcommands including import-claude. Installed as a SYMLINK, not a copy: "
              "a copied launcher at ~/.symoneural-full/bin diverged from its source and "
              "nothing noticed for days.",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-discovery",
        canonical_name="SyMoNeuRaL Discovery",
        cls="cli",
        source_root="symoneural-code/bin/symoneural-discovery",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="symoneural-code/bin/symoneural-discovery",
        parent_component="symoneural-code",
        test_command="cd backend && python3 -m pytest apps/test_symoneural_cli.py -q",
        install_command="scripts/install-cli.sh",
        install_path="~/.local/bin/symoneural-discovery",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-audit",
        canonical_name="SyMoNeuRaL Audit",
        cls="cli",
        source_root="symoneural-audit",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=PRODUCTION,
        first_party_status=FIRST_PARTY,
        primary_artifact="symoneural-audit/bin/symoneural-audit",
        test_command="cd backend && python3 -m pytest apps/test_path_fragility.py -q",
        install_command="scripts/install-cli.sh",
        install_path="~/.local/bin/symoneural-audit",
        notes="The runtime behind the path-fragility ratchet. Its README carries the "
              "marker-walk rule: never count parents to find the repository root.",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-miner-core",
        canonical_name="SyMoNeuRaL Miner Core",
        cls="library",
        source_root="symoneural-miner-core",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=DISABLED,
        first_party_status=CLEAN_ROOM,
        primary_artifact="symoneural-miner-core/src/symoneural_miner_core",
        blocker="Honest first-party miner, deliberately incomplete: Keccak-f[800]/f[1600], "
                "the Stratum client, the fail-closed config and a loopback pool fixture "
                "are done; the ProgPoW loop, the DAG and the CUDA kernel are NOT. See "
                "symoneural-miner-core/docs/ALGORITHM-GAP.md. Calling this a miner would "
                "be the relabelling this repository keeps getting burned by.",
        test_command="python3 -m pytest symoneural-miner-core/tests -q",
        output_artifact="symoneural-miner-core/SMOKE-miner-core.md",
        notes="CLEAN_ROOM_FROM_PUBLIC_SPEC is claimed for the Keccak only, and it is "
              "claimed literally: the round constants are COMPUTED from the LFSR in FIPS "
              "PUB 202 Algorithm 5 rather than pasted from anyone's table.",
    ),

    Component(
        component_id="symoneural-adaptive-fabric",
        canonical_name="SyMoNeuRaL Adaptive Fabric",
        cls="runtime",
        source_root="symoneural-adaptive-fabric",
        language="-",
        build_system="-",
        build_authority="-",
        production_status=DECLARED,
        first_party_status="DECLARED_NOT_IMPLEMENTED",
        restore_required="NO",
        blocker="README and LICENCE only -- two tracked files and no implementation. The "
                "owner asked for this runtime and it has a name and a folder; it does not "
                "yet have code. Recorded as DECLARED so the restore plan cannot appear to "
                "restore something that was never built.",
        notes="DEFINED, not PRESENT. The repository's own four-level vocabulary "
              "(DEFINED/PRESENT/WIRED/VERIFIED) is what this row is written in.",
    ),

    Component(
        component_id="symoneural-restore",
        canonical_name="SyMoNeuRaL Restore",
        cls="plane",
        source_root="restore",
        language="Python",
        build_system="none",
        build_authority="-",
        production_status=INFRASTRUCTURE,
        first_party_status=FIRST_PARTY,
        primary_artifact="restore/symoneural-restore",
        test_command="cd backend && python3 -m pytest apps/test_restore_manifests.py -q",
        install_command="(none -- run it from the extracted archive)",
        install_path="restore/symoneural-restore",
        notes="This control plane. Restores everything else, so it must be runnable from "
              "a bare extraction with nothing installed: standard library only, no venv, "
              "no third-party import.",
        build_command="(interpreted -- no build step)",
    ),

    Component(
        component_id="symoneural-buildv2",
        canonical_name="SyMoNeuRaL BuildV2",
        cls="framework",
        source_root="archive/buildv2",
        language="Python/C",
        build_system="make/cmake + tools/symon",
        build_authority="archive/buildv2/tools/symon",
        production_status=INFRASTRUCTURE,
        first_party_status=FIRST_PARTY,
        primary_artifact="archive/buildv2/tools/symon",
        restore_required="OPTIONAL",
        test_command="-",
        notes="Toolchain qualification authority. Consolidated 2026-09-08 from "
              "archive/from-desktop/symoneural-buildv2 (it had already left the Desktop "
              "in an earlier sweep) by same-filesystem rename, so MANIFEST.sha256 and the "
              "bootstrap scripts' relative paths still resolve -- verified after the move. "
              "The evidence ZIP is mode 0600 and sha256 8bf3e74f...ab40ab9, matching the "
              "value the owner published; sanitycheck.md says explicitly not to widen it "
              "to 0644, and the move did not. archive/ is gitignored, so this tree travels "
              "in the recovery archive rather than in Git -- which is why RESTORE_REQUIRED "
              "is OPTIONAL. Its .local/ (4.8 GB of Apple SDK and OSXCross) and vendor/ "
              "(197 MB) are third-party toolchain material recorded by version and "
              "checksum, not carried: the first-party build authority is ~23 MB.",
    ),

    Component(
        component_id="symoneural-yocto",
        canonical_name="SyMoNeuRaL Yocto layer",
        cls="framework",
        source_root="yocto",
        language="BitBake",
        build_system="bitbake",
        build_authority="yocto/",
        production_status=EXPERIMENTAL,
        first_party_status=FIRST_PARTY,
        primary_artifact="yocto/",
        restore_required="OPTIONAL",
        test_command="-",
        network_required="YES",
        notes="The first-party meta-symoneural layer. The /yocto PARTITION is a build "
              "area (downloads/, sstate-cache/, tmp/ and upstream layer mirrors) and is "
              "regenerable; only unique first-party layer content belongs here.",
    ),
)


# =========================================================================================
# APPLICATIONS -- the user-facing surfaces, from backend/apps/ROSTER.md
# =========================================================================================
#
# ROSTER.md is the authority for what a row IS, and it is deliberately one of four
# independent copies (the others being api.py's build_status(), controlboard's TOGGLEABLE,
# and test_status_rack.py's EXPECTED) so that a disagreement is detectable. This table is
# not a fifth copy of the roster: it records the RESTORE facts about each row -- which
# component serves it, which engine it needs, what state it owns, how to smoke it -- which
# is information the roster does not carry.

@dataclass(frozen=True)
class Application:
    application_id: str
    display_name: str
    ui_source: str
    route: str
    api_routes: str
    primary_runtime_component: str
    production_status: str
    parent_application_id: str = "-"
    secondary_components: str = "-"
    engine_dependencies: str = "-"
    persistent_state_ids: str = "-"
    auth_requirement: str = "none (public read)"
    restore_smoke_id: str = "-"


APPLICATIONS: tuple[Application, ...] = (
    Application("chat", "SyMoNeuRaL Chat", "site/chat.html", "/chat.html",
                "/api/chat", "symoneural-api", PRODUCTION,
                engine_dependencies="symoneural-llm",
                persistent_state_ids="accounts-db",
                restore_smoke_id="smoke-chat"),
    Application("image", "SyMoNeuRaL Image", "site/image.html", "/image.html",
                "/api/image", "symoneural-api", PRODUCTION,
                engine_dependencies="symoneural-diffuse",
                persistent_state_ids="image-output",
                restore_smoke_id="smoke-image"),
    Application("sigils", "SyMoNeuRaL Sigils", "site/sigils.html", "/sigils.html",
                "/api/sigils/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/sigils",
                engine_dependencies="symoneural-diffuse",
                restore_smoke_id="smoke-sigils"),
    Application("remix", "SyMoNeuRaL Remix", "site/remix.html", "/remix.html",
                "/api/remix/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/remix",
                engine_dependencies="symoneural-diffuse",
                restore_smoke_id="smoke-remix"),
    Application("ravencalc", "SyMoNeuRaL RavenCalc", "site/ravencalc.html",
                "/ravencalc.html", "/api/ravencalc/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/ravencalc",
                restore_smoke_id="smoke-ravencalc"),
    Application("project", "SyMoNeuRaL Project", "site/project.html", "/project.html",
                "/api/project/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/project",
                persistent_state_ids="project-db",
                restore_smoke_id="smoke-project"),
    Application("coder", "SyMoNeuRaL Coder", "site/livestack/coder",
                "/livestack/coder", "/api/coder/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/coder,backend/apps/authority",
                auth_requirement="mutation-authority task grant; config-gated",
                restore_smoke_id="smoke-coder"),
    Application("studio", "SyMoNeuRaL Studio", "backend/apps/studio", "/studio",
                "/api/studio/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/studio,backend/apps/authority",
                engine_dependencies="symoneural-llm",
                auth_requirement="enabled() + token_ok() admission, then task authority",
                restore_smoke_id="smoke-studio"),
    Application("reinforce", "SyMoNeuRaL Reinforce", "site/reinforce.html",
                "/reinforce.html", "/api/train/*", "symoneural-api", PRODUCTION,
                parent_application_id="studio",
                secondary_components="backend/apps/studio/plugins/reinforce",
                engine_dependencies="symoneural-llm",
                persistent_state_ids="training-adapters",
                restore_smoke_id="smoke-reinforce"),
    Application("exp", "SyMoNeuRaL Exp", "site/exp.html", "/exp",
                "/api/exp/*", "symoneural-api", PRODUCTION,
                parent_application_id="studio",
                secondary_components="backend/apps/studio/plugins/exp",
                restore_smoke_id="smoke-exp"),
    Application("live", "SyMoNeuRaL Live", "backend/apps/live", "/livestack/live",
                "/api/live/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/live",
                restore_smoke_id="smoke-live"),
    Application("streamer", "SyMoNeuRaL Streamer", "site/streamer.html",
                "/streamer.html", "/api/streamer/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/streamer",
                restore_smoke_id="smoke-streamer"),
    Application("dispatchos", "SyMoNeuRaL DispatchOS", "backend/apps/dispatchos",
                "/demo/dispatchos", "/api/dispatchos/*", "symoneural-api", PRODUCTION,
                secondary_components="backend/apps/dispatchos",
                restore_smoke_id="smoke-dispatchos"),
    Application("miner", "SyMoNeuRaL Miner", "site/miner.html", "/miner.html",
                "/api/miner/*", "symoneural-api", DISABLED,
                secondary_components="backend/apps/cryptominer,backend/apps/asicminer",
                engine_dependencies="symoneural-miner (GPL, disabled)",
                restore_smoke_id="smoke-miner"),
    Application("gateway", "SyMoNeuRaL Gateway", "site/gateway.html", "/gateway.html",
                "/api/gateway/*", "symoneural-gateway", DISABLED,
                parent_application_id="miner",
                secondary_components="backend/apps/gateway",
                restore_smoke_id="-"),
)


# =========================================================================================
# SERVICES
# =========================================================================================

@dataclass(frozen=True)
class Service:
    service_id: str
    component_id: str
    source_unit: str
    installed_unit: str
    user: str
    group: str
    working_directory: str
    ports: str
    dependencies: str
    enablement: str
    install_command: str
    start_command: str
    healthcheck: str
    env_files: str = "-"
    # The systemd unit to interrogate. Usually the basename of `installed_unit`, but not
    # always: Caddy's tracked artefact is a Caddyfile, which is CONFIGURATION, not a unit.
    # Deriving the unit name from the installed path asked systemd about a unit called
    # "Caddyfile" and got back `not-found` -- a confident measurement of the wrong object,
    # which is worse than no measurement because it looks like one.
    unit_name: str = "-"


SERVICES: tuple[Service, ...] = (
    Service(
        "symoneural-api", "symoneural-api",
        "ops/symoneural-api.service", "/etc/systemd/system/symoneural-api.service",
        "google", "google", "/home/google/Symoneural",
        "127.0.0.1:8800", "network-online.target",
        "enabled",
        "sudo install -m0644 ops/symoneural-api.service /etc/systemd/system/ && "
        "sudo systemctl daemon-reload && sudo systemctl enable symoneural-api",
        "sudo systemctl start symoneural-api",
        "curl -fsS http://127.0.0.1:8800/api/status",
        env_files="run/api.env (0600, NOT in Git -- restored from .private/host-snapshot)",
    ),
    Service(
        "symoneural-web", "symoneural-web",
        "ops/symoneural-web.service", "/etc/systemd/system/symoneural-web.service",
        "google", "google", "/home/google/Symoneural",
        "(behind Caddy on 80/443)", "symoneural-api.service",
        "enabled",
        "sudo install -m0644 ops/symoneural-web.service /etc/systemd/system/ && "
        "sudo systemctl daemon-reload && sudo systemctl enable symoneural-web",
        "sudo systemctl start symoneural-web",
        "curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1/",
    ),
    Service(
        "symoneural-gateway", "symoneural-gateway",
        "ops/symoneural-gateway.service", "/etc/systemd/system/symoneural-gateway.service",
        "google", "google", "/home/google/Symoneural",
        "-", "symoneural-api.service",
        "disabled (deliberate -- no contract, no wallet, no key material)",
        "sudo install -m0644 ops/symoneural-gateway.service /etc/systemd/system/",
        "(do not start -- disabled by design)",
        "-",
    ),
    Service(
        "symoneural-progress", "symoneural-web",
        "ops/symoneural-progress.timer",
        "~/.config/systemd/user/symoneural-progress.timer",
        "google", "google", "/home/google/Symoneural",
        "-", "-",
        "enabled (user timer)",
        "install -m0644 ops/symoneural-progress.{service,timer} "
        "~/.config/systemd/user/ && systemctl --user daemon-reload && "
        "systemctl --user enable --now symoneural-progress.timer",
        "systemctl --user start symoneural-progress.timer",
        "test -f run/progress.html",
    ),
    Service(
        "caddy", "symoneural-web",
        "ops/Caddyfile", "/etc/caddy/Caddyfile",
        "caddy", "caddy", "/var/lib/caddy",
        "80, 443", "-",
        # DISABLED, and measured so on 2026-09-08. The stock caddy.service was the
        # production owner of :80/:443 until the 2026-08-26 cutover; symoneural-web owns
        # them now and its unit declares Conflicts= so systemd refuses to run both. The
        # Caddyfile is still the live configuration -- symoneural-web reads it -- which is
        # why the config is tracked and installed while the vendor unit stays off.
        "disabled (superseded by symoneural-web at the 2026-08-26 cutover)",
        "sudo install -m0644 ops/Caddyfile /etc/caddy/Caddyfile && "
        "sudo systemctl reload caddy",
        "sudo systemctl start caddy",
        "curl -fsS -o /dev/null -w '%{http_code}' https://symoneural.com/",
        unit_name="caddy.service",
        env_files="Let's Encrypt production state in /var/lib/caddy/.local/share/caddy/ "
                  "-- COPY and chown, NEVER move: a live certificate valid to 2026-11-15.",
    ),
)


# =========================================================================================
# PERSISTENT STATE -- what Git cannot restore
# =========================================================================================

@dataclass(frozen=True)
class StateStore:
    state_id: str
    application: str
    component: str
    live_path: str
    type_: str
    contains_secrets: str
    consistency_method: str
    restore_destination: str
    restore_command: str
    validation_command: str
    required_for_restore: str
    # How this store reaches the recovery archive.
    #
    #   CONSISTENT_COPY   the bytes on disk may be TORN, so a transformed copy is taken
    #                     into .private/. Every live SQLite database is in this class: a
    #                     writer can be mid-transaction, and the in-tree file would restore
    #                     corrupt while passing every checksum.
    #   FILE_COPY         small, private, and cheap to duplicate; a second verified copy
    #                     costs nothing and removes a dependency on tree order.
    #   CARRIED_IN_ARCHIVE  already inside the repository tree the final tar preserves, and
    #                     safe to copy as-is. Duplicating it into .private/ would put the
    #                     same 17 GB in the same archive twice. It still gets a row, a
    #                     classification and a restore recipe -- what it does not get is a
    #                     redundant copy.
    backup_policy: str = "FILE_COPY"


STATE_STORES: tuple[StateStore, ...] = (
    # Every path here was measured on 2026-09-08, not recalled. An earlier draft of this
    # table named `run/accounts.db` and `run/api.env`; neither exists. The real stores are
    # one directory deeper, and two of them had a live writer attached at the time of
    # measurement -- which is the entire reason the consistency method matters.
    StateStore(
        "accounts-db", "chat", "symoneural-api",
        "run/accounts/accounts.db", "sqlite",
        "YES (session material)",
        # `.backup` takes SQLite's own read lock and produces a consistent image. A plain
        # `cp` of a database mid-transaction passes a checksum and restores corrupt, which
        # is the failure mode a backup is least able to detect.
        "sqlite3 .backup",
        "run/accounts/accounts.db",
        "install -D -m0600 <backup> run/accounts/accounts.db",
        "sqlite3 run/accounts/accounts.db 'PRAGMA integrity_check;'",
        "YES",
        backup_policy="CONSISTENT_COPY",
    ),
    StateStore(
        "dispatchos-db", "dispatchos", "symoneural-api",
        "run/dispatchos.db", "sqlite (WAL -- a writer was attached when measured)",
        "NO", "sqlite3 .backup",
        "run/dispatchos.db",
        "install -D -m0600 <backup> run/dispatchos.db",
        "sqlite3 run/dispatchos.db 'PRAGMA integrity_check;'",
        "YES",
        backup_policy="CONSISTENT_COPY",
    ),
    StateStore(
        "project-db", "project", "symoneural-api",
        "run/project/store.db", "sqlite (WAL -- a writer was attached when measured)",
        "NO", "sqlite3 .backup",
        "run/project/store.db",
        "install -D -m0600 <backup> run/project/store.db",
        "sqlite3 run/project/store.db 'PRAGMA integrity_check;'",
        "YES",
        backup_policy="CONSISTENT_COPY",
    ),
    StateStore(
        "discovery-index", "coder", "symoneural-discovery",
        "run/symoneural-discovery.sqlite3", "sqlite",
        "NO", "sqlite3 .backup",
        "run/symoneural-discovery.sqlite3",
        "install -m0600 <backup> run/symoneural-discovery.sqlite3",
        "sqlite3 run/symoneural-discovery.sqlite3 'PRAGMA integrity_check;'",
        "NO (a code index; regenerable by re-running discovery, but slow)",
        backup_policy="CONSISTENT_COPY",
    ),
    StateStore(
        "api-env", "all", "symoneural-api",
        "run/config/api.env", "env file",
        "YES", "cp -p (mode 0600 preserved)",
        "run/config/api.env",
        "install -D -m0600 <backup> run/config/api.env",
        "test -f run/config/api.env && test \"$(stat -c%a run/config/api.env)\" = 600",
        "YES",
    ),
    StateStore(
        "authority-state", "coder", "symoneural-api",
        "run/authority", "directory + fsynced pre-mutation journal",
        "NO", "rsync -a",
        "run/authority",
        "rsync -a <backup>/ run/authority/",
        "test -d run/authority",
        "NO (rebuilt on first use; a stale lease is reconciled loudly, not inherited)",
        backup_policy="CARRIED_IN_ARCHIVE",
    ),
    StateStore(
        "ledgers", "all", "symoneural-api",
        "GARRETT-REQUESTS.md,INTAKE.md", "mode-600 owner ledgers, untracked by design",
        "NO (owner-private, not secret)", "cp -p (mode 0600 preserved)",
        "repository root",
        "install -m0600 <backup>/<file> ./<file>",
        "test \"$(stat -c%a GARRETT-REQUESTS.md)\" = 600",
        "YES",
    ),
    StateStore(
        "training-adapters", "reinforce", "symoneural-api",
        "training/adapter", "model weights (LoRA)",
        "NO", "rsync -a",
        "training/adapter",
        "rsync -a <backup>/ training/adapter/",
        "test -d training/adapter && ls training/adapter",
        "YES (protected artefact -- docs/ops/EXPORTS.md names it by path)",
        backup_policy="CARRIED_IN_ARCHIVE",
    ),
    StateStore(
        "training-corpus", "reinforce", "symoneural-api",
        "training/corpus.jsonl", "dataset",
        "NO", "cp -p",
        "training/corpus.jsonl",
        "install -m0600 <backup> training/corpus.jsonl",
        "wc -l training/corpus.jsonl",
        "YES (protected artefact)",
        backup_policy="CARRIED_IN_ARCHIVE",
    ),
    StateStore(
        "models", "chat,image", "symoneural-api",
        "backend/models", "model weights, 17 GB",
        "NO", "classified per file -- see restore/manifests/MODELS.tsv",
        "backend/models",
        "restore/symoneural-restore restore-state --apply  # reacquires downloadables",
        "ls backend/models",
        "PARTIAL -- downloadable weights are reacquired from their provider, not carried",
        backup_policy="CARRIED_IN_ARCHIVE",
    ),
    StateStore(
        "image-output", "image", "symoneural-api",
        "backend/output", "user-generated content, 363 MB",
        "NO", "rsync -a",
        "backend/output",
        "rsync -a <backup>/ backend/output/",
        "test -d backend/output",
        "NO (regenerable by the user, but it is their work, so it travels)",
        backup_policy="CARRIED_IN_ARCHIVE",
    ),
)

# =========================================================================================
# SMOKES -- a restore is not proven by a --version
# =========================================================================================
#
# The repository's own rule, from the authority doc: "If the deliverable is a program that
# runs, one check must be something only a real run can turn green." #94 shipped a desktop
# client whose eighteen checks were green and whose chat surface was dead on arrival. So
# every production row here exercises the real path, and the ones that cannot are marked
# rather than faked.

@dataclass(frozen=True)
class Smoke:
    smoke_id: str
    application_id: str
    prerequisites: str
    command: str
    expected_result: str
    network_scope: str
    mutating: str
    safe_after_fresh_restore: str


SMOKES: tuple[Smoke, ...] = (
    # EVERY route and body below was validated against the LIVE API on 2026-09-08 by
    # reading /openapi.json and issuing the request. That check found SIX of the first
    # draft's thirteen smokes naming routes this API has never served --
    # /api/ravencalc/estimate, /api/coder/status, /api/studio/status, /api/exp/status,
    # /api/live/status, /api/streamer/status -- all invented from the roster's route
    # pattern rather than measured. On a restored machine each would have failed and been
    # indistinguishable from a broken restore, which is the worst possible failure mode
    # for a restore smoke: it accuses the backup.
    #
    # The window for that check closes when this disk is erased, so it was taken while the
    # API was still up, and `apps/test_restore_manifests.py` now re-checks every HTTP
    # smoke against a captured route list.
    #
    # EXPECTED_RESULT carries the measured status code. A 401 or a 503 is a PASS where the
    # surface is auth-gated or disabled by configuration -- it proves the route exists and
    # the gate works, which is exactly what a restore needs to know. Treating only 200 as
    # success would report a correctly-disabled component as a broken one.

    Smoke("smoke-chat", "chat", "symoneural-api running; symoneural-llm built",
          "curl -fsS -m 180 -X POST http://127.0.0.1:8800/api/chat "
          "-H 'Content-Type: application/json' "
          "-d '{\"prompt\":\"reply with the single word ok\"}'",
          "HTTP 200 and a non-empty completion generated by the local model. Body field "
          "is `prompt` (measured, not assumed).", "loopback", "NO", "YES"),

    Smoke("smoke-image", "image", "symoneural-api running; symoneural-diffuse built",
          "curl -fsS -m 600 -X POST http://127.0.0.1:8800/api/image "
          "-H 'Content-Type: application/json' "
          "-d '{\"prompt\":\"a plain grey square\",\"width\":512,\"height\":512}'",
          "HTTP 200 and a url resolving to a PNG on disk", "loopback",
          "YES (writes one PNG under backend/output)", "YES"),

    Smoke("smoke-sigils", "sigils", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/sigils/state",
          "HTTP 200, schema sigil/state/v1, installed=true. The mutating render path is "
          "/api/sigils/render with a `prompt` body; state is used here so the smoke is "
          "safe to run repeatedly on a fresh restore.", "loopback", "NO", "YES"),

    Smoke("smoke-remix", "remix", "symoneural-api running",
          "curl -sS -m 30 -o /dev/null -w '%{http_code}' -X POST "
          "http://127.0.0.1:8800/api/remix -H 'Content-Type: application/json' -d '{}'",
          "HTTP 422 naming the missing `prompt` field -- the route exists and validates. "
          "A full remix needs a prompt and GPU time; this proves the surface is wired "
          "without spending either.", "loopback", "NO", "YES"),

    Smoke("smoke-ravencalc", "ravencalc", "symoneural-api running",
          "curl -fsS -m 30 -X POST http://127.0.0.1:8800/api/ravencalc "
          "-H 'Content-Type: application/json' -d '{\"expression\":\"2+2\"}'",
          "HTTP 200, result.text=\"4\", exact=true and check.passed=true -- a real "
          "symbolic computation verified by the engine subtracting the simplified form "
          "from the original, not a status ping.", "loopback", "NO", "YES"),

    Smoke("smoke-project", "project", "symoneural-api running; project-db restored",
          "curl -sS -m 30 -o /dev/null -w '%{http_code}' "
          "http://127.0.0.1:8800/api/project/state",
          "HTTP 401 unauthenticated. That is the PASS: the route exists and the account "
          "gate is enforcing. A 200 here without a session would be the defect.",
          "loopback", "NO", "YES"),

    Smoke("smoke-coder", "coder", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/local/coder/status",
          "HTTP 200, ok=true, allow_remote=false, and a populated denied_segments list. "
          "Coder serves NO /api route by design -- its endpoints are /local/* behind a "
          "peer-address check, because ops/Caddyfile proxies /api/* to the public "
          "internet.", "loopback only -- refused off-box", "NO", "YES"),

    Smoke("smoke-studio", "studio", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/studio/state",
          "HTTP 200 with enabled and workspace.root, and workspace.found_by=\"walk\" -- "
          "which also confirms the marker-walk root resolution rather than parent counting",
          "loopback", "NO", "YES"),

    Smoke("smoke-reinforce", "reinforce", "symoneural-api running",
          "curl -sS -m 30 -o /dev/null -w '%{http_code}' "
          "http://127.0.0.1:8800/api/train/status",
          "HTTP 503 while SYMONEURAL_REINFORCE_ENABLED is unset -- the measured, correct "
          "answer for a surface that is off by default. 200 after enabling it.",
          "loopback", "NO", "YES"),

    Smoke("smoke-exp", "exp", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/exp/state",
          "HTTP 200. Note the route is /api/exp/state; /api/exp/status does not exist.",
          "loopback", "NO", "YES"),

    Smoke("smoke-live", "live", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/live/state",
          "HTTP 200. NVENC cost is unmeasured and apps/live/README.md says so.",
          "loopback", "NO", "YES"),

    Smoke("smoke-streamer", "streamer", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/streamer/state",
          "HTTP 200", "loopback", "NO", "YES"),

    Smoke("smoke-dispatchos", "dispatchos", "symoneural-api running",
          "curl -fsS -m 30 http://127.0.0.1:8800/api/dispatchos/status",
          "HTTP 200", "loopback", "NO", "YES"),

    Smoke("smoke-miner", "miner", "none -- the miner is DISABLED",
          "python3 symoneural-miner-core/bin/symoneural-miner-smoke --no-write",
          "13/13 checks against the LOOPBACK fixture: fail-closed config refuses to arm, "
          "a validated loopback endpoint arms, Stratum handshake and job receipt work "
          "against a real socket, a deterministic candidate is derived by first-party "
          "Keccak, the pool accepts the frame, the socket is released. NO public pool, NO "
          "real wallet, NO share submitted to any network, NO hashrate claimed. The HTTP "
          "surface /api/gpuminer/status returns 503 (disabled on this installation).",
          "loopback fixture only", "NO", "YES"),
)

# =========================================================================================
# RESTORE ORDER
# =========================================================================================

@dataclass(frozen=True)
class Step:
    order: int
    step_id: str
    action: str
    requires: str
    command: str
    verify_command: str
    mutates_system: str
    requires_root: str
    failure_policy: str


RESTORE_ORDER: tuple[Step, ...] = (
    Step(10, "host-prereqs", "Install host packages and toolchain", "-",
         "restore/symoneural-restore dependencies --instructions",
         "restore/symoneural-restore dependencies --check",
         "YES", "YES", "STOP -- nothing below can succeed"),
    Step(20, "git-repo", "Restore the repository from the bundle",
         "host-prereqs",
         "git clone .private/git-backup/Symoneural-all.bundle Symoneural",
         "git -C Symoneural fsck --full && git -C Symoneural rev-parse HEAD",
         "NO", "NO", "STOP"),
    Step(30, "private-state", "Restore private recovery state", "git-repo",
         "restore/symoneural-restore restore-state --apply",
         "restore/symoneural-restore restore-state --dry-run",
         "YES", "NO", "STOP"),
    Step(40, "upstreams", "Reacquire the pinned engine upstreams", "git-repo",
         "tools/restore-upstream.sh all",
         "tools/restore-upstream.sh --check",
         "NO", "NO", "CONTINUE -- record which engines cannot be built"),
    Step(50, "build-native", "Build the native engines", "upstreams",
         "restore/symoneural-restore build all",
         "restore/symoneural-restore verify",
         "NO", "NO", "CONTINUE -- a failed engine disables its applications, not the rack"),
    Step(60, "test", "Run the test suites", "build-native",
         "restore/symoneural-restore test all",
         "cd backend && python3 -m pytest -q",
         "NO", "NO", "STOP on a failure in the backend suite"),
    Step(70, "install-cli", "Install the CLI entry points", "test",
         "scripts/install-cli.sh",
         "command -v symoneural-cli symoneural-code symoneural-api",
         "YES", "NO", "CONTINUE"),
    Step(80, "services", "Install the systemd units", "install-cli",
         "restore/symoneural-restore services --install",
         "restore/symoneural-restore services --check",
         "YES", "YES", "STOP"),
    Step(90, "caddy", "Install the Caddy configuration and certificates", "services",
         "sudo install -m0644 ops/Caddyfile /etc/caddy/Caddyfile && "
         "sudo systemctl reload caddy",
         "curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1/",
         "YES", "YES",
         "STOP. Certificate state is COPIED and chowned into /var/lib/caddy, never moved."),
    Step(100, "start", "Start the services in dependency order", "caddy",
         "sudo systemctl start symoneural-api && sudo systemctl start symoneural-web",
         "curl -fsS http://127.0.0.1:8800/api/status",
         "YES", "YES", "STOP"),
    Step(110, "smoke", "Run every application smoke", "start",
         "restore/symoneural-restore smoke all",
         "restore/symoneural-restore status",
         "YES (image writes one PNG)", "NO", "REPORT -- do not roll back automatically"),
    Step(120, "accept", "Compare the restored release against RELEASE.json", "smoke",
         "restore/symoneural-restore verify --release",
         "restore/symoneural-restore status",
         "NO", "NO", "REPORT"),
)


def component_ids() -> set[str]:
    return {c.component_id for c in COMPONENTS}


def by_id(cid: str) -> Component:
    for c in COMPONENTS:
        if c.component_id == cid:
            return c
    raise KeyError(cid)
