# Bug: `DatabricksConfig` silently drops `catalog` and `schema_` — default namespace never reaches the ADBC connection

## Summary

`DatabricksConfig` accepts `catalog` and `schema_` (= `schema`) fields, but
`DatabricksConfig.to_adbc_kwargs()` only emits a bare `databricks://…` URI and
**never propagates them to the driver**. As a result the ADBC connection has no
default catalog/schema, and any unqualified table/view reference fails:

```
TABLE_OR_VIEW_NOT_FOUND: `sales_view` cannot be found.
Verify the current_schema() output, or qualify the name with the correct schema and catalog.
```

The fields look honored (they're declared, documented, and populated from
`.toml`/env) but are silently inert for Databricks — a config that lies. Snowflake
and Trino both wire their equivalents through (`SnowflakeConfig` →
`adbc.snowflake.sql.schema`; `TrinoConfig` → `catalog`/`schema` kwargs), so this is
a Databricks-specific gap.

## Severity / impact

Medium–high. Any caller relying on a default namespace (i.e. querying
`my_view` instead of fully-qualifying `catalog.schema.my_view`) gets a hard
`TABLE_OR_VIEW_NOT_FOUND` at query time, with no hint that the config's
`catalog`/`schema` were ignored. Affects every Databricks query path.

## Environment

- adbc-poolhouse **1.2.0**
- adbc-driver-manager 1.10.0
- Databricks ADBC driver: the Foundry manifest driver that `databricks://` resolves
  to (loaded by name via `adbc_driver_manager`; no `adbc_driver_databricks` PyPI pkg)
- Python 3.14

## Reproduction

**Unit-level (no warehouse needed) — shows the drop directly:**

```python
from adbc_poolhouse import DatabricksConfig
from pydantic import SecretStr

cfg = DatabricksConfig(
    host="example.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/abc123",
    token=SecretStr("dapiXXXX"),
    catalog="my_catalog",
    schema="my_schema",  # populates schema_ via alias
)
print(cfg.to_adbc_kwargs())
# {'uri': 'databricks://token:dapiXXXX@example.cloud.databricks.com:443/sql/1.0/warehouses/abc123'}
#   -> note: no catalog, no schema anywhere in the kwargs
```

**End-to-end (live warehouse):** build a pool from the config above, then run any
query against an *unqualified* view that lives in `my_catalog.my_schema` →
`TABLE_OR_VIEW_NOT_FOUND`.

## Root cause

`adbc_poolhouse/_databricks_config.py` — `to_adbc_kwargs()` (decomposed mode)
builds the URI from `host`/`http_path`/`token` only and returns `{"uri": uri}`.
`self.catalog` (field at `_databricks_config.py:64`) and `self.schema_`
(`:67`) are never read.

```python
# current (decomposed mode)
encoded_token = quote(self.token.get_secret_value(), safe="")
uri = f"databricks://token:{encoded_token}@{self.host}:443{self.http_path}"
return {"uri": uri}
```

## Why the ADBC capability matrix is a red herring

The arrow-adbc Databricks driver docs list "specify target catalog/schema" as
unsupported *ADBC connection options*. But the **underlying Databricks Go SQL
driver parses `?catalog=…&schema=…` from the DSN** (and offers
`WithInitialNamespace(catalog, schema)`). So the namespace can be set via the DSN
query string even though the ADBC-level option isn't exposed.

- DSN params: https://docs.databricks.com/aws/en/dev-tools/go-sql-driver (Optional parameters → `catalog`, `schema`)
- ADBC driver page: https://docs.adbc-drivers.org/drivers/databricks/

## Expected behavior

`catalog`/`schema_`, when set, become the connection's default namespace so
unqualified identifiers resolve — matching `SnowflakeConfig`
(`adbc.snowflake.sql.schema`, `_snowflake_config.py:198`) and `TrinoConfig`
(`catalog`/`schema` kwargs, `_trino_config.py:94,96`).

## Proposed fix

In **decomposed mode only**, append URL-encoded `catalog`/`schema` to the DSN
query string. Leave **URI mode untouched** (a user-supplied URI may already carry
its own params). Emit no query string when both are `None`.

```python
from urllib.parse import quote, urlencode

# decomposed mode
encoded_token = quote(self.token.get_secret_value(), safe="")
uri = f"databricks://token:{encoded_token}@{self.host}:443{self.http_path}"
params = {}
if self.catalog is not None:
    params["catalog"] = self.catalog
if self.schema_ is not None:
    params["schema"] = self.schema_
if params:
    uri = f"{uri}?{urlencode(params)}"
return {"uri": uri}
```

### Tests to add

- `to_adbc_kwargs()` URI ends with `?catalog=my_catalog&schema=my_schema` when both set.
- Only `catalog` set → `?catalog=…` (no `schema`); only `schema` → `?schema=…`.
- Both `None` → URI has no `?` query string (current behavior preserved).
- Values needing escaping (e.g. a schema with reserved chars) are percent-encoded.
- URI mode (`uri=` provided) is returned verbatim — not mutated.
- Token stays inside the URI built in `to_adbc_kwargs`; never logged (keep `SecretStr`).

## Downstream

Consumed by the Semolina project (semantic-layer ORM), Phase 45 / req DBX-02. Once
released, Semolina bumps its `adbc-poolhouse` pin and records Databricks
integration cassettes against unqualified view names. Pairs with a separate
Semolina-side fix (DBX-01) for the Databricks ADBC driver's lack of bind-parameter
support; this issue is only the catalog/schema half.
