.. _tutorial-first-query:

Your first query
================

In this tutorial, you will define a model, register an engine, build a query,
and read the results. By the end, you will have a working Semolina query you can
adapt for your own semantic views.

**Prerequisites:** Semolina installed (:ref:`tutorial-installation`).

1. Define a model
-----------------

A model maps to a semantic view in your warehouse. Create a file called
``demo.py`` and add this code:

.. code-block:: python

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()

``view="sales"`` is the name of the semantic view in your warehouse.
:py:class:`~semolina.fields.Metric` fields are aggregatable measures (revenue, cost).
:py:class:`~semolina.fields.Dimension` fields are categories for grouping (country, region).

In your warehouse, this model maps to a definition like:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         CREATE OR REPLACE SEMANTIC VIEW sales
           TABLES (
             s AS source_table PRIMARY KEY (id)
           )
           DIMENSIONS (
             s.country AS country,
             s.region AS region
           )
           METRICS (
             s.revenue AS SUM(s.revenue),
             s.cost AS SUM(s.cost)
           )
         ;

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         CREATE OR REPLACE VIEW sales
           WITH METRICS
           LANGUAGE YAML
           AS $$
             version: 1.1
             source: source_table
             dimensions:
               - name: country
                 expr: country
               - name: region
                 expr: region
             measures:
               - name: revenue
                 expr: SUM(revenue)
               - name: cost
                 expr: SUM(cost)
           $$;

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         INSTALL semantic_views FROM community;
         LOAD semantic_views;

         CREATE OR REPLACE SEMANTIC VIEW sales AS
         TABLES (
             s AS source_table PRIMARY KEY (id)
         )
         DIMENSIONS (
             s.country AS country,
             s.region AS region
         )
         METRICS (
             s.revenue AS SUM(s.revenue),
             s.cost AS SUM(s.cost)
         );

      The ``semantic_views`` community extension mirrors Snowflake's grammar,
      with an ``AS`` after the view name. Semolina installs and loads it on
      every new DuckDB connection, so you only need these two statements when
      you build the database yourself.

2. Register an engine
---------------------

Semolina needs an engine to talk to your warehouse. An engine owns one
connection pool and the dialect for a backend. Build one with
:py:func:`~semolina.config.create_engine` and register it before running any queries:

.. code-block:: python

   from semolina import register, create_engine

   register(
       "default", create_engine("default")
   )  # reads .semolina.toml

The same Python code works for every backend, which is why there are no tabs here.
``create_engine("default")`` reads the ``[connections.default]`` section of your
``.semolina.toml``, and the ``type`` field there determines which warehouse to
connect to.

See :ref:`howto-backends-overview` for full connection details
and TOML configuration.

.. tip:: No warehouse? Use DuckDB locally

   Install ``semolina[duckdb]``, then create a local database with sample data.
   The script below installs the
   `semantic_views <https://community-extensions.duckdb.org/extensions/semantic_views.html>`_
   community extension for you.

   Save this as ``setup_tutorial.py`` and run it once:

   .. code-block:: python

      import duckdb

      conn = duckdb.connect("tutorial.db")
      conn.execute("INSTALL semantic_views FROM community")
      conn.execute("LOAD semantic_views")
      conn.execute("""
          CREATE TABLE IF NOT EXISTS sales_data (
              revenue INTEGER, cost INTEGER,
              country VARCHAR, region VARCHAR
          )
      """)
      conn.execute("""
          INSERT INTO sales_data VALUES
          (1000, 100, 'US', 'West'),
          (2000, 200, 'CA', 'West'),
          (500, 50, 'US', 'East')
      """)
      conn.execute("""
          CREATE OR REPLACE SEMANTIC VIEW sales AS
          TABLES (s AS sales_data)
          DIMENSIONS (
              s.country AS country,
              s.region AS region
          )
          METRICS (
              s.revenue AS SUM(s.revenue),
              s.cost AS SUM(s.cost)
          )
      """)
      conn.close()

   Then register a DuckDB engine pointing at the file:

   .. code-block:: python

      from adbc_poolhouse import DuckDBConfig

      from semolina import register, create_engine

      engine = create_engine(DuckDBConfig(database="tutorial.db"))
      register("default", engine)

3. Build and run a query
------------------------

Use ``Model.query()`` to start building. Chain ``.metrics()`` and ``.dimensions()``
to select the fields you want, then call ``.execute()``:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

Each chained method returns a new query object, so queries are immutable and
reusable. See :ref:`howto-queries` for the rest of the builder.

4. Read the results
-------------------

``.execute()`` returns a :py:class:`~semolina.cursor.SemolinaCursor`. Call ``.fetchall_rows()``
to get :py:class:`~semolina.results.Row` objects that support both attribute and dict-style access:

.. code-block:: python

   rows = cursor.fetchall_rows()
   for row in rows:
       print(row.country, row.revenue)  # attribute access
       print(row["country"])  # dict-style access

.. warning:: Column keys are whatever your warehouse called them

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are the
   result column names exactly as the driver reports them. Only DuckDB happens to spell
   them like Python identifiers. The same query returns ``COUNTRY`` and ``AGG("REVENUE")``
   on Snowflake, and ``country`` and ``measure(revenue)`` on Databricks, so
   ``row.revenue`` raises ``AttributeError`` there. See
   :ref:`howto-result-column-names` before you deploy against a real warehouse.

Because ``revenue`` is a metric, the warehouse aggregates it per ``country``, so
the query returns one row per country. You should see output like:

.. code-block:: text

   CA 2000
   US 1500

Complete example
----------------

This self-contained demo uses a local DuckDB database. To run against a cloud
warehouse, replace the engine registration with your connection (see step 2).

First, run ``setup_tutorial.py`` from the tip above to create the database. Then
paste this into ``demo.py`` and run ``python demo.py``:

.. code-block:: python

   from adbc_poolhouse import DuckDBConfig

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       register,
       create_engine,
   )


   # 1. Define model
   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   # 2. Register a DuckDB engine
   engine = create_engine(DuckDBConfig(database="tutorial.db"))
   register("default", engine)

   # 3. Build and execute query
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   # 4. Use results
   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

You should see:

.. code-block:: text

   CA 2000
   US 1500

The two rows may arrive in either order. A query with no ``.order_by()`` leaves the
row order to the warehouse; :ref:`howto-ordering` shows how to fix it.

See also
--------

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Define models
      :link: howto-models
      :link-type: ref

      Field types, :py:class:`~semolina.models.SemanticView` parameters, immutability.

   .. grid-item-card:: Build queries
      :link: howto-queries
      :link-type: ref

      All query methods with examples.

   .. grid-item-card:: Filter queries
      :link: howto-filtering
      :link-type: ref

      Field operators, named methods, AND/OR/NOT composition.
