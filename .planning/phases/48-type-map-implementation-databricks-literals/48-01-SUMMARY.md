---
phase: 48-type-map-implementation-databricks-literals
plan: 01
subsystem: codegen
tags: [type-map, codegen, duckdb, decimal, jinja2, introspection, nullability]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "47-DECISIONS.md Decision 1 (Decimal policy, annotation-only) and Decision 2 (uniform metric nullability); the live DuckDB type-fidelity probe and its circularity canary"
provides:
  - "DuckDB DECIMAL maps to decimal.Decimal (TYPE-03, DuckDB half)"
  - "Metric annotations are uniformly `T | None`, applied only in the renderer (TYPE-04)"
  - "A generalised import-emission path (`_build_import_lines`) that derives imports from resolved annotations rather than raw introspected types"
  - "`IntrospectedField.raw_type` — a channel carrying the warehouse type into generated source as a single-line comment (D-03)"
  - "A runnable scope-fence test refusing any edit to the three value-path modules"
  - "A regenerated 47-TYPE-FIDELITY.md, and a re-pointed circularity canary with a positive twin (D-10)"
affects: [48-02, 48-03, 48-04, 48-05, 48-06, phase-50-typed-dtos]

actuals:
  tokens: 66746
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Import emission derived from resolved _FieldContext annotations, not from raw IntrospectedField types"
    - "Lossy-annotation detection by two explicit reviewable frozensets rather than a heuristic"
    - "Runnable scope fence: a git-diff gate that skips loudly rather than passing when it cannot run"

key-files:
  created:
    - tests/unit/test_scope_fence.py
  modified:
    - src/semolina/codegen/type_map.py
    - src/semolina/codegen/python_renderer.py
    - src/semolina/codegen/templates/python_model.py.jinja2
    - src/semolina/codegen/introspector.py
    - src/semolina/engines/duckdb.py
    - src/semolina/engines/snowflake.py
    - src/semolina/engines/databricks.py
    - tests/type_fidelity_probe.py
    - tests/unit/test_type_fidelity_duckdb.py
    - tests/unit/codegen/test_type_map.py
    - tests/unit/codegen/test_python_renderer.py
    - tests/unit/codegen/test_codegen_e2e.py
    - tests/unit/codegen/test_cli.py
    - tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md

key-decisions:
  - "Metric nullability is applied in _build_model_context only; the type maps and all three engines stay nullability-free, so IntrospectedField.data_type never carries `| None`"
  - "_DATETIME_TYPES deleted rather than extended — the exact-string frozenset was the pitfall-1 landmine, and _build_import_lines matches by prefix containment against resolved annotations instead"
  - "The single `from semolina import ...` line is built from a set and sorted in the template, so ruff's isort pass is a no-op rather than the only thing producing sorted output"
  - "duckdb_type_to_python refuses container types (names ending in `]`) BEFORE stripping parenthesized parameters — a Rule 1 bug the DECIMAL key exposed"
  - "The re-pointed canary uses a new `region_list AS list(o.region)` metric (raw type VARCHAR[]) rather than STRUCT or MAP: it is a genuine aggregate, so the existing probe_sql_for / probe_schema / probe_value_type triple drives it unchanged"
  - "The scope fence defaults to Phase 48's starting commit, not origin/main — the v0.7 branch legitimately created acursor.py in Phase 46, so an origin/main default would be permanently red for an unrelated reason"
  - "47-DECISIONS.md left unedited despite quoting now-superseded cell values; a dated decision record correctly describes what was true when it was decided"

patterns-established:
  - "Import derivation reads the annotation that will actually be emitted, closing the class of bug where a decoration silently desynchronises an annotation from its import"
  - "A gate that cannot run reports skipped with an explicit message, never green"
  - "Re-point, don't delete: a guard whose premise a phase legitimately falsifies is aimed at a still-true case and gains a positive twin"

requirements-completed: [TYPE-03, TYPE-04]

