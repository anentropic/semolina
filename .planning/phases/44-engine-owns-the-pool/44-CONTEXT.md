# Phase 44: Engine Owns the Pool (SQLAlchemy-Style) — Context

**Gathered:** 2026-06-23
**Status:** Ready for planning
**Source:** Captured from a `/gsd-quick` legacy-cleanup that escalated into a core-API
design discussion, plus a validated live spike (see `<specifics>`).

<domain>
## Phase Boundary

Redesign the `Engine` abstraction so it **owns the connection pool and dialect**,
SQLAlchemy-style, and is the single handle used for both **introspection** (codegen)
and **query execution** (runtime). Today these are split: the adbc-poolhouse pool +
registry own execution, while `Engine` is an unrelated codegen-only introspector
whose `execute()`/`to_sql()` methods are orphaned (and `execute()` is now broken —
it emits ADBC qmark SQL but opens a native pyformat connection).

Target end-state:
- `create_engine(config_obj_or_name)` builds and **owns one ADBC pool** + the derived
  dialect.
- `engine.introspect(view)` and `engine.execute(query)` both run through that one
  ADBC pool (**ADBC-only** — native connectors removed from the path).
- `register("default", engine)` replaces `register(name, pool, dialect)`;
  `Query.using("default")` resolves the Engine. Direct use (`engine.execute(...)`,
  `engine.connect()`) also works without registering.

**In scope:** the `Engine` ABC + per-backend subclasses, `create_engine`, the
registry (`register`/`get_pool`→`get_engine`), `Query.using()`/`Query.execute()`
resolution, `semolina.config` (fold `pool_from_config`, delete the
`*_connect_kwargs` helpers), `cli/codegen.py` `_resolve_backend`, the public
`__init__` surface, all affected unit/integration tests, and **all docs** (every
query example uses the connection API).

**Out of scope:** changing the query builder/SQL generation (done — qmark + view-name
folding already landed), the streaming/cursor layer, adding new warehouses, the
`semantic_view()` DuckDB table-function path (only its introspection/execution wiring
moves with the rest).

This is a **clean break** of the v0.5 `register(name, pool, dialect)` public API.
Acceptable pre-1.0; see [[feedback_v03_engine_removal]] (user prefers clean breaks,
no deprecation shims).
</domain>

<decisions>
## Implementation Decisions (all locked with the user)

### 1. Construction API (locked)
- `create_engine(...)` accepts **either** an adbc-poolhouse **config object**
  (`SnowflakeConfig(...)`, `DatabricksConfig(...)`, `DuckDBConfig(...)`) **or** a
  **`.semolina.toml` connection name** (`create_engine("default")` → reads
  `[connections.default]`, type-tagged).
- **No URL-string form.** A URL is a feature of *some* poolhouse config objects, not
  all backends — so it is not a first-class `create_engine` input.
- Dialect is **derived from the config type** (the `_CONFIG_MAP` in `config.py`
  already maps type → dialect). The per-backend `Engine` subclass is selected the
  same way — callers do not pick a subclass by hand.

### 2. Engine owns pool + dialect; ADBC-only (locked)
- One `Engine` instance holds exactly one adbc-poolhouse pool (+ derived dialect).
- `engine.execute(query)` and `engine.introspect(view)` both run through that pool's
  ADBC connections. `engine.connect()` checks out an ADBC connection (SQLAlchemy
  parallel). Execution reuses the existing `SemolinaCursor`/builder path.
- **Native connectors (`snowflake-connector-python`, `databricks-sql`) leave the
  path entirely.**

### 3. Introspection via ADBC — VALIDATED (locked)
- The "richer metadata" (which columns are metric/dimension/fact, the `data_type`
  JSON, comments) comes from a warehouse **SQL command** (`SHOW COLUMNS IN VIEW`),
  not a special driver API — and ADBC executes arbitrary SQL returning Arrow. So
  introspection runs the same SQL through the ADBC cursor.
- **Live spike confirmed (Snowflake):** `SHOW COLUMNS IN VIEW` over ADBC returns the
  **identical** 13-column result as the native connector — same `column_name`,
  `kind` (`METRIC`/`DIMENSION`), and `data_type` JSON (`{'type':'FIXED',...}`). The
  current parser works unchanged. `DESCRIBE SEMANTIC VIEW` also works over ADBC
  (richer 5-col/19-row structured form) as an optional future metadata source.
- **Consequence:** the per-backend introspectors keep their SQL but swap the native
  connection for the engine's ADBC pool. No native driver needed.

### 4. Registry / `Query.using()` (locked)
- `register("default", engine)` replaces `register(name, pool, dialect)`. The
  registry maps **name → Engine** (which carries its own pool + dialect).
