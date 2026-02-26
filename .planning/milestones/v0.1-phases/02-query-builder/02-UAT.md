---
status: testing
phase: 02-query-builder
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md
started: 2026-02-15T12:00:00Z
updated: 2026-02-15T12:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Q-object creation with single condition
expected: Q(country='US') creates a readable Q-object that can be inspected with repr()
result: pass

### 2. Q-object OR composition
expected: Q(country='US') | Q(country='CA') creates an OR-connected filter tree that's readable
result: pass

### 3. Q-object AND composition
expected: Q(country='US') & Q(revenue__gt=1000) creates an AND-connected filter tree
result: pass

### 4. Q-object NOT composition
expected: ~Q(country='US') creates a negated filter that inverts the condition
result: pass

### 5. Query builder - select metrics
expected: Query().metrics(Sales.revenue, Sales.cost) returns a new Query with those metrics selected
result: pass

### 6. Query builder - select dimensions
expected: Query().dimensions(Sales.country, Sales.region) returns a new Query with those dimensions selected
result: pass

### 7. Query builder - filter with Q-objects
expected: Query().metrics(Sales.revenue).filter(Q(country='US') | Q(country='CA')) accepts Q-objects for filtering
result: pass

### 8. Query builder - order by
expected: Query().metrics(Sales.revenue).order_by(Sales.revenue) returns a Query with ordering specified
result: issue
reported: "How do we do reverse order by?"
severity: minor

### 9. Query builder - limit
expected: Query().metrics(Sales.revenue).limit(100) returns a Query with a row limit set
result: pass

### 10. Query immutability
expected: q1 = Query().metrics(Sales.revenue); q2 = q1.dimensions(Sales.country) → q1 unchanged, only q2has dimensions
result: pass

### 11. Query method chaining
expected: Query().metrics(Sales.revenue).dimensions(Sales.country).filter(Q(a=1)).order_by(Sales.revenue).limit(10) chains all methods and returns final Query
result: pass

### 12. Query export from package
expected: Can import Query and Q directly: from cubano import Query, Q (not from submodules)
result: pass

## Summary

total: 12
passed: 11
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Reverse order by is supported (descending sort capability)"
  status: failed
  reason: "User reported: How do we do reverse order by?"
  severity: minor
  test: 8
  artifacts: []
  missing: []