coverage:
  - id: D1
    description: "A live DuckDB DECIMAL metric generates `Metric[decimal.Decimal | None]()` with `import decimal`, proven end to end from an in-memory warehouse through introspect -> type_map -> renderer"
    requirement: TYPE-03
    verification:
      - kind: e2e
        ref: "tests/unit/codegen/test_codegen_e2e.py::test_codegen_live_duckdb_decimal_metric"
        status: pass
    human_judgment: false
  - id: D2
    description: "Metric annotations are uniformly `T | None`; dimensions and facts gain none"
    requirement: TYPE-04
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_python_renderer.py::TestMetricNullability"
        status: pass
      - kind: unit
        ref: "tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr (3 snapshots)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Nullability decoration does not suppress import emission — a datetime metric still emits `import datetime` (pitfall 1 disarmed and guarded)"
    requirement: TYPE-04
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_python_renderer.py::TestImportEmission"
        status: pass
    human_judgment: false
  - id: D4
    description: "The raw warehouse type survives into generated source as a single-line comment for every annotation that does not name it"
    requirement: TYPE-03
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_python_renderer.py::TestRawTypeComment"
        status: pass
    human_judgment: false
  - id: D5
    description: "Phase 47's circularity canary re-pointed at a still-unmapped type with a positive twin, and 47-TYPE-FIDELITY.md regenerated"
    verification:
      - kind: unit
        ref: "tests/unit/test_type_fidelity_duckdb.py::test_an_unmapped_type_still_disagrees_by_value, ::test_decimal_metric_agrees_by_value"
        status: pass
      - kind: integration
        ref: "uv run python tests/type_fidelity_probe.py --check (exit 0)"
        status: pass
    human_judgment: false
  - id: D6
    description: "A runnable test refuses any edit to cursor.py, acursor.py, or results.py"
    verification:
      - kind: unit
        ref: "tests/unit/test_scope_fence.py::test_value_path_files_are_untouched"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 01: Type Map Tracer & Renderer Seams Summary

**A live DuckDB `DECIMAL(38,2)` metric now generates `Metric[decimal.Decimal | None]()` with a matching `import decimal` and a `# DECIMAL(38,2)` provenance comment — proven end to end from an in-memory warehouse, with the renderer's two brittle seams (import emission, comment channel) replaced before the rest of the phase leans on them.**

## Performance

- **Duration:** 16 min
- **Tasks:** 3 (delivered in 5 commits — one deviation was split into a failing test plus its fix, per CLAUDE.md)
- **Files changed:** 16 (1 created, 15 modified)

## What was built

The tracer carried one column all the way through and asserted on the emitted source. Here is what `render_and_format` now produces for the live probe view, which is the whole plan in one artifact:

```python
import decimal
from typing import Any

from semolina import Dimension, Fact, Metric, SemanticView


class TypeFidelityView(SemanticView, view="type_fidelity_view"):
    region = Dimension[str]()
    # DECIMAL(38,2)
    total_order_value = Metric[decimal.Decimal | None]()
    # DECIMAL(10,2)
    max_order_value = Metric[decimal.Decimal | None]()
    total_order_count = Metric[int | None]()
    avg_order_count = Metric[float | None]()
    min_order_count = Metric[int | None]()
    n_order_totals = Metric[int | None]()
    # TODO: VARCHAR[]
    region_list = Metric[Any | None]()
```

Three seams changed to get there.

**The map.** `_DUCKDB_TYPE_MAP` gained a `"DECIMAL"` key. No new stripping logic was needed — the existing `type_name.split("(")[0]` already delivers `"DECIMAL"` for `"DECIMAL(10,2)"`.

**Nullability.** Decision 2's `| None` is applied in `_build_model_context` and nowhere else, to `Metric` only. The maps and all three engines stay nullability-free, so `IntrospectedField.data_type` — which the fidelity artifact and the future `--check` both read as *the* mapped annotation — never carries it.

**Imports.** `_DATETIME_TYPES` is gone. It was a `frozenset` of three literal strings tested by exact membership against the *raw* introspected type, evaluated one statement before `models` was built. Appending `| None` would have stopped it matching, silently dropping `import datetime` from generated modules for datetime-typed metrics only — a `NameError` in the user's model with most of the suite still green. `render_views` now builds `models` first and `_build_import_lines` scans the resolved `_FieldContext.data_type` strings by prefix containment.

