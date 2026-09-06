.. _howto-queries:

How to build queries
====================

:ref:`tutorial-first-query` runs one query from model to rows. The builder in the middle
of it is the subject here. Chain ``.metrics()``, ``.dimensions()``, ``.where()``,
``.order_by()`` and ``.limit()`` to shape a query, then call ``.execute()`` to get results.
The API is fluent and immutable, so every call hands back a new query rather than mutating
the one you had.

This page walks the chain in the order you write it. Filtering has more surface than one
step of a walkthrough can hold, so ``.where()`` gets its place in the chain here and its
operator set in :ref:`howto-filtering`.

This guide uses the ``Sales`` model from :ref:`tutorial-first-query`:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()

Select metrics
--------------

Use ``.metrics()`` to choose which aggregated measures to include:

.. code-block:: python

   query = Sales.query().metrics(Sales.revenue)
   query = Sales.query().metrics(Sales.revenue, Sales.cost)

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE"), AGG("COST")
         FROM "SALES"

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), MEASURE(`cost`)
         FROM `sales`

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', metrics := ['revenue', 'cost'])

Passing a non-``Metric`` field raises ``TypeError``:

.. code-block:: python

   Sales.query().metrics(
       Sales.country
   )  # TypeError: metrics() requires Metric fields

At least one field is required -- calling ``.metrics()`` with no arguments raises ``ValueError``.

Select dimensions
-----------------

Use ``.dimensions()`` to group results by :py:class:`~semolina.fields.Dimension` or
:py:class:`~semolina.fields.Fact` fields:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country, Sales.region)
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE"), "COUNTRY", "REGION"
         FROM "SALES"
         GROUP BY ALL

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`, `region`
         FROM `sales`
         GROUP BY ALL

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', dimensions := ['country', 'region'], metrics := ['revenue'])

Passing a ``Metric`` field raises ``TypeError``. At least one field is required.

Use query shorthand
-------------------

Pass ``metrics`` and ``dimensions`` directly to ``query()`` as keyword arguments:

.. code-block:: python

   cursor = Sales.query(
       metrics=[Sales.revenue, Sales.cost],
       dimensions=[Sales.country],
   ).execute()

This is equivalent to the fluent chain:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue, Sales.cost)
       .dimensions(Sales.country)
       .execute()
   )

Shorthand and builder methods are additive. Calling ``.metrics()`` after ``query(metrics=...)``
adds to the selection:

.. code-block:: python

   cursor = (
       Sales.query(metrics=[Sales.revenue])
       .metrics(
           Sales.cost
       )  # now selects both revenue and cost
       .dimensions(Sales.country)
       .execute()
   )

Filter with ``.where()``
------------------------

``.where()`` takes conditions built from field operators. Conditions AND together, whether
you pass several to one call or make several calls, and a ``None`` condition is a no-op.
That last part is what turns an optional filter into a line rather than a branch:

.. code-block:: python

   def revenue_by_country(country: str | None):
       return (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(Sales.revenue > 1000)
           .where(
               Sales.country == country if country else None
           )
       )

Called with ``"US"`` that renders ``WHERE ("REVENUE" > 1000 AND "COUNTRY" = 'US')``. Called
with ``None`` the second condition drops out and only the revenue bound survives.

:ref:`howto-filtering` covers the rest: the comparison operators, the named methods that
have no operator spelling (``.between()``, ``.in_()``, ``.like()`` and the others),
composition with ``&``, ``|`` and ``~``, custom lookups, and whether a filter value binds
or inlines on each backend.

.. _howto-ordering:

Order results
-------------

Without ``.order_by()`` the warehouse returns groups in whatever order suits it. Pass a
bare field for ascending, or call ``.asc()`` or ``.desc()`` on the field to say so
explicitly:

.. code-block:: python

   # Ascending -- these two build the same query
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .order_by(Sales.revenue)
   )
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .order_by(Sales.revenue.asc())
   )

   # Descending
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .order_by(Sales.revenue.desc())
   )

Metrics and dimensions are both valid sort keys, and a sort key does not have to be in the
select list. On Snowflake and Databricks a metric sort key is wrapped in the aggregation
function; DuckDB's ``semantic_view()`` hands the columns back directly, so it sorts on
plain identifiers. Anything that is neither a field nor an order term raises ``TypeError``.

Break ties with a second sort key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rows sharing a revenue figure come back in an arbitrary order until you name a tiebreaker.
Extra fields apply left to right, so the second key only decides where the first one ties:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .order_by(Sales.revenue.desc(), Sales.country.asc())
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE"), "COUNTRY"
         FROM "SALES"
         GROUP BY ALL
         ORDER BY AGG("REVENUE") DESC, "COUNTRY" ASC

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`
         FROM `sales`
         GROUP BY ALL
         ORDER BY MEASURE(`revenue`) DESC, `country` ASC

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])
         ORDER BY "revenue" DESC, "country" ASC

