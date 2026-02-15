# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Phase 3 - SQL Generation & Mock Backend

## Current Position

Phase: 3 of 7 (SQL Generation & Mock Backend) — IN PROGRESS
Plan: 3 of 4 executed (03-01, 03-02, 03-03)
Status: MockEngine complete, Phase 3 testing infrastructure ready
Last activity: 2026-02-15 — 03-03 complete, MockEngine enables local query testing with fixtures

Progress: [█████████░░░░] 64%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 4.15 min
- Total execution time: 0.48 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-model-foundation | 1 | 3min | 3min |
| 02-query-builder | 3 | 11.08min | 3.69min |
| 03-sql-generation-mock-backend | 3 | 29min (03-01: 12min, 03-02: 5min, 03-03: 12min) | 9.67min |

**Recent Trend:**
- Last 3 plans: 12min (03-01 architecture), 5min (03-02 SQL generation), 12min (03-03 testing engine)
- Trend: Phase 3 complex architecture and testing infrastructure taking longer than Phase 2 baseline (~3.7min/plan)

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
- **[03-02]** SQLBuilder uses composable string building (not AST) - simpler for known query structure, easier to reason about
- **[03-02]** WHERE placeholder for Phase 4 - Q-object rendering complex, requires separate filter compiler
- **[03-02]** Query.to_sql() uses MockDialect by default - enables inspection/debugging without backend specification
- **[03-02]** GROUP BY ALL for automatic dimension derivation - both Snowflake and Databricks compatible, simpler than manual listing
- **[03-02]** SQLBuilder composable string builder pattern (not AST) - cleaner for known query structure, avoids AST parsing overhead
- **[03-02]** Query.to_sql() uses MockDialect by default - enables inspection/debugging without specifying backend
- **[03-03]** MockEngine returns raw fixture data in Phase 3 - full filtering/aggregation validation deferred to Phase 4-6 with real backends
- **[03-03]** Use Any for Query parameters in SQLBuilder/MockEngine - prevents circular imports while maintaining runtime safety via duck typing
- **[03-03]** Row class deferred to Phase 4 - documented in Engine ABC but not implemented yet, maintains backward compatibility

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-15
Stopped at: Phase 3 Plan 3 (03-03) complete - MockEngine testing engine with fixture support
Resume file: None
Next: Phase 3 Plan 4 (03-04) — Integration tests, or Phase 4 (Result handling / Row class)
