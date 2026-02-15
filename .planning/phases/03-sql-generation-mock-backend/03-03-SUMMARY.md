---
phase: 03-sql-generation-mock-backend
plan: 03
subsystem: testing
tags:
  - mock-engine
  - sql-generation
  - testing
  - fixtures

requires:
  - phase: 03-sql-generation-mock-backend
    plan: 01
    provides: Engine ABC, Dialect pattern, MockDialect implementation

provides:
  - MockEngine class for testing queries without warehouse connection
  - Fixture-based test data support for local validation
  - Integration between Query objects and SQL generation
  - Complete Phase 3 testing foundation

affects:
  - Phase 4 (Row class will replace dict returns)
  - Phase 5 (Real warehouse backend implementations will use same Engine pattern)
  - Integration tests across entire system

tech-stack:
  added: []
  patterns:
    - SQLBuilder composable SQL generation pattern
    - MockEngine fixture-based testing pattern
    - Dialect-driven backend abstraction

key-files:
  created:
    - src/cubano/engines/mock.py (MockEngine implementation)
  modified:
    - src/cubano/engines/sql.py (SQLBuilder added)
    - src/cubano/engines/__init__.py (MockEngine exported)
    - src/cubano/engines/base.py (Row Phase 4 note added)

key-decisions:
  - "Return raw fixture data in Phase 3 without filtering/aggregation (deferred to Phase 4-6)"
  - "Use MockDialect (Snowflake-compatible) for consistency with primary backend"
  - "Implemented SQLBuilder as blocking dependency for MockEngine (planned for 03-02 but needed for 03-03)"

---

# Phase 3 Plan 3: MockEngine Summary

**MockEngine validates query structure and returns fixture data for testing without warehouse connections, enabling local query validation with configurable test datasets**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-15T15:38:52Z
- **Completed:** 2026-02-15T15:51:00Z
- **Tasks:** 3 (plus 1 blocking dependency)
- **Files created:** 1
- **Files modified:** 3

## Accomplishments

- **MockEngine implementation:** Full query execution backend that validates structure and returns fixture data
- **SQL generation integration:** Uses SQLBuilder and MockDialect for Snowflake-compatible SQL generation
- **Testing foundation:** Enables developers to build and validate queries locally without warehouse access
- **Complete Phase 3 foundation:** With Engine ABC (03-01), SQLBuilder (03-02 as blocking fix), and MockEngine (03-03), the entire testing infrastructure is ready for downstream phases

## Task Commits

1. **Blocking Dependency (03-02): SQLBuilder implementation** - `cddc2e1` (feat)
   - Implements composable SQL generation for all backends
   - Built separately from 03-03 but required for MockEngine to function
   - Documented as auto-fixed blocking issue (RULE 3)

2. **Task 1: Create MockEngine class** - `5e26afe` (feat)
   - MockEngine(fixtures dict) - stores test data
   - to_sql(query) - validates and generates SQL using SQLBuilder + MockDialect
   - execute(query) - returns fixture data for queried view

3. **Task 2: Export MockEngine from cubano.engines** - `5e26afe` (feat)
   - Added MockEngine import to __init__.py
   - Updated __all__ exports
   - Users can now `from cubano.engines import MockEngine`

4. **Task 3: Update Engine ABC with Row note** - `629d807` (docs)
   - Added docstring note that Row is Phase 4 feature
   - Clarifies current implementations return dicts
   - Maintains forward compatibility

**Plan metadata:** Final state updates committed with this summary

## Files Created/Modified

- `src/cubano/engines/mock.py` - MockEngine class: __init__, to_sql(), execute() with full type hints and docstrings
- `src/cubano/engines/sql.py` - Added SQLBuilder class with build_select() and helper methods (_build_select_clause, _build_from_clause, _build_where_clause, _build_group_by_clause, _build_order_by_clause, _build_limit_clause)
- `src/cubano/engines/__init__.py` - Added MockEngine to imports and __all__
- `src/cubano/engines/base.py` - Updated execute() docstring with Row Phase 4 clarification

## Decisions Made

1. **SQLBuilder implementation as blocking dependency fix:** SQLBuilder is technically 03-02 work but was required for MockEngine to function. Rather than return a checkpoint requesting 03-02 first, implemented it as RULE 3 auto-fix (blocking issue). Documented in deviations.

2. **Raw fixture data without filtering:** MockEngine returns fixture data as-is in Phase 3. Full filtering/aggregation validation happens in Phase 4-6 with real backends. This keeps Phase 3 focused on structure validation.

