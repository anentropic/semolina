# How to generate Semolina model classes from warehouse views

Already have a Snowflake semantic view or Databricks metric view set up? `semolina codegen`
introspects it and prints a Python model class to stdout. You can drop that output straight
into your codebase.

## Run codegen

```bash
semolina codegen my_schema.sales_view --backend snowflake
```

That connects to your warehouse, reads the view's column metadata, and prints a ready-to-use
`SemanticView` subclass.

## Introspect multiple views at once

Pass multiple view names in a single call:

```bash
semolina codegen schema.sales_view schema.orders_view --backend databricks
```

All classes appear in one output block with a single shared imports section.

## Pipe output to a file

```bash
semolina codegen my_schema.sales_view --backend snowflake > models.py
```

There is no `--output` flag; redirect stdout as you would with any CLI tool.

## Choose a backend

Use `--backend` (or `-b`):

| Value | Warehouse | Introspects via |
|-------|-----------|-----------------|
| `snowflake` | Snowflake Semantic Views | `SHOW COLUMNS IN VIEW` |
| `databricks` | Databricks Metric Views | `DESCRIBE TABLE EXTENDED AS JSON` |

Credentials come from the same environment variables as the query engine
(for example, `SNOWFLAKE_ACCOUNT` for Snowflake).
See [Snowflake connection](backends/snowflake.md) or [Databricks connection](backends/databricks.md)
for the full list.

## Understand the generated output

=== "Snowflake"

    Given this semantic view in your warehouse:

    ```sql
    CREATE OR REPLACE SEMANTIC VIEW analytics.sales_view
      TABLES (
        s AS source_table PRIMARY KEY (id)
      )
      DIMENSIONS (
        s.country AS country,
        s.unit_price AS unit_price
      )
      METRICS (
        s.revenue AS SUM(revenue)
      )
    ;
    ```

    Running:

    ```bash
    semolina codegen analytics.sales_view --backend snowflake
    ```

    Produces:

    ```python
    from semolina import SemanticView, Metric, Dimension, Fact


    class SalesView(SemanticView, view="analytics.sales_view"):
        revenue = Metric[int]()
        country = Dimension[str]()
        unit_price = Fact[float]()
    ```

=== "Databricks"

    Given this metric view in your warehouse:

    ```sql
    CREATE OR REPLACE VIEW main.analytics.orders_view
      WITH METRICS
      LANGUAGE YAML
      AS $$
        version: 1.1
        source: source_table
        dimensions:
          - name: region
            expr: region
        measures:
          - name: total_orders
            expr: COUNT(*)
      $$;
    ```

    Running:

    ```bash
    semolina codegen main.analytics.orders_view --backend databricks
    ```

    Produces:

    ```python
    from semolina import SemanticView, Metric, Dimension, Fact


    class OrdersView(
        SemanticView, view="main.analytics.orders_view"
    ):
        total_orders = Metric[int]()
        region = Dimension[str]()
    ```

Databricks has no native Fact type, so all non-measure fields map to `Dimension()`.

## Understand field type mapping

| Warehouse classification | Generated field type |
|--------------------------|---------------------|
| Metric / Measure | `Metric[T]()` |
| Dimension | `Dimension[T]()` |
| Fact (Snowflake only) | `Fact[T]()` |

## Handle TODO comments

When a field's SQL type has no clean Python equivalent (GEOGRAPHY, VARIANT, ARRAY, MAP,
STRUCT), codegen emits a TODO comment rather than guessing:

```python
# TODO: no clean Python type for GEOGRAPHY field "territory"
territory = Dimension()
```

Review these after generation and handle them manually.

## Use a custom backend

`--backend` also accepts a dotted Python import path for custom `Engine` subclasses:

```bash
semolina codegen my_schema.my_view --backend my_package.backends.MyCustomEngine
```

The class must implement `introspect(view_name: str) -> IntrospectedView`.
It is instantiated with no arguments; credentials are the class's responsibility.

## Exit codes

`semolina codegen` uses distinct exit codes so scripts can handle each failure mode separately:

| Exit code | Meaning |
|-----------|---------|
| `0` | Success — model class written to stdout |
| `1` | Unexpected error (see stderr for details) |
| `2` | Invalid `--backend` specifier — value provided but not recognised |
| `3` | View not found — the warehouse has no semantic view with that name |
| `4` | Connection failure — credentials missing or authentication rejected |

> **Note:** Exit code 2 is also emitted by the CLI argument parser when `--backend` is
> omitted entirely. Both cases mean "the backend could not be resolved."

## Override the SQL column name with source=

By default, Semolina maps Python field names to SQL column names using each dialect's
identifier casing rules (Snowflake uppercases unquoted identifiers; Databricks lowercases them).
For a field `order_id`, Snowflake resolves `ORDER_ID` automatically.

If your warehouse stores a column with non-default casing — for example, a quoted
lowercase column `"order_id"` in Snowflake — you can override the SQL column name
with `source=`:

```python
class Orders(SemanticView, view="orders"):
    order_id = Metric[int](
        source="order_id"
    )  # maps to quoted "order_id", not "ORDER_ID"
```

`semolina codegen` emits `source=` automatically when introspection detects that a column
uses non-default casing.

## See also

- [Defining models](models.md) -- model class structure and field types
- [Snowflake connection](backends/snowflake.md) -- credential setup for Snowflake
- [Databricks connection](backends/databricks.md) -- credential setup for Databricks
