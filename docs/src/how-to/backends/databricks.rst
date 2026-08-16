.. _howto-backends-databricks:

How to connect to Databricks
=============================

Install the Databricks extra
-----------------------------

.. code-block:: bash

   pip install semolina[databricks]
   # or
   uv add "semolina[databricks]"

The extra installs ``databricks-sql-connector[pyarrow]``. Connection pooling comes
from ``adbc-poolhouse``, which Semolina depends on already.

.. important:: The ADBC driver is a separate install

   Databricks distributes its ADBC driver through Foundry rather than PyPI, so
   ``pip install semolina[databricks]`` cannot fetch it and neither can any other
   extra. Install it from Databricks' own distribution before you connect. The
   snippets below assume it is on the machine.

Configure with .semolina.toml (recommended)
--------------------------------------------

Create a ``.semolina.toml`` file in your project root:

.. code-block:: toml

   # .semolina.toml
   [connections.default]
   type = "databricks"
   host = "workspace.cloud.databricks.com"
   http_path = "/sql/1.0/warehouses/abc123"
   token = "dapi..."
   # catalog = ""
   # schema = ""

.. list-table::
   :header-rows: 1

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"databricks"``
   * - ``host``
     - ``str``
     - Yes
     - Databricks workspace hostname (e.g. ``workspace.cloud.databricks.com``)
   * - ``http_path``
     - ``str``
     - Yes
     - SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/{warehouse_id}``)
   * - ``token``
     - ``str``
     - Yes
     - Personal access token starting with ``dapi``
   * - ``catalog``
     - ``str``
     - No
     - Unity Catalog name
   * - ``schema``
     - ``str``
     - No
     - Default schema

Connection pooling is tuned with the shared ``pool_size``, ``max_overflow``,
``timeout``, and ``recycle`` fields, documented under
:ref:`reference-config-common-fields`.

Then build and register an engine:

.. code-block:: python

   from semolina import register, create_engine

   register("default", create_engine("default"))

.. tip::

   Use ``create_engine("analytics")`` to load a named connection section other
   than ``default``.

.. note:: ``semolina codegen`` needs a ``[connections.databricks]`` section

   The section above is named ``default``, which is what
   :py:func:`~semolina.config.create_engine` looks for. ``semolina codegen --backend
   databricks`` looks for ``[connections.databricks]`` instead and exits ``2`` if it is
   absent. If you plan to run codegen, add that section too. See
   :ref:`howto-codegen-credentials`.

Configure manually
-------------------

When credentials come from a vault or secrets manager, pass a config object to
:py:func:`~semolina.config.create_engine`:

.. code-block:: python

   from adbc_poolhouse import DatabricksConfig

   from semolina import register, create_engine

   engine = create_engine(
       DatabricksConfig(
           host="workspace.cloud.databricks.com",
           http_path="/sql/1.0/warehouses/abc123",
           token="dapi...",
       )
   )
   register("default", engine)

Use Unity Catalog three-part names
-----------------------------------

Databricks uses
`Unity Catalog <https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html>`_
for a three-level namespace: ``catalog.schema.view``. Pass a three-part ``view=``
name in your model:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="main.analytics.sales"):
       revenue = Metric()
       country = Dimension()

Each part is quoted separately with backticks in generated SQL:

.. code-block:: sql

   SELECT MEASURE(`revenue`), `country`
   FROM `main`.`analytics`.`sales`
   GROUP BY ALL

Run a query
-----------

Once an engine is registered, the query API works the same as any backend:

.. code-block:: python

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )
   for row in cursor.fetchall_rows():
       print(row["country"], row["measure(revenue)"])

.. warning:: Databricks names a metric column after its ``measure()`` call

   Semolina adds no ``AS`` aliases. A dimension keeps its name, but a metric arrives as
   ``measure(revenue)``, so ``row.revenue`` raises ``AttributeError``. See
   :ref:`howto-result-column-names`.

.. note::

   Introspection works too: ``semolina codegen --backend databricks <view>``
   runs ``DESCRIBE TABLE EXTENDED ... AS JSON`` over the same ADBC pool and
   generates a :py:class:`~semolina.models.SemanticView` model. Measures become
   :py:class:`~semolina.fields.Metric` fields and dimensions become
   :py:class:`~semolina.fields.Dimension` fields; a column type with no clean Python
   equivalent is emitted with a ``TODO`` annotation for you to fill in.

Generated SQL
-------------

Databricks SQL uses ``MEASURE()`` for metrics and backtick-quoted identifiers:

.. code-block:: sql

   SELECT MEASURE(`revenue`), `country`
   FROM `sales`
   GROUP BY ALL

See also
--------

- :ref:`howto-backends-overview` -- compare connection patterns
- :ref:`howto-backends-snowflake` -- connect to Snowflake semantic views
- :ref:`howto-warehouse-testing` -- test queries with a local DuckDB backend
- :ref:`howto-codegen-credentials` -- codegen reads the same ``DATABRICKS_*`` variables
  as the connection above (``DATABRICKS_HOST``, ``DATABRICKS_HTTP_PATH``,
  ``DATABRICKS_TOKEN``)
