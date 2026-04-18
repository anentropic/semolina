How to connect to Databricks
=============================

Install the Databricks extra
-----------------------------

.. code-block:: bash

   pip install semolina[databricks]
   # or
   uv add "semolina[databricks]"

The Databricks extra installs ``adbc-poolhouse[databricks]``, which provides the ADBC
Databricks driver and connection pooling.

Configure with .semolina.toml (recommended)
--------------------------------------------

Create a ``.semolina.toml`` file in your project root:

.. code-block:: toml

   # .semolina.toml
   [connections.default]
   type = "databricks"
   host = "workspace.cloud.databricks.com"
   http_path = "/sql/1.0/warehouses/abc123"
   token = "dapi..."
   # catalog = ""
   # schema = ""

.. list-table::
   :header-rows: 1

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"databricks"``
   * - ``host``
     - ``str``
     - Yes
     - Databricks workspace hostname (e.g. ``workspace.cloud.databricks.com``)
   * - ``http_path``
     - ``str``
     - Yes
     - SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/{warehouse_id}``)
   * - ``token``
     - ``str``
     - Yes
     - Personal access token starting with ``dapi``
   * - ``catalog``
     - ``str``
     - No
     - Unity Catalog name
   * - ``schema``
     - ``str``
     - No
     - Default schema

Then load and register the pool:

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = pool_from_config()
   register("default", pool, dialect=dialect)

.. tip::

   Use ``pool_from_config(connection="analytics")`` to load a named connection section
   other than ``default``.

Configure manually
-------------------

When credentials come from a vault or secrets manager, construct the pool directly:

.. code-block:: python

   from adbc_poolhouse import DatabricksConfig, create_pool
   from semolina import register

   config = DatabricksConfig(
       host="workspace.cloud.databricks.com",
       http_path="/sql/1.0/warehouses/abc123",
       token="dapi...",
   )
   pool = create_pool(config)
   register("default", pool, dialect="databricks")

Use Unity Catalog three-part names
-----------------------------------

Databricks uses `Unity Catalog <https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html>`_
for three-level namespace: ``catalog.schema.view``. Pass a three-part ``view=`` name in your model:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="main.analytics.sales"):
       revenue = Metric()
       country = Dimension()

Each part is quoted separately with backticks in generated SQL:

.. code-block:: sql

   SELECT MEASURE(`revenue`), `country`
   FROM `main`.`analytics`.`sales`
   GROUP BY ALL

Run a query
-----------

Once a pool is registered, the query API works the same as any backend:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )
   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

Generated SQL
-------------

Databricks SQL uses ``MEASURE()`` for metrics and backtick-quoted identifiers:

.. code-block:: sql

   SELECT MEASURE(`revenue`), `country`
   FROM `sales`
   GROUP BY ALL

See also
--------

- :doc:`overview` -- compare connection patterns
- :doc:`snowflake` -- connect to Snowflake semantic views
- :doc:`../warehouse-testing` -- test queries with ``MockPool``
