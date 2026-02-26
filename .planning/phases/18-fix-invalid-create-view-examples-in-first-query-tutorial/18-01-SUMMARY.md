---
phase: 18-fix-invalid-create-view-examples-in-first-query-tutorial
plan: 01
subsystem: docs
tags: [snowflake, databricks, semantic-view, metric-view, ddl, mkdocs, tutorial]

# Dependency graph
requires:
  - phase: 14-docs-rewrite
    provides: "first-query tutorial structure with tabbed Snowflake/Databricks examples"
provides:
  - "Corrected DDL examples using official Snowflake CREATE SEMANTIC VIEW and Databricks CREATE VIEW WITH METRICS syntax"
affects: [tutorials, docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Snowflake DDL uses TABLES/DIMENSIONS/METRICS clauses with table_alias.name AS expr format"
    - "Databricks DDL uses CREATE VIEW ... WITH METRICS LANGUAGE YAML with YAML body in $$ delimiters"

key-files:
  created: []
  modified:
    - docs/src/tutorials/first-query.md

key-decisions:
  - "Used matching field names (s.revenue, s.cost) in Snowflake DDL rather than total_revenue/total_cost for tutorial clarity"
  - "Changed prose from 'maps to a view like' to 'maps to a definition like' since Databricks uses YAML not SQL view syntax"
  - "Skipped fact hint in Databricks DDL since YAML has no separate fact concept (deferred to dedicated docs)"

patterns-established:
  - "DDL examples in tutorials must use valid syntax from official warehouse docs, not invented shorthand"

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-02-23
---

# Phase 18 Plan 01: Fix Invalid CREATE VIEW Examples Summary

**Replaced invented Snowflake/Databricks DDL with valid CREATE SEMANTIC VIEW and CREATE VIEW ... WITH METRICS LANGUAGE YAML syntax in first-query tutorial**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-23T17:07:08Z
- **Completed:** 2026-02-23T17:08:08Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Snowflake DDL now shows valid CREATE OR REPLACE SEMANTIC VIEW with mandatory TABLES clause, DIMENSIONS, and METRICS using table_alias.name AS expr format
- Databricks DDL now shows valid CREATE VIEW ... WITH METRICS LANGUAGE YAML wrapping a YAML body inside $$ delimiters with dimensions/measures arrays
- Removed query-time functions AGG() and MEASURE() that were incorrectly used in view definitions
- MkDocs docs build passes with --strict flag

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace DDL examples with valid warehouse syntax** - `a01fe05` (fix)

## Files Created/Modified
- `docs/src/tutorials/first-query.md` - Corrected both Snowflake and Databricks DDL code blocks in the tabbed section (lines 33-73)

## Decisions Made
- Used matching field names (`s.revenue`, `s.cost`) in Snowflake DDL rather than `total_revenue`/`total_cost` per research recommendation -- keeps tutorial simple by matching the Cubano model field names
- Changed lead-in prose from "maps to a view like" to "maps to a definition like" since Databricks metric views are defined in YAML, not as traditional SQL views
- Skipped fact column hint in Databricks DDL since the YAML syntax has no separate fact concept -- deferred to dedicated Fact field type documentation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tutorial DDL examples now use valid, recognizable warehouse syntax
- No blockers or follow-up tasks

## Self-Check: PASSED

- FOUND: docs/src/tutorials/first-query.md
- FOUND: 18-01-SUMMARY.md
- FOUND: a01fe05

---
*Phase: 18-fix-invalid-create-view-examples-in-first-query-tutorial*
*Completed: 2026-02-23*
