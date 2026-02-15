---
phase: 03-sql-generation-mock-backend
plan: 05
subsystem: engines
tags: [refactoring, testing, api-cleanup, gap-closure]

dependency_graph:
  requires: [03-01, 03-02, 03-03, 03-04]
  provides:
    - MockEngine with clean public API (no fixtures parameter)
    - pytest fixtures for test data injection
    - centralized test fixtures in conftest.py
  affects:
    - MockEngine.__init__ (signature change)
    - MockEngine.execute (now raises NotImplementedError)
    - test_engines.py (fixture injection)
    - test_sql.py (shared Sales model)

tech_stack:
  added: []
  patterns:
    - pytest fixture injection for test data
    - centralized test fixtures in conftest.py
    - separation of concerns (testing vs production API)

key_files:
  created:
    - tests/conftest.py: 81 lines, 3 pytest fixtures
  modified:
    - src/cubano/engines/mock.py: removed fixtures parameter, updated execute()
    - tests/test_engines.py: 27 tests using fixture injection
    - tests/test_sql.py: 54 tests using shared Sales model

decisions:
  - Remove fixtures parameter from MockEngine.__init__ to decouple testing from production API
  - Use pytest fixtures for test data injection instead of constructor parameters
  - Centralize Sales model in conftest.py for consistency across test files
  - MockEngine.execute() raises NotImplementedError (not available in gap closure phase)
  - Keep to_sql() functional for SQL generation testing

metrics:
  duration: 5min
  completed: 2026-02-15
  tasks: 5
  commits: 5
  tests_added: 0
  tests_modified: 81
  tests_passing: 81
  lines_added: 85
  lines_removed: 311
  net_change: -226
---

# Phase 03 Plan 05: MockEngine API Refactoring - Gap Closure

**One-liner:** Removed fixtures parameter from MockEngine constructor, using pytest fixtures for test data injection instead.

## Objective

Refactor MockEngine's public API to remove testing concerns (fixtures parameter) and use pytest fixtures for test data injection. This decouples testing logic from the engine's core design and provides a cleaner public API.

## What Changed

### API Refactoring

**Before:**
```python
# MockEngine.__init__ accepted fixtures parameter
fixtures = {'sales_view': [{'revenue': 1000, 'country': 'US'}]}
engine = MockEngine(fixtures=fixtures)
results = engine.execute(query)  # Returns fixture data
```

**After:**
```python
# MockEngine.__init__ has no parameters
engine = MockEngine()
sql = engine.to_sql(query)  # SQL generation only

# For testing with data, use pytest fixtures
@pytest.fixture
def sales_fixtures():
    return {'sales_view': [{'revenue': 1000, 'country': 'US'}]}

def test_something(sales_fixtures):
    # Use fixtures directly in assertions
    assert sales_fixtures['sales_view'][0]['revenue'] == 1000
```

### Centralized Test Fixtures

Created `tests/conftest.py` with reusable pytest fixtures:

1. **sales_model** - Sales SemanticView class (revenue, cost, country, region, unit_price)
2. **sales_fixtures** - Standard test data dict with 3 sample rows
3. **sales_engine** - MockEngine instance for SQL generation

### Test Strategy

**test_engines.py (27 tests):**
- Import Sales from conftest instead of local definition
- Removed all tests that passed fixtures to MockEngine constructor
- Added test for execute() raising NotImplementedError
- Updated integration tests to focus on SQL generation only

**test_sql.py (54 tests):**
- Import Sales from conftest for consistency
- No other changes needed (already focused on SQL generation)

## Files Modified

### Created Files

**tests/conftest.py** (81 lines)
- Sales SemanticView with 5 fields (revenue, cost, country, region, unit_price)
- sales_model fixture returning Sales class
- sales_fixtures fixture with 3 sample rows
- sales_engine fixture returning MockEngine()

### Modified Files

**src/cubano/engines/mock.py** (-67 lines, +50 lines)
- Removed fixtures parameter from __init__(self)
- Removed self.fixtures attribute
- Updated execute() to raise NotImplementedError with helpful message
- Updated class docstring with pytest fixture example
- to_sql() unchanged (continues to work)

**tests/test_engines.py** (-220 lines, +54 lines)
- Import Sales from conftest
- Removed TestMockEngineInit fixture-related tests (kept 2/4)
- Replaced TestMockEngineExecute tests with NotImplementedError test
- Updated TestMockEngineIntegration to remove execute() calls
- Updated TestENG01 to remove fixture parameter usage
- Simplified TestENG02 validation tests
- Replaced TestMockEngineFixtureFormats with TestMockEngineSQL

