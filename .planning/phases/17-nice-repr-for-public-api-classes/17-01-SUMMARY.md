---
phase: 17-nice-repr-for-public-api-classes
plan: 01
subsystem: api
tags: [repr, repl, debugging, metaclass, dataclass]

# Dependency graph
requires:
  - phase: 10.1-refactor-query-interface-to-model-centric
    provides: "SemanticViewMeta, Field, _Query, Result classes"
provides:
  - "Informative __repr__ on all public API classes for REPL/IDE debugging"
  - "_model propagation fix through frozen dataclass builder chain"
affects: [documentation, tutorials]

# Tech tracking
tech-stack:
  added: []
  patterns: ["_replace() helper for frozen dataclass init=False field propagation"]

key-files:
  created: []
  modified:
    - src/cubano/models.py
    - src/cubano/fields.py
    - src/cubano/query.py
    - src/cubano/results.py
    - tests/unit/test_models.py
    - tests/unit/test_fields.py
    - tests/unit/test_query.py
    - tests/unit/test_results.py

key-decisions:
  - "Use getattr() in SemanticViewMeta.__repr__ to satisfy basedpyright strict (metaclass cls doesn't know about subclass ClassVars)"
  - "Field.__repr__ uses type(self).__name__ so Metric/Dimension/Fact inherit correctly without override"
  - "_Query._replace() helper propagates _model through frozen dataclass replace() chain (fixes pre-existing bug)"

patterns-established:
  - "_replace() pattern: frozen dataclasses with init=False fields need custom replace helper to propagate non-init fields"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 17 Plan 01: Nice Repr for Public API Classes Summary

**Informative __repr__ on SemanticView/Field/_Query/Result with _model propagation fix through frozen dataclass chain**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T00:15:01Z
- **Completed:** 2026-02-23T00:20:26Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- All 4 public API classes now have informative __repr__ for REPL/IDE debugging
- SemanticView shows view name and fields grouped by type (metrics, dimensions, facts)
- Field/Metric/Dimension/Fact show type name and field name (or 'unbound')
- _Query shows full query state (model, metrics, dimensions, filters, order_by, limit, using)
- Result shows row count and column names
- Fixed pre-existing bug: _model now propagates through chained builder methods
- 21 new tests (610 total, up from 589)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add __repr__ to SemanticViewMeta, Field, _Query, and Result** - `f978f58` (feat)
2. **Task 2: Add comprehensive repr tests** - `17c602d` (test)

## Files Created/Modified
- `src/cubano/models.py` - SemanticViewMeta.__repr__ showing view name and grouped fields
- `src/cubano/fields.py` - Field.__repr__ showing type and name (inherited by Metric/Dimension/Fact)
- `src/cubano/query.py` - Custom _Query.__repr__ with repr=False on dataclass; _replace() helper for _model propagation
- `src/cubano/results.py` - Enhanced Result.__repr__ showing row count and column names
- `tests/unit/test_models.py` - TestSemanticViewRepr (6 tests)
- `tests/unit/test_fields.py` - TestFieldRepr (5 tests)
- `tests/unit/test_query.py` - TestQueryRepr (10 tests including _model propagation)
- `tests/unit/test_results.py` - TestResultRepr column names test (1 new test, 2 existing)

## Decisions Made
- Used `getattr()` in SemanticViewMeta.__repr__ instead of direct attribute access to satisfy basedpyright strict mode (metaclass `cls` parameter doesn't know about SemanticView's ClassVar attributes)
- Field.__repr__ placed on base Field class using `type(self).__name__` so Metric/Dimension/Fact subclasses inherit it correctly
- Added `_replace()` helper method to _Query that wraps `dataclasses.replace()` and propagates `_model` (which has `init=False` and is therefore lost by standard `replace()`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _model loss through frozen dataclass replace() chain**
- **Found during:** Task 1 (_Query.__repr__ implementation)
- **Issue:** `_model` field has `init=False` so `dataclasses.replace()` does not copy it to new instances. Every chained builder method (.metrics(), .dimensions(), .where(), etc.) created a new _Query with `_model=None`, breaking field ownership validation after the first chain step and causing repr to show `model=unbound` for bound queries.
- **Fix:** Added `_replace()` helper that calls `replace()` then copies `_model` via `object.__setattr__()`. Replaced all 6 `replace(self, ...)` calls with `self._replace(...)`.
- **Files modified:** `src/cubano/query.py`
- **Verification:** Manual REPL test confirms `model=Sales` propagates through full chain; new test `test_model_propagates_through_chain` covers this
- **Committed in:** f978f58 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix was necessary for repr correctness and also fixes a pre-existing field ownership validation weakness. No scope creep.

## Issues Encountered
- basedpyright strict mode rejects direct `cls._fields` and `cls._view_name` access in metaclass `__repr__` because `cls` is typed as `SemanticViewMeta*`, not `SemanticView`. Resolved by using `getattr()` instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All public API classes now have useful repr output for REPL debugging
- All quality gates pass: typecheck (0 errors), lint (0 errors), format (clean), tests (610 passed), docs build (clean)

## Self-Check: PASSED

- All 9 files verified present on disk
- Both task commits (f978f58, 17c602d) verified in git log

---
*Phase: 17-nice-repr-for-public-api-classes*
*Completed: 2026-02-23*
