---
phase: 47-type-fidelity-probe-decision-doc
reviewed: 2026-08-12T07:42:35Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - tests/type_fidelity_probe.py
  - tests/unit/test_type_fidelity_duckdb.py
  - tests/unit/test_type_fidelity_table.py
  - tests/integration/test_type_fidelity.py
  - justfile
  - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_params.json
  - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_query.sql
  - tests/integration/cassettes/integration/test_type_fidelity/test_snowflake_probe/adbc_driver_snowflake.dbapi/000_result.arrow
  - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_params.json
  - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_query.sql
  - tests/integration/cassettes/integration/test_type_fidelity/test_databricks_probe/adbc_driver_manager.dbapi/databricks/000_result.arrow
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 47: Code Review Report

**Reviewed:** 2026-08-12T07:42:35Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the type-fidelity probe module (`tests/type_fidelity_probe.py`, ~1892 lines), its
three consuming test modules, the new `justfile` recipe, and the committed cassette fixtures.

The module's central design contract — that the "result half" (`probe_schema`,
`probe_value_types`, `_cassette_result_cells`) never imports `semolina.codegen.type_map`, while
the "metadata half" (`measure_duckdb`'s use of `Engine.introspect`, `collect_snowflake_rows`,
`collect_databricks_rows`) legitimately does — holds throughout the file. I traced every
`FidelityRow` construction site and confirmed `result_arrow_type` and `python_value_type` are
always sourced from a raw ADBC schema or a raw Arrow-to-Python conversion, never from the type
map; only `mapped_annotation` touches `semolina.codegen.type_map`, which is correct by design.
`FidelityRow` carries no value-bearing field, and `_render_observed_value` only ever prints
`None`, literal `0`, or a type name — no warehouse row value has a path into the committed
artifact. No hardcoded secrets, no dangerous functions, no debug prints, no bare excepts, no
`# type: ignore`, no stray `>>>` doctest prompts.

The issues found are all latent/forward-looking robustness gaps rather than defects that
misstate today's measurement: a path-coupling problem that will break the staleness test once
this project's own documented archival workflow runs, a markdown-escaping gap that could
undermine the circularity guard's reliability for pathological input, an unreachable
trailing-comma bug in a general-purpose SQL builder, and two minor code-quality nits.

## Warnings

### WR-01: Committed artifact path is pinned inside the phase's own directory, which this project's workflow will relocate

