# Doc Writer Context

**Generated:** 2026-04-08
**Source:** /doc-writer:setup researcher
**Editable:** Yes -- manual edits are preserved until the next --refresh-context run. To make permanent changes, edit config.yaml and re-run setup.

## Project Summary

Semolina is a typed, Pythonic ORM for querying data warehouse semantic views (Snowflake semantic views and Databricks metric views). It provides declarative model definitions via `SemanticView` subclasses, a fluent immutable query builder with IDE autocomplete, TOML-based connection configuration, and a codegen CLI that introspects existing warehouse views to generate Python model files. Python 3.11+, built with uv, uses adbc-poolhouse for connection pooling.

## User Persona: Python web developers building analytics backends

### Profile
- **Skill level:** Advanced
- **What they know:** Fluent in Python including type hints, generics, and descriptors. Comfortable with web frameworks (Django, FastAPI) and their request/response lifecycle. Understands SQL deeply -- joins, aggregations, window functions, CTEs. Has used ORMs (Django ORM, SQLAlchemy) and understands metaclasses, querysets, and lazy evaluation. Knows virtual environments, pip/uv, and extras-based optional dependencies. Familiar with async/await, event loops, and concurrent I/O patterns.
- **What to always explain:** Always explain what semantic views are and how they differ from regular database views or tables. Spell out the semantic layer concept -- metrics, dimensions, and facts as first-class abstractions rather than raw columns. Explain AGG vs MEASURE syntax differences between Snowflake and Databricks. Clarify how Semolina's Metric/Dimension/Fact fields map to the underlying warehouse semantic layer, and why this mapping matters for correctness.
- **Their world:** Builds Python web application backends that serve analytics dashboards and BI reporting interfaces. Their stack typically includes FastAPI or Django, a task queue, and a data warehouse they query for aggregated metrics. They need to expose filtered, ordered metric data to frontend teams via REST or GraphQL endpoints. They care about type safety, IDE support, and maintainability of query code.
- **How they found this library:** Searched PyPI or GitHub for "python snowflake semantic view" or "query databricks metric view from python." May have been building raw SQL strings to query semantic views and wanted a typed, ORM-like abstraction. Could also have been recommended by a data engineering colleague who owns the warehouse semantic layer.

### Common Tasks
- **Define SemanticView models:** Subclass `SemanticView` with `Metric`, `Dimension`, and `Fact` field descriptors mapped to a named warehouse view.
- **Build queries with the fluent API:** Chain `.metrics()`, `.dimensions()`, `.where()`, `.order_by()`, and `.limit()` on immutable `_Query` objects, then `.execute()` to get a `SemolinaCursor`.
- **Filter and order results:** Use Python comparison operators on fields (`Sales.revenue > 1000`, `Sales.country == 'US'`) to build predicate trees; use `OrderTerm` for nulls ordering.
- **Connect to Snowflake or Databricks:** Register a connection pool with `register("default", pool, dialect="snowflake")` or use `pool_from_config()` to load from `.semolina.toml`.
- **Configure connections via TOML:** Write `.semolina.toml` with `[connections.default]` sections specifying warehouse type and credentials.
- **Generate models from existing warehouse views:** Run the `semolina` CLI codegen command to introspect warehouse views and produce Python model files.

### Writing Guidance for This Persona
- When explaining the query API, assume they understand method chaining, immutable builders, and descriptor protocols -- but spell out how Semolina's field operators translate to semantic layer query semantics (not just SQL).
- Use professional, precise terminology. They know what a metaclass is; do not over-explain Python mechanics.
- Examples should show realistic analytics scenarios: revenue by region, order counts filtered by date range, top-N customers by spend.

## User Persona: Data engineers exposing semantic layers via APIs

