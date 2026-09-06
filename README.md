# Semolina

[ [Docs](https://anentropic.github.io/semolina/) ]

The ORM for your Semantic Layer.

Typed models in Python, supporting IDE autocomplete, and a Django-like fluent query interface for the semantic layer of your data warehouse backend.

```sh
pip install semolina
pip install "semolina[snowflake]"
pip install "semolina[databricks]"
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

Semolina needs an engine to talk to your warehouse. An engine owns one connection pool and the dialect for a backend. Build one with `create_engine` and register it before running any queries:

```python
from semolina import create_engine, register

engine = create_engine(
    "default"
)  # reads [connections.default] from .semolina.toml
register("default", engine)
```

Use `Model.query()` to start building. Chain `.metrics()` and `.dimensions()` to select the fields you want, then call `.execute()`:

```python
query = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
)
```

`.execute()` returns a `SemolinaCursor`. Use it as a context manager so the pooled connection is released when you are done, and call `.fetchall_rows()` to get `Row` objects that support both attribute and dict-style access:

```python
with query.execute() as cursor:
    for row in cursor.fetchall_rows():
        print(row.country, row.revenue)  # attribute access
        print(row["country"])  # dict-style access
```

You should see output like:

```output
CA 2000
CA
US 1500
US
```
