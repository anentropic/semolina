# Phase 10: Documentation - Research

**Researched:** 2026-02-17
**Domain:** MkDocs, Material theme, mkdocstrings, doctest mocking, GitHub Pages
**Confidence:** HIGH

---

## RESEARCH COMPLETE

## Summary

Phase 10 builds a documentation site using MkDocs + Material theme + mkdocstrings for API reference auto-generation. All code examples in docstrings must doctest-validate using `pytest --doctest-modules` with a `conftest.py` that injects mocked engines invisibly. The site deploys to GitHub Pages via GitHub Actions. This research covers: the full MkDocs + Material stack, the doctest mocking pattern, the gen-files approach for automated API reference generation, and the GitHub Pages deployment workflow.

**Primary recommendation:** MkDocs 1.6+ with Material 9.7+ (all Insiders features now free), mkdocstrings[python] with Google-style docstrings, gen-files + literate-nav for automated API reference, `doctest_namespace` autouse fixture in `src/cubano/conftest.py` for invisible mocking.

---

## 1. Standard Stack

### Core Documentation Tools

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| mkdocs | 1.6+ | Static site generator | Core framework |
| mkdocs-material | 9.7+ | Theme | All Insiders features now free as of v9.7.0 (Nov 2025) |
| mkdocstrings[python] | 0.26+ | API reference from docstrings | Python handler uses Griffe for AST extraction |
| mkdocs-gen-files | 0.5+ | Generate docs pages at build time | For automated API reference page generation |
| mkdocs-literate-nav | 0.6+ | Navigation from Markdown files | Works with gen-files for auto navigation |
| mkdocs-section-index | 0.3+ | Bind content to section pages | Optional but clean for navigation |

### Dependencies in pyproject.toml

Docs dependencies belong in a `[dependency-groups]` section (development-only, not published to PyPI):

```toml
[dependency-groups]
dev = [
    # existing dev deps...
]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.7.0",
    "mkdocstrings[python]>=0.26.0",
    "mkdocs-gen-files>=0.5.0",
    "mkdocs-literate-nav>=0.6.0",
    "mkdocs-section-index>=0.3.0",
]
```

Install with: `uv sync --group docs`

**Important note on Material 9.7.0:** As of November 2025, ALL previously Insiders-only features (social cards, optimize plugin, typeset plugin, etc.) are now free. Material for MkDocs is entering maintenance mode as the team transitions to Zensical. All social/optimize plugins now work without sponsorship. Projects plugin and Typeset plugin are deprecated but functional.

---

## 2. MkDocs Configuration (mkdocs.yml)

### Complete Recommended Configuration

```yaml
site_name: Cubano
site_description: A Pythonic ORM for querying data warehouse semantic views
site_url: https://anentropic.github.io/cubano/
repo_url: https://github.com/anentropic/cubano
repo_name: anentropic/cubano
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    # Light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    # Dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.instant        # SPA-like instant loading (requires site_url)
    - navigation.sections       # Top-level sections as sidebar groups
    - navigation.tabs           # Top-level sections as tabs (optional)
    - navigation.top            # Back-to-top button
    - navigation.tracking       # Anchor tracking in URL
    - toc.follow                # TOC sidebar follows scroll
    - content.code.copy         # Copy-to-clipboard on all code blocks
    - content.code.annotate     # Code annotations
    - search.suggest            # Search suggestions
    - search.highlight          # Search highlight in results

plugins:
  - search
  - gen-files:
      scripts:
        - scripts/gen_ref_pages.py
  - literate-nav:
      nav_file: SUMMARY.md
  - section-index
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            docstring_section_style: table
            show_source: true
            show_root_heading: true
            show_root_toc_entry: true
            show_symbol_type_heading: true
            show_symbol_type_toc: true
            members_order: source
            filters:
              - "!^_"        # Exclude private members (single underscore)
            merge_init_into_class: true
            show_signature_annotations: true
            separate_signature: true

markdown_extensions:
  - admonition                  # Note, Warning, Tip boxes
  - attr_list                   # Required for grids and button styling
  - md_in_html                  # Required for card grids
  - pymdownx.details            # Collapsible admonitions
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite       # Inline code syntax highlighting
  - pymdownx.superfences:       # Code blocks in tabs, nested fences
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true     # Required for content tabs
  - pymdownx.snippets           # Include external files in code blocks
  - toc:
      permalink: true           # Anchor links on headings

nav:
  - Home: index.md
  - Getting Started:
      - Installation: guides/installation.md
      - First Query: guides/first-query.md
  - Guides:
      - Defining Models: guides/models.md
      - Building Queries: guides/queries.md
      - Filtering with Q: guides/filtering.md
      - Ordering & Limiting: guides/ordering.md
      - Backends:
          - Overview: guides/backends/overview.md
          - Snowflake: guides/backends/snowflake.md
          - Databricks: guides/backends/databricks.md
      - Codegen CLI: guides/codegen.md
  - API Reference: reference/  # literate-nav populates this from SUMMARY.md
  - Changelog: changelog.md
```

