# Phase 27: TOML Configuration & Real Pools - Research

**Researched:** 2026-03-17
**Domain:** TOML config parsing, adbc-poolhouse config classes, pool_from_config factory
**Confidence:** HIGH

## Summary

Phase 27 delivers `.semolina.toml` configuration loading and a `pool_from_config()` factory that creates real adbc-poolhouse pools from TOML config. The user decision is to use a flat `[connections.name]` format with a `type` field, parse with `tomllib` directly (no pydantic-settings TomlConfigSettingsSource), and pass the parsed dict to adbc-poolhouse config classes (`SnowflakeConfig`, `DatabricksConfig`) directly.

The critical technical finding is that adbc-poolhouse config classes (v1.2.0) are pydantic-settings `BaseSettings` subclasses, so they accept keyword arguments directly from a dict. The `type` field in the TOML maps to Semolina's `Dialect` StrEnum, which determines which adbc-poolhouse config class to instantiate. The config class is then passed to `adbc_poolhouse.create_pool()` which returns a `sqlalchemy.pool.QueuePool`. The pool's `.connect()` method returns an ADBC DBAPI connection with `.cursor()` -- matching the exact interface MockPool already exposes.

One key nuance: adbc-poolhouse's `SnowflakeConfig` uses `user` as the field name (matching Snowflake convention), while `DatabricksConfig` uses `host`, `http_path`, and `token` (not `access_token` or `server_hostname`). The TOML field names must match the adbc-poolhouse config class field names, since we pass dicts directly. The existing `.semolina.toml.example` format does NOT match the new `[connections.name]` format and needs to be updated.

**Primary recommendation:** Create `src/semolina/config.py` with a `pool_from_config()` function that: (1) reads `.semolina.toml` with `tomllib`, (2) extracts the named connection section from `[connections.X]`, (3) pops the `type` field to determine dialect, (4) instantiates the corresponding adbc-poolhouse config class with remaining fields, (5) calls `create_pool(config)` to get the pool, (6) returns `(pool, Dialect)` tuple.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **TOML format:** `[connections.name]` sections with `type = "snowflake"` field (flat, NOT nested sub-tables)
- **type field:** Maps directly to `Dialect` enum values
- **Multiple connections:** Same type supported (e.g. two snowflake connections)
- **Config loading:** No pydantic-settings TomlConfigSettingsSource -- parse with `tomllib` directly in `pool_from_config`
- **Config classes:** No custom Semolina config wrapper classes -- use adbc-poolhouse configs (`SnowflakeConfig`, `DatabricksConfig`) as-is
- **pool_from_config API:** Returns `(pool, Dialect)` tuple -- ready to register
- **pool_from_config signature:** `pool_from_config(connection="default", config_path=".semolina.toml")`
- **adbc-poolhouse:** Core dependency (not optional extra)
- **pydantic-settings:** Transitive dependency via adbc-poolhouse (not added independently)

### Claude's Discretion
- Whether to add adbc-driver-snowflake / adbc-driver-flightsql as optional extras in this phase
- How to handle env var overrides for credentials (adbc-poolhouse configs have built-in env support via pydantic-settings)
- Whether existing `testing/credentials.py` coexists or gets updated
- Error handling for missing/invalid TOML sections

### Deferred Ideas (OUT OF SCOPE)
- Auto-registration (user still calls register() manually)
- Connection lifecycle management (pool cleanup, graceful shutdown)
- CLI integration with config
- Arrow-native fetch methods -- Phase 28
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | `.semolina.toml` connection sections have a backend sub-section determining config class | `type` field in `[connections.name]` maps to adbc-poolhouse config class via `_CONFIG_MAP` dispatch; `type` is popped before passing to config class constructor |
| CONF-02 | `.semolina.toml` sections load into adbc-poolhouse config classes via TomlSettingsSource | **Decision changed:** Direct `tomllib` parsing + dict unpacking into adbc-poolhouse config classes (NOT pydantic-settings TomlSettingsSource). Config classes accept kwargs directly since they are pydantic BaseSettings subclasses |
| CONF-03 | User can create a pool via `pool_from_config(connection="conn1")` with default `.semolina.toml` path | `pool_from_config(connection="default", config_path=".semolina.toml")` reads TOML, dispatches to config class, calls `create_pool(config)`, returns `(pool, Dialect)` tuple |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adbc-poolhouse | >=1.2.0 | Connection pool factory + typed config classes | Provides `create_pool(config)` returning SQLAlchemy QueuePool, typed `SnowflakeConfig`/`DatabricksConfig`, `close_pool()`. Same author as Semolina. |
| tomllib | stdlib (3.11+) | TOML file parsing | Python >=3.11 stdlib. No external dependency needed. |

