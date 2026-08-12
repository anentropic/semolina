---
phase: 48-type-map-implementation-databricks-literals
plan: 03
subsystem: codegen
tags: [type-map, codegen, decimal, variant, json-value, measurement, evidence-limits]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "47-DECISIONS.md Decision 1 (Decimal policy, annotation-only); the type-fidelity probe, its cassette readers, and its live DuckDB engine builder"
  - phase: 48-type-map-implementation-databricks-literals
    plan: 01
    provides: "IntrospectedField.raw_type and the renderer's raw-type comment channel; _build_import_lines derived from resolved annotations; the scope-fence test"
provides:
  - "Snowflake FIXED and Databricks decimal map to decimal.Decimal — an equivalent decimal column now annotates identically on all three backends (TYPE-03)"
  - "DuckDB UUID/JSON/ENUM/TIMESTAMP_S|_MS|_NS mapped to their measured Python types; HUGEINT corrected to decimal.Decimal (TYPE-05, D-03, D-05)"
  - "semolina.JsonValue — a public recursive JSON union, and VARIANT/variant mapped to it (TYPE-06)"
  - "tests/unit/test_annotation_contract.py — an executed proof that every mapped annotation names a type the measured value is an instance of"
  - "type_fidelity_probe.probe_values — the value half of the probe, reusable for isinstance checks"
affects: [48-04, 48-05, 48-06, phase-49-typed-dtos, phase-50-typed-dtos]

actuals:
  tokens: 73079
  tasks: 4
  commits: 8

tech-stack:
  added: []
  patterns:
    - "Annotation contracts are proved by isinstance against a measured value, not by review of a table"
    - "A known-wrong mapping is xfail(strict=True) inside the parametrization, never excluded from it"
    - "An unmeasurable annotation is either reverted or recorded as an evidence limit, never shipped silently"

key-files:
  created:
    - src/semolina/types.py
    - tests/unit/test_annotation_contract.py
    - tests/unit/test_public_surface.py
    - .planning/todos/pending/2026-08-12-record-databricks-interval-column.md
  modified:
    - src/semolina/codegen/type_map.py
    - src/semolina/codegen/python_renderer.py
    - src/semolina/__init__.py
    - tests/type_fidelity_probe.py
    - tests/unit/codegen/test_type_map.py
    - tests/unit/codegen/test_python_renderer.py
    - tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
    - tests/unit/test_snowflake_engine.py
    - tests/integration/test_type_fidelity.py
    - .planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md
    - .planning/WINDOWS.md

key-decisions:
  - "The planned human-verification checkpoint on the annotation table was rejected by the user and replaced with an executed measurement: an annotation contract is settled by isinstance against a real value, not by someone reading a table"
  - "The Databricks day-time interval -> datetime.timedelta annotation was REVERTED. Nothing in the repo has an interval column to measure, and one guess among measured rows makes the whole contract read stronger than it is"
  - "VARIANT -> JsonValue was kept despite being equally unmeasured, because a union over the entire JSON value domain holds under both candidate outcomes (raw text or parsed structure) where a single concrete type does not"
  - "DuckDB INTERVAL is xfail(strict=True) inside the parametrization rather than excluded: excluding a row is how it stayed wrong through two phases with nothing going red"
  - "The Databricks interval branch and its two frozensets were deleted rather than left returning None on both arms — a branch that always returns None is dead code impersonating a decision"
  - "probe_value_types was refactored onto a new probe_values so the artifact's value column and the isinstance assertions read one execution of one query"

patterns-established:
  - "Prove the guard, not just the behaviour: every new assertion here was broken deliberately and watched go red before being committed"
  - "Evidence limits get three artifacts — a WINDOWS.md entry, a todo naming the recording that closes it, and a comment at the code site saying why the obvious annotation is absent"

requirements-completed: [TYPE-03, TYPE-06]
requirements-partial: [TYPE-05]

