# Phase 44 — Deferred Items (out of plan scope)

Discovered during Plan 03 execution. All are Databricks-only and explicitly
deferred to the gated Plan 04 (Databricks ADBC introspect spike) or are the
pre-existing "Databricks integration recording hangs" STATE blocker. None are
caused by Plan 03's Snowflake/DuckDB changes.

## Plan 04 scope (Databricks ADBC introspect rewrite)

- `tests/unit/test_databricks_engine.py` (30 failures) — legacy native
  `DatabricksEngine(server_hostname=..., http_path=..., access_token=...)`
  constructor + `databricks.sql` sys.modules mocks. Fails with
  `Engine.__init__() got an unexpected keyword argument 'server_hostname'`
  since the Engine base took `(*, pool, dialect, config)` in Plan 02. Must be
  rewritten onto the ADBC-cursor seam (mirroring the Plan 03 Snowflake test
  migration) when the Databricks ADBC introspect path lands.
- `tests/unit/codegen/test_codegen_e2e.py::test_codegen_databricks_field_types`
  (1 failure) — same legacy native `DatabricksEngine` constructor. The Snowflake
  and DuckDB cases in this module were migrated in Plan 03; the Databricks case
  is left under a narrowed `reportCallIssue` pragma for Plan 04.

## Pre-existing blocker (STATE: "Databricks integration recording hangs")

- `tests/integration/test_queries.py[databricks_engine]` (7 failures) —
  `CassetteMissError`: Databricks query cassettes were never recorded (the
  recording hang). These fail identically on clean `main`; Snowflake
  integration replays 7/7 green.
