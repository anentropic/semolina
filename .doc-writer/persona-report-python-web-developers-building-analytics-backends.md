# Persona Report

**Generated:** 2026-06-13
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 5
**Results:** 4 PASS, 1 PARTIAL, 0 FAIL

## Summary

The documentation serves this persona very well. A web developer who knows Python, SQL, and FastAPI but has never touched a semantic view can move from `pip install` to a working FastAPI endpoint without leaving the docs. The standout strengths are the FastAPI-specific how-to (`web-api.rst`), which gives complete endpoint code covering pool lifecycle, dynamic filters, error handling, and serialization, and the explanation page (`semantic-views.rst`), which spells out the never-assume domain concepts (what a semantic view is, Snowflake vs Databricks, the Metric/Dimension/Fact mapping). Cross-references resolve cleanly and the Diataxis split is honored: tutorials teach, how-tos do, explanation contextualizes, reference lists facts.

The single point of friction is conceptual rather than navigational: the term "AGG vs MEASURE" from this persona's never-assume list is shown in generated-SQL examples across pages but never explicitly named or explained as a Snowflake-vs-Databricks syntax difference. A determined reader infers it from the synchronized SQL tabs, so this is a PARTIAL on S4, not a blocker.

---

## Scenario S1: Install, configure TOML, define a model, execute first query end-to-end

**Verdict:** PASS

### Navigation Path

1. Started at: `index.rst` (Overview)
   - Found: quick example showing the full model -> register -> query -> read flow, plus a "Get started in 5 minutes" card linking to `tutorial-installation`.
   - Followed: the installation card.
2. Navigated to: `tutorials/installation.rst`
   - Found: Python 3.11 prerequisite, pip/uv tabs, backend extra tabs (Snowflake/Databricks/DuckDB), verify step, and a DuckDB option for following along without a warehouse. Clean "Next steps" link to first-query.
3. Navigated to: `tutorials/first-query.rst`
   - Found: model definition with the warehouse SQL it maps to (both dialects), pool registration, query building, result reading, and a complete self-contained DuckDB example with expected output. The registration step links out to `howto-backends-overview` for full TOML details.
4. Navigated to: `how-to/backends/snowflake.rst` (for real Snowflake TOML)
   - Found: complete `.semolina.toml` example, a required/optional field table, and the `pool_from_config()` + `register()` call. No missing steps.

The path from install to first result is unbroken and every concept introduced is either explained inline or linked. The persona's SQL/ORM background means the fluent API needs no extra hand-holding.

---

## Scenario S2: Build a FastAPI endpoint with dynamic filters, ordering, pagination, error handling, JSON

**Verdict:** PASS

### Navigation Path

1. Started at: `index.rst`
   - Found: "Build queries" card; How-To Guides tab in nav.
2. Navigated to: `how-to/index.rst` -> `how-to/web-api.rst`
   - Found: a near-complete answer to the entire scenario in one page -- pool setup in a FastAPI `lifespan` handler, a query endpoint, conditional filters from `Query` params using the `.where(... if x else None)` no-op pattern, `.limit()` with validation, error handling mapping `SemolinaConnectionError`/`SemolinaViewNotFoundError` to HTTP status codes, cursor-as-context-manager, and `.using()` for multiple pools.
3. Cross-referenced: `how-to/serialization.rst` for `[dict(row) for row in rows]` and batch streaming; `how-to/filtering.rst` for the full operator set; `how-to/ordering.rst` for `.order_by()` + `.limit()` top-N.
   - Found: every sub-goal (filter, order, limit, serialize, handle errors) has a working, realistic example. Code uses real analytics scenarios (revenue by country), not placeholders.

This scenario is exceptionally well served. The persona gets complete endpoint code, not just the Semolina query fragment, which matches their FastAPI-centric world.

---

## Scenario S3: Generate models from existing Snowflake semantic views via codegen CLI

**Verdict:** PASS

### Navigation Path

1. Started at: `index.rst` -> How-To Guides -> `how-to/codegen.rst`
   - Found: exact command (`semolina codegen my_schema.sales_view --backend snowflake`), multi-view invocation, piping to a file via stdout redirect, the `codegen-lint` formatting extra, a backend table, a worked Snowflake input-view -> generated-output example, TODO-comment handling for exotic types, exit codes, and `source=` casing overrides.