Separate calls append in the same order, so ``.order_by(a).order_by(b)`` and
``.order_by(a, b)`` produce identical SQL.

Put the NULLs where you want them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sort on a nullable column and Semolina emits no ``NULLS`` clause, which leaves the position
of the NULL group to the backend -- and the backends do not all default the same way. Pass
a :py:class:`~semolina.fields.NullsOrdering` to ``.asc()`` or ``.desc()`` when the position
matters:

.. code-block:: python

   from semolina import NullsOrdering

   # Rows with no region sort to the bottom, whichever warehouse runs this
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.region)
       .order_by(Sales.region.asc(NullsOrdering.LAST))
   )

.. list-table::
   :header-rows: 1

   * - Value
     - SQL generated
     - Meaning
   * - ``NullsOrdering.FIRST``
     - ``NULLS FIRST``
     - NULLs sort before non-NULL values
   * - ``NullsOrdering.LAST``
     - ``NULLS LAST``
     - NULLs sort after non-NULL values
   * - ``NullsOrdering.DEFAULT``
     - *(no NULLS clause)*
     - Backend decides (default)

Reuse an order term
~~~~~~~~~~~~~~~~~~~

``.asc()`` and ``.desc()`` return :py:class:`~semolina.fields.OrderTerm` values that hold
no reference to a query. Build the sorts your API is willing to serve once, then look them
up by name:

.. code-block:: python

   from semolina import NullsOrdering

   SORTS = {
       "revenue": Sales.revenue.desc(NullsOrdering.LAST),
       "country": Sales.country.asc(),
   }


   def top_countries(sort: str = "revenue"):
       return (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .order_by(SORTS[sort])
       )

Looking the term up rather than building it from the request parameter also keeps an
unexpected ``sort`` value out of the query: an unknown key raises ``KeyError`` before any
SQL exists.

Limit result count
------------------

