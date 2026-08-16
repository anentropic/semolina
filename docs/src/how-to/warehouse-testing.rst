.. _howto-warehouse-testing:

How to test query code without a warehouse
==========================================

Run your queries against an in-memory DuckDB semantic view instead of a live
warehouse. DuckDB executes the SQL your query builder generates, so tests see
real aggregation and filtering, and your application code calls
``Model.query().execute()`` exactly as it does in production.

This page covers the *testing* fixture. To connect an application to a DuckDB
database as a backend, see :ref:`howto-backends-duckdb`. For how engines and the
registry work, see :ref:`howto-connection-pools`.

Install the DuckDB extra
------------------------

.. code-block:: bash

   uv add "semolina[duckdb]"
   # or
   pip install "semolina[duckdb]"

Set up an in-memory engine fixture
----------------------------------

Build a DuckDB engine backed by ``":memory:"``, then create the table, semantic
view, and seed rows on each new connection. DuckDB isolates in-memory databases
per physical connection, so the setup runs on a ``connect`` event rather than
once up front. Teardown calls :py:meth:`~semolina.engines.base.Engine.dispose`, which
closes the pool and the ADBC source connection behind it:

.. note:: ``engine._pool`` is private

   Attaching the listener needs the underlying SQLAlchemy pool, and ``Engine`` has no
   public accessor for it today, so this example reaches into ``engine._pool``. That is
   a supported thing to do in your own test suite -- nothing else gives you a
   per-connection hook -- but it is not covered by the public API, so pin your Semolina
   version if you depend on it. Do not reach for it in application code: call
   :py:meth:`engine.dispose() <semolina.engines.base.Engine.dispose>` to close the pool
   rather than touching it directly.

.. code-block:: python

   import pytest
   from adbc_poolhouse import DuckDBConfig
   from sqlalchemy import event

   from semolina import (
       Dimension,
       Metric,
       SemanticView,
       register,
       unregister,
       create_engine,
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
           DIMENSIONS (s.country AS country)
           METRICS (s.revenue AS SUM(s.revenue))
           """)
       cur.close()
       dbapi_conn.commit()


   @pytest.fixture
   def sales_engine():
       engine = create_engine(
           DuckDBConfig(database=":memory:", pool_size=1)
       )
       event.listen(engine._pool, "connect", _seed)
       register("default", engine)
       yield
       unregister("default")
       engine.dispose()

The ``commit()`` after ``CREATE SEMANTIC VIEW`` matters: ADBC connections open
with ``autocommit=False``, and the ``semantic_views`` extension resolves the
view on a separate read connection that only sees committed state. See
:ref:`howto-backends-duckdb` for more on the extension.

Write a test
------------

Query your model the same way your application does. DuckDB aggregates the
metric, so ``US`` returns ``1500`` (``1000 + 500``):

.. code-block:: python

   def test_revenue_by_country(sales_engine):
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

   def test_filtered_query(sales_engine):
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

Assert on generated SQL
-----------------------

``.to_sql()`` renders a query without executing it, which makes it the tool for
structural assertions. :ref:`howto-inspect-sql` covers what it emits for each dialect;
in a test it looks like this:

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

Use ``.to_sql()`` for assertions about the SQL, and the DuckDB fixture above for
assertions about behaviour.

Record your warehouse with pytest-adbc-replay
---------------------------------------------

DuckDB runs the SQL, but it is not your warehouse: its results can differ from
Snowflake or Databricks in numeric type and precision, and in how your semantic
view resolves. When you want tests to match what your warehouse actually
returns, record the real responses once with
`pytest-adbc-replay <https://anentropic.github.io/pytest-adbc-replay/>`_ and
replay them from disk on every later run.

The plugin wraps the ADBC connection your engine's pool hands out. A credentialed
run captures each query and its Arrow result into a *cassette*; after that, tests
read the cassette and reach no warehouse.

Install it as a dev dependency:

.. code-block:: bash

   uv add --dev pytest-adbc-replay

Point ``adbc_auto_patch`` at the driver module your engine connects through, and
set ``adbc_dialect`` so recorded SQL is matched correctly on replay:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: toml

         [tool.pytest.ini_options]
         adbc_auto_patch = ["adbc_driver_snowflake.dbapi"]
         adbc_dialect = ["adbc_driver_snowflake.dbapi: snowflake"]

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: toml

         [tool.pytest.ini_options]
         adbc_auto_patch = ["adbc_driver_manager.dbapi"]
         adbc_dialect = ["adbc_driver_manager.dbapi: databricks"]

      adbc-poolhouse connects to Databricks through the ADBC driver manager, so
      the module to patch is ``adbc_driver_manager.dbapi`` rather than a
      Databricks-specific one.

   .. tab-item:: DuckDB
      :sync: duckdb

      Nothing to configure. There is no credentialed run to capture and no
      network call to avoid, so a local DuckDB is simply run rather than
      recorded -- use the in-memory engine fixture from the top of this page.

      Keep it that way: do not mark a DuckDB test with ``adbc_cassette``. The
      plugin serves a recorded result whatever the driver would really have
      done, so a cassette-backed DuckDB test looks like evidence and is none.

Register your warehouse engine -- not the in-memory DuckDB fixture from the top
of this page -- then mark the test with ``adbc_cassette`` so the plugin records
or replays its connections:

.. code-block:: python

   import pytest


   @pytest.mark.adbc_cassette
   def test_revenue_by_country(snowflake_engine):
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .execute()
       )
       rows = {
           row["COUNTRY"]: row['AGG("REVENUE")']
           for row in cursor.fetchall_rows()
       }
       cursor.close()

       assert rows == {"US": 1500, "CA": 2000}

The keys are the warehouse's own column spellings, because a cassette replays the
result your warehouse produced. That is the point of recording: a test written
against ``row.country`` passes on DuckDB and fails here. See
:ref:`howto-result-column-names`.

Record once against the real warehouse, then replay with no credentials:

.. code-block:: bash

   # Record: reads warehouse credentials from your environment
   pytest --adbc-record=once

   # Replay (the default): reads cassettes, reaches no warehouse
   pytest

Commit the cassette files next to your tests. They are matched by normalized
SQL, so they only need re-recording when the query your code generates changes.

Clean up between tests
----------------------

Call :py:func:`~semolina.registry.unregister` in teardown so a registration does not leak
into the next test. The fixtures above do this on the far side of their
``yield``.

See also
--------

- :ref:`howto-backends-duckdb` -- connect to a DuckDB database and the
  ``semantic_views`` extension
- :ref:`howto-backends-overview` -- register real engines for Snowflake and
  Databricks
- :ref:`howto-queries` -- the full query API
- :ref:`explanation-duckdb-vs-warehouse` -- what a green DuckDB suite does and does not
  prove about code that will run against Snowflake or Databricks
- `pytest-adbc-replay <https://anentropic.github.io/pytest-adbc-replay/>`_ --
  record and replay ADBC responses
