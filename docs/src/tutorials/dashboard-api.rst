.. _tutorial-dashboard-api:

Serve a dashboard endpoint
==========================

Semolina exists to put semantic-layer data behind an HTTP API. In this tutorial
you will build that API: a FastAPI service that opens an engine at startup,
answers ``GET /revenue`` from a semantic view, takes a filter off a query
parameter, and returns a typed JSON body your frontend can rely on.

You will hit the two problems that catch every first attempt -- the response
carries the warehouse's column names, and it has no schema -- and fix both with
one Pydantic class.

Everything runs against the local ``tutorial.db``, so no warehouse is involved.

**Prerequisites:** :ref:`tutorial-first-query`, the ``tutorial.db`` database its
setup script builds, and these installs:

.. code-block:: bash

   pip install "semolina[arrowmodel]"
   pip install fastapi "uvicorn[standard]"

The ``arrowmodel`` extra is what
:py:meth:`~semolina.cursor.SemolinaCursor.into` needs. A plain
``pip install semolina`` does not carry it.

1. Open the engine at startup
-----------------------------

An engine owns a connection pool, so building one per request would open and
close a warehouse connection per request. Build it once in a FastAPI
``lifespan`` handler instead, register it under ``"default"``, and take it down
on shutdown.

Create ``app.py``:

.. code-block:: python
   :caption: app.py

   from contextlib import asynccontextmanager

   from adbc_poolhouse import DuckDBConfig
   from fastapi import FastAPI

   from semolina import (
       Dimension,
       Metric,
       SemanticView,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   @asynccontextmanager
   async def lifespan(app: FastAPI):
       with create_engine(
           DuckDBConfig(database="tutorial.db"), register=True
       ):
           yield


   app = FastAPI(lifespan=lifespan)

Everything before the ``yield`` runs at startup and everything after it runs at
shutdown, and the ``with`` block spans both. ``register=True`` files the engine
in the registry under the connection name, which is how a query with no
``.using()`` call finds it. A config object carries no connection name, so this
one is registered as ``"default"`` -- the name a query looks for when you do not
give it another. Leaving the block on shutdown takes that name back out and then
disposes the pool.

Without the block you would write those two teardown steps yourself, in that
order. :ref:`howto-connection-pools` shows the long form and when you want it.

Swapping DuckDB for a real warehouse is a change to this one function: pass a
``SnowflakeConfig`` or ``DatabricksConfig`` instead, and size its pool. See
:ref:`howto-connection-pools` for the sizing decision and
:ref:`howto-backends-overview` for the connection settings.

2. Answer a request from the view
---------------------------------

Add an endpoint that runs the report query from the last tutorial and returns
the rows. Append this to ``app.py``:

.. code-block:: python
   :caption: app.py (continued)

   @app.get("/revenue")
   def revenue():
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .order_by(Sales.revenue.desc())
       )
       with query.execute() as cursor:
           return [dict(row) for row in cursor.fetchall_rows()]

The ``with`` block matters more here than it did in a script. It returns the
pooled connection the moment the handler is done with it, rather than whenever
the cursor is garbage collected, and a web application is exactly the setting
where that difference adds up.

A plain ``def`` handler is a deliberate choice, not a simplification. FastAPI
runs one in a threadpool, so a blocking ``.execute()`` does not stall the event
loop. :ref:`howto-web-api` covers the ``async def`` form for handlers that need
it.

Start the server:

.. code-block:: bash

   uvicorn app:app --reload

And ask it for the report:

.. code-block:: console

   $ curl -s http://127.0.0.1:8000/revenue
   [{"country":"CA","revenue":2000},{"country":"US","revenue":1500}]

3. See what is wrong with that response
---------------------------------------

That body looks correct, and that is the trap. Two things about it will not
survive contact with a real deployment.

**The keys are the warehouse's, not yours.** Semolina adds no ``AS`` aliases and
does no case folding, so ``dict(row)`` hands you the result column names exactly
as the driver reports them. Only DuckDB spells them like Python identifiers. Run
the same handler against Snowflake and your frontend receives this instead:

.. code-block:: json

   [{"COUNTRY": "CA", "AGG(\"REVENUE\")": 2000}]

The escaped quotes are in the JSON key. Your clients would have to parse them,
and they would break again on Databricks, which returns ``measure(revenue)``.
See :ref:`howto-result-column-names` for the full table.