``.limit(n)`` caps the number of rows the warehouse returns:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .limit(10)
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE"), "COUNTRY"
         FROM "SALES"
         GROUP BY ALL
         LIMIT 10

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`
         FROM `sales`
         GROUP BY ALL
         LIMIT 10

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])
         LIMIT 10

``n`` must be a positive integer. Zero or a negative number raises ``ValueError`` and a
non-integer raises ``TypeError``, both as you build the query rather than at
``.execute()``.

Take the top N
~~~~~~~~~~~~~~

On its own ``.limit()`` returns an arbitrary handful of rows. After an ``.order_by()`` it
returns the top N:

.. code-block:: python

   # The ten highest-revenue countries
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .order_by(Sales.revenue.desc())
       .limit(10)
   )

.. note:: There is no ``.offset()``

   ``.limit(n)`` is the only row-count control on the query builder. Semolina has no
   ``offset()``, so classic ``LIMIT``/``OFFSET`` pagination cannot be expressed through
   the fluent API in this release.

   For a paged dashboard, filter on an ordered column instead of skipping rows: order by
   a key, take ``.limit(page_size)``, and make the next request ask for rows past the
   last key you received (``.where(Sales.country > last_seen)``). That is keyset
   pagination, and on an aggregate query it is usually cheaper than ``OFFSET`` anyway,
   because the warehouse does not have to compute and discard the skipped groups.

Choose the engine
-----------------

Use ``.using()`` to select a different registered engine by name. Engine
resolution is lazy -- it happens at ``.execute()`` time, not during query
construction:

.. code-block:: python

   # Uses the engine registered as "warehouse" instead of "default"
   query = (
       Sales.query().metrics(Sales.revenue).using("warehouse")
   )

If no ``.using()`` call is made, Semolina uses the engine registered as
``"default"``. See :ref:`howto-connection-pools` for how to build and register
engines.

Execute and read results
------------------------

Call ``.execute()`` to run the query and get back a :py:class:`~semolina.cursor.SemolinaCursor`:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)  # attribute access
       print(row["country"])  # dict-style access

``.execute()`` validates the query, resolves the engine, runs the SQL and returns the
cursor. A query selecting neither a metric nor a dimension raises ``ValueError`` at this
point rather than during construction, which is what lets you build a query in pieces.

.. warning:: Column keys are whatever your warehouse called them

   Semolina adds no ``AS`` aliases and does no case folding, so a row's keys are the
   result column names exactly as the driver reports them. Only DuckDB happens to spell
   them like Python identifiers. The same query returns ``COUNTRY`` and ``AGG("REVENUE")``
   on Snowflake, and ``country`` and ``measure(revenue)`` on Databricks, so
   ``row.revenue`` raises ``AttributeError`` there. See
   :ref:`howto-result-column-names` before you deploy against a real warehouse.

Fetch methods
~~~~~~~~~~~~~

:py:class:`~semolina.cursor.SemolinaCursor` provides both ``Row``-based and raw DBAPI fetch methods:

.. code-block:: python

   # Row objects (primary pattern)
   rows = cursor.fetchall_rows()  # list[Row]
   row = cursor.fetchone_row()  # Row | None
   batch = cursor.fetchmany_rows(10)  # list[Row]

   # Raw DBAPI tuples
   raw = cursor.fetchall()  # list[tuple]
   raw_one = cursor.fetchone()  # tuple | None
   raw_batch = cursor.fetchmany(10)  # list[tuple]

   # Context manager (closes cursor + connection on exit)
   with Sales.query(
       metrics=[Sales.revenue]
   ).execute() as cursor:
       rows = cursor.fetchall_rows()

The cursor hands back other result shapes too:

- :ref:`howto-streaming` -- Arrow tables and dataframes whole, batches and lazy iteration
  for a result you would rather not hold in memory, and the async cursor ``.aexecute()``
  returns
- :ref:`howto-typed-results` -- Pydantic instances via ``.into()``
- :ref:`the untyped route <howto-serialization>` -- dictionaries and JSON

.. _howto-inspect-sql:

Inspect generated SQL
---------------------

Use ``.to_sql()`` to see the SQL structure without executing the query:

.. code-block:: python

   sql = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .to_sql()
   )
   print(sql)

.. code-block:: sql

   SELECT AGG("REVENUE"), "COUNTRY"
   FROM "SALES"
   GROUP BY ALL

The Snowflake dialect folds identifiers to upper case, which is also why result columns
come back as ``COUNTRY`` and ``AGG("REVENUE")`` -- see
:ref:`howto-result-column-names`.

.. tip::

   ``.to_sql()`` renders the Snowflake dialect by default (``AGG()``, double-quoted
   identifiers), regardless of which engine is registered. Pass a ``dialect`` argument to
   preview another backend's SQL, for example ``.to_sql(dialect="databricks")`` or
   ``.to_sql(dialect="duckdb")``.

Fork and reuse queries
----------------------

Every builder method returns a new query and leaves the original alone, so a base query is
safe to keep around and safe to hand out:

.. code-block:: python

   base = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )

   # Fork into specialized variants -- base is unchanged
   us_only = base.where(Sales.country == "US")
   us_top_10 = base.where(Sales.country == "US").limit(10)

   print(base.to_sql())  # no WHERE, no LIMIT
   print(us_top_10.to_sql())  # has WHERE and LIMIT

The same property makes it safe to assemble a query across function boundaries. A helper
that adds a clause cannot disturb the query its caller is still holding:

.. code-block:: python

   def add_revenue_floor(query, threshold: int):
       return query.where(Sales.revenue > threshold)


   cursor = add_revenue_floor(base, 1000).execute()

See also
--------

- :ref:`tutorial-first-query` -- one query from model to rows, start to finish
- :ref:`tutorial-shaping-a-report` -- filtering, ordering and limiting run step by step
- :ref:`howto-filtering` -- field operators, named methods and boolean composition
- :ref:`howto-models` -- define :py:class:`~semolina.models.SemanticView` subclasses
  with field types
- :ref:`howto-typed-results` -- map rows into Pydantic models, and the untyped
  dictionary route
- :ref:`howto-connection-pools` -- build and register the engines ``.using()`` resolves
- :ref:`howto-backends` -- the connection settings each warehouse takes, and the SQL its
  dialect renders
