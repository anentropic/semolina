---
phase: 03-sql-generation-mock-backend
plan: 02
subsystem: SQL Generation
tags: [sql-generation, dialects, query-builder, composable-sql]

requires:
  - phase: 03-sql-generation-mock-backend
    plan: 01
    provides: Engine ABC, Dialect ABC, SnowflakeDialect, DatabricksDialect, MockDialect

provides:
  - SQLBuilder class for composable SQL generation
  - Query.to_sql() implementation using MockDialect
  - Full SQL generation pipeline (SELECT/FROM/WHERE/GROUP BY/ORDER BY/LIMIT clauses)

affects:
  - 03-03-PLAN (MockEngine implementation)
  - 03-04-PLAN (Integration testing)

tech_stack:
  added: []
  patterns: [Composable SQL Builder, Dialect pattern]
  zero_dependencies: true

key_files:
  created: []
  modified:
    - src/cubano/engines/sql.py (SQLBuilder class added)
    - src/cubano/query.py (Query.to_sql() implementation)
    - tests/test_query.py (Updated to_sql test)

key_decisions:
  - SQLBuilder uses composable string building (not AST) for known query structure
  - GROUP BY ALL for automatic dimension derivation (both Snowflake and Databricks compatible)
  - WHERE clause placeholder for Phase 4 (Q-object rendering complex, deferred)
  - Query.to_sql() uses MockDialect by default for inspection/debugging

patterns_established:
  - SQLBuilder pattern: Dialect-specific SQL generation via _build_*_clause() methods
  - Deferred validation: Q-object to SQL translation deferred to Phase 4

metrics:
  duration: 5 min
  tasks: 2
  files_modified: 3
  completed: 2026-02-15T16:00:00Z

---

# Phase 3 Plan 2: SQL Generation & Mock Backend Summary

**SQLBuilder class generates dialect-specific SQL from Query objects with proper identifier quoting, metric wrapping (AGG/MEASURE), and GROUP BY ALL auto-derivation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-15T15:55:00Z
- **Completed:** 2026-02-15T16:00:00Z
- **Tasks:** 2
- **Files modified:** 3
- **Quality gates:** All passed (basedpyright, ruff check, ruff format, 113 tests)

## Accomplishments

- SQLBuilder class with composable SQL generation (SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT clauses)
- Metric wrapping via Dialect.wrap_metric() (AGG for Snowflake/Mock, MEASURE for Databricks)
- Dimension/fact quoting via Dialect.quote_identifier() with dialect-specific escaping
- Query.to_sql() generates SQL using MockDialect by default for inspection/debugging
- GROUP BY ALL support for automatic dimension grouping (Snowflake/Databricks compatible)
- Full ORDER BY support with direction (ASC/DESC) and NULLS FIRST/LAST handling
- All 113 tests pass with updated test for SQL generation

## Task Commits

1. **Task 1: SQLBuilder class implementation** - `cddc2e1` (feat)
   - Already committed in prior execution
   - SQLBuilder with build_select() and 6 helper methods
   - Full docstrings with examples

2. **Task 2: Query.to_sql() implementation** - `610affe` (feat)
   - Query.to_sql() now generates SQL instead of raising NotImplementedError
   - Uses SQLBuilder(MockDialect()) for default SQL generation
   - Updated test_to_sql_validates_then_generates_sql to verify SQL output
   - Inline imports to avoid circular dependency with Query module

## Files Created/Modified

- `src/cubano/engines/sql.py` - Added SQLBuilder class with 7 methods and comprehensive docstrings
- `src/cubano/query.py` - Updated Query.to_sql() to generate SQL
- `tests/test_query.py` - Updated test_to_sql_validates_then_raises to test SQL generation

## SQL Generation Examples

**Simple query with metric and dimension:**
```sql
SELECT AGG("revenue"), "country"
FROM "sales_view"
GROUP BY ALL
```

**With limit:**
```sql
SELECT AGG("revenue"), "country"
FROM "sales_view"
GROUP BY ALL
LIMIT 100
```

**With ORDER BY (descending):**
```sql
SELECT AGG("revenue"), "country"
FROM "sales_view"
GROUP BY ALL
ORDER BY "revenue" DESC
```

## Architecture Details

### SQLBuilder Design

