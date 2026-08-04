"""
Tests for AsyncSemolinaCursor result surface, streaming, and close ordering.

Tests cover:
- ASYNC-03: ``async for row in cursor`` streams Row objects batch by batch off
  the event loop, and the cursor closes in the one order adbc-poolhouse permits
  (reader, then cursor, then connection) without ``ConnectionBusyError``.

Every test in this module runs twice, once under asyncio and once under Trio,
via the module-local parametrized ``anyio_backend`` fixture.

Test classes:
- TestAsyncRowMethods: awaited fetchall_rows / fetchone_row / fetchmany_rows
- TestAsyncPassthrough: raw-tuple fetches, Arrow passthroughs, sync properties
- TestAsyncStreamingIteration: lazy batch pulls, empty batches, re-iteration
  (ASYNC-03, ids carry ``stream``)
- TestAsyncCursorClose: ordered close, idempotence, invalidated connections
  (ASYNC-03, ids carry ``close``)
- TestAsyncCursorRepr: repr in open/closed states
"""
# Test-only: the async tests reach the owned async pool's inner sync pool via
# engine._pool._pool to assert checkin, and inspect cursor state such as
# _closed / _reader. Scope-disable the private-access rule (intentionally not a
# `# type: ignore`).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import pytest

from semolina.acursor import AsyncSemolinaCursor
from semolina.results import Row

if TYPE_CHECKING:
    from semolina.query import _Query

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Run every test in this module under both asyncio and Trio."""
    backend: str = request.param
    return backend


FIXTURE_DATA: list[dict[str, Any]] = [
    {"revenue": 1000, "country": "US"},
    {"revenue": 2000, "country": "CA"},
    {"revenue": 500, "country": "MX"},
]


class _CountingAsyncReader:
    """
    Duck-typed fake of adbc-poolhouse's async record batch reader.

    Counts calls to ``__anext__`` so tests can assert laziness. We duck-type
    instead of subclassing because pyarrow forbids subclassing
    ``RecordBatchReader`` and poolhouse's async reader is not a public
    importable name.
    """

    def __init__(self, schema: Any, batches: Any, log: list[str] | None = None) -> None:
        """
        Initialise with a schema, an iterator of batches, and an optional close log.

        Args:
            schema: pyarrow schema describing the batches.
            batches: iterator (or iterable) of pyarrow.RecordBatch objects.
            log: shared list appended to on close, so tests can assert the
                reader closed before the cursor and connection.
        """
        self.schema = schema
        self.batches = iter(batches)
        self.read_count = 0
        self.closed = False
        self._log = log

    def __aiter__(self) -> _CountingAsyncReader:
        """Return self so the reader is its own async iterator."""
        return self

    async def __anext__(self) -> Any:
        """
        Return the next batch, raising StopAsyncIteration when exhausted.

        Returns:
            The next pyarrow.RecordBatch from the underlying iterator.
        """
        self.read_count += 1
        try:
            return next(self.batches)
        except StopIteration:
            raise StopAsyncIteration from None

    async def close(self) -> None:
        """Mark the reader closed and record the close order."""
        self.closed = True
        if self._log is not None:
            self._log.append("reader")


class _FakeAsyncCursor:
    """Minimal duck-typed fake of adbc-poolhouse's ``AsyncCursor``."""

    def __init__(
        self,
        reader: _CountingAsyncReader,
        description: list[tuple[Any, ...]] | None,
        log: list[str] | None = None,
        fetch_error: BaseException | None = None,
    ) -> None:
        """Initialise with the reader to hand out, a description, a close log, and an error."""
        self._reader = reader
        self.description = description
        self.closed = False
        self._log = log
        self._fetch_error = fetch_error

    async def fetch_record_batch(self) -> _CountingAsyncReader:
        """
        Return the counting reader (poolhouse's reader creation is awaited).

        Raises ``fetch_error`` instead when one was configured, which stands in
        for a driver that reports an already-drained result at reader-creation
        time rather than on the first pull.
        """
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._reader

    async def close(self) -> None:
        """Mark the cursor closed and record the close order."""
        self.closed = True
        if self._log is not None:
            self._log.append("cursor")


