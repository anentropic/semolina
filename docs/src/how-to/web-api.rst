.. _howto-web-api:

How to use Semolina in a web API
=================================

Integrate Semolina queries into FastAPI endpoints. This guide covers engine
lifecycle, request-scoped queries, conditional filters from query parameters, and
error handling, for both synchronous and ``async def`` handlers.

Set up the engine at application startup
----------------------------------------

Create the engine in a FastAPI lifespan handler so it is ready before the first
request and closed cleanly on shutdown. Register it under ``"default"`` so every
endpoint resolves it without passing it around:

.. code-block:: python
   :caption: app.py

   from contextlib import asynccontextmanager

   from adbc_poolhouse import SnowflakeConfig
   from fastapi import FastAPI

   from semolina import register, unregister, create_engine


   @asynccontextmanager
   async def lifespan(app: FastAPI):
       engine = create_engine(
           SnowflakeConfig(
               account="xy12345.us-east-1",
               user="svc_dashboard",
               password="...",
               database="analytics",
               warehouse="compute_wh",
               pool_size=10,
               max_overflow=5,
           )
       )
       register("default", engine)
       yield
       unregister("default")
       engine.dispose()


   app = FastAPI(lifespan=lifespan)

The engine is registered once at startup. Every endpoint that calls ``.execute()``
reuses connections from its pool. See :ref:`howto-connection-pools` for pool sizing
guidance.

Set up an async engine instead
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your handlers are ``async def``, build an async engine at startup instead.
:py:func:`~semolina.create_async_engine` takes the same config object or connection
name, and :py:func:`~semolina.register_async_engine` puts it in the async registry:

.. code-block:: python
   :caption: app.py

   from contextlib import asynccontextmanager

   from adbc_poolhouse import SnowflakeConfig
   from fastapi import FastAPI

   from semolina import (
       create_async_engine,
       register_async_engine,
       unregister_async_engine,
   )


   @asynccontextmanager
   async def lifespan(app: FastAPI):
       engine = create_async_engine(
           SnowflakeConfig(
               account="xy12345.us-east-1",
               user="svc_dashboard",
               password="...",
               database="analytics",
               warehouse="compute_wh",
               pool_size=10,
               max_overflow=5,
           )
       )
       register_async_engine("default", engine)
       yield
       unregister_async_engine("default")
       await engine.dispose()


   app = FastAPI(lifespan=lifespan)

Construction and teardown are asymmetric. Building the pool does no I/O, so
``create_async_engine()`` is a plain call. Disposing it closes ADBC driver resources,
so ``dispose()`` is awaited.

The async surface needs the ``semolina[async]`` extra -- a plain install of the package
does not carry it. See :ref:`tutorial-installation` for the install command.

Build a query endpoint
-----------------------

Define your :py:class:`~semolina.SemanticView` model and expose a query endpoint that
returns serialized results:

.. code-block:: python
   :caption: app.py (continued)

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   @app.get("/api/sales")
   def get_sales():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country)
           .execute()
       )
       rows = cursor.fetchall_rows()
       return [dict(row) for row in rows]

FastAPI serializes the list of dictionaries to JSON automatically.

A plain ``def`` handler is still a correct choice here. FastAPI runs it in a
threadpool, so a blocking ``.execute()`` does not stall the event loop, and an
application whose synchronous handlers already work has no reason to be rewritten.
The async form below is for handlers that are ``async def`` for other reasons, or
for a framework that has no threadpool fallback.

Serve a query from an async endpoint
-------------------------------------

In an ``async def`` handler, call ``aexecute()`` on the query instead of ``execute()``, and hold
the cursor open with ``async with``:

.. code-block:: python
   :caption: app.py (continued)

   @app.get("/api/sales")
   async def get_sales():
       query = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country)
       )
       async with await query.aexecute() as cursor:
           rows = await cursor.fetchall_rows()
       return [dict(row) for row in rows]

Two things differ from the synchronous handler, and nothing else does. The execute
call is awaited, and the fetch methods keep their names but are awaited too. Rows are
the same :py:class:`~semolina.Row` objects, and ``cursor.description`` and
``cursor.rowcount`` are still plain attribute reads with no ``await``, because
adbc-poolhouse keeps them synchronous.

``await query.aexecute()`` returns a cursor that is already open, which is why the
call site reads ``async with await ...``. Query building is unchanged: the same
``.metrics()``, ``.dimensions()``, ``.where()``, and ``.limit()`` calls apply, and only
the final step differs.

.. note::

   Your code imports neither ``asyncio`` nor ``anyio``, and the handler above runs
   unchanged under asyncio or Trio. Semolina awaits adbc-poolhouse's coroutines and
   adds no loop-specific code of its own, so the backend is whichever one your
   framework is already running. There is nothing to configure.

Apply conditional filters from query parameters
-------------------------------------------------

Use optional query parameters to build filters dynamically. Pass ``None`` to
``.where()`` as a no-op when a parameter is not provided:

.. code-block:: python

   from fastapi import Query


   @app.get("/api/sales")
   def get_sales(
       country: str | None = Query(default=None),
       min_revenue: int | None = Query(default=None),
       limit: int = Query(default=100, ge=1, le=1000),
   ):
       query = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country, Sales.region)
       )

       query = query.where(
           Sales.country == country if country else None,
           (
               Sales.revenue >= min_revenue
               if min_revenue
               else None
           ),
       )
       query = query.limit(limit)

       cursor = query.execute()
       rows = cursor.fetchall_rows()
       return [dict(row) for row in rows]

