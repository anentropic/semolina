"""
The half of the two cursors that does no I/O.

:class:`~semolina.cursor.SemolinaCursor` and :class:`~semolina.acursor.AsyncSemolinaCursor`
stay separate public classes, so a sync-style call on an async cursor cannot hand back a
coroutine nobody awaits. They used to be separate implementations too: one file copied into
the other with ``await`` inserted, kept in step by hand, and four shipped defects (A16, A17,
A20, A22) were one twin changing without the other (ARCH-2).

:class:`_CursorBase` holds what does not depend on whether a call is awaited: the cursor's
state, turning DBAPI tuples and Arrow batches into ``Row`` objects, the drained-result and
batch bookkeeping, and the representation and warning text. Each public cursor keeps only
its I/O — the driver calls, sync or awaited — wrapped around these helpers.

Two things stay in the public modules on purpose. The dependency guard (``_require``) and
the read claim (``_claim_read``) are called from each public method, where
``tests/unit/test_cursor_parity.py`` records them by patching each module's own names. And
every public method keeps its own docstring there, since autoapi renders a class's own
members and not those it inherits from a private base.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from .results import Row, _distinct_columns

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pyarrow

__all__ = [
    "_CursorBase",
]
"""The module's one name, private: both cursors import it, and nothing outside them should."""


class _CursorBase:
    """
    State and non-I/O logic shared by the sync and async cursors.

    Not a cursor on its own: it has no fetch methods and never touches the driver beyond
    reading ``description``, which is a plain property on both cursors' drivers.
    """

    _public_name: ClassVar[str]
    """The subclass's public name, for ``__repr__`` and the leaked-connection warning."""

    _reader: Any
    """
    The one reader, created by whichever streaming read runs first and closed on close.

    ``Any`` here because the async reader is adbc-poolhouse's, and that class is not a public
    importable name; the sync cursor narrows it to a ``pyarrow.RecordBatchReader``.
    """

    def __init__(self, cursor: Any, conn: Any) -> None:
        """
        Initialize the state both cursors share.

        Args:
            cursor: The driver's cursor (post-execute), sync or async.
            conn: The connection that produced the cursor. Closing it returns it to its pool.
        """
        self._cursor = cursor
        self._conn = conn
        self._closed = False
        # The way this cursor's result is being read, set by the first read: see _claim_read.
        self._reading: tuple[str, str] | None = None
        self._reader = None
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_pos = 0
        self._stream_exhausted = False
        # Set once a DBAPI fetch shows the result is drained. DuckDB's driver raises for any
        # fetch after that, where DB-API returns an empty result, so later fetches answer
        # from here instead of asking the driver.
        self._drained = False

    def _column_names(self) -> list[str]:
        """
        Extract column names from cursor.description.

        ``description`` is a synchronous property on both drivers, so this needs no async
        variant.

        Returns:
            List of column name strings, or empty list if description is None.
        """
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    # -- DBAPI fetches: everything but the driver call --

    def _row_columns(self) -> Sequence[str]:
        """
        Return the column names a ``Row`` is keyed by, refusing duplicates.

        Returns:
            The result's column names, in order.

        Raises:
            ValueError: If two result columns share a name, which a Row cannot represent.
        """
        return _distinct_columns(self._column_names())

    @staticmethod
    def _rows_from(columns: Sequence[str], raw_rows: list[tuple[Any, ...]]) -> list[Row]:
        """
        Build one ``Row`` per DBAPI tuple.

        Args:
            columns: The names from :meth:`_row_columns`.
            raw_rows: Tuples from a DBAPI fetch.

        Returns:
            The rows, in order.
        """
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    @staticmethod
    def _row_from(columns: Sequence[str], raw: tuple[Any, ...] | None) -> Row | None:
        """
        Build a ``Row`` from one DBAPI tuple, or pass ``None`` through.

        Args:
            columns: The names from :meth:`_row_columns`.
            raw: A tuple from ``fetchone()``, or ``None`` once the result is exhausted.

        Returns:
            The row, or ``None``.
        """
        if raw is None:
            return None
        return Row(dict(zip(columns, raw, strict=True)))

    def _after_fetchall(self, rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        """
        Record that a ``fetchall()`` drained the result, and return its rows.

        Args:
            rows: What the driver's ``fetchall()`` returned.

        Returns:
            ``rows`` unchanged.
        """
        self._drained = True
        return rows

    def _after_fetchone(self, row: tuple[Any, ...] | None) -> tuple[Any, ...] | None:
        """
        Record that a ``fetchone()`` found the result drained, if it returned ``None``.

        Args:
            row: What the driver's ``fetchone()`` returned.

        Returns:
            ``row`` unchanged.
        """
        if row is None:
            self._drained = True
        return row

    def _after_fetchmany(self, rows: list[tuple[Any, ...]], size: int) -> list[tuple[Any, ...]]:
        """
        Record that a ``fetchmany()`` drained the result, if its batch came back short.

        Args:
            rows: What the driver's ``fetchmany(size)`` returned.
            size: The size that was asked for.

        Returns:
            ``rows`` unchanged.
        """
        if len(rows) < size:
            self._drained = True
        return rows

    # -- Row iteration: everything but the batch pull --

    def _iteration_finished(self) -> bool:
        """
        Say whether iteration already ended and the last batch is used up.

        Returns:
            True when a further ``next`` must stop without asking the reader.
        """
        return self._stream_exhausted and self._batch_pos >= len(self._batch_rows)

    def _needs_batch(self) -> bool:
        """
        Say whether the current batch is used up, so the next row needs a pull.

        Returns:
            True when no buffered row is left.
        """
        return self._batch_pos >= len(self._batch_rows)

    def _buffer_batch(self, batch: pyarrow.RecordBatch) -> None:
        """
        Make ``batch`` the current batch, unless it has no rows.

        A zero-row batch is a hole in the stream, not its end (mirrors ADBC's own
        ``_RowIterator.fetchone()``), so it is skipped and the caller pulls again.

        Args:
            batch: The batch the reader just produced.

        Raises:
            ValueError: If two columns in the batch share a name, which a Row cannot
                represent.
        """
        if batch.num_rows == 0:
            return
        _distinct_columns(batch.schema.names)
        self._batch_rows = batch.to_pylist()
        self._batch_pos = 0

    def _next_buffered_row(self) -> Row:
        """
        Return the next row of the current batch and step past it.

        Returns:
            ``Row`` keyed by the batch schema's column names.
        """
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row

    # -- Lifecycle and representation --

    def _leaked_connection_message(self, exc: Exception) -> str:
        """
        Word the ``ResourceWarning`` for a connection that failed to close.

        Args:
            exc: What closing the connection raised.

        Returns:
            The warning text, naming this cursor's public class.
        """
        return (
            f"{self._public_name} could not return its pooled connection: {exc!r}. "
            "The pool slot is leaked and will not be reclaimed."
        )

    def __repr__(self) -> str:
        """
        Return human-readable representation.

        Returns:
            String like ``<SemolinaCursor columns=['a', 'b'] open>``
            or ``<SemolinaCursor closed>``, naming the cursor's public class.
        """
        if self._closed:
            return f"<{self._public_name} closed>"
        columns = self._column_names()
        return f"<{self._public_name} columns={columns} open>"
