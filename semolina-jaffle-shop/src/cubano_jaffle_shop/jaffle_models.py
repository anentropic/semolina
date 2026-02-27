"""
Semantic view models translated from dbt-jaffle-shop.

This module provides Cubano SemanticView models that translate the dbt-labs/
jaffle-shop semantic models into equivalent Python models. Each model maps dbt
dimensions to Dimension/Fact fields and measures to Metric fields, enabling
programmatic queries against dbt semantic views from Python.

Translation pattern:
- dbt dimensions (categorical) → Dimension()
- dbt dimensions (time) → Dimension()
- dbt measures → Metric()
- dbt entities (foreign keys) → Fact()
"""

from cubano import Dimension, Metric, SemanticView


class Orders(SemanticView, view="orders"):
    """
    Order fact table with one row per order.

    Measures represent aggregatable order metrics (totals, counts, costs).
    Dimensions represent order attributes for grouping and filtering.
    """

    # Measures
    order_total = Metric()
    order_count = Metric()
    tax_paid = Metric()
    order_cost = Metric()

    # Dimensions
    ordered_at = Dimension()
    order_total_dim = Dimension()
    is_food_order = Dimension()
    is_drink_order = Dimension()
    customer_order_number = Dimension()


class Customers(SemanticView, view="customers"):
    """
    Customer dimension table with one row per customer.

    Measures represent customer-level aggregations (count, lifetime spend).
    Dimensions represent customer attributes.
    """

    # Measures
    customers = Metric()
    count_lifetime_orders = Metric()
    lifetime_spend_pretax = Metric()
    lifetime_spend = Metric()

    # Dimensions
    customer_name = Dimension()
    customer_type = Dimension()
    first_ordered_at = Dimension()
    last_ordered_at = Dimension()


class Products(SemanticView, view="products"):
    """
    Product dimension table with one row per product.

    All fields are dimensions representing product attributes.
    """

    # Dimensions
    product_name = Dimension()
    product_type = Dimension()
    product_description = Dimension()
    is_food_item = Dimension()
    is_drink_item = Dimension()
    product_price = Dimension()
