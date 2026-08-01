---
created: 2026-08-01T00:00:00.000Z
title: "Research: warehouse type fidelity for metric/dimension typing"
area: api
files:
  - src/semolina/codegen/type_map.py
  - src/semolina/engines/snowflake.py
  - src/semolina/engines/databricks.py
  - src/semolina/engines/duckdb.py
  - src/semolina/fields.py
---

## Problem

Warehouse semantic view *definitions* don't declare types for metrics — a
metric is an aggregation expression whose type is inferred from underlying
tables. Everything in Semolina's typing story (codegen `Metric[float]`
annotations, prospective `value: T` filter typing, DTO/arrowmodel typing)
rests on inferred types of unverified fidelity. Research needed before
committing to a typing policy.

## What each backend actually gives us (repo evidence, 2026-08-01)

- **Snowflake** (`engines/snowflake.py:165`): `SHOW COLUMNS IN VIEW` returns a
  resolved `data_type` JSON per metric/dimension — Snowflake infers
  server-side and reports the result. Mapping is lossy: FIXED scale>0 →
  `float` (not `Decimal`); unmapped types → `TODO:` placeholder.
- **Databricks** (`engines/databricks.py:168`): `DESCRIBE TABLE EXTENDED ...
  AS JSON` returns per-column types incl. measures (`is_measure`). `decimal`
  → `float`, also lossy.
- **DuckDB** (`engines/duckdb.py:180-230`): `DESCRIBE SEMANTIC VIEW` carries
  **no type info at all**. Introspection already probes with a query-shaped
  `DESCRIBE SELECT * FROM semantic_view(...)` and reads inferred output types
  back — direct proof that definition-time types don't exist there.

So: two backends report an inferred type of unknown fidelity; one reports
nothing and we already infer via a probe.

## Research questions

1. **Fidelity**: per backend, does the introspection-time metric type always
   equal the query-time result type (`adbc_execute_schema`)? Known suspects:
   nullability (empty groups make metrics NULL), decimal precision widening
   under SUM, `AVG(int)` → double, COUNT → int64. Empirical check is cheap —
   Snowflake cassettes + jaffle-shop DuckDB exist; compare introspected type
   vs `adbc_execute_schema` for the same fields.
2. **Decimal policy**: `NUMBER(38,2)` / `decimal` currently map to `float`.
   Should they map to `decimal.Decimal`? (Arrow decimal128 round-trips
   exactly; pydantic/arrowmodel support Decimal. Float is convenient but
   silently lossy for money — and this audience queries revenue.)
3. **Nullability**: introspection doesn't capture nullable; the Arrow result
   schema does. Should generated metric annotations be `T | None` by default
   (metrics are NULL on empty groups)? Note this is the *selected-and-NULL*
   case — distinct from the rejected all-fields-Optional row-typing problem.
4. **Filter-value typing**: is wiring `Field.__gt__(value: T)` safe on
   inferred types? Per typing policy (exact return types, lenient arg types)
   probably want lenient widening — e.g. `int` accepted against a
   float/decimal metric — not strict `T`.
5. **Strategy**: trust introspection at codegen time and verify against
   `adbc_execute_schema` (a `--check` mode), or derive types from the probe
   always (DuckDB-style, uniform across backends)? The probe is
   backend-agnostic ground truth and needs no per-warehouse metadata parsing.

## Fallback policy (decided 2026-08-01)

Untyped stays a first-class fallback at every layer — this is already the
floor, not an addition:

- `Metric()` ≡ `Metric[Any]()` is documented shorthand; renderer emits
  `TODO: <raw type>` for unmappable metadata types. Keep both.
- Layers degrade independently: untyped model fields still build queries;
  `.into(DTO)`/arrowmodel converts by name against Arrow data, so typed rows
  never require a typed model; any filter `value:` typing must collapse to
  permissive for `Field[Any]`.
- Probe-based codegen (`adbc_execute_schema`) always yields a *determined*
  Arrow type (the warehouse must resolve one to execute) — remaining issues
  are mapping choices (VARIANT → str vs parsed, tz-ness, GEOGRAPHY), not
  ambiguity. Metadata-based codegen is the fallible path.
- Probe + `--check` need a live connection; offline codegen falls back to
  metadata types or untyped.

## Deliverable

A decision doc: type-mapping policy per backend (incl. Decimal + nullability
stance), whether filter `value` typing is worth wiring, and which source of
truth codegen uses. Feeds the arrowmodel/DTO work
(`2026-07-10-arrowmodel-result-serialization-integration.md`) — `.into(DTO)`
verification and generated DTO annotations depend on the same answers.

Source: user observation (2026-08-01) that semantic view definitions don't
carry metric types — inferred from underlying tables, "possibilities are
likely complex"; confirmed by the DuckDB probe workaround already in-repo.
