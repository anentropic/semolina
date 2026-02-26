# Codebase Structure

**Analysis Date:** 2026-02-17

## Directory Layout

```
cubano/                         # Repo root
├── src/
│   └── cubano/                 # Main package (src-layout)
│       ├── __init__.py         # Public API surface — all user-facing exports
│       ├── __main__.py         # python -m cubano entry point
│       ├── conftest.py         # Doctest fixtures (src/cubano/ scoped)
│       ├── fields.py           # Field descriptors: Metric, Dimension, Fact, OrderTerm, NullsOrdering
│       ├── filters.py          # Q filter object for boolean composition
│       ├── models.py           # SemanticView base class + SemanticViewMeta metaclass
│       ├── query.py            # Query immutable builder (frozen dataclass)
│       ├── registry.py         # Named engine registry (module-level dict)
│       ├── results.py          # Row result object (immutable, dict+attr access)
│       ├── engines/            # Backend engines and SQL dialects
│       │   ├── __init__.py     # Re-exports: Engine, Dialect, MockEngine, SnowflakeEngine, DatabricksEngine
│       │   ├── base.py         # Engine ABC (to_sql, execute)
│       │   ├── sql.py          # Dialect ABC, SnowflakeDialect, DatabricksDialect, MockDialect, SQLBuilder
│       │   ├── mock.py         # MockEngine (fixture-based, no warehouse)
│       │   ├── snowflake.py    # SnowflakeEngine (lazy import snowflake.connector)
│       │   └── databricks.py   # DatabricksEngine (lazy import databricks.sql)
│       ├── codegen/            # CLI codegen subsystem
│       │   ├── __init__.py     # (empty)
│       │   ├── models.py       # ModelData, FieldData — codegen internal data model
│       │   ├── loader.py       # validate_python_syntax, load_module_from_path, extract_models_from_module
│       │   ├── generator.py    # generate_sql_for_files — main codegen orchestrator
│       │   ├── renderer.py     # render_view, render_file_header (Jinja2)
│       │   ├── validator.py    # CodegenError, format_error_report
│       │   └── templates/      # Jinja2 SQL/YAML templates
│       │       ├── snowflake.sql.jinja2    # CREATE OR REPLACE SEMANTIC VIEW ...
│       │       └── databricks.yaml.jinja2  # Databricks metric view YAML
│       ├── cli/                # Typer CLI application
│       │   ├── __init__.py     # app = typer.Typer(); registers codegen subcommand
│       │   ├── codegen.py      # codegen() command function
│       │   └── utils.py        # resolve_input_paths, make_stderr_console
│       └── testing/            # Integration test utilities
│           ├── __init__.py     # Re-exports SnowflakeCredentials, DatabricksCredentials, CredentialError
│           └── credentials.py  # pydantic-settings credential classes with .load() fallback chain
├── tests/                      # Test suite (separate from src/)
│   ├── conftest.py             # Shared pytest fixtures (Sales model, MockEngine, registry cleanup)
│   ├── test_fields.py          # Field descriptor tests
│   ├── test_filters.py         # Q filter composition tests
│   ├── test_models.py          # SemanticView metaclass + immutability tests
│   ├── test_query.py           # Query builder tests
│   ├── test_registry.py        # Engine registry tests
│   ├── test_results.py         # Row object tests
│   ├── test_engines.py         # MockEngine tests
│   ├── test_sql.py             # SQLBuilder + Dialect tests
│   ├── test_snowflake_engine.py # SnowflakeEngine unit tests (mocked connector)
│   ├── test_databricks_engine.py # DatabricksEngine unit tests (mocked connector)
│   ├── test_credentials.py     # Credential loading tests
│   └── codegen/                # Codegen subsystem tests
│       ├── fixtures/           # Python files used as codegen test inputs
│       │   ├── simple_models.py
│       │   ├── multi_models.py
│       │   └── no_models.py
│       ├── test_cli.py         # CLI integration tests (typer CliRunner)
│       ├── test_generator.py   # generate_sql_for_files tests
│       ├── test_loader.py      # Module loading and introspection tests
│       ├── test_renderer.py    # Jinja2 template rendering tests
│       └── test_utils.py       # resolve_input_paths tests
├── docs/                       # MkDocs documentation source
│   └── guides/
│       └── backends/
├── site/                       # Generated MkDocs static site (not committed)
├── cubano-jaffle-shop/         # Example workspace (uv workspace member)
│   └── src/cubano_jaffle_shop/
├── dbt-jaffle-shop/            # dbt reference project (not cubano code)
├── pyproject.toml              # Project config: deps, scripts, ruff, basedpyright, pytest
└── .planning/                  # GSD planning documents
    └── codebase/               # This directory
```

