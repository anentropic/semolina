How to configure codegen credentials
======================================

``semolina codegen`` needs warehouse credentials to connect and introspect your
semantic views. Credentials are loaded from environment variables, a ``.env`` file,
or a TOML config file -- whichever is found first.

Snowflake environment variables
--------------------------------

Set these environment variables for the ``--backend snowflake`` codegen command:

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
     - Yes
     - Snowflake password
   * - ``SNOWFLAKE_WAREHOUSE``
     - Yes
     - Compute warehouse name
   * - ``SNOWFLAKE_DATABASE``
     - Yes
     - Database name
   * - ``SNOWFLAKE_ROLE``
     - No
     - Role to activate for the session
   * - ``SNOWFLAKE_SCHEMA``
     - No
     - Default schema

.. code-block:: bash

   export SNOWFLAKE_ACCOUNT="xy12345.us-east-1"
   export SNOWFLAKE_USER="svc_codegen"
   export SNOWFLAKE_PASSWORD="..."
   export SNOWFLAKE_DATABASE="analytics"
   export SNOWFLAKE_WAREHOUSE="compute_wh"

   semolina codegen my_schema.sales_view --backend snowflake

Databricks environment variables
---------------------------------

Set these environment variables for the ``--backend databricks`` codegen command:

.. list-table::
   :header-rows: 1

   * - Variable
     - Required
     - Description
   * - ``DATABRICKS_SERVER_HOSTNAME``
     - Yes
     - Workspace hostname (e.g. ``workspace.cloud.databricks.com``)
   * - ``DATABRICKS_HTTP_PATH``
     - Yes
     - SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/abc123``)
   * - ``DATABRICKS_ACCESS_TOKEN``
     - Yes
     - Personal access token (starts with ``dapi``)
   * - ``DATABRICKS_CATALOG``
     - No
     - Unity Catalog name (defaults to ``main``)
   * - ``DATABRICKS_SCHEMA``
     - No
     - Default schema

.. code-block:: bash

   export DATABRICKS_SERVER_HOSTNAME="workspace.cloud.databricks.com"
   export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/abc123"
   export DATABRICKS_ACCESS_TOKEN="dapi..."

   semolina codegen main.analytics.orders_view --backend databricks

Use a .env file
----------------

Place credentials in a ``.env`` file in your working directory. The codegen CLI
picks it up automatically:

.. code-block:: bash
   :caption: .env

   SNOWFLAKE_ACCOUNT=xy12345.us-east-1
   SNOWFLAKE_USER=svc_codegen
   SNOWFLAKE_PASSWORD=...
   SNOWFLAKE_DATABASE=analytics
   SNOWFLAKE_WAREHOUSE=compute_wh

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake

The ``.env`` file uses the same variable names as the environment variables above.
Values set in the actual environment take precedence over ``.env`` file values.

Override the .env file path with SEMOLINA_ENV_FILE
---------------------------------------------------

Set ``SEMOLINA_ENV_FILE`` to point codegen at a ``.env`` file in a different location:

.. code-block:: bash

   export SEMOLINA_ENV_FILE="/path/to/staging.env"
   semolina codegen my_schema.sales_view --backend snowflake

The priority chain for ``.env`` file resolution is:

1. ``SEMOLINA_ENV_FILE`` environment variable (highest priority)
2. Default ``.env`` in the current working directory

Fall back to config files
--------------------------

When environment variables and ``.env`` files are not present, codegen falls back to
TOML config files. It checks these paths in order:

1. ``.semolina.toml`` in the current working directory
2. ``~/.config/semolina/config.toml`` (user-level config)

The config file uses a ``[snowflake]`` or ``[databricks]`` section (not
``[connections.X]`` -- this fallback path is separate from the pool configuration):

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: toml
         :caption: .semolina.toml

         [snowflake]
         account = "xy12345.us-east-1"
         user = "svc_codegen"
         password = "..."
         database = "analytics"
         warehouse = "compute_wh"

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: toml
         :caption: .semolina.toml

         [databricks]
         server_hostname = "workspace.cloud.databricks.com"
         http_path = "/sql/1.0/warehouses/abc123"
         access_token = "dapi..."

.. warning::

   The ``[snowflake]`` and ``[databricks]`` config file sections are a last-resort
   fallback for codegen credentials only. For application connection pools, use
   ``[connections.default]`` with :py:func:`~semolina.pool_from_config` instead.
   See :doc:`backends/snowflake` or :doc:`backends/databricks`.

Troubleshooting
---------------

**Exit code 4 -- connection failure**

Codegen could not authenticate with the warehouse. Check that:

- All required environment variables are set and correctly spelled
- The ``.env`` file is in the current working directory (or ``SEMOLINA_ENV_FILE`` points to it)
- Credentials are valid (try connecting with your warehouse's CLI tool)
- Network access to the warehouse is available (VPN, firewall rules)

**Credentials not found from any source**

The codegen CLI raises :py:class:`~semolina.testing.credentials.CredentialError` when
environment variables, ``.env`` file, and config files all fail to provide required
fields. The error message lists which variables are needed.

See also
--------

- :doc:`codegen` -- full codegen CLI usage and output format
- :doc:`backends/snowflake` -- Snowflake pool configuration
- :doc:`backends/databricks` -- Databricks pool configuration
