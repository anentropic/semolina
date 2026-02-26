---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
plan: 01
subsystem: codegen
tags: [dataclasses, type-mapping, abc, reverse-codegen, snowflake, databricks]

# Dependency graph
requires:
  - phase: 09-codegen-cli
    provides: "Codegen codegen module structure (models.py, renderer.py) that introspector.py lives alongside"
  - phase: 03-sql-generation-mock-backend
    provides: "Engine ABC (base.py) that gains the abstract introspect() method"
provides:
  - "IntrospectedField frozen dataclass: name, field_type, data_type, description"
  - "IntrospectedView frozen dataclass: view_name, class_name, fields"
  - "snowflake_json_type_to_python(): maps Snowflake JSON type dicts to Python annotation strings"
  - "databricks_type_to_python(): maps Databricks type dicts to Python annotation strings"
  - "Engine.introspect() abstract method on Engine ABC"
  - "MockEngine.introspect() stub raising NotImplementedError"
affects:
  - "20-02: Databricks introspection implementation (DatabricksEngine.introspect())"
  - "Future Snowflake introspection implementation"
  - "Python code renderer (will consume IntrospectedView)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Frozen dataclasses as IR (intermediate representation) for codegen pipeline"
    - "TYPE_CHECKING guard for IntrospectedView import in Engine ABC to avoid circular imports"
    - "Sentinel None return from type-mapping functions to trigger TODO comment in renderer"
    - "case-insensitive lookup via .upper()/.lower() normalization before dict lookup"

key-files:
  created:
    - src/cubano/codegen/introspector.py
    - src/cubano/codegen/type_map.py
    - tests/unit/codegen/test_introspector.py
    - tests/unit/codegen/test_type_map.py
  modified:
    - src/cubano/engines/base.py
    - src/cubano/engines/mock.py
    - src/cubano/engines/databricks.py
    - src/cubano/engines/snowflake.py

key-decisions:
  - "IntrospectedField.data_type is str | None (not str) — None signals renderer to emit TODO comment instead of annotation"
  - "TYPE_CHECKING guard for IntrospectedView in base.py/mock.py/databricks.py/snowflake.py prevents circular imports at runtime"
  - "DatabricksEngine and SnowflakeEngine get NotImplementedError stubs immediately (ABC requires all abstract methods) — actual implementation is Plan 02"
  - "Type lookup is case-insensitive (uppercase for Snowflake, lowercase for Databricks) — normalizes before dict lookup"

patterns-established:
  - "TDD: test files committed first (RED), implementation committed second (GREEN)"
  - "Engine ABC extended with new abstract method requires all concrete Engine subclasses to add stubs immediately"

requirements-completed:
  - CODEGEN-REVERSE

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 20 Plan 01: Introspection IR + Type Mapping + Engine ABC Summary

**Frozen dataclasses IntrospectedField/IntrospectedView plus SQL-to-Python type maps for Snowflake (FIXED/TEXT/REAL/etc.) and Databricks (bigint/string/double/etc.), with Engine ABC extended by abstract introspect() method**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T06:20:45Z
- **Completed:** 2026-02-24T06:25:01Z
- **Tasks:** 1 (TDD: RED + GREEN + REFACTOR)
- **Files modified:** 8

## Accomplishments

- Established the shared IR (intermediate representation) dataclasses consumed by all downstream codegen pipeline stages
- Implemented complete SQL-to-Python type mapping for both Snowflake (11 mapped types, 5 returning None) and Databricks (14 mapped types, 4 returning None)
- Extended Engine ABC with `introspect()` abstract method, forcing all concrete engines to declare their intent

## Task Commits

TDD cycle with two commits:

1. **RED: Failing tests** - `f089fe1` (test) — test_introspector.py (15 tests) + test_type_map.py (75 tests)
2. **GREEN: Implementation** - `b474ec2` (feat) — introspector.py, type_map.py, base.py, mock.py, databricks.py, snowflake.py

No REFACTOR commit needed — code was clean after GREEN.

**Plan metadata:** pending (docs commit)

## Files Created/Modified

- `src/cubano/codegen/introspector.py` - IntrospectedField and IntrospectedView frozen dataclasses
- `src/cubano/codegen/type_map.py` - snowflake_json_type_to_python and databricks_type_to_python functions
- `src/cubano/engines/base.py` - Engine ABC extended with abstract introspect() method
- `src/cubano/engines/mock.py` - MockEngine.introspect() raises NotImplementedError
- `src/cubano/engines/databricks.py` - DatabricksEngine.introspect() stub (NotImplementedError, future Plan 02)
- `src/cubano/engines/snowflake.py` - SnowflakeEngine.introspect() stub (NotImplementedError, future plan)
- `tests/unit/codegen/test_introspector.py` - 15 tests for IntrospectedField/View construction, immutability, equality
- `tests/unit/codegen/test_type_map.py` - 75 tests covering all Snowflake and Databricks type mappings

## Decisions Made

- `IntrospectedField.data_type` is `str | None` (not `str`) — `None` signals the renderer to emit a TODO comment instead of a type annotation when encountering GEOGRAPHY, VARIANT, ARRAY, and similar complex types with no clean Python equivalent
- `TYPE_CHECKING` guard for `IntrospectedView` in `base.py`, `mock.py`, `databricks.py`, and `snowflake.py` prevents circular imports at runtime while keeping static analysis happy
- `DatabricksEngine` and `SnowflakeEngine` required immediate `NotImplementedError` stubs because Python's ABC enforcement requires all abstract methods to be overridden before instantiation — the actual Databricks implementation is Plan 02
- Type lookups are normalized to uppercase (Snowflake) or lowercase (Databricks) before dict lookup, providing case-insensitive handling without duplicate dict entries

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added introspect() stubs to DatabricksEngine and SnowflakeEngine**

- **Found during:** GREEN phase (running full test suite after implementing mock.py stub)
- **Issue:** Adding `introspect()` as abstract to Engine ABC caused `DatabricksEngine` and `SnowflakeEngine` to fail instantiation in their test files with `TypeError: Can't instantiate abstract class`
- **Fix:** Added `NotImplementedError` stubs to both engines with a docstring noting future implementation
- **Files modified:** `src/cubano/engines/databricks.py`, `src/cubano/engines/snowflake.py`
- **Verification:** `uv run pytest tests/` - all 680 tests pass
- **Committed in:** b474ec2 (GREEN phase commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** Necessary consequence of extending Engine ABC. The plan notes MockEngine needs a stub but implicitly relies on DatabricksEngine/SnowflakeEngine also needing stubs. No scope creep.

## Issues Encountered

- `blacken-docs` pre-commit hook reformatted multi-line import in docstring examples — accepted auto-format, committed on second attempt
- `D200` ruff lint on module-level docstring in test_introspector.py — fixed to single-line format

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can implement `DatabricksEngine.introspect()` using the `IntrospectedView`/`IntrospectedField` IR defined here
- The type maps in `type_map.py` are ready for use in the Databricks introspection implementation
- `MockEngine.introspect()` raises `NotImplementedError` as specified — test code for the CLI should use `SnowflakeEngine` or `DatabricksEngine` mocks for introspection testing

---
*Phase: 20-reverse-codegen*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: src/cubano/codegen/introspector.py
- FOUND: src/cubano/codegen/type_map.py
- FOUND: tests/unit/codegen/test_introspector.py
- FOUND: tests/unit/codegen/test_type_map.py
- FOUND commit f089fe1 (RED: failing tests)
- FOUND commit b474ec2 (GREEN: implementation)
