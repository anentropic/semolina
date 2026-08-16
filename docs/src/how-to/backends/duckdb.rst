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

.. note:: ``semolina codegen`` reads a different section

   ``semolina codegen --backend duckdb`` looks for ``[connections.duckdb]``, not
   ``[connections.default]``. For DuckDB you can skip the file entirely and pass
   ``--database`` instead. See :ref:`howto-codegen-credentials`.

.. note::

   DuckDB defaults to ``pool_size=1``. In-memory databases
   (``":memory:"``) are isolated per connection, so
   ``pool_size > 1`` with ``":memory:"`` raises a
   ``ValidationError``. Use a file-backed database if you need
   multiple connections.

Configure manually
-------------------

When the database path comes from your own code rather than a
TOML file, pass a config object to
:py:func:`~semolina.config.create_engine`:

.. code-block:: python

   from adbc_poolhouse import DuckDBConfig

   from semolina import register, create_engine

   engine = create_engine(
       DuckDBConfig(database="/path/to/warehouse.db")
   )
   register("default", engine)

Run a query
-----------

Once an engine is registered, the query API works the same as
any backend:

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
engine is built through :py:func:`~semolina.config.create_engine`. You do
not need to run ``INSTALL`` or ``LOAD`` manually.

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
