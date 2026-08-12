# Phase 48: Type Map Implementation & Databricks Literals - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 17 (3 created, 14 modified)
**Analogs found:** 17 / 17 (every new file has a strong in-repo sibling)

This file is the **analog + excerpt** layer. `48-RESEARCH.md` already names the touched
surface with line numbers; this document says *what existing code each new or edited file
should look like*, with the excerpt to copy from.

## File Classification

### Created

| New file | Role | Data flow | Closest analog | Match quality |
|---|---|---|---|---|
| `src/semolina/codegen/arrow_map.py` | utility (pure function layer) | transform | `src/semolina/codegen/type_map.py` | exact — same package, same "X → Python annotation string" contract |
| `src/semolina/codegen/probe.py` | service (driver I/O) | request-response | `tests/type_fidelity_probe.py:178-262` (the source being moved) + `src/semolina/codegen/introspector.py` for the module shape | exact — it is a promotion, not a rewrite |
| `tests/unit/codegen/test_arrow_map.py` | test | transform | `tests/unit/codegen/test_type_map.py` | exact — sibling test for the sibling module |
| probe-circularity test (recommend adding to `tests/unit/test_type_fidelity_table.py`, which already owns the circularity guard) | test | transform | `tests/unit/test_type_fidelity_table.py::test_result_and_mapped_vocabularies_are_disjoint` (line 220) | exact — same defence, new location |

### Modified

| File | Role | Data flow | Closest in-file analog to copy | Match quality |
|---|---|---|---|---|
| `src/semolina/codegen/type_map.py` | utility | transform | its own three existing map/function pairs | exact |
| `src/semolina/codegen/python_renderer.py` | service (renderer) | transform | its own `_build_model_context` / `render_views` seam | exact |
| `src/semolina/codegen/templates/python_model.py.jinja2` | template | transform | its own two `{% if %}` import blocks | exact |
| `src/semolina/engines/sql.py` (`Dialect.render_literal`, `DatabricksDialect.render_literal`) | model (dialect) | transform | the two existing `render_literal` bodies (they are already near-twins) | exact |
| `src/semolina/cli/codegen.py` | controller (CLI command) | request-response | its own `codegen()` signature + `_resolve_backend` error pattern | exact |
| `src/semolina/cli/__init__.py` | config (command registration) | — | its own `app.command("codegen", epilog=...)` block | exact |
| `src/semolina/__init__.py` | config (public export surface) | — | its own import block + `__all__` | exact |
| `tests/unit/codegen/test_type_map.py` | test | transform | its own `Test*` classes + `test_all_*_mappings` parametrize | exact |
| `tests/unit/codegen/test_python_renderer.py` | test | transform | existing renderer tests | exact |
| `tests/unit/codegen/test_codegen_e2e.py` + `__snapshots__/test_codegen_e2e.ambr` | test / snapshot | transform | its own three tests | exact |
| `tests/unit/codegen/test_cli.py` | test | request-response | `test_cli.py` `CliRunner` + `make_mock_engine`; `test_codegen_e2e.py::test_codegen_file_backed_duckdb` for the live-DuckDB CLI route | exact |
| `tests/unit/test_sql.py` | test | transform | `TestRenderLiteralDatabricks` (line 188) / `TestRenderLiteralStandardSql` | exact |
| `tests/unit/test_type_fidelity_duckdb.py` | test | request-response | its own `test_decimal_metric_disagrees_by_value` (line 120) | exact |
| `tests/unit/test_type_fidelity_table.py` | test | transform | its own guards (lines 204-233) | exact |
| `tests/type_fidelity_probe.py` | utility (evidence generator) | transform | its own module docstring contract (lines 10-21) | exact |
| `docs/src/explanation/type-fidelity.rst` | docs (Explanation) | — | the page itself | exact |
| `docs/src/how-to/codegen.rst` | docs (How-to) | — | its own § "Exit codes" list-table (lines 293-317) | exact |

### Fenced off — do NOT touch

`src/semolina/cursor.py`, `src/semolina/acursor.py`, `src/semolina/results.py` are prohibited by
`48-CONTEXT.md` `<scope_fence>`. No pattern below implies an edit there. If a plan finds itself
wanting to make a *value* match an annotation, that is the fence, not a missing pattern: the
annotation is corrected to the value, never the reverse.

---

## Pattern Assignments

### `src/semolina/codegen/arrow_map.py` — CREATED (utility, transform)

**Analog:** `src/semolina/codegen/type_map.py` (whole file, 199 lines, read in full).

Structure to copy, in order: module docstring stating the contract *and* what a miss means →
`from __future__ import annotations` → module-level `_MAP` dict with a comment explaining key
casing → public function with a full Google docstring. **No `__all__`** — no module under
`src/semolina/codegen/` defines one (verified: `grep -rn "^__all__" src/semolina` returns only
`__init__.py`, `testing/__init__.py`, `engines/__init__.py`).

**Module docstring pattern** (`type_map.py:1-10`) — note it names the None-return contract:

```python
"""
SQL type to Python annotation mapping for Snowflake, Databricks, and DuckDB.

Converts the type metadata returned by warehouse introspection APIs into
Python annotation strings suitable for use in generated SemanticView code.
Types without clean Python equivalents (GEOGRAPHY, VARIANT, ARRAY, etc.)
return None, which signals the renderer to emit a TODO comment instead.
"""

from __future__ import annotations
```

**Module-level map pattern with a keys-casing comment** (`type_map.py:137-160`):

```python
# DuckDB SQL type names → Python annotation strings.
# Keys are uppercase. DuckDB returns uppercase type names from DESCRIBE SELECT.
_DUCKDB_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "str",
    ...
}
```

A dict does **not** work for `arrow_type_to_python` — `pyarrow.DataType` instances are
parameterised (`decimal128(38, 2)`, `timestamp[us, tz=Europe/London]`), so the body must be an
ordered `if pyarrow.types.is_*(dtype)` cascade, not a lookup. Keep the *docstring and return
contract* identical to the dict-backed functions: `-> str | None`, `None` meaning "no clean
Python equivalent". Retaining `str | None` (rather than raising) lets the caller construct its
own `TODO: {dtype}` string exactly as the three engines already do.

**Public-function docstring pattern** (`type_map.py:163-194`) — the full shape to copy:

