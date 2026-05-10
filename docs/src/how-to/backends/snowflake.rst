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

Then load and register the pool:

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = (
       pool_from_config()
   )  # reads [connections.default]
   register("default", pool, dialect=dialect)

.. tip::

   Use ``pool_from_config(connection="analytics")`` to load a named connection section
   other than ``default``.

Configure manually
-------------------

When credentials come from a vault or secrets manager, construct the pool directly:

.. code-block:: python

   from adbc_poolhouse import SnowflakeConfig, create_pool
   from semolina import register

   config = SnowflakeConfig(
       account="xy12345.us-east-1",
       user="myuser",
       password="mypassword",
       database="analytics",
       warehouse="compute_wh",
   )
   pool = create_pool(config)
   register("default", pool, dialect="snowflake")

Run a query
-----------

Once a pool is registered, the query API works the same as any backend:

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
       print(row.country, row.revenue)

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
- :ref:`howto-warehouse-testing` -- test queries with ``MockEngine``
