# Feature Landscape: Semolina v0.3 Arrow & Connection Layer

**Domain:** Arrow-native cursor API, ADBC connection pooling, SemolinaCursor wrapper
**Researched:** 2026-03-16
**Research Mode:** Ecosystem (ADBC cursor API, Arrow result patterns, cursor wrapper design)
**Overall Confidence:** HIGH (ADBC API verified via official docs; connection patterns proven in ecosystem)

## Executive Summary

v0.3 replaces Semolina's hand-rolled Engine ABC with ADBC-based connection pools and evolves `.execute()` from returning eagerly-materialized `Result` objects to returning a `SemolinaCursor` that wraps the underlying ADBC cursor. This cursor provides three tiers of access: (1) Arrow-native methods (`fetch_arrow_table()`, `fetch_record_batch_reader()`) for zero-copy columnar access, (2) Row convenience methods (`fetchall_rows()`, `fetchmany_rows()`, `fetchone_row()`) that convert Arrow data to Semolina's existing `Row` objects, and (3) standard PEP 249 passthrough (`fetchall()`, `fetchone()`, `fetchmany()`) for raw tuple access.

The ADBC cursor API is well-documented and stable (version 21+). It implements PEP 249 (DB-API 2.0) with Arrow-specific extensions: `fetch_arrow_table()` returns a `pyarrow.Table`, and `fetch_record_batch_reader()` returns a `pyarrow.RecordBatchReader` for streaming. A critical design constraint is cursor lifetime management: the cursor MUST remain alive while a `RecordBatchReader` is being consumed, which has implications for SemolinaCursor's context manager implementation.

---

## Table Stakes

Features users expect from an Arrow-native ORM cursor. Missing = product feels incomplete or users bypass SemolinaCursor entirely.

| Feature | Why Expected | Complexity | Notes |
|---------|-------------|------------|-------|
| **SemolinaCursor wrapping ADBC cursor** | Core v0.3 deliverable; thin wrapper adding Row convenience without hiding Arrow power | Medium | Wraps `adbc_driver_manager.dbapi.Cursor` |
| **`fetch_arrow_table()`** | Primary Arrow-native access; returns `pyarrow.Table` -- the reason to use ADBC over raw connectors | Low | Direct delegation to ADBC cursor |
| **`fetch_record_batch_reader()`** | Streaming access for large results; returns `pyarrow.RecordBatchReader` | Low | Must manage cursor lifetime (cursor stays open until reader consumed) |
| **`fetchall_rows()` -> `list[Row]`** | Bridge from Arrow to Semolina's existing `Row` objects; backward compat with v0.2 | Medium | `pyarrow.Table.to_pylist()` -> `[Row(d) for d in dicts]` |
| **`fetchone_row()` -> `Row | None`** | Single-row convenience (e.g. aggregate queries) | Low | `fetchone()` tuple -> `Row` via column names from description |
| **`fetchmany_rows(size)` -> `list[Row]`** | Batched Row access for pagination patterns | Low | `fetchmany(size)` tuples -> `Row` via column names |
| **Context manager protocol** | `with cursor:` ensures proper cleanup -- ADBC cursors MUST be closed or resources leak | Low | `__enter__`/`__exit__` delegating to inner cursor |
| **`description` property** | PEP 249 standard; column metadata after execute | Low | Passthrough to ADBC cursor |
| **`close()` method** | Explicit resource cleanup | Low | Delegates to inner cursor |
| **MockPool for testing** | Users need to test without warehouse; replaces MockEngine | Medium | Must produce mock cursors returning Arrow Tables from fixture data |
| **Pool registry with dialect** | `register("default", pool, dialect="snowflake")` -- dialect tag replaces Engine subclass dispatch | Medium | Extends existing registry.py |
| **`.execute()` returns `SemolinaCursor`** | Query builder integration point | Medium | Breaking change from v0.2's `Result` return |
| **Parameterized query execution** | ADBC cursor.execute() accepts params; Semolina already builds parameterized SQL | Low | Pass `(sql_template, params)` from `build_select_with_params()` |
| **Dialect enum** | `Dialect.SNOWFLAKE`, `Dialect.DATABRICKS`, `Dialect.MOCK` | Low | Simple StrEnum replacing per-engine dialect class dispatch |
| **TOML config via TomlConfigSettingsSource** | Declarative pool configuration from `.semolina.toml` | Medium | pydantic-settings loads TOML natively on Python 3.11+ |
| **`pool_from_config()` helper** | One-liner to create a pool from TOML config | Low | Reads config, determines dialect, creates ADBC connection |
| **`query(metrics=..., dimensions=...)` shorthand** | Syntactic sugar listed in PROJECT.md targets | Low | Sugar over `Model.query().metrics(...).dimensions(...)` |

