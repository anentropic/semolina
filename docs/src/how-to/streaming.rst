.. _howto-streaming:

How to stream large results
============================

Use streaming when a query result is too large to comfortably hold in
memory, or when your downstream code already processes data in chunks.
This page shows the three streaming entry points on
:py:class:`~semolina.cursor.SemolinaCursor` (``fetch_record_batch()`` for Arrow
batches, ``for row in cursor:`` for lazy ``Row`` iteration, and
``iter_into()`` for typed instances), their async counterparts on
:py:class:`~semolina.acursor.AsyncSemolinaCursor`, a small end-to-end example
writing batches to a Parquet file, and the rule of thumb for choosing
between streaming and ``fetch_arrow_table()``.

This guide assumes you already have a :py:class:`~semolina.models.SemanticView`
subclass and a registered engine. See :ref:`howto-queries` if you need
setup first.

The snippets reuse this model:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()

Stream record batches with fetch_record_batch
----------------------------------------------

Call :py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` on the cursor
returned by ``.execute()`` to get a ``pyarrow.RecordBatchReader``:

.. code-block:: python

   with Sales.query().metrics(
       Sales.revenue
   ).execute() as cursor:
       reader = cursor.fetch_record_batch()
       for batch in reader:
           if batch.num_rows == 0:
               continue
           process(batch)

The reader is lazy: each ``RecordBatch`` arrives as the warehouse
produces it, and only one batch is in memory at a time. Some ADBC
drivers emit zero-row batches before or between data batches, so a
direct reader consumer should skip ``batch.num_rows == 0`` itself.

Iterate rows lazily with ``for row in cursor:``
------------------------------------------------

If you want :py:class:`~semolina.results.Row` objects rather than raw Arrow
batches, iterate the cursor directly:

.. code-block:: python

   with Sales.query().metrics(
       Sales.revenue
   ).execute() as cursor:
       for row in cursor:
           handle(row)

Each row is constructed lazily from the underlying
``RecordBatchReader``. :py:class:`~semolina.cursor.SemolinaCursor` skips
empty batches for you and treats a drained reader as a clean
``StopIteration``, so cursor iteration is the safer choice when you
just want rows.

Stream typed instances with iter_into
--------------------------------------

If your downstream code wants Pydantic objects rather than
:py:class:`~semolina.results.Row` mappings,
:py:meth:`~semolina.cursor.SemolinaCursor.iter_into` streams them one at a time
while converting a whole Arrow batch at a time:

.. code-block:: python

   for dto in cursor.iter_into(RevenueByCountry):
       handle(dto)

It drives the same single underlying stream as the other two, so the
pick-one-consumption-pattern rule below applies to it unchanged. Unlike
a generator function, it raises on the ``iter_into(...)`` line if the DTO
does not describe the result. :ref:`howto-typed-results` covers the DTO,
the async form, and the column-naming trap that bites when you move off
DuckDB.

Iterate rows lazily with ``async for row in cursor:``
------------------------------------------------------

In async code, execute the query with ``aexecute()`` and
iterate the returned :py:class:`~semolina.acursor.AsyncSemolinaCursor` with
``async for``:

.. code-block:: python

   async with await Sales.query().metrics(
       Sales.revenue
   ).aexecute() as cursor:
       async for row in cursor:
           await handle(row)

The contract matches the synchronous form exactly. Iteration is
single-pass, batches are pulled one at a time rather than up front,
empty batches are skipped for you, and reaching the end of the stream
does not close the cursor.

What changes is where the work happens. adbc-poolhouse pulls each
batch on a worker thread, so the event loop is free while the
warehouse computes it and other requests keep being served.
Semolina then maps that batch to :py:class:`~semolina.results.Row` objects
on the loop thread, so row mapping is the one part of the round trip
that is not offloaded. It is cheap relative to the fetch, and it is
bounded by one batch rather than by the whole result.

.. warning::

   Close an async cursor with ``async with`` or ``await cursor.aclose()``.
   Unlike :py:class:`~semolina.cursor.SemolinaCursor`, the async cursor has no
   finalizer that can reclaim a forgotten connection, so one that is never
   closed holds its pooled connection permanently. See
   :ref:`howto-web-api-async-cursor-close` for the full reason.

.. _howto-streaming-async-cancel:

Cancel an async stream mid-iteration
-------------------------------------

Long streams outlive their callers. The realistic shape puts the cancellation scope
around the whole block, so it can fire while you are part way through the rows:

.. code-block:: python

   import anyio

   with anyio.move_on_after(30):
       async with await Sales.query().metrics(
           Sales.revenue
       ).aexecute() as cursor:
           async for row in cursor:
               await handle(row)

A cancellation raised inside the ``async for`` body propagates out of the iteration. The
loop stops at the row it was handling. The async cursor does not convert the cancellation
into a ``StopAsyncIteration``, and does not swallow it: what leaves the block is the
cancellation itself.

The ordered close still holds when the cancellation arrives during teardown, which in the
snippet above it does. ``async with`` closes the reader, then the cursor, then the
connection, and each step suppresses ``Exception`` rather than ``BaseException``. A
cancellation passing through teardown therefore survives it, and a teardown error (a
``ConnectionBusyError`` from closing a connection under a live reader, most plausibly)
does not take the place of the exception you need to see.

The pooled connection goes back. After a cancelled iteration the cursor is closed and the
pool's checked-out count returns to zero, so cancelling a stream does not leak a slot.
Forgetting to close the cursor does, and that hazard is described once, under
:ref:`howto-web-api-async-cursor-close`.

For what a deadline does to the statement that is still executing, including the abort
that reaches the driver and what becomes of the connection it ran on, see
:ref:`howto-web-api-timeouts`.

Feed a downstream sink
----------------------

This is the canonical streaming pattern: a query reader piped straight
into another writer, with peak memory bounded by one batch. Here it
writes Parquet via ``pyarrow.parquet.ParquetWriter``:

.. code-block:: python

   import pyarrow.parquet as pq

   with Sales.query().metrics(
       Sales.revenue
   ).execute() as cursor:
       reader = cursor.fetch_record_batch()
       with pq.ParquetWriter(
           "sales.parquet", reader.schema
       ) as writer:
           for batch in reader:
               if batch.num_rows == 0:
                   continue
               writer.write_batch(batch)

The same shape works for any downstream sink that accepts Arrow batches:
an HTTP chunked response body, a message queue producer, an iterative
file writer. Hold the cursor open until the writer finishes (the ``with``
block does this for you).

When to stream vs. fetch_arrow_table
-------------------------------------

:py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table` materializes the
full result in memory as a single ``pyarrow.Table``. That is the right
shape when you want to hand the result to pandas, polars, or another
Arrow consumer in one go and the result fits comfortably.

