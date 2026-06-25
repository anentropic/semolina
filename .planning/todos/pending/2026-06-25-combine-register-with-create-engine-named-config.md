---
created: 2026-06-25T00:00:00.000Z
title: Reduce register()/create_engine() redundancy for named-config registration
area: api
files: [src/semolina/engines/, src/semolina/registry.py, src/semolina/config.py, docs/src/how-to, docs/src/tutorials]
---

## Problem

The documented pattern for the common case — register a default engine from a
named config in `.semolina.toml` — reads as redundant:

    register("default", create_engine("default"))  # reads .semolina.toml

The name `"default"` appears twice, and the reader has to understand that the
string passed to `create_engine` is a *config section name* while the string
passed to `register` is a *registry key* — even though in the overwhelmingly
common case they're deliberately the same value.

## Desired outcome

A principled, less repetitive way to register-from-named-config, **without**
sacrificing the other `create_engine` patterns we support:

- `create_engine("name")` — build from a named `.semolina.toml` section
- `create_engine(config_obj)` — build from an explicit config object
  (`SnowflakeConfig` / `DatabricksConfig` / `DuckDBConfig`)

Both must still produce a standalone (unregistered) Engine, since not every
caller wants the global registry.

## Candidate directions (decide during planning)

1. **`register_engine(name, /, **kwargs)` convenience** — one call that builds
   *and* registers: `register_engine("default")` reads the `default` config
   section and registers under the same key; `register_engine("default",
   config=cfg)` registers an explicit config under a chosen key. Keeps
   `create_engine` + `register` as the explicit two-step primitives underneath.
2. **`create_engine(..., register=True | "name")`** — opt-in registration as a
   keyword on the existing factory. Reads well for the same-name case
   (`create_engine("default", register=True)`) but overloads one function with
   two responsibilities (construction + global side effect).
3. **`Engine.register(name=None)` method** — `create_engine("default").register()`
   defaults the registry key to the config name the engine was built from
   (requires the Engine to retain its source-config name). Chains nicely; the
   no-arg default removes the duplicated string.

Lean toward whichever keeps a single obvious way to do the common thing while
leaving the explicit primitives intact (Zen-of-Python "one obvious way", but
don't break the power-user paths). Option 1 or 3 look most principled; 2 mixes
concerns.

## Constraints / notes

- Must not reintroduce the old `(pool, dialect)` tuple registry — the v0.6
  model is `register("name", engine)` / `get_engine`. See
  [[project_v06_engine_owns_pool]].
- Whatever lands, update the connection how-to + tutorial examples (this is the
  first snippet new users copy) and the docstrings. Apply the
  semolina-docs-author skill.
- Pre-1.0, so a clean break / rename of the ergonomic surface is acceptable if
  it's clearly better; keep the low-level primitives stable.

Source: user flagged the `register("default", create_engine("default"))` doc
example as redundant (2026-06-25) and asked for a principled combine.
