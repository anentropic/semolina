---
phase: 36-duckdb-codegen
plan: 01
subsystem: codegen
tags: [duckdb, introspection, type-mapping, semantic-views, codegen]

# Dependency graph
requires:
  - phase: 33-duckdb-dialect-packaging
    provides: DuckDBDialect and DuckDB extension packaging
provides:
  - DuckDBEngine class with two-step introspection (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT)
  - duckdb_type_to_python() function mapping 20 DuckDB SQL types to Python annotations
  - DuckDBEngine exported from semolina.engines
affects: [36-02-duckdb-codegen, cli-codegen]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-step-duckdb-introspection, native-duckdb-driver-for-introspection]

key-files:
  created:
    - src/semolina/engines/duckdb.py
    - tests/unit/test_duckdb_engine.py
  modified:
    - src/semolina/codegen/type_map.py
    - tests/unit/codegen/test_type_map.py
    - src/semolina/engines/__init__.py

key-decisions:
  - "Used native duckdb driver (not ADBC) because ADBC returns VARCHAR for all columns in DESCRIBE SELECT FROM semantic_view()"
  - "Two-step introspection: DESCRIBE SEMANTIC VIEW for field structure + DESCRIBE SELECT for types, since DATA_TYPE is always empty in DESCRIBE SEMANTIC VIEW"
  - "PRIVATE fields excluded from introspection output -- they cannot be queried directly"
  - "DuckDBEngine is introspection-only: to_sql() and execute() raise NotImplementedError"
  - "IOException caught during connect() by moving connect inside try block for proper error mapping"

patterns-established:
  - "Two-step DuckDB introspection: structure from DESCRIBE SEMANTIC VIEW, types from DESCRIBE SELECT FROM semantic_view()"
  - "duckdb_type_to_python() takes plain string type names (not dicts like Snowflake/Databricks), strips parenthesized params"

requirements-completed: [DKGEN-01, DKGEN-02]

# Metrics
duration: 6min
completed: 2026-04-26
---

# Phase 36 Plan 01: DuckDB Codegen Summary

**DuckDBEngine with two-step introspection (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT) and duckdb_type_to_python() mapping 20 SQL types**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-26T22:31:30Z
- **Completed:** 2026-04-26T22:37:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Implemented `duckdb_type_to_python()` with 20-entry type map covering all common DuckDB SQL types (VARCHAR, INTEGER, BIGINT, DOUBLE, BOOLEAN, DATE, TIMESTAMP, TIME, BLOB, INTERVAL, unsigned ints, timezone-qualified types)
- Implemented `DuckDBEngine.introspect()` with two-step approach: DESCRIBE SEMANTIC VIEW for field kinds and DESCRIBE SELECT FROM semantic_view() for type resolution
- PRIVATE metrics/facts correctly excluded from output; unmappable types produce "TODO:" prefixed data_type
- Proper error handling: CatalogException -> SemolinaViewNotFoundError, IOException -> SemolinaConnectionError

## Task Commits

Each task was committed atomically:

1. **Task 1: DuckDB type map function and tests** - `2933df2` (test: RED) -> `c772db3` (feat: GREEN)
2. **Task 2: DuckDBEngine class with two-step introspection** - `53b6e30` (test: RED) -> `e26b220` (feat: GREEN)

_TDD tasks have separate test and implementation commits._

## Files Created/Modified
- `src/semolina/engines/duckdb.py` - DuckDBEngine class with introspect(), _to_pascal_case(), _parse_describe_semantic_view()
- `src/semolina/codegen/type_map.py` - Added _DUCKDB_TYPE_MAP dict and duckdb_type_to_python() function
- `src/semolina/engines/__init__.py` - Added DuckDBEngine import and __all__ export
- `tests/unit/test_duckdb_engine.py` - 20 test methods covering init, introspection, error handling, NotImplementedError
- `tests/unit/codegen/test_type_map.py` - 28 new DuckDB test methods in TestDuckDBTypeToPython class

## Decisions Made
- Used native duckdb driver (not ADBC) because ADBC returns VARCHAR for all columns in DESCRIBE SELECT FROM semantic_view() -- verified in research phase
- DuckDBEngine takes a `database` keyword arg (file path or `:memory:`) instead of `**connection_params` like Snowflake/Databricks, since DuckDB is file-based
- `duckdb_type_to_python()` takes a plain string type name (not a dict) since DuckDB's DESCRIBE SELECT returns raw type strings, not structured metadata
- Connection opened inside try block (not before it) to ensure IOException from connect() is properly caught and mapped to SemolinaConnectionError

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] IOException not caught when duckdb.connect() fails**
- **Found during:** Task 2 (DuckDBEngine implementation)
- **Issue:** Initial implementation had `conn = duckdb.connect(...)` before the try block, so IOException from connect() was uncaught
- **Fix:** Moved connect() inside try block with `conn = None` sentinel and conditional close in finally
- **Files modified:** src/semolina/engines/duckdb.py
- **Verification:** test_io_exception_raises_connection_error passes
- **Committed in:** e26b220

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor fix necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing test failures in test_databricks_engine.py and test_snowflake_engine.py (mock patching of `databricks` / `snowflake.connector` parent modules is incomplete). These are NOT caused by this plan's changes and are out of scope. Logged for awareness.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DuckDBEngine.introspect() is ready for integration with CLI codegen command
- Plan 36-02 can add `"duckdb"` alias to `_resolve_backend()` in `cli/codegen.py`
- The existing `python_renderer.py` works with any IntrospectedView -- no renderer changes needed

## Self-Check: PASSED

All 6 files found. All 4 commit hashes verified. All 18 acceptance criteria confirmed.

---
*Phase: 36-duckdb-codegen*
*Completed: 2026-04-26*
