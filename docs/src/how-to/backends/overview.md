# How to choose and configure a backend

Semolina supports multiple data warehouse backends:

- **Snowflake** -- via `SnowflakeEngine` (install with `semolina[snowflake]`)
- **Databricks** -- via `DatabricksEngine` (install with `semolina[databricks]`)

The query API is identical for both -- only the engine you register changes.

## Register an engine

Swapping backends is a one-line change -- replace the registered engine:

=== "Snowflake"

    ```python
    from semolina import register
    from semolina.engines.snowflake import (
        SnowflakeEngine,
    )

    register(
        "default",
        SnowflakeEngine(
            account="xy12345.us-east-1",
            user="myuser",
            password="mypassword",
        ),
    )
    ```

=== "Databricks"

    ```python
    from semolina import register
    from semolina.engines.databricks import (
        DatabricksEngine,
    )

    register(
        "default",
        DatabricksEngine(
            server_hostname="...",
            http_path="/sql/1.0/warehouses/abc123",
            access_token="dapi...",
        ),
    )
    ```

Once registered, query code is identical regardless of backend:

```python
from semolina import SemanticView, Metric, Dimension


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    country = Dimension()


results = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)
```

## Test locally without a warehouse

Use `MockEngine` during development. It accepts fixture data and returns it on `.execute()`,
so you can test query logic without any warehouse connection:

```python
from semolina import register
from semolina.engines.mock import MockEngine

engine = MockEngine()
engine.load(
    "sales",
    [
        {"revenue": 1000, "country": "US"},
        {"revenue": 2000, "country": "CA"},
    ],
)
register("default", engine)
```

## See also

- [Snowflake](snowflake.md) -- connection setup and credentials for Snowflake
- [Databricks](databricks.md) -- connection setup and credentials for Databricks
- [What is a semantic view?](../../explanation/semantic-views.md) -- background on semantic views in each warehouse
