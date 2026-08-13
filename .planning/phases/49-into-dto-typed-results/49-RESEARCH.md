# Phase 49: `.into(DTO)` Typed Results - Research

**Researched:** 2026-08-13
**Domain:** Arrow → Pydantic v2 conversion (arrowmodel), optional-dependency packaging, dataframe passthrough
**Confidence:** HIGH — every load-bearing API claim below was executed in a scratch venv or read from installed source this session. Line-and-quote citations throughout.

## Summary

Phase 49 has a smaller unknown surface than it looks, because arrowmodel's actual behaviour
matches CONTEXT.md's decisions almost exactly — and I confirmed that by running it rather than
reading about it. `MyDTO.convert(batch)` is a classmethod taking `pa.RecordBatch | pa.Table`
with a keyword-only `validate: bool = False`, returning `list[Self]`; it raises
`ValueError: Arrow schema is missing required columns: [...]` for a declared field with no
matching column, and honours a field default by filling it silently. D-08 is therefore
**confirmed, not merely relocated**: arrowmodel already draws the line exactly where D-08
draws it, and Semolina's pre-check running first only improves the message (all fields at
once, D-11) rather than changing the verdict.

The bigger finding is about the *other* half of DTO-03. The fast path is silently wrong on a
type mismatch — arrowmodel's own docs say so and I reproduced it. But **`validate=True` does
not rescue the case this project cares most about**: a `decimal128` column landing in a
`float`-annotated field is silently coerced to `1.5` by the validated path, losing precision
with no error. The structural pre-check (D-06/D-10) is therefore the *only* mechanism in the
phase that catches Semolina's headline Decimal case, on either path. Plan it as load-bearing,
not as a nicety.

Three things in CONTEXT.md need correcting before planning. (1) `fetch_polars()` does **not**
need pyarrow — ADBC hands the PyCapsule stream straight to `polars.from_arrow`, so D-15's
list of four pyarrow-guarded methods over-guards one of them. (2) CI syncs
`uv sync --locked --dev --extra all`, not `--all-groups`; polars still lands, but the stated
command is wrong. (3) The `find_spec`-monkeypatch precedent is `ruff_available()` in
`python_renderer.py`, not Phase 47 — and CI already has a *real* clean-venv assertion in the
`packaging-smoke` job that is a strictly better test for DTO-05 than any monkeypatch.

**Primary recommendation:** Build the pre-check as a new `src/semolina/dto.py` module that
resolves the Arrow schema to *runtime type objects* through a new sibling of
`arrow_type_to_python` (the existing one returns annotation **strings** and is unusable here),
matches columns on arrowmodel's own key rule (`validation_alias > alias > field_name`), and
skips any annotation shape it cannot reduce to a class or a union of classes. Guard pyarrow /
pandas / polars / arrowmodel with `importlib.util.find_spec`, following `ruff_available()`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** arrowmodel's **fast path is the default**. `.into(DTO)` converts via
  `model_construct` with no per-value validation. `.into(DTO, validate=True)` passes the
  keyword straight through to arrowmodel's own `convert(validate=)`, which serialises each
  row to JSON in Rust and runs `model_validate_json` (2–5x slower, raises pydantic
  `ValidationError` naming the field, stops at the first failing row).
  — **Reversibility:** costly — the default is a published behavioural contract.
- **D-02:** `.into()` lives on **`SemolinaCursor` and `AsyncSemolinaCursor` only**. No
  `Query.into()` terminal. — **Reversibility:** reversible.
- **D-03:** The streaming form **converts a whole batch at a time** but **yields DTO instances
  individually**, mirroring `for row in cursor`. Explicitly NOT `list[DTO]`-per-batch.
- **D-04:** It is called **`iter_into(DTO)`**. `.into()` keeps its roadmap-given name for the
  eager form. — **Reversibility:** one-way.
- **D-05:** `iter_into()` **raises at the call, not on first iteration**. A regular method that
  runs the pre-check and then returns a generator — NOT a generator function. Same on the
  async cursor, where it stays a plain method returning an async iterator.
- **D-06:** The pre-check **runs always**, on both `.into()` and `iter_into()`, and needs
  **no probe and no round trip**. It reads the Arrow schema already in memory.
- **D-07:** Result columns the DTO does not declare are **ignored**.
- **D-08:** A DTO field with **no matching result column is an error, unless the field has a
  default** (including `= None`).
- **D-09:** **Nullability is not checked at all.**
- **D-10:** Type comparison is **subtype-tolerant**: it passes when the DTO's annotation can
  legally hold the Python type `arrow_type_to_python` derives from the Arrow type. `Any` and
  `object` are a deliberate opt-out; `decimal.Decimal` arriving where the DTO declared `float`
  stays a hard failure. The check has **no values to `isinstance` against**.
- **D-11:** The error **reports every mismatched field at once**.
- **D-12:** **Four extras**, one install idiom: `[pyarrow]`, `[pandas]`, `[polars]`,
  `[arrowmodel]`. — **Reversibility:** costly — published extras are an install contract.
- **D-13:** **`[all]` means all** — it gains all four new extras, so polars lands in the test
  environment, which is what makes D-16 possible.
- **D-14:** **Two new flat exceptions** in a NEW `src/semolina/exceptions.py`, exported from
  the package root: `SemolinaMissingDependencyError(RuntimeError)` and
  `SemolinaSchemaMismatchError(RuntimeError)`. Existing errors in `engines/base.py` untouched;
  no `SemolinaError` base class.
- **D-15:** **pyarrow gets the same guard**, and this is in scope. Guarded methods:
  `fetch_arrow_table`, `fetch_record_batch`, `fetch_df`, `fetch_polars`, on **both** cursors.
  `[duckdb]`'s existing `pyarrow>=17.0.0` pin can reference the new extra.
- **D-16:** **Assumption A3 (polars Decimal support) gets measured and closed in this phase.**
  Put the real row in `47-TYPE-FIDELITY.md`; `_measure_polars()` must actually measure.
- **D-17:** Closing A3 makes a sentence in `47-DECISIONS.md` stale. Handle it with a **dated
  in-body correction** beneath the original text — not a rewrite, and not silence.

### Claude's Discretion

- **D-05's fail-fast timing** (recorded because the implementation consequence is non-obvious —
  `iter_into` must not be written as a bare generator function).
- **D-11's report-all-at-once.**
- **Detection mechanism** for missing packages. Precedent: `importlib.util.find_spec`, so the
  package is never imported.
- **DTO-06's docs shape** — how-to vs tutorial, and the scenario. Follow
  `.claude/skills/semolina-docs-author/SKILL.md`; the Diataxis classification decides it.
- **arrowmodel version floor** — not installed, absent from `pyproject.toml`; pick a floor.

### Deferred Ideas (OUT OF SCOPE)

- **`Query.into(DTO)` eager terminal** — rejected for this phase (D-02).
- **`list[DTO]`-per-batch streaming (`into_batches`)** — rejected (D-03).
- **`SemolinaError` common base class** — rejected (D-14).
- **Making `pyarrow` a base dependency** — rejected in favour of the guard (D-15).
- **STREAM-04, user-controllable batch size** — deferred to a later milestone.
- **`cursor.into(DTO, check=False)` escape hatch** — raised, not pursued.
- **`2026-02-25-runtime-type-coercion-validation-on-row-construction.md`** — reviewed and
  deliberately NOT folded. Nobody may read this phase's `.into()` validation as licence to
  revisit `Row`-construction coercion.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DTO-01 | `.into(MyDTO)` → Pydantic v2 instances, matched by column name | §Q4 (measured `convert()` signature/return), §Code Examples 1 |
| DTO-02 | Stream DTOs per batch, sync and `async for`, without materialising | §Q5 (free `.schema` on both readers), §Code Examples 3–4, measured per-batch `iter()` over a live ADBC reader |
| DTO-03 | Mismatched DTO → clear error naming the field, not a silent wrong value | §Q1/§Q4 (fast path measured silently wrong; **`validate=True` also silently coerces Decimal→float**), §Q7 (the pre-check design) |
| DTO-04 | Works against untyped / partially-typed models | §Q7 (`Any` measured working; a pydantic field cannot be un-annotated at all) |
| DTO-05 | `semolina[arrowmodel]` extra; default install pulls neither arrowmodel nor its Rust extension | §Q3 (floor), §Standard Stack, §Validation (CI `packaging-smoke` clean-venv assertion) |
| DTO-06 | Docs present `.into(DTO)` as primary typed-result path, worked BI-backend example | §Architecture Patterns, §Common Pitfalls (Snowflake alias trap belongs in the example) |
| RESULT-01 | `fetch_df()` / `fetch_polars()` on both cursors | §Don't Hand-Roll (four passthrough methods), §Q2 |
| RESULT-02 | Actionable error naming the missing package | §Q2 (measured native errors on both layers), §Code Examples 5 |

## Project Constraints (from CLAUDE.md)

Binding on every plan in this phase.

- **Quality gates before commit:** `prek run --all-files` (ruff lint+format, basedpyright
  strict, shellcheck), `just test` (**two** suites — root `pytest`, then
  `semolina-jaffle-shop`), `just docs-build` (`sphinx-build -W`, strict).
  [VERIFIED: justfile:18-20, 22-24, 27-28]
- **No `# type: ignore` in code.** Solve the typing issue; pyproject-level exemptions are the
  last resort. This bites in Phase 49: arrowmodel is an optional dependency with no stub
  problem, but `pandas` / `polars` return types must be quoted under `TYPE_CHECKING`.
- **Docs work MUST load** `@.claude/skills/semolina-docs-author/SKILL.md`, and any PLAN.md with
  a documentation task must put that line in its `<execution_context>` block.
- **Bug-fix protocol:** reproduce with a failing test first, then fix; failing test commits
  before the fix commit.
- **Style:** 100-char lines; multi-line docstrings with `"""` on their own lines; D213 (summary
  on the second line); ruff isort; `Example:` sections use a `.. code-block:: python` RST
  directive, never markdown fences.
- **Docs types:** how-to guides carry illustrative snippets and use sphinx-design
  `tab-set` with `:sync-group: warehouse` for dialect examples; tutorials carry runnable code
  with expected output.

## Phase Research Questions — Answers

Every answer below was produced by executing code this session unless marked otherwise. The
scratch venv used Python 3.11.1, arrowmodel 1.0.0, pydantic 2.13.4, pyarrow 25.0.1,
polars 1.43.2, adbc-driver-manager 1.12.0, adbc-poolhouse 1.6.2, duckdb 1.5.5. The project
venv (`.venv`) is Python 3.14.2, pyarrow 24.0.0, pandas 2.3.3, pydantic 2.12.5,
adbc-poolhouse 1.6.2, adbc-driver-manager 1.10.0, duckdb 1.5.5, **no polars, no arrowmodel**.

