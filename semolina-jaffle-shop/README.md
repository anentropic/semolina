# Semolina Jaffle Shop

Example workspace demonstrating Semolina's semantic model translation capabilities.

## Purpose

This package demonstrates how to translate dbt-labs/jaffle-shop semantic models into equivalent Semolina Python models, enabling programmatic querying of dbt semantic views from Python code.

## Models

The workspace translates three semantic models from dbt-jaffle-shop:

- **Orders**: Order fact table with measures (order_total, order_count, tax_paid, order_cost) and dimensions (ordered_at, order_total_dim, is_food_order, is_drink_order, customer_order_number)
- **Customers**: Customer dimension table with measures (customers, count_lifetime_orders, lifetime_spend_pretax, lifetime_spend) and dimensions (customer_name, customer_type, first_ordered_at, last_ordered_at)
- **Products**: Product dimension table with all dimensions (product_name, product_type, product_description, is_food_item, is_drink_item, product_price)

## Example Usage

```python
from semolina_jaffle_shop import Orders, Customers, Products

# Access model metadata
print(Orders._view_name)  # 'orders'
print(
    Orders._fields.keys()
)  # dict_keys(['order_total', 'order_count', ...])

# Fields are accessible at class level
revenue_metric = Orders.order_total  # Metric instance
date_dimension = Orders.ordered_at  # Dimension instance
```

## Workspace Integration

This workspace is configured as a workspace member in the root pyproject.toml, alongside the `src/semolina` library. Both share a single uv.lock file.

## Running Tests

Every test runs against an in-memory DuckDB instance, with no warehouse connection:

```bash
uv run pytest
```

These tests run real `semantic_view()` execution in-process. They complete in
under a second and validate query builder logic against actual aggregation,
grouping, ordering, limiting, and filtering.

Live warehouse behavior is covered by Semolina's own integration tests in
`tests/integration/`, which replay recorded Snowflake and Databricks cassettes.

## Reference

See dbt-jaffle-shop semantic model definitions in `dbt-jaffle-shop/models/marts/`:
- orders.yml
- customers.yml
- products.yml
