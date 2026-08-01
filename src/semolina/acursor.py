"""
Async DBAPI 2.0 cursor wrapper with Row convenience methods.

``AsyncSemolinaCursor`` is the async sibling of
:class:`~semolina.cursor.SemolinaCursor`. It is a separate class rather than a
mode flag on the sync cursor, so a sync-style call on an async cursor cannot
silently hand back a coroutine that nobody awaits.

The two classes differ in one structural way beyond the awaits: teardown. An
async cursor must close its Arrow reader *before* its cursor and connection,
because adbc-poolhouse locks the connection for the reader's whole lifetime.
See :meth:`AsyncSemolinaCursor.aclose`.
"""

from __future__ import annotations

import contextlib
import warnings
from typing import TYPE_CHECKING, Any

from .results import Row

if TYPE_CHECKING:
    import pyarrow


class AsyncSemolinaCursor:
    """
    Async DBAPI 2.0 cursor wrapper with Row convenience methods.

    Wraps an adbc-poolhouse async cursor via delegation and adds ``Row``-mapping
    convenience over it. Returned already-open by
    :meth:`semolina.engines.abase.AsyncEngine.aexecute`.

    Fetch methods keep the names their synchronous counterparts have and are
    awaited: ``await cursor.fetchall_rows()``. ``description`` and ``rowcount``
    stay plain property reads, because adbc-poolhouse keeps them synchronous.

    ``async with`` is the canonical form. It is the only shape that reliably
    returns the pooled connection, because closing requires awaiting and a
    finalizer cannot await — see :meth:`__del__`.

    Sharing one cursor or connection across concurrent tasks raises
    adbc-poolhouse's ``ConnectionBusyError``, which propagates unwrapped: an
    ADBC connection allows serialized but not concurrent access, and that
    exception's own message tells you to check out a separate connection per
    task. It rejects rather than serializing on purpose, since serializing
    would let two tasks' statements interleave inside one transaction —
    driver-safe, logically corrupt, and silent. Each ``aexecute`` call checks
    out its own connection, so reaching this requires deliberately sharing one.

    Example:
        .. code-block:: python

            async with await engine.aexecute(query) as cursor:
                async for row in cursor:
                    print(row["country"], row["revenue"])

    See Also:
        - semolina.cursor.SemolinaCursor: The synchronous sibling
        - semolina.engines.abase.AsyncEngine: Produces this cursor
    """

    def __init__(
        self,
        cursor: Any,
        conn: Any,
        pool: Any,
    ) -> None:
        """
        Initialize AsyncSemolinaCursor wrapping an async DBAPI 2.0 cursor.

        Args:
            cursor: adbc-poolhouse async cursor (post-execute).
            conn: Async connection that produced the cursor.
            pool: Async pool that produced the connection.
        """
        self._cursor = cursor
        self._conn = conn
        self._pool = pool
        self._closed = False
        # Streaming iteration state (lazily initialised on first __anext__).
        # Typed as ``Any`` because adbc-poolhouse's async reader is not a public
        # importable name; reaching into its private module for an annotation
        # would violate that package's API and defeat its lazy-import
        # protection.
        self._reader: Any = None
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_pos = 0
        self._stream_exhausted = False

    def _column_names(self) -> list[str]:
        """
        Extract column names from cursor.description.

        ``description`` stays a synchronous property on the async cursor, so
        this needs no async variant.

        Returns:
            List of column name strings, or empty list if description is None.
        """
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    # -- Row convenience methods --

    async def fetchall_rows(self) -> list[Row]:
        """
        Fetch all remaining rows as Row objects.

        Returns:
            List of Row objects with attribute and dict access.
        """
        columns = self._column_names()
        raw_rows: list[tuple[Any, ...]] = await self._cursor.fetchall()
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    async def fetchone_row(self) -> Row | None:
        """
        Fetch next row as a Row, or None if exhausted.

        Returns:
            Row object, or None if no rows remain.
        """
        raw: tuple[Any, ...] | None = await self._cursor.fetchone()
        if raw is None:
            return None
        columns = self._column_names()
        return Row(dict(zip(columns, raw, strict=True)))

    async def fetchmany_rows(self, size: int = 1) -> list[Row]:
        """
        Fetch up to size rows as Row objects.

        Args:
            size: Maximum number of rows to fetch. Defaults to 1.

        Returns:
            List of Row objects (may be shorter than size).
        """
        columns = self._column_names()
        raw_rows: list[tuple[Any, ...]] = await self._cursor.fetchmany(size)
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    # -- DBAPI 2.0 passthrough methods --

    async def fetchall(self) -> list[tuple[Any, ...]]:
        """
        Fetch all remaining rows as raw tuples (DBAPI passthrough).

        Returns:
            List of tuple rows.
        """
        return await self._cursor.fetchall()

    async def fetchone(self) -> tuple[Any, ...] | None:
        """
        Fetch next row as raw tuple (DBAPI passthrough).

        Returns:
            Tuple row, or None if exhausted.
        """
        return await self._cursor.fetchone()

    async def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """
        Fetch up to size rows as raw tuples (DBAPI passthrough).

        Args:
            size: Maximum number of rows to fetch.

        Returns:
            List of tuple rows.
        """
        return await self._cursor.fetchmany(size)

    async def fetch_arrow_table(self) -> pyarrow.Table:
        """
        Fetch all remaining rows as a PyArrow Table (ADBC passthrough).

        Delegates to the underlying async ADBC cursor. Unlike
        :meth:`fetch_record_batch` this creates no live reader, so it places no
        constraint on close ordering: the whole result is materialised off the
        event loop and the connection is left unlocked.

        Returns:
            ``pyarrow.Table`` with the query results.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_arrow_table()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                async with await engine.aexecute(query) as cursor:
                    table = await cursor.fetch_arrow_table()
                    df = table.to_pandas()
        """
        return await self._cursor.fetch_arrow_table()

    async def fetch_record_batch(self) -> Any:
        """
        Fetch the result as an async record batch reader (ADBC passthrough).

        Delegates to the underlying async ADBC cursor for lazy, memory-bounded
        streaming, with each batch pull offloaded off the event loop. Most
        callers want ``async for row in cursor`` instead, which drives this
        reader and maps each batch to ``Row`` objects.

        The reader locks its connection for its whole lifetime, and draining it
        does not clear that lock. Close the reader before the cursor, or let
        :meth:`aclose` do it — closing the cursor or connection first raises
        ``ConnectionBusyError``.

        Returns:
            An adbc-poolhouse async record batch reader. Typed as ``Any``
            because that class is not a public importable name.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_record_batch()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                async with await engine.aexecute(query) as cursor:
                    reader = await cursor.fetch_record_batch()
                    async for batch in reader:
                        process(batch)
        """
        return await self._cursor.fetch_record_batch()

    # -- DBAPI 2.0 passthrough properties --

    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """
        Cursor description passthrough.

        Synchronous, with no await, because adbc-poolhouse keeps it a plain
        property read: there is no I/O to offload.

        Returns:
            List of 7-element tuples describing columns, or None before execute.
        """
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        """
        Row count passthrough.

        Synchronous for the same reason as :attr:`description`.

        Returns:
            Number of rows affected by the last operation.
        """
        return self._cursor.rowcount

    # -- Iteration --

    def __aiter__(self) -> AsyncSemolinaCursor:
        """
        Return self — AsyncSemolinaCursor is its own async iterator.

        Single-pass: the underlying ADBC stream is consumed once. Re-iterating
        an exhausted cursor yields zero rows. Iteration does NOT auto-close the
        cursor — call ``aclose()`` or use ``async with``.

        Returns:
            ``self`` for use in ``async for row in cursor:`` syntax.
        """
        return self

    async def __anext__(self) -> Row:
        """
        Return the next row from the underlying async record batch reader.

        Lazily pulls batches one at a time, each pull offloaded off the event
        loop by adbc-poolhouse, yielding ``Row`` objects from the current batch.
        Zero-row batches are skipped.

        Raises:
            StopAsyncIteration: When the underlying reader is exhausted and the
                current batch is fully consumed. Also raised on re-iteration of
                an exhausted cursor. Does NOT close the cursor.

        Returns:
            ``Row`` constructed from the next batch row, keyed by the batch
            schema's column names.
        """
        if self._stream_exhausted and self._batch_pos >= len(self._batch_rows):
            raise StopAsyncIteration
        if self._reader is None:
            self._reader = await self._cursor.fetch_record_batch()
        reader = self._reader
        while self._batch_pos >= len(self._batch_rows):
            try:
                # One offloaded, cancellable pull. There is no OSError
                # normalisation arm here (the sync cursor has one): poolhouse
                # converts the driver's end-of-stream into its own sentinel
                # before it can cross the thread boundary, because a bare
                # StopIteration crossing that boundary becomes a RuntimeError.
                batch = await reader.__anext__()
            except StopAsyncIteration:
                self._stream_exhausted = True
                raise
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row

    # -- Lifecycle --

    async def aclose(self) -> None:
        """
        Close in the one order adbc-poolhouse permits: reader, cursor, connection.

        A live Arrow reader locks its connection for the reader's whole
        lifetime, and draining the reader does not clear that lock — only
        ``reader.close()`` does. Both the async cursor's and the async
        connection's ``close()`` take the foreign tier of that guard, so closing
        either before the reader raises ``ConnectionBusyError`` from inside
        teardown. The order therefore holds even when the caller iterated
        partially or not at all.

        Each step is suppressed narrowly — ``Exception``, deliberately not
        ``BaseException`` — so teardown cannot mask the caller's error while a
        cancellation arriving during teardown still propagates. Idempotent: the
        closed flag is set first, so a second call is a no-op. Tolerant of an
        already-invalidated connection, which is a real state here because
        adbc-poolhouse invalidates a connection whose in-flight query it
        aborted on cancellation.
        """
        if self._closed:
            return
        self._closed = True
        if self._reader is not None:
            with contextlib.suppress(Exception):
                await self._reader.close()
        with contextlib.suppress(Exception):
            await self._cursor.close()
        with contextlib.suppress(Exception):
            await self._conn.close()

    def __del__(self) -> None:
        """
        Warn — and only warn — that a cursor was never closed.

        This is **not** parity with :meth:`semolina.cursor.SemolinaCursor.__del__`,
        which really does return a leaked connection to the pool. The async twin
        cannot: closing requires awaiting, and a finalizer cannot await. Calling
        ``aclose()`` here would leave an un-awaited coroutine and emit the
        "coroutine was never awaited" runtime warning — which is exactly why
        adbc-poolhouse's own reader finalizer refuses to do it either.

        So a cursor closed by neither ``async with`` nor ``aclose()`` leaks its
        pooled connection permanently, and enough of them exhaust the pool. Using
        ``async with`` is the whole mitigation; this warning only tells you when
        you forgot. Guarded against a partial ``__init__`` and never raises,
        because finalizers must not propagate exceptions.
        """
        if getattr(self, "_closed", True):
            return
        with contextlib.suppress(Exception):
            warnings.warn(
                "AsyncSemolinaCursor was garbage collected without being closed; "
                "its pooled connection is leaked and will not be reclaimed. Use "
                "'async with await engine.aexecute(query) as cursor:' or await "
                "'cursor.aclose()'.",
                ResourceWarning,
                stacklevel=2,
            )

    async def __aenter__(self) -> AsyncSemolinaCursor:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Exit async context manager, closing reader, cursor, and connection."""
        await self.aclose()

    def __repr__(self) -> str:
        """
        Return human-readable representation.

        Returns:
            String like ``<AsyncSemolinaCursor columns=['a', 'b'] open>``
            or ``<AsyncSemolinaCursor closed>``.
        """
        if self._closed:
            return "<AsyncSemolinaCursor closed>"
        columns = self._column_names()
        return f"<AsyncSemolinaCursor columns={columns} open>"
