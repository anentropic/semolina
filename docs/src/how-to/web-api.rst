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
:py:func:`~semolina.config.create_async_engine` takes the same config object or connection
name, and :py:func:`~semolina.registry.register_async_engine` puts it in the async registry:

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

Define your :py:class:`~semolina.models.SemanticView` model and expose a query endpoint that
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

.. warning:: Column keys are whatever your warehouse called them

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are the
   result column names exactly as the driver reports them. Only DuckDB happens to spell
   them like Python identifiers. The same query returns ``COUNTRY`` and ``AGG("REVENUE")``
   on Snowflake, and ``country`` and ``measure(revenue)`` on Databricks, so
   ``row.revenue`` raises ``AttributeError`` there. See
   :ref:`howto-result-column-names` before you deploy against a real warehouse.

This matters more in an API than in a script: the keys become your response body's
field names. Map them explicitly or return typed objects
(:ref:`howto-typed-results`) rather than letting the warehouse's spelling leak into
your public JSON.

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
the same :py:class:`~semolina.results.Row` objects, and ``cursor.description`` and
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

**What reaches your handler is the ADBC driver's own exception.** ``.execute()`` and
``aexecute()`` build the SQL, check a connection out of the pool, and run it. If the
driver raises, Semolina returns the connection to the pool and re-raises the exception
unchanged. It does not wrap, translate, or classify it.

So the type to catch is ``adbc_driver_manager.Error`` and its subclasses. The DBAPI
hierarchy applies: ``Error`` is the base, ``DatabaseError`` sits under it, and
``ProgrammingError``, ``OperationalError``, ``DataError``, ``IntegrityError``,
``InternalError``, and ``NotSupportedError`` sit under ``DatabaseError``.
``InterfaceError`` sits directly under ``Error``.

.. code-block:: python

   from adbc_driver_manager import (
       Error,
       OperationalError,
       ProgrammingError,
   )
   from fastapi import HTTPException


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
           rows = cursor.fetchall_rows()
       except OperationalError:
           # Connection lost, warehouse unreachable, statement aborted.
           raise HTTPException(
               status_code=503,
               detail="Data warehouse is unavailable",
           )
       except ProgrammingError:
           # Some drivers use this for bad SQL. Do not rely on it: see below.
           raise HTTPException(
               status_code=500,
               detail="Query could not be run",
           )
       except Error:
           # Anything else the driver raises.
           raise HTTPException(
               status_code=500,
               detail="Query failed",
           )

       return [dict(row) for row in rows]

**Which subclass you get is the driver's decision, not Semolina's, and it is not the one
you would guess.** Measured against the DuckDB driver:

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Failure
     - DuckDB
     - Snowflake / Databricks
   * - View or table does not exist
     - ``InternalError``
     - not yet measured
   * - Invalid SQL syntax
     - ``InternalError``
     - not yet measured
   * - Column does not exist
     - ``InternalError``
     - not yet measured
   * - Value fails to cast
     - ``ProgrammingError``
     - not yet measured

A missing view arriving as ``InternalError`` rather than ``ProgrammingError`` is the
useful lesson here: the subclass does not describe the failure the way its name suggests.
So catch ``Error`` and let the specific subclasses be an optimization you add only after
observing your own driver. Log the message; it carries the detail the class does not.

The Snowflake and Databricks columns are blank because measuring them needs a live
warehouse -- the recorded test cassettes contain only successful queries. Treat those two
drivers as "catch ``Error``" until someone fills the column in.

One failure never reaches the driver at all. If every pooled connection is busy and none
frees up within the pool's ``timeout``, the checkout fails first, with
``sqlalchemy.exc.TimeoutError`` -- SQLAlchemy's class, not the builtin
:py:class:`TimeoutError`, so a bare ``except TimeoutError:`` misses it. It is the
clearest 503 signal you have, because it means your pool is undersized rather than your
warehouse being down:

.. code-block:: python

   from sqlalchemy.exc import TimeoutError as PoolTimeout

   try:
       cursor = query.execute()
   except PoolTimeout:
       raise HTTPException(
           status_code=503,
           detail="No warehouse connection available",
       )

See :ref:`howto-connection-pools` for sizing the pool so this stays rare.

