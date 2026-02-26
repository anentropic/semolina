# Phase 20: Reverse Codegen - Research

**Researched:** 2026-02-24
**Domain:** Warehouse metadata introspection + Python code generation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **CLI**: Command name stays `cubano codegen`, replacing the broken forward codegen in-place
- **Input**: One or more schema-qualified view names as positional args (`my_schema.my_view`)
- **Multiple views**: `cubano codegen schema.view1 schema.view2` supported
- **`--backend` flag**: Required, explicit, not auto-detected; accepts `snowflake`, `databricks`, or dotted import path for custom backends
- **Credential loading**: Reuse existing Phase 8 credential infrastructure (`SnowflakeCredentials.load()`, `DatabricksCredentials.load()`)
- **Output destination**: Default stdout (code only, pipeable); warnings/errors to stderr; no `--output` flag this phase
- **Field mapping**: Read metric/dimension/fact classification directly from warehouse semantic view definition — not column type heuristics
- **Snowflake facts**: Read from explicit FACTS/DIMENSIONS/METRICS clauses in semantic view
- **Databricks facts**: No native Fact type — Databricks has only measures and dimensions. Strategy is Claude's discretion (see below)
- **TODO comments**: Only when a SQL data type has no clean Python type equivalent (GEOGRAPHY, VARIANT, SUPER, OBJECT, ARRAY, MAP). All other fields emitted cleanly
- **Class name**: PascalCase from view name (`sales_revenue_view` → `SalesRevenueView`)
- **Field docstrings**: Use warehouse column/field descriptions if they exist; omit docstring if no description
- **Imports**: Always include at top of output (`from cubano import SemanticView, Metric, Dimension, Fact`)
- **Multiple views**: All classes in one output block, single shared imports section at top
- **Pre-linting**: Output is pre-linted using project ruff + isort rules before printing to stdout
- **Backend architecture**: Warehouse introspection logic lives inside each backend class, not a standalone module
- **Each backend implements an introspection interface** (method/protocol TBD by planner)
- **Short-form names** (`snowflake`, `databricks`) resolve to built-in backend classes; dotted paths dynamically imported at runtime
- **Custom backends** must implement the same introspection interface to be usable with `cubano codegen`
- **Forward codegen** (Python → SQL) is explicitly out of scope and being removed

### Claude's Discretion

- Exact introspection interface/protocol design (method name, return type, ABC vs Protocol)
- Exact warehouse introspection API calls (INFORMATION_SCHEMA vs SHOW commands for Snowflake; Unity Catalog APIs for Databricks)
- Python type string mapping table for SQL types
- Error handling for views that don't exist or aren't accessible
- Whether to include a `__semantic_view__` name override when view name differs from class name
- Databricks Fact handling strategy (since Databricks only has measures/dimensions, not a native Fact type)

### Deferred Ideas (OUT OF SCOPE)

- `--output <path>` flag to write to a file directly (user can redirect stdout for now)
- Auto-detection of backend from credentials (keep explicit `--backend` flag for now)
- Syncing an existing model file with warehouse changes (drift detection)
</user_constraints>

---

## Summary

Phase 20 replaces the broken forward codegen (`Python model → CREATE SQL`) with a reverse codegen (`warehouse semantic view → Python model class`). The phase must introspect live warehouse metadata using native SQL commands (not column type heuristics), map those introspection results to Cubano `Metric`, `Dimension`, and `Fact` fields, and emit formatted, importable Python code to stdout.

The two warehouses have asymmetric introspection APIs and asymmetric semantic models. Snowflake has a rich set of SHOW/DESCRIBE commands and an explicit tripartite model (FACTS/DIMENSIONS/METRICS). Databricks exposes a `DESCRIBE TABLE EXTENDED AS JSON` command whose JSON output marks each column with `"is_measure": true/false` — there is no native "Fact" type in Databricks metric views, only measures and dimensions. This asymmetry must be handled by the Databricks backend's introspection implementation, defaulting non-measure columns to `Dimension` (the documented recommendation for Databricks from Phase 19 docs work).

Pre-linting generated code via `subprocess` using `ruff format -` (read from stdin, write to stdout) is the correct approach — ruff has no Python API for in-memory formatting. The `uv run ruff` invocation is needed to ensure the project's ruff version is used. The existing credential infrastructure, CLI patterns (Typer), and test patterns (CliRunner) from prior phases translate directly.

