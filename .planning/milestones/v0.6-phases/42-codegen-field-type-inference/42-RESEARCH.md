# Phase 42: Codegen Field-Type Inference - Research

**Researched:** 2026-06-09
**Domain:** Reverse codegen field-role inference + offline mocked-connector snapshot testing
**Confidence:** HIGH (entirely codebase-verified; no external dependency research needed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **No `Field()` fallback.** Every backend's metadata source returns a concrete role for
  every column (DuckDB `object_kind` always DIMENSION/METRIC/FACT; Snowflake `kind` always
  METRIC/DIMENSION/FACT; Databricks `is_measure` binary → metric/dimension). The "unknown role"
  case cannot occur in normal operation. Do NOT add a `Field()` placeholder path.
- **Criterion 4 must be rewritten** in ROADMAP.md/REQUIREMENTS.md from "Existing `Field()`
  fallback behaviour is preserved..." → "every column resolves to a concrete role
  (`Metric`/`Dimension`/`Fact`) across all three backends; an unrecognized role string raises
  rather than silently defaulting."
- **Strict `_field_class_for`.** Change the current catch-all `return "Dimension"` to an explicit
  mapping: `"metric"` → `Metric`, `"fact"` → `Fact`, `"dimension"` → `Dimension`, anything else
  → raise. Rationale: enforce the "no unknown case" invariant; fail loudly on schema drift instead
  of mislabeling a column as Dimension. Follows bug-fix discipline: add the raise-path test first.
- **Snowflake + Databricks codegen tested OFFLINE** via mocked metadata. No live warehouse access
  (Snowflake trial expired) and none needed. Add codegen E2E snapshot tests for SF + Databricks
  feeding hand-crafted realistic metadata rows through the existing `sys.modules` connector mock,
  snapshotting rendered Python — extending DuckDB's `test_codegen_e2e.py` pattern. Satisfies
  criteria 2 & 3 with zero warehouse dependency.
- **Databricks has no Fact type** (documented constraint). Databricks metric views support only
  metric vs dimension. State this explicitly in the how-to and test intent so it does not read as
  a bug.
- **DuckDB criterion 1 — verify, don't rebuild.** DuckDB inference + e2e snapshot already exist.
  Confirm the existing snapshot still demonstrates per-role emission and survives the
  strict-`_field_class_for` change. No new DuckDB implementation.
- **Close-out:** amend the existing codegen how-to (not a new page) for per-role emission across
  all three backends + Databricks no-Fact note + strict-raise behaviour, applying the
  semolina-docs-author skill. Close DKGEN-05 traceability. Record per-backend metadata-query paths
  + strict-raise decision in PROJECT.md Key Decisions.

### Claude's Discretion

- Whether SF/Databricks codegen e2e tests live in `tests/unit/codegen/test_codegen_e2e.py` or
  sibling files (planner decides per conventions).
- Snapshot mechanism flavour (syrupy `.ambr` as DuckDB uses, vs golden module) — prefer matching
  the existing DuckDB e2e snapshot approach.
- Whether synthetic metadata rows are authored fresh or lifted from existing engine unit-test
  fixtures (check reuse first — see Reuse Analysis below).
- Exact wording of the ROADMAP/REQUIREMENTS criterion-4 rewrite.
- Exact exception type for strict-raise (prefer an existing Semolina error class over bare
  `ValueError` if one fits — see "Strict-Raise Exception Type" below for the verified recommendation).

### Deferred Ideas (OUT OF SCOPE)

None — phase scope fully captured. Cross-phase UAT audit of v0.5 is its own Phase 43.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DKGEN-05 | `semolina codegen` emits `Metric`/`Dimension`/`Fact` field types inferred from semantic view metadata across all three backends. DuckDB sources role info from `DESCRIBE SEMANTIC VIEW`; Snowflake and Databricks use their respective semantic-view metadata queries. | Inference is already implemented in all three engines (verified below). Phase work = SF/Databricks offline snapshot coverage + strict-raise hardening of `_field_class_for` + doc amendment + traceability close. Metadata-query paths confirmed: DuckDB `DESCRIBE SEMANTIC VIEW`, Snowflake `SHOW COLUMNS IN VIEW` (`kind`), Databricks `DESCRIBE TABLE EXTENDED ... AS JSON` (`is_measure`). |
</phase_requirements>

## Summary

This is a **verification + test-coverage + one-strictness-change** phase, not greenfield. Reading
the actual source confirms every claim in CONTEXT.md: field-role inference is fully implemented in
all three engines, the renderer already emits `Metric`/`Dimension`/`Fact` (no bare `Field()`
emitter exists anywhere), and DuckDB already has a committed codegen E2E syrupy snapshot proving
per-role emission. The two real gaps are (a) Snowflake and Databricks have no codegen E2E/snapshot
test, and (b) `python_renderer._field_class_for()` silently coerces any unrecognized role to
`Dimension` via a catch-all `return "Dimension"`.

The lowest-friction path for SF/Databricks offline codegen snapshots is to drive
`engine.introspect()` (with the already-established `sys.modules` connector mock) directly into
`render_views()` / `render_and_format()`, then assert against a syrupy `.ambr` snapshot — **not**
through the CLI. The CLI path for SF/Databricks calls `SnowflakeCredentials.load()` /
`DatabricksCredentials.load()` inside `_resolve_backend`, which DuckDB's E2E test sidesteps because
DuckDB takes a `--database` path instead of credentials. Driving introspect→render directly avoids
the credential layer entirely and reuses the exact mock seams already proven in the engine unit
tests.

**Primary recommendation:** Make `_field_class_for` a strict dict lookup that raises `ValueError`
on an unrecognized role (raise-test-first per project discipline); add two offline
introspect→render syrupy snapshot tests (Snowflake with METRIC/DIMENSION/FACT rows, Databricks with
`is_measure` true/false rows, no Fact); verify the DuckDB snapshot is unchanged by the strict change;
amend `docs/src/how-to/codegen.rst`; rewrite criterion 4; close DKGEN-05 and log decisions in
PROJECT.md.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Read warehouse role metadata | Engine / introspection (`engines/{duckdb,snowflake,databricks}.py`) | — | Each engine owns its warehouse-native metadata query; produces backend-agnostic `IntrospectedField.field_type`. |
| Map role string → field class name | Renderer (`codegen/python_renderer.py:_field_class_for`) | — | Pure transformation of the normalized lowercase role string; the strict-raise invariant lives here. |
| Emit `FieldClass[T]()` source | Template (`codegen/templates/python_model.py.jinja2`) | Renderer | Template renders `{{ field.field_class }}[{{ field.data_type }}]()`; renderer supplies `field_class`. |
| Drive introspect→render end-to-end | CLI (`cli/codegen.py`) for DuckDB; tests for SF/Databricks (offline) | — | SF/Databricks CLI path requires credentials; offline tests bypass it by calling introspect→render directly. |

## Standard Stack

No new libraries. This phase uses only what is already in the project.

### Core (already present)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | (pinned in lockfile) | Test runner; `just test` = `uv run pytest` | Project standard |
| syrupy | >=5.1.0 (pyproject.toml:60) | `.ambr` snapshot assertions | Already used by DuckDB codegen E2E test |
| typer + `typer.testing.CliRunner` | (pinned) | CLI invocation in DuckDB E2E test | Only needed if SF/Databricks tests go through CLI (they should NOT — see below) |
| jinja2 | (pinned) | Renders `python_model.py.jinja2` | Existing renderer dependency |

**Installation:** none — no `pip install` / dependency change in this phase. (Package Legitimacy
Audit therefore omitted: no external packages installed.)

## Architecture Patterns

### System Architecture Diagram (codegen field-type flow)

```
warehouse metadata query                  normalized IR                render
─────────────────────────                 ─────────────                ──────
DuckDB:  DESCRIBE SEMANTIC VIEW  ┐
         (object_kind: METRIC/   │
          DIMENSION/FACT)        │
                                 │   engine.introspect()      _build_model_context()
Snowflake: SHOW COLUMNS IN VIEW  ├──► IntrospectedField  ───►  _field_class_for(    ───► python_model
           (kind: METRIC/        │    .field_type =             field.field_type)         .py.jinja2
            DIMENSION/FACT,       │    "metric"|"dimension"      = "Metric"|"Fact"          │
            .lower()-ed)         │    |"fact"  (Literal)        |"Dimension"               ▼
                                 │                              [STRICT: else raise]   FieldClass[T]()
Databricks: DESCRIBE TABLE       │                                                     source string
            EXTENDED AS JSON      │
            (is_measure: bool ───┘
             → metric|dimension;
             NO fact)
```

The renderer only ever receives lowercase role strings (`metric`/`dimension`/`fact`); both
engines normalize before constructing `IntrospectedField` (Snowflake `.lower()`s `kind`;
Databricks maps `is_measure` → literal `"metric"`/`"dimension"`). The strict map keys are therefore
lowercase.

### Pattern 1: Offline mocked-connector introspection (the established seam)

**What:** Both SF and Databricks engine unit tests pre-populate `sys.modules` with `MagicMock`
connector packages (so the lazy `import snowflake.connector` / `import databricks.sql` inside
`introspect()` resolves), then patch `connect()` → `__enter__` → `cursor()` → `__enter__` to a
mock cursor whose `description` / `fetchall()` / `fetchone()` return synthetic metadata.

**Snowflake mock seam** (`tests/unit/test_snowflake_engine.py`):
```python
# Source: tests/unit/test_snowflake_engine.py lines 47-76, 595-642
# autouse fixture installs sys.modules mocks for snowflake / .connector / .connector.errors
mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
mock_cursor.fetchall.return_value = [
    ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
    ("country", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
    ("date_key", "FACT", json.dumps({"type": "DATE"}), ""),
]
with patch("snowflake.connector.connect") as mock_connect:
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    result = engine.introspect("sales_view")
```

**Databricks mock seam** (`tests/unit/test_databricks_engine.py`):
```python
# Source: tests/unit/test_databricks_engine.py lines 28-73, 838-892
# _create_mock_databricks() + patch.dict(sys.modules, {...}); cursor.fetchone() returns (json_str,)
schema_json = json.dumps({"columns": [
    {"name": "revenue", "is_measure": True,  "type": {"name": "double"}, "comment": ""},
    {"name": "country", "is_measure": False, "type": {"name": "string"}, "comment": ""},
]})
mock_cursor.fetchone.return_value = (schema_json,)
mock_sql.connect.return_value.__enter__.return_value = mock_conn
mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
result = engine.introspect("sales_view")
```

**When to use:** This exact seam should drive the new codegen snapshot tests. After `introspect()`
returns an `IntrospectedView`, feed it to `render_and_format([view])` (or `render_views`) and
assert `== snapshot`.

### Pattern 2: DuckDB codegen E2E reference (mirror this)

**What:** `tests/unit/codegen/test_codegen_e2e.py` invokes the CLI via `CliRunner` against a real
file-backed DuckDB fixture (`duckdb_file_backed_db` in `tests/conftest.py:194`) and asserts
`result.output == snapshot`. The committed snapshot
(`tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`) shows `Fact[int]()`, `Dimension[str]()`,
`Metric[int]()` — proving per-role emission for DuckDB.

**Why SF/Databricks must NOT mirror it via CLI:** `_resolve_backend("snowflake", ...)` calls
`SnowflakeCredentials.load()` and `_resolve_backend("databricks", ...)` calls
`DatabricksCredentials.load()` (`src/semolina/cli/codegen.py:86-101`). DuckDB's E2E test works
through the CLI only because the DuckDB branch takes a `--database` path, no credentials. To stay
offline, SF/Databricks snapshot tests should call `engine.introspect(...)` (mocked connector) →
`render_and_format([...])` directly and snapshot that string, OR construct `IntrospectedView`
objects directly from the synthetic rows. Driving introspect→render exercises more of the real
path (the engine's role normalization), so it is the stronger choice for criteria 2 & 3.

### Anti-Patterns to Avoid
- **Routing SF/Databricks codegen tests through `CliRunner`/`_resolve_backend`.** Triggers the
  credentials loader; offline-incompatible. Drive introspect→render directly.
- **Re-snapshotting DuckDB output as if new.** The DuckDB snapshot already exists and must remain
  byte-identical after the strict change (it only contains known roles, so strictness is a no-op
  for it). Treat as a regression guard, not new work.
- **Adding a `Field()` import or placeholder branch.** Explicitly forbidden by the locked decision.
- **Catching the new strict-raise inside the renderer.** It must propagate (fail loudly).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Snapshot of rendered Python | Hand-maintained golden string in the test body | syrupy `.ambr` (already used) | Auto-update via `--snapshot-update`, consistent with DuckDB test |
| Connector mocking for SF/Databricks | New mock infrastructure | Existing `sys.modules` + `connect/cursor/fetch*` seam | Already proven across ~40 engine unit tests |
| Synthetic metadata rows | Inventing a new fixture shape | Lift row shapes from existing introspect tests | Shapes already match what `introspect()` parses (see Reuse Analysis) |

**Key insight:** Every piece of machinery this phase needs already exists in the test suite. The
work is composition (introspect→render→snapshot) plus one defensive `raise`, not new infrastructure.

## Confirmed Current State (exact line numbers — supersedes CONTEXT.md approximations)

| Artifact | File | Lines | Current behaviour |
|----------|------|-------|-------------------|
| `_field_class_for` (STRICT-RAISE TARGET) | `src/semolina/codegen/python_renderer.py` | **65–79** | `if "metric"→Metric; if "fact"→Fact; return "Dimension"` (catch-all default). This is the change site. |
| `_build_model_context` (caller of `_field_class_for`) | `src/semolina/codegen/python_renderer.py` | 82–120 (call at **109**) | Passes `f.field_type` straight through. |
| `IntrospectedField.field_type` | `src/semolina/codegen/introspector.py` | **40** | `Literal["metric", "dimension", "fact"]` — a *typed contract*. An out-of-Literal value is a contract violation (supports `ValueError`/strict-raise rationale). |
| Template emit | `src/semolina/codegen/templates/python_model.py.jinja2` | **17, 19** | `{{ field.field_class }}[{{ field.data_type }}]()`; import line (**7**) is `from semolina import SemanticView, Metric, Dimension, Fact` — **no `Field` import**, confirming no bare-`Field()` emitter. |
| DuckDB role parse | `src/semolina/engines/duckdb.py` | (DESCRIBE SEMANTIC VIEW parse; sets metric/dimension/fact) | Already implemented (per CONTEXT + DuckDB snapshot). |
| Snowflake role read | `src/semolina/engines/snowflake.py` | `introspect()` **264–381**; `kind` lowercased at **336** | `field_type = d["kind"].lower()`; passes into `IntrospectedField(field_type=..., # type: ignore[arg-type])` at **359**. |
| Databricks role read | `src/semolina/engines/databricks.py` | `introspect()` **271–376**; `is_measure` at **336–337** | `field_type = "metric" if is_measure else "dimension"`; no Fact. `# type: ignore[arg-type]` at **350**. |
| `Metric`/`Dimension`/`Fact` defs | `src/semolina/fields.py` | ~668–698 (per CONTEXT; not re-read — not on the change path) | All subclass `Field[T]`. |

**Note on the `# type: ignore[arg-type]` comments:** both engines assign a runtime `str` into the
`Literal`-typed `field_type`. The strict-raise lives downstream in the renderer, not in the engines.
The planner need not touch those ignores; they are pre-existing and out of scope.

## Strict-Raise Exception Type (verified recommendation)

**Recommendation: raise `ValueError`.** Rationale, from reading `src/semolina/engines/base.py`:

- The only Semolina-specific error classes are `SemolinaViewNotFoundError(RuntimeError)` and
  `SemolinaConnectionError(RuntimeError)` (`engines/base.py:19, 23`). Both are *warehouse
  connection/lookup* domain errors — semantically wrong for "the renderer received a role string
  outside its `Literal` contract." There is **no general-purpose `SemolinaError` base class**
  (`grep` confirms only `CredentialError(Exception)` in `testing/credentials.py`, also unrelated).
- `_field_class_for` receives a value that is typed `Literal["metric","dimension","fact"]`. An
  unrecognized value is a programming/contract-invariant violation, which is idiomatically a
  `ValueError` in Python. `ValueError` also matches the existing codebase convention: the `Engine`
  ABC docstrings document `ValueError` for invalid inputs (`engines/base.py:74, 114`).
- This keeps the change self-contained in `python_renderer.py` with no new error-class plumbing.

The planner may instead introduce a small dedicated error class if it prefers a named exception,
but `ValueError` is the lowest-friction, convention-consistent choice. Use the CONTEXT.md
specifics-block shape:

```python
_ROLE_TO_CLASS = {"metric": "Metric", "dimension": "Dimension", "fact": "Fact"}

def _field_class_for(field_type: str) -> str:
    try:
        return _ROLE_TO_CLASS[field_type]
    except KeyError:
        raise ValueError(f"Unrecognized field role: {field_type!r}") from None
```

(Keep the existing Google-style docstring; update its `Raises:` section to document the new
`ValueError`. Line length 100. No `# type: ignore`.)

## Reuse Analysis (synthetic metadata rows)

Per Claude's Discretion, "check reuse first." Findings:

- **Snowflake:** `tests/unit/test_snowflake_engine.py:595-642`
  (`test_introspect_basic_metric_dimension_fact`) already builds exactly the
  METRIC/DIMENSION/FACT row set the snapshot needs: a metric (`FIXED`/scale 0 → int), a dimension
  (`TEXT` → str), a fact (`DATE` → datetime.date). The `description`/`fetchall` shape is reusable
  verbatim. A `_make_cursor_row(column_name, kind, data_type_dict, comment)` helper already exists
  (line 575) for building rows.
- **Databricks:** `tests/unit/test_databricks_engine.py:842-892`
  (`test_introspect_basic_measures_and_dimensions`) builds an `is_measure=True` measure (`double`
  → float) and `is_measure=False` dimension (`string` → str). A `_make_schema_json(columns)` helper
  exists (line 838). This is the right shape for the Databricks snapshot; it correctly contains **no
  Fact** (demonstrating the no-Fact constraint).

**Recommendation:** Author the snapshot tests in `tests/unit/codegen/` (alongside
`test_codegen_e2e.py`) and *copy* the row shapes from the engine tests rather than importing across
test modules (test-to-test imports are brittle; the rows are tiny). For Databricks the snapshot
should include a comment/docstring stating that the absence of Fact is intentional (no native Fact
type). This keeps the codegen snapshot self-documenting.

**`from models import Sales` importability:** the engine unit tests do `from models import Sales`
(`tests/models.py`). This resolves because pytest inserts the rootdir/`tests` dir on `sys.path` via
the conftest mechanism (rootdir conftest at `tests/conftest.py` does `from models import Sales` at
line 17). New tests under `tests/unit/codegen/` inherit the same import resolution. The new codegen
snapshot tests do **not** need `Sales`; they need `IntrospectedView`/`IntrospectedField` and the
engine classes, all importable from `semolina.*`.

## Common Pitfalls

### Pitfall 1: Credential loader trips the offline test
**What goes wrong:** Routing SF/Databricks codegen through `CliRunner` invokes
`SnowflakeCredentials.load()` / `DatabricksCredentials.load()` in `_resolve_backend`
(`cli/codegen.py:86-101`), which either reads env/config or raises — not offline-clean.
**How to avoid:** Call `engine.introspect()` (mocked connector) → `render_and_format([view])`
directly. Do not go through `_resolve_backend`.
**Warning signs:** Test references `CredentialError`, env vars, or `.semolina.toml`.

### Pitfall 2: ruff-formatting nondeterminism in snapshots
**What goes wrong:** `render_and_format` shells out to `uv run ruff format` + isort; if ruff is
unavailable it falls back to *unformatted* source (`format_with_ruff` returns input on
`FileNotFoundError`). A snapshot captured with ruff present can diverge in CI without ruff.
**How to avoid:** Prefer snapshotting `render_views([view])` (deterministic Jinja output, no
subprocess) for the field-type assertion, OR ensure the test environment always has ruff (it does
under `uv run pytest`). The DuckDB E2E snapshot goes through the full CLI (which calls
`render_and_format`) and is stable because CI runs under `uv`. Match whichever the planner picks to
the DuckDB precedent; if matching DuckDB exactly, `render_and_format` is fine under `just test`.
**Warning signs:** Snapshot diffs that are pure whitespace/import-ordering.

### Pitfall 3: Strict change silently breaks an existing test expecting Dimension default
**What goes wrong:** Some existing renderer test might pass a role outside `{metric,dimension,fact}`
and rely on the Dimension fallback.
**How to avoid:** Grep `tests/unit/codegen/test_python_renderer.py` — verified: every test uses
only `"metric"`/`"dimension"`/`"fact"` (lines 17-352). The catch-all is currently only reachable by
non-Literal input, which no test supplies. The strict change is safe for the existing suite. Add
the new raise-path test adjacent to `TestRenderViews`.
**Warning signs:** An existing test passing `field_type="..."` with a non-standard string.

### Pitfall 4: DuckDB snapshot drift
**What goes wrong:** Touching the renderer could change DuckDB output.
**How to avoid:** The DuckDB snapshot contains only `Fact`/`Dimension`/`Metric` (all known roles),
so the strict dict lookup returns identical strings. Run `just test` and confirm
`test_codegen_file_backed_duckdb` passes with no `--snapshot-update`.

## Code Examples

### Strict `_field_class_for` raise-path test (bug-fix-first: write before the impl change)
```python
# Place adjacent to TestRenderViews in tests/unit/codegen/test_python_renderer.py
import pytest
from semolina.codegen.python_renderer import _field_class_for

def test_field_class_for_unrecognized_role_raises() -> None:
    """Unrecognized role string raises rather than defaulting to Dimension."""
    with pytest.raises(ValueError, match="Unrecognized field role"):
        _field_class_for("widget")
```

### Offline Snowflake codegen snapshot (introspect → render → syrupy)
```python
# Sketch for tests/unit/codegen/ — reuses the SF sys.modules mock seam.
# Snowflake rows lifted from test_snowflake_engine.py:608-612 (metric/dimension/fact).
def test_codegen_snowflake_field_types(snapshot):
    # ... install sys.modules snowflake mocks (autouse fixture or inline) ...
    mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
    mock_cursor.fetchall.return_value = [
        ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
        ("country", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
        ("date_key", "FACT", json.dumps({"type": "DATE"}), ""),
    ]
    with patch("snowflake.connector.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        from semolina.engines.snowflake import SnowflakeEngine
        from semolina.codegen.python_renderer import render_and_format
        engine = SnowflakeEngine(account="t", user="u", password="p")
        view = engine.introspect("sales_view")
    assert render_and_format([view]) == snapshot   # proves Metric/Dimension/Fact emission
```

### Offline Databricks codegen snapshot (no Fact — intentional)
```python
# Databricks rows lifted from test_databricks_engine.py:850-855 (measure + dimension; NO fact).
def test_codegen_databricks_field_types(snapshot):
    """Databricks emits Metric/Dimension only — it has no native Fact type."""
    schema_json = json.dumps({"columns": [
        {"name": "revenue", "is_measure": True,  "type": {"name": "double"}, "comment": ""},
        {"name": "country", "is_measure": False, "type": {"name": "string"}, "comment": ""},
    ]})
    mock_cursor.fetchone.return_value = (schema_json,)
    # ... patch.dict(sys.modules, {...}); connect/cursor seam ...
    view = engine.introspect("sales_view")
    assert render_and_format([view]) == snapshot
```

## Doc Amendment Target

**File:** `docs/src/how-to/codegen.rst` (the existing codegen how-to — NOT a new page).

**Current state (already partially covers field types):**
- Lines 211–225: a worked DuckDB example showing `Fact[int]()`/`Dimension[str]()`/`Metric[int]()`,
  followed by a `.. note::` (223–225) already stating "Databricks has no native Fact type, so all
  non-measure fields map to `Dimension()`. DuckDB ... support all three field kinds."
- Lines 227–240: a "Understand field type mapping" list-table mapping Metric/Measure → `Metric[T]()`,
  Dimension → `Dimension[T]()`, Fact (Snowflake and DuckDB) → `Fact[T]()`.

**What the amendment must add (per locked decision):**
1. Make the per-role emission explicit for *all three* backends (the table already implies it;
   confirm Snowflake/Databricks are stated, not just DuckDB).
2. Reinforce the Databricks no-Fact constraint (already present at 223–225 — verify wording is
   adequate, lightly expand if needed).
3. **New:** document the strict-raise behaviour — an unrecognized warehouse role string causes
   codegen to fail loudly rather than silently mislabel the column. This is new content not present
   today.

**Mandatory skill:** `@.claude/skills/semolina-docs-author/SKILL.md` (Diataxis how-to + humanizer).
The amendment is likely <50% of the page (targeted additions), so per CLAUDE.md it is an "API
surface change / targeted update" — apply the skill's humanizer pass on the changed prose. The
planner MUST add the skill reference to the doc task's `<execution_context>`.
**Doc gate:** `just docs-build` (= `uv run sphinx-build -W docs/src docs/_build`, strict `-W`).

## Close-Out Targets

| Action | File / Location |
|--------|-----------------|
| Rewrite criterion 4 | `.planning/ROADMAP.md:152` (Phase 42 success criterion 4) and `.planning/REQUIREMENTS.md` DKGEN-05 wording (line 23 if it implies fallback) |
| Close DKGEN-05 traceability | `.planning/REQUIREMENTS.md`: line 23 checkbox `[ ]`→`[x]`; Traceability table line 67 `Pending`→`Complete` |
| Log decisions in Key Decisions | `.planning/PROJECT.md` Key Decisions table (starts line 122) — add: per-backend metadata-query paths (`DESCRIBE SEMANTIC VIEW` / `SHOW COLUMNS IN VIEW` / `DESCRIBE TABLE EXTENDED ... AS JSON`) and strict-raise-on-unrecognized-role |
| Mark DKGEN-05 in ROADMAP progress | `.planning/ROADMAP.md` Phase 42 row + progress table |

## Project Constraints (from CLAUDE.md)

- **Quality gates before commit:** `prek run --all-files` (ruff lint+format, basedpyright strict,
  shellcheck), `just test` (unit + jaffle-shop mock tests), `just docs-build`.
- **No `# type: ignore`** in new code; solve typing properly. (The strict `_field_class_for` takes
  `str` and returns `str` — no typing friction expected.)
- **Bug-fix discipline:** reproduce with a failing test first, then the fix. Applies to the
  strict-raise change: commit the raise-path test (red), then the `_field_class_for` change (green).
- **Line length 100**; Google-style docstrings; D213 (summary on second line); multi-line docstring
  quotes on own lines; ruff isort import sorting.
- **Docs:** semolina-docs-author skill MANDATORY for the how-to amendment; tabbed SQL-dialect
  examples use sphinx-design `:sync-group: warehouse` where relevant.

## Validation Architecture

> Nyquist validation is enabled. This section maps each success criterion to an observable,
> automated check. It is consumed downstream to derive VALIDATION.md.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `uv run pytest`); syrupy >=5.1.0 for snapshots |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths `["tests", "src"]`, `--doctest-modules`) |
| Quick run command | `uv run pytest tests/unit/codegen/ -x` |
| Full suite command | `just test` (`uv run pytest` + jaffle-shop `uv run pytest`) |
| Snapshot update | `uv run pytest tests/unit/codegen/ --snapshot-update` (syrupy) |
| Doc gate | `just docs-build` (`sphinx-build -W`) |

