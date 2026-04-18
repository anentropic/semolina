Your first query
================

In this tutorial, you will define a model, register a connection, build a query,
and read the results. By the end, you will have a working Semolina query you can
adapt for your own semantic views.

**Prerequisites:** Semolina installed (:doc:`installation`).

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
:py:class:`~semolina.Metric` fields are aggregatable measures (revenue, cost).
:py:class:`~semolina.Dimension` fields are categories for grouping (country, region).

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
             s.revenue AS SUM(revenue),
             s.cost AS SUM(cost)
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

2. Register a connection pool
------------------------------

Semolina needs a connection pool to talk to your warehouse. Register one
before running any queries:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from semolina import register, pool_from_config

         pool, dialect = pool_from_config()  # reads .semolina.toml
         register("default", pool, dialect=dialect)

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         from semolina import register, pool_from_config

         pool, dialect = pool_from_config()  # reads .semolina.toml
         register("default", pool, dialect=dialect)

The same Python code works for both backends. The ``type`` field in your
``.semolina.toml`` determines which warehouse to connect to.

See :doc:`../how-to/backends/overview` for full connection details
and TOML configuration.

.. tip:: No warehouse? Use MockPool

   If you want to follow along without a warehouse
   connection, use :py:class:`~semolina.MockPool` with fixture data:

   .. code-block:: python

      from semolina import MockPool, register

      pool = MockPool()
      pool.load(
          "sales",
          [
              {
                  "revenue": 1000,
                  "cost": 100,
                  "country": "US",
                  "region": "West",
              },
              {
                  "revenue": 2000,
                  "cost": 200,
                  "country": "CA",
                  "region": "West",
              },
              {
                  "revenue": 500,
                  "cost": 50,
                  "country": "US",
                  "region": "East",
              },
          ],
      )
      register("default", pool, dialect="mock")

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
reusable.

You can also pass metrics and dimensions directly to ``query()``:

.. code-block:: python

   cursor = Sales.query(
       metrics=[Sales.revenue],
       dimensions=[Sales.country],
   ).execute()

4. Read the results
-------------------

``.execute()`` returns a :py:class:`~semolina.SemolinaCursor`. Call ``.fetchall_rows()``
to get :py:class:`~semolina.Row` objects that support both attribute and dict-style access:

.. code-block:: python

   rows = cursor.fetchall_rows()
   for row in rows:
       print(row.country, row.revenue)  # attribute access
       print(row["country"])  # dict-style access

You should see output like:

.. code-block:: text

   US 1000
   US
   CA 2000
   CA
   US 500
   US

Complete example
----------------

Here is a self-contained demo using :py:class:`~semolina.MockPool`. To run against a real
warehouse, replace the pool registration with your connection (see step 2).

Paste it into ``demo.py`` and run ``python demo.py``:

.. code-block:: python

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       MockPool,
       register,
   )


   # 1. Define model
   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   # 2. Register pool with fixture data
   pool = MockPool()
   pool.load(
       "sales",
       [
           {
               "revenue": 1000,
               "cost": 100,
               "country": "US",
               "region": "West",
           },
           {
               "revenue": 2000,
               "cost": 200,
               "country": "CA",
               "region": "West",
           },
           {
               "revenue": 500,
               "cost": 50,
               "country": "US",
               "region": "East",
           },
       ],
   )
   register("default", pool, dialect="mock")

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

   US 1000
   CA 2000
   US 500

See also
--------

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Defining Models
      :link: ../how-to/models
      :link-type: doc

      Field types, :py:class:`~semolina.SemanticView` parameters, immutability.

   .. grid-item-card:: Building Queries
      :link: ../how-to/queries
      :link-type: doc

      All query methods with examples.

   .. grid-item-card:: Filtering
      :link: ../how-to/filtering
      :link-type: doc

      Field operators, named methods, AND/OR/NOT composition.
