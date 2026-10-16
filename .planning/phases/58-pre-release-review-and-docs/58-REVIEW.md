# Phase 58 — Pre-release review (REV-01)

Reviewed 2026-10-16 against `main` at 8825ed9 (everything since v0.6.1), by three Fable-model
Agent workers run in parallel, one per dimension: architecture, correctness and test coverage.
Each worker was read-only. Its full report follows, unedited, under its own heading below.

No blockers. 20 findings: 4 should-fix and 16 minor.

## Triage

"Proposed" is the disposition put to Anentropic. "Fix" means a test-first fix in Phase 58
(REV-02). "Limitation" means recording it as an accepted limitation, which needs Anentropic's
sign-off.

| ID | Sev | Finding | Proposed |
|----|-----|---------|----------|
| COR-1 | should-fix | A fact-only query groups on Snowflake/Databricks (`GROUP BY ALL`) but returns one row per source row on DuckDB | Fix: DuckDB groups too (outer `SELECT DISTINCT` when no metric), matching the docs and the two warehouses; a row-count test on all three dialects |
| ARCH-1 | should-fix | `SemolinaConnectionError` is raised only by `introspect()`; `create_engine` and `execute` connection failures surface as raw driver errors | Fix: wrap Semolina's own connect/pool-creation calls in `SemolinaConnectionError` (statement errors stay driver-native, as documented); fix the docstrings; test both paths |
| ARCH-2 | should-fix | `cursor.py` and `acursor.py` are hand-synchronised copies; four earlier drift bugs came from this | Fix in part: a parity test that the sync and async method pairs make the same guard/claim calls. The shared-base refactor becomes a limitation: about 1,700 lines are too much to rewrite just before the tag |
| TST-1 | should-fix | `codegen --check` on an unparseable models file is never exercised | Fix: add the test |
| COR-2 | minor | `codegen` exits 4 (connection failure) when the driver can't describe a view; the documented exit 6 is unreachable for built-in backends | Fix: a distinct introspection error that maps to exit 6 |
| COR-3 | minor | DuckDB extension corrupts a `bytes` filter when a source column is named `blob` (upstream) | Limitation: note it in the DuckDB docs and file it on duckdb-semantic-views |
| ARCH-3 | minor | Public `Query` has no public read surface; docstrings teach `query._metrics` | Fix the docstrings; read-only properties are additive, so they become a limitation |
| ARCH-4 | minor | `AsyncEngine` shares no base with `Engine`; the custom `--backend` contract lives only in CLI help | Limitation, plus a docs line on the custom-engine contract |
| ARCH-5 | minor | Four private tables of the same three backends; `to_sql()` can't take an `SQLDialect` | Limitation (internal; additive later) |
| ARCH-6 | minor | `Field.lookup()` docstring promises custom `Lookup` subclasses work; they raise | Fix the docstring |
| ARCH-7 | minor | Codegen error types live outside `exceptions.py`; `_distinct_columns` raises a bare `ValueError` | Limitation |
| ARCH-8 | minor | `Engine.introspect` returns a type from `semolina.codegen`, making a `[cli]`-package path public API | Fix: move the introspection IR to `semolina.introspection`, cheap before the tag, needs an alias after |
| ARCH-9 | minor | Docstring/code mismatches in `cursor.py`, `config.py`, `exceptions.py`, `engines/base.py` | Fix the docstrings |
| TST-2 | minor | `create_async_engine` untested with a named connection and without `[async]` | Fix: add the tests |
| TST-3 | minor | DuckDB typed literals in `where_clause` are only string-pinned | Fix: one parametrised live DuckDB test |
| TST-4 | minor | Exported `dto.resolve_column_key` is called and tested by nothing | Fix: add a test (removing it from `__all__` would be an API change) |
| TST-5 | minor | Uncovered CLI error paths (`--output` a directory, write OSError, `--config` without section, `check_dto` ValueError) | Fix: add the tests |
| TST-6 | minor | Exit-code table rows for typer Exit/Abort and unlisted setup-stage errors untested | Fix: add the tests |
| TST-7 | minor | Static reader robustness branches (inheritance cycle, inconsistent MRO) untested | Fix: add the tests |
| TST-8 | minor | DUCKDB_DATABASE equal to the committed path is untested | Fix: add the test |


---

## Semolina v0.7.0 pre-release review — ARCHITECTURE

Scope: `src/semolina` at `claude/phase-58` (= main, `8825ed9`), read against `.planning/ROADMAP.md`
phases 46-58, `REQUIREMENTS.md`, `56-01-DECISIONS.md` (D5/D6/D7) and the two earlier reviews
(2026-09-06 codebase, 2026-09-29 test suite). Read-only; reproductions were run with
`uv run --frozen python -I /tmp/claude-0/review-arch/repro.py` against in-memory DuckDB.

Severity scale: **blocker** (do not tag), **should-fix** (cheap now, expensive after 0.7.0),
**minor** (worth a ticket; additive or doc-only later).

No blockers. Two should-fix items, both about things that become a compatibility promise the
moment 0.7.0 is tagged. The rest are minor.

---

### Summary table

| id | sev | where | one line |
|---|---|---|---|
| ARCH-1 | should-fix | `engines/base.py:222-235`, `engines/abase.py:221-240`, `config.py:317`, `exceptions.py:59-61` | `SemolinaConnectionError` exists and is documented as "cannot connect or authenticate", but the query path and `create_engine` raise raw `adbc_driver_manager` errors; `except SemolinaError` around `execute()` never catches a warehouse failure. Documented in `web-api.rst`, but the class docstring and D5 did not consider it, and wrapping later is a breaking change. |
| ARCH-2 | should-fix | `cursor.py` (794 lines) vs `acursor.py` (914 lines) | The two cursors are a hand-maintained copy with `await` inserted; the only parity enforcement is a method-*name* test. Four drift bugs already shipped this way (A16, A17, A20, A22). Share the non-I/O half. |
| ARCH-3 | minor | `query.py:97-140, 652`, `codegen/query_resolver.py:266,383-386,631-634`, `engines/sql.py:1244-1314,1906-1913` | `Query` is public (API-02) but every piece of state is `_private`, its `__init__` takes `_metrics=…`, and its own docstrings teach `query._metrics`. Codegen and the builder reach into it through `Any`. |
| ARCH-4 | minor | `engines/base.py:30,69,237`, `engines/abase.py:36`, `cli/codegen.py:345-372` | `AsyncEngine` shares no base with `Engine`; per-backend introspection is bound to the sync class hierarchy, so the deferred async `introspect` has no home. The custom `--backend` contract ("constructible with no arguments") contradicts `Engine.__init__`'s required kwargs and lives only in CLI help text. |
| ARCH-5 | minor | `dialect.py:46-74`, `config.py:41-45,200-222`, `codegen/dto_renderer.py:154-171`, `query.py:501` | Three private tables map the same three backends; `SQLDialect` instances cannot say which `Dialect` they are; `to_sql()` cannot take an `SQLDialect` instance, so a custom dialect's SQL is only previewable by registering an engine. |
| ARCH-6 | minor | `fields.py:673-692` vs `docs/src/how-to/filtering.rst:822-837` | `Field.lookup()` docstring calls itself an "escape hatch" that "accepts any Lookup subclass"; the how-to correctly says it is not an extension point. The docstring overpromises. |
| ARCH-7 | minor | `codegen/python_renderer.py:38`, `codegen/type_compare.py:107`, `cli/codegen.py:168,215,368`, `results.py:278` | Error-hierarchy housekeeping: two `SemolinaError` subclasses live outside `exceptions.py` and are not in its `__all__`; Semolina's own CLI imports `SemolinaConnectionError` through the "left-behind" `engines.base` re-export, so that alias can never be retired; `_distinct_columns` raises a builtin `ValueError` for a warehouse-result condition. |
| ARCH-8 | minor | `engines/{snowflake,databricks,duckdb}.py` → `codegen/introspector.py`, `codegen/type_map.py` | Engines import the codegen package at runtime and `Engine.introspect` returns `semolina.codegen.introspector.IntrospectedView`, so a `[cli]`-extra package's module path is part of the core public API. Guarded by `test_cli_packaging.py`, so safe today; moving the IR is cheap before 0.7 and needs an alias after. |
| ARCH-9 | minor | `cursor.py:41-61`, `config.py:372-383`, `exceptions.py:59-61` | Three docstrings that describe a different design than the code: "wraps any DBAPI 2.0 cursor" (every read needs pyarrow/ADBC), `register:` documented twice in `create_async_engine`, and `SemolinaConnectionError` not scoped to introspection. |

