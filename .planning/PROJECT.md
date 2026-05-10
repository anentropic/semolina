# Semolina

## What This Is

Semolina is a Python ORM for querying data warehouse semantic views. It provides typed model classes that map to Snowflake Semantic Views, Databricks Metric Views, and DuckDB semantic views, a model-centric query builder with type-safe filter predicates, Arrow-native query execution via adbc-poolhouse connection pools, TOML-based configuration, a reverse codegen CLI to generate Python models from existing warehouse views (across all three backends), and a testing framework that runs against real DuckDB in-memory pools. Think Django ORM but for analytics — a common interface over different warehouse semantic layers, with full tooling for development and testing.

## Core Value

A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## Previous Milestones

- **v0.4.0 DuckDB Backend & Arrow Output** — Shipped 2026-05-07
- **v0.3 Arrow & Connection Layer** — Shipped 2026-04-18
- **v0.2 Tooling & Documentation** — Shipped 2026-02-26
- **v0.1 MVP** — Shipped 2026-02-16

See `.planning/MILESTONES.md` for full history.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Typed model classes via metaclass: `class Sales(SemanticView, view='sales'): revenue = Metric()` — v0.1
- ✓ Three field types: Metric, Dimension, Fact — v0.1
- ✓ Model-centric query builder: `.metrics()`, `.dimensions()`, `.where()`, `.order_by()`, `.limit()` — v0.2
- ✓ Type-safe field operators returning Predicate nodes: `==`, `!=`, `<`, `<=`, `>`, `>=`, `.between()`, `.in_()`, `.like()`, `.ilike()`, `.isnull()`, etc. — v0.2
- ✓ Predicate composition with `&` (AND), `|` (OR), `~` (NOT) — v0.2
- ✓ Facts selected via `.dimensions()` — v0.1
- ✓ `.to_sql()` for debugging generated SQL without executing — v0.1
- ✓ Implicit GROUP BY derived from selected dimensions — v0.1
- ✓ `import semolina` — single package, extras for backend drivers — v0.1
- ✓ Integration testing with real Snowflake/Databricks — v0.2
- ✓ Snapshot-based warehouse test recording/replay with syrupy — v0.2
- ✓ Reverse codegen CLI: warehouse view → Python model class — v0.2
- ✓ GitHub Actions: CI tests, docs build, GitHub Pages deploy — v0.2
- ✓ Doctest validation for all docstring examples — v0.2
- ✓ adbc-poolhouse connection pools replacing Engine ABC — pooled ADBC connections, Arrow-native — v0.3
- ✓ Dialect enum + pool registry: `register("default", pool, dialect="snowflake")` — v0.3
- ✓ `.semolina.toml` config with `pool_from_config()` helper — v0.3
- ✓ SemolinaCursor wrapping ADBC cursor with `fetchall_rows()`, `fetchone_row()`, `fetchmany_rows()` — v0.3
- ✓ MockPool for testing without warehouse connections — v0.3 (replaced by real DuckDB in v0.4.0)
- ✓ `query(metrics=..., dimensions=...)` shorthand arguments — v0.3
- ✓ `.using('name')` on query to select named pool — v0.3 (evolved from v0.1 engine selection)
- ✓ `.execute()` returning `SemolinaCursor` with Row objects supporting attribute and dict-style access — v0.3 (evolved from v0.2 Result class)
- ✓ Sphinx + shibuya documentation site: tutorials, how-to guides, API reference via sphinx-autoapi — v0.3 (replaced MkDocs)
- ✓ DuckDB as a first-class backend: `Dialect.DUCKDB`, `DuckDBSQLBuilder` for `semantic_view('view', dimensions := [...], metrics := [...])` and `facts := [...]`, with WHERE/ORDER BY/LIMIT as outer SQL — v0.4.0
- ✓ `semolina[duckdb]` extra installs `duckdb>=1.5.0` and `pyarrow>=17.0.0`; `[all]` includes it — v0.4.0
- ✓ DuckDB pool auto-runs `INSTALL semantic_views FROM community; LOAD semantic_views` once per physical connection — v0.4.0
- ✓ `type = "duckdb"` in `.semolina.toml` for DuckDB pool config — v0.4.0
- ✓ `fetch_arrow_table()` on `SemolinaCursor` returning `pyarrow.Table` with zero-copy bridge to Pandas/Polars — v0.4.0
- ✓ MockPool/MockCursor/MockConnection/Dialect.MOCK removed; tests run on real DuckDB in-memory pools — v0.4.0
- ✓ Reverse codegen for DuckDB: `semolina codegen --backend duckdb --database <path>` via `DESCRIBE SEMANTIC VIEW` — v0.4.0
- ✓ Three-backend documentation: Arrow how-to, Snowflake/Databricks/DuckDB connection guides, DuckDB tabs across all `:sync-group: warehouse` tab-sets — v0.4.0

