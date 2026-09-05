.. _howto-streaming:

How to fetch results in bulk
=============================

A large result forces one choice: take the whole thing in a single call, or pull it a batch
at a time. :py:class:`~semolina.cursor.SemolinaCursor` does both, and the answer turns on how
big the result is and what you are handing it to.

Fetch the whole result when it fits comfortably in memory and the consumer wants it whole --
pandas, polars, or another Arrow consumer. Fetch it in batches when it does not fit, when you
want to start work before the warehouse has finished computing the rest, or when the thing
downstream is itself streaming.

This guide assumes you already have a :py:class:`~semolina.models.SemanticView` subclass and
a registered engine. See :ref:`howto-queries` if you need setup first. Every snippet reuses
this model:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()

.. _howto-arrow-output:

Fetch the whole result
----------------------

Three methods materialize the entire result in one call, differing only in what they hand
back: an Arrow table, a pandas frame, or a polars frame. Each works with any ADBC-backed
engine (Snowflake, Databricks, DuckDB), and each skips the per-row Python object creation
that ``fetchall_rows()`` performs.

If a dataframe is what you actually want, go straight to
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_df` or
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_polars` and skip the table.

Fetch an Arrow table
~~~~~~~~~~~~~~~~~~~~~

Call :py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table` on the cursor returned by
``.execute()``:

.. code-block:: python

   with (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   ) as cursor:
       table = cursor.fetch_arrow_table()

   print(type(table))
   # <class 'pyarrow.lib.Table'>
   print(table.schema)
   # country: string
   # revenue: int64

``fetch_arrow_table()`` delegates to the underlying ADBC cursor, which builds the table
through a ``pyarrow.RecordBatchReader``. That needs PyArrow (``pip install
semolina[pyarrow]``); ``semolina[duckdb]`` brings it along, so a DuckDB install already has
it.

Fetch a pandas DataFrame
~~~~~~~~~~~~~~~~~~~~~~~~~

Call :py:meth:`~semolina.cursor.SemolinaCursor.fetch_df` on the cursor:

.. code-block:: python

   with (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   ) as cursor:
       df = cursor.fetch_df()

   print(type(df))
   # <class 'pandas.core.frame.DataFrame'>

Install it with ``pip install "semolina[pandas]"``, which brings PyArrow along because the ADBC
driver does the conversion itself through ``reader.read_pandas()``, and that reader is a
PyArrow one. Semolina converts nothing on the way, so a long fetch stays interruptible.

Fetch a polars DataFrame
~~~~~~~~~~~~~~~~~~~~~~~~~

:py:meth:`~semolina.cursor.SemolinaCursor.fetch_polars` is the polars equivalent:

.. code-block:: python

   with (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   ) as cursor:
       df = cursor.fetch_polars()

   print(type(df))
   # <class 'polars.dataframe.frame.DataFrame'>

This requires polars and nothing else (``pip install "semolina[polars]"``). ADBC hands polars
the result's raw Arrow PyCapsule stream rather than building a table first, so no PyArrow is
involved at any point on this path.

.. warning::

   ``fetch_polars()`` has to be the first consuming call on the cursor. ADBC *takes* the
   cursor's Arrow stream handle and leaves ``None`` behind, so anything that already created
   a reader -- iterating the cursor, ``fetch_record_batch()``, ``fetch_arrow_table()``,
   ``into()`` or ``iter_into()`` -- leaves it nothing, and the call raises the driver's own
   ``ProgrammingError("Result set has been closed or consumed")``. Calling ``fetch_polars()``
   twice fails the same way. Reading ``description`` first is safe.

Decimals differ between pandas and polars
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``DECIMAL`` metric keeps its precision on both routes, but only one of them keeps its type.

polars gives a warehouse ``decimal128(38, 2)`` column a native ``Decimal(precision=38,
scale=2)`` dtype holding :py:class:`decimal.Decimal` values, observed at polars 1.43.2.
pandas has no decimal dtype, so the same column falls back to an ``object`` column of
:py:class:`decimal.Decimal` values: the values are intact, the column is untyped.

That makes ``fetch_polars()`` the better route for money. One condition is reachable in
principle and not in practice: polars raises a Rust ``PanicException`` on a ``decimal256``
column, and no backend Semolina supports produces one. A Snowflake ``NUMBER`` stops at
precision 38, and Databricks and DuckDB decimals stop there too.

See :ref:`explanation-type-fidelity` for why the warehouse, not Semolina, decides this.

Convert a table you already hold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a ``pyarrow.Table`` for some other reason, converting it directly still works and
is the right call:

.. code-block:: python

   df = table.to_pandas()

   import polars as pl

   df = pl.from_arrow(table)

Reach for ``fetch_df()`` and ``fetch_polars()`` when the dataframe is the goal. Reach for
``to_pandas()`` and ``pl.from_arrow()`` when you already hold the table.

Fetch a whole result in async code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:meth:`~semolina.acursor.AsyncSemolinaCursor.fetch_arrow_table` is awaited, and
materializes the whole result off the event loop:

.. code-block:: python

   async with await (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .aexecute()
   ) as cursor:
       table = await cursor.fetch_arrow_table()
       df = table.to_pandas()

One detail is specific to async: awaiting ``fetch_arrow_table()`` creates no live Arrow
reader, so it places no constraint on close ordering, while a streaming cursor holds a reader
that must be closed before its connection. ``async with`` handles that ordering for you
either way.

Fetch the result in batches
---------------------------

:py:class:`~semolina.cursor.SemolinaCursor` has three incremental entry points:
``fetch_record_batch()`` for Arrow batches, ``for row in cursor:`` for lazy ``Row`` iteration,
and ``iter_into()`` for typed instances. All three have counterparts on
:py:class:`~semolina.acursor.AsyncSemolinaCursor`.

Stream record batches with fetch_record_batch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Call :py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` on the cursor returned by
``.execute()`` to get a ``pyarrow.RecordBatchReader``:

.. code-block:: python

   with Sales.query().metrics(
       Sales.revenue
   ).execute() as cursor:
       reader = cursor.fetch_record_batch()
       for batch in reader:
           if batch.num_rows == 0:
               continue
           process(batch)

The reader is lazy: each ``RecordBatch`` arrives as the warehouse produces it, and only one
batch is in memory at a time. Some ADBC drivers emit zero-row batches before or between data
batches, so a direct reader consumer should skip ``batch.num_rows == 0`` itself.

Iterate rows lazily with ``for row in cursor:``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want :py:class:`~semolina.results.Row` objects rather than raw Arrow batches, iterate
the cursor directly:

.. code-block:: python

   with Sales.query().metrics(
       Sales.revenue
   ).execute() as cursor:
       for row in cursor:
           handle(row)

Each row is constructed lazily from the underlying ``RecordBatchReader``.
:py:class:`~semolina.cursor.SemolinaCursor` skips empty batches for you and treats a drained
reader as a clean ``StopIteration``, so cursor iteration is the safer choice when you just
want rows.

Reach a column with ``row["revenue"]`` rather than ``row.revenue`` in code you intend to
deploy. Semolina adds no ``AS`` aliases, so the result column carries whatever name the
warehouse gave the expression, and only DuckDB's spelling happens to be a valid Python
identifier. See :ref:`howto-result-column-names` for the name each backend returns.

Stream typed instances with iter_into
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your downstream code wants Pydantic objects rather than
:py:class:`~semolina.results.Row` mappings,
:py:meth:`~semolina.cursor.SemolinaCursor.iter_into` streams them one at a time while
converting a whole Arrow batch at a time:

.. code-block:: python

   for dto in cursor.iter_into(RevenueByCountry):
       handle(dto)

It drives the same single underlying stream as the other two, so the
pick-one-consumption-pattern rule in `Backend notes`_ applies to it unchanged. Unlike a
generator function, it raises on the ``iter_into(...)`` line if the DTO does not describe the
result. :ref:`howto-typed-results` covers the DTO, the async form, and the column-naming trap
that bites when you move off DuckDB.

Feed a downstream sink
~~~~~~~~~~~~~~~~~~~~~~~

This is the canonical batched pattern: a query reader piped straight into another writer,
with peak memory bounded by one batch. Here it writes Parquet via
``pyarrow.parquet.ParquetWriter``:

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

The same shape works for any downstream sink that accepts Arrow batches: an HTTP chunked
response body, a message queue producer, an iterative file writer. Hold the cursor open until
the writer finishes (the ``with`` block does this for you).

Iterate rows lazily with ``async for row in cursor:``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In async code, execute the query with ``aexecute()`` and iterate the returned
:py:class:`~semolina.acursor.AsyncSemolinaCursor` with ``async for``:

.. code-block:: python

   async with await Sales.query().metrics(
       Sales.revenue
   ).aexecute() as cursor:
       async for row in cursor:
           await handle(row)

The contract matches the synchronous form exactly. Iteration is single-pass, batches are
pulled one at a time rather than up front, empty batches are skipped for you, and reaching
the end of the stream does not close the cursor.

What changes is where the work happens. adbc-poolhouse pulls each batch on a worker thread,
so the event loop is free while the warehouse computes it and other requests keep being
served. Semolina then maps that batch to :py:class:`~semolina.results.Row` objects on the
loop thread, so row mapping is the one part of the round trip that is not offloaded. It is
cheap relative to the fetch, and it is bounded by one batch rather than by the whole result.

.. warning::

   Close an async cursor with ``async with`` or ``await cursor.aclose()``. Unlike
   :py:class:`~semolina.cursor.SemolinaCursor`, the async cursor has no finalizer that can
   reclaim a forgotten connection, so one that is never closed holds its pooled connection
   permanently. See :ref:`howto-web-api-async-cursor-close` for the full reason.

.. _howto-streaming-async-cancel:

Cancel an async stream mid-iteration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Long streams outlive their callers. The realistic shape puts the cancellation scope around
the whole block, so it can fire while you are part way through the rows:

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

Choose between the two
----------------------

