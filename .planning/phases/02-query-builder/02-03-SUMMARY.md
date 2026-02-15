---
phase: 02-query-builder
plan: 03
subsystem: query-builder
tags: [ordering, nulls-handling, orderterm, descriptor-methods, frozen-dataclass]

# Dependency graph
requires:
  - phase: 02-query-builder
    provides: Immutable Query builder with method chaining
provides:
  - OrderTerm frozen dataclass with field, descending, and nulls attributes
  - NullsOrdering enum (FIRST, LAST, DEFAULT) for NULL positioning control
  - Field.asc() and Field.desc() descriptor methods with optional nulls parameter
  - Query.order_by() accepting both bare Field and OrderTerm instances
affects: [03-sql-generation, phase-3]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Descriptor methods for fluent ordering API (field.desc(), field.asc())
    - Enum-based configuration for NULL handling (NullsOrdering)
    - Frozen dataclass wrapper pattern for field metadata (OrderTerm)

key-files:
  created: []
  modified:
    - src/cubano/fields.py
    - src/cubano/query.py
    - src/cubano/__init__.py
    - tests/test_fields.py
    - tests/test_query.py

key-decisions:
  - "Use descriptor methods (.asc()/.desc()) instead of separate Asc/Desc classes - more Pythonic, matches SQLAlchemy"
  - "NullsOrdering enum over string literals - type safety and IDE autocomplete"
  - "OrderTerm as frozen dataclass - immutability aligns with Query immutability"
  - "Optional nulls parameter with DEFAULT enum value - backward compatible, explicit intent"

patterns-established:
  - "Descriptor wrapper pattern: Field methods return wrapper objects (OrderTerm) for enhanced behavior"
  - "Enum-based configuration: NullsOrdering.FIRST/LAST/DEFAULT for explicit NULL positioning"
  - "Mixed type acceptance: Query.order_by() accepts both Field and OrderTerm for flexibility"

# Metrics
duration: 3.93min
completed: 2026-02-15
---

# Phase 02-query-builder Plan 03: OrderTerm with Descending and NULLS Handling

**OrderTerm frozen dataclass with .desc()/.asc() descriptor methods and NullsOrdering enum for per-column direction and NULL positioning control**

## Performance

- **Duration:** 3.93 min
- **Started:** 2026-02-15T12:28:30Z
- **Completed:** 2026-02-15T12:32:26Z
- **Tasks:** 2 (TDD: RED → GREEN)
- **Files modified:** 5

## Accomplishments
- Developers can order descending via `.order_by(Sales.revenue.desc())`
- Developers can control NULL positioning via `.order_by(Sales.revenue.desc(NullsOrdering.FIRST))`
- Mixed directions and NULL handling in single `.order_by()` call supported
- Backward compatible - bare fields still work: `.order_by(Sales.revenue)`
- OrderTerm and NullsOrdering exported from cubano package
- All quality gates pass (113 tests, basedpyright, ruff)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED - Write failing tests for OrderTerm and descending order_by** - `acc51a4` (test)
2. **Task 2: GREEN - Implement OrderTerm, Field.asc()/desc(), and update Query.order_by()** - `2148747` (feat)

_TDD flow: RED phase established 17 failing tests, GREEN phase made all pass_

## Files Created/Modified

- `src/cubano/fields.py` - Added NullsOrdering enum, OrderTerm frozen dataclass, Field.asc()/desc() methods
- `src/cubano/query.py` - Updated order_by() to accept Field | OrderTerm, updated _order_by_fields type
- `src/cubano/__init__.py` - Exported OrderTerm and NullsOrdering in __all__
- `tests/test_fields.py` - Added TestFieldOrdering class with 8 tests
- `tests/test_query.py` - Added 9 tests for descending/NULLS handling in TestQueryOrderBy and TestQueryChaining

## Decisions Made

1. **Descriptor methods over separate classes**: `.asc()` and `.desc()` on Field instead of `Asc(field)` - more Pythonic, matches SQLAlchemy convention
2. **NullsOrdering enum with DEFAULT value**: Enum provides type safety and autocomplete, DEFAULT value makes nulls parameter optional
3. **OrderTerm as frozen dataclass**: Aligns with Query's immutability pattern, prevents accidental modification
4. **Mixed type acceptance**: Query.order_by() accepts both Field and OrderTerm for backward compatibility and flexibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tests passed on first GREEN implementation, all quality gates passed immediately after linting fixes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Gap closure complete: UAT Test 8 ("How do we do reverse order by?") now resolved
- Phase 2 (Query Builder) fully complete with all ordering capabilities
- Ready for Phase 3 (SQL Generation) to compile OrderTerm into backend-specific ORDER BY ... DESC NULLS FIRST/LAST syntax
- Query builder API surface area complete and stable

## Self-Check

Verifying all claims in this summary:

**Files exist:**
- src/cubano/fields.py: ✓ Contains NullsOrdering enum, OrderTerm dataclass, Field.asc()/desc()
- src/cubano/query.py: ✓ Contains updated order_by() accepting Field | OrderTerm
- src/cubano/__init__.py: ✓ Exports OrderTerm and NullsOrdering

**Commits exist:**
- acc51a4: ✓ test(02-03): add failing tests for OrderTerm
- 2148747: ✓ feat(02-03): implement OrderTerm with NullsOrdering enum

**Tests:**
- 113 tests pass (96 existing + 17 new): ✓ Confirmed in final test run

**Quality gates:**
- basedpyright: ✓ 0 errors
- ruff check: ✓ All checks passed
- ruff format: ✓ 9 files already formatted

**Self-Check: PASSED**

---
*Phase: 02-query-builder*
*Completed: 2026-02-15*