### Active

(No active milestone — start next with `/gsd-new-milestone`)

### Out of Scope

- FastAPI / Django / GraphQL integrations — evaluate after connection layer has real-world usage
- CLI query interface — connection layer settled in v0.3; could revisit
- cube.dev and dbt Semantic Layer backends — adbc-poolhouse doesn't cover these; separate design
- Async query execution — architecture change, evaluate when needed
- Multi-view join API — complex feature, requires extensive design work
- Window functions (ROW_NUMBER, LAG, etc.) — SQL complexity beyond semantic view scope
- HAVING clause for metric filtering — evaluate after core query API stabilizes
- SEMANTIC_VIEW() clause syntax for Snowflake — using standard SQL instead
- dbt manifest → Semolina model codegen — focus is warehouse-direct introspection
- Standalone `[arrow]` pip extra — pyarrow is already a transitive dep of every backend ADBC driver, so a separate extra would be redundant
- Narwhals integration — `fetch_arrow_table()` plus user-side conversion is sufficient
- Streaming Arrow output (`to_record_batches()`) — deferred to a future milestone (`STREAM-01`/`STREAM-02`)
- DuckDB file-backed databases in codegen — in-memory only for now (`DKGEN-04` deferred)

## Context

Snowflake, Databricks, and DuckDB all ship semantic/metric view features that define metrics, dimensions, and facts as a layer above physical tables. Each uses different SQL syntax:
- **Snowflake**: `SELECT dim, AGG(metric) FROM view GROUP BY dim` — metrics wrapped in `AGG()`
- **Databricks**: `SELECT dim, MEASURE(metric) FROM view GROUP BY dim` — metrics use `MEASURE()` function
- **DuckDB**: `SELECT ... FROM semantic_view('view', dimensions := [...], metrics := [...])` — table-function form via the `semantic_views` community extension

All three abstract aggregation logic — the view defines how metrics aggregate, the query just references them. Semolina maps Python models to these views and generates the right SQL per backend.

v0.2 shipped the developer tooling layer (model-centric query API, reverse codegen, snapshot testing, docs). v0.3 replaced the hand-rolled Engine ABC with adbc-poolhouse pools and Arrow-native cursors. v0.4.0 brought DuckDB on board as a first-class backend and exposed Arrow output directly via `fetch_arrow_table()`, with MockPool retired in favour of real DuckDB in-memory testing.

## Constraints

- **Python version**: >=3.11
- **Core dependency**: adbc-poolhouse (connection pooling + Arrow transport); backend ADBC drivers are extras; CLI adds typer + rich + jinja2
- **Documentation**: Sphinx + shibuya theme, sphinx-autoapi for reference, sphinx-design for tabs
- **Packaging**: uv + pyproject.toml, uv-build backend
- **Testing**: pytest
- **Development Python**: 3.14 (per .python-version)

## Quality Gates (every phase)

Each phase must pass these before completion:
- **Typecheck**: `uv run basedpyright` — strict mode, configured via `[tool.basedpyright]` in pyproject.toml. Avoid `# type: ignore` in code; prefer pyproject.toml-level exemptions.
- **Lint & format**: `uv run ruff check` and `uv run ruff format --check`
- **Tests**: `uv run --extra dev pytest`
- **Docs build**: `uv run sphinx-build -W docs/src docs/_build`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Metaclass over decorator for models | Metaclass with args (`SemanticView, view='name'`) is cleaner than `@semantic_view('name')` decorator — more Pythonic for ORM-style classes | ✓ Good — feels natural, metaclass registration is robust |
| Backend IS the engine | `SnowflakeEngine(...)` subclasses `Engine` ABC rather than separate Engine + Backend objects — simpler, one concept | ✓ Replaced — v0.3 pool+dialect registry is cleaner |
| Standard SQL over SEMANTIC_VIEW() clause | Both backends support standard SQL; consistent approach | ✓ Good — works cleanly for both backends |
| Field refs only, no strings | `.metrics(Sales.revenue)` not `.metrics('revenue')` — enforces type safety, IDE autocomplete | ✓ Good — predictable API, easy to refactor |
| Facts via .dimensions() | Facts are non-aggregated values, behave like dimensions in queries | ✓ Good — simpler API, Fact type still useful for type distinction |
| Flat engine registry | Simple name→engine dict, lazy resolution at `.execute()` time | ✓ Replaced — v0.3 pool+dialect registry with `register(name, pool, dialect=)` |
| Custom Row class for results | Result shape is dynamic; Row supports `row.revenue` and `row['revenue']` | ✓ Kept — v0.3 Row is convenience sugar over Arrow via SemolinaCursor |
| Mock backend first | Build and test against MockEngine before real backends | ✓ Good — caught design issues early |
| Model-centric API (v0.2) | `Model.query()` replaces procedural `Query()` — better discoverability, eliminates import of Query class | ✓ Good — cleaner DX, enables `__repr__` on model class |
| Predicate tree over Q-objects (v0.2) | Typed `Predicate` subclasses (And/Or/Not/Lookup) over string-keyed Q-objects — type-safe, composable, pattern-matchable | ✓ Good — enables IDE autocomplete on filter methods, cleaner SQL compilation |
| Parameterized SQL for WHERE (v0.2) | `build_select_with_params()` returns `(sql_template, params)` — injection-safe, backend cursor-compatible | ✓ Good — necessary for correctness, no performance cost |
| Reverse over forward codegen (v0.2) | Warehouse → Python is more useful at adoption time; forward codegen has unclear value since user already has the Python model | ✓ Good — users can onboard existing views instantly |
| Snapshot testing with syrupy (v0.2) | Record/replay via .ambr files checked into git — CI runs warehouse logic without credentials | ✓ Good — enables real-scenario testing at zero per-run cost |

