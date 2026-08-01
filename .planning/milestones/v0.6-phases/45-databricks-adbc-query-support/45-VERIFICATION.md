---
phase: 45-databricks-adbc-query-support
verified: 2026-06-24T23:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 45: Databricks ADBC Query Support Verification Report

**Phase Goal:** Make Databricks query execution work end-to-end over real ADBC and record the Databricks integration cassettes. Two arrow-adbc Databricks driver blockers fixed: DBX-01 (no bind params — literal inlining), DBX-02 (no default catalog/schema — adbc-poolhouse DSN fix), DBX-03 (record + replay 7 Databricks cassettes green).
**Verified:** 2026-06-24T23:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | DBX-01: Databricks `.where()` emits inlined literals and empty params (no `?`) | VERIFIED | `TestDatabricksLiteralInlining` class (5 tests incl. CR-01/WR-01 regressions) — 158/158 passed; `DatabricksDialect.supports_parameterized_queries = False` + `_render_literal_sql` post-pass confirmed in `sql.py:376,839-880` |
| 2 | DBX-01b: Snowflake/DuckDB remain on parameterized `?` + bound params (no regression) | VERIFIED | `TestParameterizedNoRegression` class (2 tests) — `SnowflakeDialect.supports_parameterized_queries = True` confirmed; both tests green |
| 3 | DBX-01c: `render_literal` escapes adversarial values safely (backslash-first ordering for Spark; non-finite floats raise ValueError) | VERIFIED | `TestRenderLiteralDatabricks` (10 tests) + `TestRenderLiteralStandardSql` (7 tests) green; `sql.py:409-426` implements backslash-before-quote, `sql.py:115-117` raises `ValueError` for non-finite floats; CR-01/WR-01 fixes confirmed in `sql.py:868-880` (split-and-interleave, not re-scan) |
| 4 | DBX-02: adbc-poolhouse `DatabricksConfig.to_adbc_kwargs()` URI carries `?catalog=&schema=`; pin bumped to `>=1.3.1` | VERIFIED | `pyproject.toml` line 11: `"adbc-poolhouse>=1.3.1"`; live check: `uv run python -c "from adbc_poolhouse import DatabricksConfig; ..."` → `databricks://token:t@h:443/p?catalog=main&schema=s` |
| 5 | DBX-03: 7 Databricks cassettes recorded and 14/14 integration tests replay green (Databricks + Snowflake, no live warehouse) | VERIFIED | 7 cassette dirs confirmed under `tests/integration/cassettes/integration/test_queries/*_databricks_engine_/`; `uv run pytest tests/integration -k "databricks or snowflake" -q` → 14 passed; WHERE cassette `000_query.sql` shows `WHERE "country" = 'US'` (literal inlined) + `000_params.json` = `[]` (empty params) |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/semolina/engines/sql.py` | `supports_parameterized_queries` flag on ABC + `DatabricksDialect`; `render_literal()` on ABC and Databricks override; `_render_literal_sql()` post-pass in `SQLBuilder` and `DuckDBSQLBuilder` | VERIFIED | Flag at `Dialect:75`, `DatabricksDialect:376`; `render_literal` at `Dialect:86`, `DatabricksDialect:386`; `_render_literal_sql` at `SQLBuilder:843`, wired into `build_select_with_params` at lines 839-841 and `DuckDBSQLBuilder:1208-1209` |
| `tests/unit/test_sql.py` | `TestSupportsParameterizedQueries`, `TestRenderLiteralStandardSql`, `TestRenderLiteralDatabricks`, `TestDatabricksLiteralInlining`, `TestParameterizedNoRegression` | VERIFIED | All 5 classes present, 158 total tests collected and passing |
| `pyproject.toml` | `adbc-poolhouse>=1.3.1` pin | VERIFIED | Line 11: `"adbc-poolhouse>=1.3.1"` |
| `tests/integration/cassettes/integration/test_queries/*_databricks_engine_/` | 7 cassette dirs, each with `000_query.sql`, `000_params.json`, `000_result.arrow` | VERIFIED | All 7 dirs present: `test_single_metric`, `test_multiple_metrics`, `test_metric_with_dimension`, `test_multiple_metrics_with_dimension`, `test_dimension_only`, `test_filtered_by_dimension`, `test_streaming_iteration` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `DatabricksDialect.supports_parameterized_queries = False` | `SQLBuilder.build_select_with_params` literal-inline branch | Flag check at `sql.py:839` | WIRED | `if not self.dialect.supports_parameterized_queries: return self._render_literal_sql(sql, all_params), []` |
| `DatabricksDialect.render_literal` (Spark escaping) | `_render_literal_sql` post-pass | Called inside `_render_literal_sql` at `sql.py:878` | WIRED | `out.append(self.dialect.render_literal(param))` — polymorphic dispatch, no isinstance check |
| `DatabricksDialect` flag | `DuckDBSQLBuilder.build_select_with_params` | Same flag check at `sql.py:1208` | WIRED | DuckDB builder also has the literal-inline gate (guards against future DuckDB driver regression) |
| `adbc-poolhouse>=1.3.1` | Databricks ADBC connection DSN | `pyproject.toml` dep pin; `DatabricksConfig.to_adbc_kwargs()` | WIRED | DSN verified live: ends `?catalog=main&schema=s` |
| Databricks cassettes | `pytest-adbc-replay` offline replay | `tests/integration/cassettes/.../adbc_driver_manager.dbapi/databricks/` | WIRED | 14/14 integration tests pass offline |

---

## Data-Flow Trace (Level 4)

The key end-to-end data flow for DBX-01 + DBX-02 is captured in the WHERE cassette.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `test_filtered_by_dimension_databricks_engine_/adbc_driver_manager.dbapi/databricks/000_query.sql` | WHERE clause literal value `'US'` | `DatabricksDialect.render_literal("US")` via `_render_literal_sql` | Yes — `'US'` inlined, no `?` | FLOWING |
| `test_filtered_by_dimension_databricks_engine_/adbc_driver_manager.dbapi/databricks/000_params.json` | Bound params list | `build_select_with_params` returning `[]` | Yes — `[]` confirms empty | FLOWING |
| `test_filtered_by_dimension_databricks_engine_/adbc_driver_manager.dbapi/databricks/000_query.sql` | FROM clause view resolution | `DatabricksConfig.to_adbc_kwargs()` DSN carrying `?catalog=&schema=` | Yes — `FROM "sales_view"` resolved (live recording returned results) | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| DBX-01/01b/01c: 158 SQL unit tests all green | `uv run pytest tests/unit/test_sql.py -q` | `158 passed in 0.07s` | PASS |
| DBX-03: 14 integration replay tests green (Databricks + Snowflake) | `uv run pytest tests/integration -k "databricks or snowflake" -q` | `14 passed in 0.09s` | PASS |
| DBX-02: poolhouse DSN carries catalog/schema | `uv run python -c "from adbc_poolhouse import DatabricksConfig; ..."` | `databricks://token:t@h:443/p?catalog=main&schema=s` | PASS |
| WHERE cassette proves DBX-01 (literal inlined): | Read `000_query.sql` for `test_filtered_by_dimension_databricks_engine_` | `WHERE "country" = 'US'` — literal value, no `?` | PASS |
| WHERE cassette proves empty params (DBX-01): | Read `000_params.json` for `test_filtered_by_dimension_databricks_engine_` | `[]` | PASS |

---

## Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` probes declared or present for Phase 45. Integration replay serves as the functional proof (Step 7b above).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DBX-01 | 45-01-PLAN.md | Databricks `.where()` literal-inlining: `supports_parameterized_queries` flag + `render_literal` + `_render_literal_sql` post-pass | SATISFIED | `DatabricksDialect.supports_parameterized_queries = False`; `_render_literal_sql` split-and-interleave at `sql.py:843-880`; 158/158 tests pass |
| DBX-01b | 45-01-PLAN.md | Snowflake/DuckDB stay parameterized — no regression | SATISFIED | `SnowflakeDialect`/`DuckDBDialect` leave `supports_parameterized_queries = True` (ABC default); `TestParameterizedNoRegression` green |
| DBX-01c | 45-01-PLAN.md | `render_literal` adversarial escaping (backslash, single-quote, NULL, bool, IN-list, non-finite floats) | SATISFIED | `TestRenderLiteralDatabricks` + `TestRenderLiteralStandardSql` green (10 + 7 tests); WR-01 fix (`ValueError` for inf/nan) confirmed at `sql.py:115-117` and `sql.py:411-414`; CR-01 fix (split-and-interleave) confirmed at `sql.py:868-880` |
| DBX-02 | 45-02-PLAN.md | adbc-poolhouse `to_adbc_kwargs()` URI carries `?catalog=&schema=`; consumed via pin bump `>=1.3.1` | SATISFIED | `pyproject.toml` dep confirmed; live DSN check returns `?catalog=main&schema=s`; poolhouse unit tests live in the separate adbc-poolhouse 1.3.1 release |
| DBX-03 | 45-03-PLAN.md | 7 Databricks cassettes recorded + 14/14 integration replay green offline | SATISFIED | 7 cassette dirs present; 14 passed in offline replay |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No debt markers (TBD/FIXME/XXX), placeholders, or stubs found in Phase 45 modified files (`sql.py`, `test_sql.py`, `pyproject.toml`) |

Note: The code review (45-REVIEW.md) identified CR-01 (placeholder re-scan corruption) and WR-01 (non-finite float bare-identifier emission) as blockers. Both were fixed in commit `56ae0a6` before this verification. The `_render_literal_sql` in the verified code uses the split-and-interleave approach (not the original re-scan loop). The REVIEW status is `resolved`.

---

## Pre-Existing Concerns (Out of Scope)

~28 jaffle-shop test-collection errors (`ModuleNotFoundError: semolina.testing.credentials`) break `just test` collection. This predates Phase 45 — it is a stale conftest import from an earlier module cleanup unrelated to the Databricks work. The Phase 45 files (`sql.py`, `test_sql.py`) are not involved. Not a Phase 45 regression.

---

## Human Verification Required

None. All Phase 45 requirements are verifiable programmatically via:
- Unit test execution (offline, no creds)
- Integration cassette replay (offline, no creds)
- DSN construction check (no live warehouse)
- Cassette file inspection

The live recording step (DBX-03 Task 0) was the only human-action requirement — it was completed by the operator during Phase 45 execution, producing the committed cassettes that now replay fully offline.

---

## Gaps Summary

No gaps. All 5 must-haves are VERIFIED.

---

_Verified: 2026-06-24T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
