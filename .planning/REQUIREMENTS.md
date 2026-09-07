# Requirements: Semolina v0.7 — Async & Typed Results

**Defined:** 2026-08-01
**Core Value:** A single, Pythonic query API that works identically across Snowflake, Databricks, and DuckDB semantic views, with typed models, IDE autocomplete, and backend-agnostic code.

**Milestone goal:** Give Semolina a non-blocking async query surface and an honest, verified type story running from warehouse metadata through to Pydantic DTOs.

**Extended 2026-09-07:** the milestone now also carries a hardening pass (Phases 51-57)
found by a pre-release codebase review. v0.7 ships once both halves are done, as the single
tag `v0.7.0`. Nothing here is deferred to a v0.8.

## v0.7 Requirements

### Async Query Surface

- [x] **ASYNC-01**: User can `await engine.aexecute(query)` to run a query without blocking the event loop, getting back the same result surface as `.execute()`
- [x] **ASYNC-02**: User can `await Sales.query().metrics(...).aexecute()` — an async twin of `.execute()` on the query builder
- [x] **ASYNC-03**: User can `async for row in result` to stream rows lazily, with batches fetched off-thread by adbc-poolhouse and mapped to `Row` by Semolina
- [x] **ASYNC-04**: User installs async support via a `semolina[async]` extra that pins `adbc-poolhouse[async]>=1.6.2`; the default sync install gains no new dependencies. *(Amended from `>=1.5.0` on evidence, Phase 46 Plan 01: the `_resolve_tuning` helper that makes `create_async_pool` honour the config's own `pool_size` landed in adbc-poolhouse 1.6.0, so 1.5.x would silently build a five-connection pool for `DuckDBConfig(database=":memory:", pool_size=1)`. Amended again from `>=1.6.1` during Plan 05: 1.6.1's cancel path ran poison-recovery without waiting for the aborted worker to unwind, deadlocking the DuckDB driver; fixed in 1.6.2 via anentropic/adbc-poolhouse#43, and ASYNC-06 cannot hold below it.)*
- [x] **ASYNC-05**: User's async code runs identically under asyncio and Trio — Semolina library code contains zero `asyncio.*` references and no anyio import, verified by an automated check
- [x] **ASYNC-06**: User cancelling an in-flight async query (framework timeout or task cancellation) causes the underlying warehouse query to be cancelled via `adbc_cancel`, not merely abandoned

### Warehouse Type Fidelity

- [x] **TYPE-01**: Maintainers have an empirical comparison, per backend, of introspection-time field types against query-time `adbc_execute_schema` result types, run over existing Snowflake cassettes and jaffle-shop DuckDB
- [x] **TYPE-02**: The project has a committed type-mapping decision doc covering the Decimal policy, the metric-nullability stance, and which source of truth codegen uses (probe vs metadata)
- [x] **TYPE-03**: User generating models for decimal-typed warehouse columns gets an annotation naming the type that backend's own driver returns — `decimal.Decimal` on Snowflake and DuckDB, whose drivers deliver `decimal128`, and `str` on Databricks, whose driver delivers an Arrow string. One rule across all three backends, so no generated model can claim a type its driver never produces. *(**Reworded 2026-08-16** on measurement. The original wording ended "applied consistently across Snowflake, Databricks, and DuckDB — the three backends no longer disagree about money", which a live Databricks probe falsified: the Foundry ADBC driver returns every decimal as an Arrow string, at any precision and scale including 0. The requirement was not reopened, because the defect it was written against is fixed and stays fixed. Before Phase 48 the three backends gave three arbitrary answers — `int`/`float` on Snowflake, `float` on Databricks, `TODO:` on DuckDB — and not one described the value that arrived. Uniformity was the evidence that the underlying rule held while all three drivers behaved alike; it was never the property being bought. Rewording states the property directly, so the requirement stays true when a driver differs and would go false if a generated model started lying — which is the failure anyone reading TYPE-03 actually cares about. Pinned by `tests/unit/codegen/test_type_map.py::test_decimal_annotation_follows_each_driver`, which asserts the two agreeing backends do not drift apart, that Databricks diverges deliberately, and that no backend emits a `TODO:`. The Databricks answer reverts to `decimal.Decimal` if its driver gains native decimals — see WINDOWS.md entry 18 for the dated route.)*
- [x] **TYPE-04**: User generating models gets metric annotations whose nullability reflects the decision doc's stance (metrics are NULL on empty groups)
- [x] **TYPE-05**: User generating models for the category-1 map gaps — DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS` and Databricks `interval` — gets a concrete Python type rather than a `TODO:` placeholder. *(Recorded Partial at Phase 48 close on 2026-08-13: the DuckDB half was proved by `isinstance` against measured values, and Databricks `interval` still emitted `TODO:` because no fixture, cassette, or recording here contained an interval column, so a `datetime.timedelta` guess was implemented and then reverted rather than shipped unmeasured. **Earned on 2026-08-16 by live measurement** against a Databricks workspace: an `INTERVAL DAY TO SECOND` arrives over the Foundry ADBC driver as the Arrow string `'3 04:05:06.789000000'` and an `INTERVAL YEAR TO MONTH` as `'2-6'`, so both families map to `str` and neither emits a `TODO:`. Phase 48's expectation that the year-month family was unmappable **in principle** — a month has no fixed length, so no stdlib duration type describes one — was sound reasoning that turned out not to be what the question depended on: no duration ever arrives to be described. Nor is this a driver quirk a better driver would fix: the Databricks Thrift negotiation struct `TSparkArrowTypes` has no interval member at all, and `databricks-sql-connector` returns the same string off the same protocol, so interval-as-string is the wire format. Reproduce with `.planning/phases/48-type-map-implementation-databricks-literals/verify_databricks_types_live.py`. WINDOWS.md entry 7 closed with it, and the pending recording todo is completed.)*
- [x] **TYPE-06**: User generating models for a VARIANT-typed column gets a `JsonValue` union annotation rather than `Any`
- [x] **TYPE-07**: User can verify that a model's committed annotations still match the warehouse's current result schema via a `--check` mode, without executing a query for rows

### Typed Results (`.into(DTO)`)

- [x] **DTO-01**: User can call `.into(MyDTO)` on a query result to get Pydantic v2 model instances, converted from Arrow by arrowmodel and matched by column name
- [x] **DTO-02**: User streaming a large result can consume DTOs per batch, including from an async result via `async for`, without materializing the whole table
- [x] **DTO-03**: User whose DTO does not match the result schema gets a clear, actionable error naming the mismatched field, rather than a silent wrong-typed value
- [x] **DTO-04**: User can call `.into(DTO)` against an untyped or partially-typed model — conversion works off the Arrow result schema, never requiring typed model fields
- [x] **DTO-05**: User installs DTO support via an optional `semolina[arrowmodel]` extra; the default install does not pull arrowmodel or its Rust extension. *(Amended 2026-08-13, before planning: the original wording also promised the default install does not pull **pydantic**. It always has — `semolina` → `adbc-poolhouse` → `pydantic-settings>=2.0.0` → `pydantic>=2.7.0`, an unconditional chain since v0.3 — so pydantic cannot be gated behind this extra without dropping a base dependency, which is out of scope here. The extra gates arrowmodel alone.)*
- [x] **DTO-06**: Docs present `.into(DTO)` as the primary typed-result path, with a worked BI-backend example covering both the whole-table and streaming forms

### Codegen'd DTOs

- [x] **DTO-07**: User can generate a typed DTO class from a canonical query, with annotations derived from `adbc_execute_schema` rather than from declared model field types. *(Complete after Phase 50. Earned by plans 50-01 through 50-07 collectively, not by 50-01 alone, which ticked it early because six of the phase's eight plans share the ID — see 50-01-SUMMARY.md § "Next Phase Readiness". The pipeline is proven end to end on a live DuckDB backend through the published `semolina codegen-dto` command, and no declared model field type is read anywhere in the renderer. One evidence limit was recorded as WINDOWS.md entry 12 rather than as a partial: the Snowflake and Databricks result-column spellings the generated aliases bind through were pinned against this repo's own recordings, not read off a live warehouse. **Both halves were probed live on 2026-08-15/16 and the limit paid out.** Databricks matched exactly, including for a metric name requiring backticks. Snowflake did not: it upper-cases the identifier inside the quotes when labelling a result column, so a metric stored as `gross revenue` comes back as `AGG("GROSS REVENUE")` — gap `G-50-2`, fixed test-first in `SnowflakeDialect.metric_result_column_name`. The requirement stays Complete because the failure was loud (`_alias_for` raises, CLI exits 6, no mis-bound DTO reaches a user) and is now corrected against measurement; what remains is the narrower residual in WINDOWS.md entry 15.)*
- [x] **DTO-08**: User gets real IDE autocomplete and type checking on `.into(GeneratedDTO)` results — the generated class passes basedpyright strict. *(Complete after Phase 50, and proved under a configuration stricter than this repo's own: a dedicated `pyrightconfig.json` at `typeCheckingMode = "strict"` with no rule suppressions, measured on `summary.errorCount` rather than an exit code, with a negative control that trips a rule `pyproject.toml` disables. `.into(GeneratedDTO)` is proven to type as `list[GeneratedDTO]` by an `assert_type` twin whose diagnostic prints the inferred type. Two limits worth reading before trusting the wording: mypy is never run, and an unmapped Arrow type's `Any` annotation passes strict because `Any` passes everything — `reportAny` lives in basedpyright's `all` mode, not `strict` — so the generated `# TODO:` comment beside it is the real signal, which `docs/src/how-to/dto-codegen.rst` § "Replace the Any annotations" says in the user's own words.)*
- [x] **DTO-09**: User running codegen against a driver that does not implement `adbc_execute_schema` gets a working fallback (zero-row execution) rather than a hard failure. *(Recorded Partial at Phase 50 close on 2026-08-15 — proved as a branch, on a live DuckDB cursor monkeypatched to refuse, and never as a backend. **Earned on 2026-08-15 by live measurement**, during Phase 50 UAT test 5, against the Databricks workspace: `cursor.adbc_execute_schema(sql, [])` raised `NotSupportedError` from the Foundry driver — a genuine refusal, not a simulated one — `probe_schema` fell through and returned `route='zero-row'`, `codegen-dto` emitted a class whose header records `dialect: DatabricksDialect, probe route: zero-row`, and that class round-tripped through `.into()` for 2 rows. **RESEARCH assumption A2 is CONFIRMED**: the Databricks metric-view planner accepts `SELECT * FROM (<MEASURE… GROUP BY ALL>) WHERE 1=0`, so the escalation branch — "Databricks has neither ExecuteSchema nor a working fallback" — did not occur. Reproduce with `.planning/phases/50-codegen-d-typed-dtos/verify_databricks_live.py`. WINDOWS.md entry 12 closed with it.)*

### Result Conversion

- [x] **RESULT-01**: User can call `fetch_df()` on a cursor to get a `pandas.DataFrame` and `fetch_polars()` to get a `polars.DataFrame`, on both the sync and async cursor
- [x] **RESULT-02**: User without pandas or polars installed gets an actionable error naming the missing package, not an `ImportError` traceback from internals

### Databricks Literals

- [x] **DBX-04**: User can filter a Databricks query on a `date`, `datetime`, or `Decimal` value — `render_literal` inlines them correctly instead of raising `NotImplementedError`

### Tooling

- [x] **TOOL-01**: Maintainers have `git.branching_strategy` restored to `milestone` in `.planning/config.json`, reverting the temporary `none` set during v0.6

## v0.7 Hardening Requirements

**Added 2026-09-07** from `.planning/research/2026-09-06-CODEBASE-REVIEW.md`. The milestone
was verified complete on 2026-08-16 and then reviewed before tagging; the review reproduced
defects across the query builder, the result objects, codegen and the release pipeline.
These close in v0.7 rather than a follow-up milestone, so the first tagged release carries
none of them. Finding numbers in parentheses (A-, CI-, C-) refer to that document.

**What is free and what is not.** `0.6.0` is published on PyPI (2026-06-25); phases 46-50
are not. So every fix touching `.into()`, `iter_into()`, `codegen-dto`, `--check`, the async
cursor or `fetch_df`/`fetch_polars` changes a surface no user has, and needs no deprecation
path. Seven requirements touch surface published in `0.6.0` and are marked
**[0.6-visible]**. Five are bug fixes whose current behaviour is silently wrong (CORE-05,
CORE-10, ALIAS-01, FILT-01, FILT-02); two are deliberate API changes — API-04 keeps the old
name as an alias, and API-06 does not and is the only item here that can break a working
install. All seven earn a changelog entry in Phase 57; none needs a compatibility shim.

**Working rule:** failing test first, then the fix, in separate commits (CLAUDE.md). Where a
finding says "silently", the test asserts the loud behaviour — an exception type and message
— not merely the absence of the old bug.

### Release & CI Gates

- [x] **REL-01**: Pushing a tag `vX.Y.Z` whose version differs from `semolina.__version__` fails the release workflow before `uv build`, naming both values (CI-1)
- [x] **REL-02**: The release `publish` job runs only after the CI workflow is green on the tagged commit (CI-1)
- [x] **REL-03**: CI triggers on `pull_request` as well as `push`; the coverage comment runs on PRs; a `[tool.coverage.report] fail_under` is enforced and the coverage XML is uploaded (CI-4)
- [x] **REL-04**: The strict docs build (`sphinx-build -W`) runs in `ci.yml` on every push and PR, not only after merge to main (CI-5)
- [x] **REL-05**: `just test` installs the same extras and selects the same jaffle-shop markers as CI, so local and CI skip counts match; `MAINTAINER.md` states what `just test` needs (CI-2)
- [x] **REL-06**: The scope-fence test skips with a message on a shallow clone outside CI instead of failing (CI-3)
- [x] **REL-07**: The pre-commit `ruff` hook version equals the `ruff` version in `uv.lock` (CI-7)
- [x] **REL-08**: CI exercises every supported minor (3.11-3.14) or documents which are skipped and why; `.python-version` names a released interpreter (CI-6)

### Core Object Semantics

- [ ] **CORE-01**: `Row` round-trips through `copy.copy`, `copy.deepcopy` and `pickle`; is hashable when its values are; has `.get()`; and is registered as `collections.abc.Mapping` (A15, A21)
- [ ] **CORE-02**: A column whose name collides with a `Row` method (`items`, `keys`, `values`, `get`) is reachable via item access, and the rule is documented (A21)
- [ ] **CORE-03**: Field membership and `OrderTerm`/`Query` equality compare field identity, never `Field.__eq__`; the tautological metric-tuple assertions in `tests/unit/test_query.py` are replaced by assertions that fail on the wrong field (A2)
- [ ] **CORE-04**: Subclassing a `SemanticView` model either works (fields inherited, child overrides parent, `abstract = True` bases with no `view=`) or raises a clear "not supported" error — decided at D1, never the current `AttributeError` (A3)
- [ ] **CORE-05** **[0.6-visible]**: `in_()` materialises its argument, raises `TypeError` for `str`/`bytes`, accepts a generator, and the compiled placeholder count always equals the parameter count. Today `in_("US")` runs and returns wrong rows (A1)
- [ ] **CORE-06**: `Engine.execute()` and `AsyncEngine.aexecute()` raise `ValueError` on an empty query, never `AssertionError` (A8)
- [ ] **CORE-07**: Sync `close()` returns the pooled connection even when `cursor.close()` raises, and `__exit__` never masks the body's exception — mirroring `aclose()` (A20)
- [ ] **CORE-08**: Mixing `for row in cursor` with `fetchall_rows()` on one cursor raises a Semolina error naming both calls, on both cursors; the `acursor.py` class docstring no longer claims this needs cross-task sharing (A16)
- [ ] **CORE-09**: Every row-fetching method on the sync cursor raises `SemolinaMissingDependencyError` naming the `pyarrow` extra when pyarrow is absent, matching the async cursor; the `snowflake`/`databricks` extras either compose `semolina[pyarrow]` or the docs say the row API needs it (A17)
- [ ] **CORE-10** **[0.6-visible]**: Selecting the same field twice raises `ValueError` in the builder, and `Row` construction raises on duplicate column names instead of keeping the last value (A18)
- [ ] **CORE-11**: `.into()`'s fast-path schema check rejects a `timestamp` column into a `date`-annotated field (A19)
- [ ] **CORE-12**: The dead `pool` constructor argument is removed from both cursors; sync `fetch_record_batch()` records its reader and `close()` closes it (A22)

### Portable Result Column Names

- [ ] **ALIAS-01** **[0.6-visible]**: The same query yields result keys equal to the Python field names on Snowflake, Databricks and DuckDB, proven by re-recorded cassettes and live DuckDB. Today `row.revenue` raises on two of the three backends (C1)
- [ ] **ALIAS-02**: A DTO written with plain field names converts on all three backends without `validation_alias` (C1)
- [ ] **ALIAS-03**: `codegen-dto` no longer emits backend-specific aliases; its output for one query differs across backends only where driver types genuinely differ (C1)
- [ ] **ALIAS-04**: README, `how-to/queries.rst` and `how-to/typed-results.rst` examples run unchanged against Snowflake; the "Column keys are whatever your warehouse called them" warning is gone (C1)
- [ ] **ALIAS-05**: The DuckDB builder no longer silently widens the projection for a metric used only in `order_by`/`where`; it behaves as the other dialects do after D4 (A7)

*No compatibility shim is required for the DTO half: `.into()` and `codegen-dto` are Phase 49/50 surfaces and have never been released, so no published DTO carries an `AGG("REVENUE")` alias.*

### Filter Semantics

- [ ] **FILT-01** **[0.6-visible]**: `field == None` compiles to `IS NULL` and `field != None` to `IS NOT NULL`; `between()` with a `None` bound raises `TypeError` pointing at `.isnull()` — per D3. Today these compile to `= NULL` and match nothing (A5)
- [ ] **FILT-02** **[0.6-visible]**: `startswith`, `istartswith`, `endswith`, `iendswith` and `iexact` escape `%`, `_` and the escape character and emit an `ESCAPE` clause per dialect; `like`/`ilike` pass patterns through and say so; Databricks backslash handling is tested (A4)
- [ ] **FILT-03**: `to_sql()` renders every literal through `dialect.render_literal`, so strings with apostrophes, dates, decimals and `None` produce valid SQL for the chosen dialect (A6)
- [ ] **FILT-04**: Filtering on a metric is either compiled to `HAVING` on Snowflake/Databricks and verified against a recording, or rejected at validation with a message; the tutorial's claim is made true or removed — per D4 (A7)
- [ ] **FILT-05**: `introspect()` quotes the view name via the dialect's identifier quoting on all three engines, DuckDB honours a schema prefix, and a view needing quoting round-trips through `semolina codegen` (A9)
- [ ] **FILT-06**: A dotted segment inside a pre-quoted view name raises; pre-quoted segments are escaped rather than emitted verbatim (A10)
- [ ] **FILT-07**: An identifier or `source=` containing `?` works on Databricks; the inliner tracks placeholder positions from compilation (A11)
- [ ] **FILT-08**: Introspect error mapping covers every `adbc_driver_manager.Error` subclass; DuckDB classification prefers the driver's error type over message substrings (A13)

### Codegen Hardening

- [ ] **GEN-01**: A column named `class`, `"ORDER DATE"` or `limit`, two columns folding to one name, or a view named `2024_sales` each produce a non-zero exit naming the offender and write nothing; rendered source is `ast.parse`d before emission on both commands (A24)
- [ ] **GEN-02**: A ruff formatting failure is reported on stderr rather than silently returning unformatted source; the test that pinned silent fallback is inverted (A24)
- [ ] **GEN-03**: A config `ValidationError` prints field names only, never `input_value`; a test asserts the password is absent from stderr (A25)
- [ ] **GEN-04**: Missing driver extras, unmapped `adbc_driver_manager.Error` subclasses and dotted `--backend` constructor failures map to documented exit codes; `codegen` and `codegen-dto` share one exception-to-exit table (A26)
- [ ] **GEN-05**: `> models.py` and `--output models.py` produce identical bytes and both pass `ruff format --check` (A27)
- [ ] **GEN-06**: `codegen` gains `--output`, writes atomically and only after every view rendered; `--check` no longer needs `--model` as a workaround (A29)
- [ ] **GEN-07**: Regenerating from two different working directories yields identical output (A28)
- [ ] **GEN-08**: `database = "~/x.db"` in `[tool.semolina.dto]` expands before joining; when `DUCKDB_DATABASE` overrides a committed value the CLI says which source won (A30, A31)
- [ ] **GEN-09**: `--check` reports no drift for an untyped `Metric()` and exits with a distinct code when the probe failed and it fell back to metadata (A32, A33)
- [ ] **GEN-10**: `cli/utils.py` dead functions and their tests are removed (A34)

### Public Surface & Packaging

- [ ] **API-01**: Builder methods carry real parameter types; a basedpyright negative-test file proves `.metrics(Sales.country)` and `.limit("10")` are reported as errors (A12, C2)
- [ ] **API-02**: `Query` is public (`_Query` kept as an alias for one release); `Query`, `Field`, `Engine`, `AsyncEngine`, `And`, `Or`, `Not`, `Lookup` are exported from `semolina`; every public module has `__all__`; `engines/__init__` exports `AsyncEngine` and both error classes (C3, C8)
- [ ] **API-03**: A `SemolinaError` base exists and every Semolina-raised error derives from it; `get_engine` raises a dedicated not-registered error; engine errors live in `exceptions.py` with re-exports left behind; `how-to/web-api.rst` is rewritten — per D5. Purely additive: existing `except SemolinaViewNotFoundError` keeps working (C4)
- [ ] **API-04** **[0.6-visible]**: The SQL-generation ABC is renamed `SQLDialect` so only one thing is called `Dialect`; `engines.sql.Dialect` and the `DialectABC` export keep working for one release; `to_sql()` with no argument uses the dialect of the engine named by `.using()` when registered — per D7 (C5)
- [ ] **API-05**: Sync/async naming has a stated rule, and either `adispose`/`aconnect` twins exist or the docs say why not (C6)
- [ ] **API-06** **[0.6-visible]**: `typer`, `rich` and `jinja2` move to a `[cli]` extra; a base install imports none of them; the console script prints the install hint when they are absent — per D6. This is the one change that can break a working `0.6.0` install (`pip install semolina && semolina codegen`), so it needs a prominent changelog entry (CI-9)
- [ ] **API-07**: `import semolina` no longer eagerly imports `config` (and thus pydantic-settings and SQLAlchemy); `create_engine`/`create_async_engine` resolve lazily under the same import path (CI-9)
- [ ] **API-08**: `src/semolina/conftest.py` moves to a root `conftest.py` that still covers `src/` doctests; empty `semolina.testing` is deleted; packaging-smoke asserts neither is in the wheel (CI-8)
- [ ] **API-09**: The dead `# type: ignore[reportPrivateUsage]` comments are removed and `reportUnnecessaryTypeIgnoreComment` is enabled (A14)
- [ ] **API-10**: Registry mutations are locked; a test registers and resets concurrently (A12 item 13)
- [ ] **API-11**: The docs site has the `/changelog/` page `pyproject.toml` advertises, and the 0.7.0 release notes list every **[0.6-visible]** change above (CI-13)

### Test-Suite Structure

- [ ] **TEST-01**: `tests/unit/test_engines.py` abstract-method tests fail if the method stops being abstract; the nonexistent `to_sql` test is removed (CI-14)
- [ ] **TEST-02**: Snowflake introspection has a recorded cassette; copied (unrecorded) cassettes are visibly marked in the test id or removed (CI-10)
- [ ] **TEST-03**: `test_type_fidelity_table.py` compares against an artifact under `tests/`, not `.planning/`; the DuckDB version stamp cannot fail the comparison on a pin bump; the duckdb-bump PR triggers CI (CI-11, CI-15)
- [ ] **TEST-04**: Wall-clock ratio tests in `test_async_cancel.py` run outside `-n auto` parallelism or carry loosened, reasoned margins; the per-worker extension `INSTALL` retries once (CI-12)
- [ ] **TEST-05**: `semolina-jaffle-shop/` is type-checked in CI with its own config (CI-15)
- [ ] **TEST-06**: Root markers `warehouse`/`snowflake`/`databricks` are used or removed

### Hardening Decisions (blocking checkpoints)

| # | Decision | Recommendation | Gates |
|---|----------|----------------|-------|
| D1 | Model inheritance: support or refuse clearly? | Support, with `abstract = True` bases | CORE-04 |
| D2 | Result aliasing strategy (which dialects alias, how DuckDB wraps) | Alias to Python field names everywhere; no shim needed | ALIAS-01..04 |
| D3 | `== None`: rewrite to `IS NULL` or raise? | Rewrite for `==`/`!=`; raise elsewhere | FILT-01 |
| D4 | Metric in WHERE: HAVING or reject? | Verify live first; HAVING if both warehouses accept it, else reject | FILT-04, ALIAS-05 |
| D5 | Introduce `SemolinaError` base? | Yes | API-03 |
| D6 | Move CLI deps to `[cli]` extra, breaking `0.6.0` CLI installs? | Yes, now — the cost only grows after the first tagged release | API-06 |
| D7 | Rename the ABC `Dialect` → `SQLDialect`? | Yes, alias kept one release | API-04 |

### Not planned in the hardening pass

| Item | Reason |
|------|--------|
| `.offset()` | The keyset-pagination rationale in `how-to/queries.rst` is sound |
| Changing the Databricks decimal-as-string or Snowflake `FIXED(…,0)` → `Decimal` policies | Documented, measured, consistent — see TYPE-03 |
| Replacing `adbc-poolhouse` as the hard dependency | Revisit only if API-07 does not keep the base import light enough |
| Any new query feature | Every item above closes a reproduced defect or a verified gap |

## Future Requirements

Deferred, tracked, not in this roadmap.

### Async

- **ASYNC-F1**: Posture B concurrency sugar — fan-out and timeout helpers that Semolina orchestrates, which would require taking an anyio dependency
- **ASYNC-F2**: Async introspection and codegen paths using poolhouse's async `adbc_get_objects` / `adbc_get_table_schema`

### Typed Results

- **DTO-F1**: Dynamic `create_model` DTOs built at runtime from `adbc_execute_schema` (arrowmodel "level 2")

### Streaming

- **STREAM-04**: User-controllable batch/chunk size for `fetch_record_batch()`, which currently relies on ADBC defaults

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dynamic `create_model` DTOs (arrowmodel level 2) | The only tier that would probe at runtime; codegen'd DTOs give better DX and IDE types |
| Databricks materializations as a DTO source | A transparent optimizer feature, not an introspectable per-query contract; one materialization backs many query patterns, and its schema is the rollup's, not a user query's result shape. Also Databricks-only |
| DTOs derived from the `SemanticView` model | A model is the superset of all dimensions and measures; a query returns a subset with query-specific types. One static DTO per view is wrong |
| Runtime type probes | Probes run at codegen and CI `--check` time only. `.into(DTO)` needs no probe — the executed result already carries its Arrow schema |
| anyio dependency in Semolina | Posture A keeps awaits neutral, which is Trio-compatible by construction. Adopt anyio only at the exact points Semolina composes concurrency |
| Native async I/O to the warehouse socket | The Python ADBC stack has no async C API. Thread-offload over GIL-releasing native calls is the mechanism; say so plainly rather than overselling |
| Partitioned reads (`adbc_execute_partitions`) | Driver-dependent intra-query parallelism; optional angle, not committed |
| FastAPI / Django / GraphQL integration packages | The async surface is a prerequisite for these; evaluate them as their own milestone once it lands |
| `GEOGRAPHY`/`GEOMETRY`, `VECTOR`, DuckDB `UNION` type mappings | No Python-native equivalent; `TODO` plus untyped fallback. Don't solve speculatively |

## Traceability

Which phases cover which requirements. Filled during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ASYNC-01 | Phase 46 | Complete |
| ASYNC-02 | Phase 46 | Complete |
| ASYNC-03 | Phase 46 | Complete |
| ASYNC-04 | Phase 46 | Complete |
| ASYNC-05 | Phase 46 | Complete |
| ASYNC-06 | Phase 46 | Complete |
| TOOL-01 | Phase 46 | Complete |
| TYPE-01 | Phase 47 | Complete |
| TYPE-02 | Phase 47 | Complete |
| TYPE-03 | Phase 48 | Complete — reworded 2026-08-16 from a uniformity claim to the rule it stood for: each backend's decimal annotation follows its own driver (`decimal.Decimal` on Snowflake/DuckDB, `str` on Databricks) |
| TYPE-04 | Phase 48 | Complete |
| TYPE-05 | Phase 48 | Complete — earned 2026-08-16 by live Databricks measurement: both interval families arrive as Arrow strings and map to `str`, so no category-1 type emits a `TODO:` (WINDOWS 7 closed) |
| TYPE-06 | Phase 48 | Complete |
| TYPE-07 | Phase 48 | Complete |
| DBX-04 | Phase 48 | Complete |
| DTO-01 | Phase 49 | Complete |
| DTO-02 | Phase 49 | Complete |
| DTO-03 | Phase 49 | Complete |
| DTO-04 | Phase 49 | Complete |
| DTO-05 | Phase 49 | Complete |
| DTO-06 | Phase 49 | Complete |
| RESULT-01 | Phase 49 | Complete |
| RESULT-02 | Phase 49 | Complete |
| DTO-07 | Phase 50 | Complete |
| DTO-08 | Phase 50 | Complete |
| DTO-09 | Phase 50 | Complete — earned 2026-08-15 by live Databricks measurement: the Foundry driver genuinely refused `adbc_execute_schema`, the zero-row route answered, and the generated class round-tripped through `.into()` (RESEARCH A2 confirmed; WINDOWS 12 closed) |

| REL-01..08 | Phase 51 | Complete — 2026-09-07, verified green on PR #41 |
| CORE-01..12 | Phase 52 | Pending |
| ALIAS-01..05 | Phase 53 | Pending |
| FILT-01..08 | Phase 54 | Pending |
| GEN-01..10 | Phase 55 | Pending |
| API-01..11 | Phase 56 | Pending |
| TEST-01..06 | Phase 57 | Pending |

**Coverage:** 86/86 v0.7 requirements mapped, each to exactly one phase — 26 feature
requirements across Phases 46-50 (all Complete), 8 hardening requirements in Phase 51
(Complete), and 52 hardening requirements across Phases 52-57 (Pending).
