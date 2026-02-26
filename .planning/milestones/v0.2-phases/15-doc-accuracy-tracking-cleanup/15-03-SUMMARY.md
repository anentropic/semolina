---
phase: 15-doc-accuracy-tracking-cleanup
plan: 03
subsystem: testing, infra
tags: [pytest, fixtures, github-actions, ci]

# Dependency graph
requires:
  - phase: 12-warehouse-testing-syrupy
    provides: Engine fixtures that replaced orphaned connection fixtures
provides:
  - Clean integration conftest with only active fixtures
  - docs.yml checkout version aligned with other CI workflows
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - tests/integration/conftest.py
    - .github/workflows/docs.yml

key-decisions:
  - "Kept uuid import -- still used by snowflake_engine and databricks_engine fixtures"
  - "Kept snowflake_credentials and databricks_credentials fixtures -- still used by engine fixtures"

patterns-established: []

requirements-completed: [DOCS-04]

# Metrics
duration: 1min
completed: 2026-02-22
---

# Phase 15 Plan 03: Cleanup Summary

**Removed 3 orphaned Phase-8 integration fixtures and aligned docs.yml checkout@v4 to @v6**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-22T22:57:09Z
- **Completed:** 2026-02-22T22:58:24Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Removed `test_schema_name`, `snowflake_connection`, and `databricks_connection` fixtures (120+ lines of dead code)
- Updated docs.yml from `actions/checkout@v4` to `@v6`, consistent with ci.yml and release.yml
- All 589 tests pass, typecheck and lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove orphaned fixtures and align docs.yml checkout version** - `e55feb1` (chore)

## Files Created/Modified
- `tests/integration/conftest.py` - Removed 3 orphaned fixtures (test_schema_name, snowflake_connection, databricks_connection)
- `.github/workflows/docs.yml` - Updated checkout action from v4 to v6

## Decisions Made
- Kept `uuid` import since it is still used by `snowflake_engine` (line ~271) and `databricks_engine` (line ~377) fixtures
- Kept `snowflake_credentials` and `databricks_credentials` fixtures since they are still used by the Phase 12 engine fixtures

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 15 complete (all 3 plans executed)
- Integration conftest is clean with only active fixtures
- All CI workflows use consistent action versions

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 15-doc-accuracy-tracking-cleanup*
*Completed: 2026-02-22*
