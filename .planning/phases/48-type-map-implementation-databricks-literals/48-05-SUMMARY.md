---
phase: 48-type-map-implementation-databricks-literals
plan: 05
subsystem: codegen
tags: [check, drift, cli, ast, probe, exit-codes, evidence-limits]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "Decision 2 (metric nullability), Decision 3 (result schema primary, route recorded), and the measured metadata-vs-result-schema divergence --check exists to surface"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 03
    provides: "the measured annotation contract --check compares against, and its evidence limits"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 04
    provides: "semolina.codegen.probe (probe_schema, ProbeResult, ROUTE_EXECUTE_SCHEMA, ROUTE_ZERO_ROW) and semolina.codegen.arrow_map.arrow_type_to_python"
provides:
  - "semolina codegen --check --model PATH — reports annotation drift against the warehouse's current result schema, fetching no data rows (TYPE-07)"
  - "EXIT_ANNOTATION_DRIFT = 5, distinguishable from 1 (the tool broke), documented in the CLI epilog"
  - "semolina.codegen.model_reader — read a committed model's annotations by ast.parse, never by import"
  - "semolina.codegen.annotation_check — check_view, ViewCheckReport, FieldCheckRow, ROUTE_METADATA"
  - "semolina.codegen.python_renderer.metric_annotation — Decision 2's nullability rule, now shared instead of inline"
  - "a diagnostics console that resolves sys.stderr at write time, so CLI stderr is capturable"
affects: [48-06, phase-50-typed-dtos]

actuals:
  tokens: 20123
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Read a user-supplied Python file structurally with ast.parse; importing it is code execution with extra steps"
    - "A fallback route is named on every row it produced, so a green result can never hide it"
    - "Derive a result-column name from the same dialect that built the SQL, rather than tabulating per-backend spellings"
    - "When a no-side-effects claim is untestable as stated, narrow the guard to what the claim actually means and prove the guard non-vacuous"

key-files:
  created:
    - src/semolina/codegen/model_reader.py
    - src/semolina/codegen/annotation_check.py
    - tests/unit/codegen/test_model_reader.py
    - tests/unit/codegen/test_annotation_check.py
    - tests/unit/codegen/conftest.py
  modified:
    - src/semolina/codegen/python_renderer.py
    - src/semolina/cli/codegen.py
    - src/semolina/cli/__init__.py
    - tests/unit/codegen/test_cli.py
    - .planning/WINDOWS.md

key-decisions:
  - "Result-column names are derived from the dialect that built the SQL (name, resolved column, then wrap_metric/quote_identifier), not matched by field name alone. Without it --check on Snowflake would report 100% spurious drift, because the result column is AGG(\"REVENUE\") and the field is revenue. Proven against the real recording: deleting the wrap_metric candidate turns the Snowflake test red."
  - "The no-rows guarantee is scoped to the view's DATA. engine.introspect() fetches catalogue rows from DESCRIBE SEMANTIC VIEW and always has; the plan's 'patch fetchall to raise' criterion is unsatisfiable as written on any backend. The guard permits DESCRIBE/SHOW fetches and refuses everything else, and it was proven non-vacuous."
  - "ViewCheckReport gained probe_error beyond the planned three fields. 'The probe was unavailable' without saying why is the kind of silence this phase exists to remove."
  - "_stderr became Console(stderr=True). The old Console(file=sys.stderr) pinned the stream captured at import, so every CLI diagnostic escaped CliRunner and any embedding process."
  - "The per-field table prints on every run, clean or drifted. Printing only on drift would satisfy 'nothing on stdout' while quietly dropping the route report a green fallback run depends on."

patterns-established:
  - "Prove the guard: every new assertion here was broken deliberately and watched go red before being committed"
  - "An acceptance criterion whose grep contradicts its own intent is recorded as unsatisfiable-as-written and verified by parsing the code instead"

requirements-completed: [TYPE-07]
requirements-partial: []

