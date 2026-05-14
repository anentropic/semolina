---
phase: 39
slug: streaming-arrow-output
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 (basedpyright strict) |
| **Config file** | `pyproject.toml` (`[tool.basedpyright]`, `[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_cursor.py -x` |
| **Full suite command** | `just test` (unit + jaffle-shop mocks) |
| **Estimated runtime** | ~30 s quick / ~2 min full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_cursor.py -x`
- **After every plan wave:** Run `just test` AND `uv run prek run --all-files`
- **Before `/gsd-verify-work`:** Full suite green; basedpyright strict clean on `cursor.py`
- **Max feedback latency:** 30 s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | STREAM-01 | — | N/A | unit (fake reader) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-01 | — | N/A | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_returns_record_batch_reader -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-01 | — | N/A | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_schema_columns_match_description -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-01 | — | N/A | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_empty_result -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-01 | — | MockCursor parity | unit | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_mock_cursor_raises -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | N/A | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_yields_row_objects -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | N/A | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_multiple_batches -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | Lazy batch pull | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_lazy_batch_pull -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | Single-pass cursor | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_after_fetch_arrow_table -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | Single-pass cursor | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_reiteration_yields_nothing -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | Skip empty batches | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_skips_empty_batches -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | No auto-close | unit (ADBC DuckDB) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_does_not_auto_close -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | STREAM-02 | — | `__iter__` returns self | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_iter_returns_self -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | Typing fix | — | Exact return type | static | `uv run prek run --all-files` (basedpyright strict) | exists | ⬜ pending |
| TBD | TBD | 0 | SC-3 cross-backend | — | ADBC passthrough | integration (parametrized) | `pytest tests/integration/test_queries.py::test_streaming_iteration -x` (gated `--snapshot-update`) | ❌ W0 | ⬜ pending |
| TBD | TBD | 0 | SC-5 traceability | — | Doc parity | manual / grep | `grep -E 'STREAM-0[12].*Complete' .planning/REQUIREMENTS.md` | exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · Task IDs filled in when plans land.*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_cursor.py` — add `TestFetchRecordBatch` and `TestStreamingIteration` test classes (mirror `TestFetchArrowTable` pattern at `tests/unit/test_cursor.py:339`)
- [ ] `tests/unit/test_cursor.py` — add `_CountingReader` duck-typed helper for laziness assertions (no new file)
- [ ] `tests/integration/test_queries.py` — extend with `test_streaming_iteration` parametrized over `backend_engine`, gated behind `--snapshot-update` for Snowflake/Databricks (DuckDB ADBC always runs)
- [ ] Framework install: not needed — pytest already in dev group

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| REQUIREMENTS.md traceability table updated | SC-5 | Documentation update, not code | `grep -E 'STREAM-0[12]\s*\|.*\|\s*Complete' .planning/REQUIREMENTS.md` (both rows must match) |
| Shipped method names match requirement text | SC-4 | Cross-doc audit | Compare `STREAM-01`/`STREAM-02` text in REQUIREMENTS.md against signatures in `src/semolina/cursor.py` |

---

## Validation Dimensions

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Static typing | basedpyright strict via prek | Verifies `pyarrow.Table` / `pyarrow.RecordBatchReader` annotations resolve without `# type: ignore` |
| Unit (real ADBC, DuckDB in-process) | `TestFetchRecordBatch`, `TestStreamingIteration` (ADBC) | Fast (<1 s each); exercises real ADBC → pyarrow flow |
| Unit (fake reader, instrumented) | `_CountingReader` + laziness/empty-batch tests | Proves laziness and edge cases independent of ADBC batch sizing |
| Property (empty result, single row, multi-batch) | Parameterized tests in both test classes | Mirrors `TestFetchArrowTable` shape (`tests/unit/test_cursor.py:339`) |
| Integration (cross-backend) | `tests/integration/test_queries.py` parametrized via `backend_engine`, gated `--snapshot-update` for Snowflake/Databricks | CI has no warehouse credentials; record-mode validates SC-3 |
| Lifecycle | `test_does_not_auto_close`, context-manager round-trip | Confirms user-locked decision that `__iter__` does NOT close on exhaustion |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
