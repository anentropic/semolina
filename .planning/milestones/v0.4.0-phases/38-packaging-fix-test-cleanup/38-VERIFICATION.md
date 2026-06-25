---
phase: 38-packaging-fix-test-cleanup
verified: 2026-05-01T22:00:00Z
status: resolved
score: 4/4 roadmap success criteria verified
resolution:
  date: 2026-05-07
  by: duckdb-semantic-views v0.8.0 release
  notes: >
    v0.8.0 fixed the catalog resolution bug. A new constraint emerged
    (semantic_view() expansion runs on a separate read connection that only
    sees committed state), addressed in test fixtures by calling commit()
    after CREATE SEMANTIC VIEW. All 20 xfail markers removed; 924 unit
    tests pass. Docs updated with min-version note and the commit-after-DDL
    gotcha at docs/src/how-to/backends/duckdb.rst.
gaps_at_initial_verification:
  - truth: "All previously-xfailed semantic_view() ADBC tests pass without xfail markers"
    status: failed
    reason: >
      duckdb-semantic-views upstream did not release the catalog resolution fix in time.
      The installed extension shows commit hash 6789337, not the expected 0.7.1 release.
      The 20 xfail markers were restored after the test run confirmed failures.
      test_query.py still has the _xfail_adbc variable definition (lines 115-119) and
      all 16 @_xfail_adbc decorator lines (at lines 598, 611, 623, 634, 643, 684, 702,
      735, 758, 797, 1022, 1029, 1041, 1051, 1067, 1105).
      test_pool.py still has 4 @pytest.mark.xfail(...) decorator blocks (lines 220, 235,
      290, 324) and the original docstring Note block describing the catalog bug.
      test_query.py docstring (line 28) still reads "Tests requiring semantic_view()
      through ADBC are xfail (catalog resolution bug)" rather than the planned update.
    artifacts:
      - path: "tests/unit/test_query.py"
        issue: "_xfail_adbc variable and 16 @_xfail_adbc decorators still present; docstring not updated"
      - path: "tests/unit/test_pool.py"
        issue: "4 @pytest.mark.xfail blocks still present; docstring Note block describes active bug"
    missing:
      - "Remove _xfail_adbc variable definition from test_query.py lines 115-119 once upstream fixes catalog resolution"
      - "Remove all 16 @_xfail_adbc decorator lines from test_query.py once upstream fixes catalog resolution"
      - "Remove all 4 @pytest.mark.xfail blocks from test_pool.py once upstream fixes catalog resolution"
      - "Update test_query.py docstring line 28 to reflect fixed upstream"
      - "Update test_pool.py docstring Note block (lines 14-21) to reflect fixed upstream"
      - "Monitor duckdb-semantic-views for 0.7.1 release and re-run this phase when available"
---

# Phase 38: Packaging Fix + Test Cleanup Verification Report

**Phase Goal:** Restore missing duckdb pip extra, fix misplaced sphinx-autobuild dep, and remove xfail markers now that duckdb-semantic-views 0.7.1 fixes the catalog resolution bug
**Verified:** 2026-05-01T22:00:00Z
**Status:** resolved (2026-05-07 — see Resolution below)
**Re-verification:** No — initial verification

## Resolution (2026-05-07)

duckdb-semantic-views v0.8.0 fixed the catalog resolution bug. v0.8.0 also introduced a separate constraint — `semantic_view()` expansion runs on a separate read connection that only sees committed state — which required adding `commit()` after `CREATE SEMANTIC VIEW` in the test fixtures.

All 20 xfail markers removed; 924 unit tests pass. Min-version requirement and the commit-after-DDL constraint documented at `docs/src/how-to/backends/duckdb.rst`.

## Important Context (initial verification, superseded by Resolution above)

After Task 2 execution, it was discovered that the duckdb-semantic-views extension does NOT yet provide the catalog resolution fix. The installed version shows commit hash 6789337 rather than the expected 0.7.1 release tag. The 20 xfail markers were restored to prevent test suite failures. The SUMMARY.md claims they were removed, but the actual codebase still contains all xfail markers.

## Goal Achievement

### Roadmap Success Criteria (Observable Truths)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pip install semolina[duckdb]` installs duckdb>=1.5.0 and pyarrow>=17.0.0 | VERIFIED | pyproject.toml lines 38-41: `duckdb = ["duckdb>=1.5.0", "pyarrow>=17.0.0"]`; uv.lock pins duckdb 1.5.2 |
| 2 | `pip install semolina[all]` includes duckdb extra | VERIFIED | pyproject.toml line 43: `"semolina[snowflake,databricks,duckdb]"` |
| 3 | `sphinx-autobuild` is in `[dependency-groups] docs`, not `[project.dependencies]` | VERIFIED | Only appears at pyproject.toml line 68 inside `[dependency-groups] docs`; `[project] dependencies` (lines 10-15) contains only adbc-poolhouse, typer, rich, jinja2 |
| 4 | All previously-xfailed semantic_view() ADBC tests pass without xfail markers | VERIFIED (2026-05-07) | duckdb-semantic-views v0.8.0 fixed the catalog resolution bug. All 20 xfail markers removed across test_pool.py, test_query.py, test_duckdb_engine.py. Test fixtures updated to commit() after CREATE SEMANTIC VIEW (v0.8.0 constraint). 924 unit tests pass. |

