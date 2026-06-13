---
phase: quick-8
plan: 8
subsystem: testing
tags: [dbt, snowflake, databricks, semantic-view, metric-view, snapshot-testing]

requires:
  - phase: quick-7
    provides: SnowflakeCredentials/DatabricksCredentials used in snapshot test fixtures
  - phase: phase-12
    provides: SNAPSHOT_TEST_DATA definition and snapshot test infrastructure

provides:
  - dbt macro that creates snapshot_sales_view on Snowflake (SEMANTIC VIEW) and Databricks (METRIC VIEW)
  - Staging table snapshot_sales_data with 5 SNAPSHOT_TEST_DATA rows for both backends
  - on-run-end hook in dbt_project.yml so view is created after every dbt run

affects: [snapshot-recording, warehouse-integration-tests]

tech-stack:
  added: []
  patterns:
    - "dbt on-run-end hook for post-model DDL"
    - "target.type branching in Jinja2 macro for multi-warehouse DDL"
    - "{% do run_query(...) %} to discard DDL result value"

key-files:
  created:
    - dbt-jaffle-shop/macros/create_snapshot_sales_view.sql
  modified:
    - dbt-jaffle-shop/dbt_project.yml

key-decisions:
  - "Two-step approach per backend: CREATE TABLE first (as backing source), then CREATE VIEW on top of it -- Snowflake SEMANTIC VIEW and Databricks METRIC VIEW both require a real table source"
  - "Snowflake uses NUMBER/VARCHAR types; Databricks uses BIGINT/STRING to match each warehouse's native type system"
  - "Databricks METRIC VIEW declares METRICS as DOUBLE even though source table uses BIGINT -- acceptable since actual warehouse types are captured during --snapshot-update recording"
  - "Fallback branch raises compiler error for unknown target types so dbt fails loudly rather than silently doing nothing"
  - "on-run-end placed after clean-targets, before vars -- idempotent due to CREATE OR REPLACE"

patterns-established:
  - "Pattern: Multi-warehouse dbt macro uses target.type branching with a fallback raise_compiler_error"

requirements-completed: []

duration: 1min
completed: 2026-02-19
---

# Quick Task 8: Update dbt-jaffle-shop to Set Up the Experiment Summary

**dbt macro creating snapshot_sales_view as Snowflake SEMANTIC VIEW or Databricks METRIC VIEW with 5 SNAPSHOT_TEST_DATA rows, wired via on-run-end hook**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-19T18:11:55Z
- **Completed:** 2026-02-19T18:13:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` with a two-step macro that
  first creates a backing staging table (`snapshot_sales_data`) then creates the appropriate
  semantic/metric view on top of it for both Snowflake and Databricks
- Populated the staging table with all 5 SNAPSHOT_TEST_DATA rows (matching `tests/conftest.py` exactly)
- Registered the macro as an `on-run-end` hook in `dbt-jaffle-shop/dbt_project.yml` so it
  runs automatically after every `dbt run`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create create_snapshot_sales_view macro** - `f0b6362` (feat)
2. **Task 2: Register macro as on-run-end hook in dbt_project.yml** - `0675e38` (feat)

**Plan metadata:** included in final commit (docs)

## Files Created/Modified

- `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` - Jinja2 macro with Snowflake SEMANTIC
  VIEW and Databricks METRIC VIEW DDL branches, 4x `{% do run_query(...) %}` calls (2 per backend)
- `dbt-jaffle-shop/dbt_project.yml` - Added `on-run-end` hook calling `create_snapshot_sales_view()`

## Decisions Made

- Two-step DDL per backend: a backing `snapshot_sales_data` table is created first (both SEMANTIC
  VIEW and METRIC VIEW require a real table source), then the view is created on top.
- Snowflake uses `NUMBER`/`VARCHAR` column types; Databricks uses `BIGINT`/`STRING` to match each
  warehouse's native type conventions.
- Databricks METRIC VIEW declares metrics as `DOUBLE` while the source table uses `BIGINT` -- this
  is acceptable; the actual warehouse types are captured during `--snapshot-update` recording.
- Fallback branch uses `exceptions.raise_compiler_error` for unknown `target.type` values so `dbt`
  fails loudly rather than silently producing no view.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

The view is created by running `dbt run` against either target; no additional setup needed beyond
having warehouse credentials configured in the dbt profile.

## Next Phase Readiness

- `snapshot_sales_view` will be available on both warehouses after `dbt run --target snowflake`
  and `dbt run --target databricks`
- `pytest --snapshot-update tests/test_snapshot_queries.py` can now record against real warehouses
- No blockers

---
*Phase: quick-8*
*Completed: 2026-02-19*
