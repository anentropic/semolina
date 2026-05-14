# Phase 39: Streaming Arrow Output - Research

**Researched:** 2026-05-14
**Domain:** ADBC streaming, pyarrow.RecordBatchReader, DBAPI cursor iteration, basedpyright-strict typing
**Confidence:** HIGH

## Summary

Phase 39 ships two narrow additions to `SemolinaCursor` — `fetch_record_batch()` returning a `pyarrow.RecordBatchReader`, and `__iter__`/`__next__` that lazily yield `Row` objects by pulling batches from the same underlying ADBC reader. Both are passthroughs onto the result that already powers `fetch_arrow_table()`; there is no new buffering layer to build.

The interesting work is in three places that the planner needs to get right: (1) understanding that ADBC's `fetch_record_batch()` returns a **live handle on the same reader the DBAPI fetch methods consume from** (not a fresh stream) — so shared-state semantics fall out of one source of truth and need explicit testing; (2) introducing the project-wide typing pattern of `if TYPE_CHECKING: import pyarrow` with **exact return types** (`pyarrow.Table`, `pyarrow.RecordBatchReader`) — replacing the existing `-> Any` on `fetch_arrow_table()`; and (3) proving laziness with a fake `RecordBatchReader` built via `pa.RecordBatchReader.from_batches()` over a counting generator, asserting partial-batch consumption.

Cross-backend correctness is essentially free — ADBC normalises this surface across DuckDB, Snowflake, and Databricks, with the same `_RowIterator` implementation feeding all three. Backend differences are limited to prefetch tuning knobs (Snowflake) that are out of scope for v0.5.

**Primary recommendation:** Implement `fetch_record_batch()` as a one-line delegation, build `__iter__`/`__next__` over the column-zip pattern from `fetchall_rows()` (cursor.py:60–69) driven by an internal lazy batch iterator initialised on first `__next__`. Use `pa.RecordBatchReader.from_batches()` for the laziness fake test. Adopt `if TYPE_CHECKING: import pyarrow` everywhere pyarrow types appear in signatures.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Typing rule (CRITICAL — applies project-wide):**
   - Never type as `Any` if a more precise type is possible.
   - **Return types: exact** — even when upstream library has no stubs (e.g. pyarrow), use the real type with `if TYPE_CHECKING: import ...`.
   - **Argument types: lenient** — duck-typing friendly via protocols/unions/supertypes.
   - Phase 39 MUST also FIX the existing `fetch_arrow_table()` return type from `Any` to `pyarrow.Table`. The phase is the right moment to correct this because the new `fetch_record_batch()` signature establishes the pyarrow typing pattern.

2. **Iterator semantics:**
   - `SemolinaCursor.__iter__` returns `self`; `__next__` defined. Single-pass — re-iterating a consumed cursor is allowed but just yields nothing (standard StopIteration semantics, matches DBAPI `fetchone() -> None` after exhaustion).
   - **Do NOT auto-close on exhaustion** — close stays with the context manager / explicit `.close()`.
   - After `fetch_arrow_table()` or `fetchall_rows()`, iterating the cursor yields zero rows (underlying ADBC cursor is drained). No raise.

3. **Row construction during iteration:**
   - Pull batches from the `RecordBatchReader` lazily (outer loop), then per-batch row construction (inner loop) — mirror the column-zip pattern from `fetchall_rows()` at `cursor.py:60`. Column names should come from the batch schema (self-contained) — not from `cursor.description` (which is set at execute() time).

4. **Passthrough scope (in scope):**
   - `SemolinaCursor.fetch_record_batch() -> pyarrow.RecordBatchReader` — thin delegation, no buffering.
   - `SemolinaCursor.__iter__` / `__next__` yielding `Row` objects.
   - Fix `fetch_arrow_table()` typing (return `pyarrow.Table`, not `Any`).
   - Cross-backend integration smoke tests (Snowflake, Databricks, DuckDB).
   - Laziness assertion via instrumented fake `RecordBatchReader` (counts `read_next_batch` calls).
   - REQUIREMENTS.md traceability update for STREAM-01/02 → Complete.

### Claude's Discretion

- Internal helper structure (e.g. whether `__next__` uses a stored `RecordBatchReader` + per-batch row buffer, or a generator-based implementation).
- Exact test file names within `tests/unit/test_cursor.py` (new `TestStreamingIteration`, `TestFetchRecordBatch` classes — pattern established by existing `TestFetchArrowTable`).
- Whether to introduce an internal `_BatchRowIterator` helper class or inline the state machine on `SemolinaCursor`.

### Deferred Ideas (OUT OF SCOPE)