**Score:** 4/4 roadmap success criteria verified

### Additional PLAN must_haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 5 | Project description includes DuckDB | VERIFIED | pyproject.toml line 4: `"(Snowflake, Databricks, DuckDB)"` |
| 6 | All previously-xfailed tests pass without xfail markers | VERIFIED (2026-05-07) | Same as SC4 — resolved by upstream v0.8.0. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Correct packaging with duckdb extra, fixed deps, updated description | VERIFIED | duckdb extra present, sphinx-autobuild moved to docs group, description updated |
| `tests/unit/test_query.py` | Clean test file without xfail markers | FAILED | _xfail_adbc variable (lines 115-119) and 16 decorator lines still present |
| `tests/unit/test_pool.py` | Clean test file without xfail markers | FAILED | 4 @pytest.mark.xfail blocks still present at lines 220, 235, 290, 324 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml [project.optional-dependencies] duckdb` | `uv.lock` | uv lock regeneration | VERIFIED | uv.lock line 590: `name = "duckdb"`, version 1.5.2; line 1769 shows `marker = "extra == 'duckdb'"` with `specifier = ">=1.5.0"` |
| `pyproject.toml [project.optional-dependencies] all` | duckdb extra | `semolina[snowflake,databricks,duckdb]` | VERIFIED | pyproject.toml line 43 matches expected pattern exactly |

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies configuration and test files only, no dynamic data rendering.

### Behavioral Spot-Checks

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| duckdb extra declared with correct pins | `pyproject.toml` lines 38-41 | `duckdb>=1.5.0` and `pyarrow>=17.0.0` present | PASS |
| all extra references duckdb | `pyproject.toml` line 43 | `semolina[snowflake,databricks,duckdb]` | PASS |
| sphinx-autobuild absent from runtime deps | `pyproject.toml` lines 10-15 | Not present | PASS |
| sphinx-autobuild present in docs group | `pyproject.toml` lines 62-69 | Line 68 has `sphinx-autobuild[dev]>=2025.8.25` | PASS |
| xfail markers removed from test_query.py | grep for xfail in test_query.py | 16 matches found — markers still present | FAIL |
| xfail markers removed from test_pool.py | grep for xfail in test_pool.py | 4 matches found — markers still present | FAIL |
| test_query.py docstring updated | line 28 content | Still reads "Tests requiring semantic_view() through ADBC are xfail (catalog resolution bug)" | FAIL |
| test_pool.py docstring updated | lines 14-21 content | Note block still describes active catalog resolution bug | FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DUCK-01 | 38-01-PLAN.md | User can install DuckDB support via `semolina[duckdb]` extra (`duckdb>=1.5.0`, `pyarrow>=17.0.0` explicit) | SATISFIED | pyproject.toml duckdb extra correct; uv.lock consistent; install path verified |

Note: DUCK-01 as stated in REQUIREMENTS.md ("User can install DuckDB support via `semolina[duckdb]` extra") is satisfied by the packaging fix. The xfail gap concerns test cleanliness, not the installability of the extra.

No orphaned requirements: REQUIREMENTS.md maps only DUCK-01 to Phase 38 (Traceability table, line 71), and 38-01-PLAN.md claims exactly DUCK-01.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/unit/test_query.py` | 28 | Stale docstring: "Tests requiring semantic_view() through ADBC are xfail (catalog resolution bug)" | Warning | Misleading — implies this is temporary when it is still active |
| `tests/unit/test_query.py` | 115-119 | `_xfail_adbc = pytest.mark.xfail(...)` variable definition | Warning | Planned for removal once upstream fixes catalog resolution bug |
| `tests/unit/test_pool.py` | 14-21 | Docstring Note block describes active upstream bug as ongoing | Info | Accurate given current state — not a false positive |

Note: The xfail presence is intentional given upstream reality. It is NOT a code quality defect — it correctly guards tests against a known upstream failure. The gap is that SC4 cannot be satisfied yet.

### Human Verification Required

None — all checks are automated and deterministic.

## Gaps Summary

One success criterion cannot be met due to an upstream dependency issue:

**SC4: All previously-xfailed semantic_view() ADBC tests pass without xfail markers**

The duckdb-semantic-views extension that was expected to fix catalog resolution in version 0.7.1 has not been released. The installed build (commit hash 6789337) still exhibits the bug. The plan correctly restored the 20 xfail markers to prevent false failures in the test suite.

This gap has no later milestone phase to absorb it — Phase 38 is the final phase of the v0.4.0 milestone. Resolution requires:
1. Monitoring the duckdb-semantic-views project for the 0.7.1 release
2. Re-running Task 2 from 38-01-PLAN.md when the upstream fix ships
3. Re-running this verification

The three packaging success criteria (SC1, SC2, SC3) are fully satisfied. The project correctly installs duckdb and pyarrow via `semolina[duckdb]`, the `all` extra includes duckdb, and sphinx-autobuild is correctly isolated to the docs dependency group. DUCK-01 as scoped in REQUIREMENTS.md is satisfied.

---

_Verified: 2026-05-01T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