### Key Navigation Notes

- `navigation.instant` requires `site_url` to be set
- `navigation.sections` groups top-level items in sidebar (recommended for Cubano's hierarchy)
- `navigation.tabs` is optional — useful if the site grows large, but may be too much for v1
- The `reference/` entry is populated by gen-files + literate-nav automatically

---

## 3. Automated API Reference with gen-files

The recommended approach uses `mkdocs-gen-files` + `mkdocs-literate-nav` to automatically generate API reference pages at build time. This avoids manually maintaining autodoc instructions.

### Script: scripts/gen_ref_pages.py

```python
"""Generate API reference pages for all Cubano modules."""
from pathlib import Path

import mkdocs_gen_files

src = Path("src")
nav = mkdocs_gen_files.Nav()

for path in sorted(src.rglob("*.py")):
    module_path = path.relative_to(src).with_suffix("")
    doc_path = path.relative_to(src).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    # Skip __init__, __main__, private modules
    if parts[-1] in ("__init__", "__main__"):
        continue
    if any(part.startswith("_") for part in parts):
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"# `{ident}`\n\n::: {ident}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
```

This script:
1. Discovers all `.py` files under `src/`
2. Generates a `.md` page for each module with `:::` autodoc syntax
3. Writes a `SUMMARY.md` that literate-nav uses for the navigation
4. Skips `__init__`, `__main__`, and private modules

### API Reference Page Output Format

For each module (e.g., `cubano/query.py`), the generated `reference/cubano/query.md` looks like:

```markdown
# `cubano.query`

::: cubano.query
```

mkdocstrings then renders all public members from that module's docstrings with full type annotations, signatures, and cross-references.

### Manual Reference Pages (Override)

For modules that need custom organization, create hand-crafted pages that mix prose with autodoc:

```markdown
# Query Builder

Cubano uses an immutable, chainable Query builder.

::: cubano.query.Query
    options:
      show_source: false
      members:
        - metrics
        - dimensions
        - filter
        - order_by
        - limit
        - using
        - fetch
        - to_sql
```

---

## 4. Doctest Mocking Strategy

### The Challenge

Code examples in docstrings must work as doctests (`pytest --doctest-modules`) without hitting real warehouses. The examples must look realistic — real Cubano API syntax, not fake placeholder code.

### The Solution: doctest_namespace + Autouse Fixture

pytest's `doctest_namespace` fixture allows injecting objects into the doctest execution environment. The critical rule: **the `conftest.py` must be in the same directory tree as the source files**.

Because Cubano uses a `src/cubano/` layout, the conftest that injects mock namespace must be at `src/cubano/conftest.py` (or `src/conftest.py`). The existing `tests/conftest.py` is in a sibling tree and will NOT be discovered for doctests in `src/cubano/`.

### conftest.py Location: src/cubano/conftest.py

```python
"""
Doctest fixtures for Cubano source-level doctests.

Injects a pre-configured MockEngine and sample model into the doctest
namespace so examples in docstrings can run without a real warehouse.
"""
import pytest

from cubano import Dimension, Metric, Query, SemanticView, register, unregister
from cubano.engines.mock import MockEngine


class Sales(SemanticView, view="sales_view"):
    """Sample SemanticView for doctest examples."""
    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()


@pytest.fixture(autouse=True)
def doctest_setup(doctest_namespace):
    """
    Inject mock objects into all doctest namespaces.

    Provides:
    - Sales: A SemanticView class with revenue, cost, country, region fields
    - Query: The Query builder class
    - mock_engine: A MockEngine with sample data loaded
    - cubano: The cubano module (for register/unregister examples)
    """
    # Build mock engine with sample data
    engine = MockEngine()
    engine.load("sales_view", [
        {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
        {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
        {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
    ])

    # Register as default engine for .fetch() examples
    register("default", engine)

    # Inject into doctest namespace
    import cubano
    doctest_namespace["Sales"] = Sales
    doctest_namespace["Query"] = Query
    doctest_namespace["mock_engine"] = engine
    doctest_namespace["cubano"] = cubano

    yield

    # Cleanup: unregister engine after each doctest
    unregister("default")
```

### Docstring Pattern for Doctests

With the above setup, docstrings can use `Sales` and `Query` directly without any imports. The examples look like real usage:

```python
def metrics(self, *fields: Any) -> Query:
    """
    Select metrics for aggregation.

    Example:
        >>> query = Query().metrics(Sales.revenue, Sales.cost)
        >>> query._metrics  # doctest: +ELLIPSIS
        (<cubano.fields.Metric object at ...>, <cubano.fields.Metric object at ...>)
    """
```

For `.fetch()` examples (which need a registered engine):

```python
def fetch(self) -> list[Any]:
    """
    Execute query and return results as Row objects.

    Example:
        >>> results = Query().metrics(Sales.revenue).fetch()
        >>> len(results)
        3
    """
```

For `.to_sql()` examples (no engine needed):

```python
def to_sql(self) -> str:
    """
    Generate SQL for this query using MockDialect.

    Example:
        >>> sql = Query().metrics(Sales.revenue).dimensions(Sales.country).to_sql()
        >>> print(sql)
        SELECT AGG("revenue"), "country"
        FROM "sales_view"
        GROUP BY ALL
    """
```

### pytest Configuration for Doctests

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = [
    "--doctest-modules",
    "--doctest-continue-on-failure",
]
doctest_optionflags = ["ELLIPSIS", "NORMALIZE_WHITESPACE"]
testpaths = ["tests", "src"]
```

**Critical notes:**
- `--doctest-modules` was fixed for src layout in pytest 8.0.0 (Cubano already requires >=8.0.0)
- `testpaths = ["tests", "src"]` tells pytest to discover doctests from both locations
- `ELLIPSIS` is essential for matching object repr output (`<cubano.fields.Metric object at 0x...>`)
- `NORMALIZE_WHITESPACE` helps with multi-line SQL output matching

### Doctest Directives

Key directives to use in docstrings:

```python
# Skip a specific example (useful for examples that require real warehouses):
>>> engine = SnowflakeEngine(account="...")  # doctest: +SKIP

# Match variable output with ellipsis:
>>> repr(Sales.revenue)  # doctest: +ELLIPSIS
'<cubano.fields.Metric object at ...>'

# Normalize whitespace in SQL output:
>>> print(query.to_sql())  # doctest: +NORMALIZE_WHITESPACE
SELECT AGG("revenue"), "country"
FROM "sales_view"
GROUP BY ALL
```

### Warning: Registry State

Since the registry is global state, the `doctest_setup` fixture must both register and unregister the engine. The `yield` pattern ensures cleanup even if the doctest fails.

---

## 5. Docs Site Structure

### Directory Layout

```
docs/
├── index.md                    # Landing page with hero, key features, quickstart
├── changelog.md                # Link to or copy of CHANGELOG
├── guides/
│   ├── installation.md         # Install, install extras, verify
│   ├── first-query.md          # 5-minute getting started (model → query → results)
│   ├── models.md               # SemanticView, Metric, Dimension, Fact, fields
│   ├── queries.md              # Query builder: metrics(), dimensions(), limit()
│   ├── filtering.md            # Q-objects: AND/OR/NOT composition
│   ├── ordering.md             # order_by(), asc(), desc(), NullsOrdering
│   ├── backends/
│   │   ├── overview.md         # Unified guide, inline notes when backends differ
│   │   ├── snowflake.md        # SnowflakeEngine connection, AGG() syntax
│   │   └── databricks.md      # DatabricksEngine connection, MEASURE() syntax
│   └── codegen.md              # cubano codegen CLI, --backend, --output
├── reference/                  # Auto-generated by gen-files + literate-nav
│   └── SUMMARY.md              # Generated navigation index
scripts/
└── gen_ref_pages.py            # API reference generation script
mkdocs.yml
```

### Landing Page (index.md) Structure

The landing page uses card grids and the standard Material layout (no special layout override):

```markdown
# Cubano

A Pythonic ORM for querying data warehouse semantic views.

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } **5-minute quickstart**

    ---
    Install and run your first query against Snowflake or Databricks

    [:octicons-arrow-right-24: Getting Started](guides/installation.md)