```python
def duckdb_type_to_python(type_name: str) -> str | None:
    """
    Map a DuckDB SQL type name to a Python annotation string.

    DuckDB's ``DESCRIBE SELECT`` output returns type names as plain strings
    (e.g., ``'VARCHAR'``, ``'BIGINT'``, ``'TIMESTAMP WITH TIME ZONE'``).
    Parameterized types like ``'DECIMAL(10,2)'`` or ``'VARCHAR(255)'`` have
    their parenthesized suffix stripped before lookup, so ``'VARCHAR(255)'``
    correctly maps to ``'str'``.

    Args:
        type_name: Raw SQL type name from DuckDB ``DESCRIBE SELECT`` output.

    Returns:
        Python annotation string (e.g., ``'int'``, ``'str'``,
        ``'datetime.datetime'``), or ``None`` if the type has no clean
        Python equivalent (DECIMAL, STRUCT, MAP, LIST, UNION, ARRAY,
        or any unknown type name). ``None`` signals the renderer to emit a
        TODO comment in the generated output.

    Example:
        .. code-block:: python

            from semolina.codegen.type_map import duckdb_type_to_python

            duckdb_type_to_python("VARCHAR")
            # 'str'
            duckdb_type_to_python("BIGINT")
            # 'int'
            duckdb_type_to_python("DECIMAL(10,2)")
            # None
    """
```

**Doctest safety — an important correction to a RESEARCH.md worry.** `48-RESEARCH.md` warns that
`--doctest-modules` executes `Example:` blocks. It does **not** execute these ones: the house
style in `codegen/` uses a bare call followed by a `# 'str'` result *comment*, with no `>>>`
prompt, so pytest's doctest collector never sees an example. (`>>>` doctests do exist elsewhere
in `src/` — `models.py:70`, `fields.py:268` — so both styles are live in the repo. For
`arrow_map.py` and `probe.py`, copy the **comment style above**; it is the convention of the
package they join and it sidesteps the executed-example risk entirely.)

**`pyarrow` typing under basedpyright strict** — copy the `TYPE_CHECKING` import convention
from `python_renderer.py:15-20`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView
```

Note the counter-example: `tests/type_fidelity_probe.py:44` imports `pyarrow` at **module
scope** (unconditionally), because `ProbeResult.schema: pyarrow.Schema` is a runtime dataclass
field. `arrow_map.py` needs `pyarrow.types` at runtime for the predicates, so it too imports
`pyarrow` at module scope — the `TYPE_CHECKING` block is only for annotation-only imports.

---

### `src/semolina/codegen/probe.py` — CREATED (service, request-response)

**Analog:** the exact source at `tests/type_fidelity_probe.py:178-262`. This is a **move**, not
a rewrite. Verbatim, the region to relocate (module constants, the error resolver, the
dataclass, the function):

```python
# -- Result half: schema probing. Must not import semolina.codegen.type_map ---------------

ROUTE_EXECUTE_SCHEMA = "execute-schema"
"""Probe route: the driver answered ``adbc_execute_schema`` directly."""

ROUTE_ZERO_ROW = "zero-row"
"""Probe route: the driver refused ``ExecuteSchema``, so a ``WHERE 1=0`` execution was used."""


def _resolve_not_implemented_errors() -> tuple[type[Exception], ...]:
    """
    Read the installed driver manager's exception classes for a refused ``ExecuteSchema``.

    Resolved from the installed package rather than assumed. In ``adbc_driver_manager``
    1.10.0 the DBAPI hierarchy is ``Error(Exception)`` ->
    ``DatabaseError`` -> ``{NotSupportedError, ProgrammingError, OperationalError, ...}``.
    ``NotSupportedError`` is the documented DBAPI mapping for ``StatusNotImplemented``, but
    it was never exercised against a refusing driver, so ``ProgrammingError`` and
    ``OperationalError`` are included: they are the two classes the manager also uses for
    driver-side status codes, and catching all three makes the fallback fire regardless of
    which one a given driver's status is mapped onto.

    Returns:
        The exception classes that mean "this driver will not answer ``ExecuteSchema``".
    """
    import adbc_driver_manager

    return (
        adbc_driver_manager.NotSupportedError,
        adbc_driver_manager.ProgrammingError,
        adbc_driver_manager.OperationalError,
    )


NOT_IMPLEMENTED_ERRORS: tuple[type[Exception], ...] = _resolve_not_implemented_errors()
"""
Exception classes that mean the driver refused ``ExecuteSchema``.

See :func:`_resolve_not_implemented_errors` for the resolved hierarchy and the installed
version it was read from.
"""


@dataclass(frozen=True)
class ProbeResult:
    """
    A probed result schema plus the route that produced it.

    Attributes:
        schema: The query's result schema, as the driver resolved it.
        route: :data:`ROUTE_EXECUTE_SCHEMA` or :data:`ROUTE_ZERO_ROW`. Recorded so the
            artifact's provenance cell is measured rather than assumed.
    """

    schema: pyarrow.Schema
    route: str


def probe_schema(cursor: Any, sql: str, params: list[Any]) -> ProbeResult:
    """
    Return a query's result schema without depending on Semolina's type map.

    Prefers ADBC ``ExecuteSchema``; falls back to a zero-row execution for drivers that
    answer ``NOT_IMPLEMENTED`` (Databricks) or that reject bound parameters (Snowflake).

    Args:
        cursor: An ADBC DBAPI cursor.
        sql: The query whose result schema is wanted.
        params: Bind parameters for that query. Pass ``[]`` rather than ``None`` — under
            cassette replay the parameter list is part of the lookup key.

    Returns:
        The resolved schema and the route that produced it.
    """
    try:
        schema = cursor.adbc_execute_schema(sql, params)
    except NOT_IMPLEMENTED_ERRORS:
        cursor.execute(f"SELECT * FROM ({sql}) WHERE 1=0", params or None)
        reader = cursor.fetch_record_batch()
        try:
            fallback_schema = reader.schema
        finally:
            reader.close()
        return ProbeResult(schema=fallback_schema, route=ROUTE_ZERO_ROW)
    return ProbeResult(schema=schema, route=ROUTE_EXECUTE_SCHEMA)
```

Move-mechanics notes for the planner:

- The banner comment `# -- Result half: ... Must not import semolina.codegen.type_map` at
  `tests/type_fidelity_probe.py:178` is the anti-circularity contract in prose. It must travel
  with the code and become the new module's **docstring**, not be left behind.
- The imports the moved region needs, present at `tests/type_fidelity_probe.py:40-44`:
  `from dataclasses import dataclass`, `from typing import Any`, `import pyarrow`.
  `adbc_driver_manager` stays a function-local import inside `_resolve_not_implemented_errors`.
- After the move, `tests/type_fidelity_probe.py` re-imports the four names. Its own module
  docstring at lines 10-21 explicitly describes the metadata half / result half split and names
  `probe_schema` — update that prose to point at the new location:

  ```
  * the **result half** — :func:`probe_schema`. It must never import
    ``semolina.codegen.type_map`` or any symbol from it. ...
  ```
- `tests/unit/test_type_fidelity_duckdb.py` imports `probe_schema` too (used at line 130) — its
  import must follow.