2. Navigated to: `how-to/codegen-credentials.rst`
   - Found: full Snowflake env-var table (required vs optional), `.env` file support, `SEMOLINA_ENV_FILE` override, TOML fallback with the important warning that `[snowflake]` codegen sections differ from `[connections.default]` pool sections, plus a troubleshooting section keyed to exit code 4.

Every element of `done_when` (exact command, credential setup, output shape, TODO/edge cases, piping to a file) is present and accurate. The credential-vs-pool-config distinction is the kind of subtlety that would otherwise trip an advanced user, and it is explicitly called out.

---

## Scenario S4: Understand semantic views and how Metric/Dimension/Fact map to the warehouse semantic layer

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `index.rst` -> Explanation tab -> `explanation/semantic-views.rst`
   - Found: a clear definition of a semantic view, how Snowflake (*semantic views*), Databricks (*metric views*), and DuckDB implement them, why they exist (single source of truth), and where Semolina fits (mirrors the warehouse as typed models). Links to `howto-models` for field types.
2. Navigated to: `how-to/models.rst`
   - Found: a field-type table mapping Metric -> `.metrics()`, Dimension/Fact -> `.dimensions()`, with backend SQL for each, and a thorough Fact-fields section explaining the Snowflake-has-no-FACTS-clause and Databricks-has-no-fact-concept nuances. The Metric/Dimension/Fact -> warehouse-column mapping is well covered.

### Gap Analysis

**Where:** `explanation/semantic-views.rst` (and the SQL tabs in `how-to/models.rst`, `how-to/filtering.rst`, `how-to/backends/snowflake.rst`)
**What:** The persona's `never_assume` list includes "AGG vs MEASURE syntax." The generated SQL examples consistently show `AGG("revenue")` for Snowflake and `MEASURE(`revenue`)` for Databricks in synchronized tabs, but no page ever names this difference or explains that `AGG` (Snowflake) and `MEASURE` (Databricks) are the two warehouses' aggregation-invocation keywords for a metric. The explanation page -- the natural home for this -- describes the concepts but not the syntax pair. This is a type-alignment near-miss: the persona arrives in study/cognition mode wanting the "why," and the syntax difference is only shown implicitly in reference-style SQL snippets elsewhere.
**Impact:** A reader who has never seen semantic-view SQL must infer the AGG/MEASURE equivalence by eye-diffing the two SQL tabs. They can do this (both tabs are always present and synchronized), so the goal is achievable, but the one explicitly never-assume syntax item is never named. This is friction, not a wall.
**Suggested Fix:** In `explanation/semantic-views.rst`, in the "How warehouses implement them" section, add one or two sentences naming the query-time syntax: Snowflake wraps a metric with `AGG(...)`, Databricks with `MEASURE(...)`, and Semolina emits the right one per registered dialect. Optionally cross-link to `howto-models` where the SQL tabs already demonstrate it. This converts an inferred mapping into an explicit, named one for the persona.

---

## Scenario S5: Register multiple named pools (Snowflake + reporting warehouse) via TOML and select per query with .using()

**Verdict:** PASS

### Navigation Path

1. Started at: `index.rst` -> How-To Guides -> `how-to/connection-pools.rst`
   - Found: pool sizing parameters with a defaults table, TOML loading via `pool_from_config()`, lifecycle management (`unregister()` + `close_pool()`), the "Register multiple pools with `.using()`" section showing two named pools (`default` and `reports`) and per-query selection, named TOML sections (`[connections.default]` / `[connections.reports]`) loaded with `pool_from_config(connection=...)`, and a "close all pools at shutdown" loop.
2. Cross-referenced: `reference/config.rst` for the full common-field set (`pool_size`, `max_overflow`, `timeout`, `recycle`) and per-backend fields; `how-to/web-api.rst` for the `.using()` pattern inside FastAPI endpoints.
   - Found: every `done_when` element -- multiple TOML sections, multiple named `register()` calls, `.using()` selection, and shutdown lifecycle -- is present with working code. The lazy pool-resolution-at-execute note is a nice advanced detail this persona will appreciate.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario failed.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S4 | `explanation/semantic-views.rst` | "AGG vs MEASURE syntax" (a `never_assume` item) is shown implicitly in SQL tabs but never named or explained as the Snowflake/Databricks metric-invocation keyword pair. | In the "How warehouses implement them" section, add 1-2 sentences naming `AGG(...)` (Snowflake) and `MEASURE(...)` (Databricks) as the query-time metric syntax, noting Semolina emits the right one per dialect; optionally cross-link to `howto-models` where the SQL tabs already show it. |
