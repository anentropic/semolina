# Milestones — Semolina

Complete project release history and major version achievements.

---

## Shipped Milestones

### v0.3 — Arrow & Connection Layer

**Status:** ✅ Shipped 2026-04-18
**Phases:** 25–32 (8 total)
**Plans:** 16 total

**What Was Shipped:**
Replaced the hand-rolled Engine ABC with adbc-poolhouse connection pools, evolved `.execute()` to return a `SemolinaCursor` with Arrow-native fetch methods, added TOML-based configuration, query shorthand arguments, and migrated documentation to Sphinx + shibuya theme.

**Key Accomplishments:**

1. **Pool-based connection layer** — Dialect StrEnum + pool registry replacing Engine ABC with full backward compatibility and deprecation path
2. **SemolinaCursor** — `.execute()` returns DBAPI 2.0 cursor with `fetchall_rows()`, `fetchone_row()`, `fetchmany_rows()` Row convenience methods
3. **TOML configuration** — `.semolina.toml` config with `pool_from_config()` factory creating ready-to-register pool+dialect tuples via adbc-poolhouse
4. **Query shorthand** — `query(metrics=..., dimensions=...)` keyword args additive with builder methods
5. **MockPool** — DBAPI 2.0-compatible mock pool for testing without warehouse connections
6. **Sphinx documentation migration** — Full site migration from MkDocs Material to Sphinx + shibuya theme with RST, sphinx-autoapi, and tab synchronization

**Requirements Coverage:** 18/18 (100%)

- Connection Layer (CONN-01–04): ✅ Complete
- Cursor & Results (CURS-01–05): ✅ Complete
- Configuration (CONF-01–03): ✅ Complete
- Query API (QAPI-01–02): ✅ Complete
- Documentation (DOCS-01–04): ✅ Complete

**Quality Metrics:**

- Type checking: basedpyright strict mode — 0 errors
- Code quality: ruff linting and formatting — all passing
- Timeline: 33 days (2026-03-16 → 2026-04-18), 59 commits
- Files modified: 158 (+19,034 / -4,589)

**Archive Files:**

- `.planning/milestones/v0.3-ROADMAP.md` — Full phase details
- `.planning/milestones/v0.3-REQUIREMENTS.md` — All requirements marked complete
- `.planning/milestones/v0.3-MILESTONE-AUDIT.md` — Verification report

---

### v0.1 — MVP

**Status:** ✅ Shipped 2026-02-16
**Phases:** 1-7 (7 total)
**Plans:** 18 total

**What Was Shipped:**
A complete Python ORM for querying data warehouse semantic views with type-safe models, fluent query builder, and multi-backend support (Snowflake and Databricks).

**Key Accomplishments:**

1. **Typed Models:** Semantic view models via metaclass with field descriptors (Metric, Dimension, Fact)
2. **Query Builder:** Fluent, immutable query construction with Q-object filtering and ordering
3. **SQL Generation:** Backend-specific SQL compilation (AGG for Snowflake, MEASURE for Databricks)
4. **Execution Layer:** Query execution with Row objects supporting attribute and dict-style access
5. **Multi-Backend Support:** SnowflakeEngine and DatabricksEngine with lazy driver imports
6. **Production Packaging:** Zero required dependencies, optional backend extras, py.typed marker

**Requirements Coverage:** 32/32 (100%)

- Models (MOD-01–05): ✅ Complete
- Query Builder (QRY-01–08): ✅ Complete
- SQL Generation (SQL-01–05): ✅ Complete
- Execution & Results (EXE-01–03): ✅ Complete
- Engine Interface (ENG-01–02): ✅ Complete
- Snowflake Backend (ENG-03): ✅ Complete
- Databricks Backend (ENG-04): ✅ Complete
- Registry (REG-01–03): ✅ Complete
- Packaging (PKG-01–04): ✅ Complete

**Quality Metrics:**

- Test coverage: 265 tests passing
- Type checking: basedpyright strict mode — 0 errors
- Code quality: ruff linting and formatting — all passing
- Lines of code: 2,210 Python
- Execution time: 1.09 hours (18 plans at 3.62 min average)

**Archive Files:**

- `.planning/milestones/v0.1-ROADMAP.md` — Full phase details
- `.planning/milestones/v0.1-REQUIREMENTS.md` — All requirements marked complete
- `.planning/v0.1-MILESTONE-AUDIT.md` — Verification report

*Milestone history created: 2026-02-16*
*See PROJECT.md for project vision and context*

---

### v0.2 — Tooling & Documentation

**Status:** ✅ Shipped 2026-02-26
**Phases:** 8–24 (20 total, including decimal phases 10.1, 13.1, 20.1)
**Plans:** 66 total

**What Was Shipped:**
Developer tooling, integration testing, and comprehensive documentation: a model-centric query API, type-safe filter predicates with SQL compilation, snapshot-based warehouse testing, reverse codegen CLI, and a full MkDocs documentation site.

**Key Accomplishments:**

1. **Model-centric query API** — `Model.query()` replaces procedural `Query()` with eager `.execute()`, typed field operators (`==`, `>`, `<`), and `.metrics()`/`.dimensions()` introspection
2. **Type-safe filter predicates** — Predicate tree IR (And/Or/Not + 15 Lookup subclasses), named filter methods on Field, parameterized WHERE clause compilation with dialect-specific placeholders
3. **Reverse codegen CLI** — `cubano codegen <schema.view_name> --backend snowflake|databricks` introspects live warehouse views and generates ready-to-use Python model classes
4. **Snapshot-based warehouse testing** — Record/replay warehouse queries with syrupy; CI runs real warehouse test logic without per-run credential cost
5. **Integration testing framework** — Smart credential loader (env → .env → config fallback), session-scoped fixtures, parallel-safe per-worker schema isolation
6. **Comprehensive documentation** — MkDocs Material site with Diataxis framework, tabbed SQL examples (Snowflake/Databricks), auto-generated API reference, deployed to GitHub Pages

**Requirements Coverage:** 25/25 v0.2 requirements (100%)

- Integration Testing (INT-01–06): ✅ Complete
- Codegen (CODEGEN-01–08): ✅ Complete (superseded by reverse codegen in Phase 20)
- Documentation (DOCS-01–10): ✅ Complete
- Warehouse Test Recording (TEST-VCR): ✅ Complete
- Bonus: CODEGEN-WAREHOUSE (reverse codegen from v1+ backlog) ✅ Shipped

**Quality Metrics:**

- Test coverage: 759 tests passing
- Type checking: basedpyright strict mode — 0 errors
- Code quality: ruff linting and formatting — all passing
- Lines of code: 5,041 Python (src/cubano/)
- Timeline: 10 days (2026-02-16 → 2026-02-26), 429 commits

**Archive Files:**

- `.planning/milestones/v0.2-ROADMAP.md` — Full phase details
- `.planning/milestones/v0.2-REQUIREMENTS.md` — All requirements marked complete
- `.planning/milestones/v0.2-MILESTONE-AUDIT.md` — Verification report

---
