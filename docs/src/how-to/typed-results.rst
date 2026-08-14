.. _howto-typed-results:

How to get typed objects from a result
=======================================

A dashboard backend usually wants objects, not rows. This guide converts a
query result straight into Pydantic instances with
:py:meth:`~semolina.SemolinaCursor.into`, so your response layer gets
something it can serialize and your editor gets something it can
autocomplete.

Four forms are covered, all of them over the same query: the whole result
at once, the streaming form for a result you would rather not hold in
memory, and the async version of each. After that come the parts that are
cheaper to read here than to find out from a production incident, starting
with the one that breaks the moment you point this at a real warehouse.

This guide assumes you already have a :py:class:`~semolina.SemanticView`
subclass and a registered engine. See :ref:`howto-queries` if you need
setup first.

Typed results need the ``arrowmodel`` extra:

.. code-block:: bash

   pip install semolina[arrowmodel]

That one extra is enough. It brings pyarrow with it, which both the
schema check and the whole-result form read through.

The snippets reuse this model and this DTO:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()

.. code-block:: python

   import decimal

   import pydantic


   class RevenueByCountry(pydantic.BaseModel):
       country: str
       revenue: decimal.Decimal

Any ``pydantic.BaseModel`` subclass works. arrowmodel ships an
``ArrowModel`` base class and you can use it, but ``.into()`` does not ask
for it and you gain nothing here by inheriting from it.

``revenue`` is annotated :py:class:`decimal.Decimal` because a money
column arrives as one on all three backends. If the metric in your view
sums an integer column, annotate it ``int`` instead. See
:ref:`explanation-type-fidelity` for why the warehouse decides this and
you do not.

Convert the whole result
-------------------------

Call :py:meth:`~semolina.SemolinaCursor.into` with the DTO class:

.. code-block:: python

   with Sales.query().metrics(Sales.revenue).dimensions(
       Sales.country
   ).execute() as cursor:
       rows = cursor.into(RevenueByCountry)

   # [RevenueByCountry(country='US',
   #                   revenue=Decimal('43.25')), ...]

You get a plain ``list``, one instance per result row, empty if the query
matched nothing. Columns are matched to fields by name. Result columns
your DTO does not declare are dropped, so one DTO can serve several
queries and a query can gain a column without breaking the DTOs already
reading it.

Because these are Pydantic models, a FastAPI handler can return the list
directly and let the framework serialize it:

.. code-block:: python

   @app.get("/revenue")
   def revenue() -> list[RevenueByCountry]:
       with Sales.query().metrics(Sales.revenue).dimensions(
           Sales.country
       ).execute() as cursor:
           return cursor.into(RevenueByCountry)

Conversion happens in Rust, over the Arrow buffers the driver already
produced, with no intermediate Python dictionaries. It reads the whole
result into memory first, the same as
:py:meth:`~semolina.SemolinaCursor.fetch_arrow_table`.

Stream instances one at a time
-------------------------------

When the result is larger than you want to hold,
:py:meth:`~semolina.SemolinaCursor.iter_into` gives you the same
instances lazily:

.. code-block:: python

   with Sales.query().metrics(Sales.revenue).dimensions(
       Sales.country
   ).execute() as cursor:
       for dto in cursor.iter_into(RevenueByCountry):
           handle(dto)

Instances arrive one at a time, but conversion still happens a whole
Arrow batch at a time, which is where the speed comes from. Consuming one
instance pulls exactly one batch from the underlying reader, so peak
memory is bounded by a batch rather than by the result.

Two behaviours are worth knowing before you use it.

A bad DTO raises on the ``iter_into(...)`` line itself, not on the first
loop pass. The method runs the schema check and then returns a generator,
rather than being a generator function whose body waits for the first
``next()``. That is the opposite of what a returned iterator usually does,
and it is deliberate: the traceback points at the line that named the
wrong type.