-   :material-database:{ .lg .middle } **Semantic views**

    ---
    Define typed models over Snowflake semantic views and Databricks metric views

    [:octicons-arrow-right-24: Defining Models](guides/models.md)

-   :material-filter:{ .lg .middle } **Fluent query builder**

    ---
    Chain `.metrics()`, `.dimensions()`, `.filter()`, `.order_by()`, `.limit()`

    [:octicons-arrow-right-24: Building Queries](guides/queries.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---
    Auto-generated from docstrings via mkdocstrings

    [:octicons-arrow-right-24: Reference](reference/)

</div>

## Quick Example

```python
from cubano import SemanticView, Metric, Dimension, Query, register
from cubano.engines import SnowflakeEngine

class Sales(SemanticView, view="sales"):
    revenue = Metric()
    country = Dimension()

register("default", SnowflakeEngine(**connection_params))

results = (Query()
    .metrics(Sales.revenue)
    .dimensions(Sales.country)
    .limit(10)
    .fetch())
```
```

### Guide Page Structure: Getting Started (first-query.md)

Cover all these in the first-query guide:
1. Installation (`pip install cubano` or `pip install cubano[snowflake]`)
2. Define a model (SemanticView subclass)
3. Register an engine (MockEngine for local testing)
4. Build and run a query
5. Access results (`row.revenue` and `row['revenue']`)

This must get users to working code within 5 minutes.

---

## 6. Content Guide Outlines

### DOCS-03: Query Language Guide (queries.md)

Cover each method with real examples:
- `.metrics(*fields)` — selecting aggregatable measures
- `.dimensions(*fields)` — grouping by attributes (Dimension and Fact fields)
- `.filter(condition)` — Q object filter
- `.order_by(*fields)` — bare fields and OrderTerm
- `.limit(n)` — row limit
- `.using(name)` — engine selection
- `.fetch()` — execution and Row results
- `.to_sql()` — SQL inspection

Show the immutable chaining pattern explicitly:
```python
# Each method returns a NEW Query - queries are reusable
base = Query().metrics(Sales.revenue).dimensions(Sales.country)
us_only = base.filter(Q(country="US"))
top_10 = base.limit(10)  # base is unchanged
```

### DOCS-04: Q-Objects and Filter Composition (filtering.md)

Cover:
- Basic equality: `Q(country="US")`
- Lookups: `Q(revenue__gt=1000)` (document the lookup syntax)
- OR composition: `Q(country="US") | Q(country="CA")`
- AND composition: `Q(country="US") & Q(revenue__gt=500)`
- NOT negation: `~Q(country="US")`
- Complex nesting: `(Q(country="US") | Q(country="CA")) & ~Q(revenue__lt=100)`
- Multiple `.filter()` calls (ANDed together)
- Operator precedence WARNING: `&` binds tighter than `|` — always parenthesize

### DOCS-05: Backend Comparison (backends/overview.md)

| Feature | Snowflake | Databricks |
|---------|-----------|------------|
| Engine class | SnowflakeEngine | DatabricksEngine |
| Install extra | `cubano[snowflake]` | `cubano[databricks]` |
| Metric function | AGG() | MEASURE() |
| Identifier quoting | Double quotes `"name"` | Backticks `` `name` `` |
| View format | CREATE SEMANTIC VIEW | Metric Views (YAML) |
| Unity Catalog | N/A | Three-part names `catalog.schema.view` |
| GROUP BY | GROUP BY ALL | GROUP BY ALL |

Unified guides with inline notes:
```markdown
!!! note "Snowflake vs Databricks"
    Snowflake uses `AGG(revenue)` in generated SQL.
    Databricks uses `MEASURE(revenue)`.
    The Query API is identical for both.
```

---

## 7. GitHub Actions Workflow (DOCS-08, DOCS-09)

### Recommended Pattern: Two-Job Workflow (Build + Deploy)

The modern approach separates build and deploy into two jobs, using `actions/upload-pages-artifact` and `actions/deploy-pages` rather than `mkdocs gh-deploy`. This avoids needing `contents: write` permission and is the GitHub-recommended pattern.

```yaml
# .github/workflows/docs.yml
name: Docs

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: docs-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    name: Build docs
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Required for git-revision-date if used

      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Sync docs dependencies
        run: uv sync --locked --group docs

      - name: Build docs
        run: uv run mkdocs build --strict

      - name: Upload pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    name: Deploy to GitHub Pages
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 5
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}

    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### Build Validation (DOCS-10)

