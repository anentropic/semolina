---
phase: 44-engine-owns-the-pool
plan: 04
subsystem: engines/databricks
tags: [databricks, introspection, adbc, fallback, spike, checkpoint-deferred]
requires:
  - "44-02: create_engine builds an Engine owning pool+dialect; Engine base connect()/execute()"
  - "44-03: Snowflake ADBC introspect rewrite (sibling pattern for the eventual real path)"
provides:
  - "scripts/spike_databricks_adbc_introspect.py: standalone ADBC-vs-native DESCRIBE TABLE EXTENDED AS JSON validator (operator runs later)"
  - "DatabricksEngine on the Phase 44 Engine API (create_engine/pool+dialect); execute via inherited ADBC path"
  - "DatabricksEngine.introspect(): marked NotImplementedError fallback pointing at the spike (Path B)"
affects:
  - "tests/unit/test_databricks_engine.py (rewritten onto the new API + fallback)"
  - "tests/unit/codegen/test_codegen_e2e.py (Databricks case asserts the fallback; obsolete snapshot dropped)"
tech-stack:
  added: []
  patterns:
    - "Gated spike resolved via documented FALLBACK (Path B): unvalidated path ships as NotImplementedError, not a silent stub"
    - "Standalone spike (no pytest, no pytest-adbc-replay) decouples introspection validation from the recording hang"
key-files:
  created:
    - scripts/spike_databricks_adbc_introspect.py
  modified:
    - src/semolina/engines/databricks.py
    - tests/unit/test_databricks_engine.py
    - tests/unit/codegen/test_codegen_e2e.py
    - tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
decisions:
  - "Path B (fallback) taken: the Foundry Databricks ADBC driver (adbc_driver_databricks) is absent (verified find_spec -> None) and the recording hangs, so a live spike cannot run in this environment"
  - "introspect() raises NotImplementedError with a message naming the spike script + the Foundry/recording blocker, echoing the offending view name"
  - "Removed the Plan 02 scoped pyright pragmas from databricks.py and test_databricks_engine.py — no native body remains, so no scope-disable is needed; no # type: ignore introduced"
  - "Databricks codegen e2e case converted from a rendered-model snapshot to a NotImplementedError assertion; its obsolete .ambr snapshot deleted"
metrics:
  duration: ~26min
  completed: 2026-06-24
  tasks: 3
  files: 5
---

# Phase 44 Plan 04: Databricks ADBC-Introspection Spike (Gated) Summary

Databricks metric-view introspection over ADBC ships as a clearly-marked
`NotImplementedError` fallback (Path B) plus a standalone, run-it-later validation
spike — resolving open item D3 without ever blocking the Snowflake+DuckDB critical path.

## What Was Built

- **`scripts/spike_databricks_adbc_introspect.py`** — a standalone (non-pytest, no
  pytest-adbc-replay) tool that runs `DESCRIBE TABLE EXTENDED {view} AS JSON` over both
  the engine's owned ADBC pool (`create_engine(warehouse_config("databricks"))`) and the
  native `databricks.sql` connector, normalises both single-cell JSON payloads, and asserts
  structural equality (columns, `is_measure` flags, types, comments). It **fails fast**
  (exit code 2) when the Foundry ADBC driver or credentials are absent — it never hangs on a
  cold-start connect — and never prints the access token (config built via `warehouse_config`,
  token stays a wrapped `SecretStr`; only compared column metadata is printed).
- **`DatabricksEngine`** — now constructed via the Phase 44 Engine API (`create_engine` →
  pool + dialect through the base `__init__`), with query **execution** running through the
  inherited ADBC `Engine.execute` path like Snowflake/DuckDB. The native `databricks.sql`
  introspect body is gone; `introspect()` raises a marked `NotImplementedError` naming the
  spike and the Foundry-driver/recording-hang blocker, with a `TODO(Phase 44)` pointing at
  the sibling `SnowflakeEngine.introspect` pattern for the eventual real path.
- **Tests** — `test_databricks_engine.py` rewritten onto the new API (construction, dialect
  selection, execute-over-pool, and the `NotImplementedError` fallback; the pre-Phase-44
  native `sys.modules` mocks removed). The Databricks codegen e2e case asserts the fallback
  and its obsolete snapshot was dropped.

## Checkpoint Resolution

`checkpoint: deferred (fallback shipped)`

Task 2 was a `checkpoint:human-verify` (blocking-human) to validate live Databricks ADBC
introspection. The orchestrator pre-resolved it to the documented **fallback** path, confirmed
in this environment: `python -c "import importlib.util as u; print(u.find_spec('adbc_driver_databricks'))"`
returns `None` (the Foundry-distributed driver is not on PyPI / not installed), and the
Databricks recording hangs on warehouse cold-start (pre-existing STATE blocker). A live spike
therefore cannot run here, so no human input was awaited — Path B was implemented directly.

## Deferred / Human Follow-up

