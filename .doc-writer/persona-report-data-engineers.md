# Persona Report

**Generated:** 2026-04-29
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 5
**Results:** 5 PASS, 0 PARTIAL, 0 FAIL

## Summary

The documentation provides an excellent experience for a data engineer who already owns the semantic layer in the warehouse and wants to expose it via Python APIs. Every core task -- TOML configuration, codegen CLI, query endpoints, connection pooling, and understanding field mappings -- is reachable via clear navigation paths from the homepage. The docs consistently explain concepts the persona would not know (web framework patterns, Python packaging extras, connection pooling, ORM-style patterns) while not over-explaining warehouse concepts the persona already understands. Cross-references between pages are thorough, and every how-to guide links to related pages via "See also" sections.

---

## Scenario S1: I want to configure a .semolina.toml file and connect to my Snowflake warehouse using pool_from_config()

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: Quick example showing `pool_from_config()` with comment `# reads .semolina.toml`, plus "Get started in 5 minutes" card linking to tutorials/installation.
   - Followed: "Get started in 5 minutes" card.

2. Navigated to: `docs/src/tutorials/installation.rst`
   - Found: Installation instructions with tab sets for extras (`pip install semolina[snowflake]`). Extras explained clearly ("Installs adbc-poolhouse[snowflake] alongside Semolina") -- good for this persona's `never_assume` about Python packaging.
   - Followed: "See also" link to `howto-backends-overview`.

3. Navigated to: `docs/src/how-to/backends/overview.rst`
   - Found: Two connection patterns clearly distinguished: "TOML config (recommended)" and "Manual pool construction." TOML pattern shows `pool_from_config()` and `register()`. Links to backend-specific pages for TOML fields.
   - Followed: Link to `howto-backends-snowflake`.

4. Navigated to: `docs/src/how-to/backends/snowflake.rst`
   - Found: Complete `.semolina.toml` example with `[connections.default]` section, field table with types and required/optional markers, `pool_from_config()` + `register()` code, and tip about named connections.

5. Cross-referenced: `docs/src/reference/config.rst` (reachable via Reference toctree)
   - Found: Comprehensive TOML reference with all fields for all backends. Common fields section lists pool_size, max_overflow, timeout, and recycle as valid TOML fields with defaults. Multiple connection sections example. Snowflake-specific authentication fields (auth_type, private_key_path, JWT, OAuth, etc.).
   - Type-alignment: Reference page for looking up specific field details -- correct match.

### Assessment

Goal fully achieved. A data engineer can: (a) create a complete `.semolina.toml` with all required Snowflake fields, (b) understand that `pool_from_config()` reads the TOML and creates the pool, (c) call `register("default", pool, dialect=dialect)` to make it available for queries, and (d) use named connections with `pool_from_config(connection="analytics")`. The path from homepage to complete configuration knowledge requires 3-4 page reads, all connected by explicit cross-references. TOML examples use realistic values (account identifiers, warehouse names) rather than placeholders.

---

## Scenario S2: I want to use the codegen CLI to generate Python models from my existing Snowflake semantic views

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: No direct codegen card on homepage, but "Get started in 5 minutes" leads to installation which links to codegen.
   - Followed: "Get started in 5 minutes" card.

2. Navigated to: `docs/src/tutorials/installation.rst`
   - Found: "See also" section with direct link to `howto-codegen` ("generate Python models from your warehouse schema").
   - Followed: codegen link.

3. Navigated to: `docs/src/how-to/codegen.rst`
   - Found: Complete codegen how-to:
     - Exact CLI command: `semolina codegen my_schema.sales_view --backend snowflake`
     - Multiple views: `semolina codegen schema.sales_view schema.orders_view --backend databricks`
     - Pipe to file: `> models.py` redirect (explicitly noted: "no --output flag")
     - Backend table showing introspection method per backend
     - Full input/output examples in tab-set: warehouse SQL DDL alongside generated Python
     - Field type mapping table
     - TODO comment handling for unsupported types (GEOGRAPHY, VARIANT, ARRAY, MAP, STRUCT)
     - Exit codes table for scripting (0-4)
     - `source=` override for non-default column casing
   - Followed: Link to codegen-credentials.

4. Navigated to: `docs/src/how-to/codegen-credentials.rst`
   - Found: Complete credential configuration:
     - Snowflake environment variable table (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, etc.)
     - Full bash export + codegen example
     - `.env` file usage with example
     - SEMOLINA_ENV_FILE override for non-default .env paths
     - TOML config fallback with warning about [snowflake] vs [connections.default] distinction
     - Priority chain: env vars > .env file > TOML config
     - Troubleshooting section for exit code 4

5. Cross-referenced: `docs/src/reference/cli.rst`
   - Found: Formal CLI reference with arguments, options, exit codes, and environment variable tables. Consistent with how-to content.
   - Type-alignment: Reference page for exact syntax lookup -- correct match.

### Assessment

Goal fully achieved with no friction. All criteria met: exact CLI command, credential setup via three methods (env vars, .env, TOML fallback), complete output examples, file piping, and edge case handling. The credential loading priority chain is clearly documented.

---

## Scenario S3: I want to build a query endpoint that accepts filter parameters from the frontend and returns filtered metric data

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Build queries" card linking to how-to/queries.
   - Followed: How-to section via toctree to find web-api.

2. Navigated to: `docs/src/how-to/index.rst`
   - Found: Toctree listing all how-to guides including web-api.
   - Followed: To how-to/web-api.

