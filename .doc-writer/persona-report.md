# Persona Report

**Generated:** 2026-08-14
**Audience:** Python web developers building analytics backends (advanced)
**Scenarios tested:** 5
**Results:** 3 PASS, 1 PARTIAL, 1 FAIL

## Summary

For an advanced Python web developer this documentation is, on the whole, unusually
good: the install-to-first-query path is unbroken, the async/connection-pool story is
the most complete part of the whole set (lifecycle, sizing as the concurrency bound,
deadlines, cancellation semantics, client disconnect, the async-cursor close hazard),
and codegen is documented down to exit codes. The type-fidelity explanation is exactly
the page this persona needs and does not expect to get.

The one place it breaks is the place this persona lives: error handling in a web
endpoint. `how-to/web-api.rst` teaches a `try/except SemolinaConnectionError /
SemolinaViewNotFoundError` pattern around `.execute()` and maps those to 503 and 404.
Checking that claim against the source shows both exceptions are raised only by
`Engine.introspect()` (the codegen path); `Engine.execute()` and `AsyncEngine.aexecute()`
propagate the driver's exception unchanged. A reader who follows this guide ships an
endpoint whose `except` clauses never fire — a missing view returns 500, not 404 — and
the docs offer no alternative taxonomy to map warehouse failures onto status codes.

Two smaller cross-page inconsistencies bite the same persona: `how-to/serialization.rst`
shows `json.dumps(dict(row))` working, while `explanation/type-fidelity.rst` states that
money arrives as a `Decimal` and `json.dumps` has no encoder for it — and serialization
does not link to type-fidelity. And `how-to/models.rst` recommends `revenue = Metric[float]()`
while codegen, `--check`, and `.into()` all insist a decimal metric is
`Metric[decimal.Decimal | None]()`.

---

## Scenario S1: Install with the Snowflake backend, configure `.semolina.toml`, define a model, execute a first query

**Verdict:** PASS — unbroken path from `pip install` to printed rows; only friction is that the tutorial never links to the page explaining what a semantic view is.

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: one-line pitch, a "Quick example" that shows model, `create_engine`/`register`, query, `fetchall_rows()`, and a card grid.
   - Followed: "Get started in 5 minutes" -> `tutorials/installation`.
2. `tutorials/installation.rst`
   - Found: Python 3.11 prerequisite, pip/uv tab-set, `semolina[snowflake]` extra, the `async` extra with its `adbc-poolhouse[async]>=1.6.2` floor, the four result extras, and two verification commands (`import semolina; print(semolina.__version__)` -> `0.6.0`, matching `pyproject.toml`, and an async import check).
   - Followed: "Next steps" -> `tutorials/first-query`.
3. `tutorials/first-query.rst`
   - Found: model definition, the warehouse-side DDL for both Snowflake and Databricks in a synced tab-set, `register("default", create_engine("default"))`, query, `fetchall_rows()`, expected output, and a complete runnable DuckDB variant so I can finish the tutorial with no warehouse at all.
   - Friction: step 2 says the TOML `type` field decides the backend but shows no TOML; it links out for the actual fields.
   - Followed: `:ref:howto-backends-overview`.
4. `how-to/backends/overview.rst` -> `how-to/backends/snowflake.rst`
   - Found: complete `.semolina.toml` block plus a field table with required/optional marked, the note that `database`/`warehouse` are optional for querying but required for codegen, a pointer to the shared pool fields, and the `register(...)` call.
   - Goal reached: I can go from nothing to a printed row.

### Gap Analysis

**Where:** `docs/src/index.rst` (card grid) and `docs/src/tutorials/first-query.rst` ("See also")
**What:** Neither the landing page nor the tutorial links to `explanation/semantic-views`, even though "semantic view" is used from the first sentence and is on this persona's never-assume list. The concept page is reachable only from the top-nav Explanation tab or the backends overview's See-also.
**Impact:** Friction only — the tutorial shows the warehouse DDL, so the reader infers enough to proceed. But the reader most likely to need the concept is the one following the shortest path, which never offers it.
**Suggested Fix:** In `docs/src/index.rst`, add a fifth grid card ("New to semantic views?" -> `explanation-semantic-views`); in `docs/src/tutorials/first-query.rst`, add `:ref:explanation-semantic-views` as the first "See also" card.