`mkdocs build --strict` treats warnings as errors, which catches:
- Broken internal links
- References to undefined mkdocstrings identifiers
- Missing nav pages

For doctest validation, the CI pipeline should run doctests as part of the regular test job (already exists in ci.yml). The docs job runs `mkdocs build --strict` as an additional check.

**Recommendation:** Add doctest run to the existing `test` job in `ci.yml`, not the docs job. Docs job only validates the site builds correctly. Test job validates code examples work.

### Updated ci.yml Test Step

```yaml
- name: Run pytest (Cubano + doctests)
  run: uv run pytest tests/ src/ -m "mock or unit" -n auto -v
```

Note: `src/` is added to discover doctests in source files.

### Alternative: Simple Pattern (Single Job)

For simplicity, the Material theme's recommended `mkdocs gh-deploy` pattern works but requires `contents: write` permission:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v7
      - run: uv sync --locked --group docs
      - run: uv run mkdocs gh-deploy --force
```

**Recommendation:** Use the two-job pattern (first option) — it's the GitHub-recommended modern approach, uses least-privilege permissions, and provides a clear build artifact separate from deployment.

---

## 8. Plugins Worth Using (DOCS-07)

### Built-in Material Plugins (Free as of 9.7.0)

| Plugin | Purpose | Recommended |
|--------|---------|-------------|
| search | Client-side full-text search | YES (essential) |
| social | Auto-generate social cards (Twitter/OG) | Optional (nice to have) |
| optimize | Compress images, optimize site | Optional |

### Third-Party Plugins

| Plugin | Purpose | Recommended |
|--------|---------|-------------|
| mkdocs-gen-files | Generate docs pages at build time | YES (for API reference) |
| mkdocs-literate-nav | Navigation from Markdown | YES (with gen-files) |
| mkdocs-section-index | Bind content to section pages | YES |
| mkdocs-git-revision-date-localized | Show last git-modified date | Optional |
| mkdocs-minify-plugin | Minify HTML/JS/CSS | Optional (production) |

### DocSearch vs. Built-in Search

The CONTEXT.md specifies DocSearch by Algolia. However, important considerations:

1. **Application process:** DocSearch requires applying at docsearch.algolia.com for the free open-source tier. Algolia crawls the site and provides `appId`, `apiKey`, `indexName`.
2. **Material integration:** DocSearch is not a native Material plugin — it requires a custom JavaScript override or a third-party plugin.
3. **Built-in search is excellent:** Material's native lunr-based search is fast, client-side, and works offline.

**Recommendation:** Start with Material's built-in search. Apply for DocSearch when the site is live. The integration can be added later without changing the docs structure. If DocSearch is required from day one, use the `extra_javascript` override approach in mkdocs.yml.

---

## 9. Docstring Quality Requirements

### Current Docstring Style

Cubano already uses Google-style docstrings with `Args`, `Returns`, `Raises`, `Example` sections. This aligns with mkdocstrings' default `docstring_style: google`.

### Docstring Structure for API Reference

Each public class and method needs:
- Summary on second line (D213, per project style)
- `Args:` section with types (mkdocstrings renders these as a table)
- `Returns:` section
- `Raises:` section (where applicable)
- `Example:` section with at least one doctest-valid example

### Example Docstring Template

```python
def metrics(self, *fields: Any) -> Query:
    """
    Select metrics for aggregation.

    Returns a new Query with the specified metrics added. Metrics represent
    quantitative measures that the semantic view aggregates (e.g., SUM, AVG).

    Args:
        *fields: One or more Metric field references (e.g., Sales.revenue)

    Returns:
        New Query instance with metrics added

    Raises:
        TypeError: If any field is not a Metric
        ValueError: If no fields are provided

    Example:
        >>> query = Query().metrics(Sales.revenue, Sales.cost)
        >>> len(query._metrics)
        2
    """
