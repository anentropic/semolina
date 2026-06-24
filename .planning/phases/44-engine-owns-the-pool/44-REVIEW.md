---
phase: 44-engine-owns-the-pool
reviewed: 2026-06-24T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - src/semolina/__init__.py
  - src/semolina/config.py
  - src/semolina/registry.py
  - src/semolina/query.py
  - src/semolina/cli/codegen.py
  - src/semolina/conftest.py
  - src/semolina/engines/base.py
  - src/semolina/engines/snowflake.py
  - src/semolina/engines/duckdb.py
  - src/semolina/engines/databricks.py
  - src/semolina/cursor.py
  - scripts/spike_databricks_adbc_introspect.py
  - tests/conftest.py
  - tests/integration/conftest.py
  - tests/unit/test_config.py
  - tests/unit/test_registry.py
  - tests/unit/test_pool.py
  - tests/unit/test_query.py
  - tests/unit/test_cursor.py
  - tests/unit/test_snowflake_engine.py
  - tests/unit/test_duckdb_engine.py
  - tests/unit/test_databricks_engine.py
  - tests/unit/codegen/test_cli.py
  - tests/unit/codegen/test_codegen_e2e.py
findings:
  critical: 1
  warning: 0
  info: 3
  total: 4
status: issues_found
---

# Phase 44: Code Review Report

**Reviewed:** 2026-06-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23 (+ `README.md`, `tests/integration/cassettes/README.md` cross-referenced)
**Status:** issues_found

## Summary

Second re-review of Phase 44 ("Engine owns the pool"). The five fix commits were
verified against the current source, and **every prior Warning fix is genuinely
correct and complete** — none are re-raised:

- **CR-01 (prior BLOCKER, execute error path)** — confirmed fixed at
  `engines/base.py:173-184`: `conn.cursor()` + `cur.execute()` are wrapped in
  `except BaseException: conn.close(); raise`, returning the slot before
  propagating. Backed by two regression tests (`test_pool.py:382-412`).
- **WR-01 (`SemolinaCursor.__del__`)** — `cursor.py:295-313` guards a partial
  `__init__` (`getattr(self, "_closed", True)` and `getattr(self, "_conn", None)`),
  is idempotent (sets `self._closed = True`), and never raises
  (`contextlib.suppress(Exception)`). Verified by `test_cursor.py:327-368` covering
  the leaked-conn, double-close, and partial-init paths.
- **WR-02 (`connect()` contracts)** — `base.py:88-114` now documents both the
  context-manager and long-lived-handle consumption modes plus the execute()
  error-path responsibility.
- **WR-03 / WR-04 (`_resolve_section` dedup)** — `config.py:68-119` extracts the
  shared TOML-read+validate helper; `_read_connection` (`:236-262`) delegates to
  it. The `type`-pop, missing-`type`, and unsupported-`type` behaviors are
  preserved and still covered by `test_config.py:141-201`. `pool_from_config` is
  deleted from `config.py` (confirmed by grep — no remaining definition).
- **WR-05 (`_sql_str_literal`)** — defined at `duckdb.py:42-59` and **actually
  called at all four `semantic_view('...')` interpolation sites**: `view_literal`
  (`:200`), `dim_list` (`:205`), `metric_list` (`:209`), and `fact_list` (`:220`).
  Directly tested in `test_duckdb_engine.py:161-181`. Complete.
- **WR-06 (`Engine.dispose()` + narrowed `reset()` suppression)** — `base.py:116-136`
  routes ADBC pools through `close_pool` (gated on `hasattr(pool, "_adbc_source")`)
  and falls back to `pool.close()`; `registry.reset()` (`:103-110`) now suppresses
  only `OSError`/`RuntimeError`, so genuine programming errors propagate. Tested in
  `test_pool.py:415-443` and `test_registry.py:131-141`.

No new BLOCKER was introduced **inside the reviewed source files**. However, the
Phase 44 API surgery (removal of `pool_from_config` and the 3-arg `register`)
broke the **`README.md` quick-start example**, which still imports and calls the
deleted symbols. That is a shipping defect for the primary onboarding doc and is
classified Critical (CR-02). The remaining items are the carried-forward Info
findings: two are still present (IN-01 stale doc references, IN-04 `__version__`
idiom), one is order-fragile-by-coincidence (IN-03), and IN-02 is **resolved** by
the `pool_from_config` deletion.

Security posture remains sound: `SecretStr` is preserved end-to-end, the spike
unwraps the token only at the native connect boundary and never prints it, replay
cassettes use placeholder credentials, and `_sql_str_literal` now hardens the only
string-interpolated SQL path.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-02: `README.md` quick-start uses the deleted `pool_from_config` / 3-arg `register` API

