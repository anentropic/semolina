# Requirements: Semolina v0.7 — Async & Typed Results

**Defined:** 2026-08-01
**Core Value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

**Milestone goal:** Give Semolina a non-blocking async query surface and an honest, verified type story running from warehouse metadata through to Pydantic DTOs.

## v0.7 Requirements

### Async Query Surface

- [ ] **ASYNC-01**: User can `await engine.aexecute(query)` to run a query without blocking the event loop, getting back the same result surface as `.execute()`
- [ ] **ASYNC-02**: User can `await Sales.query().metrics(...).aexecute()` — an async twin of `.execute()` on the query builder
- [ ] **ASYNC-03**: User can `async for row in result` to stream rows lazily, with batches fetched off-thread by adbc-poolhouse and mapped to `Row` by Semolina
- [ ] **ASYNC-04**: User installs async support via a `semolina[async]` extra that pins `adbc-poolhouse[async]>=1.5.0`; the default sync install gains no new dependencies
- [ ] **ASYNC-05**: User's async code runs identically under asyncio and Trio — Semolina library code contains zero `asyncio.*` references and no anyio import, verified by an automated check
- [ ] **ASYNC-06**: User cancelling an in-flight async query (framework timeout or task cancellation) causes the underlying warehouse query to be cancelled via `adbc_cancel`, not merely abandoned

### Warehouse Type Fidelity

- [ ] **TYPE-01**: Maintainers have an empirical comparison, per backend, of introspection-time field types against query-time `adbc_execute_schema` result types, run over existing Snowflake cassettes and jaffle-shop DuckDB
- [ ] **TYPE-02**: The project has a committed type-mapping decision doc covering the Decimal policy, the metric-nullability stance, and which source of truth codegen uses (probe vs metadata)
- [ ] **TYPE-03**: User generating models for decimal-typed warehouse columns gets the type the decision doc specifies, applied consistently across Snowflake, Databricks, and DuckDB — the three backends no longer disagree about money
- [ ] **TYPE-04**: User generating models gets metric annotations whose nullability reflects the decision doc's stance (metrics are NULL on empty groups)
- [ ] **TYPE-05**: User generating models for the category-1 map gaps — DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS` and Databricks `interval` — gets a concrete Python type rather than a `TODO:` placeholder
- [ ] **TYPE-06**: User generating models for a VARIANT-typed column gets a `JsonValue` union annotation rather than `Any`
- [ ] **TYPE-07**: User can verify that a model's committed annotations still match the warehouse's current result schema via a `--check` mode, without executing a query for rows

### Typed Results (`.into(DTO)`)

- [ ] **DTO-01**: User can call `.into(MyDTO)` on a query result to get Pydantic v2 model instances, converted from Arrow by arrowmodel and matched by column name
- [ ] **DTO-02**: User streaming a large result can consume DTOs per batch, including from an async result via `async for`, without materializing the whole table
- [ ] **DTO-03**: User whose DTO does not match the result schema gets a clear, actionable error naming the mismatched field, rather than a silent wrong-typed value
- [ ] **DTO-04**: User can call `.into(DTO)` against an untyped or partially-typed model — conversion works off the Arrow result schema, never requiring typed model fields
- [ ] **DTO-05**: User installs DTO support via an optional `semolina[arrowmodel]` extra; the default install does not pull pydantic or the Rust extension
- [ ] **DTO-06**: Docs present `.into(DTO)` as the primary typed-result path, with a worked BI-backend example covering both the whole-table and streaming forms

### Codegen'd DTOs

- [ ] **DTO-07**: User can generate a typed DTO class from a canonical query, with annotations derived from `adbc_execute_schema` rather than from declared model field types
- [ ] **DTO-08**: User gets real IDE autocomplete and type checking on `.into(GeneratedDTO)` results — the generated class passes basedpyright strict
- [ ] **DTO-09**: User running codegen against a driver that does not implement `adbc_execute_schema` gets a working fallback (zero-row execution) rather than a hard failure

### Result Conversion

- [ ] **RESULT-01**: User can call `fetch_df()` on a cursor to get a `pandas.DataFrame` and `fetch_polars()` to get a `polars.DataFrame`, on both the sync and async cursor
- [ ] **RESULT-02**: User without pandas or polars installed gets an actionable error naming the missing package, not an `ImportError` traceback from internals

### Databricks Literals

- [ ] **DBX-04**: User can filter a Databricks query on a `date`, `datetime`, or `Decimal` value — `render_literal` inlines them correctly instead of raising `NotImplementedError`

### Tooling

- [ ] **TOOL-01**: Maintainers have `git.branching_strategy` restored to `milestone` in `.planning/config.json`, reverting the temporary `none` set during v0.6

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
| ASYNC-01 | Phase 46 | Pending |
| ASYNC-02 | Phase 46 | Pending |
| ASYNC-03 | Phase 46 | Pending |
| ASYNC-04 | Phase 46 | Pending |
| ASYNC-05 | Phase 46 | Pending |
| ASYNC-06 | Phase 46 | Pending |
| TOOL-01 | Phase 46 | Pending |
| TYPE-01 | Phase 47 | Pending |
| TYPE-02 | Phase 47 | Pending |
| TYPE-03 | Phase 48 | Pending |
| TYPE-04 | Phase 48 | Pending |
| TYPE-05 | Phase 48 | Pending |
| TYPE-06 | Phase 48 | Pending |
| TYPE-07 | Phase 48 | Pending |
| DBX-04 | Phase 48 | Pending |
| DTO-01 | Phase 49 | Pending |
| DTO-02 | Phase 49 | Pending |
| DTO-03 | Phase 49 | Pending |
| DTO-04 | Phase 49 | Pending |
| DTO-05 | Phase 49 | Pending |
| DTO-06 | Phase 49 | Pending |
| RESULT-01 | Phase 49 | Pending |
| RESULT-02 | Phase 49 | Pending |
| DTO-07 | Phase 50 | Pending |
| DTO-08 | Phase 50 | Pending |
| DTO-09 | Phase 50 | Pending |

**Coverage:** 26/26 v0.7 requirements mapped, each to exactly one phase.
