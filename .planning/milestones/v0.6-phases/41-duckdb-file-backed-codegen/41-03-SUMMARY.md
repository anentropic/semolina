---
phase: 41-duckdb-file-backed-codegen
plan: 03
subsystem: codegen
tags: [duckdb, codegen, docs, requirements, syrupy, snapshot, pre-commit]

# Dependency graph
requires:
  - phase: 41-duckdb-file-backed-codegen
    plan: 01
    provides: duckdb_file_backed_db session fixture + test_codegen_e2e.py (RED, snapshot uncaptured)
  - phase: 41-duckdb-file-backed-codegen
    plan: 02
    provides: _normalize_database_path + INSTALL/LOAD on native introspection conn (the path the E2E test exercises)
provides:
  - "Captured syrupy snapshot tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr for test_codegen_file_backed_duckdb"
  - "docs/src/how-to/codegen.rst: new 'Point DuckDB codegen at a database file' section + reconciled DuckDB output tab (v0.10.2 grammar, 5-field shape)"
  - "REQUIREMENTS.md DKGEN-04 marked Complete, wording amended to fixture-generation strategy"
  - "Pre-commit fix: *.ambr excluded from whitespace-trimming hooks (syrupy blank-line corruption)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "syrupy .ambr snapshots must be excluded from trailing-whitespace/end-of-file-fixer (2-space blank-line indents)"
    - "How-to DuckDB DDL examples use semantic_views v0.10.2 `name AS expression` grammar"

key-files:
  created:
    - tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
  modified:
    - docs/src/how-to/codegen.rst
    - .planning/REQUIREMENTS.md
    - .pre-commit-config.yaml
    - tests/unit/codegen/test_cli.py

key-decisions:
  - "Reconciled the existing DuckDB output tab to the verified fixture (5 fields: unit_price Fact, country/region Dimension, revenue/cost Metric) instead of leaving the stale 3-field example — Plan Task 2 Step 6 explicitly requires the documented output to match what users see."
  - "Documented the actual CLI behavior: codegen has NO :memory: default for DuckDB; omitting both --database and DUCKDB_DATABASE raises typer.BadParameter. The plan flagged this as a verify-before-claiming item (RESEARCH.md); confirmed against src/semolina/cli/codegen.py:103."
  - "Updated the DuckDB DDL example to v0.10.2 `name AS expression` grammar (s.revenue AS SUM(s.revenue)), replacing the stale Snowflake-style `SUM(s.revenue) AS revenue`."

requirements-completed: [DKGEN-04]

# Metrics
duration: ~25min
completed: 2026-06-09
---

# Phase 41 Plan 03: Wave 2 Close-Out Summary

**Captured the file-backed-DuckDB E2E syrupy snapshot, amended the codegen how-to with `--database` path behavior (and reconciled the stale DuckDB output tab to the v0.10.2 grammar), and closed DKGEN-04 — plus fixed a pre-commit hook that was silently corrupting the snapshot on commit.**

## Accomplishments

### Task 1 — E2E snapshot (captured ahead of the formal run)
The `test_codegen_file_backed_duckdb` snapshot was captured during the upstream-unblock work and committed in `817271e`. The generated model emits the natural passthrough-fact name now that `semantic_views` v0.10.2 fixes "cycle detected in facts":

```python
from semolina import Dimension, Fact, Metric, SemanticView


class SalesView(SemanticView, view="sales_view"):
    unit_price = Fact[int]()
    country = Dimension[str]()
    region = Dimension[str]()
    revenue = Metric[int]()
    cost = Metric[int]()
```

Class name, all three field kinds (Fact / Dimension / Metric), and the `sales_view` binding match the plan's human-verify acceptance criteria.

### Task 2 — How-to amendment (`docs/src/how-to/codegen.rst`)
- New section **"Point DuckDB codegen at a database file"** between "Choose a backend" and "Understand the generated output". Covers the three `--database` path forms (absolute / relative / `~`-expanded), the `DUCKDB_DATABASE` env-var equivalent, the required-path behavior (no in-memory default — omitting both errors), and the one-time `semantic_views` community-extension install (`community.duckdb.org`, cached at `~/.duckdb/extensions/`).
- Reconciled the existing **DuckDB output tab**: replaced stale DDL grammar + the 3-field example with the v0.10.2 `name AS expression` grammar and the 5-field shape codegen actually emits against the fixture, so the doc matches the captured snapshot.
- Sphinx `-W` build passes; humanizer pass applied (no forbidden tokens in the new section).

### Task 3 — REQUIREMENTS.md DKGEN-04 close
- `[ ]` → `[x]`; wording amended from "fixture `.db` committed to the test suite" → "generated at test-collection time by a committed pytest fixture (`tests/conftest.py::duckdb_file_backed_db`)" per the CONTEXT.md no-binary-blob decision.
- Traceability row `DKGEN-04 | Phase 41 | Pending` → `Complete`.
- Footer records the amendment for audit. Diff confined to those three lines (3 insertions / 3 deletions).

## Deviations from Plan

1. **Pre-commit snapshot-corruption fix (unplanned, required).** The `trailing-whitespace` hook stripped the 2-space blank-line indents that syrupy's amber serializer writes inside multi-line snapshots, corrupting the snapshot committed in `817271e` so `test_codegen_file_backed_duckdb` failed on the next run. Fixed by excluding `*.ambr` from `trailing-whitespace` and `end-of-file-fixer` (commit `6146e99`) and restoring the snapshot to syrupy's canonical output. Without this, the snapshot would re-corrupt on every commit.
2. **Orthogonal isort fix in `test_cli.py`** (commit `17fa158`) — pre-existing import-order debt from earlier 41 plans, surfaced by `prek run --all-files`. Behavior-neutral; committed separately to keep task commits clean.

## Task Commits

- `817271e` — test(41-03): revert unit_price_fact workaround; capture E2E snapshot (Task 1)
- `6146e99` — fix: exclude syrupy .ambr snapshots from whitespace-trimming hooks (deviation 1)
- `17fa158` — style: fix import ordering in codegen test_cli.py (deviation 2)
- `f7838a5` — docs(41-03): document DuckDB file-backed codegen --database usage (Task 2)
- `cd3346d` — docs(41-03): mark DKGEN-04 complete in REQUIREMENTS (Task 3)

## Quality Gates — All Green

- `uv run pytest tests/unit/codegen/test_codegen_e2e.py -x` — passes against the captured snapshot.
- `just test` — 970 passed, 18 skipped (unit) + 16 passed, 15 skipped (jaffle-shop); 13 snapshots passed.
- `just docs-build` (Sphinx `-W`) — build succeeded, no warnings.
- `prek run --all-files` — all hooks pass, no file modifications (confirms the `.ambr` fix holds).

## Self-Check: PASSED

DKGEN-04 is the last requirement in Phase 41. With Plan 03 complete, all three plans (41-01, 41-02, 41-03) have summaries and the phase goal — `semolina codegen` against an on-disk DuckDB `.db` file — is delivered and verified end-to-end.

---
*Phase: 41-duckdb-file-backed-codegen*
*Plan: 03*
*Completed: 2026-06-09*