```

### Existing Docstrings

A review of the current codebase shows most public APIs have docstrings with `Args`, `Returns`, `Raises`, and `Example` sections. Phase 10 will need to:
1. Add `Example` sections with doctest-valid code where missing
2. Ensure examples work with the mocked `doctest_namespace` setup
3. Add module-level docstrings that mkdocstrings renders as module descriptions

---

## 10. Key Implementation Risks & Mitigations

### Risk 1: conftest.py Discovery for Doctests

**Risk:** `doctest_namespace` fixture in `tests/conftest.py` is NOT visible to doctests in `src/cubano/`.

**Mitigation:** Create a separate `src/cubano/conftest.py` specifically for doctest fixtures. The `tests/conftest.py` continues to serve unit/integration tests. These two conftest files coexist without conflict.

### Risk 2: Registry Global State in Doctests

**Risk:** The engine registry is global. If one doctest registers an engine and fails before cleanup, subsequent doctests fail with "engine already registered".

**Mitigation:** The `doctest_setup` fixture uses `yield` with cleanup in the finally block equivalent. Also, consider adding `autouse=True` to a `clean_registry` fixture (similar to what `tests/conftest.py` already has) in the src-level conftest.

### Risk 3: Doctest Output Format Sensitivity

**Risk:** Object repr like `<cubano.fields.Metric object at 0x7f...>` changes on every run.

**Mitigation:** Use `# doctest: +ELLIPSIS` directive and match with `...`. Configure `ELLIPSIS` in `doctest_optionflags` so it's available without per-example directives.

