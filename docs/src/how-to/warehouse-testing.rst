.. _howto-warehouse-testing:

How to test application code with MockEngine
==============================================

Test query logic without connecting to a real warehouse. :py:class:`~semolina.MockEngine`
accepts fixture data and evaluates queries in-memory, so your application code works
identically in tests and production.

Set up MockEngine
-----------------

Create a :py:class:`~semolina.MockEngine`, load fixture data keyed by view name, and
register it:

.. code-block:: python

   from semolina import MockEngine, register

   engine = MockEngine()
   engine.load(
       "sales",
       [
           {"revenue": 1000, "country": "US"},
           {"revenue": 2000, "country": "CA"},
       ],
   )
   register("default", engine)

The ``view_name`` passed to ``.load()`` must match the
``view=`` parameter on your :py:class:`~semolina.SemanticView` subclass.

Write a pytest test
-------------------

Query your model the same way your application code does. :py:class:`~semolina.MockEngine`
returns results through :py:class:`~semolina.SemolinaCursor`, so assertions work on real
:py:class:`~semolina.Row` objects:

.. code-block:: python

   import pytest
   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       MockEngine,
       register,
       unregister,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   @pytest.fixture(autouse=True)
   def mock_engine():
       engine = MockEngine()
       engine.load(
           "sales",
           [
               {"revenue": 1000, "country": "US"},
               {"revenue": 2000, "country": "CA"},
           ],
       )
       register("default", engine)
       yield
       unregister("default")


   def test_revenue_query():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .execute()
       )
       rows = cursor.fetchall_rows()
       assert len(rows) == 2
       assert rows[0].country == "US"
       assert rows[0].revenue == 1000

Use a named engine for isolation
---------------------------------

Register the mock under a specific name and select it with ``.using()`` to avoid
conflicting with other registrations in your test suite:

.. code-block:: python

   register("test", engine)

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .using("test")
       .execute()
   )

Verify filters
--------------

:py:class:`~semolina.MockEngine` evaluates ``.where()`` predicates in-memory, so filtered
queries return only matching rows:

.. code-block:: python

   def test_filtered_query():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.country == "US")
           .execute()
       )
       rows = cursor.fetchall_rows()
       assert len(rows) == 1
       assert rows[0].country == "US"

.. _inspect-generated-sql:

Inspect generated SQL
---------------------

Use ``.to_sql()`` to verify the SQL your query produces without executing it:

.. code-block:: python

   def test_sql_generation():
       sql = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.country == "US")
           .to_sql()
       )
       assert 'AGG("revenue")' in sql
       assert '"country"' in sql

.. tip::

   ``.to_sql()`` uses Snowflake-style syntax (``AGG()``, double-quoted identifiers)
   regardless of which pool is registered. Use it for structural assertions, not
   dialect-specific SQL validation.

Clean up between tests
----------------------

Always call :py:func:`~semolina.unregister` in teardown to prevent registration
from leaking between tests. The ``autouse`` fixture pattern shown above handles this
automatically.

See also
--------

- :ref:`howto-backends-overview` -- register real connection pools for Snowflake and Databricks
- :ref:`howto-queries` -- the full query API
- :ref:`howto-backends-duckdb` -- use a local DuckDB database for development
