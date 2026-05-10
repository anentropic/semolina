.. _howto-serialization:

How to serialize results for API responses
==========================================

Semolina query results come back as :py:class:`~semolina.Row` objects. This guide
shows how to convert them to dictionaries and JSON for use in API responses.

Convert a Row to a dictionary
------------------------------

:py:class:`~semolina.Row` implements the mapping protocol (``__iter__`` yields keys,
``__getitem__`` returns values), so ``dict()`` converts it directly:

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

   row = cursor.fetchone_row()
   data = dict(row)
   # {"revenue": 1000, "country": "US"}

You can also use ``.items()``, ``.keys()``, and ``.values()`` for fine-grained access:

.. code-block:: python

   # Using row from above
   row.keys()  # dict_keys(["revenue", "country"])
   row.values()  # dict_values([1000, "US"])
   row.items()  # dict_items([("revenue", 1000), ("country", "US")])

Convert a Row to JSON
---------------------

Combine ``dict()`` with ``json.dumps()`` for JSON serialization:

.. code-block:: python

   import json

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

   row = cursor.fetchone_row()
   json_str = json.dumps(dict(row))
   # '{"revenue": 1000, "country": "US"}'

Serialize all rows at once
--------------------------

Use :py:meth:`~semolina.SemolinaCursor.fetchall_rows` with a list comprehension:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   rows = cursor.fetchall_rows()
   data = [dict(row) for row in rows]
   # [{"revenue": 1000, "country": "US"}, {"revenue": 2000, "country": "CA"}]

This pattern works directly with web framework JSON responses -- FastAPI's
``JSONResponse``, for example, accepts a list of dictionaries.

Stream results in batches with fetchmany_rows
----------------------------------------------

For large result sets, use :py:meth:`~semolina.SemolinaCursor.fetchmany_rows` to
process rows in fixed-size batches without loading everything into memory:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   while True:
       batch = cursor.fetchmany_rows(100)
       if not batch:
           break
       chunk = [dict(row) for row in batch]
       # Process or send chunk

This is useful when streaming results over HTTP (e.g. server-sent events or
newline-delimited JSON) or when memory is constrained.

Select specific fields for the response
-----------------------------------------

When you need a subset of fields in the response, use dictionary comprehension on each
:py:class:`~semolina.Row`:

.. code-block:: python

   rows = cursor.fetchall_rows()
   data = [
       {"country": row.country, "revenue": row.revenue}
       for row in rows
   ]

Attribute access (``row.country``) and dict-style access (``row["country"]``) both work.
Use whichever fits your style -- attribute access is more concise, dict-style access
allows dynamic field names.

See also
--------

- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-web-api` -- use serialized results in FastAPI endpoints
- :ref:`howto-filtering` -- filter queries before serialization
