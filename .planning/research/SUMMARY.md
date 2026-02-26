# Project Research Summary

**Project:** Cubano
**Version:** v0.1 (published) + v0.2 (codegen, integration testing, documentation)
**Domain:** Python ORM for Data Warehouse Semantic Views
**Researched:** 2026-02-17
**Overall Confidence:** HIGH (core architecture proven, v0.2 additions follow established patterns)

## Executive Summary

Cubano v0.1 is production-proven with 265 passing tests and a stable public API for querying semantic views in Snowflake and Databricks. v0.2 adds three complementary capabilities—code generation (Python models from warehouse schema), integration testing infrastructure, and user documentation—without breaking the core library's zero-dependency constraint. All three v0.2 components leverage industry-standard patterns: Jinja2 templates for codegen (used by LangChain, FastAPI, Trusted Firmware-M), pytest fixtures for integration tests (already proven in v0.1's test suite), and MkDocs for documentation (standard in Python ecosystem for projects of Cubano's size).

The research validates a phased approach: Phase 1 establishes integration test infrastructure in cubano-jaffle-shop (validates v0.1 API and test patterns), Phase 2 builds cubano-codegen as a separate CLI tool (independent of core, optional for users), Phase 3 adds MkDocs documentation (references both core and codegen), and Phase 4 publishes to PyPI and GitHub Pages. No rewrite risk exists—v0.2 is purely additive with strict API compatibility guaranteed by freezing all public exports in `cubano/__init__.py`.

Critical v0.2 risks concentrate in integration: codegen must validate generated Python syntax before shipping (prevents user adoption of broken code), integration tests require isolated test schemas to prevent flakiness (essential for CI reliability), and documentation examples must be tested via doctest (prevents users copying broken code). All risks have documented prevention strategies from ecosystem research. The v0.1 foundation (metaclass model system, immutable query builder, dialect-aware SQL generation) is battle-tested and requires no changes for v0.2.

## Key Findings

### Recommended Stack

v0.2 additions integrate seamlessly with v0.1's existing infrastructure while maintaining zero-dependency core:

**Core technologies (v0.1 unchanged):**
- Python 3.11+ — Modern typing features (Self, TypeVarTuple, StrEnum)
- uv + uv-build — Fast package manager and build backend (already configured)
- pytest (>=8.0.0) — Test framework with 265 existing tests validating core API
- ruff (>=0.15.1) + basedpyright (>=1.38.0) — Linting and strict type checking (already configured)

**v0.2 new dependencies (all dev-only, not required for users installing core):**
- Jinja2 (>=3.1.6) — Template engine for SQL codegen; fast, maintainable, suitable for semantic view generation
- Click (>=8.3.1) — CLI framework; battle-tested, auto-generates help from docstrings
- MkDocs (>=1.6.1) — Documentation site generator; simpler than Sphinx for 28-item API
- mkdocs-material (latest) — Professional Material Design theme; mobile responsive, widely adopted (FastAPI, Pydantic)
- mkdocstrings (>=0.28.0) — Auto-generate API docs from Python docstrings
- mkdocstrings-python (latest) — Python handler for docstring extraction using Griffe

**Key stack decisions validated:**
- **Template-based codegen over AST/reflection:** Jinja2 provides maintainability, human-readable output, and control flow (conditionals for optional fields, loops for field lists). Industry-standard approach (LangChain, FastAPI, Trusted Firmware-M). NOT using SQLAlchemy or Alembic because Cubano generates simple CREATE VIEW statements, not complex query builders or schema migrations.
- **pytest fixtures for test warehouse:** Already proven in v0.1 (265 tests). Fixture system provides excellent setup/teardown semantics for database isolation. Pattern: `@pytest.fixture(scope='session')` for warehouse connection, `@pytest.fixture` for test-scoped data isolation.
- **MkDocs over Sphinx:** Suitable for Cubano's API size and user audience. Markdown-based (familiar), faster setup (5 min vs 30 min), live reload built-in. Sphinx is overkill (designed for 500+ item APIs, complex autodoc features). Material theme is production-quality (mobile responsive, search, navigation).
- **Separate cubano-codegen package:** Maintains zero-dependency core principle; codegen is dev-time tool, not runtime. Follows SQLAlchemy Migrate pattern (migrations are separate tool). Independent versioning allows faster iteration on codegen features without blocking core releases.

### Expected Features

**Must have (table stakes for v0.2):**
- Parse Python SemanticView models — Extract metadata from existing Cubano models via `SemanticViewMeta._fields` and `_view_name` (HIGH confidence; already built in v0.1)
- Generate Snowflake CREATE SEMANTIC VIEW SQL — Snowflake AGG() syntax documented, field ordering (FACTS/DIMENSIONS/METRICS clauses) established (MEDIUM confidence; requires template implementation)
- Generate Databricks metric view YAML — MEASURE() syntax documented (MEDIUM confidence; simpler than SQL)
- Validate generated SQL syntax locally — Parse generated SQL with Python AST, catch gross syntax errors (MEDIUM confidence; warehouse introspection deferred to v0.3)
- Execute integration tests — pytest fixtures + MockEngine to validate codegen output without warehouse access (HIGH confidence; patterns proven in v0.1)
- Document generated code — Auto-generate API reference from Python docstrings via mkdocstrings (HIGH confidence; standard tool)

**Should have (competitive advantages, v0.2 optional):**
- Schema version tracking in generated code — Store source schema version hash in generated file for drift detection (MEDIUM confidence; documented mitigation for Pitfall 21)
- Generated code merge mode — `--mode merge` preserves user custom methods when regenerating (MEDIUM confidence; pattern used by datamodel-codegen, SQLAlchemy Migrate)
- Integration test isolation patterns — Document how to use isolated test schemas, temporary tables, credential fixtures (MEDIUM confidence; patterns well-established)

**Defer to v0.3 (lower priority, deferred from v0.2):**
- Live warehouse schema validation — Requires Snowflake/Databricks introspection APIs, caching (complex, high value)
- CI/CD auto-publishing pipeline — GitHub Actions workflow to deploy generated views to warehouse (medium complexity, requires credential management)
- Real warehouse integration tests — Tests executing actual queries against Snowflake/Databricks (requires test warehouse setup)

**Explicit anti-features (not building):**
- Full ORM code generation — Out of scope; use Pydantic/SQLAlchemy if full ORM needed
- LLM-based SQL generation — High error rates; template-based generation with human-written templates instead
- Automatic relationship inference — Snowflake/Databricks require explicit relationships; no "magic" inference
- Schema versioning system — Complex for v0.2; track git history of generated views instead
- Real-time query execution — Out of scope; integration tests use offline MockEngine or test warehouse

### Architecture Approach

v0.2 maintains strict separation: the core library (zero deps, published API frozen) remains untouched while three new components integrate cleanly. Core library exposes metadata via `SemanticViewMeta._fields` and `_view_name` for codegen consumption, but codegen is a separate package users install optionally. Integration tests reuse the existing cubano-jaffle-shop example workspace as a dual-purpose demonstration and validation suite. Documentation via MkDocs references all three components but builds independently.

**Major components:**

1. **Core Library (cubano)** — Model system (SemanticView, Metric, Dimension, Fact), query builder (Query, Q objects), registry (register/get_engine), result handling (Row). Status: stable, no changes for v0.2. Public API frozen; only internal optimizations allowed.

2. **Codegen Tool (cubano-codegen, NEW)** — Separate CLI tool that reads warehouse schema (dbt manifest or future Snowflake/Databricks introspection) and generates Python model classes compatible with core library. Entry point: `cubano-codegen from-dbt --manifest manifest.json --output models.py`. Uses Jinja2 templates for SQL/YAML generation, Click for CLI. Independent versioning (0.1.0 for v0.2 launch).

3. **Integration Tests (cubano-jaffle-shop extended)** — Reuses existing jaffle-shop dbt project. v0.2 adds test suite validating model definitions → SQL generation → execution end-to-end. Tests use MockEngine for speed; optional real Snowflake fixtures for v0.3. Fixture pattern: session-scoped warehouse connection, test-scoped data isolation via temporary schemas or mock data.

4. **Documentation (MkDocs, NEW)** — `/docs/` directory with mkdocs.yml, guides (models, queries, codegen, examples), API reference (auto-generated via mkdocstrings), development notes. Hosted on GitHub Pages via CI/CD. References all three components with separate sections.

**Integration patterns:**
- **Core → Codegen:** Codegen imports public API (SemanticView, Metric, Dimension, Fact) only; generates code that follows same patterns as hand-written Cubano models
- **Core + Integration tests:** Tests import models from cubano-jaffle-shop, exercise Query API, validate SQL generation with MockEngine
- **All → Documentation:** Docs reference core API (models, query methods, engines) and codegen tool (CLI usage, examples); auto-generated sections for API, manual sections for guides

### Critical Pitfalls

**From v0.1 research (prevented by current design, no changes needed):**

1. **Metaclass mutable defaults** (Pitfall 1) — Core library correctly uses immutable descriptors and frozen `MappingProxyType` for `_fields`. No changes needed. v0.2 codegen must validate generated models follow same pattern.

2. **Immutable query builder shallow copy** (Pitfall 2) — Core library correctly uses tuples for internal state, not lists. No changes needed. v0.2 integration tests must validate query branching (base query, two derived queries remain independent).

3. **SQL injection via field names** (Pitfall 3) — Core library quotes identifiers per dialect. v0.2 codegen must validate field names against `^[a-zA-Z_][a-zA-Z0-9_]*$` and quote in generated SQL.

**v0.2-specific critical pitfalls (NEW, must address in planning):**

4. **Generated code diverges from model source (Pitfall 21)** — Codegen produces models from warehouse schema; if schema drifts or users hand-edit, regenerating clobbers edits. Schema version hash in generated file comment + `--mode merge` option + runtime validation at first query. Phase 8 (Codegen) CRITICAL to implement before shipping codegen.

5. **Integration tests flaky due to shared data (Pitfall 22)** — Tests share test schema or table names; parallel execution causes race conditions. Prevention: isolated temporary schema per test (UUID-based), fixture-based cleanup, run with `pytest -n auto` to validate. Phase 9 (Integration Tests) CRITICAL to establish before writing first integration test.

6. **Documentation examples become stale (Pitfall 23)** — Code examples in docs show old API; users copy-paste broken examples. Prevention: enable Sphinx doctest or similar validation; compile all code examples as part of docs build; fail build if examples break. Phase 10 (Documentation) enforce from start.

## Implications for Roadmap

Research validates a four-phase approach with clear dependencies and risk mitigation:

### Phase 1: Integration Test Foundation (cubano-jaffle-shop extension)
**Rationale:** Validate v0.1 API stability before adding v0.2 features. No codegen or docs needed. Establishes test patterns (fixtures, isolation) that codegen and docs will reuse.

**Delivers:**
- Extended cubano-jaffle-shop with 10-15 integration tests validating model structure, query building, SQL generation, execution against MockEngine
- API compatibility test suite (`tests/test_api_compat.py` in core) verifying all v0.1 public exports still work
- Documentation of test fixture patterns (MockEngine setup, isolation, cleanup)

**Avoids:** Pitfall 22 (flaky tests) — establish data isolation patterns early; document that tests must be parallel-safe

**Duration:** 1-2 days
**Success criteria:** All 265 v0.1 unit tests pass unchanged; new integration tests pass both sequentially and with `pytest -n auto`

---

### Phase 2: Codegen CLI Tool (cubano-codegen package, NEW)
**Rationale:** Codegen is independent of integration tests; can build in parallel with Phase 1 or Phase 3. Depends on v0.1 API being frozen (Phase 1 validates this).

**Delivers:**
- `cubano-codegen` Python package (version 0.1.0) with dbt manifest → Python model generator
- CLI entry point: `cubano-codegen from-dbt --manifest manifest.json --output models.py --dialect snowflake`
- Jinja2 templates for Snowflake CREATE SEMANTIC VIEW and Databricks metric view YAML
- Unit tests (dbt manifest parsing, template rendering, SQL output validation)
- Generated models pass syntax check (`py_compile`), import correctly, have no undefined references

**Avoids:** Pitfall 25 (syntax errors) — validate generated code before writing. Pitfall 21 (codegen drift) — store schema version, support merge mode

**Duration:** 3-5 days
**Success criteria:** Codegen parses dbt manifest.json, generates valid Python models, models import without errors, generated SQL matches expected format

---

### Phase 3: Documentation Infrastructure & Content (MkDocs, NEW)
**Rationale:** Documentation references both core library and codegen; best done after both are stable. Documentation generation must depend on codegen to ensure generated models appear in API reference.

**Delivers:**
- `/docs/` directory with MkDocs config, Markdown guides, API reference structure
- User guides: Getting Started, Defining Models, Building Queries, Filtering, Execution, Using Codegen, Examples
- API reference: Auto-generated from docstrings via mkdocstrings
- CI/CD workflow (`.github/workflows/docs.yml`) that builds docs on every push, deploys to GitHub Pages
- Docstring validation: all code examples pass doctest; docs build fails if examples break

**Avoids:** Pitfall 23 (stale examples) — enable doctest; fail build if examples break. Pitfall 24 (codegen out of sync) — docs build depends on codegen

**Duration:** 2-3 days
**Success criteria:** `mkdocs serve` shows docs locally, all code examples pass doctest, generated models appear in API reference

---

### Phase 4: Release & Publishing
**Rationale:** Once all three components tested and stable, coordinate release to PyPI and GitHub Pages.

**Delivers:**
- Version bumps: cubano 0.1.0 → 0.2.0, cubano-codegen 0.1.0 (new), cubano-jaffle-shop 0.1.0 → 0.1.1
- CHANGELOG documenting v0.2 features
- PyPI publication for both packages
- GitHub Pages deployment with docs live

**Duration:** 1 day

---

### Phase Ordering Rationale

1. **Phase 1 first:** Integration tests validate v0.1 API is stable and can support v0.2 features. Establishes test patterns (fixtures, isolation) that later phases reuse.

2. **Phase 2 second:** Codegen depends on core API being frozen. Can run in parallel with Phase 1 or Phase 3, but shipped after Phase 1 validation.

3. **Phase 3 third:** Documentation references core (Phase 1) and codegen (Phase 2). Docs build must depend on codegen.

4. **Phase 4 last:** Release after all three components pass CI/CD and tested together.

### Research Flags

**Phases likely needing deeper research during planning:**

- **Phase 1 (Integration Tests):** Test data isolation with real warehouse fixtures (MockEngine proven, but warehouse-specific patterns new to Cubano). Recommend: MVP with MockEngine, design real warehouse fixtures for Phase 3+.

- **Phase 2 (Codegen):** Field type inference from dbt and other schemas. dbt has measures, dimensions, entities; Cubano supports Metric/Dimension/Fact. Mapping strategy needs clarification. Recommend: start dbt-focused, defer other sources to v0.2.1.

- **Phase 3 (Documentation):** MkDocs doctest plugin availability and behavior. Recommend: implement doctest validation in CI step as fallback.

**Phases with standard patterns (skip research-phase):**

- **Phase 1 (pytest):** Fixture scoping and isolation well-documented. Cubano already uses MockEngine. Standard patterns apply.

- **Phase 2 (Jinja2 templates):** Template-based code generation is industry standard (LangChain, FastAPI, Trusted Firmware-M). Click CLI battle-tested.

- **Phase 4 (Release):** PyPI and GitHub Actions workflows standard. Cubano already has release.yml.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | All tools recommended (Jinja2, Click, MkDocs, mkdocstrings) are industry standards. v0.1 stack proven in production. No version conflicts expected. |
| **Features** | HIGH | Table stakes features (parse models, generate SQL, validate syntax, integration tests, docs) have established patterns. Must-haves minimal and well-scoped. |
| **Architecture** | HIGH | Component boundaries (core, codegen, tests, docs) explicit and dependency-clear. v0.1 API compatibility strategy sound and proven. |
| **Pitfalls** | MEDIUM-HIGH | v0.1 pitfalls well-understood from codebase and design. v0.2-specific pitfalls documented with prevention strategies from ecosystem research, but not yet validated in Cubano context. |

**Overall confidence:** HIGH

v0.1 is proven, and v0.2 additions follow established patterns. Main uncertainty is v0.2-specific integration (codegen + tests + docs working together), validated during Phase 1-3.

### Gaps to Address

1. **Warehouse integration test fixtures:** Research assumes Snowflake/Databricks credentials via environment variables, but actual connection patterns for each warehouse and credential rotation need validation.

2. **Field type inference mapping:** Research assumes dbt measures → Metric, dimensions → Dimension, but other schema sources may differ. Recommendation: Phase 2 start dbt-only; plan other sources in v0.2.1.

3. **Docstring style validation:** Cubano uses Google-style docstrings (per MEMORY.md); mkdocstrings supports Google/NumPy/Sphinx. Verify compatibility.

4. **Real warehouse costs:** Snowflake free tier exists; Databricks costs depend on workspace size. Recommend: Phase 1 design fixtures to minimize cost; Phase 3 add cost monitoring.

5. **Codegen customization patterns:** Research suggests `--mode merge` or `_generated.py + models.py` split. Recommend: Phase 2 implement one pattern; iterate based on user feedback in v0.2.1.

## Sources

### Primary (HIGH confidence — official docs)

**Stack & Tools:**
- [Jinja2 Documentation](https://jinja.palletsprojects.com/) — Template engine for codegen
- [Click Documentation](https://click.palletsprojects.com/) — CLI framework
- [MkDocs Official](https://www.mkdocs.org/) — Documentation generator
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) — Theme
- [mkdocstrings GitHub](https://github.com/mkdocstrings/mkdocstrings) — API doc generation
- [pytest Fixtures Reference](https://docs.pytest.org/en/stable/reference/fixtures/) — Test fixtures
- [uv Workspace Documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/) — Package management

**Architecture & Patterns:**
- [SQLAlchemy 2.1 Documentation](https://docs.sqlalchemy.org/en/21/) — ORM patterns
- [Django ORM Documentation](https://docs.djangoproject.com/en/stable/topics/db/models/) — Model system patterns

**Warehouse Semantics:**
- [Snowflake CREATE SEMANTIC VIEW Documentation](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [Databricks Semantic Metadata in Metric Views](https://docs.databricks.com/aws/en/metric-views/data-modeling/semantic-metadata)

### Secondary (MEDIUM confidence — ecosystem research)

**Code Generation:**
- [Code Generation With Jinja2 - Trusted Firmware-M](https://trustedfirmware-m.readthedocs.io/en/latest/design_docs/software/tfm_code_generation_with_jinja2.html)
- [C++ Code Generation using Python and Jinja2](https://markvtechblog.wordpress.com/2024/04/28/code-generation-in-python-with-jinja2/)
- [GitHub - agronholm/sqlacodegen](https://github.com/agronholm/sqlacodegen) — SQLAlchemy code generation patterns

**Testing & Data Quality:**
- [Modern Data Warehouse Testing Strategy Guide for 2026](https://blog.qasource.com/how-to-build-an-end-to-end-data-warehouse-testing-strategy)
- [Flaky Tests in 2026: Key Causes, Fixes, and Prevention](https://www.accelq.com/blog/flaky-tests/)
- [What is Schema Drift? The Ultimate Guide](https://litedatum.com/what-is-schema-drift)

**Documentation:**
- [Python Docs Tools: MkDocs vs Sphinx](https://www.pythonsnacks.com/p/python-documentation-generator)

### Tertiary (Internal context)

- Cubano project codebase v0.1: proven, 265 passing tests, stable API
- MEMORY.md: Quality gates and style preferences
- Design notes: v0.1 architecture decisions (view metadata, dialect abstraction, immutable queries)

---

*Research completed: 2026-02-17*
*Ready for roadmap: yes*
*Proceed with Phase 1 implementation — confidence for planning: HIGH*
