.. _howto-warehouse-testing:

How to test query code without a warehouse
==========================================

Run your queries against an in-memory DuckDB semantic view instead of a live
warehouse. DuckDB executes the SQL your query builder generates, so tests see
real aggregation and filtering, and your application code calls
``Model.query().execute()`` exactly as it does in production.

This page covers the *testing* fixture. To connect an application to a DuckDB
database as a backend, see :ref:`howto-backends-duckdb`.

Install the DuckDB extra
------------------------

.. code-block:: bash

   uv add "semolina[duckdb]"
   # or
   pip install "semolina[duckdb]"

Set up an in-memory pool fixture
--------------------------------

Build a DuckDB pool backed by ``":memory:"``, then create the table, semantic
view, and seed rows on each new connection. DuckDB isolates in-memory databases
per physical connection, so the setup runs on a ``connect`` event rather than
once up front:

.. code-block:: python

   import pytest
   from adbc_poolhouse import (
       DuckDBConfig,
       close_pool,
       create_pool,
   )
   from sqlalchemy import event

   from semolina import (
       Dialect,
       Dimension,
       Metric,
       SemanticView,
       register,
       unregister,
   )


   class Sales(SemanticView, view="sales_view"):
       revenue = Metric()
       country = Dimension()


   def _seed(dbapi_conn, _record):
       cur = dbapi_conn.cursor()
       cur.execute("INSTALL semantic_views FROM community")
       cur.execute("LOAD semantic_views")
       cur.execute(
           "CREATE TABLE sales_data (id INTEGER, revenue INTEGER, country VARCHAR)"
       )
       cur.execute(
           "INSERT INTO sales_data VALUES (1, 1000, 'US'), (2, 2000, 'CA'), (3, 500, 'US')"
       )
       cur.execute("""
           CREATE OR REPLACE SEMANTIC VIEW sales_view AS
           TABLES (s AS sales_data PRIMARY KEY (id))
           DIMENSIONS (s.country AS s.country)
           METRICS (s.revenue AS SUM(s.revenue))
           """)
       cur.close()
       dbapi_conn.commit()


   @pytest.fixture
   def sales_pool():
       pool = create_pool(
           DuckDBConfig(database=":memory:", pool_size=1)
       )
       event.listen(pool, "connect", _seed)
       register("default", pool, dialect=Dialect.DUCKDB)
       yield
       unregister("default")
       close_pool(pool)

The ``commit()`` after ``CREATE SEMANTIC VIEW`` matters: ADBC connections open
with ``autocommit=False``, and the ``semantic_views`` extension resolves the
view on a separate read connection that only sees committed state. See
:ref:`howto-backends-duckdb` for more on the extension.

Write a test
------------

Query your model the same way your application does. DuckDB aggregates the
metric, so ``US`` returns ``1500`` (``1000 + 500``):

.. code-block:: python

   def test_revenue_by_country(sales_pool):
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .execute()
       )
       rows = {
           row.country: row.revenue
           for row in cursor.fetchall_rows()
       }
       cursor.close()

       assert rows == {"US": 1500, "CA": 2000}

Because the SQL actually runs, ``.where()`` filters return only matching rows:

.. code-block:: python

   def test_filtered_query(sales_pool):
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.country == "US")
           .execute()
       )
       rows = cursor.fetchall_rows()
       cursor.close()

       assert len(rows) == 1
       assert rows[0].country == "US"
       assert rows[0].revenue == 1500

.. _inspect-generated-sql:

Inspect generated SQL
---------------------

Use ``.to_sql()`` to check the SQL a query produces without executing it. It
defaults to the Snowflake dialect (``AGG()``, double-quoted identifiers folded
to upper case):

.. code-block:: python

   def test_sql_generation():
       sql = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.country == "US")
           .to_sql()
       )
       assert 'AGG("REVENUE")' in sql
       assert '"COUNTRY"' in sql

Pass a ``dialect`` to preview another backend, for example
``.to_sql(dialect="databricks")``. Use ``.to_sql()`` for structural assertions
on the generated SQL, and the DuckDB fixture above for behavior.

Roll your own pool without DuckDB
---------------------------------

When you only need to exercise code that consumes :py:class:`~semolina.Row`
objects, and you would rather not pull in the DuckDB extra, register a small
fake pool that returns canned rows. It follows the DBAPI surface
:py:class:`~semolina.SemolinaCursor` expects (``description``, ``fetchall``,
``fetchone``, ``fetchmany``, ``close``):

.. code-block:: python

   class _FakeCursor:
       def __init__(self, rows, columns):
           self.description = [
               (c, None, None, None, None, None, None)
               for c in columns
           ]
           self.rowcount = len(rows)
           self._rows = [
               tuple(row[c] for c in columns) for row in rows
           ]
           self._pos = 0

       def execute(self, sql, params=None):
           pass  # canned data ignores the SQL

       def fetchall(self):
           rows, self._pos = self._rows[self._pos :], len(
               self._rows
           )
           return rows

       def fetchone(self):
           if self._pos >= len(self._rows):
               return None
           row = self._rows[self._pos]
           self._pos += 1
           return row

       def fetchmany(self, size=1):
           rows = self._rows[self._pos : self._pos + size]
           self._pos += len(rows)
           return rows

       def close(self):
           pass


   class _FakeConn:
       def __init__(self, rows, columns):
           self._rows, self._columns = rows, columns

       def cursor(self):
           return _FakeCursor(self._rows, self._columns)

       def close(self):
           pass


   class _FakePool:
       def __init__(self, rows, columns):
           self._rows, self._columns = rows, columns

       def connect(self):
           return _FakeConn(self._rows, self._columns)

       def close(self):
           pass


   @pytest.fixture
   def fake_pool():
       pool = _FakePool(
           [
               {"country": "US", "revenue": 1500},
               {"country": "CA", "revenue": 2000},
           ],
           columns=["country", "revenue"],
       )
       register("default", pool, dialect=Dialect.SNOWFLAKE)
       yield
       unregister("default")

The fake pool returns its rows verbatim. It does not run SQL, so it never
aggregates or filters: use it to test code paths that read ``Row`` objects, and
the DuckDB fixture when the result itself is what you are checking.

Clean up between tests
----------------------

Call :py:func:`~semolina.unregister` in teardown so a registration does not leak
into the next test. The fixtures above do this on the far side of their
``yield``.

See also
--------

- :ref:`howto-backends-duckdb` -- connect to a DuckDB database and the
  ``semantic_views`` extension
- :ref:`howto-backends-overview` -- register real connection pools for
  Snowflake and Databricks
- :ref:`howto-queries` -- the full query API
