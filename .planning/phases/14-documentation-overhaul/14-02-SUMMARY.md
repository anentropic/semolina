---
phase: 14-documentation-overhaul
plan: 02
subsystem: docs
tags: [diataxis, tutorials, explanation, humanizer, mkdocs]

# Dependency graph
requires:
  - phase: 14-documentation-overhaul
    provides: "Diataxis-organized directory structure with top-tabs navigation"
provides:
  - "Diataxis tutorial pages: installation and first-query with runnable code"
  - "Semantic views explanation page with vendor doc links"
  - "Updated home page with correct links and warm-but-efficient tone"
affects: [14-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Diataxis tutorial pattern: step-by-step with expected output at each step"
    - "Diataxis explanation pattern: concept-focused, no instructions, vendor doc links"
    - "Humanizer tone: second person, warm but efficient, no AI vocabulary"

key-files:
  created: []
  modified:
    - docs/src/tutorials/installation.md
    - docs/src/tutorials/first-query.md
    - docs/src/tutorials/index.md
    - docs/src/explanation/semantic-views.md
    - docs/src/explanation/index.md
    - docs/src/index.md

key-decisions:
  - "Tutorials use MockEngine for runnable examples without warehouse credentials"
  - "Explanation page kept brief (49 lines) with links to vendor docs for setup details"
  - "Home page tagline frames Cubano for engineers who already have semantic views"

patterns-established:
  - "Tutorial pages: intro with learning goals, numbered steps, code with expected output, See also at end"
  - "Explanation pages: concept definition, vendor implementations, where Cubano fits, See also links"
  - "All prose second person, warm-but-efficient, humanizer-checked"

requirements-completed: [DOCS-01]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 14 Plan 02: Content Rewrite Summary

**Diataxis tutorial and explanation pages with runnable code, vendor doc links, and warm-but-efficient second-person prose**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T12:11:50Z
- **Completed:** 2026-02-22T12:14:57Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Rewrote installation and first-query tutorials with diataxis tutorial structure: step-by-step, runnable code, expected output at each step
- Created semantic views explanation page: concept-focused, Snowflake/Databricks vendor doc links, no step-by-step instructions
- Updated home page with correct links, target audience tagline, and consistent tone
- All prose passes humanizer check: second person, no AI vocabulary, no promotional language

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite tutorial pages using diataxis tutorial rules** - `a86994b` (feat)
2. **Task 2: Create explanation page and update home page** - `f9df67a` (feat)

## Files Created/Modified

- `docs/src/tutorials/installation.md` - Step-by-step install tutorial with backend extras and verification
- `docs/src/tutorials/first-query.md` - Complete tutorial: model, engine, query, results with expected output
- `docs/src/tutorials/index.md` - Section landing with tutorial links and audience framing
- `docs/src/explanation/semantic-views.md` - Concept explanation with Snowflake/Databricks vendor links
- `docs/src/explanation/index.md` - Section landing with link to semantic-views
- `docs/src/index.md` - Updated card descriptions, tagline, consistent tone

## Decisions Made

- Tutorials use MockEngine for all runnable examples so readers don't need warehouse credentials
- Explanation page kept at 49 lines (within 40-70 target) to stay brief and focused
- Home page tagline reframed: "Query your warehouse semantic views from Python" for the target audience of engineers who already have semantic views

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All tutorial, explanation, and home pages rewritten with diataxis structure and humanizer tone
- Ready for Plan 03 (how-to guides rewrite) to complete the content overhaul
- mkdocs build --strict passes cleanly

## Self-Check: PASSED

- All 6 modified files verified on disk
- Both task commits (a86994b, f9df67a) verified in git log

---
*Phase: 14-documentation-overhaul*
*Completed: 2026-02-22*
