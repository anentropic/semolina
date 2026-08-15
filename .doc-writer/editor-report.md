# Editor Report

**Generated:** 2026-08-14
**Scope:** `docs/src/` — 28 reStructuredText files (excluding `reference/api/`, autoapi-generated)
**Files reviewed:** 28
**Files changed:** 24

| Severity | Count | Fixed | Needs author judgement |
|----------|-------|-------|------------------------|
| BLOCKING | 12 | 12 | 0 |
| SUGGESTION | 24 | 20 | 4 |
| NITPICK | 6 | 5 | 1 |
| **Total** | **42** | **37** | **5** |

Verification: `sphinx-build -b html -n -W --keep-going docs/src` passes with zero
warnings (nitpicky mode, warnings-as-errors), excluding pre-existing autoapi-page
warnings already covered by `suppress_warnings` in `conf.py`. `conf.py` and
`reference/api/` were not touched.

## Summary

The prose is in genuinely good shape — a prior humanizer pass clearly landed, and a
scan for promotional language, AI vocabulary, and vague attributions returned almost
nothing. The real damage was elsewhere: **131 of the docs' API cross-references were
silently dead**, and the hand-written CLI reference had drifted away from the actual
`semolina codegen` implementation, including two environment variable names that do
not exist. Both classes of defect were invisible to the existing build because
`nitpicky` is off.

---

## BLOCKING

### 1. 131 dead API cross-references across 24 files — FIXED

The single largest defect. Every `:py:class:`~semolina.SemanticView``,
`:py:func:`~semolina.create_engine``, `:py:meth:`~semolina.SemolinaCursor.into``,
and so on pointed at the **re-export** path. sphinx-autoapi indexes symbols at their
**defining module** path, so none of them resolved. With `nitpicky` off they rendered
as unlinked plain text and the build stayed green.

Confirmed against the built `objects.inv`: the inventory contains
`semolina.models.SemanticView`, not `semolina.SemanticView`.

Rewrote all 131 targets to their defining-module paths. Because every reference uses
the `~` prefix, **rendered link text is unchanged** — only the targets now resolve.

| Was | Now | Uses |
|-----|-----|------|
| `semolina.SemanticView` | `semolina.models.SemanticView` | 12 |
| `semolina.create_engine` | `semolina.config.create_engine` | 12 |
| `semolina.Row` | `semolina.results.Row` | 11 |
| `semolina.SemolinaCursor` | `semolina.cursor.SemolinaCursor` | 11 |
| `semolina.Metric` / `.Dimension` | `semolina.fields.*` | 16 |
| `semolina.AsyncSemolinaCursor` | `semolina.acursor.AsyncSemolinaCursor` | 7 |
| `semolina.SemolinaCursor.fetch_*` / `.into` / `.iter_into` | `semolina.cursor.SemolinaCursor.*` | 30 |
| `semolina.register*` / `get_*` / `unregister*` | `semolina.registry.*` | 11 |
| `semolina.Fact`, `NullsOrdering`, `OrderTerm`, `Predicate`, `Dialect` | defining modules | 16 |
| `semolina.Semolina*Error` (×4) | `semolina.engines.base.*`, `semolina.exceptions.*` | 4 |

**Note for the author:** the underlying cause is that `autoapi_options` in `conf.py`
omits `imported-members`. If you would rather write the ergonomic
`~semolina.SemanticView` form in prose, adding `imported-members` to `autoapi_options`
would make the short paths resolvable and this rewrite could be reverted. I did not
change `conf.py` as instructed. Either way, **turning on `nitpicky = True` would have
caught this on day one** and is the durable fix.

### 2–4. `reference/cli.rst` documented environment variables that do not exist — FIXED

`DATABRICKS_SERVER_HOSTNAME` and `DATABRICKS_ACCESS_TOKEN` are not read by anything.
Verified against `adbc_poolhouse.DatabricksConfig`, whose `env_prefix` is
`DATABRICKS_` over fields `host`, `http_path`, `token`, `catalog`, `schema`. The real
names are `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`. A reader
following this page could not authenticate.

