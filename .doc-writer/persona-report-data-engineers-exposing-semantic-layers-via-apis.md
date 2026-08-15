# Persona Report

**Generated:** 2026-08-14
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 5 (reused from `.doc-writer/scenarios.yaml`)
**Results:** 1 PASS, 3 PARTIAL, 1 FAIL

> Note on scenario reuse: three pages were added since these scenarios were generated
> (`how-to/typed-results.rst`, `how-to/streaming.rst`, `explanation/type-fidelity.rst`).
> That is a ~12% growth with no removals, so the existing scenarios were reused for
> comparability. The new pages were visited where relevant to a scenario.

## Summary

The reference and codegen material is genuinely strong: the `.semolina.toml` field
tables, the CLI reference, credential precedence, exit codes, and the drift check are
more complete than most libraries this size ship, and the semantic-layer concepts this
persona already owns are respected rather than over-explained. The problem is at the
last mile, which is exactly where this persona lives. Nearly every page shows results
being read as `row.revenue` / `dict(row) -> {"revenue": ...}`, but `Row` keys come
verbatim from `cursor.description`, and the docs' own `how-to/typed-results` page states
that on Snowflake those keys are `COUNTRY` and `AGG("REVENUE")`. A data engineer who
follows `how-to/web-api` against Snowflake ships an endpoint that raises
`AttributeError`, or hands the frontend team JSON keyed `AGG("REVENUE")`. Secondary
gaps cluster on this persona's `never_assume` list: Python extras are used constantly
but never explained (and the `pip` form is unquoted, which fails in zsh), connection
pooling is configured in detail but never defined, and `how-to/web-api` presumes fluent
FastAPI knowledge with no install step, no run command, and no sample request.

---

## Scenario S1: Configure `.semolina.toml` and connect to Snowflake

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Get started in 5 minutes" card, quick example showing `create_engine("default")` with the comment "reads .semolina.toml".
   - Followed: card link to `tutorial-installation`.
2. `tutorials/installation.rst`
   - Found: pip/uv tab-set, backend extras, verification command. Version claim `0.6.0` checks out against `pyproject.toml`.
   - Friction: `pip install semolina[snowflake]` is unquoted while the adjacent uv line is quoted. In zsh (macOS default) the unquoted form fails with `zsh: no matches found`. Nothing on the page explains what an "extra" is or that the brackets need quoting.
3. `tutorials/first-query.rst`
   - Found: step 2 registers an engine and says it "reads .semolina.toml", but the tutorial never shows the file. Followed the link out.
4. `how-to/backends/overview.rst` → `how-to/backends/snowflake.rst`
   - Found: complete TOML block plus a required/optional field table, the `create_engine` + `register` call, a note on `database`/`warehouse` being optional for queries but required for codegen, and a pointer to the shared pool fields.
5. `reference/config.rst`
   - Found: file location, `config_path` override, multi-connection structure, full Snowflake auth field list. This answered everything the how-to left open.
   - Friction: `password = "s3cret"` sits inline with no guidance on keeping the file out of version control, and no statement about whether `create_engine` (as opposed to `semolina codegen`) also falls back to `SNOWFLAKE_*` environment variables.
6. Returned to `how-to/backends/snowflake.rst` "Run a query" to verify the connection.
   - Blocked: the verification snippet prints `row.country, row.revenue`, which per `how-to/typed-results` is not what a Snowflake result yields. See S3.

### Gap Analysis

**Where:** `tutorials/installation.rst` > "Install a backend extra" (and repeated in `how-to/backends/snowflake.rst`, `databricks.rst`, `duckdb.rst`, `how-to/codegen.rst`)
**What:** The `pip install semolina[snowflake]` form is unquoted, and the concept of an
extra is never introduced. `never_assume` lists "Python packaging (extras, optional
deps)" for this persona.
**Impact:** On the default macOS shell the very first install command fails with a shell
glob error that has nothing to do with Python, and the reader has no framing to debug it.
**Suggested Fix:** In `tutorials/installation.rst`, section "Install a backend extra":
quote the pip form (`pip install "semolina[snowflake]"`) everywhere it appears, and add
one or two sentences ahead of the tab-set explaining that the bracketed name is an
optional dependency group ("extra") that pulls in the warehouse driver, and that the
quotes are needed because some shells treat brackets as glob characters.

