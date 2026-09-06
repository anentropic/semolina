# Semolina codebase review (main @ ce5d52c, 2026-09-06)

Scope: correctness, CI and test coverage, and public-interface design. Every finding below was
reproduced against the code (Python 3.11 venv; the repo's own `.python-version = 3.14` resolved
to 3.14.0rc2 in this sandbox, on which locked pydantic 2.13.4 cannot import — a sandbox artefact,
not a repo bug, but see CI-6).

Gates as run locally: basedpyright 0 errors; ruff check/format clean; `sphinx-build -W` clean;
pytest 1736 passed / 17 skipped / 2 xfailed / 1 failed (`test_scope_fence`, shallow clone);
coverage 96% (not gated); jaffle-shop 16 passed / 15 skipped (no Snowflake creds). CI on main is
green at the latest commit.

---

## A. Correctness

### A1. Query builder / SQL compiler

| # | Sev | Where | Finding |
|---|-----|-------|---------|
| 1 | HIGH | `fields.py:411-430`, `engines/sql.py:933-940` | `in_()` accepts anything iterable. `in_("US")` compiles to `IN (?, ?)` bound to `['U','S']` — wrong rows, no error. A generator yields `IN (?)` with `[]` params (placeholder/param mismatch). Fix: materialise to tuple in `in_`, reject `str`/`bytes`. |
| 2 | HIGH | `fields.py:253` (`__eq__`), `fields.py:702` (`OrderTerm`), `query.py` dataclass eq | `Field.__eq__` returns a truthy `Exact`, so `Sales.cost in [Sales.revenue]` is `True`, `Sales.revenue.desc() == Sales.cost.desc()` is `True`, and two `_Query` objects with different metrics compare equal. `tests/unit/test_query.py:123,128,151,394-395` assert `q._metrics == (Sales.revenue,)` and are therefore tautological. Fix: `OrderTerm(eq=False)` + identity eq; `_Query(eq=False)` or custom eq; rewrite those tests to compare `.name`. |
| 3 | HIGH | `models.py:100-135` + `SemanticViewMeta.__setattr__` | Model inheritance is impossible: `class Sales2(Sales, view="sales_v2")` raises `AttributeError: Cannot modify Sales2._view_name after class creation` because `_frozen` is inherited from the parent before the child's own metadata is set. Also `cls.__dict__` only, so parent fields would not be inherited anyway, and `view=` is mandatory so abstract bases are impossible. Either support it (check `"_frozen" in cls.__dict__`, walk MRO for fields, allow `view=None` abstract bases) or raise a clear "subclassing models is not supported" error. |
| 4 | MED | `engines/sql.py:957-999` | LIKE-family lookups don't escape `%`/`_`. `iexact("50%")` (docstring says "no wildcards") matches `500`; `startswith("a_b")` matches `aXb`. The code comment defers this "to v0.3"; project is at 0.6/0.7. On Databricks `startswith("C:\\temp")` errors (backslash is the LIKE escape char). |
| 5 | MED | `engines/sql.py:897-901` | `Sales.country == None` compiles to `= ?` bound to `None` (matches nothing, silently). Django/SQLAlchemy rewrite to `IS NULL` or error. Same for `!= None`, `between(1, None)`. |
| 6 | MED | `engines/sql.py:1111-1130`, `query.py:to_sql` | `to_sql()` renders values via `repr()`: `"O'Brien"` (a double-quoted identifier in Snowflake), `datetime.date(2024, 1, 2)`, `Decimal('1.10')`, `= None`. Databricks path renders real literals, so the preview differs by dialect. `dialect.render_literal` already exists — use it. |
| 7 | MED | `engines/sql.py:1180-1193`, tutorial `shaping-a-report.rst:114` | `.where(Sales.revenue > 1000)` compiles to `WHERE "REVENUE" > ?` alongside `AGG("REVENUE") ... GROUP BY ALL`. No cassette records a WHERE on a metric on Snowflake/Databricks; the tutorial claims it "filters on the aggregated metric". Unverified, likely needs `HAVING` or rejection. DuckDB path silently widens the projection when a metric appears only in ORDER BY/WHERE (`sql.py:1375-1386`), so result shape differs by backend. |
| 8 | MED | `engines/base.py:181`, `sql.py:1224,1406` | `Engine.execute(_Query())` raises `AssertionError` (documented as `ValueError`); under `python -O` it becomes `AttributeError`. |
| 9 | MED | `snowflake.py:165`, `databricks.py:389`, `duckdb.py:604-610` | `introspect()` interpolates the raw view name into `SHOW COLUMNS IN VIEW {..}` / `DESCRIBE ...` unquoted. Injection surface if exposed; functionally, views needing quoting can't be introspected; DuckDB drops the schema segment. |
| 10 | MED | `engines/sql.py:379-387` | Pre-quoted view-name segments are emitted verbatim (unescaped); `analytics."my.view"` silently produces `"ANALYTICS"."""MY"."VIEW"""` instead of raising. |
| 11 | MED | `engines/sql.py:1096-1109` | Databricks inlining splits the whole SQL text on `?`; any identifier or `source=` containing `?` fails every query with a placeholder-count error. |
| 12 | LOW | `registry.py:62-64,104-106,251-285` | Registry is check-then-set with no lock; `reset()` iterates while another thread may register. |
| 13 | LOW | `snowflake.py:212-220`, `databricks.py:437-445`, `duckdb.py:700-705` | Introspect error mapping catches only Programming/OperationalError; DuckDB classifies by message substring. |
| 14 | LOW | `engines/sql.py` | 28 `# type: ignore[reportPrivateUsage]` comments for a rule pyproject already disables — dead noise contrary to CLAUDE.md. |

