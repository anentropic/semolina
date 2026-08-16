.. _howto-backends-overview:

How to choose and configure a backend
======================================

Semolina supports multiple data warehouse backends:

- **Snowflake** -- via ``semolina[snowflake]``
- **Databricks** -- via ``semolina[databricks]``
- **DuckDB** -- via ``semolina[duckdb]``

The query API is identical across all three -- only the connection configuration changes.

Register an engine
------------------

Build an engine with :py:func:`~semolina.config.create_engine` and register it under a
name. The engine owns one connection pool and the dialect for the backend. Two
ways to build it: from a ``.semolina.toml`` connection name, or from a config
object.

From a connection name (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from semolina import register, create_engine

   register(
       "default", create_engine("default")
   )  # reads .semolina.toml

``create_engine("default")`` reads the ``[connections.default]`` section of
``.semolina.toml``, creates an ``adbc-poolhouse`` connection pool, and derives
the dialect from the section's ``type``. That ``type`` value is a member of the
:py:class:`~semolina.dialect.Dialect` enum, so ``"snowflake"``, ``"databricks"``, and
``"duckdb"`` are the accepted values. See :ref:`howto-backends-snowflake`,
:ref:`howto-backends-databricks`, or :ref:`howto-backends-duckdb` for the TOML
fields.

From a config object
~~~~~~~~~~~~~~~~~~~~~

Pass a config object when credentials come from a vault, a secrets manager, or
need programmatic configuration.

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from adbc_poolhouse import SnowflakeConfig

         from semolina import register, create_engine

         engine = create_engine(
             SnowflakeConfig(
                 account="xy12345.us-east-1",
                 user="myuser",
                 password="mypassword",
                 database="analytics",
                 warehouse="compute_wh",
             )
         )
         register("default", engine)

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         from adbc_poolhouse import DatabricksConfig

         from semolina import register, create_engine

         engine = create_engine(
             DatabricksConfig(
                 host="workspace.cloud.databricks.com",
                 http_path="/sql/1.0/warehouses/abc123",
                 token="dapi...",
             )
         )
         register("default", engine)

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         from adbc_poolhouse import DuckDBConfig

         from semolina import register, create_engine

         engine = create_engine(
             DuckDBConfig(database="/path/to/warehouse.db")
         )
         register("default", engine)

Query with a registered engine
------------------------------

Once an engine is registered, the query API works the same regardless of
backend. What the results are *called* does not:

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

.. warning:: The attribute spelling above is DuckDB's

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are
   the result column names exactly as the driver reports them. The same query
   returns ``COUNTRY`` and ``AGG("REVENUE")`` on Snowflake and ``country`` and
   ``measure(revenue)`` on Databricks, so ``row.revenue`` raises
   ``AttributeError`` on both. This is the one place the query API's
   backend-agnosticism stops. See :ref:`howto-result-column-names`, or use
   :ref:`howto-typed-results` to get the same field names everywhere.

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
- :ref:`howto-connection-pools` -- pool sizing, lifecycle, and multiple named engines
- :ref:`explanation-semantic-views` -- background on semantic views in each warehouse