**Live Databricks ADBC introspection is UNVALIDATED and currently ships as
`NotImplementedError`.** Before the real ADBC introspect path can be implemented, the operator
must, in an environment that has the Foundry Databricks ADBC driver installed and a running
SQL Warehouse with at least one metric view:

1. Install the Foundry/Columnar Databricks ADBC driver (`adbc_driver_databricks`) — not on PyPI.
2. Provide creds via `[connections.databricks]` in `.semolina.toml` or `DATABRICKS_HOST` /
   `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN`.
3. Run `python scripts/spike_databricks_adbc_introspect.py <schema.metric_view>` and confirm it
   reports the ADBC and native JSON results are structurally identical.
4. Then implement the real `DatabricksEngine.introspect()` over `self.connect()` (mirroring
   `SnowflakeEngine.introspect`, translating `adbc_driver_manager` errors) in a follow-up plan.

The pre-existing Databricks recording hang (STATE blocker) remains open and is the same
blocker that prevents `test_queries.py[databricks_engine]` cassettes from being recorded.

## Path Taken

**Path B (descope to fallback)** — chosen because the Foundry ADBC driver is absent and the
recording hangs, exactly the explicitly-approved descope the plan documents. Path A (wire the
real ADBC introspect) is intentionally deferred until the spike validates the path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migrated the Databricks codegen e2e case to the fallback**
- **Found during:** Task 3 (`just test`)
- **Issue:** `tests/unit/codegen/test_codegen_e2e.py::test_codegen_databricks_field_types`
  drove the removed native `DatabricksEngine(server_hostname=...)` constructor and the
  native introspect path, so it raised `TypeError`/`NotImplementedError` after the Task 3
  rewrite. The plan's Task 3 scope covers replacing the native-connector Databricks tests
  with fallback-appropriate ones, but this co-located e2e case was not named in `<files>`.
- **Fix:** Replaced it with `test_codegen_databricks_introspect_not_implemented` (builds via
  `create_engine(DatabricksConfig(...))`, asserts `NotImplementedError` naming the spike),
  removed the now-dead `_create_mock_databricks` helper, the unused `sys` import, and the
  stale `reportCallIssue` pragma, and deleted the obsolete `.ambr` snapshot block.
- **Files modified:** tests/unit/codegen/test_codegen_e2e.py,
  tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr
- **Commit:** 69c5990

**2. [Rule 1 - Bug] Wrapped Databricks `token` in `SecretStr` in the new tests**
- **Found during:** Task 3 (pre-commit basedpyright strict)
- **Issue:** `DatabricksConfig(token="...")` with a plain `str` literal failed basedpyright
  strict (`token: SecretStr | None`).
- **Fix:** Wrapped the test token in `pydantic.SecretStr` in both new test sites. No
  `# type: ignore`.
- **Files modified:** tests/unit/test_databricks_engine.py, tests/unit/codegen/test_codegen_e2e.py
- **Commit:** 69c5990

## Out of Scope (not fixed — by design)

The 7 `tests/integration/test_queries.py[databricks_engine]` failures (`CassetteMissError`)
are pre-existing: Databricks cassettes were never recorded because the recording hangs (STATE
blocker). They concern query **execution** replay, not introspection, and the plan explicitly
keeps them out of scope. Logged here, not fixed.

## Verification

- `pytest tests/unit/test_databricks_engine.py` — 11 passed.
- `pytest tests/unit/codegen/test_codegen_e2e.py` — 3 passed (2 snapshots, 0 unused).
- `prek run --all-files` — all hooks pass (ruff + ruff-format + basedpyright strict; no new
  `# type: ignore`).
- `just test` — 870 passed, 16 skipped; the only 7 failures are the out-of-scope
  Databricks-cassette `CassetteMissError`s (pre-existing, unrelated to this plan).
- `scripts/spike_databricks_adbc_introspect.py` parses as valid Python; references
  `DESCRIBE TABLE EXTENDED` + `AS JSON`; builds the ADBC path via `create_engine` and a native
  comparison via `databricks.sql`; handles the missing-Foundry-driver `ImportError`; imports
  neither `pytest` nor `pytest_adbc_replay`.

## Known Stubs

**1. `DatabricksEngine.introspect()` → `NotImplementedError` (intentional, tracked)**
- **File:** src/semolina/engines/databricks.py (`introspect`)
- **Reason:** Databricks ADBC introspection is unvalidated (Foundry driver absent, recording
  hangs). This is the explicitly-approved Path B descope, gated behind the live spike. A
  follow-up plan resolves it once `scripts/spike_databricks_adbc_introspect.py` validates the
  ADBC path against a live warehouse. Query execution is unaffected (inherited ADBC path).

## Self-Check: PASSED

All created/modified files exist on disk (spike script, databricks.py, the two test files,
SUMMARY.md) and both per-task commits (f67c602, 69c5990) are present in git history.
