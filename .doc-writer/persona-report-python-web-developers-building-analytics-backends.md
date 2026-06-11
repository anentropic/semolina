# Persona Report

**Generated:** 2026-06-10
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 5
**Results:** 5 PASS, 0 PARTIAL, 0 FAIL

## Summary

This is a re-test after a small round of doc edits, with focus on the just-changed
step-4 "expected output" in `tutorials/first-query.rst`. The edited output is now
internally consistent: the aggregated values (US 1500, CA 2000) match the seed data and
the model definition, and the four-line output block correctly reflects the two-`print`
loop body shown in that step. The install-to-first-query journey holds end to end with no
broken steps. All five persona scenarios pass. The documentation continues to serve this
advanced persona well: domain concepts they do not know (semantic views, AGG vs MEASURE,
Metric/Dimension/Fact mapping) are explained, while Python mechanics they do know are not
over-explained. The only observations are minor clarity nits, none of which block a goal.

---

## Scenario S1: Install Semolina with the Snowflake backend, configure a `.semolina.toml`, define a model, and execute a first query end-to-end

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: Quick example showing the full shape (model, `pool_from_config()`, query, results), plus a "Get started in 5 minutes" card linking to installation.
   - Followed: `tutorial-installation` card.
2. Navigated to: `tutorials/installation.rst`
   - Found: Python 3.11 prerequisite, pip/uv tabs, backend-extra tabs (Snowflake/Databricks/DuckDB/Both), verify step (`import semolina; print(...)` -> `0.4.0`), and a clear "Next steps" link to first-query.
   - Followed: `tutorial-first-query` link.
3. Navigated to: `tutorials/first-query.rst`
   - Found: Step 1 (model + warehouse SQL mapping in Snowflake/Databricks tabs), step 2 (register pool via `pool_from_config()`, with a DuckDB-local fallback tip), step 3 (build/run query), step 4 (read results).
   - **Focal check (edited step-4 output):** Seed data is `(1000,100,'US','West')`, `(2000,200,'CA','West')`, `(500,50,'US','East')`. Aggregating `revenue` by `country` gives US = 1000+500 = 1500 and CA = 2000. The displayed values `US 1500` / `CA 2000` are correct. The step-4 loop has two `print` statements (attribute access then dict-style access), so the four-line block (`US 1500` / `US` / `CA 2000` / `CA`) is internally consistent with that loop body. The "Complete example" loop has a single `print`, and its two-line output (`US 1500` / `CA 2000`) is consistent with it. No contradiction between the two output blocks.
   - For a Snowflake target specifically, step 2 points to `howto-backends-overview` and the `.semolina.toml` `type` field controls the warehouse, closing the loop from install to result.

### Outcome

An unbroken path from `pip install semolina[snowflake]` through TOML/pool registration to
executing a query and reading aggregated results. Every concept the persona does not know
(semantic views, the warehouse-side semantic view definition, why a metric aggregates per
dimension) is explained inline. Goal achieved.

---

## Scenario S2: Build a FastAPI endpoint accepting filter params and returning filtered, ordered, paginated metric data as JSON

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` -> followed How-To section; located `howto-web-api`.
2. Navigated to: `how-to/web-api.rst`
   - Found: complete FastAPI lifespan pool setup (`create_pool` + `register`/`unregister` + `close_pool`), a query endpoint, conditional filters from `Query` params using `.where(... if x else None)`, `.limit()` with `ge`/`le` validation, error handling with `SemolinaConnectionError`/`SemolinaViewNotFoundError` mapped to 503/404, cursor-as-context-manager, and per-endpoint `.using()` pool selection.
3. Cross-referenced: `howto-filtering` (operators, `.between`, `.in_`, AND/OR/NOT, the `&`-vs-`|` precedence warning, conditional/`None`-no-op patterns), `howto-ordering` (`.order_by`, `.asc`/`.desc`, `NullsOrdering`, top-N, `.limit` validation), and `howto-serialization` (`dict(row)`, `json.dumps`, `[dict(row) for row in rows]`, batch streaming).

### Outcome

The web-api page is essentially a ready-to-paste endpoint pattern covering pool lifecycle,
dynamic filters, ordering/limiting, error handling, and JSON serialization — every element
of `done_when`. The filtering/ordering/serialization how-tos fill in depth. Goal achieved.

---

## Scenario S3: Generate Python models from existing Snowflake semantic views via codegen and understand the output

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` -> How-To -> `howto-codegen`.
2. Navigated to: `how-to/codegen.rst`
   - Found: exact command (`semolina codegen my_schema.sales_view --backend snowflake`), multi-view invocation, `> models.py` redirect (with an explicit note that there is no `--output` flag), `--backend` table, a worked Snowflake input-view -> generated-class example, TODO-comment handling for GEOGRAPHY/VARIANT/etc., field-type mapping table, exit codes, and `source=` casing override.
   - Followed: `howto-codegen-credentials`.
