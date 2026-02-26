---
phase: 10-documentation
plan: 02
subsystem: testing
tags: [pytest, doctest, doctest-modules, conftest, MockEngine, docstring-examples]

requires:
  - phase: 10-01
    provides: documentation phase context and DOCS-10 requirement

provides:
  - src/cubano/conftest.py with autouse doctest_namespace fixture
  - pyproject.toml configured with --doctest-modules and src/ in testpaths
  - All public API docstring examples are valid passing doctests (16 tests)

affects: [future-phases, ci-cd, 10-03, 10-04]

tech-stack:
  added: []
  patterns: [doctest-modules via src/ conftest.py, autouse doctest_namespace fixture, MockEngine for doctest isolation]

key-files:
  created:
    - src/cubano/conftest.py
  modified:
    - pyproject.toml
    - src/cubano/query.py
    - src/cubano/fields.py
    - src/cubano/filters.py
    - src/cubano/results.py
    - src/cubano/registry.py
    - src/cubano/models.py

key-decisions:
  - "conftest.py placed in src/cubano/ (not tests/) for --doctest-modules discovery — pytest conftest discovery walks source tree"
  - "doctest_setup uses autouse=True and yield for guaranteed registry cleanup (unregister('default') in teardown)"
  - "OrderTerm doctest uses 'NULLS FIRST' not '<NullsOrdering.FIRST: FIRST>' — NullsOrdering has custom __repr__ returning NULLS {value}"
  - "UP038: isinstance tuple syntax fixed to X | Y union syntax in query.py to satisfy pre-commit ruff hook"

patterns-established:
  - "Doctest examples must use >>> prefix and test actual output, not just call code"
  - "doctest_namespace fixture in src/cubano/conftest.py provides Sales, Query, Q, MockEngine, etc. to all doctests"
  - "Registry doctests use local register/unregister within the doctest body to avoid dependency on autouse fixture state"

requirements-completed: [DOCS-10]

duration: 4min
completed: 2026-02-17
---

# Phase 10 Plan 02: Doctest Infrastructure for Code Examples Summary

**Pytest doctest-modules infrastructure with MockEngine fixture injecting Sales, Query, Q into doctest namespace — 16 docstring examples in Query, Field, Filter, Row, and Registry all pass without warehouse connections**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17T12:45:12Z
- **Completed:** 2026-02-17T12:49:00Z
- **Tasks:** 2
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments

- Created `src/cubano/conftest.py` with `doctest_setup` autouse fixture that registers MockEngine as 'default' and injects Sales, Query, Q, mock_engine, cubano, SemanticView, Metric, Dimension, Fact, NullsOrdering into doctest namespace
- Configured pyproject.toml with `--doctest-modules`, `--doctest-continue-on-failure`, `ELLIPSIS`/`NORMALIZE_WHITESPACE` flags, and `testpaths = ["tests", "src"]`
- Converted all public API docstring examples from prose to valid `>>>` doctest format across 6 source modules — all 16 collected doctests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/cubano/conftest.py with doctest_namespace fixture** - `2472de9` (feat)
2. **Task 2: Configure pytest for --doctest-modules and fix docstring examples** - `6ca1b9f` (feat)

## Files Created/Modified

- `src/cubano/conftest.py` — Doctest fixture with Sales SemanticView, doctest_setup autouse fixture, MockEngine with sample data
- `pyproject.toml` — Added addopts (--doctest-modules), doctest_optionflags, testpaths includes src/
- `src/cubano/query.py` — All Query methods (metrics, dimensions, filter, order_by, limit, using, fetch, to_sql) have valid >>> examples; UP038 isinstance fixes
- `src/cubano/fields.py` — Field.asc, Field.desc, OrderTerm examples in >>> format with correct NullsOrdering repr
- `src/cubano/filters.py` — Q class examples converted to >>> format showing connector and negated attributes
- `src/cubano/results.py` — Row class gets >>> doctest (attribute access, dict access, len)
- `src/cubano/registry.py` — register() gets complete >>> doctest cycle (register, get_engine verify, unregister)
- `src/cubano/models.py` — SemanticView class docstring uses >>> format for class definition example

## Decisions Made

- conftest.py placed in `src/cubano/` not `tests/` — pytest's `--doctest-modules` conftest discovery only walks the source tree, not `tests/`
- `doctest_setup` uses `autouse=True` with yield for guaranteed `unregister("default")` cleanup on teardown even if doctest fails
- `OrderTerm` doctest uses literal `NULLS FIRST` not `<NullsOrdering.FIRST: 'FIRST'>` — `NullsOrdering.__repr__` returns `NULLS {value}` not the default enum repr
- UP038 lint fix: Changed `isinstance(f, (Dimension, Fact))` to `isinstance(f, Dimension | Fact)` in query.py — pre-commit ruff hook (newer version) flagged tuple-style isinstance

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect doctest expected output for NullsOrdering**
- **Found during:** Task 2 (running doctests)
- **Issue:** Plan specified `<NullsOrdering.FIRST: 'FIRST'>` as expected output but `NullsOrdering.__repr__` returns `NULLS FIRST`
- **Fix:** Changed expected output in OrderTerm docstring to `NULLS FIRST`
- **Files modified:** `src/cubano/fields.py`
- **Verification:** `uv run pytest src/cubano/fields.py::cubano.fields.OrderTerm --doctest-modules` passes
- **Committed in:** `6ca1b9f` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed UP038 isinstance tuple syntax**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Pre-commit ruff hook flagged `isinstance(f, (Dimension, Fact))` and `isinstance(f, (Field, OrderTerm))` as UP038
- **Fix:** Changed to `isinstance(f, Dimension | Fact)` and `isinstance(f, Field | OrderTerm)` union syntax
- **Files modified:** `src/cubano/query.py`
- **Verification:** Pre-commit hook passes, all tests still pass
- **Committed in:** `6ca1b9f` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for correctness — one for doctest output accuracy, one for linting compliance. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Doctest infrastructure complete — `uv run pytest src/ --doctest-modules` runs 16 doctests in < 1 second
- All public API examples are live-tested documentation that will fail CI if they break
- Ready for 10-03 (MkDocs documentation site) and 10-04 (API reference)

---
*Phase: 10-documentation*
*Completed: 2026-02-17*
