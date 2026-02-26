---
phase: 11-ci-example-updates
verified: 2026-02-22T00:56:30Z
status: VERIFIED
score: 4/4 must-haves verified
re_verification: true
---

# Phase 11 CI & Example Updates Verification Report

**Phase Goal:** Fix CI workflows to validate all 459 tests including 26 doctests (removing `-m "mock or warehouse"` filter), and update cubano-jaffle-shop example to use Model-centric API (Model.query(), .execute(), no deprecated Query). Infrastructure + example code update, not a new feature.
**Verified:** 2026-02-22T00:56:30Z
**Status:** VERIFIED
**Re-verification:** Yes — verified in Phase 13 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | CI test command runs unit tests (`pytest tests/`) separately from doctests (`pytest src/ --doctest-modules`) | VERIFIED | `.github/workflows/ci.yml` lines 109-110: `uv run pytest tests/ -n auto -v --snapshot-warn-unused` (step name "Run unit tests"); lines 112-113: `uv run pytest src/ --doctest-modules -v` (step name "Run doctests"). No merged `pytest tests/ src/` form exists. Two independent GitHub Actions steps with separate output sections. |
| 2 | cubano-jaffle-shop example uses Model-centric API (Model.query(), .execute(), no deprecated Query) | VERIFIED | `cubano-jaffle-shop/tests/test_mock_queries.py`: 13 instances of `Model.query()` pattern (Orders.query(), Customers.query(), Products.query()), zero `Query()` constructor calls, zero `engine.execute(query)` calls. `cubano-jaffle-shop/tests/test_warehouse_queries.py`: 15 instances of `Model.query()` pattern, same zero-old-API verification. `conftest.py` uses `cubano.register("default", engine)` / `cubano.unregister("default")` registry pattern. |
| 3 | All tests pass including doctest validation | VERIFIED | Local run (2026-02-22): `uv run pytest src/ --doctest-modules -v` → **20 passed, 6 skipped in 0.19s**. `uv run pytest tests/ -n auto -v --snapshot-warn-unused` → **445 passed in 3.28s**. The 6 skipped doctests are warehouse-dependent (operator overloads that require engine registration). The 445 unit tests include all mock, snapshot, and engine tests. |
| 4 | DOCS-10 requirement complete (separate CI step for doctest enforcement) | VERIFIED | `.github/workflows/ci.yml` line 112-113 contains dedicated "Run doctests" step: `uv run pytest src/ --doctest-modules -v`. This step is independent from the unit test step, produces its own GitHub Actions output section, and doctest failures will fail CI independently from unit test failures — honoring the locked decision that "Doctest failures reported in a separate section from unit test failures". |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/ci.yml` | Two separate pytest steps: unit tests and doctests | VERIFIED | Lines 109-113: "Run unit tests" (`pytest tests/ -n auto -v --snapshot-warn-unused`) and "Run doctests" (`pytest src/ --doctest-modules -v`) — two independent CI steps |
| `cubano-jaffle-shop/tests/test_mock_queries.py` | Model.query() API, no deprecated Query | VERIFIED | 13 `Model.query()` calls; grep for `Query()` returns 0 matches |
| `cubano-jaffle-shop/tests/test_warehouse_queries.py` | Model.query() API, no deprecated Query | VERIFIED | 15 `Model.query()` calls; grep for `Query()` returns 0 matches |
| `cubano-jaffle-shop/tests/conftest.py` | Registry pattern (cubano.register/unregister) | VERIFIED | Uses `cubano.register("default", engine)` / `cubano.unregister("default")` per fixture; fixtures yield for cleanup |
| `11-01-PLAN.md` | Plan source document | VERIFIED | `.planning/phases/11-ci-example-updates/11-01-PLAN.md` exists |
| `11-02-PLAN.md` | Plan source document | VERIFIED | `.planning/phases/11-ci-example-updates/11-02-PLAN.md` exists |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `.github/workflows/ci.yml` "Run doctests" step | `src/` doctest modules | `uv run pytest src/ --doctest-modules -v` (line 113) | VERIFIED | 20 doctests collected and executed; 6 skipped (warehouse-dependent) |
| `.github/workflows/ci.yml` "Run unit tests" step | `tests/` directory | `uv run pytest tests/ -n auto -v --snapshot-warn-unused` (line 110) | VERIFIED | 445 tests collected and pass; no marker filter (removed broken `-m "mock or warehouse"`) |
| `cubano-jaffle-shop/tests/test_mock_queries.py` | Model-centric API | `Orders.query()`, `Customers.query()`, `Products.query()` calls | VERIFIED | 13 instances of `.query()` pattern; zero old `Query()` constructors |
| `cubano-jaffle-shop/tests/conftest.py` | cubano registry | `cubano.register("default", engine)` / `cubano.unregister("default")` | VERIFIED | Registry pattern used for all engine lifecycle management |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| DOCS-10 | 11-01 | Separate CI step for doctest enforcement — doctest failures reported in separate section from unit test failures | SATISFIED | `.github/workflows/ci.yml` line 112-113: dedicated "Run doctests" step `uv run pytest src/ --doctest-modules -v` runs independently from "Run unit tests" step, producing separate GitHub Actions output sections. Doctests: 20 passed, 6 skipped (expected). Doctest failures will block CI separately from unit test failures. |

### Gaps Summary

No automated gaps found. All 4 observable truths verified. All artifacts exist, are substantive, and are properly wired.

---

_Verified: 2026-02-22T00:56:30Z_
_Verifier: Claude (gsd-executor, Phase 13 gap closure)_