---

### ARCH-1 — The query path raises nothing a `SemolinaError` handler can catch (should-fix)

**Where.** `src/semolina/engines/base.py:222-235` (`Engine.execute`), `src/semolina/engines/abase.py:221-240` (`AsyncEngine.aexecute`), `src/semolina/config.py:317` and `:435` (`create_pool` / `create_async_pool`), `src/semolina/exceptions.py:59-61`.

**What is wrong.** `SemolinaConnectionError` is defined as "Raised when the engine cannot connect to or authenticate with the warehouse" (`exceptions.py:60-61`). It is raised only inside the three `introspect()` methods (`snowflake.py:267`, `databricks.py:240`, `duckdb.py:308,318`). On the path every backend service actually uses:

- `Engine.execute` / `AsyncEngine.aexecute` call `self.connect()` (pool checkout, which is where authentication and connectivity fail) and `cur.execute(sql, params)`, and re-raise whatever the driver raises unchanged (`base.py:226-233`).
- `create_engine` calls `create_pool(wh_config)`, which opens the first connection, and its documented `Raises:` lists only `FileNotFoundError`/`KeyError`/`ValueError` (`config.py:283-289`).

`docs/src/how-to/web-api.rst:396-402` and `:436-438` say this out loud ("raised only by `Engine.introspect()`… Semolina passes [driver errors] through unchanged"), so it is a known, documented state. It is listed here anyway because:

1. **D5 did not consider it.** `56-01-DECISIONS.md` decided the *hierarchy* ("every Semolina-specific error derives from `SemolinaError`") and kept the five existing classes. It did not ask whether the one class named for connection failure should fire where connection failures happen. The web-api how-to's own recommendation — "catch `adbc_driver_manager.Error` separately when you want to answer 503" — makes the application import a driver package Semolina otherwise hides behind adbc-poolhouse.
2. **It is a one-way door.** If 0.8 wraps pool-checkout failures in `SemolinaConnectionError`, every 0.7 handler written as `except adbc_driver_manager.Error` stops matching (the chained `__cause__` does not help an `except` clause). If 0.7 ships the wrapping, nothing breaks: nobody has a working `except SemolinaConnectionError` around `execute()` today, per the docs.
3. **The class docstring is wrong as written.** A user reading `help(SemolinaConnectionError)` gets the general claim; only the how-to narrows it.

**Reproduced.** Yes:

```
ARCH-1:  execute() raised non-Semolina error: adbc_driver_manager InternalError | isinstance SemolinaError: False
ARCH-1b: connect failure in create_engine(): adbc_driver_manager InternalError | isinstance SemolinaError: False
```

(`Sales.query().metrics(Sales.revenue).execute()` against a missing view, and `create_engine(DuckDBConfig(database="/nonexistent/dir/x.db", read_only=True))`.)

**Cost scenario.** A FastAPI service follows `web-api.rst` and wraps `query.execute()` in `except SemolinaError → 500`. The warehouse credential rotates; every request now raises `adbc_driver_manager.OperationalError` from inside `Engine.execute`, which the handler does not catch, so the framework's generic 500 fires with no log line naming the cause. The team adds `except adbc_driver_manager.Error`; 0.8 later wraps checkout failures and that clause goes dead.

**Suggested fix (pick one, before the tag).**

- *Narrow (keeps the passthrough policy):* wrap only the `self.connect()` call — Semolina's own call into its own pool — in `SemolinaConnectionError(...) from exc` in `Engine.execute`, `AsyncEngine.aexecute`, `Engine.connect`, `AsyncEngine.connect`, and the `create_pool`/`create_async_pool` calls in `config.py`. Statement execution (`cur.execute`) stays driver-native, as the docs describe. Update `exceptions.py:59-61` and the `Raises:` blocks on `execute`/`aexecute`/`create_engine`. This is the same error the three `introspect()` methods already raise for the same underlying condition.
- *Minimal (doc only):* change the `SemolinaConnectionError` docstring to say "raised by `Engine.introspect()` only; query-path and pool failures are the driver's own `adbc_driver_manager.Error`", and change `Engine.execute`'s `Raises: Exception:` to name `adbc_driver_manager.Error`. Then record the passthrough as an explicit decision (D-numbered) so 0.8 does not revisit it by accident.

Either way, add a test that pins the chosen behaviour on both `execute` and `aexecute`.

---

### ARCH-2 — `cursor.py` / `acursor.py` are a hand-synchronised copy (should-fix)

**Where.** `src/semolina/cursor.py` (794 lines) and `src/semolina/acursor.py` (914 lines).

**What is wrong.** The two classes are identical in structure (method-by-method diff differs only in `async`/`await`, `__iter__`→`__aiter__`, `close`→`aclose`, and two return annotations). The shared logic that has nothing to do with I/O is duplicated verbatim:

- `_column_names` (`cursor.py:83-93` / `acursor.py:122-135`)
- the `_require` → `_claim_read` → `_distinct_columns` → `Row(dict(zip(...)))` prologue in six fetch methods each
- the pyarrow/pandas/polars/arrowmodel guard ordering and its rationale comments (`cursor.py:332-336,387-390,473-476` / `acursor.py:387-391,446-449,537-541`)
- the `check_result_schema(...)` then `_claim_read` ordering in `into`/`iter_into`
- the batch cursor bookkeeping (`_batch_rows`, `_batch_pos`, `_stream_exhausted`) and the zero-row-batch skip loop in `__next__`/`__anext__`
- the `close()`/`aclose()` suppression ladder and `ResourceWarning` text
- `description`, `rowcount`, `__repr__`

The only enforcement is `tests/unit/test_async_naming.py`, which checks that coroutine *names* have a sync namesake. Nothing checks that the two classes guard the same packages in the same order, claim the result at the same point, or raise the same error for the same misuse.