---

## Scenario S2: FastAPI endpoint with dynamic filters, ordering, limit, JSON, and warehouse failures mapped to HTTP status codes

**Verdict:** FAIL — the documented exception-handling pattern catches exceptions that `.execute()`/`.aexecute()` never raise, so the 404/503 mapping the guide teaches does not work.

### Navigation Path

1. Started at: `docs/src/index.rst` -> "Build queries" card -> `how-to/queries.rst`.
   - Found: `.metrics()`, `.dimensions()`, `.where()`, `.order_by()`, `.limit()`, `.using()`, `.to_sql()`, immutability and forking, fetch-method inventory. Generated SQL shown per dialect throughout.
   - Followed: See-also -> `how-to/filtering.rst` (full operator table, named lookups, `&`/`|`/`~`, the `None`-as-no-op idiom, and a precedence warning) and -> `how-to/serialization.rst`.
2. `how-to/index.rst` -> `how-to/web-api.rst`
   - Found: lifespan-based engine setup, a query endpoint, conditional filters from `Query(default=None)` params with the `None` no-op, cursor-as-context-manager, `.using()` per endpoint. This is a genuinely complete endpoint pattern.
   - Found: "Handle errors" section -> `except SemolinaConnectionError: 503` / `except SemolinaViewNotFoundError: 404`, with prose stating "Both apply to `aexecute()` as well; wrap it in the same `try` block."
3. Checked the claim (source read, allowed only for verification): `Engine.execute()` in `semolina/engines/base.py` and `AsyncEngine.aexecute()` in `semolina/engines/abase.py` catch `BaseException` solely to return the connection to the pool and then `raise` unchanged. `SemolinaViewNotFoundError` and `SemolinaConnectionError` are raised only inside `introspect()` in `engines/snowflake.py`, `engines/databricks.py`, and `engines/duckdb.py`. `Engine.execute()`'s own docstring says: "Raises: Exception: For backend execution errors (connection failures, SQL errors) surfaced by the underlying ADBC driver."
4. Looked for an alternative taxonomy: `reference/index.rst` lists config, CLI, and the autoapi tree only. No page documents what `.execute()` can raise, and `semolina/exceptions.py` states in its module docstring that there is deliberately no common `SemolinaError` base class — a fact a backend developer needs and which appears nowhere in the how-to or explanation sections.
5. Returned to `how-to/serialization.rst` for the JSON step.
   - Found: `dict(row)`, `json.dumps(dict(row))` -> `'{"revenue": 1000, "country": "US"}'`, `[dict(row) for row in rows]`, batched `fetchmany_rows`.
   - Conflict: `explanation/type-fidelity.rst` states a money column arrives as `decimal.Decimal` and that "`json.dumps` has no encoder for `Decimal`. Convert at the boundary." `serialization.rst` neither says this nor links to the page that does.
6. Looked for pagination: `how-to/ordering.rst` and `how-to/queries.rst` document `.limit(n)` only. No `.offset()` exists on `_Query`, and no page says so or offers a keyset/limit-based alternative.

### Gap Analysis

**Where:** `docs/src/how-to/web-api.rst` > "Handle errors"
**What:** The guide's central error-handling example wraps `query.execute()` in `except SemolinaConnectionError` / `except SemolinaViewNotFoundError`, and asserts both apply to `aexecute()`. Neither exception is raised on the query-execution path; both are raised only by `Engine.introspect()`, which is the codegen path. Driver exceptions (`ProgrammingError`, `OperationalError`, and adbc-poolhouse's `ConnectionBusyError`) reach the handler unwrapped.
**Impact:** Blocks the goal. This persona's stated need is mapping warehouse failures onto HTTP status codes; the only documented mechanism is inert. A missing or renamed view returns 500 instead of 404, an auth failure returns 500 instead of 503, and nothing in the docs would tell the developer this before production. The docs also never state that there is no common `SemolinaError` base to catch, so there is no documented fallback.
**Suggested Fix:** Either (a) correct the section to document what `.execute()`/`.aexecute()` actually raise — driver-level exceptions passing through unwrapped, no common Semolina base class, with a concrete `except Exception -> 500` plus driver-specific narrowing for 404/503 — or (b) if wrapping execute-path errors into `SemolinaConnectionError`/`SemolinaViewNotFoundError` is the intended behaviour, treat this as a library gap and note the current behaviour until it lands. Either way, add a short exception-taxonomy table to the page (or to `reference/`) listing what each documented exception is raised by: `SemolinaViewNotFoundError`/`SemolinaConnectionError` (introspection/codegen), `SemolinaSchemaMismatchError` (`into()`/`iter_into()`), `SemolinaMissingDependencyError` (missing extra), `ConnectionBusyError` (concurrent use of one connection), and driver exceptions (query execution).

