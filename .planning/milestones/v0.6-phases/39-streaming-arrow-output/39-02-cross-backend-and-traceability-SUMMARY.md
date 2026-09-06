---
phase: 39
plan: 02
subsystem: integration-tests / requirements-traceability
tags: [integration-tests, traceability, streaming, adbc, gating]
requires:
  - SemolinaCursor.__iter__ / __next__ (shipped in Plan 01)
  - SemolinaCursor.fetch_record_batch (shipped in Plan 01)
  - tests/integration/conftest.py backend_engine parametrized fixture
  - syrupy snapshot framework + snapshot-update toggle
provides:
  - tests/integration/test_queries.py::test_streaming_iteration — cross-backend smoke for `for row in cursor:`
  - REQUIREMENTS.md Traceability rows for STREAM-01 / STREAM-02 marked Complete
  - SC-4 parity audit: REQUIREMENTS.md text and shipped cursor surface verified in lock-step
affects:
  - tests/integration/test_queries.py (one new test function)
  - .planning/REQUIREMENTS.md (two traceability rows + footer timestamp)
tech-stack:
  added: []
  patterns:
    - "hasattr(backend_engine, '_connection_params') as the dependency-free 'is this a real ADBC engine?' probe in integration tests"
    - "Close-time traceability updates (avoid the v0.4.0 archive-time documentation drift)"
key-files:
  created:
    - .planning/phases/39-streaming-arrow-output/39-02-cross-backend-and-traceability-SUMMARY.md
  modified:
    - tests/integration/test_queries.py
    - .planning/REQUIREMENTS.md
decisions:
  - "Skip-gate uses hasattr(_connection_params) rather than injecting the request fixture: the attribute is a stable marker only the real SnowflakeEngine / DatabricksEngine carry (used in conftest teardown), so the check is local to the test and adds no fixture dependency. D-07 option (a) realised."
  - "Both Pending rows updated to Complete in a single docs commit (no per-row split) — the parity audit is the gate, not the table edit itself."
  - "Footer timestamp updated to record the close-time update so future audits can see the v0.4.0 lesson was applied here (refresh traceability as phases land, not at archive time)."
metrics:
  duration: "~3m"
  completed: "2026-05-14T20:05:03Z"
  tasks: 2
  files_modified: 2
---

# Phase 39 Plan 02: Cross-Backend & Traceability Summary

Closed out Phase 39 by adding a cross-backend integration smoke test that exercises `for row in cursor:` end-to-end against real Snowflake and Databricks engines (record mode) while skipping cleanly in CI/replay, and by marking STREAM-01 and STREAM-02 Complete in REQUIREMENTS.md after auditing the shipped method names against the requirement text. SC-3, SC-4, and SC-5 for Phase 39 are observably satisfied.

## What Changed

### `tests/integration/test_queries.py`

- Added `import pytest` to enable `pytest.skip(...)` in the new test.
- Added `test_streaming_iteration(backend_engine, snapshot)`:
  - Parametrized over `backend_engine` (snowflake_engine + databricks_engine variants).
  - In replay mode (`MockEngine`), the test skips via `hasattr(backend_engine, "_connection_params")` — `MockEngine` does not carry that attribute, only the real `SnowflakeEngine` / `DatabricksEngine` do (the conftest uses it for teardown at line 217 / 326).
  - In record mode (`--snapshot-update`), exercises `Sales.query().using("test").metrics(Sales.revenue).dimensions(Sales.country).order_by(Sales.country).execute()` → `[dict(row.items()) for row in cursor]`, which drives the full pool → connection → SemolinaCursor → `__iter__` → ADBC RecordBatchReader chain.

### `.planning/REQUIREMENTS.md`

- Traceability table rows for `STREAM-01` and `STREAM-02` flipped from `Pending` to `Complete`. Other phase rows (STREAM-03, DKGEN-04, DKGEN-05, AUDIT-01) remain `Pending` — still 4 Pending in total.
- Footer timestamp updated to `*Last updated: 2026-05-14 — STREAM-01 and STREAM-02 marked Complete at Phase 39 close*`.
- Coverage block untouched: v0.5 still has 6 requirements, 6 mapped, 0 unmapped.

## Parity Audit (SC-4)

Manual cross-check of the shipped surface vs. requirement text:

| Requirement | Wording in REQUIREMENTS.md | Shipped surface in `src/semolina/cursor.py` | Result |
| ----------- | -------------------------- | ------------------------------------------- | ------ |
| STREAM-01   | `cursor.fetch_record_batch()` returning `pyarrow.RecordBatchReader` | `SemolinaCursor.fetch_record_batch() -> pyarrow.RecordBatchReader` at line 164 | Match |
| STREAM-02   | `for row in cursor:` yielding `Row` objects | `SemolinaCursor.__iter__` / `__next__` returning `Row` at lines 222 / 237 | Match |

No requirement text needed amending. The v0.4.0 `to_arrow()` → `fetch_arrow_table()` drift class is not reproduced here.

## Verification

Ran per the plan's `<verification>` section:

1. `pytest tests/integration/test_queries.py::test_streaming_iteration -v` → `2 skipped, 2 warnings in 0.01s` (both `[snowflake_engine]` and `[databricks_engine]` variants SKIP cleanly in CI/replay).
2. Full suite (with the pre-existing codegen failure from 39-01's deferred-items.md deselected): `947 passed, 2 skipped, 1 deselected` — no regressions from the test addition or REQUIREMENTS edits.
3. `ruff check tests/integration/test_queries.py` — clean.
4. `ruff format --check tests/integration/test_queries.py` — clean.
5. `basedpyright tests/integration/test_queries.py` — clean (0 errors, 0 warnings) under the venv pythonpath.
6. Acceptance greps:
   - `grep -cE 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Complete' .planning/REQUIREMENTS.md` → `2`.
   - `grep -cE 'STREAM-0[12]\s*\|\s*Phase 39\s*\|\s*Pending' .planning/REQUIREMENTS.md` → `0`.
   - `grep -c 'Pending' .planning/REQUIREMENTS.md` → `4` (STREAM-03, DKGEN-04, DKGEN-05, AUDIT-01).
   - `grep -E 'STREAM-01 and STREAM-02 marked Complete' .planning/REQUIREMENTS.md` matches.
   - `grep "fetch_record_batch" src/semolina/cursor.py` AND `grep "fetch_record_batch" .planning/REQUIREMENTS.md` both match.

The pre-existing codegen import-order failure (`tests/unit/codegen/test_cli.py::TestReverseCodegenOutput::test_imports_at_top`) is unrelated to streaming work and is already documented in `.planning/phases/39-streaming-arrow-output/deferred-items.md` for Phase 40 follow-up.

## Deviations from Plan

None. The plan executed exactly as written. Both tasks landed without auto-fixes; the parity audit passed on the first read.

## Threat Model

The plan's STRIDE register (T-39-07 through T-39-09) is realised as designed:

- **T-39-07 (documentation drift)** — Mitigated by the explicit parity audit before flipping rows to `Complete`. Acceptance greps cross-check `fetch_record_batch` in both `src/semolina/cursor.py` and `.planning/REQUIREMENTS.md`.
- **T-39-08 (CI runs without credentials)** — Mitigated by the `hasattr(_connection_params)` skip gate. Verified: both variants show `SKIPPED` in `-v` output, exit code 0.
- **T-39-09 (snapshot data exposure)** — Accepted: the `Sales` fixture data is synthetic (defined in conftest `TEST_DATA`); no customer data ever touches the snapshot.

No `## Threat Flags` section: scan of changed files (`tests/integration/test_queries.py`, `.planning/REQUIREMENTS.md`) found no new network endpoints, auth paths, file access patterns, or trust-boundary schema changes.

## Commits

| Task | Description                                                          | Commit    |
| ---- | -------------------------------------------------------------------- | --------- |
| 1    | test_streaming_iteration cross-backend integration test              | `ce0ffba` |
| 2    | STREAM-01 / STREAM-02 marked Complete + footer timestamp + parity OK | `0aacb6b` |

## Self-Check: PASSED

- `tests/integration/test_queries.py` modified: FOUND
- `.planning/REQUIREMENTS.md` modified: FOUND
- `.planning/phases/39-streaming-arrow-output/39-02-cross-backend-and-traceability-SUMMARY.md` created: FOUND
- Commit `ce0ffba`: FOUND in `git log`
- Commit `0aacb6b`: FOUND in `git log`
- `test_streaming_iteration` collects (2 variants) and skips cleanly in replay mode: VERIFIED
- Parity audit passes (`fetch_record_batch` in both source and requirements): VERIFIED
- Traceability has exactly 2 `STREAM-0[12].*Complete` rows and 0 `STREAM-0[12].*Pending` rows: VERIFIED
