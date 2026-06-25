# Phase 37: Documentation - Research

**Researched:** 2026-04-27
**Domain:** Sphinx RST documentation (Diataxis framework), Semolina API surface
**Confidence:** HIGH

## Summary

Phase 37 writes two new how-to guides and updates several existing pages to reflect v0.4.0 changes (DuckDB backend, Arrow output, three-backend world). The documentation stack is mature -- Sphinx with shibuya theme, sphinx-design tab-sets, sphinx-autoapi for reference -- and requires no new tooling.

Two new pages are needed: (1) an Arrow output how-to guide covering `fetch_arrow_table()` and zero-copy conversion to Pandas and Polars, and (2) updates to the existing backends overview to fully cover DuckDB as a first-class backend alongside Snowflake and Databricks. Several existing pages already reference DuckDB (installation tutorial, warehouse-testing, backends overview) and need their content verified for accuracy against the v0.4.0 implementation.

**Primary recommendation:** Write two new how-to pages, update existing backend/codegen/config-ref pages to cover DuckDB as a third backend, add DuckDB tab to all tab-sets, and wire new pages into toctree and shibuya nav_links. Apply the semolina-docs-author skill (Diataxis + humanizer) to all new pages.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOCS-01 | How-to guide for `.to_arrow()` and zero-copy conversion to Pandas/Polars | `fetch_arrow_table()` exists on SemolinaCursor (cursor.py L130-156), delegates to ADBC cursor. pyarrow 23.0.1 installed. `Table.to_pandas()` for Pandas, `pl.from_arrow(table)` for Polars. |
| DOCS-02 | Three-backend connection guide covering Snowflake, Databricks, and DuckDB | Existing backends/overview.rst already has Snowflake+Databricks. DuckDB section exists but is minimal (only "Test locally" section). Need full DuckDB backend page + expanded overview + TOML config reference + codegen docs. DuckDBConfig fields documented via adbc-poolhouse source. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Mandatory skill:** Load `@.claude/skills/semolina-docs-author/SKILL.md` when writing or modifying docs
- **GSD planner instruction:** Add the skill to `<execution_context>` block in PLAN.md
- **New pages:** Full Diataxis + humanizer workflow (mandatory)
- **How-to guides:** Use `.. tab-set::` with `:sync-group: warehouse` for warehouse-specific code
- **Reference:** Auto-generated via sphinx-autoapi. Do not hand-write API docs.
- **Writing voice:** Warm but efficient (FastAPI/Stripe docs), second person
- **Quality gates:** `just docs-build` (runs `uv run sphinx-build -W docs/src docs/_build`) must pass with no warnings
- **Line length:** 100 chars
- **Pre-commit:** `prek run --all-files`

## Standard Stack

### Core (no new dependencies)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Sphinx | (project dep) | Documentation site generator | Already in use [VERIFIED: project pyproject.toml] |
| shibuya | (project dep) | Sphinx theme | Already configured in conf.py [VERIFIED: docs/src/conf.py] |
| sphinx-design | (project dep) | Tab-set, grid directives | Already used for warehouse tab-sets [VERIFIED: existing RST files] |
| sphinx-autoapi | (project dep) | Auto API reference | Already configured [VERIFIED: conf.py] |
| sphinx-copybutton | (project dep) | Copy button on code blocks | Already configured [VERIFIED: conf.py] |

**No new dependencies required.** All tooling is already installed and configured.

### Alternatives Considered

None. Documentation stack is established and working.

## Architecture Patterns

### Existing Documentation Structure

