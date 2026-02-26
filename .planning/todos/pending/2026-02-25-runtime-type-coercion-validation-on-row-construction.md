---
created: 2026-02-25T00:01:50.163Z
title: Runtime type coercion/validation on Row construction
area: api
files:
  - src/cubano/results.py
  - src/cubano/fields.py
---

## Problem

`Metric[int]`, `Dimension[str]`, `Fact[float]` type annotations are currently static hints only — the type checker benefits at authoring time but there is no runtime enforcement. When query results come back from the warehouse, users get whatever Python type the connector returns (often `Decimal` for numeric columns) regardless of the declared field type. The mismatch is invisible at runtime.

Example: `revenue = Metric[float]()` — Snowflake connector returns `Decimal("123.45")`. User annotates downstream code as `float` based on the model declaration, gets `Decimal` at runtime, and may never notice until a subtle precision/type bug surfaces.

The type hint becomes misleading: it promises a type the library doesn't enforce.

## Solution

At `Row` construction time (when query results are populated from warehouse response), validate each field value's Python type against the declared `T` in `Metric[T]`/`Dimension[T]`/`Fact[T]`.

Two design options to evaluate:
1. **Validate-and-raise** — raise `CubanoTypeError` (or similar) if value type doesn't match declared type. Forces users to declare the correct type (e.g. `Metric[Decimal]` not `Metric[float]`). More honest, avoids silent precision loss.
2. **Coerce** — attempt `T(value)` cast. Risk: `Decimal` → `float` is lossy; `str` → `int` might silently succeed on "123" but fail on "abc". Mirrors Pydantic behaviour.

**Recommended starting point:** validate-and-raise with clear error messages. Coercion can be added as opt-in later (`strict=False` on the model or engine).

Edge cases to handle:
- `None` values for fields not declared as `T | None`
- `Decimal` vs `float` (most common mismatch for Snowflake/Databricks numeric columns)
- `int` vs `Decimal` (COUNT aggregates)
- Unknown/untyped fields (`Metric[Any]` should skip validation)
