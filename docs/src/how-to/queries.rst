How to build queries
====================

Build queries using Semolina's fluent, immutable API. Chain ``.metrics()``, ``.dimensions()``,
``.where()``, ``.order_by()``, and ``.limit()`` to shape your query, then call ``.execute()`` to
get results.

This guide uses the ``Sales`` model from :doc:`../tutorials/first-query`:

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

         SELECT AGG("revenue"), AGG("cost")
         FROM "sales"

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), MEASURE(`cost`)
         FROM `sales`

Passing a non-``Metric`` field raises ``TypeError``:

.. code-block:: python

   Sales.query().metrics(
       Sales.country
   )  # TypeError: metrics() requires Metric fields

At least one field is required -- calling ``.metrics()`` with no arguments raises ``ValueError``.

Select dimensions
-----------------

Use ``.dimensions()`` to group results by :py:class:`~semolina.Dimension` or
:py:class:`~semolina.Fact` fields:

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

         SELECT AGG("revenue"), "country"
         FROM "sales"
         GROUP BY ALL

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`
         FROM `sales`
         GROUP BY ALL

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
-------------------------

Add filter conditions using field operators. Multiple ``.where()`` calls are **ANDed** together.
Pass ``None`` as a no-op (useful for conditional filters):

.. code-block:: python

   # Single filter
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US")
   )

   # Multiple filters -- equivalent to: WHERE country = 'US' AND revenue > 1000
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US")
       .where(Sales.revenue > 1000)
   )

   # Varargs -- all conditions ANDed together
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US", Sales.revenue > 1000)
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("revenue")
         FROM "sales"
         WHERE "country" = 'US'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         WHERE `country` = 'US'

See :doc:`filtering` for the full operator reference, named methods, and boolean
composition.

Order results
-------------

Order results by one or more fields. Pass a bare field for default ascending order,
or use ``.asc()`` / ``.desc()`` for explicit direction:

.. code-block:: python

   # Ascending (default)
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .order_by(Sales.revenue)
   )

   # Descending
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .order_by(Sales.revenue.desc())
   )

   # Multiple fields
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

         SELECT AGG("revenue")
         FROM "sales"
         ORDER BY "revenue" ASC

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         ORDER BY `revenue` ASC

See :doc:`ordering` for NULL handling and combined examples.

Limit result count
------------------

Limit the result set to ``n`` rows. Must be a positive integer:

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

         SELECT AGG("revenue"), "country"
         FROM "sales"
         GROUP BY ALL
         LIMIT 10

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`
         FROM `sales`
         GROUP BY ALL
         LIMIT 10

Passing zero or a negative value raises ``ValueError``. Passing a non-integer raises ``TypeError``.

Override the connection pool
----------------------------

Use ``.using()`` to select a different registered pool by name. Pool resolution is
lazy -- it happens at ``.execute()`` time, not during query construction:

.. code-block:: python

   # Uses the pool registered as "warehouse" instead of "default"
   query = (
       Sales.query().metrics(Sales.revenue).using("warehouse")
   )

If no ``.using()`` call is made, Semolina uses the pool registered as ``"default"``.

Execute and read results
------------------------

Call ``.execute()`` to run the query and get back a :py:class:`~semolina.SemolinaCursor`:

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

``.execute()`` validates the query (at least one metric or dimension required), resolves the
pool, runs the SQL, and returns a :py:class:`~semolina.SemolinaCursor`. Call ``.fetchall_rows()``
to get :py:class:`~semolina.Row` objects, or use the raw DBAPI methods (``.fetchall()``,
``.fetchone()``) for tuples.

Fetch methods
~~~~~~~~~~~~~

:py:class:`~semolina.SemolinaCursor` provides both ``Row``-based and raw DBAPI fetch methods:

.. code-block:: python

   # Row objects (primary pattern)
   rows = cursor.fetchall_rows()  # list[Row]
   row = cursor.fetchone_row()  # Row | None
   batch = cursor.fetchmany_rows(10)  # list[Row]

   # Raw DBAPI tuples
   raw = cursor.fetchall()  # list[tuple]
   raw_one = cursor.fetchone()  # tuple | None

   # Context manager (closes cursor + connection on exit)
   with Sales.query(
       metrics=[Sales.revenue]
   ).execute() as cursor:
       rows = cursor.fetchall_rows()

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

   SELECT AGG("revenue"), "country"
   FROM "sales"
   GROUP BY ALL

.. tip::

   ``.to_sql()`` always uses Snowflake-style syntax (``AGG()``, double-quoted identifiers)
   regardless of which pool is registered. Use it for verifying query structure during
   development, not for previewing dialect-specific SQL output.

Fork queries with immutable chaining
-------------------------------------

Every method returns a **new** query instance. The original is unchanged, so you can
fork a base query into specialized variants:

.. code-block:: python

   # Build a base query once
   base = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )

   # Fork into specialised variants -- base is unchanged
   us_only = base.where(Sales.country == "US")
   top_10 = base.limit(10)
   us_top_10 = base.where(Sales.country == "US").limit(10)

   # Each variant is independent; base still has no filter or limit
   print(base.to_sql())  # no WHERE, no LIMIT
   print(us_only.to_sql())  # has WHERE
   print(us_top_10.to_sql())  # has WHERE and LIMIT

Build queries incrementally
----------------------------

Because queries are immutable, you can build them up across function boundaries
and store intermediate queries safely:

.. code-block:: python

   def add_revenue_filter(query, threshold: int):
       return query.where(Sales.revenue > threshold)


   base = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )
   filtered = add_revenue_filter(base, 1000)
   cursor = filtered.execute()

See also
--------

- :doc:`filtering` -- field operators and boolean composition
- :doc:`ordering` -- sort results and control row counts
- :doc:`serialization` -- convert results to dictionaries and JSON
- :doc:`models` -- define :py:class:`~semolina.SemanticView` subclasses with field types
- :doc:`backends/overview` -- SQL differences between Snowflake and Databricks
