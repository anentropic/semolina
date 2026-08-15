.. _howto-codegen-credentials:

How to configure codegen credentials
======================================

``semolina codegen`` connects to your warehouse to introspect semantic views. It reads
the same ``.semolina.toml`` file your application engines use, and the same
``SNOWFLAKE_*`` / ``DATABRICKS_*`` environment variables and optional ``.env`` file fill
any field the section omits.

**It does not read the same section.** ``--backend snowflake`` reads
``[connections.snowflake]``, ``--backend databricks`` reads
``[connections.databricks]``, and ``--backend duckdb`` reads ``[connections.duckdb]``:
the section name always matches the backend. :py:func:`~semolina.config.create_engine`,
by contrast, defaults to ``[connections.default]`` and takes any section name you pass
it.

.. warning::

   A ``.semolina.toml`` containing only ``[connections.default]`` is enough for your
   application and **not** enough for codegen, which exits ``2`` with "connection config
   missing or invalid". Add a backend-named section alongside it. The two can hold
   different credentials, which is useful when codegen runs under a read-only role.

Configure in .semolina.toml
---------------------------

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.snowflake]
         type = "snowflake"
         account = "xy12345.us-east-1"
         user = "svc_codegen"
         password = "..."
         database = "analytics"
         warehouse = "compute_wh"
         # role = "codegen_role"

      For key-pair auth, drop ``password`` and point at your private key:

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.snowflake]
         type = "snowflake"
         account = "xy12345.us-east-1"
         user = "svc_codegen"
         private_key_path = "/keys/rsa_key.p8"
         # private_key_passphrase = "..."
         database = "analytics"
         warehouse = "compute_wh"

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.databricks]
         type = "databricks"
         host = "workspace.cloud.databricks.com"
         http_path = "/sql/1.0/warehouses/abc123"
         token = "dapi..."
         catalog = "main"

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: toml
         :caption: .semolina.toml

         [connections.duckdb]
         type = "duckdb"
         database = "/path/to/warehouse.db"

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake

.. note::

   ``warehouse`` and ``database`` are required for Snowflake codegen: the
   warehouse runs the introspection query and the database resolves the view
   name. The query connection pool is more relaxed and treats both as optional;
   see :ref:`howto-backends-snowflake`.

Configure with environment variables
------------------------------------

Each field also reads from a prefixed environment variable, so you can skip the
TOML file entirely. Values in ``[connections.<backend>]`` take precedence over
the environment, which takes precedence over a ``.env`` file.

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. list-table::
         :header-rows: 1

         * - Variable
           - Required
           - Description
         * - ``SNOWFLAKE_ACCOUNT``
           - Yes
           - Account identifier with region (e.g. ``xy12345.us-east-1``)
         * - ``SNOWFLAKE_USER``
           - Yes
           - Snowflake username
         * - ``SNOWFLAKE_PASSWORD``
           - One of
           - Password (or use key-pair below)
         * - ``SNOWFLAKE_PRIVATE_KEY_PATH``
           - One of
           - Path to a PKCS1 or PKCS8 private key file (key-pair auth)
         * - ``SNOWFLAKE_PRIVATE_KEY_PASSPHRASE``
           - No
           - Passphrase for an encrypted private key
         * - ``SNOWFLAKE_WAREHOUSE``
           - Yes
           - Compute warehouse name
         * - ``SNOWFLAKE_DATABASE``
           - Yes
           - Database name
         * - ``SNOWFLAKE_ROLE``
           - No
           - Role to activate for the session

      .. code-block:: bash

         export SNOWFLAKE_ACCOUNT="xy12345.us-east-1"
         export SNOWFLAKE_USER="svc_codegen"
         export SNOWFLAKE_PASSWORD="..."
         export SNOWFLAKE_DATABASE="analytics"
         export SNOWFLAKE_WAREHOUSE="compute_wh"

         semolina codegen my_schema.sales_view --backend snowflake

   .. tab-item:: Databricks
      :sync: databricks

      .. list-table::
         :header-rows: 1

         * - Variable
           - Required
           - Description
         * - ``DATABRICKS_HOST``
           - Yes
           - Workspace hostname (e.g. ``workspace.cloud.databricks.com``)
         * - ``DATABRICKS_HTTP_PATH``
           - Yes
           - SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/abc123``)
         * - ``DATABRICKS_TOKEN``
           - Yes
           - Personal access token (starts with ``dapi``)
         * - ``DATABRICKS_CATALOG``
           - No
           - Unity Catalog name (defaults to ``main``)

      .. code-block:: bash

         export DATABRICKS_HOST="workspace.cloud.databricks.com"
         export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/abc123"
         export DATABRICKS_TOKEN="dapi..."

         semolina codegen main.analytics.orders_view --backend databricks

      .. note::

         These match the names used by the connection pools (``DATABRICKS_HOST``,
         ``DATABRICKS_TOKEN``), so a single set of variables drives both codegen
         and your application.

   .. tab-item:: DuckDB
      :sync: duckdb

      DuckDB needs no authentication. Pass the database path directly, or set
      ``DUCKDB_DATABASE``:

      .. code-block:: bash

         semolina codegen sales_view --backend duckdb --database /path/to/warehouse.db
         # or
         export DUCKDB_DATABASE="/path/to/warehouse.db"
         semolina codegen sales_view --backend duckdb

      The ``--database`` flag takes precedence over ``DUCKDB_DATABASE``. With
      neither set, codegen stops and asks you for a path: there is no in-memory
      default, because an empty in-memory database has no view to introspect.

Use a .env file
----------------

Place the same prefixed variables in a ``.env`` file in your working directory and
codegen picks it up automatically:

.. code-block:: bash
   :caption: .env

   SNOWFLAKE_ACCOUNT=xy12345.us-east-1
   SNOWFLAKE_USER=svc_codegen
   SNOWFLAKE_PASSWORD=...
   SNOWFLAKE_DATABASE=analytics
   SNOWFLAKE_WAREHOUSE=compute_wh

Point at a ``.env`` file elsewhere with ``SEMOLINA_ENV_FILE``:

.. code-block:: bash

   export SEMOLINA_ENV_FILE="/path/to/staging.env"
   semolina codegen my_schema.sales_view --backend snowflake

Troubleshooting
---------------

**Exit code 2: connection config not found**

Codegen could not assemble connection config for the backend. Check that the
``[connections.<backend>]`` section exists (with a matching section name), or that
the required environment variables are set and spelled correctly.

**Exit code 4: connection failure**

Codegen assembled config but could not authenticate or reach the warehouse. Check
that credentials are valid (try your warehouse's CLI), the key-pair path is
readable, and network access is available (VPN, firewall rules).

See also
--------

- :ref:`howto-codegen` -- full codegen CLI usage and output format
- :ref:`howto-connection-pools` -- ``.semolina.toml`` connections and ``create_engine``
- :ref:`howto-backends-snowflake` -- Snowflake pool configuration
- :ref:`howto-backends-databricks` -- Databricks pool configuration
- :ref:`howto-backends-duckdb` -- DuckDB pool configuration