### A2. Cursor / Row / DTO

| # | Sev | Where | Finding |
|---|-----|-------|---------|
| 15 | HIGH | `results.py:35-53` | `Row` cannot be copied, deep-copied or pickled: `__getattr__` reads `self._data`, which is absent on an instance built without `__init__`, so it recurses (`RecursionError`, verified for all three). Blocks multiprocessing/Celery/caching. Add `__getstate__/__setstate__` or guard `name == "_data"`. |
| 16 | MED | `cursor.py:604-633`, `acursor.py:61-68` | Sync: `next(iter(cur))` then `fetchall_rows()` returns `[]` (batch already buffered). Async: same sequence raises poolhouse's `ConnectionBusyError` whose message blames cross-task sharing; the class docstring says this "requires deliberately sharing" a cursor, which is false. Untested. |
| 17 | MED | `cursor.py:84-152,608`, `pyproject` `snowflake` extra | `fetchall_rows`, `fetchone`, sync `__next__` need pyarrow via ADBC but have no `_require` guard; `pip install semolina[snowflake]` installs no pyarrow, so `for row in cursor` fails with a foreign ADBC error. Async `__anext__` is guarded — drift. |
| 18 | MED | `query.py:111-155`, `cursor.py:93,120,629` | `.metrics(Sales.revenue).metrics(Sales.revenue)` emits duplicate columns; `Row` construction silently keeps the last value. The DTO path detects duplicates (`REASON_DUPLICATE`); the Row path doesn't. |
| 19 | MED | `dto.py:335-336` | `_annotation_accepts` uses `issubclass`, so a `timestamp` column passes a `date`-annotated field and the instance holds a `datetime` (`dto.ts == date(...)` is False). |
| 20 | MED | `cursor.py:637-641,667-669` | Sync `close()` is not exception-safe: if `cursor.close()` raises, the connection is not returned and the teardown error masks the body's exception. `aclose()` handles this; the sync twin drifted. |
| 21 | MED | `results.py` | `Row` collides with its own dict-protocol names (`row.items` → bound method, `row["items"]` → value), is unhashable (`__eq__` without `__hash__`), has no `.get()`, isn't a `Mapping` (so `json.dumps(row)` fails). `RESERVED_FIELD_NAMES` reserves `get/pop/update/clear` that `Row` doesn't even implement. |
| 22 | LOW | `cursor.py:62`, `acursor.py:98` | `pool` ctor arg is dead. Sync `fetch_record_batch` doesn't record the reader; `close()` never closes it. |
| 23 | LOW | `dto.py:459`, `dto.py:163-169` vs `211-216` | `check_result_schema` is public but imports pyarrow unguarded; alias-priority rule implemented twice. |

### A3. Codegen / CLI