coverage:
  - id: D1
    description: "--check exits 0 on a matching committed model and 5 on a drifted one, live against DuckDB"
    requirement: TYPE-07
    verification:
      - kind: e2e
        ref: "tests/unit/codegen/test_cli.py::TestAnnotationCheckAgainstLiveDuckDB::test_a_freshly_generated_model_exits_0_with_empty_stdout, ::test_an_edited_annotation_exits_with_the_drift_code"
        status: pass
    human_judgment: false
  - id: D2
    description: "A --check run fetches no row of the view's data"
    requirement: TYPE-07
    verification:
      - kind: e2e
        ref: "tests/unit/codegen/test_cli.py::...::test_a_check_run_fetches_no_data_rows and tests/unit/codegen/test_annotation_check.py::TestTheReportCarriesNoRowValues (incl. ::test_the_fetch_guard_is_not_vacuous)"
        status: pass
    human_judgment: false
    note: "Scoped to data rows. Catalogue fetches (DESCRIBE/SHOW) are what introspection is; see Findings."
  - id: D3
    description: "Every row reports the route that produced its annotation, so a metadata fallback is visible"
    requirement: TYPE-07
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_annotation_check.py::TestMetadataFallback::test_metadata_fallback_is_labelled_on_every_row; tests/unit/codegen/test_cli.py::...::test_the_route_is_reported_on_a_clean_run"
        status: pass
    human_judgment: false
  - id: D4
    description: "The committed model is read without executing it"
    requirement: TYPE-07
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_model_reader.py::test_module_level_code_is_not_executed (marker file); no import_module/exec/eval in the module"
        status: pass
    human_judgment: false
  - id: D5
    description: "--check without --model is rejected at exit 2; a bad --model file exits 1 with a message, not a traceback"
    requirement: TYPE-07
    verification:
      - kind: e2e
        ref: "tests/unit/codegen/test_cli.py::TestAnnotationCheckOptionValidation"
        status: pass
    human_judgment: false
  - id: D6
    description: "The comparison core produces the right verdicts over Snowflake's real recorded Arrow types"
    requirement: TYPE-07
    verification:
      - kind: integration
        ref: "tests/unit/codegen/test_annotation_check.py::TestSnowflakeFromTheCommittedRecording (pyarrow.ipc.open_file over test_snowflake_probe)"
        status: pass
    human_judgment: false
    note: "Deliberately narrowed from D-09's 'Snowflake (cassette)': no Snowflake introspection cassette exists, so a full replayed CLI --check is not runnable. WINDOWS.md entry 9."
  - id: D7
    description: "The generation path is unchanged (D-01) and the metadata-vs-probe divergence is surfaced (D-02)"
    requirement: TYPE-07
    verification:
      - kind: e2e
        ref: "the three .ambr snapshots are absent from this plan's diff; tests/unit/codegen/test_annotation_check.py::TestMetadataProbeDivergence::test_an_interval_column_drifts"
        status: pass
    human_judgment: false
  - id: D8
    description: "Databricks --check is claimed nowhere"
    requirement: TYPE-07
    verification:
      - kind: manual
        ref: "no Databricks test in this plan's diff; no live Databricks connection attempted; WINDOWS.md entry 2 still open"
        status: pass
    human_judgment: false
    note: "Deliberately unmet by design (D-09)."

duration: 19min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 05: `semolina codegen --check` Summary

**A committed model can now be checked against the warehouse's current result schema without
fetching a row — and because every row of the report names the route that produced it, a green
`--check` can never quietly mean "I could not probe, so I compared against metadata instead".**

## Performance

- **Duration:** 19 min
- **Tasks:** 3 (delivered in 3 commits)
- **Files changed:** 9 (5 created, 4 modified)

## The `--check` surface as shipped

```
semolina codegen VIEW... --check --model PATH --backend BACKEND [--database PATH]
```

