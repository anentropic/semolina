# Persona Report

**Generated:** 2026-08-16
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 6 (S1–S5 reused from 2026-08-14; S6 added for the expanded `dto-codegen` page)
**Results:** 4 PASS, 2 PARTIAL, 0 FAIL

## Summary

Every FAIL and most PARTIALs from the previous pass have been closed. The error-handling
section of `how-to/web-api.rst` — the one thing that previously shipped a broken endpoint —
is now correct and unusually good: it names the driver exception hierarchy, states plainly
that Semolina re-raises unwrapped, marks the Snowflake/Databricks column "not yet measured"
instead of guessing, catches `sqlalchemy.exc.TimeoutError` for pool exhaustion, and warns
that a missing view is not a 404. `serialization.rst` now leads with the `Decimal`
`TypeError` rather than showing `json.dumps` succeeding, and `queries.rst`/`ordering.rst`
both state there is no `.offset()` and show keyset pagination. For this persona the
install → endpoint → deploy path is now unbroken.

The new `how-to/dto-codegen.rst` is the best page in the set for this persona's actual job.
All three routes are documented, the generated output is shown verbatim rather than
described, and the per-backend alias/annotation differences are laid out honestly. The
codegen route to a typed FastAPI response works end to end.

Two things stop it being clean. First, a factual contradiction: `how-to/typed-results.rst`
asserts that "a money column arrives as [a `Decimal`] on all three backends" and its
Databricks tab hand-writes `revenue: decimal.Decimal`, while
`explanation/type-fidelity.rst` states — from a measurement — that the Databricks ADBC
driver delivers decimals as Arrow **strings**, that a money column annotates `str` there,
and that "without `validate=True` the same DTO is refused". `explanation/duckdb-vs-warehouse.rst`
sides with the wrong one ("Treat a decimal metric as arriving as a `Decimal` everywhere").
A reader deploying to Databricks cannot tell which page to believe. This is not friction;
it is one page asserting something another page measured to be false. It is the single
highest-value fix in this report even though it does not, on its own, block a scenario.

Second, discoverability of the DTO path. `how-to/web-api.rst` — the page this persona
lives on — never mentions `semolina codegen-dto`, and lists `howto-typed-results` nowhere
in its "See also". The landing page has no route to the Explanation section at all, so
`AGG()` vs `MEASURE()` (an explicit never-assume item) is still shown in a dozen SQL
tab-sets and explained only in passing, on a page about developing against DuckDB.

---