**Primary recommendation:** Use `SHOW COLUMNS IN SEMANTIC VIEW <schema.view_name>` as the primary Snowflake introspection command (returns `kind` = METRIC/DIMENSION/FACT and `data_type` as JSON per row in one query); use `DESCRIBE TABLE EXTENDED <view_name> AS JSON` for Databricks (columns array with `is_measure` boolean and type object). Implement an `introspect(view_name: str) -> IntrospectedView` protocol on each backend.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `snowflake-connector-python` | `>=4.3.0` (already in extras) | Execute `SHOW COLUMNS` against Snowflake | Already in project, cursor returns rows with column metadata |
| `databricks-sql-connector` | `>=4.2.5` (already in extras) | Execute `DESCRIBE TABLE EXTENDED AS JSON` | Already in project, `fetchone()` returns the JSON blob |
| `typer` | `>=0.12.0` (already in deps) | CLI argument parsing for new command signature | Already in project, CliRunner for tests |
| `rich` | `>=13.0.0` (already in deps) | Stderr diagnostics | Already in project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `subprocess` (stdlib) | stdlib | Run `ruff format -` to pre-lint generated code before stdout | Always — ruff has no Python API |
| `json` (stdlib) | stdlib | Parse Snowflake `data_type` JSON column and Databricks `DESCRIBE TABLE EXTENDED AS JSON` output | Always |
| `re` (stdlib) | stdlib | PascalCase conversion from `snake_case` view names | Always |
| `importlib` (stdlib) | stdlib | Dynamic import of custom backend from dotted path | When `--backend my.package.Backend` used |

### No New Dependencies

No new dependencies are required. All introspection is done via the existing warehouse connectors (already in `[project.optional-dependencies]`). The `ruff` binary is already in `[dependency-groups.dev]` and available in the project's virtual environment.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ruff format -` via subprocess | Write to temp file, format, read back | Subprocess stdin/stdout is cleaner — no tmp file lifecycle to manage |
| `ruff format -` via subprocess | `black` for formatting | Ruff is already the project formatter; no black dependency |
| `SHOW COLUMNS` (Snowflake) | `DESCRIBE SEMANTIC VIEW` + parse property rows | SHOW COLUMNS returns one row per field with kind/data_type directly; DESCRIBE requires multi-row property parsing |
| `DESCRIBE TABLE EXTENDED AS JSON` (Databricks) | Parse YAML from `view_text` field | `is_measure` boolean is authoritative; YAML parsing adds complexity |

---

## Architecture Patterns

### Recommended Project Structure

```
src/cubano/
├── cli/
│   └── codegen.py          # REPLACE: new CLI signature (view names, no input paths)
├── codegen/
│   ├── __init__.py
│   ├── models.py            # REUSE: ModelData/FieldData already good
│   ├── introspector.py      # NEW: IntrospectedView dataclass + IntrospectionBackend Protocol
│   ├── python_renderer.py   # NEW: renders ModelData → Python source (replaces SQL renderer for this direction)
│   ├── type_map.py          # NEW: SQL type string → Python type annotation string
│   └── ...                  # existing files (renderer.py, generator.py etc) can be removed or kept
├── engines/
│   ├── base.py              # ADD: introspect() abstract method to Engine ABC
│   ├── snowflake.py         # ADD: introspect() implementation
│   ├── databricks.py        # ADD: introspect() implementation
│   └── mock.py              # ADD: introspect() stub for testing
tests/
└── unit/
    └── codegen/
        ├── test_introspector.py    # NEW: unit tests for IntrospectedView, Protocol
        ├── test_python_renderer.py # NEW: unit tests for Python code generation
        ├── test_type_map.py        # NEW: unit tests for SQL→Python type mapping
        └── test_cli_codegen.py     # REPLACE: new CLI signature tests
```

### Pattern 1: Introspection Protocol on Engine

**What:** Each engine backend implements `introspect(view_name: str) -> IntrospectedView` as part of its interface. The CLI calls `backend.introspect(view_name)` without knowing which warehouse it's talking to.

**When to use:** Always — this is the primary design pattern.

**ABC vs Protocol recommendation:** Use `Protocol` (from `typing`) for the introspection interface, not ABC. The existing `Engine` ABC covers query execution. Introspection can be a separate `SupportsIntrospection` Protocol since custom backends need structural compatibility (not forced ABC inheritance). Alternatively, add `introspect()` as an abstract method directly to the `Engine` ABC — this is simpler and consistent with existing patterns. Recommendation: **add to the ABC**, since all built-in backends will implement it and custom backends already extend `Engine`.