**Where:** `reference/config.rst` > "File structure"; `how-to/backends/snowflake.rst` > "Configure with .semolina.toml"
**What:** No guidance on secret handling: whether `.semolina.toml` should be
gitignored, and whether `create_engine` reads `SNOWFLAKE_*` environment variables the way
`semolina codegen` does. `how-to/codegen-credentials.rst` says codegen "reads the same
connection config as your application engines", which implies env fallback applies to
both, but no engine-facing page confirms it.
**Impact:** A data engineer deploying to production cannot tell from the docs how to get
credentials in without committing them, so they guess or read source.
**Suggested Fix:** In `reference/config.rst`, section "File location": state explicitly
whether `create_engine` falls back to prefixed environment variables and a `.env` file,
and add a short admonition recommending `.gitignore` for `.semolina.toml` with a pointer
to the config-object route in `how-to/connection-pools.rst` for vault-sourced credentials.

---

## Scenario S2: Generate models from existing Snowflake semantic views with the codegen CLI

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Friction: no card or mention of codegen on the front page. The four cards are install, models, queries, API reference. Codegen is one of this persona's four named tasks.
2. `how-to/index.rst`
   - Found: a bare toctree of 17 titles with no abstracts. "How to generate Semolina model classes from warehouse views" is identifiable, but it sits fourteenth.
3. `how-to/codegen.rst`
   - Found: the command, multi-view invocation, `> models.py` redirect (with an explicit note that there is no `--output` flag), the `codegen-lint` extra, backend table with the introspection statement each uses, worked before/after examples per warehouse, role-to-field-type mapping, TODO comments, VARIANT handling, `--check` drift reporting, and exit codes. This is the most complete page in the set.
   - Friction: the only extra this page names is `codegen-lint`. Nothing says that `--backend snowflake` needs `semolina[snowflake]` installed to connect at all.
4. `how-to/codegen-credentials.rst`
   - Found: TOML section, env var table with required/optional flags, `.env` file, `SEMOLINA_ENV_FILE`, precedence order, and troubleshooting for exit codes 2 and 4.
   - Friction: codegen reads `[connections.snowflake]` (section named after the backend), but S1 had me create `[connections.default]`. The rule is stated, but the framing sentence "Configure a connection once and both codegen and your engines use it" only holds if the section is named after the backend *and* the app calls `create_engine("snowflake")` — a combination no page shows.
5. `reference/cli.rst`
   - Found: arguments, options, exit codes, env vars, and confirmation that `semolina` is installed as a console script with the package. Goal reachable.

### Gap Analysis

**Where:** `how-to/codegen.rst` > "Run codegen" / "Choose a backend"
**What:** The backend extra is never listed as a prerequisite. The page's only install
instruction is the optional `codegen-lint` extra, and the exit-code-4 troubleshooting in
`how-to/codegen-credentials.rst` attributes failure to credentials, key paths, and
network only.
**Impact:** A reader who installed plain `semolina` plus `codegen-lint` (the two commands
these pages actually show) has no warehouse driver, and the failure has no documented
explanation. This is the "install the right extra, then run the command" path failing at
step one.
**Suggested Fix:** In `how-to/codegen.rst`, add a one-line prerequisite above "Run
codegen": codegen connects through the same driver as your application, so install the
extra for your backend first (`pip install "semolina[snowflake]"`), linking to
`tutorial-installation`. Add a matching bullet to the exit-code-4 troubleshooting in
`how-to/codegen-credentials.rst`.

