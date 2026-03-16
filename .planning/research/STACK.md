# Technology Stack

**Project:** Semolina v0.3 Arrow & Connection Layer
**Researched:** 2026-03-16
**Confidence:** HIGH (ADBC ecosystem well-documented; pydantic-settings TOML is stable)

## Critical Clarification: "adbc-poolhouse" Does Not Exist

The project planning documents reference "adbc-poolhouse" as a library. **No such package exists on PyPI or GitHub.** What the project actually needs is:

1. **ADBC driver packages** (`adbc-driver-snowflake`, `adbc-driver-flightsql`) for Arrow-native database connectivity
2. **A connection pool** built on top of ADBC's `adbc_clone()` pattern, using SQLAlchemy's `QueuePool` (the ADBC-recommended approach)
3. **A thin wrapper layer** (Semolina's own code) that combines these into a pool registry

The "poolhouse" concept is Semolina's own abstraction to be built, not an external dependency.

## Recommended Stack Additions for v0.3

### Core Dependencies (added to `[project.dependencies]`)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pydantic-settings | >=2.7.0 | TOML config via `TomlConfigSettingsSource` | Already in dev deps. Promotes to core for `pool_from_config()`. Uses stdlib `tomllib` (Python 3.11+). No extra TOML dep needed. |
| pydantic | >=2.0.0 | Transitive via pydantic-settings | Already a transitive dependency. Needed for BaseSettings, SecretStr, model validation. |

**Why pydantic-settings moves to core:** The `.semolina.toml` config and `pool_from_config()` are user-facing features, not dev-only. Users need pydantic-settings at runtime to load pool configuration from TOML files.

### Backend ADBC Drivers (optional extras, replacing current connectors)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| adbc-driver-snowflake | >=1.9.0 | Snowflake ADBC connectivity | Arrow-native transport. Go-based driver wrapping Snowflake Go connector. Provides DBAPI 2.0 interface with `fetch_arrow_table()`. Replaces `snowflake-connector-python`. |
| adbc-driver-flightsql | >=1.9.0 | Databricks ADBC connectivity (via Arrow Flight SQL) | Databricks exposes a Flight SQL endpoint. This driver connects via `grpc+tls://` with bearer token auth. Replaces `databricks-sql-connector`. |
| adbc-driver-manager | >=1.9.0 | ADBC driver manager / DBAPI layer | Transitive dependency of both drivers above. Provides `adbc_driver_manager.dbapi.Connection` and `Cursor` with Arrow fetch methods. |
| pyarrow | >=17.0.0 | Arrow in-memory format | Required by ADBC DBAPI interface for `fetch_arrow_table()` and `RecordBatchReader`. NOT a declared dependency of adbc-driver-manager (packaging bug, see apache/arrow-adbc#1908), so must be declared explicitly. |

### Connection Pooling (no new dependency)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sqlalchemy (QueuePool only) | >=2.0.0 | Connection pool implementation | ADBC's official recipe for connection pooling uses `sqlalchemy.pool.QueuePool` with `connection.adbc_clone()` as the factory. This is the Apache-recommended pattern. Import only `sqlalchemy.pool`, not the ORM. |

**IMPORTANT DECISION:** Whether to take SQLAlchemy as a dependency deserves careful consideration. The alternatives are:

1. **Use SQLAlchemy's QueuePool** -- battle-tested, ADBC-recommended, but adds a heavy transitive dependency
2. **Build a minimal pool** -- Semolina only needs acquire/release/close semantics; a simple queue-based pool is ~50 lines of code
3. **No pooling** -- ADBC connections via `adbc_clone()` already share internal resources (OID caches, etc.)

**Recommendation:** Build a minimal pool internally. Semolina's use case (data warehouse queries, not OLTP) has low concurrency. A simple `collections.deque`-based pool with max_size is sufficient. This avoids the SQLAlchemy dependency while still providing connection reuse. The `adbc_clone()` method handles the expensive resource sharing.

### Dev Dependencies (additions to `[dependency-groups.dev]`)

No new dev dependencies needed. pytest, syrupy, basedpyright, ruff all remain.

## Revised pyproject.toml Structure

```toml
[project]
dependencies = [
    "pydantic-settings>=2.7.0",  # TOML config for pool_from_config()
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
snowflake = [
    "adbc-driver-snowflake>=1.9.0",
    "pyarrow>=17.0.0",
]
databricks = [
    "adbc-driver-flightsql>=1.9.0",
    "pyarrow>=17.0.0",
]
all = [
    "semolina[snowflake,databricks]",
]
```

**Key changes from v0.2:**
- `snowflake-connector-python` replaced by `adbc-driver-snowflake`
- `databricks-sql-connector` replaced by `adbc-driver-flightsql`
- `pyarrow` added explicitly to each backend extra (ADBC needs it but does not declare it)
- `pydantic-settings` promoted from dev dep to core dependency

## ADBC DBAPI Cursor API (the interface SemolinaCursor wraps)

The `adbc_driver_manager.dbapi.Cursor` provides these methods that SemolinaCursor will wrap:

### Standard DBAPI (PEP 249)

| Method | Returns | Notes |
|--------|---------|-------|
| `execute(sql, parameters=None)` | None | Executes SQL. Parameters can be sequence, dict, or Arrow data. |
| `fetchone()` | tuple or None | Single row as tuple. |
| `fetchmany(size=cursor.arraysize)` | list[tuple] | Multiple rows. |
| `fetchall()` | list[tuple] | All remaining rows. |
| `close()` | None | Releases resources. Context manager supported. |
| `description` | list[tuple] | Column metadata (name, type_code, ...). |

### ADBC Extensions (Arrow-native)

| Method | Returns | Notes |
|--------|---------|-------|
| `fetch_arrow_table()` | `pyarrow.Table` | All results as Arrow Table. Zero-copy when driver supports it. This is the primary fetch method for Semolina. |
| `fetch_record_batch_reader()` | `pyarrow.RecordBatchReader` | Streaming reader for large results. Cursor must stay alive until reader is consumed. |
| `adbc_prepare()` | None | Explicit statement preparation. |

### Connection Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `connect(uri, db_kwargs={})` | Connection | Opens connection. Per-driver URI format. |
| `adbc_clone()` | Connection | Opens new connection sharing internal resources. **This is the pool factory function.** |
| `cursor()` | Cursor | Creates cursor. Context manager supported. |
| `close()` | None | Closes connection. |

## ADBC Connection Patterns by Backend

### Snowflake via adbc-driver-snowflake

```python
import adbc_driver_snowflake.dbapi

# URI-based connection
conn = adbc_driver_snowflake.dbapi.connect(
    "user:password@account/database/schema?warehouse=WH&role=ROLE"
)

# Or db_kwargs-based connection
conn = adbc_driver_snowflake.dbapi.connect(
    db_kwargs={
        "adbc.snowflake.sql.account": "xy12345",
        "adbc.snowflake.sql.warehouse": "compute_wh",
        "adbc.snowflake.sql.db": "analytics",
        "adbc.snowflake.sql.schema": "public",
        "username": "user",
        "password": "pass",
    }
)

with conn.cursor() as cur:
    cur.execute("SELECT AGG(revenue), country FROM sales_view GROUP BY ALL")
    table = cur.fetch_arrow_table()  # pyarrow.Table
```

### Databricks via adbc-driver-flightsql

```python
import adbc_driver_flightsql.dbapi
from adbc_driver_flightsql import DatabaseOptions

conn = adbc_driver_flightsql.dbapi.connect(
    f"grpc+tls://{server_hostname}:443",
    db_kwargs={
        DatabaseOptions.AUTHORIZATION_HEADER.value: f"Bearer {access_token}",
        f"{DatabaseOptions.RPC_CALL_HEADER_PREFIX.value}x-databricks-http-path": http_path,
    },
)

with conn.cursor() as cur:
    cur.execute("SELECT MEASURE(revenue), country FROM sales_view GROUP BY ALL")
    table = cur.fetch_arrow_table()  # pyarrow.Table
```

### Connection Pooling Pattern (ADBC-recommended)

```python
# Create initial "source" connection
source = adbc_driver_snowflake.dbapi.connect(uri)

# adbc_clone() creates new connections sharing internal resources
# This is the factory function for the pool
cloned_conn = source.adbc_clone()

# With SQLAlchemy QueuePool (official ADBC recipe):
import sqlalchemy.pool
pool = sqlalchemy.pool.QueuePool(source.adbc_clone, pool_size=5, max_overflow=2)
conn = pool.connect()
# ... use conn ...
conn.close()  # returns to pool, does not actually close
source.close()  # closes the template connection
```

## TomlConfigSettingsSource Integration

### Current State (v0.2)

The existing `testing/credentials.py` manually loads `.semolina.toml` with `tomllib.load()` and constructs pydantic-settings models. This is brittle and duplicates logic.

### v0.3 Approach

Use pydantic-settings' built-in `TomlConfigSettingsSource` to load `.semolina.toml` directly:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings import TomlConfigSettingsSource

class SemolinaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=".semolina.toml",
        env_prefix="SEMOLINA_",
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):
        return (
            kwargs["env_settings"],           # env vars first
            kwargs["dotenv_settings"],         # .env second
            TomlConfigSettingsSource(settings_cls),  # .semolina.toml third
        )
```

**Version requirement:** pydantic-settings >=2.7.0 (TomlConfigSettingsSource was added in 2.6.0; 2.7.0 includes important fixes). Latest is 2.13.1.

**TOML parsing:** Uses stdlib `tomllib` on Python >=3.11. No additional TOML parsing dependency needed since Semolina requires Python >=3.11.

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `snowflake-connector-python` | Replaced by ADBC driver. The old Python connector is DBAPI-only, no Arrow-native transport. | `adbc-driver-snowflake` |
| `databricks-sql-connector` | Replaced by Flight SQL ADBC driver. Old connector has limited Arrow support. | `adbc-driver-flightsql` |
| `pyarrow` as core dependency | Only needed when a backend extra is installed. Declaring it in each extra avoids bloating core installs. | Declare in each extra: `snowflake`, `databricks` |
| `sqlalchemy` | Heavy dependency (ORM, engine, metadata, etc.) just for QueuePool. Semolina's pool needs are simple. | Build minimal pool (~50 lines) using `collections.deque` + `threading.Lock` |
| `polars` | ADBC cursors support `fetch_polars_df()` but Semolina should not depend on Polars. Users can convert Arrow Tables themselves. | Expose Arrow Tables; users call `polars.from_arrow(table)` |
| `pandas` | Same rationale as Polars. ADBC has `fetch_pandas_df()` but adding pandas as a dep is unnecessary. | Users call `table.to_pandas()` on the Arrow Table |
| `tomli` | Backport of tomllib for Python <3.11. Semolina requires >=3.11, so stdlib tomllib suffices. | `tomllib` (stdlib) |
| `asyncio` wrappers | Out of scope for v0.3 per PROJECT.md. Connection layer should be sync-first. | Defer async to post-v0.3 |

## Version Compatibility Matrix

| Component | Min Version | Latest Verified | Python | Notes |
|-----------|-------------|-----------------|--------|-------|
| adbc-driver-snowflake | 1.9.0 | 1.9.0 (Nov 2025) | >=3.10 | Go-based driver via C FFI |
| adbc-driver-flightsql | 1.9.0 | 1.9.0 (Jan 2026) | >=3.10 | Go-based Flight SQL driver |
| adbc-driver-manager | 1.9.0 | 1.9.0 (Nov 2025) | >=3.10 | Transitive dep of both drivers |
| pyarrow | 17.0.0 | 23.0.1 (Feb 2026) | >=3.9 | Required by ADBC DBAPI interface |
| pydantic-settings | 2.7.0 | 2.13.1 (Feb 2026) | >=3.8 | TomlConfigSettingsSource stable since 2.6.0 |
| pydantic | 2.0.0 | 2.12+ (Feb 2026) | >=3.8 | Transitive via pydantic-settings |

All versions are compatible with Semolina's Python >=3.11 requirement.

## Integration Points with Existing Semolina Code

### What Gets Replaced

| Current (v0.2) | Replaced By (v0.3) | Module |
|-----------------|---------------------|--------|
| `Engine` ABC | Pool protocol + Dialect enum | `engines/base.py` -> `pool.py` + `dialect.py` |
| `SnowflakeEngine` | Snowflake ADBC pool + SnowflakeDialect | `engines/snowflake.py` -> config-driven |
| `DatabricksEngine` | Databricks ADBC pool + DatabricksDialect | `engines/databricks.py` -> config-driven |
| `MockEngine` | `MockPool` | `engines/mock.py` -> `pool.py` |
| `registry.register(name, engine)` | `registry.register(name, pool, dialect=...)` | `registry.py` |
| `_Query.execute() -> Result` | `_Query.execute() -> SemolinaCursor` | `query.py` |
| `Result` / `Row` | `SemolinaCursor` with `.fetchall_rows()` convenience | `cursor.py` (new) |

### What Stays the Same

| Component | Why Unchanged |
|-----------|--------------|
| `SemanticView` metaclass | Models are backend-agnostic. No connection layer coupling. |
| `Metric`, `Dimension`, `Fact` fields | Field descriptors are pure Python. No driver dependency. |
| `Predicate` tree / `filters.py` | Filter IR is backend-agnostic. Compiled to SQL by Dialect. |
| `SQLBuilder` + `Dialect` ABC | SQL generation is already cleanly separated. SnowflakeDialect/DatabricksDialect/MockDialect remain. |
| `.to_sql()` on `_Query` | Debugging method, no execution involved. |
| CLI codegen (`semolina codegen`) | Uses introspection, not the connection pool. May need ADBC connection for introspect, but SQL generation is unchanged. |

### New Modules

| Module | Responsibility |
|--------|---------------|
| `src/semolina/pool.py` | Pool protocol, minimal connection pool, MockPool, pool_from_config() |
| `src/semolina/cursor.py` | SemolinaCursor wrapping ADBC cursor with convenience methods |
| `src/semolina/dialect.py` | Dialect enum (snowflake, databricks) replacing per-engine dialect instances |
| `src/semolina/config.py` | SemolinaConfig (pydantic-settings with TomlConfigSettingsSource) |

## Installation Commands

```bash
# Core (includes pydantic-settings for config)
pip install semolina

# With Snowflake (gets ADBC Snowflake driver + pyarrow)
pip install semolina[snowflake]

# With Databricks (gets ADBC Flight SQL driver + pyarrow)
pip install semolina[databricks]

# With all backends
pip install semolina[all]

# Development
uv sync --all-extras
```

## Sources

**ADBC Documentation:**
- [Apache Arrow ADBC](https://arrow.apache.org/adbc/) -- main documentation
- [ADBC Python API Reference](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html) -- Cursor, Connection, fetch methods
- [ADBC Snowflake Driver](https://arrow.apache.org/adbc/current/driver/snowflake.html) -- connection URI, auth methods
- [ADBC Flight SQL Driver](https://arrow.apache.org/adbc/current/driver/flight_sql.html) -- Databricks via Flight SQL
- [ADBC Connection Pool Recipe](https://github.com/apache/arrow-adbc/blob/main/docs/source/python/recipe/postgresql_pool.py) -- QueuePool + adbc_clone pattern

**ADBC PyPI Packages:**
- [adbc-driver-snowflake on PyPI](https://pypi.org/project/adbc-driver-snowflake/) -- v1.9.0 (Nov 2025)
- [adbc-driver-flightsql on PyPI](https://pypi.org/project/adbc-driver-flightsql/) -- v1.9.0 (Jan 2026)
- [adbc-driver-manager on PyPI](https://pypi.org/project/adbc-driver-manager/) -- v1.9.0 (Nov 2025)
- [pyarrow on PyPI](https://pypi.org/project/pyarrow/) -- v23.0.1 (Feb 2026)
- [PyArrow not declared as ADBC dependency](https://github.com/apache/arrow-adbc/issues/1908) -- must be explicit

**pydantic-settings:**
- [pydantic-settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) -- TomlConfigSettingsSource usage
- [pydantic-settings on PyPI](https://pypi.org/project/pydantic-settings/) -- v2.13.1 (Feb 2026)
- [Configuration Files in pydantic-settings](https://deepwiki.com/pydantic/pydantic-settings/3.2-configuration-files) -- TOML deep dive

**Snowflake ADBC Guides:**
- [Quick Start Guide to Snowflake ADBC Driver](https://medium.com/snowflake/a-quick-start-guide-to-the-snowflake-adbc-driver-with-python-6de3eb28ee52) -- practical Python walkthrough
- [ADBC Support for Snowflake](https://medium.com/snowflake/arrow-database-connectivity-adbc-support-for-snowflake-7bfb3a2d9074) -- architecture overview

**Databricks Flight SQL:**
- [ADBC Arrow Driver for Databricks](https://dataengineeringcentral.substack.com/p/adbc-arrow-driver-for-databricks) -- practical implementation (Jan 2026)
- [Databricks SQL Connector for Python](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector) -- current connector being replaced

---

*Stack research for Semolina v0.3 Arrow & Connection Layer*
*Researched: 2026-03-16*
