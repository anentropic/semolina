# Semolina

## What This Is

Semolina is a Python ORM for querying data warehouse semantic views. It provides typed model classes that map to Snowflake Semantic Views, Databricks Metric Views, and DuckDB semantic views, a model-centric query builder with type-safe filter predicates, Arrow-native query execution via `create_engine()` Engines that own their ADBC connection pool and dialect (adbc-poolhouse under the hood), TOML-based configuration, a reverse codegen CLI to generate Python models from existing warehouse views (across all three backends), and a testing framework that runs against real DuckDB in-memory pools. Think Django ORM but for analytics — a common interface over different warehouse semantic layers, with full tooling for development and testing.

## Core Value

A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

## Previous Milestones

- **v0.6 Engine Architecture** — Shipped 2026-06-25
- **v0.5 Streaming Arrow & Codegen Polish** — Shipped 2026-06-13
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
- ✓ Streaming Arrow output: `SemolinaCursor.fetch_record_batch()` returning `pyarrow.RecordBatchReader` and `__iter__`/`__next__` for lazy `Row` iteration, mirroring `adbc_driver_manager` cursor methods — v0.5 (Phase 39)
- ✓ Streaming how-to guide: `docs/src/how-to/streaming.rst` with decision rule, backend notes, and ParquetWriter worked example — v0.5 (Phase 40)
- ✓ DuckDB file-backed codegen: `semolina codegen --backend duckdb --database <path>` normalizes relative/`~`/absolute paths (preserving the `:memory:` sentinel), installs `semantic_views` on the codegen connection, and is verified end-to-end against a pytest-generated fixture `.db` — v0.5 (Phase 41, DKGEN-04)
- ✓ Codegen field-type inference: every column resolves to a concrete `Metric`/`Dimension`/`Fact` role across all three backends via native metadata (`DESCRIBE SEMANTIC VIEW` / `SHOW COLUMNS IN VIEW` / `DESCRIBE TABLE EXTENDED ... AS JSON`); unrecognized roles raise `ValueError` rather than defaulting to `Dimension` — v0.5 (Phase 42, DKGEN-05)
- ✓ Cross-phase milestone audit: `/gsd-audit-uat` SC-by-SC verification of v0.5 against the shipped surface, producing `v0.5-MILESTONE-AUDIT.md` (PASSED) and closing the v0.4.0 "audit skipped" retrospective gap — v0.5 (Phase 43, AUDIT-01)
- ✓ `Engine` owns its ADBC pool + dialect (SQLAlchemy-style): `create_engine(config | name)` constructs an `Engine` with `connect()` + concrete ADBC `execute()`, serving both introspection and execution from one pool — v0.6 (Phase 44, supersedes the v0.3 `pool_from_config` + `(pool, dialect)` registry)
- ✓ `register("name", engine)` + `get_engine("name")` name→Engine registry — v0.6 (Phase 44, supersedes the v0.3 3-arg `register(name, pool, dialect)`)
- ✓ ADBC-only stack: native backend connectors and `*_connect_kwargs` removed; `pool_from_config`/`create_pool`/`get_pool` deleted (clean pre-1.0 break, all docs migrated) — v0.6 (Phase 44)
- ✓ Databricks `.where()` over real ADBC via literal-inlining: `Dialect.supports_parameterized_queries` flag + an audited `render_literal` Spark-SQL escaper + build-time post-pass; Snowflake/DuckDB keep `?` + bound params — v0.6 (Phase 45, DBX-01/01b/01c)
- ✓ adbc-poolhouse Databricks DSN carries `catalog`/`schema` (released as 1.3.1, consumed via pin bump) so unqualified `FROM \`view\`` resolves — v0.6 (Phase 45, DBX-02)
- ✓ Databricks integration cassettes recorded; `tests/integration` replays 14/14 green offline (7 Snowflake + 7 Databricks) — v0.6 (Phase 45, DBX-03)
- ✓ Databricks ADBC introspection: `DatabricksEngine.introspect()` parses `DESCRIBE TABLE EXTENDED ... AS JSON` over ADBC (cassette-backed), retiring the Phase 44-04 `NotImplementedError` fallback — v0.6 (Phase 44-04 follow-up)