class _FakeAsyncConn:
    """
    Minimal duck-typed fake of adbc-poolhouse's ``AsyncConnection``.

    ``fail_on_close`` simulates a connection already invalidated by poolhouse's
    cancellation poison-recovery, which the sync cursor never had to face.
    """

    def __init__(self, log: list[str] | None = None, *, fail_on_close: bool = False) -> None:
        """Initialise with a shared close log and an optional close failure."""
        self.closed = False
        self._log = log
        self._fail_on_close = fail_on_close

    async def close(self) -> None:
        """Record the close order, then optionally raise as an invalidated connection would."""
        if self._log is not None:
            self._log.append("conn")
        if self._fail_on_close:
            raise RuntimeError("connection already invalidated")
        self.closed = True


def _fake_cursor(
    batches: Any,
    schema: Any,
    *,
    log: list[str] | None = None,
    fail_on_close: bool = False,
    fetch_error: BaseException | None = None,
) -> tuple[AsyncSemolinaCursor, _CountingAsyncReader, _FakeAsyncConn]:
    """Wire a counting reader, fake cursor, and fake connection into an AsyncSemolinaCursor."""
    reader = _CountingAsyncReader(schema, batches, log)
    description: list[tuple[Any, ...]] = [("revenue", None), ("country", None)]
    inner = _FakeAsyncCursor(reader, description, log, fetch_error)
    conn = _FakeAsyncConn(log, fail_on_close=fail_on_close)
    return AsyncSemolinaCursor(inner, conn, object()), reader, conn


def _batch(pa: Any, schema: Any, revenue: list[int], country: list[str]) -> Any:
    """Build a single pyarrow RecordBatch from column lists."""
    return pa.RecordBatch.from_pydict({"revenue": revenue, "country": country}, schema=schema)


# ---------------------------------------------------------------------------
# TestAsyncRowMethods: awaited Row convenience methods
# ---------------------------------------------------------------------------


