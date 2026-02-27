# Semolina

**Semolina: the ORM for your Semantic Layer.** Typed models,
IDE autocomplete, and one API for Snowflake and Databricks.

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **Get started in 5 minutes**

    ---
    Install Semolina and write your first query.

    [:octicons-arrow-right-24: Tutorials](tutorials/installation.md)

-   :material-database:{ .lg .middle } **Define models**

    ---
    Map `Metric` and `Dimension` fields to your warehouse semantic views.

    [:octicons-arrow-right-24: Defining Models](how-to/models.md)

-   :material-filter:{ .lg .middle } **Build queries**

    ---
    Chain `.metrics()`, `.dimensions()`, `.where()`, `.order_by()`, `.limit()`.

    [:octicons-arrow-right-24: Building Queries](how-to/queries.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---
    Full API documentation for every module.

    [:octicons-arrow-right-24: Reference](reference/semolina/fields.md)

</div>

## Quick example

```python
from semolina import (
    SemanticView,
    Metric,
    Dimension,
    register,
)
from semolina.engines.snowflake import (
    SnowflakeEngine,
)


class Sales(SemanticView, view="sales"):
    revenue = Metric()
    country = Dimension()


register(
    "default",
    SnowflakeEngine(
        account="...",  # your account
        user="...",
        password="...",
    ),
)

query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .limit(10)
)

for row in query.execute():
    print(row.country, row.revenue)
```

Write the query once. Swap `SnowflakeEngine` for `DatabricksEngine` and the same code runs on Databricks.
