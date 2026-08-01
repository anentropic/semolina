---
created: 2026-07-10T00:00:00.000Z
title: arrowmodel integration for typed DTO / result serialization
area: api
resolves_phase: 49
files:
  - src/semolina/cursor.py
  - src/semolina/codegen/
  - docs/src/how-to
  - docs/src/tutorials
---

## Idea

Integrate [arrowmodel](https://anentropic.github.io/arrowmodel/) (Rust-backed
Arrow `RecordBatch`/`Table` -> Pydantic v2 converter; ~2x faster than
`to_pylist`+validate; streaming + nested-struct aware) as Semolina's typed
result-serialization / DTO layer, for the BI-dashboard-backend audience. It
plugs straight onto `SemolinaCursor.fetch_arrow_table()` /
`fetch_record_batch()` (cursor.py:139,165) — both already exist.

## Scrutiny — what to derive the DTO from (analysis 2026-07-10)

**Not from the SemanticView model.** A model is the superset of all
dimensions/measures; a query returns a subset with query-specific types. One
static DTO per view is wrong.

**Not from Databricks "materializations" (rejected).** Databricks metric-view
materializations are an *optional, transparent optimizer feature* — per docs,
"the query engine automatically rewrites queries to use materialized views when
appropriate." They are NOT introspectable per-query-pattern contracts: one
materialization can back many query patterns, its schema is the rollup's (not a
user query's result shape), and coupling a public DTO to a Databricks-managed
internal that refreshes transparently is fragile + Databricks-only. Every axis
this idea reached for (a fixed knowable result schema) is better served below.
(If we ever want deeper detail: docs.databricks.com metric-views materialization
reference — but the transparent-optimizer nature already decides it.)

**From the QUERY — backend-agnostic.** The `Query` already tracks its exact
output shape: `_metrics` + `_dimensions` as typed fields (query.py:76-80). The
query IS the "specific result shape". Works for Snowflake/Databricks/DuckDB
alike.

**Ground-truth types via `adbc_execute_schema`.** Query-declared field types give
names/ordering but aggregation changes types (`SUM(int)`->int64/decimal,
`AVG`->double, empty groups -> nullable). ADBC `adbc_execute_schema` returns the
exact result Arrow schema WITHOUT executing (present on the sync cursor AND
poolhouse `AsyncCursor`). Use it as the authoritative typer; Arrow schema ->
arrowmodel via `create_model` or codegen.

## Delivery levels (increasing effort)

1. **Demo / how-to — zero new code.** `MyDTO.convert(result.fetch_arrow_table())`
   plus streaming/async: `async for batch in reader: MyDTO.convert(batch)`. This
   is the "integration or demo" to start with; compounds with the async work
   ([[reference_adbc_gil_release_async]]) — per-batch convert over
   `AsyncRecordBatchReader`.
2. **Dynamic `create_model`** from `adbc_execute_schema` — automatic DTO, no IDE
   types.
3. **Codegen typed DTOs** from a saved/canonical query — best DX; fits the
   existing `src/semolina/codegen/` machinery (already reverse-generates models
   from introspection).

**Recommendation:** ship level 1 first (free, proves value, pairs with async);
levels 2-3 as follow-ons. Drop the materialization-introspection path.

## Open questions for planning

- Optional `[arrowmodel]` extra vs hard dep (arrowmodel pulls pydantic v2 +
  Rust ext) — likely optional extra, like the async story.
- Type mapping: Semolina field types + Arrow schema -> Pydantic annotations
  (nullability from Arrow, not from declared field).
- Whether Semolina owns a helper (`result.convert(MyDTO)`) or just documents the
  passthrough. Lean: document first, add a thin helper only if it earns its keep.

Source: user exploring an arrowmodel integration/demo (2026-07-10); flagged the
Databricks-materialization angle as needing scrutiny (it does — rejected above).
