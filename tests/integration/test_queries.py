"""
Warehouse query integration tests for SQL compatibility.

Tests run in replay mode (MockEngine) in CI without warehouse credentials.
Each test function runs against both Snowflake and Databricks via the backend_engine
parametrized fixture -- pytest creates [snowflake_engine] and [databricks_engine] variants
automatically.

To record snapshots against real warehouses (requires credentials):
  # Records both Snowflake and Databricks variants:
  pytest --snapshot-update tests/integration/test_queries.py

See docs/guides/warehouse-testing.md for the full workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from semolina import Dimension, Metric, SemanticView

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView for integration query tests.

    View name matches the key used in TEST_DATA and MockEngine.load().
    Do not use this model in other test modules.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


def test_single_metric(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate single metric query returns expected aggregated revenue."""
    result = Sales.query().using("test").metrics(Sales.revenue).order_by(Sales.revenue).execute()
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot


def test_multiple_metrics(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate multiple metrics query returns both revenue and cost."""
    result = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .order_by(Sales.revenue)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot


def test_metric_with_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate metric grouped by dimension returns revenue per country."""
    result = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot


def test_multiple_metrics_with_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate multiple metrics grouped by dimension returns revenue and cost per country."""
    result = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot


def test_dimension_only(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate dimension-only query returns distinct country and region combinations."""
    result = (
        Sales.query()
        .using("test")
        .dimensions(Sales.country, Sales.region)
        .order_by(Sales.region, Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot


def test_filtered_by_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """
    Validate WHERE filter by dimension returns only matching rows.

    NOTE: The [snowflake_engine] snapshot was bootstrapped from MockEngine in replay mode.
    To re-record with real Snowflake data, run:
        pytest --snapshot-update tests/integration/test_queries.py::test_filtered_by_dimension
    This requires SNOWFLAKE_* credentials in the environment.
    The [databricks_engine] variant also uses MockEngine in CI replay; re-record similarly.
    """
    result = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in result]
    assert rows == snapshot
