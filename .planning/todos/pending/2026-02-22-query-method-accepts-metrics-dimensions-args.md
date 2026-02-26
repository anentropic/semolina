---
created: 2026-02-22T09:12:00Z
title: Explore query() accepting metrics and dimensions args
area: api
files: [src/cubano/models.py, src/cubano/query.py]
---

## Problem

Currently building a query requires chaining `.metrics()` and `.dimensions()`:

```python
Sales.query().metrics(Sales.revenue).dimensions(Sales.country).where(...)
```

For simple queries this is verbose. Could `query()` itself accept these as arguments?

## Desired Behavior

```python
# Shorthand
Sales.query(metrics=[Sales.revenue], dimensions=[Sales.country]).where(...)

# Fluent builder still works for complex/conditional cases
Sales.query().metrics(Sales.revenue).dimensions(Sales.country).where(...)
```

## Open Questions

- Positional vs keyword-only args?
- Does this conflict with the `using` parameter already on `query()`?
- Should it accept varargs or lists?
- Worth the API surface increase vs just using the builder?

## Origin

Observed during Phase 13.1 UAT — filtering.md examples show the verbose pattern repeatedly.
