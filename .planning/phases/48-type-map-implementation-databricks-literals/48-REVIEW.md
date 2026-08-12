---
phase: 48-type-map-implementation-databricks-literals
reviewed: 2026-08-12T00:00:00Z
depth: deep
files_reviewed: 24
files_reviewed_list:
  - src/semolina/__init__.py
  - src/semolina/types.py
  - src/semolina/cli/__init__.py
  - src/semolina/cli/codegen.py
  - src/semolina/codegen/annotation_check.py
  - src/semolina/codegen/arrow_map.py
  - src/semolina/codegen/introspector.py
  - src/semolina/codegen/model_reader.py
  - src/semolina/codegen/probe.py
  - src/semolina/codegen/python_renderer.py
  - src/semolina/codegen/templates/python_model.py.jinja2
  - src/semolina/codegen/type_map.py
  - src/semolina/engines/databricks.py
  - src/semolina/engines/duckdb.py
  - src/semolina/engines/snowflake.py
  - src/semolina/engines/sql.py
  - docs/src/explanation/type-fidelity.rst
  - docs/src/how-to/codegen.rst
  - tests/type_fidelity_probe.py
  - tests/unit/codegen/conftest.py
  - tests/unit/codegen/test_annotation_check.py
  - tests/unit/test_annotation_contract.py
  - tests/unit/test_scope_fence.py
  - tests/unit/test_type_fidelity_duckdb.py
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-08-12
**Depth:** deep
**Files Reviewed:** 24
**Status:** issues_found

## Summary

The typed core of this phase is in good shape. `arrow_map.py` is correct against
`pyarrow` 24.0.0 on every predicate I could measure: `is_boolean` precedes `is_integer`,
`is_decimal` genuinely covers `decimal32`/`decimal64`/`decimal128`/`decimal256`, the three
string and four binary predicates are all needed, and every annotation it returns matches
what `RecordBatch.to_pylist()` actually produces (verified directly, including
`time64[ns] -> datetime.time`, `date64 -> datetime.date`,
`timestamp[ns] -> pandas.Timestamp`). `model_reader.py` really is parse-only — there is no
`import`, `importlib`, `exec`, or `compile` anywhere in it, and no fallback path. The
`isinstance` ordering in both `render_literal` bodies is right (`datetime` before `date`,
`bool` before `int`), the Spark escape order is backslash-then-quote, and both new arms
route through the single existing escaper rather than adding a second one. The scope fence
holds: `git diff 9f3c8b9..HEAD` names none of `cursor.py`, `acursor.py`, `results.py`, and
the only `Decimal(`/`float(`/`int(` hit in those three files is a docstring `print(...)`.
`test_scope_fence.py` is a real gate, and the `INTERVAL` xfails are `strict=True`.

Three defects do not survive contact, and all three are in the *reporting* and *emission*
paths rather than the mapping logic — which is exactly where a phase focused on type
correctness would be least likely to look.

- The drift table renders warehouse- and model-supplied strings through Rich's markup
  parser. `list[str] | None` prints as `list | None`, so two annotations that differ can
  print identically on a row marked `drift`, and a `[/tag]`-shaped token raises an
  unhandled `MarkupError`. Reproduced below.
- `--check` is the first code path to feed *catalogue-returned* field names back into
  `DuckDBSQLBuilder`, which interpolates them into `semantic_view('...')` with no escaping.
  Reproduced below. The escaper is pre-existing; the data flow that reaches it is new.
- The generated-model template interpolates a catalogue-supplied `source_name` into a
  double-quoted Python string literal with no escaping, so warehouse metadata can inject
  arbitrary module-level code into a file the documented workflow tells the user to import.
  This one is worth flagging precisely because this phase hardened the *sibling* channel —
  the new `type_comment` line collapses whitespace so a comment can never break out — and
  because `model_reader.py`'s docstring refuses to import a model file over threat T-48-19,
  which is the same risk viewed from the other end.

The remaining findings are narrower: `--check` parses `field_class` and `source_name` out
of the committed model and then never compares either, so a `Metric` -> `Dimension` change
or a changed `source=` reports `match`; the "no data rows" fixture does not wrap the one
fetch method the zero-row route actually calls; and three setup calls sit outside the
`try` block whose comment promises "any probe failure is a fallback, not a crash".

