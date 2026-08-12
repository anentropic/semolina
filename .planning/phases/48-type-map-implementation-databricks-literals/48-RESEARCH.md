# Phase 48: Type Map Implementation & Databricks Literals - Research

**Researched:** 2026-08-12
**Domain:** Codegen type mapping, Arrow→Python annotation derivation, CLI check modes, Spark SQL literal syntax
**Confidence:** HIGH on mechanics (every claim below traced to a file read this session or an official doc page); MEDIUM on the two design questions 47-DECISIONS.md leaves open (`--check` surface, TYPE-05 target types)

## Summary

This phase has an unusual shape: three of its six requirements are almost trivial edits to a
23-line dictionary, one is a renderer change the specification already names, one is a
well-bounded literal-escaping widening, and one — TYPE-07's `--check` — is a genuinely
unspecified new CLI surface that needs roughly as much design as the other five combined.
Plan the effort accordingly and do not let the easy five hide the hard one.

The second thing to know is that the phase's blast radius is much wider than the two files
47-DECISIONS.md names. Changing the type map changes what `IntrospectedField.data_type`
carries; that value is asserted by literal in at least four test modules, is rendered into
three syrupy snapshots, and is a *generated column* of Phase 47's committed evidence artifact
whose staleness guard (`tests/unit/test_type_fidelity_table.py:204`) turns red the moment the
map moves. Phase 47's own known-mismatch canary
(`tests/unit/test_type_fidelity_duckdb.py:126`) asserts the string `TODO: DECIMAL(38,2)` and
is designed to go red if the two columns ever agree — which is exactly what this phase makes
them do. That canary has to be deliberately re-pointed, not silently deleted, or the
circularity guard Phase 47 built dies with it.

The third thing is a measurement this research ran that nobody has run before, and it changes
what TYPE-05 should mean. Through the real ADBC DuckDB path, a `UUID` column arrives as a
Python `str`, a `JSON` column arrives as a `str`, an `ENUM` arrives as a `str`, and
`TIMESTAMP_NS` arrives as a `pandas.Timestamp` when pandas is importable and a
`datetime.datetime` when it is not. Annotating those columns `uuid.UUID` / a parsed JSON type
/ `datetime.datetime` would recreate the annotation-does-not-describe-the-value defect that
Decision 1 exists to end, one requirement later. TYPE-05 says "a concrete Python type instead
of a `TODO:` placeholder"; it does not say which, and 47-DECISIONS.md explicitly declines to
specify ("This document does not re-specify them"). The measured answers are in
§ "The DuckDB map gaps, measured" below and they should be the plan's starting point.

**Primary recommendation:** Split into four plans — (1) the type-map + renderer changes with
their full test/snapshot/artifact fallout, (2) DBX-04's `render_literal` widening, (3) the
`arrow_type_to_python` mapper plus `probe_schema` promoted from `tests/` into `src/`, (4) the
`--check` CLI surface built on (3). Put a `checkpoint:human-verify` in front of the three
TYPE-05/TYPE-06 target-type calls that the specification leaves open, because a wrong answer
there is a public API contract that Phase 49 and Phase 50 then build on.

## User Constraints (standing in for CONTEXT.md)

There is **no CONTEXT.md for this phase**. The user chose to plan without `/gsd-discuss-phase`
on the grounds that `47-DECISIONS.md` is already the normative specification. The following is
copied from `47-DECISIONS.md` and treated with the authority a CONTEXT.md `## Decisions`
section would carry.

### Locked Decisions

**From `47-DECISIONS.md` § "Inherited, not decided here":**

- VARIANT maps to a `JsonValue` union, not `Any` — recursive
  `str | int | float | bool | None | list | dict`. The DTO side uses `pydantic.JsonValue`; the
  model side needs a `semolina.JsonValue` alias, because semolina core carries no pydantic
  dependency.
- Untyped stays a first-class fallback at every layer. `Metric()` is documented shorthand for
  `Metric[Any]()`, and the renderer's `TODO: <raw type>` path stays.
- Probes run at codegen time and at CI `--check` time. Never at runtime.
- `.into(DTO)` needs no probe: the executed result already carries its Arrow schema.
- The four-category untypeable taxonomy is settled. Category 1 (map gaps) is the population the
  Decimal policy and the map additions fix.

**Decision 1 — Decimal policy.** "Warehouse decimal and numeric types map to `decimal.Decimal`
on all three backends. On Snowflake that covers the whole `FIXED` family including scale 0, not
only scale-above-0 columns."