---

### The probe-circularity test — CREATED (test, transform)

**Analog:** `tests/unit/test_type_fidelity_table.py:220-233`. That module *already is* the
circularity-guard home; it opens by declaring the two things it polices (lines 4-8), so a new
"the promoted module does not import the type map" test belongs there rather than in a new file.

**Guard-test pattern to copy** — note the shape: a docstring naming the defence, an inline
comment explaining *why it is a guard rather than a formatting check*, and an assertion message
that says what an overlap would mean:

```python
def test_result_and_mapped_vocabularies_are_disjoint() -> None:
    """The result column and the mapped column never share a value (RESEARCH.md defence 3)."""
    # Circularity guard, not a formatting check. Arrow type names (`decimal128(38, 2)`,
    # `int64`, `double`) and Python annotation strings (`int`, `float`, `datetime.date`) are
    # two vocabularies. An overlap means one column is being sourced from the other, which
    # would make the whole artifact a restatement of Semolina's own type map.
    header, rows = _parse_comparison_table(ARTIFACT_PATH.read_text(encoding="utf-8"))
    mapped = set(_column(header, rows, MAPPED_COLUMN))
    result = set(_column(header, rows, RESULT_COLUMN))

    assert mapped.isdisjoint(result), (
        f"Result and mapped vocabularies overlap on {sorted(mapped & result)} — "
        "one column is being sourced from the other."
    )
```

The module already imports `re` at top level (line 17) for its own parsing, so an `ast`-walk
import for the new test is stylistically at home. `48-RESEARCH.md` offers two implementations
(`ast`-walk of `probe.py`'s source, or an `importlib`/`sys.modules` attribute check); the
`ast` route matches this module's existing "read the artifact text and parse it" habit and
needs no import side effects.

---

### `src/semolina/codegen/type_map.py` — MODIFIED (utility, transform)

Three edit sites. All are in-file self-analogs; the shape already exists.

**Site 1 — the Snowflake `FIXED` branch** (`type_map.py:84-94`, verbatim). The `scale` read
disappears entirely under Decision 1:

```python
    raw_type = type_json.get("type")
    if not isinstance(raw_type, str):
        return None

    type_name = raw_type.upper()

    if type_name == "FIXED":
        scale = type_json.get("scale", 0)
        return "int" if scale == 0 else "float"

    return _SNOWFLAKE_TYPE_MAP.get(type_name)
```

Its docstring (lines 51-54 and the `Example:` at 68-83) states the scale rule twice and shows
`{"type": "FIXED", "scale": 0}` → `'int'`. **Both must change with the code** — the `Example:`
block is user-facing via sphinx-autoapi.

**Site 2 — the Databricks map entry** (`type_map.py:38`), inside `_DATABRICKS_TYPE_MAP`:

```python
    "decimal": "float",
```

`databricks_type_to_python` (lines 129-134) currently reads only `name`:

```python
    raw_name = type_obj.get("name")
    if not isinstance(raw_name, str):
        return None

    type_name = raw_name.lower()
    return _DATABRICKS_TYPE_MAP.get(type_name)
```

An `interval` needing `start_unit`/`end_unit` requires a pre-lookup branch here. The pattern for
"a type that needs more than the name" is the Snowflake `FIXED` branch above: a named
`if type_name == "...":` guard placed *before* the dict lookup, reading extra keys off the dict
with `.get(...)` and a default. Copy that shape; the isinstance-guard-then-normalise preamble is
already correct.

**Site 3 — `_DUCKDB_TYPE_MAP`** (`type_map.py:139-160`) plus the parameter-stripping line
(`type_map.py:195-199`, verbatim) that decides what the new keys must be spelled as:

```python
    # Strip parenthesized type parameters: "DECIMAL(10,2)" -> "DECIMAL",
    # "VARCHAR(255)" -> "VARCHAR". Space-separated qualifiers like
    # "TIMESTAMP WITH TIME ZONE" are preserved since they contain no parens.
    base = type_name.split("(")[0].strip().upper()
    return _DUCKDB_TYPE_MAP.get(base)
```

Consequence for the planner: `DECIMAL(10,2)` and `ENUM('sad','ok','happy')` both arrive
pre-stripped, so the new keys are bare `"DECIMAL"` and `"ENUM"` — **no new stripping logic is
needed**, and adding some would be the wrong instinct.

**Where `TODO:` is born — do not move it.** The three engines construct it; `type_map.py` never
does. Verbatim from the three call sites, so the planner can see they are already consistent and
need no change:

```python
# src/semolina/engines/snowflake.py:178
data_type = f"TODO: {d['data_type']}" if py_type is None else py_type
# src/semolina/engines/databricks.py:190
data_type = py_type if py_type is not None else f"TODO: {raw_type_name}"
# src/semolina/engines/duckdb.py:239
data_type = py_type if py_type is not None else f"TODO: {sql_type}"
```

Every key this phase adds to a map removes one `TODO:` at these sites, with no edit here.
`48-CONTEXT.md` D-03 asks for the raw warehouse type to be preserved in a comment or docstring
once the `TODO:` disappears — note that the `TODO:` comment channel is the *only* place the raw
type survives into generated source today (`python_renderer.py:103-107`), so preserving it for a
now-mapped type needs a new mechanism, not a reuse.

---

### `src/semolina/codegen/python_renderer.py` — MODIFIED (service, transform)

**Analog:** the file's own three-stage seam. Read in full this session.

**The nullability decoration site** — `_build_model_context` (`python_renderer.py:100-125`),
verbatim. Decision 2's `| None` goes on `data_type_str` here, after the `TODO:` branch:

```python
    fields: list[_FieldContext] = []
    for f in view.fields:
        todo_comment = ""
        if f.data_type is not None and f.data_type.startswith("TODO:"):
            # Collapse any whitespace (including embedded newlines from
            # pretty-printed warehouse type descriptors) so the comment can
            # never span multiple physical lines and break the generated code.
            todo_comment = " ".join(f.data_type.split())

        # Map IntrospectedField.data_type to Python type string for Generic subscript.
        # None data_type (unmapped warehouse type) → "Any" so generated code is valid.
        if f.data_type is None or f.data_type.startswith("TODO:"):
            data_type_str = "Any"
        else:
            data_type_str = f.data_type

        fields.append(
            _FieldContext(
                name=f.name,
                field_class=_field_class_for(f.field_type),
                ...
```

Note `field_class` is resolved right here from `f.field_type` via `_field_class_for` — so the
"is this a metric?" test the `| None` needs is already available at exactly this point. That is
why this is the correct seam and the map is not.

**The import-emission landmine** — `python_renderer.py:23` and `:174-198`, verbatim:

```python
_DATETIME_TYPES = frozenset({"datetime.date", "datetime.datetime", "datetime.time"})
```

```python
    # Determine whether any field requires datetime or Any imports
    needs_datetime = any(f.data_type in _DATETIME_TYPES for view in views for f in view.fields)
    # needs_any: True when any field has no clean Python type mapping (data_type is None
    # or starts with "TODO:" — both map to "Any" in the template)
    needs_any = any(
        f.data_type is None or f.data_type.startswith("TODO:")
        for view in views
        for f in view.fields
    )

    models = [_build_model_context(v) for v in views]

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.get_template("python_model.py.jinja2")
    return template.render(  # type: ignore[no-any-return]
        models=models,
        needs_datetime=needs_datetime,
        needs_any=needs_any,
    )
```

Three facts the planner needs from this excerpt, all visible in it:

1. `needs_datetime` is an **exact-string membership test** against a `frozenset`, evaluated on
   `f.data_type` — the *raw introspected* value, read from `views` **before**
   `_build_model_context` runs (`models = [...]` is the next statement). So a `| None` applied
   anywhere upstream silently drops `import datetime`. This is RESEARCH pitfall 1.
2. Both booleans read `views`, not `models`. Deriving imports from the **resolved**
   `_FieldContext.data_type` means reordering these two statements so `models` is computed
   first, then scanning `models`. That reordering is the actual change, and it is small.
3. The `# type: ignore[no-any-return]` on `template.render(...)` is a pre-existing,
   pyproject-sanctioned exemption in this file — it is not a licence to add more, but the plan
   should not treat its presence as a defect to fix.

**The `from semolina import ...` line is hard-coded in the template**, so `JsonValue` cannot
arrive by the same prefix rule as `decimal`/`datetime`. See the template section below.

---

### `src/semolina/codegen/templates/python_model.py.jinja2` — MODIFIED (template, transform)

**Analog:** the file's own existing import block, verbatim (whole file is 26 lines):

```jinja
{% if needs_datetime %}
import datetime
{% endif %}
{% if needs_any %}
from typing import Any
{% endif %}
from semolina import SemanticView, Metric, Dimension, Fact
{% for model in models %}
```

Pattern for a new stdlib import (`decimal`): one more `{% if %}` block, or — per RESEARCH's
recommendation — replace all of them with a single `{% for line in imports %}`. Either matches
the file's style; the loop is the one that survives Phase 50.

**The `JsonValue` wrinkle, made concrete by the snapshot.** The template emits
`from semolina import SemanticView, Metric, Dimension, Fact` (unsorted), but the committed
snapshot at `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr:4` reads:

```
from semolina import Dimension, Fact, Metric, SemanticView
```

So `format_with_ruff`'s isort pass **does** rewrite and sort that line — but only when the
optional `codegen-lint` extra is installed (`ruff_available()`, `python_renderer.py:201-212`);
otherwise the raw template output ships. ruff's isort does not merge two separate `from semolina
import` statements, so emitting a second one would produce duplicate-looking output in the
no-ruff path. Build the single `from semolina import ...` line from a set in the template
context.

---

### `src/semolina/engines/sql.py` — MODIFIED (model/dialect, transform)

*(Note: `48-CONTEXT.md` and the mapping brief say `src/semolina/sql.py`; the file is actually
`src/semolina/engines/sql.py`. There is no `src/semolina/sql.py`. `src/semolina/dialect.py`
exists separately and is not this.)*

**Analog:** the two `render_literal` bodies are already structural twins differing only in the
bool casing and the escape rule. Widen both identically (D-07).

**Base `Dialect.render_literal`** (`sql.py:111-128`), verbatim — the branch order to preserve
and the insertion point (new branches go after `str`, before the `NotImplementedError` tail):

```python
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, float) and not math.isfinite(value):
            msg = f"Cannot render non-finite float as a SQL literal: {value!r}."
            raise ValueError(msg)
        if isinstance(value, int | float):
            return repr(value)
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        type_name = type(cast("object", value)).__name__
        msg = (
            f"Cannot render SQL literal for unsupported type: {type_name}. "
            f"Add handling in render_literal() for this type."
        )
        raise NotImplementedError(msg)
