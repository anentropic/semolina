"""
Shared pytest fixtures for Cubano test suite.

Provides centralized test data and engine instances for use across all test files.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from models import Sales

from cubano.engines.mock import MockEngine


def pytest_configure(config: pytest.Config) -> None:
    """
    Set NO_COLOR before any test modules are imported.

    Rich initializes its Console at import time, reading NO_COLOR from os.environ.
    Setting it here ensures ANSI escape codes are suppressed in CliRunner output,
    including when FORCE_COLOR=1 is set in the environment.
    """
    os.environ.setdefault("NO_COLOR", "1")


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset registry after each test to prevent state leaking."""
    yield
    from cubano import registry

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
