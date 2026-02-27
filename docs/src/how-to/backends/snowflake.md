# How to connect to Snowflake

Set up `SnowflakeEngine` to run Semolina queries against Snowflake semantic views.

## Install the Snowflake extra

```bash
pip install semolina[snowflake]
# or
uv add "semolina[snowflake]"
```

The Snowflake connector is an optional extra. Importing `SnowflakeEngine` without it installed
raises `ImportError` with a helpful install message.

## Configure connection parameters

`SnowflakeEngine` accepts keyword arguments that are passed directly to
`snowflake.connector.connect()`:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account` | `str` | Yes | Account identifier with region suffix (e.g. `xy12345.us-east-1`) |
| `user` | `str` | Yes | Snowflake username |
| `password` | `str` | Yes | Snowflake password |
| `warehouse` | `str` | No | Compute warehouse name |
| `database` | `str` | No | Default database |
| `schema` | `str` | No | Default schema |
| `role` | `str` | No | Role to activate for the session |
| `authenticator` | `str` | No | Authentication method (default: `snowflake` username/password) |

```python
from semolina import register
from semolina.engines.snowflake import SnowflakeEngine

engine = SnowflakeEngine(
    account="xy12345.us-east-1",
    user="myuser",
    password="mypassword",
    warehouse="compute_wh",
    database="analytics",
    schema="public",
)
register("default", engine)
```

!!! note "Connection timing"
    `SnowflakeEngine` does **not** connect at initialisation time. The connection is
    created per `.execute()` call and closed automatically via context manager even on errors.

## Load credentials from environment variables

Use `SnowflakeCredentials` to load connection parameters from environment variables
or config files instead of hardcoding them:

```python
from semolina import register
from semolina.engines.snowflake import SnowflakeEngine
from semolina.testing.credentials import (
    SnowflakeCredentials,
)

creds = SnowflakeCredentials.load()
engine = SnowflakeEngine(
    account=creds.account,
    user=creds.user,
    password=creds.password.get_secret_value(),
    warehouse=creds.warehouse,
    database=creds.database,
    role=creds.role,
)
register("default", engine)
```

`SnowflakeCredentials.load()` tries each source in order:

1. `SNOWFLAKE_*` environment variables
2. `.env` file in the current directory (or path from `SEMOLINA_ENV_FILE` env var)
3. `[snowflake]` section in `.semolina.toml` or `~/.config/semolina/config.toml`
4. Raises `CredentialError` if all sources fail

### Environment variable names

| Env var | Credentials field |
|---------|------------------|
| `SNOWFLAKE_ACCOUNT` | `account` |
| `SNOWFLAKE_USER` | `user` |
| `SNOWFLAKE_PASSWORD` | `password` |
| `SNOWFLAKE_WAREHOUSE` | `warehouse` |
| `SNOWFLAKE_DATABASE` | `database` |
| `SNOWFLAKE_ROLE` | `role` (optional) |

### Example `.env` file

```dotenv
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser
SNOWFLAKE_PASSWORD=mypassword
SNOWFLAKE_WAREHOUSE=compute_wh
SNOWFLAKE_DATABASE=analytics
```

## Run a query

Once the engine is registered, the query API works the same as any other backend:

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
for row in results:
    print(row.country, row.revenue)
```

## Inspect generated SQL

Snowflake SQL uses `AGG()` for metrics and double-quoted identifiers:

```sql
SELECT AGG("revenue"), "country"
FROM "sales"
GROUP BY ALL
```

!!! note "Backend-specific SQL"
    Inspect the generated SQL without executing it:

    ```python
    engine = SnowflakeEngine(...)
    sql = engine.to_sql(
        Sales.query()
        .metrics(Sales.revenue)
        .dimensions(Sales.country)
    )
    print(sql)
    ```

## Review codegen output

When you run `semolina codegen --backend snowflake`, Semolina generates a
`CREATE SEMANTIC VIEW` statement for each model:

```sql
CREATE OR REPLACE SEMANTIC VIEW sales
    -- TODO: Add TABLES (...) clause pointing to your source table(s)
    -- TODO: Add RELATIONSHIPS (...) clause if joining multiple tables
    DIMENSIONS (
        country = country
    )
    METRICS (
        revenue = AGG(revenue)
    )
;
```

See [Codegen CLI](../codegen.md) for full usage.

## See also

- [Backend overview](overview.md) -- compare Snowflake and Databricks side by side
- [Databricks](databricks.md) -- connect to Databricks metric views
- [Warehouse testing](../warehouse-testing.md) -- snapshot-based testing with syrupy
