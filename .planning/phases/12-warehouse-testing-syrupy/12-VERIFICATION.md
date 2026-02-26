---
phase: 12-warehouse-testing-syrupy
verified: 2026-02-17T21:00:00Z
status: human_needed
score: 15/15 must-haves verified
re_verification: false
human_verification:
  - test: "Run pytest --snapshot-update tests/test_snapshot_queries.py with real Snowflake credentials and inspect tests/__snapshots__/test_snapshot_queries.ambr for test_filtered_by_dimension"
    expected: "test_filtered_by_dimension snapshot contains only 2 rows (US country rows: revenue=500 East, revenue=1000 West), not all 5 rows"
    why_human: "MockEngine does not implement WHERE clause filtering — it returns all loaded data regardless of .where() calls. The committed baseline was generated using MockEngine (bootstrap approach), so test_filtered_by_dimension[snowflake_engine] and [databricks_engine] both contain all 5 rows. A real warehouse recording would return only 2 US rows. The test passes in CI (MockEngine replays MockEngine snapshot) but does not validate SQL WHERE semantics against a real warehouse."
---

# Phase 12: Warehouse Testing (Syrupy) Verification Report

**Phase Goal:** Enable real warehouse testing in CI without cost using snapshot-based recording/replay
**Verified:** 2026-02-17T21:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | syrupy is installed and available in the dev dependency group | VERIFIED | `pyproject.toml` line 48: `"syrupy>=5.1.0"`, syrupy 5.1.0 reported by pytest session header |
| 2 | snapshot fixture in tests/conftest.py applies defensive credential scrubbing | VERIFIED | Lines 313-336 of `tests/conftest.py`: `snapshot.with_defaults(matcher=path_value(...))` with password/token/secret regex mappings and `_redact_credential` replacer |
| 3 | SNAPSHOT_TEST_DATA constant defined in tests/conftest.py with 5-row synthetic dataset | VERIFIED | Lines 299-305 of `tests/conftest.py`: 5 rows with integer revenue/cost, country, region fields |
| 4 | snowflake_engine fixture uses SnowflakeEngine when --snapshot-update passed, MockEngine otherwise | VERIFIED | Lines 339-379: `request.config.getoption("--snapshot-update", default=False)` gates real vs MockEngine path |
| 5 | databricks_engine fixture uses DatabricksEngine when --snapshot-update passed, MockEngine otherwise | VERIFIED | Lines 382-421: same pattern as snowflake_engine; loads SNAPSHOT_TEST_DATA into MockEngine in replay mode |
| 6 | backend_engine is a parametrized fixture with params=['snowflake_engine', 'databricks_engine'] | VERIFIED | Lines 424-438: `@pytest.fixture(params=["snowflake_engine", "databricks_engine"])`, `yield request.getfixturevalue(request.param)` |
| 7 | All three engine fixtures register/unregister engines with cubano | VERIFIED | Lines 377-379, 419-421: `cubano.register("test", engine)` before yield, `cubano.unregister("test")` after |
| 8 | 6 snapshot test functions each accepting backend_engine and snapshot | VERIFIED | `tests/test_snapshot_queries.py` lines 40-119: 6 functions, each `def test_X(backend_engine: Any, snapshot: SnapshotAssertion) -> None` |
| 9 | pytest creates 12 test IDs (6 functions x 2 backends) | VERIFIED | `pytest --collect` and live run confirm: 12 items collected, 12 passed |
| 10 | .ambr file has 12 snapshot entries with [snowflake_engine] and [databricks_engine] tags | VERIFIED | `grep "# name:"` returns 12 lines; entries tagged `[snowflake_engine]` and `[databricks_engine]` for all 6 test functions |
| 11 | All 12 snapshot test variants pass in replay mode without warehouse credentials | VERIFIED | `pytest tests/test_snapshot_queries.py -v --snapshot-warn-unused` → 12 passed in 0.03s |
| 12 | CI unit test step passes --snapshot-warn-unused | VERIFIED | `.github/workflows/ci.yml` line 110: `uv run pytest tests/ -n auto -v --snapshot-warn-unused` |
| 13 | docs/guides/warehouse-testing.md exists with ≥80 lines covering all 9 required sections | VERIFIED | 301 lines; all 9 sections present: Overview, Quick Start, Recording Workflow, Replay Mode, Re-recording, Stale Cleanup, Best Practices, Snapshot File Format, Troubleshooting |
| 14 | mkdocs.yml nav includes warehouse-testing.md under guides section | VERIFIED | `mkdocs.yml` contains `- Warehouse Testing: guides/warehouse-testing.md` |
| 15 | uv run pytest tests/ passes existing tests with no phase-12-introduced regressions | VERIFIED | Phase 12 files pass clean; 22 pre-existing failures in `test_snowflake_engine.py` (last modified in phase 5 commit 9f5b66e) pre-date phase 12 entirely; ruff errors are in `dbt-jaffle-shop/.github/` path not touched by phase 12 |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | syrupy>=5.1.0 in dev deps | VERIFIED | Line 48: `"syrupy>=5.1.0"`, filterwarnings for syrupy at line 98 |
| `tests/conftest.py` | SNAPSHOT_TEST_DATA, snapshot fixture, snowflake_engine, databricks_engine, backend_engine | VERIFIED | All 5 additions present, substantive, and type-annotated; 439 lines total |
| `tests/test_snapshot_queries.py` | 6 DRY snapshot test functions, SnapshotSales model, ≥60 lines | VERIFIED | 120 lines, 6 test functions, SnapshotSales model at lines 26-37 |
| `tests/__snapshots__/test_snapshot_queries.ambr` | 12 snapshot entries with backend tags | VERIFIED | 410 lines, 12 `# name:` entries with `[snowflake_engine]` and `[databricks_engine]` suffixes |
| `.github/workflows/ci.yml` | --snapshot-warn-unused in unit test step | VERIFIED | Line 110 confirmed |
| `docs/guides/warehouse-testing.md` | Complete guide ≥80 lines with 9 sections | VERIFIED | 301 lines, all 9 sections present |
| `mkdocs.yml` | Navigation entry for warehouse-testing | VERIFIED | `- Warehouse Testing: guides/warehouse-testing.md` present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/conftest.py snapshot fixture` | syrupy SnapshotAssertion | `snapshot.with_defaults(matcher=...)` | VERIFIED | `with_defaults` call at line 325, `path_value` imported inline from `syrupy.matchers` |
| `tests/conftest.py snowflake_engine / databricks_engine` | `request.config.getoption` | --snapshot-update flag detection | VERIFIED | `getoption("--snapshot-update", default=False)` at lines 352, 395 |
| `tests/conftest.py backend_engine` | snowflake_engine, databricks_engine fixtures | `request.getfixturevalue` | VERIFIED | `yield request.getfixturevalue(request.param)` at line 438 |
| `tests/test_snapshot_queries.py` | `tests/conftest.py:backend_engine` | fixture parameter in test functions | VERIFIED | All 6 functions: `def test_X(backend_engine: Any, snapshot: SnapshotAssertion)` |
| `tests/test_snapshot_queries.py` | `tests/__snapshots__/test_snapshot_queries.ambr` | `assert rows == snapshot` | VERIFIED | `assert rows == snapshot` at lines 50, 63, 77, 91, 104, 119 |
| `.github/workflows/ci.yml Run unit tests` | `tests/__snapshots__/test_snapshot_queries.ambr` | pytest reads committed .ambr files | VERIFIED | `--snapshot-warn-unused` present; snapshot tests run as part of `pytest tests/` |
| `docs/guides/warehouse-testing.md` | `tests/test_snapshot_queries.py` patterns | code examples use backend_engine | VERIFIED | `backend_engine` referenced 5 times in guide; code examples match actual test pattern |
| `mkdocs.yml` | `docs/guides/warehouse-testing.md` | nav entry | VERIFIED | `- Warehouse Testing: guides/warehouse-testing.md` in mkdocs nav |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| TEST-VCR | 12-01, 12-02, 12-03, 12-04 | Record/replay warehouse queries with snapshot-based testing to enable real warehouse tests in CI without cost | SATISFIED | syrupy snapshot infrastructure fully implemented; 12 tests pass in MockEngine replay; CI runs snapshots without warehouse credentials; --snapshot-warn-unused catches stale snapshots; developer guide documents the full workflow |

### Anti-Patterns Found

No anti-patterns detected in phase 12 files. No TODO/FIXME/placeholder comments, no empty implementations, no stub handlers.

**Note on pre-existing issues (not introduced by phase 12):**
- `tests/test_snowflake_engine.py`: 22 test failures and 42 basedpyright errors — last modified in phase 5 (commit 9f5b66e), not touched by phase 12
- `dbt-jaffle-shop/.github/workflows/scripts/dbt_cloud_run_job.py`: 8 ruff errors — separate subproject, not touched by phase 12

### Human Verification Required

#### 1. Snapshot data validity for filtered tests

**Test:** Set Snowflake credentials (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`) and run:
```bash
uv run pytest tests/test_snapshot_queries.py --snapshot-update -v
git diff tests/__snapshots__/test_snapshot_queries.ambr
```

