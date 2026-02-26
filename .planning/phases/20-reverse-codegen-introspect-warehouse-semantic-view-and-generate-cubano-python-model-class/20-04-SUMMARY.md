---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
plan: "04"
subsystem: codegen
tags: [typer, reverse-codegen, cli, introspection, python-renderer, mock-engine]

# Dependency graph
requires:
  - phase: 20-03
    provides: render_and_format() Python renderer converting IntrospectedView -> formatted Python source
  - phase: 20-01
    provides: IntrospectedView/IntrospectedField IR dataclasses and Engine.introspect() abstract method
  - phase: 20-02
    provides: SnowflakeEngine.introspect() and DatabricksEngine.introspect() implementations
provides:
  - New reverse codegen CLI command: cubano codegen <view_names> --backend <spec>
  - _resolve_backend() supporting snowflake/databricks shortcuts and dotted import path
  - 19 new CLI tests using MockEngine stub (no warehouse credentials needed)
  - All old forward codegen artifacts removed (4 source modules, 2 templates, 3 test files, 4 fixtures)
affects:
  - docs (codegen guide will need updating for new reverse codegen signature)
  - users upgrading from forward codegen to reverse codegen workflow

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_resolve_backend() module-level function for testable backend resolution"
    - "MockEngine via unittest.mock.patch('cubano.cli.codegen._resolve_backend') for warehouse-free CLI tests"
    - "typer.echo() for Python source stdout; Rich Console for stderr diagnostics"

key-files:
  created:
    - tests/unit/codegen/test_cli.py
  modified:
    - src/cubano/cli/codegen.py
  deleted:
    - src/cubano/codegen/generator.py
    - src/cubano/codegen/loader.py
    - src/cubano/codegen/renderer.py
    - src/cubano/codegen/validator.py
    - src/cubano/codegen/templates/snowflake.sql.jinja2
    - src/cubano/codegen/templates/databricks.yaml.jinja2
    - tests/unit/codegen/test_generator.py
    - tests/unit/codegen/test_loader.py
    - tests/unit/codegen/test_renderer.py
    - tests/unit/codegen/fixtures/simple_models.py
    - tests/unit/codegen/fixtures/multi_models.py
    - tests/unit/codegen/fixtures/no_models.py
    - tests/unit/codegen/fixtures/__init__.py

key-decisions:
  - "Plain str (not StrEnum) for --backend option: supports arbitrary dotted import paths like my.package.MyBackend beyond snowflake/databricks shortcuts"
  - "_resolve_backend() raises typer.BadParameter (not RuntimeError) so typer converts it to exit code 1 and human-readable message"
  - "unittest.mock.patch('cubano.cli.codegen._resolve_backend') as injection point for tests: avoids credentials/connections while testing full CLI integration"
  - "IntrospectedView type annotation via TYPE_CHECKING guard: list[IntrospectedView] for basedpyright strict compatibility without runtime import"

patterns-established:
  - "Backend resolution pattern: try known shortcuts (snowflake/databricks), fall back to importlib.import_module() for dotted paths, raise typer.BadParameter for unknown/invalid specs"
  - "CLI test pattern: mock at _resolve_backend boundary rather than individual engine methods"

requirements-completed:
  - CODEGEN-WAREHOUSE

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 20 Plan 04: CLI Wiring and Forward Codegen Cleanup Summary

**Replaced broken forward codegen CLI (file->SQL) with working reverse codegen CLI (warehouse->Python) and deleted all forward codegen artifacts, leaving 681 passing tests and all quality gates green.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T00:42:24Z
- **Completed:** 2026-02-24T00:46:29Z
- **Tasks:** 3
- **Files modified:** 15 (2 modified, 13 deleted)

## Accomplishments

- Deleted all forward codegen artifacts: 4 source modules, 2 SQL/YAML templates, 3 test files, 4 fixtures (927 lines removed)
- Rewrote `src/cubano/cli/codegen.py` with new `cubano codegen <views> --backend <spec>` command supporting snowflake/databricks shortcuts and dotted import paths
- Replaced 31 old forward codegen CLI tests with 19 new reverse codegen CLI tests using MockEngine injection (no warehouse credentials required)

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete old forward codegen modules and tests** - `99fce0a` (chore)
2. **Task 2: Rewrite cli/codegen.py with reverse codegen CLI** - `0cf16df` (feat)
3. **Task 3: Replace test_cli.py with reverse codegen CLI tests** - `7dc34c0` (feat)

## Files Created/Modified

- `src/cubano/cli/codegen.py` - Rewritten: new reverse codegen command with `_resolve_backend()` private helper
- `tests/unit/codegen/test_cli.py` - Replaced: 19 tests using MockEngine for warehouse-free CLI coverage
- All deleted files listed in key-files frontmatter above

## Decisions Made

- Used plain `str` (not `StrEnum`) for `--backend` option to support arbitrary dotted import paths beyond the two built-in shortcuts
- `_resolve_backend()` raises `typer.BadParameter` (not `RuntimeError`) so Typer handles exit code and error message formatting automatically
- Added `list[IntrospectedView]` type annotation via `TYPE_CHECKING` guard to satisfy basedpyright strict without runtime circular imports
- Patching `cubano.cli.codegen._resolve_backend` as the test injection point enables full CLI integration testing without any warehouse setup

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ambiguous variable name `l` in test generator expression**
- **Found during:** Task 3 (pre-commit hook ruff check)
- **Issue:** `for i, l in enumerate(lines)` uses `l` which ruff flags as E741 ambiguous variable name
- **Fix:** Renamed to `line` in the generator expression
- **Files modified:** `tests/unit/codegen/test_cli.py`
- **Verification:** `uv run ruff check tests/unit/codegen/test_cli.py` passes
- **Committed in:** `7dc34c0` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (lint error caught by pre-commit hook)
**Impact on plan:** Trivial naming fix required no design change.

## Issues Encountered

- ruff-format auto-reformatted `codegen.py` during first commit attempt (pre-commit hook). Re-staged the formatted file and committed successfully on second attempt.

## Next Phase Readiness

- Phase 20 is complete: IntrospectedView IR (Plan 01), Snowflake/Databricks introspection (Plan 02), Python renderer (Plan 03), and CLI wiring (Plan 04) all done
- `cubano codegen my_schema.my_view --backend snowflake` is the working end-user command
- Docs update for the new reverse codegen signature is a natural follow-on but not required for functionality

## Self-Check: PASSED

- FOUND: src/cubano/cli/codegen.py
- FOUND: tests/unit/codegen/test_cli.py
- FOUND: 20-04-SUMMARY.md
- DELETED: generator.py, loader.py, renderer.py, validator.py (confirmed absent)
- FOUND: commits 99fce0a, 0cf16df, 7dc34c0

---
*Phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class*
*Completed: 2026-02-24*