The iterator drives the cursor's one underlying Arrow stream, exactly as
:py:meth:`~semolina.SemolinaCursor.fetch_record_batch` does. Pick one
consumption pattern per cursor and finish it, because a second consumer
picks up wherever the first stopped rather than starting again. Keep the
cursor open until the loop ends; the ``with`` block does that for you.

Do the same from an async handler
----------------------------------

Both methods have async twins on
:py:class:`~semolina.AsyncSemolinaCursor`. Execute with ``aexecute()``,
then await ``into()``:

.. code-block:: python

   async with await Sales.query().metrics(
       Sales.revenue
   ).dimensions(Sales.country).aexecute() as cursor:
       rows = await cursor.into(RevenueByCountry)

The streaming form is not awaited. ``iter_into()`` is a plain method that
hands back an async iterator, so it goes straight into ``async for``:

.. code-block:: python

   async with await Sales.query().metrics(
       Sales.revenue
   ).dimensions(Sales.country).aexecute() as cursor:
       async for dto in cursor.iter_into(RevenueByCountry):
           await handle(dto)

Writing ``await cursor.iter_into(...)`` is the mistake to expect here.
The schema check has already run by the time you hold the iterator, for
the same reason it has on the synchronous cursor.

Each batch is pulled on a worker thread, so the event loop stays free
while the warehouse computes the next one.

.. warning::

   Close an async cursor with ``async with`` or ``await cursor.aclose()``.
   Unlike :py:class:`~semolina.SemolinaCursor`, the async cursor has no
   finalizer that can reclaim a forgotten connection, so one that is
   never closed holds its pooled connection permanently. See
   :ref:`howto-web-api-async-cursor-close`.

Name the columns your warehouse returns
----------------------------------------

This is the section that decides whether the code above survives leaving
DuckDB. Your warehouse names the result column after the expression it
computed, and only DuckDB's spelling happens to look like a Python
identifier.

The same query returns these column names, read from this project's own
recorded results:

.. list-table::
   :header-rows: 1

   * - Warehouse
     - ``revenue`` arrives as
     - ``country`` arrives as
   * - Snowflake
     - ``AGG("REVENUE")``
     - ``COUNTRY``
   * - Databricks
     - ``measure(revenue)``
     - ``country``
   * - DuckDB
     - ``revenue``
     - ``country``

Matching is exact string equality, with no case folding and no
punctuation stripping, so ``revenue`` does not find ``AGG("REVENUE")``.
Declare the real column name with ``Field(validation_alias=...)``, which
is resolved first, ahead of ``alias`` and the field name:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         class RevenueByCountry(pydantic.BaseModel):
             country: str = pydantic.Field(
                 validation_alias="COUNTRY"
             )
             revenue: decimal.Decimal = pydantic.Field(
                 validation_alias='AGG("REVENUE")'
             )

      Snowflake folds unquoted identifiers to upper case and names a
      metric column after the ``AGG()`` call that produced it, quotes
      included.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         class RevenueByCountry(pydantic.BaseModel):
             country: str
             revenue: decimal.Decimal = pydantic.Field(
                 validation_alias="measure(revenue)"
             )

      Databricks leaves dimension names alone and wraps a metric in
      ``measure()``, lower case.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         class RevenueByCountry(pydantic.BaseModel):
             country: str
             revenue: decimal.Decimal

      DuckDB's ``semantic_view()`` returns bare field names, so a DTO
      written against it needs no aliases at all.

Write the aliases for the warehouse you deploy against, not the one you
develop against. A DTO with no aliases passes on DuckDB and then fails on
Snowflake, which is the worst order to find out in. The failure is at
least loud: the schema check names every field it could not place and
prints the column names the result actually carried, so one run against
the real warehouse tells you what to write.

What ``validate=True`` does, and what it does not
--------------------------------------------------

Both methods take a keyword-only ``validate``, defaulting to ``False``:

.. code-block:: python

   rows = cursor.into(RevenueByCountry, validate=True)

With ``validate=False``, instances are built through
``model_construct``, and none of your DTO's validators or constraints
run. With ``validate=True``, each row goes through Pydantic's full
validation pipeline at roughly two to five times the cost, and the first
row that fails raises a ``ValidationError`` naming the field.

