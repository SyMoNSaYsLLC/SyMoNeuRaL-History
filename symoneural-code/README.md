# symoneural-code

The interactive client and the operator command line for the whole local stack.

**First-party, and tracked** — which is what separates this runtime folder from the five
beside it. `symoneural-llm/`, `symoneural-diffuse/`, `symoneural-listen/`,
`symoneural-miner/` and `symoneural-ui/` are *derived* trees built by
`tools/fork_engines.sh` from vendored upstream source, so they are gitignored and a clone
rebuilds them. Nothing here is derived from anybody. It is ours, it is source, and a clone
carries it.

## What is in here

| Path | |
|---|---|
| `bin/symoneural-cli` | 92 KB of first-party Python. One command over the whole local stack: `status`, `residency`, `chat`, `image`, `ravencalc`, `agent`, `tools`, `state`, `repl`, `mcp`, `upgrade`. |
| `bin/symoneural-code` | the front door to the interactive session — `symoneural-cli repl` with a shorter name and four flags translated. One implementation of a session, reachable two ways. |
| `bin/symoneural-discovery` | runs the discovery application from anywhere. |

`bin/` at the repo root holds symlinks to these three, so every existing invocation and the
39 tracked files that name `bin/symoneural-*` keep working.

## Use it

```bash
bin/symoneural-code                 # open a session
bin/symoneural-code -p "..."        # one turn, print the answer, exit -- pipeable
bin/symoneural-code -c              # continue the most recent thread
bin/symoneural-code --sessions      # list what there is to resume
bin/symoneural-cli status           # the whole stack, measured
```

The window version is `desktop/shell.py`: a GTK3 window with a VTE terminal running
`bin/symoneural-code` on a real pty.

## Root resolution — the reason this folder exists at all

Moving this client here broke it, immediately and loudly:

```
assert (ROOT / "backend" / "api.py").is_file()   #  ROOT = HERE.parent
AssertionError: repo root not found at /home/google/Symoneural/symoneural-code
```

`ROOT = HERE.parent` encodes the file's *depth in the tree*, so every move is a breaking
change. Its own comment already said the calculation *"has been wrong four times in this
repo"*; the promotion made it five. It now walks up until it finds `backend/api.py`, which
encodes what the root **is** rather than where this file happens to sit.

`bin/symoneural-discovery` had been doing that walk all along. The correct pattern was in
the repo the whole time, one file away from the one that broke.

**152 tracked files still count parents.** `symoneural-audit/` finds them.
