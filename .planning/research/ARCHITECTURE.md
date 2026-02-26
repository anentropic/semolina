# Architecture: v0.2 Integration Strategy

**Project:** Cubano v0.2
**Research Date:** 2026-02-17
**Scope:** Codegen CLI, integration testing, documentation generation, v0.1 API compatibility
**Confidence:** HIGH

---

## Executive Summary

Cubano v0.2 must integrate three new components—codegen (CLI tool), integration tests, and documentation—while maintaining strict backward compatibility with v0.1's published public API.

**Key architectural decisions:**

1. **Codegen lives as a separate CLI tool** (`cubano-codegen`), not in the core library. This maintains the core package's zero-dependency constraint and allows independent versioning/iteration on code generation strategies.

2. **Integration tests use the existing workspace pattern** (cubano-jaffle-shop) as the integration test harness, extending it to validate codegen output and real-world usage patterns. No new testing infrastructure is needed.

3. **Documentation uses MkDocs** for simplicity and GitHub Pages hosting via existing CI/CD infrastructure. Sphinx is rejected because v0.1 has too limited public API surface for autodoc to be valuable; MkDocs provides cleaner manual docs for a semantic layer.

4. **v0.1 API compatibility is strict**: All public exports from `cubano/__init__.py` remain unchanged. v0.2 adds capabilities without breaking existing code.

**Build order implications:**
- Phase 1: Extend cubano-jaffle-shop to validate current API
- Phase 2: Build cubano-codegen (separate package)
- Phase 3: Add documentation infrastructure and content
- Phase 4: Publish all three (core, codegen, docs)

---

## 1. Component Architecture

### 1.1 Core Library (v0.1 → v0.2)

**Status:** Stable, published on PyPI
**Public API:** All exports in `src/cubano/__init__.py`

Current public API (frozen in v0.2):
```python
from cubano import (
    SemanticView,      # Base class for models
    Metric, Dimension, Fact,  # Field types
    Query,             # Immutable query builder
    Q,                 # Filter composition
    OrderTerm, NullsOrdering,  # Ordering utilities
    Row,               # Result wrapper
    register, get_engine, unregister,  # Registry API
)
```

