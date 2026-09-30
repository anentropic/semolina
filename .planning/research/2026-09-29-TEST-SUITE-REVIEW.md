# Test Suite Review

**Date:** 2026-09-29
**Scope:** every test module under `tests/` and `semolina-jaffle-shop/` — 1749 passing tests,
16 skipped, 2 strict xfails, 40 seconds under `-n auto`.
**Question asked:** are these well designed *as tests*?
**Actioned as:** Phase 52.1 (Test Suite Soundness), inserted 2026-09-29 — requirements TEST-01, TEST-06..12.

The core, query, SQL, cursor, async, registry and config modules were read in full. The
DTO and codegen modules were read by structure (every test name) plus the bodies of anything
that looked off, which covered all of their source-inspecting and planning-referencing tests.

## The short answer

Most of the suite is sound. The newer work in particular (DTO pre-check, codegen CLI, async
cancellation, the replay-backed integration tests) tests behaviour, names tests after what
they prove, and often checks its own guards are not vacuous.

The problems cluster into a few families. The first one matters most: a small number of
tests **cannot fail**, including two I proved by breaking the code and watching them stay
green. After that come tests that check something other than Semolina, the scope-fence
pattern again in several places, tests pinned to private internals, tests that pin bugs we
have already decided to fix, and a lot of duplication.

Rough size of the problem: about 150 tests are worth deleting outright, another ~75 are
type-map cases that run twice, about 30 need rewriting, and one design change (a single
mapping table in `arrow_map.py`) removes the need for two source-reading tests.

---

## 1. Tests that cannot fail

These are the ones that matter. A test that cannot fail gives false confidence, which is
worse than having no test.

### 1a. Proven by breaking the code

**`tests/unit/test_engines.py` — all four tests.** Each one checks that an incomplete
`Engine` subclass raises `TypeError`. They all pass because `Engine.__init__` requires
`pool=` and `dialect=` and the tests pass neither. A *complete* subclass raises the same
error:

```
TypeError: Engine.__init__() missing 2 required keyword-only arguments: 'pool' and 'dialect'
```

Two of the tests also describe methods that are not abstract (`to_sql` does not exist on
`Engine`; `execute` is concrete). Only `introspect` is abstract. This was recorded as CI-14
and TEST-01 for two of the four, but it applies to all four, including the `introspect` one.
A test of Python's `abc` machinery has little value anyway; one test asserting
`Engine.__abstractmethods__ == {"introspect"}` would say the whole thing.

**`test_async_engine.py:100` `test_concurrency_loop_stays_free_during_query`.** Its
docstring says that if the warehouse call ran on the event loop thread, the counter would be
0. I changed `aexecute` to call the driver synchronously on the loop
(`cur._cursor.execute(...)` in place of `await cur.execute(...)`) and the test still passed,
under both asyncio and Trio. The sibling task gets scheduled during the pool checkout and the
row iteration, so it counts whether or not the execute blocks. The test needs to spin only
while the execute is in flight, for example by blocking the driver call on an event that the
spinner sets.

### 1b. Tautologies left over from the `Field.__eq__` issue

Phase 52 fixed 28 of these in `test_query.py`. Two more remain, and both have the same
shape: tuple comparison falls through to `Field.__eq__`, which returns a truthy predicate.

- `test_models.py:300` — `assert q._metrics == (Sales.revenue,)`
- `test_query.py:1285` `test_shorthand_equivalent_to_builder` — compares two metric tuples
  with `==`. Since CORE-03 this can simply be `assert q_shorthand == q_builder`.

### 1c. Assertions too weak to catch anything

| Test | What it actually asserts |
|------|--------------------------|
| `test_python_renderer.py:963` `test_returns_string`, `:970` `test_valid_python_formatted` | `isinstance(result, str)`. The second one's own comment says "either formatted or unchanged — both are str". |
| `test_python_renderer.py:1099`, `:1113` | Same, for `render_and_format`: "both are valid". |
| `test_cursor.py:321` `test_close_calls_cursor_and_conn_close` | Nothing ("should not raise"). The name promises two calls are checked. |
| `test_cursor.py:197` `test_rowcount_delegates_to_underlying_cursor` | `isinstance(sc.rowcount, int)`. It does not check delegation. |
| `test_pool.py:437` `test_dispose_disposes_a_real_pool` | Nothing. |
| `test_query.py:647` `test_fetch_with_default_engine` | `len(rows) >= 1`. The comment gives the expected value (3500), but the test never checks it. |
| `test_query.py:1118` `test_model_centric_workflow_complete` | `len(rows) >= 1`, then `_ = row.revenue`. |
| `semolina-jaffle-shop/tests/test_warehouse_queries.py` (most tests) | `len(result) <= 10` and `all(... for row in result)`, which an **empty** result satisfies. These tests also never run in CI (no credentials), so nothing would notice. |

