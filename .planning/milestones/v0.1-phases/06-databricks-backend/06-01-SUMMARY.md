---
phase: 06-databricks-backend
plan: 01
subsystem: engines/databricks
tags:
  - databricks-backend
  - lazy-import
  - connection-management
  - error-handling
  - sql-generation
dependency_graph:
  requires:
    - Phase 03-SQL generation (SQLBuilder, DatabricksDialect)
    - Phase 04-Execution results (Query, Registry)
  provides:
    - DatabricksEngine for semantic view execution
    - Lazy import pattern for optional drivers
  affects:
    - Phase 06-02 (DatabricksEngine tests)
    - User API for Databricks backend selection
tech_stack:
  added:
    - DatabricksEngine class (src/cubano/engines/databricks.py)
  patterns:
    - Lazy import with ImportError translation
    - Context managers for resource cleanup
    - Error translation to RuntimeError
    - Delegation to SQLBuilder + Dialect
key_files:
  created:
    - src/cubano/engines/databricks.py (228 lines)
  modified:
    - src/cubano/engines/__init__.py (added DatabricksEngine export)
metrics:
  tasks: 2
  duration: 1 min
  completion_date: 2026-02-16
  commits: 2
---

# Phase 6 Plan 1: DatabricksEngine Implementation Summary

Implement DatabricksEngine with lazy driver import, connection management, and error handling. Enable queries to execute against Databricks Metric Views with MEASURE() syntax support and proper connection lifecycle.

## Objective

Build a production-ready DatabricksEngine that:
- Lazily imports databricks-sql-connector only on instantiation
- Manages connection lifecycle with context managers for guaranteed cleanup
- Generates SQL using reused SQLBuilder + DatabricksDialect from Phase 3
- Translates Databricks errors to helpful RuntimeError messages
- Maps query results from tuples to dicts with column names
- Supports Unity Catalog three-part names transparently
- Integrates seamlessly into the public API

## Execution Summary

**Status:** COMPLETE

All tasks executed successfully with no deviations. DatabricksEngine is fully implemented, exported from public API, and passes all quality gates.

### Task Completion

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Create DatabricksEngine with lazy import and connection management | ✓ COMPLETE | 3135324 | src/cubano/engines/databricks.py |
| 2 | Export DatabricksEngine in public API and run quality gates | ✓ COMPLETE | 6f27e91 | src/cubano/engines/__init__.py |

## What Was Built

### DatabricksEngine Class (228 lines)

A fully-featured backend engine for Databricks semantic views with:

**Lazy Import Pattern:**
- Imports databricks.sql only when DatabricksEngine instantiated
- Prevents ImportError for users without databricks-sql-connector
- Clear error message suggests installation: `pip install cubano[databricks]`

**Connection Lifecycle:**
- Stores connection parameters in `__init__` without creating connection
- Creates connection per `execute()` call using context managers
- Nested context managers guarantee cleanup (connection and cursor)
- No connection pooling (Databricks driver handles internally)

**SQL Generation:**
- Delegates to `SQLBuilder(DatabricksDialect)` from Phase 3
- Generates MEASURE() wrapping for metrics (Databricks-specific)
- Uses backtick-quoted identifiers for case preservation
- GROUP BY ALL for automatic dimension derivation

**Result Mapping:**
- Extracts column names from cursor.description
- Maps query result tuples to list[dict[str, Any]]
- Consistent format with MockEngine and SnowflakeEngine

**Error Handling:**
- Catches OperationalError (connection, permissions, authentication)
- Catches DatabaseError (SQL syntax, invalid objects)
- Catches generic Error for other Databricks exceptions
- Translates to RuntimeError with helpful messages
- Preserves exception chain with `from e` for debugging

**Unity Catalog Support:**
- Three-part names (catalog.schema.view) work transparently
- DatabricksDialect quotes each part separately with backticks
- No additional implementation needed in DatabricksEngine

### Public API Export

Updated `src/cubano/engines/__init__.py` to:
- Import DatabricksEngine from databricks module
- Add DatabricksEngine to `__all__` list
- Enable `from cubano.engines import DatabricksEngine`

## Quality Gates: All Passed

✓ **basedpyright (strict mode):** 0 errors, 0 warnings, 0 notes
- Proper type annotations on all public methods
- TYPE_CHECKING imports prevent circular dependencies
- Connection parameters typed as `**kwargs: Any` with `dict[str, Any]` for storage

✓ **ruff (linting):** All checks passed
- Proper import organization (TYPE_CHECKING, lazy imports)
- No unused imports, proper noqa comments

✓ **ruff (formatting):** All files formatted correctly
- 100 char line length enforced
- D213 docstring style (summary on second line)

✓ **pytest:** 265 tests pass, no regressions
- All existing engine, query, field, model, registry, and SQL tests still pass
- New DatabricksEngine doesn't break any existing functionality

## Verification Against Success Criteria

1. **DatabricksEngine class exists in src/cubano/engines/databricks.py** ✓
   - File created with 228 lines (exceeds 150 minimum)
   - Inherits from Engine ABC
   - Implements to_sql() and execute() abstract methods

2. **Lazy import prevents ImportError for users without databricks-sql-connector** ✓
   - TYPE_CHECKING guard prevents import at module load time
   - __init__ imports databricks.sql with try/except
   - Clear error message with installation instructions