## Scenario S1: Install with the Snowflake backend, configure `.semolina.toml`, define a model, execute a first query

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` — one-line pitch, "Quick example" showing model + `create_engine`/`register` + query + `fetchall_rows()`, four cards. Followed "Get started in 5 minutes" → `tutorials/installation`.
2. `tutorials/installation.rst` — Python 3.11 prerequisite, pip/uv tabs, `semolina[snowflake]`, the `async` extra with its `adbc-poolhouse[async]>=1.6.2` floor and the reason for it, the four result extras with which one covers which method, two verification commands. Followed "Next steps".
3. `tutorials/first-query.rst` — model, the warehouse-side DDL for Snowflake and Databricks in a synced tab-set, `register("default", create_engine("default"))`, query, `fetchall_rows()`, expected output, and a complete runnable DuckDB variant so the tutorial finishes with no warehouse. Friction: step 2 says the TOML `type` field decides the backend but shows no TOML. Followed `:ref:howto-backends-overview`.
4. `how-to/backends/overview.rst` → `how-to/backends/snowflake.rst` — the full `.semolina.toml` block, a field table with required/optional marked, the note that `database`/`warehouse` are optional for querying but required for codegen, and a warning that Snowflake result columns arrive as `COUNTRY` / `AGG("REVENUE")` with `row.revenue` raising `AttributeError`. Goal reached.

### Gap Analysis

**Where:** `docs/src/index.rst` (card grid); `docs/src/tutorials/first-query.rst` ("See also" grid); `docs/src/reference/config.rst` ("See also")
**What:** Two small navigation defects, unchanged since the last pass. (1) Neither the landing page nor the first-query tutorial links to `explanation/semantic-views`, though "semantic layer" appears in the landing page's first sentence and is on this persona's never-assume list. (2) `reference/config.rst`'s "See also" reads ":ref:`tutorial-installation` — set up your first `.semolina.toml`", but `tutorials/installation.rst` never mentions `.semolina.toml`; the link does not deliver what it promises.
**Impact:** Friction only. The tutorial shows warehouse DDL, so the concept is inferable, and the TOML is one more hop away.
**Suggested Fix:** In `docs/src/index.rst`, add a fifth grid card ("New to semantic views?" → `explanation-semantic-views`). In `docs/src/tutorials/first-query.rst`, add `:ref:explanation-semantic-views` as the first "See also" card. In `docs/src/reference/config.rst` "See also", repoint the `.semolina.toml` setup link at `howto-connection-pools` or `howto-backends-snowflake`, which actually show the file.

---

## Scenario S2: FastAPI endpoint — dynamic filters, ordering, pagination, JSON, and warehouse failures mapped to HTTP status codes

**Verdict:** PASS (was FAIL on 2026-08-14 — converged)

### Navigation Path

1. `docs/src/index.rst` → "Build queries" card → `how-to/queries.rst` — the full builder, per-dialect SQL for every clause, immutability and forking, the fetch-method inventory, `.to_sql(dialect=...)`, and a `.. note:: There is no .offset()` that names keyset pagination as the replacement and says why it is cheaper on an aggregate query. The previous pagination gap is closed here and again in `how-to/ordering.rst`.
2. `how-to/filtering.rst` — operator table, named lookups, `&`/`|`/`~`, the `None`-as-no-op idiom, and the `&`-binds-tighter-than-`|` precedence warning.
3. `how-to/index.rst` → `how-to/web-api.rst` — lifespan engine setup, a query endpoint, conditional filters from `Query(default=None)`, cursor-as-context-manager, `.using()` per endpoint.
4. `how-to/web-api.rst` > "Handle errors" — now correct. It states that `.execute()` returns the connection to the pool and re-raises the driver's exception unchanged, names `adbc_driver_manager.Error` and its DBAPI subclasses, gives a worked `try/except → 503/500` handler, shows the measured DuckDB failure table with Snowflake/Databricks left explicitly "not yet measured", covers `sqlalchemy.exc.TimeoutError` for pool exhaustion (including that a bare `except TimeoutError:` misses it), warns that a missing view is not a 404 and that you should validate the view name yourself rather than pattern-matching driver messages, and states that there is deliberately no common `SemolinaError` base. It also disposes of the previous trap directly: a note saying `SemolinaViewNotFoundError` / `SemolinaConnectionError` are raised only by `introspect()` and that a `try` block around `.execute()` catching them will never fire.
5. `how-to/serialization.rst` — now opens the JSON section with `json.dumps(dict(row))` raising `TypeError: Object of type Decimal is not JSON serializable`, supplies a `default=` encoder, explains `str()` vs `float()` per field, notes that FastAPI's `JSONResponse` raises for the same reason, and links `explanation-type-fidelity`, `howto-typed-results`, and `explanation-duckdb-vs-warehouse`.

Goal reached: filters, ordering, limit, a stated pagination strategy, a working status-code mapping, and JSON that survives a `Decimal`.

---

## Scenario S3: Async deployment — engine lifecycle, pool sizing, timeouts, cancellation

**Verdict:** PASS

### Navigation Path

1. `tutorials/installation.rst` > "Optional: async support" — the extra, the `adbc-poolhouse[async]>=1.6.2` floor with its reason, the combined install, and an import check that distinguishes "extra missing" from "package missing".
2. `how-to/web-api.rst` — async lifespan with `create_async_engine` / `register_async_engine` / `unregister_async_engine` / `await engine.dispose()`; why construction is sync and teardown awaited; `async with await query.aexecute()`; `description`/`rowcount` stay synchronous; loop-agnostic (asyncio or Trio, nothing to configure); `ConnectionBusyError` with the correct remedy and why a lock would be worse; the `async with` warning stating the async cursor has no finalizer; `asyncio.timeout` → 504 including which exception you actually catch, the driver-level `adbc_cancel` from inside a shield, and that the invalidated connection is replaced and the checkout count returns to zero; the Starlette client-disconnect watcher and when to prefer a plain deadline.
3. `how-to/connection-pools.rst` — direct-engine vs named-registry patterns with SQLAlchemy/Django analogies, `pool_size`/`max_overflow`/`timeout`/`recycle` in both config-object and TOML form with a defaults table, the DuckDB `:memory:` `pool_size=1` constraint, the key capacity-planning sentence (the async pool's limiter is `pool_size + max_overflow`; Semolina adds no second bound, so your own semaphore only lowers throughput), the two separate registries, and — new since the last pass — a `.. warning::` naming `sqlalchemy.exc.TimeoutError` as the checkout exception with a worked 503 mapping and a note that the async pool surfaces the same one. The previous S3 gap is closed.
4. `how-to/streaming.rst` — `async for row in cursor`, where the work happens, and mid-iteration cancellation semantics.

Goal reached.

---

## Scenario S4: Understand semantic views and Metric/Dimension/Fact, including AGG vs MEASURE

**Verdict:** PARTIAL (unchanged from 2026-08-14)

### Navigation Path

1. `docs/src/index.rst` — four cards: Get started, Define models, Build queries, API reference. None points at Explanation. **Type-alignment friction:** arriving in study mode ("what is a semantic layer?"), every offered route is a tutorial or a how-to that assumes the concept. The only way in is the top-nav Explanation tab.
2. `explanation/semantic-views.rst` — a clear definition, how each of Snowflake, Databricks, and DuckDB implements it with vendor DDL links, the DuckDB `semantic_view()` table-function difference, and "Where Semolina fits". **Not found: the strings `AGG` and `MEASURE` do not appear on this page at all.**
3. `how-to/models.rst` — the role table, per-warehouse SQL per field type, and an honest treatment of `Fact` (Snowflake has no `FACTS` clause, Databricks has no fact concept, and at query time `Fact` and `Dimension` produce identical SQL). The previous `Metric[float]` contradiction is now mitigated by a `.. note:: float is used for brevity here; codegen writes something narrower`, which explains the `Metric[decimal.Decimal | None]()` form, why metrics admit `None`, and how `--check` and `.into()` differ. That is a real improvement.
4. `explanation/duckdb-vs-warehouse.rst` — this is where the closest thing to an AGG/MEASURE explanation now lives: a table with a "Metric wrapper" column (`AGG()` / `MEASURE()` / none) and the sentence "It wraps a metric in whatever function its dialect uses to evaluate one". Useful — but a reader asking "what is `AGG()`?" is in study mode and will not open a page titled "Developing on DuckDB, deploying elsewhere", and `explanation/semantic-views.rst` does not link to it.
5. `explanation/type-fidelity.rst` — still the deepest content for this persona: a metric is an expression, not a typed column; catalogue vs result-schema disagreement with measurements; why money is a `Decimal`; what can be NULL.

### Gap Analysis

**Where:** `docs/src/index.rst` (card grid); `docs/src/explanation/semantic-views.rst`
**What:** (1) No route from the landing page to the Explanation section, so the reader who has never met a semantic view is offered only how-tos. (2) `AGG()` vs `MEASURE()` — an explicit never-assume item — is exhibited in SQL tab-sets on at least six pages and named on the concept page zero times. The one real explanation is a table cell on a portability page nothing links to from `semantic-views.rst`.
**Impact:** Hinders rather than blocks. The reader finishes able to write correct code without understanding why a metric must be wrapped — which is exactly the understanding that prevents semantic-layer misuse (and explains why `.dimensions()` refuses a `Metric`).
**Suggested Fix:** In `docs/src/index.rst`, add a grid card linking to `explanation-semantic-views`. In `docs/src/explanation/semantic-views.rst`, add a section "Why a metric is wrapped: AGG and MEASURE" — a metric is a stored aggregation expression rather than a column, so querying it means asking the view to evaluate that expression (`AGG()` on Snowflake, `MEASURE()` on Databricks, the `metrics :=` argument on DuckDB), which is why Semolina refuses a `Metric` in `.dimensions()` — and add `:ref:explanation-duckdb-vs-warehouse` to that page's "See also". Cross-link the new section from `docs/src/how-to/models.rst` > "Choose field types".

---

## Scenario S5: Generate model classes from existing Snowflake semantic views with `semolina codegen`

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` — no card mentions codegen; followed the How-To Guides tab → `how-to/index.rst`, a bare toctree of eighteen titles with no abstracts. "codegen" and "dto-codegen" are both recognisable, but the index gives nothing to choose on.
2. `how-to/codegen.rst` — the exact command, multiple views in one call, `> models.py` with the note that there is no `--output` flag, the `codegen-lint` extra, the `--backend` table naming the introspection statement per warehouse, the warning that codegen reads `[connections.<backend>]` rather than `[connections.default]`, worked per-backend DDL → generated class examples, the field-type mapping table, why only metrics admit `None`, TODO comments, `JsonValue` for VARIANT with the warning not to reuse it as a Pydantic annotation, `source=`, the full `--check` drift report with its `Route` column and `Detail` lines, and exit codes 0–5. New and welcome: a `.. tip::` at the top pointing at `codegen-dto` for readers who wanted a result DTO instead.
3. `how-to/codegen-credentials.rst` — per-backend TOML, precedence (TOML > env > `.env`), the full `SNOWFLAKE_*` table with required/optional, key-pair auth, `SEMOLINA_ENV_FILE`, troubleshooting keyed to exit codes 2 and 4.

