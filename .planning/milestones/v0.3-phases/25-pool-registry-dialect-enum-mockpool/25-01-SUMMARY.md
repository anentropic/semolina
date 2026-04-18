---
phase: 25-pool-registry-dialect-enum-mockpool
plan: 01
subsystem: registry
tags: [strenum, dialect, pool, registry, backward-compat, deprecation]

# Dependency graph
requires: []
provides:
  - "Dialect StrEnum (SNOWFLAKE, DATABRICKS, MOCK) in src/semolina/dialect.py"
  - "resolve_dialect() mapping string/enum to concrete DialectABC instances"
  - "Pool+dialect registry: register(name, pool, dialect=) and get_pool(name)"
  - "Backward-compatible engine registry with DeprecationWarning"
  - "Public exports: Dialect and get_pool from semolina.__init__"
affects: [25-02-mockpool, 26-semolina-cursor, 27-toml-config]

# Tech tracking
tech-stack:
  added: []
  patterns: ["StrEnum for public-facing enum with string values", "TYPE_CHECKING guard for ABC to avoid circular imports", "contextlib.suppress for pool cleanup in reset()"]

key-files:
  created:
    - "src/semolina/dialect.py"
    - "tests/unit/test_dialect.py"
  modified:
    - "src/semolina/registry.py"
    - "src/semolina/__init__.py"
    - "src/semolina/engines/__init__.py"
    - "tests/unit/test_registry.py"

key-decisions:
  - "StrEnum Dialect is the public name; engines.sql.Dialect ABC renamed to DialectABC in engines/__init__.py"
  - "resolve_dialect uses lazy import inside function body to avoid circular imports"
  - "Old register(name, engine) emits DeprecationWarning with stacklevel=2"
  - "reset() calls pool.close() with contextlib.suppress(Exception) for safety"

patterns-established:
  - "Dialect StrEnum: public enum for backend selection across the API"
  - "Pool+dialect tuple storage: registry stores (pool, DialectABC) pairs"
  - "Backward compat via dual-dict registry: _pools for new API, _engines for deprecated"

requirements-completed: [CONN-01, CONN-03]

# Metrics
duration: 7min
completed: 2026-03-16
---

# Phase 25 Plan 01: Dialect StrEnum & Pool Registry Summary

**Dialect StrEnum with SNOWFLAKE/DATABRICKS/MOCK members, resolve_dialect() function, and pool+dialect registry replacing the v0.2 engine-only registry with full backward compatibility**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-16T23:39:23Z
- **Completed:** 2026-03-16T23:47:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created Dialect StrEnum that validates backend strings and provides string equality
- Implemented resolve_dialect() to map string/enum to concrete SnowflakeDialect/DatabricksDialect/MockDialect instances
- Rewrote registry to store (pool, dialect) tuples alongside backward-compatible engine storage
- Added get_pool() to retrieve pool+dialect pairs; kept get_engine() for backward compat
- Exported Dialect and get_pool from semolina.__init__ for public API
- Renamed engines/__init__.py ABC re-export from Dialect to DialectABC to avoid naming collision

## Task Commits

Each task was committed atomically (TDD red-green):

1. **Task 1: Dialect StrEnum and resolve_dialect()** (TDD)
   - `6a32364` test(25-01): add failing tests for Dialect StrEnum and resolve_dialect
   - `5e740e4` feat(25-01): implement Dialect StrEnum and resolve_dialect()

2. **Task 2: Registry rewrite for pool+dialect storage** (TDD)
   - `580fe21` test(25-01): add failing tests for pool+dialect registry
   - `e5f342e` feat(25-01): rewrite registry for pool+dialect storage with backward compat

_Note: TDD tasks have RED (test) then GREEN (feat) commits._

## Files Created/Modified
- `src/semolina/dialect.py` - New Dialect StrEnum and resolve_dialect() function
- `src/semolina/registry.py` - Rewritten: dual-dict _pools + _engines, register() with dialect= kwarg, get_pool()
- `src/semolina/__init__.py` - Added Dialect and get_pool exports
- `src/semolina/engines/__init__.py` - Renamed Dialect ABC re-export to DialectABC
- `tests/unit/test_dialect.py` - 17 tests for Dialect enum and resolve_dialect
- `tests/unit/test_registry.py` - 23 tests: 11 existing engine tests + 11 pool tests + 1 deprecation warning test

## Decisions Made
- Used `TYPE_CHECKING` guard for the DialectABC import in dialect.py to avoid circular import between dialect.py and engines/sql.py
- Kept the _DIALECT_MAP as a local variable inside resolve_dialect() rather than module-level, since it depends on lazy imports
- Existing engine tests wrapped with `warnings.catch_warnings()` to suppress expected DeprecationWarning noise
- Used `contextlib.suppress(Exception)` for pool.close() in reset() per ruff SIM105

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Recreated corrupted .venv**
- **Found during:** Task 1 (RED phase, running tests)
- **Issue:** .venv had shebang pointing to wrong project (cubano), making pytest unrunnable
- **Fix:** Deleted .venv and ran `uv sync` to recreate it
- **Files modified:** .venv/ (not tracked)
- **Verification:** `uv run pytest` runs successfully

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Environment fix only, no code impact.

## Issues Encountered
- Pre-existing test failures in test_databricks_engine.py and test_snowflake_engine.py due to missing driver packages (not related to this plan)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Dialect StrEnum and resolve_dialect() ready for use by MockPool (Plan 25-02)
- Registry stores pool+dialect pairs, ready for SemolinaCursor to call get_pool() (Phase 26)
- Old engine API still functional with deprecation warnings for gradual migration

---
*Phase: 25-pool-registry-dialect-enum-mockpool*
*Completed: 2026-03-16*