| Element | Shipped as |
|---|---|
| Flag | `--check`, on the existing `codegen` command |
| Model file | `--model PATH`, a separate option — not an overload of the positional `views` |
| `--check` without `--model` | `typer.BadParameter` -> exit **2**, matching `_resolve_backend`'s idiom |
| `--model` without `--check` | same — exit **2** |
| Missing / malformed `--model` file | exit **1**, message naming the path, no traceback |
| stdout | **empty**, in both outcomes |
| stderr | one `rich.table.Table` per view: Field, Committed, Probed (result schema), Route, Status |
| Metadata fallback | a `[yellow]Note:[/yellow]` line naming the reason |
| Clean run | exit **0** |
| Drift | exit **5** = `EXIT_ANNOTATION_DRIFT` |

A real run, live against the file-backed `sales_view`:

```
semolina codegen --check: sales_view
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Field      ┃ Committed         ┃ Probed (result    ┃ Route          ┃ Status ┃
┃            ┃                   ┃ schema)           ┃                ┃        ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ unit_price │ int               │ int               │ execute-schema │ match  │
│ country    │ str               │ str               │ execute-schema │ match  │
│ region     │ str               │ str               │ execute-schema │ match  │
│ revenue    │ decimal.Decimal | │ int | None        │ execute-schema │ drift  │
│            │ None              │                   │                │        │
│ cost       │ int | None        │ int | None        │ execute-schema │ match  │
└────────────┴───────────────────┴───────────────────┴────────────────┴────────┘
```

### The exit-code table is duplicated — 48-06 owns the other copy

`src/semolina/cli/__init__.py`'s Rich epilog gained, in **yellow** (green = success, yellow =
caller-actionable, red = warehouse-side):

```
  5  Annotation drift -- a committed model no longer matches the result schema
```

`docs/src/how-to/codegen.rst:293-317` carries the same table as a `list-table` and is **not
touched by this plan**. 48-06 must add the matching row; the wording above is the one to copy.

## The D-02 worked example, measured rather than predicted

The plan asked for this explicitly: generate a model, immediately `--check` it, and record
whether any field reports drift and why.

**On both DuckDB views in this repo, nothing drifts.** `type_fidelity_view` (7 metrics,
1 dimension) and `sales_view` (2 metrics, 2 dimensions, 1 fact) each report `match` on every
field, at route `execute-schema`. That is not luck and it is not a weak test: on DuckDB the
"metadata" route is `DESCRIBE SELECT * FROM semantic_view(...)`, which is a description of the
result schema of the very statement the probe resolves. The two routes agree because on this
backend they are asking the same engine the same question.

**So a view was built where they genuinely disagree**, and it is now a live test rather than a
paragraph. `span_view` carries an `INTERVAL` fact:

| Field | Metadata route says | Probe route says | Verdict |
|---|---|---|---|
| `span` | `datetime.timedelta` | `Any` | **drift** |
| `region` | `str` | `str` | match |

The probe is the one telling the truth: 48-03 measured the value as a `pyarrow.MonthDayNano`,
`_DUCKDB_TYPE_MAP["INTERVAL"]` is known wrong (D-06, WINDOWS.md entry 6), and
`arrow_type_to_python` deliberately answers `None` there rather than reproduce the error. So
`semolina codegen` writes `span = Fact[datetime.timedelta]()` and `semolina codegen --check`
immediately calls it drift — which is exactly the D-02 consequence the user accepted, made
visible rather than suppressed.

`tests/unit/codegen/test_annotation_check.py::TestMetadataProbeDivergence::test_an_interval_column_drifts`
pins it. The day the INTERVAL mapping is fixed, that test has to be updated deliberately.

## D-01: the generation path is untouched

No canonical-query builder, no offline fallback chain, no route recording in emitted source —
all of that stays Phase 50's DTO-07/DTO-09. The evidence is that **all three `.ambr` snapshots
are absent from this plan's diff** and `just test` reports "3 snapshots passed". The only
change inside `python_renderer.py` is the extraction of `metric_annotation`, which moves one
`f"{x} | None"` out of `_build_model_context` and calls it from there instead.