**File:** `README.md:35-38` (and the `cursor` example at `README.md:44-50`)
**Issue:** Phase 44 removed `pool_from_config` from `config.py` and replaced the
3-arg `register(name, pool, dialect=...)` with the 2-arg `register(name, engine)`
that takes an `Engine` from `create_engine`. The README quick-start — the first
runnable example a new user copies — still shows the removed API:

```python
from semolina import register, pool_from_config

pool, dialect = pool_from_config()  # reads .semolina.toml
register("default", pool, dialect=dialect)
```

`pool_from_config` is no longer exported from `semolina/__init__.py` (the public
`__all__` lists only `create_engine`, `get_engine`, `register`, `unregister`), so
the import raises `ImportError` and the call cannot resolve. `register("default",
pool, dialect=dialect)` also no longer matches the 2-arg signature. A user
following the README cannot get past registration. This is a correctness defect in
shipped user-facing material caused directly by the reviewed Phase 44 changes,
hence Critical rather than Info.

**Fix:** Update the README to the Phase 44 API and add the missing `cursor.close()`
(or context manager) so the documented happy path does not leak a pooled
connection:

```python
from semolina import create_engine, register

engine = create_engine("default")  # reads [connections.default] from .semolina.toml
register("default", engine)

with (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
) as cursor:
    for row in cursor.fetchall_rows():
        print(row.country, row.revenue)
```

(Per the project docs skill, a README rewrite of this connection section should run
the `semolina-docs-author` workflow.)

## Info

### IN-01: Stale `pool_from_config` references in docstrings and the cassettes README

**File:** `tests/integration/conftest.py:22`; `tests/integration/cassettes/README.md:16`
**Issue:** Both still cross-reference the deleted symbol. `conftest.py:22` reads
"see :func:`semolina.config.pool_from_config`" in the module docstring; the
cassettes README points at the same removed function. These are dangling Sphinx
xref targets / dead pointers — harmless at runtime but misleading, and a broken
`:func:` link in any rendered docs. (Carried forward from prior IN-01 and
re-confirmed; the prior review flagged "and possibly cassettes/README" — confirmed
present in both.)
**Fix:** Replace both references with `semolina.config.warehouse_config` (the
function that now resolves a config from `[connections.<backend>]` + env), which is
what the recording fixtures actually call.

### IN-03: `_dialect_for_config_type` reverse lookup is correct-by-coincidence and order-fragile

**File:** `src/semolina/config.py:139-145`
**Issue:** The reverse lookup iterates `_CONFIG_MAP.values()` and returns on the
first `isinstance(config, config_cls)` match. This is correct only while the three
poolhouse config classes (`SnowflakeConfig`, `DatabricksConfig`, `DuckDBConfig`)
remain mutually non-subclassing. If a future config class ever subclasses another
(or a shared base is added to `_CONFIG_MAP`), `isinstance` would match the first
*compatible* entry by dict-insertion order rather than the exact type, silently
selecting the wrong dialect. The forward TOML path keys by exact `type` string and
has no such fragility.
**Fix:** Match on exact type to remove the ordering dependency:
```python
dialect_by_cls = {cls: dialect for cls, dialect in _CONFIG_MAP.values()}
dialect = dialect_by_cls.get(type(config))
if dialect is None:
    supported = [cls.__name__ for cls, _ in _CONFIG_MAP.values()]
    raise ValueError(
        f"Unsupported config type '{type(config).__name__}'. Supported configs: {supported}"
    )
return dialect
```

### IN-04: `__version__` uses the obscure `__import__("importlib.metadata")` idiom

**File:** `src/semolina/__init__.py:18`
**Issue:** `__version__ = __import__("importlib.metadata").metadata.version("semolina")`
relies on the rarely-used `__import__` builtin and its quirk of returning the
top-level `importlib` package (not the `importlib.metadata` submodule) — it only
works because `.metadata` is then re-accessed off `importlib`. This is a
readability/maintainability wart, not a bug (it resolves correctly), and a likely
linter target (ruff prefers a real import).
**Fix:** Use a normal import:
```python
from importlib.metadata import version

__version__ = version("semolina")
```

---

## Re-assessment of carried-forward findings (resolved — not re-raised)

- **IN-02 (`create_engine` / `pool_from_config` duplicated the DuckDB connect-listener
  wiring):** **RESOLVED.** `pool_from_config` is deleted, so the duplication is gone.
  The connect-listener wiring now lives only in `create_engine`
  (`config.py:226-229`). The fixture-side `event.listen(engine._pool, "connect", ...)`
  calls in `conftest.py` / test helpers attach *test-data* listeners, not a second
  copy of the extension-load wiring — not a duplication.

_All five prior Warnings (WR-01..WR-06) verified fixed and correct; see Summary._

---

_Reviewed: 2026-06-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
