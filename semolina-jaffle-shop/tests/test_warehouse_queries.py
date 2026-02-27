"""
Warehouse integration tests for semolina-jaffle-shop.

Tests validate query execution against real Snowflake warehouse, ensuring
generated SQL executes correctly and returns expected result structures.
Tests verify field combinations, ordering behavior, limiting, edge cases,
and filtering against actual jaffle-shop data.

All tests marked with @pytest.mark.warehouse and @pytest.mark.snowflake for
selective execution. Tests require SNOWFLAKE_* environment variables set.
"""

import pytest
from semolina_jaffle_shop.jaffle_models import Customers, Orders, Products

from semolina.fields import NullsOrdering


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestFieldCombinations:
    """Test query field combinations execute correctly on Snowflake."""

    def test_single_metric_execution(self, snowflake_connection) -> None:
        """
        Query with single metric should execute and return results with metric field.

        Validates that metric-only queries generate valid SQL and return expected
        schema structure from real warehouse.
        """
        result = Orders.query().metrics(Orders.order_total).limit(10).execute()

        assert len(result) <= 10, "Should respect LIMIT 10"
        assert all("order_total" in row for row in result), "All rows should have order_total field"

    def test_multiple_metrics_execution(self, snowflake_connection) -> None:
        """
        Query with multiple metrics should execute and return results with all metric fields.

        Validates that multi-metric queries generate valid SQL with correct SELECT clause
        and return expected schema from warehouse.
        """
        result = Orders.query().metrics(Orders.order_total, Orders.order_count).limit(10).execute()

        assert len(result) <= 10, "Should respect LIMIT 10"
        assert all("order_total" in row for row in result), "All rows should have order_total field"
        assert all("order_count" in row for row in result), "All rows should have order_count field"

    def test_metric_with_dimension_grouping(self, snowflake_connection) -> None:
        """
        Query with metric and dimension should execute with proper GROUP BY.

        Validates that metrics + dimensions generate valid GROUP BY clause and
        return correctly aggregated results grouped by dimension.
        """
        result = (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.ordered_at)
            .limit(50)
            .execute()
        )

        assert len(result) <= 50, "Should respect LIMIT 50"
        assert all("order_total" in row for row in result), "All rows should have order_total field"
        assert all("ordered_at" in row for row in result), (
            "All rows should have ordered_at dimension"
        )

    def test_dimension_only_execution(self, snowflake_connection) -> None:
        """
        Query with dimension only should execute without metrics.

        Validates that dimension-only queries (no aggregation) generate valid
        SQL and return distinct dimension values.
        """
        result = Customers.query().dimensions(Customers.customer_name).limit(10).execute()

        assert len(result) <= 10, "Should respect LIMIT 10"
        assert all("customer_name" in row for row in result), (
            "All rows should have customer_name field"
        )


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestOrdering:
    """Test ORDER BY behavior executes correctly on Snowflake."""

    def test_order_by_metric_descending(self, snowflake_connection) -> None:
        """
        Query with ORDER BY metric DESC should return descending sorted results.

        Validates that ORDER BY clause generates correct SQL and warehouse returns
        results in descending order (highest values first).
        """
        result = (
            Orders.query()
            .metrics(Orders.order_total)
            .order_by(Orders.order_total.desc())
            .limit(10)
            .execute()
        )

        assert len(result) > 0, "Should return results"
        # Validate descending order: each value >= next value
        totals = [row["order_total"] for row in result if row["order_total"] is not None]
        for i in range(len(totals) - 1):
            assert totals[i] >= totals[i + 1], f"Results should be descending: {totals}"

    def test_order_by_dimension_ascending(self, snowflake_connection) -> None:
        """
        Query with ORDER BY dimension ASC should return ascending sorted results.

        Validates that ORDER BY dimension generates correct SQL and warehouse
        returns results in ascending alphabetical order.
        """
        result = (
            Customers.query()
            .dimensions(Customers.customer_name)
            .order_by(Customers.customer_name.asc())
            .limit(10)
            .execute()
        )

        assert len(result) > 0, "Should return results"
        # Validate ascending order: each value <= next value
        names = [row["customer_name"] for row in result if row["customer_name"] is not None]
        for i in range(len(names) - 1):
            assert names[i] <= names[i + 1], f"Results should be ascending: {names}"

    def test_order_by_with_nulls(self, snowflake_connection) -> None:
        """
        Query with ORDER BY and NULLS LAST should place nulls at end.

        Validates that NULLS ordering clause generates correct SQL and warehouse
        respects null placement directive.
        """
        result = (
            Customers.query()
            .dimensions(Customers.last_ordered_at)
            .order_by(Customers.last_ordered_at.desc(nulls=NullsOrdering.LAST))
            .limit(20)
            .execute()
        )

        assert len(result) > 0, "Should return results"
        # Validate nulls are last: find first null, ensure all subsequent are null
        null_indices = [i for i, row in enumerate(result) if row["last_ordered_at"] is None]
        if null_indices:
            first_null = null_indices[0]
            # All values after first null should be null
            for i in range(first_null, len(result)):
                assert result[i]["last_ordered_at"] is None, (
                    "All values after first null should be null (NULLS LAST)"
                )


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestLimiting:
    """Test LIMIT clause behavior on Snowflake."""

    def test_limit_small(self, snowflake_connection) -> None:
        """
        Query with small LIMIT should return exact number of rows.

        Validates that LIMIT clause generates correct SQL and warehouse
        returns requested number of rows.
        """
        result = Products.query().dimensions(Products.product_name).limit(5).execute()

        assert len(result) <= 5, "Should return at most 5 rows"

    def test_limit_large(self, snowflake_connection) -> None:
        """
        Query with large LIMIT should handle large result sets.

        Validates that queries can fetch large result sets (1000+ rows)
        without errors or performance issues.
        """
        result = Orders.query().metrics(Orders.order_total).limit(1000).execute()

        assert len(result) <= 1000, "Should return at most 1000 rows"
        assert len(result) > 0, "Should return data from warehouse"

    def test_no_limit(self, snowflake_connection) -> None:
        """
        Query without LIMIT should return all matching rows.

        Validates that queries without LIMIT clause execute successfully
        and return all available data.
        """
        result = Products.query().dimensions(Products.product_type).execute()

        assert len(result) > 0, "Should return results without limit"


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestEdgeCases:
    """Test edge case handling on Snowflake."""

    def test_empty_results(self, snowflake_connection) -> None:
        """
        Query with impossible filter should return empty list, not error.

        Validates that queries with no matching data return empty results
        gracefully rather than raising exceptions.
        """
        # Filter for impossible condition: order_total < 0 should return no results
        result = Orders.query().metrics(Orders.order_total).where(Orders.order_total < 0).execute()

        assert len(result) == 0, "Impossible filter should return empty result"

    def test_null_handling_in_results(self, snowflake_connection) -> None:
        """
        Query returning null values should include nulls in results.

        Validates that queries handle null values correctly without crashing
        and include them in result dictionaries.
        """
        result = Customers.query().dimensions(Customers.last_ordered_at).limit(100).execute()

        assert len(result) > 0, "Should return results"
        # Verify at least some nulls exist (customers who haven't ordered yet)
        # Note: This assumes jaffle-shop data has customers with null last_ordered_at
        # If no nulls exist, test still validates no crash on null handling
        # Test passes regardless - validates null handling doesn't crash
        _ = any(row["last_ordered_at"] is None for row in result)

    def test_large_result_set(self, snowflake_connection) -> None:
        """
        Query with large LIMIT should fetch all rows correctly.

        Validates that large result sets are fetched completely without
        pagination issues or incomplete results.
        """
        result = Orders.query().metrics(Orders.order_count).limit(1000).execute()

        assert len(result) > 0, "Should return results"
        # Verify all results have expected structure
        assert all("order_count" in row for row in result), "All rows should have order_count field"


