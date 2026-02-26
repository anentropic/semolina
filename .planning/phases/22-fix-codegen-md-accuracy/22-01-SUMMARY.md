---
phase: 22-fix-codegen-md-accuracy
plan: 01
subsystem: docs
tags: [mkdocs, codegen, snowflake, documentation-accuracy]

# Dependency graph
requires:
  - phase: 20-reverse-codegen
    provides: The codegen command and Snowflake introspection implementation (SHOW COLUMNS IN VIEW)
  - phase: 08-integration-testing
    provides: SnowflakeCredentials with env_prefix="SNOWFLAKE_"
provides:
  - Accurate codegen how-to guide with correct SQL command and env var name
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - docs/src/how-to/codegen.md

key-decisions:
  - "Two targeted string replacements only — no prose rewrites, no reformatting beyond what blacken-docs enforces"

patterns-established: []

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-02-25
---

# Phase 22 Plan 01: Fix codegen.md Accuracy Summary

**Corrected two factual errors in codegen.md: Snowflake introspects via `SHOW COLUMNS IN VIEW` (not `SHOW COLUMNS IN SEMANTIC VIEW`) and credentials use `SNOWFLAKE_ACCOUNT` (not `CUBANO_SNOWFLAKE_ACCOUNT`)**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-25T15:50:05Z
- **Completed:** 2026-02-25T15:51:10Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Fixed Snowflake backend table row: `SHOW COLUMNS IN SEMANTIC VIEW` -> `SHOW COLUMNS IN VIEW` (matches `snowflake.py:322`)
- Fixed credentials paragraph: `CUBANO_SNOWFLAKE_ACCOUNT` -> `SNOWFLAKE_ACCOUNT` (matches `credentials.py` `env_prefix="SNOWFLAKE_"`)
- Docs build passes with `uv run mkdocs build --strict`

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix two accuracy errors in codegen.md** - `0fc920e` (fix)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `docs/src/how-to/codegen.md` - Two string corrections plus blacken-docs auto-reformat of Databricks class definition

## Decisions Made

None - followed plan as specified. Two targeted replacements only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] blacken-docs reformatted Databricks class definition in code block**
- **Found during:** Task 1 (pre-commit hook failure on first commit attempt)
- **Issue:** `blacken-docs` hook reformatted `class OrdersView(SemanticView, view="main.analytics.orders_view"):` to a 3-line form with `(` on first line and `)` on third
- **Fix:** Accepted the reformatted output and re-staged the file; docs build still passes
- **Files modified:** `docs/src/how-to/codegen.md`
- **Verification:** Second commit attempt passed all pre-commit hooks
- **Committed in:** `0fc920e` (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — pre-commit hook reformat)
**Impact on plan:** Auto-fix necessary to allow commit. No semantic change to documentation content.

## Issues Encountered

None beyond the blacken-docs reformat handled above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `docs/src/how-to/codegen.md` is now factually accurate
- No blockers for subsequent work

---
*Phase: 22-fix-codegen-md-accuracy*
*Completed: 2026-02-25*