:py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table` materializes the full result in
memory as a single ``pyarrow.Table``. That is the right shape when you want to hand the
result to pandas, polars, or another Arrow consumer in one go and the result fits
comfortably.

:py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` and ``for row in cursor:`` keep
only one batch in memory and let you start processing the first batch before the warehouse
has finished computing the rest. That second property matters for end-to-end latency when the
warehouse is slow or the result is large.

The same trade-off holds on the async path, between ``await cursor.fetch_arrow_table()`` and
``async for row in cursor:``.

Which method within each half depends on the shape you want, not on the size:

- ``fetch_df()`` or ``fetch_polars()`` when you want a dataframe.
- ``fetch_arrow_table()`` when you want the Arrow table itself, to inspect the result schema
  or hand to another Arrow consumer.
- ``fetchall_rows()`` when you are working with individual rows or serializing to JSON.
- :py:meth:`~semolina.cursor.SemolinaCursor.into` when you want typed objects, and
  ``iter_into()`` for the same objects one at a time. See :ref:`howto-typed-results`.

Backend notes
-------------

Both halves are normalized across Snowflake, Databricks, and DuckDB through ADBC. There is no
Semolina-side code path that differs by backend. A few behaviours are worth knowing:

- **Shared state between fetch methods.** ``fetch_record_batch()``, ``fetch_arrow_table()``,
  ``fetch_df()``, ``fetch_polars()``, ``fetchone()``, ``into()``, ``iter_into()`` and
  iterating the cursor all consume from the same underlying ADBC stream. Pick one
  consumption pattern per cursor and finish it before switching. What a *second* consumer
  does depends on which one it is:

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

  The split follows the mechanism. ADBC *takes* the stream handle and leaves ``None``
  behind, so a method that asks the driver for it a second time finds nothing and says so.
  Cursor iteration and ``iter_into()`` read through a reader the cursor already holds, find
  it empty, and stop, because :py:class:`~semolina.cursor.SemolinaCursor` turns the drained
  reader's ``OSError`` into ``StopIteration`` on your behalf. ``fetch_record_batch()`` sits
  between the two: it hands you the raw reader with nothing wrapping it, so the call returns
  and the ``OSError`` surfaces on the first batch you pull. The error classes belong to the
  driver and vary by backend: measured against DuckDB on 2026-09-04, ``fetch_polars()``
  raises ``ProgrammingError("Result set has been closed or consumed")`` and the rest raise
  ``InternalError``. `Fetch a polars DataFrame`_ has the warning about calling it first.
- **Drained-stream semantics.** After ``fetch_arrow_table()`` runs, iterating the cursor
  yields zero rows (no error). Re-iterating an already-consumed cursor also yields zero rows.
  :py:class:`~semolina.cursor.SemolinaCursor` normalizes the underlying ADBC ``OSError`` on
  drained readers to a standard ``StopIteration``, so a ``for`` loop over a spent cursor ends
  the way any other exhausted iterator does.
  :py:class:`~semolina.acursor.AsyncSemolinaCursor` normalizes it to ``StopAsyncIteration``
  for the same reason.

  That normalization covers iteration, and only iteration. Do not read it as the DBAPI
  ``fetchone() -> None`` convention:
  :py:meth:`~semolina.cursor.SemolinaCursor.fetchone` returns ``None`` exactly once past the
  end of a result you consumed row by row, then raises the driver's error on the call after
  that, and raises on the very first call if another consumer already took the stream.
  Measured against DuckDB on 2026-09-04. Iterate the cursor rather than looping until
  ``fetchone()`` returns ``None``.
- **Empty batches mid-stream.** Some ADBC drivers emit zero-row batches before or between
  data batches. Cursor iteration skips them for you; if you consume the
  ``RecordBatchReader`` directly via ``fetch_record_batch()``, skip ``batch.num_rows == 0``
  batches yourself.
- **Batch sizes.** Batch size is controlled by the ADBC driver and the warehouse, not by
  Semolina. The Snowflake ADBC driver defaults to roughly 200 queued batches with up to 10
  concurrent streams; DuckDB and Databricks use their own driver-determined chunking.
  User-tunable batch sizes are not exposed in this release.
- **Cursor lifetime.** The ``RecordBatchReader`` depends on the cursor and its connection
  staying alive. Consume the reader inside the ``with`` block (or before ``cursor.close()``).
  Returning the reader from a closed cursor produces undefined behaviour (arrow-adbc issue
  #1893).

See also
--------

- :ref:`tutorial-dashboard-api` -- one query's result fetched whole and sent to a browser
- :ref:`howto-typed-results` -- convert a result into Pydantic instances, whole or streamed
- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-web-api` -- async endpoints, engine lifecycle, timeouts, and cursor closing
- :ref:`the untyped route <howto-serialization>` -- ``fetchmany_rows()`` batching, and
  ``dict(row)`` for a response body
- :ref:`explanation-type-fidelity` -- why a money column arrives as a ``Decimal``
- :ref:`tutorial-installation-result-extras` -- which extra each fetch method needs
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table` -- API reference
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_df` -- API reference
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_polars` -- API reference
- :py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` -- API reference
- :py:class:`~semolina.cursor.SemolinaCursor` -- cursor class reference
- :py:class:`~semolina.acursor.AsyncSemolinaCursor` -- async cursor class reference
