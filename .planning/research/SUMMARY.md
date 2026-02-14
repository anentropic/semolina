# Project Research Summary

**Project:** Cubano — Python ORM for Data Warehouse Semantic Views
**Domain:** ORM/Query Builder for OLAP (Snowflake Semantic Views, Databricks Metric Views)
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

Cubano is a specialized Python ORM for querying data warehouse semantic views, occupying a unique position between traditional ORMs (SQLAlchemy, Django) and semantic layer platforms (dbt, Cube.dev). Research across stack, features, architecture, and pitfalls reveals a clear path: build a zero-dependency core library with immutable, type-safe query construction and backend-specific SQL generation.

The recommended approach follows proven ORM patterns — metaclass-based models, field descriptors, immutable query builder, visitor-pattern SQL compilation — but simplifies by focusing exclusively on read-only analytics. Core stack requires Python 3.11+ with no mandatory dependencies; backend drivers (Snowflake, Databricks) install as extras. Critical architectural decisions include: metaclass with `view='name'` syntax, frozen dataclass for immutable queries, dialect-specific SQL rendering delegated to Engine classes, and custom Row objects for results.

Key risks center on metaclass/descriptor correctness (mutable defaults causing cross-contamination), immutable query builder implementation (shallow copy sharing nested state), and SQL injection via field name interpolation. Mitigation strategies are clear: use tuples for internal state, validate/quote all identifiers, and build MockEngine first for comprehensive testing without warehouse dependencies. Success depends on getting the foundation (metaclass, descriptors, immutability) correct in Phase 1 — mistakes here require full rewrites.

## Key Findings

### Recommended Stack

**Zero-dependency core library** with backend drivers as optional extras. The entire core (fields, models, query builder, SQL compiler, registry, results) uses only Python standard library: `abc`, `typing`, `dataclasses`, `collections.abc`, `re`, `copy`.

**Core technologies:**
- **Python 3.11+**: Minimum for modern typing (Self, TypeVarTuple, StrEnum) — develop on 3.14
- **uv + uv-build**: Already configured, fast package management and lightweight build
- **pytest + mypy**: Testing and type checking — critical for library with metaclass patterns
- **ruff + pre-commit**: Already configured, handles linting and formatting in one tool
- **snowflake-connector-python**: Optional extra for Snowflake backend
- **databricks-sql-connector**: Optional extra for Databricks backend

**Key decision:** No ORM/SQL dependencies (SQLAlchemy, PyPika). Cubano generates simple SELECT/GROUP BY/ORDER BY SQL targeting semantic views — doesn't need connection pooling, migrations, or complex join resolution. This keeps install footprint minimal and avoids dependency conflicts.

### Expected Features

**Must have (table stakes):**
- Type-safe model classes via metaclass with field references (no strings)
- Fluent, immutable query API (`.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.limit()`)
- Q-objects for complex filter composition (`Q(a=1) & (Q(b=2) | Q(b=3))`)
- SQL generation without execution (`.to_sql()`) for debugging
- Parameter binding for safe SQL
- Custom Row objects with attribute and dict-style access
- Backend-specific SQL dialects (Snowflake `AGG()`, Databricks `MEASURE()`)

**Should have (competitive advantages):**
- Immutable query objects (prevent accidental mutations, thread-safe base queries)
- Field references only (no string-based field access like Django)
- Zero required dependencies (core is pure Python)
- Excellent type hints with `py.typed` for IDE autocomplete
- Time-based filter helpers (`.filter_last_n_days(7)`, `.filter_current_month()`)
- Filtered aggregates (`SUM(...) FILTER (WHERE ...)`)
- CTEs (WITH clause) for readable subqueries
- Pandas/Polars DataFrame output (`.to_pandas()`)

**Defer to v2+:**
- Window functions (high complexity, high value)
- Auto-codegen models from view introspection (very high effort, very high value)
- Async support (major refactor required)
- Pivot/unpivot operations
- Query result caching

**Explicitly exclude (anti-features):**
- Write operations (INSERT/UPDATE/DELETE) — semantic views are read-only
- Relationship management (one-to-many, many-to-many) — views are pre-joined
- Schema migrations — managed by dbt/SQL, not ORM
- REST/GraphQL API generation — Cubano is a library, not a platform
- Built-in caching layer — warehouse/BI tool responsibility

### Architecture Approach

