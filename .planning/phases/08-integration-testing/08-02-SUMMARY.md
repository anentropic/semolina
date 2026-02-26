---
phase: 08-integration-testing
plan: 02
subsystem: testing
tags:
  - integration-testing
  - warehouse-connection
  - pytest-fixtures
  - parallel-testing
  - schema-isolation
dependency_graph:
  requires:
    - 08-01 (credential management)
  provides:
    - warehouse connection fixtures (snowflake_connection, databricks_connection)
    - per-worker schema isolation (test_schema_name)
    - pytest marker registration (mock, warehouse, snowflake, databricks)
    - mock_engine fixture for fast tests
  affects:
    - 08-04 (integration tests - will use these fixtures)
tech_stack:
  added:
    - pytest markers for test categorization
    - session-scoped warehouse fixtures
    - pytest-xdist worker_id integration
  patterns:
    - session-scoped connections for performance
    - per-worker schema isolation for parallel safety
    - lazy imports for optional dependencies
    - finally blocks for guaranteed cleanup
key_files:
  created: []
  modified:
    - tests/conftest.py (added 4 fixtures: test_schema_name, snowflake_connection, databricks_connection, mock_engine)
    - pyproject.toml (added [tool.pytest.ini_options] markers)
decisions:
  - decision: "Use session scope for warehouse connection fixtures"
    rationale: "Reduces connection overhead by reusing connections across tests in same worker"
  - decision: "Use worker_id fixture for schema naming"
    rationale: "Enables pytest-xdist parallel execution without data conflicts"
  - decision: "Use finally blocks with try/except for cleanup"
    rationale: "Guarantees schema cleanup even on test failures without masking errors"
  - decision: "Lazy import warehouse connectors inside fixtures"
    rationale: "Allows tests to run without installing optional dependencies"
  - decision: "Function scope for mock_engine fixture"
    rationale: "Ensures test isolation by providing fresh engine instance per test"
metrics:
  duration_minutes: 2.43
  tasks_completed: 3
  files_modified: 2
  completed_date: 2026-02-17
requirements-completed: [INT-01, INT-05]
---

# Phase 08 Plan 02: Warehouse Connection Fixtures Summary

**One-liner:** Session-scoped Snowflake and Databricks connection fixtures with pytest-xdist worker isolation via unique test schemas.

## What Was Built

Implemented parallel-safe integration testing infrastructure with per-worker schema isolation:

1. **pytest marker registration** - Added `mock`, `warehouse`, `snowflake`, and `databricks` markers to enable selective test execution (`pytest -m mock` for fast tests, `pytest -m warehouse` for integration tests)

2. **test_schema_name fixture** - Generates unique schema names per worker: `cubano_test_main` for single-worker execution, `cubano_test_gw0`/`cubano_test_gw1` for parallel execution with pytest-xdist

3. **snowflake_connection fixture** - Session-scoped Snowflake connection with isolated test schema, automatic schema creation/cleanup via finally blocks

4. **databricks_connection fixture** - Session-scoped Databricks connection with Unity Catalog schema isolation, same cleanup pattern as Snowflake

5. **mock_engine fixture** - Function-scoped MockEngine for fast local tests without warehouse dependencies

## Key Implementation Details

### Schema Isolation Pattern

```python
@pytest.fixture(scope="session")
def test_schema_name(worker_id: str) -> str:
    if worker_id == "master":
        return "cubano_test_main"
    return f"cubano_test_{worker_id}"
```

- `worker_id` provided by pytest-xdist plugin
- "master" for non-parallel execution
- "gw0", "gw1", etc. for parallel workers
- Each worker gets isolated schema preventing data conflicts

### Connection Lifecycle

```python
@pytest.fixture(scope="session")
def snowflake_connection(snowflake_credentials, test_schema_name):
    import snowflake.connector  # Lazy import for optional dependency

    conn = snowflake.connector.connect(...)
    cursor = conn.cursor()

    try:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {test_schema_name}")
        cursor.execute(f"USE SCHEMA {test_schema_name}")
        yield conn
    finally:
        try:
            cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema_name} CASCADE")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to clean up schema {test_schema_name}: {e}")
```

- **Session scope** - Connection created once per worker, reused across all tests
- **Setup** - Creates isolated schema, switches to it
- **Teardown** - Drops schema with CASCADE, closes connections
- **Error handling** - Prints warning on cleanup failure without masking test failures

