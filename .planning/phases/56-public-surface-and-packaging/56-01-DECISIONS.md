# 56-01 decisions: D5, D6, D7

Decided by Anentropic on 2026-10-16, taking all three recommendations (the "All three"
option), with the two defaults stated alongside them.

## D5: a `SemolinaError` base (API-03)

Before: five Semolina errors (`SemolinaViewNotFoundError`, `SemolinaConnectionError`,
`SemolinaMissingDependencyError`, `SemolinaSchemaMismatchError`,
`SemolinaResultConsumedError`) each subclass `RuntimeError` directly, with no common base.
`get_engine` raises a plain `ValueError` for an unregistered name.

Decided:
- `SemolinaError(Exception)` in `semolina.exceptions`. The five errors derive from it and
  keep `RuntimeError`, so every existing `except` clause still matches.
- The two engine errors move to `exceptions.py`; `engines.base` re-exports them.
- `get_engine` / `get_async_engine` raise `SemolinaEngineNotRegisteredError(SemolinaError,
  ValueError)`, so `except ValueError` keeps working.
- Plain bad-argument `ValueError`/`TypeError` raises (about 84 sites) stay as they are.
  The requirement reads "every Semolina-specific error", not every exception Semolina raises.

## D6: a `[cli]` extra (API-06)

Before: `typer`, `rich`, `jinja2` and `griffelib` are base dependencies, about 9 MB with
their own, used only by the `semolina` command.

Decided: all four move to `semolina[cli]`. The console script stays installed. Without the
extra it prints `pip install "semolina[cli]"` and exits non-zero with no traceback.
`import semolina` imports none of them, and a test pins that. This breaks
`pip install semolina && semolina codegen` for 0.6.0 users, so the 0.7.0 release notes lead
with it.

## D7: one thing called `Dialect` (API-04)

Before: `semolina.Dialect` is the user-facing enum; `semolina.engines.sql.Dialect` is the
SQL-generation ABC, also exported as `DialectABC`. `to_sql()` defaults to Snowflake even
when `.using()` names a DuckDB engine.

Decided:
- The ABC is renamed `SQLDialect`. `engines.sql.Dialect` and `DialectABC` stay as aliases
  for one release. The enum keeps the name `Dialect`.
- `to_sql()` with no argument uses the dialect of the engine `.using()` names when that
  engine is registered. When that engine is not registered it falls back to Snowflake
  rather than raising, so a SQL preview never fails just because the engine is not set up
  yet. With no `.using()` the default stays Snowflake, as decided; this phase does not
  extend the rule to the `default` engine.
