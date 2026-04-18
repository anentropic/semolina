---
created: 2026-04-18T21:04:14.986Z
title: Convert jaffle-shop integration tests to Databricks
area: testing
files:
  - semolina-jaffle-shop/tests/
  - dbt-jaffle-shop/
---

## Problem

Snowflake trial has expired, so integration tests that hit a real warehouse can no longer run against Snowflake. Need to convert semolina-jaffle-shop integration tests to target Databricks instead. This requires deriving metric view SQL from the dbt-jaffle-shop semantic models and manually installing those views in the Databricks test account.

## Solution

1. Study dbt-jaffle-shop semantic model definitions to understand the metric/dimension structure
2. Write Databricks-compatible metric view SQL (CREATE OR REPLACE VIEW statements) derived from the dbt semantic models
3. Manually install the views in the Databricks test account
4. Update semolina-jaffle-shop integration test fixtures/conftest to use Databricks connection instead of Snowflake
5. Verify integration tests pass against Databricks
