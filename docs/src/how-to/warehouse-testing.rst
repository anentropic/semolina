How to test application code with MockPool
============================================

Test query logic without connecting to a real warehouse. :py:class:`~semolina.MockPool`
accepts fixture data and returns it through the same cursor interface as a real
connection pool, so your application code works identically in tests and production.

Set up MockPool
---------------

Create a :py:class:`~semolina.MockPool`, load fixture data keyed by view name, and
register it as the default pool:

.. code-block:: python

   from semolina import MockPool, register

   pool = MockPool()
   pool.load(
       "sales",
       [
           {"revenue": 1000, "country": "US"},
           {"revenue": 2000, "country": "CA"},
       ],
   )
   register("default", pool, dialect="mock")

The ``view_name`` passed to :py:meth:`~semolina.MockPool.load` must match the
``view=`` parameter on your :py:class:`~semolina.SemanticView` subclass.

Write a pytest test
-------------------

Query your model the same way your application code does. ``MockPool`` returns
fixture data through ``SemolinaCursor``, so assertions work on real ``Row`` objects:

.. code-block:: python

   import pytest
   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       MockPool,
       register,
       unregister,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   @pytest.fixture(autouse=True)
   def mock_pool():
       pool = MockPool()
       pool.load(
           "sales",
           [
               {"revenue": 1000, "country": "US"},
               {"revenue": 2000, "country": "CA"},
           ],
       )
       register("default", pool, dialect="mock")
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

Use a named pool for isolation
------------------------------

Register the mock under a specific name and select it with ``.using()`` to avoid
conflicting with other pools in your test suite:

.. code-block:: python

   register("test", pool, dialect="mock")

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .using("test")
       .execute()
   )

Verify filter SQL
-----------------

``MockPool`` returns all fixture data regardless of ``.where()`` filters -- it does
not evaluate predicates. Use the result to confirm your query runs, and check
:ref:`inspect-generated-sql` to verify the filter appears in the generated SQL:

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
       assert (
           len(rows) == 2
       )  # MockPool returns all fixture rows

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

Always call :py:func:`~semolina.unregister` in teardown to prevent pool registration
from leaking between tests. The ``autouse`` fixture pattern shown above handles this
automatically.

See also
--------

- :doc:`backends/overview` -- register real connection pools for Snowflake and Databricks
- :doc:`queries` -- the full query API
- :doc:`../tutorials/first-query` -- getting started with ``MockPool``