### Transitive (via adbc-poolhouse)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| pydantic-settings | >=2.0.0 | Config class base (BaseSettings) | adbc-poolhouse configs extend BaseSettings. Gets env var loading for free. |
| sqlalchemy | >=2.0.0 | QueuePool implementation | `create_pool()` returns `sqlalchemy.pool.QueuePool`. Only pool module used. |
| adbc-driver-manager | >=1.8.0 | ADBC driver loading | Transitive via adbc-poolhouse. |

### Optional Extras (ADBC drivers)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| adbc-driver-snowflake | >=1.0.0 | Snowflake ADBC driver | Required when `type = "snowflake"` connection is used |
| adbc-driver-flightsql | >=1.0.0 | Flight SQL driver (Databricks alt) | Required when using FlightSQL config for Databricks |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tomllib direct parsing | pydantic-settings TomlConfigSettingsSource | User decision: tomllib is simpler, no extra config class hierarchy needed. TomlConfigSettingsSource adds complexity for scoped sections. |
| adbc-poolhouse configs as-is | Custom Semolina wrapper classes | User decision: no wrappers. Fewer classes to maintain, direct dict unpacking works fine. |

**Installation (pyproject.toml change):**
```toml
[project]
dependencies = [
    "adbc-poolhouse>=1.2.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
snowflake = [
    "adbc-poolhouse[snowflake]",
]
databricks = [
    # Databricks uses Foundry-distributed driver, not PyPI
    # User must install via ADBC Driver Foundry
]
```

## Architecture Patterns

### Recommended Project Structure Changes

```
src/semolina/
    config.py               # NEW: pool_from_config(), _CONFIG_MAP dispatch
    __init__.py             # MODIFIED: add pool_from_config export
    pool.py                 # UNCHANGED (MockPool stays)
    registry.py             # UNCHANGED (register() stays)
    dialect.py              # UNCHANGED (Dialect StrEnum stays)
```

### Pattern 1: Type-Dispatch Config Loading

**What:** The `type` field in a TOML connection section determines which adbc-poolhouse config class to instantiate. A `_CONFIG_MAP` dict maps type strings to config classes.

**When to use:** In `pool_from_config()` to dispatch from TOML to the correct config class.

**Example:**
```python
# src/semolina/config.py
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from adbc_poolhouse import (
    DatabricksConfig,
    SnowflakeConfig,
    create_pool,
)
from adbc_poolhouse._base_config import WarehouseConfig

from .dialect import Dialect

# Maps TOML type field to (config_class, dialect)
_CONFIG_MAP: dict[str, tuple[type[WarehouseConfig], Dialect]] = {
    "snowflake": (SnowflakeConfig, Dialect.SNOWFLAKE),
    "databricks": (DatabricksConfig, Dialect.DATABRICKS),
}


def pool_from_config(
    connection: str = "default",
    config_path: str | Path = ".semolina.toml",
) -> tuple[Any, Dialect]:
    """
    Create a (pool, Dialect) tuple from .semolina.toml config.

    Reads the named connection section, determines the warehouse type,
    instantiates the appropriate adbc-poolhouse config class, and creates
    a connection pool.

    Args:
        connection: Name of the connection section in [connections.X].
        config_path: Path to the TOML config file.

    Returns:
        Tuple of (pool, Dialect) ready for register().

    Raises:
        FileNotFoundError: If config file does not exist.
        KeyError: If the named connection section is not found.
        ValueError: If the type field is missing or unsupported.
    """
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)

    connections = config.get("connections", {})
    if connection not in connections:
        available = list(connections.keys())
        raise KeyError(
            f"Connection '{connection}' not found in {config_path}. "
            f"Available connections: {available}"
        )

    section = dict(connections[connection])  # shallow copy
    conn_type = section.pop("type", None)
    if conn_type is None:
        raise ValueError(
            f"Connection '{connection}' in {config_path} is missing "
            "required 'type' field (e.g. type = \"snowflake\")"
        )

    if conn_type not in _CONFIG_MAP:
        supported = list(_CONFIG_MAP.keys())
        raise ValueError(
            f"Unsupported connection type '{conn_type}'. "
            f"Supported types: {supported}"
        )

    config_cls, dialect = _CONFIG_MAP[conn_type]
    warehouse_config = config_cls(**section)
    pool = create_pool(warehouse_config)
    return pool, dialect
```

