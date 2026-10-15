# Phase 54 summary: filter semantics and SQL edge cases

Executed 2026-10-13 on branch `claude/phase-54-filter-semantics` (PR #46, stacked on #45).
No per-plan PLAN.md files were written: each plan was run test-first straight from the
ROADMAP success criteria, a failing-test commit followed by the fix.

## Done

| Plan | Requirement | What changed |
|---|---|---|
| 54-01 | FILT-01, FILT-09 | `== None` / `!= None` compile to `IS NULL` / `IS NOT NULL` (D3). Every other lookup given `None` raises `TypeError` when built: comparisons, `between()` with a `None` bound, `in_()` holding `None`, the LIKE family. `.where()` refuses a string, a bare field or a `bool` at the call. |
| 54-02 | FILT-02 | `startswith`/`endswith`/their `i` forms and `iexact` escape `%`, `_` and `!` and emit `ESCAPE '!'` on every dialect. `!`, not backslash: Snowflake and Spark string literals and Spark's default LIKE escape all treat backslash specially. `like()`/`ilike()` pass through. Verified live on the DuckDB extension. |
| 54-04 | FILT-03 | `to_sql()` renders values through `Dialect.render_literal`; Snowflake's `render_literal` doubles backslashes. The how-to's "not runnable" warning is now a note that previews run. DuckDB's `to_sql()` output is executed in a test. |
| 54-05 | FILT-05 (DuckDB, Snowflake), FILT-06, FILT-07, FILT-08 | Pre-quoted view segments are escaped, a dot inside one raises. DuckDB introspect honours the schema and quotes the name (measured on extension v0.12.1: `DESCRIBE SEMANTIC VIEW` and `semantic_view()` both resolve `schema.view`). Snowflake `SHOW COLUMNS` quotes each part. One `class_name_for` helper makes valid class names (`"Order Book"` -> `OrderBook`). Value slots are marked by the compiler (`_SLOT`), so a `?` in a name is never a placeholder. Every ADBC introspection error is translated; DuckDB checks the error type before the message. |
| 54-03 | FILT-04, ALIAS-05 (code) | A metric filter compiles to `HAVING` on the wrapped metric on Snowflake and Databricks (D4); the filter-splitting helpers moved from the DuckDB builder to `SQLBuilder`. The tutorial's dimension-OR-metric example, which raised on every backend, now ORs two dimensions. |

## Recorded live (2026-10-14)

One credentialed session on Anentropic's machine, recording only what was new
(`--adbc-record=new_episodes` for `test_queries.py`, `--adbc-record=all` for `test_introspect.py`):

- **Fixture:** both warehouses' `sales_data` gained a nullable boolean `is_online`
  (true, false, true, NULL, true), exposed as a dimension. No row changed, so every
  existing cassette's SQL and rows still hold and none was re-recorded.
- **FILT-04:** `test_filtered_by_metric`, `test_dimension_and_metric_filters_combine` and
  `test_metric_filter_matching_nothing_returns_no_rows` pin the builder's `HAVING` on both
  warehouses. The first two would return different rows if the metric filtered rows
  before aggregation.
- **54-03's moved checks:** `test_filtered_by_boolean`, `test_filtered_by_null` (D3's
  `IS NULL`, live), `test_nulls_last_ascending` (non-default on Databricks) and
  `test_nulls_last_descending` (non-default on Snowflake).
  `semolina-jaffle-shop/tests/test_warehouse_queries.py` is deleted, with its
  `snowflake_connection` fixture, its markers and its README section.
- **FILT-05, Databricks half:** `introspect()` quotes each part of the view name
  (`DatabricksDialect.quote_table_name`), unit-tested, and both introspection cassettes
  were re-recorded with `is_online`.

Replay: `tests/integration` 44 passed; full suite 1741 passed, 2 xfailed on the recording
machine. Today's temp schemas were dropped. 31 older `test_*` schemas from earlier runs
remain in the Databricks `jaffle` catalog, left for Anentropic to decide on.
