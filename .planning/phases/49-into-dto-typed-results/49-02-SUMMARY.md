---
phase: 49-into-dto-typed-results
plan: 02
subsystem: api
tags: [arrowmodel, pydantic, pyarrow, streaming, generators, dto, aliases, jsonvalue]

requires:
  - phase: 49-into-dto-typed-results
    plan: 01
    provides: "check_result_schema, resolve_column_key, _require, both error classes, SemolinaCursor.into, and the narrowed content fence this plan runs under"
  - phase: 47-type-fidelity-probe-decision-doc
    provides: "Decision 1's prohibition on touching the row value path, which the pre-check does not relax"
  - phase: 39-adbc-passthrough
    provides: "fetch_record_batch and its lifetime docstring, restated verbatim by iter_into"
provides:
  - "SemolinaCursor.iter_into(model, *, validate=False) — eager guards and pre-check, lazy production"
  - "SemolinaCursor._iter_into_impl — the generator function that owns all the laziness"
  - "tests/unit/test_dto.py: the counting fake reader, the fake cursor, and the full D-07…D-11 + PD-02 pre-check matrix"
  - "A measured non-vacuity proof for the D-05 fail-fast test"
affects: [49-06-async-twins, 49-07-docs, 50-codegen-dtos]

actuals:
  tokens: 12368
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Eager check, lazy production: a public method that must validate at the call runs its guards and returns a generator produced by a separate private generator function, and never contains `yield` itself"
    - "Non-vacuity by execution: a fail-fast test is only trusted after the deliberately-broken implementation has been observed failing it"
    - "Counting fakes over warehouses for claims about timing: laziness is a claim about how many batches were pulled, which no query can answer"

key-files:
  created:
    - tests/unit/test_dto.py
  modified:
    - src/semolina/cursor.py

key-decisions:
  - "D-04 confirmed at the Task 1 gate: the public streaming method is `iter_into`, verb-first like the cursor's `fetch_*` family. Now committed for cursor.py, Plan 06's async twin, Plan 07's docs and Phase 50's generated DTOs."
  - "`_iter_into_impl` catches StopIteration and returns rather than letting it escape: PEP 479 turns a StopIteration escaping a generator body into a RuntimeError, so the `__next__` loop's `raise` spelling could not be copied verbatim"
  - "The semolina.JsonValue RecursionError only reproduces from a real imported module — pydantic resolves a ForwardRef via sys.modules[cls.__module__], so a function-local class leaves the model deferred and raises nothing. The probe module is written to tmp_path, never to disk under tests/, because --doctest-modules would import it at collection."
  - "`datetime` must stay a runtime import in tests/unit/test_dto.py despite ruff TC003. Measured: under TYPE_CHECKING the annotation stays an unresolved ForwardRef, the pre-check gives no verdict, and every date/timestamp test silently stops testing."
  - "The union test is spelled `Union[int, None]`, not `Optional[int]`: the two ruff versions in play disagree on the rule code (UP007 pinned vs UP045 local), so either noqa spelling gets rewritten by the other and the class silently becomes a duplicate of its sibling"

patterns-established:
  - "A fail-fast test asserts on a call counter the code under test never reached, not merely on the absence of a result: `fetch_record_batch_calls == 0` distinguishes an eager pre-check from a lazy one that happens to fail on the first pull"
  - "Laziness is asserted on a counter incremented by a fake reader, never on a length or a type"

requirements-completed: []