## Directory Purposes

**`src/cubano/` (root module files):**
- Purpose: Core public-facing ORM — the library a user imports
- Key files: `__init__.py` (single source of truth for public API), `models.py`, `fields.py`, `query.py`, `filters.py`, `registry.py`, `results.py`

**`src/cubano/engines/`:**
- Purpose: Backend-specific SQL generation and execution
- Contains: Abstract `Engine` and `Dialect` classes; concrete `MockEngine`, `SnowflakeEngine`, `DatabricksEngine`; `SQLBuilder` clause assembler
- Key insight: Dialects (`SnowflakeDialect`, `DatabricksDialect`, `MockDialect`) are pure SQL syntax rules; engines own connection lifecycle

**`src/cubano/codegen/`:**
- Purpose: Code generation CLI subsystem — converts Python model files to warehouse DDL
- Contains: Pipeline stages as separate modules (loader → generator → renderer); Jinja2 templates in `templates/`
- Separate from core ORM: codegen depends on the model layer but is not needed to use the query API

**`src/cubano/cli/`:**
- Purpose: Typer CLI application wired to codegen subsystem
- Contains: `app` (Typer instance), `codegen` subcommand, `utils` for path resolution

**`src/cubano/testing/`:**
- Purpose: Credential management utilities for integration tests
- Contains: `SnowflakeCredentials` and `DatabricksCredentials` pydantic-settings classes with multi-source fallback (`SNOWFLAKE_*` env vars → `.env` file → `.cubano.toml` → `~/.config/cubano/config.toml`)

**`tests/`:**
- Purpose: Unit and integration tests; mirrors `src/cubano/` module structure
- Test markers: `unit`, `mock`, `warehouse`, `snowflake`, `databricks`
- Doctests: also run from `src/` (configured via `testpaths = ["tests", "src"]` and `--doctest-modules`)

**`src/cubano/codegen/templates/`:**
- Purpose: Jinja2 templates for SQL generation output
- Generated: No (committed source files)
- Key files: `snowflake.sql.jinja2` (Snowflake `CREATE OR REPLACE SEMANTIC VIEW`), `databricks.yaml.jinja2` (Databricks metric view YAML)

## Key File Locations

**Entry Points:**
- `src/cubano/__init__.py`: All user-facing imports (`SemanticView`, `Metric`, `Dimension`, `Fact`, `Query`, `Q`, `OrderTerm`, `NullsOrdering`, `register`, `get_engine`, `unregister`, `Row`)
- `src/cubano/__main__.py`: `python -m cubano` dispatcher
- `src/cubano/cli/__init__.py`: `cubano` CLI script entry point (`[project.scripts]` → `cubano.cli:app`)

**Configuration:**
- `pyproject.toml`: All project config — dependencies, optional extras, tool settings (ruff, basedpyright, pytest)
- `src/cubano/conftest.py`: Doctest-specific fixtures (scoped to `src/cubano/`)
- `tests/conftest.py`: Shared test fixtures for `tests/` suite

**Core Logic:**
- `src/cubano/models.py`: `SemanticViewMeta` + `SemanticView` — model immutability and field collection
- `src/cubano/fields.py`: All field descriptor types + `OrderTerm` + `NullsOrdering`
- `src/cubano/query.py`: `Query` builder — all chain methods plus `fetch()` and `to_sql()`
- `src/cubano/filters.py`: `Q` filter tree
- `src/cubano/registry.py`: Engine registry — `register()`, `get_engine()`, `unregister()`, `reset()`
- `src/cubano/engines/sql.py`: `SQLBuilder` + all `Dialect` classes — SQL generation logic lives here
- `src/cubano/codegen/generator.py`: `generate_sql_for_files()` — codegen pipeline orchestrator

**Testing:**
- `tests/conftest.py`: `Sales` model fixture, `engine` fixture, `registry_cleanup` autouse fixture
- `src/cubano/conftest.py`: `doctest_setup` autouse fixture for `--doctest-modules`