Goal reached.

### Gap Analysis

**Where:** `docs/src/how-to/index.rst`
**What:** Eighteen child pages listed as a bare toctree with no one-line abstracts, against the project's own navigation convention. `codegen` and `dto-codegen` sit adjacent with nothing distinguishing them; `typed-results`, `serialization`, and `arrow-output` are three plausible answers to "how do I get JSON out" with no way to choose.
**Impact:** Minor friction, but it is the weakest link in navigation for every scenario that starts from the landing page, and it now costs more than it did with seventeen pages.
**Suggested Fix:** In `docs/src/how-to/index.rst`, replace the bare toctree listing with a `grid`/`grid-item-card` layout giving each page a one-sentence abstract, grouped as Connect / Model / Query / Results / Generate.

---

## Scenario S6: From "I have a query" to "I have a typed row object in my FastAPI endpoint" (`semolina codegen-dto` → `.into()`)

**Verdict:** PARTIAL

### Navigation Path

1. `docs/src/index.rst` — nothing on the landing page mentions typed results or DTOs. The "Quick example" ends at `print(row.country, row.revenue)`, which the docs elsewhere say raises `AttributeError` on Snowflake. Followed the How-To Guides tab.
2. `how-to/index.rst` — found `dto-codegen` by title alone (see S5 gap).
3. `how-to/web-api.rst` > "Build a query endpoint" — the endpoint returns `[dict(row) for row in rows]`, with a warning that the keys are the warehouse's spellings and the sentence "Map them explicitly or return typed objects (:ref:`howto-typed-results`) rather than letting the warehouse's spelling leak into your public JSON." That inline link is the *only* route from the FastAPI page to the typed path. Its "See also" lists connection-pools, streaming, installation, queries, serialization, duckdb-vs-warehouse, and filtering — neither `howto-typed-results` nor `howto-dto-codegen`.
4. `how-to/dto-codegen.rst` — excellent. All three routes documented; generated output shown verbatim including the provenance header; `--name`, `--output`, multi-path emission, duplicate-class refusal; the complete `[tool.semolina.dto]` schema with both entry shapes and two key tables; relative paths resolving against `pyproject.toml`; credentials explicitly *not* in `pyproject.toml` and why; unknown keys are errors; `where()/order_by()/limit()` stripped before the probe; the per-backend alias tab-set; `Any`/`TODO:` replacement; why every metric is `| None`; the `execute-schema` vs `zero-row` probe routes with the Databricks measurement dated; what a dotted path imports; the full exit-code table including the absent `5`. It shows `.into()` in a plain script.
5. `how-to/typed-results.rst` — the FastAPI handler that closes the loop: `def revenue() -> list[RevenueByCountry]` returning `cursor.into(RevenueByCountry)` directly. Also the streaming and async twins, the `validate=` semantics table, the `SemolinaSchemaMismatchError` message, and the `arrowmodel` extra.

