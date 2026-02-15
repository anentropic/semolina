# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Phase 3 - SQL Generation & Mock Backend

## Current Position

Phase: 3 of 7 (SQL Generation & Mock Backend) — IN PROGRESS
Plan: 1 of 4 executed (03-01)
Status: Engine ABC & Dialect architecture complete
Last activity: 2026-02-15 — 03-01 complete, Engine and Dialect ABC ready for SQL generator

Progress: [███████░░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 3.70 min
- Total execution time: 0.31 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-model-foundation | 1 | 3min | 3min |
| 02-query-builder | 3 | 11.08min | 3.69min |
| 03-sql-generation-mock-backend | 1 | 12min | 12min |

**Recent Trend:**
- Last 5 plans: 3.4min, 3.93min, 12min (03-01 longer due to architecture)
- Trend: Baseline ~3.5 min/plan, 03-01 architectural setup took 12min

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Metaclass over decorator for models — cleaner syntax for ORM-style classes
- Field refs only, no strings — enforces type safety, enables IDE autocomplete
- Mock backend first — build and test entire design before real warehouse backends
- **[01-01]** Use metaclass (SemanticViewMeta) instead of __init_subclass__ alone for __setattr__ interception
- **[01-01]** Validate field names in __set_name__ to catch errors at class definition time
- **[01-01]** Store metadata in MappingProxyType for immutability guarantees
- **[02-01]** Q.__new__() over Q() for branch node creation to bypass __init__
- **[02-01]** Sorted kwargs.items() for deterministic Q-object equality
- **[02-02]** Use Any for method parameters instead of specific types - type hints on variadic args aren't enforced at runtime; isinstance checks provide runtime validation
- **[02-02]** Deferred validation in _validate_for_execution() - allows composability during construction, validates only when executing
- **[02-03]** Descriptor methods (.asc()/.desc()) over separate classes - more Pythonic, matches SQLAlchemy
- **[02-03]** NullsOrdering enum over string literals - type safety and IDE autocomplete
- **[02-03]** OrderTerm as frozen dataclass - immutability aligns with Query immutability
- **[02-03]** Optional nulls parameter with DEFAULT enum value - backward compatible, explicit intent
- **[03-01]** Dialect pattern for backend-specific SQL rules - each backend gets Dialect class for quote_identifier() and wrap_metric() instead of centralized config
- **[03-01]** TYPE_CHECKING imports for Engine ABC - avoids circular dependency with Query module while maintaining type safety
- **[03-01]** MockDialect uses Snowflake syntax (double quotes, AGG()) - simplifies MockEngine and enables consistent test SQL generation

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-15
Stopped at: Phase 3 Plan 1 (03-01) complete, Engine ABC and Dialect architecture ready for SQL generator (03-02)
Resume file: None