---

## Differentiators

Features that go beyond basic connection replacement and provide real value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Zero-copy Arrow transport** | ADBC returns Arrow buffers directly. No tuple-to-dict-to-Row overhead. | Built into ADBC | Major performance win for large results. |
| **Streaming results via RecordBatchReader** | Process millions of rows without full materialization. | Low (delegation) | ADBC cursor's `fetch_record_batch_reader()`. |
| **Connection reuse via adbc_clone()** | Shares internal driver resources (session state, caches). | Medium (pool impl) | Pool factory calls `source_conn.adbc_clone()`. |
| **Unified config for all backends** | Single `.semolina.toml` configures Snowflake and Databricks. | Medium | pydantic-settings handles validation. |
| **`to_dicts()` convenience** | Returns `list[dict]` directly -- avoids Row overhead when users just want dicts | Low | `pyarrow.Table.to_pylist()` |
| **Iterable cursor `__iter__`** | `for row in cursor:` yields `Row` -- Pythonic iteration pattern | Medium | Iterate RecordBatchReader batches, convert to Row |
| **`schema` property (Arrow schema)** | Typed column metadata: `cursor.schema` -> `pyarrow.Schema` | Low | From table or reader |
| **`column_names` property** | Quick access: `cursor.column_names` -> `list[str]` | Low | From description |
| **Cursor `__repr__`** | Informative: `<SemolinaCursor query=<Query...> columns=['revenue', 'country']>` | Low | Read from description |

---

## Anti-Features

Features to explicitly NOT build in v0.3.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Async cursor / async pool** | ADBC is sync. Architectural change for entire API surface. | Defer to post-v0.3. Keep sync-only. |
| **`to_pandas()` / `to_polars()` on cursor** | Creates implicit dependency on heavy optional packages. | Expose Arrow Table. Users call `table.to_pandas()` themselves. |
| **Automatic query retries** | Retry logic is complex (idempotency, backoff). Out of scope. | Let errors propagate. Users add tenacity at their layer. |
| **Connection health checks** | ADBC analytics connections are not long-lived OLTP pools. | Stale connections fail on use; pool creates new one. |
| **SQLAlchemy integration** | Heavy dependency. Semolina is not an ORM over SQLAlchemy. | Build minimal pool. |
| **Multiple TOML file merging** | Over-engineering. | Single `.semolina.toml`. Env vars override fields. |
| **Raw SQL execution on SemolinaCursor** | Bypasses query builder and type safety. | Users use ADBC directly for raw SQL. |
| **Multi-statement / `executemany()`** | Semolina is read-only (semantic views). | Not exposed. |
| **Automatic schema inference for typed Row** | Breaks basedpyright strict; complex runtime TypedDict. | Row stays `Any`-typed. Consider codegen for typed results later. |
| **Result pagination / server-side cursors** | Application concern, not ORM concern. | Use RecordBatchReader for streaming. |

---

## Feature Dependencies

```
Dialect enum -> Pool registry (registry needs dialect to tag pools)
Pool registry -> _Query.execute() integration (execute resolves pool from registry)
ADBC driver connect -> Pool implementation (pool wraps ADBC connections)
SemolinaCursor -> fetch_arrow_table / fetchall_rows (cursor methods)
SemolinaCursor -> _Query.execute() (execute returns SemolinaCursor)
TomlConfigSettingsSource -> pool_from_config() (config loading precedes pool)
MockPool -> SemolinaCursor (MockPool produces cursors with same interface)
Pool protocol -> MockPool (MockPool implements pool protocol)
_eval_predicate (existing) -> MockPool (reuse for WHERE filtering in mock)
query() shorthand -> _Query (sugar, depends on existing query builder)
```

### Critical Path

```
Dialect enum -> Pool protocol -> Pool registry -> ADBC pool impl -> SemolinaCursor -> .execute() wiring -> MockPool -> Tests
                                                                                            |
                                                  TomlConfigSettingsSource -> pool_from_config() (parallel track)
                                                                                            |
                                                                          query() shorthand (independent, last)
```

---

## SemolinaCursor Design Recommendation

### Tier 1: Arrow-Native (Zero Overhead)

