# Cubano

## What This Is

Cubano is a Python ORM for querying data warehouse semantic views. It provides typed model classes that map to semantic views (Snowflake Semantic Views, Databricks Metric Views) and a fluent, immutable query builder that generates the appropriate SQL for each backend. Think Django ORM but for analytics — a common interface over different warehouse semantic layers.

## Core Value

A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

- [ ] Typed model classes via metaclass: `class Sales(SemanticView, view='sales'): revenue = Metric()`
- [ ] Three field types: Metric, Dimension, Fact
- [ ] Field references for type-safe queries: `.metrics(Sales.revenue)` (no string API)
- [ ] Fluent, immutable query builder with `.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.limit()`
- [ ] Q-objects for AND/OR filter composition: `Q(country='US') | Q(country='CA')`
- [ ] Facts selected via `.dimensions()` (behave like dimensions in queries)
- [ ] `.fetch()` returning custom Row objects with attribute and dict-style access
- [ ] `.to_sql()` for debugging generated SQL without executing
- [ ] Engine ABC base class with abstract methods
- [ ] MockEngine for testing without warehouse connection
- [ ] SnowflakeEngine generating standard SQL with `AGG()` for metrics
- [ ] DatabricksEngine generating standard SQL with `MEASURE()` for metrics
- [ ] Implicit GROUP BY derived from selected dimensions
- [ ] Engine registry: flat name→engine dict, lazy resolution at `.fetch()` time
- [ ] `.using('name')` on query to select non-default engine
- [ ] `import cubano` — single package, extras for backend drivers

### Out of Scope

- Django integration (`cubano-django`) — separate package, later milestone
- `fetch_df()` / DataFrame returns — defer to later
- `fetch_async()` / async support — defer to later
- CLI codegen from warehouse introspection — defer to later
- Reverse codegen (models → semantic view YAML) — defer to later
- Time dimension convenience API (`.time()` with granularity) — time dims are just dimensions
- String-based field references (`.metrics('revenue')`) — field refs only
- Multi-view join API — defer to later
- Validation of metric/dimension combinations before execution — defer to later
- Connection pooling — backend driver concern, not Cubano's
- SEMANTIC_VIEW() clause syntax for Snowflake — using standard SQL instead

## Context

Snowflake and Databricks both recently shipped semantic/metric view features that define metrics, dimensions, and facts as a layer above physical tables. Querying them uses special SQL syntax:
- **Snowflake**: `SELECT dim, AGG(metric) FROM view GROUP BY dim` — metrics must be wrapped in `AGG()`
- **Databricks**: `SELECT dim, MEASURE(metric) FROM view GROUP BY dim` — metrics use `MEASURE()` function

Both abstract aggregation logic — the view defines how metrics aggregate, the query just references them. Cubano maps Python models to these views and generates the right SQL per backend.

The project was originally sketched as "sem" with a broader scope including Django integration. We're narrowing to the core library first.

## Constraints

- **Python version**: >=3.11
- **Zero required dependencies**: Core has no mandatory deps; backend drivers are extras (`cubano[snowflake]`, `cubano[databricks]`)
- **Packaging**: uv + pyproject.toml, uv-build backend
- **Testing**: pytest
- **Development Python**: 3.14 (per .python-version)

## Quality Gates (every phase)

Each phase must pass these before completion:
- **Typecheck**: `uv run basedpyright` — bias towards strictness, configure via `[tool.basedpyright]` in pyproject.toml. Avoid `# type: ignore` in code; prefer pyproject.toml-level exemptions for genuinely impossible cases.
- **Lint & format**: `uv run ruff check` and `uv run ruff format --check` — all code must pass
- **Tests**: `uv run --extra dev pytest` — all tests must pass

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Metaclass over decorator for models | Metaclass with args (`SemanticView, view='name'`) is cleaner than `@semantic_view('name')` decorator — more Pythonic for ORM-style classes | — Pending |
| Backend IS the engine | `SnowflakeEngine(...)` subclasses `Engine` ABC rather than separate Engine + Backend objects — simpler, one concept instead of two | — Pending |
| Standard SQL over SEMANTIC_VIEW() clause | Both backends support standard SQL style; Databricks only has standard SQL. Consistent approach across backends. | — Pending |
| Field refs only, no strings | `.metrics(Sales.revenue)` not `.metrics('revenue')` — enforces type safety, enables IDE autocomplete | — Pending |
| Facts via .dimensions() | Facts are non-aggregated values, behave like dimensions in queries — no separate `.facts()` method needed | — Pending |
| Flat engine registry | Simple name→engine dict. Lazy resolution at `.fetch()` time so models can be imported before registry is populated. | — Pending |
| Custom Row class for results | Result shape is dynamic (depends on selected fields), so static dataclasses won't work. Row supports `row.revenue` and `row['revenue']`. | — Pending |
| Mock backend first | Build and test the entire model + query builder + registry design against MockEngine before adding real warehouse backends | — Pending |

---
*Last updated: 2026-02-14 after initialization*