- `Query.using("default").execute()` resolves the Engine and runs through its pool.
- Hybrid model is intentional: SQLAlchemy-style **Engine instance** usable directly,
  Django-style **named registry** for `.using()` ergonomics. ("We have a tension
  between SQLAlchemy-style engine instance and Django-style registry of named db
  connections — `register("default", engine)` is fine for now.")

### 5. `pool_from_config` + public surface (locked)
- `pool_from_config`'s TOML-reading folds into `create_engine`; keep only as an
  **internal** helper if still used.
- Delete `snowflake_connect_kwargs()` / `databricks_connect_kwargs()` in
  `config.py` (native-only; unused once introspection is ADBC).
- Public surface: `create_engine`, `register`, `SemanticView`/fields, the config
  classes. Per-backend `Engine` subclasses become **internal** (selected by
  `create_engine`).

### Claude's Discretion
- Exact `create_engine` overload/dispatch (str vs config object) implementation.
- Whether `get_pool` is renamed to `get_engine` or kept returning a pool internally.
- Lazy vs eager pool construction inside the Engine (poolhouse already connects
  eagerly at `create_pool`; match existing behavior unless a reason emerges).
- Whether to also keep `engine.to_sql()` (redundant with `Query.to_sql()`) or drop
  it — lean drop, but planner may keep a thin delegator if cheap.
</decisions>

<specifics>
## Specifics

- **Validated spike script:** `/tmp/claude/spike_adbc_introspect.py` (creates a temp
  Snowflake semantic view, runs `SHOW COLUMNS IN VIEW` + `DESCRIBE SEMANTIC VIEW`
  via both native and ADBC, compares). Re-run with creds in `.semolina.toml`.
- **Enablers already landed** (branch `gsd/pytest-adbc-replay-migration`):
  - `SnowflakeDialect.placeholder` is now `?` (qmark) — ADBC paramstyle for all
    backends (commit `799a8b0`).
  - View-name folding via `Dialect.quote_table_name()` (commit `799a8b0`).
  - Snowflake integration cassettes recorded against live Snowflake (commit
    `4637dfc`) — must still replay green after this redesign (the recorded SQL is
    unchanged; only the connection plumbing moves).
  - `semolina.testing.credentials` removed (commit `9da2f4e`).
- **Current code touch-points:** `src/semolina/engines/base.py` (the ABC),
  `engines/snowflake.py` / `databricks.py` / `duckdb.py` (subclasses;
  introspect/execute), `src/semolina/config.py` (`pool_from_config`, `_CONFIG_MAP`,
  `warehouse_config`, the `*_connect_kwargs`), `src/semolina/registry.py`
  (`register`/`get_pool`), `src/semolina/query.py` (`execute`/`using` resolution),
  `src/semolina/cli/codegen.py` (`_resolve_backend`), `src/semolina/__init__.py`
  (exports), plus tests under `tests/unit/` and `tests/integration/`.
</specifics>

<open_items>
## Open Items / Spikes for Planning

- **Databricks introspection over ADBC is NOT yet validated.** Snowflake is proven;
  Databricks metric-view introspection uses a different command (`DESCRIBE`/
  information_schema) and could not be tested now (recording hangs / no working
  Databricks creds). It is also "just SQL," so very likely fine — but the plan must
  include a Databricks ADBC-introspection spike (and the unresolved Databricks
  **recording hang** is a separate prerequisite worth surfacing).
- **Integration-test fixtures** currently build pools directly and `register(...,
  pool, dialect=...)`; they move to the Engine API. Cassette replay must stay green.
- **Migration breadth:** every docs query example (`register`, `pool_from_config`,
  `.using()`) changes — budget a docs pass (apply [[feedback_docs_skills]]).
</open_items>

<canonical_refs>
## Canonical References

- **SQLAlchemy architecture** (the model being adopted): the `Engine` owns a
  connection `Pool` and a `Dialect`; `create_engine(url)` builds both and holds them;
  `Engine.connect()` checks a DBAPI connection out of the owned pool. Verified
  against docs.sqlalchemy.org (2.0): "A single Engine manages many individual DBAPI
  connections on behalf of the process"; sub-engines "share the same dialect and
  connection pool."
- **adbc-poolhouse**: `create_pool(config)`, `close_pool`, `SnowflakeConfig` /
  `DatabricksConfig` / `DuckDBConfig`; routes Snowflake via
  `adbc_driver_snowflake.dbapi`, Databricks via `adbc_driver_manager.dbapi`.
- **Related memory:** [[project_pytest_adbc_replay_migration]] (the branch this builds
  on), [[feedback_v03_engine_removal]] (clean-break preference),
  [[feedback_verify_claims_official_docs]], [[feedback_docs_skills]].
</canonical_refs>
