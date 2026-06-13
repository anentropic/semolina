---
phase: quick-4
plan: "01"
subsystem: documentation
tags: [docs, api-migration, query-refactor]
dependency_graph:
  requires: []
  provides: [corrected-query-api-docs]
  affects: [docs/guides/]
tech_stack:
  added: []
  patterns: [Model.query().method().execute()]
key_files:
  created: []
  modified:
    - docs/guides/first-query.md
    - docs/guides/queries.md
    - docs/guides/models.md
    - docs/guides/filtering.md
    - docs/guides/ordering.md
    - docs/guides/backends/overview.md
    - docs/guides/backends/snowflake.md
    - docs/guides/backends/databricks.md
decisions:
  - "No new decisions — straightforward substitution of old procedural API with model-centric API"
metrics:
  duration_minutes: 3
  completed_date: "2026-02-18"
  tasks_completed: 3
  files_modified: 8
---

# Quick Task 4: Update Docs to Reflect the Query Model — Summary

All 8 documentation guide files updated from the old procedural `Query()` constructor and `.fetch()` execution method to the current model-centric `Model.query().method().execute()` API introduced in Phase 10.1.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update first-query.md, queries.md, and models.md | b1a7b17 | 3 files |
| 2 | Update filtering.md, ordering.md, and all backend guides | 24e4961 | 5 files |
| 3 | Verify docs build clean with no stale API references | (verification only) | 0 files |

## Changes Made

### first-query.md
- MockEngine prose: `.fetch()` → `.execute()`
- Section 3 prose: `Use Query with method chaining` → `Use Model.query() with method chaining`
- Section 3 code: removed `from cubano import Query`, changed `Query().metrics(...).dimensions(...)` to `Sales.query().metrics(...).dimensions(...)`
- Section 4 heading: `Execute with .fetch()` → `Execute with .execute()`
- Section 4 code: `query.fetch()` → `query.execute()`
- Complete example: removed `Query` from import line, updated constructor and execution calls

### queries.md
- Intro: `Cubano's Query class` → `Cubano's query API`
- Section 1 `.metrics()`: removed `from cubano import Query`, all `Query()` → `Sales.query()`
- Section 2 `.dimensions()`: all `Query()` → `Sales.query()`
- Section 3: renamed `.filter()` → `.where()`, all `Query()` → `Sales.query()`, `.filter(` → `.where(`
- Section 4 `.order_by()`: all `Query()` → `Sales.query()`
- Section 5 `.limit()`: `Query()` → `Sales.query()`
- Section 6 `.using()`: `Query()` → `Sales.query()`, prose updated `.fetch() time` → `.execute() time`
- Section 7: renamed `.fetch()` → `.execute()`, all constructor and execution calls updated
- Section 8 `.to_sql()`: `Query()` → `Sales.query()`, tip block updated to use `.where()`
- Immutable chaining section: `Query()` → `Sales.query()`, `.filter(` → `.where(`
- Building incrementally section: removed `Query` type annotation, `Query()` → `Sales.query()`, `.filter(` → `.where(`, `.fetch()` → `.execute()`

### models.md
- Descriptor example: removed `from cubano import Query`, `Query().metrics(...)` → `Orders.query().metrics(...)`

### filtering.md
- Basic equality: removed `from cubano import Query`, `.filter(Q(...)).fetch()` → `.where(Q(...)).execute()`
- Pass it to sentence: `.filter()` → `.where()`
- Lookup expressions (3 examples): `Query()` → `Sales.query()`, `.filter(` → `.where(`
- OR composition: `Query().metrics(...).filter(q).fetch()` → `Sales.query().metrics(...).where(q).execute()`
- AND composition: same pattern, plus chained multi-call example updated
- Multiple calls prose: `.filter()` → `.where()`
- NOT negation: same replacement pattern
- Complex nesting: same replacement pattern
- Section heading: `Multiple .filter() calls` → `Multiple .where() calls`
- Section prose and code: all `.filter(` → `.where(`, `.fetch()` → `.execute()`, `Query()` → `Sales.query()`

### ordering.md
- Default ascending: removed `from cubano import Query`, `Query()` → `Sales.query()`
- Explicit ascending: `Query()` → `Sales.query()`
- Descending: `Query()` → `Sales.query()`
- NULL handling: `from cubano import NullsOrdering, Query` → `from cubano import NullsOrdering`, both `Query()` → `Sales.query()`
- Limiting results: `Query()` → `Sales.query()`
- Multiple sort fields: `Query()` → `Sales.query()`
- Ordering and limiting together: `Query()` → `Sales.query()`, `query.fetch()` → `query.execute()`
- OrderTerm objects: `Query()` → `Sales.query()`

### backends/overview.md
- Import: removed `Query` from `from cubano import register, Query`
- Query example: `Query().metrics(...).fetch()` → `Sales.query().metrics(...).execute()`
- MockEngine prose: `.fetch()` → `.execute()`

### backends/snowflake.md
- Running a query: removed `Query` from import, `Query().metrics(...).fetch()` → `Sales.query().metrics(...).execute()`
- Backend-specific SQL note: `engine.to_sql(Query()...)` → `engine.to_sql(Sales.query()...)`

### backends/databricks.md
- Running a query: removed `from cubano import Query`, `Query().metrics(...).fetch()` → `Sales.query().metrics(...).execute()`
- Backend-specific SQL note: `engine.to_sql(Query()...)` → `engine.to_sql(Sales.query()...)`

## Verification Results

```
grep -rn "Query()" docs/guides/        → 0 matches
grep -rn ".fetch()" docs/guides/       → 0 matches
grep -rn ".filter(" docs/guides/       → 0 matches
grep -rn ".query()" docs/guides/       → 46 matches
grep -rn ".execute()" docs/guides/     → 26 matches
grep -rn ".where(Q(" docs/guides/      → 15 matches
mkdocs build --strict                  → Documentation built in 1.33 seconds
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- [x] docs/guides/first-query.md — modified
- [x] docs/guides/queries.md — modified
- [x] docs/guides/models.md — modified
- [x] docs/guides/filtering.md — modified
- [x] docs/guides/ordering.md — modified
- [x] docs/guides/backends/overview.md — modified
- [x] docs/guides/backends/snowflake.md — modified
- [x] docs/guides/backends/databricks.md — modified

### Commits exist:
- [x] b1a7b17 — docs(quick-4): update first-query.md, queries.md, and models.md
- [x] 24e4961 — docs(quick-4): update filtering.md, ordering.md, and backend guides

## Self-Check: PASSED