Goal reached on the Snowflake/DuckDB codegen route. Four things I had to guess or reconcile.

### Gap Analysis

**Where:** `docs/src/how-to/typed-results.rst` (intro paragraph and the Databricks tab under "Name the columns your warehouse returns") vs `docs/src/explanation/type-fidelity.rst` > "Databricks decimals and intervals arrive as strings" vs `docs/src/explanation/duckdb-vs-warehouse.rst` > "Decimals are not a DuckDB difference"
**What:** A direct factual contradiction across three pages. `typed-results.rst` states: "`revenue` is annotated `decimal.Decimal` because a money column arrives as one on all three backends", and its Databricks tab hand-writes `revenue: decimal.Decimal = pydantic.Field(validation_alias="measure(revenue)")`. `type-fidelity.rst` states, from a measurement, that the Databricks ADBC driver hands decimal columns over as Arrow **strings** "at every precision and scale", that a money column "annotates `str` there", and that "Without `validate=True` the same DTO is refused, because `Decimal` is not what the column delivers." `duckdb-vs-warehouse.rst` compounds it: "Treat a decimal metric as arriving as a `Decimal` everywhere." Note that `dto-codegen.rst` is *not* part of the problem — its Databricks tab shows `revenue: int | None` and correctly attributes it to a `SUM` over an integer column.
**Impact:** A reader deploying to Databricks who hand-writes a DTO from the page whose job is hand-written DTOs gets a `SemolinaSchemaMismatchError` on the default path, and the page they followed told them the annotation was right. They recover — the error names the actual Arrow type, and `codegen-dto` would have written `str` — but the docs asserted something the project has measured to be false, and gave no hint that another page disagrees. This is the most serious defect remaining in the set.
**Suggested Fix:** In `docs/src/how-to/typed-results.rst`, drop "on all three backends" from the intro, and change the Databricks tab to annotate the decimal case as the driver delivers it (`str`, with `validate=True` and `decimal.Decimal` shown as the way to get `Decimal` objects back), cross-linking `:ref:explanation-type-fidelity-databricks-decimal`. In `docs/src/explanation/duckdb-vs-warehouse.rst` > "Decimals are not a DuckDB difference", replace "Treat a decimal metric as arriving as a `Decimal` everywhere" with the measured Databricks behaviour and a link to the same anchor.