### Marker Registration

```toml
[tool.pytest.ini_options]
markers = [
    "mock: Fast tests using MockEngine (no warehouse required)",
    "warehouse: Integration tests against real warehouse (requires credentials)",
    "snowflake: Snowflake-specific warehouse tests",
    "databricks: Databricks-specific warehouse tests",
]
```

Enables selective execution:
- `pytest` - Runs all tests
- `pytest -m mock` - Fast tests only
- `pytest -m warehouse` - Integration tests only
- `pytest -m "warehouse and snowflake"` - Snowflake-specific integration tests

## Usage Examples

### Fast Mock Test

```python
@pytest.mark.mock
def test_query_builder(mock_engine):
    """Fast test using MockEngine, no warehouse required."""
    query = Query().metrics(Sales.revenue)
    results = mock_engine.execute(query)
    assert len(results) > 0
```

### Snowflake Integration Test

```python
@pytest.mark.warehouse
@pytest.mark.snowflake
def test_snowflake_measure_syntax(snowflake_connection):
    """Integration test against real Snowflake warehouse."""
    cursor = snowflake_connection.cursor()
    cursor.execute("SELECT SUM(revenue) AS total FROM sales_view")
    result = cursor.fetchone()
    assert result[0] > 0
```

### Parallel Execution

```bash
# Run all tests in parallel with 4 workers
pytest -n 4

# Run only warehouse tests in parallel
pytest -n auto -m warehouse

# Run only mock tests (fast, no parallelization needed)
pytest -m mock
```

Each worker gets isolated schema:
- Worker gw0: `cubano_test_gw0`
- Worker gw1: `cubano_test_gw1`
- Worker gw2: `cubano_test_gw2`
- Worker gw3: `cubano_test_gw3`

## Deviations from Plan

**1. [Pre-existing] .env already in .gitignore**
- **Found during:** Task 3
- **Issue:** Task 3 specified adding `.env` to .gitignore for credential safety
- **Resolution:** .env was already present in .gitignore (line 140) from standard Python .gitignore template
- **Impact:** Task 3 verification passed immediately, no changes needed
- **Files affected:** None
- **Commit:** N/A - no change needed

## Verification Results

All success criteria met:

1. ✅ test_schema_name fixture generates unique names per worker
   - Verified: `cubano_test_main` for master, `cubano_test_{worker_id}` for parallel

2. ✅ snowflake_connection fixture creates and drops schema using test_schema_name
   - Verified: CREATE SCHEMA, USE SCHEMA, DROP SCHEMA CASCADE in fixture code

3. ✅ Connection fixture is session-scoped
   - Verified: `@pytest.fixture(scope="session")` decorator

4. ✅ Schema cleanup runs in teardown even when tests fail
   - Verified: yield + finally pattern with try/except

5. ✅ pytest markers registered and visible
   - Verified: `pytest --markers` shows mock, warehouse, snowflake, databricks

6. ✅ .env file is gitignored
   - Verified: `grep -q "^\\.env$" .gitignore` passes

7. ✅ mock_engine fixture is function-scoped
   - Verified: `@pytest.fixture` (default scope is function)

**Quality gates:**
- ✅ `uv run basedpyright tests/conftest.py` - 0 errors
- ✅ `uv run ruff check tests/` - All checks passed
- ✅ `pytest --collect-only` - 286 items collected
- ✅ `pytest --markers` - Shows custom markers

## Next Steps

Implemented in 08-04-PLAN.md:
- Write integration tests using warehouse connection fixtures
- Test parallel execution with pytest -n auto
- Validate schema isolation prevents data conflicts
- Test credential loading from environment variables and .env file

## Notes

- Type annotations on optional dependencies use `# type: ignore[import-not-found]` and `# type: ignore[attr-defined]` to suppress errors when snowflake-connector-python or databricks-sql-connector not installed
- Catalog variable moved outside try block in databricks_connection to avoid "possibly unbound" type error in finally block
- Session scope significantly reduces connection overhead for integration test suites with many tests
- Function scope for mock_engine ensures test isolation without connection overhead

## Self-Check: PASSED

All claims verified:
- ✅ tests/conftest.py exists and contains all 4 fixtures
- ✅ pyproject.toml exists and contains marker registration
- ✅ Commit 1a56d34 exists (Task 1: marker registration)
- ✅ Commit bb29a98 exists (Task 2: warehouse fixtures)