```python
# src/cubano/codegen/introspector.py
from dataclasses import dataclass

@dataclass(frozen=True)
class IntrospectedField:
    name: str
    field_type: str           # "metric" | "dimension" | "fact"
    data_type: str            # SQL type string e.g. "VARCHAR(25)" or "NUMBER(18,0)"
    description: str = ""     # from column comment/description, empty if none

@dataclass(frozen=True)
class IntrospectedView:
    view_name: str            # schema-qualified name as provided e.g. "my_schema.my_view"
    class_name: str           # PascalCase derived from last part of view_name
    fields: list[IntrospectedField]
```

```python
# src/cubano/engines/base.py (addition)
@abstractmethod
def introspect(self, view_name: str) -> "IntrospectedView":
    """
    Introspect a semantic/metric view and return structured field metadata.

    Args:
        view_name: Schema-qualified view name (e.g. 'my_schema.my_view')

    Returns:
        IntrospectedView with field names, types, and semantic classification

    Raises:
        ValueError: If view_name format is invalid
        RuntimeError: If view does not exist or is not accessible
    """
    pass
```

### Pattern 2: Snowflake Introspection via SHOW COLUMNS

**What:** `SHOW COLUMNS IN SEMANTIC VIEW <schema_name>.<view_name>` returns one row per field. The `kind` column contains `METRIC`, `DIMENSION`, or `FACT`. The `data_type` column contains a JSON string like `{"type":"TEXT","length":16777216,"byteLength":16777216,"nullable":true,"fixed":false}` or `{"type":"FIXED","precision":18,"scale":0}`.

**When to use:** Snowflake backend introspection.

```python
# Snowflake introspect() implementation pattern
def introspect(self, view_name: str) -> IntrospectedView:
    import snowflake.connector
    sql = f"SHOW COLUMNS IN SEMANTIC VIEW {view_name}"
    with snowflake.connector.connect(**self._connection_params) as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]
        # Each row has: column_name, data_type (JSON), kind (METRIC/DIMENSION/FACT), comment
        fields = []
        for row in rows:
            d = dict(zip(columns, row, strict=True))
            field_type = d["kind"].lower()  # "metric" | "dimension" | "fact"
            data_type = _parse_snowflake_type(d["data_type"])  # parse JSON → SQL type string
            fields.append(IntrospectedField(
                name=d["column_name"].lower(),
                field_type=field_type,
                data_type=data_type,
                description=d.get("comment", "") or "",
            ))
    return IntrospectedView(view_name=view_name, class_name=_to_pascal_case(view_name), fields=fields)
```

**SHOW COLUMNS output columns** (verified from Snowflake docs):
- `column_name`: field name
- `data_type`: JSON string, e.g. `{"type":"FIXED","precision":18,"scale":0,"nullable":true}`
- `kind`: one of `COLUMN` (for regular views) or `DIMENSION` / `FACT` / `METRIC` (for semantic views)
- `comment`: description from warehouse

**Snowflake `data_type` JSON type values** (verified from Snowflake docs):
- `FIXED` → NUMBER/INTEGER (scale=0 → `int`, scale>0 → `float` or `Decimal`)
- `TEXT` → VARCHAR/STRING → `str`
- `REAL` → FLOAT → `float`
- `BOOLEAN` → BOOLEAN → `bool`
- `DATE` → DATE → `datetime.date`
- `TIMESTAMP_LTZ` / `TIMESTAMP_NTZ` / `TIMESTAMP_TZ` → `datetime.datetime`
- `TIME` → TIME → `datetime.time`
- `BINARY` → BINARY → `bytes`
- `ARRAY` / `OBJECT` / `VARIANT` / `GEOGRAPHY` / `GEOMETRY` → `# TODO: ...` annotation needed

### Pattern 3: Databricks Introspection via DESCRIBE TABLE EXTENDED AS JSON

**What:** `DESCRIBE TABLE EXTENDED <view_name> AS JSON` returns a single row whose first column is a JSON string. The JSON has a `columns` array where each element has `name`, `type` (type object), and `is_measure` (boolean, present only for measure columns). Columns without `is_measure` are dimensions.

**When to use:** Databricks backend introspection.

```python
# Databricks introspect() implementation pattern
import json

def introspect(self, view_name: str) -> IntrospectedView:
    import databricks.sql
    sql = f"DESCRIBE TABLE EXTENDED {view_name} AS JSON"
    with databricks.sql.connect(**self._connection_params) as conn, conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        raw_json = row[0]  # or row["json_value"] depending on driver
        schema = json.loads(raw_json)
        fields = []
        for col in schema["columns"]:
            is_measure = col.get("is_measure", False)
            field_type = "metric" if is_measure else "dimension"
            # Databricks has no native Fact type; all non-measures are Dimension
            data_type = _parse_databricks_type(col["type"])
            fields.append(IntrospectedField(
                name=col["name"],
                field_type=field_type,
                data_type=data_type,
                description=col.get("comment", "") or "",
            ))
    return IntrospectedView(view_name=view_name, class_name=_to_pascal_case(view_name), fields=fields)
```

