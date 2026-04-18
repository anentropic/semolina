How to filter queries
=====================

Filter query results using Python operators and named field methods. Compose
conditions with ``&`` (AND), ``|`` (OR), and ``~`` (NOT) for arbitrary boolean logic.

This guide uses the ``Sales`` model from :doc:`../tutorials/first-query`:

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

         SELECT AGG("revenue")
         FROM "sales"
         WHERE "revenue" > 1000

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         WHERE `revenue` > 1000

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

         WHERE "revenue" BETWEEN 500 AND 2000

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `revenue` BETWEEN 500 AND 2000

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

         WHERE "country" IN ('US', 'CA', 'MX')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` IN ('US', 'CA', 'MX')

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

         WHERE "region" IS NULL

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `region` IS NULL

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

         WHERE "country" LIKE 'U%'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` LIKE 'U%'

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

         WHERE "country" LIKE 'U%'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` LIKE 'U%'

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

         WHERE "region" LIKE '%est'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `region` LIKE '%est'

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

         WHERE "country" ILIKE 'united states'

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE `country` ILIKE 'united states'

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

         SELECT AGG("revenue")
         FROM "sales"
         WHERE ("country" = 'US' OR "country" = 'CA')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`)
         FROM `sales`
         WHERE (`country` = 'US' OR `country` = 'CA')

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

         WHERE ("country" = 'US' AND "revenue" > 500)

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE (`country` = 'US' AND `revenue` > 500)

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

         WHERE NOT ("country" = 'US')

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE NOT (`country` = 'US')

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

         WHERE (("country" = 'US' OR "country" = 'CA')
             AND NOT ("revenue" < 100))

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         WHERE ((`country` = 'US' OR `country` = 'CA')
             AND NOT (`revenue` < 100))

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

Custom lookups require a corresponding ``case`` branch in the SQL compiler to generate
the correct SQL. This is an advanced extension point for users who need to add
backend-specific filter operations.

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

- :doc:`queries` -- the full query API with ``.metrics()``, ``.dimensions()``, ``.execute()``
- :doc:`models` -- field types and how they affect filtering
