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

## Untypeable-case taxonomy (2026-08-01)

The `TODO:`/`None` fall-throughs sort into four categories with different
resolutions:

1. **Map gaps — typeable, pending policy**: DuckDB `DECIMAL` (currently
   untypeable while Snowflake FIXED scale>0 maps to lossy `float` — the two
   backends disagree on how to be wrong about money), DuckDB
   `UUID`/`JSON`/`ENUM`/`TIMESTAMP_S/_MS/_NS`, Databricks `interval`. Fix via
   the Decimal policy + map additions.
2. **Compositional (ARRAY/LIST, STRUCT/OBJECT, MAP)** — untypeable from
   *metadata* (Snowflake `SHOW COLUMNS` erases element types: just "ARRAY")
   but fully typeable from the *probe* (Arrow schema carries nested types;
   arrowmodel handles nested structs). Another argument for
   probe-as-source-of-truth.
3. **Semantically dynamic (VARIANT)** — **DECIDED: type as a `JsonValue`
   union** (recursive `str | int | float | bool | None | list | dict`), not
   `Any` — honest shape, still narrowable by pyright. DTO side: use
   `pydantic.JsonValue`. Model side: semolina core has no pydantic dep, so a
   small `semolina.JsonValue` alias (or pydantic import only in generated
   code). Runtime wrinkle to verify in the probe: VARIANT typically arrives
   over Arrow as a JSON *string* — validated path wants `Json[JsonValue]`
   (parse-then-validate); arrowmodel fast path would leave `str`.
4. **No Python-native equivalent (GEOGRAPHY/GEOMETRY, VECTOR, DuckDB
   UNION)** — `TODO` + untyped fallback; don't solve speculatively.

In practice the tail is short: metrics are aggregations (numeric — the
question is Decimal-vs-float, not typeability); dimensions are group-by
attributes (str/date/int/bool). Category 1 is what users actually hit.

## Probe mechanics + timing (2026-08-01)

`adbc_execute_schema` = ADBC 1.1 `AdbcStatementExecuteSchema`: one server
round trip returning only the result Arrow schema — no rows, no data. Verify
per driver (may be `NOT_IMPLEMENTED`); fallback is a `LIMIT 0`/`WHERE 1=0`
execution — still zero rows but actually compiles+runs on the warehouse
(cost/latency on Snowflake/Databricks). DuckDB probe is in-process, no
network.

Probes run at **codegen time** (dev, one per view/canonical query, baked into
source) and **CI `--check`** (one per DTO-bearing query) — **never at
runtime**. `.into(DTO)` needs no probe: the executed result carries its Arrow
schema; arrowmodel converts by name and raises on mismatch. The probe only
moves that failure earlier. Level-2 dynamic `create_model` would probe at
runtime (once per query shape) — a reason it's the least attractive tier.

CI wrinkle: `--check` could run offline via pytest-adbc-replay cassettes
(record the probe response once, replay in CI) — hermetic drift-checking.

## Deliverable

A decision doc: type-mapping policy per backend (incl. Decimal + nullability
stance), whether filter `value` typing is worth wiring, and which source of
truth codegen uses. Feeds the arrowmodel/DTO work
(`2026-07-10-arrowmodel-result-serialization-integration.md`) — `.into(DTO)`
verification and generated DTO annotations depend on the same answers.

Source: user observation (2026-08-01) that semantic view definitions don't
carry metric types — inferred from underlying tables, "possibilities are
likely complex"; confirmed by the DuckDB probe workaround already in-repo.
