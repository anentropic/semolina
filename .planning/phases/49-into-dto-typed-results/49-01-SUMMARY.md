---
phase: 49-into-dto-typed-results
plan: 01
subsystem: api
tags: [arrowmodel, pydantic, pyarrow, polars, pandas, packaging, extras, duckdb, decimal]

requires:
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "Decision 1's Decimal policy and its prohibition on touching the row value path; the DECIMAL(10,2) probe fixture whose SUM arrives as decimal128(38, 2)"
  - phase: 48-annotation-contract
    provides: "arrow_type_to_python's predicate cascade, semolina.codegen.probe, and the scope fence this plan narrows"
  - phase: 46-async-cursor
    provides: "AsyncSemolinaCursor and its synchronous description property, which the async twins in Plan 06 reuse"
provides:
  - "Four published extras — [pyarrow], [pandas], [polars], [arrowmodel] — with [all] reaching all four and [duckdb] referencing semolina[pyarrow]"
  - "src/semolina/exceptions.py: SemolinaMissingDependencyError, SemolinaSchemaMismatchError, and the _require() find_spec guard"
  - "src/semolina/dto.py: check_result_schema() and resolve_column_key(), the structural pre-check satisfying DTO-03"
  - "arrow_type_to_runtime_type(), a thin runtime-type adapter over arrow_map's single cascade"
  - "SemolinaCursor.into(model, *, validate=False)"
  - "A value-path CONTENT fence replacing Phase 48's path fence for cursor.py/acursor.py (PD-06)"
affects: [49-02-iter-into, 49-03-type-fidelity-regeneration, 49-04-packaging, 49-05-fetch-df-polars, 49-06-async-twins, 49-07-docs, 50-codegen-dtos]

actuals:
  tokens: 18856
  tasks: 3
  commits: 3

tech-stack:
  added: [arrowmodel>=1.0.0, polars>=1.0.0, pandas>=2.0.0, pyarrow>=17.0.0]
  patterns:
    - "Guard, pre-check, then delegate: every new result-shaping method is _require() x N, then a schema check, then a one-line delegation"
    - "One cascade, two renderings: a runtime-type answer is an adapter over the annotation-string answer, never a second predicate chain"
    - "Content fences over path fences when a later phase must legitimately touch a protected module"

key-files:
  created:
    - src/semolina/exceptions.py
    - src/semolina/dto.py
    - tests/unit/test_dto_duckdb.py
    - .planning/todos/pending/2026-08-14-polars-2-0-changes-fetch-polars-return-shape.md
  modified:
    - pyproject.toml
    - uv.lock
    - src/semolina/cursor.py
    - src/semolina/codegen/arrow_map.py
    - src/semolina/__init__.py
    - tests/unit/test_scope_fence.py
    - tests/unit/codegen/test_arrow_map.py

key-decisions:
  - "arrowmodel floor pinned at >=1.0.0, uncapped: 1.0.0 is still the only release, so floor and pin are the same set today, and a floor lets a future 1.1 land without forcing a Semolina release"
  - "arrowmodel's SUS legitimacy score is a confirmed false positive — PyPI author `Anentropic <ego@anentropic.com>` and repo `anentropic/arrowmodel` are this project's own maintainer; low downloads are expected for a first-party package"
  - "The pre-check reports a mismatch only when both sides reduce to a class or a union of classes; Any, unmapped Arrow types and unreduceable generics pass silently with no verdict"
  - "typing.Any needs an explicit special case for a reason that changed between interpreters: issubclass(x, Any) raises TypeError on 3.11 but quietly answers False on 3.14, so falling through would crash on one and produce a false mismatch on the other"
  - "validate=True catches exactly one thing the pre-check does not — a NULL in a non-optional field — which is D-09's accepted consequence, now pinned by a test rather than left as an inference"
  - "_require stays module-private and is listed in exceptions.py's __all__; that satisfies basedpyright strict's reportUnusedFunction without a suppression comment, because the underscore means 'internal to Semolina', not 'internal to this file'"
  - "PD-06: Phase 48's value-path scope fence narrowed from a path fence to a content fence for the two cursor modules; results.py stays fenced by path"