coverage:
  - id: D1
    description: "An equivalent decimal column annotates decimal.Decimal on Snowflake, Databricks and DuckDB"
    requirement: TYPE-03
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_type_map.py::test_all_three_backends_agree_on_decimal"
        status: pass
      - kind: e2e
        ref: "tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr::test_codegen_snowflake_field_types"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every DuckDB annotation in the D-03 table names a type the live measured value is an instance of"
    requirement: TYPE-05
    verification:
      - kind: integration
        ref: "tests/unit/test_annotation_contract.py::test_duckdb_annotation_describes_the_measured_value (10 columns, live in-memory DuckDB via the real ADBC path)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Snowflake and Databricks annotations name types their recorded values are instances of"
    requirement: TYPE-03
    verification:
      - kind: integration
        ref: "tests/unit/test_annotation_contract.py::test_snowflake_annotation_describes_the_recorded_value, ::test_databricks_annotation_describes_the_recorded_value"
        status: pass
    human_judgment: false
  - id: D4
    description: "DuckDB INTERVAL's known-wrong annotation is pinned as a strict expected failure, so fixing the map forces the row to be updated"
    requirement: TYPE-05
    verification:
      - kind: integration
        ref: "tests/unit/test_annotation_contract.py::test_duckdb_annotation_describes_the_measured_value[c_interval] (xfail strict)"
        status: pass
    human_judgment: false
  - id: D5
    description: "semolina.JsonValue is importable, exported, subscriptable, and produced by both VARIANT mappers; a VARIANT field yields exactly one from-semolina import line including it"
    requirement: TYPE-06
    verification:
      - kind: unit
        ref: "tests/unit/test_public_surface.py::TestJsonValue"
        status: pass
      - kind: unit
        ref: "tests/unit/codegen/test_python_renderer.py::TestImportEmission::test_jsonvalue_field_imports_jsonvalue, ::test_no_jsonvalue_field_no_jsonvalue_import"
        status: pass
    human_judgment: false
  - id: D6
    description: "A Databricks interval column still emits a TODO — evidence-limited, not implemented"
    requirement: TYPE-05
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_type_map.py::TestDatabricksIntervalType"
        status: pass
    human_judgment: false
    note: "Deliberately unmet. See Evidence limits below and WINDOWS.md entry 7."

duration: 22min
completed: 2026-08-12
status: complete
---

# Phase 48 Plan 03: Type Map Completion Summary

**Every annotation this phase writes is now checked by `isinstance` against a value measured through the real driver path — which is how the one annotation that could not be measured got reverted instead of shipped.**

## Performance

- **Duration:** 22 min
- **Tasks:** 4 (delivered in 8 commits — four RED/GREEN pairs)
- **Files changed:** 15 (4 created, 11 modified)

## What was built

### The Decimal policy, completed (TYPE-03)

`FIXED` became an ordinary `_SNOWFLAKE_TYPE_MAP` entry and the scale branch is gone from the
function body, from the summary paragraph that stated the rule, from the `Args:` description
of `scale`, and from the user-facing `Example:` block. Decision 1 covers scale 0 too: the
driver returns Decimal128 for every FIXED column under `use_high_precision`, so a
`NUMBER(38,0)` is a `decimal.Decimal`, not an `int`. `_DATABRICKS_TYPE_MAP["decimal"]` moved
from `float` to `decimal.Decimal` with no branch — precision and scale do not change the
answer under this policy.

The Snowflake E2E snapshot moved accordingly, and the raw-type channel 48-01 built carried
the descriptor through:

```diff
   import datetime
+  import decimal

   from semolina import Dimension, Fact, Metric, SemanticView


   class SalesView(SemanticView, view="sales_view"):
-      revenue = Metric[int | None]()
+      # {"type": "FIXED", "scale": 0}
+      revenue = Metric[decimal.Decimal | None]()
       country = Dimension[str]()
       date_key = Fact[datetime.date]()
```

Nothing else in the `.ambr` moved. The Databricks fixture declares `revenue BIGINT, cost
BIGINT` and the DuckDB one has no FIXED analogue, exactly as predicted.

### The category-1 gaps (TYPE-05)

`_DUCKDB_TYPE_MAP` gained `UUID`/`JSON`/`ENUM` → `str` and `TIMESTAMP_S`/`_MS`/`_NS` →
`datetime.datetime`, and `HUGEINT` was corrected from `int` to `decimal.Decimal` (D-05). No
new stripping logic was needed: the existing `split("(")` already delivers `ENUM` from
`ENUM('sad', 'ok', 'happy')`.

`INTERVAL` was left alone (D-06) and recorded as broken window **6**.

### `semolina.JsonValue` (TYPE-06)

A new `src/semolina/types.py` hosts the recursive alias in the quoted form 3.11 requires,
exported from the package root as `__all__` entry 23. `VARIANT` and `variant` map to it, and
`_build_import_lines` adds `JsonValue` to the single `from semolina import ...` line only when
an annotation uses it. A VARIANT field renders as:

