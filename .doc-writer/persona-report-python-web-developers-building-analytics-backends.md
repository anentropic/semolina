# Persona Report

**Generated:** 2026-09-05
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 5
**Results:** 2 PASS, 3 PARTIAL, 0 FAIL

## Summary

The restructured set works for this persona. The six-tutorial chain holds as a sequence:
every page states its prerequisite, every prerequisite is produced by an earlier page, and
the artefacts (`tutorial.db`, `app.py`, `reports.py`, `conftest.py`, `models.py`, `dtos.py`)
carry forward without a gap. `tutorials/dashboard-api.rst` is squarely aimed at me and is the
strongest page in the set: it builds the naive endpoint, shows me exactly why the naive
response is wrong (warehouse column keys, no schema, silent `Decimal` truncation), and fixes
all three with one class. The merged how-tos are navigable -- every anchor the old page names
survived the merge (`howto-ordering` in `queries.rst`, `howto-arrow-output` in `streaming.rst`,
`howto-serialization` and `howto-result-column-names` in `typed-results.rst`,
`howto-backends-snowflake/databricks/duckdb` in `backends.rst`) and each lands on a
self-contained section. Nothing I needed was buried by a merge.

The three PARTIALs are narrow and specific, not structural. The first command of the first
tutorial fails on the default macOS shell because the extras are unquoted on that one page
while every other page quotes them. `how-to/filtering.rst` documents a custom-lookup
extension point whose example cannot run without editing Semolina's own compiler. And the
codegen tutorial's payoff -- generated DTOs used from both a handler and a test -- has a trap
that only appears when you do what the same page tells you to do, namely regenerate against
Snowflake: the generated aliases stop matching the field names your tests construct with.

Domain calibration is right for me. Semantic views, metrics-as-definitions, `AGG` vs
`MEASURE` vs `semantic_view()`, and the Metric/Dimension/Fact mapping are all explained
without being condescending about Python, descriptors, ORMs or async, which is exactly the
split I need.

---

## Scenario S1: Zero to a running FastAPI service answering `GET /revenue` with typed JSON, then pointed at Snowflake

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Start here" grid, six numbered tutorial cards, a quick example, and a note that
     already warns me `row.country` is DuckDB-only.
   - Followed: card 1 → `tutorial-installation`.
2. `tutorials/installation.rst`
   - Found: Python 3.11 prerequisite, pip/uv tabs, per-backend extras, the async extra with
     its `adbc-poolhouse>=1.6.2` floor and the reason for it, the four result extras with the
     method each one unlocks, and a verification command.
   - Friction: `pip install semolina[snowflake]` is unquoted. On zsh (macOS default) that is
     `zsh: no matches found`. One command on the same page (`"semolina[snowflake,async]"`) is
     quoted, and `how-to/backends.rst`, `how-to/warehouse-testing.rst` and
     `tutorials/dashboard-api.rst` quote consistently -- so the page contradicts its
     neighbours at the first command in the set.
   - Friction: "To follow the tutorials without a real warehouse ... See `howto-warehouse-testing`
     for the setup pattern" sends me to the pytest fixture guide (in-memory engine,
     `engine._pool` internals) when the next tutorial builds a file-backed `tutorial.db` with
     a ready-made script. I followed the link, found a testing page I was not ready for, and
     backtracked.
   - Followed: "Next steps" → `tutorial-first-query`.
3. `tutorials/first-query.rst`
   - Found: model definition, the warehouse DDL for all three backends in a tab-set,
     `create_engine`/`register`, the DuckDB `setup_tutorial.py` script, the query, the fetch,
     the column-name warning, and a complete runnable example with expected output.
   - Success: I ran the setup script and the demo mentally end to end; imports, file names and
     outputs are consistent.
4. `tutorials/shaping-a-report.rst`
   - Found: `.where()`, `&`/`|`/`~` with per-step output, `.order_by()`, `.limit()`, the
     precedence warning, and a complete `report.py`.
   - Success: the three data rows shown at the top match the setup script from step 3.
5. `tutorials/dashboard-api.rst`
   - Found: lifespan engine, `GET /revenue`, the deliberate `def`-not-`async def` explanation,
     the three problems with `dict(row)`, the Pydantic DTO with `.into()`, an optional query
     parameter through `.where(None)`, and `adbc_driver_manager.Error` → 503 with a
     reproducible way to trigger it. The full `app.py` runs as printed.