patterns-established:
  - "Optional-dependency guard: _require(package, extra) calls importlib.util.find_spec by dotted name inside the function body, with no caching, so patch('importlib.util.find_spec') reaches it"
  - "Pre-check reads cursor.description, never fetch_arrow_table().schema — synchronous on both cursors, creates no reader, which is what lets the async iter_into stay a plain method"
  - "Every error message on this surface carries field names, column names and type names only; a test asserts no seeded row value appears in the message"

requirements-completed: [DTO-01, DTO-03, DTO-05]

coverage:
  - id: D1
    description: "`.into(MyDTO)` on a live DuckDB semantic-view result returns Pydantic instances, with a decimal128(38, 2) metric arriving as a real decimal.Decimal"
    requirement: DTO-01
    verification:
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoDecimalRoundTrip::test_decimal_metric_arrives_as_a_real_decimal"
        status: pass
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoDecimalRoundTrip::test_into_returns_model_instances"
        status: pass
    human_judgment: false
  - id: D2
    description: "A DTO annotating a decimal128 column as float raises SemolinaSchemaMismatchError naming the field and both types, on validate=False AND validate=True"
    requirement: DTO-03
    verification:
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoSchemaMismatch::test_decimal_into_float_raises"
        status: pass
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoSchemaMismatch::test_decimal_into_float_raises_with_validate_true"
        status: pass
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoSchemaMismatch::test_every_mismatch_is_reported_at_once"
        status: pass
    human_judgment: false
  - id: D3
    description: "Zero-row results return [], NULLs arrive as None, Any-annotated fields pass, unclaimed columns are ignored, and defaults make a field optional"
    requirement: DTO-01
    verification:
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoEdgeShapes"
        status: pass
      - kind: integration
        ref: "tests/unit/test_dto_duckdb.py#TestIntoFieldPresence"
        status: pass
    human_judgment: false
  - id: D4
    description: "arrow_type_to_runtime_type shares one predicate cascade with arrow_type_to_python, enforced by a test that fails rather than raising KeyError at a user's call site"
    verification:
      - kind: unit
        ref: "tests/unit/codegen/test_arrow_map.py#TestArrowTypeToRuntimeType::test_every_reachable_annotation_has_a_runtime_type"
        status: pass
    human_judgment: false
  - id: D5
    description: "Four extras declared with justified floors, [all] reaches all four, [duckdb] references semolina[pyarrow], and uv.lock is regenerated so uv sync --locked succeeds"
    requirement: DTO-05
    verification:
      - kind: other
        ref: "uv sync --locked --all-groups --extra all"
        status: pass
    human_judgment: false
  - id: D6
    description: "The Phase 48 value-path scope fence still runs and still fails on a real violation after Phase 49 legitimately adds methods to cursor.py"
    verification:
      - kind: unit
        ref: "tests/unit/test_scope_fence.py#test_row_construction_introduces_no_value_conversion"
        status: pass
    human_judgment: true
    rationale: "PD-06 narrows a prohibition approved at a Phase 47 blocking human checkpoint. The replacement fence was proven non-vacuous by execution (output recorded below), but whether a content fence is an acceptable substitute for a path fence is a judgment about how much guarantee the project is willing to trade, not something a test can answer."

duration: 12min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 01: `.into(DTO)` Tracer Summary

**One live DuckDB `DECIMAL(38,2)` metric carried end to end into a `decimal.Decimal`-annotated Pydantic field through a new schema pre-check and arrowmodel — and refused, on both `validate` settings, when the same column is declared `float`.**

## Performance

- **Duration:** ~12 min of execution (excluding the blocking human checkpoint)
- **Started:** 2026-08-14T08:03:45+01:00 (first task commit)
- **Completed:** 2026-08-14T08:15:32+01:00
- **Tasks:** 3 (1 checkpoint, 2 implementation)
- **Files modified:** 11 (4 created, 7 modified)

