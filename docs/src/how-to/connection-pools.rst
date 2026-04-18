How to set up connection pools for production
==============================================

Connection pools manage a fixed set of warehouse connections, reusing them across
requests instead of opening a new connection each time. This guide covers pool sizing,
lifecycle management, and running multiple pools side-by-side.

Size the pool
-------------

:py:func:`~adbc_poolhouse.create_pool` accepts ``pool_size`` (steady-state connections)
and ``max_overflow`` (burst capacity above ``pool_size``). The defaults are 5 and 3
respectively, meaning up to 8 concurrent connections:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from adbc_poolhouse import SnowflakeConfig, create_pool
         from semolina import register

         config = SnowflakeConfig(
             account="xy12345.us-east-1",
             user="svc_analytics",
             password="...",
             database="analytics",
             warehouse="compute_wh",
         )
         pool = create_pool(
             config,
             pool_size=10,
             max_overflow=5,
             timeout=30,
             recycle=1800,
         )
         register("default", pool, dialect="snowflake")

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         from adbc_poolhouse import DatabricksConfig, create_pool
         from semolina import register

         config = DatabricksConfig(
             server_hostname="workspace.cloud.databricks.com",
             http_path="/sql/1.0/warehouses/abc123",
             access_token="dapi...",
         )
         pool = create_pool(
             config,
             pool_size=10,
             max_overflow=5,
             timeout=30,
             recycle=1800,
         )
         register("default", pool, dialect="databricks")

The pool parameters control connection behaviour:

.. list-table::
   :header-rows: 1

   * - Parameter
     - Default
     - Description
   * - ``pool_size``
     - ``5``
     - Number of connections kept open and reused
   * - ``max_overflow``
     - ``3``
     - Extra connections allowed above ``pool_size`` under burst load
   * - ``timeout``
     - ``30``
     - Seconds to wait for a connection before raising an error
   * - ``recycle``
     - ``3600``
     - Seconds before a connection is replaced with a fresh one
   * - ``pre_ping``
     - ``False``
     - Ping connections before checkout (``recycle`` is the preferred health mechanism)

.. tip::

   Start with ``pool_size`` matching your expected concurrent query count (e.g. web
   server worker count), and set ``max_overflow`` to 50--100% of ``pool_size`` for
   traffic spikes. A ``recycle`` of 1800 seconds (30 minutes) prevents stale connections
   from accumulating during low-traffic periods.

Load pool settings from TOML
-----------------------------

:py:func:`~semolina.pool_from_config` reads ``.semolina.toml`` and passes all fields
(after removing ``type``) to the ``adbc-poolhouse`` config class. Add pool parameters
directly in the TOML section:

.. code-block:: toml
   :caption: .semolina.toml

   [connections.default]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "svc_analytics"
   password = "..."
   database = "analytics"
   warehouse = "compute_wh"

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = pool_from_config()
   register("default", pool, dialect=dialect)

.. warning::

   ``pool_from_config()`` passes extra TOML fields through to the ``adbc-poolhouse``
   config class. Pool sizing parameters (``pool_size``, ``max_overflow``, etc.) are
   arguments to ``create_pool()``, not fields on the config class. To customise pool
   sizing with TOML-loaded credentials, construct the pool manually as shown in the
   section above.

Manage pool lifecycle
---------------------

Create pools at application startup and close them at shutdown. Use
``close_pool()`` from ``adbc-poolhouse`` to release both the SQLAlchemy pool and
the underlying ADBC source connection:

.. code-block:: python

   from adbc_poolhouse import (
       SnowflakeConfig,
       create_pool,
       close_pool,
   )
   from semolina import register, unregister

   # Startup
   config = SnowflakeConfig(
       account="xy12345.us-east-1",
       user="svc_analytics",
       password="...",
       database="analytics",
       warehouse="compute_wh",
   )
   pool = create_pool(config, pool_size=10)
   register("default", pool, dialect="snowflake")

   # ... application runs ...

   # Shutdown
   unregister("default")
   close_pool(pool)

:py:func:`~semolina.unregister` removes the pool from the registry so no new queries
use it. ``close_pool()`` then disposes the pool and closes the ADBC driver connection.

.. warning::

   Call ``close_pool()`` instead of ``pool.dispose()`` directly. ``close_pool()``
   also closes the underlying ADBC source connection, preventing resource leaks.

Register multiple pools with .using()
--------------------------------------

Register pools under different names to query multiple warehouses or use different
credentials for different workloads:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig, create_pool
   from semolina import register

   # Production pool -- large, for dashboard queries
   prod_config = SnowflakeConfig(
       account="xy12345.us-east-1",
       user="svc_dashboard",
       password="...",
       database="analytics",
       warehouse="large_wh",
   )
   prod_pool = create_pool(
       prod_config, pool_size=20, max_overflow=10
   )
   register("default", prod_pool, dialect="snowflake")

   # Reporting pool -- small, for scheduled reports
   report_config = SnowflakeConfig(
       account="xy12345.us-east-1",
       user="svc_reports",
       password="...",
       database="analytics",
       warehouse="small_wh",
   )
   report_pool = create_pool(report_config, pool_size=3)
   register("reports", report_pool, dialect="snowflake")

Use ``.using()`` on a query to select which pool to execute against:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   # Uses "default" pool (implicit)
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   # Uses "reports" pool (explicit)
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .using("reports")
       .execute()
   )

Pool resolution is lazy -- it happens at ``.execute()`` time, not when ``.using()``
is called. You can build queries before pools are registered.

Use named TOML sections for multiple pools
-------------------------------------------

Define multiple connection sections in ``.semolina.toml`` and load each by name:

.. code-block:: toml
   :caption: .semolina.toml

   [connections.default]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "svc_dashboard"
   password = "..."
   database = "analytics"
   warehouse = "large_wh"

   [connections.reports]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "svc_reports"
   password = "..."
   database = "analytics"
   warehouse = "small_wh"

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = pool_from_config(connection="default")
   register("default", pool, dialect=dialect)

   report_pool, report_dialect = pool_from_config(
       connection="reports"
   )
   register("reports", report_pool, dialect=report_dialect)

The ``connection`` parameter of :py:func:`~semolina.pool_from_config` maps to the section
name after ``connections.`` in the TOML file.

Close all pools at shutdown
---------------------------

When running multiple pools, close each one individually:

.. code-block:: python

   from adbc_poolhouse import close_pool
   from semolina import unregister

   for name, pool_ref in [
       ("default", prod_pool),
       ("reports", report_pool),
   ]:
       unregister(name)
       close_pool(pool_ref)

Keep references to your pool objects so you can close them during shutdown.
:py:func:`~semolina.unregister` does not return the pool -- it only removes
the registry entry.

See also
--------

- :doc:`backends/overview` -- connection patterns and backend selection
- :doc:`backends/snowflake` -- Snowflake TOML fields and credentials
- :doc:`backends/databricks` -- Databricks TOML fields and credentials
- :doc:`web-api` -- pool lifecycle in a FastAPI application
