---
phase: quick-8
verified: 2026-02-19T18:30:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Quick Task 8: Update dbt-jaffle-shop Verification Report

**Task Goal:** Update dbt-jaffle-shop to set up the expected semantic view / metric view so that
`pytest --snapshot-update tests/test_snapshot_queries.py` can record snapshots against real
Snowflake and Databricks warehouses.
**Verified:** 2026-02-19T18:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                              | Status     | Evidence                                                                                         |
| --- | ---------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| 1   | Snowflake target creates snapshot_sales_view as SEMANTIC VIEW queryable with AGG() | VERIFIED   | macro lines 32-43: `CREATE OR REPLACE SEMANTIC VIEW` with `AGG(snapshot_sales_data.revenue)`    |
| 2   | Databricks target creates snapshot_sales_view as METRIC VIEW queryable with MEASURE() | VERIFIED | macro lines 65-81: `CREATE OR REPLACE METRIC VIEW` with `METRICS (revenue DOUBLE, cost DOUBLE)` |
| 3   | View contains exactly the 5 SNAPSHOT_TEST_DATA rows                                | VERIFIED   | VALUES tuples on lines 24-28 and 57-61 match SNAPSHOT_TEST_DATA in tests/conftest.py exactly    |
| 4   | Macro uses target.type to branch between Snowflake and Databricks DDL              | VERIFIED   | Lines 12 and 45: `{% if target.type == 'snowflake' %}` / `{% elif target.type == 'databricks' %}` |

**Score:** 4/4 truths verified

### Data Row Match

SNAPSHOT_TEST_DATA (tests/conftest.py lines 300-305):

```python
{"revenue": 1000, "cost": 100, "country": "US",  "region": "West"}
{"revenue": 2000, "cost": 200, "country": "CA",  "region": "East"}
{"revenue": 500,  "cost": 50,  "country": "US",  "region": "East"}
{"revenue": 1500, "cost": 150, "country": "MX",  "region": "South"}
{"revenue": 800,  "cost": 80,  "country": "CA",  "region": "West"}
```

Macro VALUES clause (both Snowflake and Databricks branches — identical):

```sql
(1000, 100, 'US', 'West'),
(2000, 200, 'CA', 'East'),
(500,   50, 'US', 'East'),
(1500, 150, 'MX', 'South'),
(800,   80, 'CA', 'West')
```

All 5 rows match exactly. Row order is preserved.

### Required Artifacts

| Artifact                                                   | Expected                                        | Status   | Details                                                                    |
| ---------------------------------------------------------- | ----------------------------------------------- | -------- | -------------------------------------------------------------------------- |
| `dbt-jaffle-shop/macros/create_snapshot_sales_view.sql`    | dbt macro + on-run-end hook logic for both backends | VERIFIED | 93-line file; `{% macro create_snapshot_sales_view() %}` on line 10; both branches present |
| `dbt-jaffle-shop/dbt_project.yml`                          | on-run-end hook registering the macro            | VERIFIED | Line 24-25: `on-run-end:` with `"{{ create_snapshot_sales_view() }}"` hook |

### Key Link Verification

| From                          | To                                               | Via                                           | Status   | Details                                                                                                    |
| ----------------------------- | ------------------------------------------------ | --------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------- |
| `dbt_project.yml` on-run-end  | `macros/create_snapshot_sales_view.sql`          | `{{ create_snapshot_sales_view() }}` hook call | WIRED    | dbt_project.yml line 25 calls `create_snapshot_sales_view()`; macro defined in `macros/` directory        |
| macro target.type branch      | Snowflake SEMANTIC VIEW / Databricks METRIC VIEW | `{% do run_query(...) %}` with appropriate DDL | WIRED    | 4x `{% do run_query(...)%}` calls (2 per branch); discards return value correctly with `do` notation      |

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty implementations, no stub returns found in
either modified file.

### Human Verification Required

The following items require live warehouse execution to verify completely:

#### 1. Snowflake SEMANTIC VIEW creation succeeds

**Test:** Run `dbt run --target snowflake` in `dbt-jaffle-shop/`
**Expected:** `snapshot_sales_view` exists as a SEMANTIC VIEW; querying
`SELECT AGG(revenue), country FROM snapshot_sales_view GROUP BY country` returns results
**Why human:** Requires active Snowflake credentials and warehouse; DDL syntax can only be
validated against a live Snowflake instance (SEMANTIC VIEW is a Snowflake-specific feature)

#### 2. Databricks METRIC VIEW creation succeeds

**Test:** Run `dbt run --target databricks` in `dbt-jaffle-shop/`
**Expected:** `snapshot_sales_view` exists as a METRIC VIEW; querying
`SELECT MEASURE(revenue), country FROM snapshot_sales_view GROUP BY country` returns results
**Why human:** Requires active Databricks workspace; METRIC VIEW DDL syntax requires
Databricks Runtime 13.3 LTS+ and can only be validated against a live cluster

#### 3. Snapshot recording end-to-end

**Test:** Run `pytest --snapshot-update tests/test_snapshot_queries.py` with warehouse
credentials configured
**Expected:** Snapshot files are updated with results from real Snowflake and Databricks
queries against `snapshot_sales_view`; subsequent `pytest` runs (without `--snapshot-update`)
pass using the recorded snapshots
**Why human:** Requires credentials for both warehouses and validates the full
recording/replay cycle

## Summary

All automated checks pass. Both artifacts exist with substantive, non-stub content. The macro
correctly implements:

- Two-step DDL per backend (staging table then view) using `CREATE OR REPLACE` for idempotency
- `{% do run_query(...) %}` notation throughout (discards return values — correct dbt pattern)
- Exact 5-row VALUES matching `SNAPSHOT_TEST_DATA` in `tests/conftest.py`
- `target.type` branching with a `raise_compiler_error` fallback for unknown targets
- Snowflake: `NUMBER`/`VARCHAR` types, `SEMANTIC VIEW` with `AGG()` metrics
- Databricks: `BIGINT`/`STRING` types, `METRIC VIEW` with `DOUBLE` metrics

The `on-run-end` hook in `dbt_project.yml` correctly calls the macro after every `dbt run`.
No Python source files were modified (pure dbt configuration change as specified).

Commits verified: `f0b6362` (macro creation) and `0675e38` (hook registration) both exist in
the repository and affect only `dbt-jaffle-shop/` files.

---

_Verified: 2026-02-19T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
