# Dependencies — what each one does, what replacing it would cost, and the decision

Task #74 item 5. Garrett's standard, 2026-08-20: *"we should have the goal of rebranding
and/or writing fresh code for everything. You better have a really good and justified reason
for not doing so and this includes what is in the requirements.txt for python modules"*, with
the boundary drawn at *"nvidia sources i understand being locked down as of right now i see
no other sources as 'locked down' and they should be recreated"*.

So **recreate is the default and keeping is what needs an argument.** This file is where the
argument goes. A row with no reason is the failure this document exists to prevent.

**Read the three verdicts as different jobs, because they are.**

- **Recreate** — write ours, delete theirs. Reserved for what is small enough to own and
  central enough to matter.
- **Facade** — the package stays, but no application module names it. The import moves behind
  a module of ours so the vendor name appears in exactly one file per dependency and swapping
  it later is a one-file change. This is the honest answer to "rebrand a library you install
  from PyPI": the import name **is** the package's identity, so the rebranding actually
  available to us is the boundary, not the name.
- **Keep** — named directly, with the cost of replacement written down. Two of these would
  take the site's measured numbers *down*, which is the opposite of the point.

**What no verdict here can do is drop a notice.** MIT, BSD-3-Clause and Apache-2.0 all permit
renaming what we present; none permits removing the copyright notice from the accompanying
materials. `LICENSES.md` is that material. A `recreate` verdict retires a notice legitimately,
because we stop distributing the work; a `facade` verdict does not, because the package is
still installed and still shipped. Do not confuse the two.

## How the versions below were read

Every version is `importlib.metadata.version` on the interpreter that actually runs that
code, read 2026-08-21 at `f3ed5ab`. There is no single environment here and pretending there
is would make the table wrong: the serving path is the **system** interpreter (Debian, 212
packages, no virtualenv on purpose), and training, sigils, asicminer, studio and bento each
have their own venv. The interpreter is named in every row. Nothing in this table was copied
from a lockfile or carried forward.

> **Staleness boundary, audited 2026-08-26.** These are dated host readings, not the current
> install contract. Several requirement lower bounds now differ, training still has no
> tracked declaration/lock, and the Rust/Node/Yocto toolchains are outside this Python
> ledger. See `docs/ops/AUDIT-DEPENDENCY-RUNTIME-2026-08-26.md` and run
> `python3 tools/audit_runtime_dependencies.py` before using this file to prepare a host.

---

## The serving path — system interpreter, no virtualenv

`backend/api.py` deliberately has no `requirements.txt`. fastapi, uvicorn, pydantic and sympy
are already Debian packages, so the serving path installs nothing — which is also why
`.claude/settings.local.json` denies bare `pip install`: a stray install here is hard to
notice and hard to undo.

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `fastapi` | 0.115.11 | MIT | Every route, every dependency injection, the OpenAPI document `/docs` renders from. 54 import sites. | A routing layer, a validation integration and an OpenAPI generator. Weeks, and the first bug in it is a security bug — this is the code that parses attacker-controlled input on a public endpoint. | **Keep** |
| `uvicorn` | 0.32.0 | BSD-3-Clause | The ASGI server. Also the WebSocket upgrade the rack depends on. | Writing an HTTP/1.1 + WebSocket server. Rewriting an ASGI server takes the site's numbers down, not up: the published latencies are partly its. | **Keep** |
| `pydantic` | 2.10.6 | MIT | Request/response models; `Status`, `Unit` and the rack schema. Its Rust core is why validation is not on the latency budget. | A validation layer that is slower than the one being replaced, on the request path. | **Keep** |
| `anyio` | 4.8.0 | MIT | Transitive under fastapi/httpx. Not imported by us directly except once in `studio`. | Nothing to replace — it is not ours to choose. | **Keep** (transitive) |
| `sympy` | 1.13.3 | BSD-3-Clause | RavenCalc's entire engine: `sympify`, `diff`, `integrate`, `limit`, `series`, `simplify`, `solve`, `latex`. | See the section below — this is the one row that deserves more than a cell. | **Facade now, recreate incrementally** |

### The `sympy` row, argued properly

Item 5's standing candidate for this one is **recreate**, on the reasoning that *"RavenCalc is
a thin surface over a handful of calls"*. The surface is thin. The engine is not, and the two
should not be conflated because they sit either side of the same function name.

- `diff` is a recursive descent over an expression tree with a table of rules. Genuinely
  small; a real project, not an impossible one, exactly as item 5 says.
- `sympify`, `latex` and expression printing are parsing and formatting. Also tractable.
- `integrate` is not. Correct symbolic integration is the Risch algorithm plus heuristics, and
  "mostly right" is not a thing a page arguing for measurement can ship — the RavenCalc
  surface's whole claim is *"exact symbolic computation that checks its own work"*. A
  hand-rolled integrator that silently returns a wrong antiderivative is worse for this
  product than a vendor dependency, because it converts a licence question into a truthfulness
  question.