Everything I could check about the phase's claimed dispositions held except the two
security ones above. The probe query *is* builder-built (the builder is the weak link, not
the caller). The drift report *does* carry only names, types and routes — no row value is
in scope. The comment channel *is* newline-safe.

## Critical Issues

### CR-01: The drift report parses its own payload as Rich markup — annotations are silently truncated, and some field names crash the CLI

**File:** `src/semolina/cli/codegen.py:199-212`

**Issue:** `table.add_row(row.name, row.committed, row.probed, row.route, ...)` passes bare
`str` values to Rich, which renders them with `markup=True` (the `Console` default). Every
cell is therefore run through the markup parser before display. Two consequences, both
reproduced against the shipped `_render_check_report`:

1. **Silent truncation.** Any bracketed subscript is eaten as a style tag:

   ```
   semolina codegen --check: v
   ┏━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┓
   ┃ Field   ┃ Committed   ┃ Probed (result schema) ┃ Route          ┃ Status ┃
   ┡━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━┩
   │ payload │ list | None │ list | None            │ execute-schema │ drift  │
   └─────────┴─────────────┴────────────────────────┴────────────────┴────────┘
   ```

   The inputs were `committed='list[str] | None'` and `probed='list[int] | None'`. The
   verdict is right (the comparison is on the raw strings) but the report shows two
   identical cells beside the word `drift`, which is unreadable and unactionable. This is
   not a hypothetical annotation: `docs/src/how-to/codegen.rst` ("Handle TODO comments")
   instructs the reader to "replace `Any` with the type you want", and `list[str]`,
   `dict[str, Any]` and `tuple[int, ...]` are all mangled the same way.

2. **Unhandled crash.** A cell containing a closing-tag shape raises:

   ```
   CRASH: MarkupError closing tag '[/red]' at position 1 doesn't match any open tag
   ```

   Field names come from the warehouse catalogue and both Snowflake and DuckDB permit
   quoted identifiers with arbitrary characters. Nothing between `IntrospectedField.name`
   and `add_row` filters them, and `MarkupError` is caught nowhere, so this exits with a
   traceback rather than one of the file's carefully separated exit codes.

The same defect applies to `_stderr.print(f"...unavailable{detail}...")` on line 208-212,
where `detail` is `f"{type(e).__name__}: {e}"` — a driver error message such as
`Binder Error: Referenced column "x[0]" not found` goes through the same parser — and to
line 247-248, which interpolates `view_name!r`.

**Fix:** Wrap every interpolated value in `rich.text.Text`, which bypasses markup, and keep
the styling as a `Text` style argument rather than as embedded tags:

```python
from rich.text import Text

for row in report.rows:
    style = "red" if row.status == STATUS_DRIFT else "green"
    table.add_row(
        Text(row.name),
        Text(row.committed),
        Text(row.probed),
        Text(row.route),
        Text(row.status, style=style),
    )
```

and for the note, build the message as `Text.assemble(("Note: ", "yellow"), detail)` — or,
at minimum, `_stderr.print(..., markup=False)` for the interpolated portion. Add a
regression test asserting that `--check` on a model containing `Dimension[list[str]]()`
prints `list[str]` verbatim.

---

### CR-02: `--check` feeds catalogue-returned field names into an unescaped SQL string literal

**File:** `src/semolina/codegen/annotation_check.py:149,286-297` and `src/semolina/engines/sql.py:1258-1267`

**Issue:** `_canonical_model` builds a runtime model whose field `source=` values come
straight from `IntrospectedField.source_name` — i.e. from `DESCRIBE SELECT` / `SHOW COLUMNS`
output, which is warehouse-controlled. `_probe_view` then hands that model to
`builder.build_select_with_params`, and `DuckDBSQLBuilder` interpolates each resolved name
into a single-quoted SQL literal with no escaping at all:

```python
dims_list = ", ".join(f"'{n}'" for n in dim_names)     # sql.py:1258
sv_call = f"semantic_view('{view_name}', {', '.join(sv_args)})"   # sql.py:1267
```

Reproduced through the shipped call chain with a `source_name` of
`x') FROM read_csv('/etc/passwd') --`:

```
SELECT *
FROM semantic_view('v', dimensions := ['x') FROM read_csv('/etc/passwd') --'])
```