Follow proven ORM layered architecture with clear separation between model definition, query construction, SQL compilation, execution, and result mapping. All mature ORMs (SQLAlchemy, Django, ibis) converge on this pattern.

**Major components:**

1. **Model Layer** — `SemanticViewMeta` metaclass with `**kwargs` for `view='name'` syntax, field descriptors (Metric, Dimension, Fact) introspected at class creation, `_meta` object stores view metadata
2. **Query Builder** — Frozen dataclass with immutable methods via `dataclasses.replace()`, accumulates state in tuples (not lists), lazy evaluation until `.fetch()`
3. **Filter Composition** — Q-objects as tree structure with overloaded `&`, `|`, `~` operators, recursive visitor pattern for SQL compilation
4. **SQL Compiler** — Dialect classes per backend (SnowflakeDialect, DatabricksDialect) with `compile_metric()` and `compile_filter()` methods, visitor pattern over query and filter trees
5. **Engine/Registry** — Abstract Engine base class with `.execute()` and `.close()`, flat dict registry (`name → Engine`), lazy resolution at `.fetch()` time, MockEngine for testing
6. **Result Mapper** — Custom Row class with dynamic attribute access and dict protocol, immutable after creation, lightweight wrapper over dict

**Build order:** Field descriptors → Metaclass → Q-objects → Query builder → MockEngine → Registry → SQL compiler → Row class → Wire integration → Real backends (Snowflake, Databricks). Bottom-up approach enables testing each component in isolation before integration.

### Critical Pitfalls

1. **Metaclass mutable defaults** — Field descriptors with mutable defaults (`default=[]`) cause cross-contamination between model classes. Use `None` and initialize in `__init__`, create fresh copies per class in metaclass, freeze metadata after creation. This corrupts the entire foundation if wrong.

2. **Immutable query shallow copy** — Using `dataclasses.replace()` with list attributes shares state between "copies." Use tuples for `_metrics`, `_dimensions`, `_filters`, `_order_by`. Test: branch from base query, verify independence. Breaks query reuse patterns.

3. **SQL injection via field names** — Field names interpolated into SQL without quoting enables injection even with "field refs only" design. Validate field names against `^[a-zA-Z_][a-zA-Z0-9_]*$` in metaclass, always quote identifiers in SQL generation. Security issue.

4. **Backend syntax hardcoded wrong layer** — If `AGG()` vs `MEASURE()` logic lives in shared SQL builder instead of Engine classes, adding new backends requires core changes. Delegate `render_metric()` to each Engine subclass.

5. **Dynamic Row attribute conflicts** — Row class with `__getattr__` for field access shadows dict methods if field named `keys`, `values`, `items`. Use reserved keyword validation or namespace separation (`row.fields.revenue` vs `row.keys()`).

6. **MockEngine divergence** — MockEngine built first but doesn't replicate backend constraints (AGG() requirement, GROUP BY rules). Make MockEngine dialect-aware with strict validation mode. Tests pass on mock but fail on real backends.

7. **Registry stale state** — Lazy engine resolution at `.fetch()` time allows engines to be registered/unregistered/re-registered between query construction and execution. Make registry immutable after initial population, provide explicit `reset()` for tests only.

## Implications for Roadmap

Based on research, suggested 4-phase structure building foundation → core system → real backends:

### Phase 1: Foundation (Model System + Mock Backend)
**Rationale:** Get metaclass, field descriptors, and immutability correct from the start — mistakes here require complete rewrites. Build MockEngine early to enable testing without warehouse dependencies.

**Delivers:**
- Metaclass-based models with `class Sales(SemanticView, view='sales')` syntax
- Field descriptors (Metric, Dimension, Fact) with name introspection
- Immutable Query builder with `.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.limit()`
- Q-objects for filter composition with `&`, `|`, `~` operators
- MockEngine for in-memory testing
- Flat registry pattern

**Addresses (from FEATURES.md):**
- Type-safe models
- Fluent API
- Immutable queries
- Field references (no strings)

**Avoids (from PITFALLS.md):**
- Pitfall 1: Metaclass mutable defaults (use tuples, freeze metadata)
- Pitfall 2: Query shallow copy (use tuples for state)
- Pitfall 14: Field name collisions (validate reserved names)
- Pitfall 17: Empty queries (validate at least one selection)

