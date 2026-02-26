---
created: 2026-02-22T08:58:00Z
title: Nice repr for all public API classes
area: api
files:
  - src/cubano/models.py
  - src/cubano/fields.py
  - src/cubano/filters.py
  - src/cubano/query.py
  - src/cubano/results.py
---

## Problem

Most public API classes use default Python repr. For a library focused on REPL/IDE ergonomics, repr output should be informative and readable across the board.

Examples of current unhelpful repr:
- `repr(Sales)` → `<class '__main__.Sales'>` (SemanticView subclass)
- `repr(Sales.revenue)` → field repr may lack context
- `repr(Sales.revenue > 100)` → predicate tree repr
- `repr(result)` → Result object repr

## Desired Behavior

Every public API class should have a repr that reads naturally and aids debugging:

- **SemanticView classes**: show class definition with view name and fields
- **Field/Metric/Dimension/Fact**: show field name and type
- **Predicate nodes** (Lookup subclasses, And, Or, Not): show filter expression readably
- **Query**: show query state (model, metrics, dimensions, filters)
- **Result**: show shape and preview of data

## Implementation

Audit all public API classes and add `__repr__` where missing or unhelpful.

## Origin

Noticed during Phase 13.1 UAT — `type(Sales)` is `SemanticViewMeta` but repr gives no useful info. Expanded to cover all public classes.
