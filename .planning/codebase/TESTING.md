# Testing Patterns

**Analysis Date:** 2026-02-17

## Test Framework

**Runner:**
- pytest 8.0+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- Type checker (also run as quality gate): `basedpyright` in strict mode

**Assertion Library:**
- pytest's built-in `assert` statements (no separate assertion library)

**Run Commands:**
```bash
uv run --extra dev pytest          # Run all tests (includes doctests)
uv run --extra dev pytest tests/   # Unit/integration tests only
uv run --extra dev pytest src/     # Doctests in source only
uv run --extra dev pytest -x       # Stop on first failure
uv run --extra dev pytest -k "test_query"  # Run matching tests
uv run basedpyright                # Type checking (quality gate)
uv run ruff check                  # Lint (quality gate)
uv run ruff format --check         # Format check (quality gate)
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (NOT co-located with source)
- Codegen-specific tests in `tests/codegen/` subdirectory
- Doctest examples live inline in `src/cubano/` source files

**Naming:**
- Test files: `test_<module>.py` mapping to source modules (e.g., `tests/test_query.py` tests `src/cubano/query.py`)
- Warehouse-specific: `test_snowflake_engine.py`, `test_databricks_engine.py`
- Codegen group: `tests/codegen/test_loader.py`, `tests/codegen/test_generator.py`, etc.

**Structure:**
```
tests/
├── conftest.py               # Shared fixtures (Sales model, engines, credentials)
├── test_credentials.py
├── test_databricks_engine.py # Mock-based, uses unittest.mock
├── test_engines.py           # MockEngine tests
├── test_fields.py
├── test_filters.py
├── test_models.py
├── test_query.py
├── test_registry.py
├── test_results.py
├── test_snowflake_engine.py  # Mock-based, uses unittest.mock
├── test_sql.py
└── codegen/
    ├── fixtures/             # Real Python model files for integration tests
    │   ├── simple_models.py
    │   ├── multi_models.py
    │   └── no_models.py
    ├── test_cli.py
    ├── test_generator.py
    ├── test_loader.py
    ├── test_renderer.py
    └── test_utils.py