```
docs/src/
  index.rst                    # Landing page with grid cards + global toctree
  tutorials/
    index.rst                  # Toctree: installation, first-query
    installation.rst           # Already has DuckDB tab in "Install a backend extra"
    first-query.rst            # Has DuckDB tip box for local testing
  how-to/
    index.rst                  # Toctree: 12 guides currently listed
    backends/
      overview.rst             # Has DuckDB "Test locally" section (needs expansion)
      snowflake.rst            # Complete
      databricks.rst           # Complete
    connection-pools.rst       # Two-backend tab-set (needs DuckDB tab)
    codegen.rst                # Two-backend tab-set (needs DuckDB section)
    codegen-credentials.rst    # Snowflake+Databricks only (needs DuckDB section)
    warehouse-testing.rst      # Already DuckDB-focused, good shape
    [other guides...]
  reference/
    config.rst                 # Missing DuckDB type in "Common fields" and tab-set
    cli.rst                    # May need --database flag documented
  explanation/
    semantic-views.rst         # Mentions Snowflake+Databricks (needs DuckDB mention)
  conf.py                      # Shibuya nav_links - needs new pages added
```

### Pattern 1: How-to Guide with Tab-Sets (Warehouse-Specific)

**What:** Sphinx-design tab-set with `:sync-group: warehouse` for code that varies by backend
**When to use:** Whenever showing connection setup, generated SQL, or TOML config
**Example:**

```rst
.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         # Snowflake-specific code

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         # Databricks-specific code

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         # DuckDB-specific code
```

[VERIFIED: This pattern is used in backends/overview.rst, connection-pools.rst, first-query.rst]

### Pattern 2: How-to Guide (Single Topic, No Tab-Set)

**What:** How-to page for a feature that works identically across all backends
**When to use:** Arrow output guide -- `fetch_arrow_table()` works the same regardless of backend
**Structure:** Goal statement, prerequisite, code examples, "See also" links

[VERIFIED: serialization.rst follows this pattern]

### Pattern 3: Navigation Registration

**What:** Every new page must be added to three places
**Where:**
1. Parent `index.rst` toctree directive (e.g., `how-to/index.rst`)
2. `conf.py` `html_theme_options.nav_links` children list
3. Cross-reference links in related pages' "See also" sections

[VERIFIED: All existing pages follow this pattern]

### Anti-Patterns to Avoid

- **Mixing Diataxis types:** Don't put tutorial content (step-by-step learning) in a how-to guide (goal-oriented doing). Arrow guide is a how-to, not a tutorial.
- **Hand-writing API reference:** sphinx-autoapi generates `SemolinaCursor.fetch_arrow_table()` docs from docstrings. Link to it, don't duplicate.
- **Markdown in RST:** Never use triple-backtick fenced blocks in RST files. Use `.. code-block::` directives.
- **Forgetting tab sync-group:** Tab-sets without `:sync-group: warehouse` won't sync across the page.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API docs for fetch_arrow_table | Write method docs by hand | sphinx-autoapi + intersphinx | Docstring already on SemolinaCursor.fetch_arrow_table() with example |
| Warehouse SQL examples | Guess at syntax | Copy from verified test output and existing pages | DuckDB semantic_view() SQL syntax is non-trivial |
| DuckDB TOML config fields | Invent field names | Read from DuckDBConfig source + existing Snowflake/Databricks pages | Config field names must match adbc-poolhouse exactly |

## Existing Content Audit

### Pages That Already Mention DuckDB [VERIFIED: codebase grep]

| Page | Current DuckDB Content | Needs Update? |
|------|----------------------|---------------|
| `tutorials/installation.rst` | DuckDB tab in "Install a backend extra" | Minor: version number (shows 0.3.0 in verify step) |
| `tutorials/first-query.rst` | DuckDB tip box with `DuckDBConfig` example | No changes needed (accurate) |
| `how-to/backends/overview.rst` | "Test locally without a warehouse" section | Major: needs DuckDB as a first-class backend, not just testing |
| `how-to/warehouse-testing.rst` | Entire page is DuckDB-focused | No changes needed (accurate) |
| `how-to/connection-pools.rst` | No DuckDB tab in tab-sets | Needs DuckDB tab added |
| `how-to/codegen.rst` | No DuckDB backend listed | Needs DuckDB section + tab |
| `how-to/codegen-credentials.rst` | No DuckDB section | Needs DuckDB credentials section (--database + DUCKDB_DATABASE) |
| `reference/config.rst` | Lists type as "snowflake" or "databricks" only | Needs DuckDB type + fields section |
| `explanation/semantic-views.rst` | No DuckDB mention | Needs DuckDB semantic_view() explanation |