## Accomplishments

- **DTO-01 proven by measurement, not by table lookup.** `cursor.into(SalesDTO)` against a live in-memory DuckDB semantic view returns real model instances, and `isinstance(rows["US"].total_order_value, decimal.Decimal)` holds for a value that came through the real ADBC driver path from a `decimal128(38, 2)` column.
- **DTO-03 satisfied by a structural pre-check, which is the only thing that can satisfy it.** Research measured both arrowmodel paths failing silently on the headline case: the fast path leaves a `Decimal` in a `float` field, and `validate=True` coerces it to `43.25` and loses the precision. `check_result_schema` runs before either, on both settings.
- **DTO-05's declaration half shipped.** Four published extras with justified floors, `[all]` recomposed to reach all four, `[duckdb]` referencing `semolina[pyarrow]` rather than duplicating the pin, and `uv.lock` regenerated in the same commit so `uv sync --locked` still succeeds.
- **The scope fence was narrowed rather than deleted or left red** (PD-06), and the replacement was proven non-vacuous by execution before being trusted.
- **Every seam the rest of the phase builds on is now exercised:** the install contract, the guard helper, the error module, the pre-check, the cursor surface and a live warehouse have all run together on one column.

## Task Commits

1. **Task 1: arrowmodel legitimacy checkpoint** — no commit (blocking human gate; approved, decision recorded below)
2. **Task 2: Four published extras, `[all]` recomposed, regenerated lock** — `5838a62` (chore)
3. **Task 3: `.into()` tracer — exceptions, pre-check, runtime-type sibling, cursor surface, fence narrowing** — `5e03d4c` (feat)

## Files Created/Modified

- `src/semolina/exceptions.py` (new) — `SemolinaMissingDependencyError`, `SemolinaSchemaMismatchError`, `_require(package, extra)`
- `src/semolina/dto.py` (new) — `FieldMismatch`, `REASON_TYPE`/`REASON_MISSING`, `resolve_column_key`, `check_result_schema`
- `src/semolina/cursor.py` — `SemolinaCursor.into`; the `to_pylist()` → `Row(...)` value path untouched
- `src/semolina/codegen/arrow_map.py` — `_ANNOTATION_TO_TYPE` and `arrow_type_to_runtime_type`
- `src/semolina/__init__.py` — both new errors imported and added to `__all__`
- `pyproject.toml` / `uv.lock` — four extras, recomposed `[all]`, regenerated lock
- `tests/unit/test_dto_duckdb.py` (new) — 24 live-DuckDB tests across five classes
- `tests/unit/test_scope_fence.py` — PD-06 narrowing plus the new content fence
- `tests/unit/codegen/test_arrow_map.py` — `TestArrowTypeToRuntimeType`, including the cascade-coverage guard
- `.planning/todos/pending/2026-08-14-polars-2-0-changes-fetch-polars-return-shape.md` (new)

## Task 1: the legitimacy gate, and what it decided

The checkpoint was answered **approved**. Recorded here so the next phase does not re-litigate it:

- **`arrowmodel>=1.0.0`, uncapped.** Re-checked against the PyPI JSON API at execution time rather than trusting RESEARCH.md's five-week-old reading: **1.0.0 is still the only release** (uploaded 2026-07-07T14:26:25Z). The 1.1 that RESEARCH.md warned could land inside this phase has not. Floor and pin are therefore the same set today; a floor was chosen anyway so a future 1.1 can land in a user's environment without forcing a Semolina release, consistent with PD-03's reasoning that a cap in a published extra is itself a support burden.
- **The `SUS` heuristic verdict is a confirmed false positive.** PyPI `author_email` is `Anentropic <ego@anentropic.com>`; the GitHub repo `anentropic/arrowmodel` exists under the same owner, created 2026-03-21, last pushed 2026-08-03. Zero stars and no published download count are expected signals for a first-party package five weeks old, not slopsquatting signals. `gsd-tools query package-legitimacy check` returned all-null signals for *every* package including `pandas` and `pyarrow`, so its verdict carried no information for any of them.
- **Wheels confirmed:** `cp311-abi3` for macOS x86_64 + arm64, manylinux_2_17 x86_64 + aarch64, win_amd64, plus an sdist. The abi3 wheels cover CI's 3.11 and 3.14, so neither CI nor a user builds the Rust extension from source.
- **The published-extras contract accepted per D-12**, with the pydantic 2.12.5 → 2.13.4 bump accepted as expected rather than waved through: Task 2's acceptance required the existing suite green at the new version, and it is (see below).

