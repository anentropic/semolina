# Phase 44: Engine Owns the Pool (SQLAlchemy-Style) - Research

**Researched:** 2026-06-23
**Domain:** Connection-API redesign (Engine owns ADBC pool + dialect; introspection + execution unified on ADBC)
**Confidence:** HIGH (codebase + installed-package facts verified directly; one OPEN spike for Databricks)

## Summary

This is an internal-refactor phase, not a greenfield build. The CONTEXT.md locks the WHAT
and most of the HOW; the planner's job is to sequence concrete edits across ~7 source modules,
~10 test modules, and ~12 docs pages, keeping the recorded Snowflake cassettes green. I read
every touch-point file and the installed `adbc-poolhouse` 1.2.0 source, so the call patterns
below are `[VERIFIED]` against the actual code, not inferred.

The redesign collapses two parallel worlds that exist today: (1) the **execution world** —
`adbc-poolhouse` `create_pool()` → SQLAlchemy `QueuePool` → `registry._pools[name] = (pool, dialect)`
→ `query.execute()` calls `pool.connect()` / `cur.execute(sql, params)` / wraps in `SemolinaCursor`;
and (2) the **introspection world** — `Engine` subclasses (`SnowflakeEngine`, `DatabricksEngine`,
`DuckDBEngine`) that each open a **native driver** connection (`snowflake.connector`,
`databricks.sql`, `duckdb`) purely for codegen. The `Engine.execute()`/`to_sql()` abstract methods
are vestigial: nothing in the runtime path calls them, and `SnowflakeEngine.execute()` is **broken**
because the SQL builder now emits qmark (`?`) placeholders (commit `799a8b0`) while
`snowflake.connector` uses pyformat (`%s`) — confirmed by reading `snowflake.py` lines 229-252.

The target end-state makes `Engine` own a single `adbc-poolhouse` pool + derived dialect, and run
**both** `introspect()` and `execute()` through `pool.connect()`. The Snowflake introspection SQL
(`SHOW COLUMNS IN VIEW`) is already proven over ADBC (live spike, CONTEXT decision 3). The one
genuine unknown is Databricks: its introspection command (`DESCRIBE TABLE EXTENDED ... AS JSON`)
is "just SQL," but it has never been run over ADBC because **the Databricks ADBC driver is
Foundry-distributed and not installed in this environment** (only `databricks-sql-connector` ships
via the `databricks` extra). That driver-availability fact — not just the recording hang — is the
real blocker for the Databricks spike.

**Primary recommendation:** Build `create_engine()` + an internal `Engine` that wraps a poolhouse
pool, route `query.execute()` and `registry` through Engine, and migrate Snowflake/DuckDB fully on
ADBC. Gate the Databricks branch behind a spike task that **first confirms the Foundry ADBC driver
can be installed locally**, then validates `DESCRIBE TABLE EXTENDED AS JSON` over an ADBC cursor.
If the driver cannot be obtained in time, ship Snowflake+DuckDB on the new API and leave a clearly
marked `NotImplementedError`/TODO for Databricks introspection rather than blocking the milestone.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Build/own ADBC pool + dialect from config | `Engine` (new core) | `semolina.config` (TOML read) | SQLAlchemy `Engine` parallel — one handle owns pool + dialect |
| Connection checkout | `Engine.connect()` → `pool.connect()` | adbc-poolhouse `QueuePool` | Pool is the connection authority; Engine is a thin owner |
| Query execution (runtime) | `Engine.execute()` / `query.execute()` | `SQLBuilder` + `SemolinaCursor` | Reuse existing builder + cursor path unchanged |
| Introspection (codegen) | `Engine.introspect()` | warehouse SQL over ADBC cursor | "Richer metadata" is a SQL command, not a driver API |
| Name → Engine resolution | `registry` (`register`/`get_engine`) | `query.using()` | Django-style named registry layered over SQLAlchemy-style Engine |
| Config-type → dialect/Engine selection | `_CONFIG_MAP` in `config.py` | `create_engine` dispatch | Type-tag already maps config → dialect; reuse it |
| SQL generation (dialect quoting/placeholder) | `engines/sql.py` Dialect ABC | — | Out of scope to change; already qmark + view-folding |

## Standard Stack

This phase introduces **no new external packages**. It re-wires existing dependencies. The
"stack" below is what already ships and what the redesign standardizes on.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| adbc-poolhouse | 1.2.0 | `create_pool(config)` → SQLAlchemy `QueuePool`; `close_pool`; typed `*Config` classes | Already the execution-path pool factory `[VERIFIED: installed 1.2.0.dist-info]` |
| adbc-driver-snowflake | installed | Snowflake ADBC dbapi (`adbc_driver_snowflake.dbapi`) | poolhouse routes Snowflake here `[VERIFIED: _snowflake_config.py:139]` |
| adbc-driver-duckdb | installed | DuckDB ADBC driver (entrypoint `duckdb_adbc_init`) | poolhouse DuckDB path `[VERIFIED: _duckdb_config.py:82]` |
| adbc-driver-manager | installed | Generic ADBC manager; routes Databricks (Foundry driver) | poolhouse Databricks path `[VERIFIED: pyproject adbc_dialect mapping]` |
| sqlalchemy (transitive) | via poolhouse | `QueuePool`, `event.listen(pool, "connect", ...)` | poolhouse returns a `sqlalchemy.pool.QueuePool` `[VERIFIED: _pool_factory.py:95]` |

