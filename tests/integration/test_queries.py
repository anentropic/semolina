"""
Warehouse query integration tests for SQL correctness.

Tests run against recorded cassettes by default (incl. CI) via
pytest-adbc-replay — no credentials, no warehouse. Each cassette holds the
real SQL Semolina generated plus the real Arrow result the warehouse returned,
so replay validates two things at once: the generated SQL still matches what was
recorded (a mismatch raises ``CassetteMissError``), and the cursor returns the
correct aggregated rows.

Most tests assert on raw DBAPI tuples from ``cursor.fetchall()`` (metric columns
are unaliased, so ``Row`` keys would be backend-specific names like
``AGG("REVENUE")``). ``test_streaming_iteration`` covers the ``Row`` conversion
path via ``for row in cursor:``.

Every test is marked ``@pytest.mark.adbc_cassette`` (module-wide via
``pytestmark``) so the plugin intercepts the pool's connections. Each runs
against both Snowflake and Databricks through the ``backend_engine`` fixture;
cassettes are stored per test+backend.

To (re)record against real warehouses (requires SNOWFLAKE_* / DATABRICKS_*
credentials), then commit the cassettes::

    pytest --adbc-record=once tests/integration

Assertions compare raw row tuples in SELECT-clause order (metrics first, then
dimensions). Numeric values are normalised (Snowflake returns ``Decimal``,
Databricks ``int``) so expectations are backend-agnostic.

See docs/src/how-to/warehouse-testing.rst for the full workflow.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from semolina import Dimension, Metric, SemanticView

# Every test in this module records/replays an ADBC cassette. The cassette name
# is auto-derived from the node id (including the [snowflake_engine] /
# [databricks_engine] parameter), so each test+backend gets its own recording.
pytestmark = pytest.mark.adbc_cassette


class Sales(SemanticView, view="sales_view"):
    """
    Synthetic SemanticView for integration query tests.

    View name matches the ``sales_view`` created by the recording fixtures.
    Do not use this model in other test modules.
    """

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


def _norm(value: Any) -> Any:
    """
    Normalise a numeric cell so it compares across backends.

    Snowflake returns ``Decimal`` where Databricks returns ``int``/``float``.
    Integral values collapse to ``int`` so both backends match; non-integral
    values collapse to ``float`` (never truncated). Non-numerics pass through.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    return value


def _rows(raw: Any) -> list[tuple[Any, ...]]:
    """Normalise an iterable of row tuples for backend-agnostic comparison."""
    return [tuple(_norm(v) for v in row) for row in raw]


def test_single_metric(backend_engine: Any) -> None:  # noqa: ARG001
    """SUM(revenue) across all rows -> single aggregated value."""
    cursor = Sales.query().using("test").metrics(Sales.revenue).order_by(Sales.revenue).execute()
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(5800,)]


def test_multiple_metrics(backend_engine: Any) -> None:  # noqa: ARG001
    """SUM(revenue), SUM(cost) across all rows."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .order_by(Sales.revenue)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(5800, 580)]


def test_metric_with_dimension(backend_engine: Any) -> None:  # noqa: ARG001
    """SUM(revenue) grouped by country, ordered by country."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    # SELECT AGG(revenue), country  ->  (revenue, country)
    assert rows == [(2800, "CA"), (1500, "MX"), (1500, "US")]


def test_multiple_metrics_with_dimension(backend_engine: Any) -> None:  # noqa: ARG001
    """SUM(revenue), SUM(cost) grouped by country, ordered by country."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    # SELECT AGG(revenue), AGG(cost), country
    assert rows == [(2800, 280, "CA"), (1500, 150, "MX"), (1500, 150, "US")]


def test_dimension_only(backend_engine: Any) -> None:  # noqa: ARG001
    """Distinct (country, region) pairs, ordered by region then country."""
    cursor = (
        Sales.query()
        .using("test")
        .dimensions(Sales.country, Sales.region)
        .order_by(Sales.region, Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    # SELECT country, region  ordered by region, country
    assert rows == [
        ("CA", "East"),
        ("US", "East"),
        ("MX", "South"),
        ("CA", "West"),
        ("US", "West"),
    ]


def test_filtered_by_dimension(backend_engine: Any) -> None:  # noqa: ARG001
    """WHERE country = 'US' restricts the aggregation to US rows."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue, Sales.cost)
        .dimensions(Sales.country)
        .where(Sales.country == "US")
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    # US: revenue 1000+500=1500, cost 100+50=150
    assert rows == [(1500, 150, "US")]


def test_streaming_iteration(backend_engine: Any) -> None:  # noqa: ARG001
    """``for row in cursor:`` streams Row objects (ADBC fetch_record_batch path)."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .order_by(Sales.country)
        .execute()
    )
    try:
        # Build {country: revenue} so the assertion does not depend on column
        # order or names: each streamed row has one country (str) and one
        # revenue (number). Row.values() order is not a Semolina contract.
        result: dict[str, Any] = {}
        for row in cursor:
            values = list(row.values())
            country = next(v for v in values if isinstance(v, str))
            revenue = next(_norm(v) for v in values if not isinstance(v, str))
            result[country] = revenue
    finally:
        cursor.close()
    assert result == {"CA": 2800, "MX": 1500, "US": 1500}