## Naming Conventions

**Files:**
- Core modules: flat snake_case (`models.py`, `fields.py`, `query.py`)
- Test files: `test_<module>.py` mirroring the source module name
- Jinja2 templates: `<backend>.<output_format>.jinja2`

**Directories:**
- Subpackages use lowercase single-word names: `engines/`, `codegen/`, `cli/`, `testing/`

**Classes:**
- ORM classes: `PascalCase` (`SemanticView`, `SemanticViewMeta`, `Query`, `Row`)
- Field types: Semantic domain names (`Metric`, `Dimension`, `Fact`)
- Engine/Dialect classes: `<Backend>Engine` / `<Backend>Dialect` pattern (`SnowflakeEngine`, `DatabricksDialect`, `MockEngine`)
- Codegen internals: `<Purpose>Data` for data transfer objects (`ModelData`, `FieldData`)

**Private vs. Public:**
- `Query` private fields use `_` prefix (`_metrics`, `_dimensions`, `_filters`, `_order_by_fields`, `_limit_value`, `_using`)
- Module-level private state uses `_` prefix (`registry._engines`)
- `_validate_for_execution()` is private — called by `fetch()` and `to_sql()`, not user-facing

## Where to Add New Code

**New SemanticView model (user code — not in this package):**
- Create a `.py` file in user project, subclass `SemanticView` with `view='view_name'` keyword
- No changes needed in `src/cubano/`

**New field type (e.g., `TimeDimension`):**
- Add to `src/cubano/fields.py` as a `Field` subclass
- Export from `src/cubano/__init__.py`
- Update type checks in `src/cubano/query.py` (`.dimensions()` currently checks `isinstance(f, Dimension | Fact)`)

**New Query method:**
- Add to `src/cubano/query.py` — must return `replace(self, ...)` for immutability
- Add corresponding private field to the `@dataclass(frozen=True)` class header
- Propagate to `SQLBuilder` in `src/cubano/engines/sql.py` if it affects SQL generation

**New warehouse backend:**
- Create `src/cubano/engines/<backend>.py` implementing `Engine` ABC (`to_sql`, `execute`)
- Create `<Backend>Dialect` in `src/cubano/engines/sql.py` implementing `Dialect` ABC
- Export from `src/cubano/engines/__init__.py`
- Add optional dependency group in `pyproject.toml` (`[project.optional-dependencies]`)
- Add `--backend` option value in `src/cubano/cli/codegen.py` `Backend` enum
- Add Jinja2 template to `src/cubano/codegen/templates/`

**New CLI subcommand:**
- Create function in `src/cubano/cli/` (new file or in `codegen.py` if related)
- Register with `app.command('name')(function)` in `src/cubano/cli/__init__.py`

**New test:**
- Unit tests for `src/cubano/<module>.py` → `tests/test_<module>.py`
- Codegen tests → `tests/codegen/test_<component>.py`
- Integration test fixtures → `tests/codegen/fixtures/` (plain Python files with `SemanticView` subclasses)

**Utilities / helpers:**
- Shared test helpers → `tests/conftest.py`
- Shared doctest helpers → `src/cubano/conftest.py`
- CLI utilities → `src/cubano/cli/utils.py`

## Special Directories

**`site/`:**
- Purpose: MkDocs-generated static documentation site
- Generated: Yes (`mkdocs build`)
- Committed: No (generated artifact)

**`cubano-jaffle-shop/`:**
- Purpose: Example user workspace demonstrating Cubano with Jaffle Shop dbt models
- Generated: No
- Committed: Yes
- Note: uv workspace member (`[tool.uv.workspace] members = ["cubano-jaffle-shop"]`)

**`dbt-jaffle-shop/`:**
- Purpose: Reference dbt project (not cubano code); used for integration test setup
- Committed: Yes (submodule-like reference project)

**`.planning/`:**
- Purpose: GSD planning documents, phase plans, research
- Generated: No
- Committed: Yes

**`src/cubano/codegen/templates/`:**
- Purpose: Jinja2 templates bundled with the package
- Generated: No (authored templates)
- Committed: Yes
- Loaded at runtime via `FileSystemLoader(Path(__file__).parent / "templates")`

---

*Structure analysis: 2026-02-17*
