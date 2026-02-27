# Your first query

In this tutorial, you'll define a model, register an engine, build a query, and
read the results. By the end, you'll have a working Semolina query you can adapt
for your own semantic views.

**Prerequisites:** Semolina installed ([Installation](installation.md)).

## 1. Define a model

A model maps to a semantic view in your warehouse. Create a file called
`demo.py` and add this code:

```python
from semolina import (
    SemanticView,
    Metric,
    Dimension,
)


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
```

`view="sales"` is the name of the semantic view in your warehouse. `Metric`
fields are aggregatable measures (revenue, cost). `Dimension` fields are
categories for grouping (country, region).

In your warehouse, this model maps to a definition like:

=== "Snowflake"

    ```sql
    CREATE OR REPLACE SEMANTIC VIEW sales
      TABLES (
        s AS source_table PRIMARY KEY (id)
      )
      DIMENSIONS (
        s.country AS country,
        s.region AS region
      )
      METRICS (
        s.revenue AS SUM(revenue),
        s.cost AS SUM(cost)
      )
    ;
    ```

=== "Databricks"

    ```sql
    CREATE OR REPLACE VIEW sales
      WITH METRICS
      LANGUAGE YAML
      AS $$
        version: 1.1
        source: source_table
        dimensions:
          - name: country
            expr: country
          - name: region
            expr: region
        measures:
          - name: revenue
            expr: SUM(revenue)
          - name: cost
            expr: SUM(cost)
      $$;
    ```

## 2. Register an engine

Semolina needs an engine to connect to your warehouse. Register one
before running any queries:

=== "Snowflake"

    ```python
    from semolina import register
    from semolina.engines.snowflake import (
        SnowflakeEngine,
    )

    register(
        "default",
        SnowflakeEngine(
            account="...",  # your account
            user="...",
            password="...",
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
            http_path="...",
            access_token="...",
        ),
    )
    ```

See [Backends](../how-to/backends/overview.md) for full
connection details and credential loading.

!!! tip "No warehouse? Use MockEngine"
    If you want to follow along without a warehouse
    connection, use `MockEngine` with fixture data:

    ```python
    from semolina import register
    from semolina.engines.mock import MockEngine

    engine = MockEngine()
    engine.load(
        "sales",
        [
            {
                "revenue": 1000,
                "cost": 100,
                "country": "US",
                "region": "West",
            },
            {
                "revenue": 2000,
                "cost": 200,
                "country": "CA",
                "region": "West",
            },
            {
                "revenue": 500,
                "cost": 50,
                "country": "US",
                "region": "East",
            },
        ],
    )
    register("default", engine)
    ```

## 3. Build and run a query

Use `Model.query()` to start building. Chain `.metrics()` and `.dimensions()`
to select the fields you want, then call `.execute()`:

```python
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)
```

Each chained method returns a new query object, so queries are immutable and
reusable.

## 4. Read the results

Iterate over the results. Each row supports both attribute and dict-style access:

```python
for row in results:
    print(row.country, row.revenue)  # attribute access
    print(row["country"])  # dict-style access
```

You should see output like:

```
US 1000
US
CA 2000
CA
US 500
US
```

## Complete example

Here is a self-contained demo using `MockEngine`. To run against a real
warehouse, replace the engine registration with your connection (see step 2).

Paste it into `demo.py` and run `python demo.py`:

```python
from semolina import (
    SemanticView,
    Metric,
    Dimension,
    register,
)
from semolina.engines.mock import MockEngine


# 1. Define model
class Sales(SemanticView, view="sales"):
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


# 2. Register engine with fixture data
engine = MockEngine()
engine.load(
    "sales",
    [
        {
            "revenue": 1000,
            "cost": 100,
            "country": "US",
            "region": "West",
        },
        {
            "revenue": 2000,
            "cost": 200,
            "country": "CA",
            "region": "West",
        },
        {
            "revenue": 500,
            "cost": 50,
            "country": "US",
            "region": "East",
        },
    ],
)
register("default", engine)

# 3. Build and execute query
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)

# 4. Use results
for row in results:
    print(row.country, row.revenue)
```

You should see:

```
US 1000
CA 2000
US 500
```

## See also

<div class="grid cards" markdown>

- :material-table: **[Defining Models](../how-to/models.md)**

    Field types, `SemanticView` parameters, immutability.

- :material-magnify: **[Building Queries](../how-to/queries.md)**

    All 8 query methods with examples.

- :material-filter: **[Filtering](../how-to/filtering.md)**

    Field operators, named methods, AND/OR/NOT composition.

</div>
