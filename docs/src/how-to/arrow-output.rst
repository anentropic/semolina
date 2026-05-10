.. _howto-arrow-output:

How to retrieve results as Arrow tables
========================================

Query results can be fetched as a PyArrow Table instead of individual
:py:class:`~semolina.Row` objects. This gives you zero-copy interop with
Pandas and Polars, and works with any ADBC-backed pool (Snowflake,
Databricks, DuckDB).

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

``fetch_arrow_table()`` delegates to the underlying ADBC cursor. No
extra dependencies beyond the backend driver are needed.

Convert to a Pandas DataFrame
-----------------------------

PyArrow tables have a built-in ``to_pandas()`` method:

.. code-block:: python

   df = table.to_pandas()
   print(type(df))
   # <class 'pandas.core.frame.DataFrame'>

This requires pandas (``pip install pandas``). PyArrow uses zero-copy
conversion where column types allow it; some types require a copy.

Convert to a Polars DataFrame
-----------------------------

Polars accepts PyArrow tables directly through ``pl.from_arrow()``:

.. code-block:: python

   import polars as pl

   df = pl.from_arrow(table)
   print(type(df))
   # <class 'polars.dataframe.frame.DataFrame'>

This requires polars (``pip install polars``). The conversion is
zero-copy and does not depend on pandas.

When to use Arrow output
------------------------

- Use ``fetch_arrow_table()`` when passing results to Pandas, Polars,
  or other Arrow-compatible tools.
- Use ``fetchall_rows()`` when working with individual rows or
  serializing to JSON.
- Arrow output skips the per-row Python object creation that
  ``fetchall_rows()`` performs, which matters for larger result sets.

See also
--------

- :ref:`howto-serialization` -- serialize Row objects to dictionaries and JSON
- :ref:`howto-queries` -- build queries and access results
- :py:meth:`~semolina.SemolinaCursor.fetch_arrow_table` -- API reference
