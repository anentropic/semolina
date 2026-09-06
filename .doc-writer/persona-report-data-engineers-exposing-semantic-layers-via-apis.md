# Persona Report

**Generated:** 2026-09-05
**Audience:** Data engineers exposing semantic layers via APIs (intermediate)
**Scenarios tested:** 5
**Results:** 2 PASS, 2 PARTIAL, 1 FAIL

## Summary

The restructured doc set serves this persona better than it looks on paper. The thing I
was most worried about -- being handed FastAPI idioms I have never written -- does not
happen: `tutorials/dashboard-api.rst` builds the whole service from an empty file,
explains `lifespan`, justifies a plain `def` handler, and shows the 503 mapping, and
`how-to/web-api.rst` picks up from there without repeating itself. The merged
`how-to/backends.rst` also does what it was meant to: the `:sync-group: warehouse`
tab-sets are used on every tab-set on the page, so picking my warehouse once carries
through installation, TOML, config objects, result column names, and generated SQL.

Two things stop me. First, a Databricks-only reader is blocked at step one: four pages
tell me the ADBC driver comes from the "ADBC Driver Foundry" rather than PyPI, and not
one of them gives a URL, a command, or a word about how the driver is then found. That
is the only mandatory step in the whole doc set with no instructions attached. Second,
the codegen credential story -- the one thing I was told to look at hardest -- is
correct on its dedicated page and contradicted on two others, including the CLI
reference, which says codegen reads "the same sources as `create_engine`" when the whole
point of `how-to/codegen-credentials.rst` is that it does not.

Smaller but real: connection pooling is used throughout and never explained. Every
lifespan example hardcodes credentials in Python, which quietly abandons the
`.semolina.toml` workflow the same docs told me to set up.

---

## Scenario S1: Write a .semolina.toml for Snowflake and get a registered engine

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: "Go further" grid with a card "Configure your warehouse backend -- Snowflake,
     Databricks and DuckDB connection settings, and the `.semolina.toml` that holds them".
     That is exactly my task named in the card text.
   - Followed: `howto-backends-overview`
2. Navigated to: `docs/src/how-to/backends.rst` > "Configure with .semolina.toml"
   - Found: a complete `[connections.default]` Snowflake block with `type`, `account`,
     `user`, `password`, `database`, `warehouse`, and commented-out `role`/`schema`; the
     statement that `type` selects the backend and every other key is passed to the
     matching adbc-poolhouse config class; `create_engine("default")` plus `register()`
     in two lines; the `config_path=` override in a tip.
   - Found: "Snowflake > Connection fields" table lower down tells me `account` is the
     only required field and that `role` is worth setting explicitly in a service because
     semantic views are privilege-scoped. That is warehouse-side reasoning I recognise and
     it is the right level for me.
   - Found: a note warning that `semolina codegen` selects its section differently. Useful
     early warning, placed where I would hit it.
   - Followed: `reference-config` from "See also"
3. Navigated to: `docs/src/reference/config.rst`
   - Found: full field list per backend, common pool fields, and a "Which section is read"
     table. Correct doc type for what I wanted at that moment (facts, not teaching).
   - Success: I can write the file, I know where it is looked for, and I know what
     `register()` buys me.

### Minor friction (non-blocking, no gap analysis)

- `docs/src/reference/config.rst` > "See also" offers ":ref:`tutorial-installation` -- set
  up your first `.semolina.toml`". `tutorials/installation.rst` contains no TOML at all.
  The link promises the thing the page does not have.
- The six-tutorial "start here" sequence never shows a `.semolina.toml` file.
  `tutorials/first-query.rst` step 2 says `create_engine("default")` "reads
  `.semolina.toml`" and then the DuckDB tip switches to a `DuckDBConfig` object, so a
  reader on the tutorial track is told the file exists and never sees one. I only found
  the file because the homepage card sent me to the how-to instead.

---

## Scenario S2: Run `semolina codegen` against my Snowflake semantic views

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: tutorial card 6, "Generate models -- Stop hand-writing the model and the DTO".
   - Followed: `tutorial-warehouse-models`
2. Navigated to: `docs/src/tutorials/warehouse-models.rst`
   - Found: the command with a warehouse tab-set, the generated class, why metrics are
     `| None`, why an unused `Fact` import is there, `> models.py` redirection with the
     promise that chatter goes to stderr, and the `codegen-dto` follow-on. This page is
     aimed squarely at me and it lands.
   - Followed: "Next steps" tells me credentials are resolved
     `.semolina.toml` -> environment -> `.env`, and links the credentials page.
