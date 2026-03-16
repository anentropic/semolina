# Architecture Patterns

**Domain:** ADBC connection pools + Arrow-native cursors for Semolina ORM (v0.3)
**Researched:** 2026-03-16
**Confidence:** HIGH (ADBC APIs verified via official docs; pool design based on established patterns)

---

## Executive Summary

Semolina v0.3 replaces the hand-rolled Engine ABC and per-query connection lifecycle with ADBC-based connection pools and Arrow-native cursors. The central finding from research is that **"adbc-poolhouse" does not exist as a published package** on PyPI or GitHub. ADBC drivers provide DBAPI 2.0 connections with `adbc_clone()` for lightweight connection sharing, but pooling must be built at the application level (the official ADBC PostgreSQL cookbook demonstrates using SQLAlchemy's QueuePool as a reference pattern). Semolina should build its own thin pool abstraction wrapping ADBC driver connections rather than depending on an external pool library.

The ADBC ecosystem provides exactly what Semolina needs:
- `adbc-driver-snowflake` (v1.9.0, Nov 2025) -- Snowflake ADBC driver with `fetch_arrow_table()`
- `adbc-driver-flightsql` (Jan 2026 release) -- Flight SQL driver for Databricks connections
- Both expose a standard DBAPI 2.0 cursor with Arrow extensions

The architecture change touches five existing modules and introduces four new ones. The Dialect hierarchy and SQLBuilder are **preserved unchanged**. The Engine ABC, registry, query execution path, and result objects are all modified or replaced.

---

## 1. What Changes, What Stays

### Unchanged (zero modifications)

| Module | Why It Stays |
|--------|-------------|
| `engines/sql.py` | Dialect ABC, SnowflakeDialect, DatabricksDialect, MockDialect, SQLBuilder -- SQL generation is orthogonal to connection management |
| `fields.py` | Field, Metric, Dimension, Fact, OrderTerm -- query builder primitives |
| `filters.py` | Predicate tree (And, Or, Not, Lookup subclasses) -- filter system |
| `codegen/` | Introspection + code generation -- CLI feature, not query execution |
| `testing/credentials.py` | SnowflakeCredentials, DatabricksCredentials -- still useful for integration tests |
| `cli/` | CLI commands use Engine.introspect() which stays available |

### Modified

| Module | What Changes | Why |
|--------|-------------|-----|
| `registry.py` | Stores `(Pool, Dialect)` tuples instead of `Engine` | Pool + Dialect replaces Engine as the connection abstraction |
| `query.py` | `.execute()` returns `SemolinaCursor` instead of `Result` | Arrow-native cursor is the primary return type |
| `results.py` | `Row` unchanged; `Result` becomes optional sugar | Row is still the convenience wrapper; Result wraps cursor output |
| `models.py` | `SemanticView.query()` unchanged signature | _Query.execute() changes internally but model API is stable |
| `__init__.py` | New exports: Pool types, SemolinaCursor, config helpers | Public API grows |

### New Modules

| Module | Purpose |
|--------|---------|
| `pool.py` | Pool protocol + SnowflakePool + DatabricksPool implementations |
| `cursor.py` | SemolinaCursor wrapping ADBC cursor with Row convenience + Arrow fetch |
| `config.py` | TomlSettingsSource configs + `pool_from_config()` factory |
| `engines/mock.py` (additions) | MockPool + MockConnection + MockCursor added alongside existing MockEngine |

### Deprecated (kept for backward compat, not removed)

| Module | Status |
|--------|--------|
| `engines/base.py` (Engine ABC) | Deprecated, importable but not used by new code paths |
| `engines/snowflake.py` (SnowflakeEngine) | Deprecated, introspect() still works via this class |
| `engines/databricks.py` (DatabricksEngine) | Deprecated, introspect() still works via this class |

---

## 2. Component Architecture

### Component Diagram

```
User Code
    |
    v
SemanticView.query()             -- unchanged entry point
    |
    v
_Query builder chain             -- unchanged .metrics()/.dimensions()/.where()
    |
    v
_Query.execute()                 -- CHANGED: resolves pool+dialect from registry
    |
    +---> SQLBuilder(dialect)    -- UNCHANGED: generates (sql, params) from _Query
    |
    +---> Pool.acquire()         -- NEW: gets ADBC Connection from pool
    |         |
    |         v
    |     conn.cursor()          -- ADBC DBAPI cursor
    |         |
    |         v
    |     cursor.execute(sql, params)
    |
    v
SemolinaCursor(cursor, conn, pool)  -- NEW: wraps raw cursor
    |
    +---> .fetch_arrow_table()      -- Arrow-native (primary)
    +---> .fetch_record_batch_reader()  -- Streaming Arrow
    +---> .fetchall_rows()          -- list[Row] convenience
    +---> .fetchone_row()           -- Row | None convenience
    +---> .close()                  -- releases connection back to pool
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `Pool` (protocol) | Acquire/release ADBC connections; lifecycle management | Registry, ADBC driver modules |
| `SnowflakePool` | Snowflake-specific ADBC connections via `adbc_driver_snowflake.dbapi` | `adbc_driver_snowflake` |
| `DatabricksPool` | Databricks connections via `adbc_driver_flightsql.dbapi` | `adbc_driver_flightsql` |
| `MockPool` | In-memory fixture data, no real connections | _Query predicates, SemolinaCursor |
| `Registry` | Maps names to `(Pool, Dialect)` pairs; lazy resolution | Pool, Dialect, _Query |
| `SemolinaCursor` | Wraps raw ADBC/Mock cursor with Row + Arrow methods | ADBC cursor, Row, Pool (for release) |
| `SQLBuilder` | Generates dialect-specific SQL from _Query (unchanged) | Dialect |
| `Dialect` | Quoting, metric wrapping, placeholder format (unchanged) | SQLBuilder |
| `config` | Loads `.semolina.toml`, creates pools via `pool_from_config()` | Pool constructors, pydantic-settings |

### Data Flow: Real Backend

1. `Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()`
2. `_Query.execute()` calls `registry.get_pool(self._using)` -> `(pool, dialect)`
3. `SQLBuilder(dialect).build_select_with_params(self)` -> `(sql, params)`
4. `pool.acquire()` -> ADBC `Connection`
5. `conn.cursor()` -> ADBC `Cursor`
6. `cursor.execute(sql, params)` -- executes against warehouse
7. Wrap in `SemolinaCursor(cursor, conn, pool)`
8. Return `SemolinaCursor` to caller
9. Caller uses `.fetchall_rows()`, `.fetch_arrow_table()`, etc.
10. On `SemolinaCursor.close()` or `__exit__`: close cursor, release connection to pool

### Data Flow: MockPool

1. Same query chain as above
2. Registry returns `(MockPool, MockDialect)`
3. SQL generation still runs (for `.to_sql()` correctness testing)
4. `MockPool.acquire()` returns `MockConnection` (lightweight)
5. `MockConnection.cursor()` returns `MockCursor` holding fixture data
6. Execution path detects MockPool and passes the `_Query` object for predicate evaluation (MockCursor does not parse SQL)
7. Wrap in `SemolinaCursor(mock_cursor, mock_conn, mock_pool)`
8. `.fetchall_rows()` returns `list[Row]` from filtered fixtures
9. `.fetch_arrow_table()` converts fixture dicts to `pyarrow.Table` (requires pyarrow)

---

## 3. Module Design Details

### 3.1 Pool Protocol (`src/semolina/pool.py`)

```python
from __future__ import annotations
from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class Pool(Protocol):
    """Connection pool protocol. Implementations manage ADBC connection lifecycle."""

    def acquire(self) -> Any:
        """Get a connection from the pool."""
        ...

    def release(self, conn: Any) -> None:
        """Return a connection to the pool."""
        ...

    def close(self) -> None:
        """Close all connections and shut down the pool."""
        ...
```

**Why Protocol over ABC:**
- MockPool does not use real ADBC connections -- structural typing avoids forcing fake inheritance
- Third-party pool implementations work without subclassing
- Protocol is more Pythonic for a 3-method interface

**SnowflakePool implementation strategy:**
- Constructor takes `db_kwargs` matching `adbc_driver_snowflake.dbapi.connect()` options (account, username, password via `adbc.snowflake.sql.*` keys)
- Creates a "source" connection lazily on first `acquire()` -- not at construction time
- Uses `source.adbc_clone()` for subsequent connections (shares internal driver state, saves overhead)
- Maintains a LIFO stack of idle connections protected by `threading.Lock`
- `pool_size` parameter caps max idle connections (default 5)
- Lazy import of `adbc_driver_snowflake` (same pattern as current SnowflakeEngine)

**DatabricksPool implementation strategy:**
- Constructor takes URI (`grpc+tls://host:443`) + `db_kwargs` for `adbc_driver_flightsql.dbapi.connect()`
- Token auth via `DatabaseOptions.AUTHORIZATION_HEADER`: `"Bearer <token>"`
- Same clone-based pooling as SnowflakePool

**Why not SQLAlchemy QueuePool:**
Adding SQLAlchemy as a dependency for one class is excessive overhead. The pool logic is approximately 50 lines. A simple LIFO stack with `threading.Lock` is sufficient for Semolina's use case (analytics queries, not high-concurrency web servers). The ADBC PostgreSQL cookbook's QueuePool example is a reference pattern, not a required dependency.

**adbc_clone() availability note (MEDIUM confidence):**
The `adbc_clone()` method is documented in the ADBC driver manager and explicitly used in the PostgreSQL pool recipe. Snowflake driver support for `adbc_clone()` is not directly documented but is expected since it is part of the ADBC DBAPI standard. **Phase-specific research should verify this during SnowflakePool implementation.** Fallback: create new connections via `connect()` each time (slower but correct).

### 3.2 SemolinaCursor (`src/semolina/cursor.py`)

```python
class SemolinaCursor:
    """
    Wraps an ADBC DBAPI cursor with Semolina convenience methods.

    Primary API is Arrow-native:
      .fetch_arrow_table()           -> pyarrow.Table
      .fetch_record_batch_reader()   -> pyarrow.RecordBatchReader

    Convenience API converts to Row objects:
      .fetchall_rows()   -> list[Row]
      .fetchmany_rows(n) -> list[Row]
      .fetchone_row()    -> Row | None

    Properties:
      .description   -> cursor.description passthrough
      .rowcount      -> cursor.rowcount passthrough

    Context manager: releases connection back to pool on exit.
    """

    def __init__(self, cursor, conn, pool):
        self._cursor = cursor
        self._conn = conn
        self._pool = pool

    # -- Arrow-native (primary) --
    def fetch_arrow_table(self):
        """Return all results as a pyarrow.Table."""
        return self._cursor.fetch_arrow_table()

    def fetch_record_batch_reader(self):
        """Return a RecordBatchReader for streaming large results."""
        # ADBC cursors expose Arrow C Stream via internal handle
        # Implementation: pyarrow.RecordBatchReader.from_stream(handle)
        ...

    # -- Row convenience (sugar over Arrow) --
    def fetchall_rows(self) -> list[Row]:
        """Fetch all results as Row objects."""
        table = self._cursor.fetch_arrow_table()
        return _arrow_table_to_rows(table)

    def fetchone_row(self) -> Row | None:
        """Fetch one result as a Row, or None if exhausted."""
        raw = self._cursor.fetchone()
        if raw is None:
            return None
        columns = [desc[0] for desc in self._cursor.description]
        return Row(dict(zip(columns, raw)))

    def fetchmany_rows(self, size: int | None = None) -> list[Row]:
        """Fetch up to `size` results as Rows."""
        raw = self._cursor.fetchmany(size or self._cursor.arraysize)
        columns = [desc[0] for desc in self._cursor.description]
        return [Row(dict(zip(columns, r))) for r in raw]

    # -- DBAPI passthrough --
    @property
    def description(self): return self._cursor.description

    @property
    def rowcount(self): return self._cursor.rowcount

    # -- Lifecycle --
    def close(self):
        self._cursor.close()
        self._pool.release(self._conn)

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
```

**Key design decisions:**

1. **Arrow is primary, Row is sugar.** `fetch_arrow_table()` delegates directly to the ADBC cursor extension method. `fetchall_rows()` converts Arrow -> Row as convenience. This matches the project's v0.3 direction.

2. **SemolinaCursor owns connection lifecycle.** When closed, it releases the connection back to the pool. Context manager support (`with cursor:`) is the recommended pattern to prevent connection leaks.

3. **Same interface for MockPool and real pools.** SemolinaCursor wraps MockCursor identically to real ADBC cursors. The mock implementations provide the same method signatures.

4. **`_arrow_table_to_rows()` helper.** Converts `pyarrow.Table` to `list[Row]` by iterating columns:
   ```python
   def _arrow_table_to_rows(table) -> list[Row]:
       columns = table.column_names
       return [
           Row(dict(zip(columns, [table.column(c)[i].as_py() for c in columns])))
           for i in range(table.num_rows)
       ]
   ```

### 3.3 Registry Changes (`src/semolina/registry.py`)

Current:
```python
_engines: dict[str, Any] = {}

def register(name: str, engine: Any) -> None: ...
def get_engine(name: str | None = None) -> Any: ...
```

New:
```python
_pools: dict[str, tuple[Pool, Dialect]] = {}

_DIALECT_MAP: dict[str, type[Dialect]] = {
    "snowflake": SnowflakeDialect,
    "databricks": DatabricksDialect,
    "mock": MockDialect,
}

def register(name: str, pool: Pool, *, dialect: str | Dialect) -> None:
    """
    Register a pool with its dialect.

    Args:
        name: Registration name ("default", "warehouse", etc.)
        pool: Pool instance (SnowflakePool, DatabricksPool, MockPool)
        dialect: String shorthand ("snowflake") or Dialect instance
    """
    resolved = _resolve_dialect(dialect)
    _pools[name] = (pool, resolved)

def get_pool(name: str | None = None) -> tuple[Pool, Dialect]:
    """Get (pool, dialect) by name, or default."""
    ...

def unregister(name: str) -> None: ...
def reset() -> None: ...
```

**Why dialect is a separate parameter:**
- In v0.2, dialect was baked into Engine (SnowflakeEngine always uses SnowflakeDialect)
- In v0.3, the pool manages connections -- it does not know about SQL syntax
- Dialect must be specified at registration time because SQL generation depends on it
- String shorthand (`dialect="snowflake"`) is ergonomic for the common case
- Dialect instances allow customization for edge cases

**Backward compatibility approach:**
Clean break. `register(name, engine)` without `dialect=` raises `TypeError`. Engine classes are deprecated but still importable. This is a major version change (v0.2 -> v0.3); breaking the registration API is acceptable.

### 3.4 MockPool Design (`src/semolina/engines/mock.py`)

MockPool is the most nuanced component because it must:
- Satisfy the `Pool` protocol (acquire/release/close)
- Expose the same cursor API that SemolinaCursor depends on
- Evaluate predicates in-memory (reusing existing `_eval_predicate`)
- Work without PyArrow for basic `fetchall_rows()` testing
- Produce identical SemolinaCursor behavior as real pools

```python
class MockPool:
    """Connection pool for testing without warehouse connections."""

    def __init__(self):
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def load(self, view_name: str, data: list[dict[str, Any]]) -> None:
        """Load fixture data for a semantic view."""
        self._fixtures[view_name] = data

    def acquire(self) -> MockConnection:
        return MockConnection(self._fixtures)

    def release(self, conn: MockConnection) -> None:
        pass  # No-op: MockConnection is stateless

    def close(self) -> None:
        pass


class MockConnection:
    """Lightweight in-memory connection."""

    def __init__(self, fixtures):
        self._fixtures = fixtures

    def cursor(self) -> MockCursor:
        return MockCursor(self._fixtures)

    def close(self): pass


class MockCursor:
    """
    In-memory cursor that evaluates predicates against fixture data.

    Implements the ADBC cursor subset that SemolinaCursor depends on:
    - execute() -- no-op for mock (data set via _execute_query)
    - fetch_arrow_table() -- converts fixtures to pyarrow.Table
    - fetchone() / fetchmany() / fetchall() -- standard DBAPI
    - description -- column metadata
    - rowcount -- result count
    - arraysize -- batch size for fetchmany
    """

    def __init__(self, fixtures):
        self._fixtures = fixtures
        self._result_rows: list[dict[str, Any]] = []
        self._description: list[tuple[str, ...]] | None = None
        self._pos = 0
        self.arraysize = 1

    def _execute_query(self, query: _Query) -> None:
        """
        Evaluate query predicates against fixture data.

        Called by _Query.execute() when it detects a MockPool.
        Reuses _eval_predicate for in-memory filtering.
        """
        view_name = _extract_view_name(query)
        rows = self._fixtures.get(view_name, [])
        if query._filters is not None:
            rows = [r for r in rows if _eval_predicate(query._filters, r)]
        self._result_rows = rows
        if rows:
            cols = list(rows[0].keys())
            self._description = [(c, None, None, None, None, None, None) for c in cols]

    def execute(self, sql: str, params=None):
        """No-op for mock. Data is set via _execute_query."""
        pass

    def fetch_arrow_table(self):
        """Convert fixture dicts to pyarrow.Table."""
        import pyarrow as pa
        if not self._result_rows:
            return pa.table({})
        cols = list(self._result_rows[0].keys())
        arrays = {c: [row.get(c) for row in self._result_rows] for c in cols}
        return pa.table(arrays)

    def fetchone(self):
        if self._pos >= len(self._result_rows):
            return None
        row = self._result_rows[self._pos]
        self._pos += 1
        return tuple(row.values())

    def fetchmany(self, size=None):
        size = size or self.arraysize
        rows = self._result_rows[self._pos:self._pos + size]
        self._pos += len(rows)
        return [tuple(r.values()) for r in rows]

    def fetchall(self):
        rows = self._result_rows[self._pos:]
        self._pos = len(self._result_rows)
        return [tuple(r.values()) for r in rows]

    @property
    def description(self):
        return self._description

    @property
    def rowcount(self):
        return len(self._result_rows)

    def close(self): pass
```

**Mock execution path -- the key design challenge:**

MockCursor.execute() receives `(sql, params)` strings, but predicate evaluation needs the `_Query` object's Predicate tree. The solution:

```python
# In _Query.execute():
pool, dialect = get_pool(self._using)
sql, params = SQLBuilder(dialect).build_select_with_params(self)
conn = pool.acquire()
cur = conn.cursor()

if isinstance(pool, MockPool):
    cur._execute_query(self)  # passes _Query for predicate evaluation
else:
    cur.execute(sql, params)

return SemolinaCursor(cur, conn, pool)
```

This is the **only** place where `isinstance(pool, MockPool)` appears. The rest of the code path (SemolinaCursor, Row conversion, Arrow fetch) is identical for mock and real pools.

**PyArrow in MockPool:** `fetch_arrow_table()` does a lazy `import pyarrow`. If PyArrow is not installed, it raises `ImportError` with a helpful message. `fetchall_rows()` works without PyArrow because `SemolinaCursor.fetchall_rows()` can fall back to DBAPI `fetchall()` + Row conversion when `fetch_arrow_table()` is unavailable. However, the simpler implementation path is: MockCursor's fetchall() returns tuples, SemolinaCursor converts to Rows. No Arrow involved for the Row path.

### 3.5 Config Module (`src/semolina/config.py`)

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class SnowflakePoolConfig(BaseSettings):
    """Snowflake pool config from .semolina.toml [snowflake] + env vars."""
    model_config = SettingsConfigDict(
        env_prefix="SNOWFLAKE_",
        toml_file=".semolina.toml",
        toml_table_header="snowflake",
    )
    account: str
    user: str
    password: SecretStr
    warehouse: str
    database: str
    role: str | None = None
    schema_: str | None = None  # alias "schema"
    pool_size: int = 5

class DatabricksPoolConfig(BaseSettings):
    """Databricks pool config from .semolina.toml [databricks] + env vars."""
    model_config = SettingsConfigDict(
        env_prefix="DATABRICKS_",
        toml_file=".semolina.toml",
        toml_table_header="databricks",
    )
    server_hostname: str
    http_path: str
    access_token: SecretStr
    catalog: str = "main"
    pool_size: int = 5

def pool_from_config(
    section: str = "default",
    config_path: str = ".semolina.toml",
) -> tuple[Pool, Dialect]:
    """
    Create (Pool, Dialect) from .semolina.toml config.

    Reads [snowflake] or [databricks] section, infers dialect,
    constructs the appropriate Pool.

    Returns:
        (Pool, Dialect) tuple ready for register().
    """
    ...
```

**Relationship to existing credentials:**
`testing/credentials.py` already loads `.semolina.toml` sections via `tomllib`. The new config module uses pydantic-settings `TomlConfigSettingsSource` for cleaner integration with env var fallback. The credentials classes can coexist -- they serve the testing use case while config serves the production pool creation use case.

**TOML format (backward-compatible with existing .semolina.toml.example):**
```toml
[snowflake]
account = "xy12345.us-east-1"
user = "myuser"
password = "secret"
warehouse = "compute_wh"
database = "analytics"
pool_size = 5  # NEW field, optional

[databricks]
server_hostname = "workspace.cloud.databricks.com"
http_path = "/sql/1.0/warehouses/abc123"
access_token = "dapi..."
pool_size = 5  # NEW field, optional
```

### 3.6 _Query.execute() -- The Central Change

Current (v0.2):
```python
def execute(self) -> Result:
    from .registry import get_engine
    from .results import Result, Row
    self._validate_for_execution()
    engine = get_engine(self._using)
    raw_results = engine.execute(self)
    rows = [Row(data) for data in raw_results]
    return Result(rows)
```

New (v0.3):
```python
def execute(self) -> SemolinaCursor:
    from .cursor import SemolinaCursor
    from .engines.mock import MockPool
    from .engines.sql import SQLBuilder
    from .registry import get_pool

    self._validate_for_execution()
    pool, dialect = get_pool(self._using)
    sql, params = SQLBuilder(dialect).build_select_with_params(self)
    conn = pool.acquire()
    cur = conn.cursor()

    if isinstance(pool, MockPool):
        cur._execute_query(self)
    else:
        cur.execute(sql, params)

    return SemolinaCursor(cur, conn, pool)
```

**Breaking change:** Return type changes from `Result` to `SemolinaCursor`.

User migration:
```python
# v0.2:
result = Sales.query().metrics(Sales.revenue).execute()
for row in result:
    print(row.revenue)

# v0.3:
with Sales.query().metrics(Sales.revenue).execute() as cursor:
    for row in cursor.fetchall_rows():
        print(row.revenue)
```

### 3.7 query() Shorthand

New convenience on `SemanticView.query()` and `_Query()`:

```python
# Current (verbose):
Sales.query().metrics(Sales.revenue, Sales.cost).dimensions(Sales.country)

# New shorthand:
Sales.query(metrics=[Sales.revenue, Sales.cost], dimensions=[Sales.country])
```

Implementation: `SemanticView.query()` accepts optional `metrics` and `dimensions` kwargs, applies them to the initial `_Query` before returning it. This is pure sugar -- no architectural impact.

---

## 4. Patterns to Follow

### Pattern 1: Pool as Context Manager
```python
pool = SnowflakePool(db_kwargs={...}, pool_size=5)
semolina.register("default", pool, dialect="snowflake")
# ... application runs ...
pool.close()  # or: with pool: ...
```

### Pattern 2: Cursor as Context Manager (recommended usage)
```python
with Sales.query().metrics(Sales.revenue).execute() as cursor:
    table = cursor.fetch_arrow_table()
    # Connection automatically released back to pool
```

### Pattern 3: Lazy Driver Import
```python
class SnowflakePool:
    def __init__(self, **db_kwargs):
        try:
            import adbc_driver_snowflake.dbapi
        except ImportError as e:
            raise ImportError(
                "adbc-driver-snowflake is required. "
                "Install with: pip install semolina[snowflake]"
            ) from e
        self._driver = adbc_driver_snowflake.dbapi
        self._db_kwargs = db_kwargs
```

### Pattern 4: Dialect Resolution from String
```python
_DIALECT_MAP = {
    "snowflake": SnowflakeDialect,
    "databricks": DatabricksDialect,
    "mock": MockDialect,
}

def _resolve_dialect(dialect: str | Dialect) -> Dialect:
    if isinstance(dialect, Dialect):
        return dialect
    return _DIALECT_MAP[dialect]()
```

---

## 5. Anti-Patterns to Avoid

### Anti-Pattern 1: Pool Knows About SQL
**What:** Pool classes generating SQL or knowing about Dialect.
**Why bad:** Violates separation of concerns. Pool manages connections; SQLBuilder generates SQL.
**Instead:** Pool.acquire() returns a raw connection. SQL generation happens in _Query.execute() before acquire().

### Anti-Pattern 2: Eager Connection at Pool Construction
**What:** Creating ADBC connections in Pool.__init__().
**Why bad:** Fails at import/construction time if warehouse is unreachable. Makes unit testing harder.
**Instead:** Lazy initialization -- first real connection on first acquire().

### Anti-Pattern 3: SemolinaCursor Holds _Query Reference
**What:** Storing the entire _Query object on SemolinaCursor for later use.
**Why bad:** Couples cursor to query internals. Makes cursor API leak query details.
**Instead:** SemolinaCursor only holds cursor + connection + pool. Query is consumed during execute().

### Anti-Pattern 4: MockCursor Parses SQL
**What:** MockCursor parsing the SQL string to figure out what data to return.
**Why bad:** Fragile, complex, would need a SQL parser. Defeats purpose of mock testing.
**Instead:** MockCursor receives structured query data (the _Query object) via `_execute_query()`. SQL generation still runs for `.to_sql()` correctness testing.

### Anti-Pattern 5: PyArrow as Hard Dependency for Testing
**What:** Requiring PyArrow for all Semolina usage including MockPool basic operations.
**Why bad:** PyArrow is large (~150MB). Users doing basic mock testing should not need it.
**Instead:** PyArrow is optional. `fetch_arrow_table()` raises ImportError with helpful message if not installed. `fetchall_rows()` works without PyArrow via standard DBAPI fetchall() path.

---

## 6. Module Structure (Complete)

```
src/semolina/
    __init__.py              # Updated exports (SemolinaCursor, Pool, pool_from_config)
    pool.py                  # NEW: Pool protocol, SnowflakePool, DatabricksPool
    cursor.py                # NEW: SemolinaCursor wrapper
    config.py                # NEW: TomlSettingsSource configs, pool_from_config()
    registry.py              # MODIFIED: stores (Pool, Dialect) tuples
    query.py                 # MODIFIED: .execute() returns SemolinaCursor
    results.py               # MINOR: Row unchanged, Result used by fetchall_rows
    models.py                # MINOR: query() gains metrics/dimensions kwargs
    fields.py                # UNCHANGED
    filters.py               # UNCHANGED
    engines/
        __init__.py          # Updated exports
        base.py              # DEPRECATED (Engine ABC stays importable)
        sql.py               # UNCHANGED (Dialect + SQLBuilder)
        mock.py              # MODIFIED: MockPool, MockConnection, MockCursor added
                             # MockEngine stays but deprecated
        snowflake.py         # DEPRECATED (SnowflakeEngine stays for introspect)
        databricks.py        # DEPRECATED (DatabricksEngine stays for introspect)
    codegen/                 # UNCHANGED
    testing/                 # UNCHANGED
    cli/                     # UNCHANGED
```

---

## 7. Build Order (Dependency-Aware)

Each phase can be tested independently before moving to the next.

### Phase 1: Pool Protocol + MockPool (zero external dependencies)

**Build:**
1. `Pool` Protocol in `pool.py`
2. `MockPool`, `MockConnection`, `MockCursor` in `engines/mock.py`
   - Reuses existing `_eval_predicate` function
   - No PyArrow dependency for basic path

**Tests:**
- Pool protocol compliance (isinstance checks)
- MockPool.load() + MockCursor._execute_query() with predicates
- MockCursor.fetchone() / fetchmany() / fetchall() with fixture data

**Dependencies:** Only existing semolina internals (filters, fields).

### Phase 2: SemolinaCursor (depends on Phase 1)

**Build:**
3. `SemolinaCursor` in `cursor.py`
   - Arrow methods + Row convenience methods
   - Context manager lifecycle

**Tests:**
- SemolinaCursor wrapping MockCursor: fetchall_rows(), fetchone_row()
- SemolinaCursor.fetch_arrow_table() with MockCursor (requires pyarrow in test env)
- Context manager: close() releases connection
- Edge cases: empty results, single row, large results

**Dependencies:** Phase 1 (MockPool), results.py (Row).

### Phase 3: Registry + Query Changes (depends on Phases 1-2)

**Build:**
4. Modified `registry.py` -- (Pool, Dialect) storage, dialect string resolution
5. Modified `query.py` -- execute() returns SemolinaCursor

**Tests:**
- register(name, pool, dialect="mock") + get_pool(name) round-trip
- Full flow: Sales.query().metrics(Sales.revenue).execute() -> SemolinaCursor -> Rows
- MockPool predicate evaluation through full query chain
- .to_sql() still works (unchanged)
- .using("name") resolves correct pool

**Dependencies:** Phases 1-2, engines/sql.py (Dialect, SQLBuilder).

### Phase 4: Real Pools (depends on Phases 1-3)

**Build:**
6. `SnowflakePool` in `pool.py`
7. `DatabricksPool` in `pool.py`

**Tests:**
- Unit tests with mocked ADBC driver modules
- Integration tests with real warehouse credentials (CI-only)
- Pool lifecycle: acquire/release/close
- adbc_clone() behavior verification
- Connection reuse verification

**Dependencies:** Phases 1-3, adbc-driver-snowflake, adbc-driver-flightsql.

### Phase 5: Config (depends on Phase 4)

**Build:**
8. `config.py` -- SnowflakePoolConfig, DatabricksPoolConfig, pool_from_config()

**Tests:**
- TOML parsing with pydantic-settings
- Environment variable override
- pool_from_config() creates correct pool type
- Integration: pool_from_config() -> register() -> query.execute()

**Dependencies:** Phase 4 (Pool constructors), pydantic-settings.

### Phase 6: query() Shorthand + Deprecation + Exports

**Build:**
9. query() shorthand kwargs
10. Deprecation warnings on Engine classes
11. Updated `__init__.py` exports

**Tests:**
- Shorthand produces same _Query as fluent chain
- Deprecation warnings emit correctly
- All new public API items importable from `semolina`

---

## 8. PyArrow Dependency Management

PyArrow is a transitive dependency of both ADBC driver packages:
- `adbc-driver-snowflake` requires pyarrow for DBAPI interface
- `adbc-driver-flightsql` requires pyarrow for DBAPI interface

```toml
# pyproject.toml -- updated extras
[project.optional-dependencies]
snowflake = ["adbc-driver-snowflake>=1.0.0"]
databricks = ["adbc-driver-flightsql>=1.0.0"]
all = ["semolina[snowflake,databricks]"]
```

**No core dependency on pyarrow.** The base `semolina` package (without extras) does not require pyarrow. MockPool's `fetch_arrow_table()` does a lazy import. This means:
- `pip install semolina` -- works, MockPool only, no Arrow
- `pip install semolina[snowflake]` -- pulls pyarrow via adbc-driver-snowflake
- `pip install semolina[databricks]` -- pulls pyarrow via adbc-driver-flightsql

---

## 9. Introspection Continuity

The `introspect()` method currently lives on SnowflakeEngine and DatabricksEngine. In v0.3:

**Recommendation: Keep introspection on Engine classes.**
- Introspection is a CLI codegen feature, not a query execution feature
- It uses the old snowflake-connector-python / databricks-sql-connector drivers
- Migrating it to ADBC pools is a separate concern (ADBC introspection APIs exist but differ)
- Engine classes remain importable (deprecated for query execution, still valid for introspection)

The CLI command `semolina codegen` continues to instantiate SnowflakeEngine/DatabricksEngine for introspection. This is fine -- the CLI is a development tool, not a production query path.

---

## 10. Scalability Considerations

| Concern | At 10 queries/sec | At 100 queries/sec | At 1000 queries/sec |
|---------|-------------------|--------------------|---------------------|
| Pool size | Default 5, ample | May need 10-20 | Async pools needed (out of scope) |
| Connection overhead | Negligible with adbc_clone | Fast clone creation | Consider connection warmup |
| Arrow memory | Single Table in memory | Multiple Tables | Use RecordBatchReader for streaming |
| MockPool | Instant, zero overhead | Instant | Instant |
| Thread safety | Lock on acquire/release | Lock contention minimal | Consider per-thread pools |

For Semolina's use case (analytics dashboards, BI backends), the default pool size of 5 with synchronous acquisition is more than sufficient. Async query execution is explicitly out of scope per PROJECT.md.

---

## 11. Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| ADBC cursor API (fetch_arrow_table, fetchone, etc.) | HIGH | Verified via official ADBC documentation across multiple versions |
| adbc-driver-snowflake exists and works | HIGH | Published on PyPI v1.9.0 (Nov 2025), actively maintained |
| adbc-driver-flightsql for Databricks | HIGH | Published on PyPI (Jan 2026), documented for Databricks specifically |
| adbc_clone() for connection pooling | MEDIUM | Documented in ADBC PostgreSQL recipe; Snowflake/FlightSQL support needs verification |
| "adbc-poolhouse" as external library | LOW | Does not exist as a published package; name is likely project-internal shorthand |
| pydantic-settings TomlConfigSettingsSource | HIGH | Verified in pydantic-settings official docs |
| Pool protocol design | HIGH | Based on established patterns (SQLAlchemy QueuePool, psycopg pool) |
| MockPool cursor API compatibility | HIGH | Straightforward: dict-to-tuple conversion matches DBAPI spec |
| Build order feasibility | HIGH | Each phase has clear dependencies and can be tested independently |

---

## Sources

- [ADBC Driver Manager Python API (v21)](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html)
- [ADBC Quickstart (Python)](https://arrow.apache.org/adbc/current/python/quickstart.html)
- [ADBC PostgreSQL Connection Pool Recipe](https://github.com/apache/arrow-adbc/blob/main/docs/source/python/recipe/postgresql_pool.py)
- [ADBC Snowflake Driver Documentation](https://arrow.apache.org/adbc/current/driver/snowflake.html)
- [adbc-driver-snowflake on PyPI](https://pypi.org/project/adbc-driver-snowflake/)
- [adbc-driver-flightsql on PyPI](https://pypi.org/project/adbc-driver-flightsql/)
- [adbc-driver-flightsql API docs](https://arrow.apache.org/adbc/current/python/api/adbc_driver_flightsql.html)
- [Apache Arrow ADBC GitHub Repository](https://github.com/apache/arrow-adbc)
- [pydantic-settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [PyArrow RecordBatchReader API](https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatchReader.html)
- [SQLAlchemy Connection Pooling (reference pattern)](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [ADBC Arrow Driver for Databricks (blog post)](https://dataengineeringcentral.substack.com/p/adbc-arrow-driver-for-databricks)
