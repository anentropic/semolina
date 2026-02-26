---
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
verified: 2026-02-24T06:56:29Z
status: passed
score: 32/32 must-haves verified
re_verification: false
human_verification:
  - test: "Run `cubano codegen my_schema.sales_view --backend snowflake` against a live Snowflake workspace"
    expected: "Printed Python class with correct field types matching warehouse view definition"
    why_human: "Requires live Snowflake warehouse credentials — cannot verify warehouse round-trip programmatically"
  - test: "Run `cubano codegen main.analytics.orders_view --backend databricks` against a live Databricks workspace"
    expected: "Printed Python class with is_measure=True fields as Metric(), others as Dimension()"
    why_human: "Requires live Databricks workspace credentials — cannot verify warehouse round-trip programmatically"
---

# Phase 20: Reverse Codegen Verification Report

**Phase Goal:** Implement reverse codegen — introspect warehouse semantic views (Snowflake/Databricks) and generate Cubano Python model classes via CLI.
**Verified:** 2026-02-24T06:56:29Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | IntrospectedField and IntrospectedView frozen dataclasses exist with correct fields | VERIFIED | `src/cubano/codegen/introspector.py`: `@dataclass(frozen=True)` on both; `field_type: Literal["metric","dimension","fact"]`, `data_type: str \| None`, `description: str = ""` |
| 2 | Snowflake type names map to Python annotation strings | VERIFIED | `src/cubano/codegen/type_map.py`: `_SNOWFLAKE_TYPE_MAP` dict with TEXT→str, REAL→float, BOOLEAN→bool, DATE→datetime.date, all timestamps→datetime.datetime, BINARY→bytes |
| 3 | Databricks type names map to Python annotation strings | VERIFIED | `src/cubano/codegen/type_map.py`: `_DATABRICKS_TYPE_MAP` dict with string→str, bigint/int/smallint/tinyint/long→int, double/float/decimal→float, boolean→bool, date→datetime.date, timestamp/timestamp_ntz→datetime.datetime, binary→bytes |
| 4 | Types without clean Python equivalents return None to trigger TODO comment | VERIFIED | `snowflake_json_type_to_python`: ARRAY/OBJECT/VARIANT/GEOGRAPHY/GEOMETRY and unknown types return `None`; `databricks_type_to_python`: array/map/struct/variant and unknown names return `None` |
| 5 | FIXED with scale>0 returns 'float'; scale=0 returns 'int' | VERIFIED | `snowflake_json_type_to_python()`: `return "int" if scale == 0 else "float"` |
| 6 | Engine ABC declares introspect() as abstract method with IntrospectedView return type | VERIFIED | `src/cubano/engines/base.py` line 117-144: `@abstractmethod def introspect(self, view_name: str) -> IntrospectedView:` with TYPE_CHECKING guard |
| 7 | MockEngine.introspect() raises NotImplementedError | VERIFIED | `src/cubano/engines/mock.py` line 183: `raise NotImplementedError("MockEngine does not support introspection")` |
| 8 | SnowflakeEngine.introspect() executes SHOW COLUMNS IN SEMANTIC VIEW, parses rows into IntrospectedView | VERIFIED | `src/cubano/engines/snowflake.py` lines 313-339: `cur.execute(f"SHOW COLUMNS IN SEMANTIC VIEW {view_name}")`, builds IntrospectedField list, returns IntrospectedView |
| 9 | SnowflakeEngine.introspect() lowercases kind before comparison | VERIFIED | `snowflake.py` line 321: `field_type = d["kind"].lower()` |
| 10 | SnowflakeEngine.introspect() parses data_type JSON column and maps via type_map | VERIFIED | `snowflake.py` lines 322-324: `json.loads(d["data_type"])` then `snowflake_json_type_to_python(type_json)` |
| 11 | DatabricksEngine.introspect() executes DESCRIBE TABLE EXTENDED AS JSON, parses JSON output | VERIFIED | `src/cubano/engines/databricks.py` lines 321-323: `cur.execute(f"DESCRIBE TABLE EXTENDED {view_name} AS JSON")`, `json.loads(row[0])` |
| 12 | DatabricksEngine.introspect() uses col.get('is_measure', False) — never col['is_measure'] | VERIFIED | `databricks.py` line 327: `is_measure: bool = col.get("is_measure", False)` |
| 13 | DatabricksEngine.introspect() maps is_measure=True to 'metric', absent/False to 'dimension' | VERIFIED | `databricks.py` line 328: `field_type = "metric" if is_measure else "dimension"` |
| 14 | Both engines propagate description/comment into IntrospectedField.description | VERIFIED | Snowflake line 325: `description = str(d.get("comment") or "")`; Databricks line 337: `description = str(col.get("comment") or "")` |
| 15 | Both engines raise RuntimeError (not raw connector exceptions) when view not found | VERIFIED | Snowflake lines 341-343: catches ProgrammingError/DatabaseError → RuntimeError; Databricks lines 353-355: catches DatabaseError/OperationalError/Error → RuntimeError |
| 16 | render_views() produces valid importable Python source | VERIFIED | `src/cubano/codegen/python_renderer.py`: Jinja2 Environment with trim_blocks/lstrip_blocks, 25 tests pass including assertions on importable output |
| 17 | Single shared imports section at top (from cubano import SemanticView, Metric, Dimension, Fact) | VERIFIED | `templates/python_model.py.jinja2` line 1: `from cubano import SemanticView, Metric, Dimension, Fact` — outside the loop, generated once |
| 18 | datetime imported when any field uses datetime.date or datetime.datetime | VERIFIED | `python_renderer.py` line 147: `needs_datetime = any(f.data_type in _DATETIME_TYPES ...)`, template line 2-4: `{% if needs_datetime %}import datetime{% endif %}` |
| 19 | Fields with description emit a docstring; fields without description emit no docstring | VERIFIED | Template lines 14-16: `{% if field.docstring %}    """{{ field.docstring }}"""{% endif %}` |
| 20 | Fields whose data_type starts with 'TODO:' emit a # TODO: comment above the field assignment | VERIFIED | Template lines 10-12: `{% if field.todo_comment %}    # {{ field.todo_comment }}{% endif %}`; `python_renderer.py` line 88: `if f.data_type is not None and f.data_type.startswith("TODO:")` |
| 21 | Metric/Dimension/Fact fields map to correct Cubano class names | VERIFIED | `_field_class_for()` lines 68-72: metric→"Metric", fact→"Fact", else→"Dimension" |
| 22 | format_with_ruff() falls back to unformatted source if uv/ruff unavailable | VERIFIED | Lines 184-185: `except FileNotFoundError: return source`; lines 187-188: `if result.returncode != 0: return source` |
| 23 | cubano codegen <schema.view_name> --backend snowflake prints Python class to stdout | VERIFIED | `src/cubano/cli/codegen.py`: `typer.echo(source)` at end; 19 CLI tests pass including `test_output_to_stdout` |
| 24 | --backend snowflake/databricks resolves correct Engine via Credentials.load() | VERIFIED | `_resolve_backend()` lines 40-51: both shortcuts resolve credentials then instantiate engine |
| 25 | --backend dotted.path.ClassName dynamically imports via importlib | VERIFIED | `_resolve_backend()` lines 53-66: `importlib.import_module(module_path)`, `getattr(module, class_name)`, `cls()` |
| 26 | Invalid --backend exits 1 with readable error on stderr | VERIFIED | Lines 57-66: raises `typer.BadParameter`; caught in codegen() lines 84-86: prints to `_stderr`, raises `typer.Exit(code=1)` |
| 27 | View not found raises RuntimeError; CLI catches it, prints to stderr, exits 1 | VERIFIED | codegen() lines 93-95: `except RuntimeError as e: _stderr.print(...); raise typer.Exit(code=1)` |
| 28 | Old forward codegen files (generator.py, loader.py, renderer.py, validator.py) deleted | VERIFIED | `src/cubano/codegen/` contains only: `__init__.py`, `introspector.py`, `models.py`, `python_renderer.py`, `templates/`, `type_map.py` |
| 29 | Old SQL/YAML templates deleted | VERIFIED | `src/cubano/codegen/templates/` contains only `python_model.py.jinja2` |
| 30 | codegen.md describes the reverse codegen workflow with correct CLI syntax | VERIFIED | `docs/src/how-to/codegen.md`: shows `cubano codegen my_schema.sales_view --backend snowflake`, tabbed Snowflake/Databricks output, field type mapping table, TODO comments section, custom backend section |
| 31 | docs build passes with --strict (no broken references to deleted modules) | VERIFIED | `uv run mkdocs build --strict` → "Documentation built in 1.43 seconds" with 0 errors/warnings |
| 32 | SUMMARY.md updated: generator/loader/renderer/validator removed; introspector/type_map/python_renderer added | VERIFIED | `docs/src/reference/SUMMARY.md` codegen section has only: introspector, models, python_renderer, type_map — no references to deleted modules |

