"""
Warehouse integration tests for semolina-jaffle-shop.

Tests validate query execution against a real Snowflake warehouse, ensuring generated SQL
executes and returns the rows a query asks for: field combinations, ordering, limiting,
edge cases and filtering against the jaffle-shop data.

All tests are marked ``warehouse`` and ``snowflake`` and skip without Snowflake credentials
(``[connections.snowflake]`` in ``.semolina.toml`` or ``SNOWFLAKE_*``), so CI never runs
them. Each asserts a non-empty result wherever the data has rows, because an assertion such
as ``len(result) <= 10`` or ``all(... for row in result)`` is satisfied by an empty result
and so can never fail.

Rows are read by Python field name (``row["order_total"]``). On Snowflake a metric's result
column is currently ``AGG("ORDER_TOTAL")`` rather than ``order_total``. Once the builder
aliases every column to its field name, these tests pass on Snowflake.
"""

from typing import Any

import pytest
from semolina_jaffle_shop.jaffle_models import Customers, Orders, Products

from semolina import Row
from semolina.fields import NullsOrdering


def _rows(query: Any) -> list[Row]:
    """
    Execute a query and return every row, closing the cursor.

    Args:
        query: A built query, ready to execute.

    Returns:
        The fetched rows.
    """
    with query.execute() as cursor:
        return cursor.fetchall_rows()


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestFieldCombinations:
    """Test query field combinations execute correctly on Snowflake."""

    def test_single_metric_execution(self, snowflake_connection) -> None:
        """A metric-only query returns one aggregated row carrying the metric."""
        result = _rows(Orders.query().metrics(Orders.order_total).limit(10))

        assert len(result) == 1, "A metrics-only query aggregates to a single row"
        assert "order_total" in result[0]

    def test_multiple_metrics_execution(self, snowflake_connection) -> None:
        """A multi-metric query returns one aggregated row carrying every metric."""
        result = _rows(Orders.query().metrics(Orders.order_total, Orders.order_count).limit(10))

        assert len(result) == 1, "A metrics-only query aggregates to a single row"
        assert "order_total" in result[0]
        assert "order_count" in result[0]

    def test_metric_with_dimension_grouping(self, snowflake_connection) -> None:
        """A metric grouped by a dimension returns one row per group, within the limit."""
        result = _rows(
            Orders.query().metrics(Orders.order_total).dimensions(Orders.ordered_at).limit(50)
        )

        assert 0 < len(result) <= 50
        assert all("order_total" in row and "ordered_at" in row for row in result)

    def test_dimension_only_execution(self, snowflake_connection) -> None:
        """A dimension-only query returns distinct values, within the limit."""
        result = _rows(Customers.query().dimensions(Customers.customer_name).limit(10))

        assert 0 < len(result) <= 10
        assert all("customer_name" in row for row in result)


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestOrdering:
    """Test ORDER BY behavior executes correctly on Snowflake."""

    def test_order_by_metric_descending(self, snowflake_connection) -> None:
        """ORDER BY a metric DESC returns its groups largest first."""
        result = _rows(
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.ordered_at)
            .order_by(Orders.order_total.desc())
            .limit(10)
        )

        totals = [row["order_total"] for row in result if row["order_total"] is not None]
        assert len(totals) > 1, "Need at least two groups to observe an ordering"
        assert totals == sorted(totals, reverse=True)

    def test_order_by_dimension_ascending(self, snowflake_connection) -> None:
        """ORDER BY a dimension ASC returns its values in ascending order."""
        result = _rows(
            Customers.query()
            .dimensions(Customers.customer_name)
            .order_by(Customers.customer_name.asc())
            .limit(10)
        )

        names = [row["customer_name"] for row in result if row["customer_name"] is not None]
        assert len(names) > 1, "Need at least two values to observe an ordering"
        assert names == sorted(names)

    def test_order_by_with_nulls(self, snowflake_connection) -> None:
        """NULLS LAST places every NULL after every non-NULL value."""
        result = _rows(
            Customers.query()
            .dimensions(Customers.last_ordered_at)
            .order_by(Customers.last_ordered_at.desc(nulls=NullsOrdering.LAST))
            .limit(20)
        )

        assert result, "Should return results"
        is_null = [row["last_ordered_at"] is None for row in result]
        assert is_null == sorted(is_null), "A NULL appears before a non-NULL value"


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestLimiting:
    """Test LIMIT clause behavior on Snowflake."""

    def test_limit_small(self, snowflake_connection) -> None:
        """A small LIMIT caps the rows returned."""
        result = _rows(Products.query().dimensions(Products.product_name).limit(5))

        assert 0 < len(result) <= 5

    def test_limit_large(self, snowflake_connection) -> None:
        """A large LIMIT still returns the query's rows."""
        result = _rows(
            Orders.query().metrics(Orders.order_total).dimensions(Orders.ordered_at).limit(1000)
        )

        assert 0 < len(result) <= 1000

    def test_no_limit(self, snowflake_connection) -> None:
        """A query without LIMIT returns every group."""
        result = _rows(Products.query().dimensions(Products.product_type))

        assert result, "Should return results without limit"


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestEdgeCases:
    """Test edge case handling on Snowflake."""

    def test_empty_results(self, snowflake_connection) -> None:
        """An impossible filter returns no rows rather than raising."""
        result = _rows(
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.ordered_at)
            .where(Orders.order_total < 0)
        )

        assert result == []

    def test_large_result_set(self, snowflake_connection) -> None:
        """A large grouped result is fetched with every row carrying the metric."""
        result = _rows(
            Orders.query().metrics(Orders.order_count).dimensions(Orders.ordered_at).limit(1000)
        )

        assert result, "Should return results"
        assert all("order_count" in row for row in result)


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestFiltering:
    """Test filter execution on Snowflake."""

    def test_filter_boolean_true(self, snowflake_connection) -> None:
        """A boolean filter returns only matching rows."""
        result = _rows(
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.is_food_order)
            .where(Orders.is_food_order == True)  # noqa: E712
            .limit(50)
        )

        assert result, "Should return results for food orders"
        assert all(row["is_food_order"] is True for row in result)

    def test_filter_comparison_greater_than(self, snowflake_connection) -> None:
        """A comparison filter returns only rows meeting the condition."""
        result = _rows(
            Customers.query()
            .metrics(Customers.lifetime_spend)
            .dimensions(Customers.customer_name)
            .where(Customers.lifetime_spend > 100)
            .limit(50)
        )

        assert result, "Should return results with lifetime_spend > 100"
        assert all(row["lifetime_spend"] > 100 for row in result)
