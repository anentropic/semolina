---
phase: 39
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/semolina/cursor.py
  - tests/unit/test_cursor.py
autonomous: true
requirements:
  - STREAM-01
  - STREAM-02
requirements_addressed:
  - STREAM-01
  - STREAM-02
user_setup: []

must_haves:
  truths:
    - "Calling cursor.fetch_record_batch() on a SemolinaCursor wrapping a real ADBC cursor returns a pyarrow.RecordBatchReader."
    - "Iterating `for row in cursor:` yields Row objects whose attribute and dict access match the underlying column values."
    - "Iteration pulls batches from the underlying RecordBatchReader lazily — partial consumption pulls only the batches needed."
    - "Iteration skips empty (zero-row) batches mid-stream without terminating early."
    - "After fetch_arrow_table() or fetchall_rows() drains the underlying cursor, `for row in cursor:` yields zero rows (no raise) and re-iterating an exhausted cursor also yields zero rows."
    - "__iter__ does NOT close the cursor on exhaustion — close() is still required (explicit or via context manager)."
    - "Calling fetch_record_batch() on a SemolinaCursor wrapping a MockCursor raises AttributeError naturally (parity with fetch_arrow_table)."
    - "fetch_arrow_table()'s return type annotation is `pyarrow.Table` (not `Any`); basedpyright strict passes without `# type: ignore`."
    - "Importing `semolina.cursor` does NOT import pyarrow at runtime (TYPE_CHECKING only)."
  artifacts:
    - path: "src/semolina/cursor.py"
      provides: "fetch_record_batch() and __iter__/__next__ on SemolinaCursor; corrected fetch_arrow_table return type; TYPE_CHECKING pyarrow import"
      contains: "def fetch_record_batch"
    - path: "src/semolina/cursor.py"
      provides: "TYPE_CHECKING pyarrow import block"
      contains: "if TYPE_CHECKING:"
    - path: "tests/unit/test_cursor.py"
      provides: "TestFetchRecordBatch and TestStreamingIteration coverage including laziness, empty-batch skipping, drain-then-iterate, reiteration, no auto-close, and MockCursor parity"
      contains: "class TestStreamingIteration"
  key_links:
    - from: "src/semolina/cursor.py SemolinaCursor.fetch_record_batch"
      to: "self._cursor.fetch_record_batch"
      via: "passthrough delegation"
      pattern: "return self._cursor.fetch_record_batch"
    - from: "src/semolina/cursor.py SemolinaCursor.__next__"
      to: "pyarrow.RecordBatchReader.read_next_batch"
      via: "stored reader state on cursor"
      pattern: "read_next_batch"
    - from: "src/semolina/cursor.py SemolinaCursor.__next__"
      to: "batch.to_pylist()"
      via: "per-batch row construction"
      pattern: "to_pylist"
---

<objective>
Ship streaming Arrow output on `SemolinaCursor`: add `fetch_record_batch()` (passthrough to ADBC) and `__iter__`/`__next__` that lazily yield `Row` objects by pulling batches from the underlying `RecordBatchReader`. Fix the pre-existing `fetch_arrow_table()` return annotation (`Any` → `pyarrow.Table`) and adopt the project-wide `if TYPE_CHECKING: import pyarrow` typing pattern.

Purpose: Closes STREAM-01 and STREAM-02 from the v0.5 milestone — enables memory-bounded streaming consumption of warehouse results without full materialisation, while establishing the precise-pyarrow-typing pattern for the rest of the codebase.

Output:
- `src/semolina/cursor.py` with new methods, precise pyarrow types, and TYPE_CHECKING import.
- `tests/unit/test_cursor.py` with two new test classes (`TestFetchRecordBatch`, `TestStreamingIteration`) and a `_CountingReader` duck-typed helper proving laziness and edge-case handling.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/39-streaming-arrow-output/39-RESEARCH.md
@.planning/phases/39-streaming-arrow-output/39-VALIDATION.md
@CLAUDE.md
@src/semolina/cursor.py
@src/semolina/results.py
@tests/unit/test_cursor.py

<interfaces>
<!-- Key types and contracts the executor needs. Use these directly — no codebase exploration needed. -->

