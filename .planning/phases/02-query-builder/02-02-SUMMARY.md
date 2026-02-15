---
phase: 02-query-builder
plan: 02
subsystem: query-builder
tags: [query, immutability, method-chaining, fluent-api, tdd]

dependency_graph:
  requires:
    - "01-01: SemanticView base and Field descriptors for field type validation"
    - "02-01: Q-object filter composition for .filter() method"
  provides:
    - "Immutable Query class with fluent method chaining API"
    - "Type-validated field selection (.metrics, .dimensions, .order_by)"
    - "Filter composition via .filter(Q(...)) with AND combination"
    - "Query construction validation at execution time"
  affects:
    - "Phase 03: SQL generation will use Query structure"
    - "Phase 04: Query execution will use Query.fetch()"
    - "Public API: Query and Q now exported from cubano package"

tech_stack:
  added:
    - "dataclasses.replace() for immutable copy-with-changes pattern"
    - "frozen dataclass for immutability guarantee"
    - "tuple storage for field collections (immutable)"
  patterns:
    - "Fluent API: each method returns new Query instance"
    - "Deferred validation: queries validated at execution, not construction"
    - "Runtime type checking: isinstance() for descriptor validation"
    - "Helpful error messages with 'Did you mean...?' guidance"

key_files:
  created:
    - path: "src/cubano/query.py"
      lines: 238
      purpose: "Immutable Query builder with method chaining"
    - path: "tests/test_query.py"
      lines: 351
      purpose: "Comprehensive tests for Query behavior and immutability"
  modified:
    - path: "src/cubano/__init__.py"
      changes: "Export Query and Q for public API"

decisions:
  - decision: "Use Any for method parameters instead of specific types"
    rationale: "Type hints on variadic args aren't enforced at runtime; isinstance checks provide runtime validation without basedpyright false positives"
    alternatives: "Could use specific types with pyright exemptions"
    impact: "Cleaner type checking, explicit runtime validation in method bodies"

  - decision: "Ternary operator for filter combination"
    rationale: "Linter prefers ternary over if-else for simple assignments"
    alternatives: "if-else block (more verbose but readable)"
    impact: "More concise code, passes ruff checks"

  - decision: "Deferred validation in _validate_for_execution()"
    rationale: "Allows composability during construction, validates only when executing"
    alternatives: "Validate at construction time (breaks incremental building)"
    impact: "Better DX for query building, fail-fast at execution"

metrics:
  tests_added: 40
  tests_total: 96
  test_files: 3
  duration_minutes: 3.4
  completed: "2026-02-15T11:58:53Z"
---

# Phase 2 Plan 2: Immutable Query Builder - Summary

Immutable Query class with fluent method chaining using frozen dataclasses and dataclasses.replace()

## What Was Built

Implemented the core Query builder class that provides the user-facing API for constructing queries. The Query class is a frozen dataclass that uses `dataclasses.replace()` to return new instances on every method call, guaranteeing immutability. It supports:

- **Metrics selection**: `.metrics(Sales.revenue, Sales.cost)` - validates Metric fields only
- **Dimensions selection**: `.dimensions(Sales.country, Sales.unit_price)` - accepts Dimension and Fact fields
- **Filter composition**: `.filter(Q(country='US') | Q(country='CA'))` - combines with AND when called multiple times
- **Ordering**: `.order_by(Sales.revenue, Sales.country)` - accepts any Field type
- **Limiting**: `.limit(100)` - validates positive integers only
- **Method chaining**: All methods return new Query instances for fluent API
- **Execution validation**: Empty queries are allowed during construction but fail at `.fetch()` or `.to_sql()` time