```

**`DatabricksDialect.render_literal`** (`sql.py:409-426`), verbatim — identical skeleton, two
differences (lowercase bools, backslash-first escaping):

```python
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float) and not math.isfinite(value):
            msg = f"Cannot render non-finite float as a SQL literal: {value!r}."
            raise ValueError(msg)
        if isinstance(value, int | float):
            return repr(value)
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        type_name = type(cast("object", value)).__name__
        msg = (
            f"Cannot render SQL literal for unsupported type: {type_name}. "
            f"Add handling in render_literal() for this type."
        )
        raise NotImplementedError(msg)
```

Patterns this excerpt supplies for the three new branches:

- **The subclass-ordering precedent is already in the file.** `isinstance(value, bool)` is
  checked *before* `int | float` precisely because `bool` subclasses `int`. `datetime.datetime`
  subclasses `datetime.date` in exactly the same way — put `datetime` first, and cite the
  existing bool branch as the in-repo precedent (RESEARCH pitfall 2).
- **The non-finite rejection pattern to mirror for `Decimal`** is the float branch verbatim:
  a guard `isinstance(...) and not <finite>` raising `ValueError` with an f-string
  `msg` assigned to a local first. For `Decimal`, the predicates are `.is_nan()` /
  `.is_infinite()`. Keep the same message wording shape.
- **`math` is already imported** at module scope (used at `:115` and `:413`). `datetime` and
  `decimal` will need adding — check whether they are already imported before adding.
- Route every new value through `f"'{escaped}'"` via the same string branch so `sql.py:91-93`'s
  claim ("this is the single audited SQL-literal escaping site") stays true.

**No call site changes.** `SQLBuilder._render_literal_sql` (`sql.py:843-880`) is fully generic —
it zips segments with `self.dialect.render_literal(param)` and knows nothing about types:

```python
        out = [segments[0]]
        for segment, param in zip(segments[1:], params, strict=True):
            out.append(self.dialect.render_literal(param))
            out.append(segment)
        return "".join(out)
```

and its caller (`sql.py:838-841`):

```python
        sql = "\n".join(parts)
        if not self.dialect.supports_parameterized_queries:
            return self._render_literal_sql(sql, all_params), []
        return sql, all_params
