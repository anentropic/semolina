"""
Doctest fixtures for Semolina source-level doctests.

Injects a pre-configured MockPool and sample SemanticView into the
doctest namespace so examples in docstrings run without a real warehouse.

This conftest.py must live in src/semolina/ (not tests/) for pytest to
discover it during --doctest-modules collection.
"""

from collections.abc import Generator

import pytest

from semolina import Dimension, Fact, Metric, NullsOrdering, SemanticView, register, unregister
from semolina.pool import MockPool


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


@pytest.fixture(autouse=True)
def doctest_setup(doctest_namespace: dict[str, object]) -> Generator[None, None, None]:
    """
    Inject mock objects into all doctest namespaces.

    Registers a MockPool as 'default' and injects Sales,
    mock_pool, and the semolina module into the doctest namespace.
    Uses yield for cleanup so the registry is reset even on failure.

    Provides:
        Sales: SemanticView with revenue, cost, country, region, unit_price
        mock_pool: MockPool with sample rows loaded
        semolina: The semolina module (for register/unregister examples)
        Predicate: The Predicate filter base class
        SemanticView: Base class for defining semantic views
        Metric: Field descriptor for metric columns
        Dimension: Field descriptor for dimension columns
        Fact: Field descriptor for fact columns
        NullsOrdering: Enum for NULLS FIRST / NULLS LAST ordering
    """
    import semolina
    from semolina.filters import Predicate

    pool = MockPool()
    pool.load(
        "sales_view",
        [
            {"revenue": 1000, "cost": 100, "country": "US", "region": "West", "unit_price": 10},
            {"revenue": 2000, "cost": 200, "country": "CA", "region": "West", "unit_price": 20},
            {"revenue": 500, "cost": 50, "country": "US", "region": "East", "unit_price": 5},
        ],
    )

    register("default", pool, dialect="mock")

    doctest_namespace["Sales"] = Sales
    doctest_namespace["Predicate"] = Predicate
    doctest_namespace["mock_pool"] = pool
    doctest_namespace["semolina"] = semolina
    doctest_namespace["SemanticView"] = SemanticView
    doctest_namespace["Metric"] = Metric
    doctest_namespace["Dimension"] = Dimension
    doctest_namespace["Fact"] = Fact
    doctest_namespace["NullsOrdering"] = NullsOrdering

    yield

    unregister("default")