Each filter is only applied when the corresponding query parameter is present. Requests
like ``GET /api/sales?country=US&limit=50`` produce a ``WHERE`` clause; requests to
``GET /api/sales`` return unfiltered results.

.. tip::

   Queries are immutable -- each ``.where()`` and ``.limit()`` call returns a new query
   instance. You can safely build up the query across multiple conditionals without
   affecting the original.

Handle errors
--------------

Wrap ``.execute()`` to catch connection and view-not-found errors. Return appropriate
HTTP status codes instead of leaking warehouse exceptions:

.. code-block:: python

   from fastapi import HTTPException

   from semolina import (
       SemolinaConnectionError,
       SemolinaViewNotFoundError,
   )


   @app.get("/api/sales")
   def get_sales(
       country: str | None = Query(default=None),
       limit: int = Query(default=100, ge=1, le=1000),
   ):
       query = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country, Sales.region)
           .where(
               Sales.country == country if country else None
           )
           .limit(limit)
       )

       try:
           cursor = query.execute()
       except SemolinaConnectionError:
           raise HTTPException(
               status_code=503,
               detail="Data warehouse is unavailable",
           )
       except SemolinaViewNotFoundError:
           raise HTTPException(
               status_code=404,
               detail="Requested data view does not exist",
           )

       rows = cursor.fetchall_rows()
       return [dict(row) for row in rows]

:py:class:`~semolina.SemolinaConnectionError` covers authentication failures and
network issues. :py:class:`~semolina.SemolinaViewNotFoundError` is raised when the
semantic view does not exist in the warehouse. Both apply to ``aexecute()`` as well;
wrap it in the same ``try`` block.

One failure mode on the async path has no synchronous counterpart. An ADBC connection
permits serialized access but not concurrent access, so sharing one cursor or one
connection between concurrently running tasks raises ``ConnectionBusyError`` from
adbc-poolhouse. Semolina lets that exception through unwrapped, because its own message
already names the fix: check out a separate connection per task. Each ``aexecute()``
call checks out its own connection, so a handler that awaits its own query never
reaches this. You get there by holding one cursor and driving it from two tasks. The
remedy is a separate ``aexecute()`` call per task, not a lock around the shared one.
The pool rejects the concurrent access rather than serializing it on purpose: a lock
would let two tasks' statements interleave inside one transaction, which the driver
accepts and which quietly corrupts the results.

Use the cursor as a context manager
------------------------------------

For endpoints that process results before returning, use the cursor as a context manager
to ensure the connection is released back to the pool promptly:

.. code-block:: python

   @app.get("/api/sales/summary")
   def get_sales_summary():
       with Sales.query(
           metrics=[Sales.revenue, Sales.cost],
           dimensions=[Sales.country],
       ).execute() as cursor:
           rows = cursor.fetchall_rows()

       # cursor and connection are closed here
       return {
           "total_countries": len(rows),
           "results": [dict(row) for row in rows],
       }

Without a context manager, the connection is released when the cursor is garbage
collected. Using ``with`` makes the release deterministic and immediate.

.. _howto-web-api-async-cursor-close:

Close async cursors with ``async with``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the async path, use ``async with``:

.. code-block:: python

   @app.get("/api/sales/summary")
   async def get_sales_summary():
       query = Sales.query(
           metrics=[Sales.revenue, Sales.cost],
           dimensions=[Sales.country],
       )
       async with await query.aexecute() as cursor:
           rows = await cursor.fetchall_rows()

       # reader, cursor, and connection are closed here
       return {
           "total_countries": len(rows),
           "results": [dict(row) for row in rows],
       }

.. warning:: ``async with`` is required, not recommended

   The two cursors do not behave the same way when you forget to close them.
   :py:class:`~semolina.SemolinaCursor` has a finalizer that returns a forgotten
   connection to the pool, so the paragraph above is about promptness.
   :py:class:`~semolina.AsyncSemolinaCursor` cannot have that finalizer: closing it
   requires awaiting, and a finalizer cannot await.

   An async cursor closed by neither ``async with`` nor ``await cursor.aclose()``
   therefore holds its pooled connection for the life of the process. Nothing reclaims
   it later. Enough forgotten cursors exhaust the pool, and every subsequent request
   blocks until its checkout times out. The async cursor emits a ``ResourceWarning``
   when it is garbage collected unclosed, which tells you it happened but does not
   repair it.

Query a different engine per endpoint
-------------------------------------

If you register multiple engines (e.g. one per warehouse or workload), use
``.using()`` to direct each endpoint to the right engine:

.. code-block:: python

   @app.get("/api/sales")
   def get_sales():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .using("default")
           .execute()
       )
       return [dict(row) for row in cursor.fetchall_rows()]


   @app.get("/api/reports/sales")
   def get_sales_report():
       cursor = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country, Sales.region)
           .using("reports")
           .execute()
       )
       return [dict(row) for row in cursor.fetchall_rows()]

See :ref:`howto-connection-pools` for how to register multiple named engines.

On the async path ``.using(name)`` resolves against the async registry, which is a
separate store from the synchronous one. A name registered with
:py:func:`~semolina.register` is invisible to ``aexecute()``, so register the engines
your async endpoints reach with :py:func:`~semolina.register_async_engine`.

See also
--------

- :ref:`howto-connection-pools` -- pool sizing, lifecycle, and multiple engines
- :ref:`howto-streaming` -- stream rows one batch at a time, synchronously or with ``async for``
- :ref:`tutorial-installation` -- install the ``semolina[async]`` extra
- :ref:`howto-queries` -- full query builder API
- :ref:`howto-serialization` -- result serialization patterns
- :ref:`howto-filtering` -- field operators and boolean composition
