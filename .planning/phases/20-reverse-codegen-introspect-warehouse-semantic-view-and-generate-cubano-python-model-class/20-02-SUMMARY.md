---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
plan: "02"
subsystem: engines
tags: [introspection, snowflake, databricks, tdd, reverse-codegen]
dependency_graph:
  requires:
    - 20-01  # IntrospectedField/IntrospectedView IR types, type_map functions, Engine ABC
  provides:
    - SnowflakeEngine.introspect()
    - DatabricksEngine.introspect()
    - _to_pascal_case() helper in both engine modules
  affects:
    - 20-03  # CLI wiring will call these engine methods
tech_stack:
  added: []
  patterns:
    - TDD (RED/GREEN/REFACTOR)
    - Lazy imports inside method body (consistent with execute() pattern)
    - cast() for basedpyright strict dict type narrowing from Any
    - Module-level private helper (_to_pascal_case) duplicated per file for independence
key_files:
  created: []
  modified:
    - src/cubano/engines/snowflake.py
    - src/cubano/engines/databricks.py
    - tests/unit/test_snowflake_engine.py
    - tests/unit/test_databricks_engine.py
decisions:
  - "_to_pascal_case() duplicated in each engine file (not shared utility) to keep engine files independent — same rationale as existing lazy import pattern"
  - "cast('dict[str, object]', type_obj) used for Databricks type_dict narrowing under basedpyright strict — isinstance check on Any narrows to dict[Unknown, Unknown] which must be cast"
  - "Snowflake columns lowercased via desc[0].lower() for safe dict access regardless of warehouse column name casing"
  - "RuntimeError message prefix: 'Snowflake introspection failed:' / 'Databricks introspection failed:' — distinct from execute() error prefixes for easier debugging"
metrics:
  duration_minutes: 5
  completed_date: "2026-02-24"
  tasks_completed: 3
  files_modified: 4
requirements-completed: []
---

# Phase 20 Plan 02: Warehouse Introspection Implementations Summary

Implemented `SnowflakeEngine.introspect()` and `DatabricksEngine.introspect()` — the real warehouse-talking methods that the reverse codegen CLI will call. Both engines now query warehouse metadata, parse field schema, and return typed `IntrospectedView` IR objects ready for code rendering.

## What Was Built

**SnowflakeEngine.introspect(view_name):**
- Executes `SHOW COLUMNS IN SEMANTIC VIEW {view_name}` against Snowflake
- Extracts column names from `cur.description` (lowercased for safe dict access)
- Parses each row into a dict via `zip(columns, row, strict=True)`
- Lowercases `kind` (warehouse returns `METRIC`/`DIMENSION`/`FACT` in uppercase)
- Parses `data_type` JSON column and maps via `snowflake_json_type_to_python()`
- Emits `"TODO: {raw_json}"` for unmappable types (GEOGRAPHY, ARRAY, VARIANT, etc.)
- Propagates `comment` column into `IntrospectedField.description`
- Raises `RuntimeError("Snowflake introspection failed: ...")` on `ProgrammingError`/`DatabaseError`

**DatabricksEngine.introspect(view_name):**
- Executes `DESCRIBE TABLE EXTENDED {view_name} AS JSON` against Databricks
- Calls `fetchone()` and parses `row[0]` as JSON to get `schema["columns"]`
- Uses `col.get("is_measure", False)` to avoid `KeyError` when key is absent
- Maps `is_measure=True` → `"metric"`, absent/`False` → `"dimension"` (no `"fact"`)
- Handles both dict and scalar `type` values via `isinstance` + `cast()`
- Maps types via `databricks_type_to_python()`; emits `"TODO:"` for unmappable
- Propagates `comment` into `IntrospectedField.description`
- Raises `RuntimeError("Databricks introspection failed: ...")` on `DatabaseError`/`OperationalError`/`Error`

**_to_pascal_case(view_name) (both engine files):**
- Extracts last segment after final `.` (handles `schema.view` and `catalog.schema.view`)
- Splits by `_` and capitalises each word: `"sales_revenue_view"` → `"SalesRevenueView"`

## Test Coverage

21 new tests (TDD RED → GREEN):

**TestSnowflakeEngineIntrospect (11 tests):**
- Basic parsing of metric + dimension + fact fields
- Uppercase kind → lowercase field_type conversion
- FIXED scale=0 → `int`, FIXED scale=2 → `float`
- GEOGRAPHY unmappable type → `data_type` starts with `"TODO:"`
- `comment` column → `description` populated
- SQL verification: `SHOW COLUMNS IN SEMANTIC VIEW view_name`
- PascalCase class name from simple and schema-qualified view names
- `ProgrammingError` → `RuntimeError` with `"Snowflake introspection failed"`
- `DatabaseError` → `RuntimeError` with `"Snowflake introspection failed"`

**TestDatabricksEngineIntrospect (10 tests):**
- Basic parsing of measure and dimension fields
- Absent `is_measure` key → `"dimension"` (no `KeyError`)
- Array type → `data_type` starts with `"TODO:"`
- `comment` key → `description` populated
- SQL verification: `DESCRIBE TABLE EXTENDED view_name AS JSON`
- PascalCase class name from simple and three-part Unity Catalog view names
- `DatabaseError` / `OperationalError` / `Error` → `RuntimeError` with `"Databricks introspection failed"`

## Commits

| Hash | Phase | Description |
|------|-------|-------------|
| 916ad39 | RED | test(20-02): add failing introspect tests for SnowflakeEngine and DatabricksEngine |
| 336b5fc | GREEN | feat(20-02): implement introspect() on SnowflakeEngine and DatabricksEngine |

## Verification Results

```
uv run pytest tests/unit/test_snowflake_engine.py tests/unit/test_databricks_engine.py -k introspect
21 passed in 0.78s

uv run pytest tests/
701 passed in 1.57s  (no regressions)

uv run basedpyright src/cubano/engines/snowflake.py src/cubano/engines/databricks.py
0 errors, 0 warnings, 0 notes

uv run ruff check src/cubano/engines/
All checks passed!
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed basedpyright type errors in DatabricksEngine.introspect()**
- **Found during:** Task 2 (GREEN) — basedpyright reported 3 errors after initial implementation
- **Issue 1:** `cur.fetchone()` returns `Unknown` type; subscripting `row[0]` was `reportOptionalSubscript`
- **Issue 2:** `isinstance(type_obj, dict)` on `Any` narrows to `dict[Unknown, Unknown]`, causing `reportUnknownVariableType` on the union with `dict[str, object]`
- **Fix:** Annotated `row: Any` explicitly; used `cast("dict[str, object]", type_obj)` in the dict branch; added `cast` to imports
- **Files modified:** `src/cubano/engines/databricks.py`
- **Commit:** Included in GREEN commit 336b5fc

## Self-Check: PASSED
