# Persona Report

**Generated:** 2026-06-10
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 5 (reused from .doc-writer/scenarios.yaml -- re-test pass)
**Results:** 3 PASS, 2 PARTIAL, 0 FAIL

## Summary

This is a re-test following two targeted edits: the Snowflake introspection SQL in
`how-to/models.rst` was corrected to `SHOW COLUMNS IN VIEW`, and `reference/cli.rst`
plus `how-to/codegen-credentials.rst` now treat `SNOWFLAKE_WAREHOUSE` as a credential.
Both edits land cleanly and introduce no new friction -- the codegen and connection
journeys (S1, S2) remain solid. The connection/pooling, codegen, and query-endpoint
journeys are strong for this persona: TOML config, `pool_from_config()`/`register()`,
the codegen CLI, and a complete FastAPI endpoint example are all present, well
cross-linked, and pitched at the right level (Python web-framework patterns are
spelled out, as the persona requires).

Two PARTIALs remain, both carried over from the prior pass. S2 surfaces a cross-page
inconsistency about whether `SNOWFLAKE_WAREHOUSE` is required, exposed precisely
because the credentials page was edited to mark it "Yes" while `reference/cli.rst`
and `how-to/backends/snowflake.rst` disagree. S5 is the previously-flagged
AGG-vs-MEASURE mapping: it remains **only implicit** -- shown in side-by-side SQL tabs
but never stated as an explicit concept, and entirely absent from the one explanation
page where this persona would look for it.

---

## Scenario S1: Configure .semolina.toml and connect to Snowflake via pool_from_config()

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: Quick example showing `pool_from_config()` + `register("default", ...)`, and grid cards. No card explicitly labelled "connect/configure," but the quick example models the exact call sequence.
   - Followed: toctree to `how-to/index.rst`, then `how-to/backends/overview.rst`.
2. Navigated to: `how-to/backends/overview.rst`
   - Found: Two registration patterns (TOML recommended, manual). Clear `pool_from_config()` -> `register()` flow. Link to `howto-backends-snowflake` for TOML fields.
   - Followed: `:ref:howto-backends-snowflake`.