### Profile
- **Skill level:** Intermediate
- **What they know:** Proficient in Python and SQL. Deep familiarity with data warehouses (Snowflake, Databricks) including semantic layer concepts -- they likely built and maintain the metrics, dimensions, and semantic views in the warehouse. Comfortable with ETL/ELT pipelines, dbt, and TOML/YAML configuration. Understands data modeling and warehouse administration.
- **What to always explain:** Always explain web framework patterns -- how to structure endpoints, handle request parameters, and return JSON responses. Explain REST API design principles (resource naming, status codes, pagination). Clarify how to structure query endpoints that accept filter parameters from frontend consumers. Explain Python packaging concepts like extras and optional dependencies (`pip install semolina[snowflake]`). Spell out connection pooling -- what it is, why it matters for production, and how adbc-poolhouse manages it. Explain ORM-style patterns: metaclasses that collect field descriptors, fluent builders that return new instances, and descriptor protocol for field access.
- **Their world:** Works on a data platform team responsible for the warehouse semantic layer. They define metrics and dimensions in Snowflake/Databricks and need to make this data available to frontend and product teams without those teams writing raw SQL. They want a clean abstraction layer that respects the semantic definitions they have already built in the warehouse.
- **How they found this library:** Already owns the semantic layer definitions in the warehouse. Searching for tooling to expose those definitions via Python APIs so the frontend team can query metrics without learning SQL or warehouse-specific syntax. May have tried building a custom REST wrapper around raw SQL and found it unmaintainable.

### Common Tasks
- **Configure warehouse connections via TOML:** Write `.semolina.toml` with connection details for their warehouse environment(s).
- **Generate models from existing semantic views using codegen CLI:** Run `semolina codegen` to introspect their warehouse and produce typed Python models matching their existing semantic view definitions.
- **Build query endpoints for the frontend team:** Create API endpoints that accept filter parameters and use Semolina's fluent query API to return results.
- **Set up connection pools for production use:** Configure adbc-poolhouse pools with appropriate sizing and register them with Semolina for concurrent request handling.

### Writing Guidance for This Persona
- When explaining connection setup and TOML config, assume deep warehouse knowledge but spell out the Python side -- how `pool_from_config()` works, what `register()` does, and how the pool lifecycle maps to application startup.
- When showing API endpoint examples, provide complete endpoint code (not just the Semolina query part) since they may be unfamiliar with web framework conventions.
- Examples should show data platform scenarios: exposing a revenue dashboard API, serving metric queries to a React frontend, setting up codegen in a CI pipeline.

## Use Cases

### Build analytics app backends from semantic views

**Problem:** Teams building Python web backends for analytics dashboards have no typed, Pythonic way to query warehouse semantic views. They resort to string-interpolated SQL, losing type safety, IDE autocomplete, and protection against semantic layer misuse (e.g., querying a metric without proper aggregation context). The semantic layer's guardrails exist in the warehouse but are invisible to application code.
**What's possible:** Semolina provides `SemanticView` model classes with `Metric`, `Dimension`, and `Fact` descriptors that map directly to warehouse semantic view definitions. The fluent query builder enforces correct metric/dimension separation at the Python level, generates backend-specific SQL (Snowflake or Databricks dialect), and returns results via `SemolinaCursor` with `Row` objects supporting both attribute and dict access. Connection management uses TOML config and adbc-poolhouse pools.
**Outcome:** Application code queries semantic views with full type safety and IDE autocomplete. Queries are immutable and composable. Results arrive as Arrow-native data through ADBC connection pools. The codegen CLI keeps Python models in sync with warehouse definitions, preventing drift between the semantic layer and application code.
**Relevant persona(s):** Both -- web developers consume the query API; data engineers set up connections and generate models.
**Source:** user-provided

## Tone: warm-businesslike