### Pattern 2: TOML Field Names Match adbc-poolhouse Config Fields

**What:** The TOML connection section field names must match the adbc-poolhouse config class field names exactly, since we unpack the dict directly as kwargs.

**Why critical:** adbc-poolhouse's `SnowflakeConfig` uses `user` (not `username`), `account`, `password`, etc. `DatabricksConfig` uses `host` (not `server_hostname`), `http_path`, `token` (not `access_token`).

**TOML format (updated from CONTEXT.md):**
```toml
# .semolina.toml
[connections.default]
type = "snowflake"
account = "myorg-myaccount"
user = "myuser"
password = "secret"
database = "analytics"
warehouse = "compute_wh"

[connections.analytics]
type = "databricks"
host = "adb-xxx.azuredatabricks.net"
http_path = "/sql/1.0/warehouses/abc123"
token = "dapi..."
catalog = "main"
```

**IMPORTANT field name differences from existing `.semolina.toml.example`:**

| Existing example | adbc-poolhouse field | Notes |
|-----------------|---------------------|-------|
| `server_hostname` | `host` | DatabricksConfig uses `host` |
| `access_token` | `token` | DatabricksConfig uses `token` |
| `user` | `user` | SnowflakeConfig matches (also accepts `None`) |
| N/A | `schema` | Both configs use `schema` (alias for `schema_` Python field) |

### Pattern 3: Env Var Override (Free via pydantic-settings)

**What:** adbc-poolhouse config classes inherit from `BaseSettings` with `env_prefix`. Env vars automatically override TOML values when config is instantiated.

**How it works:** `SnowflakeConfig(account="xy", user="me")` will still check `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` etc. But since we pass explicit kwargs from TOML, the kwargs take priority in pydantic-settings' source ordering (init kwargs > env vars > defaults).

**Important nuance:** If we want env vars to OVERRIDE TOML values, we need to NOT pass those fields as kwargs. The simplest approach: just pass all TOML fields as kwargs and let pydantic handle it. Users who want env var overrides can omit the field from TOML.

### Pattern 4: Pool Interface Compatibility

**What:** `create_pool()` returns a `sqlalchemy.pool.QueuePool`. Its `.connect()` returns an ADBC DBAPI connection with `.cursor()` -- the same interface MockPool already exposes.

**Evidence from adbc-poolhouse source:**
```python
# adbc_poolhouse._pool_factory.py
pool = sqlalchemy.pool.QueuePool(
    source.adbc_clone,
    pool_size=pool_size,
    max_overflow=max_overflow,
    ...
)
```

**Compatibility with existing execute() path:**
```python
# In _Query.execute() -- current code works with adbc-poolhouse pools:
conn = pool.connect()    # QueuePool.connect() returns proxied connection
cur = conn.cursor()      # ADBC DBAPI cursor
cur.execute(sql, params) # Standard DBAPI execute
return SemolinaCursor(cur, conn, pool)
```

### Anti-Patterns to Avoid

- **Custom config wrapper classes:** User decision says NO. Use adbc-poolhouse configs directly.
- **pydantic-settings TomlConfigSettingsSource:** User decision says NO. Direct tomllib parsing is simpler.
- **Hardcoding field mappings:** Don't translate TOML field names to different config field names. TOML fields must match config class fields exactly (document this for users).
- **Auto-registration:** Deferred. `pool_from_config()` returns a tuple; user calls `register()` manually.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connection pooling | Custom pool with deque/Lock | `adbc_poolhouse.create_pool()` | Returns battle-tested SQLAlchemy QueuePool with adbc_clone pattern |
| Typed config validation | Manual field validation | adbc-poolhouse config classes | Pydantic model validation, SecretStr masking, env var support built-in |
| ADBC driver connection | Manual adbc_driver_manager.dbapi.connect() | adbc-poolhouse `create_pool(config)` | Handles driver resolution, dbapi module detection, clone-based pooling |
| Pool lifecycle management | Custom close/cleanup | `adbc_poolhouse.close_pool(pool)` | Properly disposes QueuePool AND closes ADBC source connection |
| TOML parsing | Custom parser | `tomllib` (stdlib) | Python 3.11+ stdlib, zero dependencies |