- Docs / how-to guide (Phase 40 handles this — STREAM-03).
- Async iteration (`__aiter__`).
- Backpressure / batch-size knobs (STREAM-04, deferred to future milestone).
- Pandas/Polars streaming adapters.
- MockCursor streaming support — `fetch_record_batch()` and `__iter__` should raise `AttributeError` on MockCursor exactly the way `fetch_arrow_table()` does today.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-01 | User can call `cursor.fetch_record_batch()` on `SemolinaCursor` to receive a `pyarrow.RecordBatchReader`, mirroring the same-named method on `adbc_driver_manager` cursors | Verified: ADBC `dbapi.Cursor.fetch_record_batch() -> pyarrow.RecordBatchReader` exists and is a one-line passthrough (returns `self._results.reader._reader`). Identical surface across DuckDB / Snowflake / Databricks ADBC drivers via shared `_RowIterator`. Implementation is one `return self._cursor.fetch_record_batch()` plus the new typing pattern. |
| STREAM-02 | User can iterate `for row in cursor:` on `SemolinaCursor` to receive `Row` objects via lazy nested iteration over the underlying `RecordBatchReader`, without full materialisation | Verified pattern: iterate `for batch in reader:` (RecordBatchReader implements `__iter__`/`__next__` natively, raises StopIteration at end of stream), then `for row_dict in batch.to_pylist():` yields per-row dicts keyed by column name. Laziness is provable by wrapping a counting generator inside `pa.RecordBatchReader.from_batches()` and asserting `read_next_batch` call count after partial consumption. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Source | Compliance |
|-----------|--------|------------|
| `prek run --all-files` must pass (ruff + basedpyright strict + shellcheck) | CLAUDE.md "Quality gates" | All new code must satisfy basedpyright strict — directly informs the `if TYPE_CHECKING: import pyarrow` pattern below. |
| `just test` must pass (unit + jaffle-shop) | CLAUDE.md "Quality gates" | New tests land in `tests/unit/test_cursor.py`; integration smoke tests may extend `tests/integration/test_queries.py` (uses `backend_engine` parametrized fixture). |
| Avoid `# type: ignore` in code; prefer solving the typing issue | CLAUDE.md "Quality gates" | `if TYPE_CHECKING` import of pyarrow is the canonical fix; no `# type: ignore` needed on the runtime delegation since the body just calls `self._cursor.fetch_record_batch()`. The forward-string return annotation does the work. |
| Line length 100 chars, ruff isort, D213 enforced | CLAUDE.md "Code style" | Docstrings: opening `"""` then summary on second line. Multi-line `"""` opens and closes on own lines. |
| Google-style docstrings with `.. code-block:: python` RST directive (NOT markdown fences) | CLAUDE.md "Docstring examples" | New methods get `Example:` blocks using `.. code-block:: python`, mirroring existing `fetch_arrow_table()` docstring at `cursor.py:149`. |
| Bug fix discipline: failing test first, then fix | CLAUDE.md "Bug fixes" | The `fetch_arrow_table()` `-> Any` correction is a typing bug — but it has no observable runtime failing test. Treat as a typing refactor wrapped into the new feature, not a separate "reproduce-first" commit; basedpyright passing on the new signature is the gate. |
| Documentation skill `@.claude/skills/semolina-docs-author/SKILL.md` | CLAUDE.md "Documentation standards" | **Not in scope for Phase 39** — only docstring updates (no how-to page). Phase 40 will invoke the skill. The skill should NOT be referenced in this phase's PLAN.md `<execution_context>`. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `adbc-driver-manager` | already a transitive dep via `adbc-poolhouse>=1.2.0` | `dbapi.Cursor.fetch_record_batch()` is the underlying method we delegate to | Already the production cursor type — Snowflake, Databricks, and DuckDB pools all hand back `adbc_driver_manager.dbapi.Cursor` instances. No new dependency. [VERIFIED: pyproject.toml line 11; `_results.reader._reader` in arrow-adbc source] |
| `pyarrow` | >=17.0.0 (already pinned in `[duckdb]` extra) | `RecordBatchReader`, `Table`, `RecordBatch` types used in signatures and tests | Already pinned in `duckdb` extra at pyarrow>=17.0.0. Both Snowflake (via `adbc-poolhouse[snowflake]`) and Databricks (via `databricks-sql-connector[pyarrow]`) transitively pull in pyarrow. [VERIFIED: pyproject.toml lines 38–44] |
| `pyarrow-stubs` | (decision: do NOT adopt) | Third-party stubs for pyarrow | Latest is `20.0.0.20251215` (Dec 2025) but the maintainer has stated they no longer have time and is looking for a new home for the project. Per the user typing rule, `if TYPE_CHECKING: import pyarrow` with exact forward-reference return types is the chosen approach — no stub package needed and the project takes no third-party-stub risk. [CITED: pypi.org/project/pyarrow-stubs/, github.com/apache/arrow/discussions/45919] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | >=8.0.0 (dev) | Unit tests + integration | Already used. New test classes in `tests/unit/test_cursor.py`. |
| `pytest.importorskip("pyarrow")` | n/a | Skip Arrow tests when pyarrow not installed | Existing pattern in `test_cursor.py` (line 344). Reuse for new tests. |
| `pytest.importorskip("adbc_driver_duckdb")` | n/a | Skip ADBC tests when DuckDB ADBC not installed | Existing pattern at `test_cursor.py:37`. Reuse for new in-process ADBC tests. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `if TYPE_CHECKING: import pyarrow` | `pyarrow-stubs` package | Stubs are unmaintained, add a dev dep, and don't change runtime behaviour. Forward-ref strings + TYPE_CHECKING are zero-cost, project-controlled. [CITED: github.com/apache/arrow/discussions/45919] |
| `if TYPE_CHECKING: import pyarrow` | Keep `-> Any` | User explicitly rejected. Loses IDE autocomplete and downstream type narrowing. |
| Stored generator on `SemolinaCursor` for `__next__` | Inline `_current_batch`/`_next_row`/`_reader` state | Generator-based is simpler to read (single `_iter()` method). State-machine is closer to ADBC's own `_RowIterator` pattern (dbapi.py:1491) and slightly faster (no generator frame per row). Either works — assigned to Claude's discretion. |
| Mirror `cursor.description` for column names | Pull `batch.schema.names` per batch | User locked: use batch schema. Self-contained — no dependency on `_cursor.description` (which is set at execute() time, but using schema keeps the iteration boundary clean and avoids one attribute access per row). |