**The comment channel.** Mapping a type removes its `TODO:` comment, and that comment was the only path by which a warehouse type reached generated source. `IntrospectedField.raw_type` replaces it, populated at the three existing `TODO:` construction sites from the string each engine already held. `_FieldContext.todo_comment` became `type_comment`, and both branches route through the same `" ".join(...split())` collapse, so a raw type containing a newline cannot push text onto a fresh line of a module the user then executes (T-48-01).

## Artifacts the plan asked to be recorded exactly

### The `.ambr` diff

Exactly the predicted delta, and nothing else. Dimension and Fact rows unchanged; no import-line churn, because the template's `from semolina import ...` line is now emitted pre-sorted and ruff's isort pass has nothing left to do.

```diff
 class SalesView(SemanticView, view="sales_view"):     # test_codegen_databricks_field_types
-      revenue = Metric[int]()
-      cost = Metric[int]()
+      revenue = Metric[int | None]()
+      cost = Metric[int | None]()
       country = Dimension[str]()
       region = Dimension[str]()

 class SalesView(SemanticView, view="sales_view"):     # test_codegen_file_backed_duckdb
       unit_price = Fact[int]()
       country = Dimension[str]()
       region = Dimension[str]()
-      revenue = Metric[int]()
-      cost = Metric[int]()
+      revenue = Metric[int | None]()
+      cost = Metric[int | None]()

 class SalesView(SemanticView, view="sales_view"):     # test_codegen_snowflake_field_types
-      revenue = Metric[int]()
+      revenue = Metric[int | None]()
       country = Dimension[str]()
       date_key = Fact[datetime.date]()
```

Task 3's snapshot regeneration produced an **empty** diff, as predicted: no committed fixture yields a lossy annotation until 48-03 makes the Snowflake `FIXED` case one.

### The `47-TYPE-FIDELITY.md` diff hunks

Five hunks. The first two are the flips the plan predicted; the remaining three are all consequences of the sanctioned probe-fixture addition described under "Deviations".

1. **The two duckdb decimal rows flip, verdict `mismatch` -> `match`:**
   ```diff
   -| duckdb | max_order_value | metric | DECIMAL(10,2) | live | TODO: DECIMAL(10,2) | decimal128(10, 2) | live (execute-schema) | decimal.Decimal | mismatch |
   +| duckdb | max_order_value | metric | DECIMAL(10,2) | live | decimal.Decimal | decimal128(10, 2) | live (execute-schema) | decimal.Decimal | match |
   -| duckdb | total_order_value | metric | DECIMAL(38,2) | live | TODO: DECIMAL(38,2) | decimal128(38, 2) | live (execute-schema) | decimal.Decimal | mismatch |
   +| duckdb | total_order_value | metric | DECIMAL(38,2) | live | decimal.Decimal | decimal128(38, 2) | live (execute-schema) | decimal.Decimal | match |
   ```
2. **A new comparison-table row** for the metric added to carry the canary:
   ```diff
   +| duckdb | region_list | metric | VARCHAR[] | live | TODO: VARCHAR[] | list<l: string> | live (execute-schema) | list | mismatch |
   ```
3. **The quoted probe SQL** gains `'region_list'` in its `metrics :=` list.
4. **The empty-group observation list** gains `` `region_list` -> non-NULL (`list`) ``.
5. **The nullable-flag list** gains `` `region_list` -> `nullable=True` ``.

The snowflake `AGG("REVENUE")` row is **unchanged**, as the plan required — that is 48-03's Snowflake `FIXED` work. The pandas-dependent Downstream Decimal row stayed `measured`; the artifact was regenerated under `uv sync --all-groups --extra all` (see "Environment note").

`uv run python tests/type_fidelity_probe.py --check` exits 0.

### The type chosen for the re-pointed canary