### Success Criterion → Observable Verification
| Criterion | Behavior | How verified | Test / artifact |
|-----------|----------|--------------|-----------------|
| 1 (DuckDB per-role) | DuckDB emits Metric/Dimension/Fact from `DESCRIBE SEMANTIC VIEW` | Existing committed snapshot shows `Fact[int]()`/`Dimension[str]()`/`Metric[int]()`; must remain green & byte-identical after strict change | `tests/unit/codegen/test_codegen_e2e.py::test_codegen_file_backed_duckdb` + `__snapshots__/test_codegen_e2e.ambr` |
| 2 (Snowflake per-role) | SF emits Metric/Dimension/Fact from `SHOW COLUMNS IN VIEW` `kind` | NEW offline introspect→render snapshot asserts rendered Python contains the three field classes | NEW test in `tests/unit/codegen/` + new `.ambr` snapshot (METRIC/DIMENSION/FACT rows) |
| 3 (Databricks per-role) | Databricks emits Metric/Dimension (no Fact) from `is_measure` | NEW offline introspect→render snapshot; asserts Metric + Dimension, intentionally no Fact (documented) | NEW test in `tests/unit/codegen/` + new `.ambr` snapshot (`is_measure` true/false) |
| 4 (rewritten: strict-raise) | Unrecognized role raises, no silent Dimension default | NEW unit test asserts `pytest.raises(ValueError)` from `_field_class_for("<unknown>")`; criterion text rewritten in ROADMAP/REQUIREMENTS | NEW `test_field_class_for_unrecognized_role_raises` in `tests/unit/codegen/test_python_renderer.py` |
| 5 (close-out) | DKGEN-05 traceability + PROJECT.md decisions updated | Doc inspection: REQUIREMENTS.md DKGEN-05 `[x]` + table `Complete`; PROJECT.md Key Decisions row present | `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md` (+ `just docs-build` green for the how-to amendment) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/codegen/ -x`
- **Per wave merge:** `just test`
- **Phase gate:** `prek run --all-files` + `just test` + `just docs-build` all green before
  `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] NEW Snowflake codegen snapshot test + `.ambr` (covers criterion 2) — file under
      `tests/unit/codegen/` (planner picks `test_codegen_e2e.py` vs sibling).
