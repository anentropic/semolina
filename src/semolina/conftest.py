"""
Doctest fixtures for Cubano source-level doctests.

Injects a pre-configured MockEngine and sample SemanticView into the
doctest namespace so examples in docstrings run without a real warehouse.

This conftest.py must live in src/cubano/ (not tests/) for pytest to
discover it during --doctest-modules collection.
"""

from collections.abc import Generator

import pytest
from cubano import Dimension, Fact, Metric, NullsOrdering, SemanticView, register, unregister
from cubano.engines.mock import MockEngine


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

    Registers a MockEngine as 'default' and injects Sales,
    mock_engine, and the cubano module into the doctest namespace.
    Uses yield for cleanup so the registry is reset even on failure.

    Provides:
        Sales: SemanticView with revenue, cost, country, region, unit_price
        mock_engine: MockEngine with sample rows loaded
        cubano: The cubano module (for register/unregister examples)
        Predicate: The Predicate filter base class
        SemanticView: Base class for defining semantic views
        Metric: Field descriptor for metric columns
        Dimension: Field descriptor for dimension columns
        Fact: Field descriptor for fact columns
        NullsOrdering: Enum for NULLS FIRST / NULLS LAST ordering
    """
    import cubano
    from cubano.filters import Predicate

    engine = MockEngine()
    engine.load(
        "sales_view",
        [
            {"revenue": 1000, "cost": 100, "country": "US", "region": "West", "unit_price": 10},
            {"revenue": 2000, "cost": 200, "country": "CA", "region": "West", "unit_price": 20},
            {"revenue": 500, "cost": 50, "country": "US", "region": "East", "unit_price": 5},
        ],
    )

    register("default", engine)

    doctest_namespace["Sales"] = Sales
    doctest_namespace["Predicate"] = Predicate
    doctest_namespace["mock_engine"] = engine
    doctest_namespace["cubano"] = cubano
    doctest_namespace["SemanticView"] = SemanticView
    doctest_namespace["Metric"] = Metric
    doctest_namespace["Dimension"] = Dimension
    doctest_namespace["Fact"] = Fact
    doctest_namespace["NullsOrdering"] = NullsOrdering

    yield

    unregister("default")