**Key insight:** adbc-poolhouse already does the heavy lifting. Phase 27 is primarily a thin glue layer: read TOML -> dispatch to config class -> create pool -> return tuple.

## Common Pitfalls

### Pitfall 1: DatabricksConfig Field Names Differ from Old Convention

**What goes wrong:** Using `server_hostname` and `access_token` in TOML (matching old `.semolina.toml.example`) when DatabricksConfig expects `host` and `token`.
**Why it happens:** The existing `.semolina.toml.example` uses `server_hostname` and `access_token` (matching `databricks-sql-connector` conventions). adbc-poolhouse's `DatabricksConfig` uses `host` and `token`.
**How to avoid:** Update `.semolina.toml.example` to use the new `[connections.name]` format with correct field names. Document the field name change prominently.
**Warning signs:** `pydantic.ValidationError` on DatabricksConfig instantiation with "unexpected keyword argument" or missing required fields.

### Pitfall 2: DatabricksConfig Requires Either URI or (host + http_path + token)

**What goes wrong:** Providing only partial Databricks config (e.g. `host` without `token`) causes a `ConfigurationError` from the model validator.
**Why it happens:** DatabricksConfig has a `@model_validator` that requires either `uri` OR all three of `host`, `http_path`, `token`.
**How to avoid:** Document the two valid Databricks connection modes in `.semolina.toml.example`. Provide clear error messages that reference the TOML section.
**Warning signs:** `ConfigurationError: DatabricksConfig requires either 'uri' or all three of 'host', 'http_path', and 'token'`.

### Pitfall 3: Pool Close Requires close_pool() Not Just pool.dispose()

**What goes wrong:** Calling `pool.dispose()` or `pool.close()` does not close the underlying ADBC source connection, causing resource leaks.
**Why it happens:** `create_pool()` stores the source connection on `pool._adbc_source`. Standard QueuePool disposal does not know about this.
**How to avoid:** Use `close_pool(pool)` from adbc-poolhouse, which calls both `pool.dispose()` and `pool._adbc_source.close()`. Update `registry.reset()` to call `close_pool()` instead of just `pool.close()`.
**Warning signs:** Resource leak warnings, unclosed Go goroutines (Snowflake ADBC driver), connections held open after registry reset.

### Pitfall 4: `schema` Field Alias in Config Classes

**What goes wrong:** Using `schema` in TOML works (it is the alias), but the Python attribute is `schema_`. Direct attribute access in code uses `config.schema_`, not `config.schema`.
**Why it happens:** `schema` shadows a pydantic internal. adbc-poolhouse uses `Field(validation_alias="schema", alias="schema")` on `schema_`.
**How to avoid:** In TOML, users write `schema = "my_schema"` (natural). In Python code, access as `config.schema_`. The dict unpacking `SnowflakeConfig(**section)` works because pydantic's `populate_by_name` is NOT explicitly set, but the `validation_alias="schema"` handles it.
**Warning signs:** KeyError or ValidationError when `schema` is in TOML. Test by including a `schema` field in TOML fixtures.

### Pitfall 5: adbc-poolhouse Is a Core Dependency -- Imports Must Not Be Lazy

**What goes wrong:** Making adbc-poolhouse imports lazy (inside functions) when it is declared as a core dependency.
**Why it happens:** Existing patterns in the codebase use lazy imports for optional dependencies (e.g. ADBC drivers in engines).
**How to avoid:** Since adbc-poolhouse is a core dependency (per user decision), top-level imports are fine in `config.py`. Only the ADBC *driver* packages remain optional.
**Warning signs:** Unnecessary `try/except ImportError` blocks around adbc-poolhouse imports.

### Pitfall 6: The `type` Field Must Be Popped Before Passing to Config Class

**What goes wrong:** Passing the full TOML section dict (including `type = "snowflake"`) to `SnowflakeConfig(**section)` causes a validation error because `type` is not a field on the config class.
**Why it happens:** The `type` field is Semolina's dispatch field, not an adbc-poolhouse field.
**How to avoid:** `section.pop("type")` before passing to the config class constructor.
**Warning signs:** `pydantic.ValidationError: 1 validation error for SnowflakeConfig -- type: Extra inputs are not permitted`.

## Code Examples

### pool_from_config() Usage

