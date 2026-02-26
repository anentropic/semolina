---
phase: 11-ci-example-updates
plan: 01
subsystem: ci-cd
tags: [pytest, github-actions, doctest, unit-testing, ci-reporting]

# Dependency graph
requires:
  - phase: 10.1-refactor-query-interface-to-model-centric
    provides: "Model-centric API locked in place; all doctests already use new API"
provides:
  - "CI split into separate unit test and doctest steps with independent reporting"
  - "Doctest failures now block CI build (separate section from unit test failures)"
  - "433 unit tests + 26 doctests = 459 total items validated in CI"
affects:
  - "11-02 (cubano-jaffle-shop API update)"
  - "Future CI enhancements and test infrastructure changes"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-step pytest pattern: unit tests (tests/) separate from doctests (src/)"
    - "GitHub Actions output sections naturally separate test type reporting"

key-files:
  created: []
  modified:
    - ".github/workflows/ci.yml"

key-decisions:
  - "Remove marker filter from unit test step (was `-m 'mock or warehouse'` - selected 0 tests, violated RULE 2)"
  - "Keep separate steps (vs. single command) to honor locked decision on distinct doctest failure reporting"
  - "No parallelization on doctest step (-n auto only on unit tests, doctests are fast)"

requirements-completed:
  - "DOCS-10"

# Metrics
duration: 8min
completed: 2026-02-17
---

# Phase 11 Plan 01: CI & Example Updates - Split pytest into Separate Test Steps Summary

**CI test job refactored with two separate pytest steps: unit tests (433 items) in dedicated step, doctests (26 items) with 6 skipped in separate step, each producing independent GitHub Actions output sections with distinct pass/fail counts**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-17T00:00:00Z
- **Completed:** 2026-02-17T00:08:00Z
- **Tasks:** 2 completed
- **Files modified:** 1

## Accomplishments

- Split single merged pytest command into two separate CI steps honoring locked decision for separate doctest failure reporting
- Removed broken marker filter that selected 0 tests (RULE 2 auto-fix)
- Each step now produces independent GitHub Actions output section with distinct pytest summary line
- Unit tests: 433 passed (all tests from tests/ directory)
- Doctests: 20 passed, 6 skipped (all from src/ with --doctest-modules)
- Total validated items: 459 (433 + 26)

## Task Commits

Each task was committed atomically:

1. **Task 1: Split the single pytest step into two separate steps in ci.yml** - `3e4bdb3` (feat)
2. **Task 2: Verify both steps produce correct results locally** - Verification completed (no code changes)

**Plan metadata:** Committed with task 1

## Files Created/Modified

- `.github/workflows/ci.yml` - Split "Run pytest (Cubano + doctests)" into two steps: "Run unit tests" and "Run doctests"

## Decisions Made

1. **Remove marker filter from unit test step** - The plan specified keeping `-m "mock or warehouse"` but this filter selected 0 tests (no tests have these markers - all are marked `@pytest.mark.unit` or unmarked). Following CONTEXT and RESEARCH guidance, removed the broken filter to actually validate tests. Aligned with RULE 2: auto-fix critical functionality.

2. **Keep separate steps (not single command)** - Honored the locked decision that "Doctest failures reported in a separate section from unit test failures" by keeping two steps. GitHub Actions naturally produces separate output sections per step.

3. **No `-n auto` on doctest step** - Unit tests run with parallel workers (`-n auto`) for speed. Doctests run sequentially (no `-n auto`) - they are fast (0.15s) and don't need parallelization.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Removed broken marker filter from unit test step**
- **Found during:** Task 1 (Reading current CI and understanding implementation)
- **Issue:** Plan specified keeping `-m "mock or warehouse"` filter, but this filter selects 0 tests. Tests are marked with `@pytest.mark.unit` or no marker, not `@pytest.mark.mock` or `@pytest.mark.warehouse`. The filter would result in 0 unit tests being run - a critical CI failure.
- **Context:** CONTEXT.md and RESEARCH.md both explicitly recommend "removing `-m "mock or warehouse"` filter". The plan contradicted its own referenced context documents.
- **Fix:** Changed unit test step from `uv run pytest tests/ -m "mock or warehouse" -n auto -v` to `uv run pytest tests/ -n auto -v`. This selects all 433 unit tests as intended.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** Tested locally: `uv run pytest tests/ -n auto -v` → 433 passed in 2.93s
- **Committed in:** `3e4bdb3`

---

**Total deviations:** 1 auto-fixed (Rule 2 - critical functionality)
**Impact on plan:** Auto-fix was essential for correctness. Without it, CI would run 0 tests. The fix aligns with CONTEXT and RESEARCH guidance which explicitly recommended removing the filter. No scope creep - only fixed the broken implementation.

## Issues Encountered

None during execution. Both test commands validated locally and pass quality gates (typecheck: 0 errors, format check: all formatted).

## Verification Results

- **Unit tests:** 433 passed in 2.93s (parallel execution with -n auto)
- **Doctests:** 20 passed, 6 skipped in 0.15s (from src/ with --doctest-modules)
- **Typecheck:** basedpyright 0 errors, 0 warnings
- **Format:** ruff format --check passed
- **YAML:** ci.yml structure valid, no merged pytest commands remain
- **Artifact verification:**
  - ✓ Contains step: `uv run pytest tests/ -n auto -v`
  - ✓ Contains step: `uv run pytest src/ --doctest-modules -v`
  - ✓ Does NOT contain: `pytest tests/ src/` (merged form eliminated)
  - ✓ Two separate output sections in CI

## Next Phase Readiness

- CI now validates all 459 test items separately (433 unit + 26 doctests)
- Doctest failures will be visibly distinguished in CI output (separate section)
- Ready for Phase 11-02: Update cubano-jaffle-shop example to use Model-centric API
- The separate pytest steps also prepare for future enhancements (e.g., separate test timing, targeted retries, parallel doctest runs)

---

*Phase: 11-ci-example-updates*
*Plan: 11-01*
*Completed: 2026-02-17*