**This is not the decision the docs record.** `acursor.py:5-7` justifies a *separate public class* ("so a sync-style call on an async cursor cannot silently hand back a coroutine"). That holds for the public surface and is right. It does not require the implementation to be a copy; a `_CursorBase` holding `_column_names`, `_rows_from(columns, raw)`, the guard/claim helpers, `description`, `rowcount`, `__repr__`, the batch state and a `_next_row_from(batch)` would leave each twin with only the awaits.

**Evidence it drifts.** The 2026-09-06 review found four defects that were exactly sync/async divergence: A16 (mixed-consumption error differed), A17 (pyarrow guard present on async `__anext__`, absent on sync), A20 (`aclose` exception-safe, `close` not), A22 (sync `fetch_record_batch` did not record the reader; async did). Phase 52-04 fixed them by editing both files by hand. The next feature touching cursors (a `fetch_batches()` helper, a timeout, a column-rename hook) repeats the exercise.

**Reproduced.** Structurally (diff of method signatures; the bodies were read side by side). No behavioural divergence found *today* beyond one benign asymmetry: sync `__next__` catches `(StopIteration, OSError)` when opening the reader (`cursor.py:695`), async catches only `OSError` (`acursor.py:783`).

**Cost scenario.** 0.8 adds a `fetch_arrow_batches()` or changes `_claim_read`'s dbapi grouping; it lands on one cursor with a test and the other without, and ships, as A17/A20/A22 did.

**Suggested fix.** Extract the shared half into a private base/mixin (no public API change; `SemolinaCursor` and `AsyncSemolinaCursor` keep their names and MROs are private). At minimum, add a parity test that, for each public method pair, asserts the same `_require` package list and the same `_claim_read` call-name/`dbapi` flag — e.g. by patching `_require`/`_claim_read` on a stub cursor and comparing the recorded call sequences. That test would have caught A17 and A22.

---

### ARCH-3 — `Query` is public but has no public read surface (minor)

**Where.** `src/semolina/query.py:97-140` (dataclass fields), `:115-122, 260-262, 309-311, 362-364, 408-410, 441-443, 474-476` (docstring examples), `:652` (`_Query` alias), `src/semolina/codegen/query_resolver.py:266, 383, 386, 631-634`, `src/semolina/engines/sql.py:1244-1314, 1335-1336, 1883-1913`.

**What is wrong.** API-02 made `Query` the exported name and the return type of `Model.query()`. Everything on it is still private:

- `inspect.signature(Query)` → `['_metrics', '_dimensions', '_filters', '_order_by_fields', '_limit_value', '_using']`: the public constructor takes underscore kwargs (reproduced).
- The only public attributes on an instance are the builder methods; there is no way to ask a query what it selects, filters, orders by or limits without `_metrics` etc.
- Seven docstring examples on the class teach `query._metrics` / `query._filters` / `query._limit_value` / `query._using` as the way to inspect a query.
- Semolina's own consumers do the same through `Any`: `query_resolver.py:266,631-634` (`query._metrics`, `query._dimensions`), `:383-386` (`query._replace(_filters=None, ...)`), and every `SQLBuilder` method takes `query: Any` and reads `query._filters`, `query._dimensions`, `query._order_by_fields`, `query._limit_value`, and `query._metrics[0].owner._view_name` (`sql.py:1906-1913`).

**Cost scenario.** A user writes a cache key or audit log from `query._metrics` (as the docstrings show) and a request-scoped `Query` middleware; a later rename of the field (or a change to how `_model` is carried) breaks user code with no deprecation path, while the typed builder (API-01) gives them no alternative. Internally, the builder is untyped against the query, so a field rename on `Query` is not caught by basedpyright.

**Suggested fix (additive, so it can also wait — but it is cheapest now).** Add read-only properties (`selected_metrics`, `selected_dimensions`, `filters`, `ordering`, `limit_value`, `engine_name`, `model`), rewrite the docstring examples to use them, type `SQLBuilder.*(query: Query)` under `TYPE_CHECKING`, and have `query_resolver` use the properties. Consider `Query.__init__` taking no public kwargs (keep the dataclass fields `init=False` with a private `_replace`), since `Query(_using="x")` is now a public call shape that cannot be renamed later.

---

### ARCH-4 — `Engine` / `AsyncEngine` asymmetry pins introspection to the sync hierarchy (minor)

**Where.** `src/semolina/engines/base.py:30, 69, 237-266`, `src/semolina/engines/abase.py:36-47`, `src/semolina/engines/{snowflake,databricks,duckdb}.py` (`introspect` bodies), `src/semolina/config.py:447-450`, `src/semolina/cli/codegen.py:345-372`.

**What is wrong.**

1. `AsyncEngine` is concrete and shares no base with `Engine` (`issubclass(AsyncEngine, Engine)` is `False`, reproduced). `Query._using_engines_dialect` (`query.py:559-561`) relies on both having a `.dialect` attribute by duck typing. There is no `Protocol` or base that says "an engine has a dialect".
2. `introspect` is the *only* abstract method on `Engine`, and the three backends implement it as a subclass method that drives a sync cursor. `abase.py:45-47` records "async introspection is deferred". But the shape chosen gives the deferred work no home: adding `AsyncEngine.introspect` means either three `AsyncSnowflakeEngine`-style subclasses duplicating ~400 lines, or extracting the three bodies into dialect-keyed strategies then. Doing the extraction now is internal and cheap; `Engine.introspect`'s public signature stays.
3. The custom-backend extension point is underspecified. `cli/codegen.py:345-372` instantiates a `--backend dotted.path.ClassName` as `cls()` and the help text says "cannot be built with no arguments" is the user's error, yet `Engine.__init__` requires `pool=` and `dialect=` keyword-only (`base.py:69`). A custom engine must therefore override `__init__`, build its own pool, and pick a dialect, none of which is documented outside the CLI epilog (`how-to/codegen.rst:655` mentions only the no-arguments rule). The CLI also cannot use an `AsyncEngine` there.

**Cost scenario.** 0.8 implements async introspection and discovers the three `introspect` bodies need to run off-thread via poolhouse; the per-backend logic is copy-pasted into async subclasses or refactored under time pressure, with the `Engine` ABC's public contract (which third-party `--backend` classes implement) as the thing at risk.

**Suggested fix.** Before 0.7: a tiny shared base (`_EngineBase` holding `_pool`, `dialect`, `_config`, `_registered_as`) so the two engines are typed siblings, and move each backend's `introspect` body into a module-level function `introspect_<backend>(cursor_factory, view_name, dialect)` that the sync subclass calls; document the custom-backend contract (`__init__` with no args, must set `dialect`, must implement `introspect`) next to `Engine`. All internal except the documentation.

---

### ARCH-5 — Three private tables of the same three backends; no way back from `SQLDialect` to `Dialect` (minor)

**Where.** `src/semolina/dialect.py:46-74` (`_DIALECT_MAP`), `src/semolina/config.py:41-45` (`_CONFIG_MAP`), `:200-222` (`_engine_cls_for_dialect`), `src/semolina/codegen/dto_renderer.py:154-171` (`_known_backend_label`, MRO scan by class *name*), `src/semolina/cli/codegen.py` (`_BACKEND_LABELS`), `src/semolina/query.py:501`.