## D-09, narrowed deliberately and stated plainly

| Backend | What is claimed | Evidence |
|---|---|---|
| **DuckDB** | The whole thing: CLI, exit codes, empty stdout, drift, route reporting, two-probe merge, no data fetch | Live, in-process, 30 tests across two modules |
| **Snowflake** | The **comparison core only** — `check_view` produces the right verdicts over the real recorded Arrow schema | `tests/.../test_snowflake_probe/adbc_driver_snowflake.dbapi` read with `pyarrow.ipc.open_file` |
| **Databricks** | **Nothing** | No test written, no connection attempted |

**Why Snowflake is narrowed.** D-09 says "Snowflake (cassette)", but this repo has no Snowflake
*introspection* cassette — `tests/type_fidelity_probe.py` states it verbatim: "Snowflake has no
counterpart, which is why its metadata cells are labelled `derived-from-code`". `check_view`
calls `engine.introspect()` first, and there is no recording to replay it against, so a full
CLI `--check` on Snowflake is not runnable here. What the recording *does* carry is the
result-schema half — `AGG("REVENUE")` as `decimal128(38, 0)`, `COUNTRY` as `string` — which is
precisely what the comparison core consumes. So the core is tested against real Snowflake types
through a real `SnowflakeDialect`, and the end-to-end CLI claim is DuckDB-only.

Recorded as **WINDOWS.md entry 9** (`unrun-verify`), naming what would close it: a Snowflake
introspection recording, taken in the same session as the interval / VARIANT / decimal gaps
from 48-03.

**Databricks `--check` remains unverified, and broken window 2 is still open.** 48-04 re-read
`go/statement.go` at `go/v0.1.2` and `v0.1.3` and confirmed there is still no `ExecuteSchema`,
so Databricks can only ever reach the zero-row route — a branch nobody has run against a
refusing driver, let alone against a live metric view's planner. No acceptance criterion here
depends on it, and none was quietly dropped either.

## What made Snowflake work at all: result-column names come from the dialect

The plan's design did not name this and it is load-bearing. On DuckDB a result column is the
bare field name, so naive name matching works. On Snowflake the canonical query selects
`AGG("REVENUE")` and the result column is named after the expression — so matching on
`revenue` would find nothing, fall to the metadata route for every metric, and report a green
`--check` that had checked nothing it claimed to.

`_result_field_names` therefore derives candidates from **the same dialect that built the SQL**:
the field name, then `source_name or normalize_identifier(name)`, then `wrap_metric(...)` for a
metric or `quote_identifier(...)` for anything else. `SnowflakeDialect` turns `revenue` into
`AGG("REVENUE")`, which is the recording's column name exactly. This is correct by construction
rather than by a per-backend lookup table that would rot.

Proven non-vacuous: deleting the `wrap_metric` candidate turns
`TestSnowflakeFromTheCommittedRecording::test_a_matching_annotation_reports_no_drift` red.

## Prove the guard, not just the behaviour

Every new assertion was deliberately broken and watched go red before being committed.

| Guard | Break applied | Result |
|---|---|---|
| Snowflake result-name resolution | dropped the `wrap_metric` candidate | red — revenue falls to the metadata route |
| Shared nullability | `metric_annotation` returns the annotation unchanged | red, 7 tests |
| Labelled fallback | probe failure reports `execute-schema` and no error | red on `test_metadata_fallback_is_labelled_on_every_row` |
| Data-fetch guard | fetch from the probe's own SELECT under the guard | red, as `test_the_fetch_guard_is_not_vacuous` asserts |
| Drift exit code | `--check` ignores `report.has_drift` | red, 2 CLI tests |
| No-execute parse | (proved by construction) `exec` of the same fixture source creates the marker | marker created — so its absence is meaningful |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking] Every CLI diagnostic escaped test capture**

