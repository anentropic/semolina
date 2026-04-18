Semolina
========

**Semolina: the ORM for your Semantic Layer.**

Typed models in Python, supporting IDE autocomplete, and a Django-like fluent query interface for the semantic layer of your data warehouse backend.

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Get started in 5 minutes
      :link: tutorials/installation
      :link-type: doc

      Install Semolina and write your first query.

   .. grid-item-card:: Define models
      :link: how-to/models
      :link-type: doc

      Map :py:class:`~semolina.Metric` and :py:class:`~semolina.Dimension` fields to your warehouse semantic views.

   .. grid-item-card:: Build queries
      :link: how-to/queries
      :link-type: doc

      Chain ``.metrics()``, ``.dimensions()``, ``.where()``, ``.order_by()``, ``.limit()``.

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
       register,
       pool_from_config,
   )


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   pool, dialect = pool_from_config()  # reads .semolina.toml
   register("default", pool, dialect=dialect)

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

.. toctree::
   :maxdepth: 2
   :hidden:

   tutorials/index
   how-to/index
   reference/index
   explanation/index