.. warning:: A missing view is not a 404

   There is no exception type that means "this semantic view does not exist" on the
   query path. A missing or misspelled view fails inside the warehouse like any other
   bad identifier, and arrives as a driver error. If your API needs to answer 404 for
   an unknown view, validate the view name against a list your application controls
   before building the query. Do not try to pattern-match the driver's message.

.. note:: ``SemolinaViewNotFoundError`` and ``SemolinaConnectionError`` are for codegen

   Both :py:exc:`~semolina.engines.base.SemolinaViewNotFoundError` and
   :py:exc:`~semolina.engines.base.SemolinaConnectionError` are raised only by
   :py:meth:`Engine.introspect() <semolina.engines.base.Engine.introspect>`, which is the
   introspection path behind :ref:`howto-codegen`. Nothing on the query path raises
   either one, so a ``try`` block around ``.execute()`` or ``aexecute()`` that catches
   them will never fire. Catch them when you call ``introspect()`` yourself; otherwise
   ignore them here.

.. note:: There is no common ``SemolinaError`` base class

   Semolina's four public exceptions are flat :py:class:`RuntimeError` subclasses with
   no shared parent. That is deliberate. A ``SemolinaError`` base would give you one
   ``except`` clause, but it would also group errors that have nothing to do with each
   other: a missing optional dependency, a DTO whose annotations disagree with the
   result schema, and a warehouse that will not answer are three unrelated problems with
   three different remedies. Catch the specific type you can actually act on.

The same applies to ``aexecute()``. It uses the identical error path, so the driver
exceptions above are what an ``async def`` handler sees too.

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
   :py:class:`~semolina.cursor.SemolinaCursor` has a finalizer that returns a forgotten
   connection to the pool, so the paragraph above is about promptness.
   :py:class:`~semolina.acursor.AsyncSemolinaCursor` cannot have that finalizer: closing it
   requires awaiting, and a finalizer cannot await.

   An async cursor closed by neither ``async with`` nor ``await cursor.aclose()``
   therefore holds its pooled connection for the life of the process. Nothing reclaims
   it later. Enough forgotten cursors exhaust the pool, and every subsequent request
   blocks until its checkout times out. The async cursor emits a ``ResourceWarning``
   when it is garbage collected unclosed, which tells you it happened but does not
   repair it.

.. _howto-web-api-timeouts:

Time out a slow query
----------------------

Put a deadline around the query so a slow one fails as a ``504`` instead of holding a
pooled connection until the client gives up:

.. code-block:: python

   import asyncio

   from fastapi import HTTPException


   @app.get("/api/sales")
   async def get_sales():
       query = (
           Sales.query()
           .metrics(Sales.revenue, Sales.cost)
           .dimensions(Sales.country)
       )
       try:
           async with asyncio.timeout(10):
               async with await query.aexecute() as cursor:
                   rows = await cursor.fetchall_rows()
       except TimeoutError:
           raise HTTPException(
               status_code=504,
               detail="Query exceeded its time budget",
           )

       return [dict(row) for row in rows]

``asyncio.timeout()`` fits FastAPI, which runs on asyncio. ``anyio.fail_after()`` does
the same job in code that has to run under either loop. Semolina imports neither, so
importing whichever one you need in your own application is fine.

The exception you catch is your framework's, not the driver's. adbc-poolhouse fires the
driver's cancel from inside a shield and re-raises the loop's cancellation in place of
ADBC's interrupt error, and Semolina's frames pass that through rather than catching it,
logging it, or converting it. Outside ``asyncio.timeout()`` you get ``TimeoutError``;
inside the block, and under ``anyio.fail_after()``, it is the loop's own cancellation
class.

A cancelled ``aexecute()`` raises rather than handing back a cursor. There is no
half-open cursor left over to find and close, and the ``async with`` above never starts.

The work stops in the warehouse, not only in your process. While the worker thread is
still inside the driver, adbc-poolhouse calls ``adbc_cancel`` on the connection from
inside a shield, so the statement is aborted rather than left to finish for nobody: a
cancelled aggregate returns in a small fraction of the time the same query takes when it
is left alone. On a metered warehouse that is the difference between a timed-out request
that stops costing you money and one that keeps billing for a result nobody will read.

