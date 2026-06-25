---
phase: quick-9
plan: 9
subsystem: testing
tags: [pytest, syrupy, snowflake, databricks, fixtures, dbt]

# Dependency graph
requires:
  - phase: quick-8
    provides: dbt macro create_snapshot_sales_view that this reverts
  - phase: phase-12
    provides: snowflake_engine and databricks_engine fixtures that this extends
provides:
  - snowflake_engine fixture with self-contained warehouse setup/teardown in recording mode
  - databricks_engine fixture with self-contained warehouse setup/teardown in recording mode
  - dbt-jaffle-shop without on-run-end hook (clean for general use)
affects: [tests/conftest.py, dbt-jaffle-shop, snapshot-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest fixture setup/teardown pattern: create warehouse objects before yield, drop after yield, guarded by is_recording"
    - "try/finally with pytest.fail() for setup failures; try/except Exception with print warning for teardown failures"

key-files:
  created: []
  modified:
    - tests/conftest.py
    - dbt-jaffle-shop/dbt_project.yml
  deleted:
    - dbt-jaffle-shop/macros/create_snapshot_sales_view.sql

key-decisions:
  - "Pytest fixtures are the correct home for test data lifecycle management — not dbt on-run-end hooks"
  - "Warehouse DDL lives in conftest.py snowflake_engine/databricks_engine fixtures, guarded by is_recording bool"
  - "Setup uses try/finally with pytest.fail() so test skips cleanly if warehouse setup fails"
  - "Teardown uses try/except Exception with print warning (no re-raise) to match existing snowflake_connection pattern"
  - "Snowflake uses NUMBER/VARCHAR types; Databricks uses BIGINT/STRING — same column names, backend-appropriate types"

patterns-established:
  - "Warehouse fixture pattern: is_recording guard -> create objects -> yield engine -> drop objects"

requirements-completed: [QUICK-9]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Quick Task 9: Revert dbt Snapshot View — Summary

**Reverted dbt macro approach (quick-8) and moved snapshot_sales_data/snapshot_sales_view lifecycle into pytest fixtures with CREATE before yield and DROP after yield, guarded by is_recording.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T18:49:14Z
- **Completed:** 2026-02-19T18:51:54Z
- **Tasks:** 2
- **Files modified:** 2 (plus 1 deleted)

## Accomplishments
- Deleted `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` entirely
- Removed `on-run-end` block from `dbt_project.yml` — dbt project is clean again
- `snowflake_engine` fixture now creates `snapshot_sales_data` (NUMBER/VARCHAR) + `SEMANTIC VIEW snapshot_sales_view` before yielding in recording mode, drops both in teardown
- `databricks_engine` fixture now creates `snapshot_sales_data` (BIGINT/STRING) + `METRIC VIEW snapshot_sales_view` before yielding in recording mode, drops both in teardown
- Replay mode (MockEngine path) unchanged — all 447 tests pass without credentials
- Lint: 0 errors, Typecheck: 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Revert dbt-jaffle-shop snapshot view changes** - `1b4c05a` (chore)
2. **Task 2: Add warehouse setup/teardown to snowflake_engine and databricks_engine fixtures** - `906af20` (feat)

**Plan metadata:** (this SUMMARY.md)

## Files Created/Modified
- `tests/conftest.py` - Added warehouse setup/teardown blocks to snowflake_engine and databricks_engine fixtures
- `dbt-jaffle-shop/dbt_project.yml` - Removed on-run-end section
- `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql` - Deleted

## Decisions Made
- Pytest fixtures are the correct home for test data lifecycle — not dbt hooks. Fixtures keep test setup self-contained and independent of dbt run execution order.
- Setup uses `try/finally` with `pytest.fail()` so any warehouse setup failure surfaces as a clear test failure rather than a confusing downstream error.
- Teardown uses `try/except Exception` with `print` warning (no re-raise), matching the existing `snowflake_connection` fixture pattern so teardown failures don't mask test results.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- During verification, a `git stash` operation accidentally deleted `tests/__snapshots__/test_snapshot_queries.ambr` (brought in from a prior stash entry). Restored with `git restore` — no code changes needed, pre-existing file fully intact.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Recording mode (`--snapshot-update`) is now fully self-contained: running `pytest --snapshot-update` creates the warehouse objects, records snapshots, and drops the objects automatically.
- No dbt run required before recording mode.
- Replay mode (CI/default) is unchanged and requires no credentials.

---
*Phase: quick-9*
*Completed: 2026-02-19*
