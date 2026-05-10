# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.3 — Arrow & Connection Layer

**Shipped:** 2026-04-18
**Phases:** 8 | **Plans:** 16 | **Commits:** 59

### What Was Built
- Pool-based connection layer replacing Engine ABC with adbc-poolhouse pools and Dialect enum
- SemolinaCursor with DBAPI 2.0 compliance and Row convenience methods (fetchall_rows, fetchone_row, fetchmany_rows)
- TOML configuration with pool_from_config() factory for zero-boilerplate connection setup
- Query shorthand kwargs (metrics=, dimensions=) additive with builder methods
- MockPool for testing without warehouse connections
- Full documentation migration from MkDocs Material to Sphinx + shibuya theme with sphinx-autoapi

### What Worked
- TDD approach for core API changes (phases 25-28) — tests written first, implementation followed
- Backward compatibility via DeprecationWarning on old Engine API — no breaking changes for existing users during transition
- Phase 30 (Sphinx migration) was well-scoped — 4 plans with clear content boundaries (scaffold, tutorials, how-tos, CI)
- Milestone audit caught real gaps (DOCS-03 partial coverage, stale engine terminology) that phases 31-32 closed

### What Was Inefficient
- Phase 32 tech debt could have been caught during phase 25 execution rather than requiring a separate cleanup phase
- Some SUMMARY.md frontmatter fields (requirements-completed) were not consistently filled, requiring audit to cross-reference VERIFICATION.md files
- Integration test conftest still uses deprecated register() API — tech debt carried forward

### Patterns Established
- Pool+dialect registry pattern: `register(name, pool, dialect=)` separates transport (pool) from SQL generation (dialect)
- SemolinaCursor delegation pattern: wraps any DBAPI 2.0 cursor, adds Row convenience without subclassing
- Sphinx + shibuya with Diataxis tabs as documentation standard
- sphinx-autoapi for zero-maintenance API reference generation

### Key Lessons
1. Milestone audits are valuable — they caught doc accuracy issues and stale terminology that would have shipped otherwise
2. Backward compatibility layers (DeprecationWarning paths) add complexity but smooth the migration for users
3. Documentation migrations are large-scope work — Phase 30 alone was 4 plans converting 16 content pages

### Cost Observations
- Model mix: primarily opus for planning/execution, sonnet for research agents
- Sessions: spread across multiple sessions over 33 days
- Notable: gap closure phases (31, 32) were small and fast — 1 plan each, focused scope

---

## Milestone: v0.4.0 — DuckDB Backend & Arrow Output

**Shipped:** 2026-05-07
**Phases:** 6 | **Plans:** 12 | **Commits:** 45 (phase-tagged)

### What Was Built
- DuckDB as a first-class backend (Dialect.DUCKDB, DuckDBSQLBuilder, `semolina[duckdb]` extra)
- `fetch_arrow_table()` on SemolinaCursor — pyarrow.Table return, zero-copy bridge to Pandas/Polars
- DuckDB extension auto-loading (`INSTALL/LOAD semantic_views`) via SQLAlchemy `pool.connect` event
- Full MockPool removal — tests now run on real DuckDB in-memory pools
- DuckDB reverse codegen (`semolina codegen --backend duckdb --database <path>`) with 21 SQL types mapped
- Three-backend documentation across how-tos, reference, and overview pages with synchronised tab-sets

### What Worked
- Phase 33 + 34 designed as independent — could have parallelised; structure kept the option open
- Native `duckdb` driver for codegen vs ADBC for queries — clean tooling/runtime split, no cross-dep
- TDD approach again for SQL builder (33-01) and Arrow output (34-01) — failing tests committed first per CLAUDE.md
- Pool `connect` event listener for extension loading — zero per-query overhead, transparent to users
- Phase 38 cleanly closed the audit's open SC4 once the upstream `duckdb-semantic-views` 0.8.0 fix landed — milestone audit re-ran from `gaps_found` to `passed`

### What Was Inefficient
- Phases 33–35 had their planning artifacts (PLAN/SUMMARY/RESEARCH/VERIFICATION) bulk-deleted in commit `2933df2` — audits had to fall back to code spot-checks, no traceable verification trail
- REQUIREMENTS.md traceability table stayed `Pending` for all 18 entries during execution; only refreshed on archival
- Cross-phase integration audit (`/gsd-audit-uat`) skipped — de facto verified by 924 tests + doc build, but no structured run
- ARROW-02 requirement text named the API `to_arrow()` while the shipped name (`fetch_arrow_table()`) was decided mid-flight — caused a naming reconciliation note in audit and docs
- Phase 38 existed because a packaging refactor mid-milestone dropped the `[duckdb]` extra — should have been caught by a packaging smoke test in CI

### Patterns Established
- DuckDB SQL builder overrides `build_select_with_params()` entirely (table-function dialects need full control)
- SQLAlchemy `pool.connect` event for one-time per-connection setup (extension loading, session pragmas)
- Backend-specific tab-items with `:sync: <backend>` in shared `:sync-group: warehouse` tab-sets
- Native driver for codegen, ADBC for runtime — codegen is offline, no need for the pool layer
- Audit-then-close pattern — initial audit can flag a gap pending upstream, then re-run after closure to flip to PASSED

### Key Lessons
1. Don't bulk-delete completed phase planning artifacts mid-milestone. The verification trail is the audit's first line of defence; losing it forces code spot-checks and weakens future retrospectives.
2. Refresh REQUIREMENTS.md traceability as phases land, not at archive time. Leaving 18 entries stuck on `Pending` made it harder to read mid-milestone status.
3. Packaging changes need their own smoke test. The `[duckdb]` extra silently went missing in a refactor and only surfaced via the audit.
4. Requirement text and shipped API name should be kept in lock-step. `to_arrow()` → `fetch_arrow_table()` was a small decision but echoed through docs, audit, and traceability.

### Cost Observations
- Model mix: opus for orchestration/planning, sonnet for research and code-light passes
- Sessions: spread across 18 days
- Notable: Phase 38 was a single-plan gap-closure phase that materially improved the audit verdict — small phases that close audit gaps are high-leverage

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Plans | Key Change |
|-----------|---------|--------|-------|------------|
| v0.1 | ~50 | 7 | 18 | Initial build |
| v0.2 | ~429 | 20 | 66 | Tooling explosion, decimal phases introduced |
| v0.3 | 59 | 8 | 16 | Focused API evolution, doc platform migration |
| v0.4.0 | 45 | 6 | 12 | Third backend (DuckDB), Arrow output, MockPool retired |

### Top Lessons (Verified Across Milestones)

1. TDD catches design issues early — validated in v0.1 (MockEngine), v0.2 (predicates), v0.3 (pool registry), v0.4.0 (DuckDB SQL builder + fetch_arrow_table)
2. Documentation phases should follow API phases, not be interleaved — validated in v0.2, v0.3, and v0.4.0 (Phase 37 sat at the end of the API work)
3. Milestone audits before completion catch real gaps — introduced in v0.3; in v0.4.0 the audit identified SC4 as deferred-pending-upstream and the closure phase (38) flipped it to PASSED
4. Don't bulk-delete completed phase artifacts — new lesson from v0.4.0 (commit `2933df2` lost three phases' verification trails)
5. Keep requirement text in sync with shipped API names — small renames echo through docs, traceability, and audit notes
