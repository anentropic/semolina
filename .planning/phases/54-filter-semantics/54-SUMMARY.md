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

## Waits on a credentialed recording session

Cassettes may not be hand-edited, so these need a live run (`uv run pytest --adbc-record=...`):

- **FILT-04 recording:** integration cassettes for the builder's `HAVING` SQL on both
  warehouses (the D4 probe measured the shapes; no cassette pins the builder's output yet).
- **54-03 fixture work:** extend the integration fixture with a boolean column and a NULL,
  record a boolean filter and `NULLS LAST` ordering, then delete
  `semolina-jaffle-shop/tests/test_warehouse_queries.py`. Changing fixture data re-records
  every cassette, so do it once, with the item above.
- **FILT-05, Databricks half:** quote the view name in `DESCRIBE TABLE EXTENDED ... AS JSON`.
  The cassette key for that statement changes when quoted, so it goes in the same session.
