.. _howto-filtering:

How to filter queries
=====================

``.where()`` gets two comparisons in :ref:`tutorial-shaping-a-report` and nothing harder.
A field supports more operators than that, plus named methods that have no operator
spelling at all, and they compose with ``&`` (AND), ``|`` (OR) and ``~`` (NOT).

Every condition on this page is a :py:class:`~semolina.filters.Predicate`. That is the type
to annotate against if you pass conditions between functions, and it is what
``.where()`` accepts.

This guide uses the ``Sales`` model from :ref:`tutorial-first-query`:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       cost = Metric()
       country = Dimension()
       region = Dimension()

Use comparison operators
------------------------

Standard Python comparison operators work directly on fields:

.. list-table::
   :header-rows: 1

   * - Operator
     - Meaning
     - Example
   * - ``==``
     - Equals
     - ``Sales.country == "US"``
   * - ``!=``
     - Not equals
     - ``Sales.country != "US"``
   * - ``>``
     - Greater than
     - ``Sales.revenue > 1000``
   * - ``>=``
     - Greater than or equal
     - ``Sales.revenue >= 500``
   * - ``<``
     - Less than
     - ``Sales.revenue < 100``
   * - ``<=``
     - Less than or equal
     - ``Sales.revenue <= 999``

.. code-block:: python

   # Revenue greater than 1000
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.revenue > 1000)
   )

   # Country equals US
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US")
   )

   # Revenue between bounds (explicit)
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where((Sales.revenue >= 500) & (Sales.revenue <= 2000))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE")
         FROM "SALES"
         WHERE "REVENUE" > 1000

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         WHERE `revenue` > 1000

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', metrics := ['revenue'])
         WHERE "revenue" > 1000

.. _howto-filtering-binding:

How filter values reach the warehouse
-------------------------------------

The SQL blocks on this page are previews from ``to_sql()``, which prints values
inline so the statement reads as one piece. That is not how most of them
execute. On two of the three backends the value never appears in the SQL string
at all:

.. list-table::
   :header-rows: 1

   * - Backend
     - How a ``.where()`` value is sent
     - What the driver receives
   * - Snowflake
     - Bound parameter
     - ``WHERE "COUNTRY" = ?`` with ``['US']``
   * - DuckDB
     - Bound parameter
     - ``WHERE "country" = ?`` with ``['US']``
   * - Databricks
     - Inlined as a SQL literal
     - ``WHERE `country` = 'US'`` with no parameters

Databricks is the exception because its ADBC driver rejects bind parameters,
answering ``NOT_IMPLEMENTED: parameterized queries``. Rather than refuse the
query, the ``DatabricksDialect`` renders the value through a single escaping
function, ``render_literal``, which backslash-escapes quotes and backslashes for
Spark SQL. A value of ``US' OR '1'='1`` arrives as the string
``US' OR '1'='1`` -- one country name that matches nothing -- not as extra SQL.

.. note:: Passing a value from an HTTP request

   You do not need to escape or allow-list a filter value before handing it to
   ``.where()``. Both paths above treat it as data: the two binding backends
   never let it near the parser, and the Databricks path escapes it at the one
   audited site.

   Validating the *type* is still yours to do. A value of an unsupported Python
   type -- a ``dict``, say -- raises ``NotImplementedError`` on Databricks when it
   cannot be rendered, but on Snowflake and DuckDB it is handed to the driver,
   which fails later and in its own vocabulary. Coercing request parameters to
   the type the column expects gives you the better error, whichever backend
   you are on.

   What you should still validate is anything that is *not* a value: a column
   name chosen by the caller selects a field rather than filling one in.

.. warning:: ``to_sql()`` output is for reading, not for running

   ``to_sql()`` substitutes each value with its Python ``repr()``. For simple
   values that happens to look like SQL, which is why the previews above are
   readable. For a value containing a single quote it is not SQL at all:
   ``Sales.country == "O'Brien"`` previews as ``WHERE "COUNTRY" = "O'Brien"``,
   and those double quotes name a *column* in Snowflake and DuckDB. Copying a
   preview into a warehouse console can therefore fail on exactly the values
   that need the most care. Execution is unaffected -- it takes the binding or
   ``render_literal`` path instead.