### Installation

No new packages. All deps already present.

```bash
# Already installed via [duckdb] extra during normal dev setup
uv sync --extra duckdb
```

**Version verification (run during Wave 0 to confirm registry currency):**
```bash
uv pip show pyarrow         # expect >=17.0.0
uv pip show adbc-driver-manager
uv pip show adbc-driver-duckdb
```

## Architecture Patterns

### Recommended Implementation Shape

```
src/semolina/cursor.py
├── SemolinaCursor                  # existing class — extend in place
│   ├── fetch_arrow_table()         # FIX: change `-> Any` to `-> pyarrow.Table`
│   ├── fetch_record_batch()        # NEW: -> pyarrow.RecordBatchReader (passthrough)
│   ├── __iter__()                  # NEW: -> Self (returns self)
│   └── __next__()                  # NEW: -> Row (raises StopIteration when drained)
│   └── _batch_iter                 # NEW private: Iterator[Row] | None (lazy-initialised)
```

No new files. No new modules. The whole change lives in `cursor.py` plus tests.

### Pattern 1: TYPE_CHECKING import for pyarrow return types

**What:** Annotate pyarrow returns precisely without a runtime import.
**When to use:** Every place a pyarrow type appears in a function signature anywhere in `src/semolina/`.
**Example:**
```python
# Source: existing semolina pattern in src/semolina/query.py:12-17
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pyarrow

from .results import Row


class SemolinaCursor:
    def fetch_arrow_table(self) -> pyarrow.Table:
        """Fetch all remaining rows as a PyArrow Table (ADBC passthrough)."""
        return self._cursor.fetch_arrow_table()

    def fetch_record_batch(self) -> pyarrow.RecordBatchReader:
        """Fetch the result as a PyArrow RecordBatchReader (ADBC passthrough)."""
        return self._cursor.fetch_record_batch()
```

With `from __future__ import annotations` already at the top of `cursor.py` (line 9), all annotations are strings at runtime — `pyarrow.Table` and `pyarrow.RecordBatchReader` are never evaluated at module load, so the `if TYPE_CHECKING:` import is sufficient for basedpyright resolution. No `# type: ignore`, no stub package. [VERIFIED: cursor.py:9 already imports `from __future__ import annotations`]

### Pattern 2: Lazy iterator using `read_next_batch` / batch row construction