```python
from semolina import Dimension, Fact, JsonValue, Metric, SemanticView


class V(SemanticView, view="v"):
    # VARIANT
    payload = Dimension[JsonValue]()
```

## The checkpoint was rejected, and replaced with measurement

Task 3 was planned as a `checkpoint:human-verify` asking the user to confirm the annotation
table matched what they had locked. They rejected the gate:

> there's no point asking me if the annotations have to match what is actually returned by the
> driver - measure the correct types instead

That is the right call, and it is a better test than the one it replaced. A human reading a
table can only confirm the table matches another table. `tests/unit/test_annotation_contract.py`
confirms the annotation matches the warehouse.

**The predicate is `isinstance(measured_value, annotated_type)`.** A name comparison would
have rejected the `TIMESTAMP_NS` row, where the value is a `pandas.Timestamp` and the
annotation is `datetime.datetime` — a sound over-approximation, since the one subclasses the
other. `isinstance` admits that and still fails an annotation naming a type the value is not.

**DuckDB is measured live.** Eleven real columns in an in-memory DuckDB, read through
`adbc_driver_duckdb` — the same driver `create_engine(DuckDBConfig(...))` uses. The type string
each column is mapped by comes from `DESCRIBE SELECT`, which is what `DuckDBEngine.introspect`
actually feeds the map, rather than from the DDL that declared it. The engine is built by
`type_fidelity_probe.make_probe_engine`, which already owns the `pool_size=1` mitigation for
adbc-poolhouse's per-connection database clone.

**Snowflake and Databricks are measured from the committed cassettes**, read with
`pyarrow.ipc.open_file`. The hand-fed mock in `tests/unit/test_snowflake_engine.py` is not used
as evidence — Phase 47 labelled it non-evidence because it asserts the answer the type map
already produces, and quoting it here would have made the check circular in exactly the way
Phase 47 exists to prevent.

**`INTERVAL` is `xfail(strict=True)`, inside the parametrization.** It fails because the value
is a `pyarrow.MonthDayNano` and the annotation says `datetime.timedelta`. Strict, so the day
someone fixes the map, the expected failure becomes a reported failure and the row has to be
updated deliberately. It is not skipped and not excluded: a silent exclusion is how the row
stayed wrong through two phases with nothing going red. `test_duckdb_contract_covers_every_measured_column`
guards the exclusion route directly.

## The Databricks interval annotation was reverted

The plan had `databricks_type_to_python` grow an `interval` branch returning
`datetime.timedelta` for the day-time family. It landed in Task 2 and was **removed in Task 3**,
along with its two frozensets.

Nothing in this repo has a Databricks interval column — no fixture, no cassette, no recording —
so `test_annotation_contract.py` cannot reach that row, and nobody has ever seen what such a
value arrives as over the Foundry ADBC driver. The annotation rested on the documented
type-object grammar plus the reasoning that a day-to-second interval is a fixed duration. That
is a good guess. It is still a guess, and it would have been the only guess sitting among rows
that are all measured, which makes the contract read stronger than it is.

Both interval families now return `None` and generate a `TODO:`. The branch was deleted rather
than left returning `None` on both arms, because a branch that always returns `None` is dead
code impersonating a decision; a comment at the map site records why the obvious annotation is
absent. `TestDatabricksIntervalType` was re-pointed to assert the refusal itself, which stays
meaningful either way and is what has to be consciously updated the day a recording exists.

**T-48-10 is closed by construction rather than by mitigation.** The threat was a
catalogue-controlled `start_unit` string reaching generated Python source. With the branch gone,
`databricks_type_to_python` reads only `name` and resolves it through a closed dict, so no other
key is read at all. `test_no_unit_value_can_reach_an_annotation` asserts it over hostile values.

## Evidence limits

Three, all recorded rather than described. Phase verification should see stated limits here, not
silent gaps.

| What | Status | Ledger |
|---|---|---|
| **Databricks `interval`** still emits a `TODO:` | TYPE-05 partially unmet, deliberately | WINDOWS.md **7** + `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md` |
| **`VARIANT` → `JsonValue`** is unmeasured | Kept, not reverted | WINDOWS.md **8** |
| **DuckDB `INTERVAL`** annotation is known wrong | Pinned by a strict xfail | WINDOWS.md **6** |