`probe.py:125` then wraps that verbatim: `SELECT * FROM ({sql}) WHERE 1=0`. `probe.py`'s
own module docstring asserts the safety property — "expected to come from a `SQLBuilder` /
`DuckDBSQLBuilder` `build_select_with_params` result … that wrapper adds no token of its own
to escape (threat T-48-14)". The wrapper is indeed clean; the builder it trusts is not.

The escaping defect in `sql.py` predates this phase. What is new is the data flow: before
Phase 48 a `source_name` reaching this builder came from a `source="..."` literal the user
typed into their own model file. `--check` is the first path that takes the warehouse's
answer and puts it back into SQL, which converts a latent quoting bug into a second-order
injection with a real (if privileged) source.

**Fix:** Give `DuckDBSQLBuilder` a string-literal escaper and route both the view name and
every field name through it, rather than fixing it at the `--check` call site:

```python
def _sql_str_literal(value: str) -> str:
    """Render a Python str as a DuckDB single-quoted literal."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"

dims_list = ", ".join(_sql_str_literal(n) for n in dim_names)
...
sv_call = f"semantic_view({_sql_str_literal(view_name)}, {', '.join(sv_args)})"
```

Add a unit test asserting that a field whose `source_name` contains `'` produces a literal
with the quote doubled and no additional SQL tokens.

---

### CR-03: A catalogue-supplied `source_name` injects arbitrary Python into the generated model

**File:** `src/semolina/codegen/templates/python_model.py.jinja2:13`

**Issue:** The template writes `source="{{ field.source_name }}"` with no escaping and no
Jinja autoescape (and Python autoescape would be wrong here anyway). `source_name` is
warehouse metadata. Reproduced through `render_views`:

```python
class V(SemanticView, view="v"):
    c = Dimension[str](source="A"); import os; os.system("id") #")
```

The input `source_name` was `A"); import os; os.system("id") #`. The generated file is
valid Python that executes at import time, and `docs/src/how-to/codegen.rst` documents the
workflow as writing this output to a file the user then imports. `view="{{ model.view_name }}"`
on line 10 has the same shape (argv-sourced, so lower value, but the same escape).

This template line is unchanged by the diff, so the defect is pre-existing. It belongs in
this review for three reasons. Phase 48 added a *new* warehouse-to-source channel
(`raw_type` -> `type_comment`) on the immediately preceding line, and correctly hardened it
(`" ".join(f.raw_type.split())` collapses every `str.isspace()` character, so a comment can
never break out - I checked, including U+2028 and U+0085, neither of which Python's
tokenizer treats as a line terminator anyway). Phase 48 also added
`model_reader.py`, whose docstring declines to import a model file precisely because
"importing runs whatever the file's module level contains … which in CI means running code
out of a repo checkout (threat T-48-19)" — the same risk from the writing end, unmitigated.
Hardening one channel while the adjacent one stays open is the kind of asymmetry a review
exists to catch.

**Fix:** Emit the string literal through `repr()` rather than through raw interpolation, so
quotes and backslashes are handled by Python's own escaper. Add a filter or precompute in
`_build_model_context`:

```python
# _FieldContext gains a pre-quoted field
source_literal=repr(f.source_name) if f.source_name is not None else None
```

```jinja
    {{ field.name }} = {{ field.field_class }}[{{ field.data_type }}](source={{ field.source_literal }})
```

