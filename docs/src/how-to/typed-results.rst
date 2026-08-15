.. _howto-typed-results:

How to get typed objects from a result
=======================================

A dashboard backend usually wants objects, not rows. This guide converts a
query result straight into Pydantic instances with
:py:meth:`~semolina.cursor.SemolinaCursor.into`, so your response layer gets
something it can serialize and your editor gets something it can
autocomplete.

Four forms are covered, all of them over the same query: the whole result
at once, the streaming form for a result you would rather not hold in
memory, and the async version of each. After those come column naming,
type checking, and the errors each one raises.

This guide assumes you already have a :py:class:`~semolina.models.SemanticView`
subclass and a registered engine. See :ref:`howto-queries` if you need
setup first.

Typed results need the ``arrowmodel`` extra:

.. code-block:: bash

   pip install semolina[arrowmodel]

That one extra is enough. It brings PyArrow with it, which both the
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

Call :py:meth:`~semolina.cursor.SemolinaCursor.into` with the DTO class:

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
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table`.

Stream instances one at a time
-------------------------------

When the result is larger than you want to hold,
:py:meth:`~semolina.cursor.SemolinaCursor.iter_into` gives you the same
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
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` does. Pick one
consumption pattern per cursor and finish it, because a second consumer
picks up wherever the first stopped rather than starting again. Keep the
cursor open until the loop ends; the ``with`` block does that for you.

Do the same from an async handler
----------------------------------

Both methods have async twins on
:py:class:`~semolina.acursor.AsyncSemolinaCursor`. Execute with ``aexecute()``,
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
   Unlike :py:class:`~semolina.cursor.SemolinaCursor`, the async cursor has no
   finalizer that can reclaim a forgotten connection, so one that is
   never closed holds its pooled connection permanently. See
   :ref:`howto-web-api-async-cursor-close`.

.. _howto-result-column-names:

Name the columns your warehouse returns
----------------------------------------

This is the section that decides whether the code above survives leaving
DuckDB. Your warehouse names the result column after the expression it
computed, and only DuckDB's spelling happens to look like a Python
identifier.

.. tip:: You do not have to write these by hand

   ``semolina codegen-dto`` probes a query and prints a DTO with the
   aliases already filled in for the backend it probed, along with the
   annotations that backend reported. See :ref:`howto-dto-codegen`.
   Everything below is the rule those generated aliases follow, and what
   to write when you author a DTO yourself.

The same query returns these column names on each backend:

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

      Snowflake folds unquoted identifiers to upper case, inside the
      quotes of a metric column as well as outside. A metric stored as
      ``gross revenue`` arrives as ``AGG("GROSS REVENUE")``, not as the
      ``AGG("gross revenue")`` the query had to send to reach it.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         class RevenueByCountry(pydantic.BaseModel):
             country: str
             revenue: decimal.Decimal = pydantic.Field(
                 validation_alias="measure(revenue)"
             )

      Databricks leaves dimension names alone and wraps a metric in
      ``measure()``, lower case, dropping any backticks the query needed.
      A metric named ``gross revenue`` arrives as
      ``measure(gross revenue)``.

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

Choose exact types or coercion
-------------------------------

Both methods take a keyword-only ``validate``, defaulting to ``False``.
It picks between two behaviours, and the difference is worth
understanding once:

.. code-block:: python

   rows = cursor.into(RevenueByCountry)  # types must match
   rows = cursor.into(
       RevenueByCountry, validate=True
   )  # types are coerced

**``validate=False``: your annotations must match the columns.**
Instances are built through ``model_construct``, which converts nothing
and runs none of your validators. Because nothing converts, an
annotation that disagreed with its column would leave a wrong-typed
value sitting in the field. Semolina compares the DTO against the
result's Arrow schema first and refuses the call instead, naming every
offending field at once. The cost is one schema comparison, no matter
how many rows come back.

**``validate=True``: your annotations are what you want, so convert to
them.** Each row goes through Pydantic's full pipeline at roughly two to
five times the cost. It converts where the conversion is legal and
raises ``ValidationError`` where it is not:

.. list-table::
   :header-rows: 1

   * - Column arrives as
     - Field declares
     - ``validate=True``
   * - ``decimal128``
     - ``float``
     - converts, precision lost
   * - ``int64``
     - ``float``
     - converts
   * - ``float64``
     - ``Decimal``
     - converts
   * - ``decimal128``
     - ``int``
     - ``ValidationError``
   * - ``string``
     - ``int``
     - ``ValidationError`` unless the text parses