| # | Sev | Where | Finding |
|---|-----|-------|---------|
| 24 | HIGH | engines `IntrospectedField.name`, `templates/python_model.py.jinja2:213-215`, `python_renderer.py:480-481` | `semolina codegen` emits invalid Python for a column named `CLASS` or `"ORDER DATE"`, a view named `2024_sales`, or two columns that fold to the same name — exit 0, no warning. The ruff formatter's non-zero exit is swallowed, so the one thing that would notice stays silent. The DTO path has all the guards (`is_valid_class_name`, `_check_dto_field_name`, duplicate detection); the model path has none. Minimum: validate names and `ast.parse` the output before emitting. |
| 25 | MED (security) | `cli/codegen.py:169-177` | On a config `ValidationError`, the pydantic error (which includes `input_value={'user': ..., 'password': 'hunter2'}`) is printed verbatim to stderr. Use `e.errors(include_input=False)`. |
| 26 | MED | `cli/codegen.py:191-193,392-405,414-425` | Expected failures (driver extra missing → `ImportError`; unmapped `adbc_driver_manager.Error` subclasses; `--backend` dotted path needing ctor args) escape as raw tracebacks with exit 1, contradicting the documented exit-code contract. `codegen-dto` handles these; `codegen` doesn't. |
| 27 | MED | `cli/codegen.py:430`, `dto_codegen.py:765` | `typer.echo(source)` appends a second trailing newline, so the documented `> models.py` workflow immediately fails `ruff format --check`. `--output` doesn't. Use `nl=False`. |
| 28 | MED | `python_renderer.py:471,486` | Ruff is invoked with `--stdin-filename models.py`, so it picks up the cwd's `pyproject.toml`; output differs by working directory (spurious diffs). Pass `--isolated` or resolve against the output dir. |
| 29 | MED | `cli/codegen.py` | No `--output` on `codegen`; shell redirect truncates `models.py` before any error, leaving an empty file. `_emit` in `dto_codegen` is also not atomic (`write_text`). |
| 30 | MED | `codegen/dto_config.py:366` | `database = "~/x.db"` becomes `<config-dir>/~/x.db` (`expanduser` after join). |
| 31 | LOW | `dto_codegen.py:796-804,437` | `DUCKDB_DATABASE` env var silently overrides a committed config with no message. |
| 32 | LOW | `model_reader.py:35-42`, `annotation_check.py:464-465` | `--check` always reports drift for an untyped `Metric()` (`Any` vs `Any | None`). |
| 33 | LOW | `annotation_check.py:404-408` | `--check` exits 0 when the probe failed and it fell back to metadata — CI can't distinguish. |
| 34 | LOW | `cli/utils.py` | `resolve_input_paths`, `make_stderr_console` are dead code with tests. |

---

## B. CI, tests, packaging