**tests/test_sql.py** (-12 lines, +4 lines)
- Import Sales from conftest
- Remove local Sales definition
- Remove unused imports (Dimension, Fact, Metric)

## Testing Strategy

### Pytest Fixture Injection

Tests now use pytest's fixture injection mechanism:

```python
# Old approach (coupled to MockEngine)
@pytest.fixture
def sales_fixtures(self):
    return {'sales_view': [...]}

def test_something(self, sales_fixtures):
    engine = MockEngine(fixtures=sales_fixtures)
    results = engine.execute(query)

# New approach (decoupled, clean)
def test_something(sales_engine):
    sql = sales_engine.to_sql(query)
    assert 'SELECT AGG("revenue")' in sql
```

### Centralized Test Data

Sales model now defined once in conftest.py:
- Ensures consistency across test_engines.py and test_sql.py
- Single source of truth for test models
- Easy to extend for other test files

## Deviations from Plan

None - plan executed exactly as written.

## Test Results

**All 81 tests passing:**
- 27 engine tests (test_engines.py)
- 54 SQL tests (test_sql.py)

**Test coverage:**
- MockEngine initialization without parameters
- MockEngine.to_sql() SQL generation
- MockEngine.execute() raising NotImplementedError
- Dialect SQL generation (Snowflake, Databricks, Mock)
- SQLBuilder SELECT, FROM, GROUP BY, ORDER BY, LIMIT clauses
- Query.to_sql() integration

## Quality Gate Status

**All quality gates pass:**

1. **Typecheck:** `uv run basedpyright` - 0 errors
2. **Lint:** `uv run ruff check` - 0 errors
3. **Format:** `uv run ruff format --check` - all files formatted
4. **Tests:** `uv run pytest` - 81/81 passing

## Commits

| Commit | Task | Description |
|--------|------|-------------|
| 607092f | 1 | Create central conftest with pytest fixtures |
| 48bbcc4 | 2 | Remove fixtures parameter from MockEngine |
| 5bddb05 | 3 | Update test_engines to use pytest fixtures |
| 9b59a79 | 4 | Update test_sql to use Sales from conftest |
| 4f6bd5f | 5 | Fix quality gate issues (imports, typecheck) |

## Self-Check

Verifying all claims from SUMMARY.md:

**Created files:**
- tests/conftest.py: EXISTS
- 81 lines: VERIFIED

**Key commits:**
- 607092f: EXISTS (Task 1 - conftest)
- 48bbcc4: EXISTS (Task 2 - MockEngine refactoring)
- 5bddb05: EXISTS (Task 3 - test_engines updates)
- 9b59a79: EXISTS (Task 4 - test_sql updates)
- 4f6bd5f: EXISTS (Task 5 - quality gates)

**Test results:**
- 81 tests passing: VERIFIED (27 engine + 54 SQL)

**Quality gates:**
- basedpyright: PASSED (0 errors)
- ruff check: PASSED (0 errors)
- ruff format: PASSED (all formatted)
- pytest: PASSED (81/81)

**API changes:**
- MockEngine.__init__() signature: VERIFIED (no parameters)
- MockEngine.execute() behavior: VERIFIED (raises NotImplementedError)
- to_sql() unchanged: VERIFIED (still functional)

## Self-Check: PASSED

All claims verified. Plan execution complete and accurate.

## Impact

### For Users

**Cleaner API:**
- MockEngine() constructor has no parameters (simpler)
- No testing concerns leaked into production API
- Clear separation: to_sql() for SQL generation, pytest fixtures for test data

**Better Testing:**
- Centralized test fixtures in conftest.py
- Reusable across test files
- Pytest fixture injection is standard Python testing practice

### For Maintainers

**Code Quality:**
- Reduced coupling between testing and production code
- Single source of truth for test models (Sales in conftest.py)
- Net reduction of 226 lines (removed duplicate fixtures, simplified tests)

**Future Work:**
- Real backend engines (SnowflakeEngine, DatabricksEngine) will implement execute() in Phase 4+
- MockEngine focused on SQL generation testing only
- Test fixtures can be extended for other test files as needed

## Next Steps

Phase 3 complete. Proceed to Phase 4 (Result handling / Row class) for:
- Query execution with real backend integration
- Row class implementation
- Result handling and data type conversion
- Real warehouse backend engines (SnowflakeEngine, DatabricksEngine)