**What is wrong.** The enum→dialect, type-string→config-class, dialect→engine-class and dialect-class→label mappings are four separate hand-maintained dicts. A `SQLDialect` instance carries no identity: `dir(SnowflakeDialect())` has no `name`/`dialect` member (reproduced), so `dto_renderer` identifies the backend by scanning `type(dialect).__mro__` for a class *name* string. Adding a fourth backend touches five files. Separately, `Query.to_sql(dialect: str | Dialect | None)` cannot take an `SQLDialect` instance, so the SQL of a custom dialect (the thing the dotted `--backend` route exists for) can only be previewed by registering an engine and using `.using()`.

**Suggested fix.** `SQLDialect.name: ClassVar[Dialect]` (or `kind`) set on each concrete dialect; one backend table in `dialect.py` keyed by the enum holding `(config_cls, dialect_cls, engine_cls, label)`; `to_sql()` accepting `SQLDialect` instances as well. All additive.

---

### ARCH-6 — `Field.lookup()` docstring advertises an extension point the how-to says does not exist (minor)

**Where.** `src/semolina/fields.py:673-692` vs `docs/src/how-to/filtering.rst:822-837`; `src/semolina/engines/sql.py:1096-1242` (`match` over a closed set).

**What is wrong.** The method docstring: "Create an arbitrary lookup predicate (escape hatch). Use this when none of the built-in operators or named methods fit. Accepts any Lookup subclass". The how-to, correctly: "This is not a public extension point yet… treat `Lookup` as machinery… open an issue". Building `Sales.country.lookup(Regex, "^U")` succeeds and `to_sql()` raises `NotImplementedError: … Add a case for it in _compile_predicate()` — a message that names a private method (reproduced).

The docs are honest, so this is not a correctness finding. It is a public-API-shape one: `lookup()` is exported through `Field`, which is now a root export (API-02), and its docstring will be what IDEs show.

**Suggested fix.** Either align the docstring with the how-to (one sentence: "only the built-in `Lookup` subclasses compile; a custom subclass raises `NotImplementedError` at `to_sql()`/`execute()`"), or make the seam real in a small way — a `Lookup.sql_template: ClassVar[str | None]` (`"{col} REGEXP {v}"`) that `_compile_predicate`'s default case renders through the same `_SLOT`/`render_literal` path. The latter is additive and would retire the private-method error message.

---

### ARCH-7 — Error-hierarchy housekeeping (minor)

**Where.**
- `src/semolina/codegen/python_renderer.py:38` (`GeneratedSourceError(SemolinaError, RuntimeError)`), `src/semolina/codegen/type_compare.py:107` (`Unresolvable(SemolinaError)`): two `SemolinaError` subclasses outside `exceptions.py`, not in `exceptions.__all__`, not mentioned by the module docstring that claims to hold "Semolina's errors, all deriving from `SemolinaError`".
- `src/semolina/cli/codegen.py:168, 215, 368` and `src/semolina/engines/{snowflake,databricks,duckdb}.py:14`: Semolina's own code imports `SemolinaConnectionError`/`SemolinaViewNotFoundError` from `semolina.engines.base`, the path API-03 describes as a "re-export left behind". While first-party code uses the alias, it can never be removed, and `engines/__init__.py:13` re-re-exports it a third way.
- `src/semolina/results.py:271-283` (`_distinct_columns`) raises builtin `ValueError` for "the result has duplicate column names" — a warehouse-result condition, not "the caller's mistake" that D5 reserves builtins for. Reachable only via a custom engine now that the builder aliases and de-duplicates, so low impact.

**Suggested fix.** Move or alias the two codegen errors into `exceptions.py` (keep the originals importable); change first-party imports to `semolina.exceptions`; either promote `_distinct_columns`' error to a `SemolinaError` subclass or note in D5 that result-shape errors stay builtin.

---

### ARCH-8 — `Engine.introspect` returns a type whose public path is inside the `[cli]` package (minor)

**Where.** `src/semolina/engines/base.py:18, 238`, `engines/snowflake.py:198-203`, `databricks.py:166-172`, `duckdb.py:200-205`, `src/semolina/codegen/introspector.py`, `src/semolina/codegen/type_map.py`.

**What is wrong.** The engines layer imports the codegen layer at call time (`codegen.introspector`, `codegen.type_map`), and the abstract method's return type is `semolina.codegen.introspector.IntrospectedView`. `codegen` is otherwise the tooling layer behind the `[cli]` extra (`dto_renderer.py` imports jinja2 at module top, `static_reader.py` imports griffe, `arrow_map.py` imports pyarrow). `tests/unit/test_cli_packaging.py:212-249` pins that `introspect()` works without the extra, so this is safe today and I am not re-raising CI-9. The architectural point is that `IntrospectedView`/`IntrospectedField` and the warehouse type maps are consumed *below* codegen, and their import path becomes public API for third-party engines at 0.7.0.

**Suggested fix.** Move `IntrospectedField`, `IntrospectedView`, `with_python_field_names`, `python_field_names`, `class_name_for` and `type_map.py` into a `semolina.introspection` package (dependency-free by construction), re-export from `semolina.codegen.introspector` for compatibility, and add a ruff `TID251`-style ban on `semolina.codegen` imports inside `semolina.engines`. Cheap now; needs a deprecation cycle later.

---

### ARCH-9 — Docstrings describing a different design than the code (minor)

- `src/semolina/cursor.py:41-47`: "Wraps any DBAPI 2.0-compatible cursor via delegation." Every read path calls `_require("pyarrow", ...)` and `fetch_record_batch`/`fetch_arrow_table`/`fetch_df`/`fetch_polars` are ADBC-only (the method docs say so). The class is an ADBC cursor wrapper; say so, since `Engine.execute` is the only constructor path anyway.
- `src/semolina/config.py:372-375` and `:379-383`: `create_async_engine` documents the `register` argument twice with different wording.
- `src/semolina/exceptions.py:59-61`: see ARCH-1; the docstring does not say the error is introspection-only.
- `src/semolina/engines/base.py:199-202`: `Raises: Exception: For backend execution errors` — name `adbc_driver_manager.Error` (or the Semolina wrapper, per ARCH-1).

---

### Areas reviewed and found sound

- **Registry** (`registry.py`): one `RLock`, split sync/async stores with the rationale in the module docstring, identity-checked `unregister`, `get_engine` as a single dict read. API-10 is complete.
- **Engine lifecycle**: `create_engine(register=…)` + `Engine.__exit__` undo exactly what they did; registration is last so a clash disposes the pool (`config.py:328-345`); `execute` returns the slot on every error path including cancellation (`base.py:222-233`, `abase.py:221-238`).
- **Filter IR** (`filters.py`): frozen dataclasses, `None` refused at construction (D3), `In` materialises and rejects `str`; the compiler is the single place that knows SQL.
- **SQL generation**: one audited literal-escaping site (`render_literal`), `_SLOT` sentinel so `?` in identifiers is safe, dialect capability flags instead of `isinstance` (`sql.py:287-319`), `sql_str_literal` shared between introspection and the DuckDB builder. The HAVING/`where_clause` split and the OR/NOT refusal are in one `SQLBuilder` with a DuckDB subclass overriding only `_build_template` and `_build_order_by_clause`.
- **Result reading**: `_claim_read` is shared by both cursors and tested; `Row` is a real `Mapping` with pickle/copy support.
- **Packaging boundaries**: `import semolina` is lazy on `config` (PEP 562), the console script gates on the `[cli]` extra without importing it (`__main__.py`), and `test_public_surface.py` fails on a public module without `__all__`.
- **Naming rule** for sync/async (API-05) is stated and enforced (`test_async_naming.py`).
- **Model inheritance** (`models.py:156-175`): MRO walk with per-class field copies, abstract bases, immutability keyed on the class's own `_frozen`.