**Expected:** The `test_filtered_by_dimension[snowflake_engine]` snapshot should contain only 2 rows (country="US") after recording against a real Snowflake warehouse, not the 5 rows currently committed.

**Why human:** The committed `.ambr` baseline was generated using the MockEngine bootstrap approach (temporarily forcing `is_recording=False`). MockEngine does not implement WHERE clause filtering — `engine.load("snapshot_sales_view", SNAPSHOT_TEST_DATA)` followed by `.where(country == "US")` returns all 5 rows because MockEngine's SQL execution does not filter. The committed snapshot captures MockEngine's unfiltered output, so `test_filtered_by_dimension` currently validates that MockEngine returns all rows (a tautology), not that the warehouse correctly filters by country. This is the expected bootstrap tradeoff but should be resolved by recording with real credentials before shipping the test suite as a genuine compatibility check.

**Severity:** The test passes, the infrastructure is correct, and the intent is sound — but the snapshot for the filtered test does not currently validate SQL WHERE semantics. This matters most when the goal is "real warehouse testing."

---

## Gaps Summary

No automated gaps found. All 15 observable truths verified. All artifacts exist, are substantive, and are properly wired.

The single human verification item is not a blocker for the snapshot infrastructure goal itself — recording/replay works correctly. It is a data quality concern specific to the filtered test snapshot that can be resolved when real warehouse credentials are available.

---

_Verified: 2026-02-17T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