**What:** Pull batches one at a time from the ADBC-backed `RecordBatchReader`, yielding rows.
**When to use:** Inside `SemolinaCursor.__iter__` / `__next__`.
**Example (generator flavour — Claude's discretion which exact shape):**
```python
# Source: pattern derived from cursor.py:60-69 (fetchall_rows) + arrow-adbc
# dbapi.py:1491-1511 (_RowIterator.fetchone — official ADBC pattern)

def __iter__(self) -> Iterator[Row]:
    """Iterate rows lazily by pulling batches from the underlying reader."""
    if self._batch_iter is None:
        self._batch_iter = self._row_generator()
    return self._batch_iter

def _row_generator(self) -> Iterator[Row]:
    reader: pyarrow.RecordBatchReader = self._cursor.fetch_record_batch()
    for batch in reader:
        columns = batch.schema.names
        for raw in zip(*(col.to_pylist() for col in batch.columns), strict=True):
            yield Row(dict(zip(columns, raw, strict=True)))
```

**Alternative (state-machine flavour, closer to ADBC's own approach):**
```python
def __iter__(self) -> "SemolinaCursor":
    return self

def __next__(self) -> Row:
    if self._reader is None:
        self._reader = self._cursor.fetch_record_batch()
        self._batch = None
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_pos = 0
    while self._batch_pos >= len(self._batch_rows):
        try:
            self._batch = self._reader.read_next_batch()
        except StopIteration:
            raise
        if self._batch.num_rows == 0:
            continue  # ADBC may emit zero-row batches; skip them
        self._batch_rows = self._batch.to_pylist()
        self._batch_pos = 0
    row = Row(self._batch_rows[self._batch_pos])
    self._batch_pos += 1
    return row
```

The state-machine version mirrors ADBC's own `_RowIterator.fetchone()` semantics (it loops past empty batches), which is the most defensible choice. [VERIFIED: arrow-adbc dbapi.py:1491-1511]

**Note on `batch.to_pylist()`:** Returns `list[dict[str, Any]]` where each dict has column names as keys (verified against pyarrow Table/RecordBatch docs). This subsumes the manual zip-with-schema-names pattern and is slightly more idiomatic. The user's locked decision says "mirror the column-zip pattern" — `to_pylist()` is functionally equivalent and produces the dict the `Row()` constructor wants. Recommend Claude use `to_pylist()` unless there's a perf reason not to; flag as a planner micro-decision.

### Pattern 3: Building a fake `RecordBatchReader` for laziness tests

**What:** Wrap a generator in `pa.RecordBatchReader.from_batches()` and count `read_next_batch` calls.
**When to use:** Unit test that proves Success Criterion 2 ("batches consumed lazily").
**Example:**
```python
# Source: pyarrow docs — RecordBatchReader.from_batches signature
# https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatchReader.html

import pyarrow as pa

class _CountingReader:
    """Wraps a RecordBatchReader and counts read_next_batch invocations."""

    def __init__(self, schema, batches):
        self.schema = schema
        self.batches = iter(batches)
        self.read_count = 0

    def __iter__(self):
        return self

    def read_next_batch(self):
        self.read_count += 1
        return next(self.batches)

    def __next__(self):
        return self.read_next_batch()

    def close(self):
        pass


def test_iter_pulls_batches_lazily() -> None:
    schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
    batches = [
        pa.RecordBatch.from_pydict(
            {"revenue": [1, 2], "country": ["US", "CA"]}, schema=schema
        ),
        pa.RecordBatch.from_pydict(
            {"revenue": [3, 4], "country": ["MX", "UK"]}, schema=schema
        ),
        pa.RecordBatch.from_pydict(
            {"revenue": [5, 6], "country": ["DE", "FR"]}, schema=schema
        ),
    ]
    counting_reader = _CountingReader(schema, batches)

    fake_cursor = SimpleNamespace(
        fetch_record_batch=lambda: counting_reader,
        description=[("revenue", None, None, None, None, None, None),
                     ("country", None, None, None, None, None, None)],
    )
    sc = SemolinaCursor(fake_cursor, conn=SimpleNamespace(close=lambda: None),
                       pool=SimpleNamespace(close=lambda: None))

    it = iter(sc)
    next(it)  # row 1, batch 1
    assert counting_reader.read_count == 1
    next(it)  # row 2, batch 1 (no new batch pull)
    assert counting_reader.read_count == 1
    next(it)  # row 3, batch 2 (new pull)
    assert counting_reader.read_count == 2
    # batches 3 still unread — proving laziness
```

This bypasses the real ADBC reader entirely and proves the SemolinaCursor pulls batches only when the previous one is drained. Use a duck-typed object (not `pa.RecordBatchReader` subclass — see anti-patterns below).

### Anti-Patterns to Avoid

- **Subclassing `pa.RecordBatchReader`:** The pyarrow docs explicitly warn against this — "Do not call this class's constructor directly, use one of the `RecordBatchReader.from_*` functions instead." Use duck typing for fakes (any object with `read_next_batch`, `__iter__`, `schema`, `close`), or wrap a generator with `pa.RecordBatchReader.from_batches()` if a real reader is needed.
- **Calling `fetch_record_batch()` inside `__init__`:** Defers state until `__next__` is first called. If a user calls `fetch_arrow_table()` first and never iterates, no work happens; if they call both, the second one sees an empty stream (matches user's locked decision: "After `fetch_arrow_table()` or `fetchall_rows()`, iterating the cursor yields zero rows").
- **Closing the cursor on `StopIteration`:** User locked out. Close stays with `.close()` / context manager.
- **Re-reading `cursor.description` per row:** The user locked the decision to use `batch.schema.names` (or `batch.to_pylist()` dicts) for column names. Avoid re-reading `cursor.description` inside `__next__`.
- **Storing the reader as a module-level attribute or returning it from a closed cursor:** ADBC issue #1893 confirms the cursor must outlive the reader. SemolinaCursor itself outlives it (close is explicit), so this is naturally satisfied — but the planner should ensure no test or example shows returning the reader from a closed-context-manager cursor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming protocol over ADBC | Custom batch fetcher, custom prefetch loop | `cursor.fetch_record_batch()` passthrough | ADBC's `_RowIterator` already does prefetch, blocking-call cancellation, schema import. Re-implementing it produces bugs and loses cancellation. [VERIFIED: arrow-adbc dbapi.py:1389-1409] |
| Row construction from RecordBatch | Manual `for i in range(num_rows): {col: arr[i].as_py() for ...}` | `batch.to_pylist()` | pyarrow's `to_pylist()` already handles null → None, timestamp → datetime, and nested types (struct, list, map) with documented semantics. Hand-rolling silently mis-handles edge cases. [CITED: arrow.apache.org/docs/python/generated/pyarrow.Table.html] |
| RecordBatchReader from in-memory data (for tests) | Manual generator + `iter()` wrapper without schema | `pa.RecordBatchReader.from_batches(schema, iter_batches)` | Official factory; correctly exposes schema; safe for real-pyarrow consumers. Also documented for testing scenarios. [CITED: arrow.apache.org docs + WebSearch result] |
| Stub types for pyarrow | `pyarrow-stubs` package | `if TYPE_CHECKING: import pyarrow` + `from __future__ import annotations` | Maintainer-orphaned project; adds dev dep; project controls its own typing surface. [CITED: github.com/apache/arrow/discussions/45919] |

**Key insight:** Phase 39 is fundamentally a delegation phase. The new code is ~25 lines of cursor logic plus a typing import. Most failure modes ("I built a custom batch fetcher", "I subclassed RecordBatchReader") come from over-engineering. The right model is: ADBC owns streaming; pyarrow owns row conversion; Semolina owns Row construction and lifecycle.

## Common Pitfalls

### Pitfall 1: Cursor lifetime vs reader consumption (ADBC issue #1893)

**What goes wrong:** A user writes:
```python
with Sales.query().execute() as cursor:
    reader = cursor.fetch_record_batch()
return reader  # cursor + connection already closed
```
The reader's underlying ADBC stream is now closed; reading from it produces undefined behaviour or errors.

**Why it happens:** ADBC's `fetch_record_batch()` returns a handle that depends on the cursor + connection staying alive. Semolina's `close()` calls `self._cursor.close()` and `self._conn.close()`. [VERIFIED: cursor.py:182-186; arrow-adbc issue #1893]

**How to avoid:** This is an API contract issue, not an implementation bug. Phase 39 should NOT try to keep the cursor alive automatically (that's an ownership tangle). Phase 40 docs (out of scope here) will spell out the rule. For Phase 39: ensure none of the docstring examples show the bad pattern; do show the correct "consume inside the `with` block" pattern.

**Warning signs:** Test that exits a context manager and then tries to read from the reader → segfault, assertion error, or empty stream. Add a test that exercises the correct pattern.

### Pitfall 2: Empty batches in the stream

**What goes wrong:** ADBC's reader may emit zero-row batches at the start or middle of a stream (a known pattern — ADBC's own `_RowIterator.fetchone()` loops past them: `if self._current_batch.num_rows > 0: break`). If `__next__` doesn't loop past empty batches, it would yield nothing and immediately raise StopIteration, terminating iteration prematurely.

**Why it happens:** Internal to ADBC drivers — some emit a schema-only batch first, some emit empty fragments at stream boundaries.

**How to avoid:** In the state-machine flavour, the outer loop is `while self._batch_pos >= len(self._batch_rows):` — naturally handles empty batches by pulling the next one. In the generator flavour, the `for batch in reader:` outer loop combined with `if not batch_rows: continue` handles it. **Add a unit test that simulates a stream with `[empty_batch, non_empty_batch, empty_batch, non_empty_batch]` and asserts the correct number of rows are produced.**

[VERIFIED: arrow-adbc dbapi.py:1491-1500 — official ADBC pattern explicitly skips zero-row batches]

### Pitfall 3: `fetch_record_batch()` and `fetchone()` share state

**What goes wrong:** A user mixes streaming and row APIs:
```python
reader = cursor.fetch_record_batch()
batch1 = next(reader)
row = cursor.fetchone()  # ??? returns rows from batch 2 onwards, not batch 1
```
Behaviour is well-defined (both read from the same underlying `_RowIterator.reader`) but surprising.

**Why it happens:** `Cursor.fetch_record_batch()` returns `self._results.reader._reader` — the same reader `_RowIterator.fetchone()` uses internally. They are not independent streams. [VERIFIED: arrow-adbc dbapi.py:1389-1409]

**How to avoid:** Don't try to "fix" this in Semolina — it's the ADBC contract. Document the contract in Phase 40 (out of scope here). For Phase 39: pick **one** entry point per cursor lifecycle in tests; don't construct ambiguous tests that mix `fetch_record_batch()` and `__iter__` on the same cursor without exercising deliberate sequencing.

### Pitfall 4: Calling `fetch_record_batch()` after `fetch_arrow_table()`

**What goes wrong:** `fetch_arrow_table()` calls `reader.read_all()`, which drains the reader. Subsequent `fetch_record_batch()` returns the same exhausted reader — iterating yields zero batches, no error. Same for iterating the cursor after `fetch_arrow_table()`.

**Why it happens:** Single underlying reader; `read_all` exhausts it.

**How to avoid:** User locked this as expected behaviour: "After `fetch_arrow_table()` or `fetchall_rows()`, iterating the cursor yields zero rows. No raise." Add a test asserting exactly this: call `fetch_arrow_table()`, then `for row in cursor: rows.append(row)`, assert `rows == []`. [VERIFIED: arrow-adbc dbapi.py:1531-1532, `read_all` drains the reader]

### Pitfall 5: Multiple `fetch_record_batch()` calls return the same object

**What goes wrong:** A naive test asserts `r1 is not r2` after two calls.

**Why it happens:** ADBC returns `self._results.reader._reader` — the same reader object each time. Idempotent at the wrapper level, but they share state with `fetchone`/`fetchall`.

**How to avoid:** Don't test for non-identity. Do test that calling twice doesn't raise (it shouldn't — there's no consume-once guard on `fetch_record_batch` in ADBC, only on `fetch_arrow`). [VERIFIED: arrow-adbc dbapi.py:1389-1409 — no `_handle = None` after fetch_record_batch]

### Pitfall 6: `pa.RecordBatchReader` is not designed for subclassing

**What goes wrong:** Test code does `class CountingReader(pa.RecordBatchReader): ...` and gets a constructor warning or runtime error.

**Why it happens:** Per pyarrow docs: "Do not call this class's constructor directly, use one of the `RecordBatchReader.from_*` functions instead."

**How to avoid:** Use a plain duck-typed object for fakes (as in Pattern 3 above), or wrap a counting generator with `pa.RecordBatchReader.from_batches(schema, gen)`. **The duck-typed approach is cleanest for laziness tests** because the counter lives on the wrapper, not inside a generator closure.

### Pitfall 7: pyarrow type checking against basedpyright strict

**What goes wrong:** Importing pyarrow at module top level breaks the `[duckdb]`-extra-only install path; importing inside the function pollutes runtime; `# type: ignore` is forbidden by CLAUDE.md.

**How to avoid:** `from __future__ import annotations` (already at cursor.py:9) makes annotations into strings. Pair with `if TYPE_CHECKING: import pyarrow`. basedpyright resolves the type for static checking; runtime never imports. Verify: `prek run --all-files` and check that `import semolina.cursor` does not import pyarrow (e.g. `python -c "import sys; import semolina.cursor; assert 'pyarrow' not in sys.modules"`).

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — pure code addition, no schema changes, no migrations | None |
| Live service config | None — no external services touched | None |
| OS-registered state | None | None |
| Secrets/env vars | None — no new credentials | None |
| Build artifacts | None — `uv build` will rebuild from updated source, no stale wheel concerns | None |

**Nothing found in any category.** Phase 39 is a code-only addition with no stateful side effects.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pyarrow` | Type annotations + tests | Verify in Wave 0 | ≥17.0.0 (already pinned) | `pytest.importorskip` for tests; runtime import never happens (TYPE_CHECKING) |
| `adbc_driver_manager` | Production runtime + tests | Already transitive via `adbc-poolhouse` | Latest | None — required |
| `adbc_driver_duckdb` | In-process ADBC tests in `test_cursor.py` | Already used in `tests/unit/test_cursor.py:37` | Latest | `pytest.importorskip` (existing pattern) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — all already in place.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 (basedpyright strict) |
| Config file | `pyproject.toml` (`[tool.basedpyright]`, `[tool.pytest.ini_options]` if present) |
| Quick run command | `uv run pytest tests/unit/test_cursor.py -x` |
| Full suite command | `just test` (unit + jaffle-shop) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| STREAM-01 | `fetch_record_batch()` returns a `pyarrow.RecordBatchReader` (DuckDB in-process) | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_returns_record_batch_reader -x` | ❌ Wave 0 |
| STREAM-01 | `fetch_record_batch()` schema matches `cursor.description` columns | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_schema_columns_match_description -x` | ❌ Wave 0 |
| STREAM-01 | `fetch_record_batch()` on empty result returns a reader that yields no rows | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_empty_result -x` | ❌ Wave 0 |
| STREAM-01 | `fetch_record_batch()` raises `AttributeError` on MockCursor (parity with `fetch_arrow_table`) | unit | `pytest tests/unit/test_cursor.py::TestFetchRecordBatch::test_mock_cursor_raises -x` | ❌ Wave 0 |
| STREAM-02 | `for row in cursor:` yields `Row` objects with correct values (DuckDB in-process) | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_yields_row_objects -x` | ❌ Wave 0 |
| STREAM-02 | Iteration produces correct count and ordering across multi-batch result | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_multiple_batches -x` | ❌ Wave 0 |
| STREAM-02 | **Laziness:** after N rows from M batches, fake reader's `read_next_batch` counter reflects partial consumption (≤ ⌈N/batch_size⌉ pulls, not all M) | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_lazy_batch_pull -x` | ❌ Wave 0 |
| STREAM-02 | Iterating cursor after `fetch_arrow_table()` yields zero rows (no raise) | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_after_fetch_arrow_table -x` | ❌ Wave 0 |
| STREAM-02 | Re-iterating a consumed cursor yields zero rows (no raise) | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_reiteration_yields_nothing -x` | ❌ Wave 0 |
| STREAM-02 | Empty batches in the middle of a stream are skipped correctly | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_skips_empty_batches -x` | ❌ Wave 0 |
| STREAM-02 | `__iter__` does NOT auto-close cursor on exhaustion | unit (ADBC) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_does_not_auto_close -x` | ❌ Wave 0 |
| STREAM-02 | `__iter__` returns `self` (DBAPI cursor iterator convention) | unit (fake) | `pytest tests/unit/test_cursor.py::TestStreamingIteration::test_iter_returns_self -x` | ❌ Wave 0 |
| Typing fix | `fetch_arrow_table()` return type annotation is `pyarrow.Table`, not `Any` | static | `uv run prek run --all-files` (basedpyright strict) | exists |
| Cross-backend SC-3 | Iteration works on Snowflake (record mode only) | integration (parametrized) | `pytest tests/integration/test_queries.py::test_streaming_iteration -x` | ❌ Wave 0 (extend existing) |
| Cross-backend SC-3 | Iteration works on Databricks (record mode only) | integration (parametrized) | `pytest tests/integration/test_queries.py::test_streaming_iteration -x` | ❌ Wave 0 (extend existing) |
| Cross-backend SC-3 | Iteration works on DuckDB (always available, in-process) | unit | covered by `TestStreamingIteration` above | ❌ Wave 0 |
| Traceability (SC-5) | `REQUIREMENTS.md` marks STREAM-01/02 as Complete; phase audit (SC-4) confirms shipped names match | doc/manual | grep verification + verifier pass | exists |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_cursor.py -x` (≤30 s, covers all unit tests).
- **Per wave merge:** `just test` (unit + jaffle-shop) and `uv run prek run --all-files`.
- **Phase gate:** Full suite green before `/gsd-verify-work`; basedpyright strict clean on `cursor.py`; `docs-build` not affected (no doc changes).

### Wave 0 Gaps

- [ ] `tests/unit/test_cursor.py` — new test classes `TestFetchRecordBatch` and `TestStreamingIteration` (mirroring `TestFetchArrowTable` pattern at line 339).
- [ ] Fake `_CountingReader` helper inside `test_cursor.py` for laziness assertions (see Pattern 3 above). No new file needed.
- [ ] Optional: cross-backend integration smoke in `tests/integration/test_queries.py` parametrized over `backend_engine` — uses existing `Sales` model and TEST_DATA fixture. Only exercises iteration path; replay-mode uses MockEngine so iteration must work over the MockCursor fallback path. **Caveat:** MockCursor doesn't expose `fetch_record_batch`. Either (a) gate the streaming integration test behind `is_recording` so it only runs in `--snapshot-update` against real warehouses, or (b) make the integration test ADBC-only by parametrising over a DuckDB-via-ADBC variant. Option (a) is the lowest-risk default; document the limitation. **Planner decision needed.**
- [ ] Framework install: not needed — pytest already in dev group.

### Validation Dimensions

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Static typing | basedpyright strict via `prek` | Ensures `pyarrow.Table` / `pyarrow.RecordBatchReader` annotations resolve without `# type: ignore` |
| Unit (real ADBC, DuckDB in-process) | New `TestFetchRecordBatch`, `TestStreamingIteration` test classes | Fast (<1s each); exercises real ADBC → pyarrow flow |
| Unit (fake reader, instrumented) | `_CountingReader` + `test_lazy_batch_pull`, `test_skips_empty_batches` | Proves laziness and edge cases without depending on ADBC batch sizes |
| Property (empty result, single row, multi-batch) | Parameterized tests in `TestFetchRecordBatch` and `TestStreamingIteration` | Mirrors `TestFetchArrowTable`'s test shape (line 339 onwards) |
| Integration (cross-backend) | Extend `tests/integration/test_queries.py` parametrized via `backend_engine`, OR add ADBC-DuckDB-only smoke | Snowflake/Databricks coverage only meaningful in `--snapshot-update` record mode (CI does not have warehouse credentials) |
| Lifecycle | `test_does_not_auto_close`, context manager round-trip | Confirms user-locked decision that `__iter__` doesn't close on exhaustion |

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 39 adds no auth surface; existing pool registration handles credentials. |
| V3 Session Management | no | No session state added. |
| V4 Access Control | no | No access-control surface. |
| V5 Input Validation | no (no new user input — `fetch_record_batch()` takes no args; `__iter__` takes no args) | n/a |
| V6 Cryptography | no | No cryptographic operations. |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Resource exhaustion via unbounded streaming | Denial of Service | Inherits ADBC's prefetch limits (Snowflake: 200 queued batches default, 10 concurrent streams default). No Semolina-side mitigation needed for v0.5; STREAM-04 will eventually add user knobs. [CITED: arrow.apache.org/adbc/0.9.0/driver/snowflake.html] |
| Cursor/connection resource leak on exception during iteration | Denial of Service (long-running) | Existing context-manager `__exit__` covers `.close()` on the cursor + connection; iteration adds no new leak path because `__next__` does not allocate persistent OS resources beyond the underlying reader (already owned by the cursor). |

No new security-relevant surface beyond what v0.4.0's `fetch_arrow_table()` already shipped.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled streaming protocols per warehouse driver | ADBC's unified `fetch_record_batch()` returning `pyarrow.RecordBatchReader` | ADBC 0.5+ (2023); pyarrow ≥ 8.0 | Semolina gets cross-backend streaming for free; backend-specific code paths unnecessary. |
| `# type: ignore[return-type]` for pyarrow returns | `if TYPE_CHECKING: import pyarrow` + `from __future__ import annotations` | Mainstream since 3.10/3.11; basedpyright strict supports it natively | Cleaner code, no ignores, full IDE autocomplete for users. |
| `pyarrow-stubs` as the canonical pyarrow typing solution | Community moving away — maintainer seeking new owner | Discussion #45919 opened 2025 | Decision to NOT adopt pyarrow-stubs is well-supported by the ecosystem direction. [CITED: github.com/apache/arrow/discussions/45919] |

**Deprecated/outdated:**
- `cursor.fetch_record_batch()` on duckdb-python (different API, returns slightly different object) — irrelevant here since we go through `adbc_driver_duckdb`, which conforms to ADBC's DBAPI.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (none) | — | — | All technical claims in this research are verified against the arrow-adbc source code at `python/adbc_driver_manager/adbc_driver_manager/dbapi.py` (HEAD on main) or against published pyarrow/ADBC docs. No `[ASSUMED]` claims. |

**Table empty: all claims verified or cited — no user confirmation needed.**

## Open Questions

1. **Integration test coverage for Snowflake/Databricks streaming.**
   - What we know: `tests/integration/test_queries.py` is the cross-backend smoke harness, parametrized via `backend_engine`. In replay mode (CI default) it uses MockEngine — which has no `fetch_record_batch` and is not ADBC-based.
   - What's unclear: How aggressively should the integration test exercise streaming? Options:
     - (A) Add streaming-iteration test gated behind `--snapshot-update` only (so it only runs against real warehouses).
     - (B) Build a separate DuckDB-ADBC-only smoke test inside `tests/integration/` to prove "ADBC pathway iteration works end-to-end through a registered pool" without needing Snowflake/Databricks credentials.
     - (C) Both.
   - Recommendation: **(B) is the highest-value coverage** — DuckDB-via-ADBC exercises the full pool → connection → cursor → SemolinaCursor → `__iter__` chain on every CI run, while Snowflake/Databricks remain "ADBC normalises this, so DuckDB coverage suffices." Add (A) as a record-mode-only sanity check.

2. **`batch.to_pylist()` vs explicit zip with `batch.schema.names`.**
   - What we know: Both work. `to_pylist()` is the official idiom and handles null/timestamp/nested types per pyarrow's contract. The user's locked decision says "mirror the column-zip pattern from `fetchall_rows()`" — but the locked decision was about column-name **source** (schema, not description), not iteration mechanics.
   - What's unclear: Is the user committed to the literal zip mechanics or to the principle of "use schema for column names"?
   - Recommendation: **Use `batch.to_pylist()`** — it produces `list[dict[str, Any]]` already keyed by column name (from schema), matching the principle. The zip is then `Row(d)` for each `d`. Faster, fewer lines. Flag for confirmation in the planner discuss step if there's any doubt.

3. **Whether `__iter__` is a fresh generator or returns `self`.**
   - What we know: User locked: "`SemolinaCursor.__iter__` returns `self`; `__next__` defined."
   - What's unclear: With `__iter__` returning self and state stored on the cursor, two simultaneous calls to `iter(cursor)` share state. Standard DBAPI behaviour. Documenting this in the docstring is sufficient.
   - Recommendation: Implement state-machine flavour with `_reader`, `_batch`, `_batch_rows`, `_batch_pos` on the cursor; document single-pass semantics in `__iter__` docstring.

## Sources

### Primary (HIGH confidence)

- **arrow-adbc source code** (HEAD on `apache/arrow-adbc:main`, `python/adbc_driver_manager/adbc_driver_manager/dbapi.py`) — confirmed implementations of `fetch_record_batch()` (line 1389), `fetch_arrow_table()` (line 1340), `fetch_arrow()` (line 1411), and `_RowIterator` (line 1436 onwards). Read directly from raw GitHub.
- **pyarrow official docs** — [pyarrow.RecordBatchReader](https://arrow.apache.org/docs/python/generated/pyarrow.RecordBatchReader.html) (iteration protocol, `from_batches`, "do not subclass" warning), [pyarrow.Table](https://arrow.apache.org/docs/python/generated/pyarrow.Table.html) (`to_pylist()` returns list of dicts keyed by column name).
- **Existing semolina code** — `src/semolina/cursor.py:60-69` (column-zip pattern), `cursor.py:130-156` (existing `fetch_arrow_table` to mirror), `query.py:12-17` (TYPE_CHECKING import pattern), `tests/unit/test_cursor.py:339-405` (`TestFetchArrowTable` to mirror).
- **CLAUDE.md** — quality gates, docstring conventions, line length, basedpyright strict, "avoid `# type: ignore`" directive.

### Secondary (MEDIUM confidence)

- **[arrow-adbc issue #1893](https://github.com/apache/arrow-adbc/issues/1893)** — confirmed cursor lifetime requirement: cursor must outlive the reader.
- **[ADBC Snowflake driver docs](https://arrow.apache.org/adbc/0.9.0/driver/snowflake.html)** — confirmed Snowflake-specific prefetch knobs (200 batch queue, 10 concurrent streams) — relevant only as context for STREAM-04 (deferred).
- **[pyarrow-stubs PyPI](https://pypi.org/project/pyarrow-stubs/)** — latest release `20.0.0.20251215`; confirms package exists and is recent.
- **[apache/arrow discussion #45919](https://github.com/apache/arrow/discussions/45919)** — pyarrow-stubs maintainer seeking new home (rationale for not adopting).

### Tertiary (LOW confidence)

- None — every claim used in the planner-facing sections has a primary or secondary source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already pinned in `pyproject.toml`; verified against source.
- Architecture patterns: HIGH — patterns are derived from existing `cursor.py` code + verified ADBC implementation (`_RowIterator` at dbapi.py:1436).
- Pitfalls: HIGH — pitfalls 1, 2, 3, 4, 5 are verified against arrow-adbc source / issue tracker; pitfall 6 quoted from pyarrow docs; pitfall 7 verified against existing `cursor.py` import structure.
- Validation architecture: HIGH — mirrors existing `TestFetchArrowTable` test shape; new fake-reader pattern verified against `pa.RecordBatchReader.from_batches` docs.

**Research date:** 2026-05-14
**Valid until:** 2026-06-14 (30 days — pyarrow and ADBC are stable; recheck if pyarrow 18+ or ADBC 24+ ships in that window)