### Things from the earlier reviews that I checked and consider closed

C1 (aliasing) — `SQLBuilder._field_alias` and the DuckDB wrapper; C3 (`_Query` public) — `Query` exported, alias kept; C4 (`SemolinaError`) — hierarchy present, but see ARCH-1 for the half D5 did not cover; C5 (two `Dialect`s) — renamed with warnings; C6 (naming) — rule + test; C8 (`__all__`) — enforced; A12/API-10 (registry lock) — done; CI-8/CI-9 (wheel, `[cli]`) — done, with tests.

---

## Semolina v0.7.0 pre-release correctness review

Scope: `git diff v0.6.1..main -- src` (43 files), traced from the public entry points
(`Model.query()...execute()/aexecute()/to_sql()`, cursor fetch/`into`/`iter_into`/`fetch_df`/
`fetch_polars`, `engine.introspect()`, `semolina codegen`, `codegen --check`, `codegen-dto`).
Read-only. Reproductions ran against in-memory / file DuckDB with the `semantic_views`
community extension (DuckDB v1.5.6). Snowflake and Databricks were checked by inspecting the
generated SQL only; nothing touched a warehouse.

Scratch scripts: `/tmp/claude-0/review-correct/t*.py` (`harness.py` builds an Engine over an
ADBC DuckDB pool with a per-connection setup script). Run with
`uv run --frozen python /tmp/claude-0/review-correct/<script>.py` from `/home/user/semolina`.

Items the 2026-09-06 review raised and phases 51-57 fixed were re-verified rather than
re-reported: LIKE escaping (FILT-02), `None` handling (D3), metric filters to `HAVING` /
outer `WHERE` (D4), ORDER BY alias shadowing, pre-quoted / dotted view names (FILT-05/06),
`?` inside identifiers (FILT-07), `.where()` type refusal (FILT-09), cursor close ordering
(CORE-07/12), result aliasing (D2). All hold on the paths I traced.

### Findings

#### COR-1 — should-fix — a fact-only (row-level) query returns different rows per backend

- `src/semolina/engines/sql.py:1518-1538` (`_build_group_by_clause`, always `GROUP BY ALL`),
  `src/semolina/engines/sql.py:1915-1930` (`DuckDBSQLBuilder._build_template`, `facts := [...]`).
- **What is wrong.** On Snowflake and Databricks every query, including one with no metric
  selected, is `SELECT <cols> FROM <view> GROUP BY ALL`, which collapses duplicate rows. On
  DuckDB the same query is `semantic_view(..., facts := [...])` with no outer DISTINCT, which
  returns one row per source row. The same `Query` therefore returns a different number of
  rows on the two families. The docs (`docs/src/how-to/queries.rst:79`) describe
  `.dimensions()` as grouping by Dimension **or Fact** fields, while the DuckDB builder's own
  error text calls the fact path "row-level queries", so the two halves of the code base
  disagree about what a fact query means.
- **Trigger.** `sales_data` with two rows having `unit_price = 10`
  (`/tmp/claude-0/review-correct/t13_facts.py`):

  ```python
  class S(SemanticView, view="sales_view"):
      unit_price = Fact(); country = Dimension()
  S.query().dimensions(S.unit_price)
  ```

  DuckDB (reproduced): `[(10,), (20,), (5,), (10,)]` — 4 rows, duplicate kept.
  Snowflake SQL emitted: `SELECT "UNIT_PRICE" AS "unit_price" FROM "SALES_VIEW" GROUP BY ALL`
  — 3 rows (duplicate collapsed). Same with `.dimensions(S.country, S.unit_price)`:
  DuckDB `[('US',10),('CA',20),('US',5),('US',10)]` vs a grouped result.
- **Reproduced:** DuckDB side yes; Snowflake/Databricks side by SQL inspection (no cassette in
  `tests/integration` runs a fact-only query on either warehouse, so this was never measured).
- **Suggested fix.** Decide one meaning and pin it with a test on all three dialects. If a
  fact query is "group by" (as the docs say), make the DuckDB builder emit
  `SELECT DISTINCT ...` (or a grouped outer select) when `query._metrics` is empty. If it is
  "row-level", drop `GROUP BY ALL` on Snowflake/Databricks when no metric is selected and
  verify live that the warehouses accept a bare fact projection. Either way add a test that
  asserts the row count on a view with duplicate fact values.

#### COR-2 — minor — `codegen` exits 4 ("connection or authentication failure") for a view the driver cannot describe

- `src/semolina/engines/duckdb.py:304-318`, `src/semolina/engines/snowflake.py:258-267`,
  `src/semolina/engines/databricks.py:231-240`, `src/semolina/cli/codegen.py:181-185`.
- **What is wrong.** Each built-in `introspect()` wraps every driver error that is not a
  "missing view" in `SemolinaConnectionError`. `exit_code_for` maps that to 4, so the
  documented exit 6 ("the warehouse driver failed while describing a view") is unreachable
  for the three built-in backends; `tests/unit/codegen/test_cli.py:772` only proves 6 through
  a custom engine that re-raises the raw driver error. A CI script branching on the exit code
  treats a broken view definition as a credentials problem.
- **Trigger (reproduced).** A DuckDB view whose metric expression references a column that
  does not exist (an intermediate state of `t8_mkdb.py`), then
  `python -m semolina codegen plain -b duckdb -d tricky.db`:
  stderr `Error: DuckDB introspection failed: INTERNAL: Binder Error: ... Referenced column
  "revenue" not found`, exit code **4**.
- **Suggested fix.** In the three engines keep `OperationalError`/`InterfaceError` as
  `SemolinaConnectionError`, and raise a distinct `SemolinaIntrospectionError` (or re-raise
  the driver error) for `InternalError`/`ProgrammingError` so `exit_code_for` returns 6. Pin
  with a DuckDB test that defines an unbindable view and asserts exit 6.

#### COR-3 — minor (upstream) — DuckDB `where_clause` on a `bytes` value is corrupted when a source column is named `blob`

- Semolina side: `src/semolina/engines/sql.py` `DuckDBDialect.render_literal` emits
  `'\x41'::BLOB`, which is correct DuckDB. The defect is in the `semantic_views` extension's
  textual rewriting of `where_clause`.
- **Trigger (reproduced, `t5_blob.py`).** Table column `blob BLOB` exposed as fact `payload`;
  `S.query().dimensions(S.name).where(S.payload == b"A")` fails with
  `WHERE "payload" = '\x41'::(payload)` — the extension rewrote the type keyword `BLOB`
  because it matches the source column name. With the column renamed (`t7_blob2.py`) the same
  filter returns the right row.
