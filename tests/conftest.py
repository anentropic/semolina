"""
Shared pytest fixtures for Cubano test suite.

Provides centralized test data and engine instances for use across all test files.
"""

from typing import Any

import pytest

from cubano import Dimension, Metric, SemanticView
from cubano.engines.mock import MockEngine


class Sales(SemanticView, view="sales_view"):
    """
    Shared Sales SemanticView for testing.

    Used across test_engines.py, test_sql.py, and other test modules to ensure
    consistency in test models.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


@pytest.fixture
def sales_model() -> type[Sales]:
    """
    Provides the Sales SemanticView class.

    Returns:
        Sales SemanticView class with revenue, cost, country, region fields

    Usage:
        def test_something(sales_model):
            query = Query().metrics(sales_model.revenue)
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
    Provides a MockEngine instance configured with sales_fixtures.

    Args:
        sales_fixtures: Injected pytest fixture with test data

    Returns:
        MockEngine instance ready for testing with sales data

    Usage:
        def test_something(sales_engine):
            query = Query().metrics(Sales.revenue)
            results = sales_engine.execute(query)
    """
    return MockEngine(fixtures=sales_fixtures)