coverage:
  - id: D1
    description: "`iter_into(BadDTO)` raises SemolinaSchemaMismatchError on the call expression, with no iteration and no reader created — and the test fails against a bare-generator implementation"
    requirement: DTO-03
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto.py#TestIterIntoFailFast::test_iter_into_is_not_a_generator_function"
        status: pass
      - kind: other
        ref: "non-vacuity proof by deliberate breakage — output recorded below"
        status: pass
    human_judgment: false
  - id: D2
    description: "Consuming one DTO pulls exactly one batch from the reader, measured on a counter"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestIterIntoLaziness::test_iter_into_lazy_first_item_pulls_exactly_one_batch"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto.py#TestIterIntoLaziness::test_iter_into_lazy_reader_is_untouched_until_the_first_next"
        status: pass
    human_judgment: false
  - id: D3
    description: "Zero-row batches mid-stream are skipped, an empty reader yields nothing, and a drained reader's OSError terminates iteration"
    requirement: DTO-02
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestIterIntoDelivery"
        status: pass
    human_judgment: false
  - id: D4
    description: "The pre-check's presence rule is FieldInfo.is_required(), so `str | None` with no default still errors while `str | None = None` converts"
    requirement: DTO-03
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestPresenceAndDefaults"
        status: pass
    human_judgment: false
  - id: D5
    description: "The confidence boundary holds on both sides: a struct, a list, an unmapped Arrow type, a non-DataType description entry and pydantic.JsonValue all produce no verdict, while decimal128 into float does"
    requirement: DTO-03
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestQuietCases"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto.py#TestTypeComparison::test_decimal_into_float_raises_on_both_validate_settings"
        status: pass
    human_judgment: false
  - id: D6
    description: "An Any-annotated DTO and a partially-typed DTO both convert; a genuinely non-annotated attribute raises PydanticUserError at class creation"
    requirement: DTO-04
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestUntypedModels"
        status: pass
    human_judgment: false
  - id: D7
    description: "A column literally named AGG(\"REVENUE\") resolves through Field(validation_alias=...) and through Field(alias=...); without one, the error lists the available columns"
    requirement: DTO-03
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestAliasResolution"
        status: pass
    human_judgment: false
  - id: D8
    description: "Two mismatched fields produce ONE error naming both (D-11)"
    requirement: DTO-03
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestReportShape::test_reports_every_mismatched_field_in_one_error"
        status: pass
      - kind: unit
        ref: "tests/unit/test_dto.py#TestReportShape::test_reports_every_kind_of_mismatch_together"
        status: pass
    human_judgment: false
  - id: D9
    description: "semolina.JsonValue cannot be a DTO annotation at all — RecursionError at class creation — while pydantic.JsonValue passes with no verdict"
    requirement: DTO-06
    verification:
      - kind: unit
        ref: "tests/unit/test_dto.py#TestJsonValueSpellings"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-08-14
status: complete
---

# Phase 49 Plan 02: `iter_into` Summary

**`iter_into` runs its guards and its schema pre-check on the call expression and then hands
back a generator — proven by breaking it on purpose and watching the test go red — and the
pre-check's full rule set is now pinned on both sides of the line between "confidently wrong"
and "no opinion".**

## Performance

- **Duration:** ~21 min (Task 1 checkpoint resolution excluded)
- **Started:** 2026-08-14T08:25 (first file read after the checkpoint was answered)
- **Completed:** 2026-08-14T08:45:40+01:00
- **Tasks:** 3 (1 checkpoint, 2 implementation)
- **Files modified:** 2 (1 created, 1 modified) — 1,169 inserted, 1 deleted
- **Tests added:** 52 (root suite 1350 → 1402)

## Task 1: the name gate, and what it decided

Answered **confirm**. Recorded here so Plans 06 and 07 and Phase 50 do not re-litigate it.

The public streaming method is **`iter_into`**, exactly as D-04 specifies. The gate existed
because the decision is rated one-way, not because the choice was open: the name lands in the
public API, in DTO-06's docs, and in the DTOs Phase 50 generates to be handed to it, so
renaming after release breaks user code and published examples.

`iter_into` is verb-first and consistent with the cursor's existing `fetch_arrow_table` /
`fetch_record_batch` / `fetchall_rows` family. `into_iter` would be the only method on either
cursor leading with a preposition; `stream_into` would add a third verb ("stream" alongside
"fetch" and "into") for one method. Both rejected on those grounds.

## The non-vacuity proof, as observed

This is the artifact the plan asked for by name, because the D-05 test is the one that is
easiest to write in a way that cannot fail. A test spelled
`pytest.raises(...): list(cursor.iter_into(BadDTO))` passes identically against the
implementation D-05 forbids.

`iter_into`'s body was temporarily replaced with a bare generator function — the guards, the
pre-check and the drive loop all moved into the public method, so it contained `yield` — and
`uv run pytest tests/unit/test_dto.py -k raises_at_call -q` was re-run. **Both** fail-fast
tests went red:

```
collected 52 items / 50 deselected / 2 selected

tests/unit/test_dto.py FF                                                [100%]

=================================== FAILURES ===================================
___ TestIterIntoFailFast.test_iter_into_with_a_mismatched_dto_raises_at_call ___

        cursor, inner = make_cursor(describe(SALES_SCHEMA), reader=None)

>       with pytest.raises(SemolinaSchemaMismatchError) as excinfo:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE SemolinaSchemaMismatchError

tests/unit/test_dto.py:295: Failed
____ TestIterIntoFailFast.test_iter_into_without_arrowmodel_raises_at_call _____

        with (
            patch("importlib.util.find_spec", side_effect=find_spec_without("arrowmodel")),
>           pytest.raises(SemolinaMissingDependencyError) as excinfo,
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        ):
E       Failed: DID NOT RAISE SemolinaMissingDependencyError

tests/unit/test_dto.py:322: Failed
=========================== short test summary info ============================
FAILED tests/unit/test_dto.py::TestIterIntoFailFast::test_iter_into_with_a_mismatched_dto_raises_at_call
FAILED tests/unit/test_dto.py::TestIterIntoFailFast::test_iter_into_without_arrowmodel_raises_at_call
======================= 2 failed, 50 deselected in 0.08s =======================
```

Worth noting what the failure mode *is*: not a wrong error, not a late error — **no error at
all**. The bare-generator `iter_into` returned a perfectly ordinary generator object and the
test simply never saw an exception. That is exactly what a user would experience: the call
that named the wrong type succeeds, and the traceback arrives from whatever `for` loop or
`list()` eventually consumed it, several frames away.

The break was reverted from a byte-for-byte copy taken before the edit; `git diff --stat`
after the revert showed the same 120 insertions / 1 deletion as before, all 52 tests pass, and
the AST guard is green:

```
uv run python -c "import ast,inspect,semolina.cursor as c; ..."   # -> AST OK
```

## Accomplishments

- **DTO-02's sync half, measured rather than asserted.** `CountingReader.batches_read` is
  incremented inside `read_next_batch`, and the laziness test takes exactly one item and
  asserts the counter reads 1 against a two-batch reader. A length assertion would have passed
  against an implementation that read everything up front, which is the claim being made.
- **D-05 is structural, not incidental.** `iter_into` contains no `yield`; `_iter_into_impl`
  does. Two tests and one AST check pin that: `inspect.isgeneratorfunction` is asserted False
  for the public method and True for the private one, and the acceptance-criteria AST walk
  finds no `Yield`/`YieldFrom` node in `iter_into`'s source.
- **The `__next__` loop's two hard-won behaviours were carried over rather than re-derived.** A
  zero-row batch mid-stream is skipped (tested with a `[2, 0, 2]` reader yielding 4 DTOs), and
  a drained reader raising `OSError` instead of `StopIteration` terminates iteration rather
  than propagating.
- **The pre-check's silence is now as well tested as its noise.** Five quiet cases — struct,
  list, unmapped interval, a `description` entry carrying a DBAPI type code instead of a
  `pyarrow.DataType`, and an `AliasChoices` validation alias — all assert `is None`, alongside
  `pydantic.JsonValue`. Every one of those is a call site that would start raising if the
  boundary moved.
- **The Snowflake alias trap is pinned**, so Plan 07's worked example cannot quietly be
  DuckDB-only: a column literally named `AGG("REVENUE")` resolves through both
  `validation_alias=` and `alias=`, and a bare `revenue` field errors with a message that
  lists the available columns.

## Task Commits

1. **Task 1: name confirmation checkpoint** — no commit (decision gate; answered `confirm`)
2. **Task 2: `iter_into` — check at the call, produce lazily** — `627da42` (feat)
3. **Task 3: the pre-check's full rule set** — `76da1e3` (test)

## Files Created/Modified

- `src/semolina/cursor.py` — `iter_into` (public, no `yield`) and `_iter_into_impl` (private
  generator function); `Iterator` added to the `TYPE_CHECKING` imports. The
  `batch.to_pylist()` → `Row(...)` value path is byte-unchanged.
- `tests/unit/test_dto.py` (new, 1,049 lines) — `CountingReader`, `FakeCursor`, `make_cursor`,
  `describe`, `columns`, `batch`, `find_spec_without`, and 52 tests across 13 classes.