**`VARCHAR[]`** — a DuckDB LIST, reached through a new `o.region_list AS list(o.region)` metric on the probe view.

The plan offered `STRUCT`, `MAP`, or `LIST`. `LIST` via an aggregate was chosen because it is a genuine metric expression, which means the existing `probe_sql_for` / `probe_schema` / `probe_value_type` triple drives it with no new helper. The three columns disagree by named literals: `TODO: VARCHAR[]` (metadata), `list<l: string>` (result schema), `list` (value). No plan in Phase 48 maps a container type, so the guard stays live for the whole phase.

The positive twin, `test_decimal_metric_agrees_by_value`, asserts the decimal case now agrees on all three columns. Both halves of the story stay committed.

### 47-DECISIONS.md: superseded, deliberately unedited

`47-DECISIONS.md` § "Decision 1" states, in prose, that *"the mapped annotation for those same two fields reads `TODO: DECIMAL(38,2)` and `int` respectively"*, and its § "What Phase 48 must change" table describes `_DUCKDB_TYPE_MAP` as having *"no `DECIMAL` key at all"*.

**Both statements are now false, and the file was not edited.** It is normative, dated, and was approved at a blocking human checkpoint; a dated decision record correctly describes what was true when it was decided. The regenerated `47-TYPE-FIDELITY.md` is the live evidence and supersedes those quoted cells. Anyone reading Decision 1 for current state should read the artifact instead.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug] `DECIMAL(10,2)[]` annotated as a scalar `decimal.Decimal`**

- **Found during:** Task 2 preparation, while spiking a list-typed metric for the canary.
- **Issue:** DuckDB spells a list type by suffixing its element type with `[]`, so a `list(o.order_total)` metric describes as `DECIMAL(10,2)[]`. `duckdb_type_to_python` strips parenthesized parameters *first*, leaving `"DECIMAL"` — so the new `DECIMAL` key annotated a list-valued field as a scalar `decimal.Decimal` while the value arrives as a `list`. Precisely the annotation-vs-value defect Decision 1 exists to end. The same shape had always been wrong for `VARCHAR(255)[] -> str`; adding the `DECIMAL` key is what put the phase's headline type into the affected class.
- **Fix:** `duckdb_type_to_python` returns `None` for any normalised type name ending in `]`, checked before the parameter strip. Unparameterised arrays (`INTEGER[]`) already returned `None`; the two spellings now agree.
- **Files modified:** `src/semolina/codegen/type_map.py`, `tests/unit/codegen/test_type_map.py`
- **Commits:** `fc04cce` (failing test), `9a22328` (fix) — split per CLAUDE.md's failing-test-first rule.

**2. [Rule 3 - Blocking] The probe view carried no unmappable type for the canary to point at**

