# How to connect to Databricks

Set up `DatabricksEngine` to run Cubano queries against Databricks metric views.

## Install the Databricks extra

```bash
pip install cubano[databricks]
# or
uv add "cubano[databricks]"
```

The Databricks connector is an optional extra. Importing `DatabricksEngine` without it
installed raises `ImportError` with a helpful install message.

## Configure connection parameters

`DatabricksEngine` accepts keyword arguments that are passed directly to
`databricks.sql.connect()`:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `server_hostname` | `str` | Yes | Databricks workspace hostname (e.g. `workspace.cloud.databricks.com`) |
| `http_path` | `str` | Yes | SQL warehouse HTTP path (e.g. `/sql/1.0/warehouses/{warehouse_id}`) |
| `access_token` | `str` | Yes | Personal access token starting with `dapi` |
| `catalog` | `str` | No | Unity Catalog name (default: workspace default catalog) |
| `schema` | `str` | No | Default schema |

```python
from cubano import register
from cubano.engines.databricks import DatabricksEngine

engine = DatabricksEngine(
    server_hostname="workspace.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123",
    access_token="dapi...",
)
register("default", engine)
```

!!! note "Connection timing"
    `DatabricksEngine` does **not** connect at initialisation time. The connection is
    created per `.execute()` call and closed automatically via context manager even on errors.

## Load credentials from environment variables

Use `DatabricksCredentials` to load connection parameters from environment variables
or config files instead of hardcoding them:

```python
from cubano import register
from cubano.engines.databricks import DatabricksEngine
from cubano.testing.credentials import DatabricksCredentials

creds = DatabricksCredentials.load()
engine = DatabricksEngine(
    server_hostname=creds.server_hostname,
    http_path=creds.http_path,
    access_token=creds.access_token.get_secret_value(),
)
register("default", engine)
```

`DatabricksCredentials.load()` tries each source in order:

1. `DATABRICKS_*` environment variables
2. `.env` file in the current directory (or path from `CUBANO_ENV_FILE` env var)
3. `[databricks]` section in `.cubano.toml` or `~/.config/cubano/config.toml`
4. Raises `CredentialError` if all sources fail

### Environment variable names

| Env var | Credentials field |
|---------|------------------|
| `DATABRICKS_SERVER_HOSTNAME` | `server_hostname` |
| `DATABRICKS_HTTP_PATH` | `http_path` |
| `DATABRICKS_ACCESS_TOKEN` | `access_token` |
| `DATABRICKS_CATALOG` | `catalog` (optional, default: `main`) |

### Example `.env` file

```dotenv
DATABRICKS_SERVER_HOSTNAME=workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/abc123
DATABRICKS_ACCESS_TOKEN=dapi...
```

## Use Unity Catalog three-part names

Databricks uses [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html)
for three-level namespace: `catalog.schema.view`. Pass a three-part `view=` name in your model:

```python
from cubano import SemanticView, Metric, Dimension


class Sales(SemanticView, view="main.analytics.sales"):
    revenue = Metric()
    country = Dimension()
```

Each part is quoted separately with backticks in generated SQL:

```sql
SELECT MEASURE(`revenue`), `country`
FROM `main`.`analytics`.`sales`
GROUP BY ALL
```

## Run a query

Once the engine is registered, the query API works the same as any other backend:

```python
results = (
    Sales.query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .execute()
)
for row in results:
    print(row.country, row.revenue)
```

## Inspect generated SQL

Databricks SQL uses `MEASURE()` for metrics and backtick-quoted identifiers:

```sql
SELECT MEASURE(`revenue`), `country`
FROM `sales`
GROUP BY ALL
```

!!! note "Backend-specific SQL"
    Inspect the generated SQL without executing it:

    ```python
    engine = DatabricksEngine(...)
    sql = engine.to_sql(
        Sales.query()
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
    )
    print(sql)
    ```

## Review codegen output

When you run `cubano codegen --backend databricks`, Cubano generates a metric view
YAML definition for each model:

```yaml
sales:
  base_table: # TODO: Replace with schema.table_name
  dimensions:
    - country:
        expr: country
  measures:
    - revenue:
        expr: SUM(revenue)  # TODO: Replace SUM with correct aggregation
```

!!! note "Aggregation placeholder"
    Cubano's `Metric()` field does not capture the aggregation function type (SUM, AVG, COUNT, etc.).
    The generated YAML uses `SUM()` as a placeholder. Replace it with the correct function
    for each metric before deploying to Databricks.

See [Codegen CLI](../codegen.md) for full usage.

## See also

- [Backend overview](overview.md) -- compare Snowflake and Databricks side by side
- [Snowflake](snowflake.md) -- connect to Snowflake semantic views
- [Warehouse testing](../warehouse-testing.md) -- snapshot-based testing with syrupy
