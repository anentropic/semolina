---
phase: 32-v03-tech-debt-cleanup
plan: 01
subsystem: testing
tags: [mockpool, deprecation-cleanup, pool-registry, tech-debt]

# Dependency graph
requires:
  - phase: 25-pool-registry
    provides: MockPool class and pool+dialect register() API
provides:
  - Fully pool-based test and doctest infrastructure with zero DeprecationWarnings
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MockPool + dialect='mock' for all test register() calls"
    - "pool_name parameter in query.using() method"

key-files:
  created: []
  modified:
    - src/semolina/conftest.py
    - src/semolina/query.py
    - tests/unit/test_query.py

key-decisions:
  - "Preserved 3 legacy engine error-path assertions in test_query.py unchanged (lines 478, 599, 610) since they test the v0.2 backward-compat fallback in execute()"
  - "Preserved execute() method body, _LegacyResultCursor, _NoOpConn, _NoOpPool unchanged since they support backward compat"

patterns-established:
  - "All new tests use MockPool + dialect='mock' instead of MockEngine"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-04-18
---

# Phase 32 Plan 01: Tech Debt Cleanup Summary

**Replaced all MockEngine usage with MockPool + dialect='mock' across conftest, query, and test files, eliminating DeprecationWarnings and aligning with v0.3 pool-based API**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-18T03:01:56Z
- **Completed:** 2026-04-18T03:07:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Converted conftest.py doctest fixtures from MockEngine to MockPool with dialect="mock" registration
- Updated query.py using() method parameter from engine_name to pool_name with pool-based docstrings, fixed doctest parse error (missing blank line before Attributes:)
- Converted all 21 register() call sites in test_query.py from MockEngine to MockPool with dialect="mock"
- All 127 tests pass with zero DeprecationWarnings from test_query.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Update conftest.py and query.py source files** - `54945c1` (refactor)
2. **Task 2: Update test_query.py MockEngine to MockPool and verify full suite** - `389271e` (refactor)

## Files Created/Modified
- `src/semolina/conftest.py` - MockEngine -> MockPool, register with dialect="mock", updated docstrings
- `src/semolina/query.py` - using() parameter engine_name -> pool_name, pool-based docstrings, doctest parse fix
- `tests/unit/test_query.py` - All 21 MockEngine register() calls converted to MockPool + dialect="mock", error assertions updated

## Decisions Made
- Preserved 3 legacy engine error-path test assertions unchanged (`match="No engine registered"`) since they test the v0.2 backward-compat fallback path in execute()
- Did not modify execute() body, _LegacyResultCursor, _NoOpConn, _NoOpPool classes -- these support backward compatibility
- Did not change to_sql() docstring reference to "Engine.to_sql(query)" -- documents old API as context

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed import sorting after MockPool import change**
- **Found during:** Task 2 (test_query.py update)
- **Issue:** Changing import from `semolina.engines.mock` to `semolina.pool` broke ruff isort ordering
- **Fix:** Ran `ruff check --fix` to auto-sort imports
- **Files modified:** tests/unit/test_query.py
- **Verification:** `uv run ruff check` passes
- **Committed in:** 389271e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor import sorting fix required by mechanical rename. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- v0.3 tech debt cleanup complete
- All quality gates pass (pytest, basedpyright, ruff check, ruff format) for changed files
- Pre-existing failures in test_databricks_engine.py and basedpyright snowflake import errors are unrelated

## Self-Check: PASSED

- All 3 modified files exist on disk
- All 2 task commits verified in git log (54945c1, 389271e)
- SUMMARY.md created at expected path

---
*Phase: 32-v03-tech-debt-cleanup*
*Completed: 2026-04-18*
