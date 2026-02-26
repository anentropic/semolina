---
phase: 19-document-fact-field-type-for-databricks-and-snowflake-users
plan: 01
subsystem: docs
tags: [mkdocs, how-to, fact-fields, snowflake, databricks, semantic-views]

# Dependency graph
requires:
  - phase: 18-fix-invalid-create-view-examples
    provides: correct warehouse DDL examples in tutorial (baseline for accurate docs)
provides:
  - Expanded ### Fact fields section with warehouse divergence, when-to-use guidance, and canonical examples
  - Updated comparison table Fact row with semantic intent framing
  - One-sentence Fact mention in semantic-views.md explanation page
affects: [documentation, how-to guides, models.md, semantic-views.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bold warehouse lead-ins (not admonitions) for warehouse-specific divergence prose"

key-files:
  created: []
  modified:
    - docs/src/how-to/models.md
    - docs/src/explanation/semantic-views.md

key-decisions:
  - "Inline bold prose (**Snowflake users:** / **Databricks users:**) instead of admonitions for warehouse divergence — lighter, matches reading flow"
  - "One-sentence Fact mention added to semantic-views.md (fits naturally, prevents the page from implying two-type system)"
  - "blacken-docs hook reformatted code comment alignment — accepted as correct"

patterns-established:
  - "Warehouse-specific guidance uses bold lead-in paragraph format (no admonition wrappers) for inline divergence prose"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 19 Plan 01: Document Fact Field Type Summary

**Fact fields section rewritten with Snowflake FACTS clause mapping, Databricks no-native-fact framing, identical-SQL runtime note, and "default to Dimension" recommendation**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-23T23:51:30Z
- **Completed:** 2026-02-23T23:52:51Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Expanded `### Fact fields` section from 2 thin sentences to a complete guide covering warehouse divergence, runtime behavior, when-to-use, and canonical column examples
- Updated comparison table `Fact` row: now shows `unit_price`, `quantity` as canonical examples and frames the field as a semantic signal vs categorical `Dimension`
- Added one-sentence `Fact` mention to `semantic-views.md` explanation page so the page no longer implies the type system has only two types

## Task Commits

1. **Task 1: Expand the Fact fields section and update related docs** - `dee7f94` (docs)

## Files Created/Modified

- `docs/src/how-to/models.md` - Comparison table Fact row updated; `### Fact fields` section fully rewritten with warehouse divergence, runtime note, when-to-use, and code contrast snippet
- `docs/src/explanation/semantic-views.md` - One-sentence Fact mention added after "Metric and Dimension fields" prose

## Decisions Made

- Used bold lead-in paragraphs (**Snowflake users:** / **Databricks users:**) for warehouse-specific divergence rather than `!!! note` admonitions — inline prose is lighter and keeps reading flow, matching the plan's style guidance
- Added Fact to `semantic-views.md` — fits naturally after the "Metric and Dimension fields" sentence and prevents the explanation page from implying a two-type system
- Accepted `blacken-docs` reformatting of code comment alignment (trailing spaces on `# categorical grouping attribute`) — correct behavior from pre-commit hook

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `blacken-docs` pre-commit hook reformatted the Python code snippet in `models.md` on first commit attempt — re-staged the modified file and committed successfully on second attempt. No content change, only whitespace normalization.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOCS-04 requirement satisfied: Fact field type is fully documented for both warehouse audiences
- `uv run mkdocs build --strict` passes with zero errors

---
*Phase: 19-document-fact-field-type-for-databricks-and-snowflake-users*
*Completed: 2026-02-24*
