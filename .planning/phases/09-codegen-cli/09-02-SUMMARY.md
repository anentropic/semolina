---
phase: 09-codegen-cli
plan: "02"
subsystem: codegen
tags: [jinja2, codegen, templates, snowflake, databricks, sql, yaml]

# Dependency graph
requires:
  - phase: 09-01
    provides: Typer CLI shell and codegen stub that consumes ModelData
provides:
  - FieldData and ModelData frozen dataclasses (shared data contract)
  - Snowflake CREATE SEMANTIC VIEW Jinja2 template
  - Databricks metric view YAML Jinja2 template
  - render_view() function dispatching to backend-specific templates
  - render_file_header() for source attribution
  - 17 unit tests for renderer (all passing)
affects: [09-03, 09-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Jinja2 FileSystemLoader with StrictUndefined for safe template rendering
    - Whitespace control markers ({%- -%}) to eliminate extra blank lines in output
    - TYPE_CHECKING guard for ModelData import in renderer (TC001 compliance)
    - Frozen dataclasses for immutable model data transfer objects

key-files:
  created:
    - src/cubano/codegen/models.py
    - src/cubano/codegen/templates/snowflake.sql.jinja2
    - src/cubano/codegen/templates/databricks.yaml.jinja2
    - src/cubano/codegen/renderer.py
    - tests/codegen/__init__.py
    - tests/codegen/test_renderer.py
  modified: []

key-decisions:
  - "ModelData in models.py (not renderer.py) avoids circular imports with 09-03 introspection layer"
  - "uv_build includes non-.py files from src/ automatically — no pyproject.toml changes needed for templates"
  - "Snowflake template generates TODO placeholders for TABLES/RELATIONSHIPS since SemanticView has no source table info"
  - "Databricks SUM() placeholder with TODO comment since Metric() fields don't capture aggregation type"

patterns-established:
  - "Jinja2 templates use {%- -%} whitespace control throughout — no extra blank lines in output"
  - "render_view() raises ValueError with supported backends list for unknown backend names"
  - "Template variables: model (ModelData), include_comments (bool) — consistent across all backends"

requirements-completed: [CODEGEN-02, CODEGEN-03]

# Metrics
duration: 3min
completed: 2026-02-17
---

# Phase 9 Plan 02: Template Renderer Summary

**Jinja2 SQL/YAML rendering layer with FieldData/ModelData dataclasses, Snowflake DDL and Databricks YAML templates, and 17 passing unit tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-17T10:25:33Z
- **Completed:** 2026-02-17T10:28:40Z
- **Tasks:** 7 (Tasks 1-5 committed individually, Task 6 verification-only, Task 7 quality gates)
- **Files modified:** 6 created, 0 modified

## Accomplishments
- FieldData and ModelData frozen dataclasses define the shared data contract between introspection (09-03) and rendering
- Snowflake template generates `CREATE OR REPLACE SEMANTIC VIEW` DDL with FACTS/DIMENSIONS/METRICS clauses
- Databricks template generates metric view YAML with dimensions and measures sections
- render_view() function dispatches to correct template with StrictUndefined environment
- All 17 renderer unit tests pass; uv_build confirmed to include .jinja2 templates automatically

## Task Commits

Each task was committed atomically:

1. **Task 1: Define FieldData and ModelData dataclasses** - `7d54f59` (feat)
2. **Task 2: Snowflake SQL template** - `e9f2d9d` (feat)
3. **Task 3: Databricks YAML template** - `1fed4c1` (feat)
4. **Task 4: renderer.py** - `0c778a4` (feat)
5. **Task 5: Unit tests** - `154be47` (test)
6. **Task 6: Template packaging** - (no code changes — verified uv_build includes templates)
7. **Task 7: Quality gates** - (no code changes — all gates passed)

## Files Created/Modified
- `src/cubano/codegen/models.py` - FieldData and ModelData frozen dataclasses
- `src/cubano/codegen/templates/snowflake.sql.jinja2` - Snowflake CREATE SEMANTIC VIEW template
- `src/cubano/codegen/templates/databricks.yaml.jinja2` - Databricks metric view YAML template
- `src/cubano/codegen/renderer.py` - render_view() and render_file_header() functions
- `tests/codegen/__init__.py` - Empty init for pytest discovery
- `tests/codegen/test_renderer.py` - 17 unit tests for renderer

## Decisions Made
- `ModelData` defined in `models.py` (not `renderer.py`) to avoid circular imports when 09-03 imports it
- `uv_build` includes non-`.py` files from `src/` automatically — verified by building wheel and inspecting contents
- Snowflake template generates `-- TODO` placeholders for `TABLES`/`RELATIONSHIPS` since `SemanticView` has no source table metadata
- Databricks uses `SUM()` placeholder with TODO comment since `Metric()` fields don't capture aggregation type
- `ModelData` imported under `TYPE_CHECKING` in `renderer.py` (ruff TC001 compliance with `from __future__ import annotations`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TC001 lint error in renderer.py**
- **Found during:** Task 4 (renderer.py implementation)
- **Issue:** Pre-commit ruff hook flagged `from cubano.codegen.models import ModelData` as TC001 — should be under TYPE_CHECKING block since `from __future__ import annotations` is present
- **Fix:** Moved import under `if TYPE_CHECKING:` block; also fixed import sort order (I001)
- **Files modified:** `src/cubano/codegen/renderer.py`
- **Verification:** `uv run ruff check src/cubano/codegen/renderer.py` passes
- **Committed in:** `0c778a4` (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - lint/type compliance)
**Impact on plan:** Necessary for correct import hygiene per project lint rules. No scope creep.

## Issues Encountered
- Pre-existing basedpyright errors in `loader.py` (5 errors) and `engines/snowflake.py`, `engines/databricks.py` from 09-01 — out of scope, logged as deferred
- Pre-existing test failures in `test_snowflake_engine.py` and `test_databricks_engine.py` due to optional warehouse connectors not installed — out of scope, pre-existing
- New files (models.py, renderer.py, tests/codegen/) are clean: 0 basedpyright errors, 0 ruff errors

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `ModelData` and `FieldData` dataclasses ready for 09-03 to populate via introspection
- `render_view()` ready for 09-03 to call after model discovery
- Templates produce correct Snowflake DDL and Databricks YAML — verified by 17 tests
- Template packaging confirmed: `uv build` includes `.jinja2` files in wheel

---
*Phase: 09-codegen-cli*
*Completed: 2026-02-17*

## Self-Check: PASSED

All files present and all commits verified:
- `src/cubano/codegen/models.py` - FOUND
- `src/cubano/codegen/renderer.py` - FOUND
- `src/cubano/codegen/templates/snowflake.sql.jinja2` - FOUND
- `src/cubano/codegen/templates/databricks.yaml.jinja2` - FOUND
- `tests/codegen/__init__.py` - FOUND
- `tests/codegen/test_renderer.py` - FOUND
- Commit `7d54f59` - FOUND
- Commit `e9f2d9d` - FOUND
- Commit `1fed4c1` - FOUND
- Commit `0c778a4` - FOUND
- Commit `154be47` - FOUND
