---
created: 2026-02-23T16:22:14.104Z
title: Document Fact field type for Databricks and Snowflake users
area: docs
files:
  - src/cubano/fields.py:630
  - docs/src/how-to/models.md
  - docs/src/tutorials/first-query.md
---

## Problem

Cubano exposes a `Fact` field type (`src/cubano/fields.py:630`) that maps to Databricks metric views' explicit "facts" concept. Facts behave functionally the same as dimensions (they're groupable, non-aggregated columns) but carry an informative semantic distinction in Databricks.

Currently there's no documentation explaining:
- What `Fact` is and when to use it vs `Dimension`
- That Databricks metric views natively distinguish facts from dimensions
- That Snowflake users can optionally label some of their dimensions as facts for semantic clarity
- The practical difference (or lack thereof) in query behavior

## Solution

Add a section to the models how-to (or a dedicated short how-to) covering:
1. `Fact` field type — what it means, when to use it
2. Databricks context — maps to the `FACT` clause in metric view DDL
3. Snowflake context — optional semantic labeling, no behavioral difference
4. Example model using `Fact` alongside `Metric` and `Dimension`
