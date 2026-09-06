# Phase 42: Codegen Field-Type Inference - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 6 (1 source modify, 3 test create/extend, 1 snapshot create, 1 doc amend) + 3 close-out doc edits
**Analogs found:** 6 / 6 (all have strong in-repo analogs; nothing greenfield)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/semolina/codegen/python_renderer.py` (modify `_field_class_for`) | utility (pure transform) | transform | itself (current body, lines 65-79) | exact (self) |
| `tests/unit/codegen/test_python_renderer.py` (add raise-path test) | test | transform | `TestRenderViews` in same file (lines 14-40) | exact |
| Snowflake codegen E2E snapshot test (in `tests/unit/codegen/`) | test | request-response → transform | `tests/unit/codegen/test_codegen_e2e.py` + `test_snowflake_engine.py:565-642` | role + data-flow match (composed from two analogs) |
| Databricks codegen E2E snapshot test (in `tests/unit/codegen/`) | test | request-response → transform | `tests/unit/codegen/test_codegen_e2e.py` + `test_databricks_engine.py:828-892` | role + data-flow match (composed from two analogs) |
| `tests/unit/codegen/__snapshots__/*.ambr` (new SF/DB snapshots) | test fixture | snapshot | `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` | exact |
| `docs/src/how-to/codegen.rst` (amend field-type section) | doc (how-to) | n/a | itself (lines 221-251) | exact (self) |
| Close-out: `.planning/ROADMAP.md`, `REQUIREMENTS.md`, `PROJECT.md` | doc/tracking | n/a | (planning files; see RESEARCH Close-Out Targets) | n/a |

---

## Pattern Assignments

### `src/semolina/codegen/python_renderer.py` — `_field_class_for` (utility, transform)

**Analog:** itself — current body at **lines 65-79** (read this turn).

**Current body to replace (lines 65-79):**
```python
def _field_class_for(field_type: str) -> str:
    """
    Return the Semolina class name for a given field type string.

    Args:
        field_type: One of 'metric', 'fact', or 'dimension'.

    Returns:
        Semolina class name: 'Metric', 'Fact', or 'Dimension'.
    """
    if field_type == "metric":
        return "Metric"
    if field_type == "fact":
        return "Fact"
    return "Dimension"   # <-- catch-all default = the silent-coercion bug
```

**Target shape (from RESEARCH lines 258-264, CONTEXT specifics lines 171-178):**
```python
_ROLE_TO_CLASS = {"metric": "Metric", "dimension": "Dimension", "fact": "Fact"}


def _field_class_for(field_type: str) -> str:
    """
    Return the Semolina class name for a given field type string.

    Args:
        field_type: One of 'metric', 'fact', or 'dimension'.

    Returns:
        Semolina class name: 'Metric', 'Fact', or 'Dimension'.

    Raises:
        ValueError: If ``field_type`` is not a recognized role string.
    """
    try:
        return _ROLE_TO_CLASS[field_type]
    except KeyError:
        raise ValueError(f"Unrecognized field role: {field_type!r}") from None
```

**Notes for executor:**
- Exception choice = `ValueError` (RESEARCH lines 238-251: no fitting Semolina error class; `engines/base.py` only has `SemolinaViewNotFoundError`/`SemolinaConnectionError`, both warehouse-domain; ABC docstrings already document `ValueError` for invalid input). Planner may choose a named class but `ValueError` is lowest-friction.
- Caller is `_build_model_context` at **line 109** (`field_class=_field_class_for(f.field_type)`) — do NOT wrap/catch there; the raise must propagate (RESEARCH anti-pattern lines 208-209).
- D213 / Google docstring style; keep summary on second line; line length 100; no `# type: ignore`.
- Place `_ROLE_TO_CLASS` at module level near the other module constants (`_DATETIME_TYPES` is at line 21).

---

### `tests/unit/codegen/test_python_renderer.py` — raise-path test (test, transform)

**Analog:** same file's existing `TestRenderViews` class (lines 14-40, read this turn). Imports already present at top: `from semolina.codegen.introspector import IntrospectedField, IntrospectedView` (line 11); `MagicMock, patch` imported (line 9).

**Existing test style to mirror (lines 17-30):**
```python
def test_single_view_metric_field(self) -> None:
    """Single view with one metric field renders Metric[int]() assignment."""
    from semolina.codegen.python_renderer import render_views
    ...
```
Note convention: the `render_*` function is imported *inside* the test body, not at module top.

**New test to add (RESEARCH lines 338-347; bug-fix discipline → write RED first, then make the impl change):**
```python
import pytest
from semolina.codegen.python_renderer import _field_class_for


def test_field_class_for_unrecognized_role_raises() -> None:
    """Unrecognized role string raises rather than defaulting to Dimension."""
    with pytest.raises(ValueError, match="Unrecognized field role"):
        _field_class_for("widget")
```
Place adjacent to `TestRenderViews` (module-level function is fine, matching test-file style — or as a method on a small new class; planner's call). `pytest` is not yet imported in this file — add the import.

**CLAUDE.md bug-fix sequence:** commit this failing test first (against the still-lenient `_field_class_for`, it FAILS because `"widget"` → `"Dimension"`), then commit the strict-`_field_class_for` change that makes it pass.

---

### Snowflake codegen E2E snapshot test (test; request-response → transform)

**Composed from two analogs.**

**Analog A — DuckDB E2E test structure** (`tests/unit/codegen/test_codegen_e2e.py`, full file read this turn). DuckDB drives the CLI because it takes `--database` (no creds). **SF must NOT use the CLI** — `_resolve_backend("snowflake", ...)` calls `SnowflakeCredentials.load()` (RESEARCH lines 192-199, Pitfall 1 lines 301-307). Instead drive `engine.introspect()` → `render_and_format([view])` directly.

**Syrupy assertion style (from DuckDB test, lines 14, 21, 42):**
```python
from syrupy.assertion import SnapshotAssertion   # under TYPE_CHECKING in analog

def test_...(snapshot: SnapshotAssertion) -> None:
    ...
    assert result.output == snapshot   # DuckDB form
# SF/DB form:  assert render_and_format([view]) == snapshot
```

**Analog B — Snowflake mock seam** (`tests/unit/test_snowflake_engine.py`, read this turn).

Autouse `sys.modules` fixture (lines 47-76) — copy into the new test module (do NOT import across test modules; RESEARCH lines 286-290):
```python
@pytest.fixture(autouse=True)
def _mock_snowflake_in_sys_modules():
    mock_sf = MagicMock(name="snowflake")
    mock_connector = MagicMock(name="snowflake.connector")
    mock_errors = MagicMock(name="snowflake.connector.errors")
    mock_errors.ProgrammingError = _SnowflakeProgrammingError   # exception stubs
    mock_errors.DatabaseError = _SnowflakeDatabaseError
    mock_sf.connector = mock_connector
    mock_connector.errors = mock_errors
    with patch.dict(sys.modules, {
        "snowflake": mock_sf,
        "snowflake.connector": mock_connector,
        "snowflake.connector.errors": mock_errors,
    }):
        yield
```

Cursor mock + introspect drive (lines 595-621) — `description` is a list of 1-tuples; `fetchall` returns role rows with JSON `data_type`:
```python
mock_conn = MagicMock()
mock_cursor = MagicMock()
mock_cursor.description = [
    ("column_name",), ("kind",), ("data_type",), ("comment",),
]
mock_cursor.fetchall.return_value = [
    ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),   # -> Metric[int]
    ("country", "DIMENSION", json.dumps({"type": "TEXT"}), ""),             # -> Dimension[str]
    ("date_key", "FACT", json.dumps({"type": "DATE"}), ""),                 # -> Fact[datetime.date]
]
with patch("snowflake.connector.connect") as mock_connect:
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    from semolina.engines.snowflake import SnowflakeEngine
    from semolina.codegen.python_renderer import render_and_format
    engine = SnowflakeEngine(account="test", user="user", password="pass")
    view = engine.introspect("sales_view")
assert render_and_format([view]) == snapshot
```
Engine constructor signature confirmed: `SnowflakeEngine(account=..., user=..., password=...)`. SF `kind` arrives UPPERCASE and the engine `.lower()`s it before `IntrospectedField` (RESEARCH line 230; verified `field_type == "metric"` etc. at test lines 631/636/641) — so fixtures use `METRIC`/`DIMENSION`/`FACT` uppercase.

Expected snapshot will demonstrate all three roles: `Metric[int]()`, `Dimension[str]()`, `Fact[datetime.date]()` (date_key → `datetime.date`; renderer adds `import datetime`, see `render_views` lines 165/129-130). These rows are reusable verbatim from the engine test (RESEARCH Reuse Analysis lines 274-279).

---

### Databricks codegen E2E snapshot test (test; request-response → transform)

**Composed from two analogs.** Same DuckDB-structure analog (A) as Snowflake; same "no CLI" rule (`_resolve_backend("databricks")` → `DatabricksCredentials.load()`).

**Analog B — Databricks mock seam** (`tests/unit/test_databricks_engine.py`, read this turn).

Autouse `sys.modules` fixture (lines 28-48) + `_create_mock_databricks()` helper (lines 51-73). Note the Databricks `fetchone()` returns a **single JSON string in a 1-tuple** (`(schema_json,)`), unlike Snowflake's `fetchall()` row list:
```python
mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
mock_conn = MagicMock()
mock_cursor = MagicMock()
schema_json = json.dumps({"columns": [
    {"name": "revenue", "is_measure": True,  "type": {"name": "double"}, "comment": ""},  # -> Metric[float]
    {"name": "country", "is_measure": False, "type": {"name": "string"}, "comment": ""},  # -> Dimension[str]
]})
mock_cursor.fetchone.return_value = (schema_json,)
with patch.dict(sys.modules, {
    "databricks": mock_databricks,
    "databricks.sql": mock_sql,
    "databricks.sql.exc": mock_exc,
}):
    from semolina.engines.databricks import DatabricksEngine
    from semolina.codegen.python_renderer import render_and_format
    mock_sql.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    engine = DatabricksEngine(
        server_hostname="test",
        http_path="/sql/1.0/warehouses/abc",
        access_token="token",
    )
    view = engine.introspect("sales_view")
assert render_and_format([view]) == snapshot
```
Constructor signature confirmed: `DatabricksEngine(server_hostname=..., http_path=..., access_token=...)`. `is_measure: True` → `field_type=="metric"`/`float`; `is_measure: False` → `dimension`/`str` (verified test lines 886-892). **No Fact row — intentional** (Databricks has no native Fact; CONTEXT lines 85-88). The new test's docstring MUST state the no-Fact absence is intentional, not a gap (RESEARCH lines 289-290). Rows reusable verbatim (RESEARCH Reuse Analysis lines 280-284).

---

### `.ambr` snapshot fixtures (test fixture, snapshot)

**Analog:** `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` (read this turn). Syrupy `AmbrSnapshotExtension` default; one named block per test:
```
# serializer version: 1
# name: test_codegen_file_backed_duckdb
  '''
  from semolina import Dimension, Fact, Metric, SemanticView


  class SalesView(SemanticView, view="sales_view"):
      unit_price = Fact[int]()
      country = Dimension[str]()
      region = Dimension[str]()
      revenue = Metric[int]()
      cost = Metric[int]()


  '''
# ---
```
**Generation, not hand-authoring:** run `uv run pytest tests/unit/codegen/ --snapshot-update` to create the new `.ambr` blocks, then commit (RESEARCH lines 214, 446). Decision point (RESEARCH Open Q2, lines 499-501): planner may co-locate SF/DB cases in `test_codegen_e2e.py` (sharing the existing `.ambr`) or use sibling test files (each gets its own `.ambr`). Co-location keeps all codegen E2E snapshots together — recommended.

**Formatting note (important for snapshot determinism):** `render_and_format` runs `ruff format` + isort (`format_with_ruff`, lines 191-222). Raw template import line is `from semolina import SemanticView, Metric, Dimension, Fact` (renderer test line 30) but the *formatted* DuckDB snapshot shows isort-sorted `from semolina import Dimension, Fact, Metric, SemanticView` (snapshot line 4). So a `render_and_format` snapshot will have sorted imports. `render_and_format` falls back to raw source if ruff is absent (lines 215-219) → Pitfall 2 (RESEARCH lines 309-318): `just test` runs under `uv` so ruff is present and snapshots are stable. If the planner wants subprocess-free determinism, snapshot `render_views([view])` instead (raw Jinja, no ruff) — both prove the field classes; matching the DuckDB `render_and_format` precedent is preferred.

---

### `docs/src/how-to/codegen.rst` — amend field-type section (doc, how-to)

**Analog:** itself, lines 211-251 (read this turn). Existing content already covers most of this:
- Lines 211-219: worked DuckDB example showing `Fact[int]()`/`Dimension[str]()`/`Metric[int]()`.
- Lines 221-225: `.. note::` already states Databricks has no native Fact type; non-measure → `Dimension()`; DuckDB supports all three.
- Lines 230-240: list-table mapping Metric/Measure → `Metric[T]()`, Dimension → `Dimension[T]()`, Fact (Snowflake and DuckDB) → `Fact[T]()`.

**Amendment scope (RESEARCH lines 397-409):**
1. Make per-role emission explicit for **all three** backends (confirm Snowflake + Databricks are stated, not just DuckDB).
2. Reinforce Databricks no-Fact constraint (present at 221-225 — verify wording, lightly expand).
3. **NEW content:** document strict-raise — an unrecognized warehouse role string makes codegen fail loudly rather than silently mislabel a column as Dimension. Not present today.

**Mandatory:** load `@.claude/skills/semolina-docs-author/SKILL.md` (Diataxis how-to + humanizer) — planner MUST add this to the doc task's `<execution_context>` (CLAUDE.md + RESEARCH lines 406-409). This is a targeted (<50%) amendment, so humanizer pass on changed prose only. Doc gate: `just docs-build` (`sphinx-build -W`, strict).

---

## Shared Patterns

### `sys.modules` connector mock (offline introspection seam)
**Source:** `tests/unit/test_snowflake_engine.py:47-76` and `tests/unit/test_databricks_engine.py:28-73`
**Apply to:** both new codegen E2E tests
**Key mechanics:** an autouse fixture installs `MagicMock` parent packages into `sys.modules` so the engine's lazy `import snowflake.connector` / `import databricks.sql` resolves; real exception-class stubs are attached so the engine's `except` clauses can catch; then `patch("...connect")` (SF) or `patch.dict(sys.modules, ...)` + `mock_sql.connect` (DB) wires `connect → __enter__ → cursor → __enter__` to a mock cursor. Copy the fixture into the new module rather than importing across test files (RESEARCH lines 286-290).

### Cursor stub shape differs per backend
**Apply to:** the two new tests — do not mix them up.
| Backend | Stub | Returns |
|---------|------|---------|
| Snowflake | `cursor.description` = list of 1-tuples `[("column_name",),("kind",),("data_type",),("comment",)]`; `cursor.fetchall.return_value` = list of 4-tuple rows | role rows with JSON `data_type` |
| Databricks | `cursor.fetchone.return_value = (schema_json,)` | single JSON string of `{"columns":[...]}` with `is_measure` bool |

### introspect → render → snapshot composition
**Source:** `render_and_format([view])` (`python_renderer.py:251-289`) wraps `render_views` + `format_with_ruff`; `render_views` (123-188) is the subprocess-free alternative.
**Apply to:** both new E2E tests + (read-only reference) the DuckDB regression guard.

### syrupy `.ambr` snapshot
**Source:** `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`
**Apply to:** both new snapshots; generate via `--snapshot-update`, commit.

### DuckDB regression guard (no new work, must stay green/byte-identical)
**Source:** `tests/unit/codegen/test_codegen_e2e.py::test_codegen_file_backed_duckdb` + its `.ambr`
**Apply as:** after the strict `_field_class_for` change, run `just test` and confirm this test passes WITHOUT `--snapshot-update`. The DuckDB snapshot contains only known roles, so the strict dict lookup returns identical strings (RESEARCH Pitfall 4, lines 329-333).

---

## No Analog Found

None. Every file maps to a concrete in-repo analog. The two new E2E tests are *compositions* of two existing analogs (DuckDB E2E structure + the engine-specific mock seam), not greenfield.

## Metadata

**Analog search scope:** `src/semolina/codegen/`, `src/semolina/engines/`, `tests/unit/codegen/`, `tests/unit/`, `docs/src/how-to/`
**Files read this turn (full or targeted):** `python_renderer.py` (1-125, 123-222, 251-290), `test_codegen_e2e.py` (full), `test_codegen_e2e.ambr` (full), `test_snowflake_engine.py` (40-129, 560-650), `test_databricks_engine.py` (28-73, 830-905), `test_python_renderer.py` (1-40), `codegen.rst` (205-254)
**Pattern extraction date:** 2026-06-09
**Codebase HEAD:** `f1a218e` (line numbers in RESEARCH verified accurate)
