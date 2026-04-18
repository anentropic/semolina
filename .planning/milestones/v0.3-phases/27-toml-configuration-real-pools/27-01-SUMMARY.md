---
phase: 27-toml-configuration-real-pools
plan: 01
subsystem: config
tags: [toml, adbc-poolhouse, pool-factory, pydantic-settings]

# Dependency graph
requires:
  - phase: 25-pool-registry-dialect-enum-mockpool
    provides: Dialect StrEnum and pool registry for (pool, Dialect) tuple storage
provides:
  - pool_from_config() factory function reading .semolina.toml
  - _CONFIG_MAP dispatch from type field to adbc-poolhouse config classes
  - adbc-poolhouse as core dependency
affects: [27-02, 28, 29]

# Tech tracking
tech-stack:
  added: [adbc-poolhouse>=1.2.0, sqlalchemy (transitive), adbc-driver-manager (transitive)]
  patterns: [type-dispatch config loading via _CONFIG_MAP dict]

key-files:
  created: [src/semolina/config.py, tests/unit/test_config.py]
  modified: [pyproject.toml]

key-decisions:
  - "Patch _CONFIG_MAP dict in tests rather than individual class names, since _CONFIG_MAP captures class references at import time"
  - "adbc-poolhouse is core dependency with top-level imports (not lazy/optional)"
  - "Updated snowflake extra to adbc-poolhouse[snowflake], kept databricks extra as databricks-sql-connector fallback"

patterns-established:
  - "_CONFIG_MAP: dict mapping type strings to (config_class, Dialect) tuples for dispatch"
  - "TOML connection sections: [connections.name] with type field popped before config class instantiation"

requirements-completed: [CONF-01, CONF-02, CONF-03]

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 27 Plan 01: Config Module Summary

**pool_from_config() factory reads .semolina.toml and creates (pool, Dialect) tuples via adbc-poolhouse config class dispatch**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T09:09:09Z
- **Completed:** 2026-03-17T09:13:50Z
- **Tasks:** 1 (TDD: RED-GREEN-REFACTOR)
- **Files modified:** 3

## Accomplishments
- Created pool_from_config() that reads TOML config and returns (pool, Dialect) tuples ready for register()
- Added adbc-poolhouse>=1.2.0 as core dependency with SnowflakeConfig and DatabricksConfig dispatch
- Comprehensive test suite: 15 tests covering dispatch, factory behavior, and all error paths
- All quality gates pass: tests, lint, format, typecheck

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `a1e76e0` (test)
2. **Task 1 (GREEN): Implementation + test fix** - `0dd6596` (feat)

_TDD task with RED and GREEN commits._

## Files Created/Modified
- `src/semolina/config.py` - pool_from_config() factory with _CONFIG_MAP type dispatch
- `tests/unit/test_config.py` - 15 tests: TestConfigDispatch (3), TestPoolFromConfig (6), TestConfigErrors (6)
- `pyproject.toml` - adbc-poolhouse core dependency, updated snowflake extra

## Decisions Made
- Patching _CONFIG_MAP dict in tests instead of patching individual class names, because _CONFIG_MAP captures class references at module import time and patching `semolina.config.SnowflakeConfig` does not affect the dict entries
- Updated snowflake optional extra from `snowflake-connector-python>=4.3.0` to `adbc-poolhouse[snowflake]`
- Kept databricks extra as `databricks-sql-connector[pyarrow]>=4.2.5` with comment about Foundry-distributed ADBC driver

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mocking strategy for _CONFIG_MAP**
- **Found during:** Task 1 GREEN phase
- **Issue:** Plan specified patching `semolina.config.SnowflakeConfig` and `semolina.config.DatabricksConfig`, but _CONFIG_MAP captures class references at import time, so patching module-level names has no effect on the already-populated dict
- **Fix:** Created `mock_config_map` fixture that patches `semolina.config._CONFIG_MAP` directly with mock config classes
- **Files modified:** tests/unit/test_config.py
- **Verification:** All 15 tests pass
- **Committed in:** 0dd6596 (GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary correction to test strategy. No scope creep.

## Issues Encountered
- Pre-existing test failures in test_databricks_engine.py and test_snowflake_engine.py (require connector packages not installed) -- unrelated to this change, not addressed

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- config.py with pool_from_config() is ready
- Plan 27-02 can proceed: public API export in __init__.py, .semolina.toml.example update, registry.reset() close_pool integration

---
*Phase: 27-toml-configuration-real-pools*
*Completed: 2026-03-17*
