---
phase: 47-type-fidelity-probe-decision-doc
plan: 02
subsystem: testing
tags: [duckdb, pyarrow, adbc, decimal, nullability, semantic-views, codegen, type-fidelity]

# Dependency graph
requires:
  - phase: 47-type-fidelity-probe-decision-doc
    plan: 01
    provides: "tests/type_fidelity_probe.py — the proven one-field evidence path: fixture DDL, probe_schema(), FidelityRow, render_artifact(), the just recipe, and the drift/disjointness guards"
provides:
  - "The full DuckDB half of 47-TYPE-FIDELITY.md — seven measured rows covering all six metrics plus the region dimension"
  - "A `## Named disagreements` section: four subsections, each with its minimal query, measured Arrow type, Python value type, and contrast case"
  - "A `## Downstream Decimal behaviour` section closing RESEARCH.md assumptions A1 and A2 and recording A3 as an explicit gap"
  - "Nine tests asserting every disagreement on its exact Arrow type literal, including the semantic_view-versus-hand-written-SUM trap"
  - "measure_empty_group_values / measure_unmatched_filter_rows / measure_versions / measure_downstream_decimal / render_disagreements / render_downstream_decimal"
affects: [47-03, 47-04, 48-type-map, 49-into-dto, 50-codegen-dtos]

actuals:
  tokens: 15300
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Generated prose: paragraphs are assembled as single strings and wrapped by textwrap at a fixed width, so interpolated Arrow types of varying length cannot produce ragged or byte-unstable output under the drift guard"
    - "Measured-not-quoted environment: the artifact reads its DuckDB and semantic_views versions from the running database, so a version bump makes it stale rather than silently mis-attributed"
    - "Value-shy rendering: _render_observed_value prints only None and 0 verbatim and reduces anything else to a type name, so a future re-seed against real data cannot leak a value into a committed file"

key-files:
  created: []
  modified:
    - tests/type_fidelity_probe.py
    - tests/unit/test_type_fidelity_duckdb.py
    - tests/unit/test_type_fidelity_table.py
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-VALIDATION.md
    - .planning/WINDOWS.md

key-decisions:
  - "Nullability is a policy call, not a measurement — every one of the seven measured fields reports the Arrow nullable flag as True, COUNT included, so the flag carries no signal and the empty-group observation is the only evidence"
  - "The artifact names the DuckDB (v1.5.5) and semantic_views (v0.12.0) versions it measured against, read from the running database rather than quoted from pyproject.toml"
  - "render_disagreements takes a ProbeEvidence record rather than a bare empty-group mapping, because the section states three measured facts and a renderer holding one of them would assert the other two unmeasured"
  - "The pandas row is knowingly environment-dependent and the artifact says so in its own text rather than hiding it behind a conditional"

patterns-established:
  - "Full RED sweep before correction: all eight new assertions were written with deliberately wrong literals and run as a batch, so every one was observed failing against the real measurement before any was corrected"
  - "The correction only ever moves the test toward the measurement, never the query or the code toward the expectation"

requirements-completed: []  # TYPE-01 is scoped "per backend"; DuckDB only is measured. Plan 47-03 adds Snowflake/Databricks and should mark it.

