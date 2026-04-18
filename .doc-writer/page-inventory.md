# Page Inventory

**Generated:** 2026-04-10
**Scope:** New pages addressing undocumented symbols and persona-identified content gaps
**Existing pages:** 13 (unchanged, not included in this inventory)

## Proposed Documentation

| # | Type | Title | Key Sections | File Path |
|---|------|-------|--------------|-----------|
| 1 | how-to | How to set up connection pools for production | Pool sizing, lifecycle management, multiple pools with .using(), TOML named sections, closing pools | docs/src/how-to/connection-pools.rst |
| 2 | how-to | How to serialize results for API responses | Row to dict, Row to JSON, batch serialization, streaming with fetchmany_rows | docs/src/how-to/serialization.rst |
| 3 | how-to | How to configure codegen credentials | Snowflake env var table, Databricks env var table, .env file, SEMOLINA_ENV_FILE override, config file fallback | docs/src/how-to/codegen-credentials.rst |
| 4 | how-to | How to use Semolina in a web API | FastAPI endpoint example, Django view example, request-scoped queries, conditional filters from query params, error handling | docs/src/how-to/web-api.rst |
| 5 | explanation | Understanding the connection and pool architecture | Why pools replaced engines, Dialect enum, pool registry lifecycle, register/get_pool/unregister, how .execute() resolves pools | docs/src/explanation/connection-architecture.rst |

## API Reference Status

**Detected:** sphinx-autoapi, configured in `docs/src/conf.py` with `autoapi_root = "reference"`. All public symbols from `semolina/__init__.py` and subpackages appear in auto-generated reference pages under `reference/semolina/`. No manual reference pages proposed.

The undocumented symbols from the gap report are handled as follows:

- **Predicate** -- Referenced in new explanation page (#5) and already linked from the filtering how-to. Docstring covered by autoapi.
- **Dialect (StrEnum)** -- Explained in new explanation page (#5) and shown in connection pool how-to (#1). Docstring covered by autoapi.
- **get_pool** -- Shown in new connection pool how-to (#1) and explanation page (#5). Docstring covered by autoapi.
- **get_engine** -- Deprecated legacy API. Mentioned briefly in explanation page (#5) as legacy. Docstring covered by autoapi.
- **SemolinaConnectionError** -- Shown in web API error handling (#4) and codegen credentials (#3). Docstring covered by autoapi.
- **SemolinaViewNotFoundError** -- Shown in web API error handling (#4). Docstring covered by autoapi.
- **CredentialError, SnowflakeCredentials, DatabricksCredentials** -- Shown in codegen credentials how-to (#3). Docstrings covered by autoapi.
- **Engine, DialectABC, SnowflakeDialect, DatabricksDialect, MockDialect, MockEngine, SnowflakeEngine, DatabricksEngine** -- Internal implementation classes. Engine is deprecated (replaced by pools). Dialect ABCs are internal SQL generation machinery. All are covered by autoapi reference output. No prose pages needed for these internal classes.

## Audience Targeting

| Page | Primary Persona | Secondary Persona |
|------|----------------|-------------------|
| #1 Connection pools | Data engineers (pool sizing, lifecycle) | Web developers (multi-pool, .using()) |
| #2 Serialization | Web developers (JSON API responses) | Data engineers (dict conversion) |
| #3 Codegen credentials | Data engineers (warehouse credentials) | Web developers (env var config) |
| #4 Web API | Data engineers (building endpoints is in their never-assume list) | Web developers (familiar with frameworks, quick reference) |
| #5 Connection architecture | Both (understanding why pools exist and how they work) | -- |

## Coverage Gap Resolution

The five persona-identified content gaps map to proposed pages:

1. **Production connection pooling** (FAIL) --> Page #1 (connection-pools.rst) + Page #5 (connection-architecture.rst)
2. **Row-to-JSON serialization** (PARTIAL) --> Page #2 (serialization.rst)
3. **Multi-pool registration** (PARTIAL) --> Page #1 (connection-pools.rst) assembles the end-to-end example
4. **Codegen environment variables** (PARTIAL) --> Page #3 (codegen-credentials.rst) with full env var tables
5. **API endpoint integration** (PARTIAL) --> Page #4 (web-api.rst) with FastAPI and Django examples

## Navigation Impact

New pages require updates to:

- `docs/src/how-to/index.rst` -- add four new entries to the toctree and inline abstracts
- `docs/src/explanation/index.rst` -- add one new entry to the toctree and inline abstract
- `docs/src/conf.py` -- no nav_links changes needed (section-level links, not per-page)
- Existing pages with cross-reference updates:
  - `how-to/queries.rst` "See also" section: add link to serialization.rst
  - `how-to/backends/overview.rst` "See also" section: add link to connection-pools.rst
  - `how-to/codegen.rst` "Credentials come from environment variables" paragraph: replace cross-reference to point at codegen-credentials.rst instead of backend pages
