# Technology Stack

**Analysis Date:** 2026-02-17

## Languages

**Primary:**
- Python >=3.11 - All source code in `src/cubano/`

**Template:**
- Jinja2 templates - Code generation output in `src/cubano/codegen/templates/`
  - `snowflake.sql.jinja2` - Snowflake CREATE SEMANTIC VIEW SQL
  - `databricks.yaml.jinja2` - Databricks metric view YAML

## Runtime

**Environment:**
- CPython >=3.11 (developed on 3.14, CI tests on 3.11 and 3.14)

**Package Manager:**
- uv (astral-sh/setup-uv@v7 in CI)
- Lockfile: `uv.lock` present and committed

## Frameworks

**Core (no ORM/web framework — zero runtime dep model):**
- `typer>=0.12.0` - CLI framework for `cubano codegen` command
- `rich>=13.0.0` - Terminal output, progress bars, error formatting
- `jinja2>=3.1.0` - Template engine for SQL/YAML code generation

**Type Checking:**
- `basedpyright>=1.38.0` (strict mode) - Configured in `pyproject.toml` `[tool.basedpyright]`

**Linting/Formatting:**
- `ruff>=0.15.1` - Both lint (ruff check) and format (ruff format)
  - Target: py311
  - Line length: 100
  - Rules: E, F, W, I, UP, B, SIM, TCH, D

**Testing:**
- `pytest>=8.0.0` - Test runner
- `pytest-cov>=6.0.0` - Coverage reporting
- `pytest-xdist>=3.6.0` - Parallel test execution (`-n auto`)
- Doctests enabled via `--doctest-modules` in `pyproject.toml`

**Documentation:**
- `mkdocs>=1.6.0` - Docs site builder
- `mkdocs-material>=9.7.0` - Material theme
- `mkdocstrings[python]>=0.26.0` - API reference from docstrings
- `mkdocs-gen-files>=0.5.0` - Auto-generate reference pages
- `mkdocs-literate-nav>=0.6.0` - Navigation from SUMMARY.md
- `mkdocs-section-index>=0.3.0` - Section index pages
- Hosted at: `https://anentropic.github.io/cubano/`

**Build:**
- `uv_build>=0.9.18,<0.11.0` - Build backend (both main package and workspace member)

## Key Dependencies

**Optional (warehouse connectors — installed as extras):**
- `snowflake-connector-python>=4.3.0` - Snowflake SQL driver
  - Installed via: `pip install cubano[snowflake]`
  - Lazily imported in `src/cubano/engines/snowflake.py`
- `databricks-sql-connector[pyarrow]>=4.2.5` - Databricks SQL driver with Arrow support
  - Installed via: `pip install cubano[databricks]`
  - Lazily imported in `src/cubano/engines/databricks.py`

**Dev-only:**
- `pydantic-settings>=2.7.0` - Credential loading for integration tests (NOT a runtime dep)
  - Used only in `src/cubano/testing/credentials.py`
- `ipython>=9.10.0` - Interactive REPL for development
- `pdbpp>=0.12.0.post1` - Enhanced Python debugger

## Configuration

**Build & Tooling:**
- `pyproject.toml` - Single source of truth for project metadata, dependencies, tool config
- `uv.lock` - Lockfile for reproducible installs

**Type Checking:**
- `pyproject.toml` `[tool.basedpyright]` - strict mode, pythonVersion=3.11, includes src+tests
- `reportPrivateUsage = false` to allow test access to private members

**Linting:**
- `pyproject.toml` `[tool.ruff]` + `[tool.ruff.lint]`
- Notable ignores: D1 (don't require all docstrings), D213/D212 (summary line style)

**Testing:**
- `pyproject.toml` `[tool.pytest.ini_options]`
- Testpaths: `tests/`, `src/` (doctests from src)
- `doctest_optionflags = ["ELLIPSIS", "NORMALIZE_WHITESPACE"]`

**Documentation:**
- `mkdocs.yml` - Site configuration, MkDocs Material theme
- `scripts/gen_ref_pages.py` - Auto-generates API reference pages

## Workspace Structure

- Root package: `cubano` (`src/cubano/`)
- Workspace member: `cubano-jaffle-shop` (`cubano-jaffle-shop/`) - Example models from dbt-jaffle-shop
- Workspace configured via `[tool.uv.workspace]` and `[tool.uv.sources]` in root `pyproject.toml`

## Platform Requirements

**Development:**
- Python >=3.11
- uv package manager
- No database required for unit/mock tests

**Production:**
- Any platform running Python >=3.11
- Optional: `cubano[snowflake]` for Snowflake connectivity
- Optional: `cubano[databricks]` for Databricks connectivity

---

*Stack analysis: 2026-02-17*