### Pages That Need NO Changes

| Page | Reason |
|------|--------|
| `how-to/models.rst` | Models are backend-agnostic |
| `how-to/queries.rst` | Query API is backend-agnostic |
| `how-to/filtering.rst` | Filter API is backend-agnostic |
| `how-to/ordering.rst` | Ordering API is backend-agnostic |
| `how-to/serialization.rst` | Row serialization is backend-agnostic |
| `how-to/web-api.rst` | Web API patterns are backend-agnostic |

### New Pages Required

1. **`how-to/arrow-output.rst`** -- Arrow output how-to (DOCS-01)
2. **`how-to/backends/duckdb.rst`** -- DuckDB backend how-to (part of DOCS-02)

## API Surface for Documentation

### fetch_arrow_table() [VERIFIED: src/semolina/cursor.py L130-156]

```python
def fetch_arrow_table(self) -> Any:
    """
    Fetch all remaining rows as a PyArrow Table (ADBC passthrough).
    Delegates to the underlying ADBC cursor's fetch_arrow_table()
    method for zero-copy Arrow data transfer.
    """
    return self._cursor.fetch_arrow_table()
```

- Return type is `Any` (pyarrow has no type stubs) but actual return is `pyarrow.Table`
- Works with all ADBC-backed pools (Snowflake, Databricks, DuckDB)
- Raises `AttributeError` if cursor doesn't support it
- pyarrow version: 23.0.1 [VERIFIED: `uv run python -c "import pyarrow; print(pyarrow.__version__)"`]

### Zero-Copy Conversions [ASSUMED]

```python
# Arrow -> Pandas (requires pandas installed)
table = cursor.fetch_arrow_table()
df = table.to_pandas()  # zero-copy where possible

# Arrow -> Polars (requires polars installed)
import polars as pl
df = pl.from_arrow(table)  # zero-copy, no pandas dependency
```

- `table.to_pandas()` is a pyarrow.Table method. Zero-copy where column types allow it, copies for non-compatible types. [ASSUMED -- standard pyarrow behavior]
- `pl.from_arrow()` accepts a pyarrow.Table. Zero-copy conversion. [ASSUMED -- standard polars behavior]
- Neither pandas nor polars is a Semolina dependency; user must install separately.

### DuckDB TOML Config Fields [VERIFIED: adbc-poolhouse DuckDBConfig source]

