---
phase: 13-docs-accuracy-verification
plan: "03"
subsystem: testing
tags: [syrupy, snapshot-testing, warehouse-testing, documentation]

# Dependency graph
requires:
  - phase: 12-warehouse-testing-syrupy
    provides: "Warehouse testing guide (warehouse-testing.md) and actual test infrastructure (tests/integration/)"
provides:
  - "Accurate warehouse-testing.md: all 5 categories of stale references corrected"
affects: [new-contributors, docs-readers]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - docs/src/guides/warehouse-testing.md

key-decisions:
  - "Phase 13-03 (Docs Accuracy Fix): warehouse-testing.md corrected for 5 stale reference categories — conftest location, test file name, constant name (TEST_DATA), snapshot directory, and Databricks env var (DATABRICKS_SERVER_HOSTNAME). Guide now matches actual tests/integration/ project structure from Phase 12 restructure."

patterns-established: []

requirements-completed: [TEST-VCR, DOCS-09]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 13 Plan 03: Warehouse Testing Guide Accuracy Fix Summary

**Five categories of stale path/constant/env-var references corrected in warehouse-testing.md — guide now matches actual tests/integration/ layout and TEST_DATA constant introduced in Phase 12**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-22T01:03:06Z
- **Completed:** 2026-02-22T01:05:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Corrected `tests/conftest.py` to `tests/integration/conftest.py` (3 occurrences)
- Corrected `tests/test_snapshot_queries.py` to `tests/integration/test_queries.py` (3 occurrences, including recording commands)
- Corrected `SNAPSHOT_TEST_DATA` to `TEST_DATA` (6 occurrences in prose, tips, and best-practices sections)
- Corrected `tests/__snapshots__/` to `tests/integration/__snapshots__/` (4 occurrences including `git add` commands)
- Corrected `DATABRICKS_HOST` to `DATABRICKS_SERVER_HOSTNAME` (2 occurrences: env var table + troubleshooting section)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix all 5 categories of inaccuracies in warehouse-testing.md** - `751c641` (fix)

**Plan metadata:** _(pending docs commit)_

## Files Created/Modified

- `docs/src/guides/warehouse-testing.md` - All 5 categories of stale references corrected; guide now functional for new contributors

## Decisions Made

None - followed plan as specified. All corrections were mechanical find-and-replace using exact strings identified in research phase.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all 10 verification checks (5 wrong values absent, 5 correct values present) passed after single Write operation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 13 Plan 04 is next (final plan in phase)
- warehouse-testing.md is now accurate and functional for new contributors
- All stale references from Phase 12 restructure are resolved

## Self-Check

### Files verified
- [x] `docs/src/guides/warehouse-testing.md` - FOUND and verified

### Verification greps (all 10 checks passed)
- `grep "tests/conftest\.py"` → 0 matches
- `grep "test_snapshot_queries"` → 0 matches
- `grep "SNAPSHOT_TEST_DATA"` → 0 matches
- `grep "tests/__snapshots__/"` → 0 matches
- `grep "DATABRICKS_HOST[^N]"` → 0 matches (exit 1)
- `grep "tests/integration/conftest\.py"` → 3 matches
- `grep "tests/integration/test_queries\.py"` → 3 matches
- `grep "TEST_DATA"` → 7 matches
- `grep "tests/integration/__snapshots__/"` → 4 matches
- `grep "DATABRICKS_SERVER_HOSTNAME"` → 2 matches

## Self-Check: PASSED

---
*Phase: 13-docs-accuracy-verification*
*Completed: 2026-02-22*