**Databricks `type` object structure** (verified from docs):
- `{"name": "string", "collation": "UTF8_BINARY"}` → `str`
- `{"name": "bigint"}` → `int`
- `{"name": "double"}` → `float`
- `{"name": "decimal", "precision": 28, "scale": 2}` → `Decimal`
- `{"name": "date"}` → `datetime.date`
- `{"name": "timestamp"}` or `{"name": "timestamp_ltz"}` → `datetime.datetime`
- `{"name": "boolean"}` → `bool`
- `{"name": "binary"}` → `bytes`
- `{"name": "array", ...}` / `{"name": "map", ...}` / `{"name": "struct", ...}` → `# TODO: ...`

### Pattern 4: Python Code Renderer (Jinja2 Template)

**What:** Take `IntrospectedView` (or `ModelData` after mapping) and render to Python source. Use the existing `ModelData`/`FieldData` dataclasses as an intermediate representation — the introspection result maps to the same structure already used by the existing codegen.

**When to use:** Always — after introspection, use a Jinja2 template to emit Python source.

```python
# Example rendered output for two views
from cubano import SemanticView, Metric, Dimension, Fact


class SalesView(SemanticView, view="my_schema.sales_view"):
    """Sales metrics and dimensions."""

    revenue = Metric()
    """Total revenue."""
    country = Dimension()
    unit_price = Fact()
    # TODO: no clean Python type for GEOGRAPHY "territory"
    territory = Dimension()
```

### Pattern 5: Pre-linting via ruff stdin

**What:** After rendering all Python classes to a string, pipe through `ruff format -` via subprocess to apply project formatting rules before printing to stdout.

**When to use:** Always — the context decision mandates pre-linted output.

```python
import subprocess
import sys

def format_python_source(source: str) -> str:
    """Run ruff format on source string via stdin, return formatted result."""
    result = subprocess.run(
        ["uv", "run", "ruff", "format", "--stdin-filename", "models.py", "-"],
        input=source,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # ruff format failure — return source unchanged (don't fail codegen)
        return source
    return result.stdout
```

Note: `uv run ruff` ensures the project's pinned ruff version is used. The `--stdin-filename models.py` hint lets ruff apply pyproject.toml config correctly.

### Pattern 6: Dynamic Backend Import

**What:** When `--backend` is a dotted path (e.g. `my_package.backends.MyBackend`), dynamically import the class with `importlib.import_module` + `getattr`.

**When to use:** When `--backend` value contains a `.` and doesn't match `snowflake` or `databricks`.

```python
import importlib

def _resolve_backend(backend_spec: str) -> Engine:
    """Resolve --backend spec to an Engine instance."""
    if backend_spec == "snowflake":
        from cubano.engines.snowflake import SnowflakeEngine
        return SnowflakeEngine(**_load_snowflake_creds())
    elif backend_spec == "databricks":
        from cubano.engines.databricks import DatabricksEngine
        return DatabricksEngine(**_load_databricks_creds())
    else:
        # Dotted import path: "my_package.backends.MyBackend"
        module_path, _, class_name = backend_spec.rpartition(".")
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls()  # Custom backends must have a no-arg constructor or accept creds
        except (ImportError, AttributeError) as e:
            raise typer.BadParameter(f"Cannot import backend {backend_spec!r}: {e}") from e
```

### Pattern 7: `__semantic_view__` Name Override

**What:** When a view name is schema-qualified (e.g. `my_schema.sales_view`), the class needs to reference the full qualified name for the `view=` parameter. The PascalCase class name is derived only from the last segment (`sales_view` → `SalesView`), while `view="my_schema.sales_view"` carries the full path.

**Recommendation:** Always emit `view="<original_schema_qualified_name>"` as passed to the CLI. No need for a `__semantic_view__` override attribute — the `SemanticView` `view=` parameter already handles this case correctly.

```python
class SalesView(SemanticView, view="my_schema.sales_view"):
    ...
```

### Anti-Patterns to Avoid

