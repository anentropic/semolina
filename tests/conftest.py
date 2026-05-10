"""
Shared pytest fixtures for Semolina test suite.

Provides centralized test data and engine instances for use across all test files.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from models import Sales

from semolina.engines.mock import MockEngine


def pytest_configure(config: pytest.Config) -> None:
    """
    Suppress ANSI codes in CliRunner output before any test modules are imported.

    Typer's rich_utils reads GITHUB_ACTIONS / FORCE_COLOR / PY_COLORS at *import
    time* and bakes FORCE_TERMINAL=True into a module-level constant when any of
    those vars is set (GitHub Actions always sets GITHUB_ACTIONS=true).  With
    FORCE_TERMINAL=True the Rich Console ignores NO_COLOR and emits ANSI escape
    codes regardless, breaking plain-string assertions on CliRunner output.

    _TYPER_FORCE_DISABLE_TERMINAL overrides that constant to False (see
    typer.rich_utils).  NO_COLOR is kept as defence-in-depth for other cases
    (e.g. FORCE_COLOR=1 in a local dev environment).
    """
    os.environ.setdefault("_TYPER_FORCE_DISABLE_TERMINAL", "1")
    os.environ.setdefault("NO_COLOR", "1")


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    from semolina import registry

    registry.reset()


@pytest.fixture
def sales_model() -> type[Sales]:
    """
    Provides the Sales SemanticView class.

    Returns:
        Sales SemanticView class with revenue, cost, country, region fields

    Usage:
        def test_something(sales_model):
            query = _Query().metrics(sales_model.revenue)
    """
    return Sales


@pytest.fixture
def sales_fixtures() -> dict[str, list[dict[str, Any]]]:
    """
    Provides standard test fixture data for sales_view.

    Returns:
        Dict mapping 'sales_view' to list of row dicts with sample sales data

    Usage:
        def test_something(sales_fixtures):
            assert sales_fixtures['sales_view'][0]['country'] == 'US'
    """
    return {
        "sales_view": [
            {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
            {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
            {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
        ]
    }


@pytest.fixture
def sales_engine(sales_fixtures: dict[str, list[dict[str, Any]]]) -> MockEngine:
    """
    Provides a MockEngine instance with sales fixture data loaded.

    Returns:
        MockEngine instance with sales_view fixtures loaded

    Usage:
        def test_something(sales_engine):
            query = _Query().metrics(Sales.revenue)
            results = sales_engine.execute(query)
    """
    engine = MockEngine()
    for view_name, data in sales_fixtures.items():
        engine.load(view_name, data)
    return engine


@pytest.fixture
def mock_engine() -> MockEngine:
    """
    Function-scoped MockEngine for isolated fast tests without warehouse connection.

    Function scope ensures each test gets a fresh engine instance, preventing
    state leakage between tests. Use this fixture for fast, deterministic tests
    that don't require real warehouse validation.

    Returns:
        Fresh MockEngine instance for this test
    """
    return MockEngine()


def _setup_sales_data(dbapi_conn: Any, _connection_record: Any) -> None:
    """
    Create sales_data table and sales_view semantic view on each new connection.

    ADBC poolhouse creates independent DuckDB instances per physical
    connection (``source.adbc_clone``), so tables and semantic views must
    be set up on every new physical connection via a ``connect`` event.
    """
    cur = dbapi_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_data (
            id INTEGER,
            revenue INTEGER,
            cost INTEGER,
            country VARCHAR,
            region VARCHAR,
            unit_price INTEGER
        )
    """)
    cur.execute("DELETE FROM sales_data")
    cur.execute("""
        INSERT INTO sales_data VALUES
        (1, 1000, 100, 'US', 'West', 10),
        (2, 2000, 200, 'CA', 'West', 20),
        (3, 500, 50, 'US', 'East', 5)
    """)
    cur.execute("""
        CREATE OR REPLACE SEMANTIC VIEW sales_view AS
        TABLES (
            s AS sales_data PRIMARY KEY (id)
        )
        DIMENSIONS (
            s.country AS s.country,
            s.region AS s.region,
            s.unit_price AS s.unit_price
        )
        METRICS (
            s.revenue AS SUM(s.revenue),
            s.cost AS SUM(s.cost)
        )
    """)
    cur.close()
    dbapi_conn.commit()


@pytest.fixture
def duckdb_pool() -> Generator[Any, None, None]:
    """
    In-memory DuckDB pool with semantic_views extension and sales_view data.

    Uses ``connect`` events to install the extension and populate test data
    on each new physical connection (ADBC clones are independent in-memory
    instances). Registers as ``"default"`` with ``dialect="duckdb"``.
    Yields the pool, then unregisters and closes on teardown.
    """
    pytest.importorskip("adbc_driver_duckdb")
    from adbc_poolhouse import DuckDBConfig, close_pool, create_pool
    from sqlalchemy import event

    from semolina.config import _load_semantic_views

    config = DuckDBConfig(database=":memory:", pool_size=1)
    pool = create_pool(config)
    event.listen(pool, "connect", _load_semantic_views)
    event.listen(pool, "connect", _setup_sales_data)

    import semolina

    semolina.register("default", pool, dialect="duckdb")
    yield pool
    semolina.unregister("default")
    close_pool(pool)