## `src/semolina/dto.py`: no change, and why that is the honest answer

The plan expected Task 3's matrix to expose defects in what Plan 01 shipped, and asked for
each to be named alongside the test that caught it. **The matrix exposed none.** All 52 tests
passed against `dto.py` as Plan 01 left it, on the first run of every case except the two
recorded under Deviations — and both of those were defects in my own test code, not in the
module under test.

That is a claim worth being suspicious of, so here is what makes it credible rather than
convenient: the matrix is not a restatement of the implementation. It asserts the *failing*
side of every rule as well as the passing side (`decimal128` into `float` raises,
`int64` into `float` raises, `date32` into `datetime` raises, a union with no accepting arm
raises, a bare `revenue` against `AGG("REVENUE")` raises), and four of those raise-cases
exercise code paths Plan 01's DuckDB tests never reached because DuckDB cannot produce the
schema. The rules held because Plan 01 wrote them off the same measured research this plan
tested against.

Two places where `dto.py` is *right for a reason the tests now record*, rather than merely
untested:

- **Two structures, not one** (Plan 01's decision 3). `test_a_description_entry_without_an_arrow_type_produces_no_verdict` is the case that would fail if column names and column types were sourced from the same filtered dict: the field would be reported *missing* rather than left un-judged.
- **`typing.Any`'s explicit branch.** Now covered on the streaming path too, via `test_an_all_any_model_streams_through_iter_into`.

## Findings

### 1. The `semolina.JsonValue` RecursionError does not reproduce from a function-local class

The first version of `test_semolina_jsonvalue_cannot_be_a_dto_annotation_at_all` declared the
DTO inside the test body and **failed: `DID NOT RAISE RecursionError`**. That is not a
contradiction of RESEARCH.md — it is a condition RESEARCH.md's reproduction carried implicitly
("module-level alias in a separate module, imported").

pydantic resolves a `ForwardRef` against `sys.modules[cls.__module__].__dict__`. A class
defined in a local scope leaves the model deferred and unbuilt, so the self-referential string
alias is never expanded and nothing recurses. Measured across three shapes:

| Shape | Result |
|---|---|
| `class M(BaseModel): payload: JsonValue` inside a test function | no raise — model deferred |
| `pydantic.create_model("M", payload=(semolina.JsonValue, ...))` | no raise — annotation stays a `ForwardRef` |
| a real module doing `from semolina import JsonValue` then declaring the class | **`RecursionError` at import** |

So the test writes the probe module to `tmp_path` and imports it. It deliberately does **not**
live on disk under `tests/`: root pytest runs with `--doctest-modules` over
`testpaths = ["tests", "src"]`, which imports every `.py` in the tree at collection time and
would take the entire suite down with a `RecursionError` before a single test ran.

**Consequence for Plan 07.** The DTO-06 docs claim is now backed by the suite, but the claim
must be stated precisely: `semolina.JsonValue` in a DTO fails at *class creation*, not at
conversion, and only once the annotation actually resolves. A user who hits it sees a pydantic
`_generate_schema.py` traceback with no Semolina frames.

### 2. On Python 3.14, `typing.Union` **is** `types.UnionType`

Measured this session:

| Spelling | `get_origin(...)` | `is typing.Union` | `is types.UnionType` |
|---|---|---|---|
| `Optional[int]` | `<class 'typing.Union'>` | True | **True** |
| `Union[int, None]` | `<class 'typing.Union'>` | True | **True** |
| `int \| None` | `<class 'typing.Union'>` | True | **True** |

PEP 604's unification has collapsed the two origins on 3.14. RESEARCH.md's table was measured
on **3.11.1**, where they are genuinely distinct, and both interpreters are in the CI matrix.
`dto.py`'s two-branch test (`origin is types.UnionType or origin is typing.Union`) is therefore
a tautology on 3.14 and load-bearing on 3.11 — correct as written, but it should not be
"simplified" by anyone reading it on a 3.14 venv. The test docstring says so.

### 3. Two lint traps that would have made tests silently vacuous

Both are recorded because in each case the tool's fix is *wrong* and the passing suite would
not have said so.

- **`# noqa: TC003` on `import datetime`.** ruff wants it in a `TYPE_CHECKING` block because it
  appears only in annotations. Measured consequence: with `datetime` unavailable at runtime,
  `M.model_fields["occurred"].annotation` is `ForwardRef('datetime.date')`, which the
  pre-check cannot reduce, so it gives no verdict — and
  `test_date_column_into_a_datetime_field_raises` would stop testing while still passing.
- **The union test is spelled `Union[int, None]`, not `Optional[int]`.** The ruff pinned in
  `.pre-commit-config.yaml` (v0.9.6) calls that rewrite **UP007**; the newer ruff in the venv
  calls it **UP045**. A `noqa` naming either code is honoured by one and ignored by the other,
  which rewrote `Optional[int]` to `int | None` and made the class an exact duplicate of its
  sibling — twice, before the cause was found. `Union[int, None]` is the same object
  (`==` holds, same `get_origin` on both interpreters) and is UP007 in both versions.

### 4. `StopIteration` could not be copied verbatim from `__next__`

`SemolinaCursor.__next__` handles a drained reader with `raise` / `raise StopIteration from exc`.
`_iter_into_impl` is a generator, and PEP 479 turns a `StopIteration` escaping a generator body
into a `RuntimeError`, so the same spelling would have converted a normal end-of-stream into a
crash. Both drain paths `return` instead. Covered by
`test_iter_into_over_an_empty_reader_yields_nothing` and
`test_iter_into_treats_a_drained_reader_oserror_as_termination`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] My `semolina.JsonValue` test asserted a raise that the shape I wrote cannot produce**