3. **MockDialect for consistency:** MockEngine uses MockDialect (Snowflake-compatible syntax) for consistency. Enables teams to develop with one dialect and switch backends in Phase 5-6.

4. **Row class deferred to Phase 4:** Added clarifying docstring instead of implementing Row. MockEngine returns dicts; Phase 4 will standardize with Row class that provides dict-like and attribute access.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Implemented SQLBuilder (scheduled for 03-02 but required by 03-03)**

- **Found during:** Task 1 (MockEngine implementation)
- **Issue:** Plan assumes SQLBuilder exists (line 87 says `builder.build_select(query)`), but SQLBuilder was planned for 03-02 and not yet created. Cannot complete 03-03 without it.
- **Fix:** Implemented complete SQLBuilder class in src/cubano/engines/sql.py with:
  - `build_select(query)` - orchestrates all clauses
  - `_build_select_clause()` - SELECT with wrapped metrics and quoted dimensions
  - `_build_from_clause()` - FROM with quoted view name
  - `_build_where_clause()` - WHERE placeholder (full Q-object rendering in Phase 4)
  - `_build_group_by_clause()` - GROUP BY ALL
  - `_build_order_by_clause()` - ORDER BY with direction and NULLS handling
  - `_build_limit_clause()` - LIMIT clause
- **Architecture:** Composable string builder pattern (not AST) using Dialect for backend-specific syntax
- **Files modified:** src/cubano/engines/sql.py
- **Verification:**
  - basedpyright passes (strict mode)
  - ruff format and ruff check pass
  - Manual test: Query generates correct SQL: `SELECT AGG("revenue"), "country" FROM "sales_view" GROUP BY ALL`
- **Committed in:** cddc2e1 (separate commit, can be attributed to 03-02)
- **Note:** This is not scope creep - SQLBuilder was always planned and designed in research. The timing was adjusted based on dependency analysis.

---

**Total deviations:** 1 auto-fixed (1 blocking dependency)
**Impact on plan:** Auto-fix necessary for task completion. No scope creep - SQLBuilder was already designed and planned. Only timing adjusted based on dependency discovery.

## Issues Encountered

None - all tasks executed smoothly. Type hints required adjustment (using `Any` for Query parameters in SQLBuilder and MockEngine due to circular import prevention), but resolved cleanly without affecting functionality.

## Verification Results

### Manual Tests

```python
from cubano import Query, SemanticView, Metric, Dimension
from cubano.engines import MockEngine

class Sales(SemanticView, view='sales_view'):
    revenue = Metric()
    country = Dimension()

fixtures = {'sales_view': [
    {'revenue': 1000, 'country': 'US'},
    {'revenue': 500, 'country': 'CA'},
]}

engine = MockEngine(fixtures=fixtures)
q = Query().metrics(Sales.revenue).dimensions(Sales.country)

# SQL generation works
sql = engine.to_sql(q)
# Produces: SELECT AGG("revenue"), "country"
#           FROM "sales_view"
#           GROUP BY ALL

# Fixture execution works
results = engine.execute(q)
# Returns: [{'revenue': 1000, 'country': 'US'}, {'revenue': 500, 'country': 'CA'}]
```

### Quality Gates

- ✅ `uv run basedpyright` - 0 errors (strict mode)
- ✅ `uv run ruff check` - All checks passed
- ✅ `uv run ruff format --check` - All files formatted
- ✅ `uv run pytest` - 113 tests passed

All quality gates pass without issues.

## User Setup Required

None - no external service configuration required. MockEngine uses only stdlib and existing Cubano internals.

## Next Phase Readiness

**Phase 3 SQL Generation & Mock Backend is functionally complete:**

- ✅ Engine ABC (03-01): Abstract interface for all backends
- ✅ Dialect pattern (03-01): Backend-specific SQL syntax
- ✅ SQLBuilder (03-02/blocking-fix): Composable SQL generation
- ✅ MockEngine (03-03): Testing without warehouse connection

**Ready for:**
- Phase 4: Result set handling (Row class, filtering/aggregation logic)
- Phase 5: Real Snowflake backend implementation
- Phase 6: Real Databricks backend implementation
- Integration tests: Full workflow tests against MockEngine, then real backends

**No blockers identified.**

---

*Phase: 03-sql-generation-mock-backend*
*Plan: 03*
*Completed: 2026-02-15*
*Executor: Claude Haiku 4.5*