- `solve` has the same shape. `solve(x**5 - x - 1)` has no radical solution and SymPy says so;
  an engine that guessed would be lying on the surface that exists to not lie.

**Decision: facade first, recreate by piece, and never behind the user's back.** The facade is
the part available immediately and it is worth having on its own — `ravencalc.py` is the only
file on this box that names the package, so the boundary already very nearly exists. Recreating
`diff` and the parser behind that boundary is real progress and is measurable. Recreating
`integrate` is a research project and is not scheduled here.

The engine line the surface prints already reflects this: it reads
`RavenCalc (symbolic core 1.13.3)`, which names our product and reports the real version of
what is doing the work, without claiming the version is ours. When a piece is genuinely ours,
that line changes and the change is the evidence.

This is the row most likely to be overruled, and it should be easy to overrule: it is one
verdict in one table, not a decision buried in code.

---

## Per-app dependencies

### `backend/apps/remix/requirements.txt`

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `fastapi`, `uvicorn` | as above | MIT / BSD-3-Clause | The app is mounted into the same ASGI app; these are the serving path's, re-declared. | — | **Keep** |
| `httpx` | 0.28.1 | BSD-3-Clause | Outbound HTTP. 8 import sites across `remix` and `studio`. | An HTTP client with connection pooling, timeouts, TLS verification and redirect handling. The SSRF guard around it is already ours and is the part worth owning. | **Facade** — DONE 2026-08-21: `apps/studio/httpclient.py`, `apps/remix/symoneural_dj/httpclient.py`. Not `http.py`; see below |
| `pillow` | 12.3.0 (sigils venv) | MIT-CMU | Image decode/encode/resize for remix and sigils. | An image codec suite. Decoding attacker-supplied images is the highest-risk parsing on this box; a hand-rolled one is a vulnerability with a schedule. | **Keep** |
| `python-dotenv` | 1.0.1 | BSD-3-Clause | Reads `.env` into the environment. Two import sites. | About forty lines. This is genuinely small enough to own, and owning it removes a dependency from two apps. | **Recreate** — smallest real win in this table |

**The httpx facades are `httpclient.py`, not the `http.py` this table used to specify.**
`apps/remix/pyproject.toml:44` sets `pythonpath = [".", "../.."]`, making `apps/remix` a
`sys.path` root under its own pytest rootdir. A module named `http.py` at a `sys.path` root
shadows the **stdlib** `http` package for everything imported beneath it — httpx included,
since httpx imports `http`. The symptom is a collection error with no obvious cause in a
suite unrelated to the file just added. A literal path in a table is followed exactly, so it
is corrected here rather than annotated.

`backend/apps/test_vendor_facade.py` enforces the three **Facade** verdicts by walking the
tree and reading the AST, not by grepping a file list: `import httpx as _h` is a violation,
`# httpx recomputes it` in a comment is not. `tools/prove_vendor_facade.py` is the red-first
proof (7 breaks, 7 red, no residue); `backend/vendor/SMOKE-vendor-facade.md` is the run.

### `backend/apps/studio/requirements.txt`

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `fastmcp` | 3.4.7 (studio venv) | Apache-2.0 | MCP server plumbing for the Studio agent's tool surface. | Implementing MCP. The protocol is someone else's spec and moves; tracking it is the cost, not the code. | **Facade** — DONE 2026-08-21: `apps/studio/mcpframework.py` |

Studio also imports `playwright`, `beautifulsoup4`, `websockets`, `pyyaml`, `numpy` and the
CUDA stack without declaring them here — see *Undeclared imports*, below.

### `backend/apps/studio/plugins/reinforce/requirements.txt`

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `cuda-python`, `cuda-core`, `cuda-cccl` | pinned ≥13 | NVIDIA proprietary | The CUDA driver/runtime bindings. | Nothing — this is the hardware's own interface. | **Exempt** (Garrett: *"only thing that doesnt get rebranded is CUDA to my knowledge"*) |
| `cupy-cuda13x` | ≥14 | MIT | Array ops on the card for the reinforce plugin. | Writing kernels and a dispatcher. Also: this is why `apps/studio/plugins/reinforce/tests` is excluded from the `apps/` pytest run — cupy is not on the system interpreter and must not be, because that is the serving path. | **Keep** |
| `numpy` | 2.2.4 | BSD-3-Clause | Array primitives, 7 import sites. | An array library. Every measured throughput figure on this box passes through it. | **Keep** |
| `cryptography` | 43.0.0 | Apache-2.0 OR BSD-3-Clause | Key handling for gateway licensing, streamer and studio. 10 import sites. | Implementing cryptographic primitives. **Never recreate this.** A rolled-your-own crypto library is the textbook example of a change that looks like independence and is a vulnerability. | **Keep — and this row is not open for reconsideration** |
| `mpi4py` | ≥4 | BSD-3-Clause | Multi-process collective ops. Nothing that ships imports it — see *Undeclared imports*. | An MPI binding, if it were used. It is not, on a single-GPU box with no `mpirun`. | **Candidate for removal** |
| `pytest`, `httpx` | 8.3.5 / 0.28.1 | MIT / BSD-3-Clause | Test-only. | — | **Keep** (test-only, not shipped) |