coverage:
  - id: D8
    description: "All six metrics and the region dimension are measured from one semantic_view(...) query, and the artifact carries seven DuckDB rows"
    requirement: TYPE-01
    verification:
      - kind: integration
        ref: "just type-fidelity && uv run python tests/type_fidelity_probe.py --check"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_table.py#test_committed_table_is_not_stale"
        status: pass
    human_judgment: false
  - id: D9
    description: "Decimal precision widening under SUM is measured as decimal128(38, 2), with MAX over the same column at decimal128(10, 2) as the contrast that makes it a rule rather than a coincidence"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_sum_decimal_widens_to_38"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_max_decimal_does_not_widen"
        status: pass
    human_judgment: false
  - id: D10
    description: "AVG(int) is measured as double -> float, contrasted with SUM over the same INTEGER column at int64 -> int"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_avg_int_is_double"
        status: pass
    human_judgment: false
  - id: D11
    description: "COUNT is measured as int64 and MIN over an INTEGER column as int32, so 'integer metric' is demonstrably not one Arrow type"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_count_is_int64_and_never_null"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_min_int_is_int32"
        status: pass
    human_judgment: false
  - id: D12
    description: "Metric nullability is non-uniform on an all-NULL group (SUM/AVG/MIN/MAX -> None, COUNT -> 0) and a GROUP BY matching nothing returns zero rows rather than a row of NULLs; the Arrow nullable flag distinguishes none of it"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_empty_group_nullability_is_not_uniform"
        status: pass
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_arrow_nullable_flag_is_uninformative"
        status: pass
    human_judgment: false
  - id: D13
    description: "The probe measures through semantic_view(...) and not a hand-written aggregate, asserted by measuring both and showing they differ"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_semantic_view_path_differs_from_hand_written_sum"
        status: pass
    human_judgment: false
  - id: D14
    description: "RESEARCH.md assumptions A1 and A2 are converted to measurements and A3 is recorded as an explicit gap naming the missing package, with no dependency added"
    requirement: TYPE-01
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py#test_downstream_decimal_measurements_are_recorded"
        status: pass
      - kind: integration
        ref: "git diff --exit-code pyproject.toml uv.lock"
        status: pass
    human_judgment: false
  - id: D15
    description: "The named-disagreements prose and the comparison table cannot drift apart, because the prose reads its types out of the same FidelityRow list the table renders"
    requirement: TYPE-01
    verification: []
    human_judgment: true
    rationale: "Structural: render_disagreements indexes the row list by field name and interpolates result_arrow_type / python_value_type / metadata_raw_type, so there is no second source to drift from. A reviewer confirms by checking that no Arrow type literal is hard-coded in render_disagreements — only the hand-written-SUM contrast (decimal128(38, 0)) is, and it is asserted by test_semantic_view_path_differs_from_hand_written_sum."

duration: 35min
completed: 2026-08-12
status: complete
---

# Phase 47 Plan 02: Named Disagreements, Measured Summary

**All four disagreements ROADMAP success criterion 2 names are now measured facts with a minimal query, a contrast case, and a test asserting the exact Arrow literal — and every measured value matched RESEARCH.md's prediction on the first run, with nothing tuned to make it agree.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 6 (0 created, 6 modified)

## The seven measured DuckDB rows

| Field | Role | Warehouse type | Mapped annotation | Result Arrow type | Python value type | Verdict |
|---|---|---|---|---|---|---|
| total_order_value | metric | DECIMAL(38,2) | TODO: DECIMAL(38,2) | decimal128(38, 2) | decimal.Decimal | mismatch |
| max_order_value | metric | DECIMAL(10,2) | TODO: DECIMAL(10,2) | decimal128(10, 2) | decimal.Decimal | mismatch |
| total_order_count | metric | BIGINT | int | int64 | int | match |
| avg_order_count | metric | DOUBLE | float | double | float | match |
| min_order_count | metric | INTEGER | int | int32 | int | match |
| n_order_totals | metric | BIGINT | int | int64 | int | match |
| region | dimension | VARCHAR | str | string | str | match |

All seven come out of one `semantic_view(...)` query, not seven separately-planned ones, so the table describes a single statement rather than seven coincidences.

## The four named disagreements, with their measured values

**1. Decimal precision widening under SUM.** `SUM(o.order_total)` over `DECIMAL(10, 2)` measures `decimal128(38, 2)` and arrives as `decimal.Decimal`. **Contrast:** `MAX(o.order_total)` over the *same column* measures `decimal128(10, 2)` — no widening. Two aggregates reading one input do not collapse into one result type; only accumulating aggregates widen. Databricks publishes a rule (`sum(DECIMAL(p, s))` → `DECIMAL(p + min(10, 31-p), s)`); Snowflake publishes none, so that cell is marked undocumented and measured only.

