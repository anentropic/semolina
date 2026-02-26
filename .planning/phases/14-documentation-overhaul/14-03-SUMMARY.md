---
phase: 14-documentation-overhaul
plan: 03
subsystem: docs
tags: [mkdocs, diataxis, how-to-guides, humanizer, tabbed-sql]

# Dependency graph
requires:
  - phase: 14-documentation-overhaul
    provides: "Diataxis-organized directory structure with how-to/ pages from Plan 01"
provides:
  - "10 rewritten how-to guides with diataxis how-to structure"
  - "Tabbed Snowflake/Databricks SQL examples in 6 guides"
  - "Backend comparison page with 3 side-by-side SQL dialect blocks"
  - "See also cross-reference sections on all how-to pages"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Diataxis how-to guide structure: goal-oriented title, illustrative snippets, See also links"
    - "Tabbed SQL dialect examples using === Snowflake / === Databricks MkDocs Material syntax"
    - "Humanizer tone pass: no AI vocabulary, no promotional language, second-person throughout"

key-files:
  created: []
  modified:
    - docs/src/how-to/index.md
    - docs/src/how-to/models.md
    - docs/src/how-to/queries.md
    - docs/src/how-to/filtering.md
    - docs/src/how-to/ordering.md
    - docs/src/how-to/backends/overview.md
    - docs/src/how-to/backends/snowflake.md
    - docs/src/how-to/backends/databricks.md
    - docs/src/how-to/codegen.md
    - docs/src/how-to/warehouse-testing.md

key-decisions:
  - "Headings use action verbs (How to define models, How to filter queries) not noun phrases"
  - "Tabbed SQL examples placed after relevant code snippet, not collected in separate section"
  - "Backend overview uses 3 full tabbed comparison blocks showing SELECT, WHERE, and ORDER BY differences"

patterns-established:
  - "How-to guide title pattern: How to [verb] [object]"
  - "Tabbed SQL placement: immediately after the Python code that generates the SQL"
  - "See also section: 2-4 links to related pages, placed at end of every how-to guide"

requirements-completed: [DOCS-03, DOCS-04, DOCS-05]

# Metrics
duration: 6min
completed: 2026-02-22
---

# Phase 14 Plan 03: How-To Guides Rewrite Summary

**10 how-to guides rewritten with diataxis structure, tabbed Snowflake/Databricks SQL examples, and humanizer-reviewed prose**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-22T12:11:59Z
- **Completed:** 2026-02-22T12:17:40Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Rewrote all 10 how-to guides from scratch following diataxis how-to guide rules (goal-oriented, practical, for competent users)
- Added tabbed Snowflake/Databricks SQL examples to 6 guides (models, queries, filtering, ordering, backends/overview, codegen)
- Backend overview page has 3 side-by-side SQL comparison blocks covering SELECT, WHERE, and ORDER BY differences (DOCS-05)
- All pages have See also cross-reference sections and use second-person perspective throughout
- Humanizer pass confirmed: zero AI vocabulary words, zero promotional language

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite core how-to guides (models, queries, filtering, ordering)** - `147ecae` (feat)
2. **Task 2: Rewrite backend and tooling how-to guides** - `821911e` (feat)

## Files Created/Modified

- `docs/src/how-to/index.md` - Section landing page with categorized links
- `docs/src/how-to/models.md` - How to define SemanticView models with field types
- `docs/src/how-to/queries.md` - How to build queries with method chaining and execution
- `docs/src/how-to/filtering.md` - How to filter with operators, named methods, boolean composition
- `docs/src/how-to/ordering.md` - How to order and limit results with NullsOrdering
- `docs/src/how-to/backends/overview.md` - Backend comparison with 3 tabbed SQL blocks
- `docs/src/how-to/backends/snowflake.md` - Snowflake connection and credential loading
- `docs/src/how-to/backends/databricks.md` - Databricks connection and Unity Catalog
- `docs/src/how-to/codegen.md` - CLI codegen with tabbed output examples
- `docs/src/how-to/warehouse-testing.md` - Snapshot testing with corrected Phase 13 paths

## Decisions Made

- Used action-verb headings ("How to define models") throughout, following diataxis how-to naming convention
- Placed tabbed SQL examples inline after the Python code that generates them, rather than collecting in a separate section, for better readability flow
- Backend overview has 3 full comparison blocks (SELECT, WHERE, ORDER BY) rather than just one, to properly satisfy DOCS-05

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All how-to guides complete with diataxis structure, tabbed SQL, and humanizer-reviewed prose
- Phase 14 documentation overhaul fully complete (Plans 01, 02, 03 all done)

## Self-Check: PASSED

- All 10 modified files verified on disk
- Both task commits (147ecae, 821911e) verified in git log

---
*Phase: 14-documentation-overhaul*
*Completed: 2026-02-22*