### `backend/apps/cryptominer/…PROD…/requirements.txt`

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `python-dotenv` | 1.0.1 | BSD-3-Clause | As above. | As above. | **Recreate** |
| `psutil` | 7.0.0 | BSD-3-Clause | Process and resource inspection for the miner's status line. | The subset used here is a few reads from `/proc`, which is Linux-only and this box is Linux-only. Small enough to own. | **Recreate** — behind the same facade module as the rest of the miner's host reads |

### `deploy/bento/requirements.txt`

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `bentoml` | 1.4.39 (bento venv) | Apache-2.0 | A packaging/serving path that is **not** the live one. 68 packages in its own venv. | Nothing, if it is not used. | **Argue for removal** — the live API is `backend/api.py` behind Caddy. A second serving stack that nothing serves from is 68 packages of attack surface and licence obligation for a path no visitor takes. Removing it is the cheapest verdict in this file and it is a decision, not a cleanup, so it is written here rather than done. |

### Other venvs

| Package | Version | Licence | What it does | What replacing it would cost | Verdict |
|---|---|---|---|---|---|
| `torch` | 2.11.0+cu128 (training venv) | BSD-3-Clause | Fine-tuning. cu128 specifically, because Blackwell sm_120 needs it. | An autograd engine and a CUDA kernel library. This is the clearest **keep** in the table: rewriting it would take the site's measured training numbers down by orders of magnitude. | **Keep** |
| `transformers` / `peft` / `trl` / `datasets` | 5.15.0 / 0.20.0 / 1.10.0 / 5.0.1 (training venv) | Apache-2.0 | The QLoRA pipeline behind `training/`. | Reimplementing LoRA training and the model zoo loaders. | **Keep** |
| `rembg` + `onnxruntime` | 2.0.80 / 1.28.0 (sigils venv) | MIT / MIT | Background removal for sigils. | An ONNX runtime. Note the constraint recorded in `backend/models/NAMES.md`: rembg resolves its model *by name*, which is why `u2net.onnx` is one of the three files deliberately not renamed. | **Keep** |
| `pyasic` | 0.75.0 (asicminer venv) | Apache-2.0 | Talks to ASIC miners over their vendor APIs. | Reimplementing several vendors' undocumented HTTP/socket APIs. The vendor protocol is the dependency, not the package. | **Keep** |
| `playwright` | (studio venv) | Apache-2.0 | Drives system Chrome for the six browser suites and for studio. | A browser automation protocol client. Also note `tests/*.mjs` use the Node build, not this one. | **Keep** (test/tooling, not on the serving path) |

---

## Undeclared imports — the gap this table exposes

Writing one row per declared package surfaced something the declarations hide: several
packages are **imported but declared nowhere**. `beautifulsoup4` (3 sites), `pyyaml`,
`websockets` and `numpy` are imported by `apps/studio` but appear in no `requirements.txt`
that covers it, and `playwright` likewise. They work because they happen to be present in a
venv or on the system interpreter.

That is a supply-chain gap, not a licensing one: an undeclared dependency is a package nobody
reviewed, nobody pinned, and nobody will notice going missing until a surface 500s. It is
recorded here rather than fixed here, because fixing it means editing five requirements files
and that is its own task with its own checks.

Conversely `mpi4py` is declared and no shipped module imports it. Its only appearance in the
tree is inside `plugins/reinforce/tests/`, as a `from mpi4py import MPI` line in a *string*
that the constraint test writes out and runs in a subprocess — and that test skips unless an
`mpirun` binary is present, which on this box it is not. So the package is declared, exercised
only by a test that does not run, and required by nothing that serves. A declared dependency
nothing imports is the same problem as an undeclared one pointed the other way, and it is the
reason its verdict above reads *candidate for removal* rather than *keep*.

## What this file is not

It is not a lockfile and does not pin anything — `requirements.txt` does that. It is the
record of *why* each package is still here, so that "we kept it" is a decision somebody made
on stated grounds rather than the absence of one. Every verdict above is overrulable; the
point is that overruling one now means arguing with a written reason instead of guessing what
the last agent was thinking.