The connection whose query was aborted is invalidated. adbc-poolhouse discards it
instead of handing it to the next caller, the pool opens a replacement, and its checkout
count returns to zero. The request after a timeout gets a working connection, and there
is nothing for you to reset.

Wrapping the whole ``async with`` block, as the snippet does, is safe, even though it
means the cursor tears down while the cancellation is propagating. Close runs in order
(reader, then cursor, then connection) and each step suppresses ``Exception`` rather
than ``BaseException``, so a ``ConnectionBusyError`` born during teardown cannot replace
the cancellation you need to see.

.. note::

   Aborting a ``semantic_view()`` query on DuckDB needs the ``semantic_views`` community
   extension at 0.12.0 or newer, which is what the pinned ``duckdb==1.5.5`` in the
   ``semolina[duckdb]`` extra installs. Builds below that floor evaluated the inner query
   on a separate client context, where DuckDB's per-context interrupt flag was never
   read, so a cancelled aggregate finished its work first and only then reported the
   interrupt.

.. _howto-web-api-client-disconnect:

Handle a client disconnect
---------------------------

Start from what your framework does, which is less than most people assume. Starlette,
which FastAPI routes requests through, awaits your handler directly and does not race it
against a disconnect watcher. The ASGI server delivers ``http.disconnect`` on the receive
channel, and a handler that never reads from that channel never finds out the client has
gone.

So a browser tab closed mid-request cancels nothing by itself. The query keeps running,
the pooled connection stays checked out, and on a metered warehouse the query keeps
billing until it finishes and the result is thrown away.

Turn the disconnect into a cancellation yourself. Run the query in a task group
alongside a poll of ``await request.is_disconnected()``, and cancel the group's scope
when the poll comes back true:

.. code-block:: python

   import anyio
   from fastapi import HTTPException, Request


   @app.get("/api/sales")
   async def get_sales(request: Request):
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
       )
       rows = None

       async with anyio.create_task_group() as task_group:

           async def watch_for_disconnect():
               while not await request.is_disconnected():
                   await anyio.sleep(0.5)
               task_group.cancel_scope.cancel()

           async def run_query():
               nonlocal rows
               async with await query.aexecute() as cursor:
                   rows = await cursor.fetchall_rows()
               task_group.cancel_scope.cancel()

           task_group.start_soon(watch_for_disconnect)
           task_group.start_soon(run_query)

       if rows is None:
           raise HTTPException(
               status_code=499,
               detail="Client disconnected",
           )

       return [dict(row) for row in rows]

``is_disconnected()`` is awaited but never blocks: it reads the receive channel inside an
already-cancelled scope, so it takes whatever message is sitting there and moves on. It
does consume from that channel, so pair this with a handler that is not also streaming
the request body.

Once the cancellation lands, everything in :ref:`howto-web-api-timeouts` applies. The
warehouse query aborts, ``aexecute()`` raises instead of handing back a cursor, and the
connection it was running on is invalidated and replaced.

One case the deadline section does not cover is worth stating on its own, because it is
the case a disconnect produces. When the cancellation arrives *after* the connection has
been checked out, with the statement already in flight, the slot still comes back: the
pool's checked-out count returns to zero and its checked-in count goes up by one. An
abandoned request costs you a cancelled query, not a connection.

Reach for the watcher only when you need it. A deadline is the simpler bound, it needs no
extra task, and it covers the abandoned request too, since a client that has gone away is
not waiting for the response that the timeout produces. The watcher earns its place when
a request may legitimately outlive any deadline you would be willing to set.

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
:py:func:`~semolina.registry.register` is invisible to ``aexecute()``, so register the engines
your async endpoints reach with :py:func:`~semolina.registry.register_async_engine`.

See also
--------

- :ref:`howto-connection-pools` -- pool sizing, lifecycle, and multiple engines
- :ref:`howto-streaming` -- stream rows one batch at a time, and cancel an
  ``async for`` mid-iteration
- :ref:`tutorial-installation` -- install the ``semolina[async]`` extra
- :ref:`howto-queries` -- full query builder API
- :ref:`howto-serialization` -- result serialization patterns
- :ref:`explanation-duckdb-vs-warehouse` -- why driver exception classes and result column
  names differ per backend, and which of them have actually been measured
- :ref:`howto-filtering` -- field operators and boolean composition
