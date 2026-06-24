.. _howto-connection-pools:

How to connect an engine to your warehouse
===========================================

An :py:class:`Engine <semolina.engines.base.Engine>` owns one ADBC connection
pool and the dialect for a warehouse. You build it once with
:py:func:`~semolina.create_engine`, then run queries through it. This guide
covers the two ways to use an engine, pool sizing, lifecycle, and querying
several warehouses side by side.

Two ways to use an engine
-------------------------

There are two patterns, and you can mix them in the same application.

The **direct engine** pattern keeps a reference to the engine and calls it
yourself. It mirrors SQLAlchemy: ``create_engine(...)`` hands you an engine, and
``engine.execute(query)`` runs a query through its pool.

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   engine = create_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_analytics",
           password="...",
           database="analytics",
           warehouse="compute_wh",
       )
   )

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )
   cursor = engine.execute(query)
   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

The **named registry** pattern registers an engine under a name and lets the
query resolve it. It mirrors Django's database aliases: register once at startup,
then ``.execute()`` finds the engine for you. A query with no ``.using()`` clause
resolves the ``"default"`` engine.

.. code-block:: python

   from semolina import register, create_engine

   register("default", create_engine("default"))

   # No .using() -> resolves the "default" engine
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )
   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

The registry pattern is the better fit for web applications, where the engine is
created once at startup and endpoints query without passing it around. The direct
pattern suits scripts and notebooks where you already hold the engine.

Build an engine from a config object or a connection name
---------------------------------------------------------

:py:func:`~semolina.create_engine` accepts either an ``adbc-poolhouse`` config
object or the name of a ``.semolina.toml`` connection section. The dialect is
derived from the config type, so you never select a backend by hand.

Pass a config object when credentials come from a vault, a secrets manager, or
your own code:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from adbc_poolhouse import SnowflakeConfig

         from semolina import create_engine

         engine = create_engine(
             SnowflakeConfig(
                 account="xy12345.us-east-1",
                 user="svc_analytics",
                 password="...",
                 database="analytics",
                 warehouse="compute_wh",
             )
         )

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         from adbc_poolhouse import DatabricksConfig

         from semolina import create_engine

         engine = create_engine(
             DatabricksConfig(
                 host="workspace.cloud.databricks.com",
                 http_path="/sql/1.0/warehouses/abc123",
                 token="dapi...",
             )
         )

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         from adbc_poolhouse import DuckDBConfig

         from semolina import create_engine

         engine = create_engine(
             DuckDBConfig(database="/path/to/warehouse.db")
         )

Pass a connection name to read settings from ``.semolina.toml`` instead. The name
maps to a ``[connections.<name>]`` section:

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

   from semolina import create_engine

   engine = create_engine(
       "default"
   )  # reads [connections.default]

``create_engine()`` with no argument is the same as ``create_engine("default")``.
Point at a different file with ``create_engine("default", config_path="config/warehouse.toml")``.

Size the pool
-------------

Pool sizing lives on the config object. The config classes carry ``pool_size``
(steady-state connections), ``max_overflow`` (burst capacity above ``pool_size``),
``timeout``, and ``recycle``. The defaults are 5 and 3, so up to 8 concurrent
connections:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import create_engine

   engine = create_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_analytics",
           password="...",
           database="analytics",
           warehouse="compute_wh",
           pool_size=10,
           max_overflow=5,
           timeout=30,
           recycle=1800,
       )
   )

Set the same fields in a ``.semolina.toml`` section to size a pool you build by
name:

.. code-block:: toml
   :caption: .semolina.toml

   [connections.default]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "svc_analytics"
   password = "..."
   database = "analytics"
   warehouse = "compute_wh"
   pool_size = 10
   max_overflow = 5
   recycle = 1800

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

.. tip::

   Start with ``pool_size`` matching your expected concurrent query count (e.g. web
   server worker count), and set ``max_overflow`` to 50--100% of ``pool_size`` for
   traffic spikes. A ``recycle`` of 1800 seconds (30 minutes) prevents stale connections
   from accumulating during low-traffic periods.

.. note::

   DuckDB defaults to ``pool_size=1``. In-memory databases (``:memory:``) are
   isolated per connection, so ``pool_size > 1`` with ``:memory:`` raises a
   ``ValidationError``. Use a file-backed database path for multiple concurrent
   connections.

