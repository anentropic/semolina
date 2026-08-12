---
phase: 48-type-map-implementation-databricks-literals
plan: 02
subsystem: engines/sql
tags: [databricks, dialect, sql-literals, decimal, datetime, tdd, injection]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "Decision 1's Decimal policy, which makes a decimal.Decimal a value users now naturally hold and therefore pass to .where()"
provides:
  - "Dialect.render_literal accepts datetime.date, datetime.datetime and decimal.Decimal with standard-SQL escaping (D-07)"
  - "DatabricksDialect.render_literal accepts the same three types with Spark escaping (DBX-04)"
  - "Aware datetimes normalise to UTC and render TIMESTAMP '...Z' (D-08)"
  - "_timestamp_literal_text — the shared, escaping-free ISO-8601 formatter both dialects call"
  - "A single evaluated escaping expression per render_literal body, shared by str, date and datetime"
affects: [48-03, 48-04, 48-05, 48-06, phase-49-into-dto]

actuals:
  tokens: 4164
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Typed-literal rendering as (prefix, text) selection followed by one shared quote-escape, so the audited escaping site stays literally single"
    - "Subclass-ordered isinstance chains with the ordering rationale stated in a comment at the branch"

key-files:
  created: []
  modified:
    - src/semolina/engines/sql.py
    - tests/unit/test_sql.py

key-decisions:
  - "The str branch was folded into the same if/elif chain as date and datetime rather than left standing above three new branches: the plan required the new types to use 'the SAME string-escaping expression the str branch uses', and three copies of that expression would have been three sites, not one"
  - "_timestamp_literal_text is a module-level function, not a method: both dialects need byte-identical D-08 normalisation, and it formats without escaping so it does not become a second escaping site"
  - "The re-pointed negative guards use {1, 2} (a set) rather than complex(1, 2) — a set is the type most likely to be passed by accident to a filter, so the guard also documents a real mistake"
  - "The end-to-end inlining test filters on the field name 'date_key', which the shared Sales test model does not declare; predicates carry field-name strings and _compile_predicate never resolves them against the model, so no fixture change was needed"

patterns-established:
  - "When a plan says 'use the same expression', restructure so there is one expression rather than copying it"

requirements-completed: [DBX-04]

coverage:
  - id: D1
    description: "Both dialects render a date as DATE 'yyyy-mm-dd'"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_date_literal, ::TestRenderLiteralDatabricks::test_date_literal"
        status: pass
    human_judgment: false
  - id: D2
    description: "A naive datetime keeps its time of day and its microseconds — never truncated to a date by the subclass trap"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_naive_datetime_literal, ::test_datetime_microseconds_survive (and the Snowflake twins)"
        status: pass
    human_judgment: false
  - id: D3
    description: "An aware datetime normalises to UTC and emits the Z zone id (D-08)"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_aware_datetime_normalises_to_utc_z (and the Snowflake twin)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A finite Decimal renders as bare fixed-point digits with no CAST and no exponent; NaN/Infinity raise ValueError"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_decimal_literal_is_bare_fixed_point, ::test_decimal_exponent_form_stays_decimal, ::test_non_finite_decimal_raises (and the Snowflake twins)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A Databricks .where() on a date inlines DATE '2024-01-31' and returns an empty parameter list — the end-to-end DBX-04 claim, asserted offline"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestDatabricksLiteralInlining::test_date_filter_inlines_with_empty_params"
        status: pass
    human_judgment: false
  - id: D6
    description: "Rendered date and timestamp literals carry exactly their two delimiting quotes; a Decimal literal is digits, an optional sign and at most one point (T-48-05, T-48-06)"
    requirement: DBX-04
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::*::test_date_literal_has_no_unescaped_quote, ::test_timestamp_literal_has_no_unescaped_quote, ::test_decimal_literal_is_digits_only"
        status: pass
    human_judgment: false
  - id: D7
    description: "Both 'fails loudly' guards survive, re-pointed at a still-unsupported type"
    verification:
      - kind: unit
        ref: "tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_unsupported_type_raises_not_implemented, ::TestRenderLiteralDatabricks::test_unsupported_type_raises_not_implemented"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 02: Databricks date/datetime/Decimal Literals Summary

