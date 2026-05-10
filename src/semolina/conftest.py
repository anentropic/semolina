"""
Doctest fixtures for Semolina source-level doctests.

Injects a pre-configured DuckDB pool and sample SemanticView into the
doctest namespace so examples in docstrings run without a real warehouse.

This conftest.py must live in src/semolina/ (not tests/) for pytest to
discover it during --doctest-modules collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

from semolina import Dimension, Fact, Metric, NullsOrdering, SemanticView, register, unregister


class Sales(SemanticView, view="sales_view"):
    """
    Sample SemanticView for doctest examples.

    Provides revenue, cost, country, region, and unit_price fields
    matching the test fixtures in tests/conftest.py.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
    unit_price = Fact()


def _setup_doctest_data(dbapi_conn: Any, _connection_record: Any) -> None:
    """
    Create sales_data table and sales_view semantic view for doctests.

    Registered as a SQLAlchemy pool ``connect`` event listener. Fires
    once per physical ADBC connection creation (each ADBC clone is an
    independent in-memory DuckDB instance).
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


@pytest.fixture(autouse=True)
def doctest_setup(doctest_namespace: dict[str, object]) -> Generator[None, None, None]:
    """
    Inject DuckDB pool and model objects into all doctest namespaces.

    Creates a DuckDB in-memory pool, loads the semantic_views extension
    and test data via connect events, registers as ``"default"`` with
    ``dialect="duckdb"``, and injects Sales model and key types into
    the doctest namespace.

    Provides:
        Sales: SemanticView with revenue, cost, country, region, unit_price
        semolina: The semolina module (for register/unregister examples)
        Predicate: The Predicate filter base class
        SemanticView: Base class for defining semantic views
        Metric: Field descriptor for metric columns
        Dimension: Field descriptor for dimension columns
        Fact: Field descriptor for fact columns
        NullsOrdering: Enum for NULLS FIRST / NULLS LAST ordering
    """
    duckdb_available = pytest.importorskip("adbc_driver_duckdb")
    if not duckdb_available:
        yield
        return

    from adbc_poolhouse import DuckDBConfig, close_pool, create_pool
    from sqlalchemy import event

    import semolina
    from semolina.config import _load_semantic_views
    from semolina.filters import Predicate

    config = DuckDBConfig(database=":memory:", pool_size=1)
    pool = create_pool(config)
    event.listen(pool, "connect", _load_semantic_views)
    event.listen(pool, "connect", _setup_doctest_data)

    register("default", pool, dialect="duckdb")

    doctest_namespace["Sales"] = Sales
    doctest_namespace["Predicate"] = Predicate
    doctest_namespace["semolina"] = semolina
    doctest_namespace["SemanticView"] = SemanticView
    doctest_namespace["Metric"] = Metric
    doctest_namespace["Dimension"] = Dimension
    doctest_namespace["Fact"] = Fact
    doctest_namespace["NullsOrdering"] = NullsOrdering

    yield

    unregister("default")
    close_pool(pool)