**Where:** `docs/src/how-to/web-api.rst` ("Build a query endpoint" and "See also")
**What:** The page this persona works from never names `semolina codegen-dto`, and omits `howto-typed-results` from its "See also" despite recommending typed objects in its own prose. The endpoint examples all return `[dict(row) for row in rows]` with the warehouse's column spellings; the typed alternative — which is the page's own stated recommendation for a public JSON body — is reachable only via one inline `:ref:` mid-paragraph.
**Impact:** Hinders. A developer who reads `web-api.rst` end to end ships `dict(row)` endpoints leaking `AGG("REVENUE")` as a JSON key, and never learns that a command exists which would have generated the DTO for them. **Type-alignment note:** the reader is in work mode on a how-to and the how-to that completes the task is not offered in the place where the decision is made.
**Suggested Fix:** In `docs/src/how-to/web-api.rst` > "Build a query endpoint", add a short subsection (or a `.. tip::`) showing the typed variant — `def revenue() -> list[RevenueByCountry]: return cursor.into(RevenueByCountry)` — with one sentence saying `semolina codegen-dto` writes that class for you. Add `:ref:howto-typed-results` and `:ref:howto-dto-codegen` to the page's "See also".

**Where:** `docs/src/how-to/dto-codegen.rst` (whole page; no section names the runtime requirement)
**What:** The page is self-contained on generation but not on use. Its `.into()` snippet is presented as the payoff — "The generated class is what `.into()` wants" — yet the page never states that `.into()` requires the `arrowmodel` extra, or that the generated module imports `pydantic`. Following this page alone produces a committed `dtos.py` and a `SemolinaMissingDependencyError` on the first request. `typed-results.rst` has the install line, one hop away in "See also".
**Impact:** Hinders. One avoidable failure at exactly the moment the reader thinks they are finished, on a page whose stated convention is self-containment.
**Suggested Fix:** In `docs/src/how-to/dto-codegen.rst`, add one line beside the `.into()` snippet: `pip install semolina[arrowmodel]`, with `:ref:tutorial-installation-result-extras`.