From src/semolina/cursor.py (existing — extend in place):
```python
# Header (lines 1-13)
"""DBAPI 2.0 cursor wrapper with Row convenience methods."""

from __future__ import annotations  # line 9 — annotations already deferred

from typing import Any  # line 11

from .results import Row  # line 13

class SemolinaCursor:
    def __init__(self, cursor: Any, conn: Any, pool: Any) -> None: ...
    def _column_names(self) -> list[str]: ...
    def fetchall_rows(self) -> list[Row]: ...
    def fetchone_row(self) -> Row | None: ...
    def fetchmany_rows(self, size: int = 1) -> list[Row]: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]: ...

    # cursor.py:130 — to be fixed from `-> Any` to `-> pyarrow.Table`
    def fetch_arrow_table(self) -> Any:
        return self._cursor.fetch_arrow_table()

    # Properties:
    @property
    def description(self) -> list[tuple[Any, ...]] | None: ...
    @property
    def rowcount(self) -> int: ...

    # Lifecycle:
    def close(self) -> None: ...
    def __enter__(self) -> SemolinaCursor: ...
    def __exit__(self, *exc: Any) -> None: ...
```

From src/semolina/results.py:
```python
class Row:
    def __init__(self, data: dict[str, Any]) -> None: ...
    # Supports attribute access (row.revenue), dict access (row['revenue']),
    # __len__, __contains__, __eq__, __iter__ (over field names).
```