- **Suggested fix.** File against `duckdb-semantic-views` (identifier substitution in
  `where_clause` must be token-aware and skip `::TYPE` casts). In Semolina a one-line note in
  the DuckDB backend docs is enough; no code change.

### Observations (not findings)

- `Engine.execute` / `AsyncEngine.aexecute` error path (`base.py:222-233`, `abase.py`
  equivalent) returns the connection to the pool without closing the ADBC cursor it created.
  The pool slot is reclaimed (verified `checkedout() == 0` after a failing execute); the
  cursor is left to the driver finaliser. `cur.close()` under the same suppression would be
  tidier.
- Sync `SemolinaCursor.__del__` (`cursor.py:755-776`) returns only the connection, not the
  reader/cursor. Documented as a safety net; the pool slot is reclaimed (verified).
- A DuckDB-generated model with `view='"Sales Report"'` renders on Databricks as
  ``FROM `"sales report"` `` (the `"` is not a Databricks quote char and is folded). That is
  what the dialect rules say should happen; a model generated for one backend with a quoted
  view name is not portable by name.
- `codegen-dto --view` takes warehouse names that must also be Python identifiers, so a
  column such as `Country Code` can only be described through a `QUERY_PATH`. The refusal is
  clear.
- Row order without `ORDER BY` varies between executions on DuckDB (hash aggregation);
  `into()`/`iter_into()`/`fetchall_rows()` all preserve the warehouse order when one is given
  (`t12_order.py`).

### Areas checked and found sound

- **Literal rendering / injection.** `'` doubled on all dialects; backslashes doubled on
  Snowflake, backslash-escaped on Databricks, raw on DuckDB; LIKE escaping with `ESCAPE '!'`
  for `startswith`/`endswith`/`iexact` and pass-through for `like`/`ilike` (all executed on
  DuckDB, `t2_filters.py`); identifiers containing `?`, backtick and `"` are quoted per
  dialect and the placeholder count stays right (`t11_misc.py`); non-finite float/Decimal
  refused; aware datetimes normalised to UTC `Z`; `IN ()` → `1 = 0`; `== None` → `IS NULL`.
- **View-name quoting on DuckDB.** `"Order Book"`, `Order Book`, `analytics.sv`,
  `"analytics"."sv"`, `"Weird""Name"`, `SALES_VIEW` all resolve identically through
  `execute()` and `introspect()` (`t1_names.py`).
- **Metric filter routing (D4) and ORDER BY shadowing.** Dimension/fact filters go to
  `where_clause` / `WHERE`, metric filters to outer `WHERE` / `HAVING`, mixed `OR`/`NOT`
  refused, unselected metric requested but not projected; swapped `source=` names and
  case-only collisions either sort by the right column or raise (`t3_shadow.py`). DuckDB
  resolves a bare name in the outer `WHERE` to the source column, not the alias, so
  `source=` swaps filter correctly (verified with rows).
- **Resource cleanup, sync and async.** `checkedout()` returns to 0 after: a failing
  execute, partial iteration + `close()`/`aclose()`, dropping a cursor without closing,
  `fetch_record_batch` + close, an exception inside `with`/`async with`, and task
  cancellation mid-`aexecute` (`t4_cleanup.py`, `t6_async.py`). `_claim_read` refuses a
  second way of reading.
- **DTO path.** `check_result_schema` accepts `T | None` on a non-null column, a DTO
  missing a result column, extra fields with defaults, and `object`; rejects `float` for
  `int64` with a clear message; `validate=True` surfaces NULL metrics as pydantic errors;
  `fetch_df`/`fetch_polars` carry the aliased column names (`t4_cleanup.py`, `t11_misc.py`).
- **Codegen round trip.** A view with spaces, a leading digit, a hyphen, SQL keywords and a
  reserved builder name (`query`) generates a model with `source=` where needed, the model
  queries correctly on DuckDB including `where`/`order_by` on renamed fields, `--check` is
  clean on the unchanged view and reports `(absent)`/type drift with exit 5 after the view
  changes (`t8_mkdb.py`, `t9_use_gen.py`, `t10_drift.py`).
- **Registry, models, filters IR.** `RLock`-guarded register/unregister/reset with separate
  sync/async stores; `SemanticViewMeta` freeze keyed on the class's own `__dict__`; inherited
  fields copied and re-owned; `In` copies to a tuple and refuses str/bytes/None; `Between`
  refuses `None` bounds; `Row` is a Mapping and reserved names cannot become fields.

---

## Semolina v0.7.0 pre-release review — TEST COVERAGE

**Scope:** `git diff v0.6.1..main` (272 commits; ~5.5k lines changed under `src/semolina/`), judged
against `tests/` on branch `claude/phase-58`.
**Run:** `uv run --frozen pytest -q -n auto -m "not timing" --cov=src/semolina` — 2399 passed,
16 skipped (all 16 are doctest `+SKIP` directives, no real test is skipped), 2 xfailed (the
D9-accepted corpus limitations), 97% line coverage, 143 uncovered statements.
**Method:** read the phase 46–57 roadmap, requirements, the cassette README and the 2026-09-29
test-suite review; read every changed core module (`engines/sql.py`, `filters.py`, `fields.py`,
`query.py`, `registry.py`, `exceptions.py`, `engines/*.py`, `config.py`) and the tests that pin
them; ran three code mutations in a throwaway copy (`/tmp/claude-0/review-tests/copy`); probed
the DuckDB extension live for the one behaviour that no test executes. Nothing in the real tree
was touched.

Items the earlier review raised and Phase 52.1 fixed were checked and are not re-reported.
Decisions D1–D9, the `_copied` cassettes, the `SHOW COLUMNS` cassette keyed on `''` (57-02) and
the strict xfails are treated as settled.

---

### Verdict

The suite would catch a regression in almost everything 0.7.0 ships. There is **no blocker**.
One **should-fix** (an error path of `codegen --check` with no test at all, where its sibling
command has one) and seven **minor** gaps, all in error paths or async twins of tested sync
paths. The core query builder, filter semantics, aliasing, engines, cursors, registry,
exception hierarchy, packaging and integration cassettes are well covered, and I could not
make a vacuous or wrong-reason test out of any of them.

#### Mutations run (throwaway copy; suite caught every one)

| Mutation | What it stands for | Result |
|---|---|---|
| `Lookup.accepts_none = True` (`filters.py`) | `>`/`<`/`startswith(None)` silently compiling to `> NULL` | caught (`test_sql.py::TestNoneInAFilter`) |
| drop the `!`→`!!` step in `escape_like` (`sql.py:174`) | a literal `!` in a prefix escaping the next char | caught (`test_the_escape_character_is_escaped_too`) |
| drop Snowflake backslash doubling (`sql.py:630`) | `to_sql()` preview mis-escaping `a\b` on Snowflake | caught |

#### Areas confirmed well covered (one line each)