### 1d. Names that contradict the assertion

- `test_sql.py:535` `test_no_group_by_when_only_dimensions` asserts that `GROUP BY ALL` **is**
  present.
- `test_query.py:1017` `test_query_from_procedural_api_allows_mixing` never mixes anything.
  It asserts `q._model is None`.
- `test_models.py:422` `test_error_message_lists_alternatives` checks for "query" and
  "reserved" in the message, not any alternatives.

---

## 2. Tests that inspect the repository instead of running the code

This is the same kind of test as `test_scope_fence.py`: a policy check dressed up as a unit
test. There are more of them than I flagged in the first review. For each, the question is
whether the check belongs somewhere else, or shouldn't exist at all.

| Test | What it does | Better home |
|------|--------------|-------------|
| `test_type_fidelity_table.py` (whole file) | Reads a document under `.planning/phases/…`, checks that it follows the GSD archive layout, compares it byte for byte with regenerated output, and checks that its table has no column headed "value". | See below. |
| `test_asyncio_trio_matrix.py` (whole file) | Parses every other test file's AST to check that each async test module declares an `anyio_backend` fixture parametrized over both backends. | Define `anyio_backend` once in `tests/conftest.py`. Then every async test gets both backends by default, the ten copies of the fixture go away, and there is nothing left to enforce. |
| `codegen/test_arrow_map.py:213`, `:246` | Parses `arrow_type_to_python`'s own source for `return "..."` literals and checks that they match `_ANNOTATION_TO_TYPE`. | Fix the design: one table mapping each Arrow type to an (annotation, runtime type) pair. Then the two can't drift, and neither test is needed. As written, returning a value through a variable would make the check pass without checking anything. |
| `codegen/test_dto_codegen_e2e.py:921` | Parses `dto_renderer.py` for `except Exception`. | A lint rule: ruff `BLE001` / `E722` per-file. |
| `test_dto_packaging.py:277` | Parses `src/` for optional imports at module scope. | A lint rule: ruff `TID253` (`banned-module-level-imports`). |
| `test_async_packaging.py`, `test_dto_packaging.py` (pin checks) | Assert that `pyproject.toml` contains exactly `"pyarrow>=17.0.0"` and so on. | Nothing. These restate the config file, so every pin change means editing two files, and the test can only fail when someone changes the pin on purpose. Keep the **subprocess** tests in these files (`import semolina` does not import anyio / pandas / codegen). Those test real behaviour. |

**On `test_type_fidelity_table.py`.** TEST-03 already plans to *repair* this by moving the
artifact from `.planning/` into `tests/`. That is the mistake I made with the scope fence:
fixing the symptom without asking whether the thing should exist. The document is a Phase 47
research write-up, and the property users rely on is "the annotation codegen writes matches
the value the driver returns". `test_annotation_contract.py` already tests exactly that, by
`isinstance` against real values. I would delete `test_type_fidelity_table.py` and treat the
document as a historical record, which is what it is. TEST-03 would then shrink to "remove
it".

---

## 3. Tests of other people's code

These tests pass or fail depending on DuckDB, ADBC, pyarrow, pydantic, `dataclasses` or the
language itself, not on Semolina.

**Third-party libraries:**

- `test_pool.py` `TestDuckDBPoolLifecycle` and `TestDuckDBPoolIntegration` (7 tests). These
  run `SELECT 1`, a raw `GROUP BY` on `sales_data`, and check that DBAPI `description`
  entries have 7 elements. None of that is Semolina code. `test_pool_wiring_generates_correct_sql`
  repeats a `test_sql.py` check with weaker substring assertions.
- `test_type_fidelity_duckdb.py`: the "four named disagreements" (SUM widens to precision 38,
  AVG returns a double, MIN returns int32, COUNT is never null), DuckDB's parser error text,
  and the Arrow nullable flag. These record how DuckDB behaves, which was useful research. As
  tests, they break whenever DuckDB changes, whether or not Semolina is affected. The claim
  that matters for users is already covered by `test_annotation_contract.py`.
- `test_cursor.py` `TestFetchArrowTable`, `TestFetchRecordBatch`, `TestSemolinaCursorPassthrough`,
  and their async twins. One delegation test per method is enough; the rest checks the ADBC
  driver.
- `integration/test_type_fidelity.py` `…replay_schema_matches_raw_arrow_file` checks that
  pytest-adbc-replay reads its own cassette the same way pyarrow does.