- **Heuristic type inference from column data type alone:** The context locks metric/dimension/fact classification to come from the warehouse's semantic view definition, not from data type guessing.
- **Using GET_DDL() for introspection:** `GET_DDL()` returns the original SQL string and requires parsing. `SHOW COLUMNS` is structured and direct.
- **Parsing YAML from Databricks `view_text`:** `DESCRIBE TABLE EXTENDED AS JSON` exposes `is_measure` directly in the `columns` array — no YAML parsing needed.
- **Using `DESCRIBE SEMANTIC VIEW` for Snowflake instead of `SHOW COLUMNS`:** DESCRIBE returns one property per row in a tall format — requires grouping by `object_name` and extracting the DATA_TYPE property row. SHOW COLUMNS is one row per field.
- **Calling `ruff format` on a temp file:** stdin piping avoids temp file lifecycle.
- **Writing generated Python to stdout with Rich console:** Use `typer.echo()` (as per existing Phase 9 pattern) so CliRunner captures output in tests correctly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL → Python type mapping | Custom regex parser | Simple dict lookup on normalized type name prefix | Snowflake returns JSON type names, Databricks returns name-keyed objects — both normalize cleanly to a string key |
| Python code formatting | Custom formatter | `ruff format -` via subprocess | ruff already in project; handles line length, import sorting (isort), all configured in pyproject.toml |
| PascalCase conversion | Regex parser | `str.title().replace("_", "")` or `re.sub` | Simple stdlib operation on snake_case view name suffix |
| Dynamic backend import | Custom plugin system | `importlib.import_module` + `getattr` | One-liner stdlib pattern |
| Credential loading | New credential system | `SnowflakeCredentials.load()` / `DatabricksCredentials.load()` from `cubano.testing.credentials` | Phase 8 infrastructure already battle-tested with full fallback chain |

**Key insight:** The warehouse already knows which fields are metrics, dimensions, and facts — no inference needed. The challenge is fetching that information efficiently (one structured query per view, not parsing DDL text).

---

## Common Pitfalls

### Pitfall 1: Snowflake `SHOW COLUMNS` Returns Lowercase Kind or JSON-Encoded Data Type

**What goes wrong:** The `kind` column from `SHOW COLUMNS IN SEMANTIC VIEW` may return uppercase strings (`METRIC`, `DIMENSION`, `FACT`) but the `data_type` column is a JSON string, not a raw SQL type. Comparing `kind == "metric"` when the warehouse returns `"METRIC"` silently misclassifies fields.

**Why it happens:** Snowflake SHOW commands return uppercase identifiers. Data type is a structured JSON object, not a plain string like `VARCHAR(25)`.

**How to avoid:** Always `.lower()` the kind value before comparing. Parse the JSON `data_type` column to extract the `type` key (e.g. `json.loads(data_type_str)["type"]`), then do a case-insensitive lookup into the type map.

**Warning signs:** All fields classified as dimension (fell through to default), or `KeyError` on `data_type` parsing.

### Pitfall 2: Databricks `is_measure` is Absent for Dimensions (Not False)

**What goes wrong:** The `is_measure` field is documented as "included only for measure columns of metric views." This means dimension columns do NOT have `is_measure` at all — not `false`, just absent. Checking `col["is_measure"]` for a dimension column raises `KeyError`.

**Why it happens:** The JSON schema only includes the key for measures.

**How to avoid:** Always use `col.get("is_measure", False)`. Never rely on the key being present.

**Warning signs:** `KeyError: 'is_measure'` on the first non-measure column encountered.

### Pitfall 3: View Name Includes Three-Part Catalog Reference in Databricks

**What goes wrong:** Databricks Unity Catalog uses three-part names (`catalog.schema.view`). If the user passes a two-part name (`schema.view`), the connection's default catalog is used, which may not match expectations. The generated `view=` parameter in the Python class must use the canonical name.

**Why it happens:** Unity Catalog is three-part; older schemas may be two-part. Ambiguity exists.

**How to avoid:** Pass the view name to `DESCRIBE TABLE EXTENDED` as the user provided it. The connector resolves catalog resolution. In the generated Python, emit `view="<exactly what the user typed>"` so the model queries the correct view.

**Warning signs:** View not found errors when the generated model is used, or data from the wrong catalog.

### Pitfall 4: Forward Codegen Removal Breaks Existing Tests

**What goes wrong:** The existing `tests/unit/codegen/test_cli.py` tests the old CLI signature (`codegen <file_path> --backend snowflake --output file`). Replacing the CLI in-place deletes the `input` positional arg (file path) and the `--output` flag, breaking all existing CLI tests.

**Why it happens:** Phase 20 replaces the command in-place per the locked decision.