- **Builder, all three dialects, exact SQL:** aliasing (`AS "field"`), `GROUP BY ALL`, `HAVING`
  split at top-level `AND`, OR/NOT-mixed refusal, unselected-dimension/fact `order_by()`
  refusal, metric ORDER BY by alias (Databricks) / expression (Snowflake) / shadow detection
  with per-dialect case rules, DuckDB `where_clause` binding, `_metrics_to_request`, `?` in
  identifiers (`_SLOT`), `In([])`→`1 = 0`, `db..view`, pre-quoted segment escaping and all
  three `quote_table_name` error wordings (`test_sql.py`, 2590 lines, parametrised by dialect).
- **Filters (D3/FILT-01/02):** `== None`/`!= None` on Snowflake, Databricks and DuckDB; every
  other lookup refusing `None` at construction (12 cases); `between`/`in_` with `None`; LIKE
  escaping on all three dialects including the Databricks backslash, bound and inlined.
- **`render_literal`:** numpy scalars incl. `datetime64` refusal, IntEnum, Decimal fixed-point,
  aware datetime → `TIMESTAMP_TZ` / `TIMESTAMPTZ`, DuckDB `TIMETZ`/`INTERVAL`/`BLOB`, ZoneInfo
  time refusal (string-level; see TST-3 for the live gap).
- **Engines:** introspect quoting per engine, DuckDB schema prefix selects that schema (live),
  names needing quotes round-trip through codegen (live), Snowflake session qualification
  (bare / two-part / three-part / no session db or schema), `?`-in-identifier on Databricks
  (cassette), error mapping: every `adbc_driver_manager.Error` subclass → connection error on
  Snowflake/Databricks (parametrised), DuckDB driver-type-before-message (FILT-08).
- **Cursors (CORE-07..12):** close-order, close-when-cursor-close-raises, `__exit__` not
  masking, one-read-pattern on both cursors, duplicate column names on both, pyarrow guard on
  every row method on both, reader bookkeeping; every sync class has an async twin class.
- **Async:** loop-freedom test now gates inside the driver call (the 52.1 fix is real),
  cancellation reaches the driver, both anyio backends via the shared `anyio_backend` fixture,
  `aexecute(Query())` raises `ValueError`, async registry/reset, `.into()`/`iter_into` async.
- **Registry (API-10):** deterministic race tests with a yielding dict; mid-lookup unregister
  raises the documented error on both stores.
- **Exceptions (API-03):** source scan of every module for `BaseException` subclasses with a
  non-vacuity guard; `RuntimeError`/`ValueError` bases kept; `engines` re-exports.
- **Public surface / packaging (API-02/04/06/07):** `__all__` enforced; both deprecated names
  warn and are not in `__all__`; `_Query` alias; `[cli]` hint exercised through the real
  `semolina.__main__:main` in a child interpreter with each package blocked (that is why
  `__main__.py` reads 0% — it is covered by subprocess, not by the in-process tracer); lazy
  `config` import; `import semolina` imports no anyio/pandas/codegen.
- **Typing (API-01):** basedpyright negative tests with a per-line error map and a clean twin
  file, so neither an `Any`-typed nor a `Never`-typed builder passes.
- **Integration:** 20 `test_queries` tests × both warehouses (41 cassette dirs, every test has
  one per backend except the four deliberately single-backend ones), each asserting exact
  rows after normalisation and the generated SQL by cassette match; the copied cassettes are
  all marked and `test_cassette_provenance.py` enforces it; timing tests run serially in CI
  (`ci.yml:167-174`).
- **Codegen hardening (GEN-01..12):** validity gate (unusable/colliding class names, parse
  check, loud ruff), credential redaction (env, toml, custom backend, introspect-time),
  shared exit table, atomic `--output` with the fallback matrix, `~` expansion, override
  announcement, `--check` fallback exit 6, the 19-case D9 corpus, inherited fields, two
  classes per view.

---

### Findings

#### TST-1 — `codegen --check` against an unparseable committed model file has no test · **should-fix**

- **Untested src:** `src/semolina/cli/codegen.py:803-810` (the `except ValueError` around
  `read_committed_model_file(model)` → message on stderr, `typer.Exit(code=1)`). Coverage: lines
  never execute, so no assertion in the suite can see any change to them.
- **Sibling has it:** `tests/unit/codegen/test_dto_cli.py:1755`
  `test_an_unparseable_committed_file_exits_1` covers the `codegen-dto --check` twin.
  `test_model_reader.py:208` checks the reader raises `ValueError`, not what the command does
  with it.
- **Regression that slips:** the `codegen` command letting a `SyntaxError`/`OSError` escape as
  a traceback, or exiting with a code other than 1, for a models file a user hand-edited
  (D9.1 says hand-edited files are supported, so this path is reachable in normal use).
- **Proved:** by coverage (lines 803-810 missing in the report); no mutation can be caught.
- **Suggested test:** in `TestAnnotationCheckOptionValidation`, write `models.py` containing
  `class Sales(SemanticView, view="sales_view"` (unclosed), run
  `codegen sales_view --backend duckdb --database … --check --model models.py` on the
  `duckdb_file_backed_db` fixture (or a mocked engine — the check must fail before
  connecting), assert `exit_code == 1`, `"Cannot parse model file"` in stderr, `"Traceback"`
  not in stderr. A second case with an unreadable file (`chmod 000`, skipped as root) covers
  the `OSError` wording at `model_reader.py:529`.

#### TST-2 — `create_async_engine` is tested only in its object-config form · **minor**

- **Untested src:** `src/semolina/config.py:411-419` (the `ImportError` re-raise whose message
  names `semolina[async]`) and `:426-427` (`create_async_engine("connection_name")` →
  `_read_connection`). Both missing in coverage. The sync twin `create_engine("name")` is
  tested in `test_config.py`; every async call site in `tests/` passes a `DuckDBConfig`.
