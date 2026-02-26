# Phase 8: Integration Testing - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can write and run integration tests against real Snowflake/Databricks warehouses, with pytest fixtures handling credential management, data isolation, and parallel execution safely. Tests validate query behavior including field combinations, filtering, ordering, and edge cases. Includes both mock-based tests (fast feedback) and real warehouse tests (confidence in actual behavior).

</domain>

<decisions>
## Implementation Decisions

### Credential Handling
- Smart credential loader with fallback chain: env vars → .env file → config file → prompt
- Loader searches standard locations to improve developer experience
- Credentials cached in memory during test session (Claude's discretion on timing strategy)
- Validation deferred to first test execution (Claude's discretion — balances feedback with startup speed)

### Test Suite Structure (Mock vs Real Warehouse)
- Mixed suite: both mock tests and real warehouse tests in the same codebase
- **Mock tests:** Focus on query builder logic and basic model validation (fast feedback)
- **Real warehouse tests:** Focus on field combinations, ordering, filtering, edge cases, and actual SQL validation
- MockEngine provides realistic result shapes and data sizes to mimic warehouse behavior
- Real warehouse tests are marked and opt-in locally (`pytest -m [marker]` — marker name is Claude's discretion)
  - Local development: mock tests run by default, real warehouse tests require explicit marker flag
  - CI/PR: all tests run (mock + real warehouse)
- Cost-aware: developers can iterate locally with mocks; CI validates against real warehouses

### Claude's Discretion
- Specific pytest marker semantics for real warehouse tests
- Test fixture architecture (module-level vs session-level vs function-level)
- Data isolation strategy for parallel execution (separate schemas per test? Temp tables with rollback?)
- Credential caching implementation details
- Credential validation timing and error handling

</decisions>

<specifics>
## Specific Ideas

- Real warehouse tests should be recognizable and easy to skip locally without breaking workflow
- Fixture setup should be transparent — developers understand what's being isolated and how
- Mock test data should be realistic enough to catch SQL generation bugs (e.g., type mismatches, aggregation errors)

</specifics>

<deferred>
## Deferred Ideas

- Scheduled integration test runs against production warehouse — future ops enhancement
- Performance profiling and benchmarking of generated queries — Phase 10+ (documentation of performance patterns)
- Multi-database fixture composition — can add if needed in future phases

</deferred>

---

*Phase: 08-integration-testing*
*Context gathered: 2026-02-17*
