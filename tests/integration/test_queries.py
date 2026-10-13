"""
Warehouse query integration tests for SQL correctness.

Tests run against recorded cassettes by default (incl. CI) via
pytest-adbc-replay — no credentials, no warehouse. Each cassette holds the
real SQL Semolina generated plus the real Arrow result the warehouse returned,
so replay validates two things at once: the generated SQL still matches what was
recorded (a mismatch raises ``CassetteMissError``), and the cursor returns the
correct aggregated rows.

Most tests assert on raw DBAPI tuples from ``cursor.fetchall()``.
``test_streaming_iteration`` covers the ``Row`` conversion path via
``for row in cursor:`` and pins the ``Row`` keys: every selected column is aliased
to its Python field name (ALIAS-01), so both backends return ``revenue`` and
``country`` rather than ``AGG("REVENUE")`` / ``COUNTRY`` or ``measure(revenue)``.

Every test is marked ``@pytest.mark.adbc_cassette`` (module-wide via
``pytestmark``) so the plugin intercepts the pool's connections. Each runs
against both Snowflake and Databricks through the ``backend_engine`` fixture;
cassettes are stored per test+backend.

To (re)record against real warehouses, configure ``[connections.snowflake]`` /
``[connections.databricks]`` in ``.semolina.toml`` (or ``SNOWFLAKE_*`` /
``DATABRICKS_*`` env vars), then commit the cassettes::

    pytest --adbc-record=all tests/integration/test_queries.py

Assertions compare raw row tuples in SELECT-clause order (metrics first, then
dimensions). Numeric values are normalized (Snowflake returns ``Decimal``,
Databricks ``int``) so expectations are backend-agnostic.

See docs/src/how-to/warehouse-testing.rst for the full workflow.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from semolina import Dimension, Metric, SemanticView
from semolina.fields import NullsOrdering

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
    is_online = Dimension()


def _norm(value: Any) -> Any:
    """
    Normalize a numeric cell so it compares across backends.

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
    """Normalize an iterable of row tuples for backend-agnostic comparison."""
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
        # Read by field name: the aliases make the Row keys the same on both
        # backends (ALIAS-01). Row.values() order is not a Semolina contract.
        result: dict[str, Any] = {}
        for row in cursor:
            assert set(row.keys()) == {"revenue", "country"}
            result[row.country] = _norm(row.revenue)
    finally:
        cursor.close()
    assert result == {"CA": 2800, "MX": 1500, "US": 1500}


def test_filtered_by_metric(backend_engine: Any) -> None:  # noqa: ARG001
    """
    A metric filter applies to the totals, after grouping (FILT-04, D4).

    CA's two rows are 2000 and 800. Its total of 2800 passes ``> 1500``; filtering the rows
    before adding them up would have returned 2000 instead.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .where(Sales.revenue > 1500)
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(2800, "CA")]


def test_dimension_and_metric_filters_combine(backend_engine: Any) -> None:  # noqa: ARG001
    """
    ANDed filters split: the dimension one filters rows, the metric one the totals.

    Without MX, the totals are CA 2800 and US 1500, and both pass ``> 1400``. Applying
    ``> 1400`` to rows would keep only CA's 2000.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .where((Sales.country != "MX") & (Sales.revenue > 1400))
        .order_by(Sales.country)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(2800, "CA"), (1500, "US")]


def test_metric_filter_matching_nothing_returns_no_rows(backend_engine: Any) -> None:  # noqa: ARG001
    """A metric filter no total meets returns an empty result rather than raising."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
        .where(Sales.revenue < 0)
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == []


def test_filtered_by_boolean(backend_engine: Any) -> None:  # noqa: ARG001
    """A boolean dimension filters with ``== True`` and comes back as ``bool``."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.is_online)
        .where(Sales.is_online == True)  # noqa: E712
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    # Online rows: 1000 + 500 + 800
    assert rows == [(2300, True)]


def test_filtered_by_null(backend_engine: Any) -> None:  # noqa: ARG001
    """``== None`` compiles to IS NULL and matches the NULL row (FILT-01, D3)."""
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.is_online)
        .where(Sales.is_online == None)  # noqa: E711
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(1500, None)]


def test_nulls_last_ascending(backend_engine: Any) -> None:  # noqa: ARG001
    """
    ``asc(nulls=LAST)`` puts the NULL group last.

    Databricks sorts NULLs first in an ascending sort unless told otherwise, so this is
    the case that needs the clause there.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.is_online)
        .order_by(Sales.is_online.asc(nulls=NullsOrdering.LAST))
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(2000, False), (2300, True), (1500, None)]


def test_nulls_last_descending(backend_engine: Any) -> None:  # noqa: ARG001
    """
    ``desc(nulls=LAST)`` puts the NULL group last.

    Snowflake sorts NULLs first in a descending sort unless told otherwise, so this is
    the case that needs the clause there.
    """
    cursor = (
        Sales.query()
        .using("test")
        .metrics(Sales.revenue)
        .dimensions(Sales.is_online)
        .order_by(Sales.is_online.desc(nulls=NullsOrdering.LAST))
        .execute()
    )
    try:
        rows = _rows(cursor.fetchall())
    finally:
        cursor.close()
    assert rows == [(2300, True), (2000, False), (1500, None)]
