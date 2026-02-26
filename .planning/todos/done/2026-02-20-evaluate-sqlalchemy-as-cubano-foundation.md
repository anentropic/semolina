---
created: 2026-02-20T00:22:53.126Z
title: Evaluate SQLAlchemy as cubano foundation
area: api
files:
  - src/cubano/filters.py
  - src/cubano/query.py
  - src/cubano/engines/base.py
---

## Problem

Cubano has hand-rolled query building (Q objects, filter lookups, SQL generation) that overlaps significantly with what SQLAlchemy Core already provides. The sanity-check question: would we be better off building on SQLAlchemy rather than maintaining our own query layer?

Relates to the "Review and extend filter lookup expressions" todo — if SQLAlchemy Core is a viable foundation, it would resolve the extensibility question there too.

**The key constraint:** some future backends (dbt-sl, Cube.dev) do not expose a SQL interface — they have their own query APIs. A hard SQLAlchemy dependency would make those backends awkward or impossible.

Open questions:
1. Is SQLAlchemy modular enough to use just the query-building layer (Core/expression language) without its ORM or connection management?
2. Could our `Engine` abstraction sit on top of SQLAlchemy Core for SQL backends while bypassing it entirely for non-SQL backends (dbt-sl, Cube)?
3. What would we lose from our current design (zero runtime deps, simple Q-object API) by adopting SQLAlchemy Core?
4. Would SQLAlchemy's dialect system give us Snowflake/Databricks SQL generation for free, or do those still require custom work?

## Solution

Research spike:
- Evaluate SQLAlchemy Core in isolation (no ORM) — what does it weigh, what does it give us?
- Prototype translating a cubano Q-expression to SQLAlchemy Core selectable vs current hand-rolled SQL
- Map which planned backends are SQL-compatible vs non-SQL (dbt-sl, Cube.dev, etc.)
- Decision: adopt SQLAlchemy Core for SQL backends / keep own layer / hybrid approach
