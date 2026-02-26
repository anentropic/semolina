---
phase: 23-api-export-cleanup
plan: "01"
subsystem: public-api
tags: [api-exports, test-cleanup, requirements-traceability]
dependency_graph:
  requires: []
  provides: [public-api-exceptions, public-api-result, clean-test-suite, accurate-requirements]
  affects: [src/cubano/__init__.py, cubano-jaffle-shop/tests/test_mock_queries.py, .planning/REQUIREMENTS.md]
tech_stack:
  added: []
  patterns: [explicit-__all__, typed-exception-exports]
key_files:
  created: []
  modified:
    - src/cubano/__init__.py
    - cubano-jaffle-shop/tests/test_mock_queries.py
    - .planning/REQUIREMENTS.md
decisions:
  - "CubanoViewNotFoundError and CubanoConnectionError exported from cubano.__init__ via engines.base import"
  - "Result exported alongside Row from cubano.__init__ via results import"
  - "CODEGEN-WAREHOUSE added to traceability table (Phase 20, Complete)"
  - "CODEGEN-REVERSE description corrected to warehouse->Python direction"
metrics:
  duration_minutes: 2
  completed_date: "2026-02-25"
  tasks_completed: 4
  files_modified: 3
requirements-completed: []
---

# Phase 23 Plan 01: API Export Cleanup Summary

Exported three missing public types from `cubano.__init__`, removed two stale xfail test markers that were masking passing tests, and corrected two traceability issues in REQUIREMENTS.md for Phase 20's codegen work.

## What Was Done

### Task 1: Export typed exceptions and Result (commit 4ec5186)

Added three new exports to `src/cubano/__init__.py`:

- `from .engines.base import CubanoConnectionError, CubanoViewNotFoundError`
- Extended `from .results import Row` to `from .results import Result, Row`
- Added `"Result"`, `"CubanoViewNotFoundError"`, `"CubanoConnectionError"` to `__all__`

**Import verification output:**
```
ok
```

Command: `uv run python -c "from cubano import CubanoViewNotFoundError, CubanoConnectionError, Result; print('ok')"`

### Task 2: Remove stale xfail markers (commit d42c81a)

Removed `@pytest.mark.xfail(reason="MockEngine doesn't evaluate filters yet")` from two tests in `cubano-jaffle-shop/tests/test_mock_queries.py::TestFiltering`:

- `test_filter_boolean`: removed xfail decorator, updated docstring to reference Phase 13.1, replaced commented-out assertion block
- `test_filter_comparison`: same pattern applied

**pytest TestFiltering output:**
```
tests/test_mock_queries.py::TestFiltering::test_filter_boolean PASSED    [ 50%]
tests/test_mock_queries.py::TestFiltering::test_filter_comparison PASSED [100%]

2 passed in 0.03s
```

Both tests now PASSED (were previously XPASS).

### Task 3: Fix REQUIREMENTS.md traceability (commit 7264cee)

Two corrections to `.planning/REQUIREMENTS.md`:

1. **Added CODEGEN-WAREHOUSE to the traceability table:**
   ```
   | CODEGEN-WAREHOUSE | Phase 20 | Complete |
   ```

2. **Corrected CODEGEN-REVERSE v1+ description:**
   - Before: `Reverse codegen (Cubano models → dbt semantic YAML)`
   - After: `Generate Cubano Python model class from warehouse semantic view introspection (warehouse→Python direction; implemented in Phase 20 as 'cubano codegen <schema.view_name>')`

3. **Updated coverage count:**
   - Before: `v0.2 requirements: 25 total` / `Mapped to phases: 25 (100%)`
   - After: `v0.2 requirements: 25 total (+ CODEGEN-WAREHOUSE from v1+ backlog, implemented Phase 20)` / `Mapped to phases: 26 (100%)`

### Task 4: Full quality gate

All four quality gates passed with zero issues:

| Gate | Result |
|------|--------|
| `uv run basedpyright` | 0 errors, 0 warnings, 0 notes |
| `uv run ruff check` | All checks passed! |
| `uv run ruff format --check` | 56 files already formatted |
| `uv run pytest` | 751 passed, 16 skipped in 2.98s |

No regressions introduced. The previously-XPASS tests now show as PASSED.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 4ec5186 | feat(23-01): export CubanoViewNotFoundError, CubanoConnectionError, Result from cubano.__init__ |
| 2 | d42c81a | fix(23-01): remove stale xfail markers from TestFiltering in jaffle-shop |
| 3 | 7264cee | docs(23-01): fix REQUIREMENTS.md CODEGEN-WAREHOUSE/REVERSE traceability |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- FOUND: src/cubano/__init__.py
- FOUND: cubano-jaffle-shop/tests/test_mock_queries.py
- FOUND: .planning/REQUIREMENTS.md

Commits exist:
- FOUND: 4ec5186
- FOUND: d42c81a
- FOUND: 7264cee
