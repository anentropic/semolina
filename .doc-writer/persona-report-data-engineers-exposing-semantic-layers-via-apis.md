# Persona Report

**Generated:** 2026-08-16
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 6
**Results:** 4 PASS, 2 PARTIAL, 0 FAIL

## Summary

The connection, codegen and endpoint paths are in good shape for this persona: `.semolina.toml`
is documented field-by-field, the `[connections.default]` vs `[connections.<backend>]` trap is
warned about in three separate places, and `how-to/web-api.rst` gives complete endpoint code
rather than fragments, which is exactly what a reader who has never written a REST handler
needs. The new `codegen-dto` surface is thoroughly documented — all three routes are stated
up front in `reference/cli.rst`, and `how-to/dto-codegen.rst` covers naming, ordering, path
resolution and unknown-key errors in enough detail to build a repeatable pipeline step.

Two gaps stand out. First, the `--view` shortcut is documented as replacing the model class and
query module, but the DTO it produces cannot be used without a `SemanticView` model and a query
anyway — because that is the only way to obtain the cursor you hand it to. The sentence "which
is the one thing this route does not replace" tells the reader the opposite. Second,
`how-to/connection-pools.rst` never says what a connection pool is or why a production API needs
one, and leans on SQLAlchemy and Django analogies; both are on this persona's never-assume list.

---

## Scenario S1: Configure .semolina.toml and connect to Snowflake with create_engine()

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Get started in 5 minutes" card, and a quick example showing
     `register("default", create_engine("default"))  # reads .semolina.toml`
   - Followed: the card to `tutorial-installation`
2. Navigated to: `docs/src/tutorials/installation.rst`
   - Found: `pip install semolina[snowflake]` under a per-backend tab set, and a verification
     command. The extras are named and explained one at a time, which matters given that Python
     packaging extras are on my never-assume list.
   - Followed: "Next steps" to `tutorial-first-query`
3. Navigated to: `docs/src/tutorials/first-query.rst`
   - Found: step 2 "Register an engine" with the same two-line registration, plus the sentence
     that `create_engine("default")` reads `[connections.default]` and that `type` picks the
     warehouse. No TOML file contents yet, but an explicit pointer onward.
   - Followed: "See :ref:`howto-backends-overview` for full connection details and TOML
     configuration"
4. Navigated to: `docs/src/how-to/backends/overview.rst` then `backends/snowflake.rst`
   - Found: a complete, copyable `.semolina.toml` block and a Required/Optional field table.
     The note distinguishing what the query engine needs from what `semolina codegen` needs is
     the kind of detail I would otherwise have discovered by failing.
   - Found: the second note, that `semolina codegen --backend snowflake` reads
     `[connections.snowflake]`, not `[connections.default]`. This is repeated in
     `reference/config.rst`, `how-to/codegen.rst` and `how-to/codegen-credentials.rst`. Four
     statements of the same trap is the right amount for a trap that silently exits 2.
5. Navigated to: `docs/src/reference/config.rst` (via "See also")
   - Found: `config_path` for a non-default file location, the full Snowflake field list
     including key-pair and OAuth auth, and a table saying exactly which caller reads which
     section.

No friction. Type-alignment is correct throughout: the tutorial taught, the how-to gave me the
file, the reference answered the field-level questions.

---

## Scenario S2: Generate SemanticView model classes with semolina codegen

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: no card or mention of codegen. The four cards are Get started / Define models /
     Build queries / API reference. Minor: generating models from an existing warehouse is my
     single most likely entry task, and the front page does not name it.
   - Followed: the hidden toctree to `how-to/index`
2. Navigated to: `docs/src/how-to/index.rst`
   - Found: a bare toctree of 18 page titles with no one-line abstracts. `codegen` renders as
     "How to generate Semolina model classes from warehouse views", which is unambiguous, so I
     picked it immediately.
3. Navigated to: `docs/src/how-to/codegen.rst`
   - Found: the command in the first code block, a backend table naming the introspection
     statement each warehouse uses, multi-view invocation, `> models.py` redirection, and the
     `codegen-lint` extra. The per-warehouse tab set shows the source DDL alongside the
     generated class, so I can check the mapping against a view I already own.
   - Found: the `--backend` section warning about `[connections.<backend>]`, consistent with S1.
   - Found: TODO comments, VARIANT handling, the raw-type comment convention, `--check` drift
     detection with its route table, and a full exit-code table.
   - Followed: "See also" to `howto-codegen-credentials`