**Where:** `docs/src/how-to/dto-codegen.rst` > "Know what a dotted path imports"; and the ordering of the first three section headings
**What:** Two smaller things a reader must guess at. (1) The `sys.path` paragraph says "The working directory is appended to `sys.path`... A package at your project root therefore resolves without being installed." A `src/` layout — the common shape for this persona's FastAPI service — puts the package at `src/myapp`, where that sentence's promise does not hold and `myapp.queries.revenue_by_country` exits `2`. The page never mentions the case, so the reader guesses between installing the project editable, running the command from `src/`, and the `--view` route. Related and unmentioned: if the application package's import graph reaches the not-yet-generated `dtos` module, the very first generation run fails on an import of the file it is about to write. (2) The headings "Generate a DTO from a module-level query" (which teaches the dotted-path route) and, two sections later, "Point codegen at the query you already wrote" (which is actually about `where()`/`order_by()`/`limit()` being stripped) read as two introductions to the same route. Scanning the headings, I opened the third expecting the first.
**Impact:** Friction. Neither blocks a determined reader, but both cost a run-and-guess cycle in exactly the project layout this persona uses.
**Suggested Fix:** In `docs/src/how-to/dto-codegen.rst` > "Know what a dotted path imports", add a sentence covering the `src/` layout (install the project, or run from the directory holding the package) and one on generating into a module the package already imports. Rename "Point codegen at the query you already wrote" to something naming its actual subject, e.g. "Filters and ordering do not change the DTO".

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario is blocked.

### PARTIAL Issues (for project author approval)