| adbc-poolhouse for connections (v0.3) | Replaces hand-rolled Engine classes with pooled ADBC connections — Arrow-native, all auth schemes, connection pooling | ✓ Good — clean separation of pool (transport) from dialect (SQL generation) |
| Pool registry with dialect enum (v0.3) | `register("default", pool, dialect="snowflake")` — dialect is a property of the connection, not the query | ✓ Good — backward-compatible migration path via DeprecationWarning |
| SemolinaCursor over ADBC cursor (v0.3) | `.execute()` returns cursor with full ADBC fetch API + Row convenience methods — Arrow is primary, Row is sugar | ✓ Good — DBAPI 2.0 compliance, familiar interface |
| TOML config with pool_from_config (v0.3) | `.semolina.toml` flat sections with `type` field dispatching to adbc-poolhouse config classes | ✓ Good — zero boilerplate for common setups |
| Sphinx + shibuya over MkDocs (v0.3) | sphinx-autoapi generates reference from docstrings; shibuya theme with Diataxis tabs | ✓ Good — autoapi removes manual API doc maintenance |
| DuckDBSQLBuilder overrides build_select_with_params() entirely (v0.4.0) | DuckDB `semantic_view()` is a table function, not a queryable view — the standard SELECT-from-view path doesn't apply | ✓ Good — clean dialect-specific isolation |
| `fetch_arrow_table()` not `to_arrow()` (v0.4.0) | Aligns with the underlying ADBC `fetch_arrow_table` convention; the requirement text predated the ADBC alignment decision | ✓ Good — consistent with transport, easy to learn for ADBC users |
| MockPool removed entirely, no deprecation (v0.4.0) | DuckDB in-memory pools are a real, fast replacement; v0.3 already flagged "clean break" as the path | ✓ Good — testing surface is now real ADBC, no mock/prod divergence risk |
| DuckDB extension auto-loads via SQLAlchemy `pool.connect` event (v0.4.0) | Run `INSTALL/LOAD semantic_views` once per physical connection, not per query | ✓ Good — zero per-query overhead, transparent to user code |
| Native `duckdb` driver for codegen, ADBC for queries (v0.4.0) | Codegen is offline tooling; the native driver is simpler and avoids depending on the pool layer | ✓ Good — clean separation between codegen and runtime stacks |
| Two-step DuckDB introspection (DESCRIBE SEMANTIC VIEW + DESCRIBE SELECT) (v0.4.0) | DuckDB's metadata is split across two DESCRIBE forms; one query is insufficient for full type inference | ✓ Good — 21 type entries mapped, intentional `TODO` placeholder for the long tail |
| No standalone `[arrow]` pip extra (v0.4.0) | pyarrow is a transitive dep of every backend ADBC driver — a separate extra would be noise | ✓ Good — keeps pyproject lean |

## Context

Shipped v0.4.0 with DuckDB as a first-class backend and Arrow-native cursor output. Total `src/semolina/` codebase: 6,388 lines Python; 924 unit tests passing.
Tech stack: Python 3.11+, adbc-poolhouse, duckdb (extra), pyarrow, Sphinx + shibuya, pytest, basedpyright, ruff.
Documentation: Sphinx site with Diataxis framework, three-backend coverage (Snowflake/Databricks/DuckDB), sphinx-autoapi for reference, deployed to GitHub Pages.

Known follow-ups for the next milestone:
- Streaming Arrow output (`to_record_batches()`) — deferred via `STREAM-01`/`STREAM-02`.
- DuckDB file-backed databases in codegen (`DKGEN-04`).
- Cross-phase integration audit (`/gsd-audit-uat`) — de facto verified by 924 tests + doc build, but no structured run.
- Convention: do not bulk-delete planning artifacts mid-milestone (Phases 33–35 lost their VERIFICATION.md trail in commit `2933df2`).

---
*Last updated: 2026-05-10 after v0.4.0 milestone*
