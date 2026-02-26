# Phase 12: warehouse-testing-syrupy - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable real warehouse testing in CI without cost using snapshot-based recording/replay with syrupy. Tests record query results once locally against live warehouse, then replay those snapshots in CI to validate query behavior without warehouse connections.

</domain>

<decisions>
## Implementation Decisions

### Snapshot Recording Strategy
- Record automatically on first local run (snapshot file doesn't exist)
- Snapshots capture query results only (no execution metadata like timing or row counts)
- Automatically scrub credentials from snapshots before storage to prevent accidental secret leaks
- Use syrupy's standard directory structure: `__snapshots__/test_module.ambr` (human-readable YAML format)

### Fixture API Design
- Tests include `snapshot` fixture parameter in signature: `def test_query(snapshot):`
- Use syrupy's built-in behavior directly: developers run `pytest --snapshot-update` to record, `pytest` defaults to replay
- No warehouse test markers needed (all tests in this phase use snapshots)
- Fail fast with clear message when snapshot file is missing or stale (guides developer to `pytest --snapshot-update`)

### Sample Test Scope
- Demonstrate both Snowflake and Databricks backend compatibility (primary focus: SQL compatibility, no errors, expected semantics)
- Include query patterns with model relationships and metric aggregations (beyond simple SELECTs)
- Happy path only (error cases tested separately)
- Use synthetic test dataset for sample tests (isolated, simplified)

### CI & Snapshot Workflow
- Commit snapshot files to git (version control all recorded results)
- Developers run `pytest --snapshot-update` locally to create initial snapshots before committing
- Use standard git diff for snapshot changes in PRs (no custom diff tooling)
- Developer guide covers both workflow (how to add tests) and snapshot management (re-recording strategy, auditing changes, deprecation approach)

### Claude's Discretion
- Specific test patterns within the Snowflake/Databricks coverage scope
- Snapshot comparison logic and exact matching strategy
- Performance optimization of snapshot storage/comparison

</decisions>

<specifics>
## Specific Ideas

- **Re-recording Strategy:** Plan for how to bulk re-record snapshots when warehouse interface changes (query API updates, field renames, etc.)
- **Compatibility Validation:** SQL compatibility focus — sample tests validate that generated queries execute correctly on target backends with expected semantics, not edge cases

</specifics>

<deferred>
## Deferred Ideas

- Custom snapshot diff tooling (e.g., "X rows changed, Y values differ" summaries) — potential future enhancement
- Performance regression testing via snapshot metadata (execution time tracking) — separate phase if needed
- Snapshot versioning/expiry policies — evaluate if needed after Phase 12 is stable

</deferred>

---

*Phase: 12-warehouse-testing-syrupy*
*Context gathered: 2026-02-17*
