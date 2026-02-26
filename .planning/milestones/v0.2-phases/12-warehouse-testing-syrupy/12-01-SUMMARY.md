---
phase: 12-warehouse-testing-syrupy
plan: 01
subsystem: testing
tags: [syrupy, snapshot, pytest, fixtures, warehouse]

# Dependency graph
requires:
  - phase: 08-integration-testing
    provides: "MockEngine, credential loaders, warehouse test fixtures"
provides:
  - "syrupy snapshot testing dependency"
  - "SNAPSHOT_TEST_DATA constant (5-row synthetic dataset)"
  - "snapshot fixture with credential scrubbing"
  - "snowflake_engine fixture (MockEngine/SnowflakeEngine)"
  - "databricks_engine fixture (MockEngine/DatabricksEngine)"
  - "backend_engine parametrized fixture (both backends)"
affects: [12-02, 12-03, 12-04]

# Tech tracking
tech-stack:
  added: [syrupy>=5.1.0]
  patterns: [snapshot-update flag detection, parametrized backend fixture, lazy engine import]

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - tests/conftest.py

key-decisions:
  - "SnapshotAssertion imported from syrupy.assertion (not syrupy) for basedpyright strict compatibility"
  - "Credential scrubbing replacer extracted to named function _redact_credential to avoid basedpyright lambda parameter issue"
  - "Engine imports aliased with underscore prefix inside recording branches to avoid shadowing TYPE_CHECKING imports"
  - "Generator and SnapshotAssertion placed in TYPE_CHECKING block per ruff TC003"

patterns-established:
  - "Snapshot fixture override: snapshot(snapshot) wraps syrupy default with credential scrubbing"
  - "Backend fixture pattern: --snapshot-update detects recording mode, MockEngine used otherwise"
  - "Parametrized backend_engine: request.getfixturevalue(request.param) delegates to named fixtures"

requirements-completed: [TEST-VCR]

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 12 Plan 01: Snapshot Infrastructure Summary

**Syrupy snapshot testing with parametrized backend_engine fixture, credential scrubbing, and --snapshot-update mode switching**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17T20:11:17Z
- **Completed:** 2026-02-17T20:15:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added syrupy>=5.1.0 to dev dependencies with filterwarnings config for deprecation suppression
- Built SNAPSHOT_TEST_DATA constant with 5 rows of integer-valued synthetic data (avoids Decimal drift)
- Implemented snapshot fixture override applying path_value credential scrubbing (password/token/secret redaction)
- Created snowflake_engine and databricks_engine fixtures that auto-detect --snapshot-update for record vs replay
- Created backend_engine parametrized fixture that drives both backends from a single test function via request.getfixturevalue

## Task Commits

Each task was committed atomically:

1. **Task 1: Add syrupy to dev dependencies** - `beed3ea` (chore)
2. **Task 2: Add snapshot infrastructure to tests/conftest.py** - `f23f5b7` (feat)

## Files Created/Modified

- `pyproject.toml` - Added syrupy>=5.1.0 to dev deps, filterwarnings for syrupy deprecation warnings
- `uv.lock` - Updated with syrupy 5.1.0 resolution
- `tests/conftest.py` - Added from __future__ import annotations, TYPE_CHECKING imports, SNAPSHOT_TEST_DATA, snapshot override, snowflake_engine, databricks_engine, backend_engine fixtures

## Decisions Made

- **SnapshotAssertion import path:** Used `syrupy.assertion` instead of `syrupy` top-level because basedpyright strict mode flags `syrupy.SnapshotAssertion` as not exported (reportPrivateImportUsage).
- **Named replacer function:** Extracted `_redact_credential` helper instead of inline lambda because basedpyright strict mode flagged lambda parameter `match` as "possibly unbound" (soft keyword conflict in Python 3.10+).
- **Aliased engine imports:** Inside recording branches, engine classes imported as `_SnowflakeEngine`, `_DatabricksEngine` etc. to avoid shadowing the TYPE_CHECKING-guarded imports used for annotations.
- **TYPE_CHECKING block:** `Generator`, `SnapshotAssertion`, `SnowflakeEngine`, `DatabricksEngine` all placed under `TYPE_CHECKING` per ruff TC003 rule, since `from __future__ import annotations` makes all annotations strings at runtime.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SnapshotAssertion import path**
- **Found during:** Task 2
- **Issue:** Plan specified `from syrupy import SnapshotAssertion` but basedpyright strict reports it as not exported from `syrupy` top-level (reportPrivateImportUsage)
- **Fix:** Changed to `from syrupy.assertion import SnapshotAssertion`
- **Files modified:** tests/conftest.py
- **Verification:** basedpyright passes with 0 errors on conftest.py
- **Committed in:** f23f5b7

**2. [Rule 1 - Bug] Replaced lambda replacer with named function**
- **Found during:** Task 2
- **Issue:** basedpyright strict mode flagged `lambda data, match:` parameter `match` as "possibly unbound" due to soft keyword status in Python 3.10+
- **Fix:** Extracted to named function `_redact_credential(_data, _matched)` avoiding the keyword conflict
- **Files modified:** tests/conftest.py
- **Verification:** basedpyright passes with 0 errors on conftest.py
- **Committed in:** f23f5b7

**3. [Rule 1 - Bug] Fixed ruff TC003 and I001 lint errors**
- **Found during:** Task 2
- **Issue:** `Generator` import at runtime triggered TC003, TYPE_CHECKING block imports not sorted per I001
- **Fix:** Moved Generator to TYPE_CHECKING block, ran ruff --fix for import sorting
- **Files modified:** tests/conftest.py
- **Verification:** ruff check passes with 0 errors on conftest.py
- **Committed in:** f23f5b7

---

**Total deviations:** 3 auto-fixed (3 bugs - basedpyright strict mode and ruff lint compliance)
**Impact on plan:** All fixes necessary for quality gate compliance. No scope creep.

## Issues Encountered

None - all issues were standard basedpyright strict mode / ruff compliance fixes resolved during Task 2.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Snapshot infrastructure ready for Plan 02 (credential model for snapshot recording)
- backend_engine fixture available for Plan 03/04 snapshot tests
- SNAPSHOT_TEST_DATA constant ready for use in snapshot test files
- No env vars needed for replay mode (CI-safe by default)

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 12-warehouse-testing-syrupy*
*Completed: 2026-02-17*