src/cubano/
├── conftest.py               # Doctest namespace injection only
└── **/*.py                   # Inline doctests throughout
```

## Test Structure

**Suite Organization:**
```python
class TestQueryMetrics:
    """Test .metrics() method (QRY-01)."""

    def test_metrics_single_field(self):
        """Should accept single Metric field."""
        q = Query().metrics(Sales.revenue)
        assert q._metrics == (Sales.revenue,)

    def test_metrics_rejects_dimension(self):
        """Should reject Dimension fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            Query().metrics(Sales.country)
        assert "Did you mean .dimensions()?" in str(exc_info.value)
```

**Class naming conventions:**
- Group by behavior under test: `TestQueryMetrics`, `TestQueryFilter`, `TestQueryImmutability`
- Spec/requirement classes: `TestENG01_MockEngineWithoutWarehouse`, `TestENG02_MockEngineValidation`
- Integration classes: `TestMockEngineIntegration`, `TestQueryFetchIntegration`

**Method docstrings:** Every test method has a one-line docstring describing the expected behavior: `"""Should accept single Metric field."""`

**Patterns:**
- Setup: Define test models as class-level or local classes (no shared mutable state)
- Each test is self-contained; fixtures provide setup/teardown
- Teardown: `autouse=True` `clean_registry` fixture resets global registry after every test

## Pytest Markers

Defined in `pyproject.toml`:
```
mock      - Fast tests using MockEngine (no warehouse required)
unit      - Pure unit tests with no external dependencies
warehouse - Integration tests against real warehouse (requires credentials)
snowflake - Snowflake-specific warehouse tests
databricks - Databricks-specific warehouse tests
```

Warehouse tests skip automatically when credentials are unavailable (handled in fixtures via `pytest.skip`).

## Mocking

**Two strategies:**

**1. MockEngine (preferred for query logic):**
- Use `MockEngine` from `cubano.engines.mock` to test query building, SQL generation, and result handling without any real backend
- Load fixture data with `engine.load(view_name, rows)`:
  ```python
  engine = MockEngine()
  engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
  results = engine.execute(query)
  ```

**2. `unittest.mock` for connector tests:**
- Warehouse engine tests (`test_snowflake_engine.py`, `test_databricks_engine.py`) use `unittest.mock` to simulate the connector libraries
- `patch.dict(sys.modules, ...)` to inject mock connector:
  ```python
  from unittest.mock import MagicMock, Mock, patch

  mock_connector = MagicMock()
  with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
      from cubano.engines.snowflake import SnowflakeEngine
      engine = SnowflakeEngine(account="test", user="user", password="pass")
      mock_connector.connect.assert_not_called()
  ```
- Helper factory functions create complex mock hierarchies:
  ```python
  def _create_mock_databricks() -> tuple[MagicMock, MagicMock, MagicMock]:
      """Create a properly structured mock for databricks.sql module."""
      DatabaseError = type("DatabaseError", (Exception,), {})
      mock_exc = MagicMock()
      mock_exc.DatabaseError = DatabaseError
      # ...
      return mock_databricks, mock_sql, mock_exc
  ```

**What to Mock:**
- External connector libraries (`snowflake.connector`, `databricks.sql`) in engine unit tests
- Never mock cubano internals in unit tests (test them directly)

**What NOT to Mock:**
- `MockEngine` itself (it is the mock)
- `Query`, `Q`, `Field` - test these with real instances

## Fixtures and Factories

**Shared test model (defined in `tests/conftest.py` and repeated locally):**
```python
class Sales(SemanticView, view="sales_view"):
    """Shared Sales SemanticView for testing."""
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
    unit_price = Fact()
```

Note: `Sales` is defined both in `tests/conftest.py` (for module-level use) and locally inside each test file that needs it (e.g., `tests/test_query.py` defines its own `Sales`). This is intentional to avoid import coupling issues.

**Fixture data (in `tests/conftest.py`):**
```python
@pytest.fixture
def sales_fixtures() -> dict[str, list[dict[str, Any]]]:
    """Provides standard test fixture data for sales_view."""
    return {
        "sales_view": [
            {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
            {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
            {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
        ]
    }

@pytest.fixture
def sales_engine(sales_fixtures) -> MockEngine:
    """Provides a MockEngine instance with sales fixture data loaded."""
    engine = MockEngine()
    for view_name, data in sales_fixtures.items():
        engine.load(view_name, data)
    return engine
```

**File-based fixtures for codegen tests:**
- `tests/codegen/fixtures/` contains real Python files (`simple_models.py`, `multi_models.py`, `no_models.py`)
- Imported by codegen tests as actual model files to exercise the loader/generator pipeline

**In-test inline source strings:**
- Codegen tests also define Python source as strings and write to `tmp_path`:
  ```python
  SIMPLE_MODEL_SRC = """
  from cubano import SemanticView, Metric, Dimension
  class Sales(SemanticView, view='sales_view'):
      revenue = Metric()
  """

  def test_extracts_single_model(self, tmp_path: Path) -> None:
      f = tmp_path / "models.py"
      f.write_text(SIMPLE_MODEL_SRC)
      module = load_module_from_path(f)
      models = extract_models_from_module(module, f)
      assert len(models) == 1
  ```

**Location:**
- Pytest fixtures in `tests/conftest.py` (function scope unless otherwise noted)
- `scope="session"` for credential fixtures and DB connections to reduce overhead
- `autouse=True` for `clean_registry` to guarantee global state reset

## Registry Cleanup Pattern

The global engine registry must be reset between tests. The `autouse` fixture handles this:

```python
@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    from cubano import registry
    registry.reset()
```

Tests that register engines directly use `cubano.register()` and rely on this fixture for cleanup.

## Doctest Configuration

**Pytest options (`pyproject.toml`):**
```toml
[tool.pytest.ini_options]
addopts = ["--doctest-modules", "--doctest-continue-on-failure"]
doctest_optionflags = ["ELLIPSIS", "NORMALIZE_WHITESPACE"]
testpaths = ["tests", "src"]
```

**Doctest namespace (`src/cubano/conftest.py`):**
- Injects `Sales`, `Query`, `Q`, `mock_engine`, `cubano`, `SemanticView`, `Metric`, `Dimension`, `Fact`, `NullsOrdering` into all doctest namespaces
- Registers a default `MockEngine` loaded with sample data so `Query().fetch()` works in examples
- Uses `yield` fixture for cleanup (unregisters engine after each doctest):
  ```python
  @pytest.fixture(autouse=True)
  def doctest_setup(doctest_namespace: dict[str, object]) -> Generator[None, None, None]:
      # ... setup ...
      register("default", engine)
      doctest_namespace["Sales"] = Sales
      yield
      unregister("default")
  ```

**Doctest style:**
```python
Example:
    >>> query = Query().metrics(Sales.revenue).limit(100)
    >>> query._limit_value
    100
```
- Use `ELLIPSIS` (`...`) for variable output
- Use `NORMALIZE_WHITESPACE` to tolerate formatting differences
- Examples are kept minimal and focused on the method's specific behavior

## Coverage

**Requirements:** No enforced coverage threshold (no `--cov-fail-under` in config).

**View Coverage:**
```bash
uv run --extra dev pytest --cov=cubano --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Test individual classes and methods in isolation
- Files: `tests/test_fields.py`, `tests/test_filters.py`, `tests/test_query.py`, `tests/test_models.py`, `tests/test_results.py`, `tests/test_registry.py`, `tests/test_sql.py`
- Scope: single class or method, no external dependencies

**Doctests:**
- Embedded in source docstrings, run by `--doctest-modules`
- Serve as both documentation and regression tests
- Located throughout `src/cubano/`

**Engine Unit Tests (with mock connectors):**
- Files: `tests/test_engines.py`, `tests/test_snowflake_engine.py`, `tests/test_databricks_engine.py`
- Use `MockEngine` or `unittest.mock` to avoid real connections

**Codegen Tests:**
- Files: `tests/codegen/test_loader.py`, `tests/codegen/test_generator.py`, `tests/codegen/test_renderer.py`, `tests/codegen/test_cli.py`, `tests/codegen/test_utils.py`
- Mix of unit and integration; use `tmp_path` for filesystem operations

**Integration / Warehouse Tests:**
- Files: `tests/test_snowflake_engine.py` (warehouse sections), `tests/test_databricks_engine.py` (warehouse sections)
- Require real credentials via `snowflake_credentials` / `databricks_credentials` fixtures
- Auto-skip when credentials unavailable (`pytest.skip`)
- Use isolated schemas per worker (`test_schema_name` fixture) for `pytest-xdist` compatibility

## Common Patterns

**Error message assertion:**
```python
def test_metrics_rejects_dimension(self):
    """Should reject Dimension fields with helpful error."""
    with pytest.raises(TypeError) as exc_info:
        Query().metrics(Sales.country)
    assert "Did you mean .dimensions()?" in str(exc_info.value)
```

**Pytest `match` parameter for error messages:**
```python
with pytest.raises(ValueError, match="No engine registered"):
    q.fetch()
```

**Async / no async:** All tests are synchronous. No `asyncio` usage.

**Immutability testing:**
```python
def test_metrics_returns_new_instance(self):
    """metrics() should return new instance, original unchanged."""
    q1 = Query()
    q2 = q1.metrics(Sales.revenue)
    assert q1._metrics == ()
    assert q2._metrics == (Sales.revenue,)
    assert q1 is not q2
```

**Local model class definitions in tests:**
When a test only needs a small model and doesn't need `Sales` from conftest:
```python
def test_field_validation_valid_identifier(self):
    class TestModel:
        pass
    field = Field()
    field.__set_name__(TestModel, "valid_name")
    assert field.name == "valid_name"
```

**`tmp_path` for filesystem tests:**
```python
def test_valid_file_passes(self, tmp_path: Path) -> None:
    f = tmp_path / "models.py"
    f.write_text(SIMPLE_MODEL_SRC)
    validate_python_syntax(f)  # Should not raise
```

**Null console for CLI tests:**
```python
@pytest.fixture
def stderr() -> Console:
    """Null stderr console for testing (discards output)."""
    return Console(file=io.StringIO(), stderr=True)
```

---

*Testing analysis: 2026-02-17*
