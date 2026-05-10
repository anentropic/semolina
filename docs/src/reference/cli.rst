.. _reference-cli:

CLI reference
=============

The ``semolina`` command-line tool provides warehouse introspection and code
generation utilities. It is installed as a console script with the
``semolina`` package.

.. code-block:: console

   $ semolina [OPTIONS] COMMAND [ARGS]...

Global options
--------------

``--version``
   Print the installed version and exit.

``--help``
   Show the help message and exit.


``semolina codegen``
--------------------

Introspect warehouse semantic views and generate
:py:class:`~semolina.SemanticView` model classes as Python source code.

.. code-block:: console

   $ semolina codegen [OPTIONS] VIEWS...

Arguments
~~~~~~~~~

``VIEWS``
   One or more schema-qualified view names to introspect
   (e.g. ``my_schema.sales_view``). Required.

Options
~~~~~~~

``--backend``, ``-b`` *TEXT*
   Backend to connect to. Accepts one of:

   - ``snowflake`` -- use the built-in Snowflake engine
   - ``databricks`` -- use the built-in Databricks engine
   - ``duckdb`` -- use the built-in DuckDB engine
   - A dotted import path (e.g. ``mypackage.backends.CustomEngine``) --
     dynamically imported and instantiated with no arguments

   Required.

``--database``, ``-d`` *TEXT*
   Path to a DuckDB database file. Only used with ``--backend duckdb``.
   Falls back to ``DUCKDB_DATABASE`` environment variable if not provided.

Exit codes
~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Code
     - Meaning
   * - 0
     - Success
   * - 1
     - Unexpected error
   * - 2
     - Invalid ``--backend`` value (or omitted)
   * - 3
     - View not found in the warehouse
   * - 4
     - Connection or authentication failure

Environment variables
~~~~~~~~~~~~~~~~~~~~~

``codegen`` reads credentials from environment variables. The required
variables depend on the backend.

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. list-table::
         :header-rows: 1
         :widths: 35 65

         * - Variable
           - Description
         * - ``SNOWFLAKE_ACCOUNT``
           - Account identifier (e.g. ``xy12345.us-east-1``)
         * - ``SNOWFLAKE_USER``
           - Username
         * - ``SNOWFLAKE_PASSWORD``
           - Password
         * - ``SNOWFLAKE_DATABASE``
           - Database name
         * - ``SNOWFLAKE_WAREHOUSE``
           - Warehouse name (optional)
         * - ``SNOWFLAKE_ROLE``
           - Role name (optional)
         * - ``SNOWFLAKE_SCHEMA``
           - Schema name (optional)

   .. tab-item:: Databricks
      :sync: databricks

      .. list-table::
         :header-rows: 1
         :widths: 35 65

         * - Variable
           - Description
         * - ``DATABRICKS_SERVER_HOSTNAME``
           - Workspace hostname
         * - ``DATABRICKS_HTTP_PATH``
           - SQL warehouse HTTP path
         * - ``DATABRICKS_ACCESS_TOKEN``
           - Personal access token
         * - ``DATABRICKS_CATALOG``
           - Unity Catalog name (optional)
         * - ``DATABRICKS_SCHEMA``
           - Schema name (optional)

   .. tab-item:: DuckDB
      :sync: duckdb

      .. list-table::
         :header-rows: 1
         :widths: 35 65

         * - Variable
           - Description
         * - ``DUCKDB_DATABASE``
           - Path to DuckDB database file (fallback for ``--database``)

Set ``SEMOLINA_ENV_FILE`` to load variables from a ``.env`` file instead of
the shell environment. DuckDB does not use ``.env`` files -- pass the
database path with ``--database`` or ``DUCKDB_DATABASE``.

See :ref:`howto-codegen-credentials` for the full credential loading chain,
``.env`` file setup, and TOML config fallback.

Output
~~~~~~

Generated Python source is written to **stdout**. Diagnostic messages
(errors, warnings) go to stderr. Redirect stdout to write a file:

.. code-block:: console

   $ semolina codegen my_schema.sales_view -b snowflake > models.py

The output contains one :py:class:`~semolina.SemanticView` subclass per
introspected view, with typed :py:class:`~semolina.Metric`,
:py:class:`~semolina.Dimension`, and :py:class:`~semolina.Fact` fields.

See also
--------

- :ref:`howto-codegen` -- how to generate models from your warehouse
- :ref:`howto-codegen-credentials` -- credential configuration for codegen
- :ref:`howto-models` -- understanding the generated model classes