A few of these are deliberate **canaries**, meaning they guard an assumption a Semolina
design decision depends on: `test_dto.py`'s `arrowmodel_really_does_refuse_*`, and
`test_async_cancel.py`'s `TestCancellationReachesTheDriver`, which is documented as the
control for the `aexecute` test. Those are worth keeping, provided each one names the
decision it protects. The rest can go.

**Python and `@dataclass`:**

- `test_filters.py`, about 70% of the file: the constructor stores its arguments, the class is
  frozen, `is_dataclass`, the `isinstance` hierarchy, and `test_predicate_is_not_dataclass`.
  `test_composition_creates_new_nodes` admits in a comment that it is "guaranteed" by
  freezing. What's worth keeping is the operator composition (`&`, `|`, `~`), and it is
  already tested again in `test_fields.py` and `test_query.py`.
- `codegen/test_introspector.py`, the whole file (20 tests of a frozen dataclass).
- `test_models.py`: `TestMetricFields`, `TestDimensionFields`, `TestFactFields` and
  `TestFieldReferences` are the same test four times.
- `test_config.py:213`, `:217` check that `_load_semantic_views` is callable and that its
  parameters are named `dbapi_conn` and `connection_record`.
- `test_public_surface.py` checks `assert JsonValue is not None` after a successful import (the
  import would already have raised), and substrings of a type alias's text.
- `test_dialect.py` checks StrEnum `.value` and equality with a string for every member.

---

## 4. Mirror tests

A mirror test derives its expected value from the code under test, so it can only agree
with it.

- `test_databricks_engine.py:155` builds `expected_sql` with the same builder `execute` uses,
  then asserts `execute` passed it along. If the builder is wrong, this still passes. Assert a
  literal SQL string instead.
- `test_python_renderer.py:1017` `test_isort_pass_applied_after_format` mocks
  `subprocess.run` with canned output, asserts the canned output comes back, and checks the
  argv. Ruff is a dev dependency, so run it for real on unsorted imports and check the result.
- `semolina-jaffle-shop/src/semolina_jaffle_shop/test_models.py` restates the model file
  field by field. Its docstring says it "validates dbt translation", but no translation
  happens: the models are written by hand. It also sits inside the package's `src/`, so it
  ships in the wheel.

---

## 5. Coupling to internals

Much of `test_query.py`, `test_sql.py` and `test_models.py` constructs `_Query()` with no
model, a state users can't reach, and then asserts on private fields (`_metrics`, `_filters`,
`_limit_value`, `_using`, `_model`, `_view_name`, `_fields`). It also injects filters with
`dataclasses.replace(query, _filters=...)` rather than `.where()`, and calls
`_compile_predicate` and `_validate_for_execution` directly.

One consequence: CORE-03 had to fix 28 tautological assertions, all of this shape. Another:
Phase 56's plan to make `Query` public, and Phase 53's plan to alias every column, will break
hundreds of these tests without any user-visible behaviour changing.

The fix is to test the builder through what a user sees, `Model.query()…to_sql()`, with
**exact** SQL strings. `test_sql.py` already does this for DuckDB (`assert sql == "SELECT
*\nFROM semantic_view(...)"`), but checks Snowflake and Databricks with substring
assertions like `'AGG("REVENUE")' in sql`. Those can't catch wrong ordering, duplicated
columns or a stray clause. `test_full_query_with_order_by` says "check order" and then checks
only that each keyword appears somewhere.

Smaller cases of the same thing: `test_dto.py:319` pins the private method name
`_iter_into_impl`, and the behaviour test right above it already covers the property.
`test_cursor.py:171` asserts that `_cursor`/`_conn`/`_pool` equal the constructor arguments.
`test_registry.py` asserts that the two stores are two dicts.

---

## 6. Tests that pin bugs we have already decided to fix

These will flip during Phase 52. When they do, the plan should rewrite them, not just delete
them.

| Test | Pins | Fixed by |
|------|------|----------|
| `test_dto.py:711` `test_timestamp_column_into_a_date_field_passes` | timestamp accepted into a `date` field | CORE-11 (52-05) |
| `test_fields.py:396` `test_in_returns_in` | `in_()` keeps the caller's list object | CORE-05 (52-03) |
| `test_cursor.py:873` `test_after_fetch_record_batch_raises_the_drivers_own_error` | ADBC's own "closed or consumed" text, not Semolina's error | CORE-08 (52-04) |
| `test_models.py:37` `test_model_definition_with_empty_view`, `test_registry.py` `test_register_with_empty_name` | an empty view name / engine name is accepted | Not planned. Worth deciding. |

`test_annotation_contract.py` handles the same situation well: a known gap is a
`pytest.mark.xfail(strict=True)` with a reason, so the day it is fixed the xfail turns red and
someone has to look.

---

## 7. Duplication and hygiene

