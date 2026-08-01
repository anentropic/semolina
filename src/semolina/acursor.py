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
from typing import Any

from .results import Row


class AsyncSemolinaCursor:
    """
    Async DBAPI 2.0 cursor wrapper with Row convenience methods.

    Wraps an adbc-poolhouse async cursor via delegation and adds ``Row``-mapping
    convenience over it. Returned already-open by
    :meth:`semolina.engines.abase.AsyncEngine.aexecute`.

    ``async with`` is the canonical form. It is the only shape that reliably
    returns the pooled connection, because closing requires awaiting and a
    finalizer cannot await.

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

    async def __aenter__(self) -> AsyncSemolinaCursor:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Exit async context manager, closing reader, cursor, and connection."""
        await self.aclose()
