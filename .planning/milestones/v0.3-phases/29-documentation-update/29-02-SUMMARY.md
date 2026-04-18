---
phase: 29-documentation-update
plan: 02
subsystem: documentation
tags: [mkdocs, how-to, backends, pool, toml, adbc-poolhouse]

# Dependency graph
requires:
  - phase: 27-config-pool-from-config
    provides: pool_from_config() function and .semolina.toml config format
  - phase: 25-pool-registry
    provides: register() with dialect= parameter and MockPool
  - phase: 26-semolina-cursor
    provides: SemolinaCursor with fetchall_rows() method
provides:
  - Rewritten backend overview how-to with pool_from_config() and manual pool construction
  - Rewritten Snowflake how-to with TOML config and SnowflakeConfig manual setup
  - Rewritten Databricks how-to with TOML config and DatabricksConfig manual setup
affects: [29-03, 29-documentation-update]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-pattern connection docs (TOML recommended + manual pool), field reference tables for TOML config]

key-files:
  created: []
  modified:
    - docs/src/how-to/backends/overview.md
    - docs/src/how-to/backends/snowflake.md
    - docs/src/how-to/backends/databricks.md

key-decisions:
  - "Preserved codegen sections as-is since codegen still uses engine introspection internally"
  - "Used query.to_sql() instead of engine.to_sql() for SQL inspection examples"

patterns-established:
  - "Backend how-to pattern: install extra, TOML config (recommended), manual construction, run query, inspect SQL, codegen, see also"

requirements-completed: [DOCS-02]

# Metrics
duration: 3min
completed: 2026-03-17
---

# Phase 29 Plan 02: Backend How-To Guides Summary

**Rewrote all three backend how-to guides (overview, Snowflake, Databricks) for v0.3 pool_from_config() TOML config and manual adbc-poolhouse pool construction**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-17T11:18:52Z
- **Completed:** 2026-03-17T11:22:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Backend overview rewritten with two connection patterns: TOML config (recommended) and manual pool construction, plus MockPool for local testing
- Snowflake how-to rewritten with .semolina.toml field reference table, SnowflakeConfig manual setup, and query.to_sql() inspection
- Databricks how-to rewritten with .semolina.toml field reference table, DatabricksConfig manual setup, Unity Catalog three-part names, and query.to_sql() inspection
- All SnowflakeEngine, DatabricksEngine, MockEngine, SnowflakeCredentials, and DatabricksCredentials references removed
- All query examples updated to use SemolinaCursor.fetchall_rows()

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite backends overview.md** - `a3624eb` (feat)
2. **Task 2: Rewrite snowflake.md and databricks.md** - `b9b2f8f` (feat)

## Files Created/Modified

- `docs/src/how-to/backends/overview.md` - Backend overview with pool_from_config() and manual pool construction patterns, MockPool testing section
- `docs/src/how-to/backends/snowflake.md` - Snowflake connection how-to with TOML config, field reference table, SnowflakeConfig manual setup
- `docs/src/how-to/backends/databricks.md` - Databricks connection how-to with TOML config, field reference table, DatabricksConfig manual setup, Unity Catalog section

## Decisions Made

- Preserved codegen output sections unchanged since codegen still uses engine introspection internally
- Used `query.to_sql()` for SQL inspection instead of removed `engine.to_sql()` pattern
- Used field names from `.semolina.toml.example` (host/token for Databricks, not server_hostname/access_token)

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

- `blacken-docs` pre-commit hook reformatted a `pool_from_config()` line in snowflake.md (auto-fixed on second commit attempt)

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Backend how-to guides complete and ready for cross-referencing from other docs
- Query and results how-to updates (plan 29-03) can proceed

## Self-Check: PASSED

All created/modified files verified on disk. All task commits verified in git log.

---
*Phase: 29-documentation-update*
*Completed: 2026-03-17*