Same treatment for `view_name`. Add a test rendering a field whose `source_name` contains
`"` and `\` and asserting the output round-trips through `ast.parse` with the original
string recovered.

## Warnings

### WR-01: `--check` parses the field role and `source=` override, then compares neither

**File:** `src/semolina/codegen/annotation_check.py:362-368`; `src/semolina/codegen/model_reader.py:59-62`

**Issue:** `CommittedField` carries `field_class` and `source_name`, and `_field_of` fills
both. `check_view` uses neither — it compares `committed_field.annotation` against
`probed_annotation` and nothing else. Two real drifts therefore report `match`:

- A committed `revenue = Dimension[int | None]()` against a warehouse `revenue` that is a
  metric. The probed side gets `metric_annotation("int")` -> `"int | None"`, the committed
  side reads `"int | None"`, verdict `match`. The model is wrong — the SQL builder will put
  the field in the wrong clause.
- A committed `country = Dimension[str](source="OLD")` against a warehouse
  `source_name="NEW"`. Both sides read `"str"`, verdict `match`, and every query the model
  builds selects a column that no longer exists.

Confirmed by reading; `grep` shows `CommittedField.field_class` and
`CommittedField.source_name` have no consumer anywhere in `src/`.

**Fix:** Extend the comparison to both attributes and give `FieldCheckRow` somewhere to
report them, e.g.:

```python
expected_class = _ROLE_TO_CLASS[field.field_type]  # 'Metric' | 'Dimension' | 'Fact'
status = (
    STATUS_MATCH
    if committed_field is not None
    and committed_annotation == probed_annotation
    and committed_field.field_class == expected_class
    and (committed_field.source_name or None) == (field.source_name or None)
    else STATUS_DRIFT
)
```

If comparing them is deliberately out of scope, delete the two unused `CommittedField`
attributes so the next reader does not assume they are load-bearing.

### WR-02: The "no data rows" guard does not wrap the method the zero-row route calls

**File:** `tests/unit/codegen/conftest.py:61`

**Issue:** `data_fetch_guard` monkeypatches `fetchall`, `fetchone`, `fetchmany` and
`fetch_arrow_table`. `probe.py:126`'s fallback branch calls `cursor.fetch_record_batch()`,
which is not in that list. The guard therefore proves nothing about the zero-row route —
and the zero-row route is the *only* route Databricks can take, and the one Snowflake takes
when parameters are bound. Every test that uses the fixture runs on DuckDB, which answers
`adbc_execute_schema`, so the fallback branch is never under the guard at all.

Today the fallback reads only `reader.schema` and closes, so nothing is fetched. The point
of a guard is to catch the change that breaks that.

**Fix:** Add `fetch_record_batch` to the patched names, and have the wrapper poison the
returned reader's `read_next_batch` / `read_all` rather than the call itself (the call has
to succeed for the schema read):

```python
for name in ("fetchall", "fetchone", "fetchmany", "fetch_arrow_table", "fetch_record_batch"):
    monkeypatch.setattr(cursor_cls, name, guarded(getattr(cursor_cls, name)))
```

and add a test that drives `probe_schema` down the fallback branch (monkeypatch
`adbc_execute_schema` to raise `NotSupportedError`) under the guard, so the branch is
exercised at least once on some backend.

### WR-03: Three setup calls sit outside the `try` that promises "any probe failure is a fallback, not a crash"

**File:** `src/semolina/codegen/annotation_check.py:286-307`

**Issue:** The broad `except Exception` at line 303 carries an explicit comment: "any probe
failure is a fallback, not a crash … the caller's alternative is a traceback for a mode
whose whole job is to report". But `engine.dialect.create_builder()` (286),
`_field_groups(...)` (287) and `_canonical_model(view)` (288) all run before the `try`. An
exception from any of them escapes `check_view`, escapes `_run_check`'s three narrow
`except` clauses, and produces exactly the traceback the design says it is avoiding.

`_canonical_model` is the plausible one: it does `role_to_class[f.field_type]` (KeyError on
an unexpected role) and constructs a class via `SemanticViewMeta` with a namespace keyed on
catalogue-supplied field names, which can collide with `SemanticView`'s own attributes — a
view with a column named `query` would shadow `model.query()` and make `_build_query` fail
at line 196.

**Fix:** Move the three calls inside the `try`:

```python
    schemas: list[pyarrow.Schema] = []
    route = ROUTE_METADATA
    try:
        builder = engine.dialect.create_builder()
        groups = _field_groups(view, split_facts=isinstance(builder, DuckDBSQLBuilder))
        model = _canonical_model(view)
        with engine.connect() as conn:
            ...