**Score:** 32/32 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/cubano/codegen/introspector.py` | IntrospectedField, IntrospectedView frozen dataclasses | VERIFIED | Both `@dataclass(frozen=True)`, correct fields, docstrings |
| `src/cubano/codegen/type_map.py` | SQL type → Python annotation mapping for both backends | VERIFIED | Two private dicts + two public functions; 75 type-map tests pass |
| `src/cubano/codegen/python_renderer.py` | render_views, format_with_ruff, render_and_format | VERIFIED | All three functions implemented; 25 tests pass |
| `src/cubano/codegen/templates/python_model.py.jinja2` | Jinja2 template for SemanticView class output | VERIFIED | 19 lines, handles needs_datetime, TODO comments, docstrings, field classes |
| `src/cubano/engines/base.py` | Engine ABC with abstract introspect() method | VERIFIED | `@abstractmethod def introspect(...)` with TYPE_CHECKING import |
| `src/cubano/engines/snowflake.py` | SnowflakeEngine.introspect() implementation | VERIFIED | Full implementation: SHOW COLUMNS, JSON parse, field type lowercasing, TODO fallback, RuntimeError wrapping |
| `src/cubano/engines/databricks.py` | DatabricksEngine.introspect() implementation | VERIFIED | Full implementation: DESCRIBE TABLE EXTENDED AS JSON, is_measure.get(), TODO fallback, RuntimeError wrapping |
| `src/cubano/engines/mock.py` | MockEngine.introspect() raises NotImplementedError | VERIFIED | `raise NotImplementedError("MockEngine does not support introspection")` |
| `src/cubano/cli/codegen.py` | New reverse codegen CLI command | VERIFIED | `codegen(views, backend)` with `_resolve_backend()`, error handling, `typer.echo(source)` |
| `tests/unit/codegen/test_introspector.py` | Tests for IntrospectedField/IntrospectedView | VERIFIED | 15 tests pass |
| `tests/unit/codegen/test_type_map.py` | Tests for all type mappings | VERIFIED | 75 tests pass |
| `tests/unit/codegen/test_python_renderer.py` | TDD tests for renderer | VERIFIED | 25 tests pass |
| `tests/unit/test_snowflake_engine.py` | SnowflakeEngine.introspect() unit tests | VERIFIED | 11 introspect tests (via mocked connector) pass |
| `tests/unit/test_databricks_engine.py` | DatabricksEngine.introspect() unit tests | VERIFIED | 10 introspect tests (via mocked connector) pass |
| `tests/unit/codegen/test_cli.py` | CLI tests for reverse codegen | VERIFIED | 19 tests pass using MockEngine injection via `unittest.mock.patch` |
| `docs/src/how-to/codegen.md` | Reverse codegen how-to guide | VERIFIED | Rewritten: new CLI syntax, tabbed output examples, field type table, TODO comments section, custom backend, See also links |
| `docs/src/reference/cubano/codegen/introspector.md` | Auto-generated reference | VERIFIED | `# cubano.codegen.introspector\n::: cubano.codegen.introspector` |
| `docs/src/reference/cubano/codegen/type_map.md` | Auto-generated reference | VERIFIED | Exists; mkdocs build passes --strict |
| `docs/src/reference/cubano/codegen/python_renderer.md` | Auto-generated reference | VERIFIED | Exists; mkdocs build passes --strict |

