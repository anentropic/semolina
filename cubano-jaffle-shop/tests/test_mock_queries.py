"""
Mock-based query validation tests for cubano-jaffle-shop.

Tests validate query builder logic (metrics, dimensions, filters, ordering, limiting)
using MockEngine with realistic fixture data. Mock tests provide fast feedback on
query construction without expensive warehouse connections.

All tests marked with @pytest.mark.mock for selective execution.
"""

import pytest
from cubano_jaffle_shop.jaffle_models import Customers, Orders, Products


@pytest.mark.mock
class TestFieldCombinations:
    """Test query field combination validation with MockEngine."""

    def test_single_metric(self, orders_engine) -> None:
        """Query with single metric should return results with metric field."""
        result = Orders.query().metrics(Orders.order_total).execute()

        assert len(result) > 0, "Should return fixture data"
        # MockEngine returns raw fixture data - verify field exists
        assert "order_total_dim" in result[0], "Results should contain order_total field"

    def test_multiple_metrics(self, orders_engine) -> None:
        """Query with multiple metrics should return results with all metric fields."""
        result = Orders.query().metrics(Orders.order_total, Orders.order_count).execute()

        assert len(result) > 0, "Should return fixture data"
        # MockEngine returns raw fixture data
        assert "order_total_dim" in result[0], "Results should contain order_total field"
        assert "order_count" in result[0], "Results should contain order_count field"

    def test_metric_with_dimension(self, orders_engine) -> None:
        """Query with metric and dimension should return results with both fields."""
        result = Orders.query().metrics(Orders.order_total).dimensions(Orders.ordered_at).execute()

        assert len(result) > 0, "Should return fixture data"
        assert "order_total_dim" in result[0], "Results should contain order_total field"
        assert "ordered_at" in result[0], "Results should contain ordered_at field"

    def test_dimension_only(self, orders_engine) -> None:
        """Query with dimension only should return results with dimension field."""
        result = Orders.query().dimensions(Orders.is_food_order).execute()

        assert len(result) > 0, "Should return fixture data"
        assert "is_food_order" in result[0], "Results should contain is_food_order field"


@pytest.mark.mock
class TestOrdering:
    """Test ORDER BY behavior with MockEngine."""

    def test_order_by_metric_desc(self, orders_engine) -> None:
        """
        Query with ORDER BY metric DESC should validate query construction.

        Note: MockEngine doesn't evaluate ORDER BY - returns raw fixture data.
        This test validates query API usage, not sorting behavior.
        """
        result = (
            Orders.query()
            .metrics(Orders.order_total)
            .order_by(Orders.order_total.desc())
            .limit(5)
            .execute()
        )

        # Should not raise - validates query construction
        assert len(result) > 0, "Should return fixture data"

    def test_order_by_dimension_asc(self, customers_engine) -> None:
        """
        Query with ORDER BY dimension ASC should validate query construction.

        Note: MockEngine doesn't evaluate ORDER BY - returns raw fixture data.
        This test validates query API usage, not sorting behavior.
        """
        result = (
            Customers.query()
            .dimensions(Customers.customer_name)
            .order_by(Customers.customer_name.asc())
            .execute()
        )

        # Should not raise - validates query construction
        assert len(result) > 0, "Should return fixture data"


@pytest.mark.mock
class TestLimiting:
    """Test LIMIT behavior with MockEngine."""

    def test_limit_results(self, products_engine) -> None:
        """
        Query with LIMIT should validate query construction.

        Note: MockEngine doesn't evaluate LIMIT - returns all fixture data.
        This test validates query API usage, not result limiting.
        """
        result = Products.query().dimensions(Products.product_name).limit(3).execute()

        # Should not raise - validates query construction
        assert len(result) > 0, "Should return fixture data"

    def test_limit_larger_than_data(self, products_engine) -> None:
        """
        Query with LIMIT larger than available data should not error.

        Note: MockEngine doesn't evaluate LIMIT - returns all fixture data.
        This test validates query API usage.
        """
        result = Products.query().dimensions(Products.product_name).limit(100).execute()

        # Should not raise - validates query construction
        assert len(result) > 0, "Should return fixture data"


@pytest.mark.mock
class TestFiltering:
    """Test MockEngine in-memory predicate evaluation with jaffle-shop fixture data."""

    def test_filter_boolean(self, orders_engine) -> None:
        """
        Boolean filter returns fewer rows than the full fixture set.

        MockEngine evaluates WHERE predicates in-memory. Only rows where
        is_food_order is True are returned; the fixture contains both True
        and False rows, so the filtered count must be strictly less than the
        total row count.
        """

        all_rows = Orders.query().dimensions(Orders.is_food_order).execute()
        filtered = (
            Orders.query()
            .dimensions(Orders.is_food_order)
            .where(Orders.is_food_order == True)  # noqa: E712
            .execute()
        )

        assert len(filtered) < len(all_rows), (
            "Filter should reduce results: fixture contains both True and False rows"
        )
        assert all(r["is_food_order"] is True for r in filtered), (
            "All returned rows must satisfy is_food_order == True"
        )

    def test_filter_comparison(self, orders_engine) -> None:
        """
        Comparison filter returns fewer rows than the full fixture set.

        MockEngine evaluates WHERE predicates in-memory. Only rows where
        order_total exceeds 50 are returned; the fixture contains rows both
        above and below this threshold, so the filtered count must be strictly
        less than the total row count.
        """
        from decimal import Decimal

        all_rows = Orders.query().metrics(Orders.order_total).execute()
        filtered = (
            Orders.query().metrics(Orders.order_total).where(Orders.order_total > 50).execute()
        )

        assert len(filtered) < len(all_rows), (
            "Filter should reduce results: fixture contains rows both above and below 50"
        )
        assert all(r["order_total"] > Decimal("50") for r in filtered), (
            "All returned rows must satisfy order_total > 50"
        )


@pytest.mark.mock
class TestMultiModelQueries:
    """Test queries across multiple jaffle-shop models using jaffle_engine."""

    def test_orders_query(self, jaffle_engine) -> None:
        """Should execute Orders query with all views loaded."""
        result = Orders.query().metrics(Orders.order_total, Orders.order_count).execute()

        assert len(result) > 0, "Should return orders fixture data"
        assert "order_total_dim" in result[0]

    def test_customers_query(self, jaffle_engine) -> None:
        """Should execute Customers query with all views loaded."""
        result = (
            Customers.query()
            .dimensions(Customers.customer_name)
            .metrics(Customers.customers)
            .execute()
        )

        assert len(result) > 0, "Should return customers fixture data"
        assert "customer_name" in result[0]

    def test_products_query(self, jaffle_engine) -> None:
        """Should execute Products query with all views loaded."""
        result = Products.query().dimensions(Products.product_name, Products.product_type).execute()

        assert len(result) > 0, "Should return products fixture data"
        assert "product_name" in result[0]
        assert "product_type" in result[0]