Open a raw connection
---------------------

When you need to run something the query builder does not cover, check a
connection out of the engine's pool with ``engine.connect()``. It is a context
manager, so the connection returns to the pool on exit:

.. code-block:: python

   with engine.connect() as conn:
       cur = conn.cursor()
       cur.execute("SHOW VIEWS")
       rows = cur.fetchall()

Manage the engine lifecycle
---------------------------

Create the engine at application startup and close it at shutdown. ``close_pool()``
from ``adbc-poolhouse`` releases both the pool and the underlying ADBC source
connection. The engine holds its pool as ``engine._pool``:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig, close_pool

   from semolina import register, unregister, create_engine

   # Startup
   engine = create_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_analytics",
           password="...",
           database="analytics",
           warehouse="compute_wh",
           pool_size=10,
       )
   )
   register("default", engine)

   # ... application runs ...

   # Shutdown
   unregister("default")
   close_pool(engine._pool)

:py:func:`~semolina.unregister` removes the engine from the registry so no new
queries resolve it. ``close_pool()`` then disposes the pool and closes the ADBC
driver connection.

.. warning::

   Call ``close_pool(engine._pool)`` rather than ``engine._pool.dispose()``.
   ``close_pool()`` also closes the underlying ADBC source connection, preventing
   resource leaks.

Look up a registered engine
---------------------------

:py:func:`~semolina.get_engine` returns the engine registered under a name, so you
can reach it without keeping your own reference:

.. code-block:: python

   from semolina import get_engine

   engine = get_engine("default")

Call it with no argument (or ``None``) to get the ``"default"`` engine -- the same
lookup ``.execute()`` performs when a query has no ``.using()`` clause:

.. code-block:: python

   engine = get_engine()  # the "default" engine

To close an engine at shutdown without tracking your own reference, look it up,
unregister it, then close its pool:

.. code-block:: python

   from adbc_poolhouse import close_pool

   from semolina import get_engine, unregister

   engine = get_engine("reports")
   unregister("reports")
   close_pool(engine._pool)

If no engine is registered under the name, ``get_engine`` raises ``ValueError``
listing the names that are available.

Query several warehouses with .using()
--------------------------------------

Register engines under different names to query multiple warehouses, or to use
different credentials for different workloads:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import register, create_engine

   # Production engine -- large warehouse, for dashboard queries
   register(
       "default",
       create_engine(
           SnowflakeConfig(
               account="xy12345.us-east-1",
               user="svc_dashboard",
               password="...",
               database="analytics",
               warehouse="large_wh",
               pool_size=20,
               max_overflow=10,
           )
       ),
   )

   # Reporting engine -- small warehouse, for scheduled reports
   register(
       "reports",
       create_engine(
           SnowflakeConfig(
               account="xy12345.us-east-1",
               user="svc_reports",
               password="...",
               database="analytics",
               warehouse="small_wh",
               pool_size=3,
           )
       ),
   )

Use ``.using()`` on a query to pick which engine to run against:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   # Uses the "default" engine (implicit)
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   # Uses the "reports" engine (explicit)
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .using("reports")
       .execute()
   )

Engine resolution is lazy -- it happens at ``.execute()`` time, not when
``.using()`` is called. You can build queries before any engine is registered.

To drive multiple named engines from one TOML file, define a section per
connection and build each by name:

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

   from semolina import register, create_engine

   register("default", create_engine("default"))
   register("reports", create_engine("reports"))

Close every engine at shutdown
------------------------------

When running multiple engines, close each one individually:

.. code-block:: python

   from adbc_poolhouse import close_pool

   from semolina import get_engine, unregister

   for name in ("default", "reports"):
       engine = get_engine(name)
       unregister(name)
       close_pool(engine._pool)

:py:func:`~semolina.get_engine` lets you reach each engine by name at shutdown, so
you do not have to thread engine references through your application.

See also
--------

- :ref:`howto-backends-overview` -- connection patterns and backend selection
- :ref:`howto-backends-snowflake` -- Snowflake TOML fields and credentials
- :ref:`howto-backends-databricks` -- Databricks TOML fields and credentials
- :ref:`howto-backends-duckdb` -- DuckDB TOML fields and connection details
- :ref:`howto-web-api` -- engine lifecycle in a FastAPI application
- :ref:`reference-config` -- the ``.semolina.toml`` file format