3. **Connection parameters stored but connection deferred to execute() time** ✓
   - __init__ stores **connection_params in self._connection_params
   - execute() creates connection fresh on each call
   - Prevents expensive setup during instantiation

4. **Context managers guarantee connection cleanup** ✓
   - Uses nested with statements: `with ... as conn, conn.cursor() as cur:`
   - Cleanup guaranteed even on exceptions
   - Tested pattern matches SnowflakeEngine

5. **SQL generation delegates to existing SQLBuilder + DatabricksDialect** ✓
   - to_sql() creates SQLBuilder(self.dialect)
   - Calls builder.build_select(query)
   - Generates MEASURE() syntax and backtick quoting

6. **Results mapped from tuples to dicts using cursor.description** ✓
   - Extracts column names: `columns = [desc[0] for desc in cur.description]`
   - Maps tuples to dicts: `[dict(zip(columns, row, strict=True)) for row in rows]`
   - Returns list[dict[str, Any]]

7. **Databricks errors translated to helpful RuntimeError messages** ✓
   - Catches OperationalError (connection, permissions)
   - Catches DatabaseError (SQL, objects)
   - Catches generic Error fallback
   - Translates to RuntimeError with original message

8. **Unity Catalog three-part naming works transparently** ✓
   - DatabricksDialect handles backtick quoting of each part
   - Connection parameters include catalog/schema if needed
   - No special handling required in DatabricksEngine

9. **DatabricksEngine exported from cubano.engines public API** ✓
   - Added import in __init__.py: `from .databricks import DatabricksEngine`
   - Added to __all__ list
   - Verified: `from cubano.engines import DatabricksEngine` works

10. **All quality gates pass (basedpyright, ruff, pytest)** ✓
    - basedpyright: 0 errors
    - ruff check: All passed
    - ruff format: All formatted
    - pytest: 265 tests pass

11. **No regressions in existing tests** ✓
    - All 265 tests continue to pass
    - No modifications to existing test files
    - New code is additive only

## Deviations from Plan

None. Plan executed exactly as specified.

## Decisions Made

**Error handling hierarchy:** OperationalError caught before DatabaseError because in some implementations OperationalError may extend DatabaseError. This ensures proper categorization of connection errors vs. query errors.

**Type annotations on cursor:** Used explicit `Any` type for cursor.description and fetchall() results with type: ignore comments. This is standard practice for untyped external libraries (databricks.sql is not fully typed).

## Architecture Notes

**Consistency with SnowflakeEngine:**
DatabricksEngine mirrors SnowflakeEngine structure exactly:
- Same lazy import pattern (try/except with clear error message)
- Same connection parameter storage model
- Same context manager pattern for cleanup
- Same result mapping approach (list of dicts)
- Same error translation strategy

**Phase 3 SQL Generation Reuse:**
- Zero new SQL generation logic
- Delegates entirely to SQLBuilder + DatabricksDialect
- DatabricksDialect already handles MEASURE() wrapping and backtick quoting
- No duplication of Phase 3 work

**Connection Lifecycle:**
- Fresh connection per execute() call (no pooling in this layer)
- Deferred connection eliminates setup cost for cases where engine is created but not used
- Context managers guarantee cleanup even on SQL syntax errors or permission failures
- Matches Snowflake driver behavior

## Testing Strategy

Phase 06-02 will implement comprehensive unit tests for DatabricksEngine:
- Mock databricks.sql at module level
- Test lazy import error handling (ImportError)
- Test connection lifecycle with context managers
- Test SQL generation via to_sql()
- Test result mapping (tuples to dicts)
- Test error translation (Databricks errors to RuntimeError)
- Test with various connection parameters

## Next Steps

- **Phase 06-02:** Implement comprehensive DatabricksEngine unit tests
  - Mock databricks.sql.connect for testing without credentials
  - Test lazy import pattern
  - Test connection/cursor lifecycle
  - Test SQL generation (delegates to SQLBuilder)
  - Test result mapping and error handling

## Files Modified

```
src/cubano/engines/
├── databricks.py (NEW - 228 lines)
└── __init__.py (modified - added DatabricksEngine export)
```

## Summary Statistics

- **Plan Duration:** 1 minute
- **Tasks Completed:** 2 of 2
- **Commits Created:** 2
- **Lines of Code:** 228 (new DatabricksEngine class)
- **Quality Gates:** All passed (0 type errors, 0 lint errors, 265 tests)
- **Deviations:** None
- **Blockers:** None

## Self-Check

All verification commands passed:

✓ File exists: src/cubano/engines/databricks.py (228 lines, exceeds 150 minimum)
✓ uv run basedpyright: 0 errors, 0 warnings, 0 notes
✓ uv run ruff check: All checks passed
✓ uv run ruff format --check: All files formatted
✓ uv run --extra dev pytest: 265 passed in 1.20s
✓ from cubano.engines import DatabricksEngine: Success
✓ DatabricksEngine.__init__: Present
✓ DatabricksEngine.to_sql: Present
✓ DatabricksEngine.execute: Present
✓ DatabricksEngine exported in __all__: Yes
✓ No test regressions: 265 tests still pass

**Status: PASSED** - All success criteria met, all quality gates passing, ready for Phase 06-02 testing plan.