```toml
# .semolina.toml
[connections.default]
type = "duckdb"
database = "/path/to/warehouse.db"  # or ":memory:"
# read_only = false  # optional
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | str | Yes | -- | Must be `"duckdb"` |
| `database` | str | No | `":memory:"` | File path or `":memory:"` |
| `read_only` | bool | No | `false` | Open database in read-only mode |

Note: `pool_size` defaults to 1 for DuckDB (in-memory DBs are isolated per connection). pool_size > 1 with `:memory:` raises ValidationError.

### DuckDB Generated SQL [VERIFIED: DuckDBSQLBuilder in engines/sql.py from Phase 33 commits]

Grouped query:
```sql
SELECT *
FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])
```

Row-level (facts) query:
```sql
SELECT *
FROM semantic_view('sales', facts := ['unit_price', 'quantity'])
```

Key difference from Snowflake/Databricks: DuckDB uses `semantic_view()` table function, not `SELECT AGG()/MEASURE() FROM view GROUP BY ALL`.

### DuckDB Codegen CLI [VERIFIED: src/semolina/cli/codegen.py]

```bash
semolina codegen view_name --backend duckdb --database /path/to/db
# Or with env var:
export DUCKDB_DATABASE=/path/to/db
semolina codegen view_name --backend duckdb
```

## Critical Finding: Branch Worktree Reversion

**IMPORTANT:** The current branch HEAD (`73b9397`) has several core source files reverted to pre-Phase 33/35 state due to worktree executor issues. The following files at HEAD are missing v0.4.0 changes:

| File | What's Missing | Impact on Docs |
|------|---------------|----------------|
| `src/semolina/dialect.py` | `Dialect.DUCKDB` reverted to `Dialect.MOCK` | `Dialect.DUCKDB` enum value exists in git history but not at HEAD |
| `src/semolina/config.py` | DuckDBConfig import + `_load_semantic_views` + duckdb in _CONFIG_MAP removed | `pool_from_config()` does not support `type = "duckdb"` at HEAD |
| `src/semolina/engines/sql.py` | DuckDBDialect + DuckDBSQLBuilder + `create_builder()` method removed | DuckDB SQL generation missing at HEAD |
| `src/semolina/query.py` | `dialect.create_builder()` reverted to `SQLBuilder(dialect)` | query execution uses old pattern |
| `src/semolina/__init__.py` | MockPool re-added to exports | Should have been removed in Phase 35 |
| `src/semolina/pool.py` | MockPool/MockCursor/MockConnection re-added | Should have been deleted in Phase 35 |

**Impact on Phase 37:** Documentation must describe the intended v0.4.0 behavior (with DuckDB support in config, dialect, SQL builder). If these files are not restored before docs are written, `just docs-build` may fail because autoapi will generate docs from the current (reverted) source. The planner should either:
1. Include a prerequisite task to restore reverted files before writing docs, OR
2. Coordinate with the user to restore these files first

The documentation content itself should describe the correct v0.4.0 API regardless.

## Common Pitfalls

### Pitfall 1: Sphinx -W (Warnings as Errors)
**What goes wrong:** New pages referenced in toctree but not created, or cross-references to pages that don't exist, cause build failure.
**Why it happens:** `just docs-build` runs `sphinx-build -W` (strict mode).
**How to avoid:** Create all pages before building. Verify every `:doc:` cross-reference target exists. Run `just docs-build` as final validation.
**Warning signs:** Build warnings mentioning "unknown document" or "toctree contains reference to nonexistent document".

### Pitfall 2: Tab-Set Sync Group Mismatch
**What goes wrong:** DuckDB tab doesn't sync with Snowflake/Databricks tabs across the page.
**Why it happens:** Missing `:sync-group: warehouse` or wrong `:sync:` key.
**How to avoid:** Use `:sync: duckdb` consistently and `:sync-group: warehouse` on every tab-set.
**Warning signs:** Clicking "DuckDB" on one tab-set doesn't switch other tab-sets.

### Pitfall 3: conf.py nav_links Not Updated
**What goes wrong:** New pages exist but don't appear in the sidebar navigation.
**Why it happens:** Shibuya theme uses `nav_links` in `html_theme_options` for sidebar, separate from toctree.
**How to avoid:** Add entries to both toctree AND nav_links. Check the existing pattern in conf.py.
**Warning signs:** Page loads via URL but is not visible in sidebar.

### Pitfall 4: Documenting Reverted Source State
**What goes wrong:** autoapi generates reference from current (reverted) source, creating inconsistency with how-to guides.
**Why it happens:** Branch has worktree reversion issues (see "Critical Finding" above).
**How to avoid:** Restore reverted files before running docs build. Or skip autoapi check during writing and verify after source restoration.
**Warning signs:** autoapi docs show `Dialect.MOCK` instead of `Dialect.DUCKDB`, or `pool_from_config()` docs don't mention DuckDB.

### Pitfall 5: DuckDB Pool Size Gotcha in Examples
**What goes wrong:** Example shows `pool_size > 1` with `:memory:` which raises ValidationError.
**Why it happens:** DuckDBConfig enforces pool_size=1 for in-memory databases.
**How to avoid:** Always use `pool_size=1` (the default) for `:memory:` examples. Mention file-backed databases for pool_size > 1.
**Warning signs:** User copies example and gets a ValidationError at runtime.

## Code Examples

### Arrow Output How-to: Core Example

```rst
.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   table = cursor.fetch_arrow_table()
   print(type(table))
   # <class 'pyarrow.lib.Table'>
   print(table.schema)
   # country: string
   # revenue: int64