```

Widening `render_literal` is therefore sufficient for the end-to-end DBX-04 claim, and the
`, []` empty-params return is what the inlining test asserts.

---

### `src/semolina/cli/codegen.py` — MODIFIED (controller, request-response)

**Analog:** the file's own `codegen()` signature and error-handling body.

**Exit-code constant pattern** (`codegen.py:22-27`), verbatim — note the block comment that
documents the Typer collision. A new `EXIT_ANNOTATION_DRIFT = 5` goes here, with the same
comment-above-the-constants habit:

```python
# Exit code constants for scripted callers.
# Note: Typer also uses exit code 2 for missing required arguments (fires earlier).
# EXIT_INVALID_BACKEND=2 fires when --backend value is provided but unrecognized.
EXIT_INVALID_BACKEND = 2
EXIT_VIEW_NOT_FOUND = 3
EXIT_CONNECTION_ERROR = 4
```

**Stdout/stderr split** (`codegen.py:17-20`), verbatim — the convention a `--check` report must
follow (drift report to stderr; stdout stays clean):

```python
# Diagnostics-only console: writes to stderr
# NOTE: _stderr is module-level for error messages outside the command function.
# Python source output uses typer.echo() so CliRunner captures it correctly.
_stderr = Console(file=sys.stderr, stderr=True)
```

**Option-declaration pattern** (`codegen.py:151-159`) — the `Annotated[... , typer.Option(...)]`
shape for the new `--check` flag and `--model PATH`:

```python
    database: Annotated[
        str | None,
        typer.Option(
            "--database",
            "-d",
            help="DuckDB database file path (or set DUCKDB_DATABASE env var)",
            envvar="DUCKDB_DATABASE",
        ),
    ] = None,
```

**The "reject an invalid option combination" pattern** — `_resolve_backend` raises
`typer.BadParameter` (`codegen.py:98-102`):

```python
        if backend_spec == "duckdb":
            if database is None:
                raise typer.BadParameter(
                    "DuckDB backend requires a database path. "
                    "Use --database or set DUCKDB_DATABASE environment variable."
                )
```

and the command body converts it to an exit code (`codegen.py:164-168`):

```python
    try:
        engine = _resolve_backend(backend, database=database)
    except typer.BadParameter as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e
```

This is exactly the pattern for "`--check` was passed without `--model`" → exit 2. Copy the
`_stderr.print(f"[bold red]Error:[/bold red] {e}")` + `raise typer.Exit(code=...) from e` pair;
it recurs four times in the body (lines 167, 176, 179, 182) and is the file's error idiom.

**The terminal-output pattern** (`codegen.py:187-194`) — how the command ends today, including
the Rich-markup-escaping habit (`r"...\[codegen-lint]..."`):

```python
    source = render_and_format(introspected_views)
    typer.echo(source)
    if not ruff_available():
        _stderr.print(
            r"[yellow]Note:[/yellow] ruff is not installed; generated output is "
            r"unformatted. Install [bold]semolina\[codegen-lint][/bold] for formatted "
            r"output."
        )
```

A `--check` run must branch *before* this point: it emits no source. `Console` is already
imported, so a Rich `Table` for the per-field drift report needs only the extra import.

**Lazy-import convention:** heavyweight imports live *inside* functions throughout this module
(`from semolina.engines.base import ...` at line 162, `from semolina.codegen.python_renderer
import ...` at line 185, `import importlib` at line 122). Follow it — `probe.py`,
`arrow_map.py`, and `ast` should be function-local so CLI startup stays cheap.

---

### `src/semolina/cli/__init__.py` — MODIFIED (config)

**Analog:** the file's own registration block, verbatim (whole file is 51 lines). The epilog
exit-code table is a Rich-markup string with `\n\n` between rows; a `5` row appends here:

```python
app.command(
    "codegen",
    epilog=(
        "[bold]Exit codes[/bold]\n\n"
        "  [green]0[/green]  Success\n\n"
        "  [yellow]1[/yellow]  Unexpected error\n\n"
        "  [yellow]2[/yellow]  Invalid [bold]--backend[/bold] value (or omitted)\n\n"
        "  [red]3[/red]  View not found in the warehouse\n\n"
        "  [red]4[/red]  Connection or authentication failure"
    ),
)(codegen)
```

Colour convention visible in the excerpt: green = success, yellow = caller/tool error, red =
warehouse-side failure. A drift code is a caller-actionable outcome — yellow. This table is
duplicated in `docs/src/how-to/codegen.rst:298-313`; the two move together.

---

### `src/semolina/__init__.py` — MODIFIED (config, export surface)

**Analog:** the file's own import block and `__all__`, verbatim (whole file is 57 lines):

```python
from .fields import Dimension, Fact, Metric, NullsOrdering, OrderTerm
from .filters import Predicate
from .models import SemanticView
...
__all__ = [
    "__version__",
    "AsyncSemolinaCursor",
    "Dialect",
    "Dimension",
    "Fact",
    "Metric",
    ...
]
```

Two conventions the excerpt fixes: everything re-exported comes from a **relative** `.module`
import (never `semolina.module`), and `__all__` is ruff-sorted with dunders and CapWords ahead
of lowercase. `JsonValue` therefore needs a home module to be re-exported *from* — there is no
existing `types.py`; `fields.py` and `models.py` are the two plausible hosts, and neither
currently defines a type alias, so this is the one export with no exact analog. The
`TypeAlias` form itself is settled by `48-RESEARCH.md` (basedpyright-verified at
`pythonVersion = "3.11"`).

---

### `tests/unit/codegen/test_arrow_map.py` — CREATED (test, transform)

**Analog:** `tests/unit/codegen/test_type_map.py` (426 lines).

**Module-docstring + import pattern** (`test_type_map.py:1-17`), verbatim:

```python
"""
Tests for SQL type -> Python annotation mapping functions.

Tests cover Snowflake JSON type mappings, Databricks type mappings, and DuckDB
type mappings, including all clean-Python-equivalent types and types that return
None to trigger TODO comment generation.
"""

from __future__ import annotations

import pytest

from semolina.codegen.type_map import (
    databricks_type_to_python,
    duckdb_type_to_python,
    snowflake_json_type_to_python,
)
```

**Class-grouping + one-assert-per-test pattern** (`test_type_map.py:20-53`) — note the
`class TestX:` docstring "Tests for X function.", the section comments (`# Numeric types`,
`# String types`), the `-> None` return annotation on every test, and the single-sentence test
docstring restating the assertion:

```python
class TestSnowflakeJsonTypeToPython:
    """Tests for snowflake_json_type_to_python function."""

    # Numeric types
    def test_fixed_scale_zero_returns_int(self) -> None:
        """FIXED with scale=0 returns 'int'."""
        assert snowflake_json_type_to_python({"type": "FIXED", "scale": 0}) == "int"

    ...
    # String types
    def test_text_returns_str(self) -> None:
        """TEXT returns 'str'."""
        assert snowflake_json_type_to_python({"type": "TEXT"}) == "str"
```

**The sweep-parametrize pattern** (`test_type_map.py:393-425`) — every backend class ends with
one exhaustive `test_all_*_mappings` covering the whole map including the `None` rows. The
`arrow_map` module wants the same closing sweep, and the DuckDB one is the table to mirror:

