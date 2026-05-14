---
phase: 37-documentation
plan: 03
subsystem: docs
tags: [sphinx, rst, duckdb, codegen, cli, documentation]

# Dependency graph
requires:
  - phase: 37-01
    provides: "Restored v0.4.0 source files and created Arrow/DuckDB how-to pages"
provides:
  - "DuckDB codegen documentation in codegen.rst and codegen-credentials.rst"
  - "DuckDB CLI reference in cli.rst (--backend duckdb, --database flag)"
  - "Version bump to 0.4.0 in installation tutorial"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DuckDB tab-item with :sync: duckdb in all warehouse tab-sets"

key-files:
  created: []
  modified:
    - docs/src/how-to/codegen.rst
    - docs/src/how-to/codegen-credentials.rst
    - docs/src/reference/cli.rst
    - docs/src/tutorials/installation.rst

key-decisions:
  - "Wrapped Databricks Fact-type note in .. note:: directive to cover both Databricks and DuckDB behavior"
  - "Documented DuckDB .env exclusion in CLI reference SEMOLINA_ENV_FILE note"

patterns-established:
  - "DuckDB codegen examples use --database /path/to/db pattern (not env var)"

requirements-completed: [DOCS-02]

# Metrics
duration: 4min
completed: 2026-04-27
---

# Phase 37 Plan 03: Codegen, CLI Reference, and Installation Docs Summary

**DuckDB codegen docs with DDL examples, CLI --database flag reference, and v0.4.0 version bump across four RST pages**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-27T10:58:43Z
- **Completed:** 2026-04-27T11:02:27Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Codegen how-to now shows DuckDB as a third backend with CREATE SEMANTIC VIEW DDL, CLI command, and generated model output
- Codegen credentials page documents --database flag, DUCKDB_DATABASE env var, and TOML config fallback for DuckDB
- CLI reference documents --backend duckdb, --database/-d flag, and DuckDB environment variables tab
- Installation tutorial version bumped from 0.3.0 to 0.4.0

## Task Commits

Each task was committed atomically:

1. **Task 1: Update codegen how-to and credentials pages with DuckDB content** - `40a21e4` (feat)
2. **Task 2: Update CLI reference and installation tutorial** - `2c4aa6d` (feat)

## Files Created/Modified
- `docs/src/how-to/codegen.rst` - Added DuckDB row to backend table, DuckDB tab with DDL and generated output, updated field type mapping and See also
- `docs/src/how-to/codegen-credentials.rst` - Added DuckDB credentials section, DuckDB tab in config fallback, updated warning box and See also
- `docs/src/reference/cli.rst` - Added duckdb to --backend list, --database flag docs, DuckDB env vars tab, updated SEMOLINA_ENV_FILE note
- `docs/src/tutorials/installation.rst` - Version number 0.3.0 to 0.4.0

## Decisions Made
- Wrapped the existing Databricks Fact-type note in a `.. note::` directive to cover both Databricks and DuckDB behavior in one place
- Updated the field type mapping table from "Fact (Snowflake only)" to "Fact (Snowflake and DuckDB)" since DuckDB supports all three field kinds
- Added explicit note that DuckDB does not use .env files in the CLI reference SEMOLINA_ENV_FILE section

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All four target pages updated with DuckDB content
- Documentation build passes with zero warnings
- Cross-references to backends/duckdb page in See also sections (created by 37-01)

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 37-documentation*
*Completed: 2026-04-27*
