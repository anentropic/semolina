"""
DuckDB-backed query validation tests for semolina-jaffle-shop.

Tests exercise the full query path (metrics, dimensions, filters, ordering,
limiting) against real in-memory DuckDB ``SEMANTIC VIEW`` execution. Unlike a
mock, ``semantic_view()`` returns only the selected columns, aggregated and
grouped, so assertions verify real values, real row counts, and real ordering.

All tests marked with @pytest.mark.duckdb for selective execution.
"""

from decimal import Decimal

import pytest
from semolina_jaffle_shop.jaffle_models import Customers, Orders, Products


@pytest.mark.duckdb
class TestFieldCombinations:
    """Test query field combinations against real DuckDB aggregation."""

    def test_single_metric(self, orders_pool) -> None:
        """A metrics-only query returns one aggregated row with the SUM."""
        with Orders.query().metrics(Orders.order_total).execute() as cursor:
            result = cursor.fetchall_rows()

        # semantic_view() aggregates: one row, column named after the metric.
        assert len(result) == 1, "Metrics-only query returns a single aggregated row"
        assert "order_total" in result[0], "Selected column is the metric 'order_total'"
        # SUM of all 12 fixture order_total values.
        assert result[0]["order_total"] == Decimal("656.54")

    def test_multiple_metrics(self, orders_pool) -> None:
        """A multi-metric query returns one row with each metric SUM."""
        with Orders.query().metrics(Orders.order_total, Orders.order_count).execute() as cursor:
            result = cursor.fetchall_rows()

        assert len(result) == 1, "Metrics-only query returns a single aggregated row"
        assert result[0]["order_total"] == Decimal("656.54")
        # 12 fixture rows, each with order_count == 1.
        assert result[0]["order_count"] == 12

    def test_metric_with_dimension(self, orders_pool) -> None:
        """A metric grouped by a dimension returns one aggregated row per group."""
        with (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.is_food_order)
            .execute() as cursor
        ):
            result = cursor.fetchall_rows()

        # is_food_order has two distinct values (True/False) -> two groups.
        assert len(result) == 2, "Grouped query returns one row per dimension value"
        assert "order_total" in result[0], "Metric column is 'order_total'"
        assert "is_food_order" in result[0], "Grouping dimension is present"
        by_group = {r["is_food_order"]: r["order_total"] for r in result}
        # Sums of order_total partitioned by is_food_order.
        assert by_group[True] == Decimal("571.30")
        assert by_group[False] == Decimal("85.24")

    def test_dimension_only(self, orders_pool) -> None:
        """A dimension-only query returns the distinct dimension values."""
        with Orders.query().dimensions(Orders.is_food_order).execute() as cursor:
            result = cursor.fetchall_rows()

        assert "is_food_order" in result[0], "Results should contain is_food_order field"
        values = {r["is_food_order"] for r in result}
        assert values == {True, False}, "Both distinct boolean values returned"


@pytest.mark.duckdb
class TestOrdering:
    """Test ORDER BY against real DuckDB execution."""

    def test_order_by_metric_desc(self, orders_pool) -> None:
        """ORDER BY metric DESC returns groups sorted by the aggregated metric."""
        with (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.is_food_order)
            .order_by(Orders.order_total.desc())
            .execute()
        ) as cursor:
            result = cursor.fetchall_rows()

        totals = [r["order_total"] for r in result]
        assert totals == sorted(totals, reverse=True), "Rows sorted by order_total descending"
        # Food group (571.30) outranks non-food group (85.24).
        assert result[0]["is_food_order"] is True

    def test_order_by_dimension_asc(self, customers_pool) -> None:
        """ORDER BY dimension ASC returns rows in ascending dimension order."""
        with (
            Customers.query()
            .dimensions(Customers.customer_name)
            .order_by(Customers.customer_name.asc())
            .execute()
        ) as cursor:
            result = cursor.fetchall_rows()

        names = [r["customer_name"] for r in result]
        assert names == sorted(names), "customer_name returned in ascending order"
        assert names[0] == "Alice Anderson", "First row is the alphabetically smallest name"


