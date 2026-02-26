---
phase: quick-7
plan: 1
subsystem: testing
tags: [snowflake, credentials, pydantic-settings, role-override, syrupy]

requires:
  - phase: quick-5
    provides: credential loading with CUBANO_ENV_FILE priority chain

provides:
  - SnowflakeCredentials.load(role=...) for role override at call time
  - snowflake_engine fixture passes role to SnowflakeEngine (was silently dropped)
  - Unit tests for role override and None-preservation

affects: [testing, credentials, conftest, snapshot-testing]

tech-stack:
  added: []
  patterns:
    - "model_copy(update={...}) for immutable override of pydantic model fields"
    - "DRY inner helper _apply_role() to share override logic across multiple loading paths"

key-files:
  created: []
  modified:
    - src/cubano/testing/credentials.py
    - tests/conftest.py
    - tests/test_credentials.py

key-decisions:
  - "Inner _apply_role() helper defined inside load() captures role from closure, covering both pydantic-settings and config-file loading paths without duplication"
  - "model_copy(update={'role': role}) used for immutable override - preserves all other credential fields"
  - "role=creds.role passes safely when creds.role is None (snowflake.connector accepts role=None as no-op)"

patterns-established:
  - "Role override at load-time: load(role='ANALYST') pattern for callers needing specific Snowflake roles"

requirements-completed: []

duration: 3min
completed: 2026-02-19
---

# Quick Task 7: SnowflakeCredentials.load() role override Summary

**Added role parameter to SnowflakeCredentials.load() using model_copy override, and fixed snowflake_engine fixture to pass role=creds.role to SnowflakeEngine**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T17:39:21Z
- **Completed:** 2026-02-19T17:42:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `SnowflakeCredentials.load(role="MY_ROLE")` now returns credentials with `role == "MY_ROLE"` regardless of SNOWFLAKE_ROLE env var or config file contents
- `snowflake_engine` snapshot fixture now passes `role=creds.role` to `SnowflakeEngine` (previously role from credentials was silently dropped during snapshot recording)
- Two new unit tests cover role override behaviour and backward compatibility (None preservation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add role parameter to SnowflakeCredentials.load()** - `a2547b8` (feat)
2. **Task 2: Fix snowflake_engine fixture and add unit tests** - `61d9a58` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `src/cubano/testing/credentials.py` - Added `role: str | None = None` param to `load()`, inner `_apply_role()` helper, model_copy override at both return paths
- `tests/conftest.py` - Added `role=creds.role` to `SnowflakeEngine(...)` call in `snowflake_engine` fixture
- `tests/test_credentials.py` - Added `test_snowflake_load_role_override` and `test_snowflake_load_no_role_preserves_none`

## Decisions Made

- Inner `_apply_role()` helper defined inside `load()` captures `role` from the closure, covering both the pydantic-settings path and config-file path without code duplication
- `model_copy(update={"role": role})` used for the override — immutable, preserves all other credential fields
- `role=creds.role` is safe even when `creds.role is None` because `snowflake.connector.connect()` accepts `role=None` silently (equivalent to no role specified)
- `DatabricksCredentials.load()` left unchanged — Databricks has no equivalent role concept in this codebase

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `uv run --extra dev pytest` failed (no `dev` extra defined in pyproject.toml). Used `uv run pytest` instead — tests ran correctly.
- Pre-existing test failures in `test_snowflake_engine.py` and `test_databricks_engine.py` (22 tests, caused by optional `snowflake-connector-python` and `databricks-sql-connector` packages not installed in the dev environment). These are unrelated to this task's changes.

## Next Phase Readiness

- Role override is available for any test or fixture that needs to specify a specific Snowflake role at load time
- `snowflake_engine` snapshot fixture now correctly propagates role from credentials during `--snapshot-update` recording

---
*Phase: quick-7*
*Completed: 2026-02-19*

## Self-Check: PASSED

- `src/cubano/testing/credentials.py` - FOUND
- `tests/conftest.py` - FOUND
- `tests/test_credentials.py` - FOUND
- Commit `a2547b8` - FOUND
- Commit `61d9a58` - FOUND
