# Requirements: Semolina v0.7 — Async & Typed Results

**Defined:** 2026-08-01
**Core Value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

**Milestone goal:** Give Semolina a non-blocking async query surface and an honest, verified type story running from warehouse metadata through to Pydantic DTOs.

## v0.7 Requirements

### Async Query Surface

- [x] **ASYNC-01**: User can `await engine.aexecute(query)` to run a query without blocking the event loop, getting back the same result surface as `.execute()`
- [x] **ASYNC-02**: User can `await Sales.query().metrics(...).aexecute()` — an async twin of `.execute()` on the query builder
- [x] **ASYNC-03**: User can `async for row in result` to stream rows lazily, with batches fetched off-thread by adbc-poolhouse and mapped to `Row` by Semolina
- [x] **ASYNC-04**: User installs async support via a `semolina[async]` extra that pins `adbc-poolhouse[async]>=1.6.2`; the default sync install gains no new dependencies. *(Amended from `>=1.5.0` on evidence, Phase 46 Plan 01: the `_resolve_tuning` helper that makes `create_async_pool` honour the config's own `pool_size` landed in adbc-poolhouse 1.6.0, so 1.5.x would silently build a five-connection pool for `DuckDBConfig(database=":memory:", pool_size=1)`. Amended again from `>=1.6.1` during Plan 05: 1.6.1's cancel path ran poison-recovery without waiting for the aborted worker to unwind, deadlocking the DuckDB driver; fixed in 1.6.2 via anentropic/adbc-poolhouse#43, and ASYNC-06 cannot hold below it.)*
- [x] **ASYNC-05**: User's async code runs identically under asyncio and Trio — Semolina library code contains zero `asyncio.*` references and no anyio import, verified by an automated check
- [x] **ASYNC-06**: User cancelling an in-flight async query (framework timeout or task cancellation) causes the underlying warehouse query to be cancelled via `adbc_cancel`, not merely abandoned

### Warehouse Type Fidelity

- [x] **TYPE-01**: Maintainers have an empirical comparison, per backend, of introspection-time field types against query-time `adbc_execute_schema` result types, run over existing Snowflake cassettes and jaffle-shop DuckDB
- [x] **TYPE-02**: The project has a committed type-mapping decision doc covering the Decimal policy, the metric-nullability stance, and which source of truth codegen uses (probe vs metadata)
- [x] **TYPE-03**: User generating models for decimal-typed warehouse columns gets the type the decision doc specifies, applied consistently across Snowflake, Databricks, and DuckDB — the three backends no longer disagree about money
- [x] **TYPE-04**: User generating models gets metric annotations whose nullability reflects the decision doc's stance (metrics are NULL on empty groups)
- [ ] **TYPE-05**: User generating models for the category-1 map gaps — DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS` and Databricks `interval` — gets a concrete Python type rather than a `TODO:` placeholder. *(Partial after Phase 48: every DuckDB type listed resolves and is proved by `isinstance` against a measured value. Databricks `interval` still emits `TODO:` — no fixture, cassette, or recording in this repo contains an interval column, so the annotation cannot be measured, and a guess was rejected. Accepted as a documented limitation at Phase 48 UAT (override in 48-VERIFICATION.md); closing it needs `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md`, tracked as WINDOWS.md broken window 7.)*
- [x] **TYPE-06**: User generating models for a VARIANT-typed column gets a `JsonValue` union annotation rather than `Any`
- [x] **TYPE-07**: User can verify that a model's committed annotations still match the warehouse's current result schema via a `--check` mode, without executing a query for rows

### Typed Results (`.into(DTO)`)

- [x] **DTO-01**: User can call `.into(MyDTO)` on a query result to get Pydantic v2 model instances, converted from Arrow by arrowmodel and matched by column name
- [x] **DTO-02**: User streaming a large result can consume DTOs per batch, including from an async result via `async for`, without materializing the whole table
- [x] **DTO-03**: User whose DTO does not match the result schema gets a clear, actionable error naming the mismatched field, rather than a silent wrong-typed value
- [x] **DTO-04**: User can call `.into(DTO)` against an untyped or partially-typed model — conversion works off the Arrow result schema, never requiring typed model fields
- [x] **DTO-05**: User installs DTO support via an optional `semolina[arrowmodel]` extra; the default install does not pull arrowmodel or its Rust extension. *(Amended 2026-08-13, before planning: the original wording also promised the default install does not pull **pydantic**. It always has — `semolina` → `adbc-poolhouse` → `pydantic-settings>=2.0.0` → `pydantic>=2.7.0`, an unconditional chain since v0.3 — so pydantic cannot be gated behind this extra without dropping a base dependency, which is out of scope here. The extra gates arrowmodel alone.)*
- [x] **DTO-06**: Docs present `.into(DTO)` as the primary typed-result path, with a worked BI-backend example covering both the whole-table and streaming forms

### Codegen'd DTOs

- [ ] **DTO-07**: User can generate a typed DTO class from a canonical query, with annotations derived from `adbc_execute_schema` rather than from declared model field types
- [ ] **DTO-08**: User gets real IDE autocomplete and type checking on `.into(GeneratedDTO)` results — the generated class passes basedpyright strict
- [ ] **DTO-09**: User running codegen against a driver that does not implement `adbc_execute_schema` gets a working fallback (zero-row execution) rather than a hard failure

### Result Conversion

- [x] **RESULT-01**: User can call `fetch_df()` on a cursor to get a `pandas.DataFrame` and `fetch_polars()` to get a `polars.DataFrame`, on both the sync and async cursor
- [x] **RESULT-02**: User without pandas or polars installed gets an actionable error naming the missing package, not an `ImportError` traceback from internals

### Databricks Literals

- [x] **DBX-04**: User can filter a Databricks query on a `date`, `datetime`, or `Decimal` value — `render_literal` inlines them correctly instead of raising `NotImplementedError`

### Tooling

- [x] **TOOL-01**: Maintainers have `git.branching_strategy` restored to `milestone` in `.planning/config.json`, reverting the temporary `none` set during v0.6

## Future Requirements

Deferred, tracked, not in this roadmap.

### Async

- **ASYNC-F1**: Posture B concurrency sugar — fan-out and timeout helpers that Semolina orchestrates, which would require taking an anyio dependency
- **ASYNC-F2**: Async introspection and codegen paths using poolhouse's async `adbc_get_objects` / `adbc_get_table_schema`

### Typed Results

- **DTO-F1**: Dynamic `create_model` DTOs built at runtime from `adbc_execute_schema` (arrowmodel "level 2")

### Streaming

- **STREAM-04**: User-controllable batch/chunk size for `fetch_record_batch()`, which currently relies on ADBC defaults

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dynamic `create_model` DTOs (arrowmodel level 2) | The only tier that would probe at runtime; codegen'd DTOs give better DX and IDE types |
| Databricks materializations as a DTO source | A transparent optimizer feature, not an introspectable per-query contract; one materialization backs many query patterns, and its schema is the rollup's, not a user query's result shape. Also Databricks-only |
| DTOs derived from the `SemanticView` model | A model is the superset of all dimensions and measures; a query returns a subset with query-specific types. One static DTO per view is wrong |
| Runtime type probes | Probes run at codegen and CI `--check` time only. `.into(DTO)` needs no probe — the executed result already carries its Arrow schema |
| anyio dependency in Semolina | Posture A keeps awaits neutral, which is Trio-compatible by construction. Adopt anyio only at the exact points Semolina composes concurrency |
| Native async I/O to the warehouse socket | The Python ADBC stack has no async C API. Thread-offload over GIL-releasing native calls is the mechanism; say so plainly rather than overselling |
| Partitioned reads (`adbc_execute_partitions`) | Driver-dependent intra-query parallelism; optional angle, not committed |
| FastAPI / Django / GraphQL integration packages | The async surface is a prerequisite for these; evaluate them as their own milestone once it lands |
| `GEOGRAPHY`/`GEOMETRY`, `VECTOR`, DuckDB `UNION` type mappings | No Python-native equivalent; `TODO` plus untyped fallback. Don't solve speculatively |

## Traceability

Which phases cover which requirements. Filled during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ASYNC-01 | Phase 46 | Complete |
| ASYNC-02 | Phase 46 | Complete |
| ASYNC-03 | Phase 46 | Complete |
| ASYNC-04 | Phase 46 | Complete |
| ASYNC-05 | Phase 46 | Complete |
| ASYNC-06 | Phase 46 | Complete |
| TOOL-01 | Phase 46 | Complete |
| TYPE-01 | Phase 47 | Complete |
| TYPE-02 | Phase 47 | Complete |
| TYPE-03 | Phase 48 | Complete |
| TYPE-04 | Phase 48 | Complete |
| TYPE-05 | Phase 48 | Partial — DuckDB half complete; Databricks `interval` open (accepted limitation, needs recording) |
| TYPE-06 | Phase 48 | Complete |
| TYPE-07 | Phase 48 | Complete |
| DBX-04 | Phase 48 | Complete |
| DTO-01 | Phase 49 | Complete |
| DTO-02 | Phase 49 | Complete |
| DTO-03 | Phase 49 | Complete |
| DTO-04 | Phase 49 | Complete |
| DTO-05 | Phase 49 | Complete |
| DTO-06 | Phase 49 | Complete |
| RESULT-01 | Phase 49 | Complete |
| RESULT-02 | Phase 49 | Complete |
| DTO-07 | Phase 50 | Pending |
| DTO-08 | Phase 50 | Pending |
| DTO-09 | Phase 50 | Pending |

**Coverage:** 26/26 v0.7 requirements mapped, each to exactly one phase.
