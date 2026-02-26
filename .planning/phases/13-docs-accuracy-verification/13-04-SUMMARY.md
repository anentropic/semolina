---
phase: 13-docs-accuracy-verification
plan: "04"
subsystem: testing
tags: [snowflake, credentials, pytest, fixtures, pydantic-settings]

# Dependency graph
requires:
  - phase: 08-integration-testing
    provides: SnowflakeCredentials.load() with CUBANO_ENV_FILE priority chain
  - phase: 11-ci-example-updates
    provides: cubano-jaffle-shop conftest.py with registry pattern
provides:
  - "cubano-jaffle-shop/tests/conftest.py snowflake_connection fixture using SnowflakeCredentials.load()"
  - "INT-01 and INT-06 satisfied in example project (not just library)"
affects: [docs, examples, jaffle-shop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use SnowflakeCredentials.load() in all Snowflake fixture bodies (not os.environ)"
    - "CredentialError exception as skip guard (not single env var check)"
    - "Iterator[None] return type on pytest generator fixtures (not None)"

key-files:
  created: []
  modified:
    - "cubano-jaffle-shop/tests/conftest.py"

key-decisions:
  - "jaffle-shop example project must mirror the library's credential loading pattern (CUBANO_ENV_FILE priority chain) for INT-06 to be fully satisfied end-to-end"
  - "Iterator[None] return type is correct for pytest generator fixtures (yield-based) — pre-existing -> None annotations were incorrect and fixed in same commit"

patterns-established:
  - "SnowflakeCredentials.load() + CredentialError: canonical pattern for all Snowflake fixture skip guards"
  - "Iterator[None] on yield-based pytest fixtures: correct basedpyright-strict compatible annotation"

requirements-completed: [INT-01, INT-06]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 13 Plan 04: Jaffle-Shop Credential Fixture Fix Summary

**jaffle-shop snowflake_connection fixture updated to use SnowflakeCredentials.load() with CredentialError skip guard and SecretStr.get_secret_value() — INT-06 now fully satisfied in example project**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T00:05:54Z
- **Completed:** 2026-02-22T00:07:54Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Replaced raw `os.environ.get()` / `os.environ[]` credential access in `snowflake_connection` fixture with `SnowflakeCredentials.load()`
- CredentialError exception now guards the skip path — respects the full CUBANO_ENV_FILE > .env > .cubano.toml priority chain
- `creds.password.get_secret_value()` correctly unwraps SecretStr before passing to SnowflakeEngine
- All 11 jaffle-shop mock tests pass with no regressions (2 XPASS — unexpectedly passing filter tests, which is positive)
- Incidentally fixed pre-existing `-> None` return type annotations on all 5 generator fixtures to `Iterator[None]` (basedpyright strict now reports 0 errors)

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace os.environ with SnowflakeCredentials.load() in snowflake_connection fixture** - `a234fe2` (feat)
2. **Task 2: Run jaffle-shop mock tests to confirm no breakage** - no file changes (verification-only task)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `cubano-jaffle-shop/tests/conftest.py` - Updated snowflake_connection fixture to use SnowflakeCredentials.load(); also fixed Iterator[None] return types on all generator fixtures

## Decisions Made
- `Iterator[None]` is the correct return type for yield-based pytest fixtures under basedpyright strict — the pre-existing `-> None` annotations on all 5 fixtures were technically wrong and produced 10 typecheck errors. Fixed in same commit as the credential change since the file was already being modified.
- The jaffle-shop example project must fully mirror the library's credential loading pattern for INT-06 to be end-to-end satisfied. Using raw `os.environ` bypassed the full CUBANO_ENV_FILE priority chain that Phase 8 established.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Fixed pre-existing Iterator[None] return types on all pytest generator fixtures**
- **Found during:** Task 1 (typecheck run after writing snowflake_connection fixture)
- **Issue:** All 5 generator fixtures had `-> None` return type, but they use `yield` making them generators. basedpyright strict reported 10 errors (2 per fixture). These errors pre-existed before this plan.
- **Fix:** Added `from collections.abc import Iterator` import and changed all 5 fixture return types from `-> None` to `-> Iterator[None]`
- **Files modified:** `cubano-jaffle-shop/tests/conftest.py`
- **Verification:** `uv run basedpyright cubano-jaffle-shop/tests/conftest.py` → 0 errors (was 10 before)
- **Committed in:** `a234fe2` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical type correctness)
**Impact on plan:** Auto-fix necessary for type correctness and was directly triggered by the typecheck requirement in Task 1. No scope creep.

## Issues Encountered
- The `uv run pytest cubano-jaffle-shop/tests/ -m mock -v` command (run from repo root) failed with `ModuleNotFoundError: No module named 'cubano_jaffle_shop'`. Required running from within the `cubano-jaffle-shop/` subdirectory: `cd cubano-jaffle-shop && uv run pytest tests/ -m mock -v`. This is a workspace path issue — tests must be run from the package directory.

## Next Phase Readiness
- Phase 13 is now complete (all 4 plans done). The v0.2 milestone is fully verified.
- All documentation accuracy issues found and fixed: filtering.md field operators, index.md API, warehouse-testing.md stale references, jaffle-shop credential pattern.
- No blockers.

## Self-Check: PASSED

- `cubano-jaffle-shop/tests/conftest.py` — FOUND
- `.planning/phases/13-docs-accuracy-verification/13-04-SUMMARY.md` — FOUND
- Commit `a234fe2` — FOUND (feat(13-04): replace os.environ with SnowflakeCredentials.load())
- Commit `3c187a6` — FOUND (docs(13-04): complete jaffle-shop credential fixture plan)

---
*Phase: 13-docs-accuracy-verification*
*Completed: 2026-02-22*
