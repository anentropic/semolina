# Semolina

## What This Is

Semolina is a Python ORM for querying data warehouse semantic views. It provides typed model classes that map to Snowflake Semantic Views and Databricks Metric Views, a model-centric query builder with type-safe filter predicates, a reverse codegen CLI to generate Python models from existing warehouse views, and a testing framework for validating queries against real warehouse data. Think Django ORM but for analytics — a common interface over different warehouse semantic layers, with full tooling for development and testing.

## Core Value

A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## Current Milestone: v0.3 Arrow & Connection Layer

**Goal:** Replace the hand-rolled connection layer with adbc-poolhouse for pooled, Arrow-native connections across all backends, and evolve the query API to return cursors with rich Arrow fetch methods.

**Target features:**
- adbc-poolhouse connection pools replacing Engine classes
- Dialect enum + pool registry (`register("default", pool, dialect="snowflake")`)
- `.semolina.toml` config via TomlSettingsSource + `pool_from_config()` helper
- `SemolinaCursor` wrapping ADBC cursor with `fetchall_rows()` / `fetchmany_rows()` / `fetchone_row()` convenience
- Arrow-native results: `fetch_arrow_table()`, `fetch_record_batch_reader()` from cursor
- `MockPool` for testing without warehouse connections
- `query(metrics=..., dimensions=...)` shorthand args

## Previous State (v0.2)

**Shipped:** 2026-02-26
**Status:** Tooling & Documentation Complete

Archive: `.planning/MILESTONES.md`

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Typed model classes via metaclass: `class Sales(SemanticView, view='sales'): revenue = Metric()` — v0.1
- ✓ Three field types: Metric, Dimension, Fact — v0.1
- ✓ Model-centric query builder: `.metrics()`, `.dimensions()`, `.where()`, `.order_by()`, `.limit()` — v0.2 (renamed from `.filter()`, `.fetch()`)
- ✓ Type-safe field operators returning Predicate nodes: `==`, `!=`, `<`, `<=`, `>`, `>=`, `.between()`, `.in_()`, `.like()`, `.ilike()`, `.isnull()`, etc. — v0.2
- ✓ Predicate composition with `&` (AND), `|` (OR), `~` (NOT) — v0.2
- ✓ Facts selected via `.dimensions()` — v0.1
- ✓ `.execute()` returning `Result` with `Row` objects supporting attribute and dict-style access — v0.2
- ✓ `.to_sql()` for debugging generated SQL without executing — v0.1
- ✓ Engine ABC base class with abstract methods — v0.1
- ✓ MockEngine for testing without warehouse (now evaluates predicates in-memory) — v0.1/v0.2
- ✓ SnowflakeEngine generating SQL with `AGG()` for metrics — v0.1
- ✓ DatabricksEngine generating SQL with `MEASURE()` for metrics — v0.1
- ✓ Implicit GROUP BY derived from selected dimensions — v0.1
- ✓ Engine registry: flat name→engine dict, lazy resolution at `.execute()` time — v0.1
- ✓ `.using('name')` on query to select non-default engine — v0.1
- ✓ `import cubano` — single package, extras for backend drivers — v0.1
- ✓ Integration testing with real Snowflake/Databricks via `SnowflakeCredentials.load()` — v0.2
- ✓ Snapshot-based warehouse test recording/replay with syrupy — v0.2
- ✓ Reverse codegen CLI: warehouse view → Python model class — v0.2
- ✓ MkDocs documentation site: tutorials, how-to guides, API reference — v0.2
- ✓ GitHub Actions: CI tests, docs build, GitHub Pages deploy — v0.2
- ✓ Doctest validation for all docstring examples — v0.2

### Active

- [ ] Replace connection layer with adbc-poolhouse — pooled ADBC connections, Arrow-native
- [ ] Dialect enum + pool registry replacing Engine ABC and engine registry
- [ ] `.semolina.toml` config with TomlSettingsSource + `pool_from_config()` helper
- [ ] SemolinaCursor wrapping ADBC cursor with Row convenience methods
- [ ] Arrow-native fetch: `fetch_arrow_table()`, `fetch_record_batch_reader()` from cursor
- [ ] MockPool for testing without warehouse connections
- [ ] `query(metrics=..., dimensions=...)` shorthand arguments

### Out of Scope

- FastAPI / Django / GraphQL integrations — evaluate after v0.3 connection layer stabilizes
- CLI query interface — deferred, connection layer must settle first
- cube.dev and dbt Semantic Layer backends — adbc-poolhouse doesn't cover these; separate design
- Async query execution — architecture change, evaluate after v0.3
- Multi-view join API — complex feature, requires extensive design work
- Window functions (ROW_NUMBER, LAG, etc.) — SQL complexity, table-stakes only for now
- HAVING clause for metric filtering — evaluate after core query API stabilizes
- SEMANTIC_VIEW() clause syntax for Snowflake — using standard SQL instead
- dbt manifest → Semolina model codegen — deferred; focus was warehouse-direct introspection