3. Navigated to: `docs/src/how-to/web-api.rst`
   - Found: Complete FastAPI integration guide:
     - Pool lifecycle via lifespan handler (startup: create_pool + register, shutdown: unregister + close_pool) with full code
     - Basic query endpoint: model definition, query building, `[dict(row) for row in rows]` serialization
     - Conditional filters from query parameters: exact pattern using FastAPI `Query` parameters, `None`-as-no-op `.where()` calls
     - Error handling: `SemolinaConnectionError` -> 503, `SemolinaViewNotFoundError` -> 404
     - Cursor as context manager for deterministic connection release
     - Multiple pool selection with `.using()` per endpoint
   - This page directly addresses every aspect of the persona's core task. Web framework patterns are fully explained.
   - Type-alignment: How-to guide for task-oriented doing -- correct match.

4. Cross-referenced: `docs/src/how-to/filtering.rst`
   - Found: Comprehensive filter reference: operator table, named methods (.between(), .in_(), .isnull(), .like(), etc.), boolean composition (&, |, ~), conditional filter building, operator precedence warning.

5. Cross-referenced: `docs/src/how-to/serialization.rst`
   - Found: Row-to-dict conversion, JSON serialization, batch streaming, field subsetting.

### Assessment

Goal fully achieved. The web-api.rst page is excellently calibrated for this persona. It provides complete endpoint code (not just Semolina query snippets), explains FastAPI patterns (lifespan handlers, Query parameters, HTTPException) which are in the persona's `never_assume` list, and demonstrates dynamic filter construction step by step. Serialization path from Row objects to JSON for API responses is clear.

---

## Scenario S4: I want to set up connection pooling for production use so my API can handle concurrent requests

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: No direct link to connection pools on homepage.
   - Followed: "Get started" path through installation to backends/overview.

2. Navigated to: `docs/src/how-to/backends/overview.rst`
   - Found: "See also" link to `howto-connection-pools` ("pool sizing, lifecycle, and multiple named pools").
   - Followed: connection-pools link.

3. Navigated to: `docs/src/how-to/connection-pools.rst`
   - Found: Complete production pooling guide:
     - Opening paragraph explains connection pooling in plain English: "manage a fixed set of warehouse connections, reusing them across requests instead of opening a new connection each time" -- essential since connection pooling is in `never_assume`.
     - Pool sizing with `pool_size` and `max_overflow` explained as "steady-state connections" and "burst capacity"
     - Parameter table with defaults and descriptions
     - Practical sizing tip: "Start with pool_size matching your expected concurrent query count (e.g. web server worker count)"
     - TOML-based pool configuration
     - Lifecycle management: startup (create_pool + register) and shutdown (unregister + close_pool) with warning about close_pool() vs pool.dispose()
     - Multiple pools with .using(): realistic production vs reporting pool example
     - Named TOML sections for multiple pools
     - Multi-pool shutdown pattern

4. Cross-referenced: `docs/src/how-to/web-api.rst`
   - Found: Pool lifecycle integrated into FastAPI lifespan handler, demonstrating the pattern in a real web framework context.

### Assessment

Goal fully achieved. Connection pooling concepts are explained from scratch for someone unfamiliar (matching `never_assume`). The sizing tip is actionable production guidance. The lifecycle pattern is complete with the important warning about using close_pool() instead of pool.dispose(). Multiple named pools are shown for the common data platform scenario of separating dashboard and reporting workloads.

---

## Scenario S5: I want to understand what Metric, Dimension, and Fact fields mean and how they map to my warehouse semantic view definitions

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Define models" card linking to how-to/models. Toctree includes explanation/index.
   - Followed: Toctree to explanation/index -> explanation/semantic-views.

2. Navigated to: `docs/src/explanation/semantic-views.rst`
   - Found: Clear explanation of what semantic views are ("a database object that sits on top of your raw tables and defines business metrics and dimensions in one governed place"). How Snowflake, Databricks, and DuckDB each implement them, with links to official warehouse documentation. "Where Semolina fits" section explaining how Python models mirror warehouse definitions. Links to codegen CLI for auto-generation.
   - Type-alignment: Explanation page for understanding concepts -- correct match.
   - Followed: "See also" link to how-to/models.

3. Navigated to: `docs/src/how-to/models.rst`
   - Found: Field type table with clear mapping:
     - Metric = "Aggregated measures: revenue totals, counts, averages" -> accepted by `.metrics()`
     - Dimension = "Categorical grouping: country, product category, date" -> accepted by `.dimensions()`
     - Fact = "Raw event-level numeric columns (unit_price, quantity)" -> accepted by `.dimensions()`
   - Detailed per-field subsections with SQL tab-sets showing AGG() for Snowflake, MEASURE() for Databricks
   - Fact section explains: Snowflake has no FACTS clause, Databricks has no native fact concept, "At query time, Fact and Dimension produce identical SQL... The distinction is semantic"
   - Guidance: "Default to Dimension. Use Fact as an intentional opt-in"

4. Cross-referenced: `docs/src/tutorials/first-query.rst`
   - Found: Tab set showing actual warehouse CREATE SEMANTIC VIEW / CREATE METRIC VIEW SQL alongside the Python model, helpful for verifying the mapping.

### Assessment

Goal fully achieved. The persona can verify the complete mapping chain: warehouse measures -> Metric (AGG/MEASURE SQL), warehouse dimensions -> Dimension (GROUP BY ALL), raw numerics -> Fact (same SQL as Dimension, semantic distinction only). The per-warehouse Fact behavior is clearly documented. The explanation page provides the conceptual frame while the models how-to provides the practical mapping details -- good Diataxis type separation.

---

## Revision Recommendations

No revision needed. All scenarios passed.
