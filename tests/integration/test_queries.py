"""
Warehouse query integration tests for SQL compatibility.

Tests run in replay mode by default (incl. CI) against a fake DBAPI pool — a
lightweight test-local mock, not DuckDB — that returns the raw ``TEST_DATA``
rows for every query. The mock does NOT aggregate or filter, so replay
snapshots are smoke-level: they exercise the query/build/cursor path but do not
validate that the generated SQL produces correct results. Real validation
happens in record mode against live warehouses.

Each test function runs against both Snowflake and Databricks via the
backend_engine parametrized fixture -- pytest creates [snowflake_engine] and
[databricks_engine] variants automatically.

To regenerate the (mock) replay snapshots in CI, no credentials needed:
  pytest --snapshot-update tests/integration/test_queries.py

To record snapshots against real warehouses (requires credentials):
  pytest --warehouse-record --snapshot-update tests/integration/test_queries.py

See docs/guides/warehouse-testing.md for the full workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from semolina import Dimension, Metric, SemanticView

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView for integration query tests.

    View name matches the key used in TEST_DATA and the replay mock pool.
    Do not use this model in other test modules.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


def test_single_metric(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate single metric query returns expected aggregated revenue."""
    cursor = Sales.query().using("test").metrics(Sales.revenue).order_by(Sales.revenue).execute()
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_multiple_metrics(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate multiple metrics query returns both revenue and cost."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .order_by(Sales.revenue)
        .execute()
    )
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_metric_with_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate metric grouped by dimension returns revenue per country."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_multiple_metrics_with_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate multiple metrics grouped by dimension returns revenue and cost per country."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_dimension_only(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """Validate dimension-only query returns distinct country and region combinations."""
    cursor = (
        Sales.query()
        .using("test")
        .dimensions(Sales.country, Sales.region)
        .order_by(Sales.region, Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_filtered_by_dimension(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """
    Validate WHERE filter by dimension returns only matching rows.

    NOTE: In replay mode the fake DBAPI pool ignores the WHERE clause and
    returns the full TEST_DATA, so the replay snapshot does NOT reflect the
    filter — it is a smoke check of the query path only. To validate the filter
    against real Snowflake/Databricks data and regenerate the snapshot, re-run
    this test with ``--warehouse-record --snapshot-update``.
    This requires SNOWFLAKE_* / DATABRICKS_* credentials in the environment.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .order_by(Sales.country)
        .execute()
    )
    rows = [dict(row.items()) for row in cursor.fetchall_rows()]
    cursor.close()
    assert rows == snapshot


def test_streaming_iteration(backend_engine: Any, snapshot: SnapshotAssertion) -> None:  # noqa: ARG001
    """
    Validate ``for row in cursor:`` streams Row objects across backends.

    The replay mock pool does not expose ``fetch_record_batch`` -- streaming is
    an ADBC-only surface. Skip in replay; record mode runs against real warehouses.

    Skip-mechanism: the replay fake pool carries ``_is_replay_mock = True``;
    real ADBC pools do not. ``getattr(..., False)`` is a stable, dependency-free
    way to detect "is this the replay mock?".
    """
    if getattr(backend_engine, "_is_replay_mock", False):
        pytest.skip("Streaming iteration requires a real ADBC pool (run with --warehouse-record)")

    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = [dict(row.items()) for row in cursor]
    finally:
        cursor.close()
    assert rows == snapshot
