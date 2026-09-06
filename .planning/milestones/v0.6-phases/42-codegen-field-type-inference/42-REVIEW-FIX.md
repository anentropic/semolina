---
phase: 42-codegen-field-type-inference
fixed_at: 2026-06-09T00:00:00Z
review_path: .planning/phases/42-codegen-field-type-inference/42-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 42: Code Review Fix Report

**Fixed at:** 2026-06-09
**Source review:** .planning/phases/42-codegen-field-type-inference/42-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — all Warnings)
- Fixed: 3
- Skipped: 0

Info findings (IN-01, IN-02, IN-03) were out of scope for `critical_warning` and
were not attempted.

## Fixed Issues

### WR-01: Documented TODO output contradicts actual renderer output

**Files modified:** `docs/src/how-to/codegen.rst`
**Commit:** 2b5d9ca
**Applied fix:** Replaced the "Handle TODO comments" example so it matches what the
renderer actually emits. Changed `territory = Dimension()` with a hand-written prose
comment to `territory = Dimension[Any]()` with the raw warehouse type descriptor
(`# TODO: {"type": "GEOGRAPHY"}`), matching `test_field_todo_data_type_emits_comment`.
Added prose noting `Any` keeps the module valid and that codegen adds
`from typing import Any` automatically. Applied the how-to second-person voice and a
humanizer pass (no promotional/AI vocabulary, single em-dash budget respected).

_Note: `uv run sphinx-build` could not be executed in this environment — the `docs`
dependency group (sphinx) is not synced and `.python-version` pins an interpreter that
requires network sync. The change is a self-contained RST code-block + prose swap using
directives already established in the same file; structure was verified by re-reading._

### WR-02: `todo_comment` interpolated into a single-line comment without sanitization

**Files modified:** `src/semolina/codegen/python_renderer.py`,
`tests/unit/codegen/test_python_renderer.py`
**Commits:** 91ca96d (failing test), ef520fe (fix)
**Applied fix:** Per the project bug-fix policy, first added a failing test
(`test_field_todo_comment_with_newline_stays_single_line`) adjacent to
`test_field_todo_data_type_emits_comment` that feeds a TODO descriptor containing
newlines and asserts the comment stays on one physical line. Then changed
`_build_model_context` to build the comment via `" ".join(f.data_type.split())`,
collapsing all whitespace (including embedded newlines from pretty-printed
STRUCT/MAP descriptors) so the generated `# ...` comment can never span lines and
break the emitted Python. All 32 renderer tests pass; failing-test-then-fix sequence
preserved across two commits.

### WR-03: Snowflake e2e test only exercised the non-default-casing (`source=`) path

**Files modified:** `tests/unit/codegen/test_codegen_e2e.py`,
`tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`
**Commit:** c028065
**Applied fix:** Changed the synthetic `SHOW COLUMNS` rows from lowercase
(`revenue`, `country`, `date_key`) to default UPPERCASE Snowflake names
(`REVENUE`, `COUNTRY`, `DATE_KEY`). These round-trip through
`name.lower().upper()` back to the original, so the engine emits no `source=` kwarg —
the common case the e2e test previously never covered. Regenerated only the Snowflake
snapshot block via syrupy `--snapshot-update`; the DuckDB and Databricks snapshot
blocks are byte-identical (verified via `git diff`, which touches only the three
Snowflake lines). Updated the docstring to document the casing path and point at the
`source=`-setting path covered in `test_python_renderer.py`.

_Note: `test_codegen_file_backed_duckdb` errors at fixture setup in this environment
because the optional `duckdb` package is not installed — pre-existing and unrelated to
this change. The Snowflake and Databricks e2e tests pass with no snapshot warnings._

---

_Fixed: 2026-06-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