- **Found during:** Task 3, writing the "stderr contains `--model`" assertion.
- **Issue:** `_stderr = Console(file=sys.stderr, stderr=True)` pins the stream object captured
  at **import** time. `CliRunner` replaces `sys.stderr` afterwards, so the Rich console kept
  writing to the real terminal and `result.stderr` was empty — measured, not inferred. Two of
  this plan's acceptance criteria ("stderr contains `--model`", "the stderr table names that
  field") were unassertable because of it, and the existing tests only worked around it by
  patching `_stderr` wholesale.
- **Fix:** `_stderr = Console(stderr=True)`. Rich then resolves `sys.stderr` at write time. The
  destination is identical in normal use; the difference is that anything replacing `sys.stderr`
  — a test runner, an embedding process — now actually receives the output. `import sys` became
  unused and was removed.
- **Files modified:** `src/semolina/cli/codegen.py`
- **Commit:** `6dbfc70`

**2. [Rule 2 - Missing] `check_view` could not resolve a Snowflake result column**

Covered in full above. Without it, `--check` would be a no-op that reports success on any
backend whose result columns are not named after their fields. `_result_field_names` is new and
unplanned.

**3. [Rule 2 - Missing] `ViewCheckReport.probe_error`**

The plan specified three fields (`view_name`, `rows`, `has_drift`). A fourth was added so the
CLI's fallback note can say *why* the probe was unavailable. Reporting that a fallback happened
without reporting its cause is the same category of silence the route reporting exists to fix.

### Process notes

**4. RED could not be committed alone, for either new module.** `basedpyright` strict rejects
`from semolina.codegen.model_reader import …` before the module exists, and `--no-verify` was
not an option. Both tasks observed RED as a `ModuleNotFoundError` first, then landed test and
implementation in one commit — the identical constraint 48-03 (deviation 3) and 48-04
(deviation 5) recorded before this.

**5. `tests/unit/codegen/conftest.py` is new and outside `files_modified`.** The data-fetch
guard is used by two test modules; a shared fixture is the idiomatic home, and duplicating the
`Cursor` monkeypatching in both would have been two things to keep in step.

## Findings

**The no-rows criterion is unsatisfiable as literally written, and the intent is narrower than
it reads.** The plan says: with `fetchall`, `fetchone`, `fetchmany` and `fetch_arrow_table`
patched to raise on the driver cursor class, `--check` still exits 0. It cannot: `check_view`
calls `engine.introspect()`, and `DuckDBEngine.introspect` reads its field list with
`cur.fetchall()` on `DESCRIBE SEMANTIC VIEW`. The same is true of every backend — introspection
*is* fetching catalogue rows, and the generation path has always done it.

Observed directly (the first version of the test failed at
`src/semolina/engines/duckdb.py:181`), then narrowed to what TYPE-07 actually promises: no row
of the **view's data**. `data_fetch_guard` wraps `Cursor.execute` to record the statement and
refuses any fetch whose statement is not `DESCRIBE`/`SHOW`. `--check` passes under it, and
`test_the_fetch_guard_is_not_vacuous` executes the probe's own SELECT under the same guard and
asserts the fetch raises — so the guard is not merely permissive.

**A grep criterion misfired for the fifth time this phase.**
`grep -c 'adbc_cassette' tests/unit/codegen/test_annotation_check.py` is specified as 0; it is
1. The hit is the module docstring stating the rule — "must never carry
`pytest.mark.adbc_cassette`" — which is exactly the sentence
`tests/unit/test_type_fidelity_duckdb.py` carries for the same reason. Per 48-04's recorded
lesson the code was not contorted to satisfy it; the intent was verified by parsing instead:

```
decorators applied: ['pytest.fixture', "pytest.mark.usefixtures('data_fetch_guard')"]
any adbc_cassette marker: False
```

