.. _howto-backends-overview:
.. _howto-backends:

How to configure your warehouse backend
=======================================

Your semantic view lives in Snowflake, Databricks, or DuckDB.
:ref:`tutorial-first-query` pointed at none of them, building a throwaway local DuckDB
file instead. This page swaps that for the real warehouse and leaves the query code
alone.

The steps are the same for every backend: install an extra, describe the connection,
build and register an engine. Only the connection details and the generated SQL differ,
so each step below is written once with a tab per backend. The per-backend sections at
the end cover the settings and quirks that belong to one warehouse only.

Pick your backend
-----------------

.. list-table::
   :header-rows: 1
   :widths: 20 28 30 22

   * - Backend
     - Extra
     - ADBC driver
     - Metric syntax
   * - Snowflake semantic views
     - ``semolina[snowflake]``
     - Installed by the extra
     - ``AGG()``
   * - Databricks metric views
     - ``semolina[databricks]``
     - Separate install from the ADBC Driver Foundry
     - ``MEASURE()``
   * - DuckDB semantic views
     - ``semolina[duckdb]``
     - Installed by the extra
     - ``semantic_view()`` table function

Install the extra
-----------------

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: bash

         pip install "semolina[snowflake]"
         # or
         uv add "semolina[snowflake]"

      The extra installs ``adbc-poolhouse[snowflake]``, which brings the ADBC Snowflake
      driver. Nothing else to fetch.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: bash

         pip install "semolina[databricks]"
         # or
         uv add "semolina[databricks]"

      The extra installs ``databricks-sql-connector[pyarrow]``. It does **not** install
      the ADBC driver, which Databricks distributes through the ADBC Driver Foundry
      rather than PyPI. See :ref:`howto-backends-databricks` below.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: bash

         pip install "semolina[duckdb]"
         # or
         uv add "semolina[duckdb]"

      The extra installs ``duckdb`` and ``pyarrow``. The ``duckdb`` version is pinned,
      because the ``semantic_views`` community extension publishes binaries only for
      specific DuckDB core releases.

Configure with .semolina.toml
-----------------------------

:py:func:`~semolina.config.create_engine` reads its settings from a
``[connections.<name>]`` section of ``.semolina.toml`` in your working directory. The
section's ``type`` selects the backend, and every other key is passed to the matching
``adbc-poolhouse`` config class. That ``type`` value is a member of the
:py:class:`~semolina.dialect.Dialect` enum, so ``"snowflake"``, ``"databricks"`` and
``"duckdb"`` are the accepted values.

Create the file in your project root:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.default]
         type = "snowflake"
         account = "xy12345.us-east-1"
         user = "svc_analytics"
         password = "..."
         database = "analytics"
         warehouse = "compute_wh"
         # role = "analyst"
         # schema = "public"

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.default]
         type = "databricks"
         host = "workspace.cloud.databricks.com"
         http_path = "/sql/1.0/warehouses/abc123"
         token = "dapi..."
         # catalog = "main"
         # schema = "analytics"

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.default]
         type = "duckdb"
         database = "/path/to/warehouse.db"
         # read_only = true

Every section also accepts the shared pool-tuning keys ``pool_size``, ``max_overflow``,
``timeout``, and ``recycle``, listed under :ref:`reference-config-common-fields` and
explained in :ref:`howto-connection-pools`.

Build an engine from that section. ``register=True`` registers it under the connection
name, so the registry key and the TOML section stay the same word:

.. code-block:: python

   from semolina import create_engine

   # reads [connections.default], registers as "default"
   create_engine("default", register=True)

A query with no ``.using()`` clause resolves the engine registered as ``"default"``.
Pass ``register="reports"`` to pick a different registry name, and see
:ref:`howto-connection-pools` for the ``with`` block that unregisters the engine and
disposes its pool at the end of a scope.

.. tip::

   ``create_engine()`` with no argument is the same as ``create_engine("default")``.
   Pass another section name to load it instead, and ``config_path=`` to read a file
   somewhere other than ``./.semolina.toml``:

   .. code-block:: python

      engine = create_engine(
          "reports", config_path="config/warehouse.toml"
      )