**Why VARIANT was kept where the interval was reverted.** The two are not the same strength of
claim. `datetime.timedelta` is a single concrete type, wrong if the value is anything else.
`JsonValue` is a union over the whole JSON value domain — `str | int | float | bool | None |
list[...] | dict[str, ...]` — so it holds whether a VARIANT arrives as raw JSON text or as a
parsed structure, which are the two plausible outcomes. It is only wrong if the value is outside
that domain entirely, such as a driver-specific wrapper object. That is a narrower exposure than
the interval had, and it is recorded either way.

**The "three backends agree on decimal" claim is carried at the mapper level and through the
mocked E2E seam**, not against a real warehouse decimal column on all three. The Snowflake
recording fixture declares bare `NUMBER` (= `NUMBER(38,0)`, already max precision, so a `SUM`
cannot widen) and the Databricks fixture has no decimal column at all. Both gaps were already
recorded in `47-TYPE-FIDELITY.md` § "Evidence limitations"; the same recording session closes
them and the interval one.

## Artifacts the plan asked to be recorded exactly

### The `.ambr` diff

Shown above under "The Decimal policy, completed". One snapshot changed;
`test_codegen_databricks_field_types` and `test_codegen_file_backed_duckdb` are byte-identical.

### The `47-TYPE-FIDELITY.md` diff hunks

Two. The first is the predicted row flip:

```diff
-| snowflake | AGG("REVENUE") | metric | {"type": "FIXED", "scale": 0} | derived-from-code | int | decimal128(38, 0) | cassette-file | decimal.Decimal | mismatch |
+| snowflake | AGG("REVENUE") | metric | {"type": "FIXED", "scale": 0} | derived-from-code | decimal.Decimal | decimal128(38, 0) | cassette-file | decimal.Decimal | match |
```

The second is a prose correction the plan did not predict, in § "No Snowflake introspection
cassette exists". The paragraph said the mock "feeds `{"type": "FIXED", "scale": 0}` in and
asserts `int` comes out". That became false the moment Task 1 landed, and it would have shipped
a false statement inside the evidence artifact:

```diff
-asserts `int` comes out, so it asserts the answer the type map already produces. That mock
+asserts `decimal.Decimal` comes out, so it asserts the answer the type map already produces.
```

The circularity argument the sentence exists to make is unchanged. The same stale claim in
`tests/integration/test_type_fidelity.py`'s docstring for `test_snowflake_probe` was corrected
in the same commit.

The artifact regenerates byte-identically after the `probe_values` refactor, which is the check
that the refactor is behaviour-preserving.

### WINDOWS.md entry ids

DuckDB `INTERVAL` is entry **6** (`deviation`). The two evidence limits added in Task 3 and
Task 4 are **7** and **8** (both `unrun-verify`). `open_count` moved 4 → 7.

## Deviations from Plan

### Directed change

**1. Task 3 replaced: human verification → executed measurement.** Directed by the user through
the coordinator, mid-plan. Covered in full above. Consequences: `tests/unit/test_annotation_contract.py`
is new and unplanned; the Databricks interval annotation from Task 2 was reverted; two evidence
limits were recorded; `probe_values` was added to the probe.

### Auto-fixed issues

**2. [Rule 1 - Bug] Two prose statements became false when Task 1 landed**

- **Found during:** Task 1, checking what the artifact would regenerate to.
- **Issue:** `tests/type_fidelity_probe.py`'s evidence-limitations section and
  `tests/integration/test_type_fidelity.py::test_snowflake_probe`'s docstring both stated that
  the Snowflake mock asserts `int`. The first is rendered verbatim into the committed evidence
  artifact.
- **Fix:** Both corrected to `decimal.Decimal`; the integration docstring additionally now says
  the disagreement it once recorded is what Phase 48 closed.
- **Commit:** `6ac1cb1`

**3. [Rule 3 - Blocking] basedpyright blocks a RED commit that imports a not-yet-existent symbol**

- **Found during:** Task 4.
- **Issue:** CLAUDE.md wants the failing test committed first; the `basedpyright` pre-commit
  hook runs over all files and rejects `from semolina import JsonValue` before `types.py`
  exists. `--no-verify` was not an option.
- **Fix:** Split the task into three commits — the alias plus its public-surface test (`c1fce25`),
  then the mapper and renderer tests as a genuine RED (`a4703fb`), then the implementation
  (`ece6c32`). The behaviour change still has a failing-test-first pair; only the symbol's
  existence moved ahead of it.