Direct delegation to ADBC cursor. No conversion.

```python
cursor = Sales.query().metrics(Sales.revenue).execute()

# Full materialization as Arrow Table
table: pyarrow.Table = cursor.fetch_arrow_table()

# Streaming as RecordBatchReader
reader: pyarrow.RecordBatchReader = cursor.fetch_record_batch_reader()
for batch in reader:
    ...
```

### Tier 2: Row Convenience (Semolina-Native)

Converts Arrow data to Semolina's `Row` objects. Small overhead, preserves v0.2 UX.

```python
rows: list[Row] = cursor.fetchall_rows()
for row in rows:
    print(row.revenue, row.country)

row: Row | None = cursor.fetchone_row()
rows: list[Row] = cursor.fetchmany_rows(100)
```

### Properties and Lifecycle

```python
cursor.description   # PEP 249 column metadata
cursor.schema        # pyarrow.Schema (Arrow-native metadata)
cursor.column_names  # list[str] shortcut

# Context manager
with Sales.query().metrics(Sales.revenue).execute() as cursor:
    table = cursor.fetch_arrow_table()
# cursor auto-closed

# Or explicit close
cursor = Sales.query().metrics(Sales.revenue).execute()
try:
    rows = cursor.fetchall_rows()
finally:
    cursor.close()
```

---

## MockPool Feature Requirements

| Feature | Why Required | Implementation |
|---------|-------------|----------------|
| Load fixture data | `pool.load("view", [...])` -- same as MockEngine | Store as `dict[str, list[dict]]` |
| Return Arrow data | Mock cursor `fetch_arrow_table()` returns real `pyarrow.Table` | `pyarrow.Table.from_pylist(fixtures)` |
| Support RecordBatchReader | Mock cursor `fetch_record_batch_reader()` | `table.to_reader()` |
| Evaluate WHERE predicates | Reuse `_eval_predicate` from existing MockEngine | Filter fixtures before Arrow conversion |
| Row convenience methods | `fetchall_rows()` etc. must work identically | Implemented in SemolinaCursor, not mock |

**Key insight:** If Row conversion lives in SemolinaCursor (not the underlying cursor), MockPool only needs to produce a cursor that correctly implements `fetch_arrow_table()`. Row logic lives in one place.

---

## MVP Recommendation

Prioritize (in dependency order):
1. **Dialect enum + Pool protocol** -- foundational
2. **Pool registry** -- extends existing registry.py
3. **ADBC connection creation for both backends** -- validates Snowflake/Databricks work through ADBC
4. **SemolinaCursor wrapper** -- primary user-facing API change
5. **MockPool** -- enables testing everything else without warehouse
6. **`.execute()` integration** -- wires cursor into query builder
7. **TOML config + `pool_from_config()`** -- user-facing configuration
8. **`query()` shorthand** -- last, lowest risk, independent

Defer to later in v0.3 or post-v0.3:
- `to_dicts()`, iterable cursor, `schema`/`column_names` properties -- convenience, not critical path
- Connection reuse via `adbc_clone()` pool -- start with fresh-connection-per-execute, add reuse if benchmarks show need

---

## Cursor Lifecycle Constraint (Critical)

The ADBC cursor MUST remain alive while a `RecordBatchReader` is being consumed:

```python
# CORRECT: cursor alive during reader consumption
with conn.cursor() as cursor:
    cursor.execute("SELECT ...")
    reader = cursor.fetch_record_batch_reader()
    for batch in reader:
        process(batch)

# INCORRECT: cursor closed before reader consumed
def broken():
    with conn.cursor() as cursor:
        cursor.execute("SELECT ...")
        return cursor.fetch_record_batch_reader()
    # cursor closed -- reader is INVALID
```

**SemolinaCursor implication:** When `fetch_record_batch_reader()` is called, `__exit__` must NOT close the inner cursor until the reader is consumed or explicitly closed. Track reader state internally.

---

## Sources

- [ADBC Python API Reference](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html)
- [ADBC Python Quickstart](https://arrow.apache.org/adbc/current/python/quickstart.html)
- [Cursor lifetime issue #1893](https://github.com/apache/arrow-adbc/issues/1893)
- [ADBC Connection Pool Recipe](https://github.com/apache/arrow-adbc/blob/main/docs/source/python/recipe/postgresql_pool.py)
- [pydantic-settings TOML](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [PROJECT.md](../../.planning/PROJECT.md)
