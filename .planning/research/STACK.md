# Technology Stack

**Project:** Cubano
**Version:** v0.1 (core) + v0.2 (codegen, integration testing, docs)
**Researched:** 2026-02-17
**Confidence:** HIGH

## Recommended Stack

### Core Language & Runtime (v0.1 — unchanged)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | >=3.11 | Runtime | Minimum for modern typing features (Self, TypeVarTuple, StrEnum). Dev on 3.14. |

### Build & Packaging (v0.1 — unchanged)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| uv | latest | Package manager & virtualenv | Fast, modern Python tooling. Already configured in repo. |
| uv-build | >=0.9.18 | Build backend | Already configured in pyproject.toml. Lightweight alternative to setuptools/hatch. |
| pyproject.toml | — | Project metadata | PEP 621 standard. Single config file for project metadata, dependencies, tool config. |

### Testing (v0.1 base + v0.2 additions)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | >=8.0.0 | Test framework | Industry standard for Python. Simple, extensible, great fixture system. Already in use (265 tests passing). |
| pytest-cov | >=6.0.0 | Coverage reporting | Standard coverage plugin for pytest. |
| snowflake-connector-python | >=4.3.0 | Real Snowflake integration | v0.2: Required for integration tests executing actual queries against Snowflake. Installed as optional extra. |

### Code Quality (v0.1 — unchanged)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ruff | >=0.15.1 | Linter + formatter | Already configured in pyproject.toml. Replaces flake8, isort, black in one fast tool. |
| basedpyright | >=1.38.0 | Type checking (strict mode) | Already configured in pyproject.toml. Strict mode catches metaclass and descriptor typing issues. |
| pre-commit | latest | Git hooks | Already configured in repo (.pre-commit-config.yaml). Runs ruff checks on commit. |

### Codegen Stack (v0.2 — NEW)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Jinja2 | >=3.1.6 | Template engine for SQL generation | Industry standard for Python templating. Used to render SQL CREATE VIEW statements from Cubano model metadata. Lightweight, fast, security-hardened. |
| Click | >=8.3.1 | CLI framework | v0.2: Build `cubano` command-line tool for codegen. Composable, decorator-based, auto-generates help. Same team as Flask (Pallets). |

### Documentation Stack (v0.2 — NEW)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| MkDocs | >=1.6.1 | Documentation site generator | v0.2: Generate and serve HTML docs from Markdown. Fast, live preview during authoring, ideal for API docs. Simple YAML config. |
| Material for MkDocs | latest | Professional MkDocs theme | v0.2: Polished Material Design theme. Mobile responsive, search included, widely adopted (FastAPI, Pydantic, etc.). |
| mkdocstrings | latest | Auto-generate API docs from docstrings | v0.2: Extract docstrings from Python code, generate API reference pages. Supports Google/NumPy/Sphinx docstring styles. |
| mkdocstrings-python | latest | Python handler for mkdocstrings | v0.2: Python-specific docstring extraction and formatting using Griffe. Type annotations rendered as cross-references. |

### Backend Drivers (Extras — v0.1 unchanged, v0.2 enhanced)

| Technology | Version | Purpose | When Installed |
|------------|---------|---------|----------------|
| snowflake-connector-python | >=4.3.0 | Snowflake connectivity | `pip install cubano[snowflake]`. Required for v0.2 integration tests and real query execution. |
| databricks-sql-connector | >=4.2.5 | Databricks connectivity | `pip install cubano[databricks]` |

## Installation Commands

### v0.1 Core (existing)

```bash
# Development setup (all extras + dev tools)
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

### v0.2 Additions (new dev dependencies)

```bash
# Add to pyproject.toml [dependency-groups.dev]
# Already present via "uv sync --all-extras":
# - jinja2>=3.1.6
# - click>=8.3.1
# - mkdocs>=1.6.1
# - mkdocs-material>=14.x (latest)
# - mkdocstrings>=0.28.x (latest)
# - mkdocstrings-python>=1.x (latest)

