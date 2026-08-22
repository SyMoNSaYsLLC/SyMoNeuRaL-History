# backend/vendor — what is here, where it came from, and what was refused

Written by `tools/index_references.py vendor`. Do not hand-edit: it is regenerated, and a
hand-added row would be a claim nobody read a licence file to make.

**10 vendored, 2 refused**, out of 12 directories under
`references/` whose name contains `sdk`.

`references/` is `/references` in `.gitignore`, so none of this was version-controlled by us
before. These copies are.

## Vendored

| repo | licence | upstream | commit |
|---|---|---|---|
| `anthropics/agent-sdk-workshop` | Apache-2.0 | [agent-sdk-workshop](https://github.com/anthropics/agent-sdk-workshop.git) | `a273fbe` |
| `anthropics/anthropic-sdk-csharp` | MIT | [anthropic-sdk-csharp](https://github.com/anthropics/anthropic-sdk-csharp.git) | `da57c281` |
| `anthropics/anthropic-sdk-go` | MIT | [anthropic-sdk-go](https://github.com/anthropics/anthropic-sdk-go.git) | `da00f43` |
| `anthropics/anthropic-sdk-java` | MIT | [anthropic-sdk-java](https://github.com/anthropics/anthropic-sdk-java.git) | `8f5861c8` |
| `anthropics/anthropic-sdk-php` | MIT | [anthropic-sdk-php](https://github.com/anthropics/anthropic-sdk-php.git) | `475a1345` |
| `anthropics/anthropic-sdk-python` | MIT | [anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python.git) | `23cf4583` |
| `anthropics/anthropic-sdk-ruby` | MIT | [anthropic-sdk-ruby](https://github.com/anthropics/anthropic-sdk-ruby.git) | `1e1bd2f4` |
| `anthropics/anthropic-sdk-typescript` | MIT | [anthropic-sdk-typescript](https://github.com/anthropics/anthropic-sdk-typescript.git) | `bfa9197f` |
| `anthropics/claude-agent-sdk-python` | MIT | [claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python.git) | `22795fe` |
| `openai/apps-sdk-ui` | MIT | [apps-sdk-ui](https://github.com/openai/apps-sdk-ui.git) | `0f00143` |

Each tree is copied with its `.git` stripped, its `LICENSE` kept, and the build/dependency
directories in `PRUNE` left behind — `node_modules`, `target`, `dist`, `.venv` and the rest.
The upstream commit above is the coordinate that makes a copy checkable; without it a
vendored tree cannot be diffed against anything, updated deliberately, or checked against an
advisory.

## Refused, and why

An absent licence is **not** a permissive default. Without a grant the default is all rights
reserved, so these are named here rather than copied, and this record is the deliverable for
them:

- **`anthropics/claude-agent-sdk-demos`** — NONE. It ships **no licence file at all**.
- **`anthropics/claude-agent-sdk-typescript`** — ALL-RIGHTS-RESERVED. Its `LICENSE.md` contains *"all rights reserved"*.

`claude-agent-sdk-typescript` is the one to read twice. It *does* ship a licence, and that
licence reserves every right and points at a commercial ToS — so a rule keyed on "has a
LICENSE file" would have vendored it. The grant is what is matched, never the presence of the
file, and never the copyright line, which is identical in an MIT file and in this one.

Two of the refused are repos Garrett named directly when he asked for this. That is recorded
rather than smoothed over: adopting unlicensed code is a decision for him to make knowingly,
and this is where it would be written down if he ever makes it.

## Vendoring is not installing

Copying source gives provenance and version control. It does not give a dependency graph.
`claude-agent-sdk-python` requires `anyio`, `sniffio`, `mcp` and `jsonschema`; none are on
this box's system interpreter, and `.claude/CLAUDE.md` bars `pip install` there because that
is the serving path — fastapi, uvicorn, pydantic and sympy are OS packages and there is no
virtualenv in front of them.

So importing anything here needs its own isolated venv. That rule is already written down
(*"anything else that conflicts gets its own isolated venv"*) and `training/.venv` is the
precedent. Building it is not part of #103; knowing it is required before anybody writes
`import claude_agent_sdk` is.

## Regenerating

```bash
python3 tools/index_references.py vendor      # idempotent -- run twice and diff
git status --porcelain backend/vendor         # .gitignore has unanchored *.log, *.key, *.bak
```

That second line is not optional. `.gitignore` carries `*.log`, `*.bak`, `*.key`,
`*.safetensors`, `*.gguf`, `__pycache__/` and `**/.venv/` with no path anchor, so each one
silently swallows matching files *inside* a vendored tree. A tree that is 90% tracked reads
as complete and is not.