### Process notes

**4. A needless `git stash --keep-index` briefly reverted an uncommitted `__init__.py` edit.**
Recovered with `git stash pop` in the same minute, nothing lost. Recorded because the stash
stack is shared across worktrees and this was avoidable: `git status --short` answers the
question the stash was run for.

## Findings

**Two acceptance criteria are unsatisfiable as written, both for the same reason as 48-01's
`| None` grep.** Recording the pattern, since it has now recurred three times.

- `grep -v '^ *#' src/semolina/codegen/type_map.py | grep -c 'scale'` is specified as 0; it is
  5. Docstrings are not `#` comments, and the surviving mentions are the docstring explaining
  that `scale` is deliberately ignored plus the `Example:` block demonstrating that two
  different scales give the same answer. The criterion's stated intent — "the `scale` read is
  gone from the function body" — holds: `grep -c 'type_json.get("scale"' ` is 0.
- `grep -c 'uuid' src/semolina/codegen/type_map.py` is specified as 0; it is 1. The hit is the
  comment recording *why* `uuid.UUID` was rejected. The intent — no `uuid.UUID` annotation
  introduced — was verified directly instead: no value in any of the three maps contains
  `uuid`, and the full value vocabulary is `bool, bytes, datetime.date, datetime.datetime,
  datetime.time, datetime.timedelta, decimal.Decimal, float, int, str` (plus `JsonValue`).

The lesson for later plans: assert on map *values* or on parsed code, not on file-wide greps
that a comment explaining the rule will trip.

**A guard that is never broken is a guess about a guard.** Every new assertion in this plan was
deliberately broken and watched go red before being committed:

| Guard | Break applied | Result |
|---|---|---|
| DuckDB contract | `UUID` → `uuid.UUID` | red, naming `builtins.str` as the measured value |
| DuckDB contract | `HUGEINT` → `int` | red, naming `decimal.Decimal` |
| INTERVAL strict xfail | `INTERVAL` → `pyarrow.MonthDayNano` | red as `XPASS(strict)` |
| Coverage guard | `c_json` dropped from the parametrization | red, naming the dropped column |
| Conditional import | `JsonValue` imported unconditionally | red on the negative test |

## Verification

| Gate | Result |
|---|---|
| `just test` — root suite | 1130 passed, 1 xfailed |
| `just test` — semolina-jaffle-shop suite | 16 passed, 15 skipped |
| `prek run --all-files` (ruff lint+format, basedpyright strict) | clean |
| `just docs-build` (sphinx `-W`) | build succeeded |
| `uv run python tests/type_fidelity_probe.py --check` | exit 0 |
| `git diff 9f3c8b9..HEAD` naming `cursor.py` / `acursor.py` / `results.py` | none |
| `git diff 9f3c8b9..HEAD` naming `47-DECISIONS.md` | none |
| `# type: ignore` added anywhere in this plan's diff | 0 |

## Known Stubs

None. No stub values and no unrun `<verify>` block.

One test is a deliberate expected failure: `test_annotation_contract.py::…[c_interval]`,
`xfail(strict=True)`, documented above and in WINDOWS.md entry 6. It is not a skipped test — it
executes, fails for the recorded reason, and will report a failure if that reason stops holding.

## Threat Flags

None new. Of the dispositions this plan owned: **T-48-10** (catalogue-controlled interval units
reaching an annotation) is closed by construction — the branch that read those keys no longer
exists, and `test_no_unit_value_can_reach_an_annotation` asserts it over hostile inputs.
**T-48-11** holds: all three mappers are closed-vocabulary `dict.get` lookups over literals
written in this repo. **T-48-13** (the WINDOWS.md dual representation drifting) was avoided by
using the `gsd-tools windows append` entry point for all three entries rather than hand-editing.
**T-48-12** (`JsonValue` has no runtime behaviour) is accepted as planned. No packages installed.

## Self-Check: PASSED

- `src/semolina/types.py` — FOUND
- `tests/unit/test_annotation_contract.py` — FOUND
- `tests/unit/test_public_surface.py` — FOUND
- `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md` — FOUND
- Commits `b651104`, `6ac1cb1`, `51342ca`, `b4f804e`, `98148f1`, `c1fce25`, `a4703fb`, `ece6c32` — all FOUND in `git log`