- [ ] NEW Databricks codegen snapshot test + `.ambr` (covers criterion 3).
- [ ] NEW `_field_class_for` raise-path test in `tests/unit/codegen/test_python_renderer.py`
      (covers rewritten criterion 4) — written *before* the impl change per bug-fix discipline.
- Framework: already present (pytest + syrupy). No install needed.

## State of the Art

Not applicable — no external technology currency concerns. All patterns are internal and
verified against the current codebase (2026-06-09).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (none) | — | All claims in this research are codebase-VERIFIED by reading the actual source files at HEAD. No `[ASSUMED]` claims. |

The exact line range of `Metric`/`Dimension`/`Fact` in `src/semolina/fields.py` (~668–698) is
taken from CONTEXT.md and not independently re-read, because those classes are not on this phase's
change path (the renderer emits class *names* as strings; it does not import the field classes).
This does not affect any planning decision.

## Open Questions (RESOLVED)

1. **Snapshot vehicle: `render_views` vs `render_and_format` for the SF/Databricks tests?**
   **RESOLVED:** plans use `render_and_format` (matches the DuckDB precedent and proves the real
   user-facing output; `just test` runs under `uv` so ruff is always present).
   - What we know: DuckDB E2E goes through the CLI → `render_and_format` (ruff-formatted). `render_views`
     is deterministic Jinja with no subprocess.
   - What's unclear: whether to match DuckDB's ruff-formatted output exactly or snapshot raw Jinja.
   - Recommendation: snapshot `render_and_format([...])` to match the DuckDB precedent and prove the
     real user-facing output; `just test` always runs under `uv` so ruff is present. If the planner
     wants subprocess-free determinism, `render_views` is an acceptable alternative — both prove the
     field classes are emitted.