3. Navigated to: `how-to/backends/snowflake.rst`
   - Found: Complete `.semolina.toml` example with `[connections.default]`, a full field table (type/account/user/password/database/warehouse/role/schema with required flags), the `pip install semolina[snowflake]` extra (correctly spelled out for this persona's never-assume list), and the `pool_from_config()` + `register()` code.
   - Success: Every "done_when" criterion met -- complete TOML, how `pool_from_config()` reads it, and how `register()` makes it available.

No friction. Type-alignment is correct: the persona is in "work" mode and lands on how-to guides that supply exact config and code.

---

## Scenario S2: Use the codegen CLI to generate models from Snowflake semantic views

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: No explicit codegen card on the landing page, but the How-To tab/toctree lists `codegen` and `codegen-credentials`.
   - Followed: toctree -> `how-to/index.rst` -> `how-to/codegen.rst`.
2. Navigated to: `how-to/codegen.rst`
   - Found: Exact command (`semolina codegen my_schema.sales_view --backend snowflake`), multi-view usage, `> models.py` redirect, backend table (Snowflake introspects via `SHOW COLUMNS IN VIEW` -- the corrected text), a worked Snowflake input-SQL -> generated-class example, TODO-comment handling, exit codes. Strong page.
   - Followed: `:ref:howto-codegen-credentials` for credentials.
3. Navigated to: `how-to/codegen-credentials.rst`
   - Found: Snowflake env var table now marks `SNOWFLAKE_WAREHOUSE` as **Required: Yes** (the edit), matching `SNOWFLAKE_DATABASE`. The `export ...` example includes `SNOWFLAKE_WAREHOUSE`. Internally consistent and complete -- this resolves the prior ambiguity about which vars are mandatory.
4. Cross-checked: `reference/cli.rst` (reachable via See-also and the Reference tab).
   - Found: The CLI reference env var table lists `SNOWFLAKE_WAREHOUSE` but has **no "Required" column at all** -- it cannot reflect the edit. A reader who lands on the reference page first sees warehouse listed flat alongside optional vars (role/schema are marked "(optional)" inline), giving no signal that warehouse is mandatory.

### Gap Analysis

**Where:** `reference/cli.rst` > "Environment variables" (Snowflake tab) vs. `how-to/codegen-credentials.rst` > "Snowflake environment variables" vs. `how-to/backends/snowflake.rst` > field table.
**What:** Three pages now disagree on whether `SNOWFLAKE_WAREHOUSE` is required for Snowflake.
- `codegen-credentials.rst`: warehouse = **Required: Yes** (codegen path).
- `reference/cli.rst`: no required/optional column for codegen env vars, so warehouse reads as undifferentiated.
- `backends/snowflake.rst`: the pool-config TOML field table marks `warehouse` = **No** (not required).

The pool-config-vs-codegen distinction is legitimate (different code paths), but a reader cannot tell that from the pages. The edit corrected the codegen how-to without aligning the CLI reference, and the backends page's "No" looks like a direct contradiction without context.
**Impact:** A determined reader following the primary codegen path (`how-to/codegen.rst` -> `how-to/codegen-credentials.rst`) gets the correct, complete answer and succeeds. The risk is a reader who consults `reference/cli.rst` first, or who notices the `backends/snowflake.rst` "No" and concludes warehouse is optional for codegen, then hits an exit-code-4 connection failure. Achievable with friction, not blocked -- hence PARTIAL.
**Suggested Fix:** In `reference/cli.rst`, "Environment variables" section: add a "Required" column to each backend's env var table mirroring `codegen-credentials.rst` (warehouse/database = Yes for Snowflake), so the reference table carries the same required-ness the how-to now asserts. Optionally, in `how-to/backends/snowflake.rst`, add a one-line note distinguishing pool-config requiredness (warehouse optional for `pool_from_config`) from codegen requiredness (warehouse required), since the two tables otherwise appear to contradict.

### Note on the edits under test

The `SNOWFLAKE_WAREHOUSE`-as-required edit and the `SHOW COLUMNS IN VIEW` correction
are both **good and introduce no new friction in the codegen journey itself**. The
PARTIAL is not caused by the edits being wrong; it is that the required-ness edit was
applied to one page of three that describe the same variable, surfacing a latent
cross-page inconsistency.

---

## Scenario S3: Build a query endpoint that accepts filter params and returns filtered metric data

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Build queries" card -> `howto-queries`; How-To toctree also lists `web-api`, `filtering`, `serialization`.
   - Followed: toctree -> `how-to/web-api.rst`.
2. Navigated to: `how-to/web-api.rst`
   - Found: Complete FastAPI endpoint code -- lifespan pool setup, a `/api/sales` endpoint with optional `country`/`min_revenue`/`limit` query params, the conditional `.where(... if x else None)` pattern, error handling mapped to HTTP 503/404, cursor-as-context-manager, and `.using()` per-endpoint. Full endpoint bodies are shown (not just the Semolina fragment), exactly as this persona needs given the never-assume list (REST/endpoint structure).
   - Followed: `:ref:howto-filtering` and `:ref:howto-serialization` for depth.
3. Navigated to: `how-to/filtering.rst`
   - Found: Operator table, named methods (`.in_`, `.between`, `.like`...), boolean composition, an explicit "Build filters conditionally" section matching the dynamic-frontend-params use case, and a precedence warning.
4. Navigated to: `how-to/serialization.rst`
   - Found: `dict(row)` and `json.dumps()` patterns for API responses.
   - Success: All "done_when" criteria met -- dynamic conditional filters, execution, and JSON-serializable results.

No friction. Strong, persona-calibrated coverage; cross-links between web-api, filtering, and serialization are clean.

---

## Scenario S4: Set up connection pooling for production concurrent requests

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` -> How-To toctree -> `how-to/connection-pools.rst`.
2. Navigated to: `how-to/connection-pools.rst`
   - Found: Opening paragraph defines what a connection pool is and why it matters (spelled out, matching the persona's never-assume "connection pooling concepts"). `create_pool` sizing params (`pool_size`, `max_overflow`, `timeout`, `recycle`, `pre_ping`) in a table with defaults, a sizing tip tied to web-worker count, TOML-loaded pooling via `pool_from_config()`, full lifecycle (startup/shutdown with `register`/`unregister`/`close_pool`), and multi-pool registration with `.using()`.
   - Followed: `:ref:howto-web-api` for pool lifecycle inside an app.
3. Navigated to: `how-to/web-api.rst`
   - Found: FastAPI `lifespan` handler creating and closing the pool -- production-shaped lifecycle.
   - Success: All "done_when" criteria met -- how adbc-poolhouse pools work, sizing/params, and lifecycle in a production app.

No friction. The page explicitly teaches the pooling concept rather than assuming it, which is correct for this intermediate, non-web-native persona.

---

## Scenario S5: Understand how Metric/Dimension/Fact map to warehouse views (incl. AGG vs MEASURE)

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Define models" card -> `howto-models`; Explanation tab -> `explanation-semantic-views`.
   - Followed: `howto-models` first (the field-types question).
2. Navigated to: `how-to/models.rst`
   - Found: A "Choose field types" table mapping `Metric` -> aggregated measures / `.metrics()`, `Dimension` -> grouping / `.dimensions()`, `Fact` -> raw numerics / `.dimensions()`. Per-field sections each show Snowflake-vs-Databricks SQL tabs: `Metric` renders `AGG(...)` on Snowflake and `MEASURE(...)` on Databricks. The corrected `SHOW COLUMNS IN VIEW` text appears in the Fact section for Snowflake introspection -- accurate and consistent with `codegen.rst`. Strong on the Metric/Dimension/Fact -> SQL-role mapping.
   - Gap noticed: The terms `AGG` and `MEASURE` appear only inside SQL code blocks. There is no prose sentence stating "a Metric compiles to `AGG()` on Snowflake and `MEASURE()` on Databricks, the two dialects' semantic-view aggregation operators." The reader must infer the AGG<->MEASURE equivalence by diffing the two tabs.
   - Followed: Explanation tab -> `explanation-semantic-views.rst` to find the conceptual "why."
3. Navigated to: `explanation/semantic-views.rst`
   - Found: Good background on what semantic views are and how Snowflake/Databricks/DuckDB implement them, plus where Semolina fits (Metric/Dimension correspond to measures/dimensions). **But the words `AGG` and `MEASURE` do not appear anywhere on this page.** The one explanation page does not address the dialect aggregation-operator difference at all.
   - Result: The mapping is reconstructable from the models how-to SQL tabs, so a determined reader succeeds -- but the explicit conceptual statement the "done_when" asks for ("how Semolina translates these into the correct SQL, AGG vs MEASURE") is never made in prose.

### Gap Analysis

**Where:** `explanation/semantic-views.rst` (entire page) and `how-to/models.rst` > "Metric fields".
**What:** The AGG-vs-MEASURE mapping is **still only implicit** (confirming the prior-pass finding -- unchanged by this round of edits). It is demonstrated by parallel SQL tabs in `models.rst` but never stated as a concept, and the explanation page that this persona would consult for the "why" omits the dialect operators entirely.
**Type-alignment:** This persona, in "study/cognition" mode for S5, needs an explanation. The available material is a how-to (action-oriented SQL snippets). The reader gets reference-by-example where they needed a conceptual statement -- a type mismatch that forces inference.
**Impact:** Does not block the goal -- the SQL tabs let a careful reader deduce that `Metric` -> `AGG()` (Snowflake) / `MEASURE()` (Databricks). But for a persona who owns the warehouse semantic layer and needs to *verify* the mapping is correct, leaving it implicit means they confirm by eyeballing code blocks rather than reading an authoritative statement. Friction, not failure -> PARTIAL.
**Suggested Fix:** In `explanation/semantic-views.rst`, "Where Semolina fits" section: add a short paragraph stating explicitly that a `Metric` is compiled to the warehouse's aggregation operator -- `AGG()` in Snowflake semantic views and `MEASURE()` in Databricks metric views -- and that Semolina selects the right one from the registered dialect, so the same Python `Metric` field is correct on both. Optionally, in `how-to/models.rst` "Metric fields", add one prose sentence before the SQL tabs naming the AGG/MEASURE equivalence rather than leaving it to the tab diff.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario failed.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S2 | `reference/cli.rst` > Environment variables (and `how-to/backends/snowflake.rst`) | `SNOWFLAKE_WAREHOUSE` required-ness now inconsistent across three pages after the credentials edit; CLI reference table has no Required column, backends pool table marks warehouse "No". | Add a "Required" column to the CLI reference env var tables mirroring `codegen-credentials.rst`; add a one-line note in `backends/snowflake.rst` distinguishing pool-config requiredness from codegen requiredness. |
| S5 | `explanation/semantic-views.rst` (and `how-to/models.rst` > Metric fields) | AGG-vs-MEASURE mapping still only implicit (shown in SQL tabs, never stated). Explanation page omits AGG/MEASURE entirely. | Add a prose paragraph in `explanation/semantic-views.rst` stating that a `Metric` compiles to `AGG()` (Snowflake) / `MEASURE()` (Databricks) and Semolina picks the operator from the dialect; optionally name the equivalence in `models.rst` before the SQL tabs. |

### Verdict convergence vs. prior pass

- S1, S3, S4: PASS (stable).
- S2: PARTIAL -- the edit under test corrected the codegen credentials page; the residual PARTIAL is a cross-page consistency issue surfaced by that edit, not a regression in the codegen journey.
- S5: PARTIAL -- unchanged; the AGG-vs-MEASURE mapping remains only implicit, confirmed as still flagged.