| # | Sev | Where | Finding |
|---|-----|-------|---------|
| CI-1 | HIGH | `release.yml:3-7`, `ci.yml:7-8`, `pyproject.toml:3` | Releases are not gated on CI (tag push triggers release; CI ignores tags), and nothing checks `github.ref_name` == `semolina.__version__`. Version is static `0.6.0` while planning says v0.7 is ready; no tags exist yet. A `v0.7.0` tag would publish `semolina-0.6.0` (or fail late at PyPI). |
| CI-2 | HIGH | `justfile:14-16` vs `ci.yml:114` | `just test` runs a materially weaker suite than CI: `uv sync --dev` installs none of duckdb/snowflake/polars/pandas/arrowmodel, so ~54 unit files `importorskip` silently. Conversely `just test` runs all 31 jaffle-shop tests while CI runs `-m duckdb` (13). Nothing documents this; `MAINTAINER.md` is one line. |
| CI-3 | HIGH | `tests/unit/test_scope_fence.py:157,561-574` | Hard-codes commit SHA `9f3c8b9…` and `test_the_default_base_ref_resolves_here` fails unconditionally on any shallow clone (fork, `--depth`, other workflows), despite the docstring promising a skip. Failed here. |
| CI-4 | MED | `ci.yml:3-8,140-141` | Workflow only triggers on `push`; the coverage-comment step (`if: pull_request`) is dead code, fork PRs get no CI, and coverage XML is discarded (no `fail_under`, no artifact). |
| CI-5 | MED | `docs.yml:5-9` | `just docs-build` is a CLAUDE.md gate but only runs on push to main — broken cross-refs are found after merge. |
| CI-6 | MED | `ci.yml:88`, `.python-version` | Matrix is 3.11 + 3.14 only; 3.12/3.13 never run despite four resolution markers in `uv.lock`. Default dev interpreter is 3.14 (here an rc that can't import pydantic). |
| CI-7 | MED | `.pre-commit-config.yaml:11` | Pre-commit ruff pinned to v0.9.6; CI/dev use 0.15.20. Hooks and CI can disagree. |
| CI-8 | MED | `src/semolina/conftest.py`, `src/semolina/testing/` | Both ship in the wheel; conftest imports `pytest` at module scope (not a runtime dep); `testing` is empty. A root `conftest.py` covers `src/` for doctests. |
| CI-9 | MED | `pyproject.toml:10-15` | `typer`, `rich`, `jinja2` are hard deps used only by `cli/` and `codegen/`; a query-only backend service pulls Click/Rich/shellingham/Jinja2. A `[cli]` extra with the existing `_require` pattern fits. `adbc-poolhouse` also drags SQLAlchemy + pydantic-settings into every install and `import semolina` eagerly imports `config`. |
| CI-10 | MED | `tests/integration/` | Only 7 query shapes × 2 backends genuinely recorded; async and type-fidelity cassettes are copies ("Nothing here is recorded"). No Snowflake introspection cassette. `warehouse`/`snowflake`/`databricks` markers unused in root suite. |
| CI-11 | LOW/MED | `tests/unit/test_type_fidelity_table.py:291-296` | Unit test byte-compares a document under `.planning/` that embeds DuckDB versions; the automated duckdb-pin PR (`duckdb-extension-check.yml`) can't trigger CI (GITHUB_TOKEN) and will fail this after merge. |
| CI-12 | LOW | `tests/unit/test_async_cancel.py:149,715,804,827` | Wall-clock ratio assertions under `-n auto` on shared runners; `tests/conftest.py:207` does a per-worker community-extension `INSTALL` with no retry. |
| CI-13 | LOW | `pyproject.toml:25` | Advertised Changelog URL (`/changelog/`) has no page in docs; git-cliff output is only a release artifact. |
| CI-14 | LOW | `tests/unit/test_engines.py:24-60` | `test_engine_to_sql_is_abstract` / `test_engine_execute_is_abstract` pass only because the ctor needs kwargs; `to_sql` doesn't exist on `Engine`. Also `test_query.py` metric-tuple asserts are tautological (finding 2). |
| CI-15 | LOW | root `[tool.basedpyright] include` | `semolina-jaffle-shop/` is never type-checked anywhere. |

---

## C. Public interface design

1. **Result column names are not portable (the big one).** No `AS` aliases are emitted (`sql.py:1180-1193`), so the same query yields `revenue` on DuckDB, `AGG("REVENUE")` on Snowflake, `measure(revenue)` on Databricks. `row.revenue` raises on the two flagship backends, the README example is wrong there, and a DTO needs a per-warehouse `validation_alias`, so a DTO tested on DuckDB can't run in production. The dialect knowledge already exists (`Dialect.metric_result_column_name`). Emitting `AS "<python_field_name>"` at one site fixes Row, DTO, codegen-dto and the docs' longest warning together.
2. **The "strongly typed" promise stops at the model.** `Metric[Decimal]` is never used at result time; `fetchall_rows() -> list[Row]` and `Row.__getattr__ -> Any`. Types require a second hand-written Pydantic class per query. Builder methods are annotated `Any` (`query.py:111,155,243,279,308`): `.metrics(Sales.country)`, `.limit("10")`, `.limit(True)` all type-check.
3. **`_Query` is private-named but is the return type of `Model.query()`.** Users can't annotate a helper that returns one without importing a private name. Same for `Field` (base) and `Engine`/`AsyncEngine`, none exported from the root.
4. **Exceptions.** Deliberately no `SemolinaError` base (`exceptions.py` docstring). For a backend-service audience, one `except SemolinaError` is what people reach for; the stated reason (not reparenting engine errors) doesn't hold since the engine errors are Semolina's own. Engine errors live in `engines.base`, others in `exceptions` — inconsistent. `get_engine` raises bare `ValueError` for "not registered".
5. **Two things named `Dialect`** (the `StrEnum` exported from root; the ABC in `engines/sql`). `Engine.dialect` holds the ABC; `to_sql(dialect=)` takes the enum. `to_sql()` defaults to Snowflake regardless of which engine is registered.
6. **Sync/async naming is asymmetric**: `execute`/`aexecute` but `dispose`/`dispose`, `connect`/`connect`; `async with await q.aexecute()` is an awkward double keyword. `fetch_df` (pandas) vs `fetch_polars`/`fetch_arrow_table`.
7. **No `.offset()`**, documented, with a reasonable keyset-pagination rationale. Fine as a choice; worth keeping visible.
8. `__all__` missing on `sql.py`, `registry.py`, `config.py`, `query.py`, `filters.py`, `fields.py`; `engines/__init__` omits `AsyncEngine` and the two error classes. `Row` should probably register as `collections.abc.Mapping`.

---

## D. What to do first

1. Alias result columns to Python field names (C1). Largest usability win; unblocks portable DTOs and makes the README true.
2. Fix `Row` copy/pickle recursion (15), `Field`/`OrderTerm`/`_Query` equality (2), model inheritance error (3), `in_()` input validation (1).
3. Codegen: validate identifiers + `ast.parse` before emit (24); stop echoing the pydantic error with inputs (25); `nl=False` (27); add `--output` (29).
4. CI: add `pull_request` trigger (CI-4); gate release on CI and assert tag == version (CI-1); run docs build on PRs (CI-5); make `just test` sync `--extra all` (CI-2); guard or drop the scope-fence SHA test (CI-3); align pre-commit ruff with the lock (CI-7); add a `coverage fail_under`.
5. Decide `== None` → `IS NULL` (5) and LIKE escaping (4); resolve the metric-in-WHERE question against a real warehouse (7).
6. Move `typer/rich/jinja2` behind a `[cli]` extra; drop `src/semolina/conftest.py` and empty `testing/` from the wheel (CI-8, CI-9).