```

[VERIFIED: fetch_arrow_table() exists on SemolinaCursor, delegates to ADBC cursor]

### Arrow -> Pandas Conversion

```rst
.. code-block:: python

   table = cursor.fetch_arrow_table()
   df = table.to_pandas()
   print(type(df))
   # <class 'pandas.core.frame.DataFrame'>
```

[ASSUMED: standard pyarrow.Table.to_pandas() API]

### Arrow -> Polars Conversion

```rst
.. code-block:: python

   import polars as pl

   table = cursor.fetch_arrow_table()
   df = pl.from_arrow(table)
   print(type(df))
   # <class 'polars.dataframe.frame.DataFrame'>
```

[ASSUMED: standard polars.from_arrow() API]

### DuckDB Backend Page: TOML Config

```rst
.. code-block:: toml

   # .semolina.toml
   [connections.default]
   type = "duckdb"
   database = "/path/to/warehouse.db"
```

[VERIFIED: DuckDBConfig accepts database field, type="duckdb" used in _CONFIG_MAP]

### DuckDB Backend Page: Manual Pool Construction

```rst
.. code-block:: python

   from adbc_poolhouse import DuckDBConfig, create_pool
   from semolina import register

   config = DuckDBConfig(database="/path/to/warehouse.db")
   pool = create_pool(config)
   register("default", pool, dialect="duckdb")
```

[VERIFIED: DuckDBConfig and create_pool pattern from adbc-poolhouse source and existing code]

### DuckDB Generated SQL (for explanation page)

```rst
.. code-block:: sql

   SELECT *
   FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])
   WHERE "country" = ?
   ORDER BY "revenue" DESC
   LIMIT 10
