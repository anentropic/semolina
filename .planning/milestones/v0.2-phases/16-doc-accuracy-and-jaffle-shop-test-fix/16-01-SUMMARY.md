---
phase: 16-doc-accuracy-and-jaffle-shop-test-fix
plan: 01
subsystem: docs, testing
tags: [mkdocs, filtering, sql, jaffle-shop, semantic-views]

# Dependency graph
requires:
  - phase: 13.1-implement-filter-lookup-system-and-where-clause-compiler
    provides: SQLBuilder._compile_predicate() with AND parenthesization
  - phase: 14-documentation-overhaul
    provides: filtering.md how-to guide
provides:
  - Corrected SQL examples in filtering.md matching compiler output
  - Corrected escape hatch reference pointing to SQLBuilder
  - Fixed jaffle-shop test using correct .metrics() for Metric field
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - docs/src/how-to/filtering.md
    - cubano-jaffle-shop/tests/test_warehouse_queries.py

key-decisions:
  - "No new decisions -- followed plan exactly as specified"

patterns-established: []

requirements-completed: [DOCS-04, INT-02]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 16 Plan 01: Doc Accuracy and Jaffle-Shop Test Fix Summary

**Corrected three audit gaps: nested WHERE SQL parentheses in both dialect tabs, escape hatch class reference, and Metric field query method in jaffle-shop test**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T23:43:56Z
- **Completed:** 2026-02-22T23:45:40Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed nested WHERE SQL examples in filtering.md to include outer AND parentheses matching `SQLBuilder._compile_predicate()` output (both Snowflake and Databricks tabs)
- Changed escape hatch reference from "your engine's `_compile_predicate()`" to "`SQLBuilder._compile_predicate()`" matching actual class location
- Fixed `test_filter_comparison_greater_than` to use `.metrics(Customers.lifetime_spend)` instead of `.dimensions()`, matching the `Metric()` field declaration

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix filtering.md SQL examples and escape hatch reference** - `728e8dd` (fix)
2. **Task 2: Fix jaffle-shop test to use .metrics() for lifetime_spend** - `ac529c4` (fix)

## Files Created/Modified

- `docs/src/how-to/filtering.md` - Corrected nested WHERE SQL outer parentheses (both tabs) and escape hatch class reference
- `cubano-jaffle-shop/tests/test_warehouse_queries.py` - Changed `.dimensions()` to `.metrics()` for lifetime_spend Metric field

## Decisions Made

None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three v0.2 milestone audit gaps (DOCS-04-NESTED-PARENS, DOCS-04-ESCAPE-HATCH, JAFFLE-SHOP-DIMENSIONS-BUG) are closed
- All quality gates pass: typecheck (0 errors), lint (all passed), format (all formatted), tests (589 passed main + 13 jaffle-shop mock), docs build (strict, no errors)

---
## Self-Check: PASSED

- [x] 16-01-SUMMARY.md exists
- [x] Commit 728e8dd found (Task 1)
- [x] Commit ac529c4 found (Task 2)

---
*Phase: 16-doc-accuracy-and-jaffle-shop-test-fix*
*Completed: 2026-02-22*
