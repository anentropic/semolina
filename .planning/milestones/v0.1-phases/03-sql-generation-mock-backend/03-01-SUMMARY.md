---
phase: 03-sql-generation-mock-backend
plan: 01
subsystem: Engine Architecture & Dialects
tags: [engines, dialects, sql-generation, architecture]
dependency_graph:
  requires: []
  provides: [Engine ABC, Dialect ABC, SnowflakeDialect, DatabricksDialect, MockDialect]
  affects: [03-02-PLAN (SQL generator), 03-03-PLAN (MockEngine), 03-04-PLAN (Integration)]
tech_stack:
  added: [abc (ABC, abstractmethod)]
  patterns: [ABC pattern, Dialect pattern]
  zero_dependencies: true
key_files:
  created:
    - src/cubano/engines/__init__.py (18 lines)
    - src/cubano/engines/base.py (108 lines)
    - src/cubano/engines/sql.py (267 lines)
decisions: []
metrics:
  duration: 12 min
  completed: 2026-02-15T15:47:29Z
---

# Phase 3 Plan 1: Engine ABC & Dialect Architecture Summary

## Objective

Build the Engine ABC base class and dialect architecture for backend-agnostic SQL generation. This establishes the abstract interface and dialect-specific implementations (Snowflake, Databricks, Mock) that will power SQL generation in subsequent plans.

## Deliverables

### 1. Engine ABC Base Class (`src/cubano/engines/base.py`)

**Purpose:** Abstract interface for all SQL generation and query execution backends.

**Key abstractions:**
- `to_sql(query: Query) -> str`: Convert Query to SQL string (dialect-specific)
- `execute(query: Query) -> list[Any]`: Execute and return results (backend-specific)

**Architecture decisions:**
- Uses `from __future__ import annotations` for forward references
- TYPE_CHECKING import for Query type hints to avoid circular imports
- Comprehensive docstrings with Args/Returns/Raises sections explaining that subclasses may raise backend-specific errors
- 108 lines with detailed documentation

**Exports:** Public via `cubano.engines.Engine`

### 2. Dialect ABC & Implementations (`src/cubano/engines/sql.py`)

**Purpose:** Encapsulate SQL generation rules for each backend.

**Dialect ABC:**
- `quote_identifier(name: str) -> str`: Quote identifiers for SQL
- `wrap_metric(field_name: str) -> str`: Wrap metrics (AGG vs MEASURE)
- Comprehensive docstrings explaining identifier quoting vs string literals
- Examples showing escaping patterns for each dialect

**SnowflakeDialect:**
- Identifier quoting: Double quotes (`"`)
- Escape rule: Internal `"` → `""`
- Metric wrapping: AGG() function
- Example: `'my"field'` → `"my""field"` → wrapped as `AGG("my""field")`

