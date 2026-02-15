# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Phase 5 - Snowflake Backend

## Current Position

Phase: 5 of 7 (Snowflake Backend) — IN PROGRESS
Plan: 2 of 5 executed (05-02)
Status: SnowflakeEngine complete with comprehensive unit tests - all mocked, no warehouse required
Last activity: 2026-02-15 — Completed Phase 05 Plan 02: SnowflakeEngine testing (5.75min)

Progress: [████████████████] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 4.06 min
- Total execution time: 0.88 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-model-foundation | 1 | 3min | 3min |
| 02-query-builder | 3 | 11.08min | 3.69min |
| 03-sql-generation-mock-backend | 5 | 46min (03-01: 12min, 03-02: 5min, 03-03: 12min, 03-04: 12min, 03-05: 5min) | 9.2min |
| 04-execution-results | 3 | 8min (04-02: 1.63min, 04-01: 1.61min, 04-03: 4.76min) | 2.67min |
| 05-snowflake-backend | 2 | 7.78min (05-01: 2.03min, 05-02: 5.75min) | 3.89min |

**Recent Trend:**
- Last 4 plans: 4.76min (04-03 execution pipeline), 2.03min (05-01 SnowflakeEngine), 5.75min (05-02 SnowflakeEngine tests)
- Trend: Implementation plans ~2min, test-heavy plans ~5min

*Updated after each plan completion*
| Phase 05-snowflake-backend P02 | 5.75 | 1 tasks | 1 files |

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
- **[03-05]** Remove fixtures parameter from MockEngine constructor - decouples testing from production API, use pytest fixtures for test data injection
- **[03-05]** MockEngine.execute() raises NotImplementedError in gap closure - real execution deferred to Phase 4+ with real backends
- [Phase 04-02]: Module-level state (_engines dict) for singleton registry pattern
- [Phase 04-02]: Silent no-op for unregister() on missing name (forgiving API)
- [Phase 04-01]: object.__setattr__ for _data initialization to bypass immutability
- [Phase 04-01]: Defensive copy in __init__ to prevent external mutation
- [Phase 04-01]: AttributeError with available fields list for better debugging
- [Phase 04-01]: Full dict protocol support for ergonomic iteration
- [Phase 04-03]: Query.using() stores engine name (string) not instance - enables lazy resolution
- [Phase 04-03]: MockEngine.load() separates test fixture injection from constructor
- [Phase 04-03]: Autouse fixture (clean_registry) prevents test state leakage
- [Phase 05-01]: Lazy import snowflake.connector only on instantiation - prevents ImportError for users without driver
- [Phase 05-01]: Store connection params in __init__, defer connection to execute() time - avoids expensive connection during setup
- [Phase 05-01]: Use context managers for connection lifecycle - guarantees cleanup even on exceptions
- [Phase 05-01]: Translate Snowflake errors to RuntimeError - consistent with Engine ABC error handling contract
- [Phase 05-01]: strict=True for zip() in result mapping - ensures column count matches row tuple length
- [Phase 05-02]: Use sys.modules patching for lazy import testing
- [Phase 05-02]: Mock snowflake.connector at connection level for testing without warehouse credentials

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Capture and document code style preferences for future work | 2026-02-15 | 495a751 | [1-capture-and-document-code-style-preferen](.planning/quick/1-capture-and-document-code-style-preferen/) |

## Session Continuity

Last session: 2026-02-15
Completed: Phase 5 Plan 2 (05-02) - SnowflakeEngine comprehensive unit tests
Resume file: None
Next: Continue Phase 5 - Integration testing (05-03)