**2. `AVG(int)` → double.** `AVG(o.order_count)` over `INTEGER` measures `double` → `float`. **Contrast:** `SUM(o.order_count)` over the same `INTEGER` column measures `int64` → `int`. It is the aggregate that decides, not the column.

**3. `COUNT` → int64.** `COUNT(o.order_total)` measures `int64` → `int`. **Contrast:** `MIN(o.order_count)` over an `INTEGER` column measures `int32`. "Integer metric" is therefore not one Arrow type, and a type map keyed on the column type would get one of that pair wrong whichever width it picked.

**4. Metric nullability on empty groups.** On the `CA` group (seed row `(4, NULL, NULL, 'CA')` — a non-NULL key with all-NULL metric inputs): `total_order_value`, `max_order_value`, `total_order_count`, `avg_order_count`, and `min_order_count` all return `None`, while `n_order_totals` returns `0`. A filter matching no region returned **0 rows**, not a row of NULLs — the artifact states that distinction in those words, because the criterion's phrase "empty groups" covers two different shapes and only one produces a NULL.

## No divergence from RESEARCH.md

Every predicted value was measured exactly, on the first run, before any test was written:
`decimal128(38, 2)`, `decimal128(10, 2)`, `int64`, `double`, `int32`, `string`, plus the hand-written-SUM contrast at `decimal128(38, 0)`. Nothing was adjusted to force agreement — the exploratory measurement ran first and the expectations were written from its output afterwards. This is the outcome the phase's critical rule exists for, and it did not need to fire.

## The Arrow `nullable` flag is dead evidence, and the artifact says so

All seven measured fields report `nullable=True`, `n_order_totals` included, even though `COUNT` demonstrably never returns NULL. No acceptance criterion in this plan is built on that flag. `test_arrow_nullable_flag_is_uninformative` asserts the uselessness explicitly rather than leaving it as a comment, so a future reader cannot mistake the flag for an answer.

## Downstream Decimal consumers — A1 and A2 closed, A3 left open on purpose

| Consumer | Observed | Status | Assumption |
|---|---|---|---|
| to_pylist | `decimal.Decimal` | measured | — |
| pandas | pandas 2.3.3: dtype `object`, elements `decimal.Decimal` | measured | A2 |
| pydantic | pydantic 2.12.5: `decimal.Decimal` field accepted unchanged | measured | A1 |
| polars | not measured — polars not installed | not measured | A3 |

A2 predicted `object`-dtype `Decimal` rather than `float64`, and that is what was measured. A1 was checked by equality *and* by the validated field still being a `decimal.Decimal`, because a model that quietly returned a `float` would satisfy equality for these seed values while having lost the guarantee. A3 stays an assumption by design: polars matters for `fetch_polars()` in Phase 49, and this plan installs nothing. `pyproject.toml` and `uv.lock` are byte-identical to their pre-plan state.

## Task Commits