`how-to/codegen-credentials.rst` had them right, so the two pages contradicted each
other. Fixed the reference page, and fixed the same wrong name in the
`how-to/backends/databricks.rst` "See also" bullet.

### 5. `codegen-credentials.rst` DuckDB fallback was backwards — FIXED

Said: *"With neither set, DuckDB opens an empty in-memory database."*
Source (`cli/codegen.py:131`) raises `typer.BadParameter("DuckDB backend requires a
database path...")`. `how-to/codegen.rst` already stated this correctly, so the two
pages directly contradicted each other. Rewritten to match the implementation.

### 6–8. `reference/cli.rst` was missing half the CLI surface — FIXED

Verified against the `codegen()` typer signature:

- `--check` and `--model` were entirely undocumented on the reference page (they are
  covered in the how-to, but the reference is the page that claims completeness).
- Exit code **5** (annotation drift) was absent from the exit-code table.
- Exit code 1 and 2 meanings were incomplete. 2 also covers unassemblable connection
  config, `--backend duckdb` with no database path, and a broken `--check`/`--model`
  pairing; 1 also covers a missing or unparseable `--model` file.

### 9. `SEMOLINA_ENV_FILE` semantics were wrong — FIXED

Said the variable loads a `.env` file *"instead of the shell environment"*. Actual
precedence, per `config.py:443`, is **TOML section > environment > `.env` file**, and
`SEMOLINA_ENV_FILE` only changes *which* `.env` path is read. Corrected, and the
matching claim in `how-to/codegen.rst` ("Credentials come from environment variables")
was widened to name the full chain.

### 10. `codegen.rst` exit-code 2 row incomplete — FIXED

Same root as #7; listed only the `--backend` and `--check`/`--model` cases.

### 11–12. Rule 1 violations: internal/maintainer detail in user docs — FIXED

- `how-to/web-api.rst`: *"the import ban that keeps `asyncio` and `anyio` out of
  Semolina is scoped to `src/semolina/`"* and *"Semolina's own cancellation tests
  drive this path under asyncio and Trio from one source file."* Repo-internal lint
  policy and test layout. Rewritten to the user-facing fact.
- `how-to/codegen.rst`: the `--check` warning described internal test coverage
  (*"nobody has yet run the zero-row wrapper..."*). Reframed as a product limitation.
