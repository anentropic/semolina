---
created: 2026-02-19T22:49:09.085Z
title: Review and extend filter lookup expressions
area: api
files:
  - src/cubano/filters.py
  - src/cubano/query.py
  - docs/src/guides/filtering.md
---

## Problem

The current filter system supports 9 lookup expressions (gt, gte, lt, lte, contains,
startswith, endswith, in, isnull) via `Q(field__lookup=value)` syntax. It's unclear
whether this covers the full range of patterns users will need when querying semantic
views, and whether the current design is extensible enough for future operators.

Open questions:
1. **Coverage gaps** — what filter patterns do real semantic view reports use that
   aren't covered? e.g. date ranges, BETWEEN, regex, array containment, NULL handling
   nuances
2. **Django F objects** — Django's `F()` lets you reference other field values in
   filters (`Q(revenue__gt=F('cost'))`). Does Cubano need cross-field comparison
   support for semantic view queries?
3. **Extensibility** — can users register custom lookup expressions, or add backend-
   specific operators (e.g. Snowflake SEARCH, Databricks array functions)?
4. **Simplification** — conversely, semantic views are aggregation-oriented (not
   row-level OLTP). Could a simpler filter model (e.g. dimension equality + metric
   range) cover 90% of real use cases without the full Django-inspired lookup system?

## Solution

TBD — requires investigation:
- Review common semantic view report query patterns (what BI tools send as filters)
- Compare against current Q-object lookup set
- Prototype Django F-style cross-field reference if needed
- Consider whether backend SQL translators need extension points for custom operators
