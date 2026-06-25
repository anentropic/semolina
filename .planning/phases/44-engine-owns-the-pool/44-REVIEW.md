---
phase: 44-engine-owns-the-pool
reviewed: 2026-06-24T11:17:26Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - README.md
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
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 44: Code Review Report (Convergence Re-Review)

**Reviewed:** 2026-06-24T11:17:26Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** clean

## Summary

Convergence re-review of Phase 44 ("Engine owns the pool") after two fix iterations.
Every prior finding was verified as genuinely fixed against the current source, and the
last iteration's four commits (ed267ea README, 88902c8 stale-ref updates, 9590d03
exact-type dialect match, fd7837e version idiom) were checked for new regressions. None
were found. The tree is clean: **0 critical, 0 warning, 0 info**.

### Prior-finding verification (all confirmed fixed)

- **CR-01 (execute error-path leak):** `Engine.execute` (`base.py:173-186`) wraps
  `conn.cursor()` + `cur.execute()` in `try/except BaseException: conn.close(); raise`,
  returning the pooled slot before propagating. Both failure modes are covered by
  `test_pool.py::TestExecuteErrorPathReleasesConnection` (cursor() raising and execute()
  raising). Fixed.
- **CR-02 (README quick-start broke on deleted API):** README now imports only exported
  symbols and uses `create_engine("default")` + `register("default", engine)`. See the
  dedicated regression check below. Fixed.
- **WR-01 (`SemolinaCursor.__del__`):** `cursor.py:295-313` guards partial `__init__`
  via `getattr`, guards double-close via `_closed`, and suppresses all exceptions.
  Covered by `test_cursor.py` leaked-conn / double-close / partial-init tests. Fixed.
- **WR-02 (`connect()` contract docs):** `base.py:88-114` documents both consumption
  modes and `execute`'s error-path responsibility. Fixed.
- **WR-03/04 (`pool_from_config` deletion + `_resolve_section` dedup):** `grep` confirms
  no `pool_from_config` anywhere in `src/` or `docs/`. `_resolve_section`
  (`config.py:68-119`) is the single TOML-read+validate helper, consumed only by
  `_read_connection`. Fixed.
- **WR-05 (`_sql_str_literal` DuckDB escaping):** `duckdb.py:42-59` doubles embedded
  single quotes and is applied at every `semantic_view(...)` interpolation site
  (`view_literal`, `dim_list`, `metric_list`, `fact_list`). Covered by `TestSqlStrLiteral`
  including an injection-payload case. Fixed.
- **WR-06 (`Engine.dispose()` + narrowed `registry.reset()`):** `dispose()`
  (`base.py:116-136`) routes ADBC pools through `close_pool` (gated on
  `hasattr(pool, "_adbc_source")`) and otherwise calls `pool.close()`; `reset()`
  (`registry.py:94-110`) calls `dispose()`, suppresses only `OSError`/`RuntimeError`, and
  always clears the map. Covered by `TestEngineDispose` and
  `test_reset_uses_close_pool_for_adbc_pools`. Fixed.
- **IN-01 (stale refs → `warehouse_config`):** `warehouse_config` exists
  (`config.py:270-315`) and is the accurate pointer; the codegen CLI
  (`cli/codegen.py:103`) and integration fixtures both call it. No remaining
  `pool_from_config` references. Fixed.
- **IN-03 (exact-type dialect match):** `_dialect_for_config_type` (`config.py:122-150`)
  matches on `type(config)` against a class-keyed map and raises a clear `ValueError` on
  unknown/subclass types. Covered by `TestDialectForConfigType` (subclass + unrelated
  object). Runtime-verified: Snowflake/Databricks/DuckDB all resolve correctly. Fixed.
- **IN-04 (`__version__` idiom):** `__init__.py:8,20-24` uses
  `from importlib.metadata import PackageNotFoundError, version` with a
  `try/except PackageNotFoundError` fallback to `"0.0.0+unknown"`. No import-time raise;
  runtime confirms `__version__` resolves to the installed version. Fixed.

### Last-iteration regression checks (all clean)

- **ed267ea (README):** Every imported symbol (`create_engine`, `register`,
  `SemanticView`, `Metric`, `Dimension`) is present in `__init__.py.__all__`.
  `create_engine("default")` + `register("default", engine)` matches the real
  1-arg-name factory / 2-arg-register API. The cursor example uses
  `with query.execute() as cursor:` and the documented `fetchall_rows()` + attribute /
  dict access exist on `SemolinaCursor` / `Row`. The output block is illustrative
  (README, not a runnable doctest), so its sample values are not a correctness concern.
  No regression.
- **9590d03 (`_dialect_for_config_type`):** Handles all three config classes and raises
  cleanly on unknown types with no isinstance order-dependence. `create_engine` passes
  the pre-`model_copy` config to it, but `model_copy` preserves the exact class, so the
  exact-type lookup is correct either way. No regression.
- **fd7837e (`__version__`):** Standard `importlib.metadata` import and correct fallback
  exception; no import-time side effects. No regression.
- **88902c8 (stale-ref updates):** `warehouse_config` is the accurate, existing target;
  no dangling references remain. No regression.

### Other observations (not findings)

- Snowflake `introspect` interpolates the view name into
  `SHOW COLUMNS IN VIEW {qualified_name}` (`snowflake.py:165`). This is the pre-existing
  pattern (Snowflake does not bind identifiers in `SHOW COLUMNS`), the input is a
  developer/codegen-supplied identifier rather than untrusted end-user input, and it was
  neither introduced nor modified by the reviewed commits. The parallel DuckDB path was
  already hardened (WR-05). Noted for completeness only — not a Phase 44 regression and
  out of scope here.
- Security posture remains sound: `SecretStr` is preserved end-to-end, the spike unwraps
  the token only at the native connect boundary and never prints it, replay cassettes use
  placeholder credentials, and `_sql_str_literal` hardens the only string-interpolated
  introspection SQL path.
- No bare `except:`, no `eval`/`exec`, no debug `print` in library runtime paths (all
  `print` / `.print` occurrences are CLI stderr diagnostics or docstring code-blocks).

## Narrative Findings (AI reviewer)

None. The tree is clean.

---

_Reviewed: 2026-06-24T11:17:26Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
