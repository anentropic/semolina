.. _howto-connection-pools:

How to connect an engine to your warehouse
===========================================

An :py:class:`Engine <semolina.engines.base.Engine>` owns one ADBC connection
pool and the dialect for a warehouse. You build it once with
:py:func:`~semolina.config.create_engine`, then run queries through it. This guide
covers the two ways to use an engine, pool sizing, lifecycle, and querying
several warehouses side by side.

An :py:class:`AsyncEngine <semolina.engines.abase.AsyncEngine>` is its sibling,
built with :py:func:`~semolina.config.create_async_engine` from the same configs and
carrying the same dialect. Each section below covers both. Which kind you get is
fixed by which constructor you called, so an engine is never switched between
modes.

Two ways to use an engine
-------------------------

There are two patterns, and you can mix them in the same application.

The **direct engine** pattern keeps a reference to the engine and calls it
yourself. It mirrors SQLAlchemy: ``create_engine(...)`` hands you an engine, and
:py:meth:`engine.execute(query) <semolina.engines.base.Engine.execute>` runs a query
through its pool.

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

:py:func:`~semolina.config.create_engine` accepts either an ``adbc-poolhouse`` config
object or the name of a ``.semolina.toml`` connection section. The dialect is
derived from the config type, so you never select a backend by hand. What comes
back is the matching subclass, one of
:py:class:`~semolina.engines.snowflake.SnowflakeEngine`,
:py:class:`~semolina.engines.databricks.DatabricksEngine`, or
:py:class:`~semolina.engines.duckdb.DuckDBEngine`. Annotate against
:py:class:`Engine <semolina.engines.base.Engine>` rather than the subclass, since
that is what the factory's return type declares.

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

:py:func:`~semolina.config.create_async_engine` has the same signature and accepts the same
two argument forms:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import create_async_engine

   # From a config object
   engine = create_async_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_analytics",
           password="...",
           database="analytics",
           warehouse="compute_wh",
       )
   )

   # Or from a .semolina.toml connection name
   engine = create_async_engine("default")

Note the missing ``await``. Building a pool opens no connections, so
``create_async_engine()`` is an ordinary call you can make at import time or outside a
running event loop. Teardown is the half that is awaited -- see
`Manage the engine lifecycle`_ below. Async support needs the ``semolina[async]``
extra; see :ref:`tutorial-installation`.

Size the pool
-------------

Pool sizing lives on the config object, for async pools as much as synchronous ones.
The config classes carry ``pool_size`` (steady-state connections), ``max_overflow``
(burst capacity above ``pool_size``), ``timeout``, and ``recycle``. For Snowflake and
Databricks the defaults are 5 and 3, so up to 8 concurrent connections:

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

Both pool kinds read these fields from the config you pass, so an async pool is sized
the same way a synchronous one is. Nothing extra is needed to size it, and there is no
async-only tuning knob.

.. warning:: The checkout timeout raises SQLAlchemy's ``TimeoutError``, not Python's

   When every connection is busy and none frees up within ``timeout`` seconds, the
   checkout fails with ``sqlalchemy.exc.TimeoutError``. That class derives from
   ``SQLAlchemyError``, **not** from the builtin :py:class:`TimeoutError`, so a bare
   ``except TimeoutError:`` does not catch it.

   Import it explicitly to map pool exhaustion onto a 503:

   .. code-block:: python

      from sqlalchemy.exc import TimeoutError as PoolTimeout

      try:
          cursor = query.execute()
      except PoolTimeout:
          raise HTTPException(
              status_code=503,
              detail="No warehouse connection available",
          )

   This applies to async engines too. The async pool offloads the same checkout to a
   worker thread, so the same exception surfaces from ``aexecute()``.


.. tip::

   Start with ``pool_size`` matching your expected concurrent query count (e.g. web
   server worker count), and set ``max_overflow`` to 50--100% of ``pool_size`` for
   traffic spikes. A ``recycle`` of 1800 seconds (30 minutes) prevents stale connections
   from accumulating during low-traffic periods.

.. note::

   DuckDB sizes itself from the database you point it at. An in-memory database
   (``:memory:``) pins ``pool_size`` to 1, because in-memory databases are isolated per
   connection: several pooled connections would each see a different empty database
   rather than sharing one. Asking for ``pool_size > 1`` with ``:memory:`` is a
   configuration error and raises a ``ValidationError`` when the config is built. A
   file-backed database path defaults to 5 and can be raised. Use one when you need
   concurrent connections, including for the async path, where a single connection
   serializes every query behind one slot.

The pool is also your concurrency bound. ``adbc-poolhouse`` gives each async pool a
capacity limiter sized to ``pool_size + max_overflow``, so that many queries can be in
flight and the rest wait for a slot. Semolina adds no second bound of its own -- no
semaphore, no worker count to tune. Raise or lower concurrency by changing
``pool_size`` and ``max_overflow``. Wrapping your own semaphore around ``aexecute()``
stacks a second limit on top of the pool's and generally just lowers throughput below
what you configured.

Open a raw connection
---------------------

When you need to run something the query builder does not cover, check a
connection out of the engine's pool with
:py:meth:`engine.connect() <semolina.engines.base.Engine.connect>`. It is a context
manager, so the connection returns to the pool on exit:

.. code-block:: python

   with engine.connect() as conn:
       cur = conn.cursor()
       cur.execute("SHOW VIEWS")
       rows = cur.fetchall()

Manage the engine lifecycle
---------------------------

Create the engine at application startup and close it at shutdown.
:py:meth:`engine.dispose() <semolina.engines.base.Engine.dispose>` releases both the pool
and the underlying ADBC source connection:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

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
   engine.dispose()

:py:func:`~semolina.registry.unregister` removes the engine from the registry so no new
queries resolve it. ``dispose()`` then closes the pool and the ADBC driver connection.

An async engine is disposed the same way, with an ``await``:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import (
       create_async_engine,
       register_async_engine,
       unregister_async_engine,
   )

   # Startup -- an ordinary call
   engine = create_async_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_analytics",
           password="...",
           database="analytics",
           warehouse="compute_wh",
           pool_size=10,
       )
   )
   register_async_engine("default", engine)

   # ... application runs ...

   # Shutdown -- awaited
   unregister_async_engine("default")
   await engine.dispose()

That asymmetry is not an oversight. Constructing a pool opens no connections and does
no I/O, so there is nothing to await. Disposing it closes live driver connections, which
is I/O, and the async engine offloads that work rather than blocking the event loop with
it during shutdown.

.. warning::

   Dispose the engine rather than reaching into ``engine._pool`` yourself.
   ``dispose()`` closes the underlying ADBC source connection as well as the pool, and
   it picks the right teardown call for the pool kind. On an async engine the pool's own
   ``close()`` is a coroutine, so calling it without awaiting closes nothing and leaks
   the pool silently.

Look up a registered engine
---------------------------

:py:func:`~semolina.registry.get_engine` returns the engine registered under a name, so you
can reach it without keeping your own reference:

.. code-block:: python

   from semolina import get_engine

   engine = get_engine("default")

Call it with no argument (or ``None``) to get the ``"default"`` engine -- the same
lookup ``.execute()`` performs when a query has no ``.using()`` clause:

.. code-block:: python

   engine = get_engine()  # the "default" engine

To close an engine at shutdown without tracking your own reference, look it up,
unregister it, then dispose it:

.. code-block:: python

   from semolina import get_engine, unregister

   engine = get_engine("reports")
   unregister("reports")
   engine.dispose()

If no engine is registered under the name, ``get_engine`` raises ``ValueError``
listing the names that are available.

Async engines live in a separate registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:func:`~semolina.registry.register_async_engine`,
:py:func:`~semolina.registry.get_async_engine`, and
:py:func:`~semolina.registry.unregister_async_engine` are the async trio, and they
operate on their own store:

.. code-block:: python

   from semolina import (
       create_async_engine,
       get_async_engine,
       register_async_engine,
       unregister_async_engine,
   )

   register_async_engine(
       "reports", create_async_engine("reports")
   )

   # get_async_engine() with no argument resolves "default"
   engine = get_async_engine("reports")

   unregister_async_engine("reports")
   await engine.dispose()

The two registries are genuinely separate, which has two consequences.
One name can hold a sync engine and an async engine at the same time, which is
what you want when the same warehouse is queried from both a batch script and a request
handler. And ``get_async_engine`` never falls back to the sync store: a name registered
only with :py:func:`~semolina.registry.register` raises ``ValueError`` when the async path looks
it up. The error names the async registration function, so a lookup that fails this way
tells you which call you skipped rather than failing later inside query execution.

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

On the async path the same ``.using()`` clause resolves against the async registry:

.. code-block:: python

   async with await (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .using("reports")
       .aexecute()
   ) as cursor:
       rows = await cursor.fetchall_rows()

So a name you use with ``aexecute()`` has to have been registered with
``register_async_engine()``. Registering ``"reports"`` synchronously and then reaching
for it from ``aexecute()`` raises rather than silently running your query somewhere
unexpected.

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

   from semolina import get_engine, unregister

   for name in ("default", "reports"):
       engine = get_engine(name)
       unregister(name)
       engine.dispose()

:py:func:`~semolina.registry.get_engine` lets you reach each engine by name at shutdown, so
you do not have to thread engine references through your application.

Async engines are closed in the same loop, one ``await`` at a time:

.. code-block:: python

   from semolina import (
       get_async_engine,
       unregister_async_engine,
   )

   for name in ("default", "reports"):
       engine = get_async_engine(name)
       unregister_async_engine(name)
       await engine.dispose()

If your application runs both kinds, close both. Neither loop sees the other's engines,
even where the names match.

See also
--------

- :ref:`howto-backends-overview` -- connection patterns and backend selection
- :ref:`howto-backends-snowflake` -- Snowflake TOML fields and credentials
- :ref:`howto-backends-databricks` -- Databricks TOML fields and credentials
- :ref:`howto-backends-duckdb` -- DuckDB TOML fields and connection details
- :ref:`howto-web-api` -- engine lifecycle in a FastAPI application, sync and async
- :ref:`howto-streaming` -- stream rows with ``for row in cursor:`` or ``async for``
- :ref:`tutorial-installation` -- install the ``semolina[async]`` extra
- :ref:`reference-config` -- the ``.semolina.toml`` file format
