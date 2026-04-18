How to choose and configure a backend
======================================

Semolina supports multiple data warehouse backends:

- **Snowflake** -- via ``semolina[snowflake]``
- **Databricks** -- via ``semolina[databricks]``

The query API is identical for both -- only the connection configuration changes.

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
:doc:`snowflake` or :doc:`databricks` for the TOML fields.

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

:py:class:`~semolina.MockPool` accepts fixture data and returns it through the same cursor
interface, so you can test query logic without any warehouse connection:

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

See :doc:`../warehouse-testing` for testing patterns with ``MockPool``.

See also
--------

- :doc:`snowflake` -- TOML configuration and connection details for Snowflake
- :doc:`databricks` -- TOML configuration and connection details for Databricks
- :doc:`../connection-pools` -- pool sizing, lifecycle, and multiple named pools
- :doc:`../../explanation/semantic-views` -- background on semantic views in each warehouse