- **Found during:** Task 2.
- **Issue:** After the `DECIMAL` key landed, every field of `type_fidelity_view` mapped cleanly, so there was no field left where the three columns disagree. Re-pointing the circularity canary was impossible without one. The plan anticipated this and sanctioned adding a column.
- **Fix:** Added `o.region_list AS list(o.region)` to `PROBE_VIEW_DDL`, `TypeFidelityView`, and `DUCKDB_PROBE_METRICS` (keeping the DDL/tuple in-step invariant the module's own docstring states, and updating the "six metrics" prose to "seven"). This is the source of `47-TYPE-FIDELITY.md` diff hunks 2-5.
- **Files modified:** `tests/type_fidelity_probe.py`
- **Commit:** `433271f`

**3. [Rule 3 - Blocking] The scope fence's prescribed `origin/main` default made it permanently red**

- **Found during:** Task 2.
- **Issue:** The plan specified `origin/main` as the fallback base ref. On this milestone branch that diff includes all of v0.7, and Phase 46 legitimately *created* `src/semolina/acursor.py` — so the fence failed on work it was never meant to police. A gate that is always red is a gate someone eventually deletes.
- **Fix:** `DEFAULT_BASE_REF` is Phase 48's starting commit (`9f3c8b9`), documented with the reasoning, and still overridable through `SEMOLINA_SCOPE_FENCE_BASE`. Proven non-vacuous in all three modes: passes against the phase base, **skips** with an explicit message on an unresolvable ref, and **fails** against `origin/main` where a fenced file genuinely changed.
- **Files modified:** `tests/unit/test_scope_fence.py`
- **Commit:** `433271f`

**4. [Rule 3 - Blocking] Test churn from the sorted `from semolina import` line**

- **Found during:** Task 1.
- **Issue:** Building the semolina import from a sorted set changed the *raw* template output from `SemanticView, Metric, Dimension, Fact` to `Dimension, Fact, Metric, SemanticView`. Four existing assertions read the raw form, and eight more asserted `Metric[int]()` without nullability.
- **Fix:** Updated the affected assertions in `test_python_renderer.py` and `test_cli.py`. The committed snapshots were already showing the sorted form (ruff's isort was producing it), so no snapshot import-line churn resulted.
- **Commit:** `25d2874`

## Findings

**The plan's `grep -c '| None' src/semolina/codegen/type_map.py is 0` criterion is unsatisfiable as written.** It returns 3, and always would have: the three mapper functions are declared `-> str | None`, and have been since before this phase. The criterion's *intent* — that no nullability decoration is produced by the map — holds and was verified directly: no value in `_SNOWFLAKE_TYPE_MAP`, `_DATABRICKS_TYPE_MAP`, or `_DUCKDB_TYPE_MAP` contains `| None`. Later plans should assert on map values, not on a file-wide grep.

**The scope fence's env var reaches a `git` argv, and the validation gate happens to close it.** `SEMOLINA_SCOPE_FENCE_BASE` is passed bare to `git merge-base`, where a value like `--fork-point` would be read as a flag. It cannot get there: every value is first put through `git rev-parse --verify --quiet "<value>^{commit}"`, and anything that does not resolve to a commit takes the skip path. Recorded so a future edit does not reorder those two calls.

**Task 1's tracer gate passed on re-run**, so no expansion task was built on an unproven slice.

## Verification

| Gate | Result |
|---|---|
| `just test` — root suite | 1106 passed, 16 skipped |
| `just test` — semolina-jaffle-shop suite | 16 passed, 15 skipped |
| `prek run --all-files` (ruff lint+format, basedpyright strict) | clean |
| `uv run python tests/type_fidelity_probe.py --check` | exit 0 |
| `git diff 9f3c8b9..HEAD` naming `cursor.py` / `acursor.py` / `results.py` | none |
| `git diff 9f3c8b9..HEAD` naming `47-DECISIONS.md` | none |
| `# type: ignore` added anywhere in this plan's diff | 0 |

## Environment note

`47-TYPE-FIDELITY.md` must be regenerated with pandas importable or its Downstream Decimal row flips to `not measured` and `test_committed_table_is_not_stale` goes red for an environment reason (WINDOWS.md broken window 3). The plan suggested `uv sync --dev --extra all`; that command **prunes the `docs` dependency group** and would break `just docs-build`. Use `uv sync --all-groups --extra all` instead. Recorded for 48-02..48-06, which regenerate the same artifact.

## Known Stubs

None. No stub values, no skipped tests, and no `<verify>` block went unrun.

## Threat Flags

None. The two `mitigate` dispositions this plan owned are both implemented and asserted: T-48-01 (newline in a raw type breaking out of its comment) by `TestRawTypeComment::test_raw_type_with_newline_stays_single_line`, and T-48-04 (a fence that passes when it cannot run) by the skip path, proven by running the fence against an unresolvable ref. T-48-02 holds by construction — import lines come from a closed dict and a fixed seed set, never from a catalogue string. No packages were installed.

## Self-Check: PASSED

- `tests/unit/test_scope_fence.py` — FOUND
- `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` — FOUND
- `src/semolina/codegen/type_map.py`, `python_renderer.py`, `templates/python_model.py.jinja2`, `introspector.py` — FOUND
- Commits `25d2874`, `fc04cce`, `9a22328`, `433271f`, `b71c481` — all FOUND in `git log`
