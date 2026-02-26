# Cubano

## What This Is

Cubano is a Python ORM for querying data warehouse semantic views. It provides typed model classes that map to Snowflake Semantic Views and Databricks Metric Views, a model-centric query builder with type-safe filter predicates, a reverse codegen CLI to generate Python models from existing warehouse views, and a testing framework for validating queries against real warehouse data. Think Django ORM but for analytics — a common interface over different warehouse semantic layers, with full tooling for development and testing.

## Core Value

A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## Current State (v0.2)

**Shipped:** 2026-02-26
**Status:** Tooling & Documentation Complete

Core library plus developer tooling is feature-complete and production-ready:

- ✅ **Model-centric query API:** `Model.query().metrics(...).where(...).execute()` — eager execution, typed field operators
- ✅ **Type-safe filter predicates:** `field == value`, `field.between()`, `field.ilike()`, AND/OR/NOT composition with `&`/`|`/`~`
- ✅ **WHERE clause compilation:** Parameterized SQL with dialect-specific placeholders (`%s` Snowflake, `?` Databricks)
- ✅ **Reverse codegen CLI:** `cubano codegen <schema.view_name> --backend snowflake|databricks` → ready-to-use Python model class
- ✅ **Integration testing framework:** Smart credential loader, session-scoped fixtures, parallel-safe per-worker schema isolation
- ✅ **Snapshot-based warehouse tests:** Record/replay with syrupy — CI runs warehouse test logic without credentials
- ✅ **Documentation:** MkDocs Material site with Diataxis framework, tabbed SQL examples, API reference, GitHub Pages deploy
- ✅ **Quality:** 759 tests passing, basedpyright strict 0 errors, doctest validation in CI

**Available for Installation:**
```bash
pip install cubano                           # Core library
pip install cubano[snowflake]               # With Snowflake support
pip install cubano[databricks]              # With Databricks support
pip install cubano[snowflake,databricks]    # With both backends
```

**Public API:**
- Core: `SemanticView, Metric, Dimension, Fact, Predicate, OrderTerm, NullsOrdering, Row, Result`
- Query: `Model.query().metrics().dimensions().where().order_by().limit().execute()/.to_sql()`
- Exceptions: `CubanoViewNotFoundError, CubanoConnectionError`
- Registry: `register, get_engine, unregister`
- Engines: `Engine, Dialect, MockEngine, SnowflakeEngine, DatabricksEngine`
- CLI: `cubano codegen <schema.view_name> --backend snowflake|databricks`

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

- [ ] FastAPI integration: query cubano models from HTTP endpoints with pydantic-compatible results
- [ ] `fetch_df()` returning pandas/polars DataFrame (Arrow transport)
- [ ] CLI query interface: `cubano query <model> --metrics revenue --where country=US`
- [ ] cube.dev and dbt Semantic Layer backends (third-party semantic layers)
- [ ] Django integration (`cubano-django`) — ORM-style queryset wrapper
- [ ] Async query execution (`async def execute()`)

### Out of Scope

- `fetch_df()` / DataFrame returns — deferred; Arrow transport is the right foundation (TODO)
- `fetch_async()` / async support — architecture change, evaluate after v0.3 stability
- Multi-view join API — complex feature, requires extensive design work
- Window functions (ROW_NUMBER, LAG, etc.) — SQL complexity, table-stakes only for now
- HAVING clause for metric filtering — evaluate after core query API stabilizes
- Connection pooling — backend driver concern, not Cubano's
- SEMANTIC_VIEW() clause syntax for Snowflake — using standard SQL instead
- dbt manifest → Cubano model codegen — deferred to v0.3; focus was warehouse-direct introspection

## Context

Snowflake and Databricks both recently shipped semantic/metric view features that define metrics, dimensions, and facts as a layer above physical tables. Querying them uses special SQL syntax:
- **Snowflake**: `SELECT dim, AGG(metric) FROM view GROUP BY dim` — metrics must be wrapped in `AGG()`
- **Databricks**: `SELECT dim, MEASURE(metric) FROM view GROUP BY dim` — metrics use `MEASURE()` function

Both abstract aggregation logic — the view defines how metrics aggregate, the query just references them. Cubano maps Python models to these views and generates the right SQL per backend.

v0.2 shipped the developer tooling layer: a model-centric query API with typed predicates, reverse codegen for onboarding new views, snapshot testing infrastructure, and comprehensive documentation. The API was significantly evolved from v0.1 (Q-objects → Predicate tree, `.fetch()` → `.execute()`, forward codegen CLI → reverse codegen CLI).

## Constraints

- **Python version**: >=3.11
- **Zero required dependencies**: Core has no mandatory deps; backend drivers are extras; CLI adds typer + rich + jinja2
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
| Backend IS the engine | `SnowflakeEngine(...)` subclasses `Engine` ABC rather than separate Engine + Backend objects — simpler, one concept | ✓ Good — no friction in practice |
| Standard SQL over SEMANTIC_VIEW() clause | Both backends support standard SQL; consistent approach | ✓ Good — works cleanly for both backends |
| Field refs only, no strings | `.metrics(Sales.revenue)` not `.metrics('revenue')` — enforces type safety, IDE autocomplete | ✓ Good — predictable API, easy to refactor |
| Facts via .dimensions() | Facts are non-aggregated values, behave like dimensions in queries | ✓ Good — simpler API, Fact type still useful for type distinction |
| Flat engine registry | Simple name→engine dict, lazy resolution at `.execute()` time | ✓ Good — zero-friction setup |
| Custom Row class for results | Result shape is dynamic; Row supports `row.revenue` and `row['revenue']` | ✓ Good — both access styles useful in practice |
| Mock backend first | Build and test against MockEngine before real backends | ✓ Good — caught design issues early |
| Model-centric API (v0.2) | `Model.query()` replaces procedural `Query()` — better discoverability, eliminates import of Query class | ✓ Good — cleaner DX, enables `__repr__` on model class |
| Predicate tree over Q-objects (v0.2) | Typed `Predicate` subclasses (And/Or/Not/Lookup) over string-keyed Q-objects — type-safe, composable, pattern-matchable | ✓ Good — enables IDE autocomplete on filter methods, cleaner SQL compilation |
| Parameterized SQL for WHERE (v0.2) | `build_select_with_params()` returns `(sql_template, params)` — injection-safe, backend cursor-compatible | ✓ Good — necessary for correctness, no performance cost |
| Reverse over forward codegen (v0.2) | Warehouse → Python is more useful at adoption time; forward codegen has unclear value since user already has the Python model | ✓ Good — users can onboard existing views instantly |
| Snapshot testing with syrupy (v0.2) | Record/replay via .ambr files checked into git — CI runs warehouse logic without credentials | ✓ Good — enables real-scenario testing at zero per-run cost |

---
*Last updated: 2026-02-26 after v0.2 milestone*