**Implementation notes:**
- Use frozen dataclass for Query with tuple attributes
- Metaclass validates field names against reserved keywords and SQL injection patterns
- MockEngine accepts `dialect='snowflake'|'databricks'` to enforce backend rules
- Comprehensive unit tests for metaclass, descriptors, immutability

### Phase 2: SQL Generation + Execution
**Rationale:** With solid foundation, add SQL compilation with backend-specific dialects and wire Query → Compiler → Engine → Results. Keep dialect logic in Engine classes, not shared compiler.

**Delivers:**
- Dialect classes (SnowflakeDialect, DatabricksDialect, MockDialect)
- SQL compiler with visitor pattern over Query and Q-objects
- `.to_sql()` method for debugging
- `.fetch()` method wiring compilation + execution
- Custom Row class with attribute and dict access
- Parameter binding (or value escaping if backends don't support params)

**Uses (from STACK.md):**
- Standard library only (`re` for validation, `dataclasses` for Row)
- pytest for SQL generation testing

**Implements (from ARCHITECTURE.md):**
- SQL Compiler component (visitor pattern)
- Result Mapper component (Row class)
- Query → Compiler → Engine integration

**Avoids (from PITFALLS.md):**
- Pitfall 3: SQL injection (validate and quote identifiers)
- Pitfall 6: Backend syntax hardcoded (delegate to Engine.render_metric())
- Pitfall 5: Implicit GROUP BY with window functions (track field metadata)
- Pitfall 7: Row attribute conflicts (reserved keyword check)

**Implementation notes:**
- Each Engine implements `render_metric(field)` and `render_dimension(field)`
- SQL compiler calls `engine.render_metric(metric)`, not `f"AGG({metric.name})"`
- All identifiers quoted in SQL: `SELECT "country", AGG("revenue") FROM "sales"`
- Row class validates against reserved names (`keys`, `values`, `items`, etc.)

### Phase 3: Snowflake Backend
**Rationale:** Implement first production backend with real warehouse connection. Snowflake chosen first because AGG() syntax is simpler and more widely documented than Databricks MEASURE().

**Delivers:**
- SnowflakeEngine with lazy import of `snowflake-connector-python`
- Snowflake-specific SQL generation (AGG() wrapper for metrics)
- Connection management via Snowflake connector
- Integration tests against Snowflake sandbox (optional, credential-gated)
- Documentation for Snowflake setup and usage

**Uses (from STACK.md):**
- snowflake-connector-python (optional extra: `pip install cubano[snowflake]`)

**Avoids (from PITFALLS.md):**
- Pitfall 20: Connection pooling (delegate to Snowflake connector)
- Snowflake-specific: AGG() requirement enforced
- Snowflake-specific: SEMANTIC_VIEW() clause vs standard SQL (verify compatibility)

**Implementation notes:**
- Lazy import: `import snowflake.connector` only in SnowflakeEngine methods
- Test with recorded VCR responses if no live Snowflake access
- Validate that standard SQL approach (not SEMANTIC_VIEW() clause) works

### Phase 4: Databricks Backend
**Rationale:** Second production backend demonstrates multi-backend abstraction works. MEASURE() syntax different from Snowflake validates dialect system.

**Delivers:**
- DatabricksEngine with lazy import of `databricks-sql-connector`
- Databricks-specific SQL generation (MEASURE() wrapper for metrics)
- Unity Catalog three-part name support (`catalog.schema.view`)
- Integration tests against Databricks workspace (optional)
- Documentation for Databricks setup

**Uses (from STACK.md):**
- databricks-sql-connector (optional extra: `pip install cubano[databricks]`)

**Avoids (from PITFALLS.md):**
- Databricks-specific: MEASURE() requirement enforced
- Databricks-specific: Unity Catalog namespacing in view names
- Databricks-specific: Parameter binding syntax differences

**Implementation notes:**
- Lazy import: `from databricks import sql` only in DatabricksEngine
- Support fully-qualified view names: `view='catalog.schema.view_name'`
- Test parameter binding differences between Snowflake and Databricks

### Phase Ordering Rationale

- **Foundation first:** Metaclass mistakes require complete rewrites — must be correct before building on top
- **MockEngine early:** Enables testing entire stack (query construction → SQL → results) without warehouse dependencies
- **SQL generation second:** Requires stable Query API from Phase 1
- **Real backends last:** Need Engine abstraction and SQL compiler working before implementing driver integrations
- **Snowflake before Databricks:** Simpler syntax, more documentation, validates approach before second backend

**Dependency chain:**
```
Phase 1 (Foundation)
    ↓
Phase 2 (SQL + Execution) — depends on Query/MockEngine from P1
    ↓
Phase 3 (Snowflake) — depends on Engine ABC + SQL compiler from P2
    ↓
Phase 4 (Databricks) — depends on multi-backend pattern validated in P3
```

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2:** SQL compilation patterns — verify parameterized query support in Snowflake/Databricks, may need research-phase for safe parameter binding
- **Phase 3:** Snowflake semantic view constraints — need to verify SEMANTIC_VIEW() clause vs standard SQL, AGG() requirements, fact table fan-out protection
- **Phase 4:** Databricks Unity Catalog — three-part naming, MEASURE() syntax, parameter binding differences

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Metaclass + descriptors + immutable builder are well-established ORM patterns (Django, SQLAlchemy provide clear precedents)
- **Phase 2:** Visitor pattern for SQL compilation is standard (SQLAlchemy, ibis demonstrate approach)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Python 3.11+, zero dependencies, uv tooling already configured. Stack decisions are low-risk. |
| Features | HIGH | Analyzed 7 major libraries (SQLAlchemy, Django, PyPika, ibis, dbt, Cube.dev). Clear table stakes vs differentiators. |
| Architecture | HIGH | Metaclass, immutable builder, visitor compilation are proven patterns. Multiple references (SQLAlchemy, Django, ibis). |
| Pitfalls | MEDIUM | Based on training knowledge of ORM patterns and Python metaclass gotchas. Snowflake/Databricks-specific pitfalls need validation with 2026 docs (web search unavailable). |

**Overall confidence:** HIGH

### Gaps to Address

**During Phase Planning:**
- Verify Snowflake AGG() requirement and syntax in current (2026) Snowflake documentation
- Confirm Databricks MEASURE() syntax and Unity Catalog naming rules
- Validate whether semantic views support window functions in dimensions (impacts Pitfall 5)
- Test parameter binding support: do Snowflake/Databricks connectors support parameterized queries, or must values be escaped inline?

**During Implementation:**
- Determine if SEMANTIC_VIEW() SQL clause is required or if standard SQL SELECT works
- Verify Snowflake fact table fan-out protection works with generated SQL
- Test thread-safety of Snowflake and Databricks connector connection pooling
- Validate whether Databricks requires different parameter binding syntax (`:param` vs `?`)

**Future Research (Deferred):**
- Window functions syntax and GROUP BY interaction (for v1.1+)
- Semantic view introspection APIs for auto-codegen (for v1.1+)
- Async driver support in Snowflake/Databricks connectors (for async Cubano API)

## Sources

### Primary (HIGH confidence)
- **Project design notes** (.resources/design/notes.md) — Cubano architecture decisions, field types, SQL generation approach
- **Semantic view examples** (.resources/ifm-semantic-layer/) — YAML definitions showing metrics, dimensions, facts
- **Existing configuration** (pyproject.toml, .pre-commit-config.yaml) — uv, ruff, pre-commit already set up

### Secondary (MEDIUM confidence)
- **SQLAlchemy architecture** (training knowledge) — Metaclass patterns, immutable Select, dialect system, Engine/Connection separation
- **Django ORM patterns** (training knowledge) — ModelBase metaclass, QuerySet immutability via `_clone()`, Q-objects, database router
- **ibis architecture** (training knowledge) — Expression trees, backend abstraction, DataFrame output formats
- **Python metaclass best practices** (training knowledge) — Descriptor protocol, mutable default pitfalls, `__init_subclass__` hooks

### Tertiary (LOW confidence — needs validation)
- **Snowflake AGG() requirement** (inferred from design notes) — should verify with 2026 Snowflake Semantic Views documentation
- **Databricks MEASURE() syntax** (inferred from design notes) — should verify with 2026 Databricks Metric Views documentation
- **Parameter binding support** (assumption based on typical SQL behavior) — needs testing with actual connectors

---

**Research completed:** 2026-02-14
**Ready for roadmap:** Yes

**Next step:** Use this summary to create detailed roadmap with phases 1-4. Each phase should expand on deliverables, success criteria, and tests. Defer window functions, codegen, async to v1.1+.