**A Databricks filter on a `date`, `datetime` or `Decimal` now inlines a correctly typed SQL literal with an empty parameter list instead of raising `NotImplementedError` — and the timestamp branch is ordered ahead of the date branch so a `datetime` can never be silently truncated to a whole day.**

## Performance

- **Duration:** 9 min
- **Tasks:** 2 (2 commits — RED then GREEN, in that order)
- **Files changed:** 2 (0 created, 2 modified)

## The recorded RED output

Task 1's tests were written and committed against the unchanged `src/`. The run before any source edit:

```
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_date_literal
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_naive_datetime_literal
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_aware_datetime_normalises_to_utc_z
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_datetime_microseconds_survive
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_decimal_literal_is_bare_fixed_point
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_decimal_exponent_form_stays_decimal
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_non_finite_decimal_raises
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_date_literal_has_no_unescaped_quote
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_timestamp_literal_has_no_unescaped_quote
FAILED tests/unit/test_sql.py::TestRenderLiteralStandardSql::test_decimal_literal_is_digits_only
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_date_literal
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_naive_datetime_literal
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_aware_datetime_normalises_to_utc_z
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_datetime_microseconds_survive
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_decimal_literal_is_bare_fixed_point
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_decimal_exponent_form_stays_decimal
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_non_finite_decimal_raises
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_date_literal_has_no_unescaped_quote
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_timestamp_literal_has_no_unescaped_quote
FAILED tests/unit/test_sql.py::TestRenderLiteralDatabricks::test_decimal_literal_is_digits_only
FAILED tests/unit/test_sql.py::TestDatabricksLiteralInlining::test_date_filter_inlines_with_empty_params
================ 21 failed, 22 passed, 136 deselected in 0.50s =================
```

The failure cause, identically for every date/datetime/Decimal case:

```
E       NotImplementedError: Cannot render SQL literal for unsupported type: date. Add handling in render_literal() for this type.
src/semolina/engines/sql.py:426: NotImplementedError
```

21 failures against a floor of 8. The RED commit (`fa24cae`) touches `tests/unit/test_sql.py` and nothing else; `git log -1 --name-only` on it lists no file under `src/`. Phase 45's recorded obstacle — basedpyright strict rejecting a test that references a not-yet-existent attribute — did not apply here, because `render_literal` already existed and only its accepted value types changed. A genuine two-commit RED/GREEN sequence was therefore possible, and is what landed.

## The exact rendered strings

All four value shapes, on `DatabricksDialect`. The base `Dialect` (exercised through `SnowflakeDialect`) returns byte-identical strings for these inputs: neither an ISO-8601 date/timestamp nor a fixed-point digit string contains a quote or a backslash, so standard-SQL doubling and Spark backslash-escaping have nothing to act on.

| Input | Rendered literal |
|---|---|
| `datetime.date(2024, 1, 31)` | `DATE '2024-01-31'` |
| `datetime.datetime(2024, 1, 31, 10, 5)` | `TIMESTAMP '2024-01-31T10:05:00'` |
| `datetime.datetime(2024, 1, 31, 10, 5, tzinfo=+02:00)` | `TIMESTAMP '2024-01-31T08:05:00Z'` |
| `datetime.datetime(2024, 1, 31, 10, 5, 3, 123456)` | `TIMESTAMP '2024-01-31T10:05:03.123456'` |
| `Decimal("10.50")` | `10.50` |
| `Decimal("1E+2")` | `100` |
| `Decimal("NaN") / Decimal("Infinity") / Decimal("-Infinity")` | `ValueError` |

And end to end, through `DatabricksSQLBuilder.build_select_with_params`:

```
`date_key` = DATE '2024-01-31'     params == []
```

`10.50` and `100` are unquoted and uncast, which is the whole point of Pitfall 3: Databricks documents a bare fractional literal as *already* DECIMAL, and it is the `D` suffix or an `E` exponent that demotes one to DOUBLE. `format(value, "f")` is used rather than `str(value)` precisely because `str(Decimal("1E+2"))` is `1E+2` — the exponent form that would have made a decimal comparison a floating-point one. `grep -c 'CAST(' src/semolina/engines/sql.py` is 0, unchanged from before the task.

