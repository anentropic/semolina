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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Key Change |
|-----------|---------|--------|------------|
| v0.1 | ~50 | 7 | Initial build, 18 plans |
| v0.2 | ~429 | 20 | Tooling explosion, decimal phases introduced |
| v0.3 | 59 | 8 | Focused API evolution, doc platform migration |

### Top Lessons (Verified Across Milestones)

1. TDD catches design issues early — validated in v0.1 (MockEngine), v0.2 (predicates), v0.3 (pool registry)
2. Documentation phases should follow API phases, not be interleaved — validated in v0.2 and v0.3
3. Milestone audits before completion catch real gaps — introduced in v0.3, will carry forward
