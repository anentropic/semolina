---
phase: 09-codegen-cli
plan: "03"
subsystem: codegen
tags: [python, importlib, inspect, ast, jinja2, typer, rich, codegen]

# Dependency graph
requires:
  - phase: 09-01
    provides: Typer CLI shell with generate_sql_for_files stub
  - phase: 09-02
    provides: ModelData/FieldData dataclasses, Jinja2 templates, renderer.py

provides:
  - Dynamic Python module loading via importlib.util
  - SemanticView introspection via inspect.getmembers
  - Python syntax validation via ast.parse
  - Error collection without fail-fast (CodegenError + format_error_report)
  - Real generate_sql_for_files orchestrator replacing the stub
  - Unit tests for loader and generator (16 tests)

affects: [09-04, phase-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - importlib.util.spec_from_file_location for arbitrary-path module loading
    - inspect.getmembers(module, inspect.isclass) for class discovery
    - ast.parse for pre-import syntax validation with precise line numbers
    - nullcontext vs Progress pattern for optional Rich progress bars
    - Error collection before reporting (non-fail-fast codegen pipeline)

key-files:
  created:
    - src/cubano/codegen/loader.py
    - src/cubano/codegen/validator.py
    - tests/codegen/test_loader.py
    - tests/codegen/test_generator.py
  modified:
    - src/cubano/codegen/generator.py

key-decisions:
  - "Use inspect.getmembers() with inspect.isclass predicate to discover SemanticView subclasses; filter by __module__ to exclude re-exports"
  - "Use cls._fields dict() cast to Field type to satisfy strict basedpyright typing"
  - "Progress bar shown only when > 5 files; nullcontext used for small batches to avoid Rich overhead"
  - "Non-fail-fast error reporting: collect all CodegenErrors then raise typer.Exit(1) once"

patterns-established:
  - "noqa: TC003 for Path imports needed at runtime in function signatures"
  - "noqa: TC002 for Console import needed at runtime in function signatures"
  - "dict() cast pattern for MappingProxyType items to satisfy strict typing"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-02-17
---

# Phase 9 Plan 03: Module Introspection Layer Summary

**Dynamic SemanticView discovery via importlib.util + inspect, with non-fail-fast error collection and Rich progress bar for bulk processing**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-17T10:25:28Z
- **Completed:** 2026-02-17T10:31:31Z
- **Tasks:** 6
- **Files modified:** 5

## Accomplishments
- Complete module introspection pipeline: syntax validation -> module loading -> class extraction -> model conversion
- Non-fail-fast error collection: all files processed before reporting errors together as a group
- Real `generate_sql_for_files` replaces stub with full pipeline wiring loader + renderer
- 16 new tests (10 loader + 6 generator) all passing alongside 17 existing renderer tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Create loader.py** - `2bac5f9` (feat)
2. **Task 2: Create validator.py** - `128eed7` (feat)
3. **Task 3: Replace generator stub with real implementation** - `f6cd4b3` (feat)
4. **Task 4: Write unit tests for the loader** - `68b706c` (test)
5. **Task 5: Write unit tests for the generator** - `bd5593b` (test)
6. **Task 6: Quality gates** - inline (no separate commit)

## Files Created/Modified
- `src/cubano/codegen/loader.py` - Dynamic module loading, syntax validation, SemanticView introspection
- `src/cubano/codegen/validator.py` - CodegenError dataclass, format_error_report
- `src/cubano/codegen/generator.py` - Real orchestrator replacing stub
- `tests/codegen/test_loader.py` - 10 unit tests for loader functions
- `tests/codegen/test_generator.py` - 6 unit tests for generate_sql_for_files

## Decisions Made
- Used `inspect.getmembers(module, inspect.isclass)` and filtered by `__module__` to exclude re-exported classes from dependencies
- Cast `cls._fields` to `dict[str, Field]` to satisfy strict basedpyright typing without `# type: ignore`
- Used `nullcontext()` for <= 5 files (no progress bar overhead) and `Progress()` for > 5 files
- Non-fail-fast: collect all per-file errors then raise `typer.Exit(1)` once at the end

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed redundant isinstance(obj, type) check**
- **Found during:** Task 6 (quality gates)
- **Issue:** basedpyright flagged `isinstance(obj, type)` as unnecessary since `inspect.isclass` already guarantees the predicate
- **Fix:** Removed redundant check, kept `issubclass` + identity check
- **Files modified:** src/cubano/codegen/loader.py
- **Verification:** basedpyright 0 errors on codegen files
- **Committed in:** 2bac5f9 (Task 1 commit, pre-commit hook ran ruff)

**2. [Rule 1 - Bug] Fixed unknown type for field_obj from MappingProxyType iteration**
- **Found during:** Task 6 (quality gates)
- **Issue:** basedpyright reported unknown argument types from iterating `cls._fields.items()` directly
- **Fix:** Added `fields_map: dict[str, Field] = dict(cls._fields)` cast before iteration; added `Field` to imports
- **Files modified:** src/cubano/codegen/loader.py
- **Verification:** basedpyright 0 errors on codegen files
- **Committed in:** 2bac5f9 (Task 1 commit)

**3. [Rule 3 - Blocking] Fixed ruff TC003/TC002 import placement issues**
- **Found during:** Task 6 (quality gates)
- **Issue:** ruff flagged `Path` and `Console` as moveable to TYPE_CHECKING blocks; they're needed at runtime for function signatures
- **Fix:** Added `# noqa: TC003` and `# noqa: TC002` to runtime-required imports in loader.py, validator.py, generator.py, test files
- **Files modified:** All new .py files
- **Verification:** ruff check passes with 0 errors
- **Committed in:** Individual task commits

---

**Total deviations:** 3 auto-fixed (1 redundant check, 1 type narrowing, 1 noqa annotations)
**Impact on plan:** All auto-fixes were type safety and lint correctness. No scope creep.

## Issues Encountered
- Pre-existing test failures in `test_snowflake_engine.py` and `test_databricks_engine.py` (missing optional `snowflake-connector-python` and `databricks-sql-connector` deps). These are out-of-scope and pre-date this plan.
- Pre-existing basedpyright errors in `src/cubano/engines/snowflake.py` and `databricks.py` (same optional dep issue). Out of scope.

## Next Phase Readiness
- `generate_sql_for_files` is fully functional and tested — ready for 09-04 (CLI wiring)
- All codegen module tests pass (33/33 tests in tests/codegen/)
- Quality gates pass for all codegen files

---
*Phase: 09-codegen-cli*
*Completed: 2026-02-17*

## Self-Check: PASSED

All files exist and all task commits found in git history.
