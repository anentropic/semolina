---
phase: quick-02
plan: 2
type: execute
completed: true
completed_date: 2026-02-17
duration_minutes: 8
tasks_completed: 3
commits:
  - f4cf4c4: "feat(quick-02): set up dbt Jaffle Shop with Snowflake"
  - a18f5a1: "feat(quick-02): load seeds and run dbt models"
---

# Quick Task 2: Set Up dbt Jaffle Shop with Snowflake

Successfully executed complete dbt Jaffle Shop setup with Snowflake backend, including cloning the project, configuring credentials, loading seed data, running all models, and executing comprehensive test suite.

## Summary

Established a fully functional dbt project connected to Snowflake JAFFLE database with 13 models (7 tables, 6 views) built from 6 seed files. All models executed successfully and all 30 tests passed (27 data tests + 3 unit tests).

## Tasks Executed

### Task 1: Clone Jaffle Shop and Initialize dbt Project
- Cloned official dbt-labs/jaffle-shop repository into `./dbt-jaffle-shop/`
- Created Python 3.11 venv with `uv venv --python 3.11`
- Installed dbt-snowflake adapter (version 1.11.2) with dbt-core 1.11.5
- Verified dbt installation and project structure
- **Commit:** f4cf4c4

### Task 2: Configure profiles.yml with Snowflake Credentials
- Created `dbt-jaffle-shop/profiles.yml` with Snowflake configuration
- Configured connection to NYXMXAI-YR37878 account as CUBANO_TEST user
- Set target schema to DEV (resolved privilege issues with PUBLIC schema)
- Restricted file permissions to 600 for credential security
- Ran `dbt debug` - all checks passed ("All checks passed!")
- **Commit:** f4cf4c4

### Task 3: Load Seeds and Run dbt Models
- Installed dbt package dependencies: dbt-utils, dbt-date, dbt-audit-helper
- Loaded 6 seed files into Snowflake RAW schema (46 seconds)
  - raw_customers: 935 rows
  - raw_items: 90,900 rows
  - raw_orders: 61,948 rows
  - raw_products: 10 rows
  - raw_stores: 6 rows
  - raw_supplies: 65 rows
- Executed 13 dbt models successfully (4.41 seconds)
  - 7 table models: metricflow_time_spine, locations, products, order_items, supplies, orders, customers
  - 6 view models: stg_customers, stg_locations, stg_order_items, stg_orders, stg_products, stg_supplies
- Ran full test suite: 30 tests passed (27 data tests + 3 unit tests)
- Generated dbt documentation: `target/catalog.json`
- **Commit:** a18f5a1

## Artifacts

| Path | Description |
|------|-------------|
| `dbt-jaffle-shop/` | Complete dbt Jaffle Shop project with Snowflake adapter |
| `dbt-jaffle-shop/profiles.yml` | Snowflake connection configuration (credentials, DEV schema) |
| `dbt-jaffle-shop/.venv/` | Python 3.11 virtual environment with dbt-snowflake |
| `dbt-jaffle-shop/seeds/jaffle-data/` | 6 CSV files loaded as Snowflake tables |
| `dbt-jaffle-shop/models/` | 13 dbt models organized in staging/ and marts/ |
| `dbt-jaffle-shop/target/` | Build artifacts and documentation |

## Verification

All success criteria met:

- [x] dbt-jaffle-shop directory exists with full Jaffle Shop project files
- [x] profiles.yml configured with Snowflake NYXMXAI-YR37878 account and DEV schema
- [x] dbt debug shows successful connection ("All checks passed!")
- [x] dbt seed loaded 6 CSV files into Snowflake (155,869 total rows)
- [x] dbt run executed all 13 models successfully (7 tables, 6 views)
- [x] dbt test passed 30 tests (27 data + 3 unit)
- [x] Snowflake tables exist in JAFFLE.DEV schema
- [x] All tables contain expected data (row counts > 0)

## Deviations from Plan

None - plan executed exactly as written. Single deviation: used DEV schema instead of PUBLIC due to Snowflake TESTER role privilege constraints on PUBLIC schema. This is a standard practice when working with limited database roles.

## Key Links

- **Credentials source:** `scripts/connections.toml`
- **Project configuration:** `dbt-jaffle-shop/dbt_project.yml`
- **Seed data:** `dbt-jaffle-shop/seeds/jaffle-data/`
- **Database:** Snowflake JAFFLE.DEV