The implementation uses runtime `isinstance()` checks to validate field types (since type hints on descriptors aren't enforced at runtime) and provides helpful error messages like "Did you mean .dimensions()?" when users pass the wrong field type.

## Implementation Details

**Query Structure:**
- Frozen dataclass with 5 private fields (all immutable: tuples and optional Q object)
- `_metrics`: tuple of Metric fields
- `_dimensions`: tuple of Dimension/Fact fields
- `_filters`: Q object or None (ANDed together on multiple .filter() calls)
- `_order_by_fields`: tuple of Field objects
- `_limit_value`: optional positive integer

**Key Patterns:**
- `dataclasses.replace()` for copy-with-changes (immutability)
- Runtime type validation with `isinstance()` on all methods
- Deferred validation via `_validate_for_execution()` (called by `.fetch()` and `.to_sql()`)
- Ternary operator for filter combination (linter preference)
- `Any` type hints on parameters (runtime validation is explicit in method bodies)

**Test Coverage:**
- 40 tests across 9 test classes
- Covers: metrics, dimensions, filter, order_by, limit, immutability, chaining, validation, stubs
- All quality gates pass: basedpyright (0 errors), ruff check (0 errors), ruff format (9 files formatted)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test model missing view parameter**
- **Found during:** GREEN phase test execution
- **Issue:** TestQueryTests.Sales model failed with "must specify a view parameter"
- **Fix:** Added `view="sales_view"` parameter to Sales model definition
- **Files modified:** tests/test_query.py
- **Commit:** b9c9892 (GREEN commit)

**2. [Rule 1 - Bug] Type checker false positives on isinstance checks**
- **Found during:** Quality gate (basedpyright) checks
- **Issue:** basedpyright flagged isinstance checks as "unnecessary" because type hints suggested types were already validated
- **Fix:** Changed method parameter types from specific (e.g., `*fields: Metric`) to `Any` to reflect that runtime validation is needed
- **Files modified:** src/cubano/query.py
- **Commit:** b9c9892 (GREEN commit)

**3. [Rule 2 - Critical] Linter preference for ternary operator**
- **Found during:** Quality gate (ruff check)
- **Issue:** SIM108 - ruff prefers ternary operator for simple if-else assignments
- **Fix:** Converted filter combination if-else to ternary: `condition if self._filters is None else self._filters & condition`
- **Files modified:** src/cubano/query.py
- **Commit:** b9c9892 (GREEN commit)

**4. [Rule 2 - Critical] Blind exception catching in test**
- **Found during:** Quality gate (ruff check)
- **Issue:** B017 - test catching blind `Exception` type instead of specific types
- **Fix:** Changed to `pytest.raises((AttributeError, TypeError))` for frozen dataclass modification test
- **Files modified:** tests/test_query.py
- **Commit:** b9c9892 (GREEN commit)

**5. [Rule 2 - Critical] Missing type annotation for fetch() return type**
- **Found during:** Quality gate (basedpyright)
- **Issue:** fetch() returned `list` without type argument (reportMissingTypeArgument)
- **Fix:** Changed return type from `list` to `list[Any]` (Phase 4 will provide concrete row type)
- **Files modified:** src/cubano/query.py
- **Commit:** b9c9892 (GREEN commit)

All deviations were auto-fixed during GREEN phase quality gate checks. No architectural changes were required.

## TDD Execution Flow

**RED Phase (Commit 19a3010):**
- Created 40 failing tests in tests/test_query.py
- Tests covered all success criteria from plan
- Module didn't exist yet (ModuleNotFoundError as expected)

**GREEN Phase (Commit b9c9892):**
- Implemented Query class in src/cubano/query.py (238 lines)
- Updated __init__.py to export Query and Q
- Fixed test model definition (added view parameter)
- Fixed type checker issues (Any types for parameters)
- Fixed linter issues (ternary operator, specific exception types)
- All 96 tests pass (40 new + 56 existing)
- All quality gates pass

**REFACTOR Phase:**
- Not needed - code was clean after GREEN phase
- Implementation follows best practices from 02-RESEARCH.md
- No code smells or duplication detected

## Verification Results

```bash
uv run --extra dev pytest tests/test_query.py tests/test_filters.py -v
# 68 passed in 0.03s

uv run --extra dev pytest -v
# 96 passed in 0.05s

uv run basedpyright
# 0 errors, 0 warnings, 0 notes

uv run ruff check
# All checks passed!

uv run ruff format --check
# 9 files already formatted
```

All success criteria met:
- [x] .metrics() accepts only Metric fields, raises TypeError for others
- [x] .dimensions() accepts Dimension and Fact fields, raises TypeError for Metric
- [x] .filter() accepts Q objects, ANDs multiple filters
- [x] .order_by() accepts any Field subclass
- [x] .limit() accepts positive integers only
- [x] Every method returns a NEW Query (frozen dataclass immutability)
- [x] Original Query is unchanged after method calls
- [x] Method chaining works end to end
- [x] _validate_for_execution() rejects empty queries
- [x] Query and Q are exported from cubano package

## Files Changed

**Created:**
- `src/cubano/query.py` - Query class implementation (238 lines)
- `tests/test_query.py` - Comprehensive test suite (351 lines, 40 tests)

**Modified:**
- `src/cubano/__init__.py` - Export Query and Q in __all__

**Git Log:**
```
b9c9892 feat(02-02): implement immutable Query builder
19a3010 test(02-02): add failing tests for Query builder
```

## Next Steps

**Phase 3 (SQL Generation):**
- Implement `Query.to_sql()` using Query structure
- Generate SELECT, GROUP BY, WHERE, ORDER BY, LIMIT clauses
- Handle metric aggregation and dimension grouping
- Compile Q-object tree to WHERE clause with proper precedence

**Phase 4 (Query Execution):**
- Implement `Query.fetch()` to execute queries
- Return typed result rows
- Connect to warehouse backends (Snowflake/Databricks)

The Query foundation is complete and ready for SQL generation.

## Self-Check: PASSED

**Created files exist:**
```bash
[ -f "src/cubano/query.py" ] && echo "FOUND: src/cubano/query.py"
# FOUND: src/cubano/query.py

[ -f "tests/test_query.py" ] && echo "FOUND: tests/test_query.py"
# FOUND: tests/test_query.py

[ -f ".planning/phases/02-query-builder/02-02-SUMMARY.md" ] && echo "FOUND: .planning/phases/02-query-builder/02-02-SUMMARY.md"
# FOUND: .planning/phases/02-query-builder/02-02-SUMMARY.md
```

**Commits exist:**
```bash
git log --oneline --all | grep -q "19a3010" && echo "FOUND: 19a3010"
# FOUND: 19a3010

git log --oneline --all | grep -q "b9c9892" && echo "FOUND: b9c9892"
# FOUND: b9c9892
```

**Test counts match:**
- Expected: 40 new tests for Query
- Actual: 40 tests in test_query.py (verified by test run)
- Total: 96 tests across all modules (verified by full test run)

**Quality gates:**
- basedpyright: 0 errors ✓
- ruff check: All checks passed ✓
- ruff format: 9 files formatted ✓
- pytest: 96/96 passed ✓

All verification checks passed.
