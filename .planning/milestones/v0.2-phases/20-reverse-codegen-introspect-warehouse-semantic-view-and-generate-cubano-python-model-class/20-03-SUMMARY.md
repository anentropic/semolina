---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
plan: "03"
subsystem: codegen
tags: [reverse-codegen, jinja2, ruff, python-renderer, tdd, code-generation]

dependency_graph:
  requires:
    - phase: 20-01
      provides: IntrospectedView/IntrospectedField IR dataclasses
    - phase: 20-02
      provides: SnowflakeEngine.introspect() and DatabricksEngine.introspect()
  provides:
    - render_views(views) -> raw Python source string
    - format_with_ruff(source) -> ruff-formatted source with fallback
    - render_and_format(views) -> formatted Python source (CLI entry point)
    - python_model.py.jinja2 Jinja2 template for SemanticView class output
  affects:
    - 20-04  # CLI wiring plan will import render_and_format and call it

tech-stack:
  added: []
  patterns:
    - TDD (RED/GREEN/REFACTOR)
    - Jinja2 Environment with trim_blocks/lstrip_blocks for clean Python output
    - Intermediate dataclasses (_FieldContext, _ModelContext) for template decoupling
    - subprocess.run() with FileNotFoundError fallback for optional tooling

key-files:
  created:
    - src/cubano/codegen/python_renderer.py
    - src/cubano/codegen/templates/python_model.py.jinja2
    - tests/unit/codegen/test_python_renderer.py
  modified: []

key-decisions:
  - "TYPE_CHECKING guard on IntrospectedView import — keeps runtime import clean, consistent with existing renderer.py pattern"
  - "Intermediate _FieldContext/_ModelContext dataclasses decouple Jinja2 template from IntrospectedField/IntrospectedView IR types"
  - "_DATETIME_TYPES frozenset for O(1) membership test across all fields when deciding needs_datetime flag"
  - "format_with_ruff() is a non-fatal wrapper — ruff failure returns source unchanged, not an error"
  - "render_views() uses TYPE_CHECKING guard + type: ignore[no-any-return] on template.render() — consistent with existing renderer.py pattern"

patterns-established:
  - "Jinja2 Environment with trim_blocks=True, lstrip_blocks=True — produces clean Python with no stray blank lines between fields"
  - "Pre-linting via format_with_ruff() before returning to CLI — user gets ruff-formatted code automatically"

requirements-completed:
  - CODEGEN-WAREHOUSE

duration: 4min
completed: "2026-02-24"
---

# Phase 20 Plan 03: Python Code Renderer Summary

**Jinja2-based Python renderer that converts IntrospectedView IR into ruff-formatted, importable SemanticView class definitions**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-24T06:36:04Z
- **Completed:** 2026-02-24T06:39:30Z
- **Tasks:** 3 (RED/GREEN/REFACTOR TDD cycle)
- **Files modified:** 3

## Accomplishments

- `render_views()` converts a `list[IntrospectedView]` to a Python source string with shared imports, per-view class definitions, field docstrings, and TODO comments
- `format_with_ruff()` formats source via `uv run ruff format` with graceful fallback to unformatted on `FileNotFoundError` or non-zero exit
- `render_and_format()` convenience wrapper used by the CLI (render + format in one call)
- `python_model.py.jinja2` template produces clean Python with no stray blank lines using `trim_blocks`/`lstrip_blocks`
- 25 new tests covering all field types, datetime import logic, TODO comments, docstrings, multi-view output, ruff fallback paths

## Task Commits

Each task was committed atomically:

1. **Task 1: RED - Failing tests** - `40539cb` (test)
2. **Task 2: GREEN - Implementation** - `4aced36` (feat)
3. **Task 3: REFACTOR** - No code changes needed (GREEN was already clean)

## Files Created/Modified

- `src/cubano/codegen/python_renderer.py` - `render_views()`, `format_with_ruff()`, `render_and_format()` functions
- `src/cubano/codegen/templates/python_model.py.jinja2` - Jinja2 template for SemanticView class output
- `tests/unit/codegen/test_python_renderer.py` - 25 TDD tests

## Decisions Made

- TYPE_CHECKING guard on `IntrospectedView` import — keeps runtime imports clean, avoids circular import risk, consistent with `renderer.py` pattern
- Intermediate `_FieldContext`/`_ModelContext` dataclasses buffer between IR types and Jinja2 template — template has no knowledge of `IntrospectedField` internals
- `_DATETIME_TYPES` frozenset for O(1) membership test when computing `needs_datetime` flag across all views and fields
- `format_with_ruff()` is deliberately non-fatal — ruff failure (missing `uv`, non-zero exit) returns source unchanged so CLI always produces output
- `type: ignore[no-any-return]` on `template.render()` — jinja2 stubs type `.render()` as `str | Any`, same pattern as existing `renderer.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed D301 ruff lint error in format_with_ruff() docstring**
- **Found during:** Task 2 (GREEN) — ruff check reported D301 "Use r-string if any backslashes in docstring" after adding example with `\n` escape sequence
- **Issue:** Example code `format_with_ruff("x=1\n")` contained a `\n` escape in a regular docstring, triggering D301
- **Fix:** Removed the example section from `format_with_ruff()` docstring (it's a trivial wrapper — the docstring prose is sufficient)
- **Files modified:** `src/cubano/codegen/python_renderer.py`
- **Verification:** `uv run ruff check src/cubano/codegen/python_renderer.py` passes
- **Committed in:** `4aced36` (Task 2 GREEN commit, applied before commit via pre-commit hook)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Trivial docstring fix. No scope creep, no behavioral changes.

## Issues Encountered

None — pre-commit hook (ruff + blacken-docs) reformatted the file on first commit attempt, which was corrected by re-staging and committing.

## Verification Results

```
uv run pytest tests/unit/codegen/test_python_renderer.py -v
25 passed in 0.26s

uv run pytest tests/
726 passed in 2.25s  (no regressions, +25 new tests)

uv run basedpyright src/cubano/codegen/python_renderer.py
0 errors, 0 warnings, 0 notes

uv run ruff check src/cubano/codegen/python_renderer.py
All checks passed!

uv run mkdocs build --strict
Documentation built in 1.81 seconds
```

## Next Phase Readiness

- `render_and_format()` is the CLI entry point — ready for Plan 04 (CLI wiring) to import and call
- Template produces clean, importable Python: `from cubano import SemanticView, Metric, Dimension, Fact` + class definitions
- All quality gates passing: basedpyright 0 errors, ruff clean, 726 tests, docs build

---

*Phase: 20-reverse-codegen*
*Completed: 2026-02-24*