```python
    @pytest.mark.parametrize(
        "type_name,expected",
        [
            ("VARCHAR", "str"),
            ("INTEGER", "int"),
            ...
            ("HUGEINT", "int"),
            ...
            ("INTERVAL", "datetime.timedelta"),
            ("DECIMAL(10,2)", None),
            ("STRUCT(a INTEGER)", None),
            ("MAP(VARCHAR, INTEGER)", None),
            ("LIST(INTEGER)", None),
            ("UNION(a INTEGER)", None),
            ("UNKNOWN_TYPE", None),
        ],
    )
    def test_all_duckdb_type_mappings(self, type_name: str, expected: str | None) -> None:
        """All DuckDB type mappings return expected Python annotation."""
```

Note the `"type_name,expected"` comma-string form (not a list of names) and no `ids=`. For
`arrow_map`, the parametrize values are `pyarrow` constructor calls (`pa.decimal128(38, 2)`,
`pa.timestamp("ns")`, `pa.dictionary(pa.uint8(), pa.string())`) — pytest will generate ids from
their reprs, which is adequate.

Also note the rows this excerpt shows will **change** under D-05/TYPE-05: `("HUGEINT", "int")`,
`("INTERVAL", "datetime.timedelta")` (staying, per D-06), and `("DECIMAL(10,2)", None)` are all
in this one table.

There is **no fixture usage** in `test_type_map.py` — pure functions, no `conftest`. Keep
`test_arrow_map.py` the same: no fixtures, no mocks, no warehouse.

---

### `tests/unit/codegen/test_cli.py` — MODIFIED (test, request-response)

**Analog:** the module's own `CliRunner` + mocked-engine harness (`test_cli.py:1-42`):

```python
"""
Tests for the reverse codegen CLI command.

Uses CliRunner to invoke the full Typer app with a mocked engine injected via
unittest.mock.patch, avoiding any warehouse connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from semolina.cli import app
from semolina.cli.codegen import EXIT_CONNECTION_ERROR, EXIT_INVALID_BACKEND, EXIT_VIEW_NOT_FOUND
from semolina.codegen.introspector import IntrospectedField, IntrospectedView
from semolina.engines.base import SemolinaConnectionError, SemolinaViewNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def make_mock_engine(views: list[IntrospectedView]) -> MagicMock:
    """
    Build a MagicMock engine whose introspect() returns views by view_name.
    ...
    """
    engine = MagicMock()
    engine.introspect.side_effect = lambda view_name: next(
        v for v in views if v.view_name == view_name
    )
    return engine
```

Copy: `runner = CliRunner()` at module scope; exit-code constants **imported from
`semolina.cli.codegen`** rather than hard-coded (so `EXIT_ANNOTATION_DRIFT` joins that import);
module-level `IntrospectedView` fixture constants (`SALES_VIEW`, `DESCRIBED_VIEW` at lines
49-70) rather than pytest fixtures.

**The live-DuckDB CLI route** lives in the sibling module, `test_codegen_e2e.py:32-55`, and is
the analog for a `--check` test that must actually reach a warehouse:

```python
def test_codegen_file_backed_duckdb(
    duckdb_file_backed_db: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """
    Codegen against an on-disk DuckDB ``.db`` produces the expected model class.
    ...
    """
    result = runner.invoke(
        app,
        [
            "codegen",
            "sales_view",
            "--backend",
            "duckdb",
            "--database",
            str(duckdb_file_backed_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot
```

Note `duckdb_file_backed_db` is a `conftest.py` fixture, and the `assert result.exit_code == 0,
result.output` idiom (failure message carries the output). A drift test asserts
`result.exit_code == EXIT_ANNOTATION_DRIFT` with the same `, result.output` tail.

---

### `tests/unit/test_sql.py` — MODIFIED (test, transform)

**Analog:** `TestRenderLiteralDatabricks` (line 188) and `TestRenderLiteralStandardSql`. The two
classes are parallel; the same additions land in both (D-07).

**The two assertions that invert** — verbatim, so the planner can name them exactly:

```python
# tests/unit/test_sql.py:176-179  (TestRenderLiteralStandardSql)
    def test_unsupported_type_raises_not_implemented(self):
        """An unsupported literal type fails loudly rather than mis-escaping."""
        with pytest.raises(NotImplementedError):
            SnowflakeDialect().render_literal(datetime.date(2024, 1, 1))
```

```python
# tests/unit/test_sql.py:232-235  (TestRenderLiteralDatabricks)
    def test_unsupported_type_raises_not_implemented(self):
        """An unsupported literal type fails loudly rather than mis-escaping."""
        with pytest.raises(NotImplementedError):
            DatabricksDialect().render_literal(datetime.date(2024, 1, 1))
```

Both use `datetime.date(2024, 1, 1)` — the exact value DBX-04 makes legal. The replacement
needs a *different* still-unsupported type (a `set`, a `complex`, an arbitrary object) so the
"fails loudly" contract keeps a live guard rather than being deleted. This is the same
"re-point, don't delete" discipline as the Phase 47 canary.

**The positive-assertion pattern to copy** for the new date/datetime/Decimal cases
(`test_sql.py:191-230`) — one behaviour per test, no `-> None` annotation in this module (unlike
`tests/unit/codegen/`), docstring restating the rule, and a requirement tag in the class
docstring:

```python
class TestRenderLiteralDatabricks:
    """DBX-01c: Spark-string render_literal (escape backslash first, then quote)."""

    def test_plain_string(self):
        """A plain string is wrapped in single quotes."""
        assert DatabricksDialect().render_literal("US") == "'US'"

    def test_single_quote_backslash_escaped(self):
        r"""Spark escapes a single quote with a backslash (\')."""
        assert DatabricksDialect().render_literal("O'Reilly") == "'O\\'Reilly'"
    ...
    def test_non_finite_float_raises(self):
        """WR-01: inf/-inf/nan are not SQL numeric literals -- fail loudly."""
        for value in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(ValueError):
                DatabricksDialect().render_literal(value)
```

`test_non_finite_float_raises` is the direct template for the non-finite-`Decimal` test: a loop
over the bad values inside a single test, `pytest.raises(ValueError)`, docstring prefixed with
the requirement id. Class docstrings carry a requirement tag (`DBX-01c:`, `WR-01:`) — the new
tests should carry `DBX-04:`.

---

### `tests/unit/test_type_fidelity_duckdb.py` — MODIFIED (test, request-response)

**Analog:** the canary itself (`test_type_fidelity_duckdb.py:120-134`), verbatim. This is the
test D-10 re-points, and its three-part structure (metadata half / result half / value) is what
must survive the re-pointing:

