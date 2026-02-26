---
created: 2026-02-23T06:51:42.779Z
title: Lazy/streaming Result with cursor-based iteration
area: api
files:
  - src/cubano/results.py
  - src/cubano/query.py
---

## Problem

`Result` eagerly materializes all rows into `list[Row]` at construction time. The `.execute()` method fetches everything from the cursor upfront. For large result sets this is wasteful — all data lives in memory even if the caller only needs the first few rows or is streaming to an HTTP response.

This also affects `__repr__`: the current implementation uses `len(self.rows)` which is cheap on a list but would need rethinking for a lazy result (can't know row count without consuming the iterator).

## Solution

TBD — options to explore:

- Cursor-wrapping iterator that yields `Row` on demand
- `len()` could raise `TypeError` (like generators) or require explicit `.materialize()` / `.fetchall()`
- `repr` could show `Result(columns=[...])` without count for lazy results, or `Result(N rows, columns=[...])` after materialization
- Consider whether `Result` should support both modes (lazy default, `.fetchall()` for eager) or just lazy
- Arrow/DataFrame output (separate todo) may influence this design