.. warning::

   ``validate=True`` is not the safe setting for a money column. Pydantic
   coerces a ``decimal128`` value into a ``float``-annotated field
   without complaint, and the precision is gone. Turning validation on
   makes that case worse rather than better, because it looks like you
   checked.

What protects that case is a structural check that runs before either
path, on both settings of ``validate``, and before a single row moves.
Semolina compares your DTO's annotations against the result's Arrow
schema and refuses the call if they disagree. A ``decimal128`` column
against a ``float`` field is a refusal, whatever ``validate`` says.

So reach for ``validate=True`` when the *values* are untrustworthy and
you want per-row constraints enforced, and leave it off otherwise. It is
a per-value check, not a stronger version of the type check.

Annotate a VARIANT column
--------------------------

A semi-structured column, a Snowflake ``VARIANT`` for instance, has no
fixed shape to annotate. Use ``pydantic.JsonValue``:

.. code-block:: python

   import pydantic


   class EventDTO(pydantic.BaseModel):
       payload: pydantic.JsonValue

.. warning::

   Not ``semolina.JsonValue``. Semolina exports a name spelled the same
   way, for use in generated :py:class:`~semolina.SemanticView` models,
   where it is only ever read as text. Used as a DTO annotation it sends
   Pydantic into a ``RecursionError`` while your class is still being
   created, with a traceback containing no Semolina frames at all.

The schema check records no verdict for a field annotated this way. It
compares classes, and ``pydantic.JsonValue`` is a recursive type alias
rather than a class, so the field passes through unexamined.

When the DTO does not match
----------------------------

A mismatch raises :py:class:`~semolina.SemolinaSchemaMismatchError` and
lists every field at fault at once, rather than making you fix one and
re-run:

.. code-block:: text

   RevenueByCountry does not match the result schema (2 mismatched fields):
     revenue (column 'revenue'): declared float, but the column is decimal128(38, 2) (arrives as decimal.Decimal)
     currency (column 'currency'): declared str, but the column is no such column (the result has ['country', 'revenue'])
   Annotate each field with the type its column arrives as, or use Field(validation_alias=...) if the result spells the column differently. Note that validate=True does not fix this: it coerces a decimal column into a float field silently, losing the precision.

The first mismatch is the type case. The second is a declared field the
result has no column for, which is an error only while the field is
required: give it a default (``= None`` counts) and it becomes optional
in the result.

One refusal looks like a bug until you see the rule behind it. An
integer column does not satisfy a field annotated ``float``:

.. code-block:: text

   R2 does not match the result schema (1 mismatched field):
     revenue (column 'revenue'): declared float, but the column is int64 (arrives as int)

Python has no numeric tower to lean on here, and the fast path really
would leave an ``int`` sitting in a field you declared ``float``. It is
the same rule that catches the ``Decimal`` case, applied consistently:
the annotation has to name the type the column arrives as. Where you do
not want a verdict, ``typing.Any`` and ``object`` opt out.

The check reads types only. It never fetches a row, so no warehouse value
can reach the error message, and it costs nothing beyond reading a schema
that is already in memory. It also says nothing about nullability — see
:ref:`explanation-type-fidelity` for why that flag carries no
information.

See also
--------

- :ref:`howto-serialization` -- convert ``Row`` objects to dictionaries and JSON, the untyped route
- :ref:`howto-streaming` -- the other streaming entry points and how they share one stream
- :ref:`howto-arrow-output` -- Arrow tables and dataframes, including the result schema
- :ref:`explanation-type-fidelity` -- why money arrives as a ``Decimal``, and what the schema check promises
- :ref:`tutorial-installation-result-extras` -- the ``arrowmodel`` extra and the other three
- :py:meth:`~semolina.SemolinaCursor.into` -- API reference
- :py:meth:`~semolina.SemolinaCursor.iter_into` -- API reference
- :py:class:`~semolina.AsyncSemolinaCursor` -- async cursor class reference
