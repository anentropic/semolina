---
created: 2026-02-18T15:21:07.194Z
title: cube.dev and dbt-sl backends
area: api
files:
  - src/cubano/backends/
---

## Problem

Cubano currently supports two semantic layer backends: Snowflake Semantic Views and Databricks Metric Views. There are two other major semantic layers in the ecosystem:

- **Cube.dev** — open-source semantic layer with its own query API (REST/GraphQL/SQL), widely used independently of any specific warehouse
- **dbt Semantic Layer (dbt-sl)** — MetricFlow-powered semantic layer built into dbt Cloud and dbt Core, queryable via JDBC/ADBC or the dbt Cloud APIs

Both have distinct query semantics and connection mechanisms but expose metrics and dimensions conceptually similar to Snowflake/Databricks. Supporting them would make Cubano the universal Python ORM for semantic layers regardless of which one a team uses.

## Solution

TBD — each backend likely needs its own extras group:
- `cubano[cube]` — wraps Cube's REST/SQL API
- `cubano[dbt-sl]` — wraps dbt Cloud Semantic Layer API (JDBC or Python SDK)

Key design question: both backends have richer query semantics than raw SQL (time grains, pre-aggregations, etc.). Need to decide how much of that surface area to expose vs. keeping the Cubano API uniform across all backends.