# To add individually:
uv pip install jinja2 click mkdocs mkdocs-material mkdocstrings mkdocstrings-python
```

## Recommended pyproject.toml Changes for v0.2

```toml
[dependency-groups]
dev = [
    # v0.1 existing
    "basedpyright>=1.38.0",
    "ipython>=9.10.0",
    "pdbpp>=0.12.0.post1",
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.15.1",

    # v0.2 NEW
    "jinja2>=3.1.6",           # Codegen: SQL template rendering
    "click>=8.3.1",            # Codegen: CLI tool
    "mkdocs>=1.6.1",           # Docs: Site generation
    "mkdocs-material>=14.0",   # Docs: Theme
    "mkdocstrings>=0.28.0",    # Docs: Autodoc from docstrings
    "mkdocstrings-python>=1.0", # Docs: Python docstring handler
]
```

## Technology Decisions by Feature

### Codegen: Cubano Models → SQL

**Stack:** Jinja2 + Click

**Why Jinja2:**
- Cubano models are Python classes with metaclass metadata; Jinja2 templates can iterate over `_fields`, access class attributes directly
- Renders clean, readable SQL with control flow (IF blocks for optional fields, FOR loops for field lists)
- Fast: single-pass compilation. No dependencies beyond stdlib
- Safe: auto-escaping for strings prevents SQL injection in generated code

**Why Click:**
- `cubano models my_module.py --output sql/` — simple, discoverable interface
- Auto-generates `--help` from docstrings
- Supports subcommands (future: `cubano generate`, `cubano validate`, etc.)
- Same team as Flask/Werkzeug — proven pattern for CLI tools in Python ecosystem

**Example Usage:**
```bash
cubano codegen --input models.py --output views.sql --dialect snowflake
```

**Why NOT SQLAlchemy/Alembic:**
- Overkill: Cubano generates simple CREATE VIEW statements, not schema migrations
- Alembic is for tracking changes; Cubano is for one-shot code generation from model definitions
- Heavy dependencies; Cubano philosophy is "zero required deps for core"

### Integration Testing: Real Snowflake Queries

**Stack:** pytest + snowflake-connector-python + conftest fixtures

**Why this approach:**
- pytest already in use (265 tests). Fixture system (setup/teardown) is perfect for Snowflake session management
- snowflake-connector-python is already an optional extra for backend driver
- v0.2 integration tests = actual queries against real Snowflake account (or test warehouse)
- Fixture pattern: Create session once per test module, reuse across tests, clean up after

**Fixture Pattern for v0.2:**
```python
# tests/integration/conftest.py
@pytest.fixture(scope="module")
def snowflake_session():
    """Real Snowflake session for integration tests."""
    from snowflake.connector import connect
    session = connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse="test_warehouse",
    )
    yield session
    session.close()

@pytest.fixture
def test_view(snowflake_session):
    """Create a test view, yield, drop after test."""
    snowflake_session.execute("CREATE TEMP VIEW test_view AS SELECT 1 AS id")
    yield
    snowflake_session.execute("DROP VIEW IF EXISTS test_view")
```

**Why NOT fakesnow/snowflake-vcrpy (for now):**
- fakesnow: Early stage; doesn't emulate all Snowflake semantics
- snowflake-vcrpy (record/replay): Good for CI speed, but requires initial recording against real Snowflake
- **Phase 1 (v0.2):** Use real Snowflake for truth. Later phases can add VCR for CI speed

**Why NOT testcontainers:**
- No Snowflake testcontainer exists (unlike PostgreSQL)
- Snowflake is cloud-only; running locally requires network access anyway
- Better to use real test warehouse than attempt emulation

### Documentation: Auto-Generated API Docs + Prose

**Stack:** MkDocs + Material theme + mkdocstrings + mkdocstrings-python

**Why this approach:**
- **MkDocs:** Simple, Markdown-based, live reload (`mkdocs serve`), perfect for prose + API docs
- **Material:** Production-quality theme used by FastAPI, Pydantic, Textual. Mobile responsive, built-in search, navigation sidebars
- **mkdocstrings:** Reads Python docstrings at build time, generates API reference pages. No runtime overhead
- **mkdocstrings-python:** Uses Griffe to parse Python code. Understands type annotations, cross-links types to docs

**Why NOT Sphinx:**
- Sphinx uses reStructuredText (RST), steeper learning curve
- Sphinx historically better for complex API docs, but mkdocstrings now covers that
- MkDocs is faster to set up, better DX for non-expert documentation writers
- Cubano docs are straightforward: models, fields, query API, examples

**Why NOT Quarto:**
- Quarto is overkill (originally for data science notebooks)
- Not specialized for Python API docs
- Adds complexity without benefit for library documentation

**Example mkdocs.yml for v0.2:**
```yaml
site_name: Cubano
theme:
  name: material
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true

nav:
  - Home: index.md
  - Getting Started: guides/getting-started.md
  - API Reference:
    - SemanticView: api/models.md
    - Fields: api/fields.md
    - Queries: api/query.md
```

**CI/CD Publishing (GitHub Actions):**
```yaml
# .github/workflows/publish-docs.yml
name: Publish Docs
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install mkdocs mkdocs-material mkdocstrings mkdocstrings-python
      - run: mkdocs build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/
      - uses: actions/deploy-pages@v4
