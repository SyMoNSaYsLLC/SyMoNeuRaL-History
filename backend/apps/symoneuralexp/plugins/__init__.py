"""Example plugins -- one file per idea, and they are meant to be read.

    bus.py        provide a service, and revoke it on unmount        module, `apply` function
    clock.py      an async body and the effect that stops its task   module, async `apply`
    echo_llm.py   a service that `intercept` can shape               module, `apply` function
    memory.py     a service worth isolating per session              module, `apply` function
    recorder.py   state whose lifetime is exactly the mount          module, `apply` is a class
    gpu.py        a service that reads the real machine              module, `apply` function
    explode.py    what failure looks like, at three different points module, `apply` function

The Kind column on the page is `registry.describe`'s reading of these same files, and it says
`module` six times and `class` once. That is the whole inventory and it is what a `use:` line
produces: the manifest names a module, so a module is what the registry resolves. The other two
shapes `registry.resolve` accepts -- a bare function, and an object with an `.apply` attribute --
have **no example in this directory**. They are specified in `registry.py`, written up in
`docs/writing-plugins.md`, and asserted in
`test_exp.py::RegistryTests::test_all_four_plugin_shapes_resolve`.

Mechanisms these seven do demonstrate: `ctx.provide` and the disposer it returns, `ctx.effect`
(including an async cleanup that awaits a cancelled task, and one registered before a deliberate
raise), attribute injection (`ctx.bus`), the required/optional dict form of `inject`, `ctx.get`
for a dependency allowed to be absent, `schema` defaults and coercion, and all three points a
mount can fail at.

Mechanisms with no worked example here: `ctx.on` and `Context.emit`, `ctx.plugin` (a plugin that
mounts a child), the `ctx.inject(deps, fn)` callback form, `ctx.extend`, and `ctx.isolate` called
in Python. Two of those are demonstrated on the manifest side instead -- `presets/sessions.yaml`
declares `isolate` and `intercept` -- and `echo_llm.py`'s docstring shows the `intercept` call it
is shaped for. The gap is real; `bus.py` is the file to copy from if you close it.

They are also the fixtures for `test_exp.py` and most of `presets/dev.yaml` (five of the seven --
that file's header names the two it leaves out). That is deliberate: an example that nothing
exercises rots, and an example that is only a fixture reads like one.
"""
from __future__ import annotations

#: What `GET /api/exp/catalogue` offers, in the order the page lists them.
CATALOGUE = ["bus", "clock", "echo_llm", "memory", "recorder", "gpu", "explode"]

__all__ = ["CATALOGUE"]
