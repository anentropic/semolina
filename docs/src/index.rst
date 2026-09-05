.. _overview:

Semolina
========

**Semolina: the ORM for your Semantic Layer.**

Typed models in Python, supporting IDE autocomplete, and a Django-like fluent query
interface for the semantic layer of your data warehouse backend.

Start here
----------

Six tutorials, in order, building one application. They run on a local DuckDB
database, so you can follow all of them without a warehouse.

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: 1. Installation
      :link: tutorial-installation
      :link-type: ref

      Install Semolina and the extra for your backend.

   .. grid-item-card:: 2. Your first query
      :link: tutorial-first-query
      :link-type: ref

      Define a model, register an engine, and read the rows back.

   .. grid-item-card:: 3. Shaping a report
      :link: tutorial-shaping-a-report
      :link-type: ref

      Narrow, sort, and trim the result with ``.where()``, ``.order_by()`` and
      ``.limit()``.

   .. grid-item-card:: 4. Serve a dashboard endpoint
      :link: tutorial-dashboard-api
      :link-type: ref

      A FastAPI service that answers ``GET /revenue`` with a typed JSON body.

   .. grid-item-card:: 5. Test without a warehouse
      :link: tutorial-testing-queries
      :link-type: ref

      Run your real query code against a semantic view built inside the test
      process.

   .. grid-item-card:: 6. Generate models
      :link: tutorial-warehouse-models
      :link-type: ref

      Stop hand-writing the model and the DTO -- have ``semolina codegen``
      read them off the warehouse.

Go further
----------

The how-to guides extend the tutorials one topic at a time, and the explanation
pages cover the ideas underneath. Read them when you hit the thing they cover.

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: New to semantic views?
      :link: explanation-semantic-views
      :link-type: ref

      What they are, and why ``AGG()``, ``MEASURE()`` and ``semantic_view()`` are three
      spellings of the same idea.

   .. grid-item-card:: Configure your warehouse backend
      :link: howto-backends-overview
      :link-type: ref

      Snowflake, Databricks and DuckDB connection settings, and the
      ``.semolina.toml`` that holds them.

   .. grid-item-card:: Define models
      :link: howto-models
      :link-type: ref

      Map :py:class:`~semolina.fields.Metric` and :py:class:`~semolina.fields.Dimension`
      fields to your warehouse semantic views.

   .. grid-item-card:: Build queries
      :link: howto-queries
      :link-type: ref

      Chain ``.metrics()``, ``.dimensions()``, ``.where()``, ``.order_by()``, ``.limit()``.

   .. grid-item-card:: Typed results
      :link: howto-typed-results
      :link-type: ref

      Convert rows into Pydantic models with ``.into()``, or generate the class with
      ``semolina codegen-dto``.

   .. grid-item-card:: API reference
      :link: reference/api/semolina/index
      :link-type: doc

      Auto-generated reference for every public class, function, and field.

Quick example
-------------

.. code-block:: python

   from semolina import (
       SemanticView,
       Metric,
       Dimension,
       create_engine,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   # reads .semolina.toml
   create_engine("default", register=True)

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .limit(10)
       .execute()
   )

   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

Write the query once. Change the ``type`` in your ``.semolina.toml`` and the
same code runs on Databricks.

.. note::

   The attribute spelling above is DuckDB's. Semolina adds no ``AS`` aliases, so
   a row's keys are whatever the driver reports: the same query gives
   ``COUNTRY`` and ``AGG("REVENUE")`` on Snowflake, where ``row.country`` raises
   ``AttributeError``. See :ref:`howto-result-column-names` before you point
   this at a real warehouse, or :ref:`howto-typed-results` for a DTO that
   normalizes the names for you.

.. toctree::
   :maxdepth: 2
   :hidden:

   tutorials/index
   how-to/index
   reference/index
   explanation/index