3. Navigated to: `how-to/codegen-credentials.rst`
   - Found: full Snowflake env-var table (required/optional), `.env` file usage, `SEMOLINA_ENV_FILE` override, config-file fallback with the correct warning that `[snowflake]` codegen sections are distinct from `[connections.default]` pool sections, and a troubleshooting section for exit code 4.

### Outcome

Command, credentials (env vars, `.env`, config fallback), output shape, edge cases (TODO
comments, unrecognized roles failing loudly), and file redirection are all covered. Goal
achieved.

---

## Scenario S4: Understand what semantic views are and how Metric/Dimension/Fact map to the warehouse semantic layer

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` -> Explanation section -> `explanation-semantic-views`.
2. Navigated to: `explanation/semantic-views.rst`
   - Found: a from-scratch definition of a semantic view, how Snowflake (semantic views), Databricks (metric views), and DuckDB (community extension, `semantic_view()` table function) each implement them, and where Semolina fits (mirrors views as typed models; reads, does not replace).
3. Cross-referenced: `howto-models.rst` for the Metric/Dimension/Fact-to-SQL detail.
   - Found: a role/field-type table, per-type SQL output in Snowflake (`AGG("...")`) and Databricks (`MEASURE(...)`) tabs, and an explicit explanation that Snowflake declares fact-like columns in `DIMENSIONS` while Databricks has no native fact concept — directly addressing the AGG-vs-MEASURE and Fact-mapping items in `never_assume`.

### Outcome

Every `done_when` item — what a semantic view is, how Snowflake vs Databricks differ, AGG
vs MEASURE, and how Metric/Dimension/Fact map to warehouse columns — is covered with the
domain background this persona explicitly lacks. Goal achieved.

---

## Scenario S5: Register multiple named connection pools (Snowflake + reporting warehouse) via `.semolina.toml` and select per query with `.using()`

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` -> How-To -> `howto-connection-pools`.
2. Navigated to: `how-to/connection-pools.rst`
   - Found: pool sizing (`pool_size`/`max_overflow`/`timeout`/`recycle`/`pre_ping` table), loading from TOML, lifecycle (`register`/`unregister`/`close_pool` with the `close_pool` vs `dispose` warning), registering multiple named pools (`default` + `reports`), `.using("reports")` per query (with the note that pool resolution is lazy at `.execute()` time), named TOML sections (`[connections.default]` + `[connections.reports]`) loaded via `pool_from_config(connection=...)`, and closing all pools at shutdown.
3. Cross-referenced: `how-to/backends/snowflake.rst` for the full Snowflake TOML field table.

### Outcome

Multiple TOML sections, multiple `register()` calls under distinct names, `.using()`
selection, and shutdown lifecycle are all present and mutually consistent. Goal achieved.

---

## Revision Recommendations

No revision needed. All scenarios passed.

### Optional polish (non-blocking, project-author discretion)

- `tutorials/first-query.rst`, step 4 "Read the results": the four-line output block
  (`US 1500` / `US` / `CA 2000` / `CA`) is correct but interleaves the dict-access line
  between the main lines, which a fast skimmer could briefly misread as malformed rows.
  The inline comments and the preceding sentence about dual access do explain it, so this
  is a clarity nit, not a correctness issue. If desired, a one-line lead-in such as "each
  row prints twice (attribute access, then dict-style)" would remove any momentary
  ambiguity. Not required for a PASS.