Streaming with :py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch`
or ``for row in cursor:`` keeps only one batch in memory and lets you
start processing the first batch before the warehouse has finished
computing the rest. That second property matters for end-to-end
latency when the warehouse is slow or the result is large.

The same choice exists on the async path, with the same trade-off.
:py:meth:`~semolina.acursor.AsyncSemolinaCursor.fetch_arrow_table` is awaited
and materializes the whole result off the event loop:

.. code-block:: python

   async with await Sales.query().metrics(
       Sales.revenue
   ).aexecute() as cursor:
       table = await cursor.fetch_arrow_table()
       df = table.to_pandas()

Prefer it when the result fits comfortably and you want one
``pyarrow.Table``; prefer ``async for row in cursor:`` when it does not,
or when you want to start work on the first batch early. One detail is
specific to async: awaiting ``fetch_arrow_table()`` creates no live
Arrow reader, so it places no constraint on close ordering, while a
streaming cursor holds a reader that must be closed before its
connection. ``async with`` handles that ordering for you either way.

.. tip::

   **Rule of thumb.** Materialize with ``fetch_arrow_table()`` when the
   result fits comfortably in memory and you want a single
   ``pyarrow.Table`` to hand to pandas, polars, or another Arrow
   consumer. Stream with ``fetch_record_batch()`` or
   ``for row in cursor:`` when the result is larger than memory,
   when you want to start processing the first batch before the
   warehouse has finished computing the rest (latency), or when the
   downstream sink is itself streaming (downstream consumer pattern --
   HTTP chunked response, Parquet writer, message queue).

Backend notes
-------------

Streaming is normalized across Snowflake, Databricks, and DuckDB through
ADBC. There is no Semolina-side code path that differs by backend. A few
behaviours are worth knowing:

- **Shared state with other fetch methods.** ``fetch_record_batch()``,
  ``fetch_arrow_table()``, ``fetch_df()``, ``fetch_polars()``,
  ``fetchone()``, ``into()``, ``iter_into()`` and iterating the cursor
  all consume from the same underlying ADBC stream. Pick one
  consumption pattern per cursor and finish it before switching. What
  a *second* consumer does depends on which one it is:

  .. list-table::
     :header-rows: 1
     :widths: 50 50

     * - Second consumer
       - On an already-drained stream
     * - Iterating the cursor, ``iter_into()``
       - Zero rows, no error
     * - ``fetch_record_batch()``
       - Hands back a reader; iterating that reader raises ``OSError``
     * - ``fetch_arrow_table()``, ``into()``, ``fetch_df()``,
         ``fetch_polars()``, ``fetchone()``
       - Raises the driver's own error

  The split follows the mechanism. ADBC *takes* the stream handle and
  leaves ``None`` behind, so a method that asks the driver for it a
  second time finds nothing and says so. Cursor iteration and
  ``iter_into()`` read through a reader the cursor already holds, find
  it empty, and stop, because
  :py:class:`~semolina.cursor.SemolinaCursor` turns the drained
  reader's ``OSError`` into ``StopIteration`` on your behalf.
  ``fetch_record_batch()`` sits between the two: it hands you the raw
  reader with nothing wrapping it, so the call returns and the
  ``OSError`` surfaces on the first batch you pull. The error classes
  belong to the driver and vary by backend: measured against DuckDB on
  2026-08-16, ``fetch_polars()`` raises
  ``ProgrammingError("Result set has been closed or consumed")`` and
  the rest raise ``InternalError``. See the warning in
  :ref:`howto-arrow-output`.
- **Drained-stream semantics.** After ``fetch_arrow_table()`` runs,
  iterating the cursor yields zero rows (no error). Re-iterating an
  already-consumed cursor also yields zero rows.
  :py:class:`~semolina.cursor.SemolinaCursor` normalizes the underlying
  ADBC ``OSError`` on drained readers to a standard ``StopIteration``,
  so a ``for`` loop over a spent cursor ends the way any other
  exhausted iterator does.
  :py:class:`~semolina.acursor.AsyncSemolinaCursor` normalizes it to
  ``StopAsyncIteration`` for the same reason.

  That normalization covers iteration, and only iteration. Do not read
  it as the DBAPI ``fetchone() -> None`` convention:
  :py:meth:`~semolina.cursor.SemolinaCursor.fetchone` returns ``None``
  exactly once past the end of a result you consumed row by row, then
  raises the driver's error on the call after that, and raises on the
  very first call if another consumer already took the stream. Measured
  against DuckDB on 2026-08-16. Iterate the cursor rather than looping
  until ``fetchone()`` returns ``None``.
- **Empty batches mid-stream.** Some ADBC drivers emit zero-row
  batches before or between data batches. Cursor iteration skips
  them for you; if you consume the ``RecordBatchReader`` directly
  via ``fetch_record_batch()``, skip ``batch.num_rows == 0`` batches
  yourself.
- **Batch sizes.** Batch size is controlled by the ADBC driver and the
  warehouse, not by Semolina. The Snowflake ADBC driver defaults to
  roughly 200 queued batches with up to 10 concurrent streams; DuckDB
  and Databricks use their own driver-determined chunking. User-tunable
  batch sizes are not exposed in this release.
- **Cursor lifetime.** The ``RecordBatchReader`` depends on the cursor
  and its connection staying alive. Consume the reader inside the
  ``with`` block (or before ``cursor.close()``). Returning the reader
  from a closed cursor produces undefined behaviour (arrow-adbc issue
  #1893).

See also
--------

- :ref:`howto-arrow-output` -- materialize results as a PyArrow Table
- :ref:`howto-typed-results` -- stream Pydantic instances with ``iter_into()``
- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-web-api` -- async endpoints, engine lifecycle, timeouts, and cursor closing
- :ref:`howto-serialization` -- convert Row objects to dictionaries and JSON
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` -- API reference
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table` -- API reference
- :py:class:`~semolina.cursor.SemolinaCursor` -- cursor class reference
- :py:class:`~semolina.acursor.AsyncSemolinaCursor` -- async cursor class reference
