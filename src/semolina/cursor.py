"""
DBAPI 2.0 cursor wrapper with Row convenience methods.

SemolinaCursor delegates to any DBAPI 2.0-compatible cursor and adds
fetchall_rows(), fetchmany_rows(), and fetchone_row() that convert
raw tuples into Row objects using cursor.description column names.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, TypeVar, cast

from .exceptions import _require
from .results import Row

if TYPE_CHECKING:
    import pyarrow
    from pydantic import BaseModel

_M = TypeVar("_M", bound="BaseModel")
"""
The DTO type ``into()`` returns instances of.

A ``TypeVar`` rather than PEP 695 ``def into[M: BaseModel](...)`` syntax: ruff's
``target-version`` is ``py311``, where that spelling is a syntax error. The bound is a string
so it stays unevaluated at runtime — pydantic is imported under ``TYPE_CHECKING`` only.
"""


class SemolinaCursor:
    """
    DBAPI 2.0 cursor wrapper with Row convenience methods.

    Wraps any DBAPI 2.0-compatible cursor via delegation. Adds
    fetchall_rows(), fetchmany_rows(), and fetchone_row() methods
    that convert DBAPI tuples to Row objects.

    Context manager support releases cursor and connection on exit.
    """

    def __init__(
        self,
        cursor: Any,
        conn: Any,
        pool: Any,
    ) -> None:
        """
        Initialize SemolinaCursor wrapping a DBAPI 2.0 cursor.

        Args:
            cursor: DBAPI 2.0-compatible cursor (post-execute).
            conn: Connection that produced the cursor.
            pool: Pool that produced the connection.
        """
        self._cursor = cursor
        self._conn = conn
        self._pool = pool
        self._closed = False
        # Streaming iteration state (lazily initialised on first __next__).
        self._reader: pyarrow.RecordBatchReader | None = None
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_pos = 0
        self._stream_exhausted = False

    def _column_names(self) -> list[str]:
        """
        Extract column names from cursor.description.

        Returns:
            List of column name strings, or empty list if description is None.
        """
        desc = self._cursor.description
        if desc is None:
            return []
        return [d[0] for d in desc]

    # -- Row convenience methods --

    def fetchall_rows(self) -> list[Row]:
        """
        Fetch all remaining rows as Row objects.

        Returns:
            List of Row objects with attribute and dict access.
        """
        columns = self._column_names()
        raw_rows: list[tuple[Any, ...]] = self._cursor.fetchall()
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    def fetchone_row(self) -> Row | None:
        """
        Fetch next row as a Row, or None if exhausted.

        Returns:
            Row object, or None if no rows remain.
        """
        raw: tuple[Any, ...] | None = self._cursor.fetchone()
        if raw is None:
            return None
        columns = self._column_names()
        return Row(dict(zip(columns, raw, strict=True)))

    def fetchmany_rows(self, size: int = 1) -> list[Row]:
        """
        Fetch up to size rows as Row objects.

        Args:
            size: Maximum number of rows to fetch. Defaults to 1.

        Returns:
            List of Row objects (may be shorter than size).
        """
        columns = self._column_names()
        raw_rows: list[tuple[Any, ...]] = self._cursor.fetchmany(size)
        return [Row(dict(zip(columns, row, strict=True))) for row in raw_rows]

    # -- DBAPI 2.0 passthrough methods --

    def fetchall(self) -> list[tuple[Any, ...]]:
        """
        Fetch all remaining rows as raw tuples (DBAPI passthrough).

        Returns:
            List of tuple rows.
        """
        return self._cursor.fetchall()

    def fetchone(self) -> tuple[Any, ...] | None:
        """
        Fetch next row as raw tuple (DBAPI passthrough).

        Returns:
            Tuple row, or None if exhausted.
        """
        return self._cursor.fetchone()

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """
        Fetch up to size rows as raw tuples (DBAPI passthrough).

        Args:
            size: Maximum number of rows to fetch.

        Returns:
            List of tuple rows.
        """
        return self._cursor.fetchmany(size)

    def fetch_arrow_table(self) -> pyarrow.Table:
        """
        Fetch all remaining rows as a PyArrow Table (ADBC passthrough).

        Delegates to the underlying ADBC cursor's ``fetch_arrow_table()``
        method for zero-copy Arrow data transfer.

        Requires an ADBC-capable cursor (Snowflake, Databricks, or DuckDB
        pool connections). Not supported by non-ADBC cursors.

        Returns:
            ``pyarrow.Table`` with the query results.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_arrow_table()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                cursor = Sales.query().metrics(Sales.revenue).execute()
                table = cursor.fetch_arrow_table()
                df = table.to_pandas()
        """
        return self._cursor.fetch_arrow_table()

    def fetch_record_batch(self) -> pyarrow.RecordBatchReader:
        """
        Fetch the result as a PyArrow ``RecordBatchReader`` (ADBC passthrough).

        Delegates to the underlying ADBC cursor's ``fetch_record_batch()``
        method for lazy, memory-bounded streaming consumption of Arrow data.

        Requires an ADBC-capable cursor (Snowflake, Databricks, or DuckDB
        pool connections). Not supported by non-ADBC cursors.

        The returned reader shares state with this cursor's other fetch
        methods — consume the reader before calling ``fetchone()``,
        ``fetch_arrow_table()``, or iterating the cursor.

        The cursor must outlive the reader: consume the reader inside the
        context manager (or before ``.close()``). See arrow-adbc issue #1893.

        Returns:
            ``pyarrow.RecordBatchReader`` over the query result.

        Raises:
            AttributeError: If the underlying cursor does not support
                ``fetch_record_batch()`` (e.g. a non-ADBC cursor).

        Example:
            .. code-block:: python

                with Sales.query().metrics(Sales.revenue).execute() as cursor:
                    reader = cursor.fetch_record_batch()
                    for batch in reader:
                        process(batch)
        """
        return self._cursor.fetch_record_batch()

    # -- Typed results --

    def into(self, model: type[_M], *, validate: bool = False) -> list[_M]:
        """
        Convert the whole result into a list of Pydantic model instances.

        Columns are matched to fields by name, resolved through arrowmodel's own key rule —
        ``validation_alias``, then ``alias``, then the field name. Result columns the model
        does not declare are ignored, so one DTO can serve several queries. A declared field
        with no matching column is an error unless it carries a default.

        Any Pydantic ``BaseModel`` subclass works; inheriting from ``arrowmodel.ArrowModel``
        is not required and buys nothing here.

        Before any row moves, the result schema is checked against the model's annotations
        (see :func:`semolina.dto.check_result_schema`). That check runs on **both** settings
        of ``validate``, and on a money column it is the only protection there is. The default
        fast path builds instances with ``model_construct`` and performs no per-value
        validation at all, so a mismatched type would simply sit in the field. Passing
        ``validate=True`` runs Pydantic's full pipeline per row at roughly 2-5x the cost and
        raises a ``ValidationError`` on the first bad row — but it does **not** protect a
        decimal column: it coerces a ``decimal128`` into a ``float`` field silently, losing
        the precision. Treat ``validate=True`` as a per-value check for genuinely
        untrustworthy data, never as the safe mode for money.

        Consumes the underlying Arrow stream, like ``fetch_arrow_table()``: pick one
        consumption pattern per cursor.

        Args:
            model: The Pydantic model to build. Any ``type[BaseModel]``.
            validate: Run Pydantic validation per row instead of the fast path. Passed
                straight through to arrowmodel. Defaults to False.

        Returns:
            A list of ``model`` instances, one per result row. Empty for a zero-row result.

        Raises:
            SemolinaMissingDependencyError: If pyarrow or arrowmodel is not installed.
            SemolinaSchemaMismatchError: If the model's annotations do not describe the
                result schema.

        Example:
            .. code-block:: python

                import decimal

                import pydantic


                class SalesDTO(pydantic.BaseModel):
                    region: str
                    total_order_value: decimal.Decimal


                with Sales.query().metrics(Sales.total_order_value).execute() as cursor:
                    rows = cursor.into(SalesDTO)
                # [SalesDTO(region='US', total_order_value=Decimal('43.25')), ...]
        """
        # pyarrow first: reading `description` without it raises ADBC's own ProgrammingError
        # from a _NoOpBackend, which names neither Semolina nor the extra that fixes it.
        _require("pyarrow", "pyarrow")
        _require("arrowmodel", "arrowmodel")

        from .dto import check_result_schema

        check_result_schema(self.description, model)

        from arrowmodel import model_convert

        # arrowmodel types model_convert as `-> list[BaseModel]`, which loses the concrete
        # model. A cast recovers it without a suppression comment.
        return cast(
            "list[_M]",
            model_convert(model, self.fetch_arrow_table(), validate=validate),
        )

    # -- DBAPI 2.0 passthrough properties --

    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """
        Cursor description passthrough.

        Returns:
            List of 7-element tuples describing columns, or None before execute.
        """
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        """
        Row count passthrough.

        Returns:
            Number of rows affected by the last operation.
        """
        return self._cursor.rowcount

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
                current batch is fully consumed. Also raised on re-iteration
                of an exhausted cursor or after ``fetch_arrow_table()``
                drains the underlying stream. Does NOT close the cursor.

        Returns:
            ``Row`` constructed from the next batch row, keyed by the batch
            schema's column names.
        """
        if self._stream_exhausted and self._batch_pos >= len(self._batch_rows):
            raise StopIteration
        if self._reader is None:
            try:
                self._reader = self._cursor.fetch_record_batch()
            except (StopIteration, OSError) as exc:
                # Underlying stream already drained (e.g. by fetch_arrow_table
                # or a prior full iteration). Treat as empty iterator.
                self._stream_exhausted = True
                raise StopIteration from exc
        reader = self._reader
        assert reader is not None  # narrowing for the type checker
        while self._batch_pos >= len(self._batch_rows):
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                self._stream_exhausted = True
                raise
            except OSError as exc:
                # ADBC drivers may surface drained-reader access as OSError
                # rather than StopIteration; normalise to iteration termination.
                self._stream_exhausted = True
                raise StopIteration from exc
            if batch.num_rows == 0:
                continue
            self._batch_rows = batch.to_pylist()
            self._batch_pos = 0
        row = Row(self._batch_rows[self._batch_pos])
        self._batch_pos += 1
        return row

    # -- Lifecycle --

    def close(self) -> None:
        """Close cursor and release connection."""
        self._cursor.close()
        self._conn.close()
        self._closed = True

    def __del__(self) -> None:
        """
        Best-effort finalizer that returns a leaked connection to the pool.

        Safety net for callers that obtain a cursor and neither ``close()`` it
        nor use the context manager: without this, the pooled connection (and
        its ``QueuePool`` slot) would not be reliably reclaimed by GC. Guarded
        against partial ``__init__`` (``_conn``/``_closed`` may be absent if
        construction raised) and double-close, and never raises — finalizers
        must not propagate exceptions. Prefer ``with ....execute() as cursor:``
        or an explicit ``close()``; this only covers the forgotten path.
        """
        if getattr(self, "_closed", True):
            return
        conn = getattr(self, "_conn", None)
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
        self._closed = True

    def __enter__(self) -> SemolinaCursor:
        """Enter context manager."""
        return self

    def __exit__(self, *exc: Any) -> None:
        """Exit context manager, closing cursor and connection."""
        self.close()

    def __repr__(self) -> str:
        """
        Return human-readable representation.

        Returns:
            String like ``<SemolinaCursor columns=['a', 'b'] open>``
            or ``<SemolinaCursor closed>``.
        """
        if self._closed:
            return "<SemolinaCursor closed>"
        columns = self._column_names()
        return f"<SemolinaCursor columns={columns} open>"