```

## Alternatives Considered

| Feature | Recommended | Alternative | When to Use Alternative |
|---------|-------------|-------------|-------------------------|
| **SQL Codegen Template** | Jinja2 | string.Template (stdlib) | Only if template needs are trivial (no control flow). Cubano needs loops over fields. |
| **SQL Codegen Template** | Jinja2 | Mako | Mako is heavier, more for web. Jinja2 sufficient and faster. |
| **CLI Framework** | Click | Typer | Typer is newer, cleaner syntax (FastAPI-inspired). Click is battle-tested. v0.2 uses Click; Typer could replace in future. |
| **CLI Framework** | Click | argparse (stdlib) | argparse is verbose, harder to maintain. Click is minimal dependency. |
| **Integration Testing** | Real Snowflake | fakesnow | fakesnow is immature. Real Snowflake is source of truth. Use fakesnow in CI speed optimization phase later. |
| **Integration Testing** | Real Snowflake | snowflake-vcrpy | VCR is useful for CI speed, but requires initial recording. Do real tests first, add VCR as optimization. |
| **Docs Site** | MkDocs | Sphinx | Sphinx better for very complex API docs. Cubano's API is straightforward; MkDocs is faster/simpler. |
| **Docs Site** | MkDocs | Read the Docs (service) | Read the Docs can host MkDocs sites. Keep docs repo-local for now; RtD later if needed. |
| **Docs Theme** | Material | MkDocs default | Material is minimal additional complexity, huge UX win. Use it. |
| **Docstring Auto** | mkdocstrings | Sphinx autodoc | mkdocstrings is MkDocs-native. Sphinx autodoc requires Sphinx setup. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **SQLAlchemy Core** for codegen | Over-engineered. Cubano generates simple CREATE VIEW, not complex query builder. | Jinja2 templates |
| **Alembic** for codegen | Alembic is for migrations (tracking schema evolution). Codegen is one-shot SQL generation. | Jinja2 + Click CLI |
| **Mako** for templates | Heavier than Jinja2, more features not needed. Jinja2 is fast and sufficient. | Jinja2 |
| **Typer** (for now) | Newer, not as battle-tested as Click. Save for future refactor if desired. | Click |
| **Faker** or **factory_boy** | These generate test data; Cubano needs real Snowflake data. Not applicable. | Use SQL fixtures; create test data in Snowflake views |
| **Sphinx** for docs | Heavier than MkDocs, RST is harder to write. Cubano docs are prose + API. | MkDocs |
| **ReadTheDocs hosting** | Not needed yet. Keep docs in repo. Hosting adds deployment complexity. | GitHub Pages via Actions |
| **Quarto** for docs | Data science oriented, not a library docs tool. | MkDocs |
| **AI codegen** (e.g., Copilot) | Won't work reliably for generating SQL from Cubano model metadata. Use templates. | Jinja2 |
| **pytest-xdist** for integration tests | Don't parallelize Snowflake tests initially (can hit rate limits, increase costs). Run sequentially. | Standard pytest (no xdist) |

## Stack Patterns by Deployment Context

### Local Development

```
Python 3.11+ → pytest (with conftest fixtures)
↓
Jinja2 rendering (codegen preview)
↓
MkDocs serve (live docs update)
↓
Real Snowflake account (test warehouse)
```

### CI/CD Pipeline (GitHub Actions)

```
Checkout → Install via uv sync
↓
pytest (unit + integration against Snowflake)
↓
Codegen tests (render templates, compare SQL)
↓
Build docs via mkdocs build
↓
Deploy docs to GitHub Pages
↓
Package with uv-build
```

### Production (installed by users)

```
Core: pip install cubano (zero deps)
↓
Backend: pip install cubano[snowflake] (gets snowflake-connector)
↓
CLI tools not included by default (optional)
```

## Version Compatibility Matrix

| Component | Version | Python | Notes |
|-----------|---------|--------|-------|
| Jinja2 | >=3.1.6 | >=3.7 | Requires Python 3.7+; used in dev only |
| Click | >=8.3.1 | >=3.10 | Requires Python 3.10+; used in dev only |
| MkDocs | >=1.6.1 | >=3.8 | Requires Python 3.8+; used in dev only |
| mkdocs-material | latest (9.x-14.x) | >=3.8 | Follows MkDocs compatibility |
| mkdocstrings | >=0.28.0 | >=3.8 | Uses Griffe for parsing |
| mkdocstrings-python | >=1.0 | >=3.8 | Requires mkdocstrings |
| pytest | >=8.0.0 | >=3.8 | Already in use; >=8.0 has excellent fixture scoping |
| snowflake-connector-python | >=4.3.0 | >=3.8 | Required for integration tests only |
| basedpyright | >=1.38.0 | >=3.11 | Already in use; strict mode enabled |
| ruff | >=0.15.1 | >=3.7 | Already in use |

**Compatibility Notes:**
- All v0.2 new dependencies (Jinja2, Click, MkDocs stack) require >=3.7 or >=3.8, which is well below Cubano's >=3.11 minimum
- No version conflicts expected; all are standard, widely-used packages
- snowflake-connector-python >=4.3.0 is required for v0.2 integration tests; already listed as optional extra

## Zero Required Dependencies (v0.1 preserved for v0.2)

Cubano **core library** still has **no mandatory third-party dependencies**:

```python
# Core uses only stdlib
import abc, typing, dataclasses, collections.abc, re, copy
```

**v0.2 additions are dev-only:**
- Codegen CLI (Jinja2, Click) — only used by maintainers to generate SQL
- Integration tests (snowflake-connector) — only run in CI/dev
- Documentation tools (MkDocs stack) — only for building docs
- None of these are required for **users** installing `pip install cubano`

This preserves Cubano's design principle: lightweight core, optional tooling.

## Integration with Existing Tooling

### uv (existing)

v0.2 dependencies integrate seamlessly:
```bash
# Update pyproject.toml, then:
uv sync --all-extras  # Installs all dev deps including v0.2 tools