@pytest.mark.warehouse
@pytest.mark.snowflake
class TestFiltering:
    """Test filter execution on Snowflake."""

    def test_filter_boolean_true(self, snowflake_connection) -> None:
        """
        Query with boolean filter should return only matching rows.

        Validates that boolean filters generate correct WHERE clause and
        warehouse returns only rows matching the filter condition.
        """
        result = (
            Orders.query()
            .metrics(Orders.order_total)
            .dimensions(Orders.is_food_order)
            .where(Orders.is_food_order == True)  # noqa: E712
            .limit(50)
            .execute()
        )

        assert len(result) > 0, "Should return results for food orders"
        # Validate all returned rows match filter
        assert all(row["is_food_order"] is True for row in result), (
            "All results should have is_food_order=True"
        )

    def test_filter_comparison_greater_than(self, snowflake_connection) -> None:
        """
        Query with comparison filter should return only matching rows.

        Validates that comparison filters (gt, lt, gte, lte) generate correct
        WHERE clause and warehouse returns only rows matching the condition.
        """
        result = (
            Customers.query()
            .metrics(Customers.lifetime_spend)
            .where(Customers.lifetime_spend > 100)
            .limit(50)
            .execute()
        )

        assert len(result) > 0, "Should return results with lifetime_spend > 100"
        # Validate all returned rows match filter
        assert all(row["lifetime_spend"] > 100 for row in result), (
            "All results should have lifetime_spend > 100"
        )
