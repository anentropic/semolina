---
phase: 29-documentation-update
plan: 01
subsystem: docs
tags: [mkdocs, tutorials, homepage, mockpool, pool-from-config, semolina-cursor]

# Dependency graph
requires:
  - phase: 28-query-shorthand
    provides: query() shorthand kwargs for tutorial examples
  - phase: 27-toml-config
    provides: pool_from_config() for connection registration examples
  - phase: 26-semolina-cursor
    provides: SemolinaCursor.fetchall_rows() for result access examples
  - phase: 25-pool-registry
    provides: MockPool and register(dialect=) for tutorial examples
provides:
  - Tutorials updated for v0.3 pool/cursor/config API
  - Homepage quick example showing pool_from_config() workflow
  - Installation page with updated backend extra descriptions
affects: [29-02-PLAN, 29-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [pool_from_config tutorial pattern, MockPool tutorial pattern, SemolinaCursor.fetchall_rows() result pattern]

key-files:
  created: []
  modified:
    - docs/src/tutorials/first-query.md
    - docs/src/tutorials/installation.md
    - docs/src/index.md

key-decisions:
  - "Tutorial and homepage code identical for Snowflake/Databricks tabs since pool_from_config() handles backend difference via .semolina.toml type field"

patterns-established:
  - "v0.3 tutorial pattern: MockPool + register(dialect='mock') for runnable examples without warehouse"
  - "v0.3 homepage pattern: pool_from_config() as the primary connection example"

requirements-completed: [DOCS-01]

# Metrics
duration: 3min
completed: 2026-03-17
---

# Phase 29 Plan 01: Tutorial & Homepage Rewrite Summary

**Tutorials and homepage rewritten for v0.3 API: MockPool, pool_from_config(), SemolinaCursor.fetchall_rows(), and query() shorthand**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-17T11:18:48Z
- **Completed:** 2026-03-17T11:22:28Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- first-query.md fully rewritten: MockPool replaces MockEngine, pool_from_config replaces Engine constructors, SemolinaCursor.fetchall_rows() replaces direct iteration, query() shorthand shown alongside fluent chain
- installation.md updated: backend extras now reference adbc-poolhouse, MockPool replaces MockEngine
- Homepage quick example updated: pool_from_config() and cursor.fetchall_rows() replace SnowflakeEngine and direct iteration

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite first-query.md tutorial and update installation.md** - `a3624eb` (feat)
2. **Task 2: Update homepage quick example** - `97ec5df` (feat)

## Files Created/Modified
- `docs/src/tutorials/first-query.md` - Full tutorial rewrite for v0.3 API with MockPool, pool_from_config, SemolinaCursor, query shorthand
- `docs/src/tutorials/installation.md` - Updated backend extra descriptions (adbc-poolhouse) and MockPool reference
- `docs/src/index.md` - Homepage quick example with pool_from_config() and cursor.fetchall_rows()

## Decisions Made
- Tutorial Snowflake and Databricks tabs show identical code since pool_from_config() handles the backend difference through the .semolina.toml type field. A note below the tabs explains this.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Task 1 files (first-query.md, installation.md) were already committed from a prior execution attempt in commit `a3624eb`. Content matched plan requirements exactly, so no additional commit was needed for Task 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tutorial and homepage are clean v0.3 API references
- Ready for 29-02 (backend how-to guides rewrite) and 29-03 (queries how-to, minor updates, stale-term sweep)
- No stale Engine/MockEngine/SnowflakeEngine/DatabricksEngine references remain in tutorials or homepage

## Self-Check: PASSED

- All 3 modified files exist on disk
- Commit `a3624eb` found in history
- Commit `97ec5df` found in history
- `uv run mkdocs build --strict` passes with zero warnings

---
*Phase: 29-documentation-update*
*Completed: 2026-03-17*
