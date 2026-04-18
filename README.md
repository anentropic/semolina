# Semolina

[ [Docs](https://anentropic.github.io/semolina/) ]

The ORM for your Semantic Layer.

Typed models in Python, supporting IDE autocomplete, and a Django-like fluent query interface for the semantic layer of your data warehouse backend.

```sh
pip install semolina
pip install semolina[snowflake]
pip install semolina[databricks]
```

A model maps to a semantic view in your warehouse.

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

Semolina needs a connection pool to talk to your warehouse. Register one before running any queries:

```python
from semolina import register, pool_from_config

pool, dialect = pool_from_config()  # reads .semolina.toml
register("default", pool, dialect=dialect)
```

Use `Model.query()` to start building. Chain `.metrics()` and `.dimensions()` to select the fields you want, then call `.execute()`:

```python
cursor = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)
```

`.execute()` returns a `SemolinaCursor`. Call `.fetchall_rows()` to get `Row` objects that support both attribute and dict-style access:

```python
rows = cursor.fetchall_rows()
for row in rows:
    print(row.country, row.revenue)  # attribute access
    print(row["country"])  # dict-style access
```

You should see output like:

```output
US 1000
US
CA 2000
CA
US 500
US
```