### Risk 4: pytest --doctest-modules + src Layout

**Risk:** Known historical issue with `--doctest-modules` in src layout.

**Status:** FIXED in pytest 8.0.0. Cubano already requires `pytest>=8.0.0`. No action needed.

**Verification:** Test with `uv run pytest src/ --doctest-modules -v` before shipping.

### Risk 5: Doctest Examples in Complex API Methods

**Risk:** Some examples (e.g., showing `.fetch()` results) require careful fixture setup to produce deterministic output.

**Mitigation:** The `MockEngine` with `engine.load()` provides deterministic data. The `doctest_setup` fixture loads consistent sample data. Use `# doctest: +ELLIPSIS` or `# doctest: +SKIP` for examples where output is intentionally variable.

### Risk 6: Material 9.7.0 Deprecations

**Risk:** Projects plugin and Typeset plugin are deprecated in 9.7.0 as team moves to Zensical.

**Mitigation:** Do not use Projects or Typeset plugins. Use gen-files + literate-nav for navigation instead of Projects. Stick to core functionality that will be maintained.

---

## 11. Phase Breakdown Recommendation

Based on requirements and research, the natural task breakdown is:

**10-01: Foundation** (DOCS-06)
- Set up MkDocs + Material locally
- docs/ directory structure
- mkdocs.yml configuration
- Verify `mkdocs serve` works

