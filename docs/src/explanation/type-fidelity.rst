.. _explanation-type-fidelity:

Warehouse types and what lands in your row
==========================================

A semantic view defines a metric as an aggregation expression, not as a column
with a declared type. ``SUM(o.order_total)`` has whatever type the warehouse
works out when it plans the query, and that type depends on the aggregate as
much as on the column underneath it.

Two consequences, and they are what this page is about. The type your warehouse
reports for a metric before you query it is not always the type you get back.
And a money column arrives in Python as a :py:class:`decimal.Decimal` rather
than a ``float``.

What the warehouse tells you before you query
---------------------------------------------

Semolina's codegen reads field types out of your warehouse's catalogue. How much
there is to read varies.

**Snowflake** answers ``SHOW COLUMNS IN VIEW`` with a resolved type per metric
and dimension. Snowflake infers the metric's type server-side and reports the
result, so there is a real answer waiting for you.

**Databricks** answers ``DESCRIBE TABLE EXTENDED ... AS JSON`` with a type per
column, measures included, alongside the metric view's own YAML definition.

**DuckDB** reports nothing. ``DESCRIBE SEMANTIC VIEW`` returns an empty type for
every field, so Semolina runs ``DESCRIBE SELECT * FROM semantic_view(...)``
instead, which is a query-shaped question rather than a catalogue lookup.

DuckDB is the general case wearing a disguise. Definition-time type information
for a metric is a convenience the warehouse may offer, and it is derived from
the underlying columns; the authoritative answer exists only once a query is
planned.

Where the catalogue and the result disagree
-------------------------------------------

Measured against DuckDB 1.5.5 with the ``semantic_views`` extension, over a
table whose ``order_total`` column is ``DECIMAL(10, 2)`` and whose
``order_count`` column is ``INTEGER``:

- ``SUM(order_total)`` comes back at precision 38, not 10. ``MAX(order_total)``
  over the same column stays at ``DECIMAL(10, 2)``. Accumulating aggregates
  widen; picking one existing value out of a column does not.
- ``AVG(order_count)`` comes back as a double, so the row holds a ``float`` for
  a column that only ever held whole numbers. ``SUM(order_count)`` over the same
  column stays an integer.
- ``COUNT(order_total)`` comes back as a 64-bit integer while
  ``MIN(order_count)`` comes back as a 32-bit one.

The width difference in the third case is invisible in a :py:class:`~semolina.Row`,
where both arrive as a Python ``int``. It surfaces if you take results as Arrow
with ``fetch_arrow_table()``, or hand the result schema to anything that cares
about integer width. The first two cases show up everywhere: a summed decimal
column is a ``Decimal``, and an average is a ``float`` no matter what you
averaged.

Rules for this are published unevenly. Databricks documents its
`sum <https://docs.databricks.com/aws/en/sql/language-manual/functions/sum>`_ and
`avg <https://docs.databricks.com/aws/en/sql/language-manual/functions/avg>`_
return types, including the precision it widens a decimal to. Snowflake
publishes no precision rule for ``SUM`` and no return type for ``AVG`` at all,
so on Snowflake the exact widths are something to measure against your own view
rather than something to look up.

Why money comes back as a Decimal
---------------------------------

Your warehouse holds a decimal column, the ADBC driver hands it over as Arrow
``decimal128``, and pyarrow turns that into a :py:class:`decimal.Decimal`.
Semolina neither rounds it nor casts it to ``float`` on the way through, so what
you get is the value the warehouse computed, at full precision.

.. code-block:: python

   cursor = (
       Orders.query().metrics(Orders.order_total).execute()
   )
   row = cursor.fetchone_row()

   print(row.order_total)
   # Decimal('30.75')

   # Decimal and float raise TypeError if you mix them in arithmetic, and
   # json.dumps has no encoder for Decimal. Convert at the boundary.
   payload = {"order_total": float(row.order_total)}

Two boundaries need that explicit ``float()``: charting libraries, which want
native floats, and hand-rolled JSON serialisation. Pydantic v2 does not, since
it handles ``Decimal`` fields directly, and neither does
``to_pandas()``, which gives you an ``object``-dtype column holding ``Decimal``
values rather than silently converting to ``float64``.

The alternative would be to ask the driver for floats. Snowflake's ADBC driver
has a low-precision mode that hands ``NUMBER`` columns over as 64-bit ints and
floats instead of decimals. It is not the default, and Semolina does not switch
it on: it would round your revenue to whatever a double can hold, and it has no
equivalent on Databricks or DuckDB, so the three backends would stop agreeing
about money.

What can be NULL
----------------

A metric is a value computed over a group, so it goes NULL when there is a group
but nothing to aggregate in it. Three cases, and they behave differently:

A group whose metric inputs are all NULL gives you a row, with ``None`` for
``SUM``, ``AVG``, ``MIN``, and ``MAX``. Say a region has one order whose total
was never recorded: the region still appears in your results, with a null total.

