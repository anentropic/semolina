# Persona Report

**Generated:** 2026-08-16
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 6 (reused from `.doc-writer/scenarios.yaml`, unchanged page set)
**Results:** 3 PASS, 3 PARTIAL, 0 FAIL

## Summary

The codegen surface — which is the part of Semolina I actually own — is now in very good shape.
Every gap I raised against `codegen-dto` in the previous pass has been closed: the `--view` route
no longer claims to replace the model class at runtime and has a "You still need a model to run the
query" subsection with working code, the `arrowmodel` extra is named in the page's first paragraph,
the query-builder reserved names are enumerated in both `reference/cli.rst` and
`how-to/dto-codegen.rst`, and `codegen-dto --check` now exists and is documented, which closes the
CI story `pyproject.toml` declaration started. S3 moves PARTIAL → PASS on that basis.

The two remaining weaknesses are both on this persona's never-assume list, and both are on pages
that are otherwise excellent. `tutorials/installation.rst` has grown into a page that discusses
extras, version floors, pins and lazy dependency resolution in reference-grade detail — for a
reader who is explicitly not assumed to know what an extra is — and its `pip install
semolina[snowflake]` lines are unquoted, which fails outright in zsh. `how-to/web-api.rst` gives me
complete, deployable endpoint code and then never tells me how to get a FastAPI application
running in the first place, so I can read every line of it and still not have a server.

Note on verdict changes: S1 and S5 move PASS → PARTIAL. Neither is a regression caused by a doc
change — both pages improved this pass. They are re-classifications from a stricter reading of the
persona's `never_assume` list ("Python packaging (extras, optional deps)" and "web framework
patterns / how to structure query endpoints"). The fixes are small and additive in both cases.

---

## Scenario S1: Configure `.semolina.toml` and connect to Snowflake with `create_engine()`

**Verdict:** PARTIAL (previous pass: PASS — re-classified, see gap 1)

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: the "Get started in 5 minutes" card and a quick example whose engine setup is the
     two lines I need: `register("default", create_engine("default"))  # reads .semolina.toml`.
   - Friction: the quick example's last line is `print(row.country, row.revenue)`. Every other
     page in the docs that shows attribute access carries a warning that `row.revenue` raises
     `AttributeError` on Snowflake. The front page does not, and I own a Snowflake warehouse.
   - Followed: the card to `tutorial-installation`.
2. Navigated to: `docs/src/tutorials/installation.rst`
   - Found: `pip install semolina[snowflake]` in a per-backend tab set, and a verification
     command with expected output. The DuckDB escape hatch for readers without warehouse access
     is signposted.
   - Friction: my first command is `pip install semolina[snowflake]`, unquoted. On zsh (the
     macOS default) that is `zsh: no matches found: semolina[snowflake]`. The `uv` line on the
     very next line *is* quoted, and the async section further down writes
     `pip install "semolina[snowflake,async]"` quoted, so the page contradicts itself.
   - Friction: "Optional: dataframes and typed results" runs ~55 lines on which extra pulls
     which transitive dependency, why `polars` does not bring `pyarrow`, and "Each extra sets a
     minimum version rather than a pin, so a later compatible release can land in your
     environment". I am told never to be assumed to know extras or optional deps; this section
     is written for someone who already reasons about dependency resolution. Type-alignment: I
     am in study mode on a tutorial and this reads as reference material.
   - Followed: "Next steps" to `tutorial-first-query`.
3. Navigated to: `docs/src/tutorials/first-query.rst`
   - Found: step 2 "Register an engine", the statement that `create_engine("default")` reads
     `[connections.default]` and that `type` there picks the warehouse. Correct pointer onward.
   - Followed: "See :ref:`howto-backends-overview` for full connection details".