Likewise `grep -c 'ast.parse' src/semolina/codegen/model_reader.py` reads 2, not 1, because the
module docstring names the function it uses; the criterion asks for "at least 1", so it passes,
but it is the same shape. The lesson stands unchanged after three plans: assert on parsed code,
not on file-wide greps that a comment explaining the rule will trip.

**`--check` measures the unfiltered result shape.** The canonical query is all metrics plus all
dimensions with no `WHERE`, because Snowflake refuses `ExecuteSchema` for any query carrying a
bound parameter. If a view's planner types a filtered query differently, `--check` says nothing
about that. Stated in `_build_query`'s docstring rather than left for a user to discover.

## Verification

| Gate | Result |
|---|---|
| `just test` — root suite | 1288 passed, 16 skipped, 2 xfailed |
| `just test` — semolina-jaffle-shop suite | 16 passed, 15 skipped |
| `prek run --all-files` (ruff lint+format, basedpyright strict) | clean |
| `just docs-build` (sphinx `-W`) | build succeeded |
| `uv run pytest tests/unit/codegen/test_cli.py -k check -x` | passed |
| `uv run python -c "from semolina.cli.codegen import EXIT_ANNOTATION_DRIFT; assert EXIT_ANNOTATION_DRIFT == 5"` | exit 0 |
| `uv run semolina codegen --help` shows a `5` row containing `drift` | yes |
| The three `.ambr` snapshots in this plan's diff | absent — 3 snapshots passed |
| `git diff 2b9060e~1..HEAD` naming `cursor.py` / `acursor.py` / `results.py` | none |
| `# type: ignore` added anywhere in this plan's diff | 0 |
| Databricks acceptance criterion written / live connection attempted | none / none |
| `47-DECISIONS.md` in this plan's diff | absent |

## Known Stubs

None. No stub values, no skipped test, no unrun `<verify>` block, no `xfail` added.

One **evidence limit** is recorded rather than hidden: `--check` has only ever been run
end-to-end against DuckDB. WINDOWS.md entry 9 (`unrun-verify`), described above under D-09.

## Threat Flags

None new. Of the dispositions this plan owned:

- **T-48-19** (elevation of privilege — reading the committed model) is mitigated as designed:
  `ast.parse` only, no `import_module` / `exec` / `eval` anywhere in `model_reader.py`, and
  `test_module_level_code_is_not_executed` asserts a marker file never appears. Executing the
  same fixture source with `exec` does create it, so the assertion is meaningful.
- **T-48-20** (tampering — canonical query construction) is mitigated: the query is built
  through `SQLBuilder` / `DuckDBSQLBuilder.build_select_with_params` from a runtime
  `SemanticView` subclass; `annotation_check.py` contains no f-string SQL at all.
- **T-48-21** holds: `probe_schema` receives a `build_select_with_params` return value with no
  user text appended, which is the contract `probe.py`'s docstring states.
- **T-48-22** (information disclosure — the drift report) is mitigated by construction: the two
  report dataclasses have no field that can hold a value, and
  `test_no_report_field_holds_anything_but_names_types_and_routes` asserts none of the probe
  fixture's seeded values appears in a rendered report.
- **T-48-23** holds: `read_committed_model`'s `ValueError` names the path, the line, and the
  syntax message, and the CLI prints it in place of a traceback.
- **T-48-24** (spoofing — a silently-fallen-back green check) is mitigated: every row carries
  its route, `ROUTE_METADATA` triggers an explicit stderr note naming the cause, and the
  labelling was broken deliberately to confirm the test catches it.
- **T-48-25** and **T-48-SC** accepted as planned; no packages installed.

## Self-Check: PASSED

- `src/semolina/codegen/model_reader.py` — FOUND
- `src/semolina/codegen/annotation_check.py` — FOUND
- `tests/unit/codegen/test_model_reader.py` — FOUND
- `tests/unit/codegen/test_annotation_check.py` — FOUND
- `tests/unit/codegen/conftest.py` — FOUND
- Commits `2b9060e`, `80db126`, `6dbfc70` — all FOUND in `git log`