**Deleted artifacts confirmed absent:**
- `src/cubano/codegen/generator.py` — ABSENT (correct)
- `src/cubano/codegen/loader.py` — ABSENT (correct)
- `src/cubano/codegen/renderer.py` — ABSENT (correct)
- `src/cubano/codegen/validator.py` — ABSENT (correct)
- `src/cubano/codegen/templates/snowflake.sql.jinja2` — ABSENT (correct)
- `src/cubano/codegen/templates/databricks.yaml.jinja2` — ABSENT (correct)
- `docs/src/reference/cubano/codegen/generator.md` — ABSENT (correct)
- `docs/src/reference/cubano/codegen/loader.md` — ABSENT (correct)
- `docs/src/reference/cubano/codegen/renderer.md` — ABSENT (correct)
- `docs/src/reference/cubano/codegen/validator.md` — ABSENT (correct)
- `tests/unit/codegen/test_generator.py` — ABSENT (correct)
- `tests/unit/codegen/test_loader.py` — ABSENT (correct)
- `tests/unit/codegen/test_renderer.py` — ABSENT (correct)
- `tests/unit/codegen/fixtures/simple_models.py` — ABSENT (correct)
- `tests/unit/codegen/fixtures/multi_models.py` — ABSENT (correct)
- `tests/unit/codegen/fixtures/no_models.py` — ABSENT (correct)

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/cubano/engines/base.py` | `src/cubano/codegen/introspector.py` | TYPE_CHECKING import of IntrospectedView | WIRED | Lines 14-15: `if TYPE_CHECKING: from cubano.codegen.introspector import IntrospectedView` |
| `src/cubano/engines/mock.py` | `src/cubano/engines/base.py` | Engine ABC abstract method | WIRED | `def introspect(self, view_name: str) -> IntrospectedView:` raises NotImplementedError |
| `src/cubano/engines/snowflake.py` | `src/cubano/codegen/introspector.py` | introspect() return type | WIRED | Lazy import inside method: `from cubano.codegen.introspector import IntrospectedField, IntrospectedView`; returns `IntrospectedView(...)` |
| `src/cubano/engines/snowflake.py` | `src/cubano/codegen/type_map.py` | snowflake_json_type_to_python() call | WIRED | `from cubano.codegen.type_map import snowflake_json_type_to_python`; called at line 323 |
| `src/cubano/engines/databricks.py` | `src/cubano/codegen/type_map.py` | databricks_type_to_python() call | WIRED | `from cubano.codegen.type_map import databricks_type_to_python`; called at line 335 |
| `src/cubano/codegen/python_renderer.py` | `src/cubano/codegen/introspector.py` | IntrospectedView type parameters | WIRED | TYPE_CHECKING import; `render_views(views: list[IntrospectedView])` |
| `src/cubano/codegen/python_renderer.py` | `src/cubano/codegen/templates/python_model.py.jinja2` | jinja2.Environment template loading | WIRED | `env.get_template("python_model.py.jinja2")` at line 158 |
| `src/cubano/cli/codegen.py` | `src/cubano/codegen/python_renderer.py` | render_and_format() call | WIRED | Lazy import line 97: `from cubano.codegen.python_renderer import render_and_format`; called at line 99 |
| `src/cubano/cli/codegen.py` | `src/cubano/engines/snowflake.py` | _resolve_backend() returning SnowflakeEngine | WIRED | Lines 41-45: lazy import + instantiation when `backend_spec == "snowflake"` |
| `src/cubano/cli/codegen.py` | `src/cubano/engines/databricks.py` | _resolve_backend() returning DatabricksEngine | WIRED | Lines 46-51: lazy import + instantiation when `backend_spec == "databricks"` |
| `docs/src/how-to/codegen.md` | `docs/src/how-to/models.md` | See also link | WIRED | `- [Defining models](models.md) -- model class structure and field types` |
| `docs/src/reference/SUMMARY.md` | `docs/src/reference/cubano/codegen/introspector.md` | nav entry | WIRED | `* [introspector](cubano/codegen/introspector.md)` present in SUMMARY.md |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CODEGEN-REVERSE | 20-01 | Generate models from warehouse introspection (live schema scanning) | SATISFIED | IntrospectedField/IntrospectedView IR, type_map, Engine.introspect() abstract method all implemented and tested |
| CODEGEN-WAREHOUSE | 20-03, 20-04, 20-05 | Generate models from warehouse introspection (live schema scanning) | SATISFIED | SnowflakeEngine.introspect() + DatabricksEngine.introspect() + CLI (`cubano codegen --backend`) + docs all implemented |

**Requirement ID / REQUIREMENTS.md Definition Discrepancy (informational):**

REQUIREMENTS.md defines `CODEGEN-REVERSE` as "Reverse codegen (Cubano models → dbt semantic YAML)" — i.e., the opposite direction (forward to dbt). However, plans 01-05 use `CODEGEN-REVERSE` to mean "warehouse → Python model class" (introspection direction). The implemented feature matches `CODEGEN-WAREHOUSE`'s definition ("Generate models from warehouse introspection"). This is a naming discrepancy in REQUIREMENTS.md — the implemented functionality is correct and complete, the requirement ID labels are inconsistent. `CODEGEN-WAREHOUSE` is not in the tracking table despite being claimed as completed in plans 03, 04, and 05. This does not block the phase — the feature is fully implemented.

### Anti-Patterns Found

No blockers or warnings. The "TODO:" strings found in source files are intentional — they are formatted output strings (`f"TODO: {d['data_type']}"`) that appear in generated Python code for SQL types with no Python equivalent. These are correct behavior, not anti-patterns.

### Human Verification Required

#### 1. Live Snowflake introspection round-trip

**Test:** With a valid `CUBANO_SNOWFLAKE_*` environment configuration, run:
```bash
cubano codegen analytics.sales_view --backend snowflake
```
**Expected:** Python class printed to stdout with fields matching the warehouse view's METRIC/DIMENSION/FACT columns; exit code 0.
**Why human:** Requires live Snowflake warehouse credentials — cannot verify warehouse round-trip programmatically.

#### 2. Live Databricks introspection round-trip

**Test:** With a valid `CUBANO_DATABRICKS_*` environment configuration, run:
```bash
cubano codegen main.analytics.orders_view --backend databricks
```
**Expected:** Python class printed to stdout; `is_measure=True` columns map to `Metric()`, others to `Dimension()`; exit code 0.
**Why human:** Requires live Databricks workspace credentials — cannot verify warehouse round-trip programmatically.

## Quality Gate Results

| Gate | Result |
|------|--------|
| `uv run basedpyright` (all phase 20 files) | 0 errors, 0 warnings, 0 notes |
| `uv run ruff check src/cubano/codegen/ src/cubano/engines/ src/cubano/cli/codegen.py` | All checks passed |
| `uv run pytest tests/` | 681 passed, 0 failed |
| `uv run mkdocs build --strict` | Documentation built in 1.43 seconds, 0 errors |

## Gaps Summary

No gaps. All 32 must-haves are verified. All quality gates pass. The phase goal — reverse codegen CLI that introspects warehouse semantic views and generates Cubano Python model classes — is fully achieved.

---

_Verified: 2026-02-24T06:56:29Z_
_Verifier: Claude (gsd-verifier)_