```python
# Create pool from config and register it
import semolina
from semolina.config import pool_from_config

pool, dialect = pool_from_config(connection="default")
semolina.register("default", pool, dialect=dialect)

# Query as normal
cursor = Sales.query().metrics(Sales.revenue).execute()
rows = cursor.fetchall_rows()
```

### Multiple Connections

```python
# .semolina.toml:
# [connections.prod]
# type = "snowflake"
# account = "prod-account"
# ...
#
# [connections.dev]
# type = "snowflake"
# account = "dev-account"
# ...

from semolina.config import pool_from_config
import semolina

prod_pool, prod_dialect = pool_from_config(connection="prod")
dev_pool, dev_dialect = pool_from_config(connection="dev")

semolina.register("prod", prod_pool, dialect=prod_dialect)
semolina.register("dev", dev_pool, dialect=dev_dialect)

# Use specific connection
cursor = Sales.query().metrics(Sales.revenue).using("prod").execute()
```

### Pool Cleanup with close_pool

```python
from adbc_poolhouse import close_pool
from semolina.config import pool_from_config

pool, dialect = pool_from_config()
# ... use pool ...
close_pool(pool)  # Properly disposes pool AND ADBC source connection
```

### TOML File Format

```toml
# .semolina.toml

[connections.default]
type = "snowflake"
account = "myorg-myaccount"
user = "myuser"
password = "secret"
database = "analytics"
warehouse = "compute_wh"
role = "analyst"
# Optional pool tuning (adbc-poolhouse defaults)
# pool_size = 5
# max_overflow = 3
# timeout = 30
# recycle = 3600

[connections.analytics]
type = "databricks"
host = "adb-xxx.azuredatabricks.net"
http_path = "/sql/1.0/warehouses/abc123"
token = "dapi..."
catalog = "main"
# schema = "default"  # optional
```

### Error Handling Patterns

```python
from semolina.config import pool_from_config

# Missing config file
try:
    pool, dialect = pool_from_config(config_path="nonexistent.toml")
except FileNotFoundError:
    print("Config file not found")

# Missing connection section
try:
    pool, dialect = pool_from_config(connection="nonexistent")
except KeyError as e:
    print(f"Connection not found: {e}")

# Missing type field
try:
    pool, dialect = pool_from_config(connection="bad_section")
except ValueError as e:
    print(f"Invalid config: {e}")
```

## adbc-poolhouse Config Class Reference

### SnowflakeConfig Key Fields

| Field | Type | Required | Default | Env Var | Notes |
|-------|------|----------|---------|---------|-------|
| `account` | `str` | Yes | - | `SNOWFLAKE_ACCOUNT` | Account identifier |
| `user` | `str \| None` | No | `None` | `SNOWFLAKE_USER` | Username |
| `password` | `SecretStr \| None` | No | `None` | `SNOWFLAKE_PASSWORD` | Password auth |
| `database` | `str \| None` | No | `None` | `SNOWFLAKE_DATABASE` | Default database |
| `warehouse` | `str \| None` | No | `None` | `SNOWFLAKE_WAREHOUSE` | Virtual warehouse |
| `role` | `str \| None` | No | `None` | `SNOWFLAKE_ROLE` | Snowflake role |
| `schema` | `str \| None` | No | `None` | `SNOWFLAKE_SCHEMA` | Default schema (alias for `schema_`) |
| `auth_type` | `str \| None` | No | `None` | `SNOWFLAKE_AUTH_TYPE` | Auth method selector |
| `private_key_path` | `Path \| None` | No | `None` | `SNOWFLAKE_PRIVATE_KEY_PATH` | JWT key file |
| `pool_size` | `int` | No | `5` | `SNOWFLAKE_POOL_SIZE` | Inherited from base |
| `max_overflow` | `int` | No | `3` | `SNOWFLAKE_MAX_OVERFLOW` | Inherited from base |
| `timeout` | `int` | No | `30` | `SNOWFLAKE_TIMEOUT` | Inherited from base |
| `recycle` | `int` | No | `3600` | `SNOWFLAKE_RECYCLE` | Inherited from base |

### DatabricksConfig Key Fields

