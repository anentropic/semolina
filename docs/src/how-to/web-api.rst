How to use Semolina in a web API
=================================

Integrate Semolina queries into FastAPI endpoints. This guide covers pool lifecycle,
request-scoped queries, conditional filters from query parameters, and error handling.

Set up the pool at application startup
---------------------------------------

Create the connection pool in a FastAPI lifespan handler so it is ready before the
first request and closed cleanly on shutdown:

.. code-block:: python
   :caption: app.py

   from contextlib import asynccontextmanager

   from adbc_poolhouse import (
       SnowflakeConfig,
       create_pool,
       close_pool,
   )
   from fastapi import FastAPI

   from semolina import register, unregister


   @asynccontextmanager
   async def lifespan(app: FastAPI):
       config = SnowflakeConfig(
           account="xy12345.us-east-1",
           user="svc_dashboard",
           password="...",
           database="analytics",
           warehouse="compute_wh",
       )
       pool = create_pool(config, pool_size=10, max_overflow=5)
       register("default", pool, dialect="snowflake")
       yield
       unregister("default")
       close_pool(pool)


   app = FastAPI(lifespan=lifespan)

The pool is registered once at startup. Every endpoint that calls ``.execute()`` reuses
connections from this pool. See :doc:`connection-pools` for pool sizing guidance.

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
semantic view does not exist in the warehouse.

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

Query a different pool per endpoint
------------------------------------

If you register multiple pools (e.g. one per warehouse or workload), use ``.using()``
to direct each endpoint to the right pool:

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

See :doc:`connection-pools` for how to register multiple named pools.

See also
--------

- :doc:`connection-pools` -- pool sizing, lifecycle, and multiple pools
- :doc:`queries` -- full query builder API
- :doc:`serialization` -- result serialization patterns
- :doc:`filtering` -- field operators and boolean composition