**File:** `tests/type_fidelity_probe.py:486-492`
**Issue:** `ARTIFACT_PATH` is hardcoded to
`.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md`. No other file in
`tests/` or `src/` references a path under `.planning/phases/` — this is a new pattern
introduced by this phase. This project has a documented `gsd-cleanup` workflow ("Archive
accumulated phase directories from completed milestones") that moves completed phase
directories out of `.planning/phases/` once a milestone closes. `test_committed_table_is_not_stale`
(`tests/unit/test_type_fidelity_table.py:117-122`) calls `main(["--check"])` every `just test`
run, which reads `ARTIFACT_PATH` unconditionally
(`tests/type_fidelity_probe.py:1877`: `ARTIFACT_PATH.read_text(...) if ARTIFACT_PATH.exists() else ""`).
Once phase 47's directory is archived, that path no longer exists, `committed` becomes `""`,
and `--check` unconditionally returns `1` — permanently failing `just test`/CI for any future,
unrelated change, until someone remembers this one hardcoded constant needs updating.
Phases 48 and 50 are documented to consume this artifact "as a specification," which makes the
eventual archival of `.planning/phases/47-.../` an expected, not hypothetical, event for this
exact directory.
**Fix:** Resolve the artifact's canonical location independently of the originating phase
number (e.g. a stable path such as `.planning/artifacts/type-fidelity.md`, or a path read from
a small committed pointer file), or make `test_committed_table_is_not_stale` degrade to a
skip/xfail with a clear message when `ARTIFACT_PATH.parent` no longer exists, instead of a hard
failure that looks like a code regression:
```python
if not ARTIFACT_PATH.exists():
    pytest.skip(f"{ARTIFACT_PATH} not found — phase directory may have been archived")
```

### WR-02: Table-cell rendering does not escape `|`, weakening the circularity guard it exists to protect

**File:** `tests/type_fidelity_probe.py:570-578` (`render_artifact`), `tests/type_fidelity_probe.py:1710-1713` (`render_capability_table`)
**Issue:** Row cells are joined with `"| " + " | ".join(cells) + " |"` straight from measured
strings (`metadata_raw_type`, which can be a raw DuckDB `DESCRIBE` type string or a
`json.dumps(descriptor)` blob at `tests/type_fidelity_probe.py:1096,1128`). Nothing escapes a
literal `|` or embedded newline in a cell before it goes into the table row. If a future field's
raw warehouse type or JSON descriptor happens to contain a `|` (plausible for DuckDB composite
types such as `UNION(...)`, or any string value inside a JSON descriptor), the row gains an
extra column. `tests/unit/test_type_fidelity_table.py::_parse_comparison_table` (lines 88-93)
parses every row purely by splitting on `|`, so a shifted row feeds wrong values into
`_column()` — this directly weakens
`test_result_and_mapped_vocabularies_are_disjoint` (the circularity guard this phase exists to
make trustworthy), either masking a real mapped/result overlap or producing a confusing
off-by-one failure that looks unrelated to its actual cause.
**Fix:** Escape `|` (and normalize embedded newlines) when building cell text, e.g. in
`FidelityRow.as_cells()` or at the join site:
```python
def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
```

### WR-03: `describe_raw_types` emits invalid SQL when both `dimensions` and `metrics` are empty

**File:** `tests/type_fidelity_probe.py:393-405`
**Issue:**
```python
parts: list[str] = []
if dimensions:
    parts.append(f"dimensions := [{dim_list}]")
if metrics:
    parts.append(f"metrics := [{metric_list}]")
...
cursor.execute(f"DESCRIBE SELECT * FROM semantic_view({view_literal}, {', '.join(parts)})")
```
When `parts` is empty, `', '.join(parts)` is `""`, producing
`semantic_view('view', )` — a trailing comma immediately before the closing paren, which is a
DuckDB syntax error. Currently unreachable because the only caller
(`measure_duckdb`, `tests/type_fidelity_probe.py:837`) always passes a non-empty `dimensions`
and `metrics` list, but this is a general-purpose helper and the bug would resurface the moment
a future caller probes a metrics-only or dimensions-only view.
**Fix:**
```python
args = ", ".join([view_literal, *parts])
cursor.execute(f"DESCRIBE SELECT * FROM semantic_view({args})")
```

## Info

### IN-01: `collect_rows()` is dead code

**File:** `tests/type_fidelity_probe.py:1149-1156`
**Issue:** `collect_rows()` combines `collect_duckdb_rows() + collect_snowflake_rows() +
collect_databricks_rows()`, but `main()` (`tests/type_fidelity_probe.py:1859-1860`)
reimplements the same three-way concatenation inline instead of calling it, and no test imports
it either.
**Fix:** Either call `collect_rows()` from `main()`, or delete the unused function.

### IN-02: Import-time filesystem/import side effects in a doctest-collected module

**File:** `tests/type_fidelity_probe.py:212` (`NOT_IMPLEMENTED_ERRORS = _resolve_not_implemented_errors()`), `tests/type_fidelity_probe.py:918` (`CASSETTE_ROOT = _cassette_root()`)
**Issue:** Both module-level constants run real I/O (reading `pyproject.toml`) or an eager
`import adbc_driver_manager` at import time. Because this module has no `python_files` pattern
match and is instead collected purely for `--doctest-modules` (per its own module docstring),
every `pytest` invocation in this repo pays this import cost and is exposed to any
misconfiguration in `pyproject.toml`'s `adbc_cassette_dir` key as a collection-time failure,
rather than only when type-fidelity tests are actually selected.
**Fix:** Low priority given the values are also needed at `--write`/`--check` time regardless;
consider deferring resolution into `main()`/the collector functions if collection-time cost
becomes a real friction point.

---

_Reviewed: 2026-08-12T07:42:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
