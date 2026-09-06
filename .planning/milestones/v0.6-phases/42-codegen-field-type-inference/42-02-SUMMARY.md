---
phase: 42-codegen-field-type-inference
plan: 02
subsystem: codegen
tags: [codegen, python-renderer, field-type, valueerror, tdd, snowflake, databricks, duckdb]

# Dependency graph
requires:
  - phase: 42-codegen-field-type-inference
    plan: 01
    provides: RED raise-path unit test (acceptance contract for the strict-raise change)
provides:
  - Strict _field_class_for that raises ValueError on any unrecognized warehouse role
  - Module-level _ROLE_TO_CLASS map (metric→Metric, dimension→Dimension, fact→Fact)
  - GREEN state for the Plan 01 raise-path test (RED→GREEN complete)
affects: [42-03-docs-and-closeout]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Strict dict lookup with KeyError→ValueError re-raise (from None) to fail loudly on schema drift instead of silent default coercion"

key-files:
  created: []
  modified:
    - src/semolina/codegen/python_renderer.py

key-decisions:
  - "Used `raise ValueError(...) from None` to suppress the KeyError chain — the role string, not the dict miss, is the meaningful error surface"
  - "Lowercase keys in _ROLE_TO_CLASS because both engines normalize role strings to lowercase before the renderer sees them"

patterns-established:
  - "Strict role→class mapping: replace catch-all defaults with explicit dict + ValueError on miss at the trust boundary"

requirements-completed: []  # DKGEN-05 is closed in Plan 03; this plan ships the production code change only.

# Metrics
duration: ~6min
completed: 2026-06-09
---

# Phase 42 Plan 02: Make `_field_class_for` Strict (Raise on Unrecognized Role) Summary

**Replaced the silent catch-all `return "Dimension"` in `_field_class_for` with an explicit `_ROLE_TO_CLASS` dict lookup that raises `ValueError` on any unrecognized warehouse role — turning the Plan 01 RED raise-path test GREEN while keeping the DuckDB e2e regression snapshot byte-identical.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-06-09
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added module-level `_ROLE_TO_CLASS = {"metric": "Metric", "dimension": "Dimension", "fact": "Fact"}` next to the existing `_DATETIME_TYPES` constant.
- Rewrote `_field_class_for(field_type: str) -> str` to `try: return _ROLE_TO_CLASS[field_type]` / `except KeyError: raise ValueError(f"Unrecognized field role: {field_type!r}") from None`.
- Added a Google-style `Raises:` section documenting the `ValueError` for unrecognized roles, explaining the loud-failure-over-silent-mislabel rationale.
- Left `_build_model_context` untouched — the raise propagates from the call site (line ~110), as required.
- RED→GREEN sequence complete: the Plan 01 `test_field_class_for_unrecognized_role_raises` now passes.

## Task Commits

1. **Task 1: Make _field_class_for strict (raise on unrecognized role)** - `a802980` (fix)

## Files Created/Modified

- `src/semolina/codegen/python_renderer.py` - Added `_ROLE_TO_CLASS` module constant; rewrote `_field_class_for` to strict dict lookup raising `ValueError` on miss; added the `Raises:` docstring section. Net diff: 10 insertions, 5 deletions.

## Decisions Made

- **`raise ... from None`**: suppressed the implicit `KeyError` chain so the traceback surfaces the meaningful contract violation (the unrecognized role string) rather than an internal dict-miss artifact. The `field_type` value is interpolated with `!r` for an unambiguous error message.
- **Lowercase keys**: both the Snowflake and Databricks engines normalize role strings to lowercase before they reach the renderer, so the map only needs lowercase keys — matching the `IntrospectedField.field_type` Literal contract.

## Deviations from Plan

None - plan executed exactly as written.

## Threat Model Outcome

- **T-42-02 (Tampering/Spoofing — role outside the Literal contract):** mitigated as planned. The strict dict lookup raises `ValueError` on any unrecognized role, removing the prior silent-coercion path where schema drift or malformed metadata would mislabel a column as `Dimension`. The generator now fails loudly at the trust boundary.

## Issues Encountered

- `uv run` panicked under the command sandbox (`system-configuration` NULL object / Tokio executor), same as Plan 01. Resolved by running pytest/commit with the sandbox disabled. No code impact.

## Verification

- `uv run pytest tests/unit/codegen/ -x` → **221 passed** (was 220 passed + 1 RED in Plan 01; the raise-path test is now GREEN). 3 snapshots passed without `--snapshot-update`.
- `uv run pytest tests/unit/codegen/test_python_renderer.py::test_field_class_for_unrecognized_role_raises` → confirmed RED before the change (`DID NOT RAISE`), GREEN after.
- `git diff HEAD -- tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` → **empty** (DuckDB regression-guard block byte-identical against Plan 01's committed snapshot).
- Source diff shows only the `_ROLE_TO_CLASS` constant + strict `_field_class_for` rewrite + `Raises:` docstring; `_build_model_context` unchanged, no surrounding `try`.
- `prek` hooks (ruff, ruff-format, basedpyright strict) passed at commit time; no `# type: ignore` introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03 amends the codegen how-to documentation and closes requirement DKGEN-05.
- No blockers. The production code change for the phase is complete; remaining work is docs + closeout.

---
*Phase: 42-codegen-field-type-inference*
*Completed: 2026-06-09*

## Self-Check: PASSED

- FOUND: src/semolina/codegen/python_renderer.py
- FOUND: .planning/phases/42-codegen-field-type-inference/42-02-SUMMARY.md
- FOUND commit: a802980 (Task 1)
- VERIFIED: `_ROLE_TO_CLASS` present in python_renderer.py
- VERIFIED: DuckDB e2e snapshot byte-identical (empty git diff)
