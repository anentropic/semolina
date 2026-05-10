.. _howto-backends-overview:

How to choose and configure a backend
======================================

Semolina supports multiple data warehouse backends:

- **Snowflake** -- via ``semolina[snowflake]``
- **Databricks** -- via ``semolina[databricks]``
- **DuckDB** -- via ``semolina[duckdb]``

The query API is identical across all three -- only the connection configuration changes.

Register a connection pool
--------------------------

Two patterns are available for creating and registering a connection pool.

TOML config (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = pool_from_config()  # reads .semolina.toml
   register("default", pool, dialect=dialect)

:py:func:`~semolina.pool_from_config` reads ``.semolina.toml`` from the current directory,
creates an ``adbc-poolhouse`` connection pool, and returns it with the matching dialect. See
:ref:`howto-backends-snowflake`, :ref:`howto-backends-databricks`, or :ref:`howto-backends-duckdb` for the TOML fields.

Manual pool construction
~~~~~~~~~~~~~~~~~~~~~~~~

Use manual construction when credentials come from a vault, secrets manager, or need
programmatic configuration.

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from adbc_poolhouse import SnowflakeConfig, create_pool
         from semolina import register

         config = SnowflakeConfig(
             account="xy12345.us-east-1",
             user="myuser",
             password="mypassword",
             database="analytics",
             warehouse="compute_wh",
         )
         pool = create_pool(config)
         register("default", pool, dialect="snowflake")

   .. tab-item:: Databricks
      :sync: databricks

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

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         from adbc_poolhouse import DuckDBConfig, create_pool
         from semolina import register

         config = DuckDBConfig(database="/path/to/warehouse.db")
         pool = create_pool(config)
         register("default", pool, dialect="duckdb")

Query with a registered pool
-----------------------------

Once a pool is registered, the query API works the same regardless of backend:

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

   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

Test locally without a warehouse
---------------------------------

DuckDB works as a local backend for development and testing -- no warehouse
credentials needed. Install ``semolina[duckdb]`` and point at an in-memory or
file-backed database. See :ref:`howto-backends-duckdb` for full setup instructions and
:ref:`howto-warehouse-testing` for the testing pattern.

See also
--------

- :ref:`howto-backends-snowflake` -- TOML configuration and connection details for Snowflake
- :ref:`howto-backends-databricks` -- TOML configuration and connection details for Databricks
- :ref:`howto-backends-duckdb` -- TOML configuration and connection details for DuckDB
- :ref:`howto-connection-pools` -- pool sizing, lifecycle, and multiple named pools
- :ref:`explanation-semantic-views` -- background on semantic views in each warehouse