**There is no schema.** The handler's return type is a list of dictionaries, so
FastAPI has nothing to put in ``/docs``, nothing to validate against, and no
type your editor can check a caller against.

A third problem is waiting on the warehouses this one does not reach. A money
metric arrives from Snowflake as a :py:class:`decimal.Decimal`, and FastAPI's
encoder turns a ``Decimal`` into a JSON float. ``12345678901234567890.99``
leaves as ``1.2345678901234567e+19``. Nothing raises, and nothing tells you.

All three have the same fix.

4. Return a typed object instead
--------------------------------

Declare a Pydantic class describing the response you want, hand it to
:py:meth:`~semolina.cursor.SemolinaCursor.into`, and return the instances.
FastAPI serializes them and generates the schema from the same declaration.

Add the class near the top of ``app.py``:

.. code-block:: python
   :caption: app.py

   import pydantic


   class RevenueByCountry(pydantic.BaseModel):
       country: str
       revenue: int

Then rewrite the handler to use it:

.. code-block:: python
   :caption: app.py (continued)

   @app.get("/revenue")
   def revenue() -> list[RevenueByCountry]:
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .order_by(Sales.revenue.desc())
       )
       with query.execute() as cursor:
           return cursor.into(RevenueByCountry)

``.into()`` matches result columns to fields by name and builds one instance per
row. The body is unchanged, because the names already agreed on DuckDB:

.. code-block:: console

   $ curl -s http://127.0.0.1:8000/revenue
   [{"country":"CA","revenue":2000},{"country":"US","revenue":1500}]

What changed is everything around it. Open http://127.0.0.1:8000/docs and the
endpoint now documents its response:

.. code-block:: json

   {
     "properties": {
       "country": {"type": "string", "title": "Country"},
       "revenue": {"type": "integer", "title": "Revenue"}
     },
     "type": "object",
     "required": ["country", "revenue"],
     "title": "RevenueByCountry"
   }

The field names in that schema are yours. On Snowflake you keep them by telling
the field which column to read:

.. code-block:: python

   revenue: decimal.Decimal | None = pydantic.Field(
       validation_alias='AGG("REVENUE")'
   )

The JSON key stays ``revenue`` whichever warehouse is underneath, which is the
whole point. :ref:`tutorial-warehouse-models` generates that class for you
rather than making you look the spellings up.

.. note:: ``revenue: int`` is DuckDB's answer, not a universal one

   By default ``.into()`` holds you to the type the column actually arrives as,
   and refuses the call with
   :py:exc:`~semolina.exceptions.SemolinaSchemaMismatchError` when an annotation
   disagrees. ``sales_data.revenue`` is an ``INTEGER`` here, so summing it gives
   an ``int``. The same metric is a ``Decimal`` on Snowflake and a ``str`` on
   Databricks. :ref:`howto-typed-results` covers the check and the ``validate=``
   escape hatch; :ref:`explanation-type-fidelity` covers why the warehouse gets
   to decide.

5. Filter from a query parameter
--------------------------------

A dashboard sends the filter with the request. Take it as an optional query
parameter and pass it to ``.where()``:

.. code-block:: python
   :caption: app.py (continued)

   from fastapi import Query


   @app.get("/revenue")
   def revenue(
       country: str | None = Query(default=None),
   ) -> list[RevenueByCountry]:
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(
               Sales.country == country if country else None
           )
           .order_by(Sales.revenue.desc())
       )
       with query.execute() as cursor:
           return cursor.into(RevenueByCountry)

``.where(None)`` is a no-op, so one expression covers both the filtered and the
unfiltered request without an ``if`` statement around the query:

.. code-block:: console

   $ curl -s "http://127.0.0.1:8000/revenue?country=US"
   [{"country":"US","revenue":1500}]

   $ curl -s "http://127.0.0.1:8000/revenue?country=ZZ"
   []

That ``country`` value came off the URL and went into the query without being
escaped or allow-listed, which is correct. Snowflake and DuckDB send it as a
bound parameter, and Databricks escapes it at one audited site because its
driver refuses bind parameters. :ref:`howto-filtering` has the detail, including
the one thing you do still have to validate.

6. Answer when the warehouse does not
-------------------------------------

``.execute()`` re-raises whatever the ADBC driver raised, unchanged. The base
class of that hierarchy is ``adbc_driver_manager.Error``, and catching it is how
a dead warehouse becomes a ``503`` instead of a ``500`` with a stack trace in
it:

.. code-block:: python
   :caption: app.py (continued)

   from adbc_driver_manager import Error
   from fastapi import HTTPException


   @app.get("/revenue")
   def revenue(
       country: str | None = Query(default=None),
   ) -> list[RevenueByCountry]:
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(
               Sales.country == country if country else None
           )
           .order_by(Sales.revenue.desc())
       )
       try:
           with query.execute() as cursor:
               return cursor.into(RevenueByCountry)
       except Error:
           raise HTTPException(
               status_code=503,
               detail="Data warehouse is unavailable",
           )

Try it. Stop the server, move the database out of the way, and start it again:

.. code-block:: bash

   mv tutorial.db tutorial.db.bak
   uvicorn app:app

.. code-block:: console

   $ curl -s -i http://127.0.0.1:8000/revenue
   HTTP/1.1 503 Service Unavailable
   content-type: application/json

   {"detail":"Data warehouse is unavailable"}

Put it back with ``mv tutorial.db.bak tutorial.db`` before moving on. DuckDB
created an empty ``tutorial.db`` when the handler asked for a connection, so
delete that one first.

Catch ``Error`` rather than a subclass. Which subclass you get is the driver's
decision and it does not follow the name: the missing view above arrives as
``InternalError``, not ``ProgrammingError``. :ref:`howto-web-api` has the
measured table, along with the pool-checkout timeout that never reaches the
driver at all.

Complete example
----------------

The whole service, ready to run with ``uvicorn app:app --reload``:

.. code-block:: python
   :caption: app.py

   from contextlib import asynccontextmanager

   import pydantic
   from adbc_driver_manager import Error
   from adbc_poolhouse import DuckDBConfig
   from fastapi import FastAPI, HTTPException, Query

   from semolina import (
       Dimension,
       Metric,
       SemanticView,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   class RevenueByCountry(pydantic.BaseModel):
       country: str
       revenue: int


   @asynccontextmanager
   async def lifespan(app: FastAPI):
       with create_engine(
           DuckDBConfig(database="tutorial.db"), register=True
       ):
           yield


   app = FastAPI(lifespan=lifespan)


   @app.get("/revenue")
   def revenue(
       country: str | None = Query(default=None),
   ) -> list[RevenueByCountry]:
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(
               Sales.country == country if country else None
           )
           .order_by(Sales.revenue.desc())
       )
       try:
           with query.execute() as cursor:
               return cursor.into(RevenueByCountry)
       except Error:
           raise HTTPException(
               status_code=503,
               detail="Data warehouse is unavailable",
           )

Two requests to check it:

.. code-block:: console

   $ curl -s http://127.0.0.1:8000/revenue
   [{"country":"CA","revenue":2000},{"country":"US","revenue":1500}]

   $ curl -s "http://127.0.0.1:8000/revenue?country=US"
   [{"country":"US","revenue":1500}]

Next steps
----------

You have a working endpoint and no test for it. Next, run this query code
against a semantic view built inside the test process:

:ref:`Test queries without a warehouse <tutorial-testing-queries>`

See also
--------

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Semolina in a web API
      :link: howto-web-api
      :link-type: ref

      ``async def`` handlers, query timeouts, client disconnects, per-endpoint
      engines, and the driver exception classes measured per backend.

   .. grid-item-card:: Typed results
      :link: howto-typed-results
      :link-type: ref

      Column aliases, the schema check and ``validate=``, streaming with
      ``iter_into()``, and serializing rows without a DTO.

   .. grid-item-card:: Generate the DTO
      :link: howto-dto-codegen
      :link-type: ref

      ``semolina codegen-dto``, its ``pyproject.toml`` config, and the
      ``--check`` run for CI.

   .. grid-item-card:: Connection pools
      :link: howto-connection-pools
      :link-type: ref

      Sizing the pool this app opened, and registering more than one engine.

   .. grid-item-card:: Type fidelity
      :link: explanation-type-fidelity
      :link-type: ref

      Why a money column arrives as a ``Decimal`` and what the schema check
      promises.

   .. grid-item-card:: DuckDB vs your warehouse
      :link: explanation-duckdb-vs-warehouse
      :link-type: ref

      Which parts of this tutorial a DuckDB-only run cannot prove.