``COUNT`` in that same group gives you ``0``, not ``None``. Counting nothing is
a real answer.

A filter that matches nothing gives you no rows at all. There is no group, so
there is nothing to be NULL. If you filter on a region that does not exist, you
get an empty result rather than a row of nulls.

So a metric annotated as non-optional is optimistic in the general case, and
that is why generated metric annotations admit ``None``. ``COUNT`` is the
exception that gets treated the same way, because the aggregate expression
behind a metric is readable from the catalogue on DuckDB and Databricks but not
on Snowflake, and one rule that holds on all three is worth more than a sharper
rule that holds on two.

Asking the warehouse, or reading the catalogue
----------------------------------------------

Given the gap between the two, Semolina prefers the answer the warehouse gives
when it plans your query, and falls back to the catalogue when it cannot ask.
Both happen when you generate or check a model, never while your application is
running a query.

Asking is cheaper than it sounds. ADBC has a call that returns a query's result
schema without executing it, and on Snowflake that maps to the warehouse's
describe-only mode: a metadata round trip, no compute. On DuckDB it is answered
in-process.

Two things get in the way. Snowflake refuses the describe-only call when the
query carries bound parameters, which is the shape a ``.where()`` produces on
that backend, so a filtered query cannot be described. And the Databricks driver
does not implement the call at all, so the only route there is to run the query
wrapped in something that returns no rows, which does reach the warehouse and
does cost you a wake-up on a serverless one.

The catalogue is what codegen uses when neither route is open, including when
you generate a model with no live connection. It is a good estimate. It is
simply not the same source as the query itself.

What a generated annotation names
---------------------------------

The annotation ``semolina codegen`` writes describes the value you will hold,
not the type the warehouse declares. A decimal column annotates
:py:class:`decimal.Decimal` on Snowflake, Databricks and DuckDB alike, so the
three backends agree about money in a generated model as well as at runtime.
Metric fields annotate ``T | None``, for the reason given under
`What can be NULL`_.

Where the annotation does not name the warehouse's own type, codegen keeps that
type as a comment above the field, so a precision and scale are not lost the
moment the annotation says only ``decimal.Decimal``:

.. code-block:: python

   # DECIMAL(10,2)
   max_order_value = Metric[decimal.Decimal | None]()

Several DuckDB columns annotate ``str`` on the same principle. A ``UUID``
arrives as text rather than as a :py:class:`uuid.UUID`, a ``JSON`` column as
unparsed JSON text, and an ``ENUM`` as the member's label. Writing
:py:class:`uuid.UUID` there would name the type you expected rather than the
object in your row, which is the gap this page exists to close.

One annotation is an over-approximation rather than an exact description. A
DuckDB ``TIMESTAMP_NS`` column annotates :py:class:`datetime.datetime`, and what
lands in your row depends on whether pandas can be imported. When it can, the
value is a ``pandas.Timestamp``, a subclass of :py:class:`datetime.datetime`
that keeps the nanoseconds. When it cannot, pyarrow truncates the value to
microsecond resolution, and raises :py:exc:`ValueError` outright on a value
carrying sub-microsecond precision. Semolina does not depend on pandas. It
arrives transitively under the ``all`` extra, so whether you have it is a
property of your environment rather than of Semolina.

Why a fresh model can fail its own check
----------------------------------------

``semolina codegen`` builds a model from the catalogue. ``semolina codegen
--check`` resolves annotations from the result schema instead, dropping back to
the catalogue only when it cannot probe and labelling every row it did that for.
The two commands read the two sources this page has been comparing all along, so
a ``--check`` run straight after a ``codegen`` run can report drift on a model
that was correct by the route which generated it.

A DuckDB ``INTERVAL`` fact is the clearest case today. The catalogue route
annotates it ``datetime.timedelta``. The result-schema route resolves no type
for it at all, because the value arrives as a ``pyarrow.MonthDayNano`` and no
type in the standard library describes one. ``--check`` calls that drift, and
the probe is the half telling the truth.

So a reported drift is a question about which source to believe, rather than a
fault in either command. See :ref:`howto-codegen-check` for the mechanics of
running the check and reading its per-field report.

See also
--------

- :ref:`explanation-semantic-views` -- what a semantic view is, and how the three warehouses implement them
- :ref:`howto-codegen` -- generate models from your warehouse, and edit the annotations codegen produces
- :ref:`howto-codegen-check` -- run ``semolina codegen --check`` against a committed model and read its report
- :ref:`howto-models` -- field types and model configuration
- :ref:`howto-arrow-output` -- fetch results as an Arrow table, where the exact result schema is visible
- :ref:`howto-filtering` -- filter a query with ``.where()``
- `Databricks: sum <https://docs.databricks.com/aws/en/sql/language-manual/functions/sum>`_ -- the documented decimal widening rule for sums