.. note:: ``semolina codegen`` picks its section differently

   :py:func:`~semolina.config.create_engine` looks up a section by *connection name*, so
   ``create_engine("default")`` reads ``[connections.default]``. ``semolina codegen``
   looks one up by *backend type*, so ``--backend snowflake`` reads
   ``[connections.snowflake]``. It also fills any missing field from ``SNOWFLAKE_*`` /
   ``DATABRICKS_*`` environment variables or a ``.env`` file, and exits ``2`` when a
   required field is missing from all of them. ``--backend duckdb`` reads no section at
   all -- pass ``--database`` or set ``DUCKDB_DATABASE``. See
   :ref:`howto-codegen-credentials`.

Configure from a config object
------------------------------

Pass an ``adbc-poolhouse`` config object instead of a name when credentials come from a
vault, a secrets manager, or your own code. The dialect is derived from the config
class, so there is no backend to select by hand:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         from adbc_poolhouse import SnowflakeConfig

         from semolina import create_engine

         create_engine(
             SnowflakeConfig(
                 account="xy12345.us-east-1",
                 user="svc_analytics",
                 password="...",
                 database="analytics",
                 warehouse="compute_wh",
             ),
             register=True,
         )

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         from adbc_poolhouse import DatabricksConfig

         from semolina import create_engine

         create_engine(
             DatabricksConfig(
                 host="workspace.cloud.databricks.com",
                 http_path="/sql/1.0/warehouses/abc123",
                 token="dapi...",
             ),
             register=True,
         )

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         from adbc_poolhouse import DuckDBConfig

         from semolina import create_engine

         create_engine(
             DuckDBConfig(database="/path/to/warehouse.db"),
             register=True,
         )

A config object carries no section name, so ``register=True`` registers these engines as
``"default"``. Pass a string instead -- ``register="reports"`` -- to name one yourself.

:py:func:`~semolina.config.create_async_engine` takes the same two argument forms and
returns an :py:class:`AsyncEngine <semolina.engines.abase.AsyncEngine>`. It needs the
``semolina[async]`` extra; see :ref:`howto-connection-pools`.

Run a query
-----------

Once an engine is registered, the query API is identical across backends:

.. code-block:: python

   from semolina import Dimension, Metric, SemanticView


   class Sales(SemanticView, view="sales"):
       revenue = Metric()
       country = Dimension()


   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .execute()
   )

What the result columns are *called* is not identical. Semolina adds no ``AS`` aliases,
so a row's keys are the column names the driver reports, which each warehouse derives
from the expression that produced them:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         for row in cursor.fetchall_rows():
             print(row["COUNTRY"], row['AGG("REVENUE")'])

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         for row in cursor.fetchall_rows():
             print(row["country"], row["measure(revenue)"])

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         for row in cursor.fetchall_rows():
             print(row.country, row.revenue)

.. warning:: ``row.revenue`` is DuckDB-only

   Attribute access works on DuckDB because ``semantic_view()`` hands the metric back
   under its declared name. Snowflake answers ``AGG("REVENUE")`` and Databricks answers
   ``measure(revenue)``, neither of which is a Python identifier, so ``row.revenue``
   raises ``AttributeError`` against both. This is the one place the query API's
   backend-agnosticism stops. See :ref:`howto-result-column-names`, or use
   :ref:`howto-typed-results` to get the same field names on every backend.

Inspect the generated SQL
-------------------------

``.to_sql()`` renders SQL for any dialect without connecting to a warehouse, which is
the quickest way to see what a backend will receive. It defaults to the Snowflake
dialect, so pass ``dialect=`` to preview another:

.. code-block:: python

   query = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )
   print(query.to_sql(dialect="databricks"))

The three dialects render as:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: sql

         SELECT AGG("REVENUE"), "COUNTRY"
         FROM "SALES"
         GROUP BY ALL

      Metrics are wrapped in ``AGG()``, identifiers are double-quoted, and unquoted
      names are folded to upper case before quoting.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: sql

         SELECT MEASURE(`revenue`), `country`
         FROM `sales`
         GROUP BY ALL

      Metrics are wrapped in ``MEASURE()`` and identifiers are backtick-quoted, with no
      case folding.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: sql

         SELECT *
         FROM semantic_view('sales', dimensions := ['country'], metrics := ['revenue'])

      There is no ``AGG()`` or ``MEASURE()`` wrapper. The ``semantic_view()`` table
      function takes the field names as string literals and aggregates internally.

.. _howto-backends-snowflake:

Snowflake
---------