## Context

Snowflake and Databricks both recently shipped semantic/metric view features that define metrics, dimensions, and facts as a layer above physical tables. Querying them uses special SQL syntax:
- **Snowflake**: `SELECT dim, AGG(metric) FROM view GROUP BY dim` — metrics must be wrapped in `AGG()`
- **Databricks**: `SELECT dim, MEASURE(metric) FROM view GROUP BY dim` — metrics use `MEASURE()` function

Both abstract aggregation logic — the view defines how metrics aggregate, the query just references them. Cubano maps Python models to these views and generates the right SQL per backend.

v0.2 shipped the developer tooling layer: a model-centric query API with typed predicates, reverse codegen for onboarding new views, snapshot testing infrastructure, and comprehensive documentation. The API was significantly evolved from v0.1 (Q-objects → Predicate tree, `.fetch()` → `.execute()`, forward codegen CLI → reverse codegen CLI).

## Constraints

- **Python version**: >=3.11
- **Core dependency**: adbc-poolhouse (connection pooling + Arrow transport); backend ADBC drivers are extras; CLI adds typer + rich + jinja2
- **Packaging**: uv + pyproject.toml, uv-build backend
- **Testing**: pytest
- **Development Python**: 3.14 (per .python-version)

## Quality Gates (every phase)

Each phase must pass these before completion:
- **Typecheck**: `uv run basedpyright` — strict mode, configured via `[tool.basedpyright]` in pyproject.toml. Avoid `# type: ignore` in code; prefer pyproject.toml-level exemptions.
- **Lint & format**: `uv run ruff check` and `uv run ruff format --check`
- **Tests**: `uv run --extra dev pytest`
- **Docs build**: `uv run mkdocs build --strict`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Metaclass over decorator for models | Metaclass with args (`SemanticView, view='name'`) is cleaner than `@semantic_view('name')` decorator — more Pythonic for ORM-style classes | ✓ Good — feels natural, metaclass registration is robust |
| Backend IS the engine | `SnowflakeEngine(...)` subclasses `Engine` ABC rather than separate Engine + Backend objects — simpler, one concept | ⚠️ Revisit — v0.3 replaces Engine with adbc-poolhouse pools |
| Standard SQL over SEMANTIC_VIEW() clause | Both backends support standard SQL; consistent approach | ✓ Good — works cleanly for both backends |
| Field refs only, no strings | `.metrics(Sales.revenue)` not `.metrics('revenue')` — enforces type safety, IDE autocomplete | ✓ Good — predictable API, easy to refactor |
| Facts via .dimensions() | Facts are non-aggregated values, behave like dimensions in queries | ✓ Good — simpler API, Fact type still useful for type distinction |
| Flat engine registry | Simple name→engine dict, lazy resolution at `.execute()` time | ⚠️ Revisit — v0.3 becomes pool registry with dialect tag |
| Custom Row class for results | Result shape is dynamic; Row supports `row.revenue` and `row['revenue']` | ⚠️ Revisit — v0.3 evaluates Row as optional convenience over Arrow |
| Mock backend first | Build and test against MockEngine before real backends | ✓ Good — caught design issues early |
| Model-centric API (v0.2) | `Model.query()` replaces procedural `Query()` — better discoverability, eliminates import of Query class | ✓ Good — cleaner DX, enables `__repr__` on model class |
| Predicate tree over Q-objects (v0.2) | Typed `Predicate` subclasses (And/Or/Not/Lookup) over string-keyed Q-objects — type-safe, composable, pattern-matchable | ✓ Good — enables IDE autocomplete on filter methods, cleaner SQL compilation |
| Parameterized SQL for WHERE (v0.2) | `build_select_with_params()` returns `(sql_template, params)` — injection-safe, backend cursor-compatible | ✓ Good — necessary for correctness, no performance cost |
| Reverse over forward codegen (v0.2) | Warehouse → Python is more useful at adoption time; forward codegen has unclear value since user already has the Python model | ✓ Good — users can onboard existing views instantly |
| Snapshot testing with syrupy (v0.2) | Record/replay via .ambr files checked into git — CI runs warehouse logic without credentials | ✓ Good — enables real-scenario testing at zero per-run cost |

| adbc-poolhouse for connections (v0.3) | Replaces hand-rolled Engine classes with pooled ADBC connections — Arrow-native, all auth schemes, connection pooling | — Pending |
| Pool registry with dialect enum (v0.3) | `register("default", pool, dialect="snowflake")` — dialect is a property of the connection, not the query | — Pending |
| SemolinaCursor over ADBC cursor (v0.3) | `.execute()` returns cursor with full ADBC fetch API + Row convenience methods — Arrow is primary, Row is sugar | — Pending |

---
*Last updated: 2026-03-16 after v0.3 milestone start*
