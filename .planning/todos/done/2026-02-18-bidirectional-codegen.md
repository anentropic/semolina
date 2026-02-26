---
created: 2026-02-18T15:20:11.757Z
title: Bidirectional codegen
area: api
files:
  - src/cubano/codegen.py
---

## Problem

Cubano's current codegen is one-directional: Python models → CREATE SEMANTIC VIEW SQL (Snowflake or Databricks). There's no reverse path — if you have an existing semantic view in the warehouse, you must hand-write the Cubano Python model class from scratch.

Bidirectional codegen would close this loop: introspect an existing semantic view from the warehouse and generate the corresponding Cubano model class automatically. This lowers the barrier to adoption (users with existing views don't need to rewrite them manually) and helps keep models in sync with warehouse definitions.

## Solution

TBD — two directions:
1. **Forward (already done):** `cubano codegen <model_file>` → CREATE SEMANTIC VIEW SQL
2. **Reverse (new):** `cubano introspect <view_name> --backend snowflake|databricks` → Python model class

Reverse codegen requires warehouse introspection via the backend's metadata APIs (Snowflake INFORMATION_SCHEMA, Databricks Unity Catalog). Likely a separate CLI subcommand (`cubano introspect` or `cubano codegen --reverse`). Credential setup from Phase 8 would be reused.