## The type chosen for the re-pointed guards

**`{1, 2}` — a `set`.** Both `test_unsupported_type_raises_not_implemented` bodies previously passed `datetime.date(2024, 1, 1)`, the exact value this plan legalises. Neither was deleted; both now pass a set, which stays unsupported and is the type a user is most plausibly going to hand a filter by accident (writing `{...}` where a `list` was meant). `grep -c 'def test_unsupported_type_raises_not_implemented'` is 2 and `grep -c 'render_literal(datetime.date(2024, 1, 1))'` is 0.

## No live Databricks workspace verified any of this

**The literal forms above rest on the Databricks documentation quoted in `48-RESEARCH.md` § "DBX-04 — `render_literal` widening", plus the offline inlining test. Nothing in this plan executed a query against a Databricks workspace.** Specifically unverified against a live engine:

- That `DATE '2024-01-31'` and `TIMESTAMP '2024-01-31T08:05:00Z'` are accepted by the Databricks metric-view planner (as opposed to merely being valid Spark SQL literal syntax).
- That a bare `10.50` compares as DECIMAL rather than being coerced to DOUBLE in a metric-view predicate.
- The `Z` choice in D-08 itself. `48-RESEARCH.md` A6 records that the same doc page produced contradictory readings of the bare `+hh:mm` offset form; `Z` was chosen because it is the one form nobody disputed. This is a documentation-confidence decision, not a measured one.

`SQLBuilder._render_literal_sql` is generic, so the offline test proves the widening is *sufficient* — the renderer is the only thing between a Python value and the SQL text. It cannot prove the warehouse accepts the result.

### The Decimal precision backstop

A `Decimal` with more than 38 significant digits renders as its bare fixed-point digit string and is left for the warehouse to reject. Semolina adds no client-side precision or scale check, because no live Databricks workspace is available to establish what that rejection looks like — inventing a client-side limit would risk rejecting values the warehouse would have accepted. This is the plan's `verification: backstop` truth, carried forward as stated.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 2 - Critical] The `str` branch was folded into the new if/elif chain rather than left above it**

- **Found during:** Task 2.
- **Issue:** The plan asked for the new branches to be "inserted after the existing `str` branch and before the `NotImplementedError` tail", and separately required each new literal to be quoted "by the SAME string-escaping expression the `str` branch of that method uses". Taken literally those two instructions conflict: leaving the `str` branch in place and adding `escaped = text.replace(...)` inside each of the date and datetime branches produces **three copies** of the escaping expression per method, six across the file. `sql.py`'s own docstring calls this "the single audited SQL-literal escaping site", and a future edit to one copy would silently diverge from the other two — the exact class of defect the single-site claim exists to prevent.
- **Fix:** `datetime` / `date` / `str` are now three arms of one `if/elif/elif/else` chain that select a `(prefix, text)` pair; the `else` arm raises `NotImplementedError` as before; one `escaped = ...` and one `return f"{prefix}'{escaped}'"` follow the chain. Each method still evaluates its escaping expression in exactly one place. Ordering, behaviour and the raised exception types are unchanged for every previously supported value.
- **Files modified:** `src/semolina/engines/sql.py`
- **Commit:** `e9d6ba0`

**2. [Rule 3 - Blocking] `_timestamp_literal_text` added as a module-level function**

- **Found during:** Task 2.
- **Issue:** D-08's normalisation (aware -> UTC -> drop tzinfo -> isoformat -> append `Z`) is four steps that must be byte-identical in both dialects. Inlining it twice invites the two copies to drift, and the divergence would be invisible until a user in a non-UTC zone got wrong rows.
- **Fix:** One private module-level function, called from both bodies. It is **not** a second escaping site: it performs no escaping at all, and everything it returns still goes out through the caller's own `.replace(...)` expression. Its docstring says so explicitly, so a later reader does not mistake it for one.
- **Files modified:** `src/semolina/engines/sql.py`
- **Commit:** `e9d6ba0`

**3. [Rule 1 - Bug, upstream tooling] `datetime.timezone.utc` rewritten to `datetime.UTC`**