Connection fields
~~~~~~~~~~~~~~~~~

``account`` is the only field ``SnowflakeConfig`` requires. Everything else depends on
which authentication method and session scope you want:

.. list-table::
   :header-rows: 1
   :widths: 22 14 14 50

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"snowflake"`` in a TOML section
   * - ``account``
     - ``str``
     - Yes
     - Account identifier, region included (e.g. ``xy12345.us-east-1``)
   * - ``user``
     - ``str``
     - No
     - Username. Needed by every auth method except workload identity
   * - ``password``
     - ``str``
     - No
     - Password, for basic auth
   * - ``private_key_path``
     - ``str``
     - No
     - Path to a PKCS1/PKCS8 key file, for key-pair auth. ``~`` is expanded
   * - ``auth_type``
     - ``str``
     - No
     - ``auth_jwt``, ``auth_oauth``, ``auth_okta``, ``auth_pat``, and others
   * - ``database``
     - ``str``
     - No
     - Default database
   * - ``schema``
     - ``str``
     - No
     - Default schema
   * - ``warehouse``
     - ``str``
     - No
     - Compute warehouse that runs the query
   * - ``role``
     - ``str``
     - No
     - Role activated for the session

``role`` is worth setting explicitly in a service. Semantic views are privilege-scoped,
so an engine that connects under the user's default role can see a different set of
views from the one you tested against.

.. note::

   Semolina requires neither: ``account`` is the only field ``SnowflakeConfig`` insists
   on, and ``semolina codegen`` builds the same config querying does. What they change is
   what the connection can resolve. A fully-qualified view name supplies the database, and
   the warehouse falls back to your Snowflake user's default -- so a session with no
   warehouse of either kind cannot run a query. Introspection issues ``SHOW COLUMNS IN
   VIEW``, which needs a three-part ``database.schema.view`` name; Semolina prepends the
   configured ``database`` when you pass fewer parts, so without it you have to qualify
   the view yourself. See :ref:`howto-codegen-credentials`.

.. _howto-backends-databricks:

Databricks
----------

.. important:: The ADBC driver is a separate install

   Databricks distributes its ADBC driver through the `ADBC Driver Foundry
   <https://adbc-drivers.org/drivers/databricks/>`_ rather than PyPI, so
   ``pip install "semolina[databricks]"`` cannot fetch it and neither can any other extra.
   You install it with ``dbc``, the Foundry's own CLI:

   .. code-block:: bash

      uv tool install dbc     # or: pipx install dbc
      dbc install databricks

   The driver is then found by name through the ADBC driver manifest -- there is no path
   to configure. If it is missing, the first connection fails with an ``ImportError``
   pointing at the Foundry docs, rather than a connection or auth error.

   The rest of this page assumes the driver is installed.

Connection fields
~~~~~~~~~~~~~~~~~

``DatabricksConfig`` accepts two connection forms and requires one of them in full:
either ``uri`` on its own, or all three of ``host``, ``http_path``, and ``token``.
Supplying neither raises a validation error when the config is built.

.. list-table::
   :header-rows: 1
   :widths: 22 14 14 50

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"databricks"`` in a TOML section
   * - ``uri``
     - ``str``
     - One form
     - Full DSN, ``databricks://token:<token>@<host>:443/<http-path>``
   * - ``host``
     - ``str``
     - Other form
     - Workspace hostname (e.g. ``adb-123.azuredatabricks.net``)
   * - ``http_path``
     - ``str``
     - Other form
     - SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/abc123``)
   * - ``token``
     - ``str``
     - Other form
     - Personal access token, starting with ``dapi``
   * - ``auth_type``
     - ``str``
     - No
     - ``OAuthU2M`` (browser) or ``OAuthM2M`` (service principal). Omit for PAT auth
   * - ``client_id``
     - ``str``
     - No
     - Service principal client ID, for ``OAuthM2M``
   * - ``client_secret``
     - ``str``
     - No
     - Service principal client secret, for ``OAuthM2M``
   * - ``catalog``
     - ``str``
     - No
     - Default Unity Catalog
   * - ``schema``
     - ``str``
     - No
     - Default schema

.. warning:: ``catalog`` and ``schema`` are ignored in URI mode

   In the decomposed form, ``catalog`` and ``schema`` are appended to the generated DSN
   as query parameters, which is how the Databricks driver picks up a default namespace.
   A ``uri`` you supply yourself is passed through untouched, so anything you want in
   scope has to already be in that string.

