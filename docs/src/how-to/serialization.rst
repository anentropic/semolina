.. _howto-serialization:

How to serialize results for API responses
==========================================

Semolina query results come back as :py:class:`~semolina.results.Row` objects. This guide
shows how to convert them to dictionaries and JSON for use in API responses.

Convert a Row to a dictionary
------------------------------

:py:class:`~semolina.results.Row` implements the mapping protocol (``__iter__`` yields keys,
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

.. warning:: Column keys are whatever your warehouse called them

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are the
   result column names exactly as the driver reports them. Only DuckDB happens to spell
   them like Python identifiers. The same query returns ``COUNTRY`` and ``AGG("REVENUE")``
   on Snowflake, and ``country`` and ``measure(revenue)`` on Databricks, so
   ``row.revenue`` raises ``AttributeError`` there. See
   :ref:`howto-result-column-names` before you deploy against a real warehouse.

The keys above are the DuckDB spelling. On Snowflake the same ``dict(row)`` produces
``{'AGG("REVENUE")': 1000, "COUNTRY": "US"}``, which is rarely the JSON you want to
return. Map the keys explicitly, as shown under `Select specific fields for the
response`_ below, or convert to a typed object with :ref:`howto-typed-results`.

You can also use ``.items()``, ``.keys()``, and ``.values()`` for fine-grained access:

.. code-block:: python

   # Using row from above
   row.keys()  # dict_keys(["revenue", "country"])
   row.values()  # dict_values([1000, "US"])
   row.items()  # dict_items([("revenue", 1000), ("country", "US")])

Convert a Row to JSON
---------------------

``json.dumps(dict(row))`` works only while every value happens to be a JSON-native
type. It is not safe for money. A metric over a ``DECIMAL`` column arrives as a
:py:class:`decimal.Decimal`, which the standard encoder refuses:

.. code-block:: python

   json.dumps(dict(row))
   # TypeError: Object of type Decimal is not JSON serializable

Give ``json.dumps()`` a ``default=`` encoder so it knows what to do with the types the
warehouse actually returns:

.. code-block:: python

   import datetime
   import decimal
   import json

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   def encode(value):
       """Encode warehouse types the standard JSON encoder does not handle."""
       if isinstance(value, decimal.Decimal):
           return str(value)
       if isinstance(
           value, (datetime.date, datetime.datetime)
       ):
           return value.isoformat()
       raise TypeError(
           f"Object of type {type(value).__name__} is not JSON serializable"
       )


   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   row = cursor.fetchone_row()
   json_str = json.dumps(dict(row), default=encode)
   # '{"revenue": "1234.56", "country": "US"}'

``str(value)`` keeps every digit, at the cost of sending the number as a JSON string.
``float(value)`` gives you a JSON number instead and loses precision: a value that
needs more than about 15 significant digits will not survive the round trip. Choose
per field, not globally. A chart axis can take the float; a ledger total cannot.

.. tip::

   Pydantic already handles ``Decimal``, so converting the result into typed objects
   with :ref:`howto-typed-results` avoids writing an encoder at all. In FastAPI, return
   the Pydantic objects and let the framework serialize them.

See :ref:`explanation-type-fidelity` for which columns arrive as a ``Decimal`` and why
Semolina does not convert them for you.

Serialize all rows at once
--------------------------

Use :py:meth:`~semolina.cursor.SemolinaCursor.fetchall_rows` with a list comprehension:

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

This pattern feeds a web framework's JSON response directly, as long as the values are
JSON-native. FastAPI's ``JSONResponse`` accepts a list of dictionaries, but it will
raise on a ``Decimal`` metric for the same reason ``json.dumps()`` does. Apply the
``default=`` encoder above, or return typed objects.

Stream results in batches with fetchmany_rows
----------------------------------------------

For large result sets, use :py:meth:`~semolina.cursor.SemolinaCursor.fetchmany_rows` to
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
:py:class:`~semolina.results.Row`:

.. code-block:: python

   rows = cursor.fetchall_rows()
   data = [
       {
           "country": row["COUNTRY"],
           "revenue": str(row['AGG("REVENUE")']),
       }
       for row in rows
   ]

This is also the place to give your API stable field names. The keys on the left are
yours; the keys on the right are the warehouse's, and only the left-hand ones belong in
a response your clients depend on.

Dict-style access (``row["COUNTRY"]``) reaches every column, whatever the warehouse
called it. Attribute access (``row.country``) only reaches a column whose name is
already a valid Python identifier: on Snowflake and Databricks that covers the
dimensions and none of the metrics, because ``AGG("REVENUE")`` and ``measure(revenue)``
are not identifiers. Write dict-style access in serialization code you intend to
deploy.

See also
--------

- :ref:`howto-queries` -- build queries and access results
- :ref:`howto-typed-results` -- convert a result into Pydantic objects, which serialize
  ``Decimal`` without an encoder
- :ref:`howto-result-column-names` -- what your warehouse calls each result column
- :ref:`explanation-type-fidelity` -- why a money column arrives as a ``Decimal``
- :ref:`explanation-duckdb-vs-warehouse` -- why the tutorial's ``json.dumps`` example
  works locally, and what changes against a warehouse
- :ref:`howto-web-api` -- use serialized results in FastAPI endpoints
- :ref:`howto-filtering` -- filter queries before serialization