4. Navigated to: `docs/src/how-to/backends/overview.rst`, then `backends/snowflake.rst`
   - Found: a complete, copyable `.semolina.toml` block and a Field/Type/Required/Description
     table. The note separating what the query engine needs (`database` and `warehouse`
     optional) from what `semolina codegen` needs (both required) is exactly the asymmetry I
     would otherwise have found by failing.
   - Found: the note that `semolina codegen --backend snowflake` reads
     `[connections.snowflake]` rather than `[connections.default]` and exits `2` otherwise. This
     trap is now stated in four places (`backends/snowflake`, `reference/config`, `how-to/codegen`,
     `how-to/codegen-credentials`), which is the right amount of repetition for a silent exit 2.
   - Friction: `backends/overview.rst` > "Query with a registered engine" repeats the
     `row.country, row.revenue` snippet with no column-naming warning, same as the front page.
5. Navigated to: `docs/src/reference/config.rst` (via "See also")
   - Found: `config_path=` for a non-default file location, the full Snowflake field list
     including key-pair and OAuth auth, `pre_ping`, and a table stating which caller reads which
     section. Every question in `done_when` is answered here.

The core of this goal — the TOML file, section selection, `register()` — is fully and precisely
documented, and I would get connected. The friction is entirely on the install step in front of it.

### Gap Analysis

**Where:** `docs/src/tutorials/installation.rst` > "Install a backend extra", "Optional: async
support", "Optional: dataframes and typed results"
**What:** Two problems on one page. (a) The bracket syntax is never explained — "extra", "pin",
"minimum version rather than a pin", "the `all` extra", "the async stack is resolved lazily" are
all used as known vocabulary, and Python packaging is on this persona's never-assume list. (b) The
`pip` invocations are inconsistently quoted: `pip install semolina[snowflake]` and
`pip install semolina[pandas]` are bare, while `pip install "semolina[snowflake,async]"` and
`pip install "semolina[duckdb]"` (in `warehouse-testing.rst`) are quoted. The bare form fails under
zsh, which is the default shell on macOS.
**Impact:** The unquoted command is a hard stop on the reader's literal first action, with an error
message ("no matches found") that says nothing about quoting. The vocabulary problem is softer —
the commands are copy-pasteable — but it means the reader cannot decide *which* extras they need
without guessing, and the result-extras section is where they have to make that decision.
**Suggested Fix:** In `tutorials/installation.rst`, section "Install a backend extra": quote every
`pip install "semolina[...]"` on the page for consistency with the `uv` lines and the async
section, and add one sentence before the tab set defining the syntax — something like "The name in
brackets is an *extra*: an optional dependency group Semolina declares, installed only when you ask
for it by name. Quote the whole argument, because some shells treat brackets as a filename
pattern." That single sentence covers both problems and serves the async and result-extras sections
too.