1. **Task 1: Widen the DuckDB probe to every field and measure the empty-group case** — `6a73a69` (feat)
2. **Task 2: One test per named disagreement, asserted on exact type literals** — `78d8c09` (test)
3. **Task 3: Measure the downstream Decimal consumers instead of assuming them** — `ef9548b` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_parse_comparison_table` swallowed every later section's table**

- **Found during:** Task 1, designing where the new sections go
- **Issue:** The 47-01 guard split the artifact on `## Field type comparison` and then collected *every* `|`-prefixed line in the remainder of the document. Its docstring claimed it "parses the table's structure rather than regexing the whole file", but with a second markdown table anywhere below it, the downstream table's separator and rows would be parsed as comparison rows — and `_column()` would then index past the end of a 4-cell row. The plan requires the disagreements section to *follow* the table, so this blocked the task.
- **Fix:** Bounded the section at the next `## ` heading before collecting pipe lines. The guard now describes the table it names.
- **Files modified:** `tests/unit/test_type_fidelity_table.py` (outside the plan's `files_modified`, but the alternative was to reorder the artifact against the plan's explicit instruction)
- **Verification:** `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed, as the acceptance criterion requires.
- **Committed in:** `6a73a69`

**2. [Rule 2 - Missing critical] `render_disagreements` takes measured evidence, not just the empty-group mapping**

- **Found during:** Task 1
- **Issue:** The plan specifies `render_disagreements(rows, empty_group_values)`, but the same plan's `must_haves` require the section to state two further facts: that the Arrow `nullable` flag reads True for every measured field including COUNT, and that an unmatched filter returns zero rows. With only the empty-group mapping in hand, the renderer would have had to *assert* both — in the one phase whose entire premise is that claims must be measured.
- **Fix:** Added `measure_unmatched_filter_rows()` and captured the schema's nullable flags during the probe run, bundled with the empty-group values into a `ProbeEvidence` record. The signature became `render_disagreements(rows, evidence)`. Both claims are now rendered from measurements.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `test_arrow_nullable_flag_is_uninformative`; the artifact's "returned 0 rows" figure is interpolated, not typed.
- **Committed in:** `6a73a69`

**3. [Rule 2 - Missing critical] Versions are measured, not quoted**

- **Found during:** Task 1
- **Issue:** The first draft of the section read "measured on DuckDB 1.5.5 with the `semantic_views` community extension" — a hand-typed version string in an evidence artifact, which is exactly the class of unverified claim this phase exists to remove.
- **Fix:** Added `measure_versions(engine)`, which reads `version()` and `duckdb_extensions()` from the running database. The artifact now reads `DuckDB v1.5.5 with semantic_views v0.12.0`, and says in its own text that both were read from the database rather than from `pyproject.toml`. A future version bump makes the artifact stale — the correct signal — rather than silently mis-attributing a measurement.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `uv run python tests/type_fidelity_probe.py --check` exits 0.
- **Committed in:** `6a73a69`

**4. [Rule 2 - Missing critical] `_render_observed_value` closes a T-47-01 path**

- **Found during:** Task 1
- **Issue:** The empty-group list renders observed *values*. For the `CA` group those are `None` and `0`, which the threat model explicitly permits — but nothing structural stopped a future re-seed, or a change of `EMPTY_GROUP_REGION`, from putting a real amount into a committed public file.
- **Fix:** `_render_observed_value` prints only `None` and integer `0` verbatim; anything else is reduced to `non-NULL (\`<type name>\`)`. The rule is enforced by the renderer rather than by the current seed data happening to be safe.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `prek run --all-files` clean; `test_artifact_has_no_value_column` still passes.
- **Committed in:** `6a73a69`

**5. [Rule 3 - Blocking] `render_artifact` gained an optional `sections` parameter**

- **Found during:** Task 1
- **Issue:** `tests/unit/test_type_fidelity_table.py::test_regeneration_is_deterministic` calls `render_artifact(collect_duckdb_rows())` with one positional argument, and the acceptance criteria require that file to keep reporting 4 passed. A required second parameter would have broken it.
- **Fix:** `sections: Sequence[str] = ()`. `main()` passes both new sections; a caller holding only rows still renders a valid table-only document. Consequence worth naming: the determinism guard now covers the table half only. The full document's determinism is still policed, by `test_committed_table_is_not_stale` regenerating and comparing bytes.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed.
- **Committed in:** `6a73a69`

**6. [Rule 1 - Efficiency/correctness] One execution for all seven value types**

- **Found during:** Task 1
- **Issue:** `probe_value_type` executed the query per field. Widening to seven fields would have meant seven executions, and — worse — seven separately-planned statements standing behind one table.
- **Fix:** Added `probe_value_types(cursor, sql, params)`, which executes once and reads every column; `probe_value_type` is now a single-column view of it, so the 47-01 canary keeps working unchanged.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Verification:** `uv run pytest tests/unit/test_type_fidelity_duckdb.py -q` — 13 passed.
- **Committed in:** `6a73a69`

### Carried forward from plan 47-01, honoured not re-litigated

- The verdict vocabulary stays two-valued (`match` / `mismatch`). `mapping-gap` was not reintroduced; both `TODO: ` rows score `mismatch`.
- **TYPE-01 remains `Pending` in `.planning/REQUIREMENTS.md`.** It is scoped per backend and only DuckDB is measured. Plan 47-03 adds the Snowflake and Databricks rows and should be the plan that marks it.
- The "Copied Snowflake cassette directory" Wave 0 checkbox in `47-VALIDATION.md` is left **unticked** — this plan copied no cassette.
- `probe_schema`'s zero-row fallback still has never fired in anger (ledger entry 2). Nothing here claims otherwise.

---

**Total deviations:** 6 auto-fixed (2 blocking, 4 missing-critical). No architectural decisions; no user input required.
**Impact on plan:** No scope creep. Deviations 2, 3 and 4 all have the same shape — the plan's own `must_haves` demanded a claim the plan's stated signature could not measure, so the measurement was added rather than the claim asserted.

## Issues Encountered

**The RED sweep, run as a batch.** All eight new assertions were written with deliberately wrong literals and run together, so each was observed failing against the real measurement before any was corrected. Two of the eight, verbatim:

1. **`test_sum_decimal_widens_to_38`, written expecting the source precision:**

   ```
   >       assert _arrow_type(probe_cursor, "total_order_value") == "decimal128(10, 2)"
   E       AssertionError: assert 'decimal128(38, 2)' == 'decimal128(10, 2)'
   E
   E         - decimal128(10, 2)
   E         ?            ^^
   E         + decimal128(38, 2)
   E         ?            ^^
   ```

2. **`test_semantic_view_path_differs_from_hand_written_sum`, written expecting the hand-written SUM to match the `semantic_view` path:**

   ```
   >       assert str(hand_written.schema.field("total_order_count").type) == "int64"
   E       AssertionError: assert 'decimal128(38, 0)' == 'int64'
   E
   E         - int64
   E         + decimal128(38, 0)
   ```

   This is the trap in its raw form: the same column, summed two ways, gives `int64` → `int` through `semantic_view(...)` and `decimal128(38, 0)` → `decimal.Decimal` outside it.

Two more worth recording, because they show the empty-group and flag findings are not artefacts of a permissive assertion:

3. **`test_empty_group_nullability_is_not_uniform`, written expecting `0` everywhere:**

   ```
   E       AssertionError: total_order_value should go NULL on the CA group
   E       assert None == 0
   ```

4. **`test_arrow_nullable_flag_is_uninformative`, written expecting COUNT to be non-nullable:**

   ```
   >       assert flags["n_order_totals"] is False
   E       assert True is False
   ```

In every case the correction moved the *test* to the measurement. No query, fixture, or code path was changed to make an expectation come true.

**`# type: ignore` avoided in the pydantic probe.** `DecimalModel(amount=value)` with `value: object` fails basedpyright strict. Rather than suppress it, the measurement uses `DecimalModel.model_validate({"amount": value})`, whose parameter is `Any`. No `# type: ignore` and no `# pyright: ignore` was added anywhere in this plan.

## Known Stubs

None. Every function added is exercised by a test or by the artifact generation, and no placeholder text was written.

## Broken window recorded

`.planning/WINDOWS.md` entry **3** (`deviation`, phase 47, open): **the artifact's pandas row is environment-dependent.** pandas is not a declared dependency of this project — it arrives only transitively through `databricks-sql-connector[pyarrow]`, which the `all` extra pulls in. CI syncs `--dev --extra all`, so the row measures there and the committed artifact is correct for CI. But a contributor who runs a plain `uv sync --dev` and then `just type-fidelity` will legitimately get `not measured — pandas not installed`, and `test_committed_table_is_not_stale` will go red for an environment reason rather than genuine drift.

This is documented in the artifact's own section text rather than hidden behind a conditional, because a row that silently reported the same thing in both environments would be the dishonest option. It is logged rather than fixed: the fix (declaring pandas as a dev dependency) adds a package, which this plan's threat model and acceptance criteria forbid.

## Notes for plan 47-03

- **`collect_rows()` is still DuckDB-only.** Add `collect_snowflake_rows()` / `collect_databricks_rows()` alongside `collect_duckdb_rows()` there. `BACKEND_ORDER` already lists all three, so ordering is settled.
- **`render_disagreements` is DuckDB-shaped.** It indexes rows by field name with no backend filter beyond `backend == "duckdb"`, and its vendor-rule prose is written from the DuckDB measurement outward. Adding Snowflake rows to the table will not automatically extend the prose — decide whether the section gains per-backend cells or a second section.
- **TYPE-01 and the cassette checkbox are both yours.** Mark `TYPE-01` complete in `.planning/REQUIREMENTS.md` and tick the "Copied Snowflake cassette directory" Wave 0 item in `47-VALIDATION.md` once the cassette is copied.
- **The Snowflake fixture cannot show widening.** Its `NUMBER` is `NUMBER(38,0)`, already at max precision (RESEARCH.md open question 1). Do not present a Snowflake SUM row as evidence of widening; the DuckDB row is the only place that is demonstrable.
- **Snowflake's probe will refuse bind parameters.** The driver's `ExecuteSchema` raises `StatusNotImplemented` when params are bound, and Semolina keeps `?` placeholders on Snowflake. Probe the unfiltered query shape, or expect the zero-row fallback to be the route — which would also be the first time that branch has ever fired (ledger entry 2).
- **Do not mark the new probe tests `@pytest.mark.adbc_cassette` if they touch DuckDB.** `adbc_auto_patch` covers `adbc_driver_manager.dbapi`, which DuckDB routes through. `test_probe_runs_live_not_replayed` guards the existing module; a new module needs its own guard.
- **The `## Downstream Decimal behaviour` section is backend-independent** and should not be duplicated per backend — it measures pyarrow and Python consumers, not warehouses.

## User Setup Required

None. No external service, credential, or package installation was needed; the in-memory DuckDB fixture and the already-present `semantic_views` extension covered everything.

## Verification

- `just test` — **1068 passed, 16 skipped** (main suite), **16 passed, 15 skipped** (jaffle-shop). Green end to end.
- `prek run --all-files` — clean.
- `just type-fidelity && uv run python tests/type_fidelity_probe.py --check` — exits 0; `git diff` on the artifact is empty.
- `uv run pytest tests/unit/test_type_fidelity_duckdb.py -q` — 13 passed.
- `uv run pytest tests/unit/test_type_fidelity_table.py -q` — 4 passed.
- `uv run pytest tests/unit/test_type_fidelity_duckdb.py -m adbc_cassette --collect-only -q` — 0 selected, 12 deselected.
- `git diff --exit-code pyproject.toml uv.lock` — clean; no dependency added.
- Every Arrow literal asserted in the tests was cross-checked against its cell in the committed artifact.

## Self-Check: PASSED

All six modified files exist on disk; all three task commits (`6a73a69`, `78d8c09`, `ef9548b`) resolve in `git log`; the artifact carries 7 DuckDB data rows, a `## Named disagreements` heading with exactly 4 subsections, and a `## Downstream Decimal behaviour` table naming all four consumers.

---
*Phase: 47-type-fidelity-probe-decision-doc*
*Completed: 2026-08-12*