### Supporting (LEAVING the path — to be deleted/orphaned)
| Library | Version | Purpose | Disposition |
|---------|---------|---------|-------------|
| snowflake-connector-python | >=4.3.0 (snowflake extra) | Native Snowflake conn used by `SnowflakeEngine` + integration DDL setup | Remove from the **introspection/execution** path. Still used by integration **record-mode DDL setup** (`tests/integration/conftest.py`) — keep there or migrate DDL to ADBC too |
| databricks-sql-connector | >=4.2.5 (databricks extra) | Native Databricks conn used by `DatabricksEngine` + integration DDL setup | Same: remove from introspection/execution path; record-mode DDL still uses it |
| duckdb (native) | >=1.5.0 | Native duckdb used by `DuckDBEngine.introspect()` | Replace with ADBC pool introspection (DuckDB execution already on ADBC pool) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Engine owns one poolhouse pool | Engine owns raw ADBC connection | Loses pooling, recycle, reset-event Arrow cleanup that poolhouse provides `[VERIFIED: _pool_factory.py:106]` |
| `create_engine(config \| name)` (no URL) | URL-string form | CONTEXT decision 1 locks NO URL form (not all backends have URLs) — do not add |
| Keep `pool_from_config` returning `(pool, Dialect)` | Fold its TOML read into `create_engine` | CONTEXT decision 5 locks the fold; keep as internal helper only if still used |

**Installation:** No `pip install` changes for the core path. The Databricks ADBC driver is
**Foundry-distributed (not PyPI)** `[VERIFIED: _databricks_config.py:32-34 + pyproject databricks extra comment]` — see the Databricks spike and Environment Availability sections.

**Version verification:**
- `adbc-poolhouse` 1.2.0 `[VERIFIED: .venv .../adbc_poolhouse-1.2.0.dist-info]`
- pyproject pins `adbc-poolhouse>=1.2.0`, `pytest-adbc-replay>=1.1.1` `[VERIFIED: pyproject.toml:11,61]`

## Package Legitimacy Audit

> Not applicable in the install sense — this phase adds **no new external packages**. All
> packages referenced are already declared in `pyproject.toml` and present in the venv. No
> WebSearch/training-derived package names were introduced. Audit table omitted by exception
> (zero new installs); the planner does not need a `checkpoint:human-verify` install gate.

## Architecture Patterns

### System Architecture Diagram

```
                       create_engine(config_obj | "conn_name")
                                      |
                  (name) reads [connections.<name>] from .semolina.toml
                  (config_obj) used directly
                                      |
                          _CONFIG_MAP: type -> Dialect
                                      |
                                      v
              +-------------------------------------------------+
              |                   Engine                        |
              |  owns: poolhouse QueuePool  +  Dialect          |
              |  (built via create_pool(config))                |
              +-------------------------------------------------+
                    |                         |
       engine.introspect(view)        engine.execute(query)  /  engine.connect()
                    |                         |
            SQL over ADBC cursor       SQLBuilder.build_select_with_params()
       (SHOW COLUMNS IN VIEW /          -> pool.connect() -> cur.execute(sql, params)
        DESCRIBE TABLE EXTENDED         -> SemolinaCursor(cur, conn, pool)
        AS JSON / DESCRIBE
        SEMANTIC VIEW)
                    |                         |
            IntrospectedView            rows / Arrow stream
                    |
            python_renderer -> generated SemanticView subclass

   registry:  register("default", engine)   ->  _engines[name] = engine
   query:     Query.using("default").execute()  ->  get_engine(name).execute(self)
```

### Recommended Structure (where edits land)
```
src/semolina/
├── engines/
│   ├── base.py          # Engine ABC: drop to_sql() (lean), keep introspect() + execute();
│   │                    #   add connect(); store pool + dialect on the base
│   ├── snowflake.py     # introspect() runs SHOW COLUMNS IN VIEW over ADBC cursor; drop native conn
│   ├── databricks.py    # introspect() runs DESCRIBE TABLE EXTENDED AS JSON over ADBC (SPIKE-gated)
│   └── duckdb.py        # introspect() runs DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT over ADBC
├── config.py            # create_engine() (NEW); fold pool_from_config TOML read;
│   │                    #   DELETE snowflake_connect_kwargs / databricks_connect_kwargs
├── registry.py          # name -> Engine; register("name", engine); get_engine()
├── query.py             # execute()/using() resolve Engine, run via engine pool
├── cli/codegen.py       # _resolve_backend() builds Engine via create_engine, not native kwargs
└── __init__.py          # export create_engine, register; drop pool_from_config? (decision 5)
```