4. Navigated to: `docs/src/how-to/codegen-credentials.rst`
   - Found: TOML, environment variable and `.env` routes with a stated precedence order, a
     Required column per variable, key-pair auth, `SEMOLINA_ENV_FILE`, and a troubleshooting
     section keyed by exit code.

Everything in `done_when` was answered. The note that `warehouse` and `database` are required
for Snowflake codegen but optional for the query pool is precisely the sort of asymmetry that
would otherwise cost me an afternoon.

---

## Scenario S3: Generate a DTO with `--view`, without a model class or query module

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst`
   - Found: "How to generate a typed DTO from a query" in the toctree. As a data engineer I did
     not know I wanted a "DTO", so I arrived here the second way instead: from
     `how-to/codegen.rst`, whose opening tip explicitly contrasts the two commands and links
     here. That tip is doing real discovery work.
2. Navigated to: `docs/src/how-to/dto-codegen.rst`
   - Found, in the third paragraph: "There are three ways to say which query. Point it at one
     you already wrote, name a view and its fields on the command line, or declare the whole set
     in `pyproject.toml`." The shortcut is announced before any of the routes are taught, which
     is what makes it findable.
   - Found: the section heading "Generate a DTO without writing a query first", with the exact
     command, the emitted class, the class-naming rule (`analytics.sales` → `Sales`), `--name`,
     and the two equivalent spellings of `--metrics`.
   - Found: the identifier limit, stated plainly — "each one has to be a plain Python
     identifier" — with the `gross revenue` → `Metric(source="gross revenue")` remedy, and the
     warning that a typo is caught by exit 6 rather than by my editor, with the message listing
     the columns the result did carry. This answers the field-name question well.
3. Navigated to: `docs/src/reference/cli.rst`
   - Found: the three routes restated as a bulleted list under `semolina codegen-dto`, per-flag
     documentation, the mutual exclusions, and the exit-code table.
   - Friction: `--metrics` says each name "must be a plain Python identifier that is not a
     keyword and not one of the names reserved by the query builder." I could not find the
     reserved names anywhere — not in `cli.rst`, not in `dto-codegen.rst`, not in `models.rst`.
4. Tried to use the result: followed "See also" to `howto-typed-results`
   - Found: `.into()` needs the `semolina[arrowmodel]` extra. `dto-codegen.rst` had told me to
     "hand the class to `.into()`" in its first paragraph and mentioned only the `codegen-lint`
     extra, so I would have hit `SemolinaMissingDependencyError` first and backtracked.
   - Blocked on the larger question: to call `.into()` I need a `SemolinaCursor`, and per
     `how-to/queries.rst` the only way to get one is `Model.query()...execute()` on a
     `SemanticView` subclass. So the model class I was told I could skip is still required.

### Gap Analysis

**Where:** `docs/src/how-to/dto-codegen.rst` > "Generate a DTO without writing a query first"
**What:** The section opens "A dotted path needs a model class and a query module to point at.
When you already know which view and which fields you want, name them on the command line and
skip both", and closes the identifier paragraph with "a model declaring `gross_revenue =
Metric(source="gross revenue")` and a query built on it, which is the one thing this route does
not replace." Both sentences describe the model and query as things this route replaces. They
are replaced only for the act of generating; at runtime the generated DTO is useless without
them, because `.into()` takes a cursor and only `Model.query().execute()` produces one.
**Impact:** This persona is explicitly not assumed to know fluent builders or descriptor-style
models, and this route was added so they would not have to write one. A reader taking the
sentence at face value generates a `Sales` DTO, then has no documented way to obtain a result to
convert. Nothing on the page closes the loop for the `--view` route the way the dotted-path
route closes it with its `revenue_by_country.execute()` snippet.
**Suggested Fix:** In `how-to/dto-codegen.rst`, section "Generate a DTO without writing a query
first": add a closing paragraph stating that the route skips writing the model and query *for
codegen*, and that running the query still needs a `SemanticView` model — with a pointer to
`:ref:`howto-codegen`` to generate that model from the same view. Narrow "skip both" to "skip
both here", and rephrase "the one thing this route does not replace" so it does not imply the
route replaces the model at runtime.

**Where:** `docs/src/how-to/dto-codegen.rst` > opening paragraph and "Format the generated output"
**What:** The page tells the reader to "hand the class to `.into()`" but never names the
`semolina[arrowmodel]` extra that `.into()` requires. `codegen-lint` is the only extra mentioned.
**Impact:** A reader who follows this page end to end generates a DTO successfully and then
fails at the first `.into()` call. The exception names the package, so it is recoverable, but it
is an avoidable failure on the page's own happy path — and Python extras are on this persona's
never-assume list.
**Suggested Fix:** In `how-to/dto-codegen.rst`, opening section: after "hand the class to
`.into()`", note that `.into()` needs the `semolina[arrowmodel]` extra and link
`:ref:`tutorial-installation-result-extras``.

**Where:** `docs/src/reference/cli.rst` > `semolina codegen-dto` > Options > `--metrics`
**What:** "not one of the names reserved by the query builder" names a constraint whose contents
appear nowhere in the documentation.
**Impact:** A field legitimately named something like `query`, `metrics` or `limit` in the
warehouse would exit 2 with no way to predict it from the docs, and no way to look up the list.
This is the one identifier rule the `--view` route cannot warn me about in advance.
**Suggested Fix:** In `reference/cli.rst`, under `--metrics`: enumerate the reserved names, or
state that the error message on exit 2 names the offending value and what it collided with.

---

## Scenario S4: Declare every DTO in pyproject.toml as a repeatable regeneration step

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst` → `how-to/dto-codegen.rst`
2. Read: "Declare every DTO in pyproject.toml"
   - Found: the motivation stated in one sentence ("Past two or three DTOs, the command line is
     something nobody remembers between releases"), then a complete `[tool.semolina.dto]` block
     showing both entry shapes — two `query` entries and one `view`/`metrics`/`dimensions`
     entry with an explicit `name`.
   - Found: `semolina codegen-dto` with no arguments as the regeneration command.
   - Found: two key tables, one for the section and one for the entries. TOML is on my assumed-
     knowledge list, and these tables are pitched at exactly the right level.
   - Found: relative `output` and `database` resolve against the directory holding
     `pyproject.toml`, "not against your shell's working directory". This is the single most
     important sentence for a pipeline step and it is stated explicitly.
   - Found: flags override the file, with a worked DuckDB example for regenerating the same
     declared set against a local fixture database without touching committed config.
   - Found: credentials are deliberately excluded from `pyproject.toml` because it gets
     committed, with a pointer to `howto-codegen-credentials`. The reasoning is given, not just
     the rule.
   - Found: emission order follows declaration order and codegen never sorts, "so inserting an
     entry produces a diff of that entry rather than of the whole module" — which is what makes
     the committed file reviewable.
   - Found: unrecognized keys are errors, with `dimension`/`dimensions` and `outputs`/`output`
     as the named examples.
   - Found: `--config` for a non-default file, and why it cannot be combined with the other two
     routes.
3. Cross-checked: `docs/src/reference/cli.rst` > `semolina codegen-dto` > Configuration
   - Found: the same rules stated compactly, plus `--config`'s requirement that the file exist
     and carry the section. The how-to and the reference agree.

Everything in `done_when` was answered, and the "Know what a dotted path imports" section told
me that `query` entries execute my module at generation time while `view` entries import
nothing — which is what I needed to decide whether this is safe to run unattended.

One thing I would still have to work out for myself: there is no `--check` for `codegen-dto`
(the page says so, and explains why code 5 does not exist here), so nothing tells me how to
verify in CI that a committed `dtos.py` still matches the warehouse. `semolina codegen --check`
covers the model side but not the DTO side. This is outside my stated goal — regeneration is
fully repeatable as documented — so it is a recommendation rather than a gap.

---

## Scenario S5: Build a query endpoint with filter parameters returning JSON

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst`
   - Followed: "How to use Semolina in a web API"
2. Navigated to: `docs/src/how-to/web-api.rst`
   - Found: a complete `app.py` with a lifespan handler creating and disposing the engine, not
     just the Semolina call. Given that web framework patterns are on my never-assume list, the
     full file is the difference between usable and not.
   - Found: "Apply conditional filters from query parameters" — the exact scenario. Optional
     `Query(default=None)` parameters, `.where(... if country else None)` as a no-op, a bounded
     `limit` with `ge`/`le`, and a sample request URL showing what produces a `WHERE` clause.
   - Found: "Handle errors" with the honest statement that what reaches my handler is the ADBC
     driver's own exception, the DBAPI hierarchy, worked `HTTPException` mappings, and a
     measured-vs-unmeasured table that marks the Snowflake and Databricks columns "not yet
     measured" rather than guessing. The advice to catch `Error` and treat subclasses as a later
     optimization is directly actionable.
   - Found: the pool-exhaustion case calling out `sqlalchemy.exc.TimeoutError` as distinct from
     the builtin, with the 503 mapping.
   - Found: the warning that a missing view is not a 404 and that I should validate view names
     against my own list rather than pattern-matching driver messages. That is REST design advice
     I would not have derived myself.
3. Followed: "See also" to `howto-serialization`
   - Found: `dict(row)`, and immediately the warning that a `Decimal` metric breaks
     `json.dumps`, with a `default=` encoder and an explicit `str` vs `float` trade-off ("A chart
     axis can take the float; a ledger total cannot").
   - Found: "Select specific fields for the response" — mapping warehouse column names to stable
     API field names, with the reasoning that only the left-hand keys belong in a response
     clients depend on.
4. Followed: to `howto-typed-results` for the cleaner route
   - Found: returning Pydantic objects from a FastAPI handler with `-> list[RevenueByCountry]`,
     which sidesteps the encoder entirely.

The column-naming warning ("Semolina adds no `AS` aliases...") appears on every page where I
could trip over it — first-query, queries, serialization, web-api — and each instance links to
`howto-result-column-names`. For a reader who will develop against DuckDB and deploy against
Snowflake, that repetition is warranted rather than redundant.

Pagination is addressed head-on: `how-to/queries.rst` states there is no `.offset()` and gives
keyset pagination as the replacement, with the reason it is cheaper on an aggregate query.

---

## Scenario S6: Set up connection pooling for production

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst` → `how-to/index.rst`
   - Followed: "How to connect an engine to your warehouse" (`connection-pools`)
2. Navigated to: `docs/src/how-to/connection-pools.rst`
   - Found, first sentence: "An `Engine` owns one ADBC connection pool and the dialect for a
     warehouse." The page begins from the assumption that I know what a connection pool is and
     why an API needs one. Connection pooling concepts are on my never-assume list, and no page
     in the documentation defines the term.
   - Friction: the two usage patterns are introduced by analogy — "It mirrors SQLAlchemy" and
     "It mirrors Django's database aliases". I have not used either. The code below each
     analogy is clear enough that I can proceed, but the sentence meant to orient me does not.
   - Found: "Size the pool" with `pool_size`, `max_overflow`, `timeout` and `recycle`, both as
     config-object kwargs and as TOML keys, with a defaults table.
   - Found: the sizing tip — start with `pool_size` at expected concurrent query count, e.g. web
     server worker count, `max_overflow` at 50–100% of it, `recycle` 1800. This is the practical
     guidance that lets me finish the task despite the missing concept.
   - Found: the `sqlalchemy.exc.TimeoutError` warning with the 503 mapping, and the statement
     that the pool is also the concurrency bound and that adding my own semaphore just lowers
     throughput.
   - Found: "Manage the engine lifecycle" with `register` / `unregister` / `dispose`, and the
     async equivalents, plus an explanation of why construction is not awaited and teardown is.
   - Found: multiple named engines with `.using()`, and a shutdown loop.
3. Followed: "See also" to `howto-web-api`
   - Found: the same lifecycle inside a FastAPI lifespan handler, which is where I actually
     need it.

I would finish this task. But I would finish it by copying numbers from a tip rather than by
understanding what I am sizing, and I would not be able to reason about the trade-off when my
own traffic does not look like the example.

### Gap Analysis

**Where:** `docs/src/how-to/connection-pools.rst` > opening section, and `explanation/index.rst`
**What:** No page states what a connection pool is, why opening a warehouse connection per
request is a problem, or what `adbc-poolhouse` does about it. The how-to reasonably starts from
"here is how to size one", but there is no explanation page to send a reader to for the concept —
`explanation/` contains semantic views, type fidelity and DuckDB-vs-warehouse only.
**Impact:** Type-alignment mismatch. I arrive wanting to understand the machinery before I
configure it (study/cognition — explanation), and the only page on the topic is a how-to that
assumes the concept. I can still complete the configuration, so this hinders rather than blocks,
but the numbers I choose are copied rather than reasoned.
**Suggested Fix:** In `how-to/connection-pools.rst`, opening section: add two or three sentences
defining a connection pool in warehouse terms — a fixed set of reusable warehouse sessions held
open so a request does not pay connection setup, with `pool_size` as the steady-state count —
before the first code block. Alternatively add a short `explanation/connection-pooling.rst` and
link it from the opening paragraph.

**Where:** `docs/src/how-to/connection-pools.rst` > "Two ways to use an engine"
**What:** The direct and registry patterns are explained by analogy to SQLAlchemy's
`create_engine` and Django's database aliases. ORM-style patterns are on this persona's
never-assume list.
**Impact:** The orienting sentence for each pattern carries no information for a reader who has
used neither ORM. The following code carries the meaning, so this is friction, not a blocker.
**Suggested Fix:** In `how-to/connection-pools.rst`, section "Two ways to use an engine": lead
each pattern with what it does — "keep the engine in a variable and call it directly" / "register
it once under a name and let queries find it" — and keep the ORM analogies as a trailing aside
for readers who know them.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None. No scenario failed.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S3 | `how-to/dto-codegen.rst` > "Generate a DTO without writing a query first" | "skip both" and "the one thing this route does not replace" tell the reader the `--view` route replaces the model class and query module; at runtime both are still required, because `.into()` needs a cursor and only `Model.query().execute()` produces one | Add a closing paragraph: the route skips the model and query for codegen only, running the query still needs a `SemanticView` model, link `:ref:`howto-codegen`` to generate it from the same view. Narrow the two sentences accordingly |
| S3 | `how-to/dto-codegen.rst` > opening paragraph | The page tells the reader to hand the class to `.into()` but never names the `semolina[arrowmodel]` extra `.into()` requires; only `codegen-lint` is mentioned | Note the `arrowmodel` extra where `.into()` is first mentioned and link `:ref:`tutorial-installation-result-extras`` |
| S3 | `reference/cli.rst` > `codegen-dto` > `--metrics` | "not one of the names reserved by the query builder" names a constraint that is never enumerated anywhere in the docs | Enumerate the reserved names, or state that the exit-2 message names the offending value and the collision |
| S6 | `how-to/connection-pools.rst` > opening section | Connection pooling is never defined, though it is on this persona's never-assume list; there is no explanation page to link to | Add two or three sentences defining a pool in warehouse terms before the first code block, or add `explanation/connection-pooling.rst` and link it |
| S6 | `how-to/connection-pools.rst` > "Two ways to use an engine" | Both patterns are introduced by analogy to SQLAlchemy and Django, which this persona is not assumed to know | Lead each pattern with a plain description of what it does; keep the ORM analogies as a trailing aside |

### Non-blocking observations

| Scenario | Page | Observation |
|----------|------|-------------|
| S2 | `docs/src/index.rst` | The front page has no card for generating models from an existing warehouse, which is this persona's most likely first task. A fifth card linking `howto-codegen` would shorten the path |
| S2, S3 | `how-to/index.rst` | The section index is a bare toctree with no one-line abstracts, so "How to generate a typed DTO from a query" has to carry all of its own discovery. The project's own navigation guidance calls for inline abstracts on section index pages |
| S4 | `how-to/dto-codegen.rst` | `codegen-dto` has no `--check`, and nothing describes how to verify in CI that a committed `dtos.py` is still current. A sentence recommending regenerate-and-diff would complete the pipeline story that the `pyproject.toml` section starts |
| S3 | `how-to/codegen-credentials.rst` | The page speaks only of `semolina codegen`; `codegen-dto` reads the same chain but is never named here, so a reader landing on this page first will not know it applies to both |
