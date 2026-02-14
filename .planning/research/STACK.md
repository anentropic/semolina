# Technology Stack

**Project:** Cubano
**Researched:** 2026-02-14

## Recommended Stack

### Core Language & Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | >=3.11 | Runtime | Minimum for modern typing features (Self, TypeVarTuple, StrEnum). Dev on 3.14. |

### Build & Packaging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| uv | latest | Package manager & virtualenv | Fast, modern Python tooling. Already configured in repo. |
| uv-build | >=0.9.18 | Build backend | Already configured in pyproject.toml. Lightweight alternative to setuptools/hatch. |
| pyproject.toml | — | Project metadata | PEP 621 standard. Single config file for project metadata, dependencies, tool config. |

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | latest | Test framework | Industry standard for Python. Simple, extensible, great fixture system. |
| pytest-cov | latest | Coverage reporting | Standard coverage plugin for pytest. |

### Code Quality

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ruff | latest | Linter + formatter | Already configured in pyproject.toml. Replaces flake8, isort, black in one fast tool. |
| pre-commit | latest | Git hooks | Already configured in repo (.pre-commit-config.yaml). Runs ruff checks on commit. |
| mypy | latest | Type checking | Cubano is a typed library — metaclass, descriptors, generics all benefit from type checking. |

### Backend Drivers (Extras)

| Technology | Version | Purpose | When Installed |
|------------|---------|---------|----------------|
| snowflake-connector-python | latest | Snowflake connectivity | `pip install cubano[snowflake]` |
| databricks-sql-connector | latest | Databricks connectivity | `pip install cubano[databricks]` |

## Zero Required Dependencies

Cubano core has **no mandatory third-party dependencies**. This is a deliberate design choice:

- **Lower barrier to adoption**: No dependency conflicts with existing projects
- **Smaller install footprint**: Core is pure Python
- **Backend drivers as extras**: Only installed when needed
- **Standard library is sufficient**: `dataclasses`, `abc`, `typing`, `re`, `collections` cover all needs

The core library uses only Python standard library modules:
- `abc` — Engine abstract base class
- `typing` — Type annotations, generics
- `dataclasses` — Internal data structures (Query state, Row)
- `collections.abc` — Mapping protocol for Row
- `re` — SQL identifier validation
- `copy` — Immutable query builder (deepcopy for Q-objects)

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Build backend | uv-build | hatchling, setuptools | uv-build already configured, lighter weight |
| Formatter | ruff | black | ruff already configured, faster, does both linting and formatting |
| Linter | ruff | flake8 + isort | ruff replaces both in one tool |
| Type checker | mypy | pyright | mypy is more established in the Python ecosystem, better for libraries |
| Test framework | pytest | unittest | pytest is more ergonomic, better fixtures, better assertions |
| Package manager | uv | pip, poetry | uv already configured, fastest Python package manager |

## Installation

```bash
# Development setup
uv sync --all-extras

# Core only (no backend drivers)
pip install cubano

# With Snowflake backend
pip install cubano[snowflake]

# With Databricks backend
pip install cubano[databricks]

# With all backends
pip install cubano[snowflake,databricks]
```

## Project Structure

```
cubano/
├── pyproject.toml
├── src/
│   └── cubano/
│       ├── __init__.py          # Public API exports
│       ├── fields.py            # Metric, Dimension, Fact descriptors
│       ├── models.py            # SemanticViewMeta metaclass, SemanticView base
│       ├── query.py             # QuerySet fluent builder
│       ├── filters.py           # Q objects for filter composition
│       ├── sql.py               # SQL compilation (dialect-specific)
│       ├── engine.py            # Engine ABC + MockEngine
│       ├── registry.py          # Engine registry (name → engine)
│       ├── results.py           # Row class for query results
│       └── backends/
│           ├── __init__.py
│           ├── snowflake.py     # SnowflakeEngine
│           └── databricks.py    # DatabricksEngine
└── tests/
    ├── conftest.py              # Shared fixtures (model definitions, mock engine)
    ├── test_fields.py
    ├── test_models.py
    ├── test_query.py
    ├── test_filters.py
    ├── test_sql.py
    ├── test_engine.py
    ├── test_registry.py
    ├── test_results.py
    └── test_backends/
        ├── test_snowflake.py
        └── test_databricks.py
```

## Key Technical Decisions

### Why No ORM Dependencies (SQLAlchemy, etc.)

Cubano generates simple SQL strings targeting semantic view syntax. It doesn't need:
- Connection pooling (backend driver concern)
- Schema migration
- Complex join resolution
- Query plan optimization

The SQL generated is straightforward SELECT/GROUP BY/ORDER BY — no need for a full SQL toolkit.

### Why Metaclass Over Descriptors-Only

The metaclass approach (`class Sales(SemanticView, view='sales')`) provides:
- Natural class inheritance syntax
- Automatic field registration at class definition time
- Clean `__init_subclass__` or `__new__` hook for validation
- Familiar pattern for Python developers (Django models, SQLAlchemy declarative)

### Why mypy Over pyright

- mypy has better support for metaclass typing patterns
- More established in the library ecosystem
- Better plugin system if needed for custom type narrowing
- pyright is excellent but optimized for application development with VS Code

## Sources

- Python typing documentation (stdlib)
- uv documentation (already configured in project)
- Snowflake Connector for Python docs
- Databricks SQL Connector docs
- Project design notes (.resources/design/notes.md)
- Existing pyproject.toml configuration
