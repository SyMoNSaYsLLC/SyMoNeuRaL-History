#!/usr/bin/env python3
"""Build the SyMoNeuRaL *project history* corpus -- the second corpus, not the first.

INTERNAL. Trade secret. See README.md beside this file. Never copy this file or its
output into site/, never serve it from an endpoint, never quote its contents into a
commit message or a page.

WHAT THIS IS
------------
`training/corpus.jsonl` and `training/build_dataset.py` teach the model the company
*voice*. This file teaches it the *project*: what the architecture is, which approaches
were tried and failed, and what the house rules are. The two are independent by
construction -- nothing here was read from, copied from or derived from either of those
files, and this generator never opens them.

SOURCES, in descending order of value. Every answer below is grounded in one of them:

  1. `git log` with full bodies (85 commits at 595835d). CLAUDE.md: "every commit states
     its reason", which is a decision plus its justification -- the shape of a training
     example already.
  2. `.claude/HANDOVER.md`  -- state, what is left, what will bite you.
  3. `.claude/CLAUDE.md`    -- the working agreements.
  4. `docs/specs/*.md`      -- proposals and audits, explicitly NOT state.
  5. `docs/` and the module docstrings under `backend/apps/` (read, never edited).

METHOD
------
Hand-authored. Every row was written by reading the source above and stating the fact in
the answering voice, rather than by templating a commit message into a question. A
mechanical `"Why did you do X?" -> <commit body>` transform was rejected: commit bodies
are written in report voice, and training on them teaches the model to answer questions
with changelog prose.

THE RULE THAT DECIDES EVERY NUMERIC ANSWER
------------------------------------------
CLAUDE.md: label every figure **measured** on this machine, **vendor** specification, or
**projected** arithmetic. Two further labels are used here where neither fits: **published
spec** (a figure from a paper or an upstream document -- the QLoRA 4.127 bits/param) and
**derived** (arithmetic corroborated against an artifact on disk -- the 0.53% trainable
fraction, confirmed by the adapter's own file size). If an example teaches a number, the
answer carries the label. An unlabelled number in this corpus would train the model to
state projections as results, which is an attack on the argument the whole site rests on.

`assert_labelled()` at the bottom enforces this mechanically: any answer containing a
figure must also carry a provenance word. It fails the build rather than warning.

    ./build_history_corpus.py                 # -> history-corpus.jsonl
    ./build_history_corpus.py --stats         # counts per bucket, no write
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
# This exact calculation has been wrong four times in this repo's history and it fails
# silently -- the parent of the repo exists, so a wrong root yields empty directories
# rather than an error. Assert it, as the generators and scripts now do.
assert (ROOT / "backend" / "api.py").is_file(), f"repo root miscomputed: {ROOT}"

OUT = HERE / "history-corpus.jsonl"

# Rows are (kind, user, assistant). The schema written out is
# {"messages": [{"role": "user", ...}, {"role": "assistant", ...}], "kind": ...},
# which is what training/train_lora.py's encode() already expects, so whoever implements
# docs/specs/qlora-upgrade.md can point --corpus at this file unchanged.
#
# No system turn. /api/chat restricts a turn's role to Literal["user","assistant"] so a
# client cannot inject one, the persona lives in the adapter rather than in a prompt, and
# authoring a system message here would mean guessing at the shape of a corpus this file
# is forbidden to read.
R: list[tuple[str, str, str]] = []


def q(kind: str, user: str, assistant: str) -> None:
    R.append((kind, user.strip(), assistant.strip()))


# ---------------------------------------------------------------------------
# 1. ARCHITECTURE AND ROUTING
# ---------------------------------------------------------------------------

q("architecture",
  "How is symoneural.com served?",
  "Caddy terminates TLS and hands back static files from /var/www/symoneural. FastAPI, "
  "running under uvicorn on 127.0.0.1:8800, does the routing for everything else. That "
  "split is the owner's stated rule and ops/Caddyfile enforces it -- no rewrites, no "
  "aliases, no conditional logic in the web server config.")

q("architecture",
  "Why Caddy instead of Apache?",
  "Two reasons, and the second one was a live problem. Caddy provisions and renews TLS "
  "automatically, which removes certbot from the picture. And it upgrades WebSockets with "
  "no directive at all: mod_proxy_wstunnel was never enabled under Apache, so /api/ws "
  "could not upgrade and console.js had been silently falling back to polling /api/status "
  "while the rack claimed it was pushed live over one socket. Apache is disabled and its "
  "vhost was deleted rather than left beside the Caddyfile.")

q("architecture",
  "CLAUDE.md says FastAPI does all the routing. Does that mean every URL reaches FastAPI?",
  "No, and this is the gap that shipped four pages 404ing. That sentence is true of what a "
  "URL *returns* and false about which URLs *arrive*. ops/Caddyfile serves everything from "
  "disk except the paths it explicitly delegates: /api/*, /docs*, /openapi.json, /, "
  "/overview, /livestack, /controlboard and /receipts. Anything not on that list never "
  "reaches FastAPI at all.")

q("architecture",
  "The /overview route exists in backend/api.py and returns 200 locally, but 404s in production. Why?",
  "Caddy is answering it from the webroot before FastAPI is ever consulted. A route only "
  "reaches the API if ops/Caddyfile delegates its path. Add it to the named matcher there "
  "and run sudo ./scripts/install-caddy.sh -- deploy.sh does not touch Caddy. A local test "
  "run cannot catch this: against 127.0.0.1:8800 the API answers directly and the Caddyfile "
  "is never exercised, which is how the suite passed 25/25 while all four section URLs were "
  "dead in production.")

q("architecture",
  "What does it take to add a fifth section page to the front page?",
  "Four files, and missing any one of them fails differently. tools/build_split.py to "
  "generate it, backend/api.py for the route, ops/Caddyfile to delegate the path so the "
  "route is reachable at all, and is_route() in scripts/deploy.sh -- otherwise the deploy "
  "reports MISSING, because pages link /livestack while the file is livestack.html.")

q("architecture",
  "Where does api.py mount the static site?",
  "At / and deliberately last, so the StaticFiles mount never shadows an API route. A route "
  "declared after a mount at / is unreachable. Mounting the site at all is what lets the "
  "whole thing be exercised from one origin, which is the only way the real frontend works: "
  "console.js opens a WebSocket and falls back to polling, and neither survives a split "
  "origin.")

q("architecture",
  "Where do generated images go?",
  "backend/output/, served by GET /api/gen/<name>. They used to be written into site/ and "
  "handed back as a webroot path, which meant every image generated on the live site 404'd "
  "until somebody deployed -- the API writes into the staging site/ while the web server "
  "serves /var/www/symoneural. Anything the API generates is served by the API.")

q("architecture",
  "The render filename comes from the client. Is that a path traversal risk?",
  "It is attacker-controlled and it lands in a filesystem path, so it is matched against "
  "the exact shape the generator emits rather than sanitised. Traversal and bogus names "
  "both 404.")

q("architecture",
  "How does the live rack get its readings?",
  "console.js opens a WebSocket at /api/ws and falls back to polling /api/status. It "
  "connects when it finds #units or #m-vram on the page, then writes into m-vram, m-pwr, "
  "m-temp, m-holder, m-queue and con-link. Carrying those ids is the whole integration -- "
  "there is no second data path, and its txt()/meter() helpers no-op on ids that are absent.")

q("architecture",
  "I want GPU statistics on a new surface page. What do I write?",
  "Nothing new. Pass gpu=True and surface=\"Name\" to page() in tools/build_pages.py and the "
  "panel appears, carrying the ids console.js already writes. Do not write a fresh poller: "
  "a second data path is how two readings of one card start disagreeing. Use gpu=False for a "
  "surface that does not wait for the card -- it still shows the card, because it is shared "
  "and worth seeing, but says outright that the page does not queue behind it.")

q("architecture",
  "How many units are on the rack and what are they?",
  "Eight: chat, image, remix, ravencalc, train, asicminer, tuner and gateway. The rack copy "
  "deliberately no longer states a count -- it said \"Five surfaces\" once and went stale "
  "with the next unit.")

q("architecture",
  "What is Unit.bus and why does it matter?",
  "It names the hardware a surface actually contends for: gpu, cpu, asic or net. It matters "
  "because console.js used to render u.bus === 'cpu' ? 'CPU' : 'GPU', which was correct "
  "while there were two buses and silently wrong at three -- an ASIC surface would have "
  "printed \"GPU\" on the one plate the page asks you to trust to name the hardware. It is a "
  "lookup now and prints -- for anything unrecognised.")

q("architecture",
  "Does the tuner contend for the GPU?",
  "No. Its bus is net: the work is network I/O and ffmpeg stream-copy muxing, so it never "
  "takes the governor lease. RavenCalc is the same shape on the other side -- bus cpu, SymPy, "
  "and deliberately never on the lock.")

q("architecture",
  "How does the tuner avoid handing a visitor-supplied URL to ffmpeg?",
  "ffmpeg is never given the URL. Python opens the upstream socket through a validated, "
  "IP-pinned client and pipes bytes into `ffmpeg -i pipe:0` with -protocol_whitelist "
  "pipe,fd. Handing over the URL would have voided the SSRF control entirely, because ffmpeg "
  "does its own DNS and its own redirects in another process, and it also keeps the "
  "visitor's credentials out of argv.")

q("architecture",
  "How does the tuner's SSRF guard actually work?",
  "validate_url resolves the hostname once, requires every returned address to be globally "
  "routable, and then returns the approved address as the only thing ever connected to. "
  "There is no second lookup, so a rebinding attacker's second answer has nothing to win.")

q("architecture",
  "Where do the IPTV credentials a visitor types get stored?",
  "In their own browser's localStorage, travelling per request. They are scrubbed from every "
  "error path and never written to disk on this box. The owner chose that explicitly.")

q("architecture",
  "How does chat remember a conversation?",
  "It does not, on the server. Conversations live in the browser: there is no history "
  "endpoint and no conversation id. The transcript is replayed to /api/chat each turn, "
  "capped at 19 client-side to match the server's 20, so a long chat is trimmed here rather "
  "than refused there. That is the same promise the rest of the site makes about your data.")

q("architecture",
  "Why is /api/chat's history role a Literal[\"user\",\"assistant\"]?",
  "So a client cannot slip in a system turn and override the trained persona and its "
  "refusals. That restriction is deliberate, not incidental.")

q("architecture",
  "Can I attach an image to a chat message?",
  "No, and it is a hardware fact rather than a product decision. The chat model is "
  "Qwen2.5-7B-Instruct and it has no vision projector -- verified, there is no mmproj in "
  "backend/models/. An image picker would be a control that can never work. A VLM would have "
  "to be downloaded, and chat and image weights already cannot co-reside on this card. "
  "Attach is text-only, read in the browser and prepended to the prompt; there is no upload "
  "endpoint and none is needed.")

q("architecture",
  "Why is the chat rail a div with role=navigation rather than a <nav>?",
  "Because the sitewide rule `nav a:not(.cta){display:none}` hides nav links below 820px, "
  "and inside a <nav> that would have deleted every conversation link on a phone.")

q("architecture",
  "What is backend/apps/reinforce/?",
  "The native CUDA engine -- 35 Python files whose kernels are C++ source strings compiled "
  "through NVRTC at runtime. There is no .cu file and no CMakeLists; the CMake you may be "
  "thinking of belongs to contrib/cuda-samples/. It is not referenced by the API, the CLI, "
  "the generators or the site, and it stands alone.")

q("architecture",
  "Is reinforce the QLoRA?",
  "No. The name invites exactly that assumption and it is wrong. Reinforce is the CUDA "
  "engine. The fine-tune lives in training/.")

q("architecture",
  "What is the plan for splitting backend/api.py?",
  "Split by concern, not into a main -> server -> api chain. api.py is about 1,573 lines and "
  "the mass is not where you would guess: roughly 1,060 lines of GPU and engine lifecycle, "
  "186 of rate limiting, 92 of schemas, 91 of routes, 87 of websocket. A thin three-file "
  "chain would produce the same monolith. The target shape is main.py, app.py, engines/, "
  "gpu.py, routes/, limits.py, schemas.py, live.py -- which is what llama.cpp does, its own "
  "main.cpp being five lines.")

q("architecture",
  "Why is backend/engines/ the valuable part of that split?",
  "Because LLAMA_SERVER and SD_CLI are hardcoded paths today, so supporting vLLM means "
  "editing the API. A customer with an A100 wants vLLM's throughput; a customer with a "
  "consumer card wants llama.cpp. The rack, the governor and the routes should not know "
  "which is running.")

q("architecture",
  "What is the Backstage plugin model doing in this project's plans?",
  "It is the composition model for the backend, and the owner required it. A plugin is an id "
  "plus a register hook whose init receives its dependencies rather than importing them. "
  "Three consequences each solve a problem already open here: every surface becomes a peer "
  "by construction, injected services give the engine abstraction for free, and the rack "
  "becomes a registry -- a surface appears on it because it registered, instead of being a "
  "hardcoded Unit list in api.py. Take the boundary, not the ceremony; extension points and "
  "a DI container pay off across many teams and this is one box.")

q("architecture",
  "Why do remix and reinforce get directories under backend/apps when chat and image do not?",
  "History, not design, and it should not be defended as design. remix and reinforce arrived "
  "as standalone projects and were imported; chat and image were written inside api.py and "
  "exist only as route handlers, so there is nothing to move until api.py is split. "
  "RavenCalc was the piece that could be fixed immediately -- its only dependency is sympy, "
  "so it moved to backend/apps/ravencalc/ with no extraction work.")

q("architecture",
  "How are the ASIC routes protected?",
  "SYMONEURAL_ASIC_ENABLED=1 and SYMONEURAL_ASIC_TOKEN must both be set or the surface 503s, so a "
  "misconfiguration fails closed on a box with a public IP. The token arrives in X-Symoneural-Token "
  "and is compared in constant time. It lives in the browser's sessionStorage rather than "
  "localStorage, because it authorises scanning and starting processes and should not "
  "outlive the tab; a 401 clears it so a wrong token is not cached.")

q("architecture",
  "Why does the rig scanner refuse public address ranges?",
  "Because this box has a public IP, and a scanner that accepts an arbitrary CIDR is one that "
  "somebody with the token -- or an SSRF into it -- can aim at the internet from our address. "
  "Only RFC1918, CGNAT, link-local and loopback are accepted, the check is on the parsed "
  "network rather than the string so alternate spellings cannot slip past, and prefixes wider "
  "than /20 are refused even when private. The refusal lives in scan.py rather than in the "
  "API wrapper, so the CLI and the route cannot drift into one being safe and the other not.")

q("architecture",
  "How does the emulator decide what to boot?",
  "By package id, resolved only against files already enumerated from the two known "
  "directories. It never takes a caller-supplied path -- an endpoint that execs against an "
  "arbitrary path is a remote file read at best. One instance at a time, the pid recorded in "
  "run/, stale pidfiles detected with signal 0 rather than assumed live, and stop signals the "
  "process group, because the script execs qemu and killing only the pid can orphan it.")

q("architecture",
  "Why does /api/status not probe the rigs inline?",
  "Because /api/status is polled and drives the websocket. A background task refreshes a "
  "cache every 20 seconds and every reading carries age_s, since \"real but N seconds old\" "
  "is a different claim from \"real right now\". The task is not started at all when the "
  "surface is disabled.")

q("architecture",
  "Why is pyasic pinned to 0.75.0?",
  "0.78+ and 0.79.0 ship without their generated protobuf stubs and raise ModuleNotFoundError "
  "on pyasic.web.braiins_os.proto.braiins at import -- from PyPI and from the local reference "
  "copy alike. It lives in backend/apps/asicminer/.venv and is reached by subprocess, because "
  "the serving interpreter carries fastapi, uvicorn, pydantic and sympy and nothing else. "
  "probe.py --selftest checks the venv with no network, so a silent upgrade surfaces as a "
  "broken venv rather than as every rig appearing unreachable.")

# ---------------------------------------------------------------------------
# 2. THE GPU GOVERNOR AND VRAM ECONOMICS
# ---------------------------------------------------------------------------

q("governor",
  "What GPU does this machine have?",
  "One RTX 5070 Ti, Blackwell, compute capability sm_120, 15.92 GiB usable with about 946 "
  "MiB used at idle. Measured on this machine.")

q("governor",
  "How much VRAM should I budget against?",
  "About 14.2 GiB free in practice, measured -- not the 15.92 GiB nameplate. Budgeting "
  "against nameplate is how you OOM at step 0.")

q("governor",
  "Why does a GPU governor exist at all?",
  "Because one card cannot hold two tenants. Chat is about 5 GB resident, image about 7 GB "
  "and a QLoRA run about 12 GB, all measured, so the weight sets do not co-fit in 15.92 GiB. "
  "The governor serialises them. That constraint is not a limitation around the "
  "architecture; it is the architecture.")

q("governor",
  "What is the GPU lock, mechanically?",
  "A mkdir lock: the directory run/gpu.lock.d. mkdir is atomic, so the first process to "
  "create it wins and everyone else spins until it is removed. That directory is the mutex -- "
  "there is nothing else.")

q("governor",
  "How should I run something that touches the card?",
  "Through scripts/gpu-governor.sh, ideally as `gpu-governor.sh with <surface> -- <cmd>`, "
  "which always releases even on a crash.")

q("governor",
  "How long should I hold the GPU lock?",
  "For a job, never for a process lifetime. Residency -- weights loaded -- and work -- using "
  "the card -- are separate things. Holding the lock while a model is merely resident and "
  "idle locks every other process out, including the CLI, until the acquire timeout.")

q("governor",
  "Is it ever OK to call `gpu-governor.sh release` with no arguments?",
  "No. Always name the surface, as in `release chat`. An unscoped release once destroyed a "
  "running fine-tune's lock from the API's shutdown hook. That is why "
  "ops/symoneural-api.service names the two surfaces the API owns rather than releasing "
  "bare.")

q("governor",
  "Why does the governor wait between tenants?",
  "It waits for VRAM to drain below a 1.5 GB floor. Killing a process returns the lock before "
  "CUDA has torn down, and the next tenant then OOMs at step 0.")

q("governor",
  "Can a page view evict a training run?",
  "No. `train` is never evicted to serve a page view. The governor prints \"REFUSING to evict "
  "a training run -- wait for it or stop it deliberately\" and the run keeps the card. That "
  "branch is the exact opposite of the miner branch, which yields to everything.")

q("governor",
  "Why does RavenCalc never take the GPU lock?",
  "It is SymPy on the CPU, so it has no reason to. Staying off the lock is what lets it "
  "speculatively pre-compute while the GPU is still loading something else.")

q("governor",
  "What happens if I run the API in a container without bind-mounting run/?",
  "The container creates its own /app/run/gpu.lock.d, which is a different directory from the "
  "host's. The host CLI mkdirs the host lock and succeeds; the container mkdirs its own and "
  "also succeeds. Both believe they own the card, both load weights, and about 12 GB of "
  "models hit a 16 GB card. The result is not a deadlock -- a deadlock would be safe, because "
  "everything would stop and you would notice. It is a silent OOM at step 0 dressed up as a "
  "CUDA fault. Fix it with -v <root>/run:/app/run, and prove it by inode rather than by "
  "assertion.")

q("governor",
  "How was the shared container lock verified?",
  "By inode. /app/run inside the container and run/ on the host both reported inode 17969339 "
  "-- one directory, not a copy. Measured. Chat streamed at 98.5 tok/s from inside that "
  "container with adapter: true, also measured.")

q("governor",
  "Why is the runtime directory called run/ and not logs/?",
  "Because it holds gpu.lock.d, the GPU mutex, alongside api.pid and the resident marker. "
  "/run and /var/run are the Unix convention for pidfiles, locks and sockets, and the name is "
  "load-bearing: call it logs/ and sooner or later somebody logrotates it or clears it out, "
  "which deletes the lock directory while a surface is holding the card. The logs happen to "
  "live there; the lock is the point.")

q("governor",
  "How fast is chat on this box?",
  "80 to 92 tok/s on Qwen2.5-7B-Instruct at Q4_K_M with the persona adapter loaded, measured "
  "on this card. Individual measured runs include 80.4, 92.8 and 98.5 tok/s -- the last from "
  "inside the rootless container.")

q("governor",
  "How long does an image render take?",
  "About 11.2 seconds for a 768x768 at 4 steps on FLUX.1-schnell q4_k, measured on this card. "
  "The weights are about 7 GB resident.")

q("governor",
  "What is the PCIe situation on this host?",
  "PCIe Gen 3 x8, host-capped, at roughly 7 GB/s host-to-device -- measured, and published on "
  "the site as a negative result. The GPU itself is capable of Gen 5. One caveat belongs with "
  "the number: docs/specs/cuda-audit.md section 4.3 alleges the published host-to-device "
  "figure was taken on a path the serving code does not use. That is flagged and not "
  "adjudicated, so quote the figure with the caveat rather than laundering it.")

q("governor",
  "Could we do a full fine-tune of the 7B here?",
  "No, and not by a small margin. 7.616B parameters under AdamW needs weights, gradients and "
  "two optimizer moments; at fp32 that is 16 bytes per parameter, about 113 GiB -- projected "
  "arithmetic. Against a 14.2 GiB budget the shortfall is roughly 8x. QLoRA is not a cost "
  "optimisation on this box, it is the only thing that makes a 7B trainable at all.")

q("governor",
  "Can we fine-tune a 32B or a 70B?",
  "No. A 32B in 4-bit is about 16 GiB of weights before a single gradient exists -- over "
  "budget with the optimizer at zero, projected. 70B is not close. Lowering the LoRA rank "
  "does not help: rank governs the adapter, and the adapter is a fraction of a GiB of an "
  "11 GiB problem.")

q("governor",
  "Is a 14B QLoRA feasible here?",
  "Feasible and tight. Projected peak is about 10.9 to 11.9 GiB against a 14.2 GiB budget, "
  "which leaves 2 to 3 GiB covering activations, fragmentation and everything else that "
  "touches the card. It needs rank 16 or below, batch 1, sequence 1024 or below, and "
  "gradient checkpointing is mandatory. Raise any one of those and it OOMs. Offer it with the "
  "arithmetic visible rather than behind a spinner.")

q("governor",
  "Can we train and serve at the same time?",
  "No, and that is architectural rather than something to engineer away. The governor "
  "serialises the card and `train` is never evicted, so a fine-tune locks chat, image and "
  "remix out for its entire duration. A \"start training\" button is a button that takes the "
  "whole rack offline, and the page needs to say so next to the button.")

q("governor",
  "Should a training route be world-callable?",
  "No -- it is a hard requirement, not a hardening task for later. A world-callable, "
  "never-evicted, long-running GPU route is a rack-wide denial of service that costs one HTTP "
  "request. The pattern already in this repo is the ASIC gate: SYMONEURAL_ASIC_ENABLED plus "
  "SYMONEURAL_ASIC_TOKEN, off by default.")

q("governor",
  "Would CPU offload rescue a run that does not fit?",
  "No. ZeRO-style optimizer offload crosses PCIe, and this host is capped at Gen 3 x8, about "
  "7 GB/s measured. Offloading optimizer state every step over a link that slow converts a "
  "VRAM problem into a wall-clock one. The argument is about an order of magnitude, so it "
  "survives at any plausible Gen 3 x8 value.")

q("governor",
  "Is multi-GPU an option?",
  "No. One card. No FSDP, no DeepSpeed ZeRO-3, no tensor parallelism and no NVLink. "
  "Reinforce's P2P test is waived rather than failed, and that is the right vocabulary here "
  "too: cannot-here, not broken.")

q("governor",
  "What does CapabilityWaived mean and why is it a 501?",
  "It is Reinforce's error for \"this box cannot do that\", deliberately not a subclass of "
  "DeviceError so that cannot-run-here never masquerades as broken, and the server surfaces "
  "it as 501 rather than 500. Applied to training: picking a 14B at rank 64 and sequence 2048 "
  "is not an error, it is a capability this box does not have, and the preflight should "
  "return 501 with the arithmetic that proves it instead of letting CUDA OOM at step 0.")

q("governor",
  "What is the OOM ladder on this box?",
  "The usual first rungs are already taken: batch is 1 and gradient checkpointing is on. What "
  "remains here is lower rank, shorter sequence, smaller base model. A preflight should say "
  "which rung it is offering, in those words.")

q("governor",
  "A fine-tune and the chat surface both want the card. What happens?",
  "Whichever acquires first holds it. If that is `train`, chat waits -- the governor refuses "
  "to evict a training run, so the wait can be the whole duration of the fine-tune. If chat "
  "holds it and `train` arrives, chat is evicted, because the weight sets do not co-fit.")

q("governor",
  "Does a QLoRA run take the governor lock by itself?",
  "training/train_lora.py does not -- it has no acquire, no with, no subprocess call to the "
  "governor. The lock has always been taken by a human wrapping the command: "
  "`gpu-governor.sh with train -- training/.venv/bin/python training/train_lora.py ...`. Any "
  "training surface built on top of it must take the lease itself, in the `with` form so it "
  "always releases, and must never call a bare release.")

# ---------------------------------------------------------------------------
# 3. NEGATIVE RESULTS -- things tried here that did not work, and are published or
#    recorded deliberately so nobody retries them.
# ---------------------------------------------------------------------------

q("negative",
  "What negative results does this project publish?",
  "Several, deliberately. The PCIe Gen 3 x8 host cap at about 7 GB/s (measured) and the "
  "failed multi-stream overlap are both on the site. Alongside them, recorded in the repo: "
  "the 7B looping on JSON output, VLC rejected on licence grounds, Yocto rejected as a "
  "firmware route, MicroBT firmware being unemulatable, the two-column rack, and the fact "
  "that no full fine-tune of any model fits on this card. A site arguing that its numbers are "
  "real has to publish the ones that went the wrong way.")

q("negative",
  "We asked the 7B for a JSON object and it broke. What happened?",
  "It looped. Measured: it emitted {\"match\":[\"premier league\",\"nfl\",\"nba\",\"mlb\","
  "\"f1\",\"nfl\",\"nba\", ... until it hit the token cap, so the object never closed, "
  "nothing parsed, and the fallback would have fired on every single request while the "
  "feature appeared to work. Asking for one line of comma-separated keywords, it answers "
  "cleanly every time.")

q("negative",
  "What is the general lesson from the JSON-looping failure?",
  "Pick the output format the model can finish. A small model is far better at a flat list "
  "than at nested structure. And a feature whose happy path never executes is worse than one "
  "that is honestly absent, because it passes a glance -- it looks fine until somebody "
  "measures it.")

q("negative",
  "Why was VLC rejected for in-browser playback?",
  "Licensing. references/IPTV/vlc-master/ is GPLv2 and its only web path is "
  "extras/package/wasm-emscripten -- an hours-long build producing a GPL WASM blob that would "
  "then be part of what we distribute in site/, making the site itself GPL-encumbered. hls.js "
  "does the same job in a 384 KB light build under Apache-2.0, verified by reading its LICENSE "
  "file rather than trusting GitHub's API, which reports NOASSERTION for that repo.")

q("negative",
  "What does the vendored hls.js not do?",
  "It is the light build: no subtitles and no alternate audio. Chrome and Firefox will not "
  "play an .m3u8 natively so they need it; Safari does, and the page uses the native path "
  "there. AES-encrypted HLS is refused rather than decrypted, and series episodes list "
  "without URLs.")

q("negative",
  "Would Yocto and meta-cryptocurrency be an easier route to custom Antminer firmware?",
  "No, and building to it would waste real time. meta-cryptocurrency was last pushed in "
  "October 2019 and its 39 recipes are cgminer driver variants for the Antminer S1 and S2 -- "
  "2013-14 hardware, back when hashboards were driven by open cgminer drivers. There is no "
  "S17/S19/T17 support and there never was. The blocker is not the build system: hashboard "
  "control on a Zynq-7007 is closed, so any build system gets you a booting Linux that cannot "
  "make the boards hash. Braiins does not use Yocto either -- their feeds are OpenWrt -- and "
  "the repo's own Yocto config targets MACHINE kirkwood, a Marvell part, where the "
  "controllers are Xilinx Zynq-7007.")

q("negative",
  "Can we emulate MicroBT/Whatsminer firmware?",
  "No, and it is settled. The container header is readable -- magic 0xae640a3f, a declared "
  "payload size, a 6,812-byte header and the control board as ASCII \"h616\" -- but everything "
  "after the header measures 7.999 bits/byte of entropy across the whole 41 MB, which is "
  "indistinguishable from random. Measured, by scanning for gzip, squashfs, UBI, JFFS2, ext, "
  "xz and cramfs magic and finding only coincidental byte pairs. You cannot extract a kernel "
  "from ciphertext. Independently: h616 is an Allwinner SoC and qemu-system-arm has machines "
  "only for H3, A10 and R40.")

q("negative",
  "So a two-column rack would halve its height?",
  "It does the opposite, and it was measured rather than argued. A unit row is a horizontal "
  "layout -- name and attribution left, badges pushed right -- so halving its width wraps the "
  "attribution. Units went from 76px each to 178px at 1440 (the rack 611 -> 775) and to 403px "
  "each at 1301 (611 -> 2,696; the panel got four times taller). The unit row is the one thing "
  "in that layout that must not be narrowed. The failure is left in the CSS with its numbers "
  "so nobody retries it.")

q("negative",
  "Can we put the section heading's lede beside its title with a grid?",
  "Only for the three heading elements. #rack keeps its heading in its own wrap, but #console "
  "and #more keep their entire contents in one, so gridding the wrap put the control board "
  "itself into a narrow grid cell and took it from 1,043px to 3,553px. Measured, and left in "
  "the CSS with the number.")

q("negative",
  "Was there ever a rack CTA?",
  "Yes, built and then removed on the owner's say-so. The relevant habit is what to do about "
  "it: revert cleanly and completely, including any API field that was added for it, rather "
  "than leaving dead code behind.")

q("negative",
  "What happened with the constellation of renders on the front page?",
  "It was nineteen renders at 38-59px scattered around four questions with SVG lines drawn to "
  "each. Two things were wrong with it there. The gutters beside a readable centre column are "
  "too narrow to hold it, so below 1280px the absolutely-positioned renders collapsed into a "
  "vertical column down the left edge -- which is what a visitor actually saw. And at 50px the "
  "watermark burned into each render is unreadable, when that watermark is the entire claim "
  "the band was making. The object was kept and moved to /build.html in its own .sky "
  "namespace.")

q("negative",
  "Why is DPO not in the training plan?",
  "Two reasons. It needs a reference model resident alongside the policy, which on 4-bit is "
  "achievable by disabling the adapter rather than loading twice but is a second design "
  "problem. And it needs paired preference data, which does not exist here. It is deferred "
  "explicitly, and the UI should say so rather than showing a greyed-out tab.")

q("negative",
  "Can trl's assistant_only_loss replace the hand-rolled label masking?",
  "Not on this model. That flag requires the chat template to emit {% generation %} markers so "
  "trl can find the assistant span, and the stock Qwen2.5 template contains zero of them -- "
  "its only match for \"generation\" is {%- if add_generation_prompt %}, which is a different "
  "mechanism. So it would fail against this template rather than silently mis-mask, which is "
  "the good failure, but the hand-rolled -100 masking is a workaround for a real gap and not "
  "legacy cruft. Do not treat it as a cleanup.")

q("negative",
  "Does offering both \"all-linear\" and an explicit target-module list give a user more coverage?",
  "No -- on Qwen2 they are the same set, so it would be a knob that does nothing and somebody "
  "would burn a run finding that out. Verified by instantiating the model on the meta device "
  "and listing nn.Linear leaves: a decoder layer contains exactly seven (q, k, v, o, gate, up, "
  "down) and the only other nn.Linear is lm_head, which peft's all-linear shorthand excludes "
  "by design. Rank is what separates one preset from another, not module coverage.")

q("negative",
  "Can we test the full tuner form path from this box?",
  "No. The SSRF guard correctly rejects loopback, so you cannot self-serve a playlist from "
  "this machine to drive it. It has to be tested against a real playlist. The Xtream client "
  "has also never been exercised against a live panel beyond channel listing -- tuning a real "
  "stream end to end is untested.")

q("negative",
  "Can we test the ASIC telemetry?",
  "Not on this box. The QEMU emulator runs the control board's ARM cores but not the FPGA "
  "fabric or the links to the hashboards, so lighttpd and upgrade.cgi run and bmminer does "
  "not. That is good for the flash path -- the part that otherwise costs a rig to get wrong -- "
  "and useless for telemetry. A real rig, or a BOS+ rig, is the only way, and no download "
  "substitutes for it.")

q("negative",
  "Does the S9 boot under QEMU?",
  "No. It unpacks -- it is a different generation, everything under xilinx/ with a JFFS2 "
  "rootfs that cannot be an initrd, so it gets an emulated MTD -- but it produces no console "
  "output, so it is reported as not booting rather than as working. The older kernel and its "
  "devicetree do not match QEMU's zynq machine. S17 Pro, S17+ and T17 do boot to a shell.")

q("negative",
  "Which firmware packages in references/ are unusable and why?",
  "The five .bin files under Projects_Crypto/Antminer/Whatsminer/ are failed downloads: one "
  "is a 138-byte nginx 404 page, two are 0 bytes and two are HTML documents -- fwcheck "
  "rejects the 138-byte one with magic 0x6d74683c, ASCII \"<htm\". And the S19j SD package "
  "fails five of its own nine hashes while `unzip -t` reports no CRC errors, so the archive is "
  "intact and its contents genuinely disagree with the manifest shipped inside it. An SD image "
  "is what you reach for when a rig is already bricked, which is the worst moment to trust a "
  "package that disagrees with itself.")

q("negative",
  "Is SyMoN_ML's DRM sound?",
  "No, and it is the most serious open finding in the repo. auth_daemon.py in the blueprint "
  "calls _check_local_sandbox_state() as a fallback when the TRON lookup does not match, and "
  "that function is `return True` unconditionally. So blocking api.trongrid.io grants a "
  "licence -- iptables -j DROP defeats the entire IP moat. That is why the auth daemon was "
  "deliberately not built: a licence check that fails open is worse than none, because the "
  "surface around it claims the weights are protected.")

q("negative",
  "What is wrong with the Akash cost figure?",
  "Not the arithmetic, the unstated assumption. $1.68/hr x 8 GPUs x 24 x 30 = $9,677 at 100% "
  "utilisation, while the pitch's $5,800/mo implies about 60%. That is a reasonable number and "
  "the document never says so, which is the first thing a sceptical reader attacks.")

q("negative",
  "The blueprint says to install torch from the cu121 index. Is that right?",
  "No. Blackwell sm_120 needs cu128. Following that instruction verbatim installs a torch that "
  "cannot run on this card. The venv at training/.venv has torch 2.11.0+cu128, and the venv is "
  "the authority -- the manual's Playbook 04 status block claiming 2.13.0+cu130 is stale.")

q("negative",
  "Does the manual's Playbook 04 training snippet run as written?",
  "No -- it would raise TypeError. It passes warmup_ratio=0.03, and warmup_ratio is absent "
  "from both TrainingArguments and SFTConfig in the installed transformers 5.15.0 and trl "
  "1.10.0 (group_by_length is gone too). train_lora.py's comment saying 5.x dropped it in "
  "favour of an explicit step count is correct -- a rare case here where the comment beat the "
  "doc. Express warmup in steps.")

q("negative",
  "Is there an axolotl, unsloth or LLaMA-Factory checkout on this box?",
  "No. references/ contains no axolotl, no unsloth, no LLaMA-Factory, no text-generation-webui "
  "and no LM Studio capture -- searched by name to depth 3 across every tree. If somebody "
  "believes one is here, it is not.")

q("negative",
  "The owner said the IPTV reference was \"the one with mediatek\". Is it?",
  "No -- references/IPTV/mediatek_builds/ is empty. He guessed, and verifying it saved "
  "building against nothing. The useful base was "
  "references/IPTV/IPTV/iptv_gateway_server.py, and the Xtream Codes protocol reference was "
  "the JS client beside it. Ask for the reference when a description is ambiguous, and then "
  "check it yourself.")

q("negative",
  "Was Braiins OS+ forked?",
  "No, deliberately. Everything that can drive an Antminer hashboard is GPLv3 -- cgminer by "
  "its own COPYING, bmminer as a cgminer fork, bosminer as Braiins' rewrite -- so a fork is a "
  "derivative work that must ship GPLv3 with source. The GPL binds derivative works, not "
  "separate programs talking over an interface, and bos-plus-api is a full public gRPC surface "
  "covering auth, telemetry, cooling, performance tuning, pools and upgrade. So SyMoNeuRaL "
  "Miner is a proprietary control plane over that API, which carries no GPL obligation. "
  "backend/apps/asicminer/ already is that.")

q("negative",
  "Where is the Braiins OS source?",
  "Not on GitHub. braiins/braiins-os, braiins/braiins-os-plus, bitmaintech/meta-bitmain and "
  "bitmaintech/openwrt all 404, and the braiins org holds old Puppet modules. Only "
  "bos-plus-api is live. references/braiins-os-feeds-master/ is packaging recipes, not miner "
  "source -- every Makefile is OpenWrt and the sources point at git@gitlab.bo, their internal "
  "host.")

q("negative",
  "Four hover captions on /build.html hang off the left edge. Why was that left alone?",
  "It is pre-existing, measured identically on production (-14, -70, -47) and locally (-13, "
  "-71, -48), hover-only, and it clips nothing. The caption box is a fixed 220px centred on "
  "renders that are 55-64px wide and sit near the edge. Nudging counter-rotated, absolutely "
  "positioned elements is exactly the class of change this project has lost rounds to, so it "
  "deserves a screenshot-and-confirm rather than a drive-by.")

q("negative",
  "Can the front page be one screen on a phone?",
  "No, and it should not be promised. At 390px the front page is 9,161px and the rack alone is "
  "about 2,700px -- measured. Ten screens do not become one, and pretending otherwise hides "
  "things a phone visitor will never find. The one-screen gate is off below 1301px, so phones "
  "get the ordinary scrolling page with every section visible.")

q("negative",
  "Do the one-screen panels scroll?",
  "Yes, internally, and no amount of work closes that. The rack is about 1,009px of content -- "
  "heading 134, rackrow 762, footnote 38, with no padding to reclaim -- against 744px of panel "
  "at 1440x900. Removing that scroll means folding the rack's own cards into <details>, which "
  "is a redesign of the flagship section and nobody has asked for it. Do not tell the owner "
  "the panels do not scroll; he has raised the scrollbar twice, and the second time it was "
  "because an agent reported \"one screen\" from a test that measured the document instead of "
  "the panel.")

# ---------------------------------------------------------------------------
# 4. TESTS THAT PASSED ON A BROKEN PAGE
# ---------------------------------------------------------------------------

q("testing",
  "How is the frontend tested here?",
  "In a real browser: `node tests/frontend.mjs`, and `node tests/frontend.mjs "
  "https://symoneural.com` against production. It drives the real pages through Playwright "
  "using the system Chrome, so nothing has to be downloaded, and it asserts on what the DOM "
  "shows -- units rendering from /api/status, the bus plate carrying a real reading, nothing "
  "overlapping at 390px, ravencalc returning x**3/3, and a generated image actually decoding.")

q("testing",
  "Why does a test assert that a generated image decodes?",
  "Because a render once succeeded server-side and still showed as a broken image for every "
  "visitor. curl proved the endpoint answered, which was never in doubt. The assertion checks "
  "naturalWidth > 0 after img.complete, which is the only thing that would have caught it.")

q("testing",
  "Why should I run the suite against production as well as localhost?",
  "Because the two differ in exactly the way that has caused every \"it's still broken\" "
  "exchange in this project. Against 127.0.0.1:8800 the API answers directly and the Caddyfile "
  "is never exercised at all -- the suite passed 25/25 locally while all four section URLs "
  "were dead in production.")

q("testing",
  "The suite passed 22/22 while a page was dead in production. How?",
  "TUNER_JS in tools/build_pages.py is a normal triple-quoted Python string, not a raw one, so "
  "a \\n written in the source became a real newline in the emitted JavaScript -- inside a "
  "string literal, which left it unterminated and killed the entire inline script. Playback, "
  "category browsing and the model filter were all dead. Every tuner assertion checked markup, "
  "CSS and endpoints, and none of those care whether the script runs. The page looked correct "
  "and did nothing. Counting passes is not the same as the page working.")

q("testing",
  "I am adding inline JS to tools/build_pages.py. What do I need to know?",
  "Write \\\\n, not \\n. Those blocks are normal triple-quoted strings, so a single-backslash n "
  "becomes a real newline in the emitted JavaScript and unterminates the string literal. It "
  "has bitten twice -- TUNER_JS shipped that way to production, and CHAT_JS did the same thing "
  "before the assertion added in between caught it.")

q("testing",
  "What does the \"no page throws a script error\" assertion do?",
  "It loads all twelve pages and fails on any pageerror. It is deliberately not "
  "tuner-specific: the escaping fault is a generator-wide hazard and any generated page could "
  "acquire it the same way. Confirmed by reintroducing the exact bug on the exact line -- the "
  "test goes red with \"tuner.html: Invalid or unexpected token\" while everything else still "
  "passes.")

q("testing",
  "Three layout assertions in a row passed on a broken page. What was the common cause?",
  "Every one of them measured a proxy instead of the render. The document's scroll height "
  "instead of the panel's; rack.top on an element that was hidden, which reports 0 and so "
  "passed for free; and element.hidden, the attribute, on an element the browser was actually "
  "painting. The suite now reads getComputedStyle(...).display and asserts that while any "
  "panel is open, no other panel occupies vertical space.")

q("testing",
  "Why did the [hidden] attribute stop hiding the masthead?",
  "Because hidden works by applying display:none from the *browser's* stylesheet, and any "
  "author rule that sets display beats it. #hero had been given display:flex to centre the "
  "masthead in its panel, written as a bare html.ns #hero, so from that commit onward the "
  "hidden attribute had no effect on it -- measured: hidden true, computed display flex, 172px "
  "rendered, two scrollbars on the live page. The selector is html.ns #hero:not([hidden]) now. "
  "Do not simplify it. The other three panels were fine only because nothing sets display on "
  "them.")

q("testing",
  "What is the rule for a new layout assertion?",
  "Verify it fails when you reintroduce the bug. That check is cheap and it has caught a "
  "vacuous assertion every single time it has been run.")

q("testing",
  "How do I debug a CSS problem in this repo?",
  "Render the page and read computed styles rather than reasoning about the cascade. Two "
  "scratch tools have each found real bugs that looked fine by eye: a truncation checker "
  "comparing scrollWidth to clientWidth across widths, and a type-scale dump of computed "
  "font-size for every text class, sorted.")

q("testing",
  "What is the recurring CSS bug class in this stylesheet?",
  "A generic class name defined twice, where the later rule silently eats the first. Five "
  "instances now: .bar collapsed the site header to 7px sitewide; .live had the nav badge "
  "styling the control board legend, so one of three legend chips had a pill and drew every "
  "eye; #console .sub outranked .mod .sub and rendered a mono footnote at 15px, larger than "
  "the sentence above it; .card was defined twice and the receipts rule won eleven unrelated "
  "cards on documentation.html; and the GPU panel had to be written as .gbar rather than .bar "
  "to design around it. Grep a new class name against both stylesheets before writing it.")

q("testing",
  "The .card collision only moved the layout by one pixel. Why did that matter?",
  "That is why it survived. Measured on documentation.html: eleven cards outside any .cards "
  "grid were rendering display:flex with 18/17/16px padding and a gradient instead of "
  "display:block, 22px and a flat panel, plus a hover that lifts and turns green. Total height "
  "moved by one pixel, so nobody noticed -- it was found by audit. The receipts block is "
  "scoped to .cards now, with a comment saying why so it is not unwound.")

q("testing",
  "A feature was written, styled and completely unreachable. How?",
  ".band-art had pointer-events:none. That is correct for the layer, which spans the band and "
  "would otherwise swallow clicks on the CTA -- but it also disabled every descendant, so the "
  "hover captions showing each render's prompt had never once appeared since they shipped. A "
  "feature that is written, styled and unreachable is invisible to any test that only checks "
  "markup, so the test added for it asserts computed pointer-events.")

q("testing",
  "Why does the GPU panel assertion check values rather than markup?",
  "Because a panel that renders its layout and never receives data is precisely the decorative "
  "gauge this site argues against, and it is indistinguishable from a working one in a "
  "screenshot. Confirmed by isolating the failure: renaming the panel's ids leaves the layout "
  "intact, the socket live and the stack at eight units, and the test still fails on vram=\"\" "
  "temp=\"\".")

q("testing",
  "How was it proved that the GPU panel shows live data?",
  "A real render was fired while watching it. holder went idle -> image with SyMoNeuRaL Image "
  "showing busy in the stack, and power differs between reads -- which is what rules out a "
  "cached value.")

q("testing",
  "The tuner endpoint assertion passed while the page was calling a path that did not exist. Why?",
  "Because it listed the two correct paths itself and probed the API directly, so it tested "
  "the API rather than the page. It now reads the /api/tuner/... strings out of the page's own "
  "script and probes those, so what is tested is what the page actually calls. Confirmed "
  "against both original bugs independently: deleting the tn- CSS gives styled=false, and "
  "reverting the endpoint gives /channels=405.")

q("testing",
  "A test started passing for the wrong reason. What happened?",
  "The selector was 'button:has-text(\"Generate\"), button'. A selector list returns the first "
  "element in DOM order matching either branch, so it matched the new Documentation dropdown, "
  "clicked open a menu, and waited four minutes for an image.")

q("testing",
  "Why did the 405 on /api/tuner/channels look like a server fault?",
  "Because no router serves that path, so the request fell through to the StaticFiles mount at "
  "/ and came back 405 Method Not Allowed -- a confusing way to be told a URL is wrong. The "
  "real routes are POST /api/tuner/playlist and POST /api/tuner/xtream/channels. The cause was "
  "guessing at an endpoint instead of reading the router the module exposes.")

q("testing",
  "Where does Playwright live?",
  "contrib/llama.cpp/tools/ui/node_modules, installed for the webui build, imported by a path "
  "derived from the test's own location. channel: 'chrome' uses the system browser so nothing "
  "downloads. Note the contrib/ prefix -- an earlier draft of the docs omitted it, which sent "
  "readers to a dead path while the suite quietly worked.")

q("testing",
  "Any traps when testing a WebSocket by hand?",
  "Two, and both produce convincing false failures. Upgrade: is an HTTP/1.1 mechanism that "
  "does not exist in HTTP/2 and curl negotiates h2 with Caddy by default, so the header "
  "arrives as meaningless metadata and FastAPI 404s a websocket-only route -- use curl "
  "--http1.1. And a *successful* upgrade leaves the socket open and streaming, so curl exits "
  "28 on timeout however well it worked; read the status line out of -D headers rather than "
  "trusting the exit code.")

q("testing",
  "Any trap with pkill in this repo?",
  "Yes. The bracket trick does not save you with `pkill -f`: if the pattern appears anywhere "
  "in your own shell's command line, pkill kills its own parent and the tool call dies with "
  "exit 144. Put the pkill in a command that does not otherwise mention the process name.")

q("testing",
  "What is the value of the tuner module's own test suite?",
  "57 tests that pass offline in under a second. Licensing has 21 and the scan guard has 8. "
  "Offline and fast is what makes them get run.")

q("testing",
  "Which tests should never be deleted?",
  "The ones that exist because of a specific bug. The render-decodes assertion (a render that "
  "404'd), computed pointer-events (a feature disabled by an ancestor), the 390px right-edge "
  "spill (the nav ran to x=512 on a 390px viewport), the cache-bust assertion (a week-old "
  "stylesheet against new markup), the pageerror sweep (a dead inline script), and the "
  "watermark-readable-as-text assertion. Each one encodes a failure that a markup check cannot "
  "see.")

# ---------------------------------------------------------------------------
# 5. VERIFICATION STEPS THAT FAILED ON HEALTHY INPUT
# ---------------------------------------------------------------------------

q("verification",
  "How many verification steps in this repo have failed on healthy input?",
  "Five in two days, and every one shouted. deploy.sh's reference counter, incremented inside "
  "a piped while read -- a subshell, so the count was discarded and the script exited 0 while "
  "printing MISSING. deploy.sh calling /overview and friends MISSING, when they are routes and "
  "correctly not files. install-caddy.sh asserting 200 on http:// when Caddy's automatic "
  "HTTP-to-HTTPS redirect returns 308 and the check did not follow redirects, so it could "
  "never have gone green. The same script asserting 200 on / after / became a 302. And its "
  "preflight reporting \"api DOWN\" immediately after a successful systemctl restart, because "
  "systemd returns before uvicorn binds the port.")

q("verification",
  "What is the rule that would have caught all five of those?",
  "Run the check against the real system and confirm it passes on known-good input -- not only "
  "that it fails on known-bad. Both halves, every time.")

q("verification",
  "Why is a check that cries wolf worse than no check?",
  "Because the damage is cumulative. A verification step that fails on healthy input gets "
  "switched off, or trains the reader to skip the whole block, and then the real failure goes "
  "straight through. One of the five was worse than a false alarm: the \"api DOWN\" branch "
  "offers a five-second abort, so it actively invited the operator to cancel a healthy "
  "deployment.")

q("verification",
  "Why did install-caddy.sh report api DOWN right after a successful restart?",
  "Because `systemctl restart symoneural-api` returns once systemd has forked the unit, "
  "seconds before uvicorn binds the port. The obvious invocation -- restart && install-caddy.sh "
  "-- races it every time. It retries for ten one-second attempts now, so a genuinely dead API "
  "still reports DOWN, ten seconds later.")

q("verification",
  "Is deploy.sh's subshell bug still live?",
  "No. It was fixed in aa424d3: the loop reads from a process substitution, so `missing` "
  "survives into the exit test. Verified empirically rather than by reading the comment -- the "
  "block was run verbatim against a fake webroot containing one present and one absent "
  "reference, and it counted 1 and exited non-zero. Earlier revisions of the docs said the bug "
  "was still live; that was the stale claim, not the code.")

q("verification",
  "What is the general lesson from the subshell bug?",
  "A counter incremented inside a piped `while read` is discarded -- the pipeline puts the loop "
  "in a subshell. The other while read in that script, the orphan scan, is still in a subshell "
  "and that is fine, because it only writes to stdout and sets nothing its caller reads.")

q("verification",
  "Why did the deploy's reference check start failing after cache-busting shipped?",
  "It tests -f on every (src|href)=\"/...\" it finds, and cache-busting appends ?v=<hash>, so "
  "it began looking for a file literally named symoneural.css?v=b56305bfed. Query strings are "
  "stripped now.")

q("verification",
  "Why does deploy.sh treat /livestack differently from livestack.html?",
  "Because one is a route and the other is a file, and both resolve. tools/build_split.py "
  "writes livestack.html, but every page links /livestack without the extension, because "
  "ops/Caddyfile reverse-proxies that path to FastAPI. So the check was asking the disk about "
  "a URL that is deliberately not on the disk. Only the extensionless form is exempted, which "
  "is a deliberate asymmetry: a genuinely missing livestack.html is still caught. Verified by "
  "running the fixed loop against the real webroot -- ok=47, routes=5, missing=0.")

q("verification",
  "A find -regex alternation silently dropped every .json file. Why?",
  "Because `js` was listed before `json`, and -regex must match the whole path: `js` matched, "
  "`on` did not, and it never backed up to try the longer alternative. Order alternations "
  "longest-first.")

q("verification",
  "What does setup.sh do?",
  "Verifies that a fresh clone can run here -- tools, GPU, CDI, serving deps, engines with "
  "resolvable libraries, weights, licences, adapter -- and prints the three steps that need "
  "root rather than taking root itself. It reported 20 ok, 0 missing on this machine.")

# ---------------------------------------------------------------------------
# 6. DEPLOY AND OPS
# ---------------------------------------------------------------------------

q("deploy",
  "How do I deploy a change to this site?",
  "It depends what you changed, and the three commands are not interchangeable. Content under "
  "site/ needs `sudo scripts/deploy.sh --prune`. A change to backend/api.py needs `sudo "
  "systemctl restart symoneural-api`. A change to ops/Caddyfile needs `sudo "
  "./scripts/install-caddy.sh`. Work out which one your change requires and say so -- several "
  "rounds have been lost to running the right command for the wrong file.")

q("deploy",
  "I edited a page in site/. Is it live?",
  "No. Static files under site/ do not reach a visitor until somebody with root runs `sudo "
  "scripts/deploy.sh --prune`. API responses change the instant backend/api.py is edited and "
  "the service restarted; static files do not. When you finish a frontend change, hand over the "
  "command and say plainly that it is built but not live -- do not describe it as deployed.")

q("deploy",
  "The owner says a change did not work. What should I check first?",
  "What is actually deployed, before defending anything. `curl -s "
  "https://symoneural.com/index.html | grep -o 'symoneural.css?v=[0-9a-f]*'` and compare "
  "against the local file's hash. Most \"this isn't working\" exchanges in this project were a "
  "correct change that had not been deployed yet, and saying so plainly ends them in one line.")

q("deploy",
  "What is an orphan in deploy.sh's sense?",
  "A file this deploy would not publish -- not \"a file absent from site/\". Those differ, "
  "because site/ is allowed to hold things the webroot must not: openapi.json is proxied to "
  "FastAPI and the art-*.json are build-time metadata. Under the old definition every "
  "already-published copy of an excluded file stayed in the webroot forever, never updated and "
  "never removed.")

q("deploy",
  "Why does the prune run before the reference check?",
  "Because the check tests the webroot. A page referencing a file that lived only there was "
  "reported ok and then deleted by the prune in the same run -- so the script passed on a state "
  "that no longer existed when it exited.")

q("deploy",
  "Why does deploy.sh filter by extension?",
  "Because it used to `find -maxdepth 1 -type f` and install everything, and what was sitting "
  "in site/ was an 11.6 MB browser \"Save page as\" capture plus its PDF print. site/ is a "
  "working directory; the webroot is not. .json is deliberately excluded -- /openapi.json is "
  "proxied to FastAPI and a static copy would be shadowed and go stale, and the twenty "
  "art-*.json are build-time metadata nothing fetches.")

q("deploy",
  "Why does the deploy back up the previous webroot, and is the backup an orphan?",
  "It backs up so a bad deploy can be undone. The backup this run just took is exempt from the "
  "prune, or --prune would delete the one file that exists to undo a bad deploy.")

q("deploy",
  "How many generators are there and what is the order?",
  "Eleven, and the order is constrained at both ends. build_pages, build_masthead, build_rack, "
  "build_console, build_cost, build_stack, build_training, build_sky, build_tabs, then "
  "build_split, then build_cachebust. build_split reads the assembled index.html to produce the "
  "four section pages, so anything that edits index.html must run before it. build_cachebust "
  "stays last, because it stamps every local asset with its content hash.")

q("deploy",
  "Why must build_cachebust.py run last?",
  "Because it stamps ?v=<content hash> on every local CSS, JS, PNG, SVG and WOFF2 link, and the "
  "Caddyfile sets max-age=604800. If a stylesheet changes and the stamps are not refreshed, "
  "every visitor with a warm cache gets new markup against a week-old stylesheet -- which is "
  "exactly the failure that put nineteen full-size renders down the left of the live page in "
  "front of a visitor.")

q("deploy",
  "How do I know a generator is idempotent?",
  "Run every generator twice and diff. md5sum the site files, run the chain, md5sum again, "
  "compare. tools/build_console.py once nested folds inside folds when run twice, which is what "
  "the check exists for.")

q("deploy",
  "What is the BEGIN/END marker contract?",
  "The generators find their own work in an HTML file by marker strings. If you change a marker "
  "in a generator you must change it in the HTML in the same commit, or the generator stops "
  "finding its block and appends a second one. That has already happened once when the markers "
  "still said \"generated by demo/build_*.py\".")

q("deploy",
  "Why does build_split.py work by subtraction?",
  "Each section page is index.html with the other sections deleted, not a shell reassembled "
  "from parts, so the head, header, footer, scripts and every cache-bust stamp match the front "
  "page by construction rather than by a copy that drifts. index.html is not modified, because "
  "the other generators find their work by markers and moving a section out from under them "
  "would make the next run append a second copy.")

q("deploy",
  "What bug did the section-removal regex have?",
  "It matched `<section id=\"X\">`, and build_console.py emits `<section id=\"console\" "
  "style=\"padding-top:34px\">`, so it silently removed nothing and welded a control board onto "
  "all four pages. The removal asserts n == 1 now rather than being trusted.")

q("deploy",
  "Which flag of build_gallery.py touches the GPU?",
  "The default run renders what is missing and --force re-renders everything; both use the "
  "card, about 11.2s per image, measured. --restamp only redraws the watermark bar -- no GPU, no "
  "governor lease, seconds of CPU, and it cannot alter a pixel of the artwork. That was "
  "verified by comparing the SHA-256 of the cropped art region before and after.")

q("deploy",
  "Why is --restamp idempotent?",
  "Because it crops each PNG to meta['size'] rows -- the art height -- and redraws the bar from "
  "the sidecar, so it discards whatever bar is present regardless of that bar's size. "
  "Subtracting the current bar height instead would compound every time it ran.")

q("deploy",
  "How is the API run in production?",
  "As the systemd unit symoneural-api. Manage it with systemctl status/restart/stop. For local "
  "work, ./scripts/symoneural.sh on|off|status -- off is the kill switch and frees the card.")

q("deploy",
  "What is the podman container in the state table?",
  "Inert, not a live server. It is running but unreachable because 8800/tcp is not published, "
  "and the image predates the current code. It exists because the owner wanted to learn CDI. "
  "Stop it or rebuild it; do not debug against it. Naming it as inert saves the next person an "
  "hour, which is what it cost the first time.")

q("deploy",
  "Is CDI working on this box?",
  "Yes, verified end to end: nvidia-smi printed the RTX 5070 Ti from inside a rootless podman "
  "container on the first attempt. /etc/cdi/nvidia.yaml is generated at CDI spec 0.7.0 with "
  "three devices, and nvidia-cdi-refresh.service/.path are enabled so the spec regenerates on "
  "driver updates. Measured on this machine: driver 610.57.04, CUDA UMD 13.3.")

q("deploy",
  "Why Podman rather than Docker here?",
  "Rootless, so no daemon runs as root on a box serving the public internet; CDI is the native "
  "device path in nvidia-container-toolkit 1.20 rather than a legacy runtime hook; and quadlet "
  "gives systemd units, which is the model the API already uses.")

q("deploy",
  "Why is the container image plain Debian trixie rather than an NVIDIA CUDA image?",
  "Because the engines are compiled on this host -- Debian trixie, OpenSSL 3.5.6 -- and "
  "NVIDIA's ubuntu24.04 runtime image carries OpenSSL 3.0.13, where the needed symbols do not "
  "exist. It failed with `libgomp.so.1: cannot open shared object file` and then "
  "`libcrypto.so.3: version OPENSSL_3.3.0 not found`. Bind-mounting host-built binaries into a "
  "container of a different distribution either matches or does not run; there is no partial "
  "credit. NVIDIA publishes no Debian-13 CUDA image but does publish a debian13 apt repo, so "
  "the image is trixie plus the CUDA runtime from that repo.")

q("deploy",
  "What is the real prize in the container work?",
  "The customer image, not this box. sm_120 plus cu128 on Blackwell is fragile to reproduce, so "
  "\"here is the image\" is a far stronger handover than \"here is a script\". Note that CUDA's "
  "EULA governs redistribution, so read that clause before baking CUDA into a delivered image.")

# ---------------------------------------------------------------------------
# 7. PATHS, ROOTS AND MOVES
# ---------------------------------------------------------------------------

q("paths",
  "How do things in this repo find their own location?",
  "Nothing hardcodes it. Scripts derive their root from their own path, backend/api.py from "
  "__file__, the engine binaries via $ORIGIN RUNPATH, and the systemd unit from a @@ROOT@@ "
  "template substituted at install time. Clone it anywhere and ./scripts/setup.sh works. The "
  "owner asked for that explicitly and it has been broken four times.")

q("paths",
  "Why do the generators and scripts assert that api.py exists?",
  "Because a root computed by climbing a fixed number of levels fails *silently* -- the parent "
  "of the repo exists, so models/ and site/ resolve to empty directories rather than raising. "
  "The assert makes a wrong answer fail immediately. That silent mode is what made the demo/ "
  "flatten take an hour to diagnose.")

q("paths",
  "What was the worst path bug in this repo's history?",
  "RUN = HERE / \"run\" when api.py moved into backend/. That pointed the API's lock at "
  "backend/run while gpu-governor.sh kept using <root>/run -- two lock directories, both "
  "acquire, both load weights, about 12 GB of models onto a 16 GB card. It is the failure this "
  "repo warns about most loudly and it was one character from shipping. GOVERNOR, LLAMA_SERVER, "
  "SD_CLI and CHAT_ADAPTER had the same fault.")

q("paths",
  "Why did llama-server die after the demo/ flatten?",
  "cmake had baked an absolute RUNPATH -- /.../demo/llama.cpp/build/bin -- into the binaries, so "
  "it failed with `libllama-server-impl.so: cannot open shared object file` and the chat "
  "surface timed out. 102 binaries were repointed to $ORIGIN with patchelf, which makes the "
  "build tree relocatable rather than merely correct at one path. If you rebuild llama.cpp, "
  "re-apply that or the breakage returns.")

q("paths",
  "What breaks when a file moves under a live service?",
  "A running Python process pins its import paths and its resolved pathlib constants at start, "
  "so moving a file leaves it working until something touches the moved thing. /api/calc "
  "returned 503 for exactly this reason: the unit started at 00:19 and ravencalc.py moved after "
  "that, so the process held a sys.path that no longer resolved. The code on disk was correct. "
  "After any move, ask for `sudo systemctl restart symoneural-api` and then hit the surface you "
  "moved.")

q("paths",
  "What happened to the venvs when the repo moved?",
  "They carry absolute paths and had to be rewritten in place: 40 files in training/.venv "
  "(shebangs plus pyvenv.cfg) and 9 in the cuda-samples venv. Verified afterwards -- torch "
  "2.11.0+cu128 still imports with CUDA available, and the pinned CUDA venv still reports "
  "exactly 7 packages.")

q("paths",
  "Why did the repo keep answering after being moved out from under the systemd unit?",
  "Because Linux holds deleted inodes open for a live process. The unit still pointed at a path "
  "that no longer existed, so the running service was fine and the next restart or reboot would "
  "have taken the site down.")

q("paths",
  "Where is HF_HOME pointed, and is it right?",
  "training/train_lora.py computes ROOT as HERE.parent.parent, which resolves to /home/google, "
  "so HF_HOME becomes /home/google/models/hf -- a directory that does not exist. The real cache "
  "is backend/models/hf, about 15 GB, moved there in 9b5da84. A fresh run against the broken "
  "path silently re-downloads about 14.2 GiB into a non-repo location. That is the same "
  "climb-a-fixed-number-of-levels bug, for the fourth time.")

q("paths",
  "Where does the root CLAUDE.md need to live?",
  "At the repo root. It is a one-line import of .claude/CLAUDE.md and it stays at the root "
  "because Claude Code discovers it there -- move it into a folder and the working agreements "
  "silently stop loading, with no error, just an agent that has never read the rules.")

q("paths",
  "Does demo/ exist?",
  "No. It was flattened into the repo root: demo/api.py is backend/api.py now and "
  "demo/playground.sh is scripts/symoneural.sh. Any path with demo/ in it is from before that "
  "and is wrong.")

q("paths",
  "Where do the generators and scripts live?",
  "tools/ holds the eleven site generators plus the shared helper _art.py. scripts/ holds "
  "everything you execute -- setup.sh, symoneural.sh, gpu-governor.sh, deploy.sh, "
  "fetch-models.sh and the installers. ops/ holds config artifacts that get installed onto a "
  "system rather than run from here: the Caddyfile, the systemd unit template and the "
  "Containerfile. The rule is that ops/ is what gets installed and scripts/ is what you run.")

q("paths",
  "What is _art.py for?",
  "It holds the markup that all three render placements share -- masthead, rack and the "
  "constellation each had their own copy of the prompt/seed/seconds lookup and one had already "
  "drifted. It is a helper, not a generator; do not run it. It is also the only place that "
  "should compute a render's dimensions: _art.dims() reads the PNG's IHDR, because height=\"802\" "
  "was hardcoded in two generators and the watermark change made both wrong at once.")

# ---------------------------------------------------------------------------
# 8. HOUSE RULES
# ---------------------------------------------------------------------------

q("rules",
  "What are the honesty rules for anything user-facing here?",
  "Label every figure measured, vendor or projected. Never invent pricing. No decorative status "
  "indicators -- every LED and gauge reflects a real reading. Publish negative results too. And "
  "layout changes must not drop data: fold long content, never trim it. These are the product, "
  "not decoration, because the site's entire argument is that its numbers are real.")

q("rules",
  "What does \"label every figure\" mean in practice?",
  "Every number on a user-facing surface says where it came from: measured on this machine, a "
  "vendor specification, or projected arithmetic. Never present a projection as a result. The "
  "control board's provenance tag never folds and never truncates, because truncating the "
  "provenance of a number is the same failure as not printing it.")

q("rules",
  "Can I use text-overflow: ellipsis on a detail line?",
  "No. Every ellipsis rule has been removed from this stylesheet and none should come back. It "
  "is data loss with extra steps: the control board was showing `~84% of 896.1 p...` and the "
  "rack was cutting `built on Qwen2.5-7B-Instruct` down to `...7B-Ins...`. Let it wrap.")

q("rules",
  "Why does truncating \"built on Qwen2.5-7B-Instruct\" matter more than it looks?",
  "Because that attribution is an Apache-2.0 licence condition, not a nicety. It is also why "
  "the rack bought the space with geometry rather than a fold -- putting a unit's name and its "
  "attribution side by side instead of stacked -- so the licence obligation does not go behind "
  "a click.")

q("rules",
  "How do I make a long section fit a small screen?",
  "Fold it, do not trim it. Real <button aria-pressed> controls, remembered in localStorage, "
  "with the text left intact in the DOM one click away. Hiding a whole column would be a drop; "
  "collapsing detail behind a control is a fold. And fold only where there is something to "
  "save: on a scrolling page there is nothing to gain and hiding would be pure loss.")

q("rules",
  "Where should a fold handler be bound?",
  "To #rack or #console, never to #units. renderRack() rewrites #units on every status push, so "
  "a class toggled on a descendant is undone by the next update.")

q("rules",
  "Can I add a decorative status light?",
  "No. Every LED and gauge on the site reflects a real reading. A fake activity light is the one "
  "dishonest pixel on a page arguing for measurement. The painted-on vent slat block was "
  "removed for exactly this reason and replaced with a bus plate that shows the unit's actual "
  "bus from /api/status.")

q("rules",
  "Do I need to be careful replacing the string MIT in this repo?",
  "Yes -- never blind-replace it. \"MIT AI Training\" is purged everywhere user-facing, but most "
  "MIT substring matches in this corpus are ordinary words: limits, limited, submit, emits. And "
  "MIT is also a licence name that must stay -- llama.cpp, stable-diffusion.cpp, FastAPI and "
  "Pillow are MIT. Only whole phrases and local filesystem paths.")

q("rules",
  "Which python interpreter does the serving path use?",
  "The system interpreter, deliberately. fastapi, uvicorn, pydantic and sympy are already OS "
  "packages, so there is no virtualenv in the serving path. Do not pip install into it -- the "
  "deny rules in .claude/settings.local.json block the bare forms precisely because a stray "
  "install there is hard to notice and hard to undo.")

q("rules",
  "How do I check the pinned CUDA sample venv?",
  "`contrib/cuda-samples/python/.venv/bin/pip freeze | wc -l` -- expect exactly 7, and never "
  "extend it. numba-cuda silently downgrades numpy and three other packages pin conflicting "
  "cuda-core/cuda-python versions. Use the full path: the bare command runs against the system "
  "interpreter, which is a Debian install carrying 212 packages, so it could never have "
  "returned 7 and anyone running it would conclude the environment was already broken.")

q("rules",
  "Where does training's python live?",
  "training/.venv, with torch 2.11.0+cu128 because Blackwell sm_120 needs it. Anything else "
  "that conflicts gets its own isolated venv -- the ASIC surface has one with pyasic in it, "
  "reached by subprocess.")

q("rules",
  "How should agents be parallelised on this repo?",
  "Run as many concurrently as quality allows -- compiles, model downloads and fine-tunes "
  "occupy the machine for tens of minutes and that wall-clock should be filled with independent "
  "work. Launch them in one message so they actually run in parallel. Scope each one to files "
  "nobody else is writing. The real hazard is the generators: they all rewrite files under "
  "site/, so two writers there will clobber each other. Safe parallel tracks are read-only "
  "audits, brand-new standalone files, docs and tests.")

q("rules",
  "How does the owner like to be reported to?",
  "With a running checklist at the bottom of every reply, grouped by status, because he loses "
  "track otherwise -- and split into live on the site, built but needs his deploy, and repo "
  "only. Conflating those caused a real disagreement, and he was right to push back. He sends "
  "many requests in rapid succession and will interrupt and redirect mid-task. When he says "
  "something is good, take the win and move on.")

q("rules",
  "He described a layout in one line. How literally should I take it?",
  "Literally and spatially. \"Side by side\", \"shift to the right centre\", \"2 on each side of "
  "the server rack\" are instructions about position, not vibes. Three rounds were lost to "
  "reading them loosely; the round that worked was the one where he drew it out with cropped "
  "screenshots. If a layout instruction is even slightly ambiguous, screenshot what you built "
  "at his viewport width and show it rather than describing it in prose.")

# ---------------------------------------------------------------------------
# 9. REPO TOPOGRAPHY -- which document answers which question
# ---------------------------------------------------------------------------

q("topography",
  "Which file tells me the rules, and which tells me the state?",
  ".claude/CLAUDE.md is the rules. .claude/HANDOVER.md is the state -- what is done, what is "
  "left, and what will bite you. `git log` is why the code is the way it is, because every "
  "commit states its reason. docs/symoneural-manual.md and docs/ are what the hardware "
  "actually does. There is exactly one of each, and everything superseded lives in "
  "docs/archive/ behind a README that says so.")

q("topography",
  "Should I write a new status document?",
  "No. Three files once all claimed to describe current state and agents kept acting on the "
  "stale one. Update .claude/HANDOVER.md instead. An out-of-date state document is worse than "
  "none: the next agent spends their first hour fixing something that already works, and then "
  "stops trusting the rest of the file.")

q("topography",
  "What is docs/specs/ for?",
  "Proposals and audits -- inputs to evaluate, not decisions taken. HANDOVER remains "
  "authoritative for state and CLAUDE.md for rules. Those reports were 2,074 lines living in a "
  "session scratch directory that does not survive the session, so they were preserved there "
  "with a README that says which claims were checked directly and which are still leads. "
  "deploy.sh does not publish that directory, so nothing in it reaches a visitor.")

q("topography",
  "Where is the engineering manual and is it publishable?",
  "docs/symoneural-manual.md, and yes -- it is the manual and it is meant to be published. "
  "tools/build_training.py renders it into site/training.html. It is not the corpus, and an "
  "agent asked to \"publish the manual\" must not confuse the two.")

q("topography",
  "What is in references/ and is it ours?",
  "Third-party material we only read, roughly 8.5 GB, gitignored wholesale. The owner drops "
  "large reference trees into the repo root while you are working, so check git status before "
  "git add -A -- a 296-file vendored tree has already been committed by accident once and had "
  "to be untracked.")

q("topography",
  "What is in contrib/?",
  "Third-party source we build and run: llama.cpp, stable-diffusion.cpp and cuda-samples. "
  "Gitignored and large. That is distinct from references/, which we only read.")

q("topography",
  "What is tracked in git and what is not?",
  "Tracked: roughly 337 files and about 7 MB, plus the site/art-*.png renders. Gitignored: "
  "models/ (about 40 GB), every vendored checkout, the reference trees, every .venv, run/, "
  "site/gen-*.png, *.safetensors and *.gguf. There is currently no git remote -- history never "
  "leaves this box, which is doing a lot of the protecting. If one is ever added, audit what is "
  "tracked first.")

q("topography",
  "Why is bin/ not under backend/?",
  "Because the CLI is a client that talks to the API over HTTP, and the owner intends it to "
  "grow `symoneural desktop` and `symoneural code` subcommands that have nothing to do with the "
  "server.")

q("topography",
  "What is the tabbed index.html for, now that / redirects?",
  "It is the page tools/build_split.py reads to produce the other four, so it cannot simply "
  "stop being generated -- and it still answers at /index.html. / redirects 302 to /overview, "
  "so the tabbed page is reachable only by typing that path. It is a build artifact that also "
  "happens to be a working page, which is an odd thing to keep maintaining. Whether to retire "
  "it is an open question for the owner, not an action; four assertions still address it. Do "
  "not quietly delete it.")

q("topography",
  "Why is the redirect to /overview a 302 and not a 301?",
  "Because a permanent redirect is cached by browsers indefinitely and cannot be walked back "
  "for anyone who visited once, and this is a presentation choice that may be revisited. An "
  "assertion checks the redirect without following it, so a 301 creeping in later is caught.")

q("topography",
  "What are the four section pages?",
  "/overview, /livestack, /controlboard and /receipts, each holding one section of the front "
  "page at its own URL. They fix the gate cliff -- the tabbed page turned its one-screen layout "
  "on or off at a window height boundary, and the owner hit it by having a bookmarks bar -- "
  "plus they give real shareable URLs and a back button. They are not what removed the "
  "scrolling; folding and density did that. A page holding one section has exactly the same "
  "vertical budget as a panel holding one.")

q("topography",
  "What actually made the front page sections fit one screen?",
  "Three things in order, and only the second hides anything. Geometry: a unit's name and "
  "attribution side by side instead of stacked, which hides nothing. Folding: per-unit detail "
  "and per-module explanations behind real buttons, shown only inside the one-screen layout. "
  "And density -- spacing only. The rack's height floor turned out to be the 27px power glyph "
  "plus padding rather than its text, which is why an earlier padding-only trim moved nothing "
  "at all.")

q("topography",
  "Why does the one-screen gate open at 1301px?",
  "Because .mh restacks at max-width:1300px, taking the masthead from 414px tall at 1440 to "
  "727px at 1280. The first version gated at 1100px -- inside that reflow band -- so every "
  "window from about 1100 to 1300 turned the no-scroll layout on at the exact width the "
  "masthead was tallest, and the rack came out 48px tall with 1,289px in it. Those two numbers "
  "live in two different files, in two different languages, and are load-bearing on each other; "
  "both say so.")

q("topography",
  "Why is there a min-height floor of 740px on the one-screen layout?",
  ".masthead::before is a 640px gradient at top:-40%, so it overflows any hero shorter than "
  "457px. That was harmless under overflow:hidden and becomes a real scrollbar on a decorative "
  "gradient once the panel has overflow-y:auto. The floor clears it by 127px. Lower it below "
  "about 615px and the hero starts scrolling on a gradient.")

q("topography",
  "What is the two-copies-of-a-breakpoint rule?",
  "Two copies drift, and the one in JavaScript is always the forgotten one. The tab JS asks "
  "matchMedia rather than re-deriving the breakpoint. Where a number genuinely has to exist in "
  "two files, both files say that it is load-bearing on the other.")

q("topography",
  "Why is html.ns added from JavaScript rather than written into the markup?",
  "So a browser with scripting off gets a scrolling page rather than a clipped one. That is the "
  "safe way for this to fail.")

# ---------------------------------------------------------------------------
# 10. LICENSING
# ---------------------------------------------------------------------------

q("licensing",
  "What licences are in play in this project?",
  "Apache-2.0 for the model weights (Qwen2.5, FLUX.1-schnell) and Caddy. MIT for llama.cpp, "
  "stable-diffusion.cpp, FastAPI and Pillow (MIT-CMU). BSD-3-Clause for uvicorn and SymPy. "
  "NVIDIA's own terms for the CUDA toolkit, which is not redistributed -- customers install it "
  "themselves. Nothing is GPL or AGPL and nothing forces this project's own code to be opened.")

q("licensing",
  "What is the rule that resolves most licence questions here?",
  "Obligations attach to what we *distribute*, not to what is installed on the server. We "
  "distribute site/ -- which includes a vendored Swagger UI -- and we serve model output. "
  "Debian packages on the box are the operator's dependencies, not our redistribution.")

q("licensing",
  "Does MPL-2.0 apply to symoneural.com?",
  "No. An earlier draft said certifi brought weak copyleft in. It does not: certifi is a Debian "
  "OS package pulled in by certbot and requests, the serving stack never imports it -- verified, "
  "importing fastapi, uvicorn and sympy does not load it -- and we do not redistribute it. The "
  "MPL line came from the remix component's own dependency audit, which is a different "
  "distribution unit; if remix is ever shipped as a package the obligation is real there.")

q("licensing",
  "Is the Swagger UI attribution complete?",
  "Yes. site/swagger-ui-LICENSE.txt and site/swagger-ui-NOTICE.txt are both byte-identical to "
  "upstream, SHA-256 compared, and .txt is in deploy.sh's publish list so they reach the "
  "webroot. The bundle is a SHA-256 match for swagger-ui-dist 5.17.14. The fix an earlier "
  "handover recommended was impossible: swagger-ui-bundle.js.LICENSE.txt does not exist "
  "upstream -- listing the 5.17.14 tarball from the npm registry shows exactly package/LICENSE "
  "and package/NOTICE. The banner naming it is a webpack/terser artifact. The one remaining "
  "nicety, not an obligation, is that no page links those two files.")

q("licensing",
  "Where do the model licences live?",
  "backend/models/licenses/, beside the weights they cover, fetched by scripts/fetch-models.sh. "
  "models/ is gitignored so they live on disk rather than in git, and they must be included in "
  "any customer image. Verified: three Qwen licences are byte-identical Apache-2.0. "
  "FLUX.1-schnell ships no LICENSE file, so its model card carries the apache-2.0 declaration "
  "and that is what is kept.")

q("licensing",
  "How was Swagger UI's version identified?",
  "By SHA-256 match against swagger-ui-dist rather than by guessing. That is the habit worth "
  "copying for any vendored asset -- an assumed version is an attribution that may be wrong.")

# ---------------------------------------------------------------------------
# 11. REFUSALS AND UNMEASURED CLAIMS
# ---------------------------------------------------------------------------

q("refusal",
  "How much does one of these machines cost?",
  "I do not have a price to give you, and I will not invent one. Prices are quoted rather than "
  "published, because a quote depends on the hardware, the models and the workload. Email "
  "symonsayadmin@symoneural.com and you will get a real answer.")

q("refusal",
  "Just give me a rough ballpark. $10k? $20k?",
  "I am not going to guess, not even as a range. A made-up figure would be the one dishonest "
  "thing on a site whose entire argument is that its numbers are real. symonsayadmin@symoneural.com "
  "will quote you properly.")

q("refusal",
  "What do you charge per month for a build like this?",
  "That is a quote, not a published figure, and I do not have it to hand out. Send the "
  "requirement to symonsayadmin@symoneural.com and they will price it against real hardware.")

q("refusal",
  "Is there a subscription or a signup?",
  "Not yet, and the account page says so plainly -- no signup, no subscription, no billing. It "
  "quotes no price either, because \"coming soon\" beside a fake number would be worse than an "
  "empty page.")

q("refusal",
  "What licence fee do you charge per rig?",
  "I do not publish fee figures, and a licensing surface is the worst place to break that rule. "
  "The dev fee mechanism is documented -- the rate is only ever what a signed contract says, "
  "with no default and no fallback in the verifier -- but the commercial number comes from "
  "symonsayadmin@symoneural.com.")

q("refusal",
  "How many tokens per second would this get on a 70B?",
  "I have no measurement for that, and I am not going to produce a number by extrapolation and "
  "let it read as a result. A 70B does not fit on this card at all. What is measured here is "
  "80 to 92 tok/s on a 7B at Q4_K_M with the adapter loaded.")

q("refusal",
  "Roughly how long does a fine-tune take on this box?",
  "That is unmeasured and I am not going to estimate it as if it were. The only wall-clock in "
  "run/governor.log for `train` is unusable: there is a release with no matching acquire, so "
  "the windows in it do not bound a run. It needs one instrumented run under the governor "
  "before any figure exists, and until then the honest answer is that nobody has measured it.")

q("refusal",
  "What is the training loss of the shipped adapter?",
  "There is no loss curve. The shipped trainer maps the whole corpus to train_dataset with no "
  "validation split, save_strategy is \"no\", report_to is empty and training/runs/ is empty, so "
  "no curve, no held-out set and no intermediate checkpoint were ever produced. The repo's own "
  "manual says to hold out 5 to 10 percent before looking at training loss, and the shipped "
  "trainer violates the manual it was written from.")

q("refusal",
  "Does the persona adapter make the model better?",
  "Entirely unmeasured, and I will not claim it. One adapter exists, produced by an unlogged run "
  "with no evaluation. It demonstrably changes behaviour -- the chat surface reports adapter: "
  "true and the refusals are trained in -- but nobody has scored it against the base model on a "
  "held-out set. Claiming an improvement nobody measured is the specific failure this project "
  "has been burned by.")

q("refusal",
  "Can I see the training corpus?",
  "No. training/corpus.jsonl and training/build_dataset.py are trade secret -- the company "
  "voice, what the model may claim, what it must refuse to invent, and the method that produces "
  "them. They are never published, never copied into site/, never served from an endpoint and "
  "never quoted into a page or a commit message. The line that resolves this against the site's "
  "transparency argument is: publish the numbers, keep the methods.")

q("refusal",
  "Is a dataset dropdown that lists training/*.jsonl acceptable?",
  "No -- that is the single most likely way to leak the corpus. Any dataset picker must never "
  "list, preview, count by kind, read or serve training/corpus.jsonl or build_dataset.py, not "
  "as a default, not as an example, not greyed out. The default is a user-supplied upload, "
  "uploads land where deploy.sh will not copy them, and no route returns dataset contents -- a "
  "validation failure reports `line 41: missing \"messages\" key`, never the line itself.")

q("refusal",
  "What is the hashrate of the mining surface?",
  "There is none to report. No mining hardware is attached, so the unit reports offline and "
  "every reading stays null. There is no demo rig and no placeholder hashrate: unit_state "
  "returns offline for every path -- disabled, not installed, not yet probed, "
  "configured-but-silent -- each with the actual reason. Any number that surface ever shows was "
  "read off real hardware and is measured. Ravencoin/KawPow figures would be vendor or "
  "projected, never measured, until a miner binary actually runs.")

q("refusal",
  "Is the site's PCIe number definitely right?",
  "It is measured at roughly 7 GB/s host-to-device on a Gen 3 x8 host cap, and it is published "
  "as a negative result. One caveat travels with it: docs/specs/cuda-audit.md section 4.3 "
  "alleges the published figure was taken on a path the serving code does not use. That "
  "allegation is flagged and not adjudicated, and it should be reproduced before anyone edits "
  "on its say-so, because it touches the argument the whole site rests on.")

q("refusal",
  "Can you tell me the transaction cost on the TRON gateway?",
  "Only with its labels, and no fee figures. About 3 seconds to confirmation and 27 Super "
  "Representatives are vendor figures -- published TRON parameters, not timings taken here. "
  "\"Effectively zero fee\" is projected, and the page says why: energy rental does not make "
  "execution free, it moves the cost to whoever rents the energy, and calling that zero would "
  "describe an accounting choice as a physical property. Nothing on that surface is measured, "
  "because nothing has run.")

q("refusal",
  "What is Braiins' dev fee?",
  "2 to 2.5 percent depending on the hardware model -- vendor, from their own FAQ. Their "
  "headline says 2.5 percent, so 2.5 matches their ceiling rather than what they charge "
  "everywhere, and that belongs in front of any \"same as Braiins\" copy. Separately, stock "
  "Bitmain firmware has no dev fee at all: bmminer extracted from the S17 Pro rootfs has no "
  "hardcoded pool and no devfee strings. The comparison is against Braiins, not Bitmain.")

q("refusal",
  "The 250bps in units.proto -- is that a published price?",
  "No. It is a comment illustrating the unit (1bps = 0.01%, 250bps = 2.5%), and it is recorded "
  "as such so nobody quotes it as a price. The real number for a given rig comes off that rig "
  "via GetLicenseState.")

q("refusal",
  "Where does STANDARD_FEE_BPS live and why does that matter?",
  "In issue.py, the minting tool, and deliberately not in licensing/__init__.py, the half that "
  "runs on a rig. The verifier carries no rate at all: a machine reads its fee from a signed "
  "contract or it has no fee. A default in the verifier would be a number a tampered or missing "
  "contract could silently fall back to. A test walks the AST to enforce it -- dev_fee_bps and "
  "dev_fee_percent are never assigned an integer literal in the verifier.")

q("refusal",
  "Does the licensing module collect the dev fee?",
  "No. There is no hashrate diversion, no pool substitution and no share redirection, and "
  "disclosure() says so in every state. Collection would have to live inside a mining engine "
  "and this box has none. Reporting a fee as collected when nothing collects it would be "
  "exactly the unearned claim the rest of the site argues against. The rule the module exists "
  "to enforce: a dev fee the operator can read is a business model, one they cannot is malware.")