6. Pointing it at Snowflake: `dashboard-api.rst` §1 → `howto-backends-overview` for the
   `[connections.default]` TOML and `SnowflakeConfig` fields, → `howto-connection-pools` for
   `pool_size`/`max_overflow`, and §4 tells me the DTO field becomes
   `pydantic.Field(validation_alias='AGG("REVENUE")')` with `decimal.Decimal | None`.
   Everything I need to change is named.
7. Checked the project README (what I would actually see first from GitHub/PyPI)
   - Friction: its sample output block prints six lines (`US 1000 / US / CA 2000 / CA /
     US 500 / US`), i.e. unaggregated per-row values, for a query that groups a metric by
     country. The docs' own answer for the same query is `CA 2000 / US 1500`. As my first
     impression it tells me the library does not aggregate.

### Gap Analysis

**Where:** `tutorials/installation.rst` > "Install a backend extra", "Optional: formatted
codegen output", "Optional: async support", "Optional: dataframes and typed results"
**What:** Nine `pip install semolina[...]` commands are unquoted; one command on the same page
and every other page in the set quote them.
**Impact:** The first command of the first tutorial errors on the default macOS shell. Not
fatal for an advanced reader, but it is the worst possible place for a copy-paste failure and
it makes the page look less carefully checked than it is.
**Suggested Fix:** In `tutorials/installation.rst`, all install sections: quote every extras
spec (`pip install "semolina[snowflake]"`), matching `how-to/backends.rst`. Apply the same to
`README.md`.

**Where:** `tutorials/installation.rst` > "Install a backend extra", final paragraph
**What:** The "follow the tutorials without a real warehouse" pointer names an in-memory
engine and links `howto-warehouse-testing`, but the tutorial chain uses a file-backed
`tutorial.db` created by the script in `tutorials/first-query.rst` §2.
**Impact:** A reader on tutorial 1 who takes the link lands in a pytest how-to that reaches
into `engine._pool` and presupposes tutorials 4 and 5. It is a sideways jump out of the chain
at the exact moment the chain is about to answer the question.
**Suggested Fix:** In `tutorials/installation.rst`, "Install a backend extra": point at
`tutorial-first-query` ("the next tutorial builds a local DuckDB database for you") and keep
`howto-warehouse-testing` for the test-suite case only.

**Where:** `README.md` > quick start, final output block
**What:** The expected output shows three unaggregated rows for a query that selects
`.metrics(Sales.revenue).dimensions(Sales.country)`; `docs/src/index.rst` and
`tutorials/first-query.rst` show the correct aggregated `CA 2000 / US 1500`. The block also
interleaves the attribute-access and dict-access prints in a way that reads as duplicate rows.
**Impact:** The README is the first page most of this persona sees. An output that contradicts
the tutorials undercuts the central claim that the warehouse aggregates the metric per
dimension.
**Suggested Fix:** In `README.md`, replace the output block with the aggregated two-row result
the tutorials show, and print one line per row rather than two.

---

