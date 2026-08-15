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
:py:class:`~semolina.models.SemanticView` model classes as Python source code.

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

   - ``snowflake`` -- use the built-in Snowflake backend
   - ``databricks`` -- use the built-in Databricks backend
   - ``duckdb`` -- use the built-in DuckDB backend
   - A dotted import path (e.g. ``mypackage.backends.CustomEngine``) --
     dynamically imported and instantiated with no arguments

   Required.

``--database``, ``-d`` *TEXT*
   Path to a DuckDB database file. Only used with ``--backend duckdb``, where it
   is required. Falls back to the ``DUCKDB_DATABASE`` environment variable if not
   provided; with neither set, the command exits ``2``.

``--check``
   Compare a committed model's annotations against the warehouse instead of
   generating one. Requires ``--model``. Writes a per-field report to stderr and
   nothing to stdout. See :ref:`howto-codegen-check`.

``--model`` *PATH*
   Path to the committed Python file to read when ``--check`` is passed. Required
   with ``--check``; either flag on its own exits ``2``.

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
     - Unexpected error, including a missing or unparseable ``--model`` file
   * - 2
     - Invalid option: an unrecognized or omitted ``--backend``, connection config
       that could not be assembled, ``--backend duckdb`` with no database path, or
       ``--check`` and ``--model`` passed without each other
   * - 3
     - View not found in the warehouse
   * - 4
     - Connection or authentication failure
   * - 5
     - Annotation drift found by ``--check``

Environment variables
~~~~~~~~~~~~~~~~~~~~~

``codegen`` reads credentials from the same sources as
:py:func:`~semolina.config.create_engine`: the ``[connections.<backend>]`` section of
``.semolina.toml`` first, then environment variables, then a ``.env`` file. The
variable names below are the config field names with a backend prefix. Which ones
you need depends on the backend.

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
           - Account identifier (e.g. ``xy12345.us-east-1``). Required.
         * - ``SNOWFLAKE_USER``
           - Username
         * - ``SNOWFLAKE_PASSWORD``
           - Password. Use this or the key-pair variables below.
         * - ``SNOWFLAKE_PRIVATE_KEY_PATH``
           - Path to a PKCS8 private key file (key-pair auth)
         * - ``SNOWFLAKE_PRIVATE_KEY_PASSPHRASE``
           - Passphrase for an encrypted private key
         * - ``SNOWFLAKE_DATABASE``
           - Database name. Needed to resolve the view name.
         * - ``SNOWFLAKE_WAREHOUSE``
           - Warehouse name. Needed to run the introspection query.
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
         * - ``DATABRICKS_HOST``
           - Workspace hostname
         * - ``DATABRICKS_HTTP_PATH``
           - SQL warehouse HTTP path
         * - ``DATABRICKS_TOKEN``
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

A ``.env`` file in the working directory is read automatically. Set
``SEMOLINA_ENV_FILE`` to read a different path instead. It fills only the fields
the TOML section and the environment leave unset.

See :ref:`howto-codegen-credentials` for the full credential loading chain,
``.env`` file setup, and TOML config fallback.

Output
~~~~~~

Generated Python source is written to **stdout**. Diagnostic messages
(errors, warnings) go to stderr. Redirect stdout to write a file:

.. code-block:: console

   $ semolina codegen my_schema.sales_view -b snowflake > models.py

The output contains one :py:class:`~semolina.models.SemanticView` subclass per
introspected view, with typed :py:class:`~semolina.fields.Metric`,
:py:class:`~semolina.fields.Dimension`, and :py:class:`~semolina.fields.Fact` fields.


``semolina codegen-dto``
------------------------

Probe an importable query object and generate a Pydantic result DTO as Python
source code, typed and aliased for the columns that query returns on that
backend. See :ref:`howto-dto-codegen`.

.. code-block:: console

   $ semolina codegen-dto [OPTIONS] QUERY_PATHS...

Arguments
~~~~~~~~~

``QUERY_PATHS``
   One or more dotted paths to module-level query objects (e.g.
   ``myapp.queries.revenue_by_region``). Resolving one imports the module that
   holds it, which runs that module. The working directory is appended to
   ``sys.path``. Several paths are emitted into one output block. Required.

Options
~~~~~~~

``--backend``, ``-b`` *TEXT*
   Backend to connect to. Takes the same values as ``codegen``'s ``--backend``:

   - ``snowflake`` -- use the built-in Snowflake backend
   - ``databricks`` -- use the built-in Databricks backend
   - ``duckdb`` -- use the built-in DuckDB backend
   - A dotted import path (e.g. ``mypackage.backends.CustomEngine``) --
     dynamically imported and instantiated with no arguments

   Required.

``--database``, ``-d`` *TEXT*
   Path to a DuckDB database file. Only used with ``--backend duckdb``, where it
   is required. Falls back to the ``DUCKDB_DATABASE`` environment variable.

``--name`` *TEXT*
   Override the generated class name, which otherwise comes from the query
   attribute (``revenue_by_region`` becomes ``RevenueByRegion``). Renames a
   single class, so it takes a single query path; passing it with more than one
   exits ``2``.

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
     - Invalid option -- an unrecognised or omitted ``--backend``, a
       ``QUERY_PATH`` that does not resolve to a query, or ``--name`` passed with
       more than one query
   * - 3
     - View not found in the warehouse
   * - 4
     - Connection or authentication failure
   * - 6
     - Probe failed, or a projected field matched no result column -- no DTO was
       written

There is no ``5``. That code belongs to ``codegen --check``, where it means
annotation drift, and this command has no ``--check``. Codes ``3`` and ``4`` are
reported by an engine's own ``connect()``, which you reach through
``--backend dotted.path.ClassName``; on the three built-in backends a driver
that cannot connect fails inside the probe and exits ``6``.

Environment variables
~~~~~~~~~~~~~~~~~~~~~

``codegen-dto`` reads credentials from the same sources, in the same order, as
``codegen``. See the table above.

Output
~~~~~~

Generated Python source is written to **stdout**. Diagnostic messages go to
stderr. Redirect stdout to write a file:

.. code-block:: console

   $ semolina codegen-dto myapp.queries.revenue_by_region -b snowflake > dtos.py

The output contains one ``pydantic.BaseModel`` subclass per query path, over a
single shared import block, with a provenance header naming the backend that was
probed. No row of your data is fetched.

See also
--------

- :ref:`howto-codegen` -- how to generate models from your warehouse
- :ref:`howto-dto-codegen` -- how to generate a result DTO from a query
- :ref:`howto-codegen-credentials` -- credential configuration for codegen
- :ref:`howto-models` -- understanding the generated model classes