**v0.2 Changes (internal only):**
- No changes to exported types
- Can add new private modules (`_codegen_support`, etc.) without breaking API
- Can add new internal helper functions as `_private_` (underscore prefix = not API)
- Can extend `Query` with new methods (adds capability, doesn't break existing code)

**Backward Compatibility Rule:** If it's in `__all__`, it's API. Don't remove, rename, or change signature.

### 1.2 Codegen Tool (NEW)

**Package Name:** `cubano-codegen`
**Location:** Separate repository (or `/src/cubano_codegen/` as sister package in same repo)
**Entry Point:** CLI tool, e.g., `cubano-codegen --help`

**Purpose:** Generate Cubano model definitions from dbt semantic models or other schema definitions.

**Why Separate:**
- Core library has zero dependencies; codegen may need additional dependencies (YAML parsers, API clients, etc.)
- Users who only query existing models don't need codegen
- Independent versioning (codegen can iterate faster than core)
- Follows SQLAlchemy Migrate, Alembic pattern (migrations are separate tools)

**Input/Output:**
```
Input: dbt manifest.json or semantic_model YAML
Output: Python file with SemanticView models
```

**Example Flow:**
```bash
# User has dbt project with semantic models
cubano-codegen from-dbt \
  --manifest /path/to/manifest.json \
  --output models.py

# Generates:
# class Orders(SemanticView, view='orders'):
#     order_total = Metric()
#     customer_id = Dimension()
#     ...
```

**Why Not Integrated into Core:**
- dbt is not a dependency of Cubano (zero deps principle)
- Code generator is a development-time tool, not runtime
- Users may have other schema sources (Snowflake UDV, Databricks Unity Catalog, hand-written)

### 1.3 Integration Tests (cubano-jaffle-shop)

**Current Role:** Example workspace demonstrating Cubano API usage

**v0.2 Role:** Becomes dual-purpose workspace:
1. **Example:** Shows how to use Cubano with real dbt semantic models
2. **Integration Test Suite:** Validates that Cubano works end-to-end with jaffle-shop models

**Structure:**
```
cubano-jaffle-shop/
├── pyproject.toml        # Dependencies: cubano (workspace=true)
├── README.md
├── src/cubano_jaffle_shop/
│   ├── __init__.py       # Public models export
│   ├── jaffle_models.py  # Curated models from dbt
│   └── test_models.py    # Integration tests (NEW in v0.2)
└── dbt/                  # dbt project (shared with ../dbt-jaffle-shop)
    └── models/
        └── marts/
            ├── orders.yml
            ├── customers.yml
            └── products.yml
```

**Test Scope:**
```python
# tests/test_models.py
from cubano_jaffle_shop import Orders, Customers

def test_orders_model_structure():
    """Orders has expected fields"""
    assert 'order_total' in Orders._fields
    assert 'customer_id' in Orders._fields

def test_query_generation():
    """Queries compile to valid SQL"""
    query = Orders.query().metrics(Orders.order_total)
    sql = query.to_sql('snowflake')
    assert 'AGG(' in sql

def test_execution():
    """Queries execute against mock engine"""
    # Uses MockEngine with seed data
    query = Orders.query().metrics(Orders.order_total)
    results = query.fetch()
    assert len(results) > 0
```

**Why Not a Separate Test Suite:**
- Reuses existing cubano-jaffle-shop structure
- Models are already there; just add tests
- uv workspace handles dependency correctly
- Single lockfile ensures consistency
- Can run with `uv run pytest cubano-jaffle-shop/`

### 1.4 Documentation

**Tool:** MkDocs (not Sphinx)
**Source:** `/docs/` directory
**Hosting:** GitHub Pages (via CI/CD workflow)
**Output:** Published to `github.io` or custom domain

**Why MkDocs over Sphinx:**

| Criterion | MkDocs | Sphinx |
|-----------|--------|--------|
| Markup | Markdown (familiar) | reStructuredText (Python-specific) |
| Autodoc | Manual docs only | Auto from docstrings (overkill for 28 API items) |
| Setup | 5 minutes | 30 minutes |
| Maintenance | Simpler config | More complex |
| Live reload | Built-in | Requires plugins |
| Suitable for | Library with 20-50 items | Large frameworks (Django, Sphinx itself) |

**Content Structure:**
```
docs/
├── mkdocs.yml          # MkDocs config
├── docs_requirements.txt # mkdocs, mkdocs-material, plugins
├── index.md            # Home page / getting started
├── installation.md
├── guide/
│   ├── models.md       # How to define SemanticView models
│   ├── queries.md      # Query builder API
│   ├── filters.md      # Q objects and filtering
│   ├── execution.md    # Engines and result handling
│   ├── codegen.md      # Using cubano-codegen (NEW)
│   └── examples.md     # Real-world usage patterns
├── api/
│   ├── models.md       # SemanticView, Field types
│   ├── query.md        # Query class reference
│   ├── engines.md      # Engine interface
│   └── registry.md     # register(), get_engine()
└── development/
    ├── contributing.md
    ├── testing.md
    └── architecture.md
```

**GitHub Pages Deployment:**
- Add `.github/workflows/docs.yml` (or extend existing workflow)
- Build on every push to `main`
- Deploy to `gh-pages` branch
- Custom domain configured in repo settings

---

## 2. Integration Points (v0.1 ↔ v0.2)

### 2.1 How Codegen Interacts with Core

**Codegen reads:**
- Public Cubano classes: `SemanticView`, `Metric`, `Dimension`, `Fact`
- Field introspection: `Orders._fields`, `Orders._view_name` (public API)

**Codegen generates:**
```python
# Output: Python code
from cubano import SemanticView, Metric, Dimension

class Orders(SemanticView, view='orders'):
    order_total = Metric()
    ordered_at = Dimension()
```

**No Core Changes Required:**
- Codegen is a standalone tool
- Reads public API only
- Generates code compatible with current v0.1 API

### 2.2 How Integration Tests Validate Both

**Tests run against:**
1. **Unit layer** (core library in `src/cubano/`)
2. **Model layer** (cubano-jaffle-shop models in `src/cubano_jaffle_shop/`)
3. **Execution layer** (MockEngine, optional real engines)

**Example test flow:**
```python
# Test validates: Model definition → Query → SQL → Execution
from cubano_jaffle_shop import Orders
from cubano import MockEngine, register

# Setup
mock = MockEngine()
mock.seed('orders', [
    {'order_total': 100, 'ordered_at': '2024-01-01'},
    {'order_total': 200, 'ordered_at': '2024-01-02'},
])
register(mock, name='test')

# Execute
query = Orders.query().using('test').metrics(Orders.order_total)
results = query.fetch()

# Verify
assert len(results) == 2
assert results[0].order_total == 100
```

**Why This Works:**
- Models are imported from published package
- Cubano core is already tested (v0.1 unit tests)
- Integration tests validate interaction between model definitions and query execution
- No test code changes needed in core; all new tests are in cubano-jaffle-shop

### 2.3 How Documentation References Both

**Docs structure acknowledges:**
- `cubano` (core library): Installation, API reference, concepts
- `cubano-codegen` (separate tool): "Using Codegen" guide section
- `cubano-jaffle-shop` (example): Linked from "Examples" section

**Example navigation:**
```
Getting Started
├── Installation (cubano, cubano-codegen)
├── First Query (cubano core)
└── Generating Models (cubano-codegen)

Guides
├── Defining Models (hand-written vs. cubano-codegen)
├── Query Building (cubano core)
└── Examples (cubano-jaffle-shop live code)

API Reference
├── SemanticView, Query, etc. (cubano core)
└── Codegen CLI (cubano-codegen)
```

---

## 3. New vs. Modified Components

### 3.1 Core Library (`src/cubano/`)

**Status:** Minimal changes, strict API compatibility

| Component | Status | Notes |
|-----------|--------|-------|
| `models.py` | No change | SemanticView API frozen |
| `fields.py` | No change | Metric, Dimension, Fact frozen |
| `query.py` | Can extend | New methods OK if not breaking |
| `engines/` | No change | Engine interface frozen |
| `registry.py` | No change | register/get_engine frozen |
| `results.py` | No change | Row API frozen |
| `filters.py` | No change | Q object API frozen |
| `__init__.py` | No change | Public exports frozen |

**Potential v0.2 Enhancements (internal only):**
- Add `_codegen_support.py` module (private, not exported)
- Add introspection helpers for codegen to use (private)
- Add `_ValidatedQuery` subclass for type checking (private)

### 3.2 Codegen Tool (`cubano-codegen/`)

**Status:** NEW package

**Structure:**
```
cubano-codegen/
├── pyproject.toml
│   ├── name = "cubano-codegen"
│   ├── version = "0.1.0" (independent versioning)
│   ├── dependencies = ["cubano", "pyyaml"]  # Depends on core
│   └── scripts = { cubano-codegen = "cubano_codegen.cli:main" }
├── src/cubano_codegen/
│   ├── __init__.py
│   ├── cli.py           # Entry point
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── dbt.py       # dbt manifest → Python models
│   │   └── snowflake.py # Snowflake schema → Python models (future)
│   └── codegen_utils.py # Field inference, naming conventions
└── tests/
    └── test_dbt_generator.py
```

**Dependencies:**
- `cubano` (core library, to import types)
- `pyyaml` (optional, for dbt manifest parsing)
- `click` or `typer` (for CLI)

**Not a workspace member?** Can be:
- **Option A:** Separate package in same repo (`cubano-codegen/` alongside `cubano-jaffle-shop/`)
- **Option B:** Separate repository entirely
- **Option C:** Same repo, separate workspace member (with `[tool.uv.workspace] members = ["cubano", "cubano-codegen", "cubano-jaffle-shop"]`)

**Recommendation:** Option C (add to workspace)
- Keeps everything together
- Single lockfile for consistency
- Easier development (e.g., `uv run cubano-codegen`)
- Can publish independently to PyPI

### 3.3 Integration Tests (`cubano-jaffle-shop/`)

**Status:** Extend existing package

| Component | Status | Notes |
|-----------|--------|-------|
| `src/cubano_jaffle_shop/jaffle_models.py` | Keep | Existing models |
| `src/cubano_jaffle_shop/test_models.py` | NEW | Add integration tests |
| `src/cubano_jaffle_shop/__init__.py` | Extend | Export test fixtures |
| `pyproject.toml` | Extend | Add pytest as dev dependency |

**New test structure:**
```python
# tests/test_integration.py
import pytest
from cubano import MockEngine, register

@pytest.fixture
def mock_engine():
    """Seed mock engine with jaffle-shop data"""
    mock = MockEngine()
    # Load seed data from CSV or JSON
    mock.seed('orders', [
        {'order_id': 1, 'order_total': 100, 'ordered_at': '2024-01-01'},
        ...
    ])
    return mock

def test_orders_query_basic(mock_engine):
    """Validate Orders model queries"""
    register(mock_engine, name='test')
    query = Orders.query().using('test').metrics(Orders.order_total)
    results = query.fetch()
    assert len(results) > 0

def test_complex_filters(mock_engine):
    """Validate filter composition"""
    register(mock_engine, name='test')
    query = (Orders.query().using('test')
        .metrics(Orders.order_total)
        .dimensions(Orders.ordered_at)
        .filter(Q(order_total__gt=100)))
    sql = query.to_sql('snowflake')
    assert 'WHERE' in sql
```

---

## 4. Build Order and Dependencies

### 4.1 Phase Ordering

**Phase 1: Integration Test Foundation**
- Extend cubano-jaffle-shop with test suite
- Validates v0.1 API stability
- No codegen or docs needed yet
- **Duration:** 1-2 days
- **Deliverable:** `cubano-jaffle-shop` with passing integration tests

**Phase 2: Codegen Tool**
- Build `cubano-codegen` CLI
- Implement dbt manifest generator
- Basic testing (unit + integration)
- **Duration:** 3-5 days
- **Deliverable:** `cubano-codegen` package, publishable to PyPI
- **Blocks:** Nothing (independent)

**Phase 3: Documentation**
- Set up MkDocs structure
- Write user guides (models, queries, engines)
- Write API reference (auto-generated or manual)
- Add codegen guide
- **Duration:** 2-3 days
- **Deliverable:** `/docs/` directory, CI/CD workflow

**Phase 4: Release & Publishing**
- Update version numbers
- Publish to PyPI (both packages)
- Deploy docs to GitHub Pages
- **Duration:** 1 day
- **Deliverable:** v0.2 on PyPI, docs live

### 4.2 Dependency Graph

```
cubano (core) ← STABLE
  ↓
cubano-jaffle-shop ← depends on cubano
  ├─ Test suite (validates integration)
  ├─ Example models (used by codegen examples)
  └─ Seeds (used by integration tests)

cubano-codegen ← depends on cubano, pyyaml
  ├─ Generates models compatible with cubano
  ├─ Can be tested against cubano-jaffle-shop
  └─ Independent versioning

Documentation
  ├─ References cubano API
  ├─ Includes cubano-codegen guide
  ├─ Links to cubano-jaffle-shop examples
  └─ Builds in CI (no code dependency)
```

**Critical:** Codegen depends on Core. Core does NOT depend on Codegen.

### 4.3 Version Numbers

| Package | v0.1 | v0.2 | Notes |
|---------|------|------|-------|
| `cubano` | 0.1.0 | 0.2.0 | Minor bump (features, no breaking changes) |
| `cubano-codegen` | N/A | 0.1.0 | New package, starts at 0.1.0 |
| `cubano-jaffle-shop` | 0.1.0 | 0.1.1 | Patch bump (just added tests) |

**Reasoning:**
- Core is 0.2.0 (minor bump for new features)
- Codegen starts at 0.1.0 (new tool, pre-1.0)
- Jaffle-shop is 0.1.1 (backwards compatible extension)

---

## 5. API Compatibility Strategy

### 5.1 What's Protected (Cannot Break)

**All public exports in `cubano/__init__.py`:**
```python
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Q
from .models import SemanticView
from .query import Query
from .registry import get_engine, register, unregister
from .results import Row

__all__ = [
    "SemanticView",      # BASE CLASS — signature frozen
    "Metric",           # FIELD TYPE — signature frozen
    "Dimension",        # FIELD TYPE — signature frozen
    "Fact",             # FIELD TYPE — signature frozen
    "Query",            # CLASS — public methods frozen
    "Q",                # CLASS — public methods frozen
    "OrderTerm",        # TYPE — frozen
    "NullsOrdering",    # TYPE — frozen
    "register",         # FUNCTION — signature frozen
    "get_engine",       # FUNCTION — signature frozen
    "unregister",       # FUNCTION — signature frozen
    "Row",              # CLASS — public API frozen
]
```

**Specific guarantees:**
- `SemanticView` constructor and `__init_subclass__` signature unchanged
- `Query` methods (`.metrics()`, `.filter()`, etc.) return `Query` (chainable)
- `Query.fetch()` returns `list[Row]`
- `register()` accepts `engine, name, *, set_default`
- `Row` supports `row.field_name` and `row['field_name']`
- `Q` supports `&`, `|`, `~` operators

### 5.2 What's Free to Change (Internal)

**All private attributes and functions:**
```python
# These are implementation details, not API:
Query._metrics          # Can be renamed
Engine._conn            # Can be moved
compile_query()         # Private helper
_codegen_support        # New private module
_ValidatedQuery         # Private class
```

**Rules for v0.2:**
- Can add new private modules
- Can add new private methods to public classes (prefixed with `_`)
- Can rename private attributes
- Can change internal implementation entirely

### 5.3 Validation Method

**Before releasing v0.2:**

1. **Run v0.1 tests unchanged** — All 265 unit tests pass with v0.2 code
2. **Test imports from old code:**
   ```python
   # This code from v0.1 users must still work:
   from cubano import SemanticView, Query, register

   class MyModel(SemanticView, view='my_view'):
       revenue = Metric()

   query = MyModel.query().metrics(MyModel.revenue).fetch()
   ```
3. **Backwards compat test suite:**
   ```python
   # tests/test_api_compat.py
   def test_import_all_public_api():
       """All public exports still available"""
       import cubano
       for name in cubano.__all__:
           assert hasattr(cubano, name)

   def test_query_builder_chain_returns_query():
       """Query methods return Query (chainable)"""
       query = (MyView.query()
           .metrics(MyView.m1)
           .dimensions(MyView.d1)
           .filter(Q(x=1)))
       assert isinstance(query, Query)

   def test_row_attribute_access():
       """Row supports row.field syntax"""
       row = Row({'name': 'test'})
       assert row.name == 'test'
   ```

---

## 6. Testing Strategy

### 6.1 Test Organization (v0.2)

```
tests/                          # Core library unit tests
├── test_*.py                   # 265 existing tests (unchanged)
└── test_api_compat.py          # NEW: Backwards compatibility tests

cubano-jaffle-shop/
├── tests/                       # NEW: Integration tests
│   ├── conftest.py
│   ├── test_models.py           # Model structure validation
│   ├── test_queries.py          # Query building and execution
│   └── test_sql_generation.py   # SQL output validation
└── src/cubano_jaffle_shop/
    ├── __init__.py              # Export models and fixtures
    └── fixtures.py              # Seed data for MockEngine

cubano-codegen/
└── tests/
    ├── test_dbt_generator.py    # Unit tests for codegen
    └── fixtures/
        └── manifest.json         # Test dbt manifest
```

### 6.2 Test Execution (CI/CD)

**Current workflow (`ci.yml`) — unchanged:**
- Typecheck (basedpyright)
- Lint (ruff)
- Format (ruff format --check)
- Test (pytest tests/)

**New workflow additions (Phase 3):**
```yaml
# .github/workflows/ci.yml — add job
  integration-tests:
    name: Integration tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
      - run: uv sync --locked --dev
      - run: uv run pytest cubano-jaffle-shop/tests/
```

**New workflow for codegen tests:**
```yaml
  codegen-tests:
    name: Codegen tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
      - run: uv sync --locked --dev
      - run: uv run pytest cubano-codegen/tests/
```

---

## 7. Documentation Build & Deployment

### 7.1 MkDocs Configuration

**`docs/mkdocs.yml`:**
```yaml
site_name: Cubano
site_description: Python ORM for data warehouse semantic views
repo_url: https://github.com/your-org/cubano

theme:
  name: material
  features:
    - navigation.instant
    - search.suggest

plugins:
  - search

nav:
  - Home: index.md
  - Installation: installation.md
  - Guides:
    - Defining Models: guide/models.md
    - Building Queries: guide/queries.md
    - Filtering Data: guide/filters.md
    - Executing Queries: guide/execution.md
    - Using Codegen: guide/codegen.md
    - Examples: guide/examples.md
  - API Reference:
    - Models: api/models.md
    - Query Builder: api/query.md
    - Engines: api/engines.md
    - Registry: api/registry.md
  - Development:
    - Contributing: development/contributing.md
    - Testing: development/testing.md
    - Architecture: development/architecture.md
```

### 7.2 Documentation Deployment

**New workflow: `.github/workflows/docs.yml`:**
```yaml
name: Build and deploy docs

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: |
          pip install mkdocs mkdocs-material
      - run: mkdocs build -f docs/mkdocs.yml
      - uses: actions/upload-artifact@v4
        with:
          name: docs
          path: docs/site/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/download-artifact@v4
        with:
          name: docs
          path: docs/site/
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: docs/site
```

**Result:** Docs auto-deploy on every push to main

---

## 8. Component Communication Diagram

```
┌─────────────────────────────────────────────────────┐
│  Users: Python Developers                           │
└────────────┬────────────────────────────────────────┘
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
┌──────────────┐  ┌────────────────┐
│  Cubano Core │  │ Cubano Codegen │
│  (v0.2.0)    │  │   (v0.1.0)     │
└──────┬───────┘  └────────┬────────┘
       │                   │
       │ imports from      │ generates
       │                   │
       ▼                   ▼
┌────────────────────────────────┐
│  Cubano Jaffle Shop            │
│  (Integration Test Workspace)  │
│  - Model definitions           │
│  - Integration tests           │
│  - Example usage               │
└────────┬───────────────────────┘
         │
         ▼
┌────────────────────────────────┐
│  Documentation (GitHub Pages)  │
│  - API reference               │
│  - User guides                 │
│  - Examples                    │
└────────────────────────────────┘
```

**Data flow:**
1. User defines model manually OR generates with cubano-codegen
2. Model code imports from cubano core
3. User runs queries against model, cubano core executes
4. Integration tests (cubano-jaffle-shop) validate the whole flow
5. Documentation guides users on all three components

---

## 9. Migration Path for Users

### 9.1 No Action Required

**Users on v0.1 who only write queries:**
```python
# This code works in v0.1 and v0.2 unchanged
from cubano import SemanticView, Query, register

class Sales(SemanticView, view='sales'):
    revenue = Metric()
    country = Dimension()

register(SnowflakeEngine(...))
results = Sales.query().metrics(Sales.revenue).fetch()
```

### 9.2 Opt-In to Codegen

**Users who write models manually can now use codegen:**
```bash
# Install new tool
pip install cubano-codegen

# Generate models from dbt
cubano-codegen from-dbt --manifest manifest.json --output models.py

# Use generated models (same API, v0.1 compatible)
from models import Orders
orders_total = Orders.query().metrics(Orders.order_total).fetch()
```

### 9.3 Codegen Breaking Changes (Future)

**v0.1.0 of cubano-codegen is not 1.0, so:**
- v0.1.1 might change generated code format
- v0.2.0 might change CLI flags
- Users pin `cubano-codegen==0.1.0` if they care about stable generation

**Core library stays stable:** `cubano>=0.1.0` works with all codegen versions

---

## 10. Risk Assessment

### 10.1 High Risk

**None identified** — all changes are additive or isolated

### 10.2 Medium Risk

| Risk | Mitigation |
|------|-----------|
| Codegen generates broken code | Comprehensive unit tests + integration tests before release |
| Documentation falls out of date | Link to examples in cubano-jaffle-shop (live code) |
| MkDocs deployment fails | Test locally before committing (GitHub Actions validates) |

### 10.3 Low Risk

| Risk | Mitigation |
|------|-----------|
| v0.1 tests break in CI | They won't — no core code changes, just additions |
| Users confused by three packages | Documentation clearly explains (core vs. tool vs. examples) |
| Workspace lockfile grows | uv manages this, minimal overhead |

---

## 11. Validation Checklist

Before Phase 1 release:

- [ ] All v0.1 unit tests pass (265/265)
- [ ] New backwards-compat tests pass (api_compat.py)
- [ ] Integration tests for cubano-jaffle-shop written
- [ ] cubano-codegen CLI works with dbt manifest.json
- [ ] Documentation renders locally with MkDocs
- [ ] GitHub Pages workflow tested (manual trigger)
- [ ] Version numbers updated (0.1.0 → 0.2.0 for core)
- [ ] CHANGELOG updated for v0.2
- [ ] All three packages pass CI (typecheck, lint, format, test)

---

## 12. Implementation Sequence (Detailed)

### Phase 1: Integration Tests (Days 1-2)

```
cubano-jaffle-shop/
├── tests/test_models.py
│   ├── test_orders_structure
│   ├── test_query_building
│   └── test_sql_generation
├── tests/conftest.py (MockEngine fixtures)
└── pyproject.toml (add pytest-dev)

tests/test_api_compat.py (core lib)
├── test_imports
├── test_query_chainability
└── test_row_access
```

### Phase 2: Codegen Tool (Days 3-7)

```
cubano-codegen/
├── src/cubano_codegen/
│   ├── cli.py (Click app, entry point)
│   ├── generators/dbt.py
│   ├── codegen_utils.py
│   └── __init__.py
├── tests/
│   ├── test_dbt_generator.py
│   └── fixtures/manifest.json
└── pyproject.toml

Update [tool.uv.workspace] members in root pyproject.toml
```

### Phase 3: Documentation (Days 8-10)

```
docs/
├── mkdocs.yml
├── index.md
├── installation.md
├── guide/*.md (6 guides)
├── api/*.md (4 API pages)
└── development/*.md (3 dev pages)

.github/workflows/docs.yml (new CI job)
```

### Phase 4: Release (Day 11)

```
Version bumps:
- cubano: 0.1.0 → 0.2.0
- cubano-codegen: (new) 0.1.0
- cubano-jaffle-shop: 0.1.0 → 0.1.1

CHANGELOG update
Tag: v0.2.0
Publish to PyPI (existing release.yml handles this)
GitHub Pages deployment
```

---

## 13. Questions & Decisions Logged

### Decided

- ✅ **Codegen is separate package** — Maintains zero-dependency core
- ✅ **Integration tests in cubano-jaffle-shop** — Reuses existing structure
- ✅ **MkDocs for documentation** — Simple, Markdown-based, suitable for size
- ✅ **Workspace member for codegen** — Single lockfile, easier development
- ✅ **Strict API compatibility** — All public exports frozen

### Deferred

- ⏳ **Async support** — Out of scope for v0.2
- ⏳ **DataFrame export** — Could add later as method on Query
- ⏳ **Type hints for Row fields** — Runtime TypedDict generation (future enhancement)
- ⏳ **Schema validation** — Could add optional Pydantic support (later)

### Future Considerations

- **Codegen for Snowflake UDV** — Add snowflake.py generator (v0.2.0 or later)
- **Codegen for dbt Cloud API** — Download manifest directly (future)
- **Model inheritance** — Support shared field groups (out of scope v0.2)
- **Documentation caching** — Static site generation with versioning (GitHub Pages limitation, future)

---

## Quality Gate Verification

- [x] **Integration points explicit** — Codegen ↔ Core ↔ Tests ↔ Docs clearly mapped
- [x] **New vs modified components identified** — Core (no changes), Codegen (new), Tests (extend), Docs (new)
- [x] **Build order respects dependencies** — Tests (validates), Codegen (new tool), Docs (references both)
- [x] **API compatibility strategy documented** — Public exports frozen, private internals free to change
- [x] **Component boundaries clear** — Zero-dependency core, separate codegen tool, workspace integration
- [x] **Testing strategy covers integration** — Unit tests + integration tests + backwards compat tests

---

## Sources

### Architecture Patterns
- [SQLAlchemy 2.1 Documentation](https://docs.sqlalchemy.org/en/21/)
- [Django ORM Documentation](https://docs.djangoproject.com/en/stable/topics/db/models/)
- [ibis Expression System](https://ibis-project.org/)

### Python Tooling
- [uv Workspace Documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [Python Package Management with uv](https://docs.astral.sh/uv/concepts/projects/dependencies/)

### Documentation Tools
- [Python Documentation: MkDocs vs Sphinx](https://www.pythonsnacks.com/p/python-documentation-generator)
- [encode/httpx: Discussion on Sphinx vs MkDocs](https://github.com/encode/httpx/discussions/1220)
- [Scientific Python Development Guide - Docs](https://learn.scientific-python.org/development/guides/docs/)

### Backwards Compatibility
- [Migration and Compatibility | pydantic/pydantic](https://deepwiki.com/pydantic/pydantic/8-backward-compatibility-and-migration)
- [SQLAlchemy Versioning](https://docs.sqlalchemy.org/en/21/orm/versioning.html)
- [OpenAPI Generator](https://openapi-generator.tech/docs/generators/python/)

### Code Generation Tools
- [Cog: A Code Generation Tool Written in Python](https://www.python.org/about/success/cog/)
- [Swagger Codegen](https://swagger.io/docs/open-source-tools/swagger-codegen/)
- [Top Python Code Generator Tools in 2025](https://www.qodo.ai/blog/top-python-code-generator-tools/)

---

**Research completed:** 2026-02-17
**Ready for Roadmap:** Phase 1 integration tests → Phase 2 codegen → Phase 3 docs → Phase 4 release
