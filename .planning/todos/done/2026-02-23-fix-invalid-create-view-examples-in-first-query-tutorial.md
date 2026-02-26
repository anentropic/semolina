---
created: 2026-02-23T00:05:45.477Z
title: Fix invalid CREATE VIEW examples in first-query tutorial
area: docs
files:
  - docs/src/tutorials/first-query/index.md
---

## Problem

In `docs/src/tutorials/first-query/`, the "1. Define a model" section contains `CREATE VIEW` SQL examples for Snowflake and Databricks (shown under "this model maps to a view like..."). These examples are invalid — they don't match the actual DDL syntax used by each warehouse.

The Snowflake and Databricks dialects have different DDL syntax for creating views, and the current examples may be using incorrect or simplified syntax that wouldn't actually work. This is misleading for users who may try to reference or reuse the SQL shown.

## Solution

1. Look up the correct `CREATE VIEW` syntax from official Snowflake and Databricks documentation
2. Rewrite the Snowflake example to match: https://docs.snowflake.com/en/sql-reference/sql/create-view
3. Rewrite the Databricks example to match: https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-view.html
4. Ensure both examples are valid, runnable DDL that a user could copy-paste into their warehouse
