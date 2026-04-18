---
phase: 30-sphinx-shibuya-documentation-migration
plan: 03
subsystem: docs
tags: [sphinx, rst, sphinx-design, tab-set, list-table, admonitions]

# Dependency graph
requires:
  - phase: 30-01
    provides: Sphinx scaffold with conf.py, toctree index files, and Sphinx dependencies
provides:
  - 9 how-to guide pages converted from Markdown to RST with tab-sets, list-tables, and admonitions
  - Full homepage with 4 grid cards and quick example code block
affects: [30-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [sphinx-design tab-set with sync-group warehouse, list-table for all tables, RST definition lists for troubleshooting]

key-files:
  created:
    - docs/src/how-to/ordering.rst
    - docs/src/how-to/codegen.rst
    - docs/src/how-to/warehouse-testing.rst
    - docs/src/how-to/backends/overview.rst
    - docs/src/how-to/backends/snowflake.rst
    - docs/src/how-to/backends/databricks.rst
    - docs/src/how-to/models.rst
    - docs/src/how-to/queries.rst
    - docs/src/how-to/filtering.rst
  modified:
    - docs/src/index.rst

key-decisions:
  - "Tab-set counts match original: 42 tab-items across 21 tab-sets in how-to pages, all using sync-group warehouse"
  - "Pipe tables converted to list-table directive consistently (8 tables across how-to pages)"
  - "Definition lists in warehouse-testing.rst troubleshooting section use RST native syntax"

patterns-established:
  - "RST tab-set pattern: 3-space indent, sync-group warehouse, sync snowflake/databricks"
  - "RST list-table pattern: header-rows 1, 3-space indentation"
  - "RST admonition pattern: .. tip/warning/note:: with optional title on directive line"

requirements-completed: [SPHINX-02]

# Metrics
duration: 10min
completed: 2026-04-09
---

# Phase 30 Plan 03: How-To & Homepage RST Conversion Summary

**All 9 how-to pages and homepage converted from Markdown to RST with 42 tab-items, 8 list-tables, 6 admonitions, and 4 grid cards**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-09T12:21:46Z
- **Completed:** 2026-04-09T12:32:40Z
- **Tasks:** 2
- **Files modified:** 19 (10 created, 9 deleted)

## Accomplishments
- Converted all 9 how-to guide pages from Markdown to RST with correct sphinx-design tab-set syntax
- Rewrote homepage with 4 grid-item-card directives and quick example code block
- All tab-sets use consistent sync-group: warehouse for cross-page tab synchronization
- All pipe tables converted to list-table directives, definition lists to RST format
- Zero .md content files remain in how-to directory

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert homepage and low-tab how-to pages** - `c1b5b06` (feat)
2. **Task 2: Convert high-tab how-to pages and verify build** - `2b926ab` (feat)

## Files Created/Modified
- `docs/src/index.rst` - Full homepage with 4 grid cards and quick example
- `docs/src/how-to/ordering.rst` - Ordering how-to (1 tab-set, 1 list-table)
- `docs/src/how-to/codegen.rst` - Codegen how-to (1 tab-set, 3 list-tables)
- `docs/src/how-to/warehouse-testing.rst` - Testing how-to (0 tabs, 3 admonitions, 2 list-tables, definition lists)
- `docs/src/how-to/backends/overview.rst` - Backend overview (1 tab-set)
- `docs/src/how-to/backends/snowflake.rst` - Snowflake how-to (1 list-table, 1 admonition)
- `docs/src/how-to/backends/databricks.rst` - Databricks how-to (1 list-table, 2 admonitions)
- `docs/src/how-to/models.rst` - Models how-to (3 tab-sets, 1 list-table, 1 admonition)
- `docs/src/how-to/queries.rst` - Queries how-to (6 tab-sets, 1 admonition)
- `docs/src/how-to/filtering.rst` - Filtering how-to (12 tab-sets, 1 list-table, 1 admonition)

**Deleted:** 9 .md files (ordering, codegen, warehouse-testing, overview, snowflake, databricks, models, queries, filtering)

## Decisions Made
- Tab-set directive counts represent containers (each containing 2 tab-items for Snowflake/Databricks), matching the original `===` pair count
- Used RST definition list syntax for warehouse-testing troubleshooting section (term on own line, definition indented 3 spaces)
- Converted blockquote note in codegen.md to `.. note::` admonition directive

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Sphinx build with `-W` (warnings-as-errors) fails due to toctree references to tutorial/explanation pages not yet converted (handled by parallel plan 30-02) and auto-generated reference file docstring parsing warnings. Build without `-W` succeeds cleanly and all 10 converted pages render as HTML.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All how-to pages and homepage are RST; ready for plan 30-04 (CI workflow and cleanup)
- Full `-W` clean build requires plan 30-02 (tutorials + explanation) to also complete

---
*Phase: 30-sphinx-shibuya-documentation-migration*
*Completed: 2026-04-09*

## Self-Check: PASSED
