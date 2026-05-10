.. _howto-codegen:

How to generate Semolina model classes from warehouse views
============================================================

Already have a Snowflake semantic view or Databricks metric view set up? ``semolina codegen``
introspects it and prints a Python model class to stdout. You can drop that output straight
into your codebase.

Run codegen
-----------

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake

That connects to your warehouse, reads the view's column metadata, and prints a ready-to-use
:py:class:`~semolina.SemanticView` subclass.

Introspect multiple views at once
---------------------------------

Pass multiple view names in a single call:

.. code-block:: bash

   semolina codegen schema.sales_view schema.orders_view --backend databricks

All classes appear in one output block with a single shared imports section.

Pipe output to a file
---------------------

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake > models.py

There is no ``--output`` flag; redirect stdout as you would with any CLI tool.

Choose a backend
----------------

Use ``--backend`` (or ``-b``):

.. list-table::
   :header-rows: 1

   * - Value
     - Warehouse
     - Introspects via
   * - ``snowflake``
     - Snowflake semantic views
     - ``SHOW COLUMNS IN VIEW``
   * - ``databricks``
     - Databricks metric views
     - ``DESCRIBE TABLE EXTENDED AS JSON``
   * - ``duckdb``
     - DuckDB semantic views
     - ``DESCRIBE SEMANTIC VIEW``

Credentials come from environment variables
(for example, ``SNOWFLAKE_ACCOUNT`` for Snowflake).
For DuckDB, pass the database path with ``--database`` (or set ``DUCKDB_DATABASE``).
See :ref:`howto-codegen-credentials` for the full list of
environment variables, ``.env`` file setup, and config
file fallback.

Understand the generated output
--------------------------------

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      Given this semantic view in your warehouse:

      .. code-block:: sql

         CREATE OR REPLACE SEMANTIC VIEW analytics.sales_view
           TABLES (
             s AS source_table PRIMARY KEY (id)
           )
           DIMENSIONS (
             s.country AS country,
             s.unit_price AS unit_price
           )
           METRICS (
             s.revenue AS SUM(revenue)
           )
         ;

      Running:

      .. code-block:: bash

         semolina codegen analytics.sales_view --backend snowflake

      Produces:

      .. code-block:: python

         from semolina import SemanticView, Metric, Dimension, Fact


         class SalesView(SemanticView, view="analytics.sales_view"):
             revenue = Metric[int]()
             country = Dimension[str]()
             unit_price = Fact[float]()

   .. tab-item:: Databricks
      :sync: databricks

      Given this metric view in your warehouse:

      .. code-block:: sql

         CREATE OR REPLACE VIEW main.analytics.orders_view
           WITH METRICS
           LANGUAGE YAML
           AS $$
             version: 1.1
             source: source_table
             dimensions:
               - name: region
                 expr: region
             measures:
               - name: total_orders
                 expr: COUNT(*)
           $$;

      Running:

      .. code-block:: bash

         semolina codegen main.analytics.orders_view --backend databricks

      Produces:

      .. code-block:: python

         from semolina import SemanticView, Metric, Dimension, Fact


         class OrdersView(
             SemanticView, view="main.analytics.orders_view"
         ):
             total_orders = Metric[int]()
             region = Dimension[str]()

   .. tab-item:: DuckDB
      :sync: duckdb

      Given this semantic view in your DuckDB database:

      .. code-block:: sql

         CREATE SEMANTIC VIEW sales_view AS
         TABLES (s AS sales_data PRIMARY KEY (id))
         DIMENSIONS (
             s.country AS country
         )
         METRICS (
             SUM(s.revenue) AS revenue
         )
         FACTS (
             s.unit_price AS unit_price
         );

      Running:

      .. code-block:: bash

         semolina codegen sales_view --backend duckdb --database /path/to/db

      Produces:

      .. code-block:: python

         from semolina import SemanticView, Metric, Dimension, Fact


         class SalesView(SemanticView, view="sales_view"):
             revenue = Metric[int]()
             country = Dimension[str]()
             unit_price = Fact[float]()

.. note::

   Databricks has no native Fact type, so all non-measure fields map to
   ``Dimension()``. DuckDB semantic views support all three field kinds
   (``METRIC``, ``DIMENSION``, ``FACT``), so codegen maps them directly.

Understand field type mapping
-----------------------------

.. list-table::
   :header-rows: 1

   * - Warehouse classification
     - Generated field type
   * - Metric / Measure
     - ``Metric[T]()``
   * - Dimension
     - ``Dimension[T]()``
   * - Fact (Snowflake and DuckDB)
     - ``Fact[T]()``

Handle TODO comments
--------------------

When a field's SQL type has no clean Python equivalent (GEOGRAPHY, VARIANT, ARRAY, MAP,
STRUCT), codegen emits a TODO comment rather than guessing:

.. code-block:: python

   # TODO: no clean Python type for GEOGRAPHY field "territory"
   territory = Dimension()

Review these after generation and handle them manually.

Exit codes
----------

``semolina codegen`` uses distinct exit codes so scripts can handle each failure mode separately:

.. list-table::
   :header-rows: 1

   * - Exit code
     - Meaning
   * - ``0``
     - Success -- model class written to stdout
   * - ``1``
     - Unexpected error (see stderr for details)
   * - ``2``
     - Invalid ``--backend`` specifier -- value provided but not recognised
   * - ``3``
     - View not found -- the warehouse has no semantic view with that name
   * - ``4``
     - Connection failure -- credentials missing or authentication rejected

.. tip::

   Exit code 2 is also emitted by the CLI argument parser when ``--backend`` is
   omitted entirely. Both cases mean "the backend could not be resolved."

Override the SQL column name with source=
-----------------------------------------

By default, Semolina maps Python field names to SQL column names using each dialect's
identifier casing rules (Snowflake uppercases unquoted identifiers; Databricks lowercases them).
For a field ``order_id``, Snowflake resolves ``ORDER_ID`` automatically.

If your warehouse stores a column with non-default casing, for example a quoted
lowercase column ``"order_id"`` in Snowflake, you can override the SQL column name
with ``source=``:

.. code-block:: python

   class Orders(SemanticView, view="orders"):
       order_id = Metric[int](
           source="order_id"
       )  # maps to quoted "order_id", not "ORDER_ID"

``semolina codegen`` emits ``source=`` automatically when introspection detects that a column
uses non-default casing.

See also
--------

- :ref:`howto-codegen-credentials` -- environment variables, .env files, and config file fallback
- :ref:`howto-models` -- model class structure and field types
- :ref:`howto-backends-snowflake` -- Snowflake pool configuration
- :ref:`howto-backends-databricks` -- Databricks pool configuration
- :ref:`howto-backends-duckdb` -- DuckDB pool configuration