## Scenario S2: Query parameters into filters, sorting and pagination, plus warehouse failures onto status codes

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst` → "Build queries" card → `howto-queries`.
2. `how-to/queries.rst`
   - Found: `.where()` with the `None`-is-a-no-op pattern written as a function taking
     `country: str | None`, which is exactly my handler shape; the `Order results` section
     (anchor `howto-ordering`, surviving the merge); a `SORTS` dict that maps a client's sort
     name to a prebuilt `OrderTerm` and raises `KeyError` on an unknown key -- the right
     answer to "the client chooses the sort"; `NullsOrdering`; and `.limit()`.
   - Found: a "There is no `.offset()`" note with keyset pagination as the recommended
     alternative.
   - Friction: the keyset sketch is one line on a dimension (`.where(Sales.country > last_seen)`).
     My real page is "revenue desc, tie-broken by country", where the cursor predicate is a
     compound comparison I have to derive myself. The "See also" card on
     `tutorials/shaping-a-report.rst` advertises "keyset pagination" as covered.
3. Followed `howto-filtering` for the operator set.
   - Found: every comparison operator, the named methods, `&`/`|`/`~`, the precedence warning,
     and -- unusually good -- "How filter values reach the warehouse", which tells me Snowflake
     and DuckDB bind and Databricks inlines through one audited escaper, so a value off the URL
     needs no escaping and only its *type* is mine to validate.
   - Friction: "Use custom lookups" reads as a supported extension point. I wrote the
     `RegexpMatch(Lookup[str])` subclass from the example and there is nothing that would make
     it compile to SQL: the "corresponding `case` branch in the SQL compiler" lives in
     Semolina's private `_compile_predicate()`, and the actual runtime result is
     `NotImplementedError: Unsupported lookup type: RegexpMatch. Add a case for it in
     _compile_predicate().` The page never says the branch is inside the library rather than
     in my code.
4. Followed `howto-web-api` for error mapping.
   - Found: `.execute()` re-raises the driver's exception unchanged; catch
     `adbc_driver_manager.Error`; a measured table showing a missing view arrives as
     `InternalError` on DuckDB with Snowflake/Databricks honestly marked "not yet measured";
     the pool-checkout failure raising `sqlalchemy.exc.TimeoutError` (not the builtin) as the
     one 503 that never reaches the driver; and "a missing view is not a 404, validate the
     view name yourself".
   - Success: I can write the 4xx/5xx map from this page alone.

### Gap Analysis

**Where:** `how-to/filtering.rst` > "Use custom lookups"
**What:** The section documents a `Lookup` subclass plus `.lookup()` as an extension point,
but a user-defined lookup has no registration hook: compilation falls through to the
catch-all in Semolina's own dialect compiler and raises `NotImplementedError`. The example as
printed cannot run from application code.
**Impact:** I need one filter the operator set does not cover (a regex or a date-truncation
predicate), follow this section, write the subclass, and discover at runtime that the missing
half is inside the installed package. That is a working-example failure (Rule 2) and an
internal detail surfacing as if it were public API.
**Suggested Fix:** In `how-to/filtering.rst`, "Use custom lookups": state plainly that a
custom lookup also needs a branch in Semolina's dialect compiler, which is not a public
extension point today, and show the exact `NotImplementedError` a reader will hit. If the
section is meant to advertise a supported extension, it needs the second half (how a
subclass reaches the compiler); if not, reduce it to a one-line "not user-extensible in this
release" note and point at the named methods and `.to_sql()`.

**Where:** `how-to/queries.rst` > "Limit result count" > "Take the top N" (note), advertised
from `tutorials/shaping-a-report.rst` > "See also" > "Order and limit results"
**What:** Keyset pagination is described in prose with a single-column example; there is no
worked example for the ordinary dashboard case of ordering by a metric with a dimension
tiebreak, where the cursor predicate is compound.
**Impact:** Paging a dashboard is a first-week task for this persona, and the one thing the
docs positively recommend is the one thing they do not show. I would build it by trial and
error against the warehouse.
**Suggested Fix:** In `how-to/queries.rst`, "Take the top N": add a short worked example --
`.order_by(Sales.revenue.desc(), Sales.country.asc()).limit(50)`, the values the handler
returns as the cursor, and the next-page `.where()` predicate that resumes from them --
noting which part the caller must pass back.

---

## Scenario S3: Async handlers on uvicorn -- lifespan, pool sizing, deadline, client disconnect

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` → tutorial 4 → `tutorials/dashboard-api.rst` §2, which
   tells me a plain `def` is deliberate under FastAPI and names `howto-web-api` for the
   `async def` form. That is the right hand-off: I am not left thinking sync is a
   simplification.
2. `how-to/web-api.rst`
   - Found: `create_async_engine` / `register_async_engine` / `unregister_async_engine` in a
     FastAPI lifespan with `await engine.dispose()`; `async with await query.aexecute()`;
     `AsyncEngine` explained as a distinct type with its own registry, and the `ValueError`
     I get if I register sync and read async.
   - Found: `howto-web-api-async-cursor-close` -- the async cursor has no finalizer, so a
     forgotten cursor holds its pooled connection for the life of the process. This is the
     single most useful warning on the page and it is stated as a requirement, not a
     suggestion.
   - Found: `asyncio.timeout()` → 504, with what the cancellation does downstream: the driver
     cancel fires from inside a shield, the warehouse statement is aborted rather than left
     billing, the connection is invalidated and replaced, checkout count returns to zero.
   - Found: the client-disconnect section, correctly starting from "Starlette does not race
     your handler against a disconnect watcher", then an anyio task-group implementation, then
     advice to prefer the simpler deadline.
3. `how-to/connection-pools.rst`
   - Found: pool sizing table with defaults, the sizing heuristic, and the statement I most
     needed -- the async pool's capacity limiter is `pool_size + max_overflow`, Semolina adds
     no second bound, and wrapping my own semaphore around `aexecute()` just lowers
     throughput. Also the `create_async_engine` is sync / `dispose()` is awaited asymmetry,
     with the reason.
4. `tutorials/installation.rst` → the `semolina[async]` extra, its `>=1.6.2` floor with the
   deadlock reason, and a separate import check because `import semolina` succeeds either way.
   I verified the extra names against the package metadata; `async`, `arrowmodel`, `pandas`,
   `polars`, `pyarrow`, `codegen-lint`, `all` are all real.