**Where:** `docs/src/how-to/serialization.rst` > "Convert a Row to JSON"
**What:** `json.dumps(dict(row))` is shown succeeding on a revenue metric. Per `explanation/type-fidelity.rst`, a decimal metric arrives as `decimal.Decimal`, which `json.dumps` cannot encode. The page has no warning and its "See also" does not link to `explanation-type-fidelity`.
**Impact:** Hinders the goal. The developer copies the pattern, it works against the DuckDB tutorial database (integer revenue) and raises `TypeError` against the real warehouse.
**Suggested Fix:** In `docs/src/how-to/serialization.rst`, add a warning under "Convert a Row to JSON" showing the `Decimal` case and the boundary conversion (`float(row.revenue)` for charts, or FastAPI's own encoder / a `default=` hook), and add `:ref:explanation-type-fidelity` and `:ref:howto-typed-results` to the See-also.

**Where:** `docs/src/how-to/queries.rst` > "Limit result count", `docs/src/how-to/ordering.rst` > "Limit the result count", `docs/src/how-to/web-api.rst`
**What:** No page addresses pagination. `.limit()` is documented; there is no `.offset()` in the API and no page says so or suggests an approach for page 2 of a dashboard table.
**Impact:** Hinders the goal. A determined developer concludes limit-only and paginates in application code, but spends time looking for an offset that does not exist.
**Suggested Fix:** In `docs/src/how-to/ordering.rst`, add a short "Paginate a result set" section stating that Semolina exposes `.limit()` and no `.offset()`, and showing the recommended pattern (deterministic `.order_by()` plus a keyset filter via `.where()`, or fetch-and-slice for small results). Cross-link it from `docs/src/how-to/web-api.rst`.

---

## Scenario S3: Deploy behind async FastAPI — async engine lifecycle, pool sizing, timeouts, cancellation

**Verdict:** PASS — the most complete part of the docs; only the pool-checkout timeout exception is left unnamed.

### Navigation Path

1. `tutorials/installation.rst` > "Optional: async support"
   - Found: `semolina[async]` extra, the `adbc-poolhouse[async]>=1.6.2` floor with the reason (earlier releases sized async pools wrongly and could deadlock on cancel), the combined `semolina[snowflake,async]` install, and an import check that distinguishes "extra missing" from "package missing" — because `import semolina` succeeds either way.
2. `how-to/web-api.rst` > "Set up an async engine instead"
   - Found: a full `asynccontextmanager` lifespan with `create_async_engine` / `register_async_engine` / `unregister_async_engine` / `await engine.dispose()`, and an explanation of why construction is sync and teardown is awaited.
   - Found: `async with await query.aexecute()` and awaited fetch methods; explicit statement that `description`/`rowcount` stay synchronous; explicit statement that the code is loop-agnostic (asyncio or Trio, nothing to configure).
   - Found: the `ConnectionBusyError` failure mode with the correct remedy (a separate `aexecute()` per task, not a lock) and why a lock would be worse.
   - Found: a `warning` making `async with` mandatory rather than advisory, because the async cursor has no finalizer and a forgotten one holds its pooled connection for the life of the process.
   - Found: "Time out a slow query" (`asyncio.timeout` -> 504, `anyio.fail_after` alternative, what exception you actually catch, the driver-level `adbc_cancel`, and the fact that the invalidated connection is replaced and the checkout count returns to zero) and "Handle a client disconnect" (Starlette does not cancel for you; a task-group watcher pattern; when to prefer a plain deadline).
3. `how-to/connection-pools.rst`
   - Found: direct-engine vs named-registry patterns with the SQLAlchemy/Django analogies this persona will recognise, `pool_size`/`max_overflow`/`timeout`/`recycle` in both config-object and TOML form with a defaults table, the DuckDB `:memory:` `pool_size=1` constraint, and the key sentence for capacity planning: the async pool's capacity limiter is `pool_size + max_overflow` and Semolina adds no second bound, so wrapping your own semaphore only lowers throughput.
   - Found: the two registries are separate stores; a name registered with `register()` is invisible to `aexecute()` and raises with a message naming the async registration function.
4. `how-to/streaming.rst`
   - Found: `async for row in cursor`, where the work happens (batch pulled on a worker thread, row mapping on the loop thread), and mid-iteration cancellation semantics including ordered teardown that cannot mask the cancellation.
   - Goal reached: I could deploy this.

### Gap Analysis

**Where:** `docs/src/how-to/connection-pools.rst` > "Size the pool" and `docs/src/reference/config.rst` > "Common fields"
**What:** `timeout` is described as "Seconds to wait for a connection before raising an error" / "before raising" — the exception class is never named. Under load, pool-checkout exhaustion is the most likely production failure for this persona, and it is the one they most want to map to a 503.
**Impact:** Minor friction on an otherwise complete page; it compounds the S2 gap, since there is no way to write the `except` clause for it.
**Suggested Fix:** In `docs/src/how-to/connection-pools.rst`, section "Size the pool", name the exception raised when a checkout exceeds `timeout` (and whether it differs on the async pool), and cross-link it from the error-handling section of `docs/src/how-to/web-api.rst`.

---

## Scenario S4: Understand semantic views, and how Metric/Dimension/Fact map to the warehouse — including AGG vs MEASURE

**Verdict:** PARTIAL — the concept page is good but unreachable from the landing page or tutorial, and AGG vs MEASURE is exhibited everywhere and explained nowhere.

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: four cards — Get started, Define models, Build queries, API reference. None points at Explanation. The term "semantic layer" appears in the first line with no definition and no link.
   - Type-alignment friction: arriving in study mode ("what is this thing?"), every offered route is a how-to or a tutorial that assumes the concept.
   - Followed: the top-nav Explanation tab (the only route) -> `explanation/index.rst` -> `explanation/semantic-views.rst`.
2. `explanation/semantic-views.rst`
   - Found: a clear definition (a governed object over raw tables holding metric/dimension definitions once), how each of Snowflake, Databricks, and DuckDB implements it with links to the vendor DDL docs, the DuckDB `semantic_view()` table-function difference, and "Where Semolina fits" (models mirror, do not replace, warehouse definitions).
   - Not found: any explanation of `AGG()` vs `MEASURE()`. The page names neither.
3. `how-to/models.rst`
   - Found: the role table (Metric -> `.metrics()`, Dimension/Fact -> `.dimensions()`), per-warehouse SQL for each field type, an honest treatment of `Fact` (Snowflake has no FACTS clause; Databricks has no fact concept; at query time Fact and Dimension are identical SQL and the distinction is semantic), identifier folding rules, and immutability.
   - Found: AGG/MEASURE appear only inside SQL tab-sets, as output. `backends/snowflake.rst` says "Snowflake SQL uses `AGG()` for metrics"; `backends/databricks.rst` says "Databricks SQL uses `MEASURE()`". Neither says what those functions do, why the semantic layer needs an aggregation wrapper at all, or why the two vendors spell it differently.
   - Contradiction spotted: this page recommends `revenue = Metric[float]()`, while `how-to/codegen.rst`, `explanation/type-fidelity.rst`, and `how-to/typed-results.rst` all say a decimal metric is `decimal.Decimal | None`.
4. `explanation/type-fidelity.rst`
   - Found: the deepest and most useful content for this persona — a metric is an expression, not a typed column; catalogue vs result-schema disagreement with measured examples; why money is a `Decimal`; what can be NULL and why generated metric annotations admit `None`.

### Gap Analysis

**Where:** `docs/src/index.rst` (card grid); `docs/src/explanation/semantic-views.rst`
**What:** Two related problems. (1) There is no route from the landing page to the Explanation section, so the reader who has never met a semantic view is offered only how-tos. (2) `AGG()` vs `MEASURE()` — an explicit never-assume item for this persona — is shown in a dozen SQL tab-sets but never explained; the reader learns the two spellings without learning what either means or why querying a metric requires the wrapper.
**Impact:** Hinders rather than blocks. A determined reader finds the Explanation tab and the concept page is genuinely good, but they finish able to write correct code without understanding why a metric must be wrapped, which is exactly the understanding that prevents semantic-layer misuse later.
**Suggested Fix:** In `docs/src/index.rst`, add a grid card linking to `explanation-semantic-views`. In `docs/src/explanation/semantic-views.rst`, add a section "Why a metric is wrapped: AGG and MEASURE" explaining that a metric is a stored aggregation expression rather than a column, that querying it means asking the view to evaluate that expression (`AGG()` on Snowflake, `MEASURE()` on Databricks, the `metrics :=` argument on DuckDB), and that this is why Semolina refuses a `Metric` in `.dimensions()`. Cross-link it from `docs/src/how-to/models.rst` > "Choose field types".

**Where:** `docs/src/how-to/models.rst` > "Create a model" and "Type the subscript"
**What:** Uses `revenue = Metric[float]()` and `unit_price = Fact[float]()` as the canonical examples, while `explanation/type-fidelity.rst` and `how-to/codegen.rst` state a decimal metric annotates `decimal.Decimal | None`. The page also never mentions that metrics can be NULL.
**Impact:** A hand-written model following this page disagrees with `semolina codegen --check` (reported as drift) and fails `.into()`'s schema check. The reader has no way to know which page to believe.
**Suggested Fix:** In `docs/src/how-to/models.rst`, change the money examples to `Metric[decimal.Decimal | None]()`, add one sentence on why metrics admit `None`, and link `:ref:explanation-type-fidelity` from that section rather than only from the codegen pages.

---

## Scenario S5: Generate model classes from existing Snowflake semantic views with the codegen CLI

**Verdict:** PASS — command, credentials, output, edge cases, drift check, and exit codes are all documented.

### Navigation Path

1. Started at: `docs/src/index.rst`. No card mentions codegen; followed the How-To Guides tab -> `how-to/index.rst`, a flat list of seventeen titles with no abstracts. "codegen" is recognisable, so I found it, but the index gave me nothing to choose on.
2. `how-to/codegen.rst`
   - Found: the exact command (`semolina codegen my_schema.sales_view --backend snowflake`), multiple views in one call, `> models.py` with the explicit note that there is no `--output` flag and that the unformatted-source reminder goes to stderr so redirection stays clean, the `codegen-lint` extra, and the `--backend` table naming the introspection statement per warehouse.
   - Found: a Snowflake tab showing the source DDL and the exact generated class, including the `# {"type": "FIXED", "scale": 0}` type comment; the field-type mapping table; why only metrics admit `None`; TODO comments for GEOGRAPHY/ARRAY/MAP/STRUCT; `JsonValue` for VARIANT with the warning not to reuse it as a Pydantic DTO annotation; `source=` for non-default casing.
   - Found: `--check` for drift with a worked table, the `Route` column semantics, `Detail` lines for role/column drift, and the honest warning that `--check` is unverified on Databricks.
   - Found: exit codes 0–5 with distinct meanings, plus the caveat that argparse also emits 2.
   - Followed: `:ref:howto-codegen-credentials`.
3. `how-to/codegen-credentials.rst`
   - Found: TOML sections per backend, the precedence order (TOML > env > `.env`), full `SNOWFLAKE_*` table with required/optional, key-pair auth, `SEMOLINA_ENV_FILE`, and troubleshooting keyed to exit codes 2 and 4.
   - Friction: codegen reads `[connections.snowflake]` while my application engine reads `[connections.default]` — stated plainly, but it means the "configure once, both use it" opening sentence is only true if I name my application section after the backend.
   - Goal reached.

### Gap Analysis

**Where:** `docs/src/how-to/index.rst`
**What:** Seventeen child pages listed as a bare toctree with no one-line abstracts, contrary to the project's own navigation convention. Codegen, web-api, typed-results, and streaming are all discoverable only by guessing from the title.
**Impact:** Minor friction; it did not block the goal but it is the weakest link in the navigation for every scenario that starts from the landing page.
**Suggested Fix:** In `docs/src/how-to/index.rst`, replace the bare toctree listing with a `grid`/`grid-item-card` layout (or a definition list) giving each page a one-sentence abstract, grouped as Connect / Model / Query / Results / Generate.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S2 | `how-to/web-api.rst` > "Handle errors" | Documents catching `SemolinaConnectionError` / `SemolinaViewNotFoundError` around `.execute()` and `.aexecute()` and maps them to 503/404. Both are raised only by `Engine.introspect()`; the execute path propagates driver exceptions unchanged, so the documented handler never fires. No alternative taxonomy is documented, and the deliberate absence of a common `SemolinaError` base is stated only in a module docstring. | Rewrite the section to describe what the execute path actually raises (driver exceptions, unwrapped; no common base class), give a working status-code mapping, and add an exception-taxonomy table naming which call site raises each Semolina exception. |

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S2 | `how-to/serialization.rst` > "Convert a Row to JSON" | `json.dumps(dict(row))` is shown succeeding; a decimal metric arrives as `Decimal`, which `json.dumps` cannot encode. No warning, no link to `type-fidelity`. | Add a warning showing the `Decimal` case and the boundary conversion; add `:ref:explanation-type-fidelity` and `:ref:howto-typed-results` to See-also. |
| S2 | `how-to/ordering.rst`, `how-to/queries.rst`, `how-to/web-api.rst` | Pagination is never addressed; `.limit()` exists, `.offset()` does not, and no page says so. | Add a "Paginate a result set" section to `how-to/ordering.rst` stating there is no `.offset()` and showing the keyset pattern via `.order_by()` + `.where()`; cross-link from `how-to/web-api.rst`. |
| S3 | `how-to/connection-pools.rst` > "Size the pool"; `reference/config.rst` > "Common fields" | The exception raised when a pool checkout exceeds `timeout` is never named, so it cannot be caught and mapped to a 503. | Name the exception (and any async difference) and cross-link from the web-api error-handling section. |
| S4 | `index.rst`; `explanation/semantic-views.rst` | No route from the landing page to Explanation; `AGG()` vs `MEASURE()` is shown in SQL tab-sets throughout but never explained, despite being a never-assume item for this persona. | Add a landing-page card linking to `explanation-semantic-views`; add a "Why a metric is wrapped: AGG and MEASURE" section to that page and cross-link it from `how-to/models.rst`. |
| S4 | `how-to/models.rst` > "Create a model" / "Type the subscript" | Recommends `Metric[float]()` for money and never mentions metric nullability, contradicting `codegen.rst`, `type-fidelity.rst`, and `typed-results.rst`, which all use `Metric[decimal.Decimal \| None]()`. | Change the money examples to `Metric[decimal.Decimal \| None]()`, explain metric nullability in one sentence, and link `explanation-type-fidelity`. |
| S1 | `tutorials/first-query.rst` > "See also" | The tutorial introduces "semantic view" without linking to the page that defines it. | Add `:ref:explanation-semantic-views` as the first See-also card. |
| S5 | `how-to/index.rst` | Seventeen child pages listed with no abstracts, against the project's own navigation convention. | Replace with a card grid or definition list carrying a one-sentence abstract per page, grouped by task. |

### Other observations (not scenario-blocking)

- `docs/src/index.rst` "Quick example" omits the cursor context manager that `README.md` and `how-to/web-api.rst` both present as the correct pattern. The landing page teaches the leakier form first.
- `docs/src/how-to/filtering.rst` > "Use custom lookups" tells the reader to subclass `Lookup`, then states that custom lookups "require a corresponding `case` branch in the SQL compiler" — which the reader cannot add. As written the section is a dead end; either document the extension point or say plainly that it is not currently user-extensible.
- `docs/src/how-to/warehouse-testing.rst` reaches into `engine._pool` and imports `sqlalchemy.event` in its fixture. The private attribute conflicts with the warning in `how-to/connection-pools.rst` not to reach into `engine._pool`, and SQLAlchemy is not documented as a dependency or extra anywhere in the install page.