- **Regression that slips:** the hint pointing at the wrong extra (the comment explains it
  must not be poolhouse's own message), or the named-connection path diverging from the sync
  one (wrong dialect, `config_path` ignored).
- **Proved:** by coverage.
- **Suggested tests:** (a) in `test_async_packaging.py`, a child interpreter with
  `sys.modules["anyio"] = None` calling `create_async_engine(DuckDBConfig(...))`, asserting the
  `ImportError` text contains `semolina[async]` and not `adbc-poolhouse[async]`; (b) in
  `test_config.py`, mirror the sync named-connection test with
  `create_async_engine("default", config_path=…)` on a DuckDB section and assert
  `isinstance(engine.dialect, DuckDBDialect)`, then `await engine.dispose()`.

#### TST-3 — DuckDB `where_clause` typed literals are never executed, only string-pinned · **minor**

- **Tests:** `tests/unit/test_sql.py:2455-2490` assert the rendered text of `DATE`, `TIMESTAMP`,
  `TIMESTAMPTZ`, `TIME`, `TIMETZ`, `INTERVAL`, `::BLOB` and Decimal literals. No test anywhere
  under `tests/unit` filters a live DuckDB query on a `date`, `datetime`, `time`, `timedelta`,
  `bytes` or `Decimal` dimension through `semantic_view(... where_clause := …)` (grep of
  `.where(` with those constructors finds only `to_sql()`-level cases; the one live DuckDB
  execution, `test_duckdbs_to_sql_output_runs`, covers an apostrophe and a Decimal *metric*
  in the outer `WHERE`, not the bound `where_clause` string).
- **Why it matters:** the string assertions are written from the same reasoning as the code.
  If the extension rejected a form (`INTERVAL '… microseconds'`, `'\xHH'::BLOB` inside a
  bound string), both the code and the test would agree and the suite would stay green.
- **Proved:** not a defect — I probed the extension directly
  (`/tmp/claude-0/review-tests/probe/literals.py`): all eight forms execute through
  `where_clause` and match the intended row. So this is a coverage gap, not a bug.
- **Suggested test:** one parametrised live test on a small fixture table with those column
  types (or extend `duckdb_file_backed_db`), `Model.query().metrics(total).where(dim == value)
  .execute()` for each value, asserting the single expected row. Eight cases, ~1s.

#### TST-4 — `semolina.dto.resolve_column_key` is public and exported but called by nothing · **minor**

- **Src:** `src/semolina/dto.py:191-229`, in `__all__` (`:54`). Coverage: body `224-229` never
  runs; `grep -rn resolve_column_key src tests` finds only its definition and docstring.
- **Regression that slips:** any change to its precedence (`validation_alias` → `alias` →
  name) — and since 0.7.0 freezes the public surface, shipping an untested public function
  is the expensive moment.
- **Suggested fix:** either three one-line tests beside `resolve_column_keys`'s
  (`validation_alias` str, `alias` str, neither) or remove it from `__all__` before the tag.

#### TST-5 — CLI output/config error paths without tests · **minor**

All uncovered; each is a two-line CliRunner test.

| Src | Path | Expected |
|---|---|---|
| `cli/codegen.py:536-540` | `--output` names an existing directory | exit 2, "is a directory" |
| `cli/codegen.py:658-664` | in-place write (stream/special path) hits `OSError` | exit 1, "could not write" |
| `cli/dto_codegen.py:364-368` | `--config path` whose file has no `[tool.semolina.dto]` | exit 2, "carries no" |
| `cli/dto_codegen.py:782-789` | `--check` where `check_dto` raises `ValueError` (field binds to no column) | exit 6, message, no traceback |

The dto-side `test_a_directory_that_does_not_exist_exits_2_before_connecting` covers the
missing-parent case, not the is-a-directory case.

#### TST-6 — two rows of the shared exit table are not exercised · **minor**

- **Src:** `src/semolina/cli/codegen.py:170-172` (`typer.Exit`/`typer.Abort` → `None`, so
  typer's own control flow is not reported as a failure) and `:181` (an unlisted error at
  `stage="setup"` → `None`).
- **Test:** `tests/unit/codegen/test_cli.py:855` `test_the_table` has `unlisted-propagates`
  only for `"warehouse"`, and no `Exit`/`Abort` row. GEN-04's promise is "one table for both
  commands"; a row that turns `typer.Exit(0)` into exit 1 would pass the current table test.
- **Suggested test:** add `pytest.param(lambda: typer.Exit(0), "warehouse", None)`,
  `pytest.param(lambda: typer.Abort(), "setup", None)` and
  `pytest.param(lambda: KeyError("bug"), "setup", None)` to the parametrisation.

#### TST-7 — static reader (`--check`, D9) robustness branches untested · **minor**

- **Src:** `src/semolina/codegen/static_reader.py:575-577` (inheritance cycle / no consistent
  MRO → "base classes were not followed" warning, falling back to the class alone),
  `:328-334` (`lookup` hitting `AliasResolutionError`/`CyclicAliasError` → `None`),
  `:382-390` (`_load_package_of` failing to load), `type_compare.py:164`
  (`typing_extensions.` canonicalised to `typing.`), `:233-236` (string forward reference that
  does not parse → `Unresolvable`).
- **Existing tests** (`test_model_reader.py:545`, `test_dto_reader.py:599,634`) reach "not
  followed" only through an unresolvable base, not through these branches.
- **Regression that slips:** `--check` crashing (instead of warning) on a committed file whose
  bases form a cycle as text (`class A(B)` / `class B(A)` is readable by griffe even though
  Python would refuse it), on a base imported from a package outside the search path, or on
  `typing_extensions.Annotated` annotations — and GEN-12's rule is "no field-like statement is
  skipped silently".
- **Suggested tests:** four committed-file fixtures, one per branch, each asserting the
  warning text and that the remaining classes are still checked.

#### TST-8 — the "same path via `DUCKDB_DATABASE`" case of the override note is untested · **minor**

- **Src:** `src/semolina/cli/dto_codegen.py:503-505` (`used == committed` → no note).
- **Test:** `tests/unit/codegen/test_dto_cli.py:1259`
  `test_no_announcement_when_nothing_overrides_the_config` deletes `DUCKDB_DATABASE`, so it
  returns at the `not from_environment` guard (`:496`) and the path comparison never runs
  (coverage confirms `:505` is missing). The test's name is honest; the case it does not
  cover is the environment set to the *same* path as the config.
- **Regression that slips:** a normalisation change (`~`, relative → absolute, symlink) making
  equal paths compare unequal, so every run with `DUCKDB_DATABASE` exported prints a spurious
  "overrides" note.
- **Suggested test:** set `DUCKDB_DATABASE` to the committed path spelled differently
  (relative vs absolute, or with `~`) and assert no `DUCKDB_DATABASE (` in stderr.

---

### Checked and *not* findings

- `Annotated[T, Field(...)]` DTO reading: the uncovered `dto_reader.py:325,329` are the
  non-`Annotated` tuple-subscript and no-`Field`-metadata fall-throughs; the real cases are
  tested at `test_dto_reader.py:299-323`.
- `config.py:535-537` (`_build_config` unsupported backend): unreachable, because
  `_read_connection` (`:161`) validates `type` first. Dead branch, not a test gap.
- `test_exceptions.py` reads module source with `ast`; it is a repository-inspecting test by
  design, but it protects a stated 0.7.0 invariant (API-03), guards its own non-vacuity, and
  there is no runtime-only way to enumerate "every class Semolina defines" without a registry.
- Snowflake introspection cassette keyed on `''` (57-02): the exact `SHOW COLUMNS IN VIEW`
  statement is pinned by `test_snowflake_engine.py:235,314,355`, so the upstream limitation is
  compensated.
- `sql.py:1238-1242` (unknown `Lookup` subclass / non-`Predicate` in `_compile_predicate`),
  `:1376-1380` (slot/param count mismatch): defensive branches behind `where()`'s FILT-09
  `TypeError` and the frozen `Lookup` set; not reachable through the public surface.
- `cursor.py:92` / `acursor.py:134` (`description is None` → `[]`): a DDL-style cursor; not a
  path a semantic-view query produces.
- 16 skips: all doctest `+SKIP`; the basedpyright and DuckDB-dependent tests ran.

### Scratch artefacts

- Coverage log: `/tmp/claude-0/review-tests/cov.log`
- Mutation logs: `/tmp/claude-0/review-tests/mut_M1_none_accepted.log`, `mut_M3_escape_bang.log`,
  `mut_M4_snowflake_backslash.log` (script: `/tmp/claude-0/review-tests/mutate.sh`)
- DuckDB literal probe: `/tmp/claude-0/review-tests/probe/literals.py`
- Throwaway copy of the tree: `/tmp/claude-0/review-tests/copy` (restored after each mutation)