5. `how-to/typed-results.rst` → the async `.into()` / `iter_into()` forms, including that
   `iter_into()` is not awaited and that `contextlib.aclosing` is needed when the loop breaks
   early.

Everything in `done_when` is answered, with measurements rather than assurances. The only
friction is minor: the async snippets in `how-to/web-api.rst` all return `dict(row)` (flagged
by a note at the top of the page as "not what you should deploy"), so there is no single
complete async endpoint that returns a typed body -- I combine the lifespan from `web-api`
with the `await cursor.into(...)` form from `typed-results`. Two pages, both clearly
cross-linked; not enough to hold the goal up.

---

## Scenario S4: Understanding semantic views, `AGG` vs `MEASURE`, and the field mapping -- landing mid-set from a search engine

**Verdict:** PASS

### Navigation Path

1. Started at: `how-to/backends.rst` (simulating a search landing for "python databricks
   metric view"), not the front page.
   - Found: an opening paragraph that names which tutorial this page extends, a "Pick your
     backend" table that immediately puts `AGG()`, `MEASURE()` and `semantic_view()` side by
     side, and per-backend sections with real connection fields. I could tell within a screen
     what page I was on and what it assumed.
   - Friction (minor): the page tells me *how* to connect before telling me *what* a metric
     view is; the definition is behind a "See also" link at the bottom of a long page. I found
     it because the Explanation tab exists in the top nav.
2. Followed `explanation-semantic-views`.
   - Found: a semantic view defined against something I know (raw tables and everyone writing
     their own `SUM(revenue)`); per-warehouse implementations with links to Snowflake's and
     Databricks' own DDL docs; and "Why you cannot select from one like a table", which is the
     paragraph that made it click -- `revenue` is the recipe `SUM(s.revenue)`, so there is no
     column to read and each warehouse spells the "evaluate this here" operator differently.
   - Found: the three-row table (Snowflake `AGG("REVENUE")` / Databricks `MEASURE(\`revenue\`)`
     / DuckDB keyword lists) and the consequence I care about as an API author: the operator
     reaches the *result column names*.
3. Followed `howto-models` for the field mapping.
   - Found: the Metric / Dimension / Fact table with which builder method accepts each, why
     Databricks has no fact concept, and that Fact and Dimension generate identical SQL so the
     distinction is semantic.
4. Cross-checked the front page: the "New to semantic views?" card is the first card under "Go
   further", so a reader who *does* start at the top is routed here immediately.

Every `never_assume` item for this persona is covered explicitly -- semantic views, semantic
layer concepts, how the three warehouses differ, `AGG` vs `MEASURE`, and metrics-vs-columns --
and none of my assumed knowledge (Python, ORMs, descriptors, SQL, async) is over-explained.
The one weak point is orientation furniture rather than content: `explanation/index.rst` and
`reference/index.rst` are bare toctrees with no per-page abstracts, unlike `tutorials/index.rst`
and `how-to/index.rst`, so a reader who lands on the Explanation tab cannot tell that
"type-fidelity" answers "what Python type does my money column arrive as". Worth fixing, not
enough to hold up the goal.

---

## Scenario S5: Generate the model and the result DTO from Snowflake, use them in the endpoint and the tests, and check for drift in CI

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst` → tutorial 6 → `tutorials/warehouse-models.rst`.
   - Found: `semolina codegen` with per-backend tabs, why DuckDB takes `--database` instead of
     credentials, the generated model with types and `| None` on metrics (with the reason:
     an aggregate over an all-NULL group is NULL), redirecting stdout to `models.py`, and a
     `check_models.py` that proves the generated class queries identically.
   - Found: `semolina codegen-dto`, why a DTO comes from a query rather than a view, the
     `--view/--metrics/--dimensions` route, the generated file with `validation_alias` on each
     field, and the "a generated DTO belongs to one backend -- regenerate against the warehouse
     you deploy to" warning.
2. §4 "Use both": `reports.py` drops its hand-written model and DTO and imports the generated
   ones; the tutorial 5 test suite is re-run unchanged and shown passing.
   - This is accurate *on DuckDB*, because the generated aliases (`validation_alias="revenue"`,
     `validation_alias="country"`) happen to equal the field names. It stops being accurate the
     moment I do what the page told me to do and regenerate against Snowflake.
3. Followed `howto-codegen` for the detail.
   - Found: multi-view runs, the field-type mapping table, `TODO` annotations for GEOGRAPHY /
     ARRAY / STRUCT, the `# DECIMAL(10,2)` comments, `source=` for non-default casing, exit
     codes, and `howto-codegen-check` with the drift table, the `Route` column, and the honest
     "unverified on Databricks" and "false positive on Databricks VARIANT" warnings.
   - The repeated warning that codegen reads `[connections.snowflake]` while `create_engine`
     reads `[connections.default]` appears here, in `backends.rst`, in `reference/config.rst`
     and in `codegen-credentials.rst`. That is the trap I would otherwise have hit, and it is
     unmissable.
4. Followed `howto-dto-codegen` and `howto-codegen-credentials`.
   - Found: the three routes, the `[tool.semolina.dto]` `pyproject.toml` section with both
     entry shapes and path-resolution rules, `--output` semantics, and the full credential
     chain (TOML section → prefixed env vars → `.env`), including key-pair auth.

### Gap Analysis

**Where:** `tutorials/warehouse-models.rst` > §3 warning "A generated DTO belongs to one
backend" and §4 "Use both"; also `how-to/typed-results.rst` > "Which alias forms are supported"
**What:** Generated DTOs emit `pydantic.Field(validation_alias=...)` on every field and no
`model_config`, so instances can only be constructed with the warehouse's column spelling as
the keyword argument. On DuckDB the alias equals the field name and nothing shows; against
Snowflake the aliases become `COUNTRY` and `AGG("REVENUE")`, so
`RevenueByCountry(country="CA", revenue=2000)` -- the exact line tutorial 5 asks me to write
and tutorial 6 asks me to re-run -- raises `ValidationError`. The docs discuss
`populate_by_name` only in terms of *reading* a result, never in terms of constructing an
instance in a test or a fixture.
**Impact:** The chain's final promise is "your model, response class and test suite all come
from the warehouse". Following the very next instruction (regenerate against the warehouse you
deploy to) breaks the test suite the previous tutorial built, with an error that points at
Pydantic rather than at the alias, and no page tells me which knob to turn.
**Suggested Fix:** In `tutorials/warehouse-models.rst` §4 (or extend the §3 warning), add one
paragraph: a generated DTO reads its columns by alias, so once the aliases stop matching the
field names, tests that construct DTOs by keyword need `model_config =
pydantic.ConfigDict(populate_by_name=True)` on a hand-edited copy, or should assert on
`model_dump()` instead of constructing instances. Mirror it in `how-to/typed-results.rst`,
"Which alias forms are supported", where `populate_by_name` is already introduced.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario failed.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S1 | `tutorials/installation.rst` > all install sections | Nine unquoted `pip install semolina[...]` commands fail on zsh; one command on the same page and every other page quote them | Quote every extras spec: `pip install "semolina[snowflake]"`. Same in `README.md` |
| S1 | `tutorials/installation.rst` > "Install a backend extra" (final paragraph) | "Follow the tutorials without a warehouse" links to the pytest fixture how-to, but the chain uses the file-backed `tutorial.db` built in tutorial 2 | Point at `tutorial-first-query`; keep `howto-warehouse-testing` for the test-suite case |
| S1 | `README.md` > quick start output block | Shows three unaggregated rows for a metric grouped by country; the docs show `CA 2000 / US 1500` | Replace with the aggregated two-row output, one line per row |
| S2 | `how-to/filtering.rst` > "Use custom lookups" | The example cannot run: a user-defined `Lookup` has no registration hook and raises `NotImplementedError` from Semolina's private compiler | State that the compiler branch is inside Semolina and not user-extensible today (with the exact error), or supply the missing half |
| S2 | `how-to/queries.rst` > "Take the top N" note | Keyset pagination is recommended but only sketched on a single dimension; no example for the metric-ordered, tie-broken case a dashboard actually pages | Add a worked keyset example with the cursor values and the resuming `.where()` predicate |
| S5 | `tutorials/warehouse-models.rst` §3–§4; `how-to/typed-results.rst` > "Which alias forms are supported" | Generated DTOs carry `validation_alias` and no `populate_by_name`, so once you regenerate against Snowflake, tests that construct DTOs by field name raise `ValidationError`; undocumented | Note the constraint where the "one backend" warning already lives, with the `populate_by_name` remedy or an assert-on-`model_dump()` alternative |
| S4 (minor) | `explanation/index.rst`, `reference/index.rst` | Bare toctrees with no per-page abstracts, unlike `tutorials/index.rst` and `how-to/index.rst`; a mid-set landing on the Explanation tab cannot tell what each page answers | Add a one-sentence abstract per child, matching the other section indexes |
