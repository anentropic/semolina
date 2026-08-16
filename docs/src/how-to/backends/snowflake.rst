.. _howto-backends-snowflake:

How to connect to Snowflake
===========================

Install the Snowflake extra
---------------------------

.. code-block:: bash

   pip install semolina[snowflake]
   # or
   uv add "semolina[snowflake]"

The Snowflake extra installs ``adbc-poolhouse[snowflake]``, which provides the ADBC
Snowflake driver and connection pooling.

Configure with .semolina.toml (recommended)
--------------------------------------------

Create a ``.semolina.toml`` file in your project root:

.. code-block:: toml

   # .semolina.toml
   [connections.default]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "myuser"
   password = "mypassword"
   database = "analytics"
   warehouse = "compute_wh"
   # role = ""
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
     - Must be ``"snowflake"``
   * - ``account``
     - ``str``
     - Yes
     - Account identifier with region (e.g. ``xy12345.us-east-1``)
   * - ``user``
     - ``str``
     - Yes
     - Snowflake username
   * - ``password``
     - ``str``
     - Yes
     - Snowflake password
   * - ``database``
     - ``str``
     - No
     - Default database
   * - ``warehouse``
     - ``str``
     - No
     - Compute warehouse name
   * - ``role``
     - ``str``
     - No
     - Role to activate for the session
   * - ``schema``
     - ``str``
     - No
     - Default schema

.. note::

   ``database`` and ``warehouse`` are optional for the query engine: a fully-qualified
   view name supplies the database, and the warehouse can fall back to your Snowflake
   user's default. ``semolina codegen`` is stricter and requires both -- see
   :ref:`howto-codegen-credentials`.

Connection pooling is tuned with the shared ``pool_size``, ``max_overflow``,
``timeout``, and ``recycle`` fields, documented under
:ref:`reference-config-common-fields`.

Then build and register an engine:

.. code-block:: python

   from semolina import register, create_engine

   register(
       "default", create_engine("default")
   )  # reads [connections.default]

.. tip::

   Use ``create_engine("analytics")`` to load a named connection section other
   than ``default``.

.. note:: ``semolina codegen`` needs a ``[connections.snowflake]`` section

   The section above is named ``default``, which is what
   :py:func:`~semolina.config.create_engine` looks for. ``semolina codegen --backend
   snowflake`` looks for ``[connections.snowflake]`` instead and exits ``2`` if it is
   absent. If you plan to run codegen, add that section too. See
   :ref:`howto-codegen-credentials`.

Configure manually
-------------------

When credentials come from a vault or secrets manager, pass a config object to
:py:func:`~semolina.config.create_engine`:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig

   from semolina import register, create_engine

   engine = create_engine(
       SnowflakeConfig(
           account="xy12345.us-east-1",
           user="myuser",
           password="mypassword",
           database="analytics",
           warehouse="compute_wh",
       )
   )
   register("default", engine)

Run a query
-----------

Once an engine is registered, the query API works the same as any backend:

.. code-block:: python

   from semolina import SemanticView, Metric, Dimension


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )
   for row in cursor.fetchall_rows():
       print(row["COUNTRY"], row['AGG("REVENUE")'])

.. warning:: Snowflake result columns are upper case and unaliased

   Semolina adds no ``AS`` aliases, so Snowflake names each column after the expression
   that produced it and folds unquoted identifiers to upper case. A dimension arrives as
   ``COUNTRY`` and a metric as ``AGG("REVENUE")``, quotes included. ``row.revenue``
   raises ``AttributeError`` here even though it works against DuckDB. See
   :ref:`howto-result-column-names`.

Generated SQL
-------------

Snowflake SQL uses ``AGG()`` for metrics and double-quoted identifiers:

.. code-block:: sql

   SELECT AGG("revenue"), "country"
   FROM "sales"
   GROUP BY ALL

See also
--------

- :ref:`howto-backends-overview` -- compare connection patterns
- :ref:`howto-backends-databricks` -- connect to Databricks metric views
- :ref:`howto-warehouse-testing` -- test queries with a local DuckDB backend