**Decision 1, scope prohibition (verbatim, and this is the phase's hardest fence):**
"**This decision changes what codegen writes into a generated model. It introduces no runtime
coercion, and Phase 48 must not add any.** … A change that touches `cursor.py` or `results.py`
to make a value match its annotation is out of scope and would invert this decision: the
annotation is being corrected to the value, never the reverse."

**Decision 2 — Metric-nullability stance.** "Uniform across all metrics: a metric annotation is
`T | None`. COUNT is a documented over-approximation — it never returns NULL, and it is
annotated as though it might." Dimension nullability is explicitly **not** covered:
"Dimensions keep their current annotation shape, and revisiting them is a later phase's call."

**Decision 3 — Source of truth.** "The query-time result schema is **primary**. Warehouse
introspection metadata is a labelled **fallback**, used when no connection is available or when
the probe is refused." Precedence: "When both are available and they disagree, the result
schema wins, and codegen records which route produced the annotation."

**Decision 4 — Per-driver `adbc_execute_schema`.** Snowflake: yes, except with bind parameters.
Databricks: no, zero-row fallback is the only path. DuckDB: yes. **Staleness note carried
forward verbatim:** "Phase 48 and Phase 50 should re-read the driver's `go/statement.go` at the
version they pin rather than treating this row as durable."

**Decision 5 (non-gating) — filter-value typing.** "Lenient widening. … Nothing in Phase 48's
requirements depends on it."

**The exact-location table, verbatim from § "What Phase 48 must change":**

| Location | Today | Under this policy |
|---|---|---|
| `snowflake_json_type_to_python`, the `FIXED` branch (lines 90-92) | `return "int" if scale == 0 else "float"` | `decimal.Decimal` for the whole `FIXED` family; the scale test goes away entirely |
| `_DATABRICKS_TYPE_MAP["decimal"]` | `"float"` | `"decimal.Decimal"` |
| `_DUCKDB_TYPE_MAP` | no `DECIMAL` key at all … returns `None`, and the renderer emits `TODO:` | a `"DECIMAL"` key mapping to `decimal.Decimal` |

Plus the two named knock-ons: "The renderer needs to emit `import decimal` when any field uses
`decimal.Decimal`" and "Metric annotations become `T | None` per Decision 2, which is a
renderer change rather than a map change."

### Claude's Discretion (where 47-DECISIONS.md is silent — flagged, not invented)

47-DECISIONS.md says of TYPE-05 and TYPE-06: "**This document does not re-specify them**; the
VARIANT answer is inherited and listed at the top." So the following are **open** and the
planner must decide them (recommendations in § "Open Questions"):

1. Which concrete Python type each DuckDB map gap maps to (`UUID`, `JSON`, `ENUM`,
   `TIMESTAMP_S|_MS|_NS`) and which Databricks `interval` shape maps to what.
2. The entire `--check` CLI surface — flag name, argument shape, exit codes, output format,
   which route is authoritative, and how the committed model is read.
3. Whether Decision 3's "result schema is primary" applies to `semolina codegen`'s *generation*
   path in this phase, or only to `--check`. **No Phase 48 requirement asks for the former.**
4. Whether DBX-04 widens only `DatabricksDialect.render_literal` or the base `Dialect` too.
5. What to do with Phase 47's now-falsified canary and the committed evidence artifact.

### Deferred Ideas (OUT OF SCOPE)

- Any runtime coercion in `cursor.py` or `results.py` (Decision 1's prohibition).
- Dimension nullability (Decision 2 explicitly defers it).
- Replacing `SHOW COLUMNS IN VIEW` with `SHOW SEMANTIC METRICS` / `SHOW SEMANTIC DIMENSIONS`
  ("Noted, not decided" in Decision 2).
- Statically enforcing Decision 5's lenient filter-value widening ("Nothing in Phase 48's
  requirements depends on it").
- `.into(DTO)` (Phase 49) and codegen'd DTO classes (Phase 50).

## Phase Requirements

| ID | Description (from `.planning/REQUIREMENTS.md:23-27,51`) | Research Support |
|----|-------------|------------------|
| TYPE-03 | Decimal-typed columns get the decision doc's type consistently across all three backends | § "The current type-map surface" (exact branch/key locations), § "Test and snapshot fallout" (what churns) |
| TYPE-04 | Metric annotations reflect the nullability stance | § "The renderer seam" — why `\| None` must be applied in `_build_model_context`, not in the maps, or `import datetime` silently disappears |
| TYPE-05 | DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S\|_MS\|_NS` and Databricks `interval` get a concrete type | § "The DuckDB map gaps, measured" (measured Arrow + Python types for all of them), § "Databricks `interval`" (authoritative JSON type-object shape) |
| TYPE-06 | VARIANT yields a `JsonValue` union rather than `Any` | § "`semolina.JsonValue` — the alias mechanics", including a basedpyright-verified 3.11-compatible form |
| TYPE-07 | `--check` mode reports annotation drift without fetching a row | § "TYPE-07 `--check` — the open design", § "The probe lives in `tests/`, not `src/`" |
| DBX-04 | Databricks `render_literal` accepts `date`, `datetime`, `Decimal` | § "DBX-04 — `render_literal` widening" with official Databricks literal grammars |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SQL type name → Python annotation string | `src/semolina/codegen/type_map.py` | — | Pure function layer, no I/O. TYPE-03, TYPE-05, TYPE-06 land here and nowhere else. |
| Arrow `DataType` → Python annotation string | **new** module (recommend `src/semolina/codegen/arrow_map.py`) | — | Does not exist today. TYPE-07 cannot compare a probed schema to a committed annotation without it; Phase 50's DTO-07 needs the same function. |
| Result-schema probing | **new** `src/semolina/codegen/probe.py` (promoted from `tests/type_fidelity_probe.py:236`) | — | `probe_schema` is test-only today. A shipped `--check` cannot import from `tests/`. |
| Nullability decoration (`T \| None`) | `src/semolina/codegen/python_renderer.py` `_build_model_context` | — | Decision 2 says renderer, not map — and the import-detection code at `python_renderer.py:175` breaks if the map does it. |
| Import emission for new annotation types | `python_renderer.py:174-198` + `templates/python_model.py.jinja2` | ruff isort pass (`format_with_ruff`) | `import decimal` / `import uuid` / `from semolina import JsonValue` all need a new emission path. |
| CLI surface, exit codes, diff output | `src/semolina/cli/codegen.py` + `src/semolina/cli/__init__.py` | — | TYPE-07's `--check`. Exit-code constants and the epilog table both live here. |
| Spark SQL literal rendering | `DatabricksDialect.render_literal` (`src/semolina/engines/sql.py:386`) | `SQLBuilder._render_literal_sql` (`sql.py:843`) | DBX-04. The post-pass at `:843` is already generic; only the renderer needs widening. |
| Arrow → Python **value** conversion | `pyarrow` via `batch.to_pylist()` (`src/semolina/cursor.py:281`) | — | **Out of bounds.** Decision 1's prohibition. Verified below. |

### System architecture diagram

The two routes Decision 3 promotes and demotes, and where the new components sit. `probe_schema`
exists today only inside `tests/type_fidelity_probe.py`; `arrow_type_to_python` and
`annotation compare` do not exist at all.

```
  metadata route (fallback)       result-schema route (--check)

  +----------+-----------+        +----------+-----------+
  | warehouse catalogue  |        |   canonical query    |
  +----------+-----------+        +----------+-----------+
             |  DESCRIBE / SHOW              |  SQL + []
             v                               v
  +----------+-----------+        +----------+-----------+
  | Engine.introspect()  |        |    probe_schema()    |
  +----------+-----------+        +----------+-----------+
             |  raw SQL type                 |  pyarrow.Schema
             v                               v
  +----------+-----------+        +----------+-----------+
  | codegen/type_map.py  |        | arrow_type_to_python |
  +----------+-----------+        +----------+-----------+
             |  annotation str               |  annotation str
             v                               v
  +----------+-----------+        +----------+-----------+
  |  python_renderer.py  |        |  annotation compare  |
  +----------+-----------+        +----------+-----------+
             |                               ^
             v                               |
  +----------+-----------+                   |
  |  models.py on disk   +-------------------+
  +----------------------+
```

### Component responsibilities

| Component | File | Responsibility after this phase |
|-----------|------|-------------------------------|
| Snowflake map | `src/semolina/codegen/type_map.py:15-25`, `:84-94` | `FIXED` → `decimal.Decimal`, scale test deleted; VARIANT → `JsonValue` |
| Databricks map | `type_map.py:29-44`, `:97-134` | `decimal` → `decimal.Decimal`; `interval` handled from `start_unit`/`end_unit`; `variant` → `JsonValue` |
| DuckDB map | `type_map.py:139-160`, `:163-199` | `DECIMAL`, `UUID`, `JSON`, `ENUM`, `TIMESTAMP_S`, `TIMESTAMP_MS`, `TIMESTAMP_NS` keys added |
| Renderer | `python_renderer.py` | `\| None` on metrics; generalised import emission |
| Template | `codegen/templates/python_model.py.jinja2` | New conditional import lines (or a rendered import block) |
| CLI | `cli/codegen.py`, `cli/__init__.py` | `--check` option, new exit code, epilog table entry |
| Dialect | `engines/sql.py:386-426` | `date`/`datetime`/`Decimal` literals |

## Project Constraints (from CLAUDE.md)

| Directive | Effect on this phase |
|-----------|----------------------|
| `prek run --all-files` before committing (ruff lint+format, basedpyright **strict**, shellcheck) | Every new module (`arrow_map.py`, `probe.py`) must pass basedpyright strict. pyarrow ships no stubs; `reportMissingTypeStubs`/`reportUnknownParameterType` are already off at the pyproject level (`pyproject.toml` `[tool.basedpyright]`), so annotate `pyarrow.DataType` under `TYPE_CHECKING` as `cursor.py` already does. |
| Avoid `# type: ignore`; pyproject-level exemptions only as last resort | The recursive `JsonValue` alias is the likely temptation. A form that needs no ignore is verified below. |
| **Bug fixes: reproduce with a failing test FIRST, then fix; commit RED then GREEN** | DBX-04 is a bug fix in spirit (`render_literal` raises on a value users legitimately pass). Note the Phase 45 precedent recorded in `STATE.md:112`: "TDD RED was demonstrated per task but RED+GREEN landed in one commit each because basedpyright strict rejects a test referencing not-yet-existent attributes and `--no-verify` was disallowed." For DBX-04 the attributes already exist, so a genuine RED-then-GREEN two-commit sequence **is** achievable — plan it. |
| `just test` = `uv run pytest` + `pushd semolina-jaffle-shop; uv run pytest` | Two suites. `semolina-jaffle-shop/tests/conftest.py` declares `DECIMAL(10,2)`/`DECIMAL(12,2)` columns, so the decimal change is exercised there too. |
| `just docs-build` = `sphinx-build -W` (strict) | Any docs edit must build warning-free. |
| Line length 100; multi-line docstrings with `"""` on own lines; D213 | Applies to all new code. |
| Docstring `Example:` uses `.. code-block:: python`, never fenced backticks | Applies to every new public function. |
| `addopts` includes `--doctest-modules`, `testpaths = ["tests", "src"]` | **Docstring examples in `src/` are executed as tests.** A new `arrow_map.py` whose `Example:` shows `arrow_type_to_python(pa.decimal128(38, 2))` will actually run. Keep them correct or non-executing. |
| **Mandatory docs skill** `@.claude/skills/semolina-docs-author/SKILL.md` | Required in `<execution_context>` of any plan touching `docs/src/`. Confirmed present at `.claude/skills/semolina-docs-author/SKILL.md`. |
| Diataxis classification | `type-fidelity.rst` is Explanation; `codegen.rst` is How-to. The `--check` usage instructions belong in the How-to, the *why* stays in the Explanation. |

## Standard Stack

**This phase installs no new packages.** Everything it needs is already declared in
`pyproject.toml` and present in the lockfile.

### Core

| Library | Version (verified in `.venv` this session) | Purpose | Why standard |
|---------|---------|---------|--------------|
| `pyarrow` | 24.0.0 | `pyarrow.Schema` / `DataType` for the probe and the Arrow→Python mapper | Already the Arrow surface throughout `cursor.py` |
| `adbc-driver-manager` | 1.10.0 | `Cursor.adbc_execute_schema`; `NotSupportedError`/`ProgrammingError`/`OperationalError` | ADBC 1.1 `ExecuteSchema` entry point; already imported by `engines/databricks.py:158` |
| `duckdb` | 1.5.5 (pinned exact) | Live DuckDB probe target | `pyproject.toml` pins `duckdb==1.5.5` (community extension version lock) |
| `typer` | declared `>=0.12.0` | The `--check` flag and exit codes | Already the CLI framework (`cli/__init__.py`) |
| `jinja2` | declared `>=3.1.0` | `python_model.py.jinja2` | Already the renderer |
| `pytest-adbc-replay` | 1.1.1 | Cassette replay for Snowflake/Databricks assertions | Already the warehouse-test mechanism |
| `syrupy` | declared `>=5.1.0` | `.ambr` snapshot assertions for codegen E2E | Already in the dev group |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| A hand-written `arrow_type_to_python` keyed on `pyarrow.types.is_*` predicates | String-matching `str(dtype)` | String matching breaks on `decimal128(38, 2)` vs `decimal256`, on `timestamp[us, tz=Europe/London]`, and on `dictionary<values=string, indices=uint8, ordered=0>`. Use the `pyarrow.types` predicate functions. |
| Importing the committed model module in `--check` | AST-parsing the file | Import is simpler and `__orig_class__` survives at runtime (verified below), but it executes arbitrary user code. AST parsing is safer and needs no importable package. See § "TYPE-07". |
| Regenerate-and-byte-diff (`ruff format --check` style) | Per-field annotation comparison | Byte-diff is much cheaper but compares against the *metadata* route, so it does not satisfy TYPE-07's wording ("match the warehouse's current result schema"). See § "TYPE-07". |
| Promoting `probe_schema` into `src/` | Duplicating it | Duplication guarantees drift between the shipped `--check` and Phase 47's evidence generator. Promote and have `tests/type_fidelity_probe.py` import it. |

**Installation:** none.

**Version verification:** run this session against `.venv`:

```
duckdb 1.5.5   pyarrow 24.0.0   adbc_driver_manager 1.10.0 (per 47-RESEARCH.md, unchanged)
```
[VERIFIED: `.venv/bin/python -c "import duckdb, pyarrow"`, this session]

## Package Legitimacy Audit

**This phase installs no external packages**, so the ecosystem-registry gate does not apply.
Every dependency is already declared in `pyproject.toml` and pinned in `uv.lock`.

| Package | Registry | Disposition |
|---------|----------|-------------|
| *(none added)* | — | N/A |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## The current type-map surface

Every identifier here was read from the file this session.

### Public functions and their exact signatures

`src/semolina/codegen/type_map.py`:

- `snowflake_json_type_to_python(type_json: dict[str, object]) -> str | None` — line 47
- `databricks_type_to_python(type_obj: dict[str, object]) -> str | None` — line 97
- `duckdb_type_to_python(type_name: str) -> str | None` — line 163

Note the asymmetry: Snowflake and Databricks receive a **dict** (so they can read `scale`,
`precision`, `start_unit`, `end_unit`), DuckDB receives a **bare string**.
[VERIFIED: src/semolina/codegen/type_map.py:47,97,163]

### The three module-level maps

`_SNOWFLAKE_TYPE_MAP` (line 15, keys uppercase), `_DATABRICKS_TYPE_MAP` (line 29, keys
lowercase), `_DUCKDB_TYPE_MAP` (line 139, keys uppercase). Verbatim, the two lines the
specification names:

```python
    "decimal": "float",                                   # type_map.py:38
```

```python
    if type_name == "FIXED":                              # type_map.py:90-92
        scale = type_json.get("scale", 0)
        return "int" if scale == 0 else "float"
```

And the DuckDB parameter-stripping line, verbatim:

```python
    base = type_name.split("(")[0].strip().upper()        # type_map.py:198
```

[VERIFIED: src/semolina/codegen/type_map.py:38, 90-92, 198 — read this session]

`_DUCKDB_TYPE_MAP` in full, verbatim from lines 139-160:

```python
_DUCKDB_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "str", "INTEGER": "int", "BIGINT": "int", "SMALLINT": "int",
    "TINYINT": "int", "HUGEINT": "int", "UBIGINT": "int", "UINTEGER": "int",
    "USMALLINT": "int", "UTINYINT": "int", "DOUBLE": "float", "FLOAT": "float",
    "BOOLEAN": "bool", "DATE": "datetime.date", "TIMESTAMP": "datetime.datetime",
    "TIMESTAMP WITH TIME ZONE": "datetime.datetime", "TIME": "datetime.time",
    "TIME WITH TIME ZONE": "datetime.time", "BLOB": "bytes",
    "INTERVAL": "datetime.timedelta",
}
```

*(Formatting condensed for width; keys and values are verbatim.)*
[VERIFIED: src/semolina/codegen/type_map.py:139-160]

### The three call sites, and where `TODO: ` is born

`TODO: ` is **not** produced by `type_map.py`. It is produced by each engine when the mapper
returns `None`, and the raw warehouse type is the only place that raw type survives:

| Backend | Call site | `TODO: ` construction, verbatim |
|---------|-----------|--------------------------------|
| Snowflake | `src/semolina/engines/snowflake.py:177` | `data_type = f"TODO: {d['data_type']}" if py_type is None else py_type` (line 178) |
| Databricks | `src/semolina/engines/databricks.py:184` | `data_type = py_type if py_type is not None else f"TODO: {raw_type_name}"` (line 190) |
| DuckDB | `src/semolina/engines/duckdb.py:238` | `data_type = py_type if py_type is not None else f"TODO: {sql_type}"` (line 239) |

[VERIFIED: src/semolina/engines/snowflake.py:177-178, databricks.py:184-190, duckdb.py:236-241]

Note the Snowflake `TODO:` embeds the whole JSON descriptor (`d['data_type']` is the raw JSON
string), which is why `python_renderer.py:107` collapses whitespace — see the renderer section.

There are **no other callers** of the three mapper functions in `src/`. The only other importer
anywhere is `tests/type_fidelity_probe.py:1172,1209`, which uses them to populate the artifact's
`Mapped annotation` column.
[VERIFIED: `grep -rn "type_to_python" src tests --include="*.py"`, this session]

## The renderer seam

`src/semolina/codegen/python_renderer.py`, read this session.

### How an annotation becomes emitted source

1. `render_views(views: list[IntrospectedView]) -> str` (line 133) computes two booleans and
   calls the Jinja2 template.
2. `_build_model_context(view) -> _ModelContext` (line 89) turns each `IntrospectedField` into a
   `_FieldContext` with `data_type: str` — "Never empty" per its docstring (line 39).
3. The template `src/semolina/codegen/templates/python_model.py.jinja2` emits
   `{{ field.name }} = {{ field.field_class }}[{{ field.data_type }}]()`.
4. `format_with_ruff(source)` (line 215) runs `ruff format` then `ruff check --fix --select I`
   as subprocesses **only if the optional `codegen-lint` extra is installed**
   (`ruff_available()`, line 201). If ruff is absent the raw template output is returned and the
   import order is whatever the template emits.

### The import mechanism — and the TYPE-04 landmine

Imports are two booleans, computed at `python_renderer.py:174-182`:

```python
    needs_datetime = any(f.data_type in _DATETIME_TYPES for view in views for f in view.fields)
    needs_any = any(
        f.data_type is None or f.data_type.startswith("TODO:")
        for view in views
        for f in view.fields
    )
```

with, at line 23:

```python
_DATETIME_TYPES = frozenset({"datetime.date", "datetime.datetime", "datetime.time"})
```

and the template:

```jinja
{% if needs_datetime %}
import datetime
{% endif %}
{% if needs_any %}
from typing import Any
{% endif %}
from semolina import SemanticView, Metric, Dimension, Fact
```

[VERIFIED: src/semolina/codegen/python_renderer.py:23,174-198 and
src/semolina/codegen/templates/python_model.py.jinja2 — both read this session]

**The landmine, stated plainly:** `needs_datetime` is an *exact-string membership test on
`IntrospectedField.data_type`*. If Decision 2's `| None` is applied anywhere upstream of
`_build_model_context` — in the maps or in the engines — then a `TIMESTAMP` metric's
`data_type` becomes `"datetime.datetime | None"`, which is not in `_DATETIME_TYPES`, so
`import datetime` is **not emitted** and the generated module raises `NameError` on import.
47-DECISIONS.md already says "which is a renderer change rather than a map change"; this is
*why*, and the plan should encode it as a prohibition rather than a preference.

**Recommendation for the import mechanism:** replace the two booleans with a computed
`imports: list[str]` (or a `set[str]` rendered sorted) derived from the resolved
`_FieldContext.data_type` strings after nullability decoration, matching on a module prefix
(`"decimal."` → `import decimal`, `"uuid."` → `import uuid`, `"datetime."` → `import datetime`)
plus explicit entries for `Any` and `JsonValue`. Two more booleans would work for this phase and
will not survive Phase 50.

**Second-order note:** `JsonValue` must join the existing `from semolina import SemanticView,
Metric, Dimension, Fact` line, which is hard-coded in the template. Either make that line
conditional-suffixed or emit a separate `from semolina import JsonValue` and let the ruff isort
pass merge them — it will not merge them; ruff's isort does not combine duplicate `from`
imports by default. Prefer building the one `from semolina import ...` line from a set.

### `TODO:` handling, three places

`python_renderer.py:103` (comment text, with whitespace collapsed by `" ".join(f.data_type.split())`),
`:111` (map to `"Any"`), `:179` (`needs_any`). All three test `.startswith("TODO:")` — note
**no trailing space** in the renderer's literal, while `tests/type_fidelity_probe.py:341`
defines `TODO_PREFIX = "TODO: "` **with** a trailing space. Any refactor that centralises the
constant must not accidentally change either test's semantics.
[VERIFIED: python_renderer.py:103,111,179; tests/type_fidelity_probe.py:341]

## CRITICAL SCOPE FENCE — verified against current code

47-DECISIONS.md's prohibition is **still accurate**. Verified two ways this session:

**1. The line is where the doc says it is.** `src/semolina/cursor.py:281`, verbatim:

```python
            self._batch_rows = batch.to_pylist()
```

It sits inside `SemolinaCursor.__next__`'s batch loop; line 283 is `row = Row(self._batch_rows[self._batch_pos])`.
[VERIFIED: src/semolina/cursor.py:279-285, read this session]

**2. There is no coercion anywhere on that path.** `grep -n "Decimal(\|float(\|int("` over
`src/semolina/results.py`, `src/semolina/cursor.py`, and `src/semolina/acursor.py` returns
exactly one hit — `acursor.py:57`, which is the string `print(row["country"], row["revenue"])`
inside a docstring example, i.e. a false positive on `print(`. `Row.__init__`
(`results.py:26-32`) does `object.__setattr__(self, "_data", dict(data))` and nothing else.
[VERIFIED: `grep -n 'Decimal(\|float(\|int(' src/semolina/results.py src/semolina/cursor.py src/semolina/acursor.py`, this session; src/semolina/results.py:26-32]

**Fence, phrased for `must_haves.prohibitions`:**

> `src/semolina/cursor.py`, `src/semolina/acursor.py`, and `src/semolina/results.py` must not be
> modified by this phase. The Decimal policy is annotation-only (47-DECISIONS.md Decision 1,
> § "Scope: this policy is annotation-only"). `batch.to_pylist()` at `cursor.py:281` is the whole
> value path and pyarrow, not Semolina, decides the Python type. Adding a `Decimal(`, `float(`,
> or `int(` conversion anywhere on that path inverts the decision: the annotation is corrected to
> the value, never the reverse.

**Verification command a plan can run:**

```bash
git diff --name-only <base>..HEAD | grep -E 'src/semolina/(cursor|acursor|results)\.py' && exit 1 || exit 0
```

## The DuckDB map gaps, measured

**This is new evidence produced by this research session, and it should change what TYPE-05
targets.** Measured through the real ADBC path — `adbc_driver_duckdb.dbapi`, the same driver
`create_engine(DuckDBConfig(...))` uses — on duckdb 1.5.5 / pyarrow 24.0.0. The `DESCRIBE`
column reproduces exactly the string `duckdb_type_to_python` receives; the value column is what
`batch.to_pylist()` produces, i.e. what a user's `Row` actually holds.

| DDL type | `DESCRIBE SELECT` string | `adbc_execute_schema` Arrow type | `to_pylist()` Python type | Current map | Honest annotation |
|---|---|---|---|---|---|
| `DECIMAL(10,2)` | `DECIMAL(10,2)` | `decimal128(10, 2)` | `decimal.Decimal` | miss → `TODO:` | `decimal.Decimal` (locked, Decision 1) |
| `UUID` | `UUID` | `string` | **`str`** | miss → `TODO:` | `str` — **not `uuid.UUID`** |
| `JSON` | `JSON` | `string` | **`str`** | miss → `TODO:` | `str` — the raw JSON text, unparsed |
| `mood` (ENUM) | `ENUM('sad', 'ok', 'happy')` | `dictionary<values=string, indices=uint8, ordered=0>` | **`str`** | strips to `ENUM`, miss → `TODO:` | `str` |
| `TIMESTAMP_S` | `TIMESTAMP_S` | `timestamp[s]` | `datetime.datetime` | miss → `TODO:` | `datetime.datetime` |
| `TIMESTAMP_MS` | `TIMESTAMP_MS` | `timestamp[ms]` | `datetime.datetime` | miss → `TODO:` | `datetime.datetime` |
| `TIMESTAMP_NS` | `TIMESTAMP_NS` | `timestamp[ns]` | **`pandas._libs.tslibs.timestamps.Timestamp`** | miss → `TODO:` | environment-dependent — see below |
| `INTERVAL` | `INTERVAL` | `month_day_nano_interval` | **`pyarrow.MonthDayNano`** | `datetime.timedelta` | **already wrong today** |
| `HUGEINT` | `HUGEINT` | `decimal128(38, 0)` | **`decimal.Decimal`** | `int` | **already wrong today** |
| `TIMESTAMPTZ` | `TIMESTAMP WITH TIME ZONE` | `timestamp[us, tz=Europe/London]` | `datetime.datetime` (aware) | `datetime.datetime` | correct |

[VERIFIED: `.venv/bin/python` driving `adbc_driver_duckdb.dbapi` over an in-memory DuckDB
1.5.5, this session. Both `adbc_execute_schema` and `to_pylist()` measured in the same process;
the same values were reproduced independently through the plain `duckdb` Python client.]

Three findings the planner has to act on:

**1. `UUID` and `JSON` arrive as `str`.** Annotating `uuid.UUID` would create exactly the
class of defect Decision 1 exists to end, one requirement later, and would make Phase 47's
own artifact score the row `mismatch`. Recommend `str` for both, with the raw type preserved
in a docstring or comment. (Note DuckDB has an `arrow_lossless_conversion` setting that changes
some of these to Arrow extension types; the default is what was measured, and Semolina sets no
such option. [ASSUMED] that the option is not enabled anywhere in the poolhouse config path —
grep `adbc_poolhouse._duckdb_config` before relying on it.)

**2. `TIMESTAMP_NS` is environment-dependent.** From pyarrow 24.0.0's own source,
`.venv/lib/python3.14/site-packages/pyarrow/scalar.pxi:706-725`, verbatim:

```python
    else:
        # TimeUnit_NANO: prefer pandas timestamps if available
        if _pandas_api.have_pandas:
            return _pandas_api.pd.Timestamp(value, tz=tzinfo, unit='ns')
        # otherwise safely truncate to microsecond resolution datetime
        if value % 1000 != 0:
            raise ValueError(
                f"Nanosecond resolution temporal type {value} is not safely "
                "convertible to microseconds to convert to datetime.datetime. "
                "Install pandas to return as Timestamp with nanosecond "
                "support or access the .value attribute."
            )
```

[VERIFIED: pyarrow 24.0.0 `scalar.pxi:706-725`, read this session]

So a `TIMESTAMP_NS` column arrives as `pandas.Timestamp` when pandas is importable, as a
truncated `datetime.datetime` when it is not, and **raises `ValueError`** when it is not and
the value carries sub-microsecond precision. This is the same environment-dependence recorded
as broken window 3. `pandas.Timestamp` is a `datetime.datetime` subclass, so
`datetime.datetime` is a *sound over-approximation* — recommend it, and document the caveat
rather than pretending the row is clean.

**3. Two existing mappings are already wrong** by the standard Decision 1 sets:
`_DUCKDB_TYPE_MAP["INTERVAL"] = "datetime.timedelta"` (value is `pyarrow.MonthDayNano`) and
`_DUCKDB_TYPE_MAP["HUGEINT"] = "int"` (value is `decimal.Decimal`). Neither is named by any
Phase 48 requirement. Flag them as findings; recommend fixing `HUGEINT` → `decimal.Decimal`
(it is literally the Decimal policy applied consistently, and TYPE-03's "the three backends no
longer disagree about money" reads oddly if a HUGEINT still says `int`) and recording `INTERVAL`
as a broken window rather than silently widening scope.

## `semolina.JsonValue` — the alias mechanics (TYPE-06)

The locked decision requires a `semolina.JsonValue` alias because semolina core carries no
pydantic dependency. Python floor is 3.11 (`requires-python = ">=3.11"`,
`[tool.basedpyright] pythonVersion = "3.11"`), which predates PEP 695 `type` statements, so the
recursive alias needs the string form.

**Verified working form** — passes basedpyright at `--pythonversion 3.11 --level error` with
0 errors:

```python
from typing import TypeAlias

JsonValue: TypeAlias = (
    "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"
)
```

[VERIFIED: `.venv/bin/basedpyright --pythonversion 3.11 --level error` on a probe file,
this session → `0 errors, 0 warnings, 0 notes`]

**Runtime subscript also works.** `Dimension[JsonValue]()` where `JsonValue` is a string at
runtime produces `semolina.fields.Dimension[ForwardRef('str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]')]`.
[VERIFIED: executed against the real `semolina.fields`, this session]

Two consequences the planner should know: the alias must be exported from
`src/semolina/__init__.py` and added to `__all__` (currently 22 entries, lines 34-57); and
`__orig_class__` for such a field holds a `ForwardRef`, not a resolved type, which matters if
`--check` reads annotations by import (see below).

## Databricks `interval` and `variant` (TYPE-05, TYPE-06)

`DatabricksEngine.introspect` reads `DESCRIBE TABLE EXTENDED {view_name} AS JSON`
(`src/semolina/engines/databricks.py:169`) and passes `col["type"]` — the whole dict — to
`databricks_type_to_python` (`:184`). The recorded cassette payload shows the shape:

```json
{"name": "revenue", "type": {"name": "bigint"}, "nullable": true, "is_measure": true}
{"name": "country", "type": {"name": "string", "collation": "UTF8_BINARY"}, "nullable": true}
```

[VERIFIED: `tests/integration/cassettes/integration/test_introspect/test_databricks_introspect_metric_view/adbc_driver_manager.dbapi/databricks/000_result.arrow`, read with `pyarrow.ipc.open_file` this session]

Databricks documents the type-object grammar for the shapes this phase needs:

- interval: `{ "name" : "interval", "start_unit": "<start_unit>", "end_unit": "<end_unit>" }`
- decimal: `{ "name" : "decimal", "precision": p, "scale": s }`
- variant: `{ "name" : "variant" }`

[CITED: docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table]

So `databricks_type_to_python` already receives everything it needs. Two notes:

- Databricks has **two** interval families — `YearMonthIntervalType` and `DayTimeIntervalType`
  [CITED: docs.databricks.com/aws/en/sql/language-manual/sql-ref-datatypes] — distinguished by
  `start_unit`/`end_unit`. A day-to-second interval has a natural `datetime.timedelta`
  equivalent; a year-to-month interval does not (a month is not a fixed duration). Mapping both
  to `datetime.timedelta` would be wrong for one of them.
- **No fixture, cassette, or recording anywhere in this repo contains a Databricks interval or
  variant column.** The Databricks integration fixture declares `revenue BIGINT, cost BIGINT`
  (47-TYPE-FIDELITY.md § "Evidence limitations"). So whichever Python type is chosen, it is
  **unmeasured** — mark it `[ASSUMED]` in the plan and consider a
  `checkpoint:human-verify`. [ASSUMED: Arrow representation of a Databricks day-time interval
  over the Foundry ADBC driver]

## DBX-04 — `render_literal` widening

### What the code does today

`Dialect.render_literal` (base, `src/semolina/engines/sql.py:86-128`) and
`DatabricksDialect.render_literal` (`sql.py:386-426`) share one shape: `None` → `NULL`; `bool`
first (because `bool` is an `int` subclass); non-finite float → `ValueError`; `int | float` →
`repr(value)`; `str` → quoted and escaped; **everything else → `NotImplementedError`**.

Databricks escaping, verbatim from `sql.py:419`:

```python
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
```

Backslash first, then quote. The base (Snowflake/DuckDB) form at `sql.py:121` is
`value.replace("'", "''")`. [VERIFIED: src/semolina/engines/sql.py:111-128, 409-426]

`DatabricksDialect.supports_parameterized_queries = False` (`sql.py:376`) is the only dialect
that flips it, so `render_literal` is reached only on Databricks in practice, via
`SQLBuilder._render_literal_sql` (`sql.py:843-880`), which is called from
`build_select_with_params` (`sql.py:839-841`) and from the DuckDB override (`sql.py:1208-1210`).
The post-pass is fully generic — it splits the template on the placeholder and interleaves
`self.dialect.render_literal(param)` — so **only the renderer needs widening; no call site
changes.** [VERIFIED: src/semolina/engines/sql.py:376, 839-841, 843-880, 1208-1210]

### The literal syntax, from official Databricks documentation

**DATE.** Literal form is `DATE 'dateString'`, where dateString is
`'[+|-]yyyy[...]-[m]m-[d]d'`; the `DATE` prefix is case-insensitive; years need at least four
digits; months and days may be one or two digits. Example: `DATE '2020-12-31'`.
[CITED: docs.databricks.com/aws/en/sql/language-manual/data-types/date-type]

**TIMESTAMP.** Literal form is `TIMESTAMP timestampString` with the string
`'[+|-]yyyy[...]-[m]m-[d]d[T][h]h:[m]m:[s]s.[ms][ms][ms][us][us][us][zoneId]'` — up to six
fractional digits, `T` separator optional. "If no zoneId is specified it defaults to session
time zone."
[CITED: docs.databricks.com/aws/en/sql/language-manual/data-types/timestamp-type]

The `zoneId` forms the page lists are: `Z`; a bare offset `+|-[h]h:[m]m`; a prefixed offset
(`UTC+`, `UTC-`, `GMT+`, `GMT-`, `UT+`, `UT-` followed by `+|-h[h]`, `+|-hh[:]mm`,
`+|-hh:mm:ss`, or `+|-hhmmss`); and a region id such as `Europe/Paris`.
[CITED: same page] **Confidence MEDIUM on the bare-offset form specifically** — the page lists
it as its own accepted form, but a summarising read of the same page produced a contradictory
reading, so it was not possible to settle from the doc alone in this session. See Open Question 5.

**DECIMAL vs DOUBLE — this is the one that could silently corrupt a filter.** Databricks
documents the DOUBLE literal grammar as:

> `decimal_digits { D | exponent [ D ] } | digit [ ... ] { exponent [ D ] | [ exponent ] D }`

with the note that the `D` suffix or an `E` exponent "is needed to distinguish DOUBLE from
DECIMAL for fractional values". The DECIMAL literal grammar is
`decimal_digits { [ BD ] | [ exponent BD ] } | digit [ ... ] [ exponent ] BD`, and the `BD`
postfix is **optional**; max precision 38.
[CITED: docs.databricks.com/aws/en/sql/language-manual/data-types/double-type and
docs.databricks.com/aws/en/sql/language-manual/data-types/decimal-type]

**So a bare `10.50` in Databricks SQL is already a DECIMAL, not a DOUBLE.** Spark does not
default fixed-point literals to double. That means `str(Decimal("10.50"))` → `10.50` is a
correct decimal literal and **no `CAST(... AS DECIMAL(p,s))` is required for correctness**.
The precision and scale are inferred from the literal's own digits, and Databricks' type
coercion rules then find a common type with the column — which is a widening, not a truncation.

Two caveats worth a `CAST` anyway if the plan wants belt and braces: a `Decimal` in scientific
notation (`Decimal("1E+2")`, which `str()` renders as `1E+2`) needs the `BD` suffix or an
explicit cast to stay decimal, since a bare exponent form is a DOUBLE; and `Decimal("NaN")` /
`Decimal("Infinity")` have no SQL literal at all and must raise the same way non-finite floats
already do at `sql.py:413-415`.

### Recommended `DatabricksDialect.render_literal` additions

Order matters and is the single easiest thing to get wrong:

1. `datetime.datetime` **before** `datetime.date` — `datetime` is a *subclass* of `date`, so a
   `date` check placed first silently truncates a datetime to `DATE '...'` and drops the time.
2. `decimal.Decimal` — must be its own branch; `isinstance(Decimal("1"), int | float)` is
   `False`, so it currently falls straight through to `NotImplementedError`.
3. Reject non-finite `Decimal` (`.is_nan()` / `.is_infinite()`) with `ValueError`, mirroring the
   existing float rule at `sql.py:413-415`.

Suggested rendering (each value goes through the *existing* string escaper so the audited
escaping site stays single):

| Python value | Rendered literal | Rationale |
|---|---|---|
| `datetime.date(2024, 1, 31)` | `DATE '2024-01-31'` | `isoformat()` matches the documented `yyyy-mm-dd` shape exactly |
| `datetime.datetime(2024, 1, 31, 10, 5)` (naive) | `TIMESTAMP '2024-01-31T10:05:00'` | `isoformat()`; `T` separator is documented as accepted; naive = session time zone |
| `datetime.datetime(..., tzinfo=utc)` | `TIMESTAMP '2024-01-31T10:05:00+00:00'` | `isoformat()` emits the bare-offset form; see Open Question 5 for the `Z`-normalisation alternative |
| `Decimal("10.50")` | `10.50` | bare fixed-point literal is DECIMAL per the DOUBLE-vs-DECIMAL grammar above |

The date/timestamp strings contain no quote or backslash by construction (ISO-8601 alphabet),
so escaping is a no-op — but route them through the same escape path anyway so a future format
change cannot introduce an injection point.

### Scope decision the planner must make

Should the **base** `Dialect.render_literal` also widen? DBX-04 names only Databricks, and
Snowflake/DuckDB never reach `render_literal` because both keep `?` + params. But the base is
the documented "single audited SQL-literal escaping site" (`sql.py:91-93`) and a future dialect
flipping `supports_parameterized_queries` would inherit the gap. **Recommendation:** widen both,
with standard-SQL forms in the base (`DATE '...'`, `TIMESTAMP '...'`, bare decimal). Cheap,
symmetric, and the existing test class `TestRenderLiteralStandardSql` already exercises the base
through `SnowflakeDialect`. Flag it as a deliberate scope choice, not an accident.

## TYPE-07 `--check` — the open design

47-DECISIONS.md never specifies the CLI surface. What follows is the fact base plus a
recommendation per choice. **Every recommendation here is the researcher's, not the
specification's.**

### The existing CLI surface

- Entry point: `semolina = "semolina.cli:app"` (`pyproject.toml` `[project.scripts]`).
- One command, `codegen`, registered at `src/semolina/cli/__init__.py:18-28` with a Rich epilog
  that documents the exit codes.
- Signature (`src/semolina/cli/codegen.py:138-159`):
  `codegen(views: list[str] [Argument], backend: str [--backend/-b], database: str | None [--database/-d, envvar DUCKDB_DATABASE])`.
- Exit-code constants, `src/semolina/cli/codegen.py:25-27`, verbatim:

  ```python
  EXIT_INVALID_BACKEND = 2
  EXIT_VIEW_NOT_FOUND = 3
  EXIT_CONNECTION_ERROR = 4
  ```

  with `0` = success and `1` = unexpected error (`codegen.py:183`, and the epilog table at
  `cli/__init__.py:21-27`). The docs mirror this at `docs/src/how-to/codegen.rst:293-317`.
- Output convention: generated Python goes to **stdout** via `typer.echo` (`codegen.py:188`);
  every diagnostic goes to **stderr** via a module-level Rich `Console(file=sys.stderr,
  stderr=True)` (`codegen.py:20`). The comment at `codegen.py:17-19` records why: "Python source
  output uses typer.echo() so CliRunner captures it correctly."

[VERIFIED: src/semolina/cli/codegen.py:17-27,138-195; src/semolina/cli/__init__.py:11-28;
docs/src/how-to/codegen.rst:293-317]

### How Phase 47 got a result schema without fetching rows

`tests/type_fidelity_probe.py`:

- `ROUTE_EXECUTE_SCHEMA = "execute-schema"` (line 180), `ROUTE_ZERO_ROW = "zero-row"` (line 183)
- `NOT_IMPLEMENTED_ERRORS` (line 212), built by `_resolve_not_implemented_errors()` (line 187)
  from the **installed** driver manager as
  `(NotSupportedError, ProgrammingError, OperationalError)` — resolved from the package rather
  than assumed, with the reasoning in its docstring.
- `@dataclass(frozen=True) class ProbeResult` (line 221) with fields `schema: pyarrow.Schema`
  and `route: str`.
- `probe_schema(cursor: Any, sql: str, params: list[Any]) -> ProbeResult` (line 236), verbatim
  body:

  ```python
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

[VERIFIED: tests/type_fidelity_probe.py:180-262, read this session]

**Yes, `adbc_execute_schema` is the right reuse path** — it is the ADBC 1.1 entry point, it is
what Decision 4's capability table is about, and `probe_schema` already carries the
route-recording Decision 3 asks for. The problem is purely one of location.

### The probe lives in `tests/`, not `src/`

`probe_schema` is in `tests/type_fidelity_probe.py`. A shipped `semolina codegen --check` cannot
import from the test tree. Options:

| Option | Cost | Risk |
|---|---|---|
| **(a) Promote to `src/semolina/codegen/probe.py`; have `tests/type_fidelity_probe.py` import it** | one move + one import edit | The artifact must regenerate byte-identical afterwards (`test_committed_table_is_not_stale`). Also check Phase 47's anti-circularity intent: `probe.py` must **not** import `semolina.codegen.type_map`, or the artifact's result half starts depending on the map. |
| (b) Write a fresh implementation in `src/` and leave the test copy alone | zero coupling risk | Guaranteed drift. The shipped `--check` and the evidence generator would diverge silently, which is the exact failure Phase 47 built the drift guard against. |

**Recommendation: (a).** Add an explicit test asserting `semolina.codegen.probe` does not import
`semolina.codegen.type_map` (an `ast`-walk or an `importlib` module-attribute check), preserving
Phase 47's defence 3 at its new location.

### The missing piece: Arrow → Python annotation

**No such function exists anywhere in the repo.** `--check` compares a *committed Python
annotation* against a *`pyarrow.Schema`*, so one of the two must be translated. Build
`arrow_type_to_python(dtype: pyarrow.DataType) -> str` on `pyarrow.types.is_*` predicates, not
on `str(dtype)` — the string forms are `decimal128(38, 2)`,
`timestamp[us, tz=Europe/London]`, and `dictionary<values=string, indices=uint8, ordered=0>`,
none of which survive naive matching.

The measured Arrow→Python pairs it must reproduce (all from the DuckDB table above, plus the
Snowflake/Databricks cassette rows in `47-TYPE-FIDELITY.md` § "Field type comparison"):

| Arrow | Python |
|---|---|
| `decimal128(p, s)` | `decimal.Decimal` |
| `int8/16/32/64`, `uint*` | `int` |
| `float`, `double` | `float` |
| `string`, `large_string` | `str` |
| `dictionary<values=string, ...>` | `str` |
| `bool` | `bool` |
| `date32`, `date64` | `datetime.date` |
| `timestamp[s\|ms\|us]` | `datetime.datetime` |
| `timestamp[ns]` | `datetime.datetime` (over-approximation — see the pandas caveat) |
| `time32`, `time64` | `datetime.time` |
| `binary`, `large_binary` | `bytes` |
| `month_day_nano_interval` | no clean answer — `TODO:` or `Any` |

This function is also **exactly what Phase 50's DTO-07 needs** ("annotations come from
`adbc_execute_schema`"). Build it as a first-class, documented, tested module rather than a
private helper inside the CLI.

### The design choices, with recommendations

| # | Choice | Options | Recommendation | Rationale |
|---|---|---|---|---|
| 1 | Flag name | `--check` / `--check-annotations` / a `check` subcommand | **`--check` on the existing `codegen` command** | ROADMAP SC4 says "a `--check` mode"; `ruff format --check` and `black --check` set the reader's expectation. A subcommand would duplicate `--backend`/`--database`. |
| 2 | What is being checked | regenerate-and-byte-diff vs per-field annotation comparison | **Per-field comparison against the probed result schema** | TYPE-07's wording is "still match the warehouse's current *result schema*". A byte-diff compares against the *metadata* route and would not satisfy it. Say so explicitly in the plan so a reviewer does not "simplify" it back. |
| 3 | How the committed model is read | import the module vs AST-parse the file | **AST-parse**, with import as a documented fallback | `__orig_class__` does survive at runtime (verified: `Metric[decimal.Decimal \| None]()` → `semolina.fields.Metric[decimal.Decimal \| None]`), so import works — but it executes user code, needs the module importable, and returns a `ForwardRef` for the `JsonValue` case. AST reads `Metric[X]()` subscripts textually with no side effects. |
| 4 | Which route is authoritative | probe vs metadata | **Probe primary, metadata fallback, route always reported** | Decision 3, directly. Print the route (`execute-schema` / `zero-row` / `metadata`) in the output so a green `--check` that silently fell back is visible. |
| 5 | Query shape to probe | full canonical query vs unfiltered | **Unfiltered: all metrics + all dimensions, no WHERE** | Snowflake refuses `ExecuteSchema` with any bound parameter (Decision 3; `47-TYPE-FIDELITY.md` quotes the refusing shape `WHERE "COUNTRY" = ?`). `--check` has no filter to apply anyway. |
| 6 | DuckDB facts-vs-metrics | one query vs two | **Two probes, merged** | `DuckDBSQLBuilder.build_select_with_params` raises `ValueError` when both facts and metrics are present (`sql.py:1160-1165`). `DuckDBEngine.introspect` already solves this by issuing two `DESCRIBE SELECT` statements (`duckdb.py:202-227`) — mirror that. |
| 7 | Exit codes | reuse `1` vs a new constant | **New `EXIT_ANNOTATION_DRIFT = 5`** | `1` is "unexpected error" and a script must distinguish "drift found" from "the tool broke". `5` is the next free value and slots into the existing epilog table and `docs/src/how-to/codegen.rst:293-317`. |
| 8 | Output format | unified diff vs per-field table | **Per-field table to stderr, nothing to stdout on success** | The existing convention is source-to-stdout, diagnostics-to-stderr (`codegen.py:17-20`). A per-field table names the field, the committed annotation, the probed annotation, and the route — a unified diff over regenerated source would not, and it would also flag formatting noise. |
| 9 | Where the model file comes from | a positional path vs `--model`/`--output` | **An explicit `--model PATH` option, required when `--check` is passed** | The existing positional argument is `views`. Overloading it would be ambiguous. Reject `--check` without `--model` via `typer.BadParameter` → `EXIT_INVALID_BACKEND` (2), matching the existing pattern at `codegen.py:99-102`. |
| 10 | Does `semolina codegen` (generation) also become probe-primary? | yes vs no | **No — not in this phase** | Decision 3 is normative but **no Phase 48 requirement asks for it**, and its literal text is Phase 50's DTO-07/DTO-09. Doing it here means a canonical-query builder, offline fallback, and route recording in the generation path — a second phase's worth of work smuggled into this one. **Flag as an explicit plan assumption for user confirmation.** |

### The Databricks blocker that is still open

47-DECISIONS.md Decision 3 says, verbatim: "**And the Databricks route is unverified.** …
If the planner rejects the wrapper, Databricks has neither `ExecuteSchema` nor a fallback, and
that is a Phase 48 blocker rather than a footnote." Broken window 2 is still `open`
(`.planning/WINDOWS.md`), and the follow-up todo
`.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md` exists.

**Plan implication:** `--check` on Databricks cannot be claimed to work until someone runs
`SELECT * FROM (SELECT MEASURE(...) FROM v GROUP BY ALL) WHERE 1=0` against a live workspace.
Either put a `checkpoint:human-verify` on it, or scope `--check`'s acceptance criteria to
DuckDB (live) and Snowflake (cassette) and record Databricks as evidence-limited — which is
what Phase 47 did, honestly, in the same situation.

Also carry forward Decision 4's staleness note: re-read `adbc-drivers/databricks`
`go/statement.go` at the version pinned when this phase executes. The driver was `go/v0.1.3` on
2026-08-12 and 47-RESEARCH.md gave that row a **seven-day** shelf life against its own thirty.
By the time Phase 48 runs, that window has expired.

## Test and snapshot fallout

This is the section most likely to be under-estimated. Every item was located by grep or by
reading the file this session.

### Tests that assert the OLD type map by literal and will go red

| File:line | Assertion | Why it breaks |
|---|---|---|
| `tests/unit/codegen/test_type_map.py:26` | `snowflake_json_type_to_python({"type": "FIXED", "scale": 0}) == "int"` | FIXED → `decimal.Decimal` |
| `tests/unit/codegen/test_type_map.py:30,34` | `... scale 2/10 ... == "float"` | same |
| `tests/unit/codegen/test_type_map.py:178` | `databricks_type_to_python({"name": "decimal"}) == "float"` | → `decimal.Decimal` |
| `tests/unit/codegen/test_type_map.py:357` | `duckdb_type_to_python("DECIMAL(10,2)") is None` | → `decimal.Decimal` |
| `tests/unit/codegen/test_type_map.py:131,256,424` | three parametrised `test_all_*_mappings` tables | every changed key |
| `tests/unit/test_snowflake_engine.py:129` (per 47-RESEARCH.md) | `revenue.data_type == "int"` from a hand-fed `{"type": "FIXED", "scale": 0}` | same |
| `tests/unit/test_databricks_engine.py:244` | `type.name -> Python annotation via databricks_type_to_python` | decimal row if present |
| `tests/unit/test_sql.py:176-179` | `SnowflakeDialect().render_literal(date(2024,1,1))` **raises `NotImplementedError`** | DBX-04, if the base widens |
| `tests/unit/test_sql.py:232-235` | `DatabricksDialect().render_literal(date(2024,1,1))` **raises `NotImplementedError`** | DBX-04, definitely |

Note the last two: DBX-04 does not merely *add* behaviour, it **inverts an explicitly asserted
contract**. The CLAUDE.md "failing test first" rule applies cleanly here — write the new
positive assertion, watch it fail, then flip the negative one in the same commit as the fix.

### Snapshots that will churn

`tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` holds three snapshots. Predicted
changes under Decisions 1 and 2 (this is a prediction, not a measurement — regenerate with
`pytest --snapshot-update` and read the diff):

| Snapshot | Today | Predicted |
|---|---|---|
| `test_codegen_file_backed_duckdb` | `revenue = Metric[int]()`, `cost = Metric[int]()` | `Metric[int \| None]()` — the fixture (`tests/conftest.py:194-231`) is all-INTEGER, so no decimal change here |
| `test_codegen_snowflake_field_types` | `revenue = Metric[int]()` + `import datetime` | `Metric[decimal.Decimal \| None]()` + `import decimal` **and** `import datetime` |
| `test_codegen_databricks_field_types` | `revenue = Metric[int]()`, `cost = Metric[int]()` | `Metric[int \| None]()` |

Dimensions and Facts are unchanged (Decision 2 covers metrics only).
[VERIFIED: tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr and tests/conftest.py:194-231, read this session]

Also expect churn in `tests/unit/codegen/test_python_renderer.py` (any test asserting the
emitted `Metric[...]` string or the import block).

### Phase 47's evidence artifact goes stale — and its canary goes red

Two distinct problems, and they need different answers.

**1. The artifact.** `47-TYPE-FIDELITY.md` § "Field type comparison" has a generated
`Mapped annotation` column produced by running the live type map
(`tests/type_fidelity_probe.py:1172,1209` and `collect_duckdb_rows`). Changing the map changes
those cells, and `classify_verdict` (`tests/type_fidelity_probe.py:351-370`) then flips three
rows from `mismatch` to `match`:

- duckdb `max_order_value`: `TODO: DECIMAL(10,2)` → `decimal.Decimal`
- duckdb `total_order_value`: `TODO: DECIMAL(38,2)` → `decimal.Decimal`
- snowflake `AGG("REVENUE")`: `int` → `decimal.Decimal`

`tests/unit/test_type_fidelity_table.py:204 test_committed_table_is_not_stale` calls
`main(["--check"])` and fails with the message "a stale artifact ships as Phase 48's
specification". So the phase **must** run `just type-fidelity` and commit the regenerated
artifact. Two checks that will *not* break: `test_result_and_mapped_vocabularies_are_disjoint`
(`:220`) compares whole cell values as sets, and `decimal.Decimal` never equals
`decimal128(38, 2)`; and `classify_verdict` itself needs no change, because the artifact's
mapped column comes from `IntrospectedField.data_type`, which carries **no** `| None` (Decision
2's nullability is a renderer concern and never reaches `introspect()`).

Consequence to flag: `47-DECISIONS.md` quotes the old cell values in its own prose ("the mapped
annotation for those same two fields reads `TODO: DECIMAL(38,2)` and `int` respectively").
`47-DECISIONS.md` is normative and human-approved at a blocking checkpoint. **Do not edit it.**
Add a dated forward note in Phase 48's own artifacts instead; a dated decision record correctly
describes what was true when it was decided.

**2. The canary.** `tests/unit/test_type_fidelity_duckdb.py:120
test_decimal_metric_disagrees_by_value` asserts, at line 126:

```python
    assert by_name[PROBE_FIELD].data_type == "TODO: DECIMAL(38,2)"
```

then `decimal128(38, 2)` for the schema and `decimal.Decimal` for the value.
[VERIFIED: tests/unit/test_type_fidelity_duckdb.py:120-134]

This is Phase 47's circular-evidence guard ("A comparison that cannot produce a mismatch is not
measuring anything" — 47-RESEARCH.md, defence 1). Phase 48 legitimately makes the two columns
agree, which is the *success* condition, not a regression. **Deleting the test destroys the
guard.** Recommended: re-point it at a type the map still misses after this phase — DuckDB
`STRUCT(...)`, `MAP(...)`, or `LIST(...)`, all of which stay `TODO:` and are already covered by
`tests/unit/codegen/test_type_map.py:361-377` — and rename it so its intent survives (e.g.
`test_an_unmapped_type_still_disagrees_by_value`). Convert the decimal assertion into a positive
`agrees_by_value` test so both halves of the story stay committed.

### Where each requirement's tests should go

| Req | Closest existing module | Note |
|---|---|---|
| TYPE-03 | `tests/unit/codegen/test_type_map.py` (three `Test*` classes, one per backend) | Plus one cross-backend test asserting all three mappers return `"decimal.Decimal"` — that is literally SC1 |
| TYPE-04 | `tests/unit/codegen/test_python_renderer.py` + the `.ambr` snapshots | Assert `Metric[... \| None]` **and** that `import datetime` still appears for a nullable datetime metric — the landmine test |
| TYPE-05 | `tests/unit/codegen/test_type_map.py` | Parametrise over the measured DuckDB table above |
| TYPE-06 | `tests/unit/codegen/test_type_map.py` + `tests/unit/test_models.py` (or a new export test) | `semolina.JsonValue` must be importable and in `__all__` |
| TYPE-07 | `tests/unit/codegen/test_cli.py` (CliRunner precedent) + a new `tests/unit/codegen/test_arrow_map.py` | `test_codegen_file_backed_duckdb` shows the live-DuckDB CLI pattern |
| DBX-04 | `tests/unit/test_sql.py::TestRenderLiteralDatabricks` (line 188) and `TestDatabricksLiteralInlining` (line 917) | The second class asserts the *inlined SQL*, which is where the end-to-end DBX-04 claim lives offline |

### Can the TYPE-03 "three backends agree" claim be asserted from existing recordings?

Partly, and the plan should say which part.

- **At the mapper level: yes, fully offline, no cassette needed.** Assert
  `snowflake_json_type_to_python({"type": "FIXED", "scale": 0})`,
  `databricks_type_to_python({"name": "decimal", "precision": 10, "scale": 2})`, and
  `duckdb_type_to_python("DECIMAL(10,2)")` all return `"decimal.Decimal"`. That *is* SC1's
  substance and it needs nothing but the three pure functions.
- **At the end-to-end codegen level: DuckDB yes, Snowflake and Databricks only through the
  existing mocked seams.** `tests/unit/codegen/test_codegen_e2e.py` drives Snowflake and
  Databricks over a **mocked ADBC-cursor seam**, not over cassettes (its module docstring says
  so). So the E2E snapshots can carry the claim without any recording.
- **Against a real warehouse decimal column: no, and it cannot be fixed cheaply.**
  `47-TYPE-FIDELITY.md` § "Evidence limitations" records that the Snowflake fixture declares
  bare `NUMBER` (= `NUMBER(38,0)`, already max precision, cannot widen) and that **the
  Databricks fixture has no decimal column at all** (`revenue BIGINT, cost BIGINT`). Closing
  either needs a live re-recording session, which is operator-gated. Two follow-up todos already
  exist. **Do not plan a recording as a task; plan the claim as evidence-limited and say so.**

Snapshot files to watch: `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` is the only
`.ambr` in the repo.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Getting a query's result schema | A `DESCRIBE`-output parser | `cursor.adbc_execute_schema(sql, params)` with the zero-row fallback, i.e. the existing `probe_schema` | The driver already resolves it; a parser reimplements warehouse type inference. Already written and tested. |
| Classifying an Arrow type | `str(dtype).startswith(...)` | `pyarrow.types.is_decimal` / `is_timestamp` / `is_dictionary` … | String forms carry parameters (`decimal128(38, 2)`, `timestamp[us, tz=...]`) that break prefix matching |
| Deciding which exception means NOT_IMPLEMENTED | Guessing `NotSupportedError` | `tests/type_fidelity_probe.py:187` `_resolve_not_implemented_errors()` | It reads the installed driver manager and catches all three plausible classes, with the reasoning recorded. 47-RESEARCH.md assumption A4 was open precisely here. |
| Escaping a SQL literal | A second escaper for dates | The existing `render_literal` string branch (`sql.py:419`) | `sql.py:91-93` calls it "the single audited SQL-literal escaping site". Keep it single. |
| Substituting placeholders with literals | `str.replace` | `SQLBuilder._render_literal_sql` (`sql.py:843`) | Its docstring documents the exact bug a naive replace causes: a rendered literal containing `?` gets re-matched |
| Reading generic subscripts off a model | Regex over source | `ast` module, or `__orig_class__` if importing | Both verified to work this session |
| Formatting generated source | A custom formatter | `format_with_ruff` (`python_renderer.py:215`) | Already there, already handles the ruff-absent case |

**Key insight:** almost every mechanism this phase needs already exists somewhere in the repo —
the work is moving `probe_schema` into `src/`, adding one genuinely new pure function
(`arrow_type_to_python`), and editing a dictionary. The expensive part is the fallout, not the
mechanism.

## Common Pitfalls

### Pitfall 1: applying `| None` in the type map, which silently drops `import datetime`

**What goes wrong:** generated models raise `NameError: name 'datetime' is not defined` on
import — but only for views that have a datetime-typed *metric*, so most tests still pass.
**Why it happens:** `needs_datetime` at `python_renderer.py:175` is an exact-string membership
test against `_DATETIME_TYPES`, evaluated on `IntrospectedField.data_type` before the renderer
sees it.
**How to avoid:** decorate nullability inside `_build_model_context`, and derive imports from
the *resolved* `_FieldContext.data_type` strings by module prefix rather than exact match.
**Warning sign:** a generated snapshot that contains `Metric[datetime.datetime | None]` but no
`import datetime` line.

### Pitfall 2: `datetime` before `date` in `render_literal`

**What goes wrong:** `.where(Model.ts == datetime(2024,1,1,10,5))` silently becomes
`DATE '2024-01-01'` and returns the wrong rows — no error, no traceback.
**Why it happens:** `datetime.datetime` is a subclass of `datetime.date`, so an
`isinstance(value, datetime.date)` branch placed first swallows both.
**How to avoid:** test `datetime.datetime` first. Assert it directly:
`render_literal(datetime(2024,1,1,10,5))` must contain `10:05`.
**Warning sign:** a Databricks filter on a timestamp returning a whole day's rows.

### Pitfall 3: assuming a bare decimal literal is a DOUBLE in Spark

**What goes wrong:** wrapping every decimal in `CAST(... AS DECIMAL(38,18))` "for safety",
which changes the comparison's type coercion and can reject a filter Spark would otherwise
accept.
**Why it happens:** most SQL dialects parse `10.50` as a float.
**How to avoid:** Databricks documents the opposite — the `D` suffix or an exponent is what
makes a fractional literal a DOUBLE
[CITED: docs.databricks.com/aws/en/sql/language-manual/data-types/double-type]. A bare `10.50`
is already DECIMAL. Only the exponent form (`Decimal("1E+2")` → `str()` gives `1E+2`) needs `BD`
or a cast.
**Warning sign:** generated SQL full of `CAST` wrappers that the recorded cassettes never had.

### Pitfall 4: deleting Phase 47's canary because it "now fails"

**What goes wrong:** the circularity guard that makes the whole type-fidelity artifact
trustworthy disappears in a green-tests commit.
**Why it happens:** `test_decimal_metric_disagrees_by_value` is *designed* to fail when the two
columns agree, and this phase makes them agree.
**How to avoid:** re-point it at a still-unmapped DuckDB type (`STRUCT`/`MAP`/`LIST`) and add a
positive `agrees_by_value` twin for the decimal case.
**Warning sign:** a diff that removes an assertion without adding one.

### Pitfall 5: annotating `uuid.UUID` / a parsed JSON type for TYPE-05

**What goes wrong:** the phase closes TYPE-05 by re-opening TYPE-03's defect on different
columns — an annotation that does not describe the value.
**Why it happens:** "give `UUID` a concrete Python type" reads as "`uuid.UUID`".
**How to avoid:** the measured value is `str` (see the measured table). Annotate what arrives.
**Warning sign:** any TYPE-05 target type that no measurement in this document supports.

### Pitfall 6: forgetting the second test suite

**What goes wrong:** `just test` fails in `semolina-jaffle-shop` after the root suite is green.
**Why it happens:** `just test` runs two independent uv projects, and jaffle-shop's fixtures
declare `DECIMAL(10,2)` / `DECIMAL(12,2)` columns
(`semolina-jaffle-shop/tests/conftest.py:35-40,94-95,158`).
**How to avoid:** run `just test`, not `uv run pytest`, at each wave gate.
**Warning sign:** a plan whose verification command is `uv run pytest`.

### Pitfall 7: the regenerated artifact not being byte-identical

**What goes wrong:** `test_committed_table_is_not_stale` stays red after `just type-fidelity`.
**Why it happens:** broken window 3 — the artifact's pandas row is environment-dependent;
`uv sync --dev` without `--extra all` flips it to `not measured`.
**How to avoid:** regenerate under the same environment CI uses (`--dev --extra all`).
**Warning sign:** the only diff hunk being the pandas row.

## Code Examples

### The value path the fence protects (do not modify)

```python
# Source: src/semolina/cursor.py:279-285, read this session
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row
```

### The probe to promote into `src/`

```python
# Source: tests/type_fidelity_probe.py:236-262, read this session
def probe_schema(cursor: Any, sql: str, params: list[Any]) -> ProbeResult:
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

Note `params or None` on the fallback branch and plain `params` on the primary — under cassette
replay the parameter list is part of the lookup key, and `[]` and `None` are different keys
(47-RESEARCH.md, pitfall 3).

### The recursive JSON alias, basedpyright-clean at pythonVersion 3.11

```python
# Verified: basedpyright --pythonversion 3.11 --level error -> 0 errors, this session
from typing import TypeAlias

JsonValue: TypeAlias = (
    "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"
)
```

### Reading a committed annotation without importing the module

```python
# Verified this session that the runtime alternative also works:
#   Metric[decimal.Decimal | None]()  ->  __orig_class__ is
#   semolina.fields.Metric[decimal.Decimal | None]
# The AST route needs no import and executes no user code:
import ast

tree = ast.parse(Path("models.py").read_text(encoding="utf-8"))
# each field is  <name> = Metric[<annotation>](...)  -> ast.Assign whose value is
# an ast.Call whose func is an ast.Subscript; ast.unparse(node.slice) recovers the
# annotation string exactly as written.
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| ADBC driver docs at `arrow.apache.org/adbc/current/driver/*` | Drivers live at the ADBC Driver Foundry (`github.com/adbc-drivers/*`); the Apache URLs serve a JS redirect stub | before 2026-08 | Re-read `adbc-drivers/databricks` `go/statement.go` at the pinned version, per Decision 4's staleness note |
| Databricks ADBC driver has no `ExecuteSchema` | still true at `go/v0.1.3` (2026-08-12) | — | **Seven-day shelf life** on that row per 47-RESEARCH.md; it has expired. Re-check before planning `--check`'s Databricks story. |
| `render_literal` raises on date/decimal | DBX-04 widens it | this phase | The v0.6 close explicitly deferred this: `STATE.md` § "Deferred Items" — "`render_literal` Date/Decimal support … Deferred — widen when a real case needs it". Decision 1 is that case. |

**Deprecated / outdated in this repo's assumptions:**

- `_DUCKDB_TYPE_MAP["INTERVAL"] = "datetime.timedelta"` — the value is `pyarrow.MonthDayNano`.
  Measured this session. Not named by any Phase 48 requirement.
- `_DUCKDB_TYPE_MAP["HUGEINT"] = "int"` — the value is `decimal.Decimal`. Measured this session.
- 47-RESEARCH.md assumption A4 (which exception class means NOT_IMPLEMENTED) is **closed** by
  `_resolve_not_implemented_errors()`; A1 and A2 are closed by the artifact; **A3 (polars) and
  A5 (Databricks zero-row fallback) remain open**, and A5 is a Phase 48 concern.

## Runtime State Inventory

Not applicable — this is not a rename, refactor, or migration phase. No stored data, live
service config, OS-registered state, secret, or build artifact carries a value this phase
changes. The one persistent artifact affected is a committed file in the repo
(`47-TYPE-FIDELITY.md`), handled in § "Test and snapshot fallout".

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| `duckdb` + `semantic_views` community extension | live DuckDB codegen + `--check` tests | yes | 1.5.5 | none needed |
| `adbc_driver_duckdb` | DuckDB ADBC path | yes | present in `.venv`; exercised this session | none needed |
| `adbc_driver_snowflake` | Snowflake cassette replay | yes | 1.10.0 | none needed |
| `pytest-adbc-replay` | cassette replay | yes | 1.1.1 | none needed |
| `pyarrow` | Arrow→Python mapper | yes | 24.0.0 | none needed |
| `basedpyright` | strict typecheck gate | yes | verified by running it this session | none |
| `ruff` (dev group **and** `codegen-lint` extra) | `format_with_ruff` subprocess path | yes in dev | `>=0.15.1` | `ruff_available()` already degrades gracefully |
| `pandas` | only affects the `TIMESTAMP_NS` value type and the artifact's pandas row | **transitively, via `databricks-sql-connector[pyarrow]` under the `all` extra only** | 2.3.3 per the artifact | broken window 3; regenerate the artifact under `--dev --extra all` |
| Live Databricks workspace | verifying the zero-row fallback (broken window 2) and any `interval` measurement | **no** | — | evidence-limited claim + `checkpoint:human-verify`, as Phase 47 did |
| Live Snowflake credentials | a decimal-widening recording | **no** | — | follow-up todo `2026-08-12-record-snowflake-introspection-cassette.md` |

**Missing dependencies with no fallback:** none block the phase.
**Missing with fallback:** live Databricks (→ scope `--check`'s Databricks acceptance to
evidence-limited, or gate on a human checkpoint); live Snowflake (→ mapper-level and
mocked-seam assertions carry TYPE-03).

## Validation Architecture

`workflow.nyquist_validation` is absent from `.planning/config.json`, so it is treated as
enabled and this section is included.

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest, declared `>=8.0.0` in the `dev` group |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests", "src"]`, `addopts = ["-v", "--doctest-modules", "--doctest-continue-on-failure"]` |
| Quick run command | `uv run pytest tests/unit/codegen tests/unit/test_sql.py -x` |
| Full suite command | `just test` (root `uv run pytest` **plus** `pushd semolina-jaffle-shop; uv run pytest`) |
| Snapshot tool | `syrupy` — sole snapshot file `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` |
| Cassette config | `adbc_cassette_dir = "tests/integration/cassettes"`, `adbc_record_mode = "none"` |

**Doctest warning:** `--doctest-modules` over `testpaths = ["tests", "src"]` means every
`Example:` block in a new `src/semolina/codegen/arrow_map.py` or `probe.py` docstring is
executed. Keep them runnable and correct, or make them non-executing prose.

### Phase Requirements → Test Map

| Req | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| TYPE-03 | All three mappers return `"decimal.Decimal"` for an equivalent decimal column | unit | `uv run pytest tests/unit/codegen/test_type_map.py -x` | exists — assertions change |
| TYPE-03 | End-to-end codegen emits the same annotation on all three backends | snapshot | `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` | exists — `.ambr` regenerates |
| TYPE-04 | A metric renders `Metric[T \| None]`; a dimension does not | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -x` | exists |
| TYPE-04 | A nullable datetime metric still emits `import datetime` (pitfall 1 guard) | unit | `uv run pytest tests/unit/codegen/test_python_renderer.py -k import -x` | ❌ Wave 0 |
| TYPE-05 | Each measured DuckDB gap maps to the measured Python type | unit (parametrised) | `uv run pytest tests/unit/codegen/test_type_map.py -k duckdb -x` | exists — new cases |
| TYPE-05 | Databricks `interval` resolves from `start_unit`/`end_unit` | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k interval -x` | ❌ Wave 0 |
| TYPE-06 | VARIANT maps to the `JsonValue` union; `semolina.JsonValue` is importable and in `__all__` | unit | `uv run pytest tests/unit/codegen/test_type_map.py -k variant tests/unit/test_models.py -x` | ❌ Wave 0 |
| TYPE-07 | `arrow_type_to_python` covers every Arrow type the three backends produce | unit | `uv run pytest tests/unit/codegen/test_arrow_map.py -x` | ❌ Wave 0 |
| TYPE-07 | `--check` exits 0 on a matching model and non-zero on a drifted one, over live DuckDB, fetching no rows | integration (live DuckDB via CliRunner) | `uv run pytest tests/unit/codegen/test_cli.py -k check -x` | ❌ Wave 0 |
| TYPE-07 | `--check` reports which route produced the schema | unit | same module | ❌ Wave 0 |
| DBX-04 | `render_literal` renders `date`, naive `datetime`, aware `datetime`, `Decimal` | unit | `uv run pytest tests/unit/test_sql.py -k RenderLiteralDatabricks -x` | exists — negative assertions invert |
| DBX-04 | A `.where()` on a date produces inlined SQL with `DATE '...'` and empty params | unit | `uv run pytest tests/unit/test_sql.py -k DatabricksLiteralInlining -x` | exists |
| DBX-04 | Non-finite `Decimal` raises `ValueError`, not `NotImplementedError` | unit | same | ❌ Wave 0 |
| all | Phase 47's artifact regenerates byte-identically after the map change | unit | `uv run pytest tests/unit/test_type_fidelity_table.py -x` | exists — needs `just type-fidelity` first |
| all | The circularity canary still produces a real mismatch on a still-unmapped type | unit | `uv run pytest tests/unit/test_type_fidelity_duckdb.py -x` | exists — must be re-pointed |
| fence | `cursor.py` / `acursor.py` / `results.py` untouched | shell gate | `git diff --name-only <base>..HEAD \| grep -E 'src/semolina/(cursor\|acursor\|results)\.py' && exit 1 \|\| exit 0` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/codegen tests/unit/test_sql.py -x`
- **Per wave merge:** `just test` (both suites) + `prek run --all-files`
- **Phase gate:** `just test` green, `prek run --all-files` green, `just docs-build` green under
  `-W`, and `uv run python tests/type_fidelity_probe.py --check` exit 0, before
  `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/codegen/test_arrow_map.py` — covers TYPE-07's mapper
- [ ] `tests/unit/codegen/test_cli.py` — new `--check` cases (module exists; cases do not)
- [ ] `tests/unit/codegen/test_python_renderer.py` — the import-emission guard for TYPE-04
- [ ] `tests/unit/test_sql.py` — positive date/datetime/Decimal cases before the negatives flip
- [ ] a test asserting `semolina.codegen.probe` does not import `semolina.codegen.type_map`
      (preserves Phase 47 defence 3 at the promoted location)
- [ ] the `cursor.py`/`results.py` untouched shell gate
- [ ] Framework install: none

## Security Domain

`security_enforcement` is absent from `.planning/config.json` (absent = enabled), so this
section is included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | no | No auth surface touched |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | None |
| V5 Input Validation | **yes** | DBX-04 adds three new value types to the SQL-literal path. Every one must route through the existing audited escaper at `sql.py:419`; `--check` interpolates view names into SQL and must reuse `_sql_str_literal` (`src/semolina/engines/duckdb.py:42`) rather than f-stringing |
| V6 Cryptography | no | None |
| V7 Error handling & logging | **yes** | `--check`'s drift report must name fields and types, never row values. A probe fetches no rows by construction; the zero-row fallback returns none. Keep it that way. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| SQL injection through a widened `render_literal` | Tampering | ISO-8601 date/timestamp strings and `Decimal` digit strings have no quote or backslash by construction, but route them through the same `.replace("\\", "\\\\").replace("'", "\\'")` path so the audited site stays single. Add adversarial unit tests mirroring the existing `O'Reilly` / `a\b` / `'; DROP` cases at `tests/unit/test_sql.py:195-211`. |
| Injection through catalog-sourced identifiers in `--check`'s canonical query | Tampering | Build the query through `SQLBuilder` / `DuckDBSQLBuilder`, or through `_sql_str_literal` for `semantic_view('...')` arguments — never by f-string |
| Arbitrary code execution when reading a committed model | Tampering / Elevation | Prefer `ast.parse` over `importlib.import_module`. If import is chosen, document it and note that the CLI already imports dotted paths at `cli/codegen.py:130-135` |
| Row data leaking into a `--check` report | Information disclosure | Report types and field names only; assert it in a test |
| Credentials leaking into a new recording | Information disclosure | `adbc_scrub_keys = ["password", "token", "access_token"]` is already configured. If any recording happens, grep the cassette before committing — Phase 47's verification did exactly this. |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Phase 48 does **not** need to make `semolina codegen`'s generation path probe-primary; Decision 3's promotion lands in Phase 50 via DTO-07/DTO-09 | TYPE-07 choice 10 | **High.** If wrong, the phase is roughly twice the size — a canonical-query builder, an offline fallback, and route recording in the generation path. Needs explicit user confirmation before planning. |
| A2 | DuckDB `UUID` and `JSON` should annotate as `str`, matching the measured value | The DuckDB map gaps | Medium. If a `uuid.UUID` annotation is wanted instead, it is a deliberate departure from Decision 1's principle and should be recorded as such, not slipped in. |
| A3 | `TIMESTAMP_NS` annotating as `datetime.datetime` is an acceptable over-approximation (`pandas.Timestamp` is a `datetime.datetime` subclass) | The DuckDB map gaps | Low-medium. Correct as a supertype; wrong if the project wants annotations to name the exact runtime class. |
| A4 | A Databricks day-time `interval` arrives as something `datetime.timedelta` describes | Databricks `interval` | Medium. **Unmeasured — no fixture, cassette, or recording in the repo has an interval column.** The year-month family almost certainly needs a different answer. |
| A5 | A Databricks `VARIANT` arrives as a JSON string, which the `JsonValue` union covers as one of its members | TYPE-06 | Low. `JsonValue` includes `str`, so the annotation is honest-but-loose either way. Worth one doc sentence: the user gets JSON *text*, not a parsed `dict`. |
| A6 | Databricks accepts a bare `+00:00` offset in a `TIMESTAMP` literal | DBX-04 | Medium. The doc lists `+\|-[h]h:[m]m` as its own accepted zoneId form, but a second reading of the same page contradicted it. Mitigation: normalise aware datetimes to UTC and emit `Z`, which is unambiguously listed. |
| A7 | The Databricks `DESCRIBE ... AS JSON` type object for an interval reads `{"name": "interval", "start_unit": ..., "end_unit": ...}` in the version this repo targets | Databricks `interval` | Medium. Cited to current Databricks docs; not confirmed against a recording, because none exists. |
| A8 | `adbc-poolhouse`'s DuckDB config does not enable `arrow_lossless_conversion` or any option that would change UUID/JSON/ENUM Arrow representations | The DuckDB map gaps | Low. One grep of `adbc_poolhouse._duckdb_config` closes it. |
| A9 | The predicted `.ambr` snapshot deltas are exactly the three rows listed | Test and snapshot fallout | Low. It is a prediction; `pytest --snapshot-update` settles it in one run. |
| A10 | The `adbc-drivers/databricks` `ExecuteSchema` answer is still `no` when this phase executes | TYPE-07 Databricks blocker | Medium. Decision 4 gives that row a seven-day shelf life from 2026-08-12; it has expired. Re-read `go/statement.go` at the pinned version as the first task of the `--check` plan. |

## Open Questions

1. **Which Python type does each TYPE-05 gap map to?**
   - What we know: the measured Arrow and Python types for every DuckDB gap (table above);
     the authoritative Databricks type-object grammar for `interval`.
   - What's unclear: 47-DECISIONS.md explicitly declines to specify them.
   - Recommendation: `DECIMAL`→`decimal.Decimal` (locked), `UUID`→`str`, `JSON`→`str`,
     `ENUM`→`str`, `TIMESTAMP_S|_MS|_NS`→`datetime.datetime`, Databricks day-time
     `interval`→`datetime.timedelta`, year-month `interval`→ keep `TODO:`. Gate the four
     non-obvious ones behind a `checkpoint:human-verify` — they are a public annotation contract
     that Phases 49 and 50 build on.

2. **Does `semolina codegen` (generation) become probe-primary in this phase?** (A1)
   - What we know: Decision 3 says the result schema is primary and codegen records the route.
     No Phase 48 requirement asks for it. Phase 50's DTO-07 and DTO-09 restate it almost word
     for word.
   - Recommendation: **no** — scope Decision 3's implementation to `--check` here and to
     generation in Phase 50. Record it as an explicit plan assumption and confirm with the user
     before the first plan is written. This is the single largest scoping lever in the phase.

3. **What happens to Phase 47's canary and its committed artifact?**
   - What we know: the artifact's staleness guard forces a regeneration; the canary's literal
     assertion is falsified by design.
   - Recommendation: regenerate and commit the artifact (broken window 3 means doing it under
     `--dev --extra all`); re-point the canary at `STRUCT`/`MAP`/`LIST` and add a positive
     "agrees by value" twin for the decimal case; leave `47-DECISIONS.md` untouched and note the
     supersession in Phase 48's own summary.

4. **Does the base `Dialect.render_literal` widen too, or only Databricks?**
   - What we know: DBX-04 names Databricks; the base is the documented single audited escaping
     site; only Databricks reaches it today.
   - Recommendation: widen both. Cheap, symmetric, and `TestRenderLiteralStandardSql` already
     exercises the base.

5. **Aware-datetime rendering on Databricks: bare offset or `Z`?** (A6)
   - What we know: `Z` is unambiguously listed; the bare `+|-[h]h:[m]m` form is listed but a
     re-read of the same page produced a contradictory summary.
   - Recommendation: normalise to UTC and emit `TIMESTAMP '...Z'`. Same instant, no ambiguity,
     one extra line. If the plan prefers `isoformat()`'s native offset, put a
     `checkpoint:human-verify` on a live Databricks query — this cannot be settled from the repo.

6. **Can `--check`'s Databricks path be claimed at all this phase?**
   - What we know: Databricks has no `ExecuteSchema`, and nobody has confirmed its metric-view
     planner accepts the `WHERE 1=0` wrapper (broken window 2, still open).
   - Recommendation: scope `--check`'s verifiable acceptance to DuckDB (live) and Snowflake
     (cassette); record Databricks as evidence-limited with the existing follow-up todo, exactly
     as Phase 47 did. **Do not write an acceptance criterion nobody can run.**

7. **The two already-wrong DuckDB mappings (`INTERVAL`, `HUGEINT`).**
   - What we know: measured this session; neither is named by a Phase 48 requirement.
   - Recommendation: fix `HUGEINT` → `decimal.Decimal` (it is the Decimal policy applied
     consistently, and leaving it as `int` makes TYPE-03's "no longer disagree about money"
     read false). Record `INTERVAL` as a broken window rather than widening scope on a type
     with no good Python answer.

## Docs Impact

Two pages change, and one of them is derived from a normative document.

| Page | Change | Why |
|---|---|---|
| `docs/src/explanation/type-fidelity.rst` | **The closing `.. note::` at lines 152-165 becomes false.** It currently says, verbatim, "The Python annotations that `semolina codegen` writes into a generated model are a separate matter, and they do not all agree with that yet… A Snowflake `NUMBER` column may still be annotated `int` or `float`, a Databricks `decimal` column `float`, and a DuckDB `DECIMAL` column `Any` with a `TODO` comment. The type map is being brought into line with the values described here. Until it is, trust the value you get at runtime over the annotation in a generated model". Phase 48 is the thing that note is waiting for. Remove or rewrite it. | The page is derived one-directionally from `47-DECISIONS.md`; the note is the only part that describes a *temporary* state |
| `docs/src/how-to/codegen.rst` | Three sections. § "Handle TODO comments" (lines 275-291) lists VARIANT among the types that get `Any` — no longer true under TYPE-06. § "Exit codes" (lines 293-317) needs the new drift code. A new § documenting `--check` usage. § "Understand field type mapping" (lines 251-273) may want a nullability row. | How-to is where `--check` usage belongs; the exit-code table is duplicated between the doc and `cli/__init__.py`'s epilog and both must move together |

**Mandatory skill.** Per `./CLAUDE.md`, any plan touching either page must carry
`@.claude/skills/semolina-docs-author/SKILL.md` in its `<execution_context>`. The
`type-fidelity.rst` note rewrite is a targeted correction rather than a >50% rewrite, so the
"minor fixes" carve-out does not obviously apply — it changes a substantive claim. Treat it as
requiring the skill. The new `--check` how-to section is new-page-equivalent content and
definitely requires it.

**Do not edit `47-DECISIONS.md`.** It is normative, dated, and was approved at a blocking human
checkpoint. Its § "Derived documentation" states the direction of the dependency: "This document
is normative and that page is derived from it… If the two ever disagree, this one is right and
the page is wrong." Phase 48 changes the *code*, not the decision.

## Sources

### Primary (HIGH confidence — read or executed this session)

- `src/semolina/codegen/type_map.py` (whole file), `codegen/python_renderer.py` (whole file),
  `codegen/introspector.py`, `codegen/templates/python_model.py.jinja2`
- `src/semolina/engines/sql.py` (whole file), `engines/databricks.py:150-209`,
  `engines/duckdb.py:190-254`, `engines/snowflake.py` (TODO site)
- `src/semolina/cursor.py:255-305`, `src/semolina/results.py:1-40`, `src/semolina/__init__.py`
- `src/semolina/cli/codegen.py` (whole file), `src/semolina/cli/__init__.py`
- `tests/type_fidelity_probe.py:178-370` (probe surface, verdict classifier)
- `tests/unit/test_sql.py:172-236`, `tests/unit/test_type_fidelity_duckdb.py:120-134`,
  `tests/unit/test_type_fidelity_table.py:196-234`, `tests/unit/codegen/test_type_map.py`
- `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`, `tests/unit/codegen/test_codegen_e2e.py:1-80`,
  `tests/conftest.py:194-231`
- `tests/integration/cassettes/.../test_databricks_introspect_metric_view/.../000_result.arrow`
  (read with `pyarrow.ipc.open_file`)
- `pyproject.toml`, `justfile`, `.planning/config.json`, `.planning/WINDOWS.md`,
  `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`
- `47-DECISIONS.md`, `47-TYPE-FIDELITY.md`, `47-RESEARCH.md`, `47-VERIFICATION.md`
- `.venv/lib/python3.14/site-packages/pyarrow/scalar.pxi:700-835` (nanosecond timestamp conversion)
- **Live measurement:** in-memory DuckDB 1.5.5 through `adbc_driver_duckdb.dbapi` —
  `DESCRIBE SELECT` type names, `adbc_execute_schema` Arrow types, and `to_pylist()` Python
  types for `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S|_MS|_NS`/`TIMESTAMP`/`TIMESTAMPTZ`/
  `INTERVAL`/`HUGEINT`; reproduced independently through the plain `duckdb` Python client
- **Live typecheck:** `basedpyright --pythonversion 3.11 --level error` on the recursive
  `JsonValue` alias → 0 errors
- **Live runtime check:** `Metric[decimal.Decimal | None]()` retains `__orig_class__`;
  `Dimension[JsonValue]()` accepts the string alias as a `ForwardRef`

### Secondary (MEDIUM confidence — official vendor documentation)

- docs.databricks.com/aws/en/sql/language-manual/data-types/date-type — `DATE 'dateString'` grammar
- docs.databricks.com/aws/en/sql/language-manual/data-types/timestamp-type — `TIMESTAMP` grammar,
  fractional seconds, zoneId forms, session-timezone default
- docs.databricks.com/aws/en/sql/language-manual/data-types/decimal-type — DECIMAL literal
  grammar, optional `BD`, max precision 38
- docs.databricks.com/aws/en/sql/language-manual/data-types/double-type — DOUBLE literal grammar;
  the `D`-suffix/exponent rule that makes a bare fractional literal a DECIMAL
- docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table — the
  `AS JSON` type-object grammar for interval, decimal, and variant
- docs.databricks.com/aws/en/sql/language-manual/sql-ref-datatypes — the two interval type
  families and VARIANT

### Tertiary (LOW confidence — noted, not relied upon)

- The zoneId bare-offset reading (A6) — the same page yielded two contradictory summaries in one
  session; treated as an open question rather than a fact

## Metadata

**Confidence breakdown:**

- Current type-map and renderer surface: **HIGH** — every identifier, line number, and literal
  quoted from a file read this session
- The `cursor.py`/`results.py` scope fence: **HIGH** — line verified verbatim and the
  no-coercion claim re-grepped rather than inherited
- DuckDB map-gap target types: **HIGH** on the measurement, **MEDIUM** on the policy choice
  (the specification declines to make it)
- Databricks literal syntax: **HIGH** on DATE, DECIMAL-vs-DOUBLE, and the type-object grammar;
  **MEDIUM** on the aware-timestamp offset form (A6)
- Databricks `interval` target type: **LOW** — unmeasured, no fixture or cassette exists
- `--check` design: **MEDIUM** — the mechanics are HIGH (CLI surface, probe, exit codes all read
  from source), the design choices are recommendations against a silent specification
- Test and snapshot fallout: **HIGH** on which tests break, **MEDIUM** on the exact predicted
  snapshot text

**Research date:** 2026-08-12
**Valid until:** 2026-09-11 (30 days) — except the `adbc-drivers/databricks` `ExecuteSchema`
row, which 47-RESEARCH.md gave a **seven-day** shelf life from 2026-08-12 and which is therefore
already expired. Re-read `go/statement.go` at the pinned version before planning `--check`'s
Databricks story.
