---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
plan: "05"
subsystem: docs
tags: [docs, how-to, reference, reverse-codegen, codegen]

# Dependency graph
requires:
  - phase: 20-04
    provides: Reverse codegen CLI (cubano codegen <views> --backend <spec>) replacing forward codegen
  - phase: 20-01
    provides: IntrospectedField/IntrospectedView IR dataclasses
  - phase: 20-03
    provides: python_renderer and type_map modules
provides:
  - Rewritten how-to guide for reverse codegen workflow (warehouse view -> Python class)
  - New reference pages for introspector, type_map, python_renderer modules
  - Deleted old reference pages for generator, loader, renderer, validator modules
affects:
  - docs (forward codegen guide replaced, reference nav updated)
  - users reading docs (no longer misled by old forward codegen guide)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mkdocstrings auto-generated reference pages for new codegen modules"
    - "MkDocs tabbed content for Snowflake vs Databricks generated output examples"

key-files:
  created:
    - docs/src/reference/cubano/codegen/introspector.md
    - docs/src/reference/cubano/codegen/type_map.md
    - docs/src/reference/cubano/codegen/python_renderer.md
  modified:
    - docs/src/how-to/codegen.md
    - docs/src/reference/SUMMARY.md
  deleted:
    - docs/src/reference/cubano/codegen/generator.md
    - docs/src/reference/cubano/codegen/loader.md
    - docs/src/reference/cubano/codegen/renderer.md
    - docs/src/reference/cubano/codegen/validator.md

key-decisions:
  - "How-to guide is goal-oriented (data engineer with existing warehouse view wants Python class quickly), not tutorial-style"
  - "Databricks note added inline after tabs: no native Fact type, all non-measure fields map to Dimension()"
  - "blacken-docs hook reformats Python code blocks to 79-char line length — accepted formatting"

patterns-established:
  - "Reference pages for new codegen modules follow same single-line ::: directive pattern"
  - "SUMMARY.md drives mkdocstrings reference nav — removing entries removes pages from build scope"

requirements-completed:
  - CODEGEN-WAREHOUSE

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 20 Plan 05: Documentation Update Summary

**Replaced the forward codegen how-to guide with a reverse codegen guide, removed reference pages for deleted modules, and added reference pages for new introspector/type_map/python_renderer modules.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T06:50:07Z
- **Completed:** 2026-02-24T06:52:03Z
- **Tasks:** 2
- **Files modified:** 9 (3 created, 3 modified, 4 deleted via git rm)

## Accomplishments

- Rewrote `docs/src/how-to/codegen.md` from scratch: replaced forward codegen guide (Python file -> SQL/YAML) with reverse codegen guide (warehouse view -> Python class), showing new `cubano codegen schema.view --backend snowflake|databricks` CLI syntax, tabbed Snowflake/Databricks output examples, field type mapping table, TODO comment explanation, and custom backend section
- Deleted 4 old reference pages (`generator.md`, `loader.md`, `renderer.md`, `validator.md`) that pointed to modules removed in Plan 04
- Created 3 new reference pages (`introspector.md`, `type_map.md`, `python_renderer.md`) via `:::` mkdocstrings directives
- Updated `docs/src/reference/SUMMARY.md` codegen section to reflect new module structure

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite docs/src/how-to/codegen.md for reverse codegen** - `2d5bac0` (docs)
2. **Task 2: Update reference pages (delete old, add new, update SUMMARY.md)** - `4ad379b` (docs)

## Files Created/Modified

- `docs/src/how-to/codegen.md` - Rewritten: reverse codegen how-to guide
- `docs/src/reference/SUMMARY.md` - Updated: removed generator/loader/renderer/validator, added introspector/python_renderer/type_map
- `docs/src/reference/cubano/codegen/introspector.md` - Created: auto-generated reference for IntrospectedField/IntrospectedView
- `docs/src/reference/cubano/codegen/type_map.md` - Created: auto-generated reference for type mapping functions
- `docs/src/reference/cubano/codegen/python_renderer.md` - Created: auto-generated reference for render_views/render_and_format
- Deleted: `generator.md`, `loader.md`, `renderer.md`, `validator.md`

## Decisions Made

- How-to guide written goal-oriented (Diataxis how-to format): reader has an existing warehouse view, wants a Python class, not a tutorial walkthrough
- Databricks "no Fact type" note placed inline after the tabbed examples rather than in a separate admonition
- blacken-docs hook auto-reformatted Python code blocks to 79-char line length on commit; accepted and re-staged

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Format] blacken-docs reformatted Python code blocks in codegen.md**
- **Found during:** Task 1 (pre-commit hook)
- **Issue:** `class OrdersView(SemanticView, view="main.analytics.orders_view"):` exceeds 79-char line length; blacken-docs wraps it
- **Fix:** Re-staged the reformatted file and committed successfully on second attempt
- **Files modified:** `docs/src/how-to/codegen.md`
- **Committed in:** `2d5bac0` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (formatting hook, no design impact)

## Verification

- `uv run mkdocs build --strict` -- PASSED (0 errors, 0 warnings)
- `uv run pytest tests/ -q` -- PASSED (681 tests)
- codegen.md describes reverse codegen with correct CLI syntax and generated output
- Reference nav shows introspector, type_map, python_renderer; no generator/loader/renderer/validator

## Self-Check: PASSED

- FOUND: docs/src/how-to/codegen.md (rewritten)
- FOUND: docs/src/reference/cubano/codegen/introspector.md
- FOUND: docs/src/reference/cubano/codegen/type_map.md
- FOUND: docs/src/reference/cubano/codegen/python_renderer.md
- FOUND: docs/src/reference/SUMMARY.md (updated)
- DELETED: generator.md, loader.md, renderer.md, validator.md (confirmed absent via git status)
- FOUND: commits 2d5bac0, 4ad379b

---
*Phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class*
*Completed: 2026-02-24*