**How to avoid:** The planner should include a task to delete or replace the old CLI tests and old codegen modules (`generator.py`, `loader.py`, `validator.py`, `renderer.py`, templates) as part of the phase. Old tests must be replaced, not extended.

**Warning signs:** Test count drops significantly, or old tests pass on new CLI (they shouldn't, given changed signature).

### Pitfall 5: `ruff format -` Requires `uv run` in Project Context

**What goes wrong:** Calling `subprocess.run(["ruff", "format", ...])` may find a system ruff or no ruff at all, applying different formatting rules than the project's pinned version.

**Why it happens:** `ruff` may not be on PATH outside the uv virtual environment.

**How to avoid:** Use `["uv", "run", "ruff", "format", "--stdin-filename", "models.py", "-"]`. If `uv` is not available (unusual), fall back to returning unformatted source with a stderr warning.

**Warning signs:** Formatted output violates project line length (100 chars) or import order.

### Pitfall 6: Snowflake Schema-Qualified Name Quoting

**What goes wrong:** `SHOW COLUMNS IN SEMANTIC VIEW my_schema.my_view` works for lowercase names, but names with uppercase or special characters need quoting. Unquoted names are case-folded to uppercase by Snowflake.

**Why it happens:** Snowflake SQL is case-insensitive by default; unquoted identifiers fold to uppercase.

**How to avoid:** The user passes the view name as-is. For now, pass it directly without quoting (the Phase 8 integration tests already use lowercase names successfully). Flag this as a known limitation in the implementation. Properly handling quoted identifiers is a v0.3 concern.

**Warning signs:** View not found for mixed-case names that work in Snowflake's Snowsight UI.

### Pitfall 7: `SHOW COLUMNS` vs `SHOW COLUMNS IN SEMANTIC VIEW`

**What goes wrong:** `SHOW COLUMNS` without the `IN SEMANTIC VIEW` qualifier applies to regular views/tables and does NOT return `METRIC`/`DIMENSION`/`FACT` values in the `kind` column — it returns `COLUMN` for everything.

**Why it happens:** Semantic view introspection requires the explicit `IN SEMANTIC VIEW` qualifier.

**How to avoid:** Always use `SHOW COLUMNS IN SEMANTIC VIEW <schema.view_name>`. Test that the `kind` column returns semantic values (not `COLUMN`).

**Warning signs:** All fields classified as `COLUMN` (unrecognized kind), falling through to a default dimension classification.

---

## Code Examples

### SQL Type → Python Annotation Mapping (Snowflake)

Derived from official Snowflake Python handler type mapping docs (HIGH confidence):

```python
# src/cubano/codegen/type_map.py
_SNOWFLAKE_TYPE_MAP: dict[str, str] = {
    # JSON "type" key from SHOW COLUMNS data_type field
    "FIXED": "int",          # scale=0; use "float" if scale>0
    "TEXT": "str",
    "REAL": "float",
    "BOOLEAN": "bool",
    "DATE": "datetime.date",
    "TIMESTAMP_LTZ": "datetime.datetime",
    "TIMESTAMP_NTZ": "datetime.datetime",
    "TIMESTAMP_TZ": "datetime.datetime",
    "TIME": "datetime.time",
    "BINARY": "bytes",
    # Semi-structured / complex / geo — need TODO
    "ARRAY": None,           # None signals TODO comment
    "OBJECT": None,
    "VARIANT": None,
    "GEOGRAPHY": None,
    "GEOMETRY": None,
}

def snowflake_json_type_to_python(type_json: dict) -> str | None:
    """Return Python type annotation string, or None for types needing TODO."""
    type_name = type_json.get("type", "").upper()
    if type_name == "FIXED":
        scale = type_json.get("scale", 0)
        return "float" if scale > 0 else "int"
    return _SNOWFLAKE_TYPE_MAP.get(type_name)  # None = needs TODO
```

### SQL Type → Python Annotation Mapping (Databricks)

Derived from official Databricks docs and `databricks-sql-connector` source (HIGH confidence):

```python
_DATABRICKS_TYPE_MAP: dict[str, str] = {
    # "name" key from DESCRIBE TABLE EXTENDED AS JSON columns[n].type
    "string": "str",
    "bigint": "int",
    "int": "int",
    "smallint": "int",
    "tinyint": "int",
    "long": "int",
    "double": "float",
    "float": "float",
    "decimal": "float",      # or "Decimal" — float is pragmatic for Cubano users
    "boolean": "bool",
    "date": "datetime.date",
    "timestamp": "datetime.datetime",
    "timestamp_ntz": "datetime.datetime",
    "binary": "bytes",
    # Complex types — need TODO
    "array": None,
    "map": None,
    "struct": None,
    "variant": None,
}

def databricks_type_to_python(type_obj: dict) -> str | None:
    """Return Python type annotation string, or None for types needing TODO."""
    type_name = type_obj.get("name", "").lower()
    return _DATABRICKS_TYPE_MAP.get(type_name)  # None = needs TODO
```

### PascalCase Conversion

```python
import re

def view_name_to_class_name(view_name: str) -> str:
    """Convert schema-qualified view name to PascalCase class name.

    Examples:
        "sales_view" -> "SalesView"
        "my_schema.sales_revenue_view" -> "SalesRevenueView"
    """
    # Use only the last part (after last dot for schema qualification)
    local_name = view_name.rsplit(".", 1)[-1]
    return "".join(word.capitalize() for word in local_name.split("_"))
```

### Pre-Linting Generated Code

```python
import subprocess

def format_with_ruff(source: str) -> str:
    """Format Python source string through ruff, returning formatted result."""
    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "format", "--stdin-filename", "models.py", "-"],
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass  # uv not found; return unformatted
    return source
```

### New CLI Signature (Typer)

```python
def codegen(
    views: Annotated[
        list[str],
        typer.Argument(help="Schema-qualified view names (e.g. my_schema.my_view)")
    ],
    backend: Annotated[
        str,
        typer.Option("--backend", "-b", help="Backend: snowflake, databricks, or dotted.path.ClassName")
    ],
) -> None:
    """Introspect warehouse semantic views and generate Cubano model classes."""
    ...
```

Note: `Backend` StrEnum from old codegen is removed. `--backend` is now a plain `str` to accommodate custom dotted import paths.

### Generated Python Template (Jinja2)

```jinja2
{# src/cubano/codegen/templates/python_model.py.jinja2 #}
from cubano import SemanticView, Metric, Dimension, Fact
{% if needs_datetime %}
import datetime
{% endif %}
{% for model in models %}


class {{ model.class_name }}(SemanticView, view="{{ model.view_name }}"):
{% if model.docstring %}
    """{{ model.docstring }}"""
{% endif %}

{% for field in model.fields %}
{% if field.todo_comment %}
    # TODO: no clean Python type for {{ field.data_type }} field "{{ field.name }}"
{% endif %}
    {{ field.name }} = {{ field.field_class }}()
{% if field.docstring %}
    """{{ field.docstring }}"""
{% endif %}
{% endfor %}
{% endfor %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Forward codegen: Python model → CREATE SQL | Reverse codegen: warehouse view → Python model | Phase 20 | Old `generator.py`, `loader.py`, `validator.py`, `renderer.py`, SQL templates deleted |
| `codegen <file_path> --backend X --output Y` | `codegen <schema.view_name> [<schema.view_name2> ...] --backend X` | Phase 20 | Old input-file-based CLI replaced |
| Backend enum: `snowflake \| databricks` | Backend string: `snowflake \| databricks \| dotted.import.Path` | Phase 20 | Custom backends now supported |
| No introspection in Engine ABC | `introspect(view_name) -> IntrospectedView` on Engine ABC | Phase 20 | All backends implement warehouse inspection |

**Deprecated/outdated:**
- `src/cubano/codegen/generator.py`: Delete (forward pipeline orchestrator)
- `src/cubano/codegen/loader.py`: Delete (Python file loading for forward direction)
- `src/cubano/codegen/validator.py`: Delete (Python syntax validation for forward direction)
- `src/cubano/codegen/renderer.py`: Delete or repurpose (was Jinja2 SQL renderer; new renderer emits Python)
- `src/cubano/codegen/templates/snowflake.sql.jinja2`: Delete
- `src/cubano/codegen/templates/databricks.yaml.jinja2`: Delete
- `tests/unit/codegen/test_cli.py`: Replace entirely (old signature incompatible)
- `tests/unit/codegen/test_generator.py`, `test_loader.py`, `test_renderer.py`, `test_utils.py`: Delete or replace

---

## Open Questions

1. **Snowflake SHOW COLUMNS returns column descriptions?**
   - What we know: `SHOW COLUMNS IN SEMANTIC VIEW` returns a `comment` column per the docs.
   - What's unclear: Whether the `comment` column carries the description set in the YAML spec, or only SQL-level COMMENTs.
   - Recommendation: Test against real Snowflake view. If description is not in `SHOW COLUMNS`, use `DESCRIBE SEMANTIC VIEW` as a secondary call to fetch descriptions.

2. **Databricks `DESCRIBE TABLE EXTENDED AS JSON` column comment field**
   - What we know: JSON schema has a `comment` key per column.
   - What's unclear: Whether the `comment` field is populated from the metric view's semantic metadata `description` property.
   - Recommendation: Use `col.get("comment", "") or ""` — works whether populated or empty.

3. **Custom backend credential loading**
   - What we know: Short-form backends (`snowflake`, `databricks`) load credentials via `SnowflakeCredentials.load()` / `DatabricksCredentials.load()`.
   - What's unclear: How custom backends receive credentials — the `--backend my.pkg.MyBackend` resolves the class, but what constructor signature to call.
   - Recommendation: Custom backends are instantiated with no args (they manage their own credentials). This is a constraint for the interface design; document it clearly.

4. **Schema-qualified name in `view=` parameter for Snowflake**
   - What we know: `SnowflakeEngine` already handles `view_name="sales_view"` as the view identifier.
   - What's unclear: Whether Snowflake semantic views must be referenced by three-part name (db.schema.view) when using the generated model. Current cubano backend uses the `view_name` as-is in SQL.
   - Recommendation: Emit `view="<schema.view>"` exactly as the user typed. The existing SQL builder wraps it in double quotes: `FROM "my_schema"."my_view"` if there's a dot, which is correct Snowflake behavior.

5. **Whether to emit `Fact()` type annotation hint**
   - What we know: Databricks has no Fact concept; Snowflake FACTS clause maps to `Fact()`.
   - What's unclear: Context says "Field docstrings: use warehouse descriptions if they exist" but doesn't specify whether the generated Fact field should include a `# fact` comment hint for Databricks users who might want to compare with Snowflake.
   - Recommendation: No special comment for Databricks — Dimension is the correct mapping and documents itself.

---

## Sources

### Primary (HIGH confidence)

- Snowflake documentation: [Using SQL commands to create and manage semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/sql) — SHOW COLUMNS, DESCRIBE SEMANTIC VIEW, INFORMATION_SCHEMA views
- Snowflake documentation: [DESCRIBE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/desc-semantic-view) — object_kind values, property structure, data type format
- Snowflake documentation: [SHOW SEMANTIC DIMENSIONS](https://docs.snowflake.com/en/sql-reference/sql/show-semantic-dimensions) — output columns (name, data_type, synonyms, comment)
- Snowflake documentation: [Data Type Mappings Between SQL and Handler Languages](https://docs.snowflake.com/en/developer-guide/udf-stored-procedure-data-type-mapping) — SQL → Python type mapping table (NUMBER, VARCHAR, DATE, etc.)
- Databricks documentation: [DESCRIBE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table) — `DESCRIBE TABLE EXTENDED AS JSON` schema including `is_measure` boolean
- Databricks documentation: [Unity Catalog metric views](https://docs.databricks.com/aws/en/metric-views/) — two-type model (measures + dimensions, no Fact)
- Databricks documentation: [Use SQL to create and manage metric views](https://docs.databricks.com/aws/en/metric-views/create/sql) — `DESCRIBE TABLE EXTENDED AS JSON` usage
- Ruff GitHub discussion: [Using ruff in pipes](https://github.com/astral-sh/ruff/discussions/13690) — `ruff format --stdin-filename foo.py -` stdin pattern

### Secondary (MEDIUM confidence)

- Existing project code: `src/cubano/engines/snowflake.py`, `src/cubano/engines/databricks.py` — existing connection patterns and error handling directly reusable
- Existing project code: `src/cubano/codegen/models.py` — `ModelData`/`FieldData` dataclasses reusable as intermediate representation
- Existing project code: `tests/unit/codegen/test_cli.py` — CliRunner patterns for testing the new CLI

### Tertiary (LOW confidence)

- None identified. All critical claims verified against official documentation.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all tools already in project; no new dependencies
- Introspection APIs: HIGH — verified against official Snowflake and Databricks documentation with specific command syntax and output structures
- Architecture: HIGH — derived from existing patterns in the codebase, consistent with prior phase decisions
- Type mappings: HIGH (Snowflake), MEDIUM (Databricks) — Snowflake mapping verified against official UDF docs; Databricks type names derived from connector internals and docs
- Pitfalls: MEDIUM — based on API documentation and common patterns; some (e.g. SHOW COLUMNS kind casing) not testable without live warehouse access

**Research date:** 2026-02-24
**Valid until:** 2026-05-24 (stable warehouse APIs; Snowflake semantic views and Databricks metric views are GA features)