```python
def test_decimal_metric_disagrees_by_value(probe_engine: Engine, probe_cursor: Any) -> None:
    """Introspection, the result schema, and the value type disagree by named literals."""
    view = probe_engine.introspect(PROBE_VIEW_NAME)
    by_name = {field.name: field for field in view.fields}

    # Metadata half: the type map has no DECIMAL entry, so codegen emits a TODO annotation.
    assert by_name[PROBE_FIELD].data_type == "TODO: DECIMAL(38,2)"

    # Result half: the warehouse resolves SUM(DECIMAL(10,2)) to a widened decimal128.
    sql, params = probe_sql_for(PROBE_FIELD)
    probed = probe_schema(probe_cursor, sql, params)
    assert str(probed.schema.field(PROBE_FIELD).type) == "decimal128(38, 2)"

    # What the user actually receives, via the same to_pylist() call semolina.cursor makes.
    assert probe_value_type(probe_cursor, sql, params, PROBE_FIELD) == "decimal.Decimal"
```

The "agrees by value" twin D-10 asks for is this exact body with the first assertion becoming
`== "decimal.Decimal"` — same fixtures, same three-comment structure, opposite verdict.

**Fixture pattern** for anything new here (`test_type_fidelity_duckdb.py:96-117`) — note the
explicit teardown and the docstring that cites the conftest fixture it mirrors:

```python
@pytest.fixture
def probe_engine() -> Generator[Engine, None, None]:
    """
    Yield the probe's own in-memory DuckDB engine, closing its pool on teardown.

    Mirrors the register/unregister/close symmetry of ``tests/conftest.py``'s
    ``duckdb_pool``, minus the registry step: the probe never resolves an engine by name.
    """
    from adbc_poolhouse import close_pool

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


@pytest.fixture
def probe_cursor(probe_engine: Engine) -> Generator[Any, None, None]:
    """Yield a live ADBC cursor on the probe engine's pool."""
    with probe_engine.connect() as conn:
        cursor = conn.cursor()
        yield cursor
        cursor.close()
```

This module is also the one carrying the "never route this through cassette replay" contract
(`test_probe_runs_live_not_replayed`, line 137) — a `--check` test against live DuckDB inherits
that hazard and should copy the guard's reasoning if it lands here.

---

### `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` — MODIFIED (snapshot)

**Analog:** the file's own three entries, verbatim (43 lines total), so the planner can state
the target state exactly rather than predicting prose:

```
# serializer version: 1
# name: test_codegen_databricks_field_types
  '''
  from semolina import Dimension, Fact, Metric, SemanticView


  class SalesView(SemanticView, view="sales_view"):
      revenue = Metric[int]()
      cost = Metric[int]()
      country = Dimension[str]()
      region = Dimension[str]()

  '''
# ---
# name: test_codegen_snowflake_field_types
  '''
  import datetime

  from semolina import Dimension, Fact, Metric, SemanticView


  class SalesView(SemanticView, view="sales_view"):
      revenue = Metric[int]()
      country = Dimension[str]()
      date_key = Fact[datetime.date]()

  '''
# ---
```

Two things this excerpt settles that RESEARCH.md could only predict: the semolina import line is
**ruff-sorted** in the committed snapshot (so the isort pass does run in CI), and
`test_codegen_file_backed_duckdb` snapshots `result.output` (CLI, trailing blank line) while the
other two snapshot `render_and_format(...)` directly. Regenerate with `--snapshot-update` and
read the diff; do not hand-edit.

---

### `docs/src/explanation/type-fidelity.rst` — MODIFIED (docs, Explanation)

**Analog:** the page itself. The `.. note::` at lines 152-165, verbatim — this is the block that
becomes false:

```rst
.. note::

   Two kinds of claim live on this page. Everything above about warehouse
   behaviour and about the values in your rows is current: a decimal metric
   arrives as a ``Decimal`` today, and has always done so.

   The Python annotations that ``semolina codegen`` writes into a generated
   model are a separate matter, and they do not all agree with that yet. A
   Snowflake ``NUMBER`` column may still be annotated ``int`` or ``float``, a
   Databricks ``decimal`` column ``float``, and a DuckDB ``DECIMAL`` column
   ``Any`` with a ``TODO`` comment. The type map is being brought into line with
   the values described here. Until it is, trust the value you get at runtime
   over the annotation in a generated model, and see :ref:`howto-codegen` for
   how to replace an annotation by hand.
```

Immediately below it (lines 167-171) is the page's `See also` section — the CLAUDE.md
"self-contained page with See also links at the bottom" convention, already satisfied:

```rst
See also
--------

- :ref:`explanation-semantic-views` -- what a semantic view is, and how the three warehouses implement them
- :ref:`howto-codegen` -- generate models from your warehouse, and edit the annotations codegen produces
```