- **Found during:** Task 2, `prek run --all-files`.
- **Issue:** ruff's UP017 rewrote the `datetime.timezone.utc` the plan's action text prescribed. Not a defect — `datetime.UTC` is the same object, available since 3.11, and the project floor is `>=3.11`. Recorded because the plan text names the older spelling and a reader diffing the two would otherwise wonder.
- **Files modified:** `src/semolina/engines/sql.py` (by the hook)
- **Commit:** `e9d6ba0`

## Findings

**No call site needed changing, exactly as the plan predicted.** `SQLBuilder._render_literal_sql` zips SQL segments with `self.dialect.render_literal(param)` and inspects no types; `build_select_with_params` returns `(inlined_sql, [])` whenever `supports_parameterized_queries` is false. Widening the renderer was sufficient for the end-to-end claim, and `test_date_filter_inlines_with_empty_params` passes with zero non-test changes outside the two `render_literal` bodies.

**The end-to-end test needed no fixture change.** The plan's behaviour line describes `.where(Model.date_key == date(...))`, and the shared `Sales` test model declares no date field. It did not matter: `Exact` and its siblings store a field-name *string*, and `_compile_predicate` quotes it through `dialect.normalize_identifier` without ever resolving it against a model. The test filters on `"date_key"` and asserts on `` `date_key` = DATE '2024-01-31' ``. Recorded so a later plan does not add a date column to `tests/models.py` believing this test required one.

**The base dialect's new branches are currently unreachable in production.** `DatabricksDialect` is the only dialect that sets `supports_parameterized_queries = False`, so `Dialect.render_literal` is reached today only from tests. D-07 widened it anyway, and that is the point: the gap would otherwise reappear the moment any other dialect flipped the flag. `TestRenderLiteralStandardSql` keeps the base honest in the meantime.

## Verification

| Gate | Result |
|---|---|
| `uv run pytest tests/unit/test_sql.py` | 179 passed |
| `just test` — root suite | 1127 passed, 16 skipped |
| `just test` — semolina-jaffle-shop suite | 16 passed, 15 skipped |
| `prek run --all-files` (ruff lint+format, basedpyright strict) | clean |
| `tests/unit/test_scope_fence.py` | 1 passed |
| `git diff 9f3c8b9..HEAD` naming `cursor.py` / `acursor.py` / `results.py` | none |
| RED commit before GREEN in `git log` | `fa24cae` then `e9d6ba0` |
| `# type: ignore` added in this plan's diff | 0 |
| `grep -c 'CAST(' src/semolina/engines/sql.py` | 0 (unchanged) |
| `datetime.datetime` branch line number below `datetime.date` in both bodies | 166 < 168, 488 < 490 |

## Known Stubs

None. No stub values, no skipped tests, and no `<verify>` block went unrun.

## Threat Flags

None new. The four `mitigate` dispositions this plan owned are implemented and asserted:

- **T-48-05** (user value into inlined SQL): every date and timestamp goes through the same escaping expression as a plain string, and that expression is now evaluated exactly once per method. `test_date_literal_has_no_unescaped_quote` / `test_timestamp_literal_has_no_unescaped_quote` assert each literal carries exactly its two delimiting quotes.
- **T-48-06** (Decimal branch): `format(value, "f")` emits only digits, an optional `-` and at most one `.` — asserted by `test_decimal_literal_is_digits_only`. `NaN`/`Infinity` are rejected before rendering, so no `nan` token can reach the SQL text.
- **T-48-07** (branch order): `datetime` is tested before `date` in both bodies, with the rationale in a comment at the branch and the `bool`-before-`int` precedent cited. `test_naive_datetime_literal` and `test_datetime_microseconds_survive` fail if the order is ever swapped.
- **T-48-08** (DECIMAL vs DOUBLE): `test_decimal_exponent_form_stays_decimal` pins `Decimal("1E+2")` to `100`.

T-48-09 stays `accept` — the new `ValueError` message interpolates `{value!r}` exactly as the pre-existing float branch does. No packages were installed (T-48-SC).

## Self-Check: PASSED

- `src/semolina/engines/sql.py` — FOUND
- `tests/unit/test_sql.py` — FOUND
- Commit `fa24cae` (RED) — FOUND in `git log`
- Commit `e9d6ba0` (GREEN) — FOUND in `git log`
