"""Shared SemanticView models for unit tests."""

from __future__ import annotations

from cubano import Dimension, Fact, Metric, SemanticView


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
    unit_price = Fact()