**Duplicate tests:**
- In `test_query.py`, `TestQueryWhere` repeats `TestQueryFilter`, `TestExecuteMethod` repeats
  `TestQueryFetch`, and `TestFieldOperators` repeats the class of the same name in
  `test_fields.py`.
- `test_sql.py` checks the Snowflake FROM clause three times.
- `test_type_map.py` has one test per mapping *and* a parametrized table covering the same
  mappings, so every case runs twice.
- The missing-dependency guard tests are written out three times (sync cursor, async cursor,
  DTO).
- "Extension loaded" is checked in both `test_pool.py` and `test_config.py`.

**Dead pyright suppressions.** `tests/conftest.py`, `test_registry.py`, `test_config.py` and
`test_pool.py` start with `# pyright: reportAttributeAccessIssue=false` and a comment saying
"Plan 02 REMOVES this pragma" (Phase 44). Plan 02 never removed them. I deleted all four and
ran basedpyright over those files: **0 errors**. So they currently hide nothing, but they
switch off a strict check across four whole files for any future error.

**Other hygiene:**
- `tests/type_fidelity_probe.py` is a 2000-line support module, and ordinary unit tests
  (`test_cursor.py`, `test_dto_duckdb.py`) import from it, which ties them to the research
  tooling.
- `test_cursor.py:51` `_make_cursor` opens an ADBC connection per test and never closes it. It
  also creates every column as `VARCHAR`, so the tests compare `str(row.revenue) == "1000"`
  and could never notice a value-type regression.
- `test_query.py:1069` `test_execute_empty_vs_nonempty` registers engines without
  `try/finally`.
- The `unit` marker is on 7 files, never selected, and `--strict-markers` is off (TEST-06
  covers the other three markers).
- `clean_registry` is defined in `tests/conftest.py` (autouse) and again in
  `test_registry.py`.
- Test docstrings cite `.planning/WINDOWS.md`, `50-RESEARCH.md` R-02, "Phase 10.1", "QRY-04"
  and so on. Those references stop resolving once `gsd-cleanup` archives the phase
  directories. A test's docstring should say what it proves in its own words.
- `TestQueryStubs` ("stub methods for future phases") tests methods that are no longer stubs.
  `test_sql.py:1230` checks that a placeholder removed long ago is still absent.
- About 70 `# type: ignore` comments across the test tree, against CLAUDE.md's guidance.
  A third of them are in `integration/conftest.py`.

---

## 8. What is done well, and worth copying

- **Replay-backed integration tests** (`integration/test_queries.py`): each test checks the
  generated SQL (a mismatch is a cassette miss) *and* the exact result rows, on two
  backends, with no credentials.
- **Counting fakes for laziness**: `_CountingReader` / `CountingReader` assert *how many
  batches were pulled*, not how many rows came back. That is the property actually being
  claimed.
- **Checking the guard itself**: `test_the_fetch_guard_is_not_vacuous`, the "discovery is not
  vacuous" checks, and `test_the_type_check_cannot_quietly_vanish_from_a_dev_environment`.
- **Deterministic cancellation** (`test_async_cancel.py`, `TestDeterministicCancellation`):
  it tests slot release and cancellation transparency with no timing involved.
- **Injection tests that strip literals** (`outside_string_literals`): they assert what a
  parser would actually see, not substring counts.
- **DTO pre-check tests** (`test_dto.py`): one rule per test, both sides of every boundary,
  named as sentences.
- **Strict xfails** for known gaps.

---

## Recommended actions

In order of value. Items marked *(plan)* already have a home in the v0.7 roadmap; the rest
would be new work.

1. **Fix the tests that cannot fail** (§1): `test_engines.py` *(plan: TEST-01)*, the loop-free
   concurrency test, the two remaining tautologies, the §1c weak assertions, and the three
   misleading names. Small, and each fix can be checked by breaking the code the same way I
   did here.
2. **Delete the repository-inspection tests** (§2). Move `anyio_backend` into `conftest.py`,
   add ruff `BLE001` and `TID253` config, and merge the two `arrow_map` tables. Rewrite
   TEST-03 from "move the artifact" to "delete the guard".
3. **Delete the tests of other people's code** (§3). Keep the named canaries and write down
   which decision each one protects.
4. **Rewrite the builder tests against `to_sql()` with exact SQL** (§5). Do this before Phase
   53 (aliasing) and Phase 56 (public `Query`), because both will otherwise churn hundreds of
   private-attribute assertions for no behavioural reason.
5. **Hand the §6 tests to the plans that fix those bugs**, so each fix commit rewrites its test
   rather than deleting it.
6. **Hygiene** (§7): delete the dead pragmas, merge the duplicate tests, close the cursor
   fixtures, and take planning IDs out of test docstrings. This fits Phase 57's "test-suite
   structure" plan.