**Where:** `how-to/codegen-credentials.rst` > intro paragraph
**What:** The claim that one connection serves both codegen and your engines is true only
under a section-naming convention the rest of the docs do not follow. Every engine-facing
page tells the reader to create `[connections.default]`; codegen requires
`[connections.snowflake]`.
**Impact:** The reader follows S1, then runs codegen and gets exit 2 ("connection config
not found") on a file they were just told is correct.
**Suggested Fix:** In `how-to/codegen-credentials.rst`, section "Configure in
.semolina.toml": show the shared-section pattern end to end — a `[connections.snowflake]`
section used by codegen and read by `create_engine("snowflake")` in the app — or state
plainly that a `[connections.default]` section is invisible to codegen and a second
backend-named section is needed.

**Where:** `docs/src/index.rst` > card grid
**What:** No entry point to codegen from the front page.
**Impact:** The task this persona is most likely to arrive with (I already own the
semantic views; generate the Python for me) requires scanning an unannotated 17-item
how-to list.
**Suggested Fix:** In `docs/src/index.rst`, add a fifth grid card linking to
`howto-codegen` ("Generate models from views you already have").

---

## Scenario S3: Build a query endpoint that accepts filter parameters and returns filtered metric data

**Verdict:** FAIL

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst` → `how-to/web-api.rst`.
2. `how-to/web-api.rst`
   - Found: engine lifespan setup, a query endpoint, conditional filters from query params (the exact pattern needed), error handling mapped to 503/404, cursor context managers, timeouts, disconnect handling, per-endpoint engine selection.
   - Friction: the page presumes FastAPI fluency. There is no `pip install fastapi uvicorn`, no command to run the app, no sample request or response body, and no explanation of the lifespan handler, `@app.get`, or `Query(default=None)`. Web framework patterns and REST endpoint structure are both `never_assume` items for this persona.
   - Friction: long explanation-tier passages (ConnectionBusyError rationale, cancel scopes, shielded teardown ordering, anyio task groups) sit between the practical steps.
3. `how-to/filtering.rst`
   - Found: full operator table, named methods, AND/OR/NOT composition, an explicit "Build filters conditionally" section, and a precedence warning. Excellent for the goal.
4. `how-to/serialization.rst`
   - Found: `dict(row)`, `json.dumps(dict(row))`, `[dict(row) for row in rows]`, and the claim that this "works directly with web framework JSON responses". Sample output shown as `{"revenue": 1000, "country": "US"}`.
5. `how-to/typed-results.rst` (reached later via the how-to list)
   - Found the contradiction: a table stating that the same query returns `AGG("REVENUE")` / `COUNTRY` on Snowflake and `measure(revenue)` / `country` on Databricks, and that matching is exact string equality with no case folding.
   - Claim check against source (permitted): `SemolinaCursor._column_names()` returns `[d[0] for d in cursor.description]` and `fetchall_rows()` builds `Row(dict(zip(columns, row)))`; `Row.__getattr__` does a plain dict lookup with no normalization. The SQL shown across the docs (`SELECT AGG("revenue"), "country"`) carries no `AS` alias, and `src/semolina/dto.py` independently documents Snowflake result columns as expression text like `AGG("REVENUE")`.
   - Conclusion: the result-reading examples on the tutorial, queries, serialization, web-api, Snowflake, Databricks, README and front pages are correct only for DuckDB.

### Gap Analysis

**Where:** `how-to/serialization.rst` (all sections), `how-to/web-api.rst` (all endpoint examples), `how-to/queries.rst` > "Execute and read results", `tutorials/first-query.rst` steps 3-4, `how-to/backends/snowflake.rst` and `how-to/backends/databricks.rst` > "Run a query", plus `README.md` and `docs/src/index.rst`
**What:** Results are shown as `row.revenue` / `row.country` and `dict(row) -> {"revenue": ..., "country": ...}` on pages that are explicitly configuring Snowflake or Databricks. `Row` keys are the raw result-column names, so on Snowflake the keys are `COUNTRY` and `AGG("REVENUE")`. `row.revenue` raises `AttributeError`. Only `how-to/typed-results.rst` documents this, and it frames it as a Pydantic `validation_alias` concern rather than a fact about every result; neither `how-to/serialization.rst` nor `how-to/web-api.rst` links to it or mentions it.
**Impact:** This is the scenario's whole point — handing usable JSON to the frontend team. Following the documented endpoint pattern against the persona's own Snowflake warehouse produces either a 500 from `AttributeError` or a response body keyed `AGG("REVENUE")` that the frontend contract cannot consume. The reader has no way to discover this from the pages that lead them there, and the failure surfaces only against the real warehouse, after a DuckDB run passed.
**Suggested Fix:** In `how-to/serialization.rst`, add a section immediately after "Convert a Row to a dictionary" that states result keys come from the warehouse's own column naming, reproduces the per-backend column-name table from `how-to/typed-results.rst`, and shows the remapping the reader must do for a stable API contract (an explicit key map, or `.into(DTO)` with `validation_alias`). Correct the sample outputs on that page and in `how-to/web-api.rst` so a Snowflake-configured example does not show DuckDB-shaped keys, or state which backend each sample output is from. Add `:ref:`howto-typed-results`` to the "See also" of `how-to/serialization.rst` and `how-to/web-api.rst`.

**Where:** `how-to/serialization.rst` > "Convert a Row to JSON"
**What:** `json.dumps(dict(row))` is presented without qualification, but `explanation/type-fidelity.rst` states that a money metric arrives as `decimal.Decimal` and that `json.dumps` has no encoder for it, and `semolina codegen` annotates metrics `decimal.Decimal | None`. The serialization page never mentions `Decimal` and does not link to the explanation page.
**Impact:** The documented JSON path raises `TypeError: Object of type Decimal is not JSON serializable` on the persona's first real revenue metric.
**Suggested Fix:** In `how-to/serialization.rst`, section "Convert a Row to JSON": add the `Decimal` case with the `float()`-at-the-boundary conversion from `explanation/type-fidelity.rst` (noting Pydantic and FastAPI handle it natively), and link to `:ref:`explanation-type-fidelity``.

**Where:** `how-to/web-api.rst` > "Set up the engine at application startup" and "Build a query endpoint"
**What:** No prerequisites (FastAPI/uvicorn are never installed), no command to run the application, no sample request or response, and no explanation of the framework constructs used (lifespan handler, route decorator, `Query`). Type-alignment: the page reads as a how-to for someone already competent in FastAPI, while this persona needs the surrounding scaffolding.
**Impact:** The persona can copy the Semolina-specific lines but cannot get a running endpoint without leaving the docs, which is the outcome they adopted the library to avoid.
**Suggested Fix:** In `how-to/web-api.rst`, add a short "Prerequisites" block ahead of the first snippet (`pip install fastapi uvicorn`, the `uvicorn app:app --reload` command, and one-sentence descriptions of the lifespan handler and the route decorator), and add a `curl` request with its JSON response after "Apply conditional filters from query parameters" so the reader can confirm the contract the frontend will see.

**Where:** `how-to/web-api.rst` > "Time out a slow query", "Handle a client disconnect", and the `ConnectionBusyError` passage under "Handle errors"
**What:** Explanation-tier reasoning (cancellation propagation, shielded teardown, `BaseException` vs `Exception` suppression ordering, anyio task groups) is interleaved with the how-to steps.
**Impact:** For an intermediate reader in work mode, the actionable endpoint recipe is buried in material calibrated for the advanced persona.
**Suggested Fix:** Move the cancellation and teardown rationale into a new explanation page (or a section of `explanation/type-fidelity.rst`'s sibling) and leave the recipe plus a link in `how-to/web-api.rst`, or collapse it into `.. dropdown::` blocks so the step sequence stays legible.

---

## Scenario S4: Set up connection pooling for production

**Verdict:** PARTIAL

### Navigation Path

1. `how-to/web-api.rst` pointed to `howto-connection-pools` for sizing guidance.
2. `how-to/connection-pools.rst`
   - Found: the two usage patterns, config-object and connection-name construction, `pool_size` / `max_overflow` / `timeout` / `recycle` with defaults and a sizing tip, the DuckDB in-memory constraint, `engine.connect()` for raw access, `dispose()` lifecycle with the sync/async asymmetry explained, `get_engine`, and multi-engine registration with `.using()`.
   - Friction: the page opens with "An Engine owns one ADBC connection pool" and never says what a connection pool is or why one is needed in production — a `never_assume` item.
   - Friction: the two patterns are introduced by analogy to SQLAlchemy and to Django's database aliases. This persona has no ORM or web framework background, so the analogies carry no meaning.
   - Friction: the page title is "How to connect an engine to your warehouse", so nothing in the how-to list advertises pooling; the toctree entries carry no abstracts.
3. `reference/config.rst` > "Common fields" confirmed the same knobs are settable from TOML, including `pre_ping`, which the how-to omits.

### Gap Analysis

**Where:** `how-to/connection-pools.rst` > intro; and no explanation page covers it
**What:** Connection pooling is configured in depth but never defined. `explanation/` contains only `semantic-views` and `type-fidelity`.
**Impact:** The persona can copy working values but cannot reason about them — why a pool exists, what a checkout is, what happens at exhaustion, why `recycle` matters. `done_when` for this scenario explicitly includes understanding how pooling works.
**Suggested Fix:** Add two or three sentences at the top of `how-to/connection-pools.rst`
defining a pool from first principles (opening a warehouse connection is slow and
authenticated; the pool keeps a set of them open and lends one out per query, returning it
afterwards; concurrency is bounded by `pool_size + max_overflow`), or create a short
explanation page and link it. Replace or supplement the SQLAlchemy/Django analogies with a
plain description of each pattern, since this persona has neither reference point.

**Where:** `how-to/index.rst` (and `tutorials/index.rst`, `explanation/index.rst`, `reference/index.rst`)
**What:** Section index pages are bare toctrees with a single-line intro. The project's
own navigation convention calls for one-sentence abstracts per child, and the front page
uses cards, but the section indexes do not.
**Impact:** Finding pooling guidance means recognizing it inside a 17-title list where the
relevant page is titled "How to connect an engine to your warehouse".
**Suggested Fix:** In `how-to/index.rst`, replace the bare toctree with a grid of cards
(or a definition list) giving each guide a one-sentence abstract, grouped by task —
connect, model, query, serve, generate.

---

## Scenario S5: Understand Metric, Dimension, and Fact and how they map to warehouse definitions

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` → "Define models" card → `how-to/models.rst`.
2. `how-to/models.rst`
   - Found: the `view=` class argument with its required-ness and quoting/case-folding rules, a field-type table stating which builder method accepts each, per-field sections with Snowflake `AGG()` vs Databricks `MEASURE()` SQL side by side, the Fact story spelled out separately for Snowflake and Databricks users including that Fact and Dimension produce identical SQL, the optional type subscript, class-level descriptor access with a link to the Python descriptor HOWTO, and model immutability.
   - The ORM-style machinery is described behaviourally rather than assumed: what class-level access returns, that instances are never created, that the class freezes after definition.
3. `explanation/semantic-views.rst`
   - Found: the warehouse-side framing, links to Snowflake/Databricks/DuckDB DDL docs, the DuckDB `semantic_view()` table-function difference, and an explicit statement that Semolina reads from warehouse definitions rather than replacing them.
4. `how-to/codegen.rst` > "Understand field type mapping" confirmed the warehouse-role-to-field-type table and why only metrics admit `None`; `explanation/type-fidelity.rst` supplied the three NULL cases.

No gap. The persona's own domain knowledge is respected and the Python-side mapping is
fully specified, with the AGG/MEASURE distinction visible on every relevant example.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S3 | `how-to/serialization.rst`, `how-to/web-api.rst`, `how-to/queries.rst`, `tutorials/first-query.rst`, `how-to/backends/snowflake.rst`, `how-to/backends/databricks.rst`, `README.md`, `docs/src/index.rst` | Results shown as `row.revenue` / `{"revenue": ...}` on Snowflake- and Databricks-configured pages, but `Row` keys are raw result-column names (`COUNTRY`, `AGG("REVENUE")`). Only `how-to/typed-results.rst` says so, and nothing links to it. | Add a per-backend column-naming section to `how-to/serialization.rst` with the remapping needed for a stable API contract; label or correct sample outputs so a Snowflake example does not show DuckDB keys; cross-link `howto-typed-results` from serialization and web-api. |
| S3 | `how-to/serialization.rst` > "Convert a Row to JSON" | `json.dumps(dict(row))` shown unqualified, but money metrics arrive as `decimal.Decimal`, which `json.dumps` cannot encode. | Add the `Decimal` case and the `float()` boundary conversion; link to `explanation-type-fidelity`. |
| S3 | `how-to/web-api.rst` > startup and endpoint sections | No FastAPI install, no run command, no sample request/response, no explanation of lifespan / route decorator / `Query` — all `never_assume` items for this persona. | Add a Prerequisites block with install and run commands, brief descriptions of the framework constructs, and a `curl` example with its JSON response. |

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S1 | `tutorials/installation.rst` > "Install a backend extra" (+ backends and codegen pages) | `pip install semolina[snowflake]` unquoted fails in zsh; "extra" never explained. | Quote the pip form everywhere; add one or two sentences defining an extra and why quoting is needed. |
| S1 | `reference/config.rst` > "File location"; `how-to/backends/snowflake.rst` | No secret-handling guidance; unclear whether `create_engine` reads `SNOWFLAKE_*` env vars as codegen does. | State the engine-side env/`.env` fallback explicitly and recommend gitignoring `.semolina.toml`, pointing at the config-object route for vault credentials. |
| S2 | `how-to/codegen.rst` > "Run codegen"; `how-to/codegen-credentials.rst` > troubleshooting | Backend extra never listed as a codegen prerequisite; exit-4 troubleshooting omits the missing-driver case. | Add a prerequisite line linking to `tutorial-installation`, and a missing-driver bullet to the troubleshooting list. |
| S2 | `how-to/codegen-credentials.rst` > intro and "Configure in .semolina.toml" | "Configure a connection once and both codegen and your engines use it" holds only under a section-naming convention no other page follows (`[connections.default]` is invisible to codegen). | Show the shared backend-named section used by both codegen and `create_engine("snowflake")`, or state the limitation plainly. |
| S2 | `docs/src/index.rst` > card grid | No front-page route to codegen, this persona's headline task. | Add a card linking to `howto-codegen`. |
| S4 | `how-to/connection-pools.rst` > intro | Pooling configured but never defined; SQLAlchemy/Django analogies assume background this persona lacks. | Define a pool from first principles in two or three sentences and replace the analogies with plain descriptions. |
| S4 | `how-to/index.rst` (and the other section indexes) | Bare toctrees with no per-child abstracts; the pooling guide is titled "How to connect an engine to your warehouse". | Replace with a card grid or definition list carrying one-sentence abstracts, grouped by task. |
| S3 | `how-to/web-api.rst` > timeouts, client disconnect, `ConnectionBusyError` | Explanation-tier cancellation/teardown reasoning interleaved with how-to steps, burying the recipe for an intermediate reader. | Move the rationale to an explanation page or collapse it into dropdowns, leaving the steps plus a link. |