### Writing Rules
- Brief (1-2 sentence) introduction explaining what the page covers and why the reader needs it.
- Multiple examples per concept: basic usage first, then common variations (different field types, filter combinations, connection patterns).
- Include "Common Mistakes" or "Troubleshooting" sections where relevant -- especially around semantic layer concepts that may be unfamiliar.
- Transition sentences between major sections for reading flow.
- Use admonitions for tips, warnings, and important notes. Prefer specific types (`.. tip::`, `.. warning::`) over generic `.. note::`.
- Warm but professional -- no jokes, no first person, no casual asides. Second person ("you") throughout.
- Do not stack multiple admonitions back-to-back; consolidate into one with a list if needed.

## Framework Preferences: sphinx-shibuya

### Navigation Strategy
- **Strategy:** Sections as top tabs
- Each Diataxis section (Tutorials, How-To Guides, Explanation, Reference) is a dropdown tab in the top navbar via `nav_links` in `conf.py`.
- `nav_links` are static URL lists in `html_theme_options` -- they do NOT derive from the toctree and have no build-time validation. When pages are renamed or moved, `nav_links` must be updated manually.
- Each section has its own `index.rst` with a `:hidden:` toctree listing child pages. The root `index.rst` has a hidden toctree listing all section index files.
- When a reader clicks a tab, the sidebar shows only that section's toctree (scoped sidebar).
- nav_links URLs are plain strings (e.g., `"tutorials/index"`), NOT RST cross-references. Do NOT use `:ref:` or `:doc:` syntax in nav_links.
- Section index pages list children with 1-sentence abstracts written inline (Sphinx does not auto-render child descriptions).
- Front page (`index.rst`) is linked as "Overview" at the same level as the section tabs. Use "Overview" not "Home".
- The project's `conf.py` already has `nav_links` configured with Tutorials (with children), How-To Guides, Reference, and Explanation tabs.

### Features to Use
- **sphinx-autoapi:** Generates the Reference tab automatically from source docstrings. The Author agent MUST NOT write manual reference pages. Google-style docstrings (via Napoleon) are the convention. Currently configured with `autoapi_root = "reference"`, outputting under `reference/semolina/`. Use `:py:class:`, `:py:func:`, `:py:meth:` roles to link to auto-generated reference pages.
- **sphinx-design (grids + cards):** Use `.. grid::` and `.. grid-item-card::` for section index pages and landing pages. Use `:link:` on cards for clickable navigation. Responsive values `1 2 3 3` for mobile-to-desktop adaptation.
- **sphinx-design (tab sets):** Use `.. tab-set::` and `.. tab-item::` for Snowflake/Databricks dialect examples (already the project convention). Use `:sync-group:` and `:sync:` to synchronize tab selections across the page.
- **sphinx-design (dropdowns):** Use `.. dropdown::` for optional or advanced content. Apply `:color:` and `:icon:` for visual distinction.
- **sphinx-design (badges + buttons):** Use `:bdg-success:`, `:bdg-warning:`, `:bdg-info:` for version and stability markers. Use `.. button-ref::` sparingly on landing pages for prominent CTAs.
- **sphinx-copybutton:** Enabled -- code blocks automatically get a copy button. No extra markup needed.
- **sphinx.ext.napoleon:** Enabled -- parses Google-style docstrings into structured parameter/return lists.
- **sphinx.ext.intersphinx:** Enabled with Python stdlib mapping. Use `:py:class:\`pathlib.Path\`` etc. for external links.
- **sphinx.ext.viewcode:** Enabled -- adds "[source]" links to auto-generated API docs.

### Features NOT to Use
- **sphinxcontrib-mermaid:** Not in `conf.py` extensions or `docs` dependency group. Do not use `.. mermaid::` directives.
- **Fenced code blocks:** RST files must use `.. code-block::` directives, never triple-backtick fences.
- **`:doc:` cross-references:** Strongly discouraged. Use `:ref:\`label\`` with labels above headings. Labels survive page moves; file-path references break.
- **Generic `.. note::` overuse:** Prefer specific admonition types (`.. tip::`, `.. warning::`, `.. danger::`).
