---
phase: 42-codegen-field-type-inference
plan: 01
subsystem: testing
tags: [codegen, syrupy, snapshot-testing, snowflake, databricks, pytest, tdd]

# Dependency graph
requires:
  - phase: 41-duckdb-file-backed-codegen
    provides: render_and_format + DuckDB codegen E2E snapshot precedent
provides:
  - RED raise-path unit test for _field_class_for (acceptance contract for Plan 02 strict-raise change)
  - Offline Snowflake codegen E2E snapshot test (Metric/Dimension/Fact emission)
  - Offline Databricks codegen E2E snapshot test (Metric/Dimension only, no Fact)
  - Committed .ambr snapshot blocks for Snowflake + Databricks codegen output
affects: [42-02-make-field-class-strict, 42-03-docs-and-closeout]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Offline engine introspection via in-module sys.modules connector mocks (no CliRunner, no credentials loader)"
    - "Per-backend cursor stub shape: Snowflake fetchall 4-tuples vs Databricks fetchone single JSON 1-tuple"

key-files:
  created: []
  modified:
    - tests/unit/codegen/test_python_renderer.py
    - tests/unit/codegen/test_codegen_e2e.py
    - tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr

key-decisions:
  - "Co-located SF/Databricks codegen E2E tests in test_codegen_e2e.py sharing the existing .ambr (keeps all codegen E2E snapshots together)"
  - "Copied the sys.modules connector-mock seams into the test module rather than importing across test files"
  - "Snowflake mock seam made a non-autouse named fixture applied via @pytest.mark.usefixtures, so it does not affect the credential-free DuckDB CLI test in the same module"

patterns-established:
  - "Offline codegen snapshot: engine.introspect() -> render_and_format([view]) -> assert == snapshot, with mocked connector"
  - "Bug-fix-first discipline: commit the RED acceptance test before the production change (Plan 02)"

requirements-completed: []  # DKGEN-05 is closed in Plan 03, not here; this plan only establishes the failing acceptance contract.

# Metrics
duration: ~10min
completed: 2026-06-09
---

# Phase 42 Plan 01: Wave 0 Codegen Field-Type Acceptance Tests Summary

**Three Wave 0 failing/passing tests defining the phase contract: a RED `ValueError` raise-path unit test for `_field_class_for`, plus offline Snowflake (Metric/Dimension/Fact) and Databricks (Metric/Dimension, no Fact) codegen snapshot tests — all running without credentials or a live warehouse.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-09T17:36Z (approx)
- **Completed:** 2026-06-09T17:38Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `test_field_class_for_unrecognized_role_raises`, committed RED against the still-lenient `_field_class_for` (CLAUDE.md bug-fix-first discipline) — it stays red until Plan 02.
- Added `test_codegen_snowflake_field_types`: offline introspect→render snapshot proving Snowflake emits `Metric[int]`, `Dimension[str]`, and `Fact[datetime.date]`.
- Added `test_codegen_databricks_field_types`: offline introspect→render snapshot proving Databricks emits `Metric[float]` and `Dimension[str]` only, with the no-Fact absence documented as intentional in the test docstring.
- Generated and committed new `.ambr` snapshot blocks for both backends; the DuckDB regression-guard snapshot stays byte-identical (still green).

## Task Commits

1. **Task 1: Add the strict-raise RED unit test** - `51ad93a` (test)
2. **Task 2: Add offline Snowflake codegen snapshot test** - `b4ed3c0` (test)
3. **Task 3: Add offline Databricks codegen snapshot test (no Fact)** - `97417f4` (test)

## Files Created/Modified

- `tests/unit/codegen/test_python_renderer.py` - Added `import pytest` and module-level `test_field_class_for_unrecognized_role_raises` asserting `ValueError` with match "Unrecognized field role".
- `tests/unit/codegen/test_codegen_e2e.py` - Added Snowflake + Databricks mock seams (`_mock_snowflake_in_sys_modules` fixture, `_create_mock_databricks` helper, exception stubs) and the two offline codegen snapshot tests.
- `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` - New `test_codegen_snowflake_field_types` block (Metric/Dimension/Fact) and `test_codegen_databricks_field_types` block (Metric/Dimension, no Fact field).

## Decisions Made

- Made the Snowflake `sys.modules` mock a **named (non-autouse) fixture** applied via `@pytest.mark.usefixtures`, so the DuckDB CLI test (which needs the real import path / credential-free `--database` flow) in the same module is unaffected. The Databricks seam is scoped with a local `patch.dict` inside the test, matching the engine-test precedent.
- Co-located both new tests in `test_codegen_e2e.py` sharing the existing `.ambr` file (recommended by PATTERNS), keeping all codegen E2E snapshots in one place.

## Deviations from Plan

None - plan executed exactly as written. (No production code touched; `python_renderer.py` is unchanged, as required.)

## Issues Encountered

- `uv run` panicked under the command sandbox (`system-configuration` NULL object / Tokio executor). Resolved by running test/commit commands with the sandbox disabled. No code impact.
- The pre-commit `ruff` hook reformatted the new module docstring in `test_codegen_e2e.py` (D213: summary on second line) and aborted the first commit attempt; re-staged the hook-fixed file and the commit succeeded. The hook fix is a CLAUDE.md-aligned formatting correction, not a behavior change.

## Verification

- `uv run pytest tests/unit/codegen/test_python_renderer.py::test_field_class_for_unrecognized_role_raises` → FAILS (RED, expected; fixed in Plan 02).
- `uv run pytest tests/unit/codegen/test_codegen_e2e.py -k "snowflake or databricks"` → both PASS.
- `uv run pytest tests/unit/codegen/` → 220 passed, 1 failed (only the intentional RED raise-path test); DuckDB regression snapshot green.
- Snowflake `.ambr` block contains `Metric[`, `Dimension[`, and `Fact[`. Databricks `.ambr` block contains `Metric[` and `Dimension[` with no `Fact[` field assignment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can now make `_field_class_for` strict (raise on unrecognized role) and the RED test `51ad93a` will turn green; the DuckDB snapshot must stay byte-identical.
- Plan 03 amends the codegen how-to and closes DKGEN-05.
- No blockers.

---
*Phase: 42-codegen-field-type-inference*
*Completed: 2026-06-09*

## Self-Check: PASSED

- FOUND: tests/unit/codegen/test_python_renderer.py
- FOUND: tests/unit/codegen/test_codegen_e2e.py
- FOUND: tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
- FOUND: .planning/phases/42-codegen-field-type-inference/42-01-SUMMARY.md
- FOUND commit: 51ad93a (Task 1)
- FOUND commit: b4ed3c0 (Task 2)
- FOUND commit: 97417f4 (Task 3)
