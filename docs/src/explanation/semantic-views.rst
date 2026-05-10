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

Where Semolina fits
-------------------

Semolina mirrors your warehouse semantic views as typed Python models. Each model
is a Python class with :py:class:`~semolina.Metric` and :py:class:`~semolina.Dimension`
fields that correspond to the measures and dimensions defined in your warehouse. A
third field type, :py:class:`~semolina.Fact`, lets you mark raw event-level numerics
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