**10-02: API Reference** (DOCS-02, DOCS-07 partial)
- Install gen-files, literate-nav, section-index
- Write gen_ref_pages.py script
- Verify all modules appear in reference/
- Configure mkdocstrings with Google style

**10-03: Doctest Infrastructure** (DOCS-10)
- Create `src/cubano/conftest.py` with `doctest_namespace` fixture
- Configure `pyproject.toml` for `--doctest-modules`
- Add/fix docstring examples across all public APIs
- Verify all doctests pass

**10-04: Guides** (DOCS-01, DOCS-03, DOCS-04, DOCS-05)
- Getting started guide (install + first query)
- Query language guide
- Q-objects and filtering guide
- Backend comparison guide

**10-05: CI/CD** (DOCS-08, DOCS-09)
- GitHub Actions workflow for docs build
- GitHub Pages deployment
- Validate `mkdocs build --strict` in CI

---

## Sources

### Primary (HIGH confidence)

- [Material for MkDocs: Getting Started](https://squidfunk.github.io/mkdocs-material/getting-started/)
- [mkdocstrings-python Usage](https://mkdocstrings.github.io/python/usage/)
- [mkdocstrings Recipes (gen-files + literate-nav)](https://mkdocstrings.github.io/recipes/)
- [pytest doctest documentation](https://docs.pytest.org/en/stable/how-to/doctest.html)
- [Material: Setting up navigation](https://squidfunk.github.io/mkdocs-material/setup/setting-up-navigation/)
- [Material: Grids reference](https://squidfunk.github.io/mkdocs-material/reference/grids/)
- [Material: Code blocks reference](https://squidfunk.github.io/mkdocs-material/reference/code-blocks/)
- [Material: Publishing your site](https://squidfunk.github.io/mkdocs-material/publishing-your-site/)
- [Material Insiders Now Free for Everyone (Nov 2025)](https://squidfunk.github.io/mkdocs-material/blog/2025/11/11/insiders-now-free-for-everyone/)

### Secondary (MEDIUM confidence)

- [mkdocstrings configuration: docstrings](https://mkdocstrings.github.io/python/usage/configuration/docstrings/)
- [mkdocstrings configuration: members](https://mkdocstrings.github.io/python/usage/configuration/members/)
- [pytest src layout + doctest-modules fix (pytest#11475)](https://github.com/pytest-dev/pytest/issues/11475)
- [DocSearch by Algolia for open source](https://docsearch.algolia.com/)
- [GitHub Actions: upload-pages-artifact](https://github.com/actions/upload-pages-artifact)
- [GitHub Actions: deploy-pages](https://github.com/actions/deploy-pages)
- [mkdocs-git-revision-date-localized](https://github.com/timvink/mkdocs-git-revision-date-localized-plugin)

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| MkDocs + Material stack | HIGH | Mature, stable, well-documented |
| mkdocstrings configuration | HIGH | Official docs clear, Google style matches existing code |
| doctest_namespace pattern | HIGH | Official pytest docs confirm approach; src layout fixed in pytest 8.0.0 |
| gen-files + literate-nav | HIGH | Official mkdocstrings recipe, widely used pattern |
| GitHub Actions workflow | HIGH | Official GitHub docs + Material docs |
| DocSearch integration | MEDIUM | Application process required; start with built-in search |
| Material 9.7.0 free tier | HIGH | Official announcement, verified |

**Research date:** 2026-02-17
**Valid until:** ~2026-05-17 (90 days; MkDocs ecosystem stable)