2. **One combined test file or per-backend siblings?** (Claude's Discretion.)
   **RESOLVED:** both new SF + Databricks codegen snapshot tests are co-located in
   `tests/unit/codegen/test_codegen_e2e.py` (sharing the existing `.ambr` snapshot file).
   - Recommendation: add SF + Databricks cases to the existing `tests/unit/codegen/test_codegen_e2e.py`
     (one `.ambr` file already lives there), keeping all codegen E2E snapshots co-located. Planner's call.

## Environment Availability

> SF/Databricks tests are fully offline (mocked connectors). DuckDB fixture is already exercised.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Live Snowflake | criterion 2 | ✗ (not needed) | — | Offline `sys.modules` connector mock (established) |
| Live Databricks | criterion 3 | ✗ (not needed) | — | Offline `sys.modules` connector mock (established) |
| `duckdb` (native) | criterion 1 fixture | ✓ (Phase 41 fixture uses it) | community `semantic_views` ext | — |
| `uv` + ruff | `render_and_format` snapshot | ✓ (`just test` runs under uv) | pinned | `format_with_ruff` falls back to raw source if absent |
| Sphinx (`-W`) | how-to amendment gate | ✓ (`just docs-build`) | pinned | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** live warehouses (intentionally replaced by mocks — this is
the design, not a gap).

## Sources

### Primary (HIGH confidence — codebase read at HEAD `f1a218e`)
- `src/semolina/codegen/python_renderer.py` — `_field_class_for` (65–79), `_build_model_context` (82–120)
- `src/semolina/codegen/introspector.py` — `IntrospectedField.field_type` Literal (40)
- `src/semolina/codegen/templates/python_model.py.jinja2` — emit (17,19), imports (7; no `Field`)
- `src/semolina/engines/snowflake.py` — `introspect()` (264–381), `kind` (336)
- `src/semolina/engines/databricks.py` — `introspect()` (271–376), `is_measure` (336–337)
- `src/semolina/engines/base.py` — error classes (19, 23); ABC docstrings cite ValueError (74,114)
- `src/semolina/cli/codegen.py` — `_resolve_backend` (65–125; credential load 86–101), `codegen` (128–179)
- `tests/unit/codegen/test_codegen_e2e.py` — DuckDB CLI E2E pattern (full file)
- `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` — committed DuckDB snapshot
- `tests/unit/codegen/test_python_renderer.py` — renderer tests (only known roles, 17–352)
- `tests/unit/test_snowflake_engine.py` — SF mock seam (47–76), introspect rows (575–642)
- `tests/unit/test_databricks_engine.py` — Databricks mock seam (28–73), introspect rows (838–892)
- `tests/conftest.py` — `duckdb_file_backed_db` (194), `from models import Sales` (17)
- `tests/models.py` — `Sales` model
- `docs/src/how-to/codegen.rst` — field-type section (211–251)
- `.planning/REQUIREMENTS.md` (DKGEN-05, traceability), `.planning/ROADMAP.md` (Phase 42),
  `.planning/PROJECT.md` (Key Decisions 122+), `justfile` (test 18, docs-build 23)
- `.planning/phases/42-codegen-field-type-inference/42-CONTEXT.md` — locked decisions

### Secondary / Tertiary
- None — no web/Context7 lookups required; phase is entirely internal.

## Metadata

**Confidence breakdown:**
- Current-state confirmation: HIGH — every artifact read directly at HEAD; line numbers exact.
- SF/Databricks offline test approach: HIGH — mock seams and reuse fixtures verified in source.
- Strict-raise exception choice: HIGH — verified absence of a fitting Semolina error class;
  `ValueError` matches Literal-contract semantics and ABC docstring convention.
- Doc amendment target: HIGH — `codegen.rst` lines located; existing field-type content read.

**Research date:** 2026-06-09
**Valid until:** 2026-07-09 (stable; internal codebase, no fast-moving external deps). Re-verify
line numbers only if `python_renderer.py` / the engines change before planning executes.
