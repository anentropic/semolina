# Phase 11: CI & Example Updates - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix CI workflows to validate all 459 tests including 16 doctests (removing `-m "mock or warehouse"` filter), and update cubano-jaffle-shop example to use Model-centric API (Model.query(), .execute(), no deprecated Query). This is infrastructure + example code update work, not a new feature.

</domain>

<decisions>
## Implementation Decisions

### Doctest Scope & Execution
- Doctest examples in docstrings must be explicitly marked (not all docstrings run as doctests)
- Doctest failures block the CI build (same severity as unit test failures)
- CI reporting shows separate count: "443 unit tests + 16 doctests = 459 total" (not just "459 passed")

### cubano-jaffle-shop Example Update
- Update all .py files in the example repository for consistency (ensure no mix of old Query API + new Model-centric API)
- Verification approach: code review only (manual review that code uses Model.query(), .execute(), no old Query API references)
- Updated code should be clean and self-documenting (no extra explanatory comments needed)

### CI Failure Reporting
- Doctest failures reported in a separate section from unit test failures (easier to identify doctest-specific issues)
- CI reporting includes detailed breakdown of test types and counts (not just aggregate "459 passed")

### Claude's Discretion
- Specific marker mechanism for doctests (pytest directives, custom prefix, special section, etc. — I'll choose standard Python approach)
- Doctest output verbosity in CI logs (full example + expected/actual output, or error-only — I'll use pytest's default doctest verbosity)

</decisions>

<specifics>
## Specific Ideas

- CI should show doctest count separately so it's clear we're validating documentation examples
- All files in cubano-jaffle-shop should be updated to prevent user confusion from seeing both old and new API in examples
- Failed doctests should be visibly distinguished in CI output (separate section) to help users debug documentation examples

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-ci-example-updates*
*Context gathered: 2026-02-17*
