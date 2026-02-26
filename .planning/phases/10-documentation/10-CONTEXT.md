# Phase 10: Documentation - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a comprehensive documentation site where users learn Cubano concepts through guides and reference the API through auto-generated reference. All code examples must be executable via doctest with invisible mocking (no real warehouse hits). Site uses MkDocs + Material theme + DocSearch for discoverability.

</domain>

<decisions>
## Implementation Decisions

### Documentation Structure & Navigation
- **Navigation style:** Left sidebar (Material default) for hierarchical browsing + card grids throughout docs for visual organization
- **Search:** DocSearch by Algolia for powerful search-first navigation (free tier for open source)
- **Landing page:** Not cards-only; uses standard Material layout with sidebar. Cards appear within guides to organize related topics visually.

### Example Execution & Validation
- **Examples must doctest:** All code examples in docstrings validate via `pytest --doctest-modules`
- **Invisible mocking approach:** Examples use real Cubano API syntax and look like real warehouse queries, but backend is mocked via pytest conftest `doctest_namespace` fixture
- **Mock data strategy:** MockWarehouse or MockSnowflake backend injected at doctest time (fast, no real warehouse)
- **Build enforcement:** Docs build fails if any example breaks — prevents stale examples

### Content Depth & Audience
- **Primary audience:** Python developers (assume SQL and database warehouse knowledge)
- **Content organization:** Hybrid — hand-written conceptual guides (Getting Started, Building Queries, Filtering, Using Codegen) + auto-generated API reference via mkdocstrings
- **API reference sourcing:** Single source of truth = docstrings in Python code. mkdocstrings auto-generates formatted reference from docstrings.
- **Backend differences:** Unified guides with inline notes when Snowflake and Databricks differ (e.g., "Snowflake uses X, Databricks uses Y")

### Interactive Elements & Usability
- **Copy-to-clipboard buttons:** On all code examples for quick copying
- **Dark mode support:** Light/dark mode toggle (Material default, respects system preference)
- **Syntax highlighting:** Python and SQL code blocks (standard with Material theme)
- **Search tuning:** Configure DocSearch to index API names, parameters, not just page titles for discoverability
- **Theme customization notes:** Include developer documentation for how to customize Material theme (colors, fonts, layout) for future maintainers

### Claude's Discretion
- Specific page structure and hierarchy within guides
- Card grid styling, spacing, and visual design choices
- Table of contents auto-generation depth and grouping
- Homepage hero section copy, imagery, and branding
- Custom CSS extensions or plugins beyond Material defaults
- Navigation sidebar section grouping (e.g., "Guides", "API Reference", "Examples")

</decisions>

<specifics>
## Specific Ideas

- Examples should feel executable and real — users should see `Sales.from_warehouse(...).metrics().fetch()` not abstract pseudo-code
- Getting Started guide should result in users running actual Cubano queries within 5 minutes of reading
- "Using Codegen" guide should cross-reference Phase 9 codegen documentation and show real generated SQL examples

</specifics>

<deferred>
## Deferred Ideas

- Interactive query builder / live playground — future enhancement
- Video walkthroughs — future milestone
- Versioned documentation (v0.1, v0.2 separate sites) — evaluate after v0.2 stable
- Jupyter notebook tutorials — future enhancement
- Language localization — out of scope

</deferred>

---

*Phase: 10-documentation*
*Context gathered: 2026-02-17*