- **Found during:** Task 3 (first run of the module: 51 passed, 1 failed)
- **Issue:** `DID NOT RAISE RecursionError` — the DTO was declared inside the test function, so
  pydantic deferred the model and never expanded the alias. The test would have been a false
  negative for the docs claim it exists to back.
- **Fix:** Rewrote it to write a real module to `tmp_path`, `monkeypatch.syspath_prepend`, and
  import it. Three shapes were measured before choosing (table above), so the choice is
  recorded rather than guessed. Also removed the `# type: ignore[valid-type]` the original
  spelling needed, which CLAUDE.md discourages.
- **Files modified:** `tests/unit/test_dto.py`
- **Committed in:** `76da1e3`

**2. [Rule 1 — Bug] Two lint outcomes silently degraded my own tests**

- **Found during:** Task 3 (`prek run --all-files`)
- **Issue:** (a) ruff rewrote `Optional[int]` to `int | None` despite a `# noqa: UP045`, making
  the two-spelling union test a duplicate that proves nothing — caused by the rule-code split
  between the pinned and local ruff versions. (b) basedpyright reported
  `Class "M" is not accessed` for the deliberately-illegal class inside
  `pytest.raises(PydanticUserError)`, which never binds its name because its creation raises.
- **Fix:** (a) spelled the annotation `Union[int, None]` with `# noqa: UP007`, which both ruff
  versions honour, and recorded why in the test docstring. (b) moved the illegal class into a
  small `declare_it()` helper that returns it, so the reference is real and no suppression is
  needed.
- **Files modified:** `tests/unit/test_dto.py`
- **Verification:** `prek run --all-files` all hooks passed; `grep` confirms the
  `Union[int, None]` spelling survives a full hook run.
- **Committed in:** `76da1e3`

---

**Total deviations:** 2 auto-fixed, both bugs in newly-written test code. **No source
behaviour changed as a deviation**, and no plan instruction was departed from.

## Prohibitions: held

- **The row value path is untouched.** `src/semolina/cursor.py`'s `batch.to_pylist()` feeding
  `Row(...)` is byte-unchanged, and no `float()` / `int()` / `Decimal()` conversion was added
  anywhere. Enforced by execution, not inspection: `tests/unit/test_scope_fence.py` reports
  **2 passed, neither skipped**.
- **No row value reaches an error message.** The pre-check fetches nothing — it reads
  `cursor.description` only, so it has no values to leak by construction. Every assertion in
  the report-shape tests is on a field name, a column key, an Arrow type name or a Python type
  name.
- **`pydantic.JsonValue` used throughout**; `semolina.JsonValue` appears only inside the one
  test that asserts it cannot be used.

