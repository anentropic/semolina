.. _howto-arrow-output:

How to retrieve results as Arrow tables
========================================

Query results can be fetched as a PyArrow Table instead of individual
:py:class:`~semolina.Row` objects. This gives you zero-copy interop with
Pandas and Polars, and works with any ADBC-backed pool (Snowflake,
Databricks, DuckDB).

If a dataframe is what you actually want, go straight to
:py:meth:`~semolina.SemolinaCursor.fetch_df` or
:py:meth:`~semolina.SemolinaCursor.fetch_polars` and skip the table. Both
are covered below.

Fetch an Arrow table
--------------------

Call :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` on the cursor
returned by ``.execute()``:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   table = cursor.fetch_arrow_table()
   print(type(table))
   # <class 'pyarrow.lib.Table'>
   print(table.schema)
   # country: string
   # revenue: int64

``fetch_arrow_table()`` delegates to the underlying ADBC cursor, which
builds the table through a ``pyarrow.RecordBatchReader``. That needs
pyarrow (``pip install semolina[pyarrow]``); ``semolina[duckdb]`` brings
it along, so a DuckDB install already has it.

Fetch a Pandas DataFrame
------------------------

Call :py:meth:`~semolina.SemolinaCursor.fetch_df` on the cursor:

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

This requires pandas and pyarrow (``pip install
"semolina[pandas,pyarrow]"``). The ADBC driver does the conversion
itself, through ``reader.read_pandas()``, so Semolina converts nothing on
the way and a long fetch stays interruptible.

Fetch a Polars DataFrame
------------------------

:py:meth:`~semolina.SemolinaCursor.fetch_polars` is the polars
equivalent:

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

This requires polars and nothing else (``pip install
semolina[polars]``). ADBC hands polars the result's raw Arrow PyCapsule
stream rather than building a table first, so no pyarrow is involved at
any point on this path.

.. warning::

   ``fetch_polars()`` has to be the first consuming call on the cursor.
   ADBC *takes* the cursor's Arrow stream handle and leaves ``None``
   behind, so anything that already created a reader -- iterating the
   cursor, ``fetch_record_batch()``, ``fetch_arrow_table()``, ``into()``
   or ``iter_into()`` -- leaves it nothing, and the call raises the
   driver's own ``ProgrammingError("Result set has been closed or
   consumed")``. Calling ``fetch_polars()`` twice fails the same way.
   Reading ``description`` first is safe.

Decimals differ between the two
--------------------------------

A ``DECIMAL`` metric keeps its precision on both routes, but only one of
them keeps its type.

polars gives a warehouse ``decimal128(38, 2)`` column a native
``Decimal(precision=38, scale=2)`` dtype holding
:py:class:`decimal.Decimal` values, measured on this project's own
type-fidelity probe at polars 1.43.2. pandas has no decimal dtype, so the
same column falls back to an ``object`` column of
:py:class:`decimal.Decimal` values: the values are intact, the column is
untyped.

That makes ``fetch_polars()`` the better route for money. One condition
is recorded because it is reachable in principle and not in practice:
polars was measured raising a Rust ``PanicException`` on a
``decimal256`` column, and no backend Semolina supports has been
observed producing one. A Snowflake ``NUMBER`` stops at precision 38, and
Databricks and DuckDB decimals stop there too.

Convert a table you already hold
---------------------------------

If you have a ``pyarrow.Table`` for some other reason, converting it
directly still works and is the right call:

.. code-block:: python

   df = table.to_pandas()

   import polars as pl

   df = pl.from_arrow(table)

Reach for ``fetch_df()`` and ``fetch_polars()`` when the dataframe is the
goal. Reach for these two when the table is.

When to use Arrow output
------------------------

- Use ``fetch_df()`` or ``fetch_polars()`` when you want a dataframe.
- Use ``fetch_arrow_table()`` when you want the Arrow table itself, to
  inspect the result schema or hand to another Arrow consumer.
- Use ``fetchall_rows()`` when working with individual rows or
  serializing to JSON.
- Use :py:meth:`~semolina.SemolinaCursor.into` when you want typed
  objects. See :ref:`howto-typed-results`.
- Arrow output skips the per-row Python object creation that
  ``fetchall_rows()`` performs, which matters for larger result sets.

All four consume the same underlying stream, so pick one per cursor.

See also
--------

- :ref:`howto-streaming` -- stream Arrow batches and iterate rows lazily
- :ref:`howto-typed-results` -- convert a result into Pydantic instances
- :ref:`howto-serialization` -- serialize Row objects to dictionaries and JSON
- :ref:`explanation-type-fidelity` -- why a money column arrives as a ``Decimal``
- :ref:`howto-queries` -- build queries and access results
- :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` -- API reference
- :py:meth:`~semolina.SemolinaCursor.fetch_df` -- API reference
- :py:meth:`~semolina.SemolinaCursor.fetch_polars` -- API reference