### Active

<!-- Current scope. No milestone is active — v0.6 shipped 2026-06-25. Run `/gsd-new-milestone` to define the next one (questioning → research → requirements → roadmap). -->

(None — between milestones. See `## Next Milestone` below for candidate directions.)

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

## Next Milestone

No milestone is active. v0.6 shipped 2026-06-25 (no `REQUIREMENTS.md` this milestone — Phase 44/45 tracked local phase-scoped IDs). A fresh `REQUIREMENTS.md` will be created by `/gsd-new-milestone`.

**Deferred candidate seeds** (not yet committed):

- **STREAM-04** — user-controllable batch/chunk size for `fetch_record_batch()` (currently relies on ADBC defaults)
- **DJANGO-01** — `django-semolina` helper package (settings-based engine registration, `AppConfig.ready()` hook, codegen management command); scoped in `_notes/django-semolina-v0.1.md`, intended for a separate repo
- **render_literal Date/Decimal** — Databricks literal-inlining currently raises `NotImplementedError` for Date/Decimal WHERE values; widen when a real case needs it

**Backlog directions** (17 pending todos under `.planning/todos/pending/`): a CLI query interface, a GraphQL interface, Cube.dev / dbt Semantic Layer backends, and dataframe-agnostic result output via Arrow. Several overlap with current Out of Scope entries — revisit those reasons when scoping the next milestone.

Run `/gsd-new-milestone` to turn one of these directions into requirements and a roadmap.

## Context

Snowflake, Databricks, and DuckDB all ship semantic/metric view features that define metrics, dimensions, and facts as a layer above physical tables. Each uses different SQL syntax:
- **Snowflake**: `SELECT dim, AGG(metric) FROM view GROUP BY dim` — metrics wrapped in `AGG()`
- **Databricks**: `SELECT dim, MEASURE(metric) FROM view GROUP BY dim` — metrics use `MEASURE()` function
- **DuckDB**: `SELECT ... FROM semantic_view('view', dimensions := [...], metrics := [...])` — table-function form via the `semantic_views` community extension

All three abstract aggregation logic — the view defines how metrics aggregate, the query just references them. Semolina maps Python models to these views and generates the right SQL per backend.