Use Unity Catalog three-part names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Databricks resolves objects through
`Unity Catalog <https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html>`_,
a three-level namespace of ``catalog.schema.view``. Setting ``catalog`` and ``schema``
on the connection is one way to reach a view. The other is to qualify it in the model,
which keeps the model portable across connections:

.. code-block:: python

   from semolina import Dimension, Metric, SemanticView


   class Sales(SemanticView, view="main.analytics.sales"):
       revenue = Metric()
       country = Dimension()

Semolina quotes each part separately rather than treating the dotted string as one
identifier:

.. code-block:: sql

   SELECT MEASURE(`revenue`), `country`
   FROM `main`.`analytics`.`sales`
   GROUP BY ALL

Generate a model from a metric view
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``semolina codegen --backend databricks <view>`` runs
``DESCRIBE TABLE EXTENDED ... AS JSON`` over the same ADBC pool and writes a
:py:class:`~semolina.models.SemanticView` subclass. Measures become
:py:class:`~semolina.fields.Metric` fields and dimensions become
:py:class:`~semolina.fields.Dimension` fields. A column type with no clean Python
equivalent is emitted with a ``TODO`` annotation for you to fill in. See
:ref:`howto-codegen`.

.. _howto-backends-duckdb:

DuckDB
------

DuckDB stands in for a warehouse throughout the tutorials, and it is also a backend you
can ship on. Shipping on it means a database file you keep, rather than the throwaway
:ref:`tutorial-first-query` builds. For the in-memory fixture a test suite wants
instead, see :ref:`howto-warehouse-testing`.

Connection fields
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 14 14 50

   * - Field
     - Type
     - Required
     - Description
   * - ``type``
     - ``str``
     - Yes
     - Must be ``"duckdb"`` in a TOML section
   * - ``database``
     - ``str``
     - No
     - File path or ``":memory:"`` (default: ``":memory:"``)
   * - ``read_only``
     - ``bool``
     - No
     - Open the database in read-only mode (default: ``false``)

.. warning:: An in-memory database caps the pool at one connection

   DuckDB isolates in-memory databases per connection, so several pooled connections
   would each see a different empty database rather than sharing one. ``:memory:``
   therefore defaults ``pool_size`` to 1, and asking for more raises a
   ``ValidationError`` when the config is built. A file path defaults to 5, like the
   other backends, and can be raised. Use a file whenever you need concurrency --
   including on the async path, where a single connection serializes every query behind
   one slot.

The semantic_views extension
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DuckDB's ``semantic_view()`` table function comes from the ``semantic_views`` community
extension. :py:func:`~semolina.config.create_engine` runs
``INSTALL semantic_views FROM community`` and ``LOAD semantic_views`` on each new
connection in the pool, so you do not need to install or load it yourself. ``INSTALL``
is a no-op once the extension is cached locally.

The ``semolina[duckdb]`` extra pins its DuckDB version deliberately: the community
extension publishes binaries only for specific DuckDB core releases, and a mismatched
pair fails to load.

.. note:: Commit after ``CREATE SEMANTIC VIEW`` on a shared connection

   If you create a semantic view and query it on the same connection, call ``commit()``
   after the DDL. ADBC connections open with ``autocommit=False``, and the extension
   expands ``semantic_view()`` on a separate read connection that sees only committed
   state, so an uncommitted view looks like a missing one. Code that creates views
   through a separate session, or that sets ``autocommit=True``, is unaffected.

See also
--------

- :ref:`tutorial-first-query` -- the query code that runs unchanged above any of these
  engines
- :ref:`howto-connection-pools` -- pool sizing, engine lifecycle, and several named
  engines at once
- :ref:`howto-warehouse-testing` -- run your query code against a local DuckDB fixture
  instead of a warehouse
- :ref:`howto-typed-results` -- get the same field names on every backend
- :ref:`howto-codegen-credentials` -- the credentials ``semolina codegen`` reads, and how
  they differ from these
- :ref:`explanation-semantic-views` -- what a semantic view is in each warehouse
- :ref:`explanation-duckdb-vs-warehouse` -- what a query that works on DuckDB proves
  about the same query on Snowflake, and what it does not
- :ref:`reference-config` -- the full ``.semolina.toml`` file format
