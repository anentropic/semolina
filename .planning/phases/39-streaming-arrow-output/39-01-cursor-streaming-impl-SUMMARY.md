---
phase: 39
plan: 01
subsystem: cursor / arrow-streaming
tags: [streaming, pyarrow, adbc, cursor, typing]
requires:
  - SemolinaCursor (pre-existing) wrapping ADBC dbapi cursor
  - adbc_driver_manager.dbapi.Cursor.fetch_record_batch() returning pyarrow.RecordBatchReader
  - pyarrow.RecordBatch.to_pylist() Arrow→Python row conversion
provides:
  - SemolinaCursor.fetch_record_batch() -> pyarrow.RecordBatchReader (STREAM-01)
  - SemolinaCursor.__iter__/__next__ yielding Row objects lazily (STREAM-02)
  - Precise pyarrow.Table return annotation on fetch_arrow_table()
  - TYPE_CHECKING-only pyarrow import pattern (template for future modules)
affects:
  - src/semolina/cursor.py (streaming surface, typing)
  - pyproject.toml (basedpyright exemptions for pyarrow's missing stubs)
tech-stack:
  added: []
  patterns:
    - "if TYPE_CHECKING: import pyarrow + from __future__ import annotations for stubless pyarrow types"
    - "Duck-typed RecordBatchReader fakes (subclassing forbidden by pyarrow)"
    - "OSError → StopIteration normalisation for drained ADBC readers"
key-files:
  created:
    - .planning/phases/39-streaming-arrow-output/deferred-items.md
    - .planning/phases/39-streaming-arrow-output/39-01-cursor-streaming-impl-SUMMARY.md
  modified:
    - src/semolina/cursor.py
    - tests/unit/test_cursor.py
    - pyproject.toml
decisions:
  - "Normalise drained-reader OSError to StopIteration in __next__: actual ADBC behaviour deviates from the RESEARCH.md assumption (StopIteration on re-read). Catching OSError + tracking _stream_exhausted gives users 'no raise on re-iterate' semantics that Pythonic iteration expects."
  - "pyarrow ships no py.typed marker; the plan's must-have 'basedpyright strict passes without # type: ignore' is satisfied via pyproject.toml-level exemptions (reportMissingTypeStubs, reportUnknownParameterType) per CLAUDE.md's documented last-resort path. Per-line type:ignore would have been worse."
  - "Threat T-39-01 (DoS via unbounded streaming) accept-disposition retained: streaming IS the mitigation, not the attack surface."
  - "Threat T-39-04 (reader use-after-free past cursor lifetime) accept(document) retained: documented in the fetch_record_batch docstring; not enforceable without breaking the passthrough."
metrics:
  duration: "~8m"
  completed: "2026-05-14T19:58:49Z"
  tasks: 2
  files_modified: 4
---

# Phase 39 Plan 01: Cursor Streaming Implementation Summary

Shipped streaming Arrow output on `SemolinaCursor`: `fetch_record_batch()` returns a `pyarrow.RecordBatchReader` (ADBC passthrough) and `__iter__`/`__next__` yield `Row` objects lazily by pulling batches on demand. Closes STREAM-01 and STREAM-02 from the v0.5 milestone and establishes the TYPE_CHECKING-pyarrow typing pattern for the rest of the codebase.

## What Changed

### `src/semolina/cursor.py`

- Added `from typing import TYPE_CHECKING` and a `TYPE_CHECKING`-gated `import pyarrow` block.
- `fetch_arrow_table()` now annotated `-> pyarrow.Table` (was `-> Any`); docstring `Returns:` simplified now that the type is precise.
- Added `fetch_record_batch() -> pyarrow.RecordBatchReader` as a one-line passthrough to `self._cursor.fetch_record_batch()` with a docstring covering cursor-must-outlive-reader contract (arrow-adbc #1893).
- Added `__init__` state for streaming iteration: `_reader`, `_batch_rows`, `_batch_pos`, `_stream_exhausted`.
- Added `__iter__` returning `self`.
- Added `__next__` with the documented lazy state machine: lazy reader init, empty-batch skip loop, OSError→StopIteration normalisation for drained ADBC readers, no auto-close on StopIteration.

### `tests/unit/test_cursor.py`

- New module-level `_CountingReader` duck-typed fake (subclassing `pyarrow.RecordBatchReader` is forbidden by pyarrow docs).
- New `TestFetchRecordBatch` class (4 tests): `test_returns_record_batch_reader`, `test_schema_columns_match_description`, `test_empty_result`, `test_mock_cursor_raises`.
- New `TestStreamingIteration` class (8 tests): `test_iter_returns_self`, `test_yields_row_objects`, `test_multiple_batches`, `test_lazy_batch_pull`, `test_skips_empty_batches`, `test_after_fetch_arrow_table`, `test_reiteration_yields_nothing`, `test_does_not_auto_close`.

### `pyproject.toml`

- Added `reportMissingTypeStubs = false` and `reportUnknownParameterType = false` under `[tool.basedpyright]` with a comment explaining the pyarrow stub gap. These are project-wide exemptions per CLAUDE.md's "use pyproject.toml-level exemptions as last resort" allowance.

## Verification

- `pytest tests/unit/test_cursor.py` → 36 passed (24 existing + 12 new).
- `basedpyright --pythonpath … src tests` → 0 errors, 0 warnings.
- `ruff check src tests` → all clean.
- `ruff format --check src tests` → clean.
- Module-level pyarrow isolation in `cursor.py`: AST inspection confirms top-level imports are `__future__`, `typing`, `.results` only; `pyarrow` lives inside `if TYPE_CHECKING:`.

## Deviations from Plan

### Rule 1 fix — drained-reader OSError → StopIteration normalisation

**Found during:** Task 2 GREEN step verification of `test_after_fetch_arrow_table` and `test_reiteration_yields_nothing`.

**Issue:** The plan's behaviour contract (and RESEARCH.md §Pitfall 4) stated that on a drained reader, `read_next_batch()` raises `StopIteration` cleanly. In practice on DuckDB ADBC, both `cursor.fetch_record_batch()` after a prior `fetch_arrow_table()` AND `reader.read_next_batch()` after the reader has been fully consumed raise `OSError: Invalid Input Error: Attempting to execute an unsuccessful or closed pending query result`.

**Fix:** Wrapped both call sites in `try/except OSError` and converted to `StopIteration`. Added an `_stream_exhausted` flag to short-circuit further iteration attempts. This is Rule 1 (bug: code doesn't work as intended for the documented re-iterate / drain-then-iterate semantics).

**Files modified:** `src/semolina/cursor.py` (in `__next__`).
**Commit:** `cedc2e9`.

### Rule 2 fix — pyproject.toml basedpyright exemptions for pyarrow stub gap

**Found during:** Task 2 quality-gate check (`basedpyright --pythonpath …`).

**Issue:** The plan's must-have truth `"basedpyright strict passes without # type: ignore"` cannot be satisfied at the module level alone — `pyarrow` ships no `py.typed` marker, so any `pyarrow.Table` / `pyarrow.RecordBatchReader` annotation produces `reportMissingTypeStubs` + `reportUnknownParameterType` errors. The pre-existing code dodged this by typing as `Any`.

**Fix:** Added two project-level exemptions to `[tool.basedpyright]` with an explanatory comment. CLAUDE.md explicitly sanctions `pyproject.toml-level exemptions as last resort`; per-line `# type: ignore` would have been worse.

**Files modified:** `pyproject.toml`.
**Commit:** `cedc2e9`.

## Deferred Items

Logged in `.planning/phases/39-streaming-arrow-output/deferred-items.md`:

1. **Pre-existing pyarrow runtime leak via `semolina.config`** — `import semolina.cursor` triggers `semolina/__init__.py` which imports `semolina.config` which eagerly imports `pyarrow`. AST confirms `cursor.py` itself has zero runtime pyarrow imports. The package-level isolation acceptance criterion is impossible to satisfy until `config.py` is rewritten — out of scope for streaming work.
2. **Pre-existing codegen test failure** (`TestReverseCodegenOutput::test_imports_at_top`) — reproduces on the unmodified branch base; codegen-subsystem issue unrelated to STREAM-01/STREAM-02.

Both belong to Phase 40 (codegen polish) follow-up.

## Threat Model

No new surface in the threat register. The plan's STRIDE table (T-39-01 through T-39-06) is unchanged: the mitigations called out (basedpyright strict for T-39-03, context-manager `__exit__` for T-39-02) are now observably enforced by the new tests and the new annotations.

No `## Threat Flags` section: scan of changed files (`cursor.py`, `test_cursor.py`, `pyproject.toml`, `deferred-items.md`) found no new network endpoints, auth paths, file access patterns, or trust-boundary schema changes.

## Commits

| Task | Description                                                                | Commit    |
| ---- | -------------------------------------------------------------------------- | --------- |
| 1    | RED — TestFetchRecordBatch + TestStreamingIteration + `_CountingReader`    | `cd6ee3c` |
| 2    | GREEN — fetch_record_batch, __iter__/__next__, typing fix, pyproject flags | `cedc2e9` |
| —    | Docs — deferred-items.md                                                   | `d7cb703` |

## Self-Check: PASSED

- `src/semolina/cursor.py` modified: FOUND
- `tests/unit/test_cursor.py` modified: FOUND
- `pyproject.toml` modified: FOUND
- `.planning/phases/39-streaming-arrow-output/deferred-items.md` created: FOUND
- Commit `cd6ee3c`: FOUND in `git log`
- Commit `cedc2e9`: FOUND in `git log`
- Commit `d7cb703`: FOUND in `git log`
- 12 new tests collect and pass: VERIFIED (`pytest -v` output)
- basedpyright strict clean: VERIFIED (`0 errors, 0 warnings, 0 notes`)
- ruff lint+format clean: VERIFIED