- **Composable pattern:** Builds SQL by composing individual clauses (not AST approach)
- **Dialect-aware:** Uses Dialect instance for identifier quoting and metric wrapping
- **Method organization:** Public build_select() delegates to _build_*_clause() helpers
- **Type safety:** Full type hints with TYPE_CHECKING for Query forward reference

### Clause Implementations

1. **SELECT clause** - Wraps metrics with dialect.wrap_metric(), quotes dimensions with dialect.quote_identifier()
2. **FROM clause** - Extracts view name from first field's owner model, quotes with dialect
3. **WHERE clause** - Placeholder for Phase 4 (returns "WHERE 1=1", Q-object rendering complex)
4. **GROUP BY clause** - Returns "GROUP BY ALL" (auto-derivation supported by both Snowflake/Databricks)
5. **ORDER BY clause** - Handles bare Fields (ASC default) and OrderTerms (with direction + NULLS handling)
6. **LIMIT clause** - Returns "LIMIT n" when limit_value set

### Query.to_sql() Design

- Inline imports of SQLBuilder and MockDialect avoid circular imports
- Uses MockDialect for inspection/debugging (Snowflake-compatible)
- Deferred validation via _validate_for_execution() before SQL generation
- Updated docstring explains MockDialect is used by default

## Decisions Made

- **SQLBuilder over centralized function:** Class approach allows stateful dialect management and future extensibility
- **Inline imports in Query.to_sql():** Avoids circular import between query and engines modules
- **GROUP BY ALL over manual dimension listing:** Simpler, more maintainable, auto-derived from SELECT
- **WHERE placeholder for Phase 4:** Q-object to SQL rendering complex, requires separate filter compiler
- **MockDialect as default for Query.to_sql():** Enables inspection/debugging without backend specification

## Deviations from Plan

**None - plan executed exactly as written.**

Task 1 (SQLBuilder class creation) was completed in prior execution and committed as `cddc2e1`. Task 2 (Query.to_sql() implementation) was completed in this execution exactly as specified in the plan.

## Quality Gate Verification

- **basedpyright (strict mode):** 0 errors, 0 warnings ✓
- **ruff check:** All checks passed ✓
- **ruff format:** All files formatted (100 char line length) ✓
- **pytest:** All 113 tests pass (49 query tests) ✓

## Test Coverage

Updated `test_to_sql_validates_then_generates_sql` to verify:
- Empty query raises ValueError (validation)
- Valid metric query generates SQL with AGG() wrapping
- SQL contains proper FROM clause with view name
- SQL structure matches expected format

## Self-Check

**Verification of claims in this summary:**

1. **Files exist:**
   - [x] src/cubano/engines/sql.py (517 lines, SQLBuilder class)
   - [x] src/cubano/query.py (updated Query.to_sql())
   - [x] tests/test_query.py (updated test)

2. **Commits exist:**
   - [x] cddc2e1: SQLBuilder class implementation
   - [x] 610affe: Query.to_sql() implementation with updated test

3. **Quality gates:**
   - [x] basedpyright: 0 errors
   - [x] ruff check: All passed
   - [x] ruff format: All formatted
   - [x] pytest: 113 tests passed

4. **Functionality verified:**
   - [x] SQLBuilder.build_select() generates valid SQL
   - [x] Metrics wrapped with AGG() (MockDialect)
   - [x] Dimensions quoted with " (MockDialect)
   - [x] FROM clause quotes view name
   - [x] GROUP BY ALL when dimensions present
   - [x] ORDER BY with direction handling
   - [x] LIMIT clause when limit_value set
   - [x] Query.to_sql() returns SQL string (not NotImplementedError)

## Next Steps

Phase 3-03 (MockEngine) will:
1. Implement Engine interface extending Engine ABC
2. Use MockDialect for SQL generation (via SQLBuilder)
3. Support fixture-based data returns for testing
4. Validate query structure without warehouse connection

Phase 3-04 (Integration) will:
1. Integrate MockEngine into Query execution pipeline
2. Add engine registry for backend selection
3. Create end-to-end test scenarios
4. Prepare for real warehouse backends (Phase 5/6)

---

*Phase: 03-sql-generation-mock-backend Plan: 02*
*Completed: 2026-02-15*
