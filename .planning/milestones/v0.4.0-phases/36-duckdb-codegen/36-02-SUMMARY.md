---
phase: 36-duckdb-codegen
plan: 02
subsystem: cli
tags: [duckdb, codegen, cli, typer, introspection]

# Dependency graph
requires:
  - phase: 36-duckdb-codegen
    plan: 01
    provides: DuckDBEngine class with introspect() method
provides:
  - DuckDB backend alias ("duckdb") in codegen CLI _resolve_backend()
  - --database/-d CLI option with DUCKDB_DATABASE env var fallback
  - Clear error message when --database missing for duckdb backend
affects: [cli-codegen, duckdb-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns: [env-var-fallback-for-cli-options]

key-files:
  created: []
  modified:
    - src/semolina/cli/codegen.py
    - tests/unit/codegen/test_cli.py

key-decisions:
  - "Used typer.Option envvar parameter for DUCKDB_DATABASE fallback rather than manual os.environ lookup"
  - "database parameter is keyword-only on _resolve_backend to keep it backwards compatible with existing callers"
  - "Missing --database for duckdb backend raises typer.BadParameter (exit 2) with message mentioning both --database and DUCKDB_DATABASE"

patterns-established:
  - "CLI options with env var fallback via typer.Option(envvar=...) pattern"
  - "Backend-specific options passed through _resolve_backend keyword args"

requirements-completed: [DKGEN-01, DKGEN-02]

# Metrics
duration: 3min
completed: 2026-04-26
---

# Phase 36 Plan 02: DuckDB CLI Backend Summary

**DuckDB backend wired into codegen CLI with --database option and DUCKDB_DATABASE env var fallback**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-26T22:43:12Z
- **Completed:** 2026-04-26T22:46:24Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Added "duckdb" alias in _resolve_backend() that creates DuckDBEngine(database=...) from the --database option
- Added --database/-d CLI option with DUCKDB_DATABASE env var fallback via Typer's envvar parameter
- Clear error message when --database is missing for duckdb backend: exits 2 with actionable guidance
- Updated help text and unknown-backend error message to list all three backends (snowflake, databricks, duckdb)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire DuckDB backend into CLI with --database option and tests**
   - `5c1254a` (test: RED -- 6 failing tests for DuckDB CLI backend)
   - `dbaff24` (feat: GREEN -- implementation making all 30 CLI tests pass)

_TDD task with separate test and implementation commits._

## Files Created/Modified
- `src/semolina/cli/codegen.py` - Added duckdb elif branch in _resolve_backend(), --database option in codegen(), updated help/error text
- `tests/unit/codegen/test_cli.py` - Added TestDuckDBBackend class with 6 tests covering --database flag, env var, missing database, direct resolution, view-not-found, connection-error

## Decisions Made
- Used Typer's `envvar="DUCKDB_DATABASE"` on the `--database` option for automatic env var fallback -- cleaner than manual `os.environ` lookup
- Made `database` keyword-only on `_resolve_backend()` to maintain backward compatibility with existing callers that pass only `backend_spec`
- Patched `semolina.engines.duckdb.DuckDBEngine` in the direct-resolution test since the import is lazy (inside elif branch)

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- `semolina codegen --backend duckdb --database path/to/db view_name` is fully functional
- The codegen CLI now supports all three warehouse backends (Snowflake, Databricks, DuckDB)
- DuckDB codegen documentation can reference the --database option and DUCKDB_DATABASE env var

## Self-Check: PASSED

All 2 modified files found. All 2 commit hashes verified. All 11 acceptance criteria confirmed.

---
*Phase: 36-duckdb-codegen*
*Completed: 2026-04-26*