Use named filter methods
------------------------

Fields provide named methods for common SQL operations beyond simple comparisons.

``.between(lo, hi)``
~~~~~~~~~~~~~~~~~~~~~

Range check (inclusive):

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.revenue.between(500, 2000))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "REVENUE" BETWEEN 500 AND 2000

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `revenue` BETWEEN 500 AND 2000

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "revenue" BETWEEN 500 AND 2000

``.in_(values)``
~~~~~~~~~~~~~~~~~

Membership in a collection:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.in_(["US", "CA", "MX"]))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "COUNTRY" IN ('US', 'CA', 'MX')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` IN ('US', 'CA', 'MX')

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "country" IN ('US', 'CA', 'MX')

``.isnull()``
~~~~~~~~~~~~~~

Null check:

.. code-block:: python

   # Find rows where region IS NULL
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.region.isnull())
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "REGION" IS NULL

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `region` IS NULL

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "region" IS NULL

``.like(pattern)`` and ``.ilike(pattern)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQL LIKE pattern matching with ``%`` and ``_`` wildcards. ``.ilike()`` is
case-insensitive:

.. code-block:: python

   # Case-sensitive
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.like("U%"))
   )

   # Case-insensitive
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.ilike("u%"))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "COUNTRY" LIKE 'U%'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` LIKE 'U%'

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "country" LIKE 'U%'

``.startswith(prefix)`` and ``.istartswith(prefix)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prefix match. ``.istartswith()`` is case-insensitive:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.startswith("U"))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "COUNTRY" LIKE 'U%'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` LIKE 'U%'

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "country" LIKE 'U%'

``.endswith(suffix)`` and ``.iendswith(suffix)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Suffix match. ``.iendswith()`` is case-insensitive:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.region.endswith("est"))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "REGION" LIKE '%est'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `region` LIKE '%est'

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "region" LIKE '%est'

``.iexact(value)``
~~~~~~~~~~~~~~~~~~~

Case-insensitive equality (no wildcards):

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.iexact("united states"))
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE "COUNTRY" ILIKE 'united states'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` ILIKE 'united states'

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE "country" ILIKE 'united states'

Combine conditions with OR
---------------------------

Use ``|`` to combine two conditions with OR logic:

.. code-block:: python

   # country = 'US' OR country = 'CA'
   condition = (Sales.country == "US") | (
       Sales.country == "CA"
   )

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(condition)
       .execute()
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE")
         FROM "SALES"
         WHERE ("COUNTRY" = 'US' OR "COUNTRY" = 'CA')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         WHERE (`country` = 'US' OR `country` = 'CA')

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])
         WHERE ("country" = 'US' OR "country" = 'CA')

Combine conditions with AND
-----------------------------

Use ``&`` to combine two conditions with AND logic:

.. code-block:: python

   # country = 'US' AND revenue > 500
   condition = (Sales.country == "US") & (Sales.revenue > 500)

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(condition)
       .execute()
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE ("COUNTRY" = 'US' AND "REVENUE" > 500)

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE (`country` = 'US' AND `revenue` > 500)

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE ("country" = 'US' AND "revenue" > 500)

Multiple ``.where()`` calls are also ANDed together:

.. code-block:: python

   # Equivalent to the & example above
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US")
       .where(Sales.revenue > 500)
       .execute()
   )

You can also pass multiple conditions as arguments to a single ``.where()`` call:

.. code-block:: python

   # Also equivalent -- varargs are ANDed together
   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country == "US", Sales.revenue > 500)
       .execute()
   )

Negate conditions with NOT
---------------------------

Use ``~`` to negate a condition:

.. code-block:: python

   # NOT (country = 'US')
   condition = ~(Sales.country == "US")

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(condition)
       .execute()
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE NOT ("COUNTRY" = 'US')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE NOT (`country` = 'US')

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE NOT ("country" = 'US')

Negation composes with AND and OR:

.. code-block:: python

   # NOT (revenue < 100)
   condition = ~(Sales.revenue < 100)

Build complex nested conditions
--------------------------------

Combine ``|``, ``&``, and ``~`` to express arbitrary conditions. Use parentheses to
control grouping:

.. code-block:: python

   # (country = 'US' OR country = 'CA') AND NOT (revenue < 100)
   condition = (
       (Sales.country == "US") | (Sales.country == "CA")
   ) & ~(Sales.revenue < 100)

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(condition)
       .execute()
   )

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         WHERE (("COUNTRY" = 'US' OR "COUNTRY" = 'CA') AND NOT ("REVENUE" < 100))

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE ((`country` = 'US' OR `country` = 'CA') AND NOT (`revenue` < 100))

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         WHERE (("country" = 'US' OR "country" = 'CA') AND NOT ("revenue" < 100))

Build filters conditionally
-----------------------------

Each ``.where()`` call ANDs with the accumulated filter. This is useful for
conditionally building filters in application code:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )

   if region_filter:
       query = query.where(Sales.region == region_filter)

   if min_revenue:
       query = query.where(Sales.revenue >= min_revenue)

   cursor = query.execute()

``.where()`` also accepts ``None`` as a no-op, making conditional filters a one-liner:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .where(
           Sales.region == region_filter
           if region_filter
           else None
       )
       .where(
           Sales.revenue >= min_revenue
           if min_revenue
           else None
       )
   )

   cursor = query.execute()

Use custom lookups
-------------------

For filter operations not covered by the built-in operators or named methods,
define a custom :py:class:`~semolina.filters.Lookup` subclass and use ``.lookup()``:

.. code-block:: python

   from semolina.filters import Lookup


   class RegexpMatch(Lookup[str]):
       """Regexp match: ``field REGEXP pattern``."""


   # Use with .lookup()
   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .where(Sales.country.lookup(RegexpMatch, "^U.*S$"))
   )

Defining the subclass and building the query both succeed. Compiling it does not:

.. code-block:: python

   query.to_sql()
   # NotImplementedError: Unsupported lookup type: RegexpMatch.
   # Add a case for it in _compile_predicate().

.. warning:: This is not a public extension point yet

   The ``case`` branch that error asks for lives in ``SQLBuilder._compile_predicate`` --
   a private method inside the installed package, not in your code. Reaching it means
   subclassing :py:class:`~semolina.engines.sql.SQLBuilder` to override that private
   method, subclassing the dialect to override ``create_builder()`` so your builder is
   the one used, and then depending on a private API across upgrades.

   So treat ``Lookup`` as machinery the built-in operators are made from, rather than a
   seam you can extend from application code. If you need an operator Semolina does not
   have, open an issue -- adding it upstream is the supported route, and it is a small
   change in the place that already handles every other operator.

.. warning:: Operator precedence: ``&`` binds tighter than ``|``

   Python evaluates ``&`` before ``|`` -- the same precedence as bitwise operators.
   This can produce unexpected results when mixing them:

   .. code-block:: python

      # DANGEROUS: reads as a | (b & c)
      condition = (Sales.country == "US") | (
          Sales.revenue > 500
      ) & (Sales.cost < 100)

      # SAFE: parentheses make intent explicit
      condition = (
          (Sales.country == "US") | (Sales.revenue > 500)
      ) & (Sales.cost < 100)
      condition = (Sales.country == "US") | (
          (Sales.revenue > 500) & (Sales.cost < 100)
      )

   **Always use parentheses when mixing** ``|`` **and** ``&`` **in the same expression.**

See also
--------

- :ref:`tutorial-shaping-a-report` -- ``.where()`` and boolean composition, run step by step
- :ref:`howto-queries` -- the full query API with ``.metrics()``, ``.dimensions()``, ``.execute()``
- :ref:`howto-models` -- field types and how they affect filtering
- :ref:`tutorial-dashboard-api` -- passing a request parameter straight into ``.where()``
- :ref:`explanation-duckdb-vs-warehouse` -- why the backends differ on bind
  parameters and driver behaviour
