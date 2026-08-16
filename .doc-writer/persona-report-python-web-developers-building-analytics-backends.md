# Persona Report

**Generated:** 2026-08-16
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 6 (reused from `.doc-writer/scenarios.yaml`; page set unchanged)
**Results:** 5 PASS, 1 PARTIAL, 0 FAIL

## Summary

These docs are unusually well suited to this persona. The single biggest risk for a
web developer — being dropped into semantic-layer vocabulary with no grounding — does
not happen: `explanation/semantic-views.rst` is reachable from a front-page card, and
it explains not just what a semantic view is but *why* `SELECT revenue FROM sales`
is meaningless, which is the exact conceptual gap an ORM-fluent reader arrives with.
The async surface added in v0.7 is documented to a standard I rarely see: extra,
minimum dependency pin, lifespan build/register/dispose, the sync/async registry
split, pool sizing as the concurrency bound, `asyncio.timeout()`, what
`adbc_cancel` does to the statement and to the pooled connection, and the
`ResourceWarning`-only failure mode of a forgotten async cursor. A FastAPI service
can be wired up from `how-to/web-api.rst` alone.

One thing is missing at the point where this persona will look for it. Nothing on
`how-to/filtering.rst` or `how-to/web-api.rst` says whether a filter value taken from
an HTTP query parameter is sent as a bound parameter or interpolated into SQL. The
web-api guide shows a raw `Query(default=None)` string flowing straight into
`.where(Sales.country == country)` — the exact pattern whose safety I need
confirmed before deploying. The only trace of an answer is an aside in
`explanation/type-fidelity.rst` ("Snowflake refuses the describe-only call when the
query carries bound parameters, which is the shape a `.where()` produces on that
backend"), which is not where anyone looks and does not cover the other two backends.

Secondary observation: every framework-lifecycle example is FastAPI. Half of this
persona is on Django, and "where does `create_engine()` go in a Django app" has no
answer anywhere.

---

## Scenario S1: Install with the Snowflake backend, configure `.semolina.toml`, define a model, execute a first query

**Verdict:** PASS

### Navigation Path

1. Started at `docs/src/index.rst`
   - Found: value proposition, a Quick example that already shows the whole shape
     (model, `register`/`create_engine`, fluent chain, `fetchall_rows()`), and a
     "Get started in 5 minutes" card.
   - Followed: the card → `tutorial-installation`.
2. `tutorials/installation.rst`
   - Found: `pip install semolina[snowflake]`, plus a clear map of every optional
     extra (`async`, `arrowmodel`, `pandas`, `polars`, `pyarrow`, `codegen-lint`)
     with a stated reason for each and the exception name raised if you call a method
     without its extra. The "Verify the installation" step is real (`__version__`,
     and a separate import check for the async stack).
   - Calibration: the "Use a virtual environment" tip is below this persona's level
     but sits inside a tab and costs nothing.
   - Followed: "Next steps" → `tutorial-first-query`.
3. `tutorials/first-query.rst`
   - Found: model definition, the warehouse-side DDL in a three-way tab-set (this is
     what makes the Python model legible to someone who has never written a
     `CREATE SEMANTIC VIEW`), engine registration, query, results.
   - Friction: the tutorial's runnable path is DuckDB. As a Snowflake reader, step 2
     tells me `create_engine("default")` "reads `.semolina.toml`" but never shows one.
     The link out is explicit and correctly labelled ("See `howto-backends-overview`
     for full connection details and TOML configuration"), so this is a detour rather
     than a break.
   - Followed: that link → `how-to/backends/overview.rst` → `howto-backends-snowflake`.
4. `how-to/backends/snowflake.rst`
   - Found: a complete `.semolina.toml` with a required/optional table for every
     field, the config-object alternative, the generated SQL, and — importantly — the
     warning that Snowflake returns `COUNTRY` and `AGG("REVENUE")`, so `row.revenue`
     raises `AttributeError` even though the tutorial's DuckDB example works.
   - Result: goal reached. I know exactly what to write and what my rows will be
     called.

Minor note, not a gap: the tutorial and the front-page Quick example both call
`.execute()` without a context manager, while README, `how-to/web-api.rst`, and
`how-to/typed-results.rst` all use `with`. For a reader who will be writing request
handlers, the `with` form is the habit worth showing first.

---

## Scenario S2: FastAPI endpoint with dynamic filters, ordering, pagination, an exception taxonomy, and JSON serialization

**Verdict:** PARTIAL

### Navigation Path

1. Started at `docs/src/index.rst` → hidden toctree → `how-to/index.rst`, where
   `web-api` is listed.
2. `how-to/web-api.rst`
   - Found, in order: engine at startup in a `lifespan` handler with
     `register`/`unregister`/`dispose`; a query endpoint; the warning that
     `dict(row)` puts `AGG("REVENUE")` into my response body and that the quoting
     survives into my clients; the typed-DTO alternative with
     `response_model=list[RevenueByCountry]`; conditional filters from
     `Query(default=None)` using `.where(... if ... else None)`; error handling.
   - The error-handling section is the standout. It states plainly that what reaches
     the handler is `adbc_driver_manager.Error` unwrapped, gives the DBAPI hierarchy,
     gives a *measured* table of which subclass each failure produces (with the
     Snowflake/Databricks column honestly marked "not yet measured"), separates
     `sqlalchemy.exc.TimeoutError` from the builtin `TimeoutError`, and explains why
     a missing view cannot be a 404. That is exactly the taxonomy I needed to map to
     status codes, and it does not pretend to know more than it does.
3. `how-to/queries.rst` (via "See also")
   - Found: the full builder, and an explicit note that there is **no `.offset()`**,
     with keyset pagination described as the substitute and a reason (the warehouse
     does not compute and discard skipped groups). Answering a missing feature with
     the technique that replaces it is the right call for a paged dashboard.
4. `how-to/serialization.rst`
   - Found: `json.dumps` fails on `Decimal`; a `default=` encoder for `Decimal` and
     `date`/`datetime`; the `str()` vs `float()` precision trade stated per field
     rather than globally; and the pointer that Pydantic removes the need entirely.
5. `how-to/ordering.rst` and `how-to/filtering.rst`
   - Found: everything a dynamic filter builder needs — operators, `.in_()`,
     `.between()`, `.isnull()`, `like`/`ilike`, `&`/`|`/`~`, the `&`-binds-tighter
     warning, and the `None`-as-no-op idiom repeated consistently.

### Gap Analysis

**Where:** `how-to/filtering.rst` (no section exists), and `how-to/web-api.rst` >
"Apply conditional filters from query parameters"

**What:** The docs never state how a filter value reaches the warehouse — bound
parameter, escaped literal, or interpolated text — and whether that differs by
backend. Every `WHERE` example on `how-to/filtering.rst` renders as a literal
(`WHERE "COUNTRY" = 'US'`), which reads as string interpolation whether or not it is.
`how-to/web-api.rst` then shows an untrusted `str` from `Query(default=None)` going
straight into `.where(Sales.country == country)` with no comment. The only statement
on the subject anywhere is a parenthetical in `explanation/type-fidelity.rst` >
"Asking the warehouse, or reading the catalogue": "Snowflake refuses the describe-only
call when the query carries bound parameters, which is the shape a `.where()`
produces on that backend." That tells me Snowflake binds; it says nothing about
Databricks or DuckDB, and it is on a page about aggregate return types.

**Impact:** Hinders rather than prevents. I can write the endpoint, but I cannot ship
it: an endpoint that interpolates a query-string value into warehouse SQL is a
resume-generating incident, and every ORM this persona has used (Django, SQLAlchemy)
states its position on this explicitly. The likely reaction is to stop and read the
source, or to hand-sanitize inputs that may already be safe.

**Suggested Fix:** In `how-to/filtering.rst`, add a short section (after "Use
comparison operators") stating what happens to a value passed to a predicate, per
backend — bound parameter vs. inlined literal, and what escaping applies where a
literal is inlined. Say plainly whether a value taken from an HTTP request is safe to
pass directly. State the one thing that is *not* value-safe (field and view names come
from your model, not from request data, so a caller cannot choose a column). Then add
one sentence with a `:ref:` to it in `how-to/web-api.rst` > "Apply conditional filters
from query parameters", since that is the page where the untrusted value first
appears. If Snowflake binds and another backend inlines, say so in the same table
style the docs already use for column names and driver exceptions — that per-backend
honesty is this documentation set's strongest habit and it is missing here.

**Secondary gap (same page, lower priority)**

**Where:** `how-to/web-api.rst`, whole page

**What:** Every lifecycle example is FastAPI-specific (`asynccontextmanager`
lifespan, `Query()`, `HTTPException`, Starlette's disconnect behaviour). Nothing says
where `create_engine()` and `register()` belong in a Django project, or what changes
under a synchronous WSGI worker model — notably that the pool is per process, so
`pool_size` multiplies by worker count against the warehouse's connection budget.

**Impact:** For the Django half of this persona the engine-lifecycle question is
unanswered. They can infer it (build in `AppConfig.ready()`, or a module import),
but pool-size-times-workers is the kind of thing you discover from Snowflake, not
from a doc.

**Suggested Fix:** In `how-to/web-api.rst`, add a short "Other frameworks" section
near "Set up the engine at application startup": one paragraph placing
`create_engine()`/`register()` in a Django `AppConfig.ready()`, and one sentence
noting that each worker process owns its own pool, so size `pool_size` against
warehouse capacity divided by worker count. It does not need a full Django example to
remove the blocker.

---

## Scenario S3: Deploy behind async handlers — async engine lifecycle, pool sizing, timeouts, cancellation

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` → `tutorials/installation.rst` > "Optional: async support"
   - Found: `semolina[async]`, the fact that a plain install carries none of it, why
     (`anyio` stays out of a base install; nothing imports until an async entry point
     is called), the `adbc-poolhouse[async]>=1.6.2` floor **with the reason** (earlier
     releases sized async pools wrongly and could deadlock on a cancelled query), and
     a verification command that actually distinguishes "installed" from "not"
     — `import semolina` succeeds either way, which the page says out loud.
2. `how-to/web-api.rst` > "Set up an async engine instead"
   - Found: `create_async_engine` + `register_async_engine` + `unregister_async_engine`
     + `await engine.dispose()` in a lifespan handler, and the explanation of the
     construction/teardown asymmetry (building a pool does no I/O; disposing closes
     driver resources).
3. Same page > "Serve a query from an async endpoint"
   - Found: `async with await query.aexecute() as cursor`, with the odd-looking
     `async with await` explained rather than left to be pattern-matched. Also the
     note that `cursor.description` and `.rowcount` stay synchronous, and that no
     asyncio/anyio import is needed on my side.
   - The `async with` **is required** warning is the highest-value paragraph on the
     page for a service that must not leak: the async cursor cannot have a finalizer
     because closing needs an await, so an unclosed one holds its pooled connection
     for the life of the process and only emits a `ResourceWarning`.
4. Same page > "Time out a slow query" and "Handle a client disconnect"
   - Found: `asyncio.timeout()` mapped to 504; which exception class surfaces
     (framework's, not the driver's) and why; that the statement is actually aborted
     in the warehouse via `adbc_cancel` from inside a shield, with the metered-billing
     consequence spelled out; that the aborted connection is invalidated and replaced
     so the next request is clean; that wrapping the whole `async with` is safe
     because teardown suppresses `Exception` not `BaseException`. The disconnect
     section correctly starts by saying Starlette does *not* cancel your handler, which
     is the assumption most people get wrong.
5. `how-to/connection-pools.rst` > "Size the pool"
   - Found: `pool_size`/`max_overflow`/`timeout`/`recycle` with defaults, that the
     same fields size async pools, and the direct statement that the pool **is** the
     concurrency bound (`pool_size + max_overflow` capacity limiter) with a warning
     that adding your own semaphore just lowers throughput. Also the sync/async
     registry separation and that `get_async_engine` never falls back to the sync
     store.
6. `how-to/streaming.rst` > "Cancel an async stream mid-iteration" — covers the
   long-lived streaming case and confirms the pool slot returns.

No gap. Everything in `done_when` is present, sourced, and dated where measured.

---

## Scenario S4: Understand semantic views, AGG vs MEASURE, and how Metric/Dimension/Fact map to the warehouse

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` — the "New to semantic views?" card is on the front page and
   names the exact confusion ("why `AGG()`, `MEASURE()` and `semantic_view()` are
   three spellings of the same idea"). Followed it.
2. `explanation/semantic-views.rst`
   - Found: what a semantic view is in one paragraph aimed at someone who knows
     ordinary views; per-warehouse implementation with links to Snowflake's and
     Databricks' own DDL docs; and the section that does the real work — "Why you
     cannot select from one like a table". `revenue` is the recipe `SUM(s.revenue)`,
     not a column, so `SELECT revenue FROM sales` means nothing. That is precisely
     the mental model an ORM-fluent reader is missing, and it is stated before the
     syntax table rather than after.
   - The three-row table (Snowflake `AGG("REVENUE")` / Databricks
     ``MEASURE(`revenue`)`` / DuckDB `metrics := [...]`) answers AGG-vs-MEASURE
     directly, and the observation that DuckDB changes the *shape* of the query while
     the other two change the select list is the detail that makes the dialect
     abstraction make sense.
   - Correctly hands off downstream: the same difference reaches the result column
     names, with a `:ref:` to `howto-result-column-names`.
3. `how-to/models.rst` (followed from "Where Semolina fits")
   - Found: the Metric/Dimension/Fact table with "Accepted by" columns, and — the
     part that matters for correctness — explicit per-warehouse notes that Snowflake
     has no `FACTS` clause and Databricks has no fact concept at all, so `Fact` is a
     semantic marker that compiles identically to `Dimension`. A reader could
     otherwise assume `Fact` changes the SQL.

No gap. The one thing I would have liked is a `:ref:` from `how-to/queries.rst`'s
"See also" back to `explanation-semantic-views`, since "Build queries" is also a
front-page card and a reader who enters there gets no route to the concept. Not
blocking — the front page carries both cards.

---

## Scenario S5: Generate model classes from existing Snowflake semantic views with the codegen CLI

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` → `how-to/index.rst` → `codegen`. (Also reachable from
   `tutorials/installation.rst` "See also" and from `explanation/semantic-views.rst`.)
2. `how-to/codegen.rst`
   - Found: exact command, multi-view invocation, `> models.py` with an explicit
     statement that there is no `--output` flag and that the ruff reminder goes to
     stderr so redirection captures only Python. Backend table naming the
     introspection statement each one runs.
   - The trap is called out loudly and repeatedly: codegen reads
     `[connections.snowflake]`, **not** `[connections.default]`, and a file with only
     `default` works for the app and exits `2` for codegen. That warning appears on
     this page, on `how-to/backends/snowflake.rst`, on
     `how-to/codegen-credentials.rst`, and in `reference/config.rst`. Repetition is
     right here — it is the failure everyone will hit once.
   - Generated output shown per backend against the source DDL, so I can see what
     each warehouse construct becomes. `TODO:` comments, the raw-type comment above
     concrete annotations, the `JsonValue` VARIANT case, and `source=` for
     non-default casing are all covered.
   - `--check` for CI drift, with a per-field table, a `Route` column that prevents a
     green check from silently meaning "I could not ask", exit code 5 kept distinct
     from 1, and two honest warnings: Databricks `--check` is unverified end to end,
     and it produces a false positive on every Databricks VARIANT column.
3. `how-to/codegen-credentials.rst`
   - Found: TOML per backend (including Snowflake key-pair auth), the full env-var
     table with a Required column, precedence order (TOML > env > `.env`),
     `SEMOLINA_ENV_FILE`, and troubleshooting keyed to exit codes 2 and 4.

No gap. Every item in `done_when` is answered without leaving these two pages.

---

## Scenario S6: Generate a result DTO with `semolina codegen-dto`, commit it, and return typed rows from a FastAPI endpoint

**Verdict:** PASS

### Navigation Path

1. `docs/src/index.rst` — "Typed results" card → `how-to/typed-results.rst`.
   (`how-to/web-api.rst` > "Return a typed response instead" also routes here, and
   that is how I first hit it in S2.)
2. `how-to/typed-results.rst`
   - Found: `pip install semolina[arrowmodel]` and the statement that this one extra
     is enough; `.into()` / `iter_into()` and both async twins; and
     `howto-result-column-names`, which is the section that decides whether any of
     this survives leaving DuckDB. The alias rules are given as a per-backend tab-set
     with `Field(validation_alias=...)`, including the non-obvious one — Snowflake
     folds to upper case *inside* the quotes, so `gross revenue` arrives as
     `AGG("GROSS REVENUE")`.
   - `validate=False` vs `validate=True` is explained as a real decision (structural
     check vs. Pydantic coercion), with a conversion table, the money-as-`float`
     warning, and the nullability asymmetry. The refused Pydantic alias constructs
     (`AliasChoices`, `AliasPath`, `alias_generator`) are listed with what to write
     instead, including the note that `alias_generator` leaves a DTO looking correct
     until it is used.
3. `how-to/dto-codegen.rst`
   - Found: all three generation routes (dotted path, `--view`, `pyproject.toml`),
     with a clear statement of which imports and which does not; the generated class
     with its provenance header; `--output` (directory must exist, written only after
     everything renders); `--check` for CI including the alias comparison that the
     model-level check cannot do; why every metric is `| None`; the `Any`/`TODO:`
     replacement rule and the fact that `--check` treats a hand-fixed `Any` as
     agreeing; and the plain statement that a DTO does not travel between warehouses.
   - The `src/` layout note (a dotted path resolves only once the project is
     installed) is the kind of detail that would otherwise cost an hour.
4. Back to `how-to/web-api.rst` > "Return a typed response instead"
   - Found: `response_model=list[RevenueByCountry]` with `cursor.into(...)`, and the
     explanation that the generated `validation_alias` is what makes my JSON say
     `revenue` instead of `AGG("REVENUE")`.

No gap. One small stumble worth noting: `how-to/dto-codegen.rst` refers twice to
`--backend dotted.path.ClassName` ("it is what `--backend dotted.path.ClassName` has
always done", and in the exit-code note) without that form ever being introduced on
the page — every example there uses `--backend snowflake` or `duckdb`. It is properly
documented in `reference/cli.rst` under `--backend`, which the page links in "See
also", so it resolves; it just reads as a forward reference to something I have not
been told about. A half-sentence gloss ("`--backend` also accepts a dotted path to a
custom engine class — see `reference-cli`") at the first mention would remove it.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario was blocked.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S2 | `how-to/filtering.rst` (no such section) | Nothing states whether a filter value is sent as a bound parameter or an inlined literal, or whether that differs by backend. All `WHERE` examples render as literals. The only mention anywhere is an aside in `explanation/type-fidelity.rst` about Snowflake's describe-only call. | Add a section after "Use comparison operators" stating, per backend, what happens to a value passed to a predicate (bound vs. inlined, and what escaping applies where inlined); state plainly whether a value from an HTTP request is safe to pass directly; note that field and view names come from the model, not from request data. Use the same per-backend table style already used for column names and driver exceptions. |
| S2 | `how-to/web-api.rst` > "Apply conditional filters from query parameters" | The page shows an untrusted `Query(default=None)` string flowing straight into `.where(Sales.country == country)` with no comment on value handling — the first place in the docs where request data reaches SQL. | Add one sentence with a `:ref:` to the new filtering section above, at the point the query parameter enters `.where()`. |
| S2 | `how-to/web-api.rst` > "Set up the engine at application startup" | Every lifecycle example is FastAPI. No guidance on where `create_engine()`/`register()` belong in a Django app, and no note that each worker process owns its own pool (so `pool_size` multiplies by worker count against warehouse capacity). | Add a short "Other frameworks" subsection: one paragraph placing the calls in a Django `AppConfig.ready()`, one sentence on per-process pools and sizing against worker count. |
| S6 | `how-to/dto-codegen.rst` > "Know what a dotted path imports" | `--backend dotted.path.ClassName` is cited twice as if already introduced; the page's own examples only ever use `snowflake`/`duckdb`. | At the first mention, add a half-sentence gloss: `--backend` also accepts a dotted path to a custom engine class, with a `:ref:` to `reference-cli`. |
| S4 (non-blocking) | `how-to/queries.rst` > "See also" | "Build queries" is a front-page card, so a reader can enter there without having met semantic views; the page's See also has no route to `explanation-semantic-views`. | Add `:ref:`explanation-semantic-views`` to the See also list. |
| S1 (non-blocking) | `docs/src/index.rst` "Quick example" and `tutorials/first-query.rst` steps 3–4 | Both call `.execute()` without a context manager, while README, `how-to/web-api.rst`, and `how-to/typed-results.rst` use `with`. For a reader who will write request handlers, the first example sets the habit. | Use `with ... .execute() as cursor:` in the front-page Quick example and in the tutorial's "Complete example", matching the README. |
