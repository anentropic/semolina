.. _tutorial-shaping-a-report:

Shaping a report
================

Your first query returned every country in the view, in whatever order the
warehouse felt like. A report needs less than that, and needs it in a
particular order. In this tutorial you will add filters, sorting, and a row
cap to the query you already have, checking the result after each change.

**Prerequisites:** :ref:`tutorial-first-query`, and the ``tutorial.db`` DuckDB
database its setup script builds. You will reuse the same ``Sales`` model.

The data underneath is three rows:

.. code-block:: text

   revenue  cost  country  region
   1000     100   US       West
   2000     200   CA       West
   500      50    US       East

Start from a working query
--------------------------

Create ``report.py`` with the model, the engine, and a query that selects both
dimensions. Every step below changes one thing about this query:

.. code-block:: python
   :caption: report.py

   from adbc_poolhouse import DuckDBConfig

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   create_engine(
       DuckDBConfig(database="tutorial.db"), register=True
   )

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
       .execute()
   )

   for row in cursor.fetchall_rows():
       print(row.country, row.region, row.revenue)

Run it with ``python report.py``:

.. code-block:: text

   CA West 2000
   US West 1000
   US East 500

Adding ``region`` to ``.dimensions()`` changed the grouping. ``US`` was one row
of ``1500`` in the last tutorial and is two rows here, because the warehouse now
groups by country *and* region. Choosing a dimension is already a decision about
what the report counts.

.. warning:: Column keys are whatever your warehouse called them

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are
   the result column names exactly as the driver reports them. Only DuckDB
   happens to spell them like Python identifiers. The same query returns
   ``COUNTRY`` and ``AGG("REVENUE")`` on Snowflake, and ``country`` and
   ``measure(revenue)`` on Databricks, so ``row.revenue`` raises
   ``AttributeError`` there. See :ref:`howto-result-column-names` before you
   deploy against a real warehouse.

1. Keep only the rows you want
------------------------------

``.where()`` takes a condition built from a field and a Python operator. Insert
one into the chain, before ``.execute()``:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
       .where(Sales.region == "West")
       .execute()
   )

Run it again:

.. code-block:: text

   US West 1000
   CA West 2000

The ``East`` row is gone. ``Sales.region == "West"`` compares nothing at the
moment you write it: it builds a :py:class:`~semolina.filters.Predicate` object,
which ``.where()`` compiles into the ``WHERE`` clause the warehouse runs.

Comparison operators other than ``==`` work the same way, and so do the named
methods on a field. This one filters on the aggregated metric rather than on a
dimension:

.. code-block:: text

   .where(Sales.revenue > 1000)

2. Combine conditions
---------------------

Real reports rarely ask one question. Use ``&`` for AND, ``|`` for OR, and ``~``
for NOT, wrapping each condition in its own parentheses:

.. code-block:: text

   .where((Sales.region == "West") & (Sales.revenue > 1000))

.. code-block:: text

   CA West 2000

``US West`` was in the previous result and is not in this one, because its
``1000`` fails the second condition. Swap the ``&`` for a ``|`` and the two
conditions become alternatives:

.. code-block:: text

   .where((Sales.region == "East") | (Sales.revenue > 1500))

.. code-block:: text

   CA West 2000
   US East 500

``~`` negates whatever follows it:

.. code-block:: text

   .where(~(Sales.region == "West"))

.. code-block:: text

   US East 500

.. warning:: ``&`` binds tighter than ``|``

   Python gives these operators the precedence it gives the bitwise ones, so
   ``a | b & c`` reads as ``a | (b & c)``, which is rarely what a report means.
   Parenthesize the grouping you want whenever you mix the two.

3. Fix the order
----------------

Nothing so far has said which order the rows arrive in, and the warehouse is
free to choose. That is why step 1 returned ``US`` before ``CA``.
``.order_by()`` makes the choice yours. Pass a bare field for ascending, or call
``.desc()`` on it for descending:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
       .order_by(Sales.revenue.desc())
       .execute()
   )

.. code-block:: text

   CA West 2000
   US West 1000
   US East 500

Drop the ``.desc()`` and the same query counts up instead:

.. code-block:: text

   .order_by(Sales.revenue)

.. code-block:: text

   US East 500
   US West 1000
   CA West 2000

Sorting on the metric is what makes a "biggest first" report possible, and it is
the step that has to come before the next one.

4. Cut it to the top rows
-------------------------

``.limit(n)`` caps the number of rows the warehouse returns. On its own it gives
you an arbitrary handful. After an ``.order_by()`` it gives you a top N:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
       .order_by(Sales.revenue.desc())
       .limit(2)
       .execute()
   )

.. code-block:: text

   CA West 2000
   US West 1000

``n`` has to be a positive integer. Zero or a negative number raises
``ValueError`` and a non-integer raises ``TypeError``, both before anything
reaches the warehouse.

Complete example
----------------

Put the three clauses together and you have the report this tutorial was heading
for: the two biggest markets in the West region, largest first.

Replace ``report.py`` with this and run ``python report.py``:

.. code-block:: python
   :caption: report.py

   from adbc_poolhouse import DuckDBConfig

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()


   create_engine(
       DuckDBConfig(database="tutorial.db"), register=True
   )

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
       .where(Sales.region == "West")
       .order_by(Sales.revenue.desc())
       .limit(2)
       .execute()
   )

   for row in cursor.fetchall_rows():
       print(row.country, row.region, row.revenue)

You should see:

.. code-block:: text

   CA West 2000
   US West 1000

Each of those methods returned a new query rather than changing the one it was
called on, so a half-built query is safe to keep around and branch from. The
next tutorial leans on that when the filter arrives from an HTTP request.

Next steps
----------

You can now shape a result. Next, serve one over HTTP:

:ref:`Serve a dashboard endpoint <tutorial-dashboard-api>`

See also
--------

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Filter queries
      :link: howto-filtering
      :link-type: ref

      Every operator and named method, custom lookups, and how a filter value
      reaches each warehouse.

   .. grid-item-card:: Order and limit results
      :link: howto-ordering
      :link-type: ref

      NULL positioning, multi-field sorts, and keyset pagination.

   .. grid-item-card:: Build queries
      :link: howto-queries
      :link-type: ref

      The rest of the query builder.

   .. grid-item-card:: Result column names
      :link: howto-result-column-names
      :link-type: ref

      What each warehouse calls the columns this query returns.
