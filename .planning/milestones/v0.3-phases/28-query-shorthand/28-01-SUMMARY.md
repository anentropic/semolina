---
phase: 28-query-shorthand
plan: 01
subsystem: api
tags: [query-builder, shorthand, keyword-args, fluent-api]

# Dependency graph
requires:
  - phase: 10-model-centric-api
    provides: "SemanticView.query() entry point and _Query builder"
provides:
  - "metrics= and dimensions= keyword args on SemanticView.query()"
  - "Shorthand + builder additivity (combine styles freely)"
  - "All query() params now keyword-only"
affects: [29-arrow-cursor, documentation]

# Tech tracking
tech-stack:
  added: []
  patterns: [keyword-only-shorthand, delegation-to-builder-methods]

key-files:
  created: []
  modified:
    - src/semolina/models.py
    - tests/unit/test_query.py
    - tests/unit/test_models.py

key-decisions:
  - "Sequence[Any] type hint for metrics/dimensions params (matches _Query.metrics() Any pattern, avoids descriptor __get__ returning Field[T] instead of Metric[T])"
  - "All query() params keyword-only via * separator (using= was positional-or-keyword, now keyword-only)"

patterns-established:
  - "Shorthand-then-chain: query(metrics=[...]).metrics(...) is additive"
  - "Delegation pattern: shorthand delegates to existing builder methods, zero validation duplication"

requirements-completed: [QAPI-01, QAPI-02]

# Metrics
duration: 3min
completed: 2026-03-17
---

# Phase 28 Plan 01: Query Shorthand Summary

**metrics= and dimensions= keyword args on SemanticView.query() with builder additivity and zero validation duplication**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-17T09:52:38Z
- **Completed:** 2026-03-17T09:55:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `metrics=` and `dimensions=` shorthand kwargs to `SemanticView.query()` for concise one-liner queries
- Builder methods remain fully additive with shorthand args (e.g. `query(metrics=[a]).metrics(b)` selects both)
- All 19 new tests pass (13 shorthand + 4 additivity + 2 model-level)
- All quality gates green: typecheck, lint, format, full test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Write tests for query shorthand and additivity (RED)** - `9858f17` (test)
2. **Task 2: Implement query shorthand in SemanticView.query() (GREEN)** - `03996ea` (feat)

_TDD workflow: RED commit with failing tests, then GREEN commit making them pass._

## Files Created/Modified
- `src/semolina/models.py` - Updated `query()` with `metrics=`, `dimensions=`, keyword-only `using=` params
- `tests/unit/test_query.py` - Added `TestQueryShorthand` (13 tests) and `TestQueryShorthandAdditivity` (4 tests)
- `tests/unit/test_models.py` - Added 2 shorthand tests to existing `TestModelQuery` class

## Decisions Made
- Used `Sequence[Any]` instead of `Sequence[Metric[Any]]` for type hints because the Field descriptor `__get__` returns `Field[T]` (not `Metric[T]`) for class-level access, causing basedpyright strict mode errors. Runtime validation via `.metrics()` and `.dimensions()` provides type safety.
- Made `using=` keyword-only (was positional-or-keyword) for consistency with the new keyword-only `metrics=` and `dimensions=` params.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed type hints from Sequence[Metric[Any]] to Sequence[Any]**
- **Found during:** Task 2 (implementation)
- **Issue:** Plan specified `metrics: Sequence[Metric[Any]]` but basedpyright strict mode rejects `Sales.revenue` (descriptor returns `Field[T]` not `Metric[T]`)
- **Fix:** Used `Sequence[Any]` matching the existing `_Query.metrics(*fields: Any)` pattern
- **Files modified:** src/semolina/models.py
- **Verification:** `uv run basedpyright` passes with zero new errors
- **Committed in:** `03996ea` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for typecheck compliance. Runtime validation unchanged.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Query shorthand API complete and tested
- Ready for Phase 29 (Arrow Cursor Integration) or documentation updates

---
*Phase: 28-query-shorthand*
*Completed: 2026-03-17*
