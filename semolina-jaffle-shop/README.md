# Cubano Jaffle Shop

Example workspace demonstrating Cubano's semantic model translation capabilities.

## Purpose

This package demonstrates how to translate dbt-labs/jaffle-shop semantic models into equivalent Cubano Python models, enabling programmatic querying of dbt semantic views from Python code.

## Models

The workspace translates three semantic models from dbt-jaffle-shop:

- **Orders**: Order fact table with measures (order_total, order_count, tax_paid, order_cost) and dimensions (ordered_at, order_total_dim, is_food_order, is_drink_order, customer_order_number)
- **Customers**: Customer dimension table with measures (customers, count_lifetime_orders, lifetime_spend_pretax, lifetime_spend) and dimensions (customer_name, customer_type, first_ordered_at, last_ordered_at)
- **Products**: Product dimension table with all dimensions (product_name, product_type, product_description, is_food_item, is_drink_item, product_price)

## Example Usage

```python
from cubano_jaffle_shop import Orders, Customers, Products

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

This workspace is configured as a workspace member in the root pyproject.toml, alongside the `src/cubano` library. Both share a single uv.lock file.

## Running Tests

### Quick Mock Tests (Default)

Run fast mock tests without warehouse connection:

```bash
uv run pytest
```

Mock tests complete in < 1 second and validate query builder logic.

### Integration Tests (Warehouse Required)

Run integration tests against real Snowflake warehouse:

```bash
# Set credentials (one-time setup)
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=your_warehouse
export SNOWFLAKE_DATABASE=JAFFLE_SHOP

# Run warehouse tests
uv run pytest -m warehouse -v
```

Alternatively, create `.env` file:

```bash
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=JAFFLE_SHOP
```

### Parallel Execution

Run tests in parallel with pytest-xdist:

```bash
uv run pytest -m warehouse -n auto
```

Each worker runs in isolated schema (e.g., `cubano_test_gw0`, `cubano_test_gw1`).

### All Tests (Mock + Warehouse)

Run complete test suite:

```bash
uv run pytest -m "mock or warehouse" -v
```

## Test Markers

- `@pytest.mark.mock`: Fast tests using MockEngine (no credentials)
- `@pytest.mark.warehouse`: Integration tests against real warehouse (requires credentials)
- `@pytest.mark.snowflake`: Snowflake-specific tests
- `@pytest.mark.databricks`: Databricks-specific tests

## CI Behavior

GitHub Actions runs full suite (mock + warehouse) on every push using repository secrets for credentials.

## Reference

See dbt-jaffle-shop semantic model definitions in `dbt-jaffle-shop/models/marts/`:
- orders.yml
- customers.yml
- products.yml