| Field | Type | Required | Default | Env Var | Notes |
|-------|------|----------|---------|---------|-------|
| `uri` | `SecretStr \| None` | Conditional | `None` | `DATABRICKS_URI` | Full DSN string (mode 1) |
| `host` | `str \| None` | Conditional | `None` | `DATABRICKS_HOST` | Workspace hostname (mode 2) |
| `http_path` | `str \| None` | Conditional | `None` | `DATABRICKS_HTTP_PATH` | SQL warehouse path (mode 2) |
| `token` | `SecretStr \| None` | Conditional | `None` | `DATABRICKS_TOKEN` | PAT (mode 2) |
| `auth_type` | `str \| None` | No | `None` | `DATABRICKS_AUTH_TYPE` | OAuth type selector |
| `catalog` | `str \| None` | No | `None` | `DATABRICKS_CATALOG` | Unity Catalog |
| `schema` | `str \| None` | No | `None` | `DATABRICKS_SCHEMA` | Default schema |
| `pool_size` | `int` | No | `5` | `DATABRICKS_POOL_SIZE` | Inherited from base |

**Databricks connection modes:** Either `uri` alone, OR all three of `host` + `http_path` + `token`. Model validator enforces this.

## State of the Art

| Old Approach (existing .semolina.toml) | New Approach (Phase 27) | Impact |
|----------------------------------------|-------------------------|--------|
| `[snowflake]` / `[databricks]` flat sections | `[connections.name]` sections with `type` field | Supports multiple named connections |
| `server_hostname` / `access_token` (Databricks) | `host` / `token` (adbc-poolhouse field names) | Breaking change to TOML format |
| Manual `tomllib.load()` in `testing/credentials.py` | `pool_from_config()` factory function | Standardized config-to-pool pipeline |
| `snowflake-connector-python` / `databricks-sql-connector` | adbc-poolhouse + ADBC drivers | Arrow-native transport, connection pooling |
| `pydantic-settings` as dev dependency | `pydantic-settings` as transitive (via adbc-poolhouse) | No longer need to declare separately |

**Deprecated/outdated:**
- `.semolina.toml.example` with old flat `[snowflake]`/`[databricks]` format: needs updating
- `testing/credentials.py` with manual `tomllib` + `SnowflakeCredentials`: can coexist (testing use case) but should be updated later

## Open Questions

1. **Should `testing/credentials.py` be updated to use `pool_from_config()`?**
   - What we know: `testing/credentials.py` has its own `SnowflakeCredentials`/`DatabricksCredentials` classes with manual TOML loading. It serves the integration test credential loading use case.
   - What's unclear: Whether tests should migrate to the new TOML format now or later.
   - Recommendation: Leave `testing/credentials.py` unchanged in this phase. It serves a different purpose (test credential loading with fallback chains). Can be updated in a future phase.

2. **Should optional extras (adbc-driver-snowflake, adbc-driver-flightsql) be updated in pyproject.toml?**
   - What we know: Current extras reference `snowflake-connector-python` and `databricks-sql-connector`. Phase 27 adds adbc-poolhouse as core dependency.
   - Recommendation: Update the `[project.optional-dependencies]` to reference adbc-poolhouse extras: `snowflake = ["adbc-poolhouse[snowflake]"]`. Keep `databricks` extra documentation-only since the Databricks driver is Foundry-distributed (not PyPI).

3. **How should `registry.reset()` handle adbc-poolhouse pools?**
   - What we know: Current `reset()` calls `pool.close()` on each pool. adbc-poolhouse pools need `close_pool(pool)` to properly close the ADBC source connection.
   - Recommendation: Import `close_pool` from adbc-poolhouse and use it in `reset()`. Fall back to `pool.close()` if the pool does not have `_adbc_source` (e.g. MockPool).

4. **Databricks driver: Foundry vs FlightSQL?**
   - What we know: adbc-poolhouse's `DatabricksConfig` uses the Columnar Databricks ADBC driver (Foundry-distributed, not on PyPI). The `FlightSQLConfig` is an alternative that IS on PyPI (`adbc-driver-flightsql`).
   - Recommendation: Support both `type = "databricks"` (DatabricksConfig, Foundry driver) and consider `type = "flightsql"` (FlightSQLConfig, PyPI driver) in the `_CONFIG_MAP`. This gives users flexibility. Document the Foundry vs PyPI distinction.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | type field maps to correct config class | unit | `uv run pytest tests/unit/test_config.py::TestConfigDispatch -x` | Wave 0 |