v0.2 shipped the developer tooling layer (model-centric query API, reverse codegen, snapshot testing, docs). v0.3 replaced the hand-rolled Engine ABC with adbc-poolhouse pools and Arrow-native cursors. v0.4.0 brought DuckDB on board as a first-class backend and exposed Arrow output directly via `fetch_arrow_table()`, with MockPool retired in favour of real DuckDB in-memory testing. v0.5 added lazy streaming on top of that Arrow surface (`fetch_record_batch()` + row iteration) and polished codegen — file-backed DuckDB databases plus correct `Metric`/`Dimension`/`Fact` field-type inference across all three backends. v0.6 reshaped the connection layer itself: the `Engine` now owns its ADBC pool and dialect (SQLAlchemy-style `create_engine` / `register(engine)`), native connectors were dropped for an ADBC-only stack, and Databricks query execution was brought fully online over real ADBC with the first recorded Databricks integration cassettes.

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
| Per-backend semantic-view metadata-query paths for codegen field-role inference (Phase 42) | DuckDB reads role from `DESCRIBE SEMANTIC VIEW`; Snowflake reads `kind` from `SHOW COLUMNS IN VIEW`; Databricks reads `is_measure` from `DESCRIBE TABLE EXTENDED ... AS JSON` (metric vs dimension — no native Fact type) | ✓ Good — each backend's native metadata source resolves every column to a concrete role |
| Strict `_field_class_for` raises on unrecognized role (Phase 42) | Replaced the silent `return "Dimension"` catch-all with an explicit `_ROLE_TO_CLASS` lookup that raises `ValueError` on any role outside metric/dimension/fact — schema drift or a new warehouse version fails loudly at codegen time instead of mislabeling a column | ✓ Good — no silent mislabeling; the "every column resolves to a concrete role" invariant is enforced |
| Streaming output is pure ADBC passthrough (Phase 39) | `fetch_record_batch()` returns the underlying ADBC cursor's `RecordBatchReader` directly, and `__iter__`/`__next__` iterate it lazily — no Semolina-side buffering or backend-specific code; backend differences are absorbed by ADBC | ✓ Good — one code path streams across Snowflake/Databricks/DuckDB; mirrors `adbc_driver_manager` so the API is familiar |
| Codegen path normalization at the CLI boundary (Phase 41) | `_normalize_database_path` expands relative/`~`/absolute paths (preserving the `:memory:` sentinel) at the CLI edge, so the introspection layer always receives a resolved path | ✓ Good — keeps path handling out of the codegen core; file- and memory-backed codegen share one introspection path |
| Engine owns the pool, SQLAlchemy-style (Phase 44) | `create_engine(config \| name)` builds an `Engine` owning one ADBC pool + dialect; `register("name", engine)`/`get_engine` replace the `(pool, dialect)` tuple registry — collapses three concepts (pool, dialect, registry tuple) into one object that serves both introspection and execution | ✓ Good — single concept, mirrors SQLAlchemy, supersedes the v0.3 pool+dialect registry |
| ADBC-only, clean pre-1.0 break (Phase 44) | Native backend connectors and `*_connect_kwargs` deleted; `pool_from_config`/`create_pool`/3-arg `register` removed outright with no deprecation, all 12 doc pages migrated in the same milestone | ✓ Good — one transport stack, no mock/native divergence; pre-1.0 means no users to break |
| Databricks `.where()` via literal-inlining behind a capability flag (Phase 45) | The arrow-adbc Databricks driver rejects bind params; rather than gate `.where()` as unsupported, a `Dialect.supports_parameterized_queries` flag + one audited `render_literal` Spark-SQL escaper + a build-time post-pass inline WHERE literals for Databricks while Snowflake/DuckDB keep `?` + params | ✓ Good — uniform query API across backends; single audited escape control point; adversarially tested |
| Fix upstream in adbc-poolhouse, not locally (Phase 45) | The Databricks DSN dropping catalog/schema was fixed in adbc-poolhouse `to_adbc_kwargs()` (released 1.3.1) and consumed via a pin bump, not worked around in Semolina | ✓ Good — fix lives where the bug is; benefits all poolhouse consumers |
| Cassette-stays-green replay gate (Phase 44) | Prove the engine-owns-the-pool refactor is safe by replaying the existing Snowflake cassettes byte-identical, rather than re-recording | ✓ Good — refactor verified to never touch SQL-builder output, zero re-record risk |

## Context

Shipped v0.6 with the Engine-owns-the-pool architecture (`create_engine` / `register(engine)`, ADBC-only) and full Databricks query support over real ADBC (literal-inlined WHERE, poolhouse catalog/schema DSN fix, recorded cassettes, ADBC introspection). Total `src/semolina/` codebase: 5,929 lines Python (net −1,392 vs the Phase 44 baseline — native connectors removed); `tests/integration` replays 14/14 (7 Snowflake + 7 Databricks) offline.
Tech stack: Python 3.11+, adbc-poolhouse, duckdb (extra), pyarrow, Sphinx + shibuya, pytest, basedpyright, ruff.
Documentation: Sphinx site with Diataxis framework, three-backend coverage (Snowflake/Databricks/DuckDB), sphinx-autoapi for reference, deployed to GitHub Pages.

Conventions carried into the next milestone:
- Do not bulk-delete planning artifacts mid-milestone (Phases 33–35 lost their VERIFICATION.md trail in commit `2933df2`).
- Refresh `REQUIREMENTS.md` traceability as phases land, not at archive time.
- Packaging changes need their own smoke test in CI (`[duckdb]` extra silently went missing during a v0.4.0 refactor).
- Keep requirement text in lock-step with shipped API names (v0.5 audit confirmed zero drift — every named API exists under exactly that name).
- Run the cross-phase audit (`/gsd-audit-uat`) before milestone close, not as an afterthought.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-25 after v0.6 (Engine Architecture) milestone complete*