Listed in the order I would fix them.

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S6 | `how-to/typed-results.rst`; `explanation/duckdb-vs-warehouse.rst` | Both assert a decimal metric arrives as a `Decimal` on all three backends and hand-write `revenue: decimal.Decimal` for Databricks. `explanation/type-fidelity.rst` states from measurement that the Databricks driver delivers decimals as Arrow strings and that such a DTO is refused without `validate=True`. Three pages, two answers, no cross-reference. | Correct `typed-results.rst`'s intro sentence and Databricks tab to match the measured behaviour and link `explanation-type-fidelity-databricks-decimal`; replace "Treat a decimal metric as arriving as a `Decimal` everywhere" in `duckdb-vs-warehouse.rst` with the same. |
| S6 | `how-to/web-api.rst` > "Build a query endpoint", "See also" | The FastAPI page never mentions `semolina codegen-dto`, and omits `howto-typed-results` from "See also" while recommending typed objects in its prose. All its endpoints return `dict(row)` with warehouse column spellings. | Add a typed-endpoint tip showing `-> list[DTO]` + `cursor.into(DTO)` and naming `codegen-dto`; add both refs to "See also". |
| S4 | `index.rst`; `explanation/semantic-views.rst` | No route from the landing page to Explanation; `AGG()` vs `MEASURE()` is shown in SQL tab-sets on six-plus pages and never named on the concept page, despite being a never-assume item. The only real explanation is a table cell in `duckdb-vs-warehouse.rst`, which `semantic-views.rst` does not link. | Add a landing-page card to `explanation-semantic-views`; add a "Why a metric is wrapped: AGG and MEASURE" section to that page; cross-link from `how-to/models.rst` and to `explanation-duckdb-vs-warehouse`. |
| S6 | `how-to/dto-codegen.rst` | Never states that `.into()` needs the `arrowmodel` extra, so following the page alone yields a committed DTO and a `SemolinaMissingDependencyError` on first use. | Add the `pip install semolina[arrowmodel]` line beside the `.into()` snippet with a ref to `tutorial-installation-result-extras`. |
| S6 | `how-to/dto-codegen.rst` > "Know what a dotted path imports"; section ordering | The `sys.path` guidance does not hold for a `src/` layout and the page does not say so; the first and third section headings both read as introductions to the dotted-path route. | Add a `src/`-layout sentence (and the first-generation import bootstrap case); rename the third heading to name its actual subject. |
| S5 | `how-to/index.rst` | Eighteen child pages as a bare toctree with no abstracts; `codegen`/`dto-codegen` and `typed-results`/`serialization`/`arrow-output` are indistinguishable from the index. | Replace with a card grid carrying a one-sentence abstract per page, grouped Connect / Model / Query / Results / Generate. |
| S1 | `index.rst`; `tutorials/first-query.rst` > "See also"; `reference/config.rst` > "See also" | No link from landing page or tutorial to the page defining "semantic view"; `reference/config.rst` points at `tutorial-installation` for "set up your first `.semolina.toml`", but that page never mentions the file. | Add the concept links; repoint the config "See also" at a page that actually shows `.semolina.toml`. |

### Resolved since the 2026-08-14 pass

- **S2 FAIL** (`web-api.rst` documenting `except SemolinaConnectionError` / `SemolinaViewNotFoundError` around `.execute()`) — fixed and then some: driver exception hierarchy, measured-vs-unmeasured table, pool timeout, "a missing view is not a 404", and an explicit note that those two exceptions belong to `introspect()`.
- **S2 PARTIAL** (`serialization.rst` showing `json.dumps(dict(row))` succeeding) — fixed; the `Decimal` `TypeError` now leads the section.
- **S2 PARTIAL** (pagination unaddressed) — fixed in both `queries.rst` and `ordering.rst` with the keyset pattern and the reason.
- **S3 PARTIAL** (pool-checkout exception unnamed) — fixed in `connection-pools.rst` with a warning naming `sqlalchemy.exc.TimeoutError` and a 503 mapping.
- **S4 PARTIAL** (`models.rst` recommending `Metric[float]()` for money) — mitigated by the new note explaining what codegen writes and why, and how `--check` and `.into()` differ.

### Other observations (not scenario-blocking)

- `docs/src/how-to/filtering.rst` > "Use custom lookups" still tells the reader to subclass `Lookup`, then says custom lookups "require a corresponding `case` branch in the SQL compiler" — which the reader cannot add. Unchanged dead end; either document the extension point or say it is not currently user-extensible.
- `docs/src/reference/cli.rst` says a `--metrics` name must not be "one of the names reserved by the query builder", and neither that page nor `dto-codegen.rst` lists which names those are.
- `docs/src/index.rst` "Quick example" still ends at `print(row.country, row.revenue)`, the attribute access that four other pages warn raises `AttributeError` on Snowflake. It is the first code this persona reads.
- `docs/src/how-to/warehouse-testing.rst` reaches into `engine._pool`, which `connection-pools.rst` explicitly warns against.