The structural type check is skipped on this path, because Pydantic is
already deciding and refusing first would block conversions that work.

So: leave ``validate`` alone and Semolina holds you to the warehouse's
types. Pass ``validate=True`` when you have deliberately declared
something narrower and want the values converted to it.

.. warning::

   A money column declared ``float`` converts under ``validate=True``,
   and the precision goes with it:
   ``12345678901234567890.99`` becomes ``1.2345678901234567e+19``. That
   is a reasonable thing to ask for in a chart and a bad thing to ask
   for in a ledger. Declare :py:class:`decimal.Decimal` and let the
   default path hold you to it unless you specifically want the
   narrowing.

One asymmetry to know: ``validate=True`` is more permissive about types
but *stricter* about nulls. The structural check says nothing about
nullability (see :ref:`explanation-type-fidelity` for why the Arrow
flag carries no information), so a NULL will happily land in a
non-optional field on the fast path. Pydantic rejects it. If you turn
validation on and start seeing errors about ``None``, annotate the field
``| None`` rather than turning validation back off.

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
   way, for use in generated :py:class:`~semolina.models.SemanticView` models,
   where it is only ever read as text. Used as a DTO annotation it sends
   Pydantic into a ``RecursionError`` while your class is still being
   created, with a traceback containing no Semolina frames at all.

The schema check records no verdict for a field annotated this way. It
compares classes, and ``pydantic.JsonValue`` is a recursive type alias
rather than a class, so the field passes through unexamined.

When the DTO does not match
----------------------------

A mismatch raises :py:class:`~semolina.exceptions.SemolinaSchemaMismatchError` and
lists every field at fault at once, rather than making you fix one and
re-run:

.. code-block:: text

   RevenueByCountry does not match the result schema (2 mismatched fields):
     revenue (column 'revenue'): declared float, but the column is decimal128(38, 2) (arrives as decimal.Decimal)
     currency (column 'currency'): declared str, but the column is no such column (the result has ['country', 'revenue'])
   Annotate each field with the type its column arrives as, or use Field(validation_alias=...) if the result spells the column differently.
   If a narrowing is deliberate, pass validate=True: Pydantic then converts each value, coercing where it legally can (decimal -> float) and raising ValidationError where it cannot (decimal -> int).

The first mismatch is the type case. The second is a declared field the
result has no column for, which is an error only while the field is
required: give it a default (``= None`` counts) and it becomes optional
in the result.

Only the type half is skipped by ``validate=True``. A required field with
no matching column is still refused on either path, because no
conversion invents a column.

One refusal looks like a bug until you see the rule behind it. An
integer column does not satisfy a field annotated ``float``:

.. code-block:: text

   R2 does not match the result schema (1 mismatched field):
     revenue (column 'revenue'): declared float, but the column is int64 (arrives as int)

Python has no numeric tower to lean on here, and the fast path really
would leave an ``int`` sitting in a field you declared ``float``. It is
the same rule that catches the ``Decimal`` case, applied consistently:
on the default path the annotation has to name the type the column
arrives as. If you wanted the float, ``validate=True`` converts it.
Where you do not want a verdict at all, ``typing.Any`` and ``object``
opt out.

The check reads types only. It never fetches a row, so no warehouse value
can reach the error message, and it costs nothing beyond reading a schema
that is already in memory. It also says nothing about nullability; see
:ref:`explanation-type-fidelity` for why that flag carries no
information.

See also
--------

- :ref:`howto-dto-codegen` -- generate the DTO above from the query itself, aliases included
- :ref:`howto-serialization` -- convert ``Row`` objects to dictionaries and JSON, the untyped route
- :ref:`howto-streaming` -- the other streaming entry points and how they share one stream
- :ref:`howto-arrow-output` -- Arrow tables and dataframes, including the result schema
- :ref:`explanation-type-fidelity` -- why money arrives as a ``Decimal``, and
  what the schema check promises
- :ref:`explanation-duckdb-vs-warehouse` -- why code that works on DuckDB breaks against
  Snowflake, and which of these differences a DuckDB-only test suite cannot catch
- :ref:`tutorial-installation-result-extras` -- the ``arrowmodel`` extra and the other three
- :py:meth:`~semolina.cursor.SemolinaCursor.into` -- API reference
- :py:meth:`~semolina.cursor.SemolinaCursor.iter_into` -- API reference
- :py:class:`~semolina.acursor.AsyncSemolinaCursor` -- async cursor class reference