## The `uv.lock` deltas actually observed

The plan predicted "pydantic 2.12.5 → 2.13.4, plus new entries for arrowmodel and polars" and asked for any other movement to be recorded as a finding rather than a formality. Observed, complete:

| Package | Before | After | Expected? |
|---|---|---|---|
| `arrowmodel` | absent | 1.0.0 | yes |
| `polars` | absent | 1.43.2 | yes |
| `polars-runtime-32` | absent | 1.43.2 | **no — see below** |
| `pydantic` | 2.12.5 | 2.13.4 | yes (dragged by arrowmodel) |
| `pydantic-core` | 2.41.5 | 2.46.4 | yes (pydantic's own native half) |

**Nothing else moved.** `git diff -U0 uv.lock | grep -E '^[-+](name|version) = '` returns exactly the rows above.

**Finding — `polars-runtime-32` is a fourth new package, not a third.** It is a hard dependency of `polars` itself at the same version (`polars 1.43.2` declares `dependencies = [{ name = "polars-runtime-32" }]`), published by Ritchie Vink and pointing at `pola-rs/polars` — polars 1.4x splits its compiled runtime into a separate distribution. Legitimate, and checked against the registry rather than assumed, because an unexpected transitive is exactly what threat T-49-04 is about.

**The full existing suite is green at pydantic 2.13.4**: 1349 passed, 16 skipped, 2 xfailed, with one failure that is not a pydantic regression (next section). The jaffle-shop suite is 16 passed, 15 skipped.

## `tests/type_fidelity_probe.py --check`: failed, on exactly the two rows Plan 03 owns

Exit code 1. The complete diff:

```
-| pydantic | pydantic 2.12.5: `decimal.Decimal` field accepted unchanged | measured | A1 |
-| polars | not measured — polars not installed | not measured | A3 |
+| pydantic | pydantic 2.13.4: `decimal.Decimal` field accepted unchanged | measured | A1 |
+| polars | not measured — polars installed but out of scope until Phase 49 | not measured | A3 |
```

This surfaces in the root suite as `tests/unit/test_type_fidelity_table.py::test_committed_table_is_not_stale`, the only failing test in the run.

**Not fixed here, deliberately.** The plan's `<verification>` block anticipates precisely this and says "Record which, do not fix it here" — D-16's regeneration is Plan 03's. Regenerating now would also have been actively wrong: `_measure_polars()` still hard-codes `"out of scope until Phase 49"` and still returns `STATUS_NOT_MEASURED`, so a regeneration today would commit a polars row that is freshly generated and still false.

**Note a contradiction inside the plan itself, resolved in favour of `<verification>`.** Task 2's acceptance criteria say `uv run pytest -x -q` must exit 0 and that "a failure here is a real regression from pydantic 2.12.5 -> 2.13.4". The failure is not a pydantic regression — it is the artifact staleness gate correctly firing because the environment changed, which the same plan's `<verification>` block predicts by name. Recorded rather than suppressed, and rather than silently satisfying the stricter criterion by stepping into Plan 03's task.

## PD-06: the scope-fence narrowing, and its non-vacuity proof

**This narrows a prohibition approved at a Phase 47 blocking human checkpoint, so it gets its own heading.**

`tests/unit/test_scope_fence.py` fenced `src/semolina/{cursor,acursor,results}.py` by *path*: any diff naming one of them, between commit `9f3c8b9` and HEAD, failed. Phase 49 legitimately adds `into`, `iter_into`, `fetch_df` and `fetch_polars` to both cursors, so the gate went red at this plan's first source commit and would have stayed red for the whole phase. Re-pointing `DEFAULT_BASE_REF` would not have helped — the phase's own commits touch those files.

What changed:

- `FENCED_PATH_PATTERN` narrowed from `(cursor|acursor|results)` to `results\.py` alone. Phase 49 has no reason to touch `results.py`, so the stronger path-level guarantee survives where it still applies.
- A new `test_row_construction_introduces_no_value_conversion` parses `cursor.py` and `acursor.py` with `ast`, locates the five row-construction functions by name (`__next__`, `__anext__`, `fetchall_rows`, `fetchone_row`, `fetchmany_rows`), and fails on any `ast.Call` inside them targeting a name in `FORBIDDEN_CONVERSION_NAMES` (`float`, `int`, `complex`, `Decimal`, `round`, `quantize`, `to_integral_value`, `to_integral_exact`, `from_float`, `normalize`). Both `ast.Name` and `ast.Attribute` call shapes are reduced to the bare name, so an import alias cannot smuggle a conversion past it.
- Two anti-vacuity assertions the old fence did not have: the test fails if either module is missing, and fails if a module yields **none** of the five named functions — so a rename empties the fence loudly rather than leaving it green and guarding nothing.
- It reads the working tree rather than a diff, so unlike the path fence it **cannot skip**, and it also catches a conversion that predates the base commit.

**Observed failure against a deliberately-introduced violation.** `src/semolina/cursor.py`'s `__next__` was temporarily changed from `row = Row(self._batch_rows[self._batch_pos])` to `row = Row({k: float(v) for k, v in self._batch_rows[self._batch_pos].items()})`, which is a genuine instance of the prohibited change. The fence went red:

```
E       AssertionError: Value conversion introduced on the row-construction path:
        ['src/semolina/cursor.py::__next__ (line 325) calls float'].
        47-DECISIONS.md Decision 1 is annotation-only: the annotation is corrected to the
        value, never the reverse. If a value genuinely needs converting, that is a new
        decision, not an implementation detail.
E       assert not ['src/semolina/cursor.py::__next__ (line 325) calls float']

tests/unit/test_scope_fence.py:268: AssertionError
=========================== short test summary info ============================
FAILED tests/unit/test_scope_fence.py::test_row_construction_introduces_no_value_conversion
============================== 1 failed in 0.06s ===============================
```

The violation was reverted and both fence tests report **passed, neither skipped**.

**Honest assessment of what was traded.** A path fence catches edits a content fence cannot imagine — a new helper called from `__next__` but defined elsewhere, a conversion pushed into `results.Row.__init__`, an `eval`. The content fence catches the specific thing Decision 1 names, in the specific place it names it. That is a real reduction in guarantee, and it is why this section exists rather than a line in a changelog.

## Decisions Made

Beyond the plan's own PD-01…PD-06 (all followed as written):

1. **`typing.Any`'s special case is load-bearing for a reason that changed between interpreters.** RESEARCH.md measured `issubclass(x, Any)` raising `TypeError` on Python 3.11. On this project's 3.14 venv it does not raise — it quietly returns `False`, and `isinstance(Any, type)` is `True`. So without the explicit early return, an `Any`-annotated field would crash on 3.11 and be reported as a *false mismatch* on 3.14. Both interpreters are in the CI matrix. Recorded in the code comment and covered by `test_any_annotated_field_passes_the_pre_check`.
2. **`validate=True` catches exactly one thing the pre-check does not: a NULL in a non-optional field.** Discovered by a test failure, not predicted by the plan. The probe's `CA` group aggregates nothing, so `total_order_value` is NULL there; the fast path puts `None` into a `decimal.Decimal` field silently, while `validate=True` raises pydantic's own `ValidationError`. This is D-09's accepted consequence (nullability is deliberately not checked, because the Arrow `nullable` flag reads `True` for every DuckDB field including `COUNT`) and is now pinned by `test_validate_true_rejects_a_null_the_pre_check_allows` so a future change to either half has to be deliberate.
3. **`check_result_schema` keeps two structures, not one.** Column *names* come from every `description` entry; column *types* only from entries whose `d[1]` is a real `pyarrow.DataType`. The plan said to "skip that column entirely" when the type is not a `DataType`, but skipping it from the name set too would make a non-ADBC cursor report every declared field as missing — turning a "no type opinion" case into a wall of false positives. The presence test and the type test are now sourced separately.
4. **`_require` stays private and is listed in `exceptions.py`'s `__all__`.** basedpyright strict's `reportUnusedFunction` fires on an underscore-prefixed function with no same-file reference, and cross-module imports of a private name do not count. Listing it in `__all__` resolves it with no `# type: ignore` and no pyproject-level exemption, and is honest: the underscore means "internal to Semolina", not "internal to this file".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Two acceptance-criteria commands in the plan are factually wrong; used working equivalents**
- **Found during:** Task 2
- **Issue:** The criterion `uv run python -c "import polars, arrowmodel; print(polars.__version__, arrowmodel.__version__)"` exits 1. **arrowmodel 1.0.0 exposes no `__version__` attribute** — its public names are `AliasChoices`, `AliasPath`, `ArrowModel`, `ArrowModelConverter`, `BaseModel`, `model_convert`, `model_iter`.
- **Fix:** Verified the same intent through `importlib.metadata.version("arrowmodel")`, which reports `1.0.0`. No source change; the criterion's intent (both packages importable at known versions) is satisfied.
- **Verification:** `uv run python -c "import importlib.metadata as m, polars, arrowmodel; print(m.version('polars'), m.version('arrowmodel'))"` → `1.43.2 1.0.0`.
- **Committed in:** n/a (no code change)

**2. [Rule 1 — Bug] Two of my own test assertions were wrong; fixed before committing**
- **Found during:** Task 3
- **Issue:** (a) `test_validate_true_also_returns_decimals` used a non-optional `decimal.Decimal` annotation against a result containing the `CA` group's NULL, so `validate=True` correctly raised. (b) `TypeFidelityView.__view_name__` does not exist; the attribute is `_view_name`.
- **Fix:** (a) split into two tests — one using `decimal.Decimal | None` for the positive claim, and a new `test_validate_true_rejects_a_null_the_pre_check_allows` that pins the NULL asymmetry as intended behaviour rather than hiding it. (b) corrected the attribute name.
- **Files modified:** `tests/unit/test_dto_duckdb.py`
- **Verification:** `uv run pytest tests/unit/test_dto_duckdb.py -q` → 24 passed.
- **Committed in:** `5e03d4c`

---

**Total deviations:** 2 auto-fixed (2 bugs — one in the plan's acceptance criteria, one in newly-written test code). No scope creep; no source behaviour changed as a result.

## Issues Encountered

- **`import semolina` pulls `pyarrow` into `sys.modules`, and always has.** I tried to assert it absent and found it present. Traced to **`adbc_poolhouse`**, which imports pyarrow at module scope when it is available; it does not *declare* pyarrow (`requires` lists only `pydantic-settings`, `sqlalchemy`, `adbc-driver-manager`), so D-15's premise still holds — in a genuinely base install pyarrow is absent and `_require("pyarrow", ...)` is reachable. **Consequence for Plan 04:** its packaging test must not assert `pyarrow` absent from `sys.modules` after `import semolina`, only `arrowmodel` / `pandas` / `polars`. `tests/unit/test_dto_packaging.py` should be written accordingly; `49-PATTERNS.md` flagged this as "check before asserting", and this is the checked answer.
- **`uv sync --all-groups --extra all` uninstalls the `semolina-jaffle-shop` workspace member.** Harmless — `pushd semolina-jaffle-shop; uv run pytest` reinstalls it on the spot and the suite is 16 passed, 15 skipped. Noted so it is not mistaken for breakage next time.
- **`prek` reformatted files during two commit attempts**, aborting them. Re-staged and re-committed; no content was lost and the tests were re-run green after each reformat.

## Verification Results

| Gate | Result |
|---|---|
| `uv sync --locked --all-groups --extra all` | exit 0 |
| `uv run pytest tests/unit/test_dto_duckdb.py tests/unit/codegen/test_arrow_map.py -x -q` | 97 passed |
| `uv run pytest tests/unit/test_scope_fence.py -x -v` | 2 passed, **neither skipped** |
| `uv run pytest -q` (root) | 1349 passed, 16 skipped, 2 xfailed, **1 failed** — `test_committed_table_is_not_stale` only (Plan 03) |
| `semolina-jaffle-shop` suite | 16 passed, 15 skipped |
| `prek run --all-files` | all hooks passed, incl. basedpyright strict, **no new suppression comment anywhere in the diff** |
| `uv run sphinx-build -W docs/src docs/_build` | build succeeded |
| `uv run python tests/type_fidelity_probe.py --check` | exit 1 — polars + pydantic rows only (Plan 03 owns) |
| `git diff --exit-code src/semolina/engines/base.py` | exit 0 — byte-unchanged (D-14) |

## Known Stubs

None. Everything this plan declares is implemented and exercised against a live warehouse. `iter_into`, `fetch_df`, `fetch_polars` and the async twins are **not stubbed** — they are simply not part of this plan and do not exist yet; Plans 02, 05 and 06 own them.

## Next Phase Readiness

Ready. The seams the remaining plans expand are all proven:

- **Plan 02 (`iter_into`)** — reuses `check_result_schema` unchanged and must call it eagerly, then return a generator. Note `ArrowModelConverter.convert()/iter()` take **no** `validate=` keyword; it is set on the constructor.
- **Plan 03 (D-16, type-fidelity regeneration)** — inherits a red `--check` on exactly two rows, both listed above with their exact text. `_measure_polars()` must gain a `table` parameter and actually measure; `render_downstream_decimal` also generates prose that Phase 49 falsifies.
- **Plan 04 (packaging)** — see the `sys.modules` finding above before writing `test_dto_packaging.py`.
- **Plan 05 (`fetch_df` / `fetch_polars`)** — `_require` is ready; guard `fetch_polars` on **polars only**, not pyarrow.
- **Plan 06 (async twins)** — `AsyncSemolinaCursor.description` is already a plain synchronous property, so `check_result_schema` works there with no await, which is what keeps `iter_into` a plain method.
- **Plan 07 (docs)** — the `validate=True` caveat and the `int`-into-`float` surprise (PD-02) both need saying out loud, and the worked example needs `Field(validation_alias=...)` to survive leaving DuckDB.

One item for phase verification: **PD-06's fence narrowing is the plan's only `human_judgment: true` deliverable.** The replacement fence was proven non-vacuous by execution, but the trade it makes is a judgment call.

## Requirement Status: all three left Pending, deliberately

`requirements-completed` above lists the IDs this plan *advances*, not IDs it closes. All three were briefly marked Complete by the state tooling and **reverted**, because every one is partial by this plan's own `<success_criteria>`:

| ID | What shipped here | What is still owed | Owner |
|---|---|---|---|
| DTO-01 | `.into()` on the **sync** cursor | the async twin | Plan 06 |
| DTO-03 | the pre-check on the **eager** path | `iter_into`'s eager raise | Plan 02 |
| DTO-05 | the **declaration** half (extras + lock) | the clean-venv proof that a base install pulls no arrowmodel | Plan 04 |

Following Phase 48's precedent with TYPE-05 (left Pending as "partial by decision"), and Phase 47 Plan 01's: ticking a box for work that has not been measured records unmeasured work in a phase whose whole premise is that claims are measured. `REQUIREMENTS.md` is unchanged by this plan.

## Self-Check: PASSED

All five claimed artifacts exist on disk (`src/semolina/exceptions.py`, `src/semolina/dto.py`, `tests/unit/test_dto_duckdb.py`, the polars 2.0 todo, this SUMMARY). Both claimed commits resolve in `git log`: `5838a62`, `5e03d4c`.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*