**Where:** `docs/src/index.rst` > "Quick example", and `docs/src/how-to/backends/overview.rst` >
"Query with a registered engine"
**What:** Both show `print(row.country, row.revenue)` with no column-naming caveat. The identical
warning admonition ("Column keys are whatever your warehouse called them") appears on
`first-query`, `queries`, `serialization`, `web-api` and `backends/snowflake` — these two pages are
the exceptions, and one of them is the first code any reader sees.
**Impact:** For a Snowflake or Databricks owner, the front-page example is code that raises
`AttributeError` on their warehouse. It is recoverable, and the warning is reached later on almost
any onward path, but the docs have a consistent convention here and these two pages break it.
**Suggested Fix:** In `index.rst` > "Quick example", add one line after the example pointing at
:ref:`howto-result-column-names` (a full admonition would be too heavy for a landing page — one
sentence such as "Attribute access works as written on DuckDB; Snowflake and Databricks spell
result columns differently, see ..." is enough). In `backends/overview.rst` > "Query with a
registered engine", add the same warning admonition the sibling backend pages already carry.

---

## Scenario S2: Generate `SemanticView` model classes with `semolina codegen`

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: six cards. None names model generation from an existing warehouse, which is my single
     most likely entry task. The "Typed results" card does now surface `semolina codegen-dto`,
     so the CLI is at least visible from the landing page.
   - Followed: the toctree to `how-to/index`.
2. Navigated to: `docs/src/how-to/index.rst`
   - Found: a bare toctree of 18 titles with no one-line abstracts. "How to generate Semolina
     model classes from warehouse views" is unambiguous enough that I picked it immediately.
3. Navigated to: `docs/src/how-to/codegen.rst`
   - Found: the command in the first code block; a backend table naming the introspection
     statement each warehouse uses (`SHOW COLUMNS IN VIEW`, `DESCRIBE TABLE EXTENDED AS JSON`,
     `DESCRIBE SEMANTIC VIEW`), which lets me predict what privileges the codegen role needs;
     multi-view invocation; `> models.py` redirection with the explicit note that there is no
     `--output` flag; and the `codegen-lint` extra.
   - Found: a per-warehouse tab set showing the source DDL beside the generated class. I can
     check the mapping against a view I already own without running anything.
   - Found: the `[connections.<backend>]` warning, consistent with S1; DuckDB `--database` path
     forms including `~` expansion; TODO comments; `VARIANT` → `JsonValue`; the raw-type comment
     convention that preserves `DECIMAL(10,2)` precision the annotation drops; `--check` with its
     Route table and Detail lines; and a full exit-code table.
   - Found: the two `--check` warnings — unverified on Databricks, and a guaranteed false
     positive on Databricks `VARIANT` columns. Both name a date and what was measured. That is
     what I need to decide whether to gate a CI job on it.
   - Followed: "See also" to `howto-codegen-credentials`.
4. Navigated to: `docs/src/how-to/codegen-credentials.rst`
   - Found: TOML, environment variable and `.env` routes with a stated precedence order, a
     Required column per variable, key-pair auth, `SEMOLINA_ENV_FILE`, and troubleshooting keyed
     by exit code (2 = config not assembled, 4 = auth/network).

Everything in `done_when` is answered: the exact command, which section and which environment
variables it reads, what the output looks like per warehouse, and `> models.py`. The note that
`warehouse` and `database` are required for Snowflake codegen but optional for the query pool is
the kind of asymmetry that would otherwise cost me an afternoon.

---

## Scenario S3: Generate a DTO with `--view`, without a model class or query module

**Verdict:** PASS (previous pass: PARTIAL — all three gaps closed)

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: the "Typed results" card now names `semolina codegen-dto` directly, so this route is
     reachable from the landing page rather than only from `how-to/codegen.rst`'s opening tip.
2. Navigated to: `docs/src/how-to/dto-codegen.rst`
   - Found, in the first paragraph: "hand the class to `.into()`, which needs the `arrowmodel`
     extra", with the install command inline and the note that codegen itself does not need it so
     a CI job can skip it. This was the second gap last pass; it is now the first thing on the page.
   - Found, third paragraph: "There are three ways to say which query." The `--view` shortcut is
     announced before any route is taught, which is what makes it findable for someone who does
     not know the word "DTO".
   - Found: "Generate a DTO without writing a query first" — the exact command, the emitted
     class, the naming rule (`analytics.sales` → `Sales`), `--name`, and the two equivalent
     spellings of `--metrics`.
   - Found: the reserved-name list enumerated in full (`query`, `metrics`, `dimensions`, `where`,
     `filter`, `order_by`, `limit`, `execute`, `to_sql`, `using`, `keys`, `values`, `items`,
     `get`, `pop`, `update`, `clear`) with the note that a violation exits `2` before anything
     connects. This was the third gap last pass.
   - Found: the non-identifier case answered head-on — a warehouse field spelled `gross revenue`
     "is the one case this route has no answer for", needing
     `gross_revenue = Metric(source="gross revenue")` and a query built on it.
   - Found: the subsection "You still need a model to run the query", which states that `--view`
     replaces the importable *query*, not the model, and gives the complete runtime snippet
     (`SalesView.query(...).execute()` → `cursor.into(Sales)`) plus a pointer to `howto-codegen`
     to generate that model. This was the first and largest gap last pass and it is now closed
     precisely — including the warning that the projection has to match or the aliases will not
     bind.
3. Navigated to: `docs/src/reference/cli.rst`
   - Found: the three routes restated as a bulleted list, per-flag documentation, the mutual
     exclusions, and the exit-code table. `--metrics` now enumerates the reserved names here too,
     so the how-to and the reference agree.
   - Minor friction: the exit-code note says codes `3` and `4` are "reached through
     `--backend dotted.path.ClassName`". That form *is* documented one screen up under
     `--backend` ("A dotted import path ... dynamically imported and instantiated with no
     arguments"), but `dto-codegen.rst` references it twice without that context, and nothing in
     the docs shows how one would write such a class. Out of scope for my goal.

Every element of `done_when` is answered: I can find the route, run it, read the class, know the
identifier limit and its remedy, and know exactly what I still have to write to use the result.

---

## Scenario S4: Declare every DTO in `pyproject.toml` as a repeatable regeneration step

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst` → `how-to/dto-codegen.rst`
2. Read: "Declare every DTO in pyproject.toml"
   - Found: the motivation in one sentence ("Past two or three DTOs, the command line is
     something nobody remembers between releases"), then a complete `[tool.semolina.dto]` block
     covering both entry shapes — two `query` entries and one `view`/`metrics`/`dimensions` entry
     with an explicit `name`.
   - Found: `semolina codegen-dto` with no arguments as the regeneration command; two key tables
     (section keys and entry keys) pitched at exactly the right level given TOML is on my
     assumed-knowledge list.
   - Found: relative `output` and `database` resolve against the directory holding
     `pyproject.toml`, "not against your shell's working directory". For a pipeline step this is
     the single most important sentence on the page and it is stated explicitly.
   - Found: flags override the file, with a worked DuckDB example for regenerating the declared
     set against a local fixture DB without touching committed config — and the warning that
     `DUCKDB_DATABASE` in the environment beats the section's `database`, which is the trap that
     would have bitten me.
   - Found: credentials are deliberately excluded because `pyproject.toml` gets committed, with
     the reasoning given rather than just the rule.
   - Found: declaration order is preserved and never sorted, "so inserting an entry produces a
     diff of that entry rather than of the whole module"; unrecognized keys are errors, with
     `dimension`/`dimensions` named; `--config` for a non-default file and why it cannot be
     combined with the other routes.
3. Read: "Check a committed DTO in CI"
   - Found: `semolina codegen-dto --check` is the whole invocation when a `[tool.semolina.dto]`
     section exists, because it reads the file `output` names. The per-field stderr table, the
     alias columns that appear only when an alias moved, the fact that a file generated against
     Snowflake and checked against Databricks drifts on every metric, and exit `5` vs `1` vs `2`.
   - This closes the observation I raised last pass, when `codegen-dto` had no `--check` and
     nothing described how to verify a committed `dtos.py` in CI.
4. Cross-checked: `docs/src/reference/cli.rst` > `codegen-dto` > Configuration
   - Found: the same rules compactly, plus `--config`'s requirement that the file exist and carry
     the section. How-to and reference agree.

`done_when` is fully answered, and "Know what a dotted path imports" tells me that `query` entries
execute my module at generation time while `view` entries import nothing — which is what I needed to
decide whether this is safe to run unattended in a pipeline.

---

## Scenario S5: Build a query endpoint with filter parameters returning JSON

**Verdict:** PARTIAL (previous pass: PASS — re-classified, see gap)

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst`
   - Followed: "How to use Semolina in a web API".
2. Navigated to: `docs/src/how-to/web-api.rst`
   - Found: a complete `app.py` with a lifespan handler that creates, registers, unregisters and
     disposes the engine — not just the Semolina call. Also the async variant, with the reason
     construction is not awaited and teardown is.
   - Blocked on getting started: the page opens "Integrate Semolina queries into FastAPI
     endpoints" and immediately uses `@asynccontextmanager`, `FastAPI(lifespan=...)`,
     `@app.get(...)`, `Query(default=None, ge=1, le=1000)`, `HTTPException` and `Request`. None of
     these is introduced, there is no `pip install fastapi`, and nothing tells me how to run the
     resulting file or what URL to hit. I have never written a web endpoint; I can read this page
     end to end and still have no server.
   - Found: "Apply conditional filters from query parameters" — my exact scenario. Optional
     parameters, `.where(... if country else None)` as a no-op, a bounded `limit`, and a sample
     request URL (`GET /api/sales?country=US&limit=50`) showing what produces a `WHERE` clause.
     The sample URL is the one place the page shows me what a request looks like.
   - Found: "Return a typed response instead" — `semolina codegen-dto` output declared as
     `response_model=list[RevenueByCountry]`, with the explanation that the `validation_alias`
     turns `AGG("REVENUE")` into a JSON key named `revenue`. This is the answer to the question my
     frontend team will actually ask, and it links both to `howto-typed-results` and
     `howto-dto-codegen`.
   - Found: "Handle errors" — the honest statement that what reaches my handler is the ADBC
     driver's own exception, the DBAPI hierarchy, worked `HTTPException` mappings, and a
     measured-vs-unmeasured table that marks the Snowflake and Databricks columns "not yet
     measured" rather than guessing. The advice to catch `Error` and treat subclasses as a later
     optimization is directly actionable.
   - Found: pool exhaustion as `sqlalchemy.exc.TimeoutError`, distinct from the builtin, mapped
     to 503; the warning that a missing view is not a 404 and that I should validate view names
     against my own list rather than pattern-matching driver messages. That is REST design advice
     I would not have derived myself and it is the right amount of it.
   - Found: cursor-as-context-manager, the async `async with` requirement (with the reason the
     async cursor cannot have a finalizer), `asyncio.timeout()` → 504, and the client-disconnect
     watcher.
3. Followed: "See also" to `howto-serialization`
   - Found: `dict(row)`, then immediately that a `Decimal` metric breaks `json.dumps`, with a
     `default=` encoder and an explicit `str` vs `float` trade-off ("A chart axis can take the
     float; a ledger total cannot"). Also that FastAPI's `JSONResponse` fails the same way.
   - Found: "Select specific fields for the response" — mapping warehouse column names to stable
     API field names, with the reasoning that only the left-hand keys belong in a response that
     clients depend on.
4. Followed: to `howto-typed-results`, and to `howto-queries` for pagination
   - Found: returning Pydantic objects from a handler, which sidesteps the encoder entirely; and
     in `queries.rst`, the explicit note that there is no `.offset()` with keyset pagination as
     the replacement and the reason it is cheaper on an aggregate query.

Every item in `done_when` is present and complete. What is missing is the step before it.

### Gap Analysis

**Where:** `docs/src/how-to/web-api.rst` > page introduction and "Set up the engine at application
startup"
**What:** The page assumes an existing, running FastAPI application. There is no prerequisite line,
no `pip install "fastapi[standard]"`, no command to run the server, and no one-sentence gloss of
the FastAPI primitives it uses — `lifespan`, the `@app.get` route decorator, and `Query()` for
request parameters. "Web framework patterns", "REST API design" and "how to structure query
endpoints" are all three on this persona's never-assume list, and this is the page that exists to
serve exactly that task ("Build query endpoints for the frontend team").
**Impact:** Hinders rather than blocks — FastAPI's own documentation is one search away, and every
Semolina-specific thing I need is here and correct. But the reader this page was written for is a
data engineer who has never stood up a web service, and for them the page currently starts one step
after the step they are stuck on. Type-alignment: I arrive in work mode wanting to build my first
endpoint, and the page is pitched at someone maintaining their tenth.
**Suggested Fix:** In `how-to/web-api.rst`, after the introductory paragraph: add a short
prerequisites block giving `pip install "fastapi[standard]"`, the instruction to save the examples
as `app.py`, the command to run it (`fastapi dev app.py`), and the URL of the generated interactive
docs — plus a link to FastAPI's own first-steps guide for readers new to it. Then add one clause
each where the primitives first appear: what a lifespan handler is (code that runs once before the
first request and once after the last), and that `Query(default=None)` declares an optional URL
query parameter. Roughly ten lines, and it makes the page self-starting for the persona it targets.

---

## Scenario S6: Set up connection pooling for production

**Verdict:** PARTIAL (unchanged; one of the two previous gaps closed)

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst`
   - Followed: "How to connect an engine to your warehouse" (`connection-pools`).
2. Navigated to: `docs/src/how-to/connection-pools.rst`
   - Found, first sentence: "An `Engine` owns one ADBC connection pool and the dialect for a
     warehouse." The page still begins from the assumption that I know what a connection pool is
     and why a request-serving application needs one. No page in the documentation defines the
     term, and `explanation/` contains only semantic views, type fidelity and DuckDB-vs-warehouse.
   - Improved since last pass: "Two ways to use an engine" now leads each pattern with a plain
     description — "keeps a reference to the engine and calls it yourself", "registers an engine
     under a name and lets the query resolve it" — and the SQLAlchemy and Django analogies trail
     as asides. That was my second gap last pass and it is fixed; the orienting sentence now
     carries meaning for a reader who has used neither ORM.
   - Found: "Size the pool" with `pool_size`, `max_overflow`, `timeout` and `recycle`, both as
     config-object kwargs and TOML keys, with a defaults table (5 and 3, so up to 8 concurrent
     connections — that sentence does real work).
   - Found: the sizing tip — start with `pool_size` at expected concurrent query count, e.g. web
     server worker count; `max_overflow` at 50–100% of it; `recycle` 1800. This is the practical
     guidance that lets me finish the task despite the missing concept, though "web server worker
     count" is itself a term I am not assumed to know.
   - Found: the `sqlalchemy.exc.TimeoutError` warning with the 503 mapping, and the statement
     that the pool is also the concurrency bound — "Semolina adds no second bound of its own",
     and wrapping my own semaphore around `aexecute()` just lowers throughput. That answers the
     question I would have asked next.
   - Found: the DuckDB `:memory:` note explaining *why* `pool_size` is pinned to 1 (in-memory
     databases are isolated per connection, so pooled connections would each see a different
     empty database). This is the one place on the page where the mechanics of pooling are
     explained, and it is explained well — as an aside about DuckDB.
   - Found: "Manage the engine lifecycle" with `register` / `unregister` / `dispose`, the async
     equivalents, why construction is not awaited and teardown is, and the warning not to reach
     into `engine._pool`.
   - Found: multiple named engines with `.using()`, separate sync and async registries, and a
     shutdown loop.
3. Followed: "See also" to `howto-web-api`
   - Found: the same lifecycle inside a FastAPI lifespan handler, which is where I actually need
     it.

I would finish this task, and the sizing numbers I would pick would be reasonable ones. But I would
pick them by copying a tip rather than by understanding what I am sizing, and I could not reason
about the trade-off when my traffic stops looking like the example.

### Gap Analysis

**Where:** `docs/src/how-to/connection-pools.rst` > opening section (and the absence of an
`explanation/` page on the topic)
**What:** No page states what a connection pool is, why opening a warehouse connection per request
is a problem, or what `adbc-poolhouse` does about it. The how-to reasonably starts at "here is how
to size one", but there is no explanation page to send a reader to for the concept. Connection
pooling is on this persona's never-assume list. The closest thing to an explanation on the page is
the DuckDB `:memory:` note, which explains connection isolation as a side effect of a different
point.
**Impact:** Type-alignment mismatch. I arrive wanting to understand the machinery before I
configure it (study/cognition — explanation), and the only page on the topic is a how-to that
assumes the concept. I can still complete the configuration, so this hinders rather than blocks.
The specific consequence is that `pool_size`, `max_overflow` and `recycle` are numbers I copy
rather than derive, and `timeout` — which is the one that turns into a 503 for my users — is the
one I understand least.
**Suggested Fix:** In `how-to/connection-pools.rst`, opening section: add two or three sentences
before the first code block defining a pool in warehouse terms — a fixed set of warehouse sessions
held open and handed out per query, so a request does not pay authentication and session setup
every time; `pool_size` is how many are kept, `max_overflow` how many extra may be opened under
burst, and `timeout` how long a request waits for one before failing. That single paragraph makes
the sizing table readable rather than copyable. (Alternatively, a short
`explanation/connection-pooling.rst` linked from the opening paragraph, which would also give
`web-api.rst` somewhere to point when it says "See :ref:`howto-connection-pools` for pool sizing
guidance".)

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario failed.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S1 | `tutorials/installation.rst` > "Install a backend extra" (and the async / result-extras sections) | `pip install semolina[snowflake]` is unquoted and fails in zsh, while the `uv` line beside it and the async example are quoted; and "extra", "pin", "minimum version rather than a pin" are used as known vocabulary though Python packaging is on this persona's never-assume list | Quote every `pip install "semolina[...]"` on the page, and add one sentence before the tab set defining what an extra is and why the argument needs quoting |
| S1 | `index.rst` > "Quick example"; `how-to/backends/overview.rst` > "Query with a registered engine" | Both show `print(row.country, row.revenue)` with no column-naming caveat, though the same warning appears on five other pages; the front-page example is the first code a Snowflake owner reads and it raises `AttributeError` on their warehouse | Add a one-line pointer to `:ref:`howto-result-column-names`` under the front-page example, and the existing warning admonition to `backends/overview.rst` |
| S5 | `how-to/web-api.rst` > introduction and "Set up the engine at application startup" | The page assumes a running FastAPI app: no install command, no command to run the server, and no gloss of `lifespan`, `@app.get` or `Query()` — all on this persona's never-assume list, on the page that serves their primary task | Add a short prerequisites block (`pip install "fastapi[standard]"`, save as `app.py`, `fastapi dev app.py`, the `/docs` URL, a link to FastAPI's first-steps guide) and a clause each explaining the lifespan handler and `Query()` where they first appear |
| S6 | `how-to/connection-pools.rst` > opening section | Connection pooling is never defined anywhere in the docs, though it is on this persona's never-assume list, so `pool_size` / `max_overflow` / `timeout` are numbers to copy rather than reason about | Add two or three sentences defining a pool in warehouse terms before the first code block, or add `explanation/connection-pooling.rst` and link it from the opening paragraph |

### Resolved since the previous pass

| Scenario | Page | Previously reported | Status |
|----------|------|---------------------|--------|
| S3 | `how-to/dto-codegen.rst` > "Generate a DTO without writing a query first" | "skip both" implied `--view` replaces the model at runtime | Fixed — new "You still need a model to run the query" subsection with runtime code and a pointer to `howto-codegen` |
| S3 | `how-to/dto-codegen.rst` > opening paragraph | `.into()` named without its `arrowmodel` extra | Fixed — the extra and its install command are now in the first paragraph |
| S3 | `reference/cli.rst` > `--metrics` | Reserved builder names referenced but never enumerated | Fixed — enumerated in both `cli.rst` and `dto-codegen.rst` |
| S4 | `how-to/dto-codegen.rst` | No way to verify a committed `dtos.py` in CI | Fixed — `codegen-dto --check` documented with its report format and exit codes |
| S6 | `how-to/connection-pools.rst` > "Two ways to use an engine" | Both patterns introduced by SQLAlchemy / Django analogy alone | Fixed — each pattern now leads with a plain description, analogies trail |

### Non-blocking observations

| Scenario | Page | Observation |
|----------|------|-------------|
| S2 | `docs/src/index.rst` | Still no card for generating models from an existing warehouse, this persona's most likely first task. The "Typed results" card now names `semolina codegen-dto`, which helps, but `semolina codegen` is not reachable from the landing page |
| S2, S3 | `how-to/index.rst` | The section index is a bare toctree of 18 titles with no one-line abstracts, so each title carries all of its own discovery. The project's own navigation guidance calls for inline abstracts on section index pages |
| S3 | `how-to/codegen-credentials.rst` | The page speaks only of `semolina codegen`. `codegen-dto` reads the same chain and `cli.rst` sends readers here for both, but the page never names it — one sentence in the intro would fix it |
| S3 | `how-to/dto-codegen.rst` > "Exit codes" | `--backend dotted.path.ClassName` is referenced twice as if familiar; it is documented under `--backend` in `reference/cli.rst`, but a reader who has not been there will not know what it means, and nothing shows how such a class would be written |
| S6 | `how-to/connection-pools.rst` > "Size the pool" | The sizing tip anchors on "web server worker count", which is itself outside this persona's assumed knowledge. Anchoring on "how many dashboard queries you expect to be in flight at once" would land better |