### Pattern 1: poolhouse pool checkout (the call pattern Engine.execute must wrap)
**What:** A poolhouse pool is a `sqlalchemy.pool.QueuePool`. `pool.connect()` returns a pooled
DBAPI connection proxy; `.cursor()` gives an ADBC DBAPI cursor; `cur.execute(sql, params)` runs
qmark SQL; `cursor.description` yields column names; ADBC cursors also expose
`fetch_arrow_table()` / `fetch_record_batch()`.
**When to use:** Both `execute()` and `introspect()` SQL.
**Example (today's runtime path — Engine.execute should reproduce this):**
```python
# Source: src/semolina/query.py:419-427 [VERIFIED]
pool, dialect = get_pool(self._using)          # becomes: engine = get_engine(self._using)
builder = dialect.create_builder()
sql, params = builder.build_select_with_params(self)
conn = pool.connect()                          # becomes: engine.connect()
cur = conn.cursor()
cur.execute(sql, params)
return SemolinaCursor(cur, conn, pool)         # pool still needed for reset-event cleanup
```
Note: `SemolinaCursor.__init__(cursor, conn, pool)` needs `conn` and `pool` for lifecycle/reset
`[VERIFIED: cursor.py:30-52, 288-292]`. If Engine wraps the pool, pass `engine._pool` (or expose a
property) so the reset event (`_release_arrow_allocators`) still fires on checkin.

### Pattern 2: building the pool inside the Engine
**What:** `create_pool(config)` does all the work — extracts driver path / dbapi module from the
config object, builds the `QueuePool`, attaches `_adbc_source`, and registers the Arrow-cleanup
reset event. poolhouse connects **eagerly** at `create_pool` (a source ADBC connection is opened
immediately) `[VERIFIED: _pool_factory.py:88-106]`.
**When to use:** Inside `create_engine` after resolving the config object.
**Example:**
```python
# Source: adbc_poolhouse._pool_factory.create_pool [VERIFIED installed 1.2.0]
from adbc_poolhouse import create_pool, close_pool
pool = create_pool(config)            # config = SnowflakeConfig(...) / DatabricksConfig(...) / DuckDBConfig(...)
# DuckDB only: attach the semantic_views loader connect-event (see config._load_semantic_views)
```
**DuckDB caveat:** DuckDB needs the `semantic_views` extension loaded per physical connection via
a `connect` event listener `[VERIFIED: config.py:31-43, 121-124]`. `create_engine` must replicate
the `event.listen(pool, "connect", _load_semantic_views)` that `pool_from_config` does today, or
introspection/execution of DuckDB semantic views fails.

### Pattern 3: `create_engine` str-vs-config dispatch (Claude's Discretion)
**Recommendation:** Single public function with runtime type-dispatch, mirroring how
`pool_from_config` already reads type-tagged TOML and how `_CONFIG_MAP` maps type → dialect.
```python
# Recommended shape (ASSUMED design — planner finalizes)
def create_engine(
    config: WarehouseConfig | str = "default",
    *,
    config_path: str | Path = ".semolina.toml",
) -> Engine:
    if isinstance(config, str):
        cfg, dialect = _config_and_dialect_from_toml(config, config_path)  # folded pool_from_config
    else:
        cfg = config
        dialect = _dialect_for_config_type(type(cfg))   # reuse _CONFIG_MAP reverse lookup
    pool = create_pool(cfg)
    return _engine_for_dialect(dialect)(pool=pool, dialect=resolve_dialect(dialect))
```
- `isinstance(config, str)` cleanly separates the name path from the config-object path
  (poolhouse configs are pydantic `BaseSettings`, never `str`).
- `_CONFIG_MAP` today maps `"snowflake" -> (SnowflakeConfig, Dialect.SNOWFLAKE)`
  `[VERIFIED: config.py:24-28]`. For the config-object path you need the **reverse** map
  (`type(config) -> Dialect`); build it once from `_CONFIG_MAP` so it stays in sync.
- Use `@overload` to give precise return/typing if the planner wants strictness under basedpyright,
  but a single body with `isinstance` is sufficient and simpler.

### Anti-Patterns to Avoid
- **Per-call native connect inside Engine** (today's `snowflake.connector.connect()` per
  `execute()`/`introspect()`): defeats pooling and is the source of the `%s` vs `?` break. Run
  everything through the owned poolhouse pool.
- **Letting `query.execute()` reach into `engine._pool` directly** beyond what `SemolinaCursor`
  needs: expose `engine.connect()` and (if needed) the pool for cursor lifecycle, but keep the
  builder/cursor wiring in one place.
- **Hand-quoting view names in introspection SQL**: the dialect already provides
  `quote_table_name()` with fold-and-quote semantics `[VERIFIED: sql.py:173-208]`. Snowflake
  introspection currently string-prepends the database (`snowflake.py:317-321`) — preserve that
  qualification logic when moving to ADBC.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pool creation from typed config | Custom ADBC connect + pool | `adbc_poolhouse.create_pool(config)` | Handles driver-path/dbapi-module dispatch, Foundry NOT_FOUND→ImportError, Arrow reset cleanup `[VERIFIED: _driver_api.py, _pool_factory.py]` |
| Pool teardown | `pool.dispose()` alone | `adbc_poolhouse.close_pool(pool)` | Also closes the `_adbc_source` connection; `dispose()` alone leaks it `[VERIFIED: _pool_factory.py:244-264]` |
| Arrow record-batch cleanup on checkin | Manual cursor closing | poolhouse `reset` event (automatic) | Already attached by `create_pool` `[VERIFIED: _pool_factory.py:106,407]` |
| Snowflake schema→db qualification | New logic | Keep `snowflake.py:317-321` qualification | Existing tested behavior; just swap the connection underneath |
| Cursor → Row mapping / Arrow streaming | New cursor wrapper | `SemolinaCursor` (unchanged) | Already wraps ADBC cursors, supports `fetch_arrow_table`/`fetch_record_batch`/iteration `[VERIFIED: cursor.py]` |
| TOML connection parsing | New parser | Fold existing `pool_from_config` reader | Already reads `[connections.<name>]`, pops `type`, expands `~` private key `[VERIFIED: config.py:61-126]` |

**Key insight:** Almost every primitive this phase needs already exists and is tested. The work is
**re-composition and deletion**, not new construction. The highest-risk new surface is the
`create_engine` dispatch and the Databricks ADBC introspection path.

## Runtime State Inventory

> This is a refactor/API-rename phase. Grep finds files; it does not find runtime state. All five
> categories answered explicitly below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None.** No datastore keys/collections/user_ids encode the renamed API surface. Recorded **cassettes** under `tests/integration/cassettes/` store the generated **SQL text + Arrow results**, keyed by pytest node id (test name + backend param), NOT by `register`/pool symbol names `[VERIFIED: conftest docstring + pyproject adbc_cassette_dir]`. The SQL is unchanged by this phase, so cassettes replay green — verified by reasoning: only connection plumbing moves, SQL builder output is identical. | No cassette regen needed *if* SQL unchanged; verify by running `tests/integration` in replay mode after the change |
| Live service config | **None.** No external UI/SaaS config (n8n, Datadog, etc.) references the Semolina connection API. `.semolina.toml` is in-repo and IS part of the migration (its `[connections.<name>]` schema is unchanged — only how the library consumes it moves). | None beyond docs/code |
| OS-registered state | **None.** No OS task/service registrations embed `register`/`pool_from_config`/Engine names. | None |
| Secrets/env vars | `SNOWFLAKE_*` / `DATABRICKS_*` / `DUCKDB_*` env vars and `.semolina.toml` `[connections.*]` sections are read by `warehouse_config`/`pool_from_config` `[VERIFIED: config.py:129-174]`. **These names/shapes are unchanged** by this phase — only the consuming code changes. `SEMOLINA_ENV_FILE` override likewise unchanged. | No env/secret rename; just ensure `create_engine` still reads them |
| Build artifacts | **None stale.** No egg-info/compiled artifacts carry the old API. Generated codegen output (`SemanticView` subclasses) is produced by `python_renderer` and does NOT embed pool/register calls — it emits model classes only `[VERIFIED: codegen.py:187-190]`. | None |

**The canonical question — after every repo file is updated, what still has the old API cached?**
Answer: nothing at the OS/datastore/service level. The only persisted artifacts that matter are
the **integration cassettes**, and they are keyed by test node + recorded SQL, both unchanged.

## Common Pitfalls

### Pitfall 1: Cassette drift from incidental SQL changes
**What goes wrong:** Any change to the generated SQL (quoting, placeholder, view-name folding,
column order) makes recorded cassettes mismatch and integration tests fail with no live warehouse
to re-record against.
**Why it happens:** pytest-adbc-replay matches on the SQL string the driver receives.
**How to avoid:** This phase must NOT touch `SQLBuilder` output. Keep `build_select_with_params`
identical; only move *where the cursor comes from*. Add a verification step: run
`pytest tests/integration` in replay mode (default) and confirm green before/after.
**Warning signs:** `test_queries.py` failures referencing cassette mismatch.

### Pitfall 2: DuckDB `semantic_views` extension not loaded on the Engine's pool
**What goes wrong:** `engine.introspect()` / `execute()` on a DuckDB view raises a parser/catalog
error because the `semantic_views` community extension wasn't loaded on the physical connection.
**Why it happens:** ADBC clones independent in-memory DuckDB instances per connection; the
extension must be loaded via a `connect` event listener, which `pool_from_config` does but a naive
`create_engine` would forget `[VERIFIED: config.py:121-124; conftest.py:125]`.
**How to avoid:** `create_engine` must attach `_load_semantic_views` as a `connect` listener when
the config is `DuckDBConfig`. Mirror the existing branch in `pool_from_config`.
**Warning signs:** "Catalog Error" / unknown function `semantic_view` only on DuckDB.

### Pitfall 3: SemolinaCursor lifecycle when Engine owns the pool
**What goes wrong:** Connections leak or Arrow allocators aren't released if `SemolinaCursor`
no longer receives the pool object.
**Why it happens:** The poolhouse `reset` event (`_release_arrow_allocators`) fires on
checkin; `SemolinaCursor.close()` calls `conn.close()` which returns the connection to the pool
and triggers reset `[VERIFIED: cursor.py:288-292; _pool_factory.py:407-428]`.
**How to avoid:** `Engine.execute()` must still pass the real `conn` and the underlying pool (or a
proxy that closes correctly) to `SemolinaCursor(cur, conn, pool)`.
**Warning signs:** Growing memory under repeated queries; "pool limit exceeded" timeouts.

### Pitfall 4: `Engine.execute()` is currently broken — don't preserve its behavior, replace it
**What goes wrong:** Copying the existing `SnowflakeEngine.execute()` carries the `%s`/native-conn
bug forward.
**Why it happens:** `snowflake.py:229-252` opens `snowflake.connector.connect()` (pyformat) but
the builder now emits `?` (qmark) `[VERIFIED: snowflake.py:238-245; sql.py:242-243]`.
**How to avoid:** Reimplement `execute()` on the ADBC pool path (qmark-compatible). The native
`execute()` was never wired into `query.execute()`, so there is no behavior to preserve.

### Pitfall 5: Databricks ADBC driver is not installable from PyPI
**What goes wrong:** The Databricks introspection spike (and any Databricks ADBC pool) fails at
`create_pool` with an `ImportError` ("ADBC driver 'databricks' not found") because the driver is
Foundry-distributed, not on PyPI, and is **not installed in this venv**
`[VERIFIED: _databricks_config.py:32-34; importlib find_spec shows adbc_driver_snowflake/duckdb
present, no databricks ADBC driver; pyproject databricks extra ships only databricks-sql-connector]`.
**Why it happens:** Columnar's Databricks ADBC driver ships via the ADBC Driver Foundry.
**How to avoid:** The Databricks spike's FIRST sub-task is "obtain + install the Foundry Databricks
ADBC driver" — without it the introspection cannot be validated regardless of credentials. Treat
driver acquisition and the known recording-hang as two separate prerequisites.

## Code Examples

### Snowflake introspection over ADBC (the proven path — swap conn, keep SQL)
```python
# Source: src/semolina/engines/snowflake.py:323-364 [VERIFIED] — connection swap only
with engine.connect() as conn:            # was: snowflake.connector.connect(**params)
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")   # SQL unchanged; qualification preserved
    columns = [desc[0].lower() for desc in cur.description]
    for row in cur.fetchall():
        d = dict(zip(columns, row, strict=True))
        type_json = json.loads(d["data_type"])             # 13-col result identical over ADBC (spike)
        ...
# Error translation: catch ADBC errors instead of snowflake.connector ProgrammingError/DatabaseError
```
Note: error-class translation must change. Today it catches `snowflake.connector.errors.*`
`[VERIFIED: snowflake.py:372-380]`. Over ADBC, errors surface as `adbc_driver_manager.Error`
subclasses (PEP-249) — the introspectors must catch those and still raise
`SemolinaViewNotFoundError` / `SemolinaConnectionError`.

### Databricks introspection command (the SPIKE target)
```python
# Source: src/semolina/engines/databricks.py:330-332 [VERIFIED]
cur.execute(f"DESCRIBE TABLE EXTENDED {view_name} AS JSON")
row = cur.fetchone()
schema = json.loads(row[0])     # single-cell JSON string -> {"columns": [{"name","type","is_measure","comment"}...]}
```
This is plain SQL returning a single JSON string cell, so it *should* run over an ADBC Arrow cursor
unchanged. UNVALIDATED — see spike. (`is_measure=True` → metric; absent/False → dimension; no
"fact" concept in Databricks metric views.)

### DuckDB introspection over ADBC (replace native duckdb conn)
```python
# Source: src/semolina/engines/duckdb.py:198-241 [VERIFIED] — runs two DESCRIBE passes
# Native today: duckdb.connect(...).execute(...). Move to engine.connect() ADBC cursor.
# MUST ensure semantic_views extension loaded (connect-event on the pool) before DESCRIBE.
cur.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")        # field structure
cur.execute(f"DESCRIBE SELECT * FROM semantic_view('{unqualified}', dimensions := [...], metrics := [...])")
```
DuckDB introspection used `read_only=True` + per-call `INSTALL/LOAD` on a fresh native connection
`[VERIFIED: duckdb.py:198-200]`. On the pooled ADBC path the extension load moves to the
`connect` event; the read-only intent maps to `DuckDBConfig(read_only=True)`.

## State of the Art

| Old Approach | Current/Target Approach | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| `register(name, pool, dialect=...)` (3-arg) | `register("name", engine)` (2-arg) | Phase 44 | All call sites + every doc example change |
| `Engine` = native introspector; pool = execution | `Engine` owns pool + dialect; both go through it | Phase 44 | Unifies the two worlds; SQLAlchemy parallel |
| Native connectors for introspect/execute | ADBC-only (poolhouse pool) | Phase 44 | snowflake-connector-python / databricks-sql / native duckdb leave the path |
| Snowflake builder emitted `%s` | qmark `?` for all backends | commit `799a8b0` (landed) | Enabler; makes ADBC execution viable |
| View name unquoted/unfolded | `Dialect.quote_table_name()` fold+quote | commit `799a8b0` (landed) | Enabler |
| `semolina.testing.credentials` module | removed | commit `9da2f4e` (landed) | No test-credential helper to migrate |

**Deprecated/outdated (to delete in this phase):**
- `snowflake_connect_kwargs()` / `databricks_connect_kwargs()` in `config.py`
  `[VERIFIED: config.py:177-243]` — native-only, unused once introspection is ADBC. NOTE: still
  referenced by `cli/codegen.py:_resolve_backend` (lines 89,99,103,113) AND by
  `tests/integration/conftest.py` record-mode DDL setup (lines 91,102,209,221). Both must be
  migrated/removed before deletion or basedpyright/imports break.
- `Engine.to_sql()` abstract method — CONTEXT decision: lean drop (redundant with `Query.to_sql()`).
- `pool_from_config` public export — fold into `create_engine`; keep internal only if used.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DESCRIBE TABLE EXTENDED ... AS JSON` runs unchanged over an ADBC cursor (single JSON cell) | Databricks introspection | Databricks codegen broken until the SQL form is adjusted for ADBC; mitigated by the spike |
| A2 | The Foundry Databricks ADBC driver can be installed in the dev/CI env in time | Pitfall 5, Env Availability | Databricks branch cannot be validated; fallback = ship Snowflake+DuckDB, mark Databricks TODO |
| A3 | Recorded Snowflake cassettes replay green because SQL output is byte-identical post-refactor | Runtime State, Pitfall 1 | Integration tests fail; requires re-record (needs live Snowflake) — verify early |
| A4 | `create_engine` `isinstance(config, str)` dispatch is sufficient (poolhouse configs are never str) | Pattern 3 | If a future config is str-like, dispatch ambiguous — low risk, pydantic BaseSettings are not str |
| A5 | Passing the underlying pool to `SemolinaCursor` preserves Arrow reset cleanup when Engine owns it | Pitfall 3 | Memory/connection leaks; verify with the existing `test_pool.py` lifecycle tests |
| A6 | DuckDB execution already runs on the ADBC pool today (only its *introspection* is native) | duckdb.py / conftest | If DuckDB exec path differs, scope grows — LOW: `duckdb_pool` fixture registers a poolhouse pool `[VERIFIED: conftest.py:107-133]` |

## Open Questions (RESOLVED)

1. **Should record-mode integration DDL setup also move to ADBC?**
   - What we know: `tests/integration/conftest.py` uses native `snowflake.connector` /
     `databricks.sql` for CREATE SCHEMA/TABLE/VIEW during recording `[VERIFIED: conftest.py:113-138,
     224-255]`. Only query SQL is recorded, not DDL.
   - What's unclear: whether the phase should keep native connectors solely for record-mode DDL
     (so the `snowflake`/`databricks` extras stay) or migrate DDL to ADBC too.
   - RESOLVED: Keep native connectors for record-mode DDL setup only (smallest blast radius);
     remove them from the **library** path. Document that the extras now exist for recording, not
     runtime. Revisit in a later phase. (Implemented in plan 44-05 T1 — fixtures retain native DDL.)

2. **`get_pool` → `get_engine` rename vs. keep (Claude's Discretion).**
   - What we know: `registry.get_pool()` returns `(pool, dialect)` and is called by
     `query.execute()` `[VERIFIED: registry.py:57-87; query.py:415-419]`.
   - RESOLVED: Rename to `get_engine` returning the `Engine` (cleaner, matches the new model).
     Update `query.execute()`, `test_registry.py`, `test_pool.py`. It's pre-1.0; clean break is fine.
     (Implemented in plans 44-02 T3 + 44-01 T1.)

3. **Does the Databricks recording hang block the spike, or only block cassettes?**
   - What we know: STATE.md lists the hang in `databricks.sql.connect` / ADBC pool connect as a
     blocker for both cassettes and the spike.
   - RESOLVED: The spike can validate introspection against a live Databricks ADBC connection
     WITHOUT pytest-adbc-replay recording — decouple "does DESCRIBE work over ADBC" from "can we
     record a cassette." Validate introspection first; treat recording as a separate task.
     (Implemented in plan 44-04 — spike decoupled from recording.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| adbc-poolhouse | Pool creation (all backends) | ✓ | 1.2.0 | — |
| adbc_driver_snowflake | Snowflake ADBC path | ✓ | installed | — |
| adbc_driver_duckdb | DuckDB ADBC path | ✓ | installed | — |
| adbc_driver_manager | Databricks routing + generic | ✓ | installed | — |
| **Databricks ADBC driver (Foundry)** | **Databricks ADBC introspection spike** | **✗** | **—** | **Ship Snowflake+DuckDB; mark Databricks introspection TODO/NotImplemented** |
| snowflake-connector-python | record-mode DDL setup only | ✓ | >=4.3.0 | — |
| databricks-sql-connector | record-mode DDL setup only | ✓ | >=4.2.5 | — |
| Live Snowflake account | Re-record cassettes IF SQL changes | ✗ (no creds in session) | — | Don't change SQL; replay existing cassettes |
| Live Databricks warehouse | Databricks spike + cassettes | ✗ (creds absent; connect hangs) | — | Spike-gated; descope if unavailable |

**Missing dependencies with no fallback:** none that block the core (Snowflake+DuckDB) path.
**Missing dependencies with fallback:** the Databricks ADBC Foundry driver and live Databricks
access — fallback is to ship the new API for Snowflake+DuckDB and gate Databricks introspection
behind a clearly-marked TODO until the driver + a working warehouse are available.

## Validation Architecture

> `workflow.nyquist_validation` is absent in `.planning/config.json` → treated as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 (+ pytest-xdist, pytest-adbc-replay >=1.1.1, syrupy, pytest-cov) `[VERIFIED: pyproject dev group]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` incl. `adbc_*` keys) |
| Quick run command | `just test` (unit + jaffle-shop mock) — per CLAUDE.md |
| Full suite command | `just test` then `pytest tests/integration` (replay mode, default) |

### Phase Requirements → Test Map
> No phase_req_ids mapped. Coverage derived from CONTEXT locked decisions.

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| D1 create_engine(config\|name) | builds Engine from config object | unit | `pytest tests/unit/test_config.py -k create_engine` | ❌ Wave 0 (new tests) |
| D1 create_engine(name) | reads `[connections.<name>]` | unit | `pytest tests/unit/test_config.py -k from_toml` | ⚠️ adapt existing `pool_from_config` tests |
| D2 Engine owns pool; execute via ADBC | query runs through engine pool | unit | `pytest tests/unit/test_pool.py` | ✅ adapt (register signature) |
| D3 introspect via ADBC (Snowflake) | SHOW COLUMNS over ADBC | unit | `pytest tests/unit/test_snowflake_engine.py` | ✅ rewrite mocks (native→ADBC) |
| D3 introspect via ADBC (Databricks) | DESCRIBE ... AS JSON over ADBC | spike+unit | spike script, then `pytest tests/unit/test_databricks_engine.py` | ✅ rewrite mocks; ⚠️ spike-gated |
| D3 introspect via ADBC (DuckDB) | DESCRIBE SEMANTIC VIEW over ADBC pool | unit | `pytest tests/unit/test_duckdb_engine.py` | ✅ rewrite (native→pool) |
| D4 register("name", engine) | name→Engine; using() resolves | unit | `pytest tests/unit/test_registry.py` | ✅ rewrite (3-arg→2-arg) |
| D2/D3 end-to-end replay | cassettes still green | integration | `pytest tests/integration` | ✅ adapt fixtures |
| codegen CLI | `_resolve_backend` builds Engine via create_engine | unit | `pytest tests/unit/codegen/test_cli.py` | ✅ adapt |

### Sampling Rate
- **Per task commit:** `just test` (fast unit + mock).
- **Per wave merge:** `just test && pytest tests/integration` (replay) `&& just docs-build`.
- **Phase gate:** full suite green + `prek run --all-files` (ruff + basedpyright strict) before
  `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/unit/test_config.py` — new `create_engine` tests (config-object + TOML-name dispatch);
      adapt existing `pool_from_config` mock tests (they patch `semolina.config.create_pool`).
- [ ] `tests/unit/test_registry.py` — rewrite all `register(pool, dialect=...)` → `register(engine)`;
      `get_pool` → `get_engine` (10+ tests reference the 3-arg form `[VERIFIED]`).
- [ ] `tests/unit/test_snowflake_engine.py` / `test_databricks_engine.py` / `test_duckdb_engine.py`
      — replace native-connector `sys.modules` mocks with ADBC-cursor mocks (current mocks stub
      `snowflake.connector` / `databricks.sql` / `duckdb` `[VERIFIED]`).
- [ ] `tests/unit/test_pool.py` — update `register("test", pool, dialect=...)` call sites
      (lines 255, and the `test_execute_with_named_pool_using` flow `[VERIFIED]`).
- [ ] `tests/integration/conftest.py` — fixtures move from `create_pool` + `register(pool, dialect)`
      to `create_engine` + `register(engine)`; decide native-DDL-setup disposition (Open Q1).
- [ ] `tests/conftest.py` + `src/semolina/conftest.py` (doctest) — `duckdb_pool` / `doctest_setup`
      fixtures register pools today; move to Engine API `[VERIFIED: conftest.py:130; conftest.py:119]`.
- [ ] Databricks ADBC introspection **spike script** (standalone, not pytest) — see spike shape.

## Security Domain

> `security_enforcement` is `null` in `.planning/config.json` → treat as enabled (default).
> This phase moves connection plumbing; it touches credential handling, so the relevant controls:

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Warehouse auth handled by poolhouse configs (password/JWT/OAuth/PAT). `SecretStr` already wraps secrets `[VERIFIED: _snowflake_config.py:42, _databricks_config.py:39,51]` — do not log/`repr` raw secret values |
| V6 Cryptography | yes (key handling) | Snowflake private-key path `~`-expansion stays in `_expand_private_key_path` `[VERIFIED: config.py:46-58]`; never hand-roll key parsing |
| V7 Secrets management | yes | Credentials sourced from `.semolina.toml` / `SNOWFLAKE_*`/`DATABRICKS_*` env / `.env`; pytest-adbc-replay scrubs keys via `adbc_scrub_keys` `[VERIFIED: pyproject adbc_scrub_keys]` — ensure no new secret leaks into cassettes |
| V5 Input Validation | partial | View names flow into introspection SQL via f-strings (existing behavior); `quote_table_name` folds/quotes for execution. Introspection `SHOW COLUMNS IN VIEW {name}` / `DESCRIBE ... {name}` are existing patterns — not a new injection surface, but do not widen it |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage into recorded cassettes | Information Disclosure | `adbc_scrub_keys` + placeholder-cred replay config (already in place) `[VERIFIED]` |
| Secret leakage via Engine `repr`/logs | Information Disclosure | Keep `SecretStr`; ensure new `Engine.__repr__` (if added) never prints config secrets |
| Identifier injection in introspection SQL | Tampering | Pre-existing f-string pattern; no regression — keep folding/quoting for execution paths |

## Sources

### Primary (HIGH confidence — read directly this session)
- `src/semolina/engines/{base,snowflake,databricks,duckdb}.py` — Engine ABC + subclasses
- `src/semolina/{config,registry,query,cursor,dialect}.py` + `engines/sql.py` — plumbing
- `src/semolina/cli/codegen.py`, `src/semolina/__init__.py` — CLI + exports
- `.venv/.../adbc_poolhouse/{__init__,_pool_factory,_driver_api,_base_config,_snowflake_config,
  _databricks_config,_duckdb_config}.py` — installed 1.2.0 API surface
- `tests/conftest.py`, `src/semolina/conftest.py`, `tests/integration/conftest.py`,
  `tests/unit/test_{registry,pool,config,snowflake_engine,databricks_engine}.py`,
  `tests/unit/codegen/test_cli.py` — migration scope
- `pyproject.toml`, `.planning/{config.json,STATE.md}`, `44-CONTEXT.md`

### Secondary (MEDIUM)
- `.planning/STATE.md` Blockers (Databricks recording hang); pyproject `databricks` extra comment
  (Foundry-distributed driver) — corroborated by `find_spec` showing the driver absent.

### Tertiary (LOW)
- SQLAlchemy `create_engine`/Engine-owns-Pool model — used as the architectural analogy
  (CONTEXT canonical ref; not re-fetched this session, treated as `[CITED]` background).

## Metadata

**Confidence breakdown:**
- Standard stack / call patterns: HIGH — read installed poolhouse 1.2.0 + all touch-point files.
- Architecture (Engine owns pool, dispatch): HIGH for the model (locked in CONTEXT); MEDIUM for
  exact `create_engine` signature (Claude's Discretion — recommended, not mandated).
- Snowflake/DuckDB introspection-on-ADBC: HIGH (Snowflake live-spiked per CONTEXT; DuckDB pool
  already exists).
- Databricks introspection-on-ADBC: LOW — UNVALIDATED; blocked by Foundry-driver absence +
  recording hang. Spike required.
- Cassette stability: MEDIUM-HIGH — reasoned from "SQL unchanged"; must be verified by running
  `tests/integration` in replay mode.

**Research date:** 2026-06-23
**Valid until:** 2026-07-23 (stable internal codebase; refresh if adbc-poolhouse or the
pytest-adbc-replay plugin version bumps).