ADBC contract (verified, RESEARCH.md §Pattern 1, §Pitfall 2, §Pitfall 4):
- `adbc_driver_manager.dbapi.Cursor.fetch_record_batch() -> pyarrow.RecordBatchReader` exists and is a one-line passthrough. Same surface for Snowflake, Databricks, DuckDB (shared `_RowIterator`).
- The reader returned shares state with `fetchone`/`fetchall`/`fetch_arrow_table` — there is one underlying stream.
- Readers may emit empty (zero-row) batches in the middle of a stream; consumers must skip them (ADBC's own `_RowIterator.fetchone()` does this at dbapi.py:1491–1500).
- `fetch_arrow_table()` calls `reader.read_all()` and drains the underlying reader.
- The reader iteration protocol is: `pa.RecordBatchReader` implements `__iter__`/`__next__` natively; `read_next_batch()` raises `StopIteration` when exhausted.

Pyarrow helpers (RESEARCH.md §Pattern 3, §Don't Hand-Roll):
- `pa.RecordBatchReader.from_batches(schema, iter_batches)` — official factory for real readers.
- `batch.to_pylist() -> list[dict[str, Any]]` — returns rows as dicts keyed by column name (handles null/timestamp/nested types correctly).
- DO NOT subclass `pa.RecordBatchReader` — pyarrow docs forbid it. Use duck typing for fakes (any object with `read_next_batch`, `__iter__`, `schema`, `close`).

Existing test patterns to mirror:
- `tests/unit/test_cursor.py:32` — `_make_cursor(fixture_data, view_name)` helper builds a SemolinaCursor over a DuckDB in-process ADBC cursor.
- `tests/unit/test_cursor.py:66` — `_make_adbc_cursor(create_sql, insert_sql, select_sql)` returns `(SemolinaCursor, conn)`; caller closes conn. Use this for tests that need explicit SQL.
- `tests/unit/test_cursor.py:339` — `TestFetchArrowTable` class pattern (uses `pytest.importorskip("pyarrow")`, try/finally to close conn).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing tests for fetch_record_batch, __iter__, and the typing fix</name>
  <files>tests/unit/test_cursor.py</files>
  <read_first>
    - tests/unit/test_cursor.py (entire file — mirror `TestFetchArrowTable` at line 339 onwards; reuse `_make_adbc_cursor` at line 66 and `_make_cursor` at line 32)
    - src/semolina/cursor.py (so the executor sees the current SemolinaCursor surface — note `fetch_arrow_table` at line 130 still returns `Any`)
    - src/semolina/results.py (Row constructor signature)
    - .planning/phases/39-streaming-arrow-output/39-RESEARCH.md (Pattern 3 _CountingReader recipe; Pitfalls 1, 2, 4; Validation Architecture per-requirement test map)
    - .planning/phases/39-streaming-arrow-output/39-VALIDATION.md (per-task verification map — list of test names is the contract)
    - CLAUDE.md (Bug fixes section — failing test before fix; Code style — 100 chars, D213, opening/closing `"""` on own lines)
  </read_first>
  <behavior>
    Test classes/methods to create (names are load-bearing — they appear in 39-VALIDATION.md):

    Class `TestFetchRecordBatch` (mirrors `TestFetchArrowTable` at test_cursor.py:339):
      - `test_returns_record_batch_reader`: `_make_adbc_cursor` → `sc.fetch_record_batch()` returns an object that is a `pyarrow.RecordBatchReader` instance (use `pytest.importorskip("pyarrow")` then `isinstance(reader, pyarrow.RecordBatchReader)`).
      - `test_schema_columns_match_description`: reader's `schema.names` matches the column names from `sc.description`.
      - `test_empty_result`: empty SELECT returns a reader that yields zero rows when fully consumed (use `list(reader)` or `reader.read_all().num_rows == 0`).
      - `test_mock_cursor_raises`: construct `SemolinaCursor(object(), object(), object())` (a plain object has no `fetch_record_batch`), call `sc.fetch_record_batch()`, expect `AttributeError`. Parity with `fetch_arrow_table`.

    Module-level helper `_CountingReader` (duck-typed; do NOT subclass `pa.RecordBatchReader`):
      - Attributes: `schema`, `batches` (iter), `read_count` (int), `closed` (bool, default False).
      - Methods: `__init__(self, schema, batches)`, `__iter__(self)` returns self, `read_next_batch(self)` increments `read_count` and returns `next(self.batches)` (raises StopIteration naturally), `__next__(self)` delegates to `read_next_batch`, `close(self)` sets `closed = True`.

    Class `TestStreamingIteration`:
      - `test_iter_returns_self`: `iter(sc) is sc`. Use a SemolinaCursor with a fake cursor providing `fetch_record_batch=lambda: _CountingReader(schema, iter([]))`.
      - `test_yields_row_objects`: ADBC DuckDB cursor with 3 rows; `rows = list(sc)`; assert len == 3, all `isinstance(r, Row)`, attribute access matches.
      - `test_multiple_batches`: use `_CountingReader` with 3 non-empty batches (2 rows each); `rows = list(sc)`; assert len == 6 and order preserved.
      - `test_lazy_batch_pull`: `_CountingReader` with 3 batches (2 rows each); take 1 row → `read_count == 1`; take a 2nd row from same batch → `read_count == 1`; take 3rd row (forces new batch) → `read_count == 2`; abandon iteration → 3rd batch never pulled.
      - `test_skips_empty_batches`: `_CountingReader` with `[empty_batch, non_empty_batch_2_rows, empty_batch, non_empty_batch_2_rows]`; assert `list(sc)` yields exactly 4 Row objects in correct order.
      - `test_after_fetch_arrow_table`: ADBC DuckDB cursor with 3 rows; `sc.fetch_arrow_table()`; then `list(sc)` returns `[]` (no raise).
      - `test_reiteration_yields_nothing`: ADBC DuckDB cursor with 3 rows; `list(sc)` returns 3 rows; second `list(sc)` returns `[]` (no raise).
      - `test_does_not_auto_close`: ADBC DuckDB cursor with 3 rows; consume fully via `list(sc)`; assert `sc._closed is False` AND `repr(sc)` does NOT contain "closed".

    For empty-batch construction:
    ```python
    schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
    empty_batch = pa.RecordBatch.from_pydict({"revenue": [], "country": []}, schema=schema)
    ```

    For SemolinaCursor with fake cursor in unit tests (no ADBC needed):
    ```python
    from types import SimpleNamespace
    fake_cursor = SimpleNamespace(fetch_record_batch=lambda: reader, description=...)
    sc = SemolinaCursor(fake_cursor, SimpleNamespace(close=lambda: None), SimpleNamespace())
    ```
  </behavior>
  <action>
    Append to `tests/unit/test_cursor.py` (after `TestFetchArrowTable` ends at line ~406):

    1. Add module-level `_CountingReader` class as specified in `<behavior>`. Place it right after `FIXTURE_DATA` (line ~96) so it's available to both test classes. Use `pytest.importorskip("pyarrow")` at the top of any test that uses it — do NOT import `pyarrow` at module top level. Build the schema and batches inside each test using a local `import pyarrow as pa` after the importorskip.

    2. Add `class TestFetchRecordBatch:` with the 4 tests listed in `<behavior>`. Mirror the `try/finally: conn.close()` pattern from `TestFetchArrowTable` (test_cursor.py:351-357) for any test that calls `_make_adbc_cursor`. For `test_mock_cursor_raises`, do NOT use ADBC — construct `SemolinaCursor(object(), object(), object())` and `pytest.raises(AttributeError)`.

    3. Add `class TestStreamingIteration:` with the 8 tests listed in `<behavior>`. For fake-reader tests, use `SimpleNamespace` for the fake cursor (`from types import SimpleNamespace` at top of file if not already present — check imports). For ADBC tests, use `_make_adbc_cursor`.

    4. Section banner comments must match existing style (see test_cursor.py:243 etc.) — `# ---...---` separators with class-name headers.

    5. RUN: `uv run pytest tests/unit/test_cursor.py::TestFetchRecordBatch tests/unit/test_cursor.py::TestStreamingIteration -x` and confirm all new tests **fail** (collection succeeds; failures are `AttributeError: 'SemolinaCursor' object has no attribute 'fetch_record_batch'` or `TypeError: 'SemolinaCursor' object is not iterable`). This is the RED step; Task 2 turns them GREEN.

    Style constraints (CLAUDE.md): line length 100, ruff isort, D213 (docstring summary on second line after `"""`), opening/closing `"""` on own lines for multi-line docstrings.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_cursor.py::TestFetchRecordBatch tests/unit/test_cursor.py::TestStreamingIteration --collect-only -q | grep -E '(test_returns_record_batch_reader|test_schema_columns_match_description|test_empty_result|test_mock_cursor_raises|test_iter_returns_self|test_yields_row_objects|test_multiple_batches|test_lazy_batch_pull|test_skips_empty_batches|test_after_fetch_arrow_table|test_reiteration_yields_nothing|test_does_not_auto_close)' | wc -l | grep -q 12</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "class TestFetchRecordBatch" tests/unit/test_cursor.py` returns 1
    - `grep -c "class TestStreamingIteration" tests/unit/test_cursor.py` returns 1
    - `grep -c "class _CountingReader" tests/unit/test_cursor.py` returns 1
    - All 12 test method names from `<behavior>` exist: `grep -cE "def test_(returns_record_batch_reader|schema_columns_match_description|empty_result|mock_cursor_raises|iter_returns_self|yields_row_objects|multiple_batches|lazy_batch_pull|skips_empty_batches|after_fetch_arrow_table|reiteration_yields_nothing|does_not_auto_close)" tests/unit/test_cursor.py` returns 12
    - `uv run pytest tests/unit/test_cursor.py::TestFetchRecordBatch tests/unit/test_cursor.py::TestStreamingIteration -x` FAILS (this is RED — exit code != 0 because the implementation doesn't exist yet)
    - The existing 7 test classes in test_cursor.py still collect and pass: `uv run pytest tests/unit/test_cursor.py --ignore-glob='*TestFetchRecordBatch*' -k 'not TestFetchRecordBatch and not TestStreamingIteration' -x` exits 0
  </acceptance_criteria>
  <done>
    Two new test classes (`TestFetchRecordBatch`, `TestStreamingIteration`) and one helper (`_CountingReader`) exist in `tests/unit/test_cursor.py`. The 12 new tests collect successfully, run, and fail with the expected error (no `fetch_record_batch` / not iterable). Existing tests still pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement fetch_record_batch, __iter__/__next__, and fix fetch_arrow_table typing</name>
  <files>src/semolina/cursor.py</files>
  <read_first>
    - src/semolina/cursor.py (entire file — modifying in place)
    - src/semolina/results.py (Row constructor)
    - tests/unit/test_cursor.py (the tests Task 1 added — these are the GREEN target)
    - .planning/phases/39-streaming-arrow-output/39-RESEARCH.md (Pattern 1 TYPE_CHECKING import; Pattern 2 state-machine flavour; Pitfall 1 cursor lifetime contract for docstring; Pitfall 2 empty-batch skip loop; Pitfall 4 drained-reader semantics)
    - CLAUDE.md (typing rule: no `Any` returns when precise type exists; no `# type: ignore`; D213; docstring `.. code-block:: python` RST directive — NOT markdown fences)
  </read_first>
  <behavior>
    All 12 tests in `TestFetchRecordBatch` and `TestStreamingIteration` (added by Task 1) must pass. Specifically:
    - `sc.fetch_record_batch()` returns the underlying cursor's `fetch_record_batch()` result unchanged (one-line passthrough).
    - `iter(sc) is sc` (identity).
    - `next(sc)` returns a `Row` constructed from one row of the current batch; advances internal cursor; pulls the next non-empty batch when current batch is drained.
    - `next(sc)` skips zero-row batches (mirrors ADBC `_RowIterator.fetchone()` pattern at dbapi.py:1491-1500).
    - `next(sc)` raises `StopIteration` when the underlying reader is exhausted AND the current batch is fully consumed.
    - StopIteration does NOT close the cursor (`self._closed` stays `False`).
    - After `fetch_arrow_table()` drains the reader, iteration yields nothing (the reader is exhausted; `read_next_batch` raises StopIteration immediately on first `__next__`).
    - Re-iterating a fully-consumed cursor yields nothing (same reason).
    - `fetch_arrow_table()` is annotated `-> pyarrow.Table` (not `-> Any`).
    - Importing `semolina.cursor` does NOT import `pyarrow` at runtime.
  </behavior>
  <action>
    Edit `src/semolina/cursor.py` (CURRENT file is 208 lines):

    **Step A — typing imports (top of file):**
    1. After line 11 (`from typing import Any`), change to `from typing import TYPE_CHECKING, Any`.
    2. Add a TYPE_CHECKING block immediately after the typing import (before `from .results import Row` at line 13):
       ```python
       if TYPE_CHECKING:
           import pyarrow
       ```
    Result: `from __future__ import annotations` at line 9 + `if TYPE_CHECKING: import pyarrow` makes `pyarrow.Table` and `pyarrow.RecordBatchReader` valid forward-reference annotations with zero runtime cost.

    **Step B — fix fetch_arrow_table return type (line 130):**
    Change `def fetch_arrow_table(self) -> Any:` to `def fetch_arrow_table(self) -> pyarrow.Table:`. Update the docstring `Returns:` section to remove the "typed as ``Any`` because pyarrow does not ship type stubs" caveat (now obsolete) — replace with `"""``pyarrow.Table`` with the query results."""`. Body unchanged.

    **Step C — add fetch_record_batch immediately after fetch_arrow_table (insert after line 156, before the `# -- DBAPI 2.0 passthrough properties --` comment at line 158):**
    ```python
    def fetch_record_batch(self) -> pyarrow.RecordBatchReader:
        """
        Fetch the result as a PyArrow ``RecordBatchReader`` (ADBC passthrough).

        Delegates to the underlying ADBC cursor's ``fetch_record_batch()``
        method for lazy, memory-bounded streaming consumption of Arrow data.

        Requires an ADBC-capable cursor (Snowflake, Databricks, or DuckDB
        pool connections). Not supported on MockCursor.

        The returned reader shares state with this cursor's other fetch
        methods — consume the reader before calling ``fetchone()``,
        ``fetch_arrow_table()``, or iterating the cursor.

        The cursor must outlive the reader: consume the reader inside the
        context manager (or before ``.close()``). See arrow-adbc issue #1893.

        Returns:
            ``pyarrow.RecordBatchReader`` over the query result.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_record_batch()`` (e.g. MockCursor).

        Example:
            .. code-block:: python

                with Sales.query().metrics(Sales.revenue).execute() as cursor:
                    reader = cursor.fetch_record_batch()
                    for batch in reader:
                        process(batch)
        """
        return self._cursor.fetch_record_batch()
    ```

    **Step D — add streaming iterator state to `__init__` (line 27-44):**
    After `self._closed = False` (line 44), add:
    ```python
    self._reader: pyarrow.RecordBatchReader | None = None
    self._batch_rows: list[dict[str, Any]] = []
    self._batch_pos = 0
    ```

    **Step E — add `__iter__` and `__next__` (insert as a new section before `# -- Lifecycle --` at line 180):**
    ```python
    # -- Iteration --

    def __iter__(self) -> SemolinaCursor:
        """
        Return self — SemolinaCursor is its own iterator.

        Single-pass: the cursor's underlying ADBC stream is consumed once.
        Re-iterating an exhausted cursor yields zero rows (matches DBAPI
        ``fetchone() -> None`` semantics on a drained cursor). Iteration
        does NOT auto-close the cursor — call ``close()`` or use the
        context manager.

        Returns:
            ``self`` for use in ``for row in cursor:`` syntax.
        """
        return self

    def __next__(self) -> Row:
        """
        Return the next row from the underlying RecordBatchReader.

        Lazily pulls batches one at a time from the underlying reader,
        yielding ``Row`` objects from the current batch. Zero-row batches
        are skipped (mirrors ADBC's own ``_RowIterator.fetchone()``).

        Raises:
            StopIteration: When the underlying reader is exhausted and the
                current batch is fully consumed. Does NOT close the cursor.

        Returns:
            ``Row`` constructed from the next batch row, keyed by the batch
            schema's column names.
        """
        if self._reader is None:
            self._reader = self._cursor.fetch_record_batch()
        while self._batch_pos >= len(self._batch_rows):
            batch = self._reader.read_next_batch()  # raises StopIteration when done
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row
    ```

    **Notes:**
    - `batch.to_pylist()` returns `list[dict[str, Any]]` keyed by column name (RESEARCH.md §Don't Hand-Roll). This satisfies D-04 (column names from batch schema, not `cursor.description`).
    - The `while` loop around `read_next_batch()` handles the empty-batch skip case (Pitfall 2) AND propagates StopIteration naturally when the reader exhausts (Pitfall 4 — after `fetch_arrow_table` drains the reader, the very first `read_next_batch` raises StopIteration, so iteration yields nothing).
    - Per CLAUDE.md "Bug fixes": the typing fix on `fetch_arrow_table` has no observable runtime test (only basedpyright). It's a typing refactor wrapped into this feature — the RED-then-GREEN discipline is satisfied by Task 1's failing tests for the new methods. Verify the typing fix via `prek run --all-files` in the acceptance criteria.

    Style constraints: line length 100, opening/closing `"""` on own lines for multi-line docstrings, D213 (summary on second line), `.. code-block:: python` RST directive (NOT markdown fences).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/test_cursor.py::TestFetchRecordBatch tests/unit/test_cursor.py::TestStreamingIteration -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -E "if TYPE_CHECKING:" src/semolina/cursor.py` matches (TYPE_CHECKING block present)
    - `grep -E "^    import pyarrow$" src/semolina/cursor.py` matches (pyarrow imported under TYPE_CHECKING — leading 4-space indent confirms it's inside the `if TYPE_CHECKING:` block)
    - `grep -E "def fetch_arrow_table\(self\) -> pyarrow\.Table:" src/semolina/cursor.py` matches (Any → pyarrow.Table)
    - `! grep "def fetch_arrow_table(self) -> Any" src/semolina/cursor.py` (old signature gone)
    - `grep -E "def fetch_record_batch\(self\) -> pyarrow\.RecordBatchReader:" src/semolina/cursor.py` matches
    - `grep -E "def __iter__\(self\) -> SemolinaCursor:" src/semolina/cursor.py` matches
    - `grep -E "def __next__\(self\) -> Row:" src/semolina/cursor.py` matches
    - `grep -E "self\._cursor\.fetch_record_batch\(\)" src/semolina/cursor.py | wc -l` returns 2 (one in `fetch_record_batch`, one in `__next__`)
    - `grep -E "\.to_pylist\(\)" src/semolina/cursor.py` matches (Row construction uses to_pylist)
    - No `# type: ignore` introduced: `! grep "# type: ignore" src/semolina/cursor.py`
    - Runtime pyarrow isolation: `uv run python -c "import sys; import semolina.cursor; assert 'pyarrow' not in sys.modules, 'pyarrow leaked into runtime'"` exits 0
    - All 12 new tests pass: `uv run pytest tests/unit/test_cursor.py::TestFetchRecordBatch tests/unit/test_cursor.py::TestStreamingIteration -x` exits 0
    - Full unit cursor suite passes: `uv run pytest tests/unit/test_cursor.py -x` exits 0
    - Quality gate clean (basedpyright strict + ruff): `uv run prek run --all-files` exits 0
  </acceptance_criteria>
  <done>
    `SemolinaCursor` exposes `fetch_record_batch() -> pyarrow.RecordBatchReader` and is iterable via `__iter__`/`__next__` yielding `Row` objects. `fetch_arrow_table()` returns `pyarrow.Table` (not `Any`). `pyarrow` is imported under `TYPE_CHECKING` only. All 12 new tests in `tests/unit/test_cursor.py` pass, the existing cursor test suite still passes, and `prek run --all-files` is clean.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User code → SemolinaCursor | User-supplied SQL is already executed before `fetch_record_batch()` / iteration; the streaming surface only consumes results. No new untrusted input crosses here. |
| SemolinaCursor → underlying ADBC cursor | Pure passthrough; no parsing, no string interpolation, no new control flow on user data. |
| pyarrow RecordBatchReader → Row construction | `batch.to_pylist()` performs the Arrow→Python conversion; trusted because pyarrow handles null/timestamp/nested types per its documented contract. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-39-01 | Denial of Service | `SemolinaCursor.__next__` over an unbounded result set | accept | Streaming is the mitigation, not the threat — bounded memory is the entire point of this phase. ADBC enforces driver-level prefetch limits (Snowflake: 200 batches queued, 10 concurrent streams per RESEARCH.md §Security Domain). User-controllable knobs deferred to STREAM-04. |
| T-39-02 | Denial of Service | Cursor/connection resource leak if exception raised during iteration | mitigate | Existing context-manager `__exit__` (cursor.py:192-194) calls `close()` which releases both cursor and connection. `__next__` allocates no new OS resources beyond the reader (already owned by the underlying cursor). Verified by `test_does_not_auto_close` and existing `test_context_manager_closes_on_exit`. |
| T-39-03 | Tampering | Type confusion via wrong-type annotation (`Any` → user assumes `RecordBatchReader` but gets None) | mitigate | Exact return types (`pyarrow.Table`, `pyarrow.RecordBatchReader`) are now declared and enforced by basedpyright strict (`prek run --all-files`). No `# type: ignore` is permitted (CLAUDE.md). |
| T-39-04 | Information Disclosure | Reader leaks past cursor lifetime (use-after-free on closed ADBC connection) | accept (document) | Architectural contract from arrow-adbc issue #1893 — cursor MUST outlive the reader. Phase 39 documents this in the `fetch_record_batch` docstring example (consume inside `with` block). Not enforceable in Semolina without breaking the passthrough; Phase 40 how-to will spell it out further. |
| T-39-05 | Repudiation | n/a — no logging/audit trail surface added | accept | No new auditable actions. |
| T-39-06 | Elevation of Privilege | n/a — no auth/authz surface added | accept | Pool registration handles credentials; streaming touches no privilege boundary. |
</threat_model>

<verification>
After both tasks complete:

1. `uv run pytest tests/unit/test_cursor.py -x` — all cursor unit tests pass (new + existing).
2. `uv run prek run --all-files` — ruff format/lint clean; basedpyright strict clean on `cursor.py` with the new `pyarrow.Table`/`pyarrow.RecordBatchReader` annotations and no `# type: ignore`.
3. `uv run python -c "import sys; import semolina.cursor; assert 'pyarrow' not in sys.modules"` — confirms TYPE_CHECKING isolation (no runtime pyarrow import).
4. `just test` — full unit + jaffle-shop suite green (no regressions in adjacent modules).
</verification>

<success_criteria>
- All 12 new tests in `tests/unit/test_cursor.py` pass.
- All pre-existing tests in `tests/unit/test_cursor.py` still pass (no regressions to the 7 existing test classes).
- `src/semolina/cursor.py` exposes `fetch_record_batch() -> pyarrow.RecordBatchReader` and is iterable, with `fetch_arrow_table()` correctly typed `-> pyarrow.Table`.
- `prek run --all-files` exits 0 (ruff + basedpyright strict).
- `pyarrow` is NOT imported at runtime when `semolina.cursor` is imported (TYPE_CHECKING isolation verified).
- STREAM-01 and STREAM-02 are now observably satisfied at the unit-test level (cross-backend integration coverage lands in Plan 02).
</success_criteria>

<output>
After completion, create `.planning/phases/39-streaming-arrow-output/39-01-SUMMARY.md` recording: files modified, test classes added, the typing pattern adopted (`if TYPE_CHECKING: import pyarrow` + `from __future__ import annotations`), and the deliberate accept-disposition on T-39-01/T-39-04.
</output>