# Or selective install:
uv pip install jinja2 click
```

### pytest (existing, 265 tests passing)

v0.2 adds integration test patterns to existing test suite:
```
tests/
├── unit/                  # Existing (265 tests)
├── integration/          # NEW for v0.2
│   ├── conftest.py       # Snowflake session fixture
│   ├── test_codegen.py   # Jinja2 rendering tests
│   └── test_snowflake_queries.py  # Real Snowflake tests
```

### basedpyright strict mode (existing)

v0.2 code should pass strict type checking. Jinja2, Click have type stubs.

### ruff (existing)

Add to `pyproject.toml [tool.ruff.lint]` if needed:
```toml
extend-select = ["C901"]  # Complexity checks (optional, for codegen logic)
```

### GitHub Actions CI (existing)

Extend workflow to build and deploy docs:
```yaml
- name: Build docs
  run: mkdocs build
- name: Deploy to Pages
  uses: actions/deploy-pages@v4
```

## Rationale Summary

| v0.2 Feature | Chosen Stack | Why |
|--------------|--------------|-----|
| **SQL Codegen** | Jinja2 + Click | Fast templating + battle-tested CLI framework. Minimal, focused tools. |
| **Integration Tests** | pytest + snowflake-connector | Reuse existing pytest ecosystem. Real Snowflake for truth. |
| **API Docs** | MkDocs + Material + mkdocstrings | Simple, fast, beautiful. Standard in Python ecosystem (FastAPI, Pydantic). |
| **Docs Publishing** | GitHub Actions → Pages | Free, built-in, no external service needed. |

## Sources

**Code Generation:**
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [Click Documentation](https://click.palletsprojects.com/)
- [Real Python: Jinja Templating](https://realpython.com/primer-on-jinja-templating/)
- [DevToolbox: Click CLI Guide 2026](https://devtoolbox.dedyn.io/blog/python-click-typer-cli-guide)

**Integration Testing:**
- [Snowflake Documentation: Testing Snowpark Python](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-python-snowpark)
- [Snowflake Local Testing Framework](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally)
- [snowflake-vcrpy GitHub](https://github.com/Snowflake-Labs/snowflake-vcrpy)
- [fakesnow GitHub](https://github.com/tekumara/fakesnow)
- [pytest Fixtures Reference](https://docs.pytest.org/en/stable/reference/fixtures/)

**Documentation:**
- [MkDocs Official](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings GitHub](https://github.com/mkdocstrings/mkdocstrings)
- [mkdocstrings Python Usage](https://mkdocstrings.github.io/python/usage/)
- [GitHub Actions: Deploy Pages](https://github.com/actions/deploy-pages)
- [Publishing Your Site with MkDocs](https://squidfunk.github.io/mkdocs-material/publishing-your-site/)

**Comparison & Analysis:**
- [Python Docs Tools: MkDocs vs Sphinx](https://www.pythonsnacks.com/p/python-documentation-generator)
- [MkDocs vs Sphinx: Detailed Comparison](https://inventivehq.com/blog/python-package-documentation-guide)

---

*Stack research for Cubano v0.2 (codegen, integration testing, documentation)*
*Researched: 2026-02-17*