```

[VERIFIED: DuckDBSQLBuilder in git history at commit a96e156]

## Pages Inventory: What to Create and Update

### New Pages

| Page | Type | Content Summary |
|------|------|----------------|
| `how-to/arrow-output.rst` | How-to guide | fetch_arrow_table(), to_pandas(), pl.from_arrow(), when to use Arrow vs Row |
| `how-to/backends/duckdb.rst` | How-to guide | Install extra, TOML config, manual construction, generated SQL, semantic_view() extension auto-loading |

### Pages to Update

| Page | Changes Needed |
|------|---------------|
| `how-to/index.rst` | Add `arrow-output` and `backends/duckdb` to toctree |
| `how-to/backends/overview.rst` | Add DuckDB as first-class backend (not just testing); add DuckDB tab to manual pool tab-set; update bullet list |
| `how-to/connection-pools.rst` | Add DuckDB tab to "Size the pool" tab-set; note pool_size=1 default for DuckDB |
| `how-to/codegen.rst` | Add DuckDB tab-item to "Choose a backend" and "Understand the generated output" sections |
| `how-to/codegen-credentials.rst` | Add DuckDB credentials section (--database flag + DUCKDB_DATABASE env var) |
| `reference/config.rst` | Add DuckDB tab to field reference; update "type" field to include "duckdb" |
| `explanation/semantic-views.rst` | Add DuckDB section explaining semantic_view() table function |
| `docs/src/conf.py` | Add new pages to `nav_links` children list; add DuckDB backend page |
| `tutorials/installation.rst` | Update version number from 0.3.0 to 0.4.0 |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Sphinx 8.x with `-W` flag |
| Config file | `docs/src/conf.py` |
| Quick run command | `uv run sphinx-build -W docs/src docs/_build` |
| Full suite command | `just docs-build` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | Arrow how-to page renders with correct content | smoke | `just docs-build` (no warnings) | No -- new page |
| DOCS-02 | Three-backend guide renders with DuckDB sections | smoke | `just docs-build` (no warnings) | No -- new page + updates |

### Sampling Rate
- **Per task commit:** `just docs-build`
- **Per wave merge:** `just docs-build`
- **Phase gate:** Full build green before `/gsd-verify-work`

### Wave 0 Gaps
- None -- Sphinx build infrastructure exists and is functional

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `table.to_pandas()` provides zero-copy conversion from pyarrow.Table | Code Examples | Low -- well-documented pyarrow API, but "zero-copy" depends on column types. Should note this caveat in docs. |
| A2 | `polars.from_arrow(table)` provides zero-copy conversion from pyarrow.Table | Code Examples | Low -- standard polars API. If method name is different, docs would show wrong code. |
| A3 | Reverted source files need restoration before docs build will pass cleanly | Critical Finding | High -- if autoapi generates docs from reverted source, reference pages will be inconsistent with how-to content |

## Open Questions

1. **Should reverted source files be restored before or during Phase 37?**
   - RESOLVED: Wave 0 restoration task added to 37-01 (Task 0). Restores all six source files plus associated test files from commit 2e170a6 (last known-good state before the 2933df2 revert). Runs `just test` and `prek run --all-files` as acceptance criteria.

2. **Should the DuckDB how-to page cover the semantic_views extension auto-loading?**
   - RESOLVED: Covered in 37-01 T2 as implementation detail note. The DuckDB backend how-to "Generated SQL" section notes that the `semantic_views` extension loads automatically via the `_load_semantic_views` event listener -- users do not need to run INSTALL or LOAD manually.

3. **Should connection-pools.rst add a DuckDB tab?**
   - RESOLVED: Covered in 37-02 T1. A DuckDB tab is added to the "Size the pool" tab-set in connection-pools.rst with a `.. note::` about pool_size=1 default for in-memory databases.

## Sources

### Primary (HIGH confidence)
- `src/semolina/cursor.py` -- fetch_arrow_table() implementation and docstring
- `src/semolina/config.py` -- pool_from_config() and _CONFIG_MAP (both current and correct versions)
- `src/semolina/engines/duckdb.py` -- DuckDBEngine introspection
- `src/semolina/cli/codegen.py` -- DuckDB codegen CLI with --database option
- `docs/src/` -- All existing RST files examined for current state
- `docs/src/conf.py` -- Sphinx config, nav_links structure
- adbc-poolhouse `DuckDBConfig` source -- DuckDB config fields (database, read_only, pool_size)
- Git history commits a96e156, 1c109b2, 3cdd382, 5243206 -- DuckDB dialect, config, SQL builder code

### Secondary (MEDIUM confidence)
- `.planning/phases/36-duckdb-codegen/36-01-SUMMARY.md` -- Phase 36 implementation details
- `.planning/phases/36-duckdb-codegen/36-02-SUMMARY.md` -- DuckDB CLI wiring details

### Tertiary (LOW confidence)
- pyarrow `Table.to_pandas()` zero-copy behavior -- based on training knowledge [ASSUMED]
- polars `from_arrow()` API -- based on training knowledge [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new tools, everything already in place
- Architecture: HIGH -- patterns established by 12 existing how-to pages
- Pitfalls: HIGH -- based on direct examination of Sphinx config and build setup
- API surface: HIGH -- verified from source code
- Worktree reversion finding: HIGH -- verified via git diff analysis

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (stable -- documentation tooling and patterns are well-established)