- `tutorials/installation.rst`: version-floor rationale reading as a maintainer
  changelog (*"`pandas>=2.0.0` was not measured; behaviour was exercised at 2.3.3 and
  3.0.5"*). Replaced with the floors themselves.

---

## SUGGESTION

### Diataxis type integrity

| Page | Issue | Action |
|------|-------|--------|
| `tutorials/installation.rst` | Async section carried a two-paragraph changelog of adbc-poolhouse defects (1.6.0 pool sizing, 1.6.2 cancel deadlock). Explanation content in a tutorial. | Compressed to one sentence stating the floor |
| `tutorials/installation.rst` | pandas/polars install-asymmetry digression, explaining ADBC's internal conversion path mid-tutorial. | Compressed; links out to `howto-arrow-output` |
| `tutorials/first-query.rst` | Offered `query(metrics=..., dimensions=...)` as an alternative to the fluent chain. The skill requires tutorials to have one clear path with no "you could also" tangents; `how-to/queries.rst` already documents the shorthand. | Removed, replaced with a link |
| `how-to/typed-results.rst` | Intro teaser: *"parts that are cheaper to read here than to find out from a production incident."* | Replaced with a plain contents sentence |
| `how-to/arrow-output.rst` | "Decimals differ between the two" is explanation living in a how-to. | Kept (operationally needed) but added an explicit link to `explanation-type-fidelity` |
| `how-to/web-api.rst` | "Handle a client disconnect" opened by naming a Starlette source file and function. Third-party internals in a how-to. | Reduced to the observable behaviour |

Explanation pages (`semantic-views.rst`, `type-fidelity.rst`) were checked for
step-by-step instructions and contain none. They link out for action items correctly.
No structural blur requiring a page split was found.

### Terminology (Pass 1)

| Term | Before | After | Authority |
|------|--------|-------|-----------|
| pandas | `Pandas` (4, incl. 2 headings) | `pandas` | Project's own branding; dominant form in these docs |
| polars | `Polars` (4, incl. 2 headings) | `polars` | As above |
| PyArrow | `pyarrow` in prose (9) | `PyArrow` | Project's own capitalization; ``pyarrow`` retained in literals, module paths, extra names |
| -ize/-ise | `materialise`, `normalised`, `serialisation`, `specialised`, `unrecognised`, `recognise` (12) | `-ize` forms | Oxford spelling; `serialize`/`serialization` already dominant (22 uses) and is a page title and filename |
| behaviour | `behavior` (2) | `behaviour` | Oxford spelling; `behaviour` already dominant (5 uses) |

The page set had been mixing American `-ize` with British `-ise` and `-our`
inconsistently. Standardising on Oxford spelling (`-ize` + `-our`) preserves the
existing `serialization.rst` filename and page title while making the rest consistent.

Concept terminology was already clean and needed **no** changes: "semantic view"
(Snowflake/DuckDB) vs "metric view" (Databricks) is never crossed; "measure" is used
only for the warehouse-side concept and `Metric` only for the Semolina field;
"model" (a `SemanticView` subclass) and "DTO" (the Pydantic result class) are held
apart consistently; "engine" is used uniformly for the registered object.

`.doc-writer/terminology.yaml` was regenerated. The previous version listed
`pool_from_config`, which no longer exists in `config.py` (removed by the v0.6
engine-owns-pool change), and had no entries for the async surface.

### Reference accuracy

| Page | Issue | Action |
|------|-------|--------|
| `reference/config.rst` | `pool_size` documented as "default 5" in Common fields; `DuckDBConfig.pool_size` defaults to **1**. | Annotated "(DuckDB: 1)" |
| `reference/config.rst` | `pre_ping` exists on all three config classes and was undocumented. | Added |

### Coverage gaps (cheap cross-references added)

From `.doc-writer/gap-report.md`. No new pages were written; each is a one-sentence
addition to an existing page.

| Symbol | Placed in | Why there |
|--------|-----------|-----------|
| `Predicate` | `how-to/filtering.rst` intro | The page teaches filtering but never named the type a reader would annotate against |
| `Dialect` | `how-to/backends/overview.rst` | Names the enum behind the TOML `type` field, at the point `type` is first explained |
| `SemolinaMissingDependencyError` | `tutorials/installation.rst` extras section | The one place a reader learns what happens if an extra is missing |
| `SnowflakeEngine` / `DatabricksEngine` / `DuckDBEngine` | `how-to/connection-pools.rst` | Names what `create_engine()` returns, and directs type annotations at `Engine` instead |

The `reference-cli` label existed but was linked from nowhere; added to
`how-to/codegen.rst` "See also".

Still uncovered and **not** fixed (would need new prose, which is the Author's call):
`DialectABC` (the custom-dialect extension point) has no narrative entry at all.

### Other

- `how-to/warehouse-testing.rst` documents `engine._pool`, a private attribute, while
  `how-to/connection-pools.rst` warns readers not to touch it. Added a note scoping
  the usage to test fixtures and pointing at `dispose()`. **The underlying API gap is
  real and needs author judgement** — see below.
- `how-to/models.rst`: *"This guarantee ensures models stay consistent across the
  lifecycle of a query"* — vague attribution. Rewritten to state the actual guarantee.
- `how-to/arrow-output.rst`: *"Reach for these two when the table is"* — ambiguous
  referent. Named the two functions.
- `tutorials/first-query.rst`: the DuckDB tip told readers to install the
  `semantic_views` extension, while the script immediately below installs it and
  `how-to/backends/duckdb.rst` says `create_engine()` auto-installs it. Reworded.
- `index.rst` tagline was 148 characters and mildly promotional; tightened and
  rewrapped. Nine other prose lines over 100 characters were rewrapped. URLs and
  verbatim error-message code blocks were left long deliberately.

---

## NITPICK

- **Fixed:** `how-to/streaming.rst` had two section headings using *single* backticks
  (`` `for row in cursor:` ``). With no `default_role` set in `conf.py`, single
  backticks are `title-reference` and render as *italics*, not code. Changed to double
  backticks. No `:ref:` label or internal link pointed at either heading, so no target
  was broken.
- **Fixed:** `how-to/streaming.rst` linked `pyarrow.parquet.ParquetWriter` as a
  `:py:class:`. Third-party symbol with no intersphinx mapping, so it could never
  resolve. Demoted to inline literal, per the cross-reference rule's third-party
  skip-list.
- **Fixed:** `tutorials/first-query.rst` "See also" cards used Title Case ("Defining
  Models", "Building Queries") against sentence case everywhere else, including the
  equivalent cards on `index.rst`. Normalised.
- **Fixed:** 12 literal em dashes (`—`) replaced with commas, colons, semicolons, or
  sentence splits. The rest of the corpus uses the reST `--` convention, so these were
  both a humanizer issue and a rendering inconsistency. Zero remain.
- **Not fixed:** `how-to/backends/duckdb.rst` is wrapped at roughly 55 characters while
  every other page wraps near 80. Cosmetic; reflowing it would produce a large diff
  with no reader-visible change.

---

## Needs author judgement — NOT fixed

1. **`private_key_path` key format.** `reference/config.rst` says "PKCS1 or PKCS8";
   `how-to/codegen-credentials.rst` says "PKCS8". The field belongs to adbc-poolhouse,
   so I could not settle it from Semolina's source and did not want to guess. One of
   the two is wrong.

2. **Duplicated "Inspect generated SQL" section.** `how-to/queries.rst` (label
   `howto-inspect-sql`) and `how-to/warehouse-testing.rst` (label
   `inspect-generated-sql`) carry near-identical content under two labels. Neither
   label is referenced from anywhere. Consolidating means deleting one and picking a
   surviving label — a content decision, not an editing one.

3. **No supported hook for a per-connection seed listener.** `warehouse-testing.rst`
   must reach into `engine._pool` to attach a SQLAlchemy `connect` listener, because
   `Engine` exposes no public accessor. The docs cannot be made clean here without an
   API addition. Flagging rather than papering over it.

4. **Snowflake codegen "required" fields.** The docs assert `warehouse` and `database`
   are required for Snowflake codegen. At the config level only `account` is required
   (`SnowflakeConfig.model_fields`); the failure is deferred to query execution. The
   docs' framing is *practically* right and I made it consistent across pages, but the
   claim is not enforced where the docs imply it is.

5. **Version string will drift.** `tutorials/installation.rst` shows `0.6.0` as the
   expected output of `semolina.__version__`. Correct against `pyproject.toml` today;
   it silently rots at the next release. Consider `|release|` substitution.

### Observations, no action requested

- `_Query.using()`'s parameter is still named `pool_name` in `query.py:308`, and its
  docstring says "Select pool for this query by name", while every doc page calls it
  an engine name. The docs are right for the v0.6 model; the source lags. Not a docs
  defect, but the drift will surface in the autoapi reference.
- `.doc-writer/page-inventory.md` is stale in the same way the old terminology map was:
  it describes pools replacing engines and lists `get_pool`, `MockEngine`,
  `MockDialect`, and a proposed `explanation/connection-architecture.rst` that does not
  exist. Worth regenerating or deleting so it does not mislead a future run.
- `conf.py` does not set `nitpicky = True`. Turning it on is the single highest-value
  change available here: it is what makes finding #1 impossible to reintroduce.

---

# Round 2

**Trigger:** two persona-test agents found content defects that the four editing
passes structurally could not catch. Passes 1–4 check terminology, page type, prose
register, and link integrity — none of them asks *"is the documented pattern one that
can actually happen at runtime?"* Every defect below is of that kind: correct reST,
correct terminology, correct Diataxis placement, and wrong about the library.

All six were applied. Facts were supplied pre-verified by the coordinator and were not
re-derived; two supporting details were checked directly because they had to be written
into example code (see "Verified during Round 2" below).

`just docs-build` passes. `sphinx-build -n -W --keep-going` still reports zero warnings
on hand-written pages, and no `:ref:` target is broken.

| Severity | Count | Fixed |
|----------|-------|-------|
| BLOCKING | 4 | 4 |
| SUGGESTION | 4 | 4 |

## BLOCKING

### R2-1. `web-api.rst` "Handle errors" documented a pattern that cannot fire — FIXED

The section told readers to catch `SemolinaConnectionError` and
`SemolinaViewNotFoundError` around `.execute()`, and to map the latter to a 404. Both
exceptions are raised **only** inside `introspect()` — the codegen path.
`Engine.execute()` catches `BaseException` solely to return the connection to the pool
and re-raises unchanged, and `AsyncEngine.aexecute()` mirrors it. The documented
`except` clauses are unreachable on the query path, so a reader following this page
shipped an error handler that silently never runs and returned 500 for a missing view.

Rewritten to describe what actually arrives: `adbc_driver_manager.Error` and its DBAPI
subclasses. Added:

- A worked example catching `OperationalError` / `ProgrammingError` / `Error`, with the
  honest caveat that *which* subclass appears is the driver's choice and varies across
  Snowflake, Databricks, and DuckDB — so `Error` is the backstop.
- A warning that **a missing view is not a 404**: no exception type carries that
  meaning on the query path, and the remedy is to validate view names against a list
  the application controls rather than pattern-matching driver messages.
- A note redirecting `SemolinaViewNotFoundError` / `SemolinaConnectionError` to
  `introspect()` and codegen, where they do fire.
- The "no common `SemolinaError` base class" rationale, surfaced as user-facing prose.
  It previously existed only in the `exceptions.py` module docstring, so a reader
  looking for one `except` clause had no way to learn why there isn't one.

The false "Both apply to `aexecute()` as well" claim is gone; the async path now
correctly points at the same driver exceptions.

### R2-2. Result column keys are warehouse-native — most pages implied otherwise — FIXED

`row.revenue` works on DuckDB and raises `AttributeError` on Snowflake and Databricks.
Semolina emits no `AS` aliases and does no case folding, so keys are the driver's
verbatim column names. Only `typed-results.rst` documented this; every other page
presented the DuckDB spelling as universal — which is exactly why the failure lands at
deployment rather than in development.

Added `.. _howto-result-column-names:` to the canonical section in
`typed-results.rst` so the constraint has one address, then added a warning plus
cross-reference at the first point of attribute/dict access on each affected page:

| Page | Placement |
|------|-----------|
| `tutorials/first-query.rst` | Step 4, immediately after both access styles are shown |
| `how-to/queries.rst` | "Execute and read results" |
| `how-to/serialization.rst` | First `dict(row)`, plus the concrete Snowflake key spelling |
| `how-to/web-api.rst` | First endpoint, framed as "these keys become your response body" |
| `how-to/backends/snowflake.rst` | Example rewritten to `row["COUNTRY"]`, `row['AGG("REVENUE")']` |
| `how-to/backends/databricks.rst` | Example rewritten to `row["country"]`, `row["measure(revenue)"]` |

The two backend pages had their examples corrected outright rather than annotated,
because a page titled "How to connect to Snowflake" showing code that fails on
Snowflake is the sharpest form of the defect. Examples elsewhere were left alone per
instruction; the constraint is now impossible to miss once per page.

### R2-3. `serialization.rst` showed `json.dumps(dict(row))` succeeding on money — FIXED

A decimal metric arrives as `decimal.Decimal`, which the standard JSON encoder refuses
with `TypeError`. The page showed the pattern working and never mentioned it. Since
codegen annotates metrics `decimal.Decimal | None`, this is the common case, not an
edge case.

Rewrote the section to show the `TypeError` first, then a working `default=` encoder
handling `Decimal` and `date`/`datetime`. Stated the trade-off honestly rather than
picking for the reader: `str()` keeps every digit but sends a JSON string, `float()`
gives a JSON number and silently loses precision beyond ~15 significant digits —
"a chart axis can take the float; a ledger total cannot." Added a tip that Pydantic
handles `Decimal` natively, so `into()` avoids the encoder entirely, and linked
`explanation-type-fidelity` for which columns are affected.

Also corrected the downstream claim that the list-of-dicts pattern "works directly
with FastAPI's `JSONResponse`" — it fails there for the same reason.

### R2-4. Codegen TOML section mismatch broke the documented sequence — FIXED

`create_engine()` defaults to `[connections.default]`; codegen reads
`[connections.<backend>]`. A reader who followed a backend page to write
`[connections.default]` and then ran `semolina codegen --backend snowflake` got exit 2
on a file they had just been told was correct.

- `reference/config.rst`: new "Which section is read" table contrasting the two rules.
- `how-to/codegen.rst`: warning naming the required section per backend.
- `backends/snowflake.rst`, `backends/databricks.rst`, `backends/duckdb.rst`: note at
  the point each page tells the reader to write `[connections.default]`.
- `codegen-credentials.rst`: the opening claim that codegen "reads the **same
  connection config as your application engines**" was itself the misleading part —
  same *file*, different *section*. Rewritten, with a warning that a default-only file
  is sufficient for the app and insufficient for codegen, and a note that the two
  sections can legitimately hold different credentials (codegen under a read-only role).

## SUGGESTION

### R2-5. `models.rst` annotations contradicted codegen and `--check` — FIXED

The page teaches with `Metric[float]()` while every other page and codegen itself use
`Metric[decimal.Decimal | None]()`. Because `--check` compares annotation strings for
equality, a hand-written `float` on a decimal column reports drift.

Added a note preserving the page's simple pedagogy: `float` is used for brevity, codegen
writes `decimal.Decimal | None` (`Decimal` because that is the value you get, `| None`
because a metric over an empty group is null), and `--check` compares exactly. The
teaching examples were **not** mass-rewritten.

Kept the distinction the coordinator flagged: `.into(DTO)` is a separate mechanism, and
a hand-authored `float` there is honoured as a deliberate narrowing under
`validate=True`. The note says so explicitly so the two are not conflated. Added
`howto-codegen-check` and `explanation-type-fidelity` to the page's "See also".

### R2-6. Pagination has no `offset()` and no page said so — FIXED

`.limit(n)` is the only row-count control; there is no `offset()`, so `LIMIT`/`OFFSET`
pagination cannot be expressed. Added a note to both pages that document `.limit()`
(`queries.rst`, `ordering.rst`) stating the absence plainly and pointing at keyset
pagination as the available approach — order by a key, take a page, filter past the last
key seen. Noted that on an aggregate query this is usually cheaper than `OFFSET`, since
the warehouse never computes the discarded groups.

### R2-7. The pool checkout timeout exception is now named — FIXED (verified directly)

The coordinator asked me to say so in the report if I could not verify this. **I could
verify it**, so it is documented rather than deferred. See below for method.

The exception is `sqlalchemy.exc.TimeoutError`, and the trap is that it derives from
`SQLAlchemyError`, **not** from the builtin `TimeoutError` — so `except TimeoutError:`
does not catch it. Documented in three places:

- `connection-pools.rst`: warning after the pool-sizing table, with the import and a
  503 mapping.
- `web-api.rst`: added to the error-handling section, framed as the clearest 503 signal
  available because it means the pool is undersized rather than the warehouse being down.
- `reference/config.rst`: the `timeout` field now names what it raises.

### R2-8. Line-length regressions from the Round 1 reference rewrite — FIXED

Lengthening 131 cross-reference targets pushed six prose lines past 100 characters.
Rewrapped. The only remaining long lines are inside a verbatim error-message code block
in `typed-results.rst`, which must stay byte-exact.

## Verified during Round 2

Two facts were checked directly, because both had to be written into example code and
a wrong import or class name would have reproduced the very class of defect this round
exists to fix:

1. **ADBC exception hierarchy**, from `adbc_driver_manager`: `Error` → `DatabaseError`
   → {`ProgrammingError`, `OperationalError`, `DataError`, `IntegrityError`,
   `InternalError`, `NotSupportedError`}, with `InterfaceError` directly under `Error`.
2. **Pool checkout timeout**, by constructing a `QueuePool(pool_size=1, max_overflow=0,
   timeout=1)` and exhausting it: raises `sqlalchemy.exc.TimeoutError`, MRO
   `TimeoutError → SQLAlchemyError → HasDescriptionCode → Exception`. Also confirmed
   that `AsyncPool.connect()` offloads the *same* inner `QueuePool.connect` to a worker
   thread, so the timeout and its exception apply on the async path too — the
   `anyio.CapacityLimiter` is an additional concurrency bound, not a replacement.

## Could not verify

Nothing in Round 2 was left unverified. One item is a deliberate judgement call rather
than a fact gap: **which ADBC subclass corresponds to which failure** is driver-specific
and was not exhaustively mapped across Snowflake, Databricks, and DuckDB. Rather than
publish a table that might be wrong for one backend, the guide tells readers to catch
`Error` as a backstop and log the message. A per-driver mapping would be worth adding
once someone has observed all three.

## Folded in, not fixed

- **`nitpicky = True` is not currently viable.** Measured at 75 warnings, all from
  `reference/api/`, none from hand-written pages — which independently confirms the
  Round 1 rewrite of 131 references is complete. Enabling it needs a
  `nitpick_ignore_regex` covering ~67 third-party, TypeVar, and private targets, plus
  ~8 genuinely broken references inside `src/` docstrings
  (`semolina.SemolinaSchemaMismatchError`, `WarehouseConfig`, `Engine`,
  `semolina.reset`). Those eight are a source change and out of scope here, but they
  are real defects in the API reference and worth a follow-up.
- **PKCS1/PKCS8** was resolved by the coordinator against
  `adbc_poolhouse/_snowflake_config.py:51-56`: `private_key_path` accepts PKCS1 or
  PKCS8, and only inline `private_key_pem` is PKCS8-only. `reference/config.rst` was
  already correct; `codegen-credentials.rst` was corrected. Removing this from the Round
  1 "needs author judgement" list leaves four open items there.

## Structural observation

Four of six Round 2 defects share one root cause: **the docs were written and tested
against DuckDB, and DuckDB is the only backend whose behaviour is forgiving.** It
lowercases column names, so `row.revenue` works. It is the tutorial backend, the testing
backend, and the backend the examples were validated against. Snowflake and Databricks
each break the same code differently.

`typed-results.rst` already says this ("Write the aliases for the warehouse you deploy
against, not the one you develop against"), and it is the one page that got it right.
The observation is worth promoting somewhere more prominent than a mid-page paragraph —
a short "developing on DuckDB, deploying elsewhere" explanation page would give every
how-to a single place to link. That is a new page, so it is the Author's call, not mine.