class TestAsyncRowMethods:
    """Test the awaited Row convenience methods against real DuckDB."""

    async def test_fetchall_rows_returns_all_rows(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetchall_rows() returns every remaining row as a Row keyed by column name."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            rows = await cur.fetchall_rows()

        assert len(rows) == 2
        assert all(isinstance(row, Row) for row in rows)
        assert {row["country"]: row["revenue"] for row in rows} == {"US": 1500, "CA": 2000}

    async def test_fetchone_row_then_none(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetchone_row() returns Rows until drained, then None."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            first = await cur.fetchone_row()
            second = await cur.fetchone_row()
            third = await cur.fetchone_row()

        assert isinstance(first, Row)
        assert isinstance(second, Row)
        assert third is None

    async def test_fetchmany_rows_respects_size(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetchmany_rows(2) returns at most two Row objects."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            rows = await cur.fetchmany_rows(2)

        assert len(rows) <= 2
        assert all(isinstance(row, Row) for row in rows)


# ---------------------------------------------------------------------------
# TestAsyncPassthrough: raw tuples, Arrow, and the synchronous properties
# ---------------------------------------------------------------------------


class TestAsyncPassthrough:
    """Test raw DBAPI passthroughs, Arrow passthroughs, and property reads."""

    async def test_fetchall_returns_raw_tuples(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetchall() returns raw tuples, not Row objects."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            rows = await cur.fetchall()

        assert len(rows) == 2
        assert all(isinstance(row, tuple) for row in rows)

    async def test_fetchone_and_fetchmany_return_raw_tuples(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetchone() and fetchmany() return raw tuples."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            one = await cur.fetchone()
            rest = await cur.fetchmany(5)

        assert isinstance(one, tuple)
        assert all(isinstance(row, tuple) for row in rest)

    async def test_fetch_arrow_table_matches_fetchall_rows(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetch_arrow_table()'s row count matches fetchall_rows() on a fresh cursor."""
        pytest.importorskip("pyarrow")

        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            table = await cur.fetch_arrow_table()
        async with await async_duckdb_engine.aexecute(sales_query) as cur2:
            rows = await cur2.fetchall_rows()

        assert table.num_rows == len(rows)

    async def test_fetch_record_batch_returns_a_reader(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """fetch_record_batch() hands back an async reader that yields batches."""
        pytest.importorskip("pyarrow")

        cursor = await async_duckdb_engine.aexecute(sales_query)
        reader = await cursor.fetch_record_batch()
        try:
            batch = await reader.__anext__()
            assert batch.num_rows > 0
        finally:
            await reader.close()
            await cursor.aclose()

    async def test_fetch_record_batch_is_idempotent(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """
        A second fetch_record_batch() hands back the reader the first one created.

        poolhouse locks the connection for a reader's whole lifetime and rejects
        a second reader on the same connection, so the only safe answer to a
        repeat call is the reader already in flight.
        """
        pytest.importorskip("pyarrow")

        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            first = await cur.fetch_record_batch()
            second = await cur.fetch_record_batch()

            assert second is first

    async def test_fetch_record_batch_and_iteration_share_one_reader(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Mixing the passthrough with ``async for`` drives one reader, not two."""
        pytest.importorskip("pyarrow")

        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            reader = await cur.fetch_record_batch()
            rows = [row async for row in cur]

            assert cur._reader is reader

        assert len(rows) == 2

    async def test_description_and_rowcount_are_sync_properties(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Both description and rowcount are readable without an await."""
        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            description = cur.description
            rowcount = cur.rowcount

        assert description is not None
        assert {d[0] for d in description} == {"revenue", "country"}
        assert isinstance(rowcount, int)


# ---------------------------------------------------------------------------
# TestAsyncStreamingIteration: laziness and batch semantics (ASYNC-03)
# ---------------------------------------------------------------------------


class TestAsyncStreamingIteration:
    """Test async streaming semantics over the record batch reader (ASYNC-03)."""

    def test_aiter_returns_self_for_stream(self) -> None:
        """aiter(cur) is cur — the cursor is its own async iterator."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(iter([]), schema)
        assert cur.__aiter__() is cur

    async def test_stream_yields_rows_from_multiple_batches(self) -> None:
        """Iteration yields rows from every non-empty batch, in order."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        batches = [
            _batch(pa, schema, [1, 2], ["US", "CA"]),
            _batch(pa, schema, [3, 4], ["MX", "FR"]),
            _batch(pa, schema, [5, 6], ["DE", "JP"]),
        ]
        cur, _reader, _conn = _fake_cursor(iter(batches), schema)

        rows = [row async for row in cur]
        assert [row.revenue for row in rows] == [1, 2, 3, 4, 5, 6]
        assert [row.country for row in rows] == ["US", "CA", "MX", "FR", "DE", "JP"]

    async def test_stream_pulls_one_batch_at_a_time(self) -> None:
        """
        Each batch is pulled only when its first row is needed.

        This is the discriminator against materializing the whole result behind
        a streaming interface: a cursor that drained the reader up front would
        show read_count == 4 after the first row.
        """
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        batches = [
            _batch(pa, schema, [1, 2], ["US", "CA"]),
            _batch(pa, schema, [3, 4], ["MX", "FR"]),
            _batch(pa, schema, [5, 6], ["DE", "JP"]),
        ]
        cur, reader, _conn = _fake_cursor(iter(batches), schema)

        # First row forces the first batch to be pulled.
        first = await cur.__anext__()
        assert first.revenue == 1
        assert reader.read_count == 1

        # Second row comes from the same batch — no new pull.
        second = await cur.__anext__()
        assert second.revenue == 2
        assert reader.read_count == 1

        # Third row exhausts batch 1 -> pulls batch 2.
        third = await cur.__anext__()
        assert third.revenue == 3
        assert reader.read_count == 2

        # Abandon iteration — batch 3 must NOT have been pulled.
        assert reader.read_count == 2

    async def test_stream_skips_empty_batches(self) -> None:
        """A zero-row batch mid-stream is skipped, not yielded as a row."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        empty = _batch(pa, schema, [], [])
        cur, _reader, _conn = _fake_cursor(
            iter(
                [
                    empty,
                    _batch(pa, schema, [10, 20], ["US", "CA"]),
                    empty,
                    _batch(pa, schema, [30, 40], ["MX", "FR"]),
                ]
            ),
            schema,
        )

        rows = [row async for row in cur]
        assert [row.revenue for row in rows] == [10, 20, 30, 40]

    async def test_stream_reiteration_yields_nothing(self) -> None:
        """Re-entering the loop on an exhausted cursor yields zero rows and does not raise."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(iter([_batch(pa, schema, [1], ["US"])]), schema)

        first_pass = [row async for row in cur]
        second_pass = [row async for row in cur]
        assert len(first_pass) == 1
        assert second_pass == []

    async def test_stream_after_fetch_arrow_table_yields_nothing(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """
        Iterating a stream something else already drained yields zero rows.

        The async parity case for ``test_after_fetch_arrow_table`` on the sync
        cursor: ADBC drivers surface access to a drained result as ``OSError``,
        and the caller of an iterator should see the iterator stop rather than a
        driver error.
        """
        pytest.importorskip("pyarrow")

        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            table = await cur.fetch_arrow_table()
            rows = [row async for row in cur]

        assert table.num_rows == 2
        assert rows == []

    async def test_stream_normalises_a_drained_reader_creation_error(self) -> None:
        """
        A driver reporting the drain when the reader is created also stops cleanly.

        DuckDB reports it on the first pull, so the real-engine test above cannot
        reach this arm. Other ADBC drivers report it at creation instead, which
        is why the synchronous cursor guards both call sites — this is the async
        half of that parity.
        """
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(
            iter([]),
            schema,
            fetch_error=OSError("Attempting to execute an unsuccessful or closed query result"),
        )

        assert [row async for row in cur] == []

    async def test_stream_does_not_auto_close(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Iterating to exhaustion does NOT close the cursor."""
        cursor = await async_duckdb_engine.aexecute(sales_query)
        try:
            rows = [row async for row in cursor]
            assert len(rows) == 2
            assert cursor._closed is False
        finally:
            await cursor.aclose()


# ---------------------------------------------------------------------------
# TestAsyncCursorClose: the mandatory close order and its edge cases
# ---------------------------------------------------------------------------


class TestAsyncCursorClose:
    """Test the ordered close, its idempotence, and its failure tolerance."""

    async def test_close_order_is_reader_cursor_connection(self) -> None:
        """aclose() closes the reader first, then the cursor, then the connection."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        log: list[str] = []
        cur, reader, _conn = _fake_cursor(
            iter([_batch(pa, schema, [1, 2], ["US", "CA"])]), schema, log=log
        )

        await cur.__anext__()
        await cur.aclose()

        assert log == ["reader", "cursor", "conn"]
        assert reader.closed is True

    async def test_close_with_live_reader_returns_connection_to_pool(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """
        Closing a partially-consumed real cursor does not raise and frees the slot.

        A fake cannot prove this: the guard being satisfied is a property of
        adbc-poolhouse's real connection, which rejects a foreign close while a
        reader is live.
        """
        cursor = await async_duckdb_engine.aexecute(sales_query)
        first = await cursor.__anext__()
        assert isinstance(first, Row)
        # The reader is live and undrained at this point.
        assert cursor._reader is not None
        assert async_duckdb_engine._pool._pool.checkedout() == 1

        await cursor.aclose()

        assert async_duckdb_engine._pool._pool.checkedout() == 0

    async def test_close_without_iterating_returns_connection_to_pool(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """Closing a cursor that was never iterated also frees the slot."""
        cursor = await async_duckdb_engine.aexecute(sales_query)
        assert cursor._reader is None

        await cursor.aclose()

        assert async_duckdb_engine._pool._pool.checkedout() == 0

    async def test_close_returns_the_slot_after_public_fetch_record_batch(
        self, sales_query: _Query, async_duckdb_engine: Any
    ) -> None:
        """
        A reader taken through the public passthrough is still closed by aclose().

        The reader the cursor creates for its own iteration is not the only one
        that locks the connection: one handed to the caller by
        ``fetch_record_batch()`` locks it identically, and draining it does not
        release the lock. If ``aclose()`` does not own that reader, the cursor
        and connection closes both raise ``ConnectionBusyError`` into the
        suppressor and the pool slot never comes back.
        """
        pytest.importorskip("pyarrow")

        async with await async_duckdb_engine.aexecute(sales_query) as cur:
            reader = await cur.fetch_record_batch()
            async for _batch in reader:
                pass

        assert async_duckdb_engine._pool._pool.checkedout() == 0

    async def test_close_is_idempotent(self) -> None:
        """A second aclose() is a no-op rather than a second teardown."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        log: list[str] = []
        cur, _reader, _conn = _fake_cursor(iter([_batch(pa, schema, [1], ["US"])]), schema, log=log)

        await cur.__anext__()
        await cur.aclose()
        await cur.aclose()

        assert log == ["reader", "cursor", "conn"]

    async def test_close_tolerates_invalidated_connection(self) -> None:
        """aclose() completes when the connection was already invalidated."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        log: list[str] = []
        cur, reader, _conn = _fake_cursor(
            iter([_batch(pa, schema, [1], ["US"])]), schema, log=log, fail_on_close=True
        )

        await cur.__anext__()
        await cur.aclose()

        assert cur._closed is True
        assert reader.closed is True
        assert log == ["reader", "cursor", "conn"]

    async def test_close_warns_when_the_connection_cannot_be_returned(self) -> None:
        """
        A connection close that fails is suppressed, but reported as a ResourceWarning.

        Suppressing the failure is right — teardown must not mask the caller's
        own error — but suppressing it *silently* turns a failed check-in into a
        permanent pool leak that nothing anywhere records. The class already
        warns about the leak it cannot prevent in ``__del__``; the leak it can
        detect deserves the same vocabulary.
        """
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(
            iter([_batch(pa, schema, [1], ["US"])]), schema, fail_on_close=True
        )

        await cur.__anext__()
        with pytest.warns(ResourceWarning, match="could not return its pooled connection"):
            await cur.aclose()

        assert cur._closed is True

    async def test_close_does_not_warn_on_a_clean_teardown(self) -> None:
        """A teardown that succeeds emits no ResourceWarning."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(iter([_batch(pa, schema, [1], ["US"])]), schema)

        await cur.__anext__()
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            await cur.aclose()

    async def test_close_via_async_context_manager(self) -> None:
        """`async with` runs the same ordered close on exit."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        log: list[str] = []
        cur, _reader, _conn = _fake_cursor(iter([_batch(pa, schema, [1], ["US"])]), schema, log=log)

        async with cur as entered:
            assert entered is cur
            await cur.__anext__()

        assert log == ["reader", "cursor", "conn"]
        assert cur._closed is True


# ---------------------------------------------------------------------------
# TestAsyncCursorRepr
# ---------------------------------------------------------------------------


class TestAsyncCursorRepr:
    """Test repr in the open and closed states."""

    async def test_repr_open_lists_columns(self) -> None:
        """An open cursor's repr lists its columns."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(iter([]), schema)

        text = repr(cur)
        assert "AsyncSemolinaCursor" in text
        assert "open" in text
        assert "revenue" in text

    async def test_repr_closed(self) -> None:
        """A closed cursor's repr says so and lists no columns."""
        pa = pytest.importorskip("pyarrow")

        schema = pa.schema([("revenue", pa.int64()), ("country", pa.string())])
        cur, _reader, _conn = _fake_cursor(iter([]), schema)

        await cur.aclose()
        assert repr(cur) == "<AsyncSemolinaCursor closed>"