**DatabricksDialect:**
- Identifier quoting: Backticks (`` ` ``)
- Escape rule: Internal `` ` `` → ` `` `
- Metric wrapping: MEASURE() function
- Example: `'my`field'` → `` `my``field` `` → wrapped as `MEASURE(`my``field`)`

**MockDialect:**
- Identifier quoting: Double quotes like Snowflake (consistency for testing)
- Escape rule: Same as Snowflake
- Metric wrapping: AGG() like Snowflake for Snowflake-compatible mock SQL
- Enables MockEngine to validate query structure without warehouse connection

**File stats:** 267 lines with detailed docstrings including escaping examples

**Exports:** Public via `cubano.engines.Dialect`, `cubano.engines.SnowflakeDialect`, `cubano.engines.DatabricksDialect`, `cubano.engines.MockDialect`

### 3. Public API (`src/cubano/engines/__init__.py`)

**Purpose:** Clean exports of Engine ABC and Dialect classes.

**Exports:**
```python
from cubano.engines import (
    Engine,
    Dialect,
    SnowflakeDialect,
    DatabricksDialect,
    MockDialect,
)
```

**__all__ list:** Complete with all 5 exports

## Verification Results

### Module Structure
- ✓ `src/cubano/engines/` directory exists with `__init__.py`, `base.py`, `sql.py`
- ✓ All files are proper Python modules with correct imports
- ✓ No circular imports (uses TYPE_CHECKING for forward references)

### Engine ABC
- ✓ Inherits from ABC
- ✓ `to_sql(query: Query) -> str` is abstract method with @abstractmethod
- ✓ `execute(query: Query) -> list[Any]` is abstract method with @abstractmethod
- ✓ Both methods have comprehensive docstrings with Args/Returns/Raises sections
- ✓ Forward references to Query avoid circular dependency with cubano.query

### Dialect ABC & Implementations
- ✓ Dialect is abstract class with @abstractmethod decorators
- ✓ `quote_identifier(name: str) -> str` is abstract method
- ✓ `wrap_metric(field_name: str) -> str` is abstract method
- ✓ All three dialects implement both methods correctly

### Identifier Quoting
```
SnowflakeDialect('my_field')       → "my_field"
SnowflakeDialect('my"field')       → "my""field"    ✓ Correct escaping
DatabricksDialect('my_field')      → `my_field`
DatabricksDialect('my`field')      → `my``field`    ✓ Correct escaping
MockDialect('my_field')            → "my_field"
MockDialect('my"field')            → "my""field"    ✓ Correct escaping
```

### Metric Wrapping
```
SnowflakeDialect.wrap_metric('revenue')     → AGG("revenue")         ✓
DatabricksDialect.wrap_metric('revenue')    → MEASURE(`revenue`)     ✓
MockDialect.wrap_metric('revenue')          → AGG("revenue")         ✓
```

### Quality Gates
- ✓ `uv run basedpyright src/cubano/engines/` — 0 errors
- ✓ `uv run ruff check src/cubano/engines/` — All checks passed
- ✓ `uv run ruff format --check src/cubano/engines/` — All files formatted
- ✓ `uv run --extra dev pytest tests/` — All 113 tests pass

### Public API
- ✓ All 5 classes are exported in `__all__` list
- ✓ Imports work correctly: `from cubano.engines import Engine, Dialect, ...`
- ✓ Type hints are resolvable by basedpyright (strict mode)

## Architecture Impact

### What This Enables

**Phase 3-02 (SQL Generator):** Can now use these dialects to generate backend-specific SQL:
```python
query = Query().metrics(Sales.revenue).dimensions(Sales.country)
dialect = SnowflakeDialect()
sql_gen = SQLGenerator(dialect)
sql = sql_gen.build_select(query)  # SELECT "revenue", "country" FROM "sales" GROUP BY ALL
```

**Phase 3-03 (MockEngine):** Can now implement execution backend:
```python
class MockEngine(Engine):
    def __init__(self, fixtures):
        self.dialect = MockDialect()

    def to_sql(self, query: Query) -> str:
        # Uses MockDialect for SQL generation

    def execute(self, query: Query) -> list[Any]:
        # Returns fixture data
```

**Phase 3-04 (Integration):** Can test entire query pipeline with MockEngine before real backends

### Zero Dependencies

- All stdlib: `abc` (abstractmethod, ABC)
- No third-party libraries needed for Phase 3-01
- Follows project policy of zero runtime dependencies

### Design Decisions

1. **Dialect pattern over centralized config:** Each backend gets a Dialect class, not a config object. Enables extensibility and type safety.

2. **quote_identifier() separate from wrap_metric():** Two methods allow generators to quote identifiers independently (table names, etc.) without always wrapping in AGG/MEASURE.

3. **MockDialect uses Snowflake syntax:** Simplifies MockEngine implementation and test data consistency.

4. **Forward references in Engine ABC:** Uses TYPE_CHECKING to import Query only for type hints, avoiding circular dependency with cubano.query module.

5. **Comprehensive docstrings:** Every method documents escaping behavior, edge cases, and dialect-specific differences to guide SQL generator implementation.

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] All three files exist in src/cubano/engines/
- [x] Engine ABC with to_sql() and execute() abstract methods
- [x] Dialect ABC with quote_identifier() and wrap_metric() abstract methods
- [x] Three dialect implementations (Snowflake, Databricks, Mock)
- [x] All methods have comprehensive docstrings with examples
- [x] Escaping is correct (double quotes/backticks, proper escaping)
- [x] All files pass basedpyright (strict), ruff check, ruff format
- [x] __init__.py exports all public classes

## Self-Check

**Verification of claims in this summary:**

1. **Files exist:**
   - [x] src/cubano/engines/__init__.py (18 lines)
   - [x] src/cubano/engines/base.py (108 lines)
   - [x] src/cubano/engines/sql.py (267 lines)

2. **Commits exist:**
   - [x] b86c7c8: Engine ABC base class
   - [x] 0645882: Dialect ABC with implementations
   - [x] 2ecfa89: __init__.py public API

3. **Quality gates:**
   - [x] basedpyright: 0 errors
   - [x] ruff check: All passed
   - [x] ruff format: All formatted
   - [x] pytest: 113 passed (no failures)

4. **Imports work:**
   - [x] `from cubano.engines import Engine`
   - [x] `from cubano.engines import Dialect`
   - [x] `from cubano.engines import SnowflakeDialect`
   - [x] `from cubano.engines import DatabricksDialect`
   - [x] `from cubano.engines import MockDialect`

5. **Escaping verified:**
   - [x] SnowflakeDialect: 'my"field' → "my""field" ✓
   - [x] DatabricksDialect: 'my`field' → `my``field` ✓
   - [x] MockDialect: 'my"field' → "my""field" ✓

## Next Steps

Plan 03-02 (SQL Generator) will:
1. Use Engine ABC to define SQLGenerator
2. Use Dialect instances to generate dialect-specific SQL
3. Build SELECT/FROM/WHERE/GROUP BY/ORDER BY/LIMIT clauses
4. Integrate with Query object to generate full SQL

Plan 03-03 (MockEngine) will:
1. Implement Engine interface
2. Use MockDialect for validation
3. Return fixture data for testing
4. Enable query testing without warehouse

Plan 03-04 (Integration) will:
1. Integrate MockEngine into Query.fetch()
2. Add engine registry pattern
3. Create end-to-end test scenarios