3. Navigated to: `docs/src/how-to/codegen-credentials.rst`
   - Found: the correct and clearly-stated rule -- `--backend snowflake` reads
     `[connections.snowflake]`, not `[connections.default]`; env var tables per backend;
     `.env` and `SEMOLINA_ENV_FILE`; exit codes 2 and 4 with what to check. The warning
     that a default-only file is enough for the app and exits 2 for codegen is precisely
     the trap I would have fallen into.
   - Found: `--backend duckdb` "reads no TOML at all".
4. Navigated to: `docs/src/how-to/codegen.rst` (from the credentials page's "See also")
   - **Friction:** its warning box "Codegen reads a different section from
     `create_engine()`" ends with "`--backend duckdb` reads `[connections.duckdb]`" --
     the direct opposite of what I just read one page earlier. I now do not know which
     page to trust on the rest of the chain either.
5. Navigated to: `docs/src/reference/cli.rst` > "Environment variables" to settle it
   - **Friction:** it says codegen "reads credentials from the same sources as
     `create_engine`". The credentials how-to opens by saying it does not. The reference
     page, which is where I go to settle an argument, takes the wrong side.

### Gap Analysis

**Where:** `docs/src/how-to/codegen.rst` > "Choose a backend" warning ("Codegen reads a
different section from `create_engine()`"), and `docs/src/reference/config.rst` >
"Which section is read".

**What:** Both state that `semolina codegen --backend duckdb` reads
`[connections.duckdb]` (config.rst via "Always `[connections.<name>]`, matching the
backend"). It does not. `how-to/backends.rst` and `how-to/codegen-credentials.rst` both
state the opposite -- that DuckDB codegen reads no TOML section and takes `--database` /
`DUCKDB_DATABASE` only -- and the code agrees with them: `src/semolina/cli/codegen.py`
short-circuits the DuckDB branch and builds `DuckDBConfig(database=...)` directly without
going near `warehouse_config()`.

**Impact:** Two pages against two pages, with the reference page on the wrong side. A
reader who puts a `[connections.duckdb]` section in their file and drops `--database`
gets exit 2 and no idea which page lied. It also undermines the credential page I do
need to trust for Snowflake, which is the path I actually ship on.

**Suggested Fix:** In `how-to/codegen.rst`, section "Choose a backend": change the
warning's last clause to say `--backend duckdb` reads no TOML section and takes
`--database` or `DUCKDB_DATABASE` instead, matching `how-to/codegen-credentials.rst`. In
`reference/config.rst`, section "Which section is read": add a DuckDB row or qualifier to
the table so "Always `[connections.<name>]`" is not stated for a backend it is false for.

**Where:** `docs/src/reference/cli.rst` > "`semolina codegen`" > "Environment variables"
(line 96-98).

**What:** "`codegen` reads credentials from the same sources as
`create_engine`" contradicts the premise of `how-to/codegen-credentials.rst` ("The CLI
does not read credentials from quite the same place your application does") and the
section-selection rule stated on three other pages.

**Impact:** This is the page a reader consults to resolve a conflict, and it is the one
that flattens the distinction the rest of the docs work hard to draw. It would send me
back to a `[connections.default]`-only file and exit 2.

**Suggested Fix:** In `reference/cli.rst`, section "Environment variables": replace "the
same sources as `create_engine`" with the actual rule -- the `[connections.<backend>]`
section named after `--backend`, then prefixed environment variables, then a `.env` file
-- and cross-reference `howto-codegen-credentials` for the difference from
`create_engine`.

---

## Scenario S3: Build a query endpoint that filters from the frontend's query string

**Verdict:** PASS

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Found: tutorial card 4, "Serve a dashboard endpoint -- A FastAPI service that answers
     `GET /revenue` with a typed JSON body".
   - Followed: `tutorial-dashboard-api`
2. Navigated to: `docs/src/tutorials/dashboard-api.rst`
   - Found: prerequisites naming both installs (`semolina[arrowmodel]`, `fastapi`,
     `uvicorn[standard]`) and saying why the extra is needed. Step 1 builds the whole
     `app.py` including the `lifespan` handler, and then explains that everything before
     `yield` is startup and everything after is shutdown -- I did not have to know that
     already.
   - Found: step 2 justifies the plain `def` handler ("FastAPI runs one in a threadpool,
     so a blocking `.execute()` does not stall the event loop"). That is exactly the kind
     of framework decision I would have got wrong on my own, made explicitly rather than
     assumed.
   - Found: step 3 shows me the response I would have shipped and why it is wrong
     (warehouse column spellings, no schema, `Decimal` -> float precision loss), then
     fixes all three with one Pydantic class in step 4.
   - Found: step 5 takes the filter off `Query(default=None)` and relies on `.where(None)`
     being a no-op, with curl output for both the filtered and unfiltered request. Step 6
     turns `adbc_driver_manager.Error` into a 503 and gives me a reproducible way to test
     it (`mv tutorial.db tutorial.db.bak`), including the cleanup step afterwards.
   - Found: a "Complete example" block with the entire runnable service. I can paste it.
   - Followed: "Semolina in a web API" card
3. Navigated to: `docs/src/how-to/web-api.rst`
   - Found: correct type for a working reader -- no re-teaching, straight into `async def`,
     `async with await query.aexecute()`, the required-not-recommended async cursor close,
     `asyncio.timeout()` -> 504, the disconnect watcher, and a measured table of which
     driver exception class you actually get. The honesty about the Snowflake/Databricks
     columns being unmeasured is worth more to me than a guess would be.
   - Success: I have a complete endpoint, an error mapping, and a hardening path.
4. Also checked: `docs/src/how-to/filtering.rst` > "How filter values reach the warehouse"
   - Found: the per-backend binding table and a note that I do not need to escape or
     allow-list a request value, but do need to validate its *type* and must never let a
     caller choose a column name. That answered the security question the tutorial
     deliberately left open, and it answered it with measurements rather than reassurance.

### Minor friction (non-blocking, no gap analysis)

- Pagination is a REST concern this persona is told not to be assumed fluent in, and the
  only treatment of it (the "There is no `.offset()`" note and keyset guidance in
  `how-to/queries.rst`) is not linked from either `tutorials/dashboard-api.rst` or
  `how-to/web-api.rst`. I found it by chance while reading the query builder.

---

## Scenario S4: Size and manage connection pools for production

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - No pooling card in either grid. Found the route via the How-to guides tab.
2. Navigated to: `docs/src/how-to/index.rst`
   - Found: "Connecting to your warehouse" toctree with `connection-pools`. Good grouping.
   - Followed: `connection-pools`
3. Navigated to: `docs/src/how-to/connection-pools.rst`
   - **Friction:** the page opens "An `Engine` owns one ADBC connection pool and the
     dialect for a warehouse" and never says what a connection pool is or why a service
     needs one. I know what a warehouse connection costs, but I have never configured a
     pool, and this page assumes I have.
   - **Friction:** the two usage patterns are introduced by analogy -- "It mirrors
     SQLAlchemy", "It mirrors Django's database aliases". Those are the two ORMs I do not
     use. The analogies carry the explanation rather than decorating it, so I have to
     reconstruct the meaning from the code blocks underneath.
   - Found: "Size the pool" is good. `pool_size` / `max_overflow` / `timeout` / `recycle`
     in a table with defaults, plus a concrete heuristic ("`pool_size` matching the number
     of queries you expect to be in flight at once, a web server's worker count,
     typically" and "`max_overflow` 50-100% of `pool_size`"). That is what I came for.
   - Found: "The pool is also your concurrency bound" -- capacity limiter sized to
     `pool_size + max_overflow`, and an explicit "do not add your own semaphore". Exactly
     the mistake I would have made.
   - Found: the `sqlalchemy.exc.TimeoutError` warning with the 503 mapping, and the
     DuckDB in-memory `pool_size=1` rule.
   - Found: "Manage the engine lifecycle" -- `register` / `unregister` / `dispose`, and the
     async version with the asymmetry explained.
   - **Friction:** every lifecycle example builds the engine from an inline
     `SnowflakeConfig(... password="...")`. So does the async lifespan in
     `how-to/web-api.rst`. Having just been told to put my credentials in
     `.semolina.toml`, none of the production-shaped examples read from it.

### Gap Analysis

**Where:** `docs/src/how-to/connection-pools.rst` > page introduction (before "Two ways to
use an engine"). No explanation page covers this either --
`docs/src/explanation/index.rst` lists only semantic views, type fidelity, and DuckDB vs
warehouse.

**What:** Connection pooling is never explained, only configured. The nearest thing in
the whole doc set is one sentence inside a tutorial
(`tutorials/dashboard-api.rst` step 1: "building one per request would open and close a
warehouse connection per request"), which a reader arriving from the How-to tab never
sees. Page-type mismatch: I needed a short piece of explanation before the how-to, and
the how-to assumes I already had it.

**Impact:** I can still succeed -- the parameter table is operational enough to copy the
defaults and the heuristic is concrete -- but I am tuning numbers whose failure modes I
do not understand. `never_assume` for this persona lists "connection pooling concepts"
and "ORM-style patterns" specifically, and this page leans on both.

**Suggested Fix:** In `how-to/connection-pools.rst`, in the two paragraphs introducing
`Engine`: add two or three sentences saying what the pool holds and what it saves --
warehouse connections are expensive to open and authenticate, the pool keeps a set of
them open and hands one to each query, and a service that skipped the pool would pay
that cost on every request. Then either drop the "mirrors SQLAlchemy" / "mirrors Django"
framing in "Two ways to use an engine" or demote it to a parenthetical, so the patterns
stand on their own description for a reader who has used neither ORM.

**Where:** `docs/src/how-to/connection-pools.rst` > "Manage the engine lifecycle", and
`docs/src/how-to/web-api.rst` > "Open an async engine at startup".

**What:** Every startup/shutdown example constructs the engine from an inline config
object with a literal `password="..."` / `token="dapi..."`. There is no example of the
combination this persona actually ships: `create_engine("default")` reading
`.semolina.toml` (with `pool_size` set in the file) inside a `lifespan` handler.

**Impact:** The TOML workflow and the production-lifecycle workflow are documented on
separate tracks and never meet, so I have to assemble the obvious-in-hindsight
combination myself and guess whether pool settings in the TOML file are honoured when the
engine is built by name. (`how-to/backends.rst` says they are; the lifecycle page never
demonstrates it.)

**Suggested Fix:** In `how-to/connection-pools.rst`, section "Manage the engine
lifecycle": show one variant that builds the engine with `create_engine("default")` and
notes that `pool_size` / `max_overflow` come from the TOML section, so credentials stay
out of the source file.

---

## Scenario S5: Databricks-only -- install, connect, and learn the Databricks specifics

**Verdict:** FAIL

### Navigation Path

1. Started at: `docs/src/index.rst`
   - Followed: "Configure your warehouse backend" -> `howto-backends-overview`
2. Navigated to: `docs/src/how-to/backends.rst`
   - Found: "Pick your backend" table gives me my row immediately -- extra
     `semolina[databricks]`, `MEASURE()` syntax, and "Separate install from the ADBC
     Driver Foundry" under "ADBC driver".
   - **Merged-page check passes:** I selected the Databricks tab once and every subsequent
     tab-set on the page (install, TOML, config object, result column names, generated
     SQL) followed it, because all five carry `:sync-group: warehouse`. I never read a
     Snowflake code block I did not ask for. The per-backend sections at the end are plain
     headings rather than tabs, but they are clearly titled and I skipped Snowflake's
     in one scroll. The merge works for a single-warehouse reader.
   - Found: everything Databricks-specific I needed -- the two connection forms (`uri` vs
     `host`/`http_path`/`token`) and that one must be complete; the warning that `catalog`
     and `schema` are ignored in URI mode; Unity Catalog three-part naming with the
     generated SQL showing each part quoted separately; `measure(revenue)` as the result
     column spelling; and `MEASURE()` in the SQL preview.
   - **Dead end:** ".. important:: The ADBC driver is a separate install -- Databricks
     distributes its ADBC driver through the ADBC Driver Foundry rather than PyPI ...
     Install it from Databricks' own distribution before you connect. The snippets on this
     page assume it is already on the machine." No link, no command, no next page.
3. Went looking for the missing step through every route the docs offer:
   - `tutorials/installation.rst` > "Install a backend extra" > Databricks tab: "The ADBC
     Databricks driver is **not** on PyPI and no extra can fetch it; see
     :ref:`howto-backends-databricks`" -- which is the paragraph in step 2 that sent me
     nowhere. The two pages point at each other.
   - `how-to/warehouse-testing.rst` mentions `adbc_driver_manager.dbapi` as the module to
     patch for Databricks, which tells me the driver is reached through the driver
     manager but nothing about obtaining it.
   - `how-to/codegen.rst` and `explanation/type-fidelity.rst` describe how the Foundry
     driver behaves, which only confirms I am the one expected to have installed it.
   - No page in the set contains a Foundry URL, an install command, or a word about where
     the driver has to end up for adbc-poolhouse to find it. I would leave the docs here.

### Gap Analysis

**Where:** `docs/src/how-to/backends.rst` > "Databricks" > the ".. important:: The ADBC
driver is a separate install" admonition, and `docs/src/tutorials/installation.rst` >
"Install a backend extra" > Databricks tab.

**What:** The one mandatory prerequisite for connecting to Databricks is named four times
across the doc set and never made actionable. There is no link to the ADBC Driver
Foundry, no install command, and no statement of how the installed driver is discovered
at runtime (driver-manager search path, a `driver=` setting, or nothing to do). The two
pages that raise it cross-reference each other in a loop.

**Impact:** A Databricks-only reader cannot get to a working connection from the
documentation. Everything downstream on the page -- the TOML section, the config object,
the query, the codegen commands -- is written on the assumption that this step is already
done, so the whole Databricks path is gated behind a step with no instructions. This is
the difference between "hard" and "not possible from the docs", so it is a FAIL rather
than friction. The Snowflake and DuckDB paths are unaffected.

**Suggested Fix:** In `how-to/backends.rst`, section "Databricks", inside the existing
"The ADBC driver is a separate install" admonition: add the Foundry URL and the install
command, and one sentence saying how the driver is located afterwards (and what error you
get when it is not found). If Semolina genuinely cannot pin or verify that step, say so
explicitly and link the Databricks page that owns it, so the reader has a destination
rather than a name to search for. Then update the `tutorials/installation.rst` Databricks
tab to point at that instruction rather than at the paragraph that restates the problem.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S5 | `how-to/backends.rst` > "Databricks" (the "ADBC driver is a separate install" admonition); `tutorials/installation.rst` > "Install a backend extra" > Databricks tab | The mandatory ADBC Databricks driver install is named four times and never made actionable -- no URL, no command, no word on how the driver is discovered. The two pages that raise it link only to each other. | Put the ADBC Driver Foundry link and the install command in the backends.rst admonition, plus one sentence on how the driver is located and the error when it is not; repoint the installation.rst Databricks tab at that instruction. |

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S2 | `how-to/codegen.rst` > "Choose a backend" warning | Claims `--backend duckdb` reads `[connections.duckdb]`; DuckDB codegen reads no TOML section (contradicts `codegen-credentials.rst` and `backends.rst`, and the CLI's own behaviour). | In `how-to/codegen.rst`, section "Choose a backend": change the warning's DuckDB clause to say it reads no TOML section and takes `--database` / `DUCKDB_DATABASE`, matching the credentials page. |
| S2 | `reference/config.rst` > "Which section is read" | The table's "Always `[connections.<name>]`, matching the backend" is false for `--backend duckdb`. | In `reference/config.rst`, section "Which section is read": add a DuckDB row or qualifier so the blanket "always" is not stated for a backend it does not hold for. |
| S2 | `reference/cli.rst` > "`semolina codegen`" > "Environment variables" | Says codegen reads credentials "from the same sources as `create_engine`", contradicting the entire premise of `how-to/codegen-credentials.rst`. The reference page is where readers go to settle exactly this question. | In `reference/cli.rst`, section "Environment variables": state the real chain (`[connections.<backend>]`, then prefixed env vars, then `.env`) and cross-reference `howto-codegen-credentials` for how it differs from `create_engine`. |
| S4 | `how-to/connection-pools.rst` > page introduction | Connection pooling is configured but never explained; no explanation page covers it, and the two usage patterns are carried by SQLAlchemy/Django analogies this persona's `never_assume` list rules out. | In `how-to/connection-pools.rst`, introduction: add two or three sentences on what the pool holds and what it saves per request; in "Two ways to use an engine", demote the SQLAlchemy/Django analogies so each pattern stands on its own description. |
| S4 | `how-to/connection-pools.rst` > "Manage the engine lifecycle" (and `how-to/web-api.rst` > "Open an async engine at startup") | Every startup/shutdown example inlines credentials in a config object; the `.semolina.toml` workflow and the production lifecycle workflow never meet. | In `how-to/connection-pools.rst`, section "Manage the engine lifecycle": add a variant building the engine with `create_engine("default")`, noting that `pool_size` / `max_overflow` come from the TOML section so credentials stay out of the source. |
| S1 | `reference/config.rst` > "See also" | The link ":ref:`tutorial-installation` -- set up your first `.semolina.toml`" points at a page containing no TOML; and no tutorial in the six-lesson sequence ever shows a `.semolina.toml` file, though `tutorials/first-query.rst` step 2 tells the reader `create_engine("default")` reads one. | In `reference/config.rst`, "See also": repoint that entry at `howto-backends` (which does show the file) or reword it. Optionally, in `tutorials/first-query.rst` step 2, show the three-line `[connections.default]` block the sentence refers to. |
| S3 | `tutorials/dashboard-api.rst` and `how-to/web-api.rst` | Pagination (a `never_assume` REST concern) is covered only in `how-to/queries.rst`'s "There is no `.offset()`" note and is not linked from either endpoint page. | In `how-to/web-api.rst`, "See also": add a line pointing at `howto-queries` for `.limit()` and the keyset-pagination approach for a paged dashboard. |
