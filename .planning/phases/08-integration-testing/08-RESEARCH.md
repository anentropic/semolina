# Phase 8: Integration Testing - Research

**Researched:** 2026-02-17
**Domain:** pytest integration testing for data warehouse query builders
**Confidence:** HIGH

## Summary

Integration testing for warehouse query builders requires balancing fast developer feedback (mock tests) with production confidence (real warehouse tests). The pytest ecosystem provides mature patterns for this hybrid approach through markers, fixtures with multiple scopes, and parallel execution with pytest-xdist.

The core strategy separates concerns: **mock tests** validate query builder logic and SQL generation using MockEngine fixtures (function scope, no credentials), while **real warehouse tests** validate actual query execution, result ordering, field combinations, and edge cases using session-scoped credential fixtures and per-worker schema isolation.

Credential management follows a standard fallback chain (env vars → .env file → config file → prompt) using pydantic-settings with SecretStr for sensitive values. Data isolation for parallel tests uses pytest-xdist's `worker_id` fixture to create separate schemas per worker (e.g., `test_gw0`, `test_gw1`), with session-scoped fixtures handling setup/teardown. Tests run locally with mock-only execution (`pytest` without flags), while CI runs full suite (`pytest -m "mock or warehouse"`).

**Primary recommendation:** Use custom marker `warehouse` for real warehouse tests, function-scoped fixtures for mock tests, session-scoped fixtures for warehouse connections with per-worker schema isolation, and pydantic-settings for credential management. Register markers in pyproject.toml and document the testing strategy clearly for contributors.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Credential Handling:**
- Smart credential loader with fallback chain: env vars → .env file → config file → prompt
- Loader searches standard locations to improve developer experience
- Credentials cached in memory during test session (Claude's discretion on timing strategy)
- Validation deferred to first test execution (Claude's discretion — balances feedback with startup speed)

**Test Suite Structure (Mock vs Real Warehouse):**
- Mixed suite: both mock tests and real warehouse tests in the same codebase
- **Mock tests:** Focus on query builder logic and basic model validation (fast feedback)
- **Real warehouse tests:** Focus on field combinations, ordering, filtering, edge cases, and actual SQL validation
- MockEngine provides realistic result shapes and data sizes to mimic warehouse behavior
- Real warehouse tests are marked and opt-in locally (`pytest -m [marker]` — marker name is Claude's discretion)
  - Local development: mock tests run by default, real warehouse tests require explicit marker flag
  - CI/PR: all tests run (mock + real warehouse)
- Cost-aware: developers can iterate locally with mocks; CI validates against real warehouses

### Claude's Discretion
- Specific pytest marker semantics for real warehouse tests
- Test fixture architecture (module-level vs session-level vs function-level)
- Data isolation strategy for parallel execution (separate schemas per test? Temp tables with rollback?)
- Credential caching implementation details
- Credential validation timing and error handling

### Deferred Ideas (OUT OF SCOPE)
- Scheduled integration test runs against production warehouse — future ops enhancement
- Performance profiling and benchmarking of generated queries — Phase 10+ (documentation of performance patterns)
- Multi-database fixture composition — can add if needed in future phases

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INT-01 | User can run pytest suite against real Snowflake jaffle-shop data | Session-scoped Snowflake connection fixture with credential management; warehouse marker for filtering |
| INT-02 | Integration tests validate queries with various field combinations (metrics, dimensions, filters) | Real warehouse tests using parameterized fixtures or test cases covering field matrix |
| INT-03 | Integration tests verify correct result ordering and limiting behavior | Warehouse tests with ORDER BY and LIMIT validation; compare results to expected fixtures |
| INT-04 | Integration tests handle edge cases (empty results, null values, large result sets) | Dedicated test cases for edge scenarios using real warehouse fixture |
| INT-05 | Test suite isolates data in separate schema to prevent flakiness | Per-worker schema isolation using worker_id fixture; session-scoped schema setup/teardown |
| INT-06 | Warehouse credentials loaded from environment (not hardcoded) | pydantic-settings BaseSettings with .env support and environment variable precedence |

</phase_requirements>

## Test Fixture Patterns

### Fixture Scopes and Lifecycle

pytest supports five fixture scopes controlling fixture lifetime and reuse:

| Scope | Lifetime | Use Case |
|-------|----------|----------|
| **function** | Created/destroyed per test | Default; ideal for isolated test data, mock engines |
| **class** | Shared across all tests in a class | Grouping related tests with shared setup |
| **module** | Shared across all tests in a module | Reducing setup overhead for module-level resources |
| **session** | Single instance for entire test run | Expensive resources: database connections, warehouse schema creation |

**Source:** [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html)

**Recommended architecture for Cubano:**

```python
# tests/conftest.py

@pytest.fixture(scope="function")
def mock_engine():
    """Function-scoped MockEngine for fast, isolated tests."""
    engine = MockEngine()
    return engine

@pytest.fixture(scope="session")
def warehouse_credentials():
    """Session-scoped credentials loaded once."""
    # Load from env/config, cache for session
    return load_credentials()

@pytest.fixture(scope="session")
def warehouse_connection(warehouse_credentials, worker_id):
    """Session-scoped warehouse connection with per-worker schema."""
    conn = create_connection(warehouse_credentials)
    schema_name = f"test_{worker_id}"
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    yield conn
    conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    conn.close()
```

**Rationale:**
- **Function scope for mock tests:** Each test gets fresh MockEngine, preventing state leakage
- **Session scope for warehouse:** Reduces connection overhead; expensive schema creation happens once per worker
- **Teardown with yield:** Clean separation of setup (before yield) and cleanup (after yield)

**Confidence:** HIGH - Official pytest documentation and verified patterns across Python testing ecosystem

### Autouse Fixtures

Autouse fixtures automatically apply to all tests without explicit request:

```python
@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    from cubano import registry
    registry.reset()
```

**Current usage in Cubano:** Already implemented in `tests/conftest.py` for registry cleanup.

**Recommendation:** Continue using autouse for global cleanup tasks. Avoid for credential/connection fixtures (explicit is better for expensive resources).

**Source:** [pytest autouse fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)

**Confidence:** HIGH

### Fixture Dependency and Teardown Order

Fixtures resolve dependencies automatically through parameter names. Teardown follows reverse dependency order—the last fixture established tears down first.

```python
@pytest.fixture(scope="session")
def warehouse_connection(warehouse_credentials):
    # warehouse_connection depends on warehouse_credentials
    # Teardown: warehouse_connection closes first, then warehouse_credentials
    pass
```

**Critical for warehouse tests:** Ensures connections close before credential objects are cleaned up, preventing orphaned connections.

**Source:** [pytest fixture dependency order](https://docs.pytest.org/en/stable/how-to/fixtures.html)

**Confidence:** HIGH

## Data Isolation & Flakiness Prevention

### Parallel Test Execution with pytest-xdist

pytest-xdist enables parallel test execution across multiple CPUs/workers. Each worker independently collects and executes a subset of tests.

**Installation:**
```bash
uv add --dev pytest-xdist
```

**Usage:**
```bash
pytest -n auto  # Auto-detect CPU count
pytest -n 4     # Run with 4 workers
```

**Distribution modes:**
- `--dist load` (default): Send pending tests to any available worker
- `--dist loadscope`: Group tests by module (functions) or class (methods); distribute groups as whole units

**Source:** [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)

**Recommendation:** Use default `--dist load` for Cubano. If specific tests share resources (e.g., same test schema), use `@pytest.mark.xdist_group("shared_schema")` to serialize them.

**Confidence:** HIGH

### Worker Identification for Isolation

pytest-xdist provides `worker_id` fixture to identify worker processes:

```python
@pytest.fixture(scope="session")
def warehouse_schema(warehouse_connection, worker_id):
    """Create per-worker schema for data isolation."""
    if worker_id == "master":
        schema_name = "test_main"  # Non-parallel execution
    else:
        schema_name = f"test_{worker_id}"  # e.g., test_gw0, test_gw1

    warehouse_connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    yield schema_name
    warehouse_connection.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
```

**Environment variables:**
- `PYTEST_XDIST_WORKER`: Worker name like `"gw2"`
- `PYTEST_XDIST_WORKER_COUNT`: Total worker count, e.g., `"4"` with `-n 4`

**Source:** [pytest-xdist worker identification](https://pytest-xdist.readthedocs.io/en/stable/how-to.html)

**Confidence:** HIGH

### Snowflake-Specific Isolation

Snowflake schemas provide logical isolation within a database. Each schema can contain its own tables, views, and semantic views.

**Isolation strategy:**
```sql
-- Setup (per worker)
CREATE SCHEMA IF NOT EXISTS test_gw0;
USE SCHEMA test_gw0;

-- Teardown (per worker)
DROP SCHEMA IF EXISTS test_gw0 CASCADE;
```

**Pros:**
- Clean isolation: No cross-worker data contamination
- Parallel-safe: Each worker has dedicated namespace
- Simple cleanup: `DROP SCHEMA CASCADE` removes all objects

**Cons:**
- Schema creation overhead: ~100-200ms per schema
- Requires CREATE SCHEMA permission

**Alternative: Transaction rollback** (NOT recommended for Snowflake integration tests):
- Snowflake transactions lock tables, preventing parallel writes
- Nested transactions not supported in Snowflake
- Rollback strategy conflicts with parallel execution

**Source:** [Snowflake schema organization](https://centricconsulting.com/blog/snowflake-security-and-data-privacy-identifying-organizing-and-isolating-data/), [Snowflake transactions](https://docs.snowflake.com/en/sql-reference/transactions)

**Recommendation:** Use per-worker schema isolation for Snowflake tests. Avoid transaction-based rollback.

**Confidence:** HIGH

### Databricks-Specific Isolation (Unity Catalog)

Unity Catalog uses three-level hierarchy: catalog → schema → table/view.

**Isolation strategy:**
```sql
-- Setup (per worker)
CREATE SCHEMA IF NOT EXISTS catalog_name.test_gw0;
USE catalog_name.test_gw0;

-- Teardown (per worker)
DROP SCHEMA IF EXISTS catalog_name.test_gw0 CASCADE;
```

**Physical storage isolation:** Can configure separate cloud storage locations at schema level for regulatory requirements.

**Pros:**
- Same as Snowflake: clean isolation, parallel-safe, simple cleanup
- Unity Catalog provides fine-grained access control at schema level

**Cons:**
- Requires Unity Catalog setup (Cubano assumes Unity Catalog for Databricks)
- Schema creation overhead: ~150-250ms per schema

**Source:** [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices), [Unity Catalog distributed governance](https://www.databricks.com/blog/2023/03/09/distributed-data-governance-and-isolated-environments-unity-catalog.html)

**Recommendation:** Use per-worker schema isolation in Unity Catalog for Databricks tests. Mirror Snowflake pattern for consistency.

**Confidence:** MEDIUM - Unity Catalog specifics verified, but Cubano doesn't have Databricks implementation yet (Phase 6 completed this feature)

### Session-Scoped Fixture Execution in Parallel Mode

**Critical limitation:** Each worker independently collects and executes tests, causing session-scoped fixtures to run **multiple times** (once per worker).

**Problem:**
```python
@pytest.fixture(scope="session")
def shared_schema():
    # This runs ONCE PER WORKER, not once for entire test run
    # Multiple workers will create overlapping schemas
    pass
```

**Solution:** Use file-based locking to coordinate across workers:

```python
import filelock

@pytest.fixture(scope="session")
def shared_expensive_resource(tmp_path_factory, worker_id):
    if worker_id == "master":
        # Not in parallel mode, no locking needed
        return expensive_setup()

    # Parallel mode: use lock file
    root_tmp_dir = tmp_path_factory.getbasetemp().parent
    lock_file = root_tmp_dir / "shared_resource.lock"

    with filelock.FileLock(lock_file):
        # First worker creates resource; others wait and read
        data_file = root_tmp_dir / "shared_data.json"
        if not data_file.exists():
            resource = expensive_setup()
            data_file.write_text(resource.to_json())
        else:
            resource = Resource.from_json(data_file.read_text())

    return resource
```

**Source:** [pytest-xdist shared resource patterns](https://pytest-xdist.readthedocs.io/en/stable/how-to.html)

**Recommendation for Cubano:** Avoid shared resources across workers. Use per-worker schemas instead. If shared setup is required (e.g., loading common test data), use file locking pattern above.

**Confidence:** HIGH

## Credential Management

### pydantic-settings for Environment Variables

pydantic-settings provides `BaseSettings` class that automatically loads configuration from environment variables.

**Installation:**
```bash
uv add --dev pydantic-settings
```

**Basic usage:**
```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class SnowflakeCredentials(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SNOWFLAKE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    account: str
    user: str
    password: SecretStr
    warehouse: str
    database: str
    role: str | None = None
```

**Environment variable precedence:** Environment variables always take priority over `.env` file values. This ensures production secrets in environment override development `.env` files.

**Source:** [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

**Confidence:** HIGH

### SecretStr for Sensitive Values

pydantic's `SecretStr` masks sensitive data during serialization and logging:

```python
from pydantic import SecretStr

password = SecretStr("my_secret_password")
print(password)  # Output: SecretStr('**********')
str(password)    # Output: '**********'
password.get_secret_value()  # Output: 'my_secret_password'
```

**Security benefit:** Prevents accidental credential leakage in logs, error messages, and test output.

**Source:** [Pydantic SecretStr](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

**Recommendation:** Use `SecretStr` for all password and token fields in credential classes.

**Confidence:** HIGH

### Fallback Chain Implementation

**User requirement:** env vars → .env file → config file → prompt

**Implementation pattern:**
```python
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class WarehouseCredentials(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    account: str
    user: str
    password: SecretStr

    @classmethod
    def load(cls) -> "WarehouseCredentials":
        """Load credentials with fallback chain."""
        # Step 1: Try env vars + .env file (pydantic-settings handles this)
        try:
            return cls()
        except ValidationError:
            pass

        # Step 2: Try config file
        config_paths = [
            Path.cwd() / ".cubano.toml",
            Path.home() / ".config" / "cubano" / "config.toml",
        ]
        for config_path in config_paths:
            if config_path.exists():
                try:
                    return cls.from_toml(config_path)
                except ValidationError:
                    continue

        # Step 3: Prompt (interactive mode only)
        if sys.stdin.isatty():
            return cls.from_prompt()

        raise CredentialError("No credentials found")
```

**TOML config file support:**
```python
from pydantic_settings import TomlConfigSettingsSource

class WarehouseCredentials(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
```

**Source:** [Pydantic Settings customization](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

**Confidence:** HIGH - pydantic-settings is the standard solution for this pattern

### Credential Caching Strategy

**User requirement:** Credentials cached in memory during test session

**Implementation using session-scoped fixture:**
```python
@pytest.fixture(scope="session")
def snowflake_credentials():
    """Load credentials once per test session, cache in memory."""
    return SnowflakeCredentials.load()

@pytest.fixture(scope="session")
def databricks_credentials():
    """Load credentials once per test session, cache in memory."""
    return DatabricksCredentials.load()
```

**Validation timing (user's discretion):** Defer validation to first test execution to balance feedback with startup speed.

**Lazy validation pattern:**
```python
@pytest.fixture(scope="session")
def snowflake_connection(snowflake_credentials):
    """Create connection on first use (deferred validation)."""
    # Validation happens here, not during credential load
    conn = snowflake.connector.connect(
        account=snowflake_credentials.account,
        user=snowflake_credentials.user,
        password=snowflake_credentials.password.get_secret_value(),
    )
    yield conn
    conn.close()
```

**Pros:**
- Fast test collection (no network calls during collection phase)
- Clear error messages (validation failure points to specific test)
- Session caching reduces redundant credential loading

**Cons:**
- Delayed feedback for credential errors (won't know until first warehouse test runs)

**Recommendation:** Use session-scoped credential fixtures with lazy validation. Balance: developers get fast test startup; failures are still caught before running expensive warehouse queries.

**Confidence:** HIGH

## Mock vs Real Warehouse Testing

### Pytest Markers for Test Organization

Custom markers allow categorizing and selectively executing tests.

**Registration in pyproject.toml:**
```toml
[tool.pytest.ini_options]
markers = [
    "mock: Fast tests using MockEngine (no warehouse required)",
    "warehouse: Integration tests against real warehouse (requires credentials)",
    "snowflake: Snowflake-specific warehouse tests",
    "databricks: Databricks-specific warehouse tests",
]
```

**Applying markers:**
```python
@pytest.mark.mock
def test_query_builder_with_mock_engine(mock_engine):
    """Test query building logic without warehouse."""
    query = Query().metrics(Sales.revenue)
    sql = mock_engine.to_sql(query)
    assert 'AGG("revenue")' in sql

@pytest.mark.warehouse
@pytest.mark.snowflake
def test_query_execution_on_snowflake(snowflake_connection):
    """Test actual query execution on Snowflake warehouse."""
    query = Query().metrics(Orders.order_total).limit(10)
    results = snowflake_connection.execute(query)
    assert len(results) == 10
```

**Filtering tests:**
```bash
# Local development: mock tests only (default)
pytest

# Explicitly run mock tests
pytest -m mock

# Run warehouse tests
pytest -m warehouse

# Run Snowflake-specific tests
pytest -m "warehouse and snowflake"

# CI: run all tests
pytest -m "mock or warehouse"
```

**Source:** [pytest custom markers](https://docs.pytest.org/en/stable/example/markers.html), [pytest marker filtering](https://docs.pytest.org/en/stable/how-to/mark.html)

**Recommendation:** Use `mock` and `warehouse` as primary markers. Add `snowflake` and `databricks` for backend-specific tests. Document in README that `pytest` runs mock tests only; warehouse tests require `-m warehouse`.

**Confidence:** HIGH

### Conditional Test Execution Based on Credentials

**Pattern:** Skip warehouse tests if credentials unavailable (prevents failure in local development without credentials).

```python
import pytest

@pytest.fixture(scope="session")
def snowflake_credentials():
    """Load Snowflake credentials, skip tests if unavailable."""
    try:
        return SnowflakeCredentials.load()
    except CredentialError:
        pytest.skip("Snowflake credentials not available")

@pytest.mark.warehouse
def test_with_snowflake(snowflake_credentials, snowflake_connection):
    """Automatically skipped if credentials not available."""
    pass
```

**Alternative: Environment variable flag:**
```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_WAREHOUSE_TESTS"),
    reason="RUN_WAREHOUSE_TESTS not set"
)

@pytest.mark.warehouse
def test_warehouse_query():
    pass
```

**CI configuration:**
```bash
# CI environment
export RUN_WAREHOUSE_TESTS=1
pytest -m "mock or warehouse"
```

**Source:** [pytest conditional skipping](https://docs.pytest.org/en/stable/how-to/skipping.html)

**Recommendation:** Use credential-based skipping (first pattern). More intuitive: if credentials exist, tests run; if not, tests skip with clear reason.

**Confidence:** HIGH

### Parameterized Fixtures for Backend Switching

**Use case:** Run same test against both MockEngine and real warehouse.

```python
@pytest.fixture(params=["mock", "snowflake"])
def engine(request, mock_engine, snowflake_connection):
    """Parametrized fixture: runs test twice (mock + warehouse)."""
    if request.param == "mock":
        return mock_engine
    elif request.param == "snowflake":
        return snowflake_connection

def test_query_execution(engine):
    """Runs twice: once with MockEngine, once with Snowflake."""
    query = Query().metrics(Sales.revenue)
    results = engine.execute(query)
    assert len(results) > 0
```

**Source:** [pytest parametrized fixtures](https://docs.pytest.org/en/stable/how-to/parametrize.html)

**Recommendation:** Use sparingly. Most tests should target either mock OR warehouse, not both. Parametrization useful for smoke tests validating backend compatibility.

**Confidence:** MEDIUM - Pattern works, but may increase test suite complexity

### Realistic Mock Data

**User requirement:** MockEngine provides realistic result shapes and data sizes to mimic warehouse behavior.

**Current implementation (from conftest.py):**
```python
@pytest.fixture
def sales_fixtures() -> dict[str, list[dict[str, Any]]]:
    return {
        "sales_view": [
            {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
            {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
            {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
        ]
    }
```

**Enhancements for realism:**

1. **Data types match warehouse:** Use same types as warehouse results (int, float, str, datetime, Decimal)
2. **Result sizes:** Mock data should include empty results (0 rows), small results (1-10 rows), medium results (100-1000 rows) for testing pagination/limits
3. **Edge cases:** Include null values, duplicate values, extreme values in mock data

**Enhanced pattern:**
```python
from decimal import Decimal
from datetime import datetime

@pytest.fixture
def orders_fixtures():
    return {
        "orders": [
            # Normal cases
            {"order_id": 1, "total": Decimal("100.50"), "ordered_at": datetime(2024, 1, 1)},
            {"order_id": 2, "total": Decimal("250.00"), "ordered_at": datetime(2024, 1, 2)},
            # Edge cases
            {"order_id": 3, "total": None, "ordered_at": None},  # Nulls
            {"order_id": 4, "total": Decimal("0.00"), "ordered_at": datetime(2024, 1, 1)},  # Zero
            {"order_id": 5, "total": Decimal("999999.99"), "ordered_at": datetime(2024, 12, 31)},  # Max
        ]
    }
```

**Tools for generating realistic data:**
- **Faker:** Generate realistic names, addresses, dates
- **factory_boy:** Create fixture factories with relationships

**Source:** [pytest-mock tutorial](https://www.datacamp.com/tutorial/pytest-mock), [faker library](https://faker.readthedocs.io/)

**Recommendation:** Start with hand-crafted fixtures for simplicity. Add Faker if test data complexity grows. Focus on edge cases (nulls, empty results, duplicates) more than volume.

**Confidence:** HIGH

## Parallel Test Execution (pytest -n auto)

### Common Pitfalls with pytest-xdist

**Pitfall 1: Shared database state**
- **Problem:** Multiple workers write to same schema, causing conflicts
- **Solution:** Per-worker schema isolation (covered above)

**Pitfall 2: Session-scoped fixtures run per worker**
- **Problem:** Expensive setup duplicated across workers
- **Solution:** Accept duplication OR use file locking for shared resources

**Pitfall 3: Connection pool exhaustion**
- **Problem:** Each worker creates connection pool; total connections exceed warehouse limit
- **Solution:** Use single connection per worker (not pool) OR configure pool size based on worker count

**Source:** [pytest-xdist best practices](https://pytest-with-eric.com/plugins/pytest-xdist/)

**Confidence:** HIGH

### Connection Pool vs Individual Connection

**Snowflake connection pooling:**
```python
from snowflake.connector.connection_pool import SnowflakeConnectionPool

pool = SnowflakeConnectionPool(
    user="...",
    password="...",
    account="...",
    min_size=1,
    max_size=5,  # Max 5 concurrent connections
)
```

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Connection pool per worker** | Reuses connections within worker | Total connections = workers × pool_size (can exhaust warehouse limit) |
| **Single connection per worker** | Predictable connection count | No connection reuse; slight overhead per query |

**Recommendation:** Use **single connection per worker** for integration tests. Test queries are infrequent enough that connection overhead is negligible. Predictable connection count prevents warehouse exhaustion.

**Source:** [Snowflake connector connection pooling](https://docs.devart.com/python/snowflake/connection-pooling.htm)

**Confidence:** MEDIUM - Connection pooling is well-documented, but Cubano's specific query patterns may not benefit significantly

### Pytest Hooks for Worker Setup/Teardown

pytest-xdist provides hooks for worker lifecycle:

```python
# conftest.py

def pytest_configure_node(node):
    """Called for each worker before test collection."""
    # Worker-specific configuration
    pass

def pytest_testnodedown(node, error):
    """Called when worker finishes or crashes."""
    # Cleanup worker resources
    pass
```

**Use cases:**
- Initialize worker-specific resources (e.g., separate log files)
- Clean up worker resources on crash

**Source:** [pytest-xdist hooks](https://github.com/pytest-dev/pytest-xdist)

**Recommendation:** Use session-scoped fixtures with yield for cleanup. Hooks needed only for advanced use cases (e.g., separate log files per worker).

**Confidence:** MEDIUM - Hooks exist but session-scoped fixtures are simpler and sufficient for most cases

## jaffle-shop Integration

### Current State of cubano-jaffle-shop

**What exists:**
- `cubano-jaffle-shop` workspace with pyproject.toml
- Translated Cubano models: `Orders`, `Customers`, `Products` in `jaffle_models.py`
- Model validation tests in `test_models.py` (assert field counts, types, view names)
- No integration test fixtures yet

**What's needed for Phase 8:**
- `tests/` directory in `cubano-jaffle-shop/`
- `conftest.py` with warehouse credential fixtures
- Integration tests validating queries against real warehouse data
- Mock test fixtures for jaffle-shop models

**Source:** Codebase analysis (pyproject.toml, jaffle_models.py, test_models.py)

**Confidence:** HIGH

### Test Structure for Cubano Models

**Recommended structure:**
```
cubano-jaffle-shop/
├── src/cubano_jaffle_shop/
│   ├── jaffle_models.py       # Existing: Orders, Customers, Products models
│   └── test_models.py          # Existing: Model structure validation
├── tests/
│   ├── conftest.py             # NEW: Fixtures for warehouse connections
│   ├── test_mock_queries.py    # NEW: Mock engine tests
│   ├── test_snowflake_queries.py  # NEW: Snowflake integration tests
│   └── fixtures/
│       ├── mock_data.py        # NEW: Mock fixture data for jaffle-shop
│       └── expected_results.py # NEW: Expected results for validation
└── pyproject.toml
```

**Example tests:**

```python
# tests/test_mock_queries.py
import pytest
from cubano import Query
from cubano_jaffle_shop.jaffle_models import Orders

@pytest.mark.mock
def test_orders_total_revenue_mock(mock_engine, orders_mock_data):
    """Test order total calculation with mock data."""
    mock_engine.load("orders", orders_mock_data)
    query = Query().metrics(Orders.order_total)
    results = mock_engine.execute(query)
    assert len(results) > 0

# tests/test_snowflake_queries.py
@pytest.mark.warehouse
@pytest.mark.snowflake
def test_orders_total_revenue_snowflake(snowflake_connection):
    """Test order total calculation against Snowflake warehouse."""
    query = Query().metrics(Orders.order_total).limit(100)
    results = snowflake_connection.execute(query)
    assert len(results) == 100
    assert all("order_total" in row for row in results)
```

**Confidence:** HIGH

### dbt Test Patterns for Reference

dbt provides testing patterns that can inform Cubano integration tests:

**dbt data tests:**
```yaml
# dbt models/orders.yml
models:
  - name: orders
    tests:
      - unique:
          column_name: order_id
      - not_null:
          column_name: order_id
```

**dbt unit tests (Python):**
```python
# Use pytest to run dbt models against mock data
def test_orders_model(dbt_project):
    results = dbt_project.run_model("orders", seeds=["customers", "products"])
    assert len(results) > 0
```

**Cubano equivalent:**
```python
@pytest.mark.warehouse
def test_orders_field_combinations(warehouse_connection):
    """Test various metric/dimension combinations."""
    test_cases = [
        (Query().metrics(Orders.order_total), ["order_total"]),
        (Query().dimensions(Orders.ordered_at), ["ordered_at"]),
        (Query().metrics(Orders.order_total).dimensions(Orders.ordered_at),
         ["order_total", "ordered_at"]),
    ]

    for query, expected_fields in test_cases:
        results = warehouse_connection.execute(query.limit(1))
        assert all(field in results[0] for field in expected_fields)
```

**Source:** [dbt unit testing patterns](https://pypi.org/project/pytest-dbt/), [dbt testing guide](https://dagster.io/guides/dbt-unit-testing-why-you-need-them-tutorial-best-practices)

**Confidence:** MEDIUM - dbt patterns are well-established, but direct translation to Cubano requires adaptation

## Architecture Patterns

### Recommended Fixture Organization

**Pattern: Hierarchical conftest.py files**

```
tests/
├── conftest.py                 # Root: shared fixtures (mock engine, credentials)
├── unit/
│   ├── conftest.py             # Unit test fixtures
│   └── test_query_builder.py
└── integration/
    ├── conftest.py             # Integration fixtures (warehouse connections)
    ├── test_snowflake.py
    └── test_databricks.py
```

**Root conftest.py:**
```python
# tests/conftest.py
import pytest
from cubano.engines.mock import MockEngine

@pytest.fixture
def mock_engine():
    """Shared mock engine fixture."""
    return MockEngine()

@pytest.fixture(scope="session")
def warehouse_credentials():
    """Load credentials once per session."""
    return load_credentials()
```

**Integration conftest.py:**
```python
# tests/integration/conftest.py
import pytest

@pytest.fixture(scope="session")
def snowflake_connection(warehouse_credentials, worker_id):
    """Snowflake connection with per-worker schema."""
    # Implementation from earlier sections
    pass
```

**Source:** [pytest conftest organization](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/)

**Confidence:** HIGH

### Pattern: Credential Fixture with Fallback

```python
# tests/conftest.py
import pytest
from pathlib import Path
from typing import Optional

@pytest.fixture(scope="session")
def snowflake_credentials() -> Optional[SnowflakeCredentials]:
    """Load Snowflake credentials, skip if unavailable."""
    try:
        # Try env vars first
        return SnowflakeCredentials()
    except ValidationError:
        pass

    # Try .env file
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        try:
            return SnowflakeCredentials(_env_file=str(env_file))
        except ValidationError:
            pass

    # Try config file
    config_file = Path.home() / ".config" / "cubano" / "config.toml"
    if config_file.exists():
        try:
            return SnowflakeCredentials.from_toml(config_file)
        except ValidationError:
            pass

    # No credentials found: skip warehouse tests
    pytest.skip("Snowflake credentials not available")
```

**Confidence:** HIGH

### Pattern: Per-Worker Schema Isolation

```python
# tests/integration/conftest.py
import pytest

@pytest.fixture(scope="session")
def test_schema_name(worker_id):
    """Generate unique schema name for this worker."""
    if worker_id == "master":
        return "cubano_test_main"
    else:
        return f"cubano_test_{worker_id}"

@pytest.fixture(scope="session")
def snowflake_schema(snowflake_connection, test_schema_name):
    """Create and clean up test schema."""
    # Setup
    cursor = snowflake_connection.cursor()
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {test_schema_name}")
    cursor.execute(f"USE SCHEMA {test_schema_name}")

    yield test_schema_name

    # Teardown
    cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema_name} CASCADE")
    cursor.close()
```

**Confidence:** HIGH

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Environment variable loading | Custom .env parser | pydantic-settings | Handles precedence, type validation, multiple sources (env, .env, config files) |
| Parallel test execution | Custom worker pool | pytest-xdist | Mature, handles test distribution, worker isolation, fixture scoping |
| Test data generation | Manual fixture writing | Faker (if needed) | Generates realistic data; reduces fixture maintenance |
| Credential masking | Custom redaction logic | pydantic SecretStr | Automatic masking in logs, serialization, repr |
| Per-worker resources | Manual worker tracking | pytest-xdist worker_id fixture | Built-in, reliable, handles edge cases (master mode) |

**Key insight:** Testing infrastructure is complex. Use battle-tested libraries to avoid subtle bugs in credential handling, parallel execution, and test isolation.

## Common Pitfalls

### Pitfall 1: Hardcoded Credentials in Tests

**What goes wrong:** Credentials committed to git, exposed in CI logs, security risk.

**Why it happens:** Convenience during development; lack of credential management setup.

**How to avoid:**
- Use pydantic-settings with .env files (add `.env` to `.gitignore`)
- Use SecretStr for password fields
- Validate no hardcoded credentials in pre-commit hook (search for patterns like `password="..."`))

**Warning signs:**
- String literals containing "password", "token", "secret" in test files
- Connection strings with credentials embedded

**Source:** [SecretStr documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

**Confidence:** HIGH

### Pitfall 2: Shared Database State in Parallel Tests

**What goes wrong:** Tests fail intermittently; race conditions when multiple workers write to same schema.

**Why it happens:** Assuming tests run sequentially; not accounting for pytest-xdist parallelism.

**How to avoid:**
- Use per-worker schema isolation with `worker_id` fixture
- Test parallel execution locally: `pytest -n 4` before pushing to CI

**Warning signs:**
- Tests pass locally but fail in CI
- Flaky tests that fail ~25% of the time (depends on worker count)

**Source:** [pytest-xdist data isolation](https://pytest-with-eric.com/plugins/pytest-xdist/)

**Confidence:** HIGH

### Pitfall 3: Session-Scoped Fixtures Not Cleaning Up

**What goes wrong:** Test schemas accumulate in warehouse; costs increase; clutter makes debugging harder.

**Why it happens:** Exception during teardown; missing `yield` in fixture.

**How to avoid:**
- Always use `yield` for fixtures with cleanup (not `return`)
- Wrap cleanup in try/except to ensure it runs even if tests fail
- Use `DROP SCHEMA IF EXISTS` (idempotent cleanup)

**Example:**
```python
@pytest.fixture(scope="session")
def warehouse_schema(connection, schema_name):
    # Setup
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

    yield schema_name

    # Teardown: always runs, even if tests fail
    try:
        connection.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    except Exception as e:
        print(f"Warning: Failed to clean up schema {schema_name}: {e}")
```

**Warning signs:**
- Test schemas in warehouse that weren't dropped
- Warehouse storage costs increasing over time

**Confidence:** HIGH

### Pitfall 4: Mixing Mock and Warehouse Tests Without Markers

**What goes wrong:** Developers accidentally run expensive warehouse tests locally; slow feedback loop.

**Why it happens:** No clear separation between fast mock tests and slow warehouse tests.

**How to avoid:**
- Mark all warehouse tests with `@pytest.mark.warehouse`
- Document in README: `pytest` runs mock tests only; use `pytest -m warehouse` for integration tests
- Configure pytest.ini to register markers (prevents typos)

**Warning signs:**
- Complaints about slow local test runs
- Tests requiring credentials fail in local development

**Confidence:** HIGH

### Pitfall 5: Credentials Validated Too Early

**What goes wrong:** Test collection fails if credentials missing; can't run mock tests without warehouse credentials.

**Why it happens:** Session-scoped credential fixture validates during collection phase.

**How to avoid:**
- Defer validation to first use (lazy connection creation)
- Use `pytest.skip()` in credential fixture if credentials unavailable

**Example:**
```python
@pytest.fixture(scope="session")
def warehouse_credentials():
    """Skip warehouse tests if credentials unavailable."""
    try:
        return SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")
```

**Warning signs:**
- `pytest -m mock` fails when warehouse credentials missing
- Can't run any tests without full credential setup

**Confidence:** HIGH

## Code Examples

### Complete Credential Management Example

```python
# src/cubano/testing/credentials.py
from pathlib import Path
from typing import Optional
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

class SnowflakeCredentials(BaseSettings):
    """
    Snowflake warehouse credentials with fallback loading.

    Load order:
    1. Environment variables (SNOWFLAKE_ACCOUNT, etc.)
    2. .env file in current directory
    3. ~/.config/cubano/config.toml
    """

    model_config = SettingsConfigDict(
        env_prefix="SNOWFLAKE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    account: str
    user: str
    password: SecretStr
    warehouse: str
    database: str
    role: Optional[str] = None

    @classmethod
    def load(cls) -> "SnowflakeCredentials":
        """Load credentials with fallback chain."""
        # Step 1: Try environment variables + .env file
        try:
            return cls()
        except ValidationError:
            pass

        # Step 2: Try config file
        config_paths = [
            Path.cwd() / ".cubano.toml",
            Path.home() / ".config" / "cubano" / "config.toml",
        ]
        for config_path in config_paths:
            if config_path.exists():
                try:
                    # Load from TOML (requires tomli/tomllib)
                    import tomllib
                    config = tomllib.loads(config_path.read_text())
                    return cls(**config.get("snowflake", {}))
                except (ValidationError, KeyError):
                    continue

        raise CredentialError(
            "Snowflake credentials not found. "
            "Set SNOWFLAKE_* environment variables or create .env file."
        )

class DatabricksCredentials(BaseSettings):
    """Databricks warehouse credentials."""

    model_config = SettingsConfigDict(
        env_prefix="DATABRICKS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    server_hostname: str
    http_path: str
    access_token: SecretStr
    catalog: str = "main"

    @classmethod
    def load(cls) -> "DatabricksCredentials":
        """Load credentials with fallback chain."""
        try:
            return cls()
        except ValidationError:
            pass

        config_paths = [
            Path.cwd() / ".cubano.toml",
            Path.home() / ".config" / "cubano" / "config.toml",
        ]
        for config_path in config_paths:
            if config_path.exists():
                try:
                    import tomllib
                    config = tomllib.loads(config_path.read_text())
                    return cls(**config.get("databricks", {}))
                except (ValidationError, KeyError):
                    continue

        raise CredentialError(
            "Databricks credentials not found. "
            "Set DATABRICKS_* environment variables or create .env file."
        )

class CredentialError(Exception):
    """Raised when credentials cannot be loaded."""
    pass
```

**Source:** Original implementation based on pydantic-settings patterns

**Confidence:** HIGH

### Complete Fixture Setup Example

```python
# tests/conftest.py
import pytest
from pathlib import Path
from cubano.engines.mock import MockEngine
from cubano.testing.credentials import (
    SnowflakeCredentials,
    DatabricksCredentials,
    CredentialError,
)

# Configure pytest markers
pytest_plugins = []

def pytest_configure(config):
    config.addinivalue_line("markers", "mock: Fast tests using MockEngine")
    config.addinivalue_line("markers", "warehouse: Integration tests against real warehouse")
    config.addinivalue_line("markers", "snowflake: Snowflake-specific tests")
    config.addinivalue_line("markers", "databricks: Databricks-specific tests")

# Registry cleanup (existing fixture)
@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    from cubano import registry
    registry.reset()

# Mock engine fixtures
@pytest.fixture
def mock_engine():
    """Function-scoped MockEngine for isolated tests."""
    return MockEngine()

# Credential fixtures (session-scoped, lazy loading)
@pytest.fixture(scope="session")
def snowflake_credentials():
    """Load Snowflake credentials, skip tests if unavailable."""
    try:
        return SnowflakeCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Snowflake credentials not available: {e}")

@pytest.fixture(scope="session")
def databricks_credentials():
    """Load Databricks credentials, skip tests if unavailable."""
    try:
        return DatabricksCredentials.load()
    except CredentialError as e:
        pytest.skip(f"Databricks credentials not available: {e}")

# Worker identification for parallel execution
@pytest.fixture(scope="session")
def test_schema_name(worker_id):
    """Generate unique schema name for this worker."""
    if worker_id == "master":
        return "cubano_test_main"
    else:
        # worker_id is like "gw0", "gw1", etc.
        return f"cubano_test_{worker_id}"

# Snowflake connection fixture
@pytest.fixture(scope="session")
def snowflake_connection(snowflake_credentials, test_schema_name):
    """
    Create Snowflake connection with isolated test schema.

    Schema isolation prevents parallel test conflicts.
    Session scope reduces connection overhead.
    """
    import snowflake.connector

    # Create connection (deferred validation)
    conn = snowflake.connector.connect(
        account=snowflake_credentials.account,
        user=snowflake_credentials.user,
        password=snowflake_credentials.password.get_secret_value(),
        warehouse=snowflake_credentials.warehouse,
        database=snowflake_credentials.database,
        role=snowflake_credentials.role,
    )

    # Create isolated test schema
    cursor = conn.cursor()
    try:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {test_schema_name}")
        cursor.execute(f"USE SCHEMA {test_schema_name}")

        yield conn

    finally:
        # Cleanup: drop test schema
        try:
            cursor.execute(f"DROP SCHEMA IF EXISTS {test_schema_name} CASCADE")
        except Exception as e:
            print(f"Warning: Failed to clean up schema {test_schema_name}: {e}")
        finally:
            cursor.close()
            conn.close()

# Databricks connection fixture
@pytest.fixture(scope="session")
def databricks_connection(databricks_credentials, test_schema_name):
    """
    Create Databricks connection with isolated test schema.

    Uses Unity Catalog schema isolation.
    """
    from databricks import sql

    # Create connection
    conn = sql.connect(
        server_hostname=databricks_credentials.server_hostname,
        http_path=databricks_credentials.http_path,
        access_token=databricks_credentials.access_token.get_secret_value(),
    )

    # Create isolated test schema in Unity Catalog
    cursor = conn.cursor()
    catalog = databricks_credentials.catalog

    try:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{test_schema_name}")
        cursor.execute(f"USE {catalog}.{test_schema_name}")

        yield conn

    finally:
        # Cleanup: drop test schema
        try:
            cursor.execute(f"DROP SCHEMA IF EXISTS {catalog}.{test_schema_name} CASCADE")
        except Exception as e:
            print(f"Warning: Failed to clean up schema {test_schema_name}: {e}")
        finally:
            cursor.close()
            conn.close()
```

**Source:** Original implementation based on researched patterns

**Confidence:** HIGH

### Integration Test Example

```python
# tests/integration/test_snowflake_queries.py
import pytest
from cubano import Query
from cubano_jaffle_shop.jaffle_models import Orders, Customers

@pytest.mark.warehouse
@pytest.mark.snowflake
class TestSnowflakeQueryExecution:
    """Integration tests for Snowflake warehouse queries."""

    def test_simple_metric_query(self, snowflake_connection):
        """Test single metric query execution."""
        query = Query().metrics(Orders.order_total).limit(10)
        results = snowflake_connection.execute(query)

        assert len(results) == 10
        assert all("order_total" in row for row in results)

    def test_metric_with_dimension(self, snowflake_connection):
        """Test metric grouped by dimension."""
        query = (
            Query()
            .metrics(Orders.order_total)
            .dimensions(Orders.ordered_at)
            .limit(50)
        )
        results = snowflake_connection.execute(query)

        assert len(results) <= 50
        assert all("order_total" in row and "ordered_at" in row for row in results)

    def test_multiple_metrics(self, snowflake_connection):
        """Test multiple metrics in single query."""
        query = (
            Query()
            .metrics(Orders.order_total, Orders.order_count)
            .limit(10)
        )
        results = snowflake_connection.execute(query)

        assert len(results) == 10
        assert all(
            "order_total" in row and "order_count" in row
            for row in results
        )

    def test_filtering(self, snowflake_connection):
        """Test query with filter."""
        from cubano import Q

        query = (
            Query()
            .metrics(Orders.order_total)
            .dimensions(Orders.is_food_order)
            .filter(Q(is_food_order=True))
            .limit(100)
        )
        results = snowflake_connection.execute(query)

        assert all(row["is_food_order"] is True for row in results)

    def test_ordering(self, snowflake_connection):
        """Test query with ORDER BY."""
        query = (
            Query()
            .metrics(Orders.order_total)
            .dimensions(Orders.ordered_at)
            .order_by(Orders.order_total.desc())
            .limit(10)
        )
        results = snowflake_connection.execute(query)

        # Verify descending order
        totals = [row["order_total"] for row in results]
        assert totals == sorted(totals, reverse=True)

    def test_empty_results(self, snowflake_connection):
        """Test query returning empty result set."""
        from cubano import Q

        query = (
            Query()
            .metrics(Orders.order_total)
            .filter(Q(order_total__lt=0))  # Impossible condition
        )
        results = snowflake_connection.execute(query)

        # Should return empty list, not raise error
        assert results == []

    def test_null_handling(self, snowflake_connection):
        """Test queries handle NULL values correctly."""
        query = Query().dimensions(Customers.last_ordered_at).limit(100)
        results = snowflake_connection.execute(query)

        # Some customers may not have orders (NULL last_ordered_at)
        # Query should succeed and include NULLs
        assert isinstance(results, list)

    def test_large_result_set(self, snowflake_connection):
        """Test query with large result set (pagination)."""
        query = Query().metrics(Orders.order_total).limit(1000)
        results = snowflake_connection.execute(query)

        # Should respect LIMIT
        assert len(results) == 1000
```

**Source:** Original implementation

**Confidence:** HIGH

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest.mock directly | pytest-mock plugin | ~2018 | Simpler fixture-based mocking; better pytest integration |
| Manual environment variable handling | pydantic-settings | 2020-2021 | Type-safe config; automatic validation; multi-source support |
| pytest-django transaction rollback for all DBs | Per-worker schema isolation | 2022+ | Better parallel test support; works with warehouses lacking nested transaction support |
| Hardcoded test credentials | Credential management with SecretStr | 2023+ | Security best practice; prevents accidental credential leaks |
| Manual worker tracking | pytest-xdist worker_id fixture | 2016+ (stable) | Reliable worker identification; handles master mode |

**Deprecated/outdated:**
- **pytest.fixture(params=..., scope="session")**: Scope + params interaction changed in pytest 7+; prefer module scope or function scope for parametrized fixtures
- **pytest.config**: Deprecated in favor of `request.config` fixture
- **Manual .env parsing with os.getenv()**: Use pydantic-settings for type safety and validation

**Source:** pytest changelog, pydantic-settings documentation, pytest-xdist evolution

**Confidence:** MEDIUM - Based on ecosystem trends, not specific version deprecation notices

## Open Questions

### 1. Connection Pool Sizing for Parallel Tests

**What we know:**
- Snowflake supports connection pooling via `SnowflakeConnectionPool`
- Each pytest-xdist worker can create its own pool
- Total connections = workers × pool_size

**What's unclear:**
- What's the default connection limit for Snowflake accounts?
- Does single connection per worker add measurable overhead for integration tests?

**Recommendation:** Start with single connection per worker. Add connection pooling only if query latency becomes a problem (unlikely for integration tests with limited query volume).

**Source:** [Snowflake connection pooling](https://docs.devart.com/python/snowflake/connection-pooling.htm)

**Confidence:** MEDIUM

### 2. Databricks SQL Connector Transaction Support

**What we know:**
- Databricks SQL connector supports query execution
- Unity Catalog provides schema isolation

**What's unclear:**
- Does Databricks SQL connector support transactions (BEGIN/COMMIT/ROLLBACK)?
- Can we use transaction rollback instead of schema isolation?

**Recommendation:** Use schema isolation (matches Snowflake pattern). Investigate transaction support if schema creation overhead becomes a problem.

**Source:** [Databricks SQL connector documentation](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector)

**Confidence:** LOW - Limited documentation on transaction support for Databricks SQL connector

### 3. Optimal pytest-xdist Worker Count for CI

**What we know:**
- `pytest -n auto` detects CPU count
- Each worker creates warehouse connection

**What's unclear:**
- Does GitHub Actions runner CPU count align with optimal worker count?
- Should we limit worker count to avoid warehouse connection limits?

**Recommendation:** Use `-n auto` in CI. Monitor for connection exhaustion. If problems occur, reduce to `-n 4` or lower.

**Confidence:** LOW - Depends on GitHub Actions runner specs and Snowflake/Databricks connection limits

## Sources

### Primary (HIGH confidence)

- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Fixture scopes, yield teardown, autouse
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/en/stable/how-to.html) - Worker identification, test isolation
- [pytest custom markers](https://docs.pytest.org/en/stable/example/markers.html) - Marker registration and filtering
- [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - BaseSettings, SecretStr, multi-source loading
- [Snowflake Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) - Schema isolation patterns

### Secondary (MEDIUM confidence)

- [Pytest Fixtures: The Complete Guide for 2026](https://devtoolbox.dedyn.io/blog/pytest-fixtures-complete-guide) - Fixture best practices
- [How to Handle pytest Markers](https://oneuptime.com/blog/post/2026-02-02-pytest-markers-guide/view) - 2026 marker guide
- [Parallel Testing Made Easy With pytest-xdist](https://pytest-with-eric.com/plugins/pytest-xdist/) - xdist patterns and pitfalls
- [Pytest Conftest With Best Practices](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/) - conftest organization
- [Perfect Test Isolation using Database Transactions](https://blog.alexsanjoseph.com/posts/20250914-perfect-test-isolation-using-database-transactions/) - Transaction rollback patterns
- [Snowflake Security and Data Privacy](https://centricconsulting.com/blog/snowflake-security-and-data-privacy-identifying-organizing-and-isolating-data/) - Schema isolation
- [Unity Catalog distributed governance](https://www.databricks.com/blog/2023/03/09/distributed-data-governance-and-isolated-environments-unity-catalog.html) - Databricks schema isolation

### Tertiary (LOW confidence)

- [Snowflake connection pooling](https://docs.devart.com/python/snowflake/connection-pooling.htm) - Third-party connector docs
- [dbt unit testing patterns](https://pypi.org/project/pytest-dbt/) - dbt testing ecosystem

## Metadata

**Confidence breakdown:**
- Test fixture patterns: HIGH - Official pytest documentation and verified patterns
- Data isolation strategies: HIGH - Official warehouse documentation and xdist patterns
- Credential management: HIGH - pydantic-settings is standard solution
- Mock vs real testing: HIGH - pytest markers and conditional execution well-documented
- Parallel execution: HIGH - pytest-xdist is mature and widely used
- jaffle-shop integration: HIGH - Codebase analysis

**Research date:** 2026-02-17
**Valid until:** 60 days (stable ecosystem; pytest and pydantic-settings evolve slowly)
