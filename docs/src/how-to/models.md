# How to define models

Define a `SemanticView` subclass to map your warehouse's semantic view into a typed
Python class with IDE autocomplete and query safety.

## Create a model

Subclass `SemanticView` and pass the warehouse view name via `view=`:

```python
from semolina import SemanticView, Metric, Dimension, Fact


class Sales(SemanticView, view="sales"):
    revenue = Metric[float]()
    cost = Metric[float]()
    country = Dimension[str]()
    region = Dimension[str]()
    unit_price = Fact[float]()
```

The type parameter (`[float]`, `[str]`, etc.) is optional but recommended — it lets your
IDE infer the column's Python type when you access query results.

The `view=` parameter is **required** -- it identifies the semantic view in your warehouse.
Omitting it raises a `TypeError` at class creation time.

!!! tip "Views in non-default schemas"
    If your view lives in a specific schema, pass the
    schema-qualified name:

    ```python
    class Sales(
        SemanticView,
        view="analytics.sales",
    ):
        revenue = Metric[float]()
    ```

    For Databricks Unity Catalog, use three-part names:

    ```python
    class Sales(
        SemanticView,
        view="catalog.schema.sales",
    ):
        revenue = Metric[float]()
    ```

## Choose field types

Each field type corresponds to a role in your semantic view query:

| Field | Use for | Accepted by |
|-------|---------|-------------|
| `Metric` | Aggregated measures: revenue totals, counts, averages | `.metrics()` |
| `Dimension` | Categorical grouping: country, product category, date | `.dimensions()` |
| `Fact` | Raw event-level numeric columns (`unit_price`, `quantity`) — signals semantic intent vs a categorical `Dimension` | `.dimensions()` |

### Metric fields

A `Metric` represents an aggregatable measure. In generated SQL, metrics are wrapped
in the backend's aggregation function:

```python
class Orders(SemanticView, view="orders"):
    total_revenue = Metric[float]()
    order_count = Metric[int]()
```

=== "Snowflake"

    ```sql
    SELECT AGG("total_revenue"), AGG("order_count")
    FROM "orders"
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`total_revenue`), MEASURE(`order_count`)
    FROM `orders`
    ```

Passing a `Metric` to `.dimensions()` raises a `TypeError`. Pass it to `.metrics()` instead.

### Dimension fields

A `Dimension` represents a categorical attribute used for grouping:

```python
class Orders(SemanticView, view="orders"):
    country = Dimension[str]()
    product_category = Dimension[str]()
```

=== "Snowflake"

    ```sql
    SELECT "country", "product_category"
    FROM "orders"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT `country`, `product_category`
    FROM `orders`
    GROUP BY ALL
    ```

### Fact fields

A `Fact` represents a raw numeric value that has not been pre-aggregated.

**Snowflake users:** Snowflake's `CREATE SEMANTIC VIEW` does not have a separate `FACTS`
clause — fact-like numeric columns are declared in `DIMENSIONS`. Snowflake may return
`kind=FACT` for some columns when you introspect with `SHOW COLUMNS IN SEMANTIC VIEW`,
in which case `semolina codegen` will emit `Fact()` automatically. For hand-written models,
use `Fact` for raw numeric columns you want to distinguish semantically from categorical
dimensions.

**Databricks users:** Databricks metric views have no native fact concept. Every
non-aggregate field is a `dimension:` in the metric view YAML. Use `Fact` in your Semolina
model for raw numeric columns you want to distinguish semantically from categorical grouping
attributes — the warehouse won't enforce the distinction, but your teammates and future
readers will see the intent.

At query time, `Fact` and `Dimension` produce identical SQL (`SELECT "col" FROM ...
GROUP BY ALL`). The distinction is semantic, not a difference in execution.

Default to `Dimension`. Use `Fact` as an intentional opt-in for two situations:

1. **Semantic precision** — the column is a raw event-level numeric (`unit_price`,
   `quantity`, `line_amount`) you want to distinguish from categorical attributes like
   `country` or `product_category`.
2. **Snowflake alignment** — `semolina codegen` introspected the column as `kind=FACT` from
   your warehouse. Match that designation in Semolina.

```python
class Orders(SemanticView, view="orders"):
    # raw price column, not aggregated
    unit_price = Fact[float]()
    quantity = Fact[int]()
    # categorical grouping attribute
    country = Dimension[str]()
    product_category = Dimension[str]()
```

=== "Snowflake"

    ```sql
    SELECT "unit_price", "quantity"
    FROM "orders"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT `unit_price`, `quantity`
    FROM `orders`
    GROUP BY ALL
    ```

## Type the subscript

Annotate each field with the Python type of the underlying warehouse column.
The subscript is optional but recommended — it lets your IDE infer the type when you access
query results:

```python
revenue = Metric[float]()
order_id = Metric[int]()
country = Dimension[str]()
# date column; requires: import datetime
created_at = Dimension[datetime.date]()
```

When the column type has no clean Python equivalent (GEOGRAPHY, VARIANT, ARRAY), use
`Metric[Any]()` and import `Any` from `typing`. The `semolina codegen` command emits a
`# TODO:` comment for these cases.

You can also omit the subscript entirely. `Metric()` is shorthand for `Metric[Any]()` —
valid Python, just without type narrowing.

## Put it together

Here is a complete model with all three field types:

```python
from semolina import SemanticView, Metric, Dimension, Fact


class Orders(SemanticView, view="orders"):
    """Order-level metrics and dimensions."""

    total_revenue = Metric[float]()
    order_count = Metric[int]()
    country = Dimension[str]()
    product_category = Dimension[str]()
    unit_price = Fact[float]()  # raw price, not aggregated
```

## Access field descriptors

Fields use Python's [descriptor protocol](https://docs.python.org/3/howto/descriptor.html).
Accessing `Orders.total_revenue` at the class level returns the `Metric` descriptor itself --
the same object you pass into query methods:

```python
# Class-level access: returns the descriptor
field = Orders.total_revenue
# <class 'semolina.fields.Metric'>
print(type(field))

# Pass directly into query methods
query = Orders.query().metrics(
    Orders.total_revenue,
    Orders.order_count,
)
```

Accessing a field on an **instance** raises `AttributeError`. Semolina models are never
instantiated -- the class is the query target.

## Model immutability

Models are frozen immediately after the class body executes. Attempting to modify a
model attribute after class creation raises `AttributeError`:

```python
class Sales(SemanticView, view="sales"):
    revenue = Metric[float]()


# AttributeError: Cannot modify after creation
Sales.revenue = Metric[float]()
```

This guarantee ensures models stay consistent across the lifecycle of a query.

## Add field docstrings for codegen

Docstrings assigned to field instances appear as comments in `semolina codegen` SQL output:

```python
class Orders(SemanticView, view="orders"):
    total_revenue = Metric[float]()
    total_revenue.__doc__ = "Sum of revenue, tax excluded"
```

See [Codegen CLI](codegen.md) for how docstrings appear in generated SQL.

## See also

- [Building queries](queries.md) -- use your model to build and execute queries
- [Filtering](filtering.md) -- filter queries with field operators
- [Generating models from warehouse views](codegen.md) -- codegen output uses typed subscripts
- [API reference: fields](../reference/semolina/fields.md) -- full Field class documentation
