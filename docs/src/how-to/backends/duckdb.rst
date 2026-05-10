.. _howto-backends-duckdb:

How to connect to DuckDB
=========================

Install the DuckDB extra
-------------------------

.. code-block:: bash

   pip install semolina[duckdb]
   # or
   uv add "semolina[duckdb]"

The DuckDB extra installs ``duckdb`` and ``pyarrow`` for local
semantic view queries.

Configure with .semolina.toml (recommended)
--------------------------------------------

Create a ``.semolina.toml`` file in your project root:

.. code-block:: toml

   # .semolina.toml
   [connections.default]
   type = "duckdb"
   database = "/path/to/warehouse.db"
   # read_only = false

.. list-table::
   :header-rows: 1

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"duckdb"``
   * - ``database``
     - ``str``
     - No
     - File path or ``":memory:"`` (default: ``":memory:"``)
   * - ``read_only``
     - ``bool``
     - No
     - Open in read-only mode (default: ``false``)

Then load and register the pool:

.. code-block:: python

   from semolina import register, pool_from_config

   pool, dialect = pool_from_config()
   register("default", pool, dialect=dialect)

.. tip::

   Use ``pool_from_config(connection="analytics")`` to load a named
   connection section other than ``default``.

.. note::

   DuckDB defaults to ``pool_size=1``. In-memory databases
   (``":memory:"``) are isolated per connection, so
   ``pool_size > 1`` with ``":memory:"`` raises a
   ``ValidationError``. Use a file-backed database if you need
   multiple connections.

Configure manually
-------------------

When credentials come from a vault or secrets manager, construct
the pool directly:

.. code-block:: python

   from adbc_poolhouse import DuckDBConfig, create_pool
   from semolina import register

   config = DuckDBConfig(database="/path/to/warehouse.db")
   pool = create_pool(config)
   register("default", pool, dialect="duckdb")

Run a query
-----------

Once a pool is registered, the query API works the same as any
backend:

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

DuckDB uses a ``semantic_view()`` table function instead of the
``AGG()`` / ``MEASURE()`` syntax used by Snowflake and Databricks:

.. code-block:: sql

   SELECT *
   FROM semantic_view(
       'sales',
       dimensions := ['country'],
       metrics := ['revenue']
   )

For row-level (facts) queries:

.. code-block:: sql

   SELECT *
   FROM semantic_view(
       'sales',
       facts := ['unit_price', 'quantity']
   )

The ``semantic_views`` extension loads automatically when a DuckDB
pool is created through ``pool_from_config()``. You do not need to
run ``INSTALL`` or ``LOAD`` manually.

.. note::

   Semolina requires the ``semantic_views`` community extension
   v0.8.0 or later. Earlier versions failed to resolve table
   references through the ADBC driver. The auto-install runs
   ``INSTALL semantic_views FROM community``, which pulls the latest
   build from the community repository.

.. note::

   If you create a semantic view inside a test fixture and query it
   on the same connection, call ``commit()`` after the
   ``CREATE SEMANTIC VIEW`` statement. ADBC connections default to
   ``autocommit=False``, and the extension expands ``semantic_view()``
   on a separate read connection that only sees committed state, so an
   uncommitted view appears as not found. Production code that creates
   views through a separate session, or that uses ``autocommit=True``,
   does not need this workaround.

See also
--------

- :ref:`howto-backends-overview` -- compare connection patterns
- :ref:`howto-backends-snowflake` -- connect to Snowflake semantic views
- :ref:`howto-backends-databricks` -- connect to Databricks metric views
- :ref:`howto-warehouse-testing` -- test queries with a local DuckDB
  backend