```

### WR-04: The route label is the last group's route, and committed-only rows get a route that never looked at them

**File:** `src/semolina/codegen/annotation_check.py:296-300,380-389`

**Issue:** Two smaller labelling defects in a feature whose stated point is that "the route
is always reported" (module docstring, threat T-48-24):

- Inside the group loop, `route = probed.route` overwrites on each iteration, so a
  two-group DuckDB probe that answered `execute-schema` for the metrics and fell back to
  `zero-row` for the facts reports `zero-row` for *both* groups' fields. The route becomes
  a claim about the last query rather than about the row it labels.
- The trailing loop over `committed_fields` (fields the warehouse does not have) labels each
  row with `route` — typically `execute-schema` — even though no probe examined that field.
  `probed` is `ABSENT`, so nothing was resolved by any route.

**Fix:** Record the route per schema and carry it alongside, e.g. return
`list[tuple[pyarrow.Schema, str]]` from `_probe_view` and set `field_route` from the entry
that produced the hit. For the trailing loop, use a distinct label (`ABSENT`, or a new
`ROUTE_NOT_PROBED`) rather than borrowing the probe's.

### WR-05: Exit code 2's documentation is now false in two places

**File:** `src/semolina/cli/__init__.py:26`; `docs/src/how-to/codegen.rst` (Exit codes tip)

**Issue:** `_resolve_check_model` raises `typer.BadParameter` for the `--check`/`--model`
mispairing, which `codegen()` converts to `EXIT_INVALID_BACKEND` (2). The `--help` epilog
still reads "`2` Invalid `--backend` value (or omitted)", and the how-to's tip still reads
"Both cases mean 'the backend could not be resolved.'" There is now a third case that has
nothing to do with the backend. The how-to's `--check` section does say "Either flag on its
own exits `2`", so the page contradicts itself.

**Fix:** Reword both to "Invalid option — an unrecognised or omitted `--backend`, or
`--check`/`--model` passed without its partner", and drop or amend the "both cases" tip.

### WR-06: `_arrow_annotation` treats a duplicate column name as an absent one

**File:** `src/semolina/codegen/annotation_check.py:248-253`

**Issue:** `pyarrow.Schema.get_field_index` returns `-1` both when the name is missing *and*
when the schema carries several fields with that name. The `index >= 0` test cannot tell
them apart, so a result schema with a duplicated column name silently sends that field to
the metadata route. The row is labelled `metadata`, so it is not silent-silent — but the
CLI's note says "the result-schema probe was unavailable", which is not what happened, and
the note only fires because *some* row took the metadata route.

**Fix:** Use `schema.get_all_field_indices(name)` and branch explicitly:

```python
indices = schema.get_all_field_indices(name)
if len(indices) == 1:
    mapped = arrow_type_to_python(schema.field(indices[0]).type)
    return mapped if mapped is not None else _UNMAPPED_ANNOTATION
if len(indices) > 1:
    return _UNMAPPED_ANNOTATION  # ambiguous, and say so rather than falling back silently
```

## Info

### IN-01: Encoding-only Arrow types other than `dictionary` fall through to `Any`

**File:** `src/semolina/codegen/arrow_map.py:77-82,110`

**Issue:** `is_dictionary` recurses into `value_type`, with a good comment explaining why.
`run_end_encoded` is the other pure-encoding type in `pyarrow` and it falls off the end to
`None` — I measured `arrow_type_to_python(pyarrow.run_end_encoded(int32, string))` as `None`
where `str` would be the honest answer. No driver in this repo produces REE today, so this
is a note rather than a defect.

**Fix:** Either add `if pyarrow.types.is_run_end_encoded(dtype): return arrow_type_to_python(dtype.value_type)`
alongside the dictionary arm, or extend the module docstring's `None` list to name it, so
the omission reads as a decision.

### IN-02: The Snowflake cassette path is resolved relative to the current working directory

**File:** `tests/unit/codegen/test_annotation_check.py:431-434,472`

**Issue:** `SNOWFLAKE_PROBE_CASSETTE` is a bare relative string and `_recorded_schema` does
`pathlib.Path(SNOWFLAKE_PROBE_CASSETTE) / "000_result.arrow"`. Running pytest from anywhere
other than the repo root makes the whole Snowflake half error out. The sibling modules
already solve this (`type_fidelity_probe.resolve_artifact_path`,
`test_type_fidelity.REPO_ROOT = Path(__file__).resolve().parents[2]`).

**Fix:** Anchor on `Path(__file__).resolve().parents[3]` like the other modules do.

### IN-03: `tests/type_fidelity_probe.py` may carry imports left behind by the promotion

**File:** `tests/type_fidelity_probe.py`

**Issue:** The promotion removed `ProbeResult` (a `@dataclass`) and `probe_schema` from this
module. `dataclass` and `pyarrow` were imported for them. Ruff passes, so they must still
have a consumer, but this is the kind of residue a promotion leaves and it is worth a
deliberate look rather than trusting F401 alone (both names are plausibly still used
elsewhere in a 1800-line module).

**Fix:** Confirm each remaining import in the module header still has a use, and drop any
that does not.

---

_Reviewed: 2026-08-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