@pytest.mark.duckdb
class TestLimiting:
    """Test LIMIT against real DuckDB execution."""

    def test_limit_results(self, products_pool) -> None:
        """LIMIT caps the number of returned rows."""
        with Products.query().dimensions(Products.product_name).limit(3).execute() as cursor:
            result = cursor.fetchall_rows()

        assert len(result) == 3, "LIMIT 3 returns exactly three rows"

    def test_limit_larger_than_data(self, products_pool) -> None:
        """LIMIT larger than the dataset returns all available rows."""
        with Products.query().dimensions(Products.product_name).limit(100).execute() as cursor:
            result = cursor.fetchall_rows()

        # 10 distinct product names in the fixture.
        assert len(result) == 10, "LIMIT 100 returns all 10 distinct products"


@pytest.mark.duckdb
class TestFiltering:
    """Test real SQL WHERE filtering against DuckDB execution."""

    def test_filter_boolean(self, orders_pool) -> None:
        """A boolean dimension filter reduces the distinct rows returned."""
        with Orders.query().dimensions(Orders.is_food_order).execute() as cursor:
            all_rows = cursor.fetchall_rows()
        with (
            Orders.query()
            .dimensions(Orders.is_food_order)
            .where(Orders.is_food_order == True)  # noqa: E712
            .execute()
        ) as cursor:
            filtered = cursor.fetchall_rows()

        assert len(filtered) < len(all_rows), (
            "Filtering to True drops the False group from the distinct results"
        )
        assert all(r["is_food_order"] is True for r in filtered), (
            "All returned rows satisfy is_food_order == True"
        )

    def test_filter_comparison(self, orders_pool) -> None:
        """
        A dimension comparison filter reduces grouped results.

        Filtering on an aggregated metric is not meaningful here (every group's
        SUM already exceeds small thresholds), so this filters on the
        ``customer_order_number`` dimension instead. Only rows where
        ``customer_order_number > 4`` survive; the fixture has values both above
        and below, so the filtered group count is strictly smaller.
        """
        with (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.customer_order_number)
            .execute()
        ) as cursor:
            all_rows = cursor.fetchall_rows()
        with (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.customer_order_number)
            .where(Orders.customer_order_number > 4)
            .execute()
        ) as cursor:
            filtered = cursor.fetchall_rows()

        assert len(filtered) < len(all_rows), (
            "Filter should reduce results: fixture has order numbers above and below 4"
        )
        assert all(r["customer_order_number"] > 4 for r in filtered), (
            "All returned rows satisfy customer_order_number > 4"
        )


@pytest.mark.duckdb
class TestMultiModelQueries:
    """Test queries across all three jaffle-shop views via jaffle_pool."""

    def test_orders_query(self, jaffle_pool) -> None:
        """Orders query executes with all views registered."""
        with Orders.query().metrics(Orders.order_total, Orders.order_count).execute() as cursor:
            result = cursor.fetchall_rows()

        assert len(result) == 1, "Metrics-only query returns one aggregated row"
        assert result[0]["order_total"] == Decimal("656.54")
        assert result[0]["order_count"] == 12

    def test_customers_query(self, jaffle_pool) -> None:
        """Customers query executes with all views registered."""
        with (
            Customers.query()
            .dimensions(Customers.customer_name)
            .metrics(Customers.customers)
            .execute()
        ) as cursor:
            result = cursor.fetchall_rows()

        # 6 distinct customers, each contributing customers == 1.
        assert len(result) == 6, "One grouped row per distinct customer"
        assert "customer_name" in result[0]
        assert all(r["customers"] == 1 for r in result)

    def test_products_query(self, jaffle_pool) -> None:
        """Products (metric-less) query returns distinct dimension combinations."""
        with (
            Products.query().dimensions(Products.product_name, Products.product_type).execute()
        ) as cursor:
            result = cursor.fetchall_rows()

        # 10 distinct (name, type) combinations in the fixture.
        assert len(result) == 10, "Distinct product name/type combinations"
        assert "product_name" in result[0]
        assert "product_type" in result[0]
        assert {r["product_type"] for r in result} == {"food", "drink"}
