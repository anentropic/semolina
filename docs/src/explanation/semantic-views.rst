.. _explanation-semantic-views:

What is a semantic view?
========================

A semantic view is a database object that sits on top of your raw tables and
defines business metrics and dimensions in one governed place. Instead of every
analyst writing their own ``SUM(revenue)`` query and hoping the numbers agree,
the warehouse stores the definition once and everyone queries the same source of
truth.

How warehouses implement them
-----------------------------

**Snowflake** calls them *semantic views*. You create one with
`CREATE SEMANTIC VIEW <https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view>`_,
declaring measures, dimensions, and relationships over your physical tables. The
view generates SQL at query time based on which fields are requested.

**Databricks** calls them *metric views*. You define them with
`CREATE METRIC VIEW <https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-metric-view.html>`_,
listing metrics (with aggregation functions) and dimensions. The concept is the
same: a single definition that produces consistent numbers across queries.

**DuckDB** implements semantic views through the community
`semantic_views extension <https://community-extensions.duckdb.org/extensions/semantic_views.html>`_.
You create them with ``CREATE SEMANTIC VIEW``, declaring metrics, dimensions,
and facts over a source table. At query time, DuckDB uses a ``semantic_view()``
table function instead of a direct ``SELECT`` from the view:

.. code-block:: sql

   SELECT *
   FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])

The function takes the view name and named keyword lists for the fields to query.
Semolina generates this syntax when the registered dialect is DuckDB.

All three approaches share a goal: make business metrics self-service and
trustworthy by centralizing the logic in the warehouse.

.. _explanation-semantic-views-querying:

Why you cannot select from one like a table
--------------------------------------------

A semantic view stores a metric as a *definition*, not as a column. ``revenue``
is the recipe ``SUM(s.revenue)``, and the warehouse only computes it once you
say which dimensions to group by. So ``SELECT revenue FROM sales`` does not mean
anything: there is no column to read. You have to ask for the metric through the
operator that tells the warehouse "evaluate this definition here".

Each warehouse spells that operator differently, and this is the single biggest
surface difference between the three:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Warehouse
     - Asking for a metric
     - Asking for a dimension
   * - Snowflake
     - ``AGG("REVENUE")``
     - ``"COUNTRY"``, with ``GROUP BY ALL``
   * - Databricks
     - ``MEASURE(`revenue`)``
     - ``` `country` ```, with ``GROUP BY ALL``
   * - DuckDB
     - ``metrics := ['revenue']``
     - ``dimensions := ['country']``

Snowflake and Databricks keep the familiar ``SELECT ... FROM view`` shape and
change what may appear in the select list. DuckDB changes the shape instead: you
select from a ``semantic_view()`` table function and pass the field names as
lists, so there is no per-metric operator at all.

This is why Semolina exists as more than a convenience. You write
``.metrics(Sales.revenue).dimensions(Sales.country)`` once, and the dialect for
the registered engine decides whether that becomes ``AGG()``, ``MEASURE()`` or a
keyword list. The :ref:`query builder <howto-queries>` shows the generated SQL
for all three side by side.

The difference does not stop at the SQL you send. It reaches the column names
that come back -- Snowflake returns a column literally named ``AGG("REVENUE")``
-- which is why a result row's keys are not your model's field names. See
:ref:`howto-result-column-names` for that, and
:ref:`explanation-duckdb-vs-warehouse` for the other behaviours that differ once
you move off a local DuckDB.

Where Semolina fits
-------------------

Semolina mirrors your warehouse semantic views as typed Python models. Each model
is a Python class with :py:class:`~semolina.fields.Metric` and
:py:class:`~semolina.fields.Dimension` fields that correspond to the measures and
dimensions defined in your warehouse. A
third field type, :py:class:`~semolina.fields.Fact`, lets you mark raw event-level numerics
separately from categorical dimensions -- see :ref:`howto-models`.

This gives you:

- **IDE autocomplete** on field names (no more guessing column names in raw SQL)
- **Type safety** at the model level (metrics and dimensions are distinct types)
- **Backend-agnostic queries** -- write once, run against Snowflake, Databricks,
  or DuckDB by changing the connection config

Semolina does not replace your warehouse definitions. It reads from them. You
define the semantic view in your warehouse, then create a matching
Semolina model in Python. The
:ref:`codegen CLI <howto-codegen>` can generate these models for you.

See also
--------

- `Snowflake: CREATE SEMANTIC VIEW <https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view>`_ -- Snowflake's semantic view documentation
- `Databricks: CREATE METRIC VIEW <https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-metric-view.html>`_ -- Databricks' metric view documentation
- :ref:`tutorial-installation` -- get started with Semolina
- :ref:`tutorial-first-query` -- define a model and run a query
- :ref:`howto-models` -- field types and model configuration
- :ref:`howto-backends-overview` -- Snowflake, Databricks, and DuckDB connection details
- :ref:`howto-result-column-names` -- what the columns are called when the results come back
- :ref:`explanation-duckdb-vs-warehouse` -- what a DuckDB-only test suite cannot tell you
