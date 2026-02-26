---
created: 2026-02-20T23:29:17.455Z
title: Implement filter lookup system and WHERE clause compiler
area: api
files:
  - src/cubano/filters.py
  - src/cubano/fields.py
  - src/cubano/engines/sql.py
  - docs/src/guides/filtering.md
---

## Problem

The WHERE clause in `src/cubano/engines/sql.py:438` returns `"WHERE 1=1"` — a placeholder.
The Q-object API exists and is fully designed but nothing translates it to SQL (or Cube.dev
JSON filters) yet. Filters silently do nothing at query execution time.

Additionally:
- Field operators generate `__ge`/`__le` but docs/lookups say `__gte`/`__lte` (naming bug)
- `Q(foo__totally_invented=1)` is silently accepted — no lookup name validation
- `.between()` and `.in_()` methods don't exist on Field yet (most common real-world patterns)

See `_ideas/filter-api-design.md` for full design decisions from the 2026-02-20 session.

## Solution

**Step 1 — Fix naming inconsistency (prerequisite):**
Standardise on `__gte`/`__lte` throughout: fix `fields.py` `__ge__`/`__le__` methods to emit
`__gte`/`__lte` instead. Update any test fixtures that hardcode `__ge`/`__le`.

**Step 2 — Add missing Field methods:**
Add to `Field` class in `fields.py`:
- `.between(lo, hi)` → `Q(field__between=(lo, hi))`
- `.in_([...])` → `Q(field__in=[...])`
- `.ilike("pat")` → `Q(field__ilike="pat")`
- `.iexact("x")` → `Q(field__iexact="x")`
- `.istartswith("x")` → `Q(field__istartswith="x")`
- `.iendswith("x")` → `Q(field__iendswith="x")`

**Step 3 — Implement `_QCompiler` in SQL engine:**
Replace the `WHERE 1=1` placeholder with a proper tree walker that handles:
- Leaf nodes: field name + lookup → SQL predicate
- Branch nodes: AND/OR with parenthesisation
- Negation: NOT (...)
- All 13 core lookups with dialect-specific quoting

**Step 4 — Add `Lookup[T]` escape hatch:**
Create `cubano/lookups.py` with `Lookup(Generic[T])` base class.
Add `Field.lookup(lookup_cls: type[Lookup[T]], value: T) -> Q` method.
Engine compilers dispatch on Lookup subclass type in Q nodes.

**Step 5 — Lookup validation:**
Add validation at Q construction or `.where()` time that lookup names are registered.
Unknown lookups should raise `ValueError` with a helpful message.

**Step 6 — Update docs and tests:**
- `docs/src/guides/filtering.md` — add `.between()`, `.in_()`, case-insensitive methods
- Add unit tests for all new Field methods and all lookup → SQL translations
- Add integration test with a filter that actually reaches the WHERE clause
