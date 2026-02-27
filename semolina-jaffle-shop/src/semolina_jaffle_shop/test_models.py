"""
Tests for semolina-jaffle-shop semantic model translation.

Validates that dbt semantic models are correctly translated to Semolina
models with accurate field types and counts.
"""

from semolina import Dimension, Metric

from .jaffle_models import Customers, Orders, Products


class TestOrdersTranslation:
    """Validate Orders model translation from dbt semantic model."""

    def test_orders_translation(self) -> None:
        """Test Orders model has correct view name, field count, and types."""
        # Check view name
        assert Orders._view_name == "orders"

        # Check field count
        expected_fields = {
            "order_total",
            "order_count",
            "tax_paid",
            "order_cost",
            "ordered_at",
            "order_total_dim",
            "is_food_order",
            "is_drink_order",
            "customer_order_number",
        }
        assert set(Orders._fields.keys()) == expected_fields
        assert len(Orders._fields) == 9

        # Check metric fields
        metrics = ["order_total", "order_count", "tax_paid", "order_cost"]
        for metric_name in metrics:
            field = Orders._fields[metric_name]
            assert isinstance(field, Metric), f"{metric_name} should be Metric"

        # Check dimension fields
        dimensions = [
            "ordered_at",
            "order_total_dim",
            "is_food_order",
            "is_drink_order",
            "customer_order_number",
        ]
        for dim_name in dimensions:
            field = Orders._fields[dim_name]
            assert isinstance(field, Dimension), f"{dim_name} should be Dimension"


class TestCustomersTranslation:
    """Validate Customers model translation from dbt semantic model."""

    def test_customers_translation(self) -> None:
        """Test Customers model has correct view name, field count, and types."""
        # Check view name
        assert Customers._view_name == "customers"

        # Check field count
        expected_fields = {
            "customers",
            "count_lifetime_orders",
            "lifetime_spend_pretax",
            "lifetime_spend",
            "customer_name",
            "customer_type",
            "first_ordered_at",
            "last_ordered_at",
        }
        assert set(Customers._fields.keys()) == expected_fields
        assert len(Customers._fields) == 8

        # Check metric fields
        metrics = [
            "customers",
            "count_lifetime_orders",
            "lifetime_spend_pretax",
            "lifetime_spend",
        ]
        for metric_name in metrics:
            field = Customers._fields[metric_name]
            assert isinstance(field, Metric), f"{metric_name} should be Metric"

        # Check dimension fields
        dimensions = [
            "customer_name",
            "customer_type",
            "first_ordered_at",
            "last_ordered_at",
        ]
        for dim_name in dimensions:
            field = Customers._fields[dim_name]
            assert isinstance(field, Dimension), f"{dim_name} should be Dimension"


class TestProductsTranslation:
    """Validate Products model translation from dbt semantic model."""

    def test_products_translation(self) -> None:
        """Test Products model has correct view name, field count, and types."""
        # Check view name
        assert Products._view_name == "products"

        # Check field count
        expected_fields = {
            "product_name",
            "product_type",
            "product_description",
            "is_food_item",
            "is_drink_item",
            "product_price",
        }
        assert set(Products._fields.keys()) == expected_fields
        assert len(Products._fields) == 6

        # Check that all fields are dimensions (no metrics in Products)
        dimensions = [
            "product_name",
            "product_type",
            "product_description",
            "is_food_item",
            "is_drink_item",
            "product_price",
        ]
        for dim_name in dimensions:
            field = Products._fields[dim_name]
            assert isinstance(field, Dimension), f"{dim_name} should be Dimension"