| CONF-01 | TOML [connections.name] sections parsed correctly | unit | `uv run pytest tests/unit/test_config.py::TestTomlParsing -x` | Wave 0 |
| CONF-02 | Dict unpacking into SnowflakeConfig works | unit | `uv run pytest tests/unit/test_config.py::TestSnowflakeConfig -x` | Wave 0 |
| CONF-02 | Dict unpacking into DatabricksConfig works | unit | `uv run pytest tests/unit/test_config.py::TestDatabricksConfig -x` | Wave 0 |
| CONF-03 | pool_from_config returns (pool, Dialect) tuple | unit | `uv run pytest tests/unit/test_config.py::TestPoolFromConfig -x` | Wave 0 |
| CONF-03 | pool_from_config defaults to connection="default" | unit | `uv run pytest tests/unit/test_config.py::TestPoolFromConfig -x` | Wave 0 |
| CONF-03 | pool_from_config defaults to config_path=".semolina.toml" | unit | `uv run pytest tests/unit/test_config.py::TestPoolFromConfig -x` | Wave 0 |
| - | Error: missing config file raises FileNotFoundError | unit | `uv run pytest tests/unit/test_config.py::TestConfigErrors -x` | Wave 0 |
| - | Error: missing connection section raises KeyError | unit | `uv run pytest tests/unit/test_config.py::TestConfigErrors -x` | Wave 0 |
| - | Error: missing type field raises ValueError | unit | `uv run pytest tests/unit/test_config.py::TestConfigErrors -x` | Wave 0 |
| - | Error: unsupported type raises ValueError | unit | `uv run pytest tests/unit/test_config.py::TestConfigErrors -x` | Wave 0 |

### Testing Strategy Notes

**Mocking `create_pool`:** Unit tests should mock `adbc_poolhouse.create_pool` to avoid requiring real ADBC drivers. The mock returns a fake pool object. Tests verify that:
1. The correct config class is instantiated with correct fields
2. `create_pool` is called with the config instance
3. The returned tuple contains the pool and correct Dialect

**TOML fixtures:** Create temporary `.toml` files in `$TMPDIR` for testing. Use Python's `tempfile` module.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_config.py` -- covers CONF-01, CONF-02, CONF-03 (all config tests)
- [ ] `.semolina.toml.example` update to new `[connections.name]` format

*(Framework install: not needed -- pytest already configured)*

## Sources

### Primary (HIGH confidence)

- [adbc-poolhouse GitHub source](https://github.com/anentropic/adbc-poolhouse) - v1.2.0, full source code reviewed for SnowflakeConfig, DatabricksConfig, FlightSQLConfig, BaseWarehouseConfig, create_pool(), close_pool(), managed_pool()
- [adbc-poolhouse pyproject.toml](https://github.com/anentropic/adbc-poolhouse/blob/main/pyproject.toml) - Dependencies: pydantic-settings>=2.0.0, sqlalchemy>=2.0.0, adbc-driver-manager>=1.8.0
- Existing Semolina codebase - `registry.py`, `dialect.py`, `pool.py`, `cursor.py`, `query.py`, `__init__.py`, `testing/credentials.py`
- Phase 27 CONTEXT.md - User decisions on TOML format, config strategy, API design
- Python 3.11+ `tomllib` stdlib documentation

### Secondary (MEDIUM confidence)

- [adbc-poolhouse documentation](https://anentropic.github.io/adbc-poolhouse/) - Public API overview, usage patterns
- Phase 25 RESEARCH.md - adbc-poolhouse confirmed on PyPI, pool interface patterns

### Notes on REQUIREMENTS.md vs CONTEXT.md Discrepancy

The REQUIREMENTS.md still references "TomlSettingsSource" in CONF-02. The CONTEXT.md (user decisions) explicitly overrides this: "No pydantic-settings TomlConfigSettingsSource -- parse with tomllib directly." The CONTEXT.md takes precedence as it represents the latest user decision. CONF-02 should be interpreted as "TOML sections load into adbc-poolhouse config classes" via dict unpacking, not via TomlSettingsSource.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - adbc-poolhouse v1.2.0 source code fully reviewed; config classes, create_pool, close_pool verified
- Architecture: HIGH - thin glue layer pattern; tomllib -> dict -> config class -> create_pool is straightforward
- Pitfalls: HIGH - DatabricksConfig field name differences verified from source; model validators documented; `type` pop requirement verified
- Config class fields: HIGH - exact field names, types, and defaults verified from adbc-poolhouse source code

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain; adbc-poolhouse API unlikely to break within minor versions)