### Q1 — Does arrowmodel tolerate a declared field with no matching Arrow column? **D-08 CONFIRMED.**

**Answer: it raises, and it raises on exactly D-08's line.** A required field with no matching
column is a `ValueError`; a field with a default (including `= None`) is filled from the
default and no error occurs.

Executed against a 2-column `RecordBatch` (`id: int64`, `name: string`):

| Model field | Result |
|---|---|
| `missing: str` (required) | `ValueError: Arrow schema is missing required columns: ['missing']. Available columns: ['id', 'name']` |
| `missing: str = "dflt"` | OK — `M2(id=1, name='a', missing='dflt')` |
| `missing: str \| None = None` | OK — `M3(id=1, name='a', missing=None)` |
| `missing: str \| None` (no default → still required) | same `ValueError` |
| required-missing with `validate=True` | same `ValueError` (raised before the validated path runs) |

[VERIFIED: executed, arrowmodel 1.0.0]. Corroborated by the published reference:
"Optional fields with defaults are silently skipped when absent. Extra Arrow columns not
present in the model are silently ignored." [CITED: anentropic.github.io/arrowmodel/reference/api.html]

**Consequence for planning.** D-08 does not relocate a failure; it *anticipates* arrowmodel's
own rule. Semolina's pre-check running first (D-06) is therefore purely an improvement — it
can report every missing field at once (D-11) alongside every type mismatch, where arrowmodel
reports only the missing-column set and nothing about types. Note the "required" test is
`FieldInfo.is_required()`, not "has `= None`": `str | None` **without** a default is required
and correctly errors [VERIFIED: executed].

Two related timings the planner must know:

- `ArrowModelConverter(Model)` construction does **not** raise for a missing column; only
  `convert()`/`iter()` do, because column indices are resolved per-batch schema.
  [VERIFIED: executed; corroborated by the class docstring "Per SCHEMA-03: ValueError raised
  at convert() for missing required fields"]
- `Model.iter(batch)` **is a generator function** — it returns without raising and the
  `ValueError` surfaces on the first `next()`. [VERIFIED: executed]. This is the concrete
  reason D-05 exists: Semolina's `iter_into` must run its own pre-check eagerly and must not
  inherit arrowmodel's lazy timing.

### Q2 — How do you test "package not installed" when CI installs everything?

**Two mechanisms, not one. Use both.**

**(a) The real one — a clean venv in CI, which already exists.** `.github/workflows/ci.yml`
has a `packaging-smoke` job that builds an extras-free venv and asserts absence directly:

```yaml
      - name: Install base (no extras) in clean venv
        run: |
          uv venv /tmp/base-venv
          uv pip install --python /tmp/base-venv/bin/python "."

      - name: Base install pulls no anyio (ASYNC-04)
        run: |
          /tmp/base-venv/bin/python -c "import semolina, importlib.util; assert importlib.util.find_spec('anyio') is None, 'anyio present in a base install'; print('OK')"
```
[VERIFIED: .github/workflows/ci.yml:149, 173-180 — quoted verbatim]

This is the correct home for **DTO-05**, which is a claim about what a *default install* pulls.
Extend the same job with `arrowmodel`, and (for D-12's honesty) with `pandas` / `polars`.
No monkeypatch can prove DTO-05; a clean venv can.

**(b) The unit-test one — patch `importlib.util.find_spec`.** The precedent is **not** Phase 47
(`tests/type_fidelity_probe.py:1586` uses `find_spec` but is never monkeypatched). It is
`ruff_available()`:

```python
def ruff_available() -> bool:
    return importlib.util.find_spec("ruff") is not None
```
[VERIFIED: src/semolina/codegen/python_renderer.py:429-440 — body quoted verbatim from :440]

and its tests:

```python
    def test_true_when_installed(self) -> None:
        with patch("importlib.util.find_spec", return_value=object()):
            assert ruff_available() is True

    def test_false_when_not_installed(self) -> None:
        with patch("importlib.util.find_spec", return_value=None):
            assert ruff_available() is False
```
[VERIFIED: tests/unit/codegen/test_python_renderer.py:1081-1093 — quoted verbatim]

There is a second, sharper variant in the same repo — patching the *helper* rather than
`find_spec`, which is what you want for the error-message tests because it does not disturb
unrelated `find_spec` calls in the same process:

```python
        with (
            patch.object(python_renderer, "ruff_available", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
```
[VERIFIED: tests/unit/codegen/test_python_renderer.py:1069-1072 — quoted verbatim]

**Copyable pattern for Phase 49.** Put one module-private helper per package in
`src/semolina/exceptions.py` (or a small `_optional.py`), e.g.

```python
def _require(package: str, extra: str) -> None:
    if importlib.util.find_spec(package) is None:
        raise SemolinaMissingDependencyError(
            f"{package} is not installed. Install it with: pip install semolina[{extra}]"
        )
```

then test the raising path with `patch("importlib.util.find_spec", return_value=None)` and
the passing path with `return_value=object()`. Because `find_spec` is called by name inside
the helper, `patch("importlib.util.find_spec", ...)` reaches it — confirmed by the existing
tests above passing today.

**What the native failures actually look like today**, measured so the planner can assert the
*replacement* message is genuinely better:

| Layer | Call | Missing package | Observed |
|---|---|---|---|
| sync ADBC | `cursor.fetch_polars()` | polars | `ModuleNotFoundError: No module named 'polars'`, raised at `dbapi.py:1431` (`import polars`), 10-frame traceback |
| async poolhouse | `await cursor.fetch_polars()` | polars | `ModuleNotFoundError: No module named 'polars'` — crosses the offload unchanged |
| sync ADBC | `cursor.fetch_arrow_table()` etc. | pyarrow | `ProgrammingError("This API requires PyArrow to be installed")` |
| sync ADBC | `cursor.description` | pyarrow **and** polars | `ProgrammingError("This API requires PyArrow or another suitable backend to be installed")` |

[VERIFIED: executed against a live in-memory DuckDB through the project venv, which has no
polars; and `_requires_pyarrow` read at .venv/…/adbc_driver_manager/dbapi.py:1479-1484 and
`_NoOpBackend.convert_description` at _dbapi_backend.py:147-151]

### Q3 — arrowmodel version floor

**Recommendation: `arrowmodel>=1.0.0` (pin the only released version as the floor; do not cap).**

| Fact | Value | Source |
|---|---|---|
| Releases on PyPI | **1.0.0 only**, uploaded 2026-07-07T14:26:25 | [VERIFIED: pypi.org/pypi/arrowmodel/json] |
| `requires_python` | `>=3.11` | [VERIFIED: same] |
| `requires_dist` | `['pydantic>=2.13.4']` — **no pyarrow dependency** | [VERIFIED: same] |
| Wheels | `cp311-abi3` for macosx x86_64 + arm64, manylinux_2_17 x86_64 + aarch64, win_amd64, plus sdist | [VERIFIED: same] |
| `validate=` keyword | present in 1.0.0 (the only release) — so there is no "which version introduced it" question to answer | [VERIFIED: executed `inspect.signature`] |

**Two consequences the planner must not miss.**

1. **`arrowmodel>=1.0.0` drags `pydantic>=2.13.4`, and the project currently resolves 2.12.5.**
   pydantic arrives unconditionally via `semolina → adbc-poolhouse → pydantic-settings →
   pydantic`; `.venv` has 2.12.5 today [VERIFIED: `importlib.metadata.version` in `.venv`], and
   2.13.4 is the current PyPI release [VERIFIED: pypi.org/pypi/pydantic/json]. Adding
   `[arrowmodel]` to `[all]` therefore **bumps pydantic in CI**, which changes a committed
   artifact cell: `47-TYPE-FIDELITY.md` reads
   `| pydantic | pydantic 2.12.5: \`decimal.Decimal\` field accepted unchanged | measured | A1 |`
   [VERIFIED: 47-TYPE-FIDELITY.md §"Downstream Decimal behaviour"]. Since D-16 regenerates that
   artifact anyway, the pydantic row and the polars row move in the same commit — plan them as
   one task, and expect `just type-fidelity` to be a required step, not an optional one.
2. **abi3 covers the CI matrix.** CI tests 3.11 and 3.14 on ubuntu-latest
   [VERIFIED: .github/workflows/ci.yml:82-84]; the `cp311-abi3 … manylinux_2_17_x86_64` wheel
   serves both, so no source build and no Rust toolchain in CI.

No upper cap: 1.0.0 is the first stable release from the same author as this project, and a
`<2` cap would have to be justified by a known break that does not exist yet.

### Q4 — The exact arrowmodel call surface

Read off the installed package with `inspect.signature`, not from docs.

```text
ArrowModel.convert  (data: 'pa.RecordBatch | pa.Table', *, validate: 'bool' = False) -> 'list[Self]'
ArrowModel.iter     (data: 'pa.RecordBatch | pa.Table', *, validate: 'bool' = False) -> 'Iterator[Self]'
model_convert       (model_class: 'type[BaseModel]', data: 'pa.RecordBatch | pa.Table', *, validate: 'bool' = False) -> 'list[BaseModel]'
model_iter          (model_class: 'type[BaseModel]', data: 'pa.RecordBatch | pa.Table', *, validate: 'bool' = False) -> 'Iterator[BaseModel]'
ArrowModelConverter.__init__ (self, model_class: 'type[BaseModel]', *, validate: 'bool' = False) -> 'None'
ArrowModelConverter.convert  (data: 'pa.RecordBatch | pa.Table') -> 'list[BaseModel]'
ArrowModelConverter.iter     (data: 'pa.RecordBatch | pa.Table') -> 'Iterator[BaseModel]'
```
[VERIFIED: executed `inspect.signature` against arrowmodel 1.0.0 — output quoted verbatim]

Public names in `arrowmodel`: `ArrowModel`, `ArrowModelConverter`, `model_convert`,
`model_iter`, plus re-exported `AliasChoices` / `AliasPath` / `BaseModel`.
`ArrowModel.__mro__` is `(ArrowModel, pydantic.main.BaseModel, object)`. [VERIFIED: executed]

Answers to the specific sub-questions:

- **Classmethod?** Yes — `ArrowModel.convert` is bound as a `method` on the class.
- **Keyword spelling and default?** `validate`, keyword-only, default `False`. Note the
  asymmetry: `ArrowModelConverter.convert()` has **no** `validate=` kwarg — validate is set on
  the *constructor*. If `iter_into` reuses one converter across batches (recommended, see
  below), it must pass `ArrowModelConverter(DTO, validate=validate)`.
- **Return?** `convert()` → a real `list`. `iter()` → a **generator** (`inspect.isgenerator`
  True). [VERIFIED: executed]
- **Accepted inputs?** `pyarrow.RecordBatch` ✅, `pyarrow.Table` ✅ (multi-batch Table works —
  a 2-batch Table yielded 4 rows), zero-row batch → `[]` ✅.
  **`pyarrow.RecordBatchReader` is REJECTED** — `ValueError: Expected an object with dunder
  __arrow_c_array__` [VERIFIED: executed]. **A polars DataFrame is also rejected at 1.0.0**,
  despite the landing page's "any Arrow-PyCapsule-compatible input" claim:
  `AttributeError: 'Schema' object has no attribute 'get_field_index'` [VERIFIED: executed].
  So Semolina must feed pyarrow objects and must iterate the reader itself — which is exactly
  what D-03 specifies.
- **Non-`ArrowModel` pydantic models?** `model_convert(PlainBaseModel, batch)` works
  [VERIFIED: executed]. `.into()` can therefore accept **any** `type[BaseModel]`, not only
  `ArrowModel` subclasses — a real API-surface choice for the planner (see Open Question 1).
- **Column-matching key?** `validation_alias > alias > field_name`, per the
  `ArrowModelConverter` docstring ("Per ALIAS-01"), and executed against a committed Snowflake
  cassette whose column is literally `AGG("REVENUE")`: `Field(validation_alias='AGG("REVENUE")')`
  and `Field(alias='AGG("REVENUE")')` both resolve; a wrong alias produces the same missing-column
  `ValueError` naming the *alias*. [VERIFIED: executed]

**The finding that changes DTO-03's design.** arrowmodel's own docs state the fast path's
failure mode: *"If a column contains a string where the model expects an int, you get a model
instance with a string in an int field – no error, no coercion, just a quietly wrong value."*
[CITED: anentropic.github.io/arrowmodel/explanation/fast-vs-validated.html]. Reproduced.
But the validated path is **not** a substitute for the pre-check:

| Arrow column | DTO annotation | `validate=False` | `validate=True` |
|---|---|---|---|
| `decimal128(38,2)` | `float` | `Decimal('1.50')` — silently wrong type | **`1.5` — silently coerced, precision lost, NO error** |
| `decimal128(38,2)` | `decimal.Decimal` | `Decimal('1.50')` | `Decimal('1.50')` |
| `string` | `int` | `'notanint'` | `ValidationError … int_parsing` |
| `int64` | `str` | `1` | `ValidationError … string_type` |

[VERIFIED: executed, arrowmodel 1.0.0 + pydantic 2.13.4]

So D-01's summary of `validate=True` ("raises pydantic `ValidationError` naming the field") is
right for non-coercible pairs and **wrong for the Decimal→float pair that 47-DECISIONS.md's
whole Decimal policy exists to protect**. The pre-check is the only guard on that case. Say so
in the docs rather than letting a reader infer that `validate=True` is the safer mode for money.

### Q5 — Does reading `.schema` on a streaming reader cost I/O or a batch? **No, on both paths.**

**Async (poolhouse).** Confirmed in installed source:

```python
    @property
    def schema(self) -> pyarrow.Schema:
        """
        The reader's Arrow schema (synchronous; no offload --- touches no I/O).
        ...
        """
        return self._reader.schema
```
[VERIFIED: .venv/…/adbc_poolhouse/_async/_reader.py:219-229 — quoted verbatim]

and in the module docstring: *"**Synchronous `schema` (D-29-04).** `schema` is a plain
`@property` passthrough of the sync reader's schema. It touches no I/O, so it is not offloaded
and not `async`"* [VERIFIED: _reader.py:23-26].

**Executed confirmation, both paths, against a live in-memory DuckDB carrying the Phase 47
probe view (3 result rows):**

- sync `pyarrow.RecordBatchReader`: read `.schema` first, then drained the reader → **3 rows**
  still available.
- async `adbc_poolhouse._async._reader.AsyncRecordBatchReader`: `.schema` read took
  **0.000002 s**, then `async for` yielded **3 rows**.

[VERIFIED: executed via `semolina.create_engine` / `create_async_engine` on the project venv]

**A better source than the reader, and the one I recommend.** `cursor.description` already
carries the pyarrow types, synchronously, on **both** cursors, *without creating a reader at
all*:

```text
   region              | DataType(string)                     | <class 'pyarrow.lib.DataType'>
   total_order_value   | Decimal128Type(decimal128(38, 2))    | <class 'pyarrow.lib.Decimal128Type'>
   region_list         | ListType(list<l: string>)            | <class 'pyarrow.lib.ListType'>
```
[VERIFIED: executed; and the shape is fixed by
`.venv/…/adbc_driver_manager/_dbapi_backend.py:245-251`:
`return [(field.name, field.type, None, None, None, None, None) for field in s]`]

`AsyncSemolinaCursor.description` is already a plain synchronous property
[VERIFIED: src/semolina/acursor.py:255-266, "Synchronous, with no await, because
adbc-poolhouse keeps it a plain property read: there is no I/O to offload"], and
`SemolinaCursor.description` likewise [VERIFIED: src/semolina/cursor.py:201-209].

This matters for D-05 more than the schema-cost question does. On the **async** cursor,
obtaining the reader requires `await self._cursor.fetch_record_batch()`
[VERIFIED: src/semolina/acursor.py:249-251] — so a *plain* `def iter_into(...)` cannot reach
`reader.schema` without an await, and D-05 says it must stay a plain method. Reading
`self.description` solves that cleanly: it is sync, free, and creates no reader.

**Recommendation:** build the pre-check from `description` on both cursors and both forms
(`.into()` too — `fetch_arrow_table().schema` also works there, but one code path is better
than two). Caveat to test: `description` requires pyarrow (the `_NoOpBackend` raises), which is
consistent with `.into()` needing pyarrow anyway.

### Q6 — polars Decimal support (Assumption A3). **MEASURABLE AND POSITIVE.**

**The measurement.** polars 1.43.2 maps Arrow `decimal128` to a **native `Decimal(precision,
scale)` dtype** holding `decimal.Decimal` values — strictly better than pandas' `object` dtype.

| Probe | Observed |
|---|---|
| `pl.from_arrow(Table with decimal128(38,2))` dtype | `Decimal(precision=38, scale=2)` |
| element type | `decimal.Decimal` (`Decimal('43.25')`) |
| null element | `None` |
| `.sum()` | `Decimal('143.25')` — stays Decimal |
| `group_by().agg(sum)` dtype | `decimal[38,2]` — preserved |
| `col * 2` dtype | `decimal[38,2]` — preserved |
| `.to_pandas()` | back to `dtype('O')` holding `Decimal` |
| **`pl.from_arrow(decimal256(50,4))`** | **`pyo3_runtime.PanicException: operator does not support primitive Int256`** — a Rust panic, not a Python exception |

[VERIFIED: executed, polars 1.43.2 / pyarrow 25.0.1, over both a `pyarrow.Table` and a
`RecordBatchReader` (the PyCapsule-stream shape ADBC actually uses)]

The `decimal256` panic is narrow: Snowflake `NUMBER(38,x)`, Databricks `DECIMAL(≤38,x)` and
DuckDB `DECIMAL(≤38,x)` all land as `decimal128` — the live DuckDB probe returns
`decimal128(38, 2)` and `decimal128(10, 2)` [VERIFIED: executed], and the committed Snowflake
cassette is `decimal128(38, 0)` [VERIFIED: read from
`tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/…/000_result.arrow`].
So the honest caveat for `fetch_polars()` is "decimal256 panics, and none of the three
supported backends produce one" — worth one sentence, not a warning banner.

**How the probe harness is invoked, so the planner can write a task that produces a real row.**

- Entry point: `just type-fidelity` → `uv run python tests/type_fidelity_probe.py --write`
  [VERIFIED: justfile:22-24 — quoted verbatim]. `--check` is the staleness gate; it diffs the
  regenerated text against the committed file and exits 1
  [VERIFIED: tests/type_fidelity_probe.py:1941-1958].
- The function to replace is `_measure_polars()` at `tests/type_fidelity_probe.py:1575-1595`.
  It currently takes **no arguments** and returns a hard-coded row:

  ```python
      if importlib.util.find_spec("polars") is None:
          observed = "not measured — polars not installed"
      else:
          observed = "not measured — polars installed but out of scope until Phase 49"
      return DownstreamObservation(
          consumer="polars",
          observed=observed,
          status=STATUS_NOT_MEASURED,
          assumption="A3",
      )
  ```
  [VERIFIED: tests/type_fidelity_probe.py:1586-1595 — quoted verbatim]

  It is called from `measure_downstream_decimal()` at line 1634 as `"polars": _measure_polars()`
  [VERIFIED: :1634]. The pandas sibling `_measure_pandas(table)` at :1499-1532 is the shape to
  copy: it takes the probe `table`, imports inside the function, and renders
  `f"pandas {pandas.__version__}: dtype \`{column.dtype}\`, elements \`{element_type}\`"`.
  So `_measure_polars(table)` should take the same `pyarrow.Table`, call
  `polars.from_arrow(table)`, and render polars version + dtype + element type. The
  `table` is available at the call site (`measure_downstream_decimal()` already holds it).
- **Blocking prerequisite:** `polars` is not installed in `.venv`
  [VERIFIED: `importlib.util.find_spec('polars') is None` in `.venv`], which is precisely what
  D-13 fixes. The row cannot be produced before the `pyproject.toml` task lands, so **order the
  waves: extras first, regeneration after.**
- Regenerate with `uv sync --all-groups --extra all`, not `--dev --extra all` — the latter
  prunes the `docs` group and breaks `just docs-build` [VERIFIED: STATE.md Accumulated
  Decisions, Phase 48].
- Guards to expect: `tests/unit/test_type_fidelity_table.py` parses the committed artifact and
  enforces the circularity rule [VERIFIED: tests/type_fidelity_probe.py:20-23 docstring].
  Regenerating changes at least three cells (polars row, pydantic version, and any environment
  string) — check whether that test asserts on literal cell text before planning the edit.

**Correction to CONTEXT.md.** D-13 says "this project's CI runs `uv sync --all-groups --extra
all`". It does not: every CI job runs `uv sync --locked --dev --extra all`
[VERIFIED: .github/workflows/ci.yml:34, 55, 76, 107]. The conclusion still holds (polars lands
via `[all]` → `[polars]`), but the command is `--dev`, and `--locked` means **`uv.lock` must be
regenerated and committed** as part of the pyproject task or every CI job fails on a lock
mismatch. That is an easy-to-miss plan step.

### Q7 — What comparison machinery is reusable, and what must not be reused

**Reusable: the predicate cascade in `arrow_map.py`. Not reusable: anything in
`annotation_check.py`.**

`arrow_type_to_python` is classification-by-`pyarrow.types.is_*` and is the right *logic*
[VERIFIED: src/semolina/codegen/arrow_map.py:26-114]. But its signature is
`(dtype: pyarrow.DataType) -> str | None` — it returns an **annotation string**
(`'decimal.Decimal'`, `'datetime.datetime'`, `'int'`), because its consumer is a source-code
renderer. The pre-check holds real runtime objects from `DTO.model_fields[name].annotation`
and has nothing to compare a string against.

`annotation_check.py` is a **string-vs-string** comparator over a *textually parsed* committed
model (`CommittedField.annotation`), driven by `probe_schema` and shaped around
`IntrospectedView` / `IntrospectedField` [VERIFIED: src/semolina/codegen/annotation_check.py:39-49,
97-121, 249-280, 403-504]. Every one of those inputs is absent at `.into()` time. **Do not
import from it.** Its `FieldCheckRow` / `ViewCheckReport` shape is worth imitating for the
*error report* (name, expected, got, status) and nothing else — CONTEXT.md already says
"not a drop-in", and the reason is concrete: it compares text produced by a renderer.

**Recommended construction.** Add a sibling in `arrow_map.py` that shares the one cascade:

```python
_ANNOTATION_TO_TYPE: dict[str, type] = {
    "bool": bool, "int": int, "float": float, "str": str, "bytes": bytes,
    "decimal.Decimal": decimal.Decimal,
    "datetime.date": datetime.date,
    "datetime.datetime": datetime.datetime,
    "datetime.time": datetime.time,
}

def arrow_type_to_runtime_type(dtype: pyarrow.DataType) -> type | None:
    name = arrow_type_to_python(dtype)
    return None if name is None else _ANNOTATION_TO_TYPE[name]
```

One cascade, two renderings — the two cannot drift, which is the property Phase 47/48 spent a
whole phase protecting. The nine names above are exhaustive for `arrow_map.py` as it stands
[VERIFIED: arrow_map.py:66-114 — every `return` in the function is one of
`"bool"`, `"decimal.Decimal"`, `"int"`, `"float"`, `"str"`, `"bytes"`, `"datetime.date"`,
`"datetime.datetime"`, `"datetime.time"`, a recursive call, or `None`]. Add a unit test that
asserts the map covers every string the cascade can return, so a future `arrow_map` addition
fails loudly rather than raising `KeyError` at a user's call site.

**A validated bonus: arrowmodel agrees with `arrow_type_to_python` on the runtime type.** This
was not obvious — arrowmodel reads Arrow buffers in Rust and never calls `to_pylist()`, which
is what `arrow_type_to_python`'s docstring says its answers describe [VERIFIED: arrow_map.py:31-33].
I measured both sides across 29 Arrow types:

| Divergence | `to_pylist()` | arrowmodel fast path | Impact |
|---|---|---|---|
| `date64` | `datetime.date` | `datetime.datetime` | Pre-check predicts `datetime.date`; arrowmodel gives a `datetime` (a *subclass* of `date`), so the check stays sound. None of the three backends emit `date64`. |
| `month_day_nano_interval` | `pyarrow.MonthDayNano` | `tuple` | `arrow_type_to_python` returns `None` for intervals anyway — outside the mapped set. |
| `timestamp[ns]` (with pandas installed) | `pandas.Timestamp` | `datetime.datetime` | arrowmodel is *more* consistent. `arrow_type_to_python`'s documented over-approximation (broken window 3) simply does not apply to `.into()`. Worth recording. |

Every other type — bool, all int widths, both floats, decimal128/256, string/large_string/
string_view, all three binaries, date32, timestamp at all four units and tz-aware, time32/time64,
dictionary-encoded, list, null, duration — **agreed exactly**. [VERIFIED: executed, 29-case
matrix, pyarrow 25.0.1 + arrowmodel 1.0.0; and the `timestamp[ns]` row re-run with pandas 3.0.5
installed]

**The awkward cases, all measured on pydantic 2.13.4 / Python 3.11.1.** What
`model_fields[name].annotation` actually is:

| Declared | `annotation` repr | `type(annotation)` | `get_origin` | `get_args` | `is_required()` |
|---|---|---|---|---|---|
| `a: int` | `<class 'int'>` | `type` | `None` | `()` | True |
| `b: int \| None` | `int \| None` | `UnionType` | `types.UnionType` | `(int, NoneType)` | True |
| `c: Optional[int] = None` | `typing.Optional[int]` | `_UnionGenericAlias` | `typing.Union` | `(int, NoneType)` | False |
| `d: Any` | `typing.Any` | `_AnyMeta` | `None` | `()` | True |
| `e: object` | `<class 'object'>` | `type` | `None` | `()` | True |
| `f: decimal.Decimal` | `<class 'decimal.Decimal'>` | `type` | `None` | `()` | True |
| `g: list[str]` | `list[str]` | `GenericAlias` | `list` | `(str,)` | True |
| `i: str = "x"` | `<class 'str'>` | `type` | `None` | `()` | False |
| `j: int = Field(default=3)` | `<class 'int'>` | `type` | `None` | `()` | False |
| `k: pydantic.JsonValue` | `JsonValue` | `TypeAliasType` | `None` | `()` | True |
| `l: "int"` (string annotation) | `<class 'int'>` | `type` | `None` | `()` | True |

[VERIFIED: executed — table transcribed from the run]

Point by point against D-10:

- **`Any`** — `typing.Any` is not a class, so `issubclass(x, Any)` raises `TypeError`.
  Special-case it explicitly as "pass". [VERIFIED: `type(annotation)` is `_AnyMeta`]
- **`object`** — is a real class, and `issubclass(anything, object)` is True, so the opt-out
  comes for free with no special case. [VERIFIED: issubclass table]
- **`X | None` unwrapping** — two shapes must both be handled:
  `get_origin(int | None) is types.UnionType` **and** `get_origin(Optional[int]) is typing.Union`
  both True [VERIFIED: executed]. Drop `NoneType` (D-09), then pass if **any** remaining member
  accepts.
- **`decimal.Decimal` vs `float`** — `issubclass(Decimal, float)` is **False**, so a plain
  `issubclass` keeps this the hard failure D-10 requires, with no special-casing. ✅
- **The one D-10 does not name, and the planner must decide: `int` into `float`.**
  `issubclass(int, float)` is **False** in Python — there is no nominal numeric tower.
  Under a strict `issubclass` rule, an Arrow `int64` column landing in a `float`-annotated DTO
  field is a *mismatch* and `.into()` raises. That is arguably correct (the fast path really
  does put an `int` in a field declared `float` — the same class of silent wrong-typing as
  Decimal→float) but it will surprise people who expect pydantic's lax coercion. **Recommend:
  no special case — treat it as a mismatch and document it**, consistent with the Decimal
  policy. Flag it in the plan so it is a decision, not an accident.
- **`bool` into `int`** — `issubclass(bool, int)` is True → passes. Correct under
  subtype-tolerance. `datetime` into `date` also passes; `date` into `datetime` fails.
  [VERIFIED: issubclass table]
- **`JsonValue` from a VARIANT column — a landmine.** `semolina.types.JsonValue` is a
  *self-referential string* `TypeAlias`
  [VERIFIED: src/semolina/types.py:19 —
  `JsonValue: TypeAlias = "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"`].
  Used as a **pydantic field annotation** it sends pydantic into infinite recursion:
  `RecursionError: maximum recursion depth exceeded during compilation`
  [VERIFIED: executed — module-level alias in a separate module, imported, then
  `class M(BaseModel): payload: JsonValue`]. `semolina/types.py`'s own docstring already
  anticipates the right answer: *"Phase 49's DTO side mirrors it against `pydantic.JsonValue`"*
  [VERIFIED: src/semolina/types.py:5-8]. So **DTO docs must tell users to annotate a VARIANT
  column with `pydantic.JsonValue`, never `semolina.JsonValue`**, and this needs a test.
  `pydantic.JsonValue` resolves to a `typing_extensions.TypeAliasType` whose `__value__` is
  `Annotated[Union[Annotated[list['JsonValue'], Tag], …, Annotated[str, Tag], …], Discriminator, _AllowAnyJson]`
  [VERIFIED: executed] — `get_origin()` is `None` and `get_args()` is `()`, so a naive union
  walk sees an opaque object.
- **`list[...]` / nested Struct** — `arrow_type_to_python` returns `None` for both
  [VERIFIED: arrow_map.py:114 falls through to `return None`; struct/list have no branch].
  arrowmodel handles both *correctly* — `list[str]` from an Arrow `list<string>` ✅, and an
  Arrow struct into a nested `BaseModel` field ✅ [VERIFIED: executed]. So an unmapped Arrow
  type must **not** fail the pre-check — failing would break conversions that work.
  Recommendation: **`arrow_type_to_runtime_type(...) is None` → skip the field, no verdict.**
  One documented exception measured: an Arrow **struct** column into an `Any`-annotated field
  raises inside arrowmodel — `TypeError: Arrow Struct column (fields: ["a"]) has no matching
  Pydantic model. Annotate the field with a BaseModel subclass, or a container of one (e.g.
  \`MyModel\`, \`MyModel | None\`, \`list[MyModel]\`), so its fields can be constructed.`
  [VERIFIED: executed]. The message is already actionable; let it through unwrapped.
- **A completely un-annotated field does not exist.** pydantic rejects it at class creation:
  `pydantic.errors.PydanticUserError: A non-annotated attribute was detected: \`x = 1\`. All
  model fields require a type annotation…` [VERIFIED: executed]. DTO-04's "untyped model"
  therefore means `Any`-annotated, which works: `Untyped.convert(batch)` produced `int` and
  `str` values in `Any` fields [VERIFIED: executed].

**Overall design rule I recommend the planner adopt:** the pre-check reports a mismatch only
when it is *confident* — both sides reduce to a class (or a union of classes). Anything else
(`Any`, an unmapped Arrow type, a `TypeAliasType`, an `Annotated`, a parameterised generic it
cannot reduce) passes silently. DTO-03 asks for "rather than a silently wrong-typed value",
not for a second type checker; and every false positive is a working call site that now raises.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Arrow → Pydantic row conversion | arrowmodel (Rust extension) | — | Don't-hand-roll; 2x faster than `to_pylist()` + `model_construct`, and already written |
| Schema/DTO structural pre-check | Semolina (`src/semolina/dto.py`) | — | Nothing upstream does it; arrowmodel checks presence only, never types |
| Arrow type → Python type mapping | Semolina (`codegen/arrow_map.py`) | — | Already exists; extend with a runtime-type sibling, do not duplicate |
| Result → pandas / polars | ADBC driver-manager + poolhouse | — | Both already implement `fetch_df` / `fetch_polars`; Semolina delegates |
| Missing-dependency detection & message | Semolina (cursor guards) | — | Both lower layers deliberately refuse to do it |
| Streaming batch delivery | ADBC / poolhouse readers | Semolina (`iter_into` drive loop) | Reader lifetime and offload are poolhouse's; per-batch conversion is Semolina's |
| Extras / install contract | `pyproject.toml` | CI `packaging-smoke` | Declaration plus a clean-venv proof |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `arrowmodel` | `>=1.0.0` | Arrow `RecordBatch`/`Table` → Pydantic v2 instances in Rust | The only library doing this conversion natively; by this project's own author; ships abi3 wheels for the whole CI matrix [VERIFIED: pypi.org/pypi/arrowmodel/json] |
| `pydantic` | `>=2.13.4` (transitive, via arrowmodel) | The DTO base | Already an unconditional dependency via `adbc-poolhouse → pydantic-settings`; arrowmodel raises the floor |
| `pyarrow` | `>=17.0.0` | Result schema and Table/RecordBatch objects | Already pinned inside `[duckdb]` [VERIFIED: pyproject.toml:43]; reuse the same floor for the new `[pyarrow]` extra |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `polars` | `>=1.0.0` | `fetch_polars()` | 1.0.0 already handles both `Table` and PyCapsule-stream input and maps `decimal128` to a native `Decimal` dtype [VERIFIED: executed on polars 1.0.0 + pyarrow 17.0.0] |
| `pandas` | `>=2.0.0` | `fetch_df()` | Behaviour measured at 2.3.3 (project) and 3.0.5 (scratch); decimal stays `object` dtype in both. `>=2.0.0` is the conservative floor [ASSUMED — 2.0.0 itself not exercised] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `arrowmodel` | `table.to_pylist()` + `Model.model_validate(row)` | ~2x slower [CITED: arrowmodel fast-vs-validated benchmarks: 15.6 ms vs 33.9 ms at 1000 rows], no Rust dependency, but re-implements what DTO-01 explicitly names arrowmodel for |
| `polars` extra | narwhals | In PROJECT.md's Out of Scope; ADBC already ships `fetch_polars` |
| `Model.convert(...)` classmethod | `model_convert(Model, ...)` free function | The free function accepts *any* `type[BaseModel]`, not just `ArrowModel` subclasses — a real widening of `.into()`'s accepted input (see Open Question 1) |
| Per-call `Model.iter(batch)` in streaming | `ArrowModelConverter(Model)` built once, `.iter(batch)` per batch | The converter compiles the alias-aware field map once and reuses it across batches ("Per SCHEMA-02" [VERIFIED: `ArrowModelConverter.__doc__`]); recommended for `iter_into` |

**Installation** (what the `pyproject.toml` task produces):

```toml
pyarrow    = ["pyarrow>=17.0.0"]
pandas     = ["pandas>=2.0.0"]
polars     = ["polars>=1.0.0"]
arrowmodel = ["arrowmodel>=1.0.0"]
duckdb     = ["duckdb==1.5.5", "semolina[pyarrow]"]
all        = ["semolina[snowflake,databricks,duckdb,async,pyarrow,pandas,polars,arrowmodel]"]
```

**Version verification** — run before writing the table; do not trust training data:

```bash
pip index versions arrowmodel   # 1.0.0 only
pip index versions polars       # 1.43.2 current
pip index versions pandas       # 3.0.5 current
pip index versions pyarrow      # 25.0.1 current
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `arrowmodel` | PyPI | 1.0.0 published 2026-07-07 (~5 weeks); repo created 2026-03-21 | not published by PyPI JSON API | `github.com/anentropic/arrowmodel` — HTTP 200, 0 stars | SUS by heuristic → **OK by provenance** | **Approved.** Same author as this project (`anentropic`, `ego@anentropic.com`), named explicitly in DTO-01/DTO-05 and in `.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md`, and already recorded in the user's own memory as the candidate typed-DTO layer. Low downloads are expected for a first-party package, not a slopsquatting signal. |
| `polars` | PyPI | 1.43.2, 2026-08-01 | — | pola-rs/polars | OK | Approved |
| `pandas` | PyPI | 3.0.5, 2026-07-22 | — | pandas-dev/pandas | OK | Approved |
| `pyarrow` | PyPI | 25.0.1, 2026-08-10 | — | apache/arrow | OK | Approved — already a declared dependency inside `[duckdb]` |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none requiring a checkpoint. `gsd-tools query
package-legitimacy check --ecosystem pypi …` returned `SUS` with signals `exists: null,
publishedAt: null, weeklyDownloads: null, repoUrl: null` for **all four** packages including
`pandas` and `pyarrow` [VERIFIED: executed] — the seam could not reach PyPI, so its verdict is
uninformative here and is superseded by the direct registry lookups above.

**Sdist / build safety:** arrowmodel ships prebuilt `cp311-abi3` wheels for macOS (x86_64 +
arm64), manylinux_2_17 (x86_64 + aarch64) and win_amd64 [VERIFIED: pypi.org/pypi/arrowmodel/json],
so neither CI nor a normal user builds the Rust extension from source. No postinstall-script
concept exists on PyPI wheels.

## Architecture Patterns

### System Architecture — data flow

Trace the primary use case (a BI backend asking for typed rows) by following the arrows:

- **Entry: user code** → `Sales.query().metrics(...).execute()` (or `await ...aexecute()`)
  → returns an **open** `SemolinaCursor` / `AsyncSemolinaCursor`.
- **Branch A — whole table.** `cursor.into(SalesDTO)`
  → *guard*: `find_spec("pyarrow")`, `find_spec("arrowmodel")` → `SemolinaMissingDependencyError`
  → *pre-check*: read `cursor.description` (sync, no I/O, no reader) → per-field compare
  → mismatches? → `SemolinaSchemaMismatchError` listing **all** of them (D-11)
  → `cursor.fetch_arrow_table()` → `pyarrow.Table`
  → `arrowmodel` (Rust: buffers → `model_construct`, or → JSON → `model_validate_json`)
  → `list[SalesDTO]` to the caller.
- **Branch B — streaming.** `cursor.iter_into(SalesDTO)`
  → same guard, same pre-check, **executed at the call** (D-05)
  → returns a generator that drives `cursor.fetch_record_batch()` →
  `pyarrow.RecordBatchReader` (sync) or poolhouse `AsyncRecordBatchReader` (async)
  → per batch: `ArrowModelConverter.iter(batch)` → yield one DTO at a time (D-03)
  → back-pressure stays with the reader; only one batch of DTOs is live.
- **Branch C — dataframes.** `cursor.fetch_df()` → guard `pandas` → ADBC
  `reader.read_pandas()`. `cursor.fetch_polars()` → guard `polars` (**not** pyarrow) → ADBC
  `polars.from_arrow(self.fetch_arrow())` over the raw PyCapsule stream.
- **External boundaries.** Semolina never imports arrowmodel / pandas / polars at module scope;
  every one is a `TYPE_CHECKING`-only annotation plus a function-local import behind a
  `find_spec` guard. The async branch's every batch pull crosses poolhouse's thread offload.

### Recommended Project Structure

```
src/semolina/
├── exceptions.py     # NEW (D-14): SemolinaMissingDependencyError, SemolinaSchemaMismatchError
│                     #             + the _require(package, extra) find_spec helper
├── dto.py            # NEW: the structural pre-check — schema x model_fields -> mismatch list
├── cursor.py         # into(), iter_into(), fetch_df(), fetch_polars(), + 4 pyarrow guards
├── acursor.py        # the async twins
├── codegen/
│   └── arrow_map.py  # + arrow_type_to_runtime_type() sibling, one shared cascade
└── __init__.py       # export the two new errors
```

Putting the pre-check in `src/semolina/dto.py` rather than under `codegen/` matters: `codegen/`
is the probe-driven, source-rendering half of the project, and Phase 47/48 spent real effort
keeping the "result half" and the "metadata half" from converging. `.into()` belongs to the
result half and touches no introspection at all.

### Pattern 1: guard, pre-check, then delegate

**What:** every new public method is three cheap steps followed by a one-line delegation.
**When to use:** all six new methods (`into`, `iter_into`, `fetch_df`, `fetch_polars` × 2 cursors).
**Why:** it matches the established ADBC-passthrough pattern (Phase 39) — two-line delegates
with long docstrings carrying the lifetime rules [VERIFIED: src/semolina/cursor.py:139-197] —
while adding exactly the two things the lower layers refuse to do.

### Pattern 2: `iter_into` is a method that *returns* a generator

**What:**

```python
def iter_into(self, model: type[BaseModel], *, validate: bool = False) -> Iterator[Any]:
    _require("pyarrow", "pyarrow")
    _require("arrowmodel", "arrowmodel")
    _check_schema(self.description, model)      # raises here, at the call (D-05)
    return self._iter_into_impl(model, validate=validate)   # the generator function

def _iter_into_impl(self, model, *, validate):
    from arrowmodel import ArrowModelConverter
    converter = ArrowModelConverter(model, validate=validate)
    reader = self.fetch_record_batch()
    for batch in reader:
        yield from converter.iter(batch)
```

**When to use:** wherever a public method must validate eagerly but produce lazily.
**Why:** a `def` containing `yield` runs *no* body until the first `next()`. Measured proof
that this is not theoretical: `Model.iter(batch)` returned a generator and only raised on
`next()` [VERIFIED: executed].

The async twin keeps `__aiter__`-style neutrality — a plain `def` returning an object with
`__aiter__`/`__anext__`, or a plain `def` returning an async generator — matching Phase 46's
choice to keep `__aiter__` plain while `fetch_record_batch` is `async def`
[VERIFIED: src/semolina/acursor.py:282-293, 206-251].

### Pattern 3: one converter per call, reused across batches

Build `ArrowModelConverter(model, validate=validate)` **once** outside the batch loop. Its
docstring states the payoff: *"Per SCHEMA-02: Schema mapping compiled once at init, reused
across batches."* [VERIFIED: `ArrowModelConverter.__doc__`]. Note again that its `convert()` /
`iter()` take **no** `validate=` — that lives on the constructor [VERIFIED: `inspect.signature`].

### Anti-Patterns to Avoid

- **Writing `iter_into` as a generator function.** Silently defeats D-05. Test it by calling
  `iter_into` with a bad DTO and asserting the raise happens **without** touching the result.
- **Handing a `RecordBatchReader` to arrowmodel.** Rejected: `ValueError: Expected an object
  with dunder __arrow_c_array__` [VERIFIED: executed]. Iterate it yourself.
- **Reusing `annotation_check.py`'s comparator.** It compares annotation *strings* parsed out
  of committed source and needs a live probe. See Q7.
- **Guarding `fetch_polars()` with the pyarrow check.** ADBC's `fetch_polars` uses
  `polars.from_arrow(self.fetch_arrow())` — the raw PyCapsule handle, no pyarrow
  [VERIFIED: .venv/…/adbc_driver_manager/dbapi.py:1430-1441]. Guarding it on pyarrow would
  refuse a call that works.
- **Letting `.into()`'s docstring example become a doctest.** Root pytest runs with
  `--doctest-modules` over `testpaths = ["tests", "src"]` [VERIFIED: pyproject.toml:159-165],
  so a `>>>` example importing arrowmodel would fail on a base install. Existing docstrings use
  `.. code-block:: python`, which doctest ignores — keep that.
- **Reading rows to decide anything.** 47-DECISIONS.md Decision 1 is a prohibition; the pre-check
  must remain schema-only, and `cursor.py`/`results.py` value handling must not be touched.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arrow buffers → Pydantic instances | A `to_pylist()` + `model_validate` loop | `arrowmodel` | ~2x slower, and re-solves aliases, nested structs, dictionary encodings, and null handling [CITED: arrowmodel fast-vs-validated] |
| Alias-aware column matching | Your own `alias or name` lookup | arrowmodel's `validation_alias > alias > field_name` — and **mirror it** in the pre-check | A pre-check matching on a different key than the converter will pass a DTO arrowmodel then rejects, or vice versa |
| Arrow Table → `pandas.DataFrame` | `table.to_pandas()` in Semolina | `cursor.fetch_df()` | Already implemented and cancellation-aware (`_blocking_call(..., self._stmt.cancel)`) [VERIFIED: dbapi.py:1427-1428] |
| Arrow → `polars.DataFrame` | `pl.from_arrow(table)` in Semolina | `cursor.fetch_polars()` | ADBC skips pyarrow entirely and hands polars the PyCapsule stream — strictly cheaper |
| Off-loop dataframe materialisation | Your own thread offload | poolhouse `AsyncCursor.fetch_df/fetch_polars` | Runs through the pool limiter with cancellation and poison recovery [VERIFIED: adbc_poolhouse/_async/_cursor.py:384-489] |
| Arrow type → Python type | A second mapping table | `arrow_type_to_python` + a thin runtime-type sibling | Two tables drift; Phase 48 already paid for that lesson (arrow_map.py:31-36) |

**Key insight:** in this phase, almost every "conversion" is already written by someone. The
only genuinely new code is the part both lower layers *deliberately* refuse to write — the
missing-dependency message and the type pre-check. Keep the new surface that small.

## Common Pitfalls

### Pitfall 1: `validate=True` is not the safe mode for money

**What goes wrong:** a reader concludes `.into(DTO, validate=True)` is the belt-and-braces
option and stops worrying about the Decimal policy.
**Why it happens:** the validated path serialises to JSON and calls `model_validate_json`, so
a `decimal128` column into a `float` field is *coerced* to `1.5` — no error, precision gone.
**How to avoid:** state in the docs that the pre-check, not `validate=True`, is what protects
the Decimal contract; and let the pre-check run on both paths (D-06 already says "always").
**Warning signs:** a test asserting `validate=True` raises for Decimal→float will fail; write it
asserting the *pre-check* raises. [VERIFIED: executed]

### Pitfall 2: Snowflake result columns are not Python identifiers

**What goes wrong:** the DTO-06 worked example is written against DuckDB, where columns are
bare field names, then breaks the first time a user points it at Snowflake — whose canonical
result column is literally `AGG("REVENUE")` [VERIFIED: read from the committed cassette
`…/test_snowflake_probe/…/000_result.arrow`, schema `AGG("REVENUE"): decimal128(38, 0)`].
**Why it happens:** Snowflake names the result column after the expression, which
`annotation_check._result_field_names` already documents [VERIFIED: annotation_check.py:222-238].
**How to avoid:** show `Field(validation_alias='AGG("REVENUE")')` in the docs, and make the
pre-check resolve on the same key. Both `validation_alias=` and `alias=` were measured working
[VERIFIED: executed against the cassette].
**Warning signs:** a `ValueError: Arrow schema is missing required columns: ['revenue']` whose
"Available columns" list is full of quoted SQL.

### Pitfall 3: `semolina.JsonValue` in a DTO recurses pydantic to death

**What goes wrong:** `class MyDTO(ArrowModel): payload: JsonValue` (importing from `semolina`)
→ `RecursionError: maximum recursion depth exceeded during compilation`, at *class creation*.
**Why it happens:** the alias is a self-referential **string** (`src/semolina/types.py:19`),
which pydantic re-expands at every nesting level instead of turning into a definition-ref.
**How to avoid:** DTO annotations for a VARIANT column use `pydantic.JsonValue`.
`semolina.JsonValue` remains correct for *generated `SemanticView` models*, which are read as
text and never imported by pydantic.
**Warning signs:** a RecursionError with a pydantic `_generate_schema.py` traceback and no
Semolina frames. [VERIFIED: executed]

### Pitfall 4: arrowmodel can *panic* on an unaligned decimal buffer

**What goes wrong:** `pyo3_runtime.PanicException: Memory pointer from external source (e.g,
FFI) is not aligned with the specified scalar type` — a Rust panic, which is **not** an
`Exception` and will not be caught by `except Exception`.
**Why it happens:** arrow-rs requires a `decimal128` buffer aligned to its 16-byte scalar
width; the Arrow C data interface only guarantees 8. I reproduced this by writing the live
DuckDB probe result to an Arrow IPC **file** and reading it back with
`pyarrow.ipc.open_file(...).read_all()` — only the `decimal128(38,2)` column panicked; every
other column converted fine, and `table.combine_chunks()` (which copies) fixed it.
**Not reproduced on the real path:** a live ADBC DuckDB result carrying `decimal128(38,2)` and
`decimal128(10,2)`, both as a `Table` and per-batch through a `RecordBatchReader`, converted
cleanly; so did the committed Snowflake `decimal128(38,0)` cassette read straight from IPC.
**How to avoid:** if a Phase 49 test feeds a cassette-read table to arrowmodel, call
`.combine_chunks()` first. If a panic ever appears from the driver path, it is an upstream
arrow-rs/arrowmodel issue, not a Semolina bug.
**Warning signs:** stderr line beginning `thread '<unnamed>' … panicked at … arrow-buffer`.
[VERIFIED: executed — reproduced and isolated across 4 transports]

### Pitfall 5: `fetch_polars()` must be the first consuming call

**What goes wrong:** `ProgrammingError: Result set has been closed or consumed`.
**Why it happens:** ADBC's `fetch_polars` calls `self.fetch_arrow()`, which *takes* the
`ArrowArrayStreamHandle` and sets it to `None` [VERIFIED: dbapi.py:1443-1450]. Anything that
already created the reader (iteration, `fetch_record_batch`, `fetch_arrow_table`) leaves
nothing for it.
**Measured, on a live ADBC cursor:** `description` then `fetch_polars` ✅;
`fetch_record_batch` then `fetch_polars` ❌; `fetch_polars` twice ❌; `fetch_df` then
`description` ✅. [VERIFIED: executed]
**How to avoid:** document it in the `fetch_polars` docstring alongside the existing
one-consumption-pattern-per-cursor rule [VERIFIED: src/semolina/cursor.py:174-177].

### Pitfall 6: `--locked` CI and the uv.lock

**What goes wrong:** every CI job fails with a lock-mismatch before running a single test.
**Why it happens:** all four jobs run `uv sync --locked --dev --extra all`
[VERIFIED: ci.yml:34, 55, 76, 107]; adding four extras changes the resolution.
**How to avoid:** regenerate and commit `uv.lock` in the same task as the `pyproject.toml`
edit. Expect pydantic 2.12.5 → 2.13.4 in the lock diff (Q3).

### Pitfall 7: polars 2.0 will break ADBC's `fetch_polars()`

**What goes wrong (already, as a warning):**
`FutureWarning: from_arrow(<ArrowStreamExportable>) will return a Series instead of a DataFrame
in 2.0. To avoid this warning, pass the ArrowStreamExportable to either \`pl.DataFrame\` or
\`pl.Series\` instead based on your desired output type.` — emitted from
`adbc_driver_manager/dbapi.py:1543` during `fetch_polars()`.
[VERIFIED: executed, adbc-driver-manager 1.12.0 + polars 1.43.2]
**Why it matters:** the project's pytest config sets `filterwarnings` and docs build with `-W`;
more importantly a `polars>=1.0.0` extra with no cap will one day resolve polars 2.x and
`fetch_polars()` will return a `Series`.
**How to avoid:** decide deliberately — either cap (`polars>=1.0.0,<2.0`) or record it as a
known future break. Note the project venv's adbc-driver-manager is 1.10.0 and does not emit the
warning; 1.12.0 does.

## Code Examples

### 1. Eager `.into(DTO)` over a real semantic-view result

```python
# Source: executed this session against an in-memory DuckDB semantic view
import decimal
from arrowmodel import ArrowModel


class SalesDTO(ArrowModel):
    region: str
    total_order_value: decimal.Decimal   # a DECIMAL(38,2) metric
    n: int


table = cursor.fetch_arrow_table()       # pyarrow.Table, possibly multi-chunk
rows = SalesDTO.convert(table)           # list[SalesDTO]; extra columns ignored (D-07)
# [SalesDTO(region='US', total_order_value=Decimal('43.25'), n=7), ...]
```

### 2. The DTO-03 failure the pre-check must catch

```python
# Source: executed this session
class WrongDTO(ArrowModel):
    total_order_value: float             # the column is decimal128(38, 2)


WrongDTO.convert(table)
# [WrongDTO(total_order_value=Decimal('43.25'))]   <- fast path: silently a Decimal
WrongDTO.convert(table, validate=True)
# [WrongDTO(total_order_value=43.25)]              <- validated path: silently a float
# Neither raises. Only Semolina's pre-check can.
```

### 3. Streaming, sync — the `iter_into` inner loop

```python
# Source: executed this session against a live ADBC RecordBatchReader
from arrowmodel import ArrowModelConverter

reader = cursor.fetch_record_batch()     # pyarrow.RecordBatchReader
schema = reader.schema                   # free: no batch pulled, no I/O
converter = ArrowModelConverter(SalesDTO, validate=validate)
for batch in reader:                     # one batch in memory at a time
    yield from converter.iter(batch)     # DTOs yielded individually (D-03)
```

### 4. Streaming, async

```python
# Source: executed this session against adbc_poolhouse AsyncRecordBatchReader
reader = await self._cursor.fetch_record_batch()
_ = reader.schema                        # plain property; measured at 2 microseconds
converter = ArrowModelConverter(model, validate=validate)
async for batch in reader:               # each pull offloaded off the event loop
    for dto in converter.iter(batch):
        yield dto
```

### 5. The missing-dependency guard

```python
# Source: pattern from src/semolina/codegen/python_renderer.py:429-440
import importlib.util


def _require(package: str, extra: str) -> None:
    if importlib.util.find_spec(package) is None:
        raise SemolinaMissingDependencyError(
            f"{package} is required for this method but is not installed. "
            f"Install it with: pip install semolina[{extra}]"
        )
```

### 6. `_measure_polars`, the D-16 replacement

```python
# Source: shaped on _measure_pandas at tests/type_fidelity_probe.py:1499-1532
def _measure_polars(table: Any) -> DownstreamObservation:
    if importlib.util.find_spec("polars") is None:
        return DownstreamObservation("polars", "not measured — polars not installed",
                                     STATUS_NOT_MEASURED, "A3")
    import polars

    column = polars.from_arrow(table)[DECIMAL_PROBE_FIELD]
    element_type = python_value_type_name(column[0])
    return DownstreamObservation(
        consumer="polars",
        observed=f"polars {polars.__version__}: dtype `{column.dtype}`, elements `{element_type}`",
        status=STATUS_MEASURED,
        assumption="A3",
    )
    # Expected output at polars 1.43.2:
    #   dtype `Decimal(precision=38, scale=2)`, elements `decimal.Decimal`
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `table.to_pylist()` then `Model(**row)` | `Model.convert(table)` in Rust | arrowmodel 1.0.0, 2026-07-07 | ~2x on flat schemas; parity on deeply nested |
| pandas as the default dataframe answer | polars alongside, with a *native* Decimal dtype | polars ≥1.0 | `fetch_polars()` preserves decimal precision where `fetch_df()` degrades to `object` |
| pandas arriving transitively via `databricks-sql-connector` / `snowflake-connector-python` | an explicit `[pandas]` extra | this phase (D-12) | Closes WINDOWS.md broken window 3 |
| `pl.from_arrow(cursor.fetch_arrow_table())` | ADBC hands polars the PyCapsule stream directly | adbc-driver-manager ≥1.x | `fetch_polars()` needs no pyarrow at all |

**Deprecated/outdated:**
- The landing-page claim that arrowmodel accepts "any Arrow-PyCapsule-compatible input"
  including polars DataFrames — **false at 1.0.0** for polars input [VERIFIED: executed]. Plan
  against `RecordBatch | Table` only.
- `polars.from_arrow(<ArrowStreamExportable>)` returning a DataFrame — deprecated, changes in
  polars 2.0 (Pitfall 7).

## Environment Availability

| Dependency | Required By | Available in `.venv` | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pyarrow | pre-check, `.into()`, `fetch_arrow_table` | ✓ | 24.0.0 | — |
| pandas | `fetch_df()` | ✓ (transitive) | 2.3.3 | none needed; D-12 makes it explicit |
| polars | `fetch_polars()`, **D-16** | ✗ | — | **none — D-16 is blocked until the `[polars]` extra lands and `uv sync` runs** |
| arrowmodel | `.into()`, `iter_into()` | ✗ | — | none — must be added by the `pyproject.toml` task |
| pydantic | DTOs | ✓ (transitive) | 2.12.5 | will be bumped to ≥2.13.4 by arrowmodel |
| duckdb + `semantic_views` | every end-to-end test | ✓ | 1.5.5 | — |
| adbc-poolhouse | async cursor | ✓ | 1.6.2 | — |

[VERIFIED: `importlib.metadata.version` / `importlib.util.find_spec` executed in `.venv`]

**Missing dependencies with no fallback:**
- `polars` and `arrowmodel` are absent from the working venv. Every task that exercises them
  depends on the `pyproject.toml` + `uv.lock` + `uv sync` task landing first. **This is a wave
  ordering constraint, not a nicety** — D-16 in particular cannot produce a real row before it.

**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.0.0 (+ pytest-xdist, pytest-cov, syrupy, pytest-adbc-replay ≥1.1.1) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (root) and `semolina-jaffle-shop/pyproject.toml` |
| Root addopts | `-v --doctest-modules --doctest-continue-on-failure`, `testpaths = ["tests", "src"]` [VERIFIED: pyproject.toml:158-165] |
| Quick run command | `uv run pytest tests/unit/test_dto.py -x -q` |
| Full suite command | `just test` — `uv run pytest` **then** `pushd semolina-jaffle-shop; uv run pytest; popd` [VERIFIED: justfile:18-20] |
| Extra gates | `prek run --all-files`, `just docs-build` |

### Phase Requirements → Test Map

| Req | Behaviour | Test type | Suite | Automated command | File exists? |
|---|---|---|---|---|---|
| DTO-01 | `.into(DTO)` returns Pydantic instances matched by column name, sync + async | unit + DuckDB-live | root `tests/unit/test_dto.py` | `uv run pytest tests/unit/test_dto.py -k into_returns -x` | ❌ Wave 0 |
| DTO-01 | end-to-end against a real semantic view | integration (live DuckDB, no cassette) | root `tests/unit/test_dto_duckdb.py` (mirrors `test_type_fidelity_duckdb.py`) | `uv run pytest tests/unit/test_dto_duckdb.py -x` | ❌ Wave 0 |
| DTO-02 | `iter_into` yields DTOs one at a time without materialising | unit | root | `uv run pytest tests/unit/test_dto.py -k iter_into -x` | ❌ Wave 0 |
| DTO-02 | `async for` twin over the poolhouse reader, asyncio **and** trio | unit (loop matrix) | root `tests/unit/test_dto_async.py` | `uv run pytest tests/unit/test_dto_async.py -x` | ❌ Wave 0 — **must satisfy `tests/unit/test_asyncio_trio_matrix.py`**, which selects modules by content via an AST walk |
| DTO-02 | one batch in memory: assert the reader is not drained after N yields | unit | root | `uv run pytest tests/unit/test_dto.py -k lazy -x` | ❌ Wave 0 |
| DTO-03 | mismatch → `SemolinaSchemaMismatchError` naming field + both types | unit | root | `uv run pytest tests/unit/test_dto.py -k mismatch -x` | ❌ Wave 0 |
| DTO-03 | **all** mismatches reported, not the first (D-11) | unit | root | `uv run pytest tests/unit/test_dto.py -k reports_every -x` | ❌ Wave 0 |
| DTO-03 | `iter_into` raises **at the call**, before any batch moves (D-05) | unit | root | `uv run pytest tests/unit/test_dto.py -k raises_at_call -x` | ❌ Wave 0 — must be non-vacuous: prove it fails against a bare-generator implementation |
| DTO-03 | Decimal→float is a hard failure on **both** `validate` settings | unit | root | `uv run pytest tests/unit/test_dto.py -k decimal_into_float -x` | ❌ Wave 0 |
| DTO-04 | `Any`-annotated and partially-typed DTOs convert | unit | root | `uv run pytest tests/unit/test_dto.py -k untyped -x` | ❌ Wave 0 |
| DTO-04 | missing column **with a default** is allowed; without one, errors (D-08) | unit | root | `uv run pytest tests/unit/test_dto.py -k default -x` | ❌ Wave 0 |
| DTO-05 | `[arrowmodel]` extra declared; `[all]` includes it; lock in step | unit (reads pyproject) | root `tests/unit/test_dto_packaging.py` | `uv run pytest tests/unit/test_dto_packaging.py -x` | ❌ Wave 0 — copy `tests/unit/test_async_packaging.py` |
| DTO-05 | `import semolina` pulls no arrowmodel/pandas/polars | unit (child interpreter) | root | same file | ❌ Wave 0 — copy `test_packaging_importing_semolina_does_not_import_anyio` (`tests/unit/test_async_packaging.py:88`) |
| DTO-05 | **a base install has no arrowmodel** | CI job | `.github/workflows/ci.yml` `packaging-smoke` | `uv pip install .` in a clean venv + `find_spec` assert | ✅ job exists (ci.yml:149-180) — extend it |
| DTO-06 | docs build strict; examples reference real API | docs gate | root | `just docs-build` | ✅ |
| RESULT-01 | `fetch_df()`/`fetch_polars()` on both cursors return the right type | unit + DuckDB-live | root `tests/unit/test_cursor.py` / `test_async_cursor.py` | `uv run pytest tests/unit/test_cursor.py -k fetch_df -x` | ✅ files exist, tests don't |
| RESULT-02 | missing package → `SemolinaMissingDependencyError` naming the extra | unit (`find_spec` patch) | root | `uv run pytest tests/unit/test_cursor.py -k missing_dependency -x` | ❌ Wave 0 |
| RESULT-02 | the pyarrow guard on all four methods, both cursors (D-15) | unit | root | same | ❌ Wave 0 |
| D-16 | `47-TYPE-FIDELITY.md` polars row is `measured` | artifact gate | root | `uv run python tests/type_fidelity_probe.py --check` | ✅ harness exists; `_measure_polars` must change |

### How the DuckDB-backed path exercises `.into()` end to end

There is a ready-made fixture: `tests/type_fidelity_probe.py::make_probe_engine()` builds an
in-memory DuckDB carrying `type_fidelity_view` with a `DECIMAL(10,2)` base column whose `SUM`
metric arrives as `decimal128(38, 2)` [VERIFIED: executed — full result schema captured above].
That is exactly the shape DTO-03's headline case needs, and it runs live in-process with no
cassette (the module docstring forbids routing it through pytest-adbc-replay
[VERIFIED: tests/type_fidelity_probe.py:30-34]). `tests/unit/test_type_fidelity_duckdb.py` is
the precedent for a live-DuckDB unit test that is not an integration test.

The end-to-end chain a DTO test should assert, in one test: build the engine → `execute()` a
real query → `.into(SalesDTO)` → assert `isinstance(rows[0].total_order_value, decimal.Decimal)`.
That is the same "measured, not asserted from a table" discipline Phase 48 adopted
[VERIFIED: STATE.md — "proved by executed measurement (isinstance against a value from the real
driver path…), not by human review of a table"].

**Suite split.** Everything above belongs in the **root** `tests/` suite. `semolina-jaffle-shop`
is a separate uv workspace member whose dev group is only `semolina[duckdb]`
[VERIFIED: semolina-jaffle-shop/pyproject.toml:16-17] — it would need `semolina[arrowmodel]`
added to test `.into()`, and its CI step runs `pytest -m "duckdb"` only
[VERIFIED: ci.yml:140-143]. **Recommendation: do not put `.into()` tests there.** If the
DTO-06 docs example is drawn from jaffle-shop models (a good idea — it is the realistic BI
schema), keep the *models* there and the *test* in root.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_dto.py -x -q` (plus the specific file the
  task touched).
- **Per wave merge:** `just test` (both suites) + `prek run --all-files`.
- **Phase gate:** `just test`, `prek run --all-files`, `just docs-build`,
  `uv run python tests/type_fidelity_probe.py --check`, and a green CI `packaging-smoke` job,
  all before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/unit/test_dto.py` — DTO-01/02/03/04 pre-check and conversion behaviour
- [ ] `tests/unit/test_dto_async.py` — DTO-02 async twin (must satisfy the asyncio/trio matrix walk)
- [ ] `tests/unit/test_dto_duckdb.py` — live DuckDB end-to-end, decimal `isinstance` proof
- [ ] `tests/unit/test_dto_packaging.py` — DTO-05 extras contract + child-interpreter import check
- [ ] new tests in `tests/unit/test_cursor.py` / `test_async_cursor.py` — RESULT-01/02 and the
      four pyarrow guards
- [ ] `.github/workflows/ci.yml` `packaging-smoke` — extend the base-install assertion to
      arrowmodel/pandas/polars
- [ ] no framework install needed — pytest and every plugin are already in the dev group

## Security Domain

Low surface: no network, no auth, no user-supplied SQL introduced by this phase.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase adds no credential path |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | The DTO *is* the validation boundary. `validate=True` runs pydantic's full pipeline; the fast path deliberately does not, and that is a documented user choice, not a silent downgrade |
| V6 Cryptography | no | — |
| V14 Configuration | yes | Optional extras must not widen the default install's attack surface — the `packaging-smoke` clean-venv assertion is the control |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A warehouse value silently occupying a differently-typed DTO field, then serialised into an API response | Tampering / Information disclosure | The structural pre-check (D-06/D-10); document that the fast path performs no per-value validation |
| Rust extension panic escaping as a non-`Exception` `BaseException` and bypassing `except Exception` handlers in a web framework | Denial of service | Pitfall 4; do not wrap arrowmodel calls in `except Exception` and assume coverage |
| A leaked pooled connection from an unclosed async cursor driving `iter_into` | Denial of service (pool exhaustion) | Existing Phase 46 rule — `async with`; the async cursor has no `__del__` rescue [VERIFIED: src/semolina/acursor.py:401-428] |
| A new extra pulling an unexpected transitive dependency into user installs | Supply chain | `uv.lock` committed; `packaging-smoke`; the legitimacy audit above |
| Result data reaching a log or error message | Information disclosure | The pre-check reads **schema only** — no rows are fetched. Keep error messages free of values, matching `annotation_check.py`'s stated rule ("No row value ever reaches a report", :22-25) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `pandas>=2.0.0` is a safe floor for `fetch_df()` | Standard Stack | Low — only 2.3.3 and 3.0.5 were exercised; a user on 1.x would get an unpinned break. Bump to `>=2.0.0` and move on |
| A2 | Snowflake and Databricks never produce `decimal256`, so polars' Int256 panic is unreachable in practice | Q6 | Medium — a Snowflake `NUMBER` above precision 38 does not exist, but no Databricks decimal column has ever been recorded in this repo (WINDOWS.md 8). Phrase the docs caveat conditionally |
| A3 | `find_spec` patching reaches the guard helper the same way it reaches `ruff_available()` | Q2 | Low — the existing tests prove the mechanism; only the module under patch differs |
| A4 | The arrowmodel alignment panic (Pitfall 4) cannot arise from the Snowflake or Databricks driver paths | Pitfall 4 | Medium — only the DuckDB driver path and one Snowflake cassette were exercised. A live-warehouse `.into()` has never been run |
| A5 | The DTO-06 worked example should draw its schema from `semolina-jaffle-shop` | Validation Architecture | Low — a docs-shape preference, settled by the docs skill's Diataxis classification |
| A6 | `tests/unit/test_type_fidelity_table.py` will not need editing when the artifact's polars/pydantic cells change | Q6 | Medium — I read the probe's guards but not that test file's assertions. Check it before planning the D-16 task |

## Open Questions (RESOLVED)

> **Resolved 2026-08-14 at planning.** All five became recorded plan decisions in
> `49-01-PLAN.md`'s `<plan_decisions>` block — PD-01 … PD-05, each with a reversibility
> rating. The per-question resolutions are noted inline below. Question 5, which this
> document left genuinely unresolved, was closed by the planner reading
> `tests/unit/test_type_fidelity_table.py` directly.

1. **Does `.into()` accept any `type[BaseModel]`, or only `ArrowModel` subclasses?**
   → **PD-01** (rated *costly*): accepted as recommended — `.into()` takes any
   `type[BaseModel]` via `model_convert`.
   - What we know: `model_convert(PlainBaseModel, batch)` works [VERIFIED: executed], and
     `ArrowModel.convert` is just sugar over `ArrowModelConverter`.
   - What's unclear: whether Semolina wants to advertise plain-`BaseModel` support. Accepting
     both is one extra line (`model_convert(model, data, validate=validate)` instead of
     `model.convert(...)`), removes an inheritance requirement from users' existing DTOs, and
     makes Phase 50's generated class free to subclass whatever it likes.
   - Recommendation: **accept `type[BaseModel]`** and call `model_convert` / `ArrowModelConverter`
     rather than the classmethods. Document `ArrowModel` as unnecessary.

2. **Is an Arrow `int64` column into a `float`-annotated field a mismatch?**
   → **PD-02** (rated *reversible*): accepted as recommended — a mismatch, no numeric tower.
   - What we know: `issubclass(int, float)` is False [VERIFIED: executed]; the fast path really
     does leave an `int` there.
   - What's unclear: whether users will read this as pedantic.
   - Recommendation: treat as a mismatch, no special case, consistent with Decimal→float — but
     make it an explicit plan decision so it is not discovered in UAT.

3. **Cap polars below 2.0?**
   → **PD-03** (rated *costly*): accepted as recommended — `polars>=1.0.0`, uncapped, with a
   todo for the polars 2.0 return-shape break.
   - What we know: ADBC's `fetch_polars` already emits a `FutureWarning` saying its call shape
     returns a `Series` in polars 2.0 [VERIFIED: executed].
   - Recommendation: `polars>=1.0.0` with a note, and open a todo to revisit when polars 2.0
     lands. A cap in a published extra is itself a support burden.

4. **Does the pre-check read `description` or `fetch_arrow_table().schema` for `.into()`?**
   → **PD-04** (rated *reversible*): accepted as recommended — `description`. This is what lets
   the async `iter_into` stay a plain method rather than a coroutine.
   - What we know: both work; `description` works on both cursors with no reader and no await.
   - Recommendation: `description`, for one code path across four methods. Verify in the plan
     that `description` is still valid *after* `fetch_arrow_table()` (it is — measured for
     `fetch_df` then `description`).

5. **Does `tests/unit/test_type_fidelity_table.py` assert on literal artifact cells?**
   → **PD-05** (rated *reversible*): **no** — resolved at planning by reading the file.
   `_parse_comparison_table` bounds itself to `## Field type comparison` and breaks at the next
   `##`, so it never sees the Downstream Decimal rows; no edit to that test is needed.
   **But** the planner found a real trap in its place: `render_downstream_decimal`
   (`tests/type_fidelity_probe.py:1665-1680`) *generates* both the "A3 stays open" prose and the
   "pandas is not a declared dependency" caveat, and Phase 49 falsifies both — so editing the
   markdown artifact alone would fail `--check`. Assumption A6 is therefore closed, and the D-16
   task edits the generator, not just the artifact.
   - Original note: Unresolved. Read it before writing the D-16 task; if it does, the
     regeneration task must update it in the same commit (A6).

## Sources

### Primary (HIGH confidence)

- **Executed code, this session** — arrowmodel 1.0.0 in a scratch venv (13 experiment scripts:
  API surface, missing-column matrix, validate-path coercion matrix, 29-type
  `to_pylist` vs arrowmodel comparison, alias resolution against a committed cassette,
  pydantic `model_fields` introspection, `JsonValue` recursion, alignment-panic isolation);
  live in-memory DuckDB through `semolina.create_engine` / `create_async_engine` in `.venv`
  (reader-schema cost, `description` contents, native missing-polars errors, `fetch_polars`
  ordering hazards); polars 1.43.2 and 1.0.0 Decimal measurement.
- **Installed source, read this session** —
  `.venv/…/adbc_driver_manager/dbapi.py` (1233-1302, 1330-1450, 1479-1484),
  `.venv/…/adbc_driver_manager/_dbapi_backend.py` (125-264),
  `.venv/…/adbc_poolhouse/_async/_reader.py` (19-46, 80-86, 219-229),
  `.venv/…/adbc_poolhouse/_async/_cursor.py` (354-489).
- **Repo source, read this session** — `src/semolina/cursor.py`, `src/semolina/acursor.py`,
  `src/semolina/codegen/arrow_map.py`, `src/semolina/codegen/annotation_check.py`,
  `src/semolina/types.py`, `src/semolina/codegen/python_renderer.py:415-464`,
  `tests/type_fidelity_probe.py`, `tests/unit/test_async_packaging.py`,
  `tests/unit/codegen/test_python_renderer.py:1060-1095`, `tests/unit/test_public_surface.py`,
  `pyproject.toml`, `justfile`, `.github/workflows/ci.yml`,
  `semolina-jaffle-shop/pyproject.toml`.
- **PyPI JSON API** — arrowmodel, polars, pandas, pyarrow, pydantic release metadata.

### Secondary (MEDIUM confidence)

- `https://anentropic.github.io/arrowmodel/reference/api.html` — convert/iter signatures and
  the missing-column rule (independently reproduced by execution).
- `https://anentropic.github.io/arrowmodel/explanation/fast-vs-validated.html` — fast vs
  validated semantics, the "quietly wrong value" statement, benchmark figures (figures not
  independently reproduced).
- `https://anentropic.github.io/arrowmodel/how-to/iterate-large-datasets.html` — the
  per-batch streaming pattern.
- `https://anentropic.github.io/arrowmodel/` — landing page. Its "any Arrow-PyCapsule-compatible
  input" claim was **falsified** for polars input at 1.0.0.

### Tertiary (LOW confidence)

- `gsd-tools query package-legitimacy check` — returned `SUS` with all-null signals for every
  package including pandas and pyarrow; treated as uninformative and superseded by direct
  registry lookups.

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — every version read from PyPI this session; arrowmodel installed
  and exercised; polars floor verified by installing 1.0.0 and running the decimal case.
- arrowmodel API surface (Q1, Q4): **HIGH** — `inspect.signature` on the installed package plus
  13 executed experiments, cross-checked against published docs.
- Streaming schema cost (Q5): **HIGH** — poolhouse source quoted verbatim plus executed
  confirmation on both sync and async readers against a live DuckDB.
- polars Decimal (Q6): **HIGH** for the measurement; **MEDIUM** for the claim that no supported
  backend emits decimal256 (A2).
- Pre-check design (Q7): **HIGH** on the measured facts (annotation shapes, issubclass table,
  the `JsonValue` recursion, the arrowmodel/`to_pylist` agreement matrix); **MEDIUM** on the
  int→float recommendation, which is a judgement call flagged as Open Question 2.
- Test strategy (Q2): **HIGH** — both mechanisms quoted verbatim from files in this repo.
- Pitfalls: **HIGH** for 1, 2, 3, 5, 6; **MEDIUM** for 4 (alignment panic — reproduced but not
  on any warehouse driver path) and 7 (polars 2.0 — a FutureWarning, not yet a break).

**Research date:** 2026-08-13
**Valid until:** 2026-09-12 (30 days). Shorter for arrowmodel: a single 1.0.0 release five
weeks old, so a 1.1 could land inside this phase — re-run `pip index versions arrowmodel`
before pinning the floor.