## Issues Encountered

- **`prek` uses the ruff pinned in `.pre-commit-config.yaml` (v0.9.6), not the venv's ruff.**
  The two disagree on rule codes for PEP 604 rewrites. Worth knowing before writing any future
  `# noqa` for the `UP` family: verify it against `prek`, not against `uv run ruff`.
- **`TMPDIR` differs between sandboxed and unsandboxed Bash invocations** on this machine, so a
  file written to `$TMPDIR` in one mode is not found in the other. Cost one confused `diff`;
  no impact on the work.

## Verification Results

| Gate | Result |
|---|---|
| `uv run pytest tests/unit/test_dto.py -x -q` | **52 passed** |
| `uv run pytest tests/unit/test_dto.py -k raises_at_call -x` | 2 passed |
| non-vacuity: same command against a bare-generator `iter_into` | **2 failed** (output above) |
| `uv run pytest tests/unit/test_dto.py -k lazy -x` | 2 passed (assertion on `reader.batches_read`) |
| `uv run pytest tests/unit/test_dto.py -k reports_every -x` | 2 passed |
| `uv run pytest tests/unit/test_dto.py -k decimal_into_float -x` | 2 passed (both `validate` settings) |
| `uv run pytest tests/unit/test_dto.py -k default -x` | 4 passed (incl. `str \| None` with no default) |
| `uv run pytest tests/unit/test_dto.py -k alias -x` | 5 passed (against `AGG("REVENUE")`) |
| `uv run pytest tests/unit/test_dto.py -k untyped -x` | 5 passed (incl. `PydanticUserError`) |
| AST guard: no `Yield`/`YieldFrom` in `iter_into` | `OK` |
| `uv run pytest tests/unit/test_scope_fence.py -x` | 2 passed, **neither skipped** |
| `just test` | root **1402 passed**, 16 skipped, 2 xfailed; jaffle-shop 16 passed, 15 skipped |
| `prek run --all-files` | all hooks passed, incl. basedpyright strict, **no `# type: ignore` in the diff** |

The root suite was 1350 passed before this plan and is 1402 after: +52, and nothing that was
green went red.

## Known Stubs

None. `iter_into` is fully implemented and exercised. The async twin (`AsyncSemolinaCursor`)
does not exist yet and is Plan 06's — not stubbed, simply not in this plan.

## Next Phase Readiness

Ready.

- **Plan 06 (async twins).** `iter_into`'s shape is the one to mirror: a **plain `def`** that
  runs the guards and the pre-check and returns an async iterator, not an `async def` and not a
  bare async generator. `AsyncSemolinaCursor.description` is already a synchronous property
  (PD-04), which is what makes that possible with no `await` before the check. Note that the
  async reader's drain signal is `StopAsyncIteration`, not `StopIteration`/`OSError`, so the
  drive loop's `except` clauses do not transfer verbatim — and PEP 479's async analogue applies
  equally. The plan's own non-vacuity requirement should be repeated there: an `async def`
  containing `yield` defers its body exactly as a sync generator does.
- **Plan 07 (docs).** Three claims are now backed by tests and can be written without hedging:
  `semolina.JsonValue` fails at *class creation* (not conversion) and only from an importable
  module; `int` into `float` raises (PD-02) and reads as pedantic, which is a docs problem to
  solve with words rather than a rule to relax; and the worked example needs
  `Field(validation_alias='AGG("REVENUE")')` to survive leaving DuckDB.
- **Phase 50 (generated DTOs).** The method the generated DTOs are handed to is named
  `iter_into`, confirmed at a one-way gate.

## Self-Check: PASSED

- `src/semolina/cursor.py` — exists; `SemolinaCursor.iter_into` and
  `SemolinaCursor._iter_into_impl` both resolve by import.
- `tests/unit/test_dto.py` — exists, 1,049 lines, 52 tests collected.
- `.planning/phases/49-into-dto-typed-results/49-02-SUMMARY.md` — this file.
- Both claimed commits resolve in `git log`: `627da42`, `76da1e3`.
- Working tree clean before this SUMMARY was written.

---
*Phase: 49-into-dto-typed-results*
*Completed: 2026-08-14*