Voice pattern visible in the surrounding prose (lines 141-150): second person, short
declaratives, no step-by-step ("It is a good estimate. It is simply not the same source as the
query itself."). Match it. Per CLAUDE.md this edit changes a substantive claim, so it requires
`@.claude/skills/semolina-docs-author/SKILL.md` in the plan's `<execution_context>`.

---

### `docs/src/how-to/codegen.rst` — MODIFIED (docs, How-to)

**Analog:** the page's own sections. Three edits, each with an in-page template.

**Exit-code table** (lines 293-317), verbatim — the `list-table` shape a `5` row joins, plus the
`.. tip::` convention for a caveat:

```rst
Exit codes
----------

``semolina codegen`` uses distinct exit codes so scripts can handle each failure mode separately:

.. list-table::
   :header-rows: 1

   * - Exit code
     - Meaning
   * - ``0``
     - Success -- model class written to stdout
   * - ``1``
     - Unexpected error (see stderr for details)
   * - ``2``
     - Invalid ``--backend`` specifier -- value provided but not recognised
   * - ``3``
     - View not found -- the warehouse has no semantic view with that name
   * - ``4``
     - Connection failure -- credentials missing or authentication rejected

.. tip::

   Exit code 2 is also emitted by the CLI argument parser when ``--backend`` is
   omitted entirely. Both cases mean "the backend could not be resolved."
```

**The VARIANT claim to correct** (lines 275-291), verbatim — TYPE-06 falsifies the first
sentence's VARIANT mention:

```rst
Handle TODO comments
--------------------

When a field's SQL type has no clean Python equivalent (GEOGRAPHY, VARIANT, ARRAY, MAP,
STRUCT), codegen types the field as ``Any`` and drops the raw warehouse type into a
TODO comment rather than guessing:

.. code-block:: python

   # TODO: {"type": "GEOGRAPHY"}
   territory = Dimension[Any]()

The comment carries the warehouse's own type descriptor verbatim, so you have the
detail you need to pick a concrete type. ``Any`` keeps the generated module valid in
the meantime; codegen adds ``from typing import Any`` for you whenever a field needs it.

Review these fields after generation and replace ``Any`` with the type you want.
```

**Section pattern for the new `--check` section** (lines 251-273) — a `Verb the thing` heading
underlined with `-`, an orienting sentence, a `list-table` or code block, then a paragraph
explaining *why* the design is what it is:

```rst
Understand field type mapping
-----------------------------

Codegen resolves each backend's native role string to a field type:

.. list-table::
   :header-rows: 1

   * - Warehouse classification
     - Generated field type
   * - Metric / Measure
     - ``Metric[T]()``
   ...

If a backend ever hands back a role string that codegen doesn't recognize,
generation stops with a ``ValueError`` instead of guessing. ...
```

Heading style across the page is imperative-verb-first (`Handle TODO comments`, `Understand
field type mapping`, `Override the SQL column name with source=`), so the new one reads e.g.
`Check a committed model for drift`. The `--check` how-to section is new-page-equivalent
content and definitely requires the docs skill.

---

## Shared Patterns

### Error handling: `typer.BadParameter` → `_stderr.print` → `typer.Exit(code=...)`

**Source:** `src/semolina/cli/codegen.py:164-183`
**Apply to:** every new `--check` failure path in `cli/codegen.py`

```python
    try:
        engine = _resolve_backend(backend, database=database)
    except typer.BadParameter as e:
        _stderr.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=EXIT_INVALID_BACKEND) from e
    ...
        except SemolinaViewNotFoundError as e:
            _stderr.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=EXIT_VIEW_NOT_FOUND) from e
```

Always `from e`; always the `[bold red]Error:[/bold red]` prefix; always stderr.

### Fail-loudly-on-unknown rather than guess

**Source:** `src/semolina/codegen/python_renderer.py:83-86`
**Apply to:** `arrow_map.py`'s fallthrough decision, and any new type_map branch

```python
    try:
        return _ROLE_TO_CLASS[field_type]
    except KeyError:
        raise ValueError(f"Unrecognized field role: {field_type!r}") from None
```

Note the project distinguishes two "unknown" cases and treats them differently: an unknown
*role* raises (drift in a closed vocabulary), while an unknown *type* returns `None` and becomes
a `TODO:` (an open vocabulary the user can resolve by hand). `arrow_map.py` is the second kind —
return `None`, do not raise.

### Google docstrings with an `Args:` / `Returns:` / `Raises:` triple and an RST `Example:`

**Source:** `src/semolina/codegen/type_map.py:163-194`, `python_renderer.py:68-87`
**Apply to:** every new public function in `arrow_map.py` and `probe.py`

Summary line on the **second** line after the opening `"""` (D213); closing `"""` on its own
line; `Example:` bodies use `.. code-block:: python` and the `# 'result'` comment style (no
`>>>`), so `--doctest-modules` does not execute them.

### Module-level docstring stating an invariant the code must keep

**Source:** `tests/type_fidelity_probe.py:10-21`, `tests/unit/test_type_fidelity_table.py:1-13`
**Apply to:** `src/semolina/codegen/probe.py` (the anti-circularity contract) and any test module
carrying the record/replay contract

```
The module is split into two regions that must never be allowed to converge:

* the **metadata half** — ... Its mapped-annotation column is
  produced by ``semolina.codegen.type_map``, which is exactly the thing being measured;
* the **result half** — :func:`probe_schema`. It must never import
  ``semolina.codegen.type_map`` or any symbol from it. ...

Two columns sourced from one place would make the comparison circular, and a comparison that
cannot produce a mismatch is not measuring anything.
```

### Lazy (function-local) imports for heavy or optional dependencies

**Source:** `src/semolina/cli/codegen.py:93,103,122,162,185`;
`tests/type_fidelity_probe.py:203` (`import adbc_driver_manager` inside the resolver)
**Apply to:** the CLI's use of `probe`/`arrow_map`/`ast`; `probe.py`'s driver-manager import

### `TYPE_CHECKING`-guarded imports for annotation-only symbols

**Source:** `src/semolina/codegen/python_renderer.py:15-20`, `cli/codegen.py:13-15`
**Apply to:** new modules — but note `pyarrow` must be a **runtime** import in `arrow_map.py`
(predicates) and `probe.py` (dataclass field), unlike these examples.

---

## No Analog Found

| File / element | Role | Data flow | Reason |
|---|---|---|---|
| The `JsonValue` type-alias **host module** | config / type surface | — | `src/semolina/` has no `types.py` and no existing module defines a public `TypeAlias`. Every `__all__` entry today is a class or function. The alias's *form* is settled (`48-RESEARCH.md`, basedpyright-verified); only its home is unprecedented. |
| A drift **report renderer** (per-field table to stderr) | controller output | transform | The CLI has never emitted structured output — only source to stdout and one-line Rich errors to stderr. `rich.table.Table` is not used anywhere in `src/`. Nearest precedents are prose-only: `_stderr.print` at `cli/codegen.py:190-194` and the markdown table renderer in `tests/type_fidelity_probe.py` (`render_artifact`), which is a file generator, not a console reporter. |
| Reading a committed model by `ast.parse` | service | file-I/O | No `ast` usage exists in `src/`. The nearest in-repo precedent is dynamic *import* at `cli/codegen.py:130-135` (`importlib.import_module` + `getattr`), which is the route RESEARCH recommends against. `48-RESEARCH.md` § "Code Examples" supplies the AST sketch; there is no house pattern to copy. |

---

## Metadata

**Analog search scope:** `src/semolina/` (all), `tests/unit/`, `tests/unit/codegen/`,
`tests/type_fidelity_probe.py`, `docs/src/how-to/`, `docs/src/explanation/`
**Files read in full this session:** `codegen/type_map.py`, `codegen/python_renderer.py`,
`codegen/templates/python_model.py.jinja2`, `cli/codegen.py`, `cli/__init__.py`,
`semolina/__init__.py`, `tests/unit/codegen/test_codegen_e2e.py`,
`tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`
**Files read in targeted, non-overlapping ranges:** `engines/sql.py` (80-134, 370-429, 826-883),
`tests/type_fidelity_probe.py` (1-70, 170-269), `tests/unit/codegen/test_type_map.py` (1-60,
330-425), `tests/unit/codegen/test_cli.py` (1-70), `tests/unit/test_sql.py` (160-237),
`tests/unit/test_type_fidelity_duckdb.py` (95-144), `tests/unit/test_type_fidelity_table.py`
(1-60, 190-239), `docs/src/how-to/codegen.rst` (245-324),
`docs/src/explanation/type-fidelity.rst` (140-171)
**Pattern extraction date:** 2026-08-12
